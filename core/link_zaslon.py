"""Zaslon racunalnika na televizorju (Safeer Desktop Stream, faza 1: slika).

Racunalnik zajame svoj zaslon, ga kodira v H.264 in ga poslje televizorju po **neposredni**
povezavi v domacem omrezju - nic ne gre skozi sredisce in nic v oblak. Povezava je TLS s
samopodpisanim potrdilom Controla, katerega odtis televizor dobi skupaj z enkratnim zetonom v
odgovoru na ukaz `screen.start` (ista pot in isto potrdilo kot pri datotekah).

Format je namenoma preprost: po pozdravu tece gol pretok H.264 (Annex-B), ki ga Android dekodira
strojno (MediaCodec). Brez vsebnika in brez medpomnilnika, ker je cilj cim manjsa zakasnitev.

Pozdrav (prvi vrstici, UTF-8):
    SAFEER-ZASLON <zeton>\\n        <- televizor
    {"w":1920,"h":1080,"fps":30}\\n <- racunalnik, nato gol H.264

Zvok in vnos (tipkovnica, daljinec) v tej fazi nista vkljucena; kar ni narejeno, tudi ne
obljubljamo.
"""

from __future__ import annotations

import glob
import json
import math
import os
import shutil
import socket
import secrets
import select
import signal
import ssl
import subprocess
import sys
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

from core import link_vticnik, link_zaslon_meritve
from core.link_datoteke import TLS_MAPA, zagotovi_potrdilo
from core.link_mediji import dogodek_v_tipko
from core.link_plosek import Plosek
from core.link_vnos import Vnos

#: Vrste okvirjev v pretoku.
OKVIR_SLIKA, OKVIR_ZVOK = 1, 2
#: Obvestilo racunalnika (JSON), npr. {"konec": "zaprto"}: na drugem zaslonu ni vec nobenega
#: programa. Starejsi televizorji okvir te vrste preskocijo.
OKVIR_OBVESTILO = 3
#: Zig zajema za naslednji okvir slike ali zvoka (JSON {"vrsta", "zig_ms", "bajt"}), poslan v ISTEM sendall
#: tik pred njim; enak protokol kot na Windows. Starejsi televizorji okvir neznane vrste preskocijo.
OKVIR_ZIG = 4
#: Ura zigov v glavi: ura_ms (time.monotonic v ms), ista za sliko in zvok.
ZIG_GLAVA = {"okvir": OKVIR_ZIG, "ura": "monotonic_ms"}
#: Zvok: ce stetje bajtov zaostane za uro branja trajno (ves ZVOK_OKNO_MS) za vec kot ZVOK_PORAVNAJ_MS,
#: je pulse izpustil podatke in zig poravnamo. Kratkotrajen zaostanek (zastoj pisanja, sunek iz pulse)
#: ni vrzel in ne premakne ziga.
ZVOK_PORAVNAJ_MS, ZVOK_OKNO_MS = 40.0, 200.0
#: Zvok: ce kos premakne zacetek nazaj za vec kot toliko (sunek, zaostanek), zig tega kosa ni znan.
#: NEPREVERJENO (Z1): spodnja ovojnica ne vidi stalne zakasnitve pulse + ffmpeg + cev (od zajema do
#: branja), zato je zig zvoka pozen za najmanjso zakasnitev v seji; ni odsteta, ker ni izmerjena.
ZVOK_TOCNOST_MS = 1.0
#: Slika: povprecni cas od zajema slike do branja njenega zacetka iz cevi (pretvorba, kodiranje, cev).
#: x264 je izmerjen (x11grab, 1920x1080, glej linux-zigi-izhod.md); vaapi NI izmerjen - None pomeni
#: brez ziga slike, dokler ga ne izmerimo na ciljnem racunalniku.
ZAKASNITEV_SLIKE_MS: Dict[str, Optional[float]] = {"x264": 13.5, "vaapi": None, "hevc": None}
#: Velikost, pri kateri je zakasnitev x264 izmerjena (brez prevzorcenja); drugje zig slike ni znan.
IZMERJENA_SLIKA = (1920, 1080)
#: Koliko casa program na locenem zaslonu caka na televizor, ki je izginil, preden ga zapremo.
OSIROTELO_S = 90
#: Kako pogosto po koncu seje preverimo, ali je drugi zaslon prazen in lahko pospravimo zvok.
ZVOK_POSPRAVI_S = 5.0
#: Merilni dnevnik (zastoj zvoka 4 s): oznaka vrstice, po kateri se iscejo meritve v dnevniku.
CAS_OZNAKA = "SafeerZaslonCas"


def _cas(dogodek: str, seja: int = 0, **polja) -> None:
    """SAMO MERITEV: ena vrstica na dogodek na stderr, monotona ura v ms (+ stenska ura za primerjavo).

    Na obnasanje seje ne vpliva: vsako napako izpisa (zaprt stderr, polna cev ...) pogoltnemo.
    """
    try:
        dodatno = "".join(" %s=%s" % (k, v) for k, v in polja.items())
        sys.stderr.write("%s dogodek=%s t_ms=%d wall_ms=%d seja=%s%s\n" % (
            CAS_OZNAKA, dogodek, time.monotonic_ns() // 1_000_000, time.time_ns() // 1_000_000,
            seja, dodatno))
        sys.stderr.flush()
    except Exception:
        pass


class ProgramaNi(RuntimeError):
    """Televizor je zahteval locen zaslon s programi, a tam ni nicesar vec."""
#: Koliko casa sme biti drugi zaslon prazen, preden sejo koncamo: po zaprtju zadnjega programa
#: in (ce se program sploh ni odprl) od zacetka seje. Temen prazen zaslon je slepa ulica.
PRAZNO_PO_ZAPRTJU_S, PRAZNO_OD_ZACETKA_S = 1.5, 30.0
#: Zvok: surov PCM, ker je najpreprostejsi in brez zakasnitve (1,5 Mb/s je v domacem omrezju nic).
ZVOK_HZ, ZVOK_KANALI = 48000, 2
#: Toliko zaporednih popolnoma tihih koscev zvoka (po 10 ms) se posljemo, preden utihnemo: kratek premor med
#: zvokoma ostane v toku (predvajalnik naprave ne zaide v prazno), dolga tisina pa ne stane nic.
ZVOK_REP_TISINE = 30
#: Kolikor casa cakamo, da se televizor javi, preden sejo zavrzemo.
CAKANJE_S = 30
#: Toliko casa ima, kdor se poveze, za rokovanje TLS in pozdrav; kdor obstane, ne sme zadrzati televizorja.
ROKOVANJE_S = 10
#: Najdlje sme pisanje enega okvirja cakati na televizor. Televizor sam po 10 s tisine sejo konca
#: (ZaslonOdjemalec.TISINA_MS); kdor dvakrat toliko ne vzame nobenega bajta, ga ni vec. Brez te omejitve je
#: seja visela, dokler ni obupalo jedro (cetrt ure ali nikoli), z njo pa zajem in programi na locenem zaslonu.
ROK_PISANJA_S = 20.0
#: Najvecja slika, ki jo posiljamo (televizor je 4K, a 1080p je za namizje dovolj in hitreje).
NAJVEC_SIRINA, NAJVEC_VISINA = 1920, 1080
#: Najvecja slika s HEVC, kadar televizor v screen.start izrecno pove, da jo dekodira ("maxsize": {"hevc": [w, h]}).
#: Samo za PRIVZETA_KAKOVOST in samo s HEVC; brez izjave ostane NAJVEC_SIRINA x NAJVEC_VISINA (stari televizorji).
NAJVEC_HEVC = (3840, 2160)
#: Rok za enkraten preizkus kodirnika hevc_vaapi (s).
HEVC_PREIZKUS_S = 10
#: Najvec razlicnih preizkusov hevc_vaapi (velikosti) na zagon programa. Velikost izbere televizor
#: (maxsize), zato brez meje vsak nov screen.start z drugo izjavo zazene nov ffmpeg (do HEVC_PREIZKUS_S).
HEVC_PREIZKUSOV_NAJVEC = 4
# Kvantizator (qp) je pri tem kodirniku edini vzvod kakovosti - gonilnik zna samo CQP. Izmerjeno na
# mirnem namizju: qp 28 = 0,6 Mb/s, qp 24 = 0,8, qp 20 = 0,9, qp 18 = 1,0, qp 16 = 1,3 Mb/s, in
# procesor je pri vseh enak (strosek je zajem, ne kodiranje). Ker je pasovne sirine v domacem
# omrezju na pretek, so privzete vrednosti izdatne - drobno besedilo mora biti ostro.
KAKOVOSTI = {
    "nizka": {"fps": 30, "bitrate": "4M", "qp": 26, "sirina": 1280, "visina": 720},
    "srednja": {"fps": 30, "bitrate": "8M", "qp": 20, "sirina": 1920, "visina": 1080},
    # Gledalec zdoma na obicajni povezavi 4G (kakovost_za_pot): polnih 60 slik/s, manj podatkov.
    "mobilna": {"fps": 60, "bitrate": "8M", "qp": 20, "sirina": 1920, "visina": 1080},
    "visoka": {"fps": 60, "bitrate": "16M", "qp": 18, "sirina": 1920, "visina": 1080},
    "najvisja": {"fps": 60, "bitrate": "24M", "qp": 16, "sirina": 1920, "visina": 1080},
}
# Privzeto posljemo najboljse, kar zmoreta racunalnik in omrezje: ostrejsa slika je po meritvah
# skoraj zastonj (strosek je zajem, ne kodiranje), pasovne sirine v domacem omrezju pa je na pretek.
# Nizje stopnje ostajajo v dogovoru zato, da se bo mogoce samodejno umakniti, kadar povezava ali
# racunalnik tega ne bosta zmogla - ne zato, da bi uporabnik izbiral.
PRIVZETA_KAKOVOST = "najvisja"
#: Stopnje od najmanj do najvec podatkov.
VRSTNI_RED_KAKOVOSTI = ("nizka", "srednja", "mobilna", "visoka", "najvisja")
#: Gledalec zdoma (prek Huba, Global Link): mera je obicajna povezava 4G, na 5G stopnjo vise. Doma (neposredno) ostane
#: zahtevana stopnja - domace omrezje je praviloma hitrejse. Kljuc je omrezje, ki ga pove naprava (`net`).
KAKOVOST_ZDOMA = {"5g": "visoka"}
KAKOVOST_ZDOMA_PRIVZETO = "mobilna"


def kakovost_za_pot(kakovost: str, prek_huba: bool, omrezje: str = "") -> str:
    """Stopnja kakovosti glede na pot, po kateri je gledalec prisel, in na njegovo omrezje.

    Neposredno (domace omrezje): zahtevana stopnja. Prek Huba (zdoma): najvec stopnja za omrezje gledalca - 5G
    »visoka«, vse drugo (4G, Wi-Fi ali kabel v tujem omrezju, neznano, starejsa naprava) »mobilna«. Nikoli vec, kot
    je naprava zahtevala."""
    if kakovost not in KAKOVOSTI:
        kakovost = PRIVZETA_KAKOVOST
    if not prek_huba:
        return kakovost
    meja = KAKOVOST_ZDOMA.get(str(omrezje or "").strip().lower(), KAKOVOST_ZDOMA_PRIVZETO)
    return kakovost if VRSTNI_RED_KAKOVOSTI.index(kakovost) <= VRSTNI_RED_KAKOVOSTI.index(meja) else meja
#: Kako pogosto seja, ki caka gledalca, pogleda, ali ji je povezavo predal Hub.
PREVERI_PREVZETE_S = 0.2

# Meritve seje (core/link_zaslon_meritve.py; 1. faza: samo merimo, slika, poti in roki ostanejo).
#: Ping gledalcu, ki zna 'rtt' (caps v screen.start; glava toka to potrdi z "rtt": true).
UTRIP_S = 0.5
#: Nit meritev: TCP_INFO vticnice seje enkrat na sekundo, vrstica v dnevnik vsakih 10 s. Na vticnico ne pise nikoli.
MERITVE_S = 1.0
MERITVE_DNEVNIK_S = 10.0
#: Povzetek vsake seje gre v dnevnik, seje s sliko pa se kot ena vrstica JSON v
#: <link_hub.NASTAVITVE_MAPA>/meritve/zaslon-seje.jsonl; SAFEER_ZASLON_MERITVE pove drugo pot.
#: Nad 1 MiB datoteko zamenjamo (stara gre v .1).
POVZETKI_NAJVEC_B = 1024 * 1024


def rtt_vklopljen() -> bool:
    """Ping v toku slike je privzeto vklopljen (za gledalca, ki ga zna); SAFEER_ZASLON_RTT=0 ga izklopi."""
    return os.environ.get("SAFEER_ZASLON_RTT", "1").strip() != "0"


def pot_povzetkov() -> str:
    """Datoteka s povzetki sej: SAFEER_ZASLON_MERITVE ali <NASTAVITVE_MAPA>/meritve/zaslon-seje.jsonl."""
    pot = os.environ.get("SAFEER_ZASLON_MERITVE", "").strip()
    if pot:
        return pot
    from core import link_hub
    return os.path.join(link_hub.NASTAVITVE_MAPA, "meritve", "zaslon-seje.jsonl")


def zapisi_povzetek(povzetek: dict, pot: Optional[str] = None) -> None:
    """Doda vrstico JSON v datoteko povzetkov; nad POVZETKI_NAJVEC_B jo prej zamenja (.1). Napaka diska ni napaka seje."""
    pot = pot or pot_povzetkov()
    try:
        mapa = os.path.dirname(pot)
        if mapa:
            os.makedirs(mapa, exist_ok=True)
        try:
            if os.path.getsize(pot) > POVZETKI_NAJVEC_B:
                os.replace(pot, pot + ".1")
        except OSError:
            pass
        with open(pot, "a", encoding="utf-8") as d:
            d.write(json.dumps(povzetek, ensure_ascii=False) + "\n")
    except OSError:
        pass


#: Kodirniki v ukazu zajema (ffmpeg -c:v ..., wf-recorder -c ...).
_KODIRNIKI = ("h264_vaapi", "hevc_vaapi", "libx264")


def kodirnik_ukaza(ukaz, strojno: bool = False) -> str:
    """Kodirnik, ki ga ukaz zajema res uporabi (h264_vaapi, hevc_vaapi, libx264); brez njega po `strojno`."""
    for del_ukaza in ukaz or ():
        if del_ukaza in _KODIRNIKI:
            return del_ukaza
    return "h264_vaapi" if strojno else "libx264"


def vrsta_kodirnika(kodirnik: str) -> str:
    """'vaapi' (graficna kartica) ali 'x264' (procesor) - kot ga pove glava toka."""
    return "vaapi" if kodirnik.endswith("_vaapi") else "x264"


#: Meje locenega zaslona, kadar ga oblikujemo po napravi, ki gleda (tocke; daljsa in krajsa stranica).
POGLED_NAJMANJ = (640, 360)
POGLED_NAJVEC = (3840, 2160)
#: Toliko navideznih tock po krajsi stranici mora programom ostati tudi pri najvecjem merilu (okna, pogovorna okna).
POGLED_NAJMANJ_NAVIDEZNO = 540
#: Gostota zaslona (Android density), pri kateri so gumbi namiznih programov ravno prav veliki brez merila.
POGLED_GOSTOTA_ENA = 1.5
POGLED_NAJVECJE_MERILO = 3.0


def velikost_za_gledalca(pogled, privzeto: tuple) -> tuple:
    """Velikost locenega zaslona po povrsini, na kateri bo slika (`view` v `screen.start`: w, h v tockah).

    Loceni zaslon je navidezen: naredimo ga natanko v obliki in velikosti zaslona naprave, ki gleda - programi
    zapolnijo cel zaslon, brez crnih robov in brez prevzorcenja. Pravi zaslon racunalnika se ne spremeni.
    Brez podatka (starejsa naprava) ali z nesmiselnim podatkom velja `privzeto`. Stranici sta sodi (H.264).
    """
    if not isinstance(pogled, dict):
        return privzeto
    try:
        w, h = int(pogled.get("w") or 0), int(pogled.get("h") or 0)
    except (TypeError, ValueError):
        return privzeto
    dolga, kratka = max(w, h), min(w, h)
    if (dolga < POGLED_NAJMANJ[0] or kratka < POGLED_NAJMANJ[1]
            or dolga > POGLED_NAJVEC[0] or kratka > POGLED_NAJVEC[1]):
        return privzeto
    return (w // 2 * 2, h // 2 * 2)


def najvecje_merilo(velikost: tuple) -> float:
    """Najvecje merilo locenega zaslona te velikosti: programom mora po krajsi stranici ostati vsaj
    POGLED_NAJMANJ_NAVIDEZNO navideznih tock, sicer okna z najmanjso velikostjo niso vec cela (drsenja ni).
    Na cetrtine navzdol, med 1 in POGLED_NAJVECJE_MERILO."""
    try:
        kratka = min(int(velikost[0]), int(velikost[1]))
    except (TypeError, ValueError, IndexError):
        return 1.0
    m = math.floor(kratka / float(POGLED_NAJMANJ_NAVIDEZNO) * 4 + 1e-9) / 4
    return max(1.0, min(POGLED_NAJVECJE_MERILO, m))


def merilo_za_gledalca(pogled, velikost: tuple) -> float:
    """Merilo izhoda locenega zaslona (sway `output scale`) za napravo, ki gleda.

    Namizni program na gostem zaslonu telefona ima drobne gumbe. Merilo jih poveca, ne da bi se spremenila slika,
    ki jo posiljamo (fizicna locljivost ostane): gostota naprave / 1,5, a najvec toliko, da programom po krajsi
    stranici ostane vsaj POGLED_NAJMANJ_NAVIDEZNO navideznih tock. Na cetrtine navzdol, med 1 in 3. Televizor
    (gledamo ga od dalec, a ima 1920x1080 za namizje) ostane pri 1. Naprava sme merilo povedati sama (`scale`,
    izbira uporabnika) - tudi zanj velja meja prostora (najvecje_merilo).
    """
    if not isinstance(pogled, dict):
        return 1.0

    def stevilo(kljuc: str) -> float:
        try:
            v = float(pogled.get(kljuc) or 0)
        except (TypeError, ValueError):
            return 0.0
        return v if math.isfinite(v) and v > 0 else 0.0

    najvec = najvecje_merilo(velikost)

    def na_cetrtine(m: float) -> float:
        return max(1.0, min(najvec, math.floor(m * 4 + 1e-9) / 4))

    izrecno = stevilo("scale")
    if izrecno:
        return na_cetrtine(izrecno)
    gostota = stevilo("density")
    if not gostota or str(pogled.get("kind") or "").strip().lower() == "tv":
        return 1.0
    return na_cetrtine(gostota / POGLED_GOSTOTA_ENA)


def zakasnitev_slike(vaapi: Optional[str], sirina: int, visina: int, izvor: tuple,
                     kodek: str = "h264") -> Optional[float]:
    """Zakasnitev kodirnika za zig slike na namizju; None, kadar ni izmerjena.

    Izmerjeno je samo x264 pri 1920x1080 brez prevzorcenja (ukaz_ffmpeg: lestvica, ko se velikost
    razlikuje od izvora). Pri drugi velikosti, prevzorcenju ali vaapi zig slike ne gre.
    """
    if kodek != "h264":
        # HEVC (hevc_vaapi) ni izmerjen: brez ziga slike, dokler ga ne izmerimo.
        return ZAKASNITEV_SLIKE_MS.get(kodek)
    if vaapi:
        return ZAKASNITEV_SLIKE_MS["vaapi"]
    if (int(sirina), int(visina)) != IZMERJENA_SLIKA or (int(izvor[0]), int(izvor[1])) != IZMERJENA_SLIKA:
        return None
    return ZAKASNITEV_SLIKE_MS["x264"]


def ura_ms() -> float:
    """Skupna ura zigov za sliko in zvok: monotona ura procesa v ms (kot na Windows)."""
    return time.monotonic() * 1000.0


def _okvir_z_zigom(vrsta: int, zig: Optional[float], bajt: int, vsebina: bytes) -> bytes:
    """Okvir slike ali zvoka; ce zig poznamo, pred njim okvir OKVIR_ZIG. Oboje kot EN niz bajtov za en
    sendall, da ga druga nit ne more vriniti med zig in njegov okvir. `bajt`: koliko bajtov vsebine te
    vrste je slo pred tem okvirjem."""
    if zig is None:
        return _okvir(vrsta, vsebina)
    zig_json = json.dumps({"vrsta": vrsta, "zig_ms": int(round(zig)), "bajt": int(bajt)},
                          separators=(",", ":")).encode("utf-8")
    return _okvir(OKVIR_ZIG, zig_json) + _okvir(vrsta, vsebina)


class ZigiZvoka:
    """Zig zajema prvega vzorca vsakega kosa surovega PCM iz stetja bajtov od prvega kosa.

    Cas branja ni cas zajema: pulse in ffmpeg dajeta kose v sunkih, pisanje na vticnico pa branje
    zadrzi. Velja pa meja: vzorec ne more biti prebran, preden je zajet, zato je
    `prebrano - trajanje kosa` zgornja meja za zig. Zacetek je najvecji, ki tej meji ustreza pri vseh
    dosedanjih kosih (spodnja ovojnica); ce stetje neprekinjeno ZVOK_OKNO_MS zaostaja za vec kot
    ZVOK_PORAVNAJ_MS, so podatki izpadli in zig premaknemo naprej za najmanjsi zaostanek v tem casu.
    Kos, ob katerem se zacetek premakne nazaj (prvi kos, sunek ob zagonu ali po zastoju), ziga nima:
    poslani zigi bi bili sicer prepozni. Televizor naslednji zig poveze z bajti ("bajt").
    Brez ure v notranjosti: cas branja poda klicatelj, zato je deterministicen v preizkusu.
    """

    def __init__(self, hz: int = 48000, kanali: int = 2, bajtov_na_vzorec: int = 2,
                 poravnaj_ms: float = ZVOK_PORAVNAJ_MS, okno_ms: float = ZVOK_OKNO_MS) -> None:
        self._bajtov_na_ms = hz * kanali * bajtov_na_vzorec / 1000.0
        self._poravnaj_ms = poravnaj_ms
        self._okno_ms = okno_ms
        self._zacetek: Optional[float] = None
        self._bajtov = 0
        self._nad_min: Optional[float] = None
        self._nad_od = 0
        self.poravnav = 0
        #: Velikost zadnje poravnave (ms), za dnevnik.
        self.zadnja_poravnava_ms = 0.0
        #: Zadnji poslani zig v celih ms (kot gre na TV): nov zig ne sme biti manjsi.
        self._zadnji_ms: Optional[int] = None
        #: Po poravnavi naprej: do tega stevca bajtov premik zacetka nazaj pomeni, da poravnava ni bila vrzel,
        #: ampak zaloga po zastoju bralca, ki se pocasi prazni.
        self._preizkus_do: Optional[int] = None
        #: Do tega stevca bajtov zig ni znan (zacetek se po napacni poravnavi se vraca nazaj).
        self._dvom_do: Optional[int] = None

    def zig(self, dolzina: int, prebrano_ms: float) -> Optional[float]:
        if dolzina <= 0 or not math.isfinite(prebrano_ms):
            return None
        pred = self._bajtov / self._bajtov_na_ms
        meja = prebrano_ms - dolzina / self._bajtov_na_ms
        znan = self._zacetek is not None and meja - pred >= self._zacetek - ZVOK_TOCNOST_MS
        nazaj = self._zacetek is not None and meja - pred < self._zacetek
        if self._zacetek is None or meja - pred < self._zacetek:
            self._zacetek = meja - pred
        zig = self._zacetek + pred
        zaostanek = meja - zig
        self._bajtov += dolzina
        if nazaj and self._preizkus_do is not None and self._bajtov <= self._preizkus_do:
            # Zacetek gre nazaj kmalu po poravnavi naprej: to je bila zaloga, ne vrzel. Ziga ni, dokler
            # se zacetek ne umiri za cel okno_ms (sicer bi sli znani, a za zalogo prepozni zigi).
            self._dvom_do = self._bajtov + int(round(self._okno_ms * self._bajtov_na_ms))
            self._preizkus_do = self._dvom_do
        if zaostanek <= self._poravnaj_ms:
            self._nad_min = None
        else:
            # Stetje zaostaja: vrzel ali trajna zakasnitev. Iz (dolzina, cas) ju ne locimo, zato zig
            # tega kosa ni znan (pri vrzeli bi bil prezgodnji za celo vrzel).
            znan = False
            if self._nad_min is None:
                self._nad_min, self._nad_od = zaostanek, self._bajtov - dolzina
            else:
                self._nad_min = min(self._nad_min, zaostanek)
            if (self._bajtov - self._nad_od) / self._bajtov_na_ms >= self._okno_ms:
                # Vrzel: od tu naprej stejemo od novega zacetka; zig gre samo naprej.
                self._zacetek += self._nad_min
                self.zadnja_poravnava_ms = self._nad_min
                self._nad_min = None
                self.poravnav += 1
                self._preizkus_do = self._bajtov + int(round(self._okno_ms * self._bajtov_na_ms))
        if self._dvom_do is not None:
            if self._bajtov < self._dvom_do:
                znan = False
            else:
                self._dvom_do = None
        if not znan:
            return None
        # Zig gre na TV zaokrozen na cele ms (_okvir_z_zigom): po zaokrozitvi ne sme iti nazaj.
        zig_ms = int(round(zig))
        if self._zadnji_ms is not None and zig_ms < self._zadnji_ms:
            return None
        self._zadnji_ms = zig_ms
        return zig


#: Vrste enot NAL (H.264), ki odprejo novo sliko, ce pred njimi ze stoji rezina (7.4.1.2.3).
_NAL_PRED_SLIKO = frozenset((6, 7, 8, 9, 14, 15, 16, 17, 18))
#: H.265: vrste, ki odprejo novo sliko, ce pred njimi ze stoji rezina (H.265 7.4.2.4.4): VPS 32, SPS 33,
#: PPS 34, AUD 35, predponski SEI 39, 41..44, 48..55. Pripenski SEI 40, EOS 36, EOB 37 in FD 38 sodijo k
#: tekoci sliki in nove ne odprejo.
_NAL_PRED_SLIKO_HEVC = frozenset((32, 33, 34, 35, 39, 41, 42, 43, 44) + tuple(range(48, 56)))
#: H.265: rezine (VCL) 0..9 in 16..21; 10..15 in 22..31 so rezervirane in jih ne stejemo.
_NAL_REZINA_HEVC = frozenset(tuple(range(0, 10)) + tuple(range(16, 22)))


class ZigiSlike:
    """Zig slike za kos gola H.264 (Annex-B) iz cevi kodirnika: cas branja minus zakasnitev kodirnika.

    Kos dobi zig samo, ce se zacne natanko z zacetkom nove slike in v njem ni zacetka se ene slike;
    sicer (nadaljevanje velike slike, vec slik naenkrat zaradi zaostanka) zig ni znan in okvir 4 ne gre.
    Meje slik iscemo po enotah NAL, tudi kadar je zacetna koda razdeljena med dva kosa.
    """

    def __init__(self, zakasnitev_ms: Optional[float], kodek: str = "h264") -> None:
        self._zakasnitev_ms = zakasnitev_ms
        #: H.265 ima 2 bajta glave enote NAL (vrsta = bajt0 >> 1 & 0x3F), H.264 enega (bajt0 & 0x1F).
        self._hevc = kodek == "hevc"
        self._glava = 2 if self._hevc else 1
        self._rep = b""
        self._po_rezini = False
        self._prvi = True

    def zacetki(self, podatki: bytes) -> List[int]:
        """Odmiki (v `podatki`) zacetkov novih slik; negativen odmik = slika se je zacela v prejsnjem kosu."""
        buf = self._rep + podatki
        osnova = len(self._rep)
        zacetki: List[int] = []
        rep_od = max(0, len(buf) - 4)
        i = buf.find(b"\x00\x00\x01")
        while i != -1:
            if i + 3 + self._glava >= len(buf):
                # Glava ali prvi bajt rezine sta v naslednjem kosu: to kodo obdelamo takrat.
                rep_od = min(rep_od, i - 1 if i > 0 and buf[i - 1] == 0 else i)
                break
            if self._hevc:
                vrsta = (buf[i + 3] >> 1) & 0x3F
                pred_sliko, rezina = _NAL_PRED_SLIKO_HEVC, _NAL_REZINA_HEVC
            else:
                vrsta = buf[i + 3] & 0x1F
                pred_sliko, rezina = _NAL_PRED_SLIKO, (1, 5)
            zacetek = i - 1 if i > 0 and buf[i - 1] == 0 else i
            nova = self._prvi
            if vrsta in pred_sliko:
                nova = nova or self._po_rezini
                self._po_rezini = False
            elif vrsta in rezina:
                # Prvi bit za glavo enote NAL: H.264 first_mb_in_slice == 0 (ue(v) z enim bitom 1),
                # H.265 first_slice_segment_in_pic_flag == 1 - oboje pomeni prvo rezino nove slike.
                nova = nova or (self._po_rezini and bool(buf[i + 3 + self._glava] & 0x80))
                self._po_rezini = True
            if nova:
                self._prvi = False
                zacetki.append(zacetek - osnova)
            i = buf.find(b"\x00\x00\x01", i + 3)
        self._rep = buf[rep_od:]
        return zacetki

    def zig(self, podatki: bytes, prebrano_ms: float) -> Optional[float]:
        zacetki = self.zacetki(podatki)
        if self._zakasnitev_ms is None or zacetki != [0]:
            return None
        return prebrano_ms - self._zakasnitev_ms


def _zaslon_geometrija(display: str) -> Optional[tuple]:
    """Velikost zaslona (xdotool); brez njega ne ugibamo, ampak vrnemo None."""
    if not shutil.which("xdotool"):
        return None
    try:
        okolje = dict(os.environ, DISPLAY=display)
        r = subprocess.run(["xdotool", "getdisplaygeometry"], text=True, capture_output=True,
                           timeout=5, env=okolje)
        deli = r.stdout.split()
        if len(deli) == 2:
            return int(deli[0]), int(deli[1])
    except Exception:
        pass
    return None


def _deljeni_monitor() -> Optional[dict]:
    """X11 z vec monitorji (RandR): primarni monitor v pikah X - deli se ta, ne vsi stisnjeni v eno sliko. En monitor
    ali brez RandR: None (ves zaslon, kot prej)."""
    from core import x11
    try:
        p = x11.Povezava()
    except OSError:
        return None
    try:
        monitorji = p.monitorji()
    finally:
        p.zapri()
    return monitorji[0] if len(monitorji) > 1 else None


#: Kljucna slika: starejsi gledalec jo potrebuje vsako sekundo (enoto, ki jo izpusti, popravi sele ona). Gledalec, ki
#: enot ne izpusca (`caps: ["gop"]`), dobi dolgo skupino: povezava je zanesljiva, kljucna slika pa je pri mirni sliki
#: skoraj ves promet.
GOP_DOLG_S = 10
_HEVC: Dict[str, bool] = {}
#: Kljuc v `_HEVC`: zajem s HEVC je na tem racunalniku ze odpovedal (`hevc_odpovedal`).
_HEVC_ODPOVED = "odpoved"
#: Zacetna koda enote NAL (Annex-B): brez nje v toku zajema ni bilo nobene slike.
ZACETEK_NAL = b"\x00\x00\x01"


def hevc_odpovedal() -> None:
    """Zajem s HEVC je koncal sam in brez ene same slike: do ponovnega zagona Controla ostanemo pri H.264."""
    _HEVC[_HEVC_ODPOVED] = True


def hevc_mozen(ffmpeg: str, vaapi: Optional[str]) -> bool:
    """Ali ta racunalnik HEVC res strojno kodira: enkraten kratek preizkus z ffmpeg, izid si zapomnimo.

    Seznam kodirnikov ni dovolj - `hevc_vaapi` je v ffmpeg tudi tam, kjer ga graficna kartica ali gonilnik ne zmoreta.
    """
    if not ffmpeg or not vaapi or _HEVC.get(_HEVC_ODPOVED):
        return False
    kljuc = "%s|%s" % (ffmpeg, vaapi)
    if kljuc not in _HEVC:
        try:
            r = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-vaapi_device", vaapi,
                                "-f", "lavfi", "-i", "color=black:size=320x240:rate=30", "-frames:v", "3",
                                "-vf", "format=nv12,hwupload", "-c:v", "hevc_vaapi", "-rc_mode", "CQP", "-qp", "24",
                                "-bf", "0", "-f", "null", "-"], capture_output=True, timeout=20,
                               stdin=subprocess.DEVNULL)
            _HEVC[kljuc] = r.returncode == 0
        except Exception:  # noqa: BLE001 - brez preizkusa ostanemo pri H.264
            _HEVC[kljuc] = False
    return _HEVC[kljuc]


#: Izid preizkusa `gpu_lestvica_mozna` po (ffmpeg, naprava); kljuc `_GPU_ODPOVED`: zajem s pomanjsavo na graficni je
#: ze odpovedal (`gpu_odpovedal`).
_GPU: Dict[str, bool] = {}
_GPU_ODPOVED = "odpoved"
#: Pomanjsava na graficni (enaka v preizkusu in v seji): izmerjeno 10. 10. 2026 - glej ukaz_ffmpeg.
SCALE_VAAPI = "scale_vaapi={sirina}:{visina}:format=nv12:mode=default"


def gpu_vklopljena() -> bool:
    """Pomanjsava slike na graficni kartici je privzeto vklopljena; SAFEER_ZASLON_GPU=0 jo izklopi (stara pot)."""
    return os.environ.get("SAFEER_ZASLON_GPU", "1").strip() != "0"


def gpu_odpovedal() -> None:
    """Zajem s pomanjsavo na graficni je koncal sam in brez slike: do ponovnega zagona Controla pomanjsa procesor."""
    _GPU[_GPU_ODPOVED] = True


def gpu_lestvica_mozna(ffmpeg: str, vaapi: Optional[str]) -> bool:
    """Ali zna graficna kartica sliko zaslona sama pretvoriti in pomanjsati (hwupload,scale_vaapi): enkraten kratek
    preizkus z ffmpeg na enaki obliki slike, kot jo da x11grab (bgr0); izid si zapomnimo.

    Izmerjeno 10. 10. 2026 (Intel iHD, 2560x1440 -> 1080p, hevc_vaapi qp18): ffmpeg 74 % CPU namesto 346 % z lanczos
    na procesorju, mirno namizje 0,34 Mbit/s. Na drugih gonilnikih nalaganje bgr0 na graficno morda ne gre - zato
    preizkus in sicer stara pot."""
    if not ffmpeg or not vaapi or _GPU.get(_GPU_ODPOVED) or not gpu_vklopljena():
        return False
    kljuc = "%s|%s" % (ffmpeg, vaapi)
    if kljuc not in _GPU:
        try:
            r = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-vaapi_device", vaapi,
                                "-f", "lavfi", "-i", "color=black:size=640x360:rate=30,format=bgr0", "-frames:v", "3",
                                "-vf", "hwupload," + SCALE_VAAPI.format(sirina=320, visina=180), "-c:v", "h264_vaapi",
                                "-rc_mode", "CQP", "-qp", "24", "-bf", "0", "-f", "null", "-"],
                               # Izhoda ne zbiramo: steje samo izhodna koda. Program, ki bi namesto preizkusa
                               # pisal tok brez konca, bi sicer v nekaj sekundah porabil ves pomnilnik
                               # (izmerjeno 11. 10. 2026: >6 GB v preizkusih z laznim ffmpeg).
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20,
                               stdin=subprocess.DEVNULL)
            _GPU[kljuc] = r.returncode == 0
        except Exception:  # noqa: BLE001 - brez preizkusa ostane pomanjsava na procesorju
            _GPU[kljuc] = False
    return _GPU[kljuc]


def ukaz_pomanjsa_gpu(ukaz) -> bool:
    """Ali ukaz zajema sliko pomanjsa na graficni kartici (scale_vaapi)."""
    return any("scale_vaapi" in str(d) for d in ukaz or ())


#: Preizkusi diagnoze kodirnika (tools/preveri-kodirnik.py): ime -> kodirnik in njegove moznosti. Prvi je danasnji
#: nacin seje; ostali povedo, kaj bi gonilnik se zmogel (-async_depth, -aud, bitna hitrost namesto kvantizatorja).
PREIZKUSI_KODIRNIKA = (
    ("h264_cqp", ["-c:v", "h264_vaapi", "-profile:v", "high", "-rc_mode", "CQP", "-qp", "24"]),
    ("h264_cqp_async_depth_1", ["-c:v", "h264_vaapi", "-profile:v", "high", "-rc_mode", "CQP", "-qp", "24",
                                "-async_depth", "1"]),
    ("h264_cqp_aud", ["-c:v", "h264_vaapi", "-profile:v", "high", "-rc_mode", "CQP", "-qp", "24", "-aud", "1"]),
    ("h264_vbr_4M", ["-c:v", "h264_vaapi", "-profile:v", "high", "-rc_mode", "VBR", "-b:v", "4M"]),
    ("h264_cbr_4M", ["-c:v", "h264_vaapi", "-profile:v", "high", "-rc_mode", "CBR", "-b:v", "4M"]),
    ("hevc_cqp", ["-c:v", "hevc_vaapi", "-profile:v", "main", "-rc_mode", "CQP", "-qp", "24"]),
)


def naprave_vaapi() -> List[str]:
    """Vse naprave za strojno kodiranje (/dev/dri/renderD*), do katerih ima ta uporabnik dostop."""
    try:
        imena = sorted(i for i in os.listdir("/dev/dri") if i.startswith("renderD"))
    except OSError:
        return []
    return [os.path.join("/dev/dri", i) for i in imena if os.access(os.path.join("/dev/dri", i), os.R_OK | os.W_OK)]


def diagnoza_kodirnika(ffmpeg: Optional[str] = None, naprave: Optional[List[str]] = None,
                       zazeni=subprocess.run) -> dict:
    """Kaj strojni kodirnik tega racunalnika res zmore: na vsaki dostopni napravi kratek preizkus (3 slike lavfi,
    kot hevc_mozen) za vsak nacin iz PREIZKUSI_KODIRNIKA. Samo za orodje tools/preveri-kodirnik.py - aplikacija
    tega ne klice. Izid: {"ffmpeg", "naprave": {pot: {preizkus: {"ok", "napaka"}}}, "namigi"}."""
    ffmpeg = ffmpeg or shutil.which("ffmpeg") or ""
    naprave = naprave_vaapi() if naprave is None else list(naprave)
    izid: dict = {"ffmpeg": ffmpeg, "naprave": {}, "namigi": [
        "vainfo --display drm --device /dev/dri/renderD128 | grep -iE 'h264|hevc'",
        "sudo dmesg | grep -iE 'huc|guc'",
        "sudo cat /sys/kernel/debug/dri/0/gt0/uc/huc_info  (pot se lahko razlikuje)"]}
    if not ffmpeg:
        izid["napaka"] = "ffmpeg ni namescen"
        return izid
    if not naprave:
        izid["napaka"] = "ni dostopne naprave /dev/dri/renderD*"
    for naprava in naprave:
        preizkusi = {}
        for ime, moznosti in PREIZKUSI_KODIRNIKA:
            ukaz = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-vaapi_device", naprava,
                    "-f", "lavfi", "-i", "color=black:size=320x240:rate=30", "-frames:v", "3",
                    "-vf", "format=nv12,hwupload"] + moznosti + ["-bf", "0", "-f", "null", "-"]
            try:
                r = zazeni(ukaz, capture_output=True, timeout=20, stdin=subprocess.DEVNULL)
                napaka = (r.stderr or b"")
                if isinstance(napaka, bytes):
                    napaka = napaka.decode("utf-8", "replace")
                preizkusi[ime] = {"ok": r.returncode == 0, "napaka": napaka.strip()[-300:]}
            except Exception as e:  # noqa: BLE001 - diagnoza pove napako, ne pade
                preizkusi[ime] = {"ok": False, "napaka": "%s: %s" % (type(e).__name__, e)}
        izid["naprave"][naprava] = preizkusi
    return izid


def izberi_kodek(zeleni, hevc) -> str:
    """Kodek slike za sejo: prvi s seznama naprave (`codecs` v `screen.start`), ki ga znamo. Brez seznama (starejsa
    naprava) ali brez strojnega HEVC na racunalniku ostane H.264. `hevc` je klic, ki pove, ali racunalnik HEVC zmore -
    poklicemo ga samo, ce naprava HEVC res hoce (preizkus kodirnika stane cas)."""
    if isinstance(zeleni, (list, tuple)):
        for k in zeleni[:8]:
            k = str(k).strip().lower()
            if k == "hevc" and (hevc() if callable(hevc) else bool(hevc)):
                return "hevc"
            if k == "h264":
                return "h264"
    return "h264"


def kodek_za_pot(kodek: str, prek_huba: bool) -> str:
    """Kodek glede na pot, po kateri je gledalec prisel. HEVC samo prek Huba (Global Link, zdoma): tam steje vsak
    megabit. V domacem omrezju pasovne sirine ne manjka, dekoder H.264 pa je na vseh napravah preverjen brez zamika -
    dekoder HEVC televizorja slike oddaja v sunkih (izmerjeno 6. 10. 2026)."""
    return kodek if (kodek != "hevc" or prek_huba) else "h264"


#: Ali strojno kodiranje na napravi res dela (pot -> bool), preizkuseno enkrat na zagon.
_VAAPI_DELUJE: dict = {}


def vaapi_deluje(pot: str, ffmpeg: Optional[str] = None, zazeni=subprocess.run) -> bool:
    """Kratek preizkus h264_vaapi (3 slike). Naprava /dev/dri obstaja tudi, ko gonilnika VA ni (npr. Flatpak na
    starejsem Intelu: »Device creation failed: -5«, izmerjeno na testnem PC 13. 10. 2026) - takrat bi zajem zaslona
    takoj padel. Brez ffmpeg ne preizkusamo (stara pot: naprava obstaja = dela)."""
    if pot in _VAAPI_DELUJE:
        return _VAAPI_DELUJE[pot]
    ffmpeg = ffmpeg or shutil.which("ffmpeg")
    if not ffmpeg:
        return True
    try:
        r = zazeni([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-vaapi_device", pot,
                    "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30", "-frames:v", "3",
                    "-vf", "format=nv12,hwupload", "-c:v", "h264_vaapi", "-rc_mode", "CQP", "-qp", "24",
                    "-f", "null", "-"], capture_output=True, timeout=10)
        dela = r.returncode == 0
    except Exception:
        dela = False
    _VAAPI_DELUJE[pot] = dela
    if not dela:
        print("[zaslon] strojno kodiranje na %s ne dela - zajem s procesorjem (x264)" % pot, flush=True)
    return dela


def vaapi_naprava(ffmpeg: Optional[str] = None) -> Optional[str]:
    """Naprava za strojno kodiranje (Intel/AMD), ki res dela; None, kadar je ni (zajem s procesorjem)."""
    for ime in ("renderD128", "renderD129"):
        pot = os.path.join("/dev/dri", ime)
        if os.path.exists(pot):
            return pot if vaapi_deluje(pot, ffmpeg) else None
    return None


#: Izid preizkusa hevc_vaapi po (ffmpeg, naprava, sirina, visina).
_HEVC_MOZEN: Dict[tuple, bool] = {}


def hevc_vaapi_mozen(ffmpeg: str, naprava: Optional[str], sirina: int, visina: int,
                     zazeni: Callable = subprocess.run) -> bool:
    """Ali ta racunalnik HEVC res strojno kodira v tej velikosti: enkraten kratek preizkus, izid si zapomnimo.

    Naprava (vaapi_naprava) je pogoj kot za h264_vaapi; sama po sebi ni dovolj, ker gonilnik HEVC ali te
    velikosti morda ne zmore. libx265 namenoma ne preizkusamo: njegova hitrost ni izmerjena.
    """
    if not ffmpeg or not naprava or _HEVC.get(_HEVC_ODPOVED):
        return False        # zapah hevc_odpovedal(): zajem s HEVC je ze odpovedal do ponovnega zagona
    kljuc = (ffmpeg, naprava, int(sirina), int(visina))
    if kljuc not in _HEVC_MOZEN:
        if len(_HEVC_MOZEN) >= HEVC_PREIZKUSOV_NAJVEC:
            # Meja preizkusov je dosezena: brez novega preizkusa ostanemo pri H.264 (izida si ne zapomnimo,
            # da se slovar ne veca).
            return False
        ukaz = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-vaapi_device", naprava,
                "-f", "lavfi", "-i", "color=black:size=%dx%d:rate=30" % (int(sirina), int(visina)),
                "-frames:v", "3", "-vf", "format=nv12,hwupload", "-c:v", "hevc_vaapi", "-profile:v", "main",
                "-rc_mode", "CQP", "-qp", "24", "-bf", "0", "-f", "null", "-"]
        try:
            r = zazeni(ukaz, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=HEVC_PREIZKUS_S)
            _HEVC_MOZEN[kljuc] = getattr(r, "returncode", 1) == 0
        except Exception:  # noqa: BLE001 - brez uspesnega preizkusa ostanemo pri H.264
            _HEVC_MOZEN[kljuc] = False
    return _HEVC_MOZEN[kljuc]


def _velikost_izjave(najvecja, kodek: str) -> Optional[Tuple[int, int]]:
    """(sirina, visina) iz izjave televizorja {"hevc": [w, h]}; None za vse, kar ni dvoje pozitivnih celih stevil."""
    if not isinstance(najvecja, dict):
        return None
    v = najvecja.get(kodek)
    if not isinstance(v, (list, tuple)) or len(v) != 2:
        return None
    if not all(isinstance(x, int) and not isinstance(x, bool) and 0 < x <= 16384 for x in v):
        return None
    return int(v[0]), int(v[1])


def izberi_tok(kodeki, najvecja, izvor: tuple, osnova: tuple, hevc_mozen: Callable[[int, int], bool],
               polna: bool = True) -> Tuple[str, int, int]:
    """(kodek, sirina, visina) seje na namizju.

    HEVC samo, ce ga televizor izrecno navede v `kodeki` (codecs iz screen.start) pred "h264" IN ga racunalnik
    res kodira (hevc_mozen(sirina, visina)). Vec kot `osnova` samo s HEVC, samo ob izrecni izjavi
    `najvecja` {"hevc": [w, h]} in samo pri polni kakovosti; najvec NAJVEC_HEVC. Brez seznama (stari
    televizor), brez izjave ali ob kakrsnemkoli dvomu: H.264 v velikosti `osnova` kot doslej.
    """
    privzeto = ("h264",) + tuple(Zaslon._prilagodi(izvor, osnova[0], osnova[1]))
    if not isinstance(kodeki, (list, tuple)):
        return privzeto
    # Ali naprava HEVC hoce (prvi znani kodek na njenem seznamu): to odloca mainov izberi_kodek; velikost sele spodaj.
    hoce = izberi_kodek(kodeki, True) == "hevc"
    if not hoce:
        return privzeto
    meja = (int(osnova[0]), int(osnova[1]))
    izjava = _velikost_izjave(najvecja, "hevc")
    if izjava is not None:
        if izjava[0] < meja[0] or izjava[1] < meja[1]:
            # Dekoder HEVC ne zmore niti osnovne velikosti: raje H.264 kot manjsa slika.
            return privzeto
        if polna:
            meja = (min(izjava[0], NAJVEC_HEVC[0]), min(izjava[1], NAJVEC_HEVC[1]))
    sirina, visina = Zaslon._prilagodi(izvor, meja[0], meja[1])
    if not hevc_mozen(sirina, visina):
        return privzeto
    return "hevc", sirina, visina


def ukaz_ffmpeg(display: str, sirina: int, visina: int, izvor_sirina: int, izvor_visina: int,
                fps: int, bitrate: str, vaapi: Optional[str], ffmpeg: str = "ffmpeg",
                qp: int = 24, kodek: str = "h264", gop: int = 0, gpu: bool = False,
                odmik: tuple = (0, 0), vhod: Optional[List[str]] = None) -> List[str]:
    """Ukaz za zajem in kodiranje. Strojno (VAAPI), ce je mogoce, sicer x264 brez zamika.

    `kodek`: "hevc" samo strojno (pri istem kvantizatorju manj bajtov); brez VAAPI vedno H.264.
    `gop`: razmik kljucnih slik v slikah; 0 = vsako sekundo (starejsi gledalec).
    `gpu`: sliko, ki jo je treba pomanjsati, pretvori in pomanjsa graficna kartica (gpu_lestvica_mozna), ne procesor.
    `odmik`: zgornji levi kot monitorja v pikah X (vec monitorjev: delimo en monitor, ne vseh, stisnjenih v eno sliko).
    `vhod`: namesto x11grab (Wayland: surove slike iz core/zajem_pipewire.py na stdin, portal_zaslon.vhod_ffmpeg).
    Locen od zagona, da ga je mogoce preveriti v testu brez kamere in zaslona.
    libx265 namenoma ne (njegova hitrost ni izmerjena): brez VAAPI je tok vedno H.264.
    """
    hevc = kodek == "hevc" and bool(vaapi)
    u = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin"]
    if vhod:
        u += list(vhod)
    else:
        izvor = display + ("+%d,%d" % (int(odmik[0]), int(odmik[1])) if tuple(odmik) != (0, 0) else "")
        u += ["-f", "x11grab", "-draw_mouse", "1", "-framerate", str(fps),
              "-video_size", f"{izvor_sirina}x{izvor_visina}", "-i", izvor]
    # Kadar je slika ze prave velikosti, je ne prevzorcimo: vsako skaliranje zmehca besedilo in
    # nekaj stane. To je najpogostejsi primer (zaslon 1920x1080 -> 1920x1080).
    lestvica = (sirina, visina) != (izvor_sirina, izvor_visina)
    filter_lestvica = f"scale={sirina}:{visina}:flags=lanczos," if lestvica else ""
    if vaapi:
        # Intelov gonilnik ima na tem prenosniku samo nizkoenergijski vhod (EncSliceLP), ta pa
        # podpira le CQP - z -b:v kodirnik sploh ne odpre ("no RC mode compatible"). Zato kakovost
        # dolocimo s kvantizatorjem, hitrost pa omejimo z velikostjo slike in sliko na sekundo.
        # Profil high (CABAC, transformacija 8x8) je za besedilo opazno boljsi od main in
        # televizor ga strojno dekodira (OMX.MTK.VIDEO.DECODER.AVC).
        #
        # Varcnega nacina (low_power) namenoma ne vsiljujemo: na tem prenosniku (Intel Gen12) drug
        # nacin sploh ne obstaja - izmerjeno je z low_power 0 in 1 izid enak do decimalke - na
        # drugih racunalnikih pa lahko gonilnik izbere boljso pot, ce mu je ne zvezemo.
        # CQP je edini nacin hitrosti, ki ga ta gonilnik zna (CBR, VBR, ICQ in QVBR so preizkuseni
        # in vsi padejo), obenem pa ga zna vsak - zato kakovost dolocimo s kvantizatorjem.
        #
        # Pomanjsava na procesorju (lanczos) je bila pri 2560x1440 -> 1080p vecina dela ffmpeg (346 % CPU). Graficna
        # sliko pretvori in pomanjsa sama (74 % CPU). Nacin `default` (algoritem izbere gonilnik) izrecno: ffmpeg >= 6
        # brez njega vzame `hq`, ta pa je bil na Intel iHD za besedilo 3 dB slabsi (PSNR svetlosti 34,3 proti 37,4 dB;
        # lanczos 37,5 dB), barve pa so enake kot s procesorjem (55 dB). Kjer slike ne pomanjsamo, ostane pretvorba na
        # procesorju - tam je poceni in izmerjena.
        if gpu and lestvica:
            filter_slike = f"hwupload,{SCALE_VAAPI.format(sirina=sirina, visina=visina)}"
        else:
            filter_slike = f"{filter_lestvica}format=nv12,hwupload"
        u += ["-vaapi_device", vaapi,
              "-vf", filter_slike,
              "-c:v", "hevc_vaapi" if hevc else "h264_vaapi", "-profile:v", "main" if hevc else "high",
              "-rc_mode", "CQP", "-qp", str(qp)]
    else:
        u += ["-vf", f"{filter_lestvica}format=yuv420p",
              "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency", "-profile:v", "high",
              "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", "1M"]
    # Brez B-slik in z rednim kljucnim okvirjem: televizor se lahko prikljuci hitro,
    # izguba paketa pa se popravi v eni sekundi.
    u += ["-g", str(gop if gop > 0 else max(1, fps)), "-bf", "0", "-flags", "+low_delay",
          "-f", "hevc" if hevc else "h264", "-"]
    return u


def glava_toka(slika: dict, zvok: bool, vnos, plosek, kodek: str = "h264") -> dict:
    """Glava toka po pozdravu. Za H.264 enaka kot prej (stari televizorji); za HEVC dodatno "kodek": "hevc"."""
    glava = {"v": 2, "w": slika["width"], "h": slika["height"],
             "fps": slika["fps"],
             "zvok": {"hz": ZVOK_HZ, "kanali": ZVOK_KANALI, "oblika": "s16le"} if zvok else None,
             "vnos": vnos, "plosek": plosek,
             # Zigi zajema (okvir 4 pred sliko/zvokom); stari televizor kljuc prezre.
             "zig": dict(ZIG_GLAVA)}
    if kodek == "hevc":
        # Televizor bere glava.optString("kodek") == "hevc"; brez kljuca dekodira H.264.
        glava["kodek"] = "hevc"
    return glava


#: Zahteva televizorja po novem kljucnem okvirju (IDR): najvec KLJUCNI_NAJVEC v KLJUCNI_OKNO_S
#: sekundah (drsece okno). Vec bi pomenilo stalne ponovne zagone zajema in crno sliko.
KLJUCNI_OKNO_S, KLJUCNI_NAJVEC = 2.0, 1
#: Koliko casa ima stari proces slike po SIGTERM, da izprazni zadnje okvirje, preden ga ubijemo.
ZAMENJAVA_S = 2.0
#: Kako dolgo nov proces slike ne sme pasti, da ga sprejmemo (NEPREVERJENO: cas zagona ffmpeg).
ZAGON_PREVERI_S = 0.3


def presodi_kljucni(sprejeti: Tuple[float, ...], zdaj: float, okno_s: float = KLJUCNI_OKNO_S,
                    najvec: int = KLJUCNI_NAJVEC) -> Tuple[bool, Tuple[float, ...]]:
    """Cisto pravilo omejitve: (dovoljeno, novi casi sprejetih zahtev).

    `sprejeti` so monotoni casi (s) prej sprejetih zahtev, `zdaj` je cas nove zahteve. Steje se samo
    sprejeta zahteva; zavrnjena okna ne podaljsa, zato je zahteva cez okno_s od zadnje sprejete vedno
    dovoljena. Cas, ki gre nazaj, se steje kot zadnji sprejeti cas; neveljaven cas (NaN, neskoncno)
    zavrnemo, da ne pokvari okna.
    """
    if not isinstance(zdaj, (int, float)) or not math.isfinite(zdaj):
        return False, tuple(sprejeti)
    if sprejeti and zdaj < sprejeti[-1]:
        zdaj = sprejeti[-1]
    ostali = tuple(t for t in sprejeti if zdaj - t < okno_s)
    if len(ostali) >= najvec:
        return False, ostali
    return True, ostali + (float(zdaj),)


class OmejevalnikKljucnih:
    """Stanje omejitve za eno sejo in stevca za dnevnik. Varen za vec niti."""

    def __init__(self, okno_s: float = KLJUCNI_OKNO_S, najvec: int = KLJUCNI_NAJVEC,
                 ura: Callable[[], float] = time.monotonic) -> None:
        self._okno_s = okno_s
        self._najvec = najvec
        self._ura = ura
        self._sprejeti: Tuple[float, ...] = ()
        self._kljuc = threading.Lock()
        self.sprejetih = 0
        self.zavrnjenih = 0

    def dovoli(self) -> bool:
        with self._kljuc:
            dovoljeno, self._sprejeti = presodi_kljucni(self._sprejeti, self._ura(), self._okno_s, self._najvec)
            if dovoljeno:
                self.sprejetih += 1
            else:
                self.zavrnjenih += 1
            return dovoljeno


class _ProcesSlike:
    """Proces slike, ki ga je mogoce zamenjati z novim, ne da bi se seja koncala.

    Navzven je enak objekt ves cas seje, zato `self._proces is slika` v _strazi_prazno in
    _porocaj_medij ostane resnicen tudi po zamenjavi. Bralec (_crpaj) prebere stari pretok do konca
    in nadaljuje z novim, zato se okvirja dveh procesov ne prepletata. Nov ffmpeg zacne s SPS, PPS in
    IDR, kar je edini zanesljiv nacin za kljucni okvir na zahtevo iz ffmpeg CLI.
    """

    def __init__(self, zazeni: Callable[[], subprocess.Popen]) -> None:
        self._zazeni = zazeni
        self._kljuc = threading.Lock()
        self._ustavljen = False
        self._p = zazeni()
        #: Proces, ki ga bralec trenutno prazni; na novega preide sele ob koncu starega pretoka.
        self._bran = self._p
        #: Zadrzan konec starega pretoka (samo med zamenjavo).
        self._rep = b""
        self.zamenjav = 0
        #: Ali je zadnji vrnjeni kos sveze prebran iz tekocega procesa (samo takrat je zig slike mogoc).
        self.svez = True
        #: Prvi kos novega procesa je cakal v cevi, dokler se je praznil stari: brez ziga.
        self._po_zamenjavi = False
        #: Procesi, katerih pretoka ne posljemo vec (tuj zaslon po menjavi seje): beremo do EOF in
        #: zavrzemo, tudi rep. Nic od tega ne pride do _crpaj (ne v "bajt", ne v ZigiSlike, ne v svez).
        self._zavrzeni: tuple = ()
        #: Ali znova() sme zagnati nov proces (IDR na zahtevo); pri KMS ne, glej slika_kms.
        self.idr_na_zahtevo = True

    @property
    def stdout(self) -> "_ProcesSlike":
        return self

    def read(self, kos: int) -> bytes:
        while True:
            p = self._bran
            podatki = p.stdout.read(kos)
            if podatki:
                if p in self._zavrzeni:
                    continue                # tuj zaslon: niti bajta na televizor; svez ostane, kot je
                if p is self._p:
                    self.svez = not self._po_zamenjavi
                    self._po_zamenjavi = False
                    return podatki
                # Stari pretok praznimo: zadrzimo del od zadnje zacetne kode naprej, ker je lahko
                # odrezan, ce starega procesa ne bo mogoce ustaviti drugace kot s SIGKILL.
                podatki = self._rep + podatki
                i = podatki.rfind(b"\x00\x00\x01")
                if i <= 0:
                    self._rep = podatki
                    continue
                self._rep = podatki[i:]
                self.svez = False           # konec starega toka (lahko z ostankom prejsnjega branja)
                return podatki[:i]
            with self._kljuc:
                if self._ustavljen or self._p is p:
                    return b""
                # Stari proces je izpraznjen, nov ze tece: beremo naprej iz njega.
                self._bran = self._p
                self._po_zamenjavi = True
            rep, self._rep = self._rep, b""
            if p in self._zavrzeni:
                rep = b""
            try:
                p.stdout.close()        # EOF je dosezen, deskriptorja ne prepustimo GC
            except OSError:
                pass
            try:
                koda = p.wait(timeout=ZAMENJAVA_S + 1)
            except subprocess.TimeoutExpired:
                koda = None
            # Po SIGKILL je zadnja enota NAL lahko odrezana: zavrzemo jo, nov pretok zacne s SPS/IDR.
            if rep and koda != -signal.SIGKILL:
                self.svez = False           # ostanek, prebran ze pri prejsnjem branju
                return rep

    def znova(self) -> bool:
        """Zazene nov proces slike in pospravi starega v ozadju. False, ce seja ze konca ali zagon pade."""
        with self._kljuc:
            if self._ustavljen or self._bran is not self._p or not self.idr_na_zahtevo:
                # Seja se konca, prejsnja zamenjava se ni izpraznjena ali vir ne dovoli novega
                # procesa (KMS): brez vmesnega procesa, stanje (_p, _bran, svez) ostane enako.
                return False
        try:
            nov = self._zazeni()
        except Exception:
            return False
        try:
            # Nov proces, ki takoj pade (zaseden zajem ali kodirnik), ne sme koncati delujoce seje.
            nov.wait(timeout=ZAGON_PREVERI_S)
            self._pospravi(nov)
            print("[zaslon] nov proces slike je takoj koncal (koda %s), ostane stari" % nov.returncode,
                  flush=True)
            return False
        except subprocess.TimeoutExpired:
            pass
        with self._kljuc:
            if self._ustavljen or self._bran is not self._p:
                star = nov
            else:
                star, self._p = self._p, nov
                self.zamenjav += 1
        try:
            threading.Thread(target=self._pospravi, args=(star,), name="safeer-zaslon-zamenjava",
                             daemon=True).start()
        except RuntimeError:
            self._pospravi(star)        # nit ni na voljo: pospravimo kar tu
        return star is not nov

    @staticmethod
    def _pospravi(star: subprocess.Popen) -> None:
        try:
            star.terminate()
            star.wait(timeout=ZAMENJAVA_S)
        except Exception:
            try:
                star.kill()
                star.wait(timeout=1)    # pobere proces, da ne ostane zombi
            except Exception:
                pass

    def preklopi(self, zazeni: Callable[[], subprocess.Popen], zavrzi: bool = False) -> bool:
        """Nov vir slike za ostanek seje (KMS -> x11grab) in takoj nov proces iz njega.

        zavrzi=True (menjava seje): pretok tekocega procesa se od tega trenutka ne poslje vec, tudi
        ce zamenjava ne uspe; preostanek v cevi se prebere in zavrze. Nov vir (x11grab) zna IDR na
        zahtevo, zato se ta spet dovoli.
        """
        with self._kljuc:
            self._zazeni = zazeni
            self.idr_na_zahtevo = True
            if zavrzi:
                self._zavrzeni = (self._p, self._bran)
        return self.znova()

    def poll(self):
        return self._p.poll()

    def terminate(self) -> None:
        with self._kljuc:
            self._ustavljen = True
            procesi = {id(self._p): self._p, id(self._bran): self._bran}.values()
        for p in procesi:           # tudi stari, ki ga bralec se prazni
            p.terminate()

    def kill(self) -> None:
        with self._kljuc:
            self._ustavljen = True
            procesi = {id(self._p): self._p, id(self._bran): self._bran}.values()
        for p in procesi:
            p.kill()

    def wait(self, timeout: Optional[float] = None):
        return self._p.wait(timeout=timeout)


#: Vticnik privilegiranega pomocnika za zajem KMS (core/link_kms_pomocnik.py, enota systemd).
KMS_VTICNIK = "/run/safeer/kms.sock"
#: Kako pogosto med zajemom KMS preverimo sejo in monitorje (s).
KMS_STRAZA_S = 1.0


def kms_na_voljo() -> bool:
    """Pomocnik za zajem KMS je namescen in vklopljen (vticnik obstaja)."""
    return os.path.exists(KMS_VTICNIK)


def _razlog(besedilo: str) -> str:
    """Razlog za merilni dnevnik kot ena beseda (polja v _cas so locena s presledki)."""
    besedilo = besedilo.strip()
    if besedilo.startswith("napaka:"):
        besedilo = besedilo[len("napaka:"):].strip()
    cisto = "".join(c if (c.isascii() and c.isalnum()) or c in "()._-" else "_" for c in besedilo)
    return cisto[:60] or "neznano"


class _KmsProces:
    """Zajem, ki ga je zagnal pomocnik KMS; za _ProcesSlike izgleda kot Popen.

    stdout je bralni konec cevi (SCM_RIGHTS). Zajem je koncan, ko pomocnik zapre kontrolni
    vticnik (ffmpeg je koncal). terminate() zapre samo nas konec vticnika: pomocnik nato ustavi
    ffmpeg (SIGTERM, po 3 s SIGKILL), bralec pa dobi EOF kot pri Popen. stdout tu namenoma ne
    zapremo, ker ga lahko druga nit (_crpaj prek _ProcesSlike.read) ravno bere.
    """

    def __init__(self, vticnik: socket.socket, fd: int) -> None:
        self._vticnik = vticnik
        self.stdout = os.fdopen(fd, "rb", buffering=0)
        self.returncode: Optional[int] = None
        self._kljuc = threading.Lock()

    def poll(self) -> Optional[int]:
        with self._kljuc:
            if self.returncode is None:
                try:
                    podatki = self._vticnik.recv(1, socket.MSG_DONTWAIT | socket.MSG_PEEK)
                except (BlockingIOError, InterruptedError):
                    return None
                except OSError:
                    podatki = b""
                if not podatki:
                    self.returncode = 0
            return self.returncode

    def wait(self, timeout: Optional[float] = None) -> int:
        # Kot Popen.wait: TimeoutExpired, ce zajem po timeout se tece (znova to potrebuje).
        konec = None if timeout is None else time.monotonic() + timeout
        while self.poll() is None:
            ostane = 0.2 if konec is None else konec - time.monotonic()
            if ostane <= 0:
                raise subprocess.TimeoutExpired("kms", timeout)
            try:
                select.select([self._vticnik], [], [], min(ostane, 0.2))
            except (OSError, ValueError):
                time.sleep(min(ostane, 0.2))
        return self.returncode

    def terminate(self) -> None:
        with self._kljuc:
            if self.returncode is None:
                # Ne vemo, ali je pomocnik moral uporabiti SIGKILL: _ProcesSlike.read zato
                # zadnjo (morda odrezano) enoto NAL starega pretoka zavrze.
                self.returncode = -signal.SIGKILL
        try:
            self._vticnik.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._vticnik.close()
        except OSError:
            pass

    kill = terminate


def odpri_kms(sirina: int, visina: int, fps: int, kodek: str, qp: int,
              seja: int = 0) -> Optional[_KmsProces]:
    """Prosi pomocnika za zajem KMS; vrne proces s pretokom ali None (takrat ostane x11grab).

    Vsak odgovor brez "ok" (npr. "napaka: seja wayland (kms samo x11)", "napaka: prepogosto",
    "napaka: zajem ze tece", "napaka: zasedeno") pomeni None; razlog gre v merilni dnevnik.
    """
    if not kms_na_voljo():
        _cas("kms_zavrnjen", seja, razlog="ni_pomocnika")
        return None
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.settimeout(5)
        s.connect(KMS_VTICNIK)
        zahteva = {"w": int(sirina), "h": int(visina), "fps": int(fps), "kodek": kodek, "qp": int(qp)}
        s.sendall((json.dumps(zahteva) + "\n").encode("utf-8"))
        sporocilo, fds, _, _ = socket.recv_fds(s, 256, 1)
        if not sporocilo.startswith(b"ok") or not fds:
            for fd in fds:
                os.close(fd)
            if not sporocilo:
                razlog = "ni_odgovora"
            elif sporocilo.startswith(b"ok"):
                razlog = "brez_fd"
            else:
                razlog = _razlog(sporocilo[:80].decode("utf-8", "replace"))
            _cas("kms_zavrnjen", seja, razlog=razlog)
            s.close()
            return None
        for fd in fds[1:]:
            os.close(fd)
        s.settimeout(None)
        proces = _KmsProces(s, fds[0])
        _cas("kms_odprt", seja, w=zahteva["w"], h=zahteva["h"], fps=zahteva["fps"])
        return proces
    except (OSError, ValueError) as napaka:
        _cas("kms_zavrnjen", seja, razlog=type(napaka).__name__)
        try:
            s.close()
        except OSError:
            pass
        return None


def slika_kms(zahteva: dict, seja: int = 0) -> Optional[_ProcesSlike]:
    """_ProcesSlike z zajemom prek pomocnika KMS ali None (takrat klicatelj uporabi x11grab).

    IDR na zahtevo (znova) pomocnika NE sprasuje: pomocnik dovoli en zajem naenkrat in bi med
    tekocim zajemom vedno odgovoril "zajem ze tece". znova zato takoj vrne False (stari proces in
    zaporedje zamenjav za zige ostaneta), kljucni okvir pride z -g fps (ukaz_kms) najkasneje v 1 s.
    """
    prvi = odpri_kms(seja=seja, **zahteva)
    if prvi is None:
        return None
    try:
        prvi.wait(timeout=ZAGON_PREVERI_S)
    except subprocess.TimeoutExpired:
        pass
    else:
        # Pomocnik je rekel ok, ffmpeg pa je takoj koncal (npr. hwmap, gonilnik): x11grab.
        _cas("kms_zavrnjen", seja, razlog="ffmpeg_koncal")
        prvi.terminate()
        try:
            prvi.stdout.close()
        except OSError:
            pass
        return None
    zacetni = [prvi]

    def zazeni():
        if zacetni:
            return zacetni.pop()
        raise OSError("kms: nov zajem med zajemom ni mogoc")     # varovalo; znova sem ne pride
    slika = _ProcesSlike(zazeni)
    slika.idr_na_zahtevo = False
    return slika


def odpri_sliko(zazeni_x11: Callable[[], subprocess.Popen], kms: Optional[dict] = None,
                seja: int = 0) -> Tuple[_ProcesSlike, bool]:
    """(proces slike, ali je KMS). Brez zahteve KMS ali ob vsaki zavrnitvi: x11grab kot prej."""
    slika = slika_kms(kms, seja) if kms else None
    if slika is not None:
        return slika, True
    return _ProcesSlike(zazeni_x11), False


def kms_monitorji() -> int:
    """Stevilo prizganih izhodov DRM (sysfs); kmsgrab zajame samo prvi aktivni CRTC."""
    stevilo = 0
    for pot in glob.glob("/sys/class/drm/card[0-9]*-*/enabled"):
        try:
            with open(pot) as f:
                if f.read().strip() == "enabled":
                    stevilo += 1
        except OSError:
            pass
    return stevilo


def seja_aktivna() -> Optional[bool]:
    """Ali je nasa seja logind ta trenutek na zaslonu; None, ce tega ne moremo izvedeti."""
    seja = os.environ.get("XDG_SESSION_ID", "")
    if not seja or not shutil.which("loginctl"):
        return None
    try:
        r = subprocess.run(["loginctl", "show-session", seja, "-p", "Active", "--value"],
                           text=True, capture_output=True, timeout=3)
    except Exception:
        return None
    vrednost = (r.stdout or "").strip()
    return True if vrednost == "yes" else (False if vrednost == "no" else None)


def kms_stanje(display: str) -> tuple:
    """Kar mora med zajemom KMS ostati enako: aktivna seja, stevilo monitorjev, velikost zaslona."""
    return seja_aktivna(), kms_monitorji(), _zaslon_geometrija(display)


def strazi_kms(slika: _ProcesSlike, zazeni_x11: Callable[[], subprocess.Popen],
               stanje: Callable[[], tuple], tece: Callable[[], bool], seja: int = 0,
               premor: float = KMS_STRAZA_S) -> bool:
    """Med zajemom KMS: ob menjavi seje (VT, drug uporabnik) ali monitorjev preklopi na x11grab.

    kmsgrab zajame fizicni zaslon, ne nase seje X: po preklopu na drugo sejo bi televizor sicer
    kazal tuj zaslon. Nazaj na KMS v isti seji ne gremo. Vrne True, ce je preklopil.
    """
    zacetno = stanje()
    while tece():
        time.sleep(premor)
        if not tece():
            return False
        zdaj = stanje()
        if zdaj[0] is True and zdaj == zacetno:
            continue
        razlog = "seja" if zdaj[0] is not True else "monitor"
        # Po menjavi seje je v cevi ze tuj zaslon: ne poslje se niti preostanek (pri menjavi
        # monitorja je pretok se nas in se izprazni kot pri vsaki zamenjavi).
        if slika.preklopi(zazeni_x11, zavrzi=razlog == "seja"):
            _cas("kms_preklop", seja, razlog=razlog)
            return True
        if razlog == "seja":
            # x11grab ne stece, tuj zaslon pa ne sme ostati na televizorju: seja se konca.
            _cas("kms_preklop", seja, razlog="seja_konec")
            slika.terminate()
            return False
    return False


def privzeti_monitor() -> Optional[str]:
    """Kar racunalnik ta trenutek predvaja (monitor privzetega izhoda).

    Ime izhoda vprasamo `pactl`; ce ga ni ali ce se ne more povezati (to se zgodi procesu, ki ne
    tece v uporabnikovi seji), uporabimo `@DEFAULT_MONITOR@` - to ime razresi zvocni streznik sam.
    None vrnemo samo, kadar zvocnega streznika ocitno ni.
    """
    if shutil.which("pactl"):
        try:
            r = subprocess.run(["pactl", "get-default-sink"], text=True, capture_output=True, timeout=3)
            ime = (r.stdout or "").strip()
            if ime:
                return ime + ".monitor"
        except Exception:
            pass
    zvocni_vticnik = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid(), "pulse", "native")
    if os.path.exists(zvocni_vticnik) or os.environ.get("PULSE_SERVER"):
        return "@DEFAULT_MONITOR@"
    return None


def _okvir(vrsta: int, vsebina: bytes) -> bytes:
    """Okvir pretoka: bajt vrste, stirje bajti dolzine, vsebina."""
    return bytes([vrsta]) + len(vsebina).to_bytes(4, "big") + vsebina


def _zapri(s) -> None:
    """shutdown pred close: niti, ki na vticnici cakajo (branje, pisanje), se zbudijo, druga stran pa dobi konec.
    Samo close() ne zbudi nikogar in televizorju konca ne poslje, dokler vticnico kdo drzi."""
    if s is None:
        return
    try:
        s.shutdown(socket.SHUT_RDWR)
    except Exception:
        pass
    try:
        s.close()
    except Exception:
        pass


def _koncaj(proces: Optional[subprocess.Popen]) -> None:
    """Ustavi zajem (slika ali zvok); ce se na prijazen konec ne odzove, ga ubije."""
    if proces is None or proces.poll() is not None:
        return
    try:
        proces.terminate()
        proces.wait(timeout=3)
    except Exception:
        try:
            proces.kill()
        except Exception:
            pass


def ukaz_zvok(vir: str, ffmpeg: str = "ffmpeg") -> List[str]:
    """Zajem zvoka racunalnika kot surov PCM. Majhni koscki (10 ms), da zvok ne zaostaja za sliko."""
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "pulse", "-fragment_size", "1920", "-i", vir,
            "-ac", str(ZVOK_KANALI), "-ar", str(ZVOK_HZ), "-f", "s16le", "-"]


def vklopljeno_iz_nastavitev(vrednost: object) -> bool:
    """Ali je deljenje zaslona v Safeer Controlu vklopljeno (`zaslon_za_tv` v control.json).

    Uporabnik ni nikoli izbiral (kljuca ni): VKLOPLJENO - pripravljeno (14. 10. 2026). To je varno, ker zaslon vsaka
    druga naprava dobi sele, ko ji uporabnik NA TEM racunalniku odpre zmoznost »z« (core/link_dostop, za vsako napravo
    posebej) - rocno ali z »Dovoli« v obvestilu s prosnjo za dostop; brez tega racunalnik screen.start zavrne sam.
    Izrecna izbira uporabnika (tudi izklop) velja naprej."""
    return True if vrednost is None else bool(vrednost)


class Zaslon:
    """Deljenje zaslona racunalnika s televizorjem: ena seja naenkrat, samo na uporabnikov ukaz."""

    ZMOZNOST = "desktop"

    def __init__(self, tls_mapa: str = TLS_MAPA, ffmpeg: Optional[str] = None,
                 vklopljeno: bool = False, kms: bool = False) -> None:
        self.tls_mapa = tls_mapa
        #: Uporabnik mora deljenje zaslona vklopiti v Safeer Controlu; privzeto je izklopljeno.
        self.vklopljeno = bool(vklopljeno)
        #: Zajem prek KMS (privilegiran pomocnik). Privzeto izklopljen: kmsgrab ne narise
        #: kazalca miske (x11grab ga z -draw_mouse 1), na namizju pa kazalca ne posljemo drugace.
        self.kms = bool(kms)
        #: Klicatelj (Control) ga nastavi, da si izbiro zapomni in pokaze stanje v pladnju.
        self.ob_spremembi = None
        self.ffmpeg = ffmpeg or (shutil.which("ffmpeg") or "")
        self.odtis = ""
        self.vrata = 0
        self._zeton = ""
        self._naprava = ""
        self._kakovost = PRIVZETA_KAKOVOST
        #: Omrezje gledalca, kot ga pove sam (`net` v screen.start): wifi, ethernet, 5g, 4g ... ali prazno.
        self._omrezje = ""
        #: Ali zajem kodira graficna kartica (kvantizator); programski kodirnik ima namesto njega bitno hitrost.
        self._strojno = False
        self._slika: Dict[str, int] = {}
        #: Stevec sej: straza osirotelih programov ve, ali se je medtem zacela nova seja.
        self._seja_st = 0
        self._izvor = (1920, 1080)
        self._zvok_vir: Optional[str] = None
        self._posluh: Optional[socket.socket] = None
        self._proces: Optional[_ProcesSlike] = None
        #: Zakasnitev kodirnika te seje za zig slike (ZAKASNITEV_SLIKE_MS); None = brez ziga slike.
        self._zakasnitev_slike: Optional[float] = None
        self._kljucni = OmejevalnikKljucnih()
        #: Seja je bila izbrana z izrecno veliko sliko (nad osnovno velikostjo): mogoca je samo s HEVC, kodeka po poti ne znizamo.
        self._hevc_veliki = False
        self._zvocni: Optional[subprocess.Popen] = None
        self._nit: Optional[threading.Thread] = None
        #: Povezava televizorja v tekoci seji (ovita, core/link_vticnik.py); ustavi() jo zapre in s tem zbudi niti seje.
        self._odjemalec = None
        #: Povezave gledalcev, ki jih je sprejel Hub (Global Link) in cakajo, da jih seja prevzame:
        #: (vticnica, dogodek konca seje, stevilka seje).
        self._prevzeti: list = []
        self._prek_huba = False
        #: Kaj zna naprava, ki gleda (`caps` v `screen.start`), npr. "handoff": preklop na namizje, kadar je program tam.
        self._zmoznosti: set = set()
        #: Kodek slike tekoce seje ("h264" ali "hevc").
        self._kodek = "h264"
        self._vnos = Vnos()
        # Navidezni igralni plosek racunalnika: nastane sele, ko televizor res poslje plosek.
        self._plosek = Plosek()
        #: Locen zaslon za televizor (core.link_sway.DrugiZaslon) ali None.
        self.drugi = None
        self._cilj = "desktop"
        #: Okolje za zajem slike (drugi zaslon potrebuje svoj WAYLAND_DISPLAY); None = nase.
        self._okolje_zajema: Optional[dict] = None
        #: Wayland: seja portala (core/portal_zaslon.Seja) tekoce seje in dodatno za Popen zajema (fd PipeWire).
        self._portal = None
        self._zajem_dodatno: dict = {}
        #: Zmoznosti portala (D-Bus) za na_voljo(): (cas, zmoznosti) - status se bere pogosto.
        self._portal_zmore: tuple = (0.0, {})
        #: En dialog portala naenkrat: televizor, ki screen.start ponovi, ne odpre drugega dialoga (druga zahteva
        #: pocaka in dobi sejo z zetonom obnovitve brez vprasanja).
        self._portal_zaklep = threading.Lock()
        self._vnosov = 0
        self._tece_od = 0.0
        self._povezan = False
        #: Meritve tekoce seje (core/link_zaslon_meritve.Meritve) ali None, dokler gledalec ni povezan.
        self._meritve: Optional[link_zaslon_meritve.Meritve] = None
        self._kljucavnica = threading.Lock()

    # ------------------------------------------------------------------ stanje

    def _zmore_portal(self) -> dict:
        """Wayland: kaj zna portal (zajem, vnos) in ali ima GStreamer pipewiresrc; 60 s v predpomnilniku."""
        cas, zmore = self._portal_zmore
        if time.monotonic() - cas > 60 or not zmore:
            from core import portal_zaslon
            try:
                zmore = dict(portal_zaslon.zmoznosti(), gst=portal_zaslon.gstreamer_pipewire())
            except Exception:  # noqa: BLE001 - ni vodila seje
                zmore = {"zajem": False, "vnos": False, "gst": False}
            self._portal_zmore = (time.monotonic(), zmore)
        return zmore

    def na_voljo(self) -> dict:
        """Ali ta racunalnik sploh zna deliti zaslon in s cim.

        Wayland: zajem in vnos prek portala (core/portal_zaslon); prej je tu stal DISPLAY (XWayland) in zajem je dal
        crno sliko. Kar portal ne zna, ni »mozno« - televizor tega ne ponudi."""
        from core import seja_prikaza
        display = os.environ.get("DISPLAY", "")
        vaapi = vaapi_naprava(self.ffmpeg)
        wayland = seja_prikaza.je_wayland()
        portal = self._zmore_portal() if wayland else {}
        return {
            "dovoljeno": self.vklopljeno,
            "mozno": bool(self.ffmpeg) and (bool(portal.get("zajem") and portal.get("gst")) if wayland else bool(display)),
            "ffmpeg": bool(self.ffmpeg),
            "zaslon": os.environ.get("WAYLAND_DISPLAY", "") if wayland else display,
            "seja": "wayland" if wayland else ("x11" if display else ""),
            "strojno": bool(vaapi),
            "kms": self.kms and kms_na_voljo(),
            "zvok": bool(privzeti_monitor()),
            "vnos": bool(portal.get("vnos")) if wayland else self._vnos.mozno,
            "plosek": self._plosek.mozno(),
            "kakovosti": sorted(KAKOVOSTI),
            "locen_zaslon": self.drugi is not None,
        }

    def stanje(self) -> dict:
        s = {"tece": self._proces is not None or self._posluh is not None,
             "povezan": self._povezan, "naprava": self._naprava, "kakovost": self._kakovost,
             "screen": self._cilj}
        if self._slika:
            s.update(self._slika)
        if self._tece_od:
            s["sekund"] = int(time.time() - self._tece_od)
        s["vnosov"] = self._vnosov
        meritve = self._meritve
        if meritve is not None and self._povezan:
            # Med sejo: meritve in kodirnik, ki ga zajem res uporablja (screen.status jih pokaze).
            s["meritve"] = meritve.posnetek()
            s["kodirnik"] = meritve.opis.get("kodirnik")
        return s

    # ------------------------------------------------------------------ zagon

    def nastavi(self, vklopljeno: bool) -> None:
        """Uporabnik je deljenje zaslona vklopil ali izklopil. Izklop takoj konca tekoco sejo."""
        self.vklopljeno = bool(vklopljeno)
        if not self.vklopljeno:
            self.ustavi()
        if self.ob_spremembi is not None:
            try:
                self.ob_spremembi(self.vklopljeno)
            except Exception:
                pass

    def _na_drugem(self, cilj: str) -> bool:
        """Ali ta seja kaze drugi zaslon (programe s televizorja) namesto uporabnikovega namizja.

        `apps` = da, ce drugi zaslon tece; `desktop` = nikoli; brez navedbe (starejsi televizor) =
        da, kadar so na drugem zaslonu odprta okna - sicer bi jih televizor sploh ne videl."""
        if self.drugi is None or not self.drugi.tece():
            return False
        if cilj == "desktop":
            return False
        return cilj == "apps" or self.drugi.okna() > 0

    def zacni(self, id_naprave: str, kakovost: str = PRIVZETA_KAKOVOST, cilj: str = "",
              prek_huba: bool = False, pogled: Optional[dict] = None, zmoznosti=None, kodeki=None,
              omrezje: str = "", najvecja=None) -> dict:
        """Pripravi sejo: odpre TLS vrata in caka televizor. Zajem se zacne sele, ko se ta javi.

        `pogled`: povrsina naprave, ki gleda (`view` iz `screen.start`). Loceni zaslon dobi njeno obliko in
        velikost; pravega zaslona racunalnika ne spreminjamo nikoli.
        `prek_huba`: gledalec zna po sliko tudi do vrat Huba (pot `/cast/desktop`, Global Link). Po kateri poti res
        pride, vemo sele ob povezavi: takrat izberemo kodek (kodek_za_pot) in stopnjo (kakovost_za_pot).
        `omrezje`: omrezje naprave, ki gleda (`net`: wifi, ethernet, 5g, 4g ...); po njem je umerjena kakovost zdoma.
        `kodeki` ("codecs") in `najvecja` ("maxsize", npr. {"hevc": [3840, 2160]}) sta izrecni zmoznosti naprave: slika
        nad osnovno velikostjo (do NAJVEC_HEVC) samo s HEVC, samo ob izrecni izjavi in pri polni kakovosti (izberi_tok)."""
        if not self.vklopljeno:
            raise RuntimeError("Deljenje zaslona ni vklopljeno")
        if not self.ffmpeg:
            raise RuntimeError("Na tem racunalniku ni ffmpeg")
        from core import seja_prikaza
        display = os.environ.get("DISPLAY", "")
        wayland = seja_prikaza.je_wayland()
        if not display and not wayland:
            raise RuntimeError("Zaslona ni mogoce zajeti (seja ni na voljo)")
        k = KAKOVOSTI.get(kakovost) or KAKOVOSTI[PRIVZETA_KAKOVOST]
        self._seja_st += 1
        seja_st = self._seja_st
        if cilj == "apps" and self.drugi is not None and not self.drugi.tece():
            # Televizor hoce program, locenega zaslona pa ni vec (Control je bil znova zagnan,
            # programi so zaprti). Prej je dobil namizje racunalnika - tega ni zahteval in tam
            # je lahko karkoli zasebnega. Zdaj pove, da programa ni vec.
            raise ProgramaNi("Program na racunalniku ni vec odprt")
        self.ustavi()
        na_drugem = self._na_drugem(cilj)
        merilo = 1.0
        kodek_x11 = vaapi_x11 = None
        odmik = (0, 0)
        kms = None
        if na_drugem:
            # Drugi zaslon je natanko tako velik, kot ga naprava prikaze: brez prevzorcenja in brez crnih robov.
            # Naprava, ki pove svojo povrsino, dobi zaslon v svoji obliki; starejsa velikost iz kakovosti.
            izvor = velikost_za_gledalca(pogled, (k["sirina"], k["visina"]))
            self.drugi.velikost(*izvor)
            merilo = merilo_za_gledalca(pogled, izvor)
            if hasattr(self.drugi, "osnovno_merilo"):
                self.drugi.osnovno_merilo(merilo)
            sirina, visina = int(izvor[0]), int(izvor[1])
        elif wayland:
            # Portal: uporabnik izbere zaslon (prvic) ali se izbira obnovi; velikost je v logicnih tockah zaslona -
            # v istih tockah gre nazaj vnos (NotifyPointerMotionAbsolute), zato je merilo zaslona (HiDPI) vseeno.
            portal = self._odpri_portal()
            izvor = (portal.tok["sirina"], portal.tok["visina"])
            sirina, visina = self._prilagodi(izvor, k["sirina"], k["visina"])
        else:
            # Vec monitorjev: delimo primarni monitor (prej ves koren, oba zaslona stisnjena v eno sliko - drobno
            # besedilo neberljivo). En monitor ali brez RandR: kot prej, ves zaslon.
            monitor = _deljeni_monitor()
            if monitor and monitor["sirina"] and monitor["visina"]:
                izvor = (monitor["sirina"], monitor["visina"])
                odmik = (monitor["x"], monitor["y"])
            else:
                izvor = _zaslon_geometrija(display) or (NAJVEC_SIRINA, NAJVEC_VISINA)
                odmik = (0, 0)
            vaapi_x11 = vaapi_naprava(self.ffmpeg)
            polna = (kakovost if kakovost in KAKOVOSTI else PRIVZETA_KAKOVOST) == PRIVZETA_KAKOVOST
            # Kodek in velikost: HEVC (tudi 4K) samo ob izrecni zmoznosti naprave in delujocem kodirniku.
            kodek_x11, sirina, visina = izberi_tok(
                kodeki, najvecja, izvor, (k["sirina"], k["visina"]),
                lambda w, h: hevc_vaapi_mozen(self.ffmpeg, vaapi_x11, w, h), polna)
        # KMS samo za namizje X11 z VAAPI (kmsgrab -> hwmap), z enim monitorjem (kmsgrab vzame prvi CRTC) in z znano
        # aktivno sejo (straza med zajemom). Samo H.264: ali pomocnik zna HEVC, ni preverjeno. Pred zaklepom,
        # ker loginctl lahko traja do 3 s.
        if (self.kms and not na_drugem and not wayland and kodek_x11 == "h264" and vaapi_x11
                and tuple(odmik) == (0, 0) and kms_na_voljo() and kms_monitorji() == 1 and seja_aktivna() is True):
            kms = {"sirina": sirina, "visina": visina, "fps": int(k["fps"]), "kodek": "h264",
                   "qp": int(k["qp"])}
        with self._kljucavnica:
            self._kakovost = kakovost if kakovost in KAKOVOSTI else PRIVZETA_KAKOVOST
            self._naprava = id_naprave
            self._zeton = secrets.token_urlsafe(24)
            self._kljucni = OmejevalnikKljucnih()
            self._slika = {"width": sirina, "height": visina, "fps": int(k["fps"])}
            self._izvor = (int(izvor[0]), int(izvor[1]))
            kljuc, potrdilo, self.odtis = zagotovi_potrdilo(self.tls_mapa)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(potrdilo, kljuc)
            posluh = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            posluh.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            posluh.bind(("0.0.0.0", 0))
            posluh.listen(1)
            posluh.settimeout(CAKANJE_S)
            self.vrata = posluh.getsockname()[1]
            self._posluh = posluh
            self._tece_od = time.time()
            self._povezan = False
            self._prek_huba = bool(prek_huba)
            self._zmoznosti = {str(z) for z in (zmoznosti or []) if isinstance(z, str)}
            self._omrezje = str(omrezje or "")[:16]
            # Dolga skupina slik samo gledalcu, ki enot ne izpusca; HEVC samo, ce ga naprava hoce in racunalnik zmore.
            gop = int(k["fps"]) * GOP_DOLG_S if "gop" in self._zmoznosti else 0
            dodatki = {}
            # Zig slike in velika slika veljata samo za namizje X11 (spodaj); drugi zaslon in portal: brez ziga slike (ni izmerjen).
            self._zakasnitev_slike = None
            self._hevc_veliki = False
            if na_drugem:
                self._cilj = "apps"
                self._zajem_dodatno = {}
                self._zvok_vir = self.drugi.zvok_vir()
                self._vnos = self.drugi.vnos
                self._okolje_zajema = self.drugi.okolje()
                graficna = self.drugi.graficna() if hasattr(self.drugi, "graficna") else None
                self._kodek = izberi_kodek(kodeki, lambda: hevc_mozen(self.ffmpeg, graficna))
                if self._kodek != "h264":
                    dodatki["kodek"] = self._kodek
                if gop:
                    dodatki["gop"] = gop
                ukaz = self.drugi.ukaz_zajema(int(k["fps"]), int(k["qp"]), str(k["bitrate"]), **dodatki)
                self._strojno = bool(graficna)

                def sestavi(kodek, raven, _osnova=dict(dodatki)):
                    # Isti zajem z drugim kodekom ali stopnjo - za pot, po kateri gledalec v resnici pride
                    # (kodek_za_pot, kakovost_za_pot). Sestavimo ga sele, ce bo treba.
                    d = {x: y for x, y in _osnova.items() if x != "kodek"}
                    if kodek != "h264":
                        d["kodek"] = kodek
                    return self.drugi.ukaz_zajema(int(raven["fps"]), int(raven["qp"]), str(raven["bitrate"]), **d)
            elif wayland:
                self._cilj = "desktop"
                self._okolje_zajema = None
                self._zvok_vir = privzeti_monitor()
                from core import portal_zaslon
                self._vnos = portal_zaslon.VnosPortal(portal)
                vaapi = vaapi_naprava(self.ffmpeg)
                self._kodek = izberi_kodek(kodeki, lambda: hevc_mozen(self.ffmpeg, vaapi))
                fps = int(k["fps"])
                vhod = portal_zaslon.vhod_ffmpeg(sirina, visina, fps)
                # GStreamer sliko pomanjsa ze sam (koncna velikost), ffmpeg samo kodira.
                ukaz, self._zajem_dodatno = portal_zaslon.ukaz_zajema(
                    portal, sirina, visina, fps,
                    ukaz_ffmpeg("", sirina, visina, sirina, visina, fps, str(k["bitrate"]), vaapi, self.ffmpeg,
                                int(k["qp"]), kodek=self._kodek, gop=gop, vhod=vhod))
                self._strojno = bool(vaapi)

                def sestavi(kodek, raven, _portal=portal):
                    return portal_zaslon.ukaz_zajema(
                        _portal, sirina, visina, int(raven["fps"]),
                        ukaz_ffmpeg("", sirina, visina, sirina, visina, int(raven["fps"]), str(raven["bitrate"]),
                                    vaapi, self.ffmpeg, int(raven["qp"]), kodek=kodek, gop=gop,
                                    vhod=portal_zaslon.vhod_ffmpeg(sirina, visina, int(raven["fps"]))))[0]
            else:
                self._cilj = "desktop"
                self._okolje_zajema = None
                self._zajem_dodatno = {}
                self._zvok_vir = privzeti_monitor()
                self._vnos = Vnos(display=display, odmik=odmik)
                na_monitor = {"odmik": odmik} if tuple(odmik) != (0, 0) else {}
                vaapi = vaapi_x11
                self._kodek = kodek_x11
                self._zakasnitev_slike = zakasnitev_slike(vaapi, sirina, visina, izvor, kodek_x11)
                # Slika nad osnovno velikostjo je mogoca samo s HEVC: te seje ne znizamo na H.264 po poti.
                self._hevc_veliki = kodek_x11 == "hevc" and (sirina, visina) != tuple(
                    self._prilagodi(izvor, k["sirina"], k["visina"]))
                # Preizkus graficne samo, kadar sliko res pomanjsamo (sicer ga ne potrebujemo).
                gpu = (sirina, visina) != tuple(izvor[:2]) and gpu_lestvica_mozna(self.ffmpeg, vaapi)
                ukaz = ukaz_ffmpeg(display, sirina, visina, izvor[0], izvor[1], int(k["fps"]),
                                   str(k["bitrate"]), vaapi, self.ffmpeg, int(k["qp"]),
                                   kodek=self._kodek, gop=gop, gpu=gpu, **na_monitor)
                self._strojno = bool(vaapi)

                def sestavi(kodek, raven):
                    return ukaz_ffmpeg(display, sirina, visina, izvor[0], izvor[1], int(raven["fps"]),
                                       str(raven["bitrate"]), vaapi, self.ffmpeg, int(raven["qp"]),
                                       kodek=kodek, gop=gop, gpu=gpu, **na_monitor)
            self._nit = threading.Thread(target=self._streci, args=(posluh, ctx, ukaz, seja_st, sestavi, kms, display),
                                         name="safeer-zaslon", daemon=True)
            self._nit.start()
        return {"port": self.vrata, "fp": self.odtis, "token": self._zeton, "v": 2,
                "codec": self._kodek, **self._slika, "quality": self._kakovost,
                "audio": {"hz": ZVOK_HZ, "channels": ZVOK_KANALI, "format": "s16le"} if self._zvok_vir else None,
                "input": self._vnos.mozno, "gamepad": self._plosek.mozno(), "screen": self._cilj,
                # Igra: puscice daljinca morajo biti puscice, ne miska.
                "game": self._cilj == "apps" and getattr(self.drugi, "zadnja_skupina", "") == "igre",
                # Racunalnik zna skok po gumbih (dogodek "fokus"); starejsi Control tega ne zna.
                "focus": self._cilj == "apps" and hasattr(self.drugi, "fokus"),
                # Predvajalnik: televizor ga upravlja kot predvajalnik in narise svoj pas za predvajanje.
                "profile": getattr(self.drugi, "zadnji_profil", "") if self._cilj == "apps" else "",
                "media": self._cilj == "apps" and hasattr(self.drugi, "mediji"),
                # Gledalec sme po sliko prek Huba (Global Link); starejsi Control tega polja nima.
                "relay": bool(prek_huba),
                # Merilo locenega zaslona (1 = brez): slika je enako velika, programi so narisani vecje.
                # `scale_max`: do kod sme uporabnik vsebino povecati, da programi se ostanejo celi.
                "scale": merilo, "scale_max": najvecje_merilo(izvor) if na_drugem else 1.0}

    def _odpri_portal(self):
        """Seja portala za deljenje namizja na Waylandu. Napaka -> RuntimeError z besedilom za gledalca."""
        from core import portal_zaslon
        self.ustavi()                 # prejsnja seja (in njen portal) ne sme ostati odprta
        with self._portal_zaklep:
            try:
                seja = portal_zaslon.Seja(vnos=True)
                seja.odpri()
            except portal_zaslon.NapakaPortala as e:
                print("[zaslon] portal:", e.koda, e, flush=True)
                raise RuntimeError(portal_zaslon.SPOROCILA.get(e.koda) or str(e)) from e
        with self._kljucavnica:
            self._portal = seja
        return seja

    @staticmethod
    def _prilagodi(izvor, najvec_sirina, najvec_visina) -> tuple:
        """Ohrani razmerje zaslona in ne povecuj cez izvirnik; sirina in visina morata biti sodi."""
        s, v = izvor
        if s <= 0 or v <= 0:
            return najvec_sirina, najvec_visina
        merilo = min(najvec_sirina / s, najvec_visina / v, 1.0)
        return (max(2, int(s * merilo) // 2 * 2), max(2, int(v * merilo) // 2 * 2))

    def _sprejmi(self, posluh: socket.socket, ctx: ssl.SSLContext):
        """Caka televizor s pravim zetonom. Kdor pride z napacnim (ali brez TLS), ne dobi nicesar in seje tudi
        ne podre - televizor, ki mu je zaslon namenjen, se lahko se vedno poveze. (Prej je prva tuja povezava
        sejo koncala: kdorkoli v omrezju je lahko deljenje zaslona preprecil.)"""
        konec = time.monotonic() + CAKANJE_S

        def prevzeti():
            # Gledalec zdoma ne pride na ta vrata, ampak do Huba; povezavo, ki jo je Hub ze sprejel (TLS z istim
            # potrdilom) in nadgradil, dobimo tu - zeton je preveril prevzemi().
            prevzet = self._vzemi_prevzetega()
            if prevzet is not None:
                try:
                    link_vticnik.brez_zamika(prevzet[0])
                except Exception:  # noqa: BLE001 - nastavitev vticnice je dodatek
                    pass
            return prevzet

        def velja(pozdrav: str) -> bool:
            zeton = self._zeton
            return bool(zeton) and pozdrav.startswith("SAFEER-ZASLON ") and secrets.compare_digest(
                pozdrav.split(" ", 1)[1].strip().encode("utf-8"), zeton.encode("utf-8"))

        # Vsaka povezava ima svoj rok za rokovanje TLS in pozdrav skupaj (ROKOVANJE_S) in tece v svoji niti
        # (link_vticnik.sprejmi_s_pozdravom): prej je vsak bajt pozdrava dobil svojih 10 s (do 42 min na povezavo),
        # povezave pa so se obdelale po vrsti - nekaj tihih je pokrilo ves CAKANJE_S (pregleda 19. 10. 2026).
        # Slika in zvok sta drobni, pogosti okvirji: vsak naj gre takoj, ne sele po potrditvi prejsnjega (brez_zamika).
        odjemalec = link_vticnik.sprejmi_s_pozdravom(
            posluh, ctx, velja, self._preberi_vrstico, konec, ROKOVANJE_S, prej=prevzeti,
            presledek=PREVERI_PREVZETE_S, ob_sprejemu=link_vticnik.brez_zamika)
        if odjemalec is None:
            return None
        if isinstance(odjemalec, tuple):
            return odjemalec
        return odjemalec, None

    # ------------------------------------------------------------------ gledalec prek Huba (Global Link)

    def caka(self, zeton: str) -> bool:
        """Ali seja s tem zetonom caka gledalca. Hub vprasa, preden povezavo nadgradi."""
        z = self._zeton
        if not z or not zeton or self._posluh is None or self._povezan:
            return False
        return secrets.compare_digest(str(zeton).encode("utf-8"), z.encode("utf-8"))

    def prevzemi(self, odjemalec, zeton: str) -> bool:
        """Povezavo gledalca, ki je prisla do Huba (Global Link), preda cakajoci seji in se vrne, ko se seja konca.

        Hub je povezavo ze nadgradil (101); od tu tece po njej isti pretok kot po neposredni: glava JSON, okvirji,
        vnos nazaj. False: seje s tem zetonom ni (vec) - klicatelj povezavo zapre."""
        if not self.caka(zeton):
            return False
        konec = threading.Event()
        with self._kljucavnica:
            self._prevzeti.append((odjemalec, konec, self._seja_st))
        rok = time.monotonic() + CAKANJE_S + 5
        while not konec.wait(0.5):
            with self._kljucavnica:
                se_caka = any(p[0] is odjemalec for p in self._prevzeti)
                # Seja povezavo vzame v nekaj desetinkah sekunde. Ce je ne (medtem ustavljena), ne visimo.
                # Enako, ce je sejo medtem dobil drug gledalec.
                if se_caka and (self._posluh is None or self._povezan or time.monotonic() > rok):
                    self._prevzeti = [p for p in self._prevzeti if p[0] is not odjemalec]
                    return False
        return True

    def _vzemi_prevzetega(self):
        """Povezava, ki jo je Hub predal tej seji: (vticnica, dogodek konca) ali None."""
        with self._kljucavnica:
            while self._prevzeti:
                odjemalec, konec, seja = self._prevzeti.pop(0)
                if seja == self._seja_st:
                    return odjemalec, konec
                konec.set()                 # za sejo, ki je ni vec: Hub povezavo zapre
        return None

    def _streci(self, posluh: socket.socket, ctx: ssl.SSLContext, ukaz: List[str], seja: int,
                sestavi=None, kms: Optional[dict] = None, display: str = "") -> None:
        odjemalec = None
        na_kms = False
        #: Omejevalnik zahtev po kljucnem okvirju te seje; zacni() za naslednjo sejo nastavi novega.
        omejevalnik = self._kljucni
        konec_prevzete = None
        slika = zvok = None
        meritve = None
        #: Konec seje za niti utripa in meritev (finally ga nastavi).
        konec_seje = threading.Event()
        steklo = False
        pot_meritev = ""
        try:
            sprejet = self._sprejmi(posluh, ctx)
            if sprejet is None:
                return
            odjemalec, konec_prevzete = sprejet
            # Sele zdaj vemo, po kateri poti je gledalec prisel. Doma (neposredno): zahtevana kakovost in H.264.
            # Zdoma (prek Huba): kakovost za omrezje gledalca (kakovost_za_pot) in HEVC, ce je dogovorjen
            # (kodek_za_pot). Kodek, kvantizator in stopnjo pove glava toka.
            prek = konec_prevzete is not None
            kodek_seje, raven_ime = self._kodek, self._kakovost
            # Velika slika (nad osnovno velikostjo) je mogoca samo s HEVC: tak kodek velja po vseh poteh.
            kodek_poti = kodek_seje if self._hevc_veliki else kodek_za_pot(kodek_seje, prek)
            raven_poti = kakovost_za_pot(raven_ime, prek, self._omrezje)
            if sestavi is not None and (kodek_poti, raven_poti) != (kodek_seje, raven_ime) \
                    and int(KAKOVOSTI[raven_poti]["fps"]) == int(self._slika["fps"]):
                ukaz = sestavi(kodek_poti, KAKOVOSTI[raven_poti])
                kodek_seje, raven_ime = kodek_poti, raven_poti
            if kms is not None:
                # Zajem KMS je samo H.264 in ima svoj kvantizator: sledi poti (kodek, stopnja).
                kms = dict(kms, qp=int(KAKOVOSTI[raven_ime]["qp"])) if kodek_seje == "h264" else None
            kodirnik = kodirnik_ukaza(ukaz, self._strojno)
            meritve = link_zaslon_meritve.Meritve(pot="hub" if prek else "neposredno", kodek=kodek_seje,
                                                  kakovost=raven_ime, kodirnik=vrsta_kodirnika(kodirnik))
            meritve.opis["zaslon"] = self._cilj
            meritve.opis["lestvica"] = "gpu" if ukaz_pomanjsa_gpu(ukaz) else "cpu"
            # Kam gre povzetek, velja ob zacetku seje (konec seje je v drugi niti, morda po spremembi okolja).
            pot_meritev = pot_povzetkov()
            # Ping v toku samo gledalcu, ki ga zna (caps 'rtt'); glava mu to potrdi. Starejsi gledalec dobi iste
            # bajte kot doslej.
            utrip = "rtt" in self._zmoznosti and rtt_vklopljen()
            glava = glava_toka(self._slika, bool(self._zvok_vir), self._vnos.mozno, self._plosek.mozno(), kodek_seje)
            glava.update({"kodek": kodek_seje, "qp": int(KAKOVOSTI[raven_ime]["qp"]) if self._strojno else 0,
                          "kakovost": raven_ime})
            if utrip:
                glava["rtt"] = True
                glava["kodirnik"] = vrsta_kodirnika(kodirnik)
            odjemalec.sendall((json.dumps(glava) + "\n").encode("utf-8"))
            # Meritev: sidro med napravama (TV zapise glava_prejeta).
            _cas("glava_poslana", seja, zvok=1 if glava.get("zvok") else 0)
            odjemalec.settimeout(None)
            # Sliko in zvok piseta dve niti, vnos bere tretja: vticnica TLS tega sama ne prenese
            # (core/link_vticnik.py). Ovita vticnica obenem jamci, da gre vsak okvir (en sendall) ven cel.
            # Branje sme cakati poljubno dolgo - televizor med gledanjem ne posilja nicesar -, pisanje pa ne.
            odjemalec = link_vticnik.zavaruj(odjemalec)
            if isinstance(odjemalec, link_vticnik.VarnaTls):
                odjemalec.nastavi_rok_pisanja(ROK_PISANJA_S)

            niti = []
            okolje, dodatno = self._okolje_zajema, dict(self._zajem_dodatno)
            zazeni_x11 = lambda: subprocess.Popen(ukaz, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                                  stdin=subprocess.DEVNULL, bufsize=0, env=okolje, **dodatno)
            # Zajem KMS prek pomocnika (do nekaj s) odpremo zunaj kljucavnice; ob vsaki zavrnitvi ostane x11grab kot prej.
            _cas("pred_popen_slika", seja)
            kms_slika = slika_kms(kms, seja) if kms else None
            with self._kljucavnica:
                if self._seja_st != seja or self._posluh is not posluh:
                    if kms_slika is not None:
                        kms_slika.terminate()
                    return                  # medtem ustavljeno ali pa se je zacela nova seja
                # Zajem zazenemo pod kljucem in ga takoj vpisemo: ustavi() ga tako vedno najde.
                if kms_slika is not None:
                    slika, na_kms = kms_slika, True
                    # kmsgrab -> VAAPI ni izmerjen: izrecno brez ziga slike (pred zagonom niti _crpaj).
                    self._zakasnitev_slike = None
                else:
                    slika, _ = odpri_sliko(zazeni_x11, None, seja)
                    # IDR na zahtevo z novim procesom: pri portalu (Wayland) ponovni zagon ni preverjen.
                    slika.idr_na_zahtevo = self._portal is None
                _cas("po_popen_slika", seja)
                self._proces = slika
                self._odjemalec = odjemalec
                self._povezan = True
                self._kodek = kodek_seje
                self._kakovost = raven_ime
                self._meritve = meritve
                prebrano = [0, False]       # bajtov slike in ali je bila v toku ze kaka enota NAL
                niti.append(threading.Thread(target=self._crpaj,
                                             args=(slika, OKVIR_SLIKA, odjemalec, 32 * 1024, prebrano),
                                             kwargs={"merilo": meritve, "kodek": kodek_seje},
                                             name="safeer-zaslon-slika", daemon=True))
                if na_kms:
                    niti.append(threading.Thread(
                        target=strazi_kms, name="safeer-zaslon-kms", daemon=True,
                        args=(slika, zazeni_x11, lambda: kms_stanje(display),
                              lambda: self._proces is slika and slika.poll() is None, seja)))
                if self._zvok_vir:
                    try:
                        _cas("pred_popen_zvok", seja)
                        zvok = subprocess.Popen(ukaz_zvok(self._zvok_vir, self.ffmpeg), stdout=subprocess.PIPE,
                                                stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, bufsize=0)
                        _cas("po_popen_zvok", seja, pid=zvok.pid)
                        self._zvocni = zvok
                        # Zvok beremo v majhnih koscih (10 ms), da ne caka za veliko sliko.
                        niti.append(threading.Thread(target=self._crpaj, args=(zvok, OKVIR_ZVOK, odjemalec, 1920),
                                                     kwargs={"merilo": meritve},
                                                     name="safeer-zaslon-zvok", daemon=True))
                    except Exception:
                        zvok = self._zvocni = None
            print("[zaslon] seja: kodirnik %s, kodek %s, kakovost %s, %dx%d@%d, pot %s%s%s"
                  % (kodirnik, kodek_seje, raven_ime, self._slika["width"], self._slika["height"], self._slika["fps"],
                     meritve.opis["pot"], ", ping v toku" if utrip else "",
                     ", pomanjsa graficna" if ukaz_pomanjsa_gpu(ukaz) else ""), flush=True)
            # Vnos tece nazaj po isti povezavi; brati ga moramo sproti, sicer se vticnica zamasi.
            niti.append(threading.Thread(target=self._beri_vnos, args=(odjemalec,),
                                         kwargs={"meritve": meritve, "slika": slika, "kljucni": omejevalnik},
                                         name="safeer-zaslon-vnos", daemon=True))
            # Meritve: TCP_INFO in dnevnik (vedno; na vticnico ne pise), ping samo gledalcu, ki ga zna.
            niti.append(threading.Thread(target=self._meri, args=(odjemalec, meritve, konec_seje),
                                         name="safeer-zaslon-meritve", daemon=True))
            if utrip:
                niti.append(threading.Thread(target=self._utrip, args=(odjemalec, meritve, konec_seje),
                                             name="safeer-zaslon-utrip", daemon=True))
            if self._cilj == "apps" and self.drugi is not None:
                niti.append(threading.Thread(target=self._strazi_prazno, args=(odjemalec, slika),
                                             name="safeer-zaslon-prazno", daemon=True))
                if hasattr(self.drugi, "mediji"):
                    niti.append(threading.Thread(target=self._porocaj_medij, args=(odjemalec, slika),
                                                 name="safeer-zaslon-medij", daemon=True))
            for n in niti:
                n.start()
            steklo = True
            _cas("niti_zagnane", seja, niti=len(niti))
            niti[0].join()          # dokler tece slika, tece seja
            self._preveri_hevc(slika, kodek_seje, prebrano)
            if not na_kms:                  # ukaz je ukaz x11grab, KMS ima svojega
                self._preveri_gpu(slika, ukaz, prebrano)
        except (OSError, ssl.SSLError, ValueError):
            pass
        finally:
            konec_seje.set()                # niti utripa in meritev nehajo
            if omejevalnik.sprejetih or omejevalnik.zavrnjenih:
                print("[zaslon] kljucni ob koncu seje: sprejetih %d, zavrnjenih %d"
                      % (omejevalnik.sprejetih, omejevalnik.zavrnjenih), flush=True)
            povzetek = self._povzetek(meritve) if steklo else None
            # Najprej shutdown: druge niti (zvok, vnos) drzijo vticnico in sam close televizorju
            # ne bi poslal konca - ta bi gledal zamrznjeno sliko.
            _zapri(odjemalec)
            if konec_prevzete is not None:
                konec_prevzete.set()        # nit Huba, ki je povezavo predala, se vrne
            _koncaj(slika)
            _koncaj(zvok)
            if povzetek is not None:
                print("[zaslon] povzetek seje: %s" % json.dumps(povzetek, ensure_ascii=False), flush=True)
                # V zbirko meritev samo seje, v katerih je slika res tekla: seja brez ene same slike (zajem ni
                # stekel, gledalec je odsel takoj) ni meritev poti in bi pokvarila porazdelitve.
                if meritve.bajtov_slike() > 0:
                    zapisi_povzetek(povzetek, pot_meritev)
            # Seja pospravi samo za sabo. Ce se je medtem zacela nova (televizor se je povezal znova), je ta nit
            # prej ustavila in podrla tudi njo: ustavi() ne loci, cigav je zajem, ki ga konca.
            with self._kljucavnica:
                moja = self._seja_st == seja
                if self._odjemalec is odjemalec:
                    self._odjemalec = None
                if self._meritve is meritve:
                    self._meritve = None
            if moja:
                if self._cilj == "apps" and self.drugi is not None:
                    self._strazi_osirotele(seja)
                    self._pospravi_zvok_po_seji(seja)
                self.ustavi(seja)
            else:
                try:
                    posluh.close()
                except OSError:
                    pass

    def _strazi_osirotele(self, seja: int) -> None:
        """Televizor je izginil sredi seje (ugasnjen, aplikacija zaprta ali posodobljena) in se ne
        vrne: program na locenem zaslonu bi tekel naprej nevidno, dokler ga kdo ne zapre na
        racunalniku. Ce v OSIROTELO_S ni nove seje, ga zapremo - kot bi uporabnik koncal sejo."""
        def straza() -> None:
            time.sleep(OSIROTELO_S)
            if self._seja_st != seja or self._povezan:
                return
            drugi = self.drugi
            if drugi is not None and hasattr(drugi, "zapri_okna") and drugi.okna() > 0:
                print("[zaslon] televizorja ni vec, programi na locenem zaslonu se zapirajo", flush=True)
                drugi.zapri_okna()
        threading.Thread(target=straza, name="safeer-zaslon-osiroteli", daemon=True).start()

    def _pospravi_zvok_po_seji(self, seja: int) -> None:
        """Po koncu seje odstrani navidezni izhod Safeer-TV, ko na drugem zaslonu ni vec programov
        (zaprl jih je uporabnik ali straza osirotelih). Ce program ostane odprt, ostane tudi izhod."""
        drugi = self.drugi
        if drugi is None or not hasattr(drugi, "pospravi_zvok"):
            return

        def straza() -> None:
            konec = time.monotonic() + OSIROTELO_S + 30
            while time.monotonic() < konec:
                time.sleep(ZVOK_POSPRAVI_S)
                if self._seja_st != seja or self._povezan:
                    return
                if drugi.okna() == 0 and drugi.pospravi_zvok():
                    return
        threading.Thread(target=straza, name="safeer-zaslon-zvok-pospravi", daemon=True).start()

    def _strazi_prazno(self, odjemalec, slika: _ProcesSlike) -> None:
        """Ko se zadnji program na drugem zaslonu zapre (igra ob Esc, uporabnik jo zapre), televizor
        sicer gleda temen prazen zaslon. Zato mu to povemo in sejo koncamo - vrne se v Safeer OS."""
        videl = False
        zacetek = time.monotonic()
        prazno_od: Optional[float] = None
        povedal_caka = False
        while self._proces is slika and slika.poll() is None:
            # Dokler okna se ni, gledamo pogosteje: »Odpiram ...« in preklop na namizje naj ne cakata po nepotrebnem.
            time.sleep(0.5 if videl else 0.25)
            zdaj = time.monotonic()
            if self.drugi.okna() > 0:
                if not videl and povedal_caka:
                    self._obvesti(odjemalec, {"program": "odprt"})
                videl, prazno_od = True, None
                continue
            prazno_od = zdaj if prazno_od is None else prazno_od
            podatki: dict = {}
            if videl and zdaj - prazno_od >= PRAZNO_PO_ZAPRTJU_S:
                razlog = "zaprto"
            elif not videl and zdaj - zacetek >= PRAZNO_OD_ZACETKA_S:
                razlog = "ni_okna"
            elif not videl:
                izid = self._izid_zagona()
                if izid == "na_namizju" and "handoff" in self._zmoznosti:
                    # Program je odprt na namizju racunalnika (ena sama instanca): naprava preklopi tja.
                    razlog, podatki = "na_namizju", self._opis_zagona()
                elif izid:
                    # Rod zagona je koncal brez okna: uporabnik ne gleda pol minute praznega zaslona.
                    razlog = "ni_okna"
                else:
                    if not povedal_caka:
                        povedal_caka = True
                        self._obvesti(odjemalec, dict({"program": "caka"}, **self._opis_zagona()))
                    continue
            else:
                continue
            if self._proces is not slika:
                return
            try:
                odjemalec.sendall(_okvir(OKVIR_OBVESTILO,
                                         json.dumps(dict({"konec": razlog}, **podatki)).encode("utf-8")))
            except (OSError, ssl.SSLError, ValueError):
                pass
            print("[zaslon] drugi zaslon je prazen (%s), seja koncana" % razlog, flush=True)
            self.ustavi()
            return

    def _izid_zagona(self) -> str:
        """Izid zadnjega zagona na locenem zaslonu ("" | "koncan" | "na_namizju"); napaka pomeni »ne vemo«."""
        drugi = self.drugi
        if drugi is None or not hasattr(drugi, "izid_zagona"):
            return ""
        try:
            return str(drugi.izid_zagona() or "")
        except Exception:  # noqa: BLE001 - straza praznega zaslona ne sme pasti
            return ""

    def _opis_zagona(self) -> dict:
        drugi = self.drugi
        if drugi is None or not hasattr(drugi, "opis_zagona"):
            return {}
        try:
            return dict(drugi.opis_zagona() or {})
        except Exception:  # noqa: BLE001
            return {}

    @staticmethod
    def _koda_odpovedi(slika: subprocess.Popen, prebrano) -> Optional[int]:
        """Koda izhoda zajema, ki je koncal SAM in brez ene same enote NAL; None, ce je slika tekla, ce zajem se tece
        ali ce smo ga ustavili mi (konec seje: negativna koda)."""
        if prebrano[1]:
            return None
        try:
            koda = slika.wait(timeout=1.0)
        except Exception:  # noqa: BLE001 - zajem se tece: to ni odpoved kodirnika
            return None
        return koda if isinstance(koda, int) and koda >= 0 else None

    @staticmethod
    def _preveri_hevc(slika: subprocess.Popen, kodek: str, prebrano) -> None:
        """Zajem s HEVC, ki konca SAM in brez ene same enote NAL, na tem racunalniku ne deluje (kratek preizkus z
        ffmpeg je sicer uspel): do ponovnega zagona Controla ostanemo pri H.264. Naprava sejo zahteva znova sama.
        Zajem, ki smo ga ustavili mi (konec seje), ima negativno kodo izhoda in ne steje."""
        if kodek != "hevc":
            return
        koda = Zaslon._koda_odpovedi(slika, prebrano)
        if koda is not None:
            hevc_odpovedal()
            print("[zaslon] zajem s HEVC ni dal slike (koda %d): do ponovnega zagona ostanemo pri H.264" % koda,
                  flush=True)

    @staticmethod
    def _preveri_gpu(slika: subprocess.Popen, ukaz, prebrano) -> None:
        """Kot _preveri_hevc za pomanjsavo na graficni: zajem s scale_vaapi, ki konca sam in brez slike - do ponovnega
        zagona Controla sliko pomanjsa procesor (stara pot). Ce je hkrati HEVC, padeta oba: varneje ob dvomu."""
        if not ukaz_pomanjsa_gpu(ukaz):
            return
        koda = Zaslon._koda_odpovedi(slika, prebrano)
        if koda is not None:
            gpu_odpovedal()
            print("[zaslon] zajem s pomanjsavo na graficni ni dal slike (koda %d): do ponovnega zagona pomanjsa "
                  "procesor" % koda, flush=True)

    def _zahteva_kljucni(self, slika: "_ProcesSlike", omejevalnik: OmejevalnikKljucnih) -> bool:
        """Televizor prosi za nov kljucni okvir (dekodirnik je ponastavljen ali slika pokvarjena).

        Odgovor je nov pretok s SPS, PPS in IDR iz novega procesa slike; zvok in povezava tecejo
        naprej. Omejitev je tu, na racunalniku, ker televizorju (staremu ali tujemu) ne zaupamo."""
        dovoljeno = omejevalnik.dovoli()
        # Samo proces te seje; po ustavi() je self._proces None ali ze proces nove seje.
        zamenjano = dovoljeno and self._proces is slika and slika.znova()
        stevilo = omejevalnik.zavrnjenih
        sprejetih = omejevalnik.sprejetih
        if dovoljeno:
            # Sprejeta zahteva = nov ffmpeg; dnevnik redcimo enako kot zavrnjene (poplava).
            izpisi = not zamenjano or sprejetih in (1, 10, 100) or sprejetih % 500 == 0
        else:
            izpisi = stevilo in (1, 10, 100) or stevilo % 500 == 0
        if izpisi:
            print("[zaslon] kljucni %s: sprejetih %d, zavrnjenih %d" % (
                "nov proces slike" if zamenjano else ("zagon ni uspel" if dovoljeno else "zavrnjen"),
                omejevalnik.sprejetih, stevilo), flush=True)
        return bool(zamenjano)

    def _crpaj(self, proces, vrsta: int, odjemalec, kos: int, prebrano=None,
               merilo=None, kodek: str = "h264") -> None:
        """Bere en vir (slika ali zvok) in ga v okvirjih poslje televizorju. Vsak okvir je en `sendall`
        na oviti vticnici, ta pa jamci, da se okvirja dveh virov nikoli ne prepleteta.

        Kljucavnica za pisanje je tako del povezave in ne vec del tega objekta: prej je pisanje stare seje, ki je
        obstalo (televizor je izginil brez slovesa), drzalo kljucavnico tudi novi seji - televizor se je povezal
        znova, slike pa ni dobil, dokler jedro stare povezave ni opustilo.

        `merilo` (core/link_zaslon_meritve.Meritve): vsak sendall izmerimo - koliko bajtov in koliko casa je cakal;
        zacni_pisanje pred njim, da je zastoj viden, medtem ko traja.

        Zigi zajema (okvir OKVIR_ZIG pred sliko ali zvokom, v istem sendall): zvok iz stetja bajtov (ZigiZvoka), slika samo za
        svez kos H.264 iz izmerjenega kodirnika (ZigiSlike, `proces.svez`); `kodek` je kodek te seje."""
        tihih = 0
        # Meritev: lokalne zastavice pripadajo samo tej niti (en _crpaj na vir na sejo), brez kljucavnic na vroci poti.
        seja_cas = self._seja_st
        ime_cas = "slika" if vrsta == OKVIR_SLIKA else ("zvok" if vrsta == OKVIR_ZVOK else str(vrsta))
        prvo_branje_cas = prvo_poslano_cas = po_5s_cas = True
        neprazen_cas = vrsta != OKVIR_ZVOK   # tisino iscemo samo pri zvoku
        bajti_cas = 0
        t_prvo_cas = 0
        zigi_zvoka = ZigiZvoka(ZVOK_HZ, ZVOK_KANALI) if vrsta == OKVIR_ZVOK else None
        # Zig slike samo za H.264 (izmerjen x264); HEVC ni izmerjen, zato None tudi ob zamenjani seji.
        zakasnitev = self._zakasnitev_slike if kodek == "h264" else None
        zigi_slike = ZigiSlike(zakasnitev, kodek) if vrsta == OKVIR_SLIKA else None
        poslano = 0
        poravnav_prej = 0
        try:
            while True:
                podatki = proces.stdout.read(kos)
                if not podatki:
                    break
                if prebrano is not None:
                    prebrano[0] += len(podatki)
                    if not prebrano[1] and ZACETEK_NAL in podatki:
                        prebrano[1] = True
                prebrano_ms = ura_ms()
                bajti_cas += len(podatki)
                if prvo_branje_cas:
                    prvo_branje_cas = False
                    t_prvo_cas = time.monotonic_ns() // 1_000_000
                    # Slika: prvi kos iz kodirnika = prvi okvir slike; zvok: prvi kos iz pulse.
                    _cas("prvi_okvir_slika" if vrsta == OKVIR_SLIKA else "prvo_branje_" + ime_cas,
                         seja_cas, bajti=len(podatki))
                if not neprazen_cas and podatki.count(0) != len(podatki):
                    neprazen_cas = True
                    _cas("prvi_zvok_neprazen", seja_cas, bajti_skupaj=bajti_cas)
                # Zig izracunamo za VSAK kos (tudi za tisino, ki je ne posljemo): stetje bajtov ZigiZvoka mora videti vse.
                if zigi_zvoka is not None:
                    zig = zigi_zvoka.zig(len(podatki), prebrano_ms)
                    if zigi_zvoka.poravnav != poravnav_prej:
                        # Poravnava je lahko tudi trajna zakasnitev (zaostanek v pulse): velikost v dnevnik.
                        poravnav_prej = zigi_zvoka.poravnav
                        _cas("zvok_poravnava", seja_cas, ms=int(round(zigi_zvoka.zadnja_poravnava_ms)),
                             stevilo=poravnav_prej)
                elif zigi_slike is not None:
                    zig = zigi_slike.zig(podatki, prebrano_ms)
                    # Meje slik stejemo vedno (stanje ZigiSlike), zig pa samo za svez kos: ne za konec
                    # starega toka in ne za prvi kos novega procesa po zamenjavi (cakal je v cevi).
                    # Vir, ki svezosti ne pove (nima svez), zig slike nima: varno privzeto.
                    if not getattr(proces, "svez", False):
                        zig = None
                else:
                    zig = None
                if vrsta == OKVIR_ZVOK:
                    # Popolna tisina (sami nicelni bajti): po kratkem repu je ne posiljamo - 1,5 Mb/s za nic.
                    if podatki.count(0) == len(podatki):
                        tihih += 1
                        if tihih > ZVOK_REP_TISINE:
                            continue
                    else:
                        tihih = 0
                # Zig in okvir gresta kot EN niz bajtov v en sendall (druga nit ne more vriniti okvirja vmes).
                okvir = _okvir_z_zigom(vrsta, zig, poslano, podatki)
                if merilo is None:
                    odjemalec.sendall(okvir)
                else:
                    try:
                        merilo.zacni_pisanje(vrsta)     # zastoj je v meritvah viden, medtem ko traja
                    except Exception:  # noqa: BLE001 - meritev ne sme ustaviti slike
                        pass
                    zacetek = time.monotonic()
                    predano = 0
                    try:
                        odjemalec.sendall(okvir)
                        predano = len(okvir)
                    finally:
                        # Tudi pisanje, ki pade (rok pisanja), je cakalo: steje v zasedenost, bajtov pa nima.
                        try:
                            merilo.poslano(vrsta, predano, time.monotonic() - zacetek)
                        except Exception:  # noqa: BLE001 - meritev ne sme ustaviti slike
                            pass
                poslano += len(podatki)
                if prvo_poslano_cas:
                    prvo_poslano_cas = False
                    _cas("prvi_bajt_" + ime_cas, seja_cas, bajti=len(podatki), bajti_skupaj=bajti_cas)
                if po_5s_cas and time.monotonic_ns() // 1_000_000 - t_prvo_cas >= 5000:
                    po_5s_cas = False
                    # Zvok v realnem casu: ~5 s * 192000 B/s = 960000 B; precej vec = sunek zaostanka iz pulse.
                    _cas(ime_cas + "_po_5s", seja_cas, bajti_skupaj=bajti_cas)
        except (OSError, ssl.SSLError, ValueError, AttributeError):
            pass

    def _v_zaslon(self, dogodek: dict) -> dict:
        """Tocka iz slike (kot jo vidi tablica) v tocko zaslona: slika je lahko pomanjsana."""
        try:
            x, y = float(dogodek.get("x")), float(dogodek.get("y"))
        except (TypeError, ValueError):
            return dogodek
        sw, sv = max(1, self._slika.get("width", 1)), max(1, self._slika.get("height", 1))
        iw, iv = self._izvor
        return {"vrsta": "tocka", "x": int(min(max(x, 0), sw - 1) * iw / sw),
                "y": int(min(max(y, 0), sv - 1) * iv / sv)}

    def _obvesti(self, odjemalec, podatki: dict) -> None:
        """Obvestilo televizorju po isti povezavi kot slika (okvir izbire, kazalec za povecavo ...)."""
        try:
            odjemalec.sendall(_okvir(OKVIR_OBVESTILO, json.dumps(podatki).encode("utf-8")))
        except (OSError, ssl.SSLError, ValueError):
            pass

    # ------------------------------------------------------------------ meritve seje (1. faza: samo merimo)

    def _utrip(self, odjemalec, meritve, konec: threading.Event) -> None:
        """Nit 'safeer-zaslon-utrip' (samo gledalcu, ki zna 'rtt' in mu je glava to potrdila): vsakih UTRIP_S ping
        v obvestilu {"rtt": {"n", "t", "z"}}. Cas zabelezimo PRED pisanjem: ping, ki obtici za vrsto, ze caka.
        `t` je nasa monotona ura v ms (gledalec ga samo vrne), `z` zadnji izmerjeni zamik za prikaz na gledalcu."""
        n = 0
        while not konec.is_set():
            n += 1
            t = int(time.monotonic() * 1000)
            meritve.ping_poslan(n, t)
            self._obvesti(odjemalec, {"rtt": {"n": n, "t": t, "z": meritve.zadnji_rtt()}})
            if konec.wait(UTRIP_S):
                return

    def _meri(self, odjemalec, meritve, konec: threading.Event) -> None:
        """Nit 'safeer-zaslon-meritve': enkrat na sekundo TCP_INFO vticnice seje, vsakih MERITVE_DNEVNIK_S vrstica
        v dnevnik. Na vticnico ne pise nikoli (bralni klic jedra, mimo TLS)."""
        dnevnik = time.monotonic()
        while not konec.wait(MERITVE_S):
            try:
                meritve.tcp(link_vticnik.tcp_info(odjemalec))
                if time.monotonic() - dnevnik >= MERITVE_DNEVNIK_S:
                    dnevnik = time.monotonic()
                    print("[zaslon] meritve: %s" % link_zaslon_meritve.opis_posnetka(meritve.posnetek()), flush=True)
            except Exception:  # noqa: BLE001 - meritve ne smejo podreti seje
                pass

    @staticmethod
    def _povzetek(meritve) -> Optional[dict]:
        """Vrstica za zaslon-seje.jsonl ob koncu seje (cas konca in povzetek meritev) ali None."""
        if meritve is None:
            return None
        try:
            return dict({"cas": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, **meritve.povzetek())
        except Exception:  # noqa: BLE001 - povzetek je samo opazovanje
            return None

    def _nastavi_merilo(self, odjemalec, dogodek: dict) -> None:
        """Naprava hoce vecje ali manjse gumbe programov na locenem zaslonu (meni seje). Slika, ki jo posiljamo,
        ostane enako velika in seja tece naprej. Na pravem zaslonu (cilj `desktop`) dogodek nima ucinka."""
        drugi = self.drugi
        if self._cilj != "apps" or drugi is None or not hasattr(drugi, "osnovno_merilo"):
            return
        try:
            zeljeno = float(dogodek.get("merilo"))
        except (TypeError, ValueError):
            return
        if not math.isfinite(zeljeno) or zeljeno <= 0:
            return
        merilo = merilo_za_gledalca({"scale": zeljeno}, self._izvor)
        drugi.osnovno_merilo(merilo)
        self._obvesti(odjemalec, {"merilo": merilo, "najvec": najvecje_merilo(self._izvor)})

    def _fokus(self):
        drugi = getattr(self._vnos, "drugi", None)
        return getattr(drugi, "fokus", None) if self._cilj == "apps" else None

    def _odpre_tipkovnico(self, dogodek) -> bool:
        """OK (klik) na polju za besedilo, izbranem s skokom: televizor naj odpre tipkovnico."""
        f = self._fokus()
        if f is None or not isinstance(dogodek, dict) or dogodek.get("vrsta") != "klik":
            return False
        if str(dogodek.get("gumb", "levi") or "levi") != "levi" or dogodek.get("dvojni"):
            return False
        e, t = f.izbira, f.tocka
        return bool(e is not None and len(e) > 7 and e[7] and t is not None
                    and abs(t[0] - e[0]) < 1 and abs(t[1] - e[1]) < 1)

    def _po_vnosu(self, odjemalec, dogodek, tipkovnica: bool, imel_izbiro: bool = False) -> None:
        f = self._fokus()
        if f is None or not isinstance(dogodek, dict):
            return
        vrsta = dogodek.get("vrsta")
        if vrsta == "klik" and imel_izbiro:
            def potrdi() -> None:
                time.sleep(0.35)
                if f.izbira is None:          # uporabnik je medtem ze premaknil kazalec
                    return
                e = f.osvezi_izbiro()
                self._obvesti(odjemalec, {"izbira": [int(e[2]), int(e[3]), int(e[4]), int(e[5])]
                                          if e is not None else None})
            threading.Thread(target=potrdi, name="safeer-izbira", daemon=True).start()
        if vrsta == "fokus":
            e = f.izbira
            self._obvesti(odjemalec, {
                "izbira": [int(e[2]), int(e[3]), int(e[4]), int(e[5])] if e is not None else None,
                "brez_gumbov": bool(f.brez_gumbov), "profil": f.profil()})
        if tipkovnica:
            self._obvesti(odjemalec, {"tipkovnica": True})
        if getattr(self._vnos, "porocaj_kazalec", False) and vrsta in ("premik", "fokus", "povecava") \
                and f.tocka is not None:
            self._obvesti(odjemalec, {"kazalec": [int(f.tocka[0]), int(f.tocka[1])]})

    def _beri_vnos(self, odjemalec, meritve=None, slika=None, kljucni=None) -> None:
        """Dogodki televizorja (ena vrstica JSON na dogodek). Kar ni na seznamu dovoljenega, pade.

        Odmev pinga ({"vrsta": "rtt", ...}) gre v `meritve` seje (core/link_zaslon_meritve.py) - nikoli do vnosa,
        plosecka ali stevca vnosov."""
        ostanek = b""
        try:
            while True:
                kos = odjemalec.recv(4096)
                if not kos:
                    break
                ostanek += kos
                while b"\n" in ostanek:
                    vrstica, ostanek = ostanek.split(b"\n", 1)
                    if len(vrstica) > 4096:
                        continue
                    try:
                        dogodek = json.loads(vrstica.decode("utf-8", "replace"))
                    except (ValueError, RecursionError):
                        continue
                    if isinstance(dogodek, dict) and dogodek.get("vrsta") == "kljucni":
                        if slika is not None and kljucni is not None:
                            try:
                                self._zahteva_kljucni(slika, kljucni)
                            except Exception as e:  # zamenjava slike ne sme ustaviti vnosa
                                print("[zaslon] kljucni napaka: %s" % type(e).__name__, flush=True)
                        continue
                    if isinstance(dogodek, dict) and dogodek.get("vrsta") == "rtt":
                        if meritve is not None:
                            try:
                                meritve.pong(dogodek, time.monotonic())
                            except Exception:  # noqa: BLE001 - meritev ne sme ustaviti vnosa
                                pass
                        continue
                    if isinstance(dogodek, dict) and dogodek.get("vrsta") == "tocka":
                        dogodek = self._v_zaslon(dogodek)
                    if isinstance(dogodek, dict) and dogodek.get("vrsta") == "medij":
                        self._medij(odjemalec, dogodek)
                        continue
                    if isinstance(dogodek, dict) and dogodek.get("vrsta") == "merilo":
                        self._nastavi_merilo(odjemalec, dogodek)
                        continue
                    tipkovnica = self._odpre_tipkovnico(dogodek)
                    f = self._fokus()
                    imel_izbiro = f is not None and f.izbira is not None
                    if self._plosek_dogodek(dogodek) or self._vnos.izvedi(dogodek):
                        self._po_vnosu(odjemalec, dogodek, tipkovnica, imel_izbiro)
                        self._vnosov += 1
                        # Redko, a dovolj, da se v dnevniku vidi, da vnos res prihaja skozi.
                        if self._vnosov in (1, 10, 100) or self._vnosov % 500 == 0:
                            print("[zaslon] vnos #%d: %s" % (self._vnosov, dogodek.get("vrsta")), flush=True)
                if len(ostanek) > 8192:
                    ostanek = b""
        except (OSError, ssl.SSLError, ValueError):
            pass
        finally:
            # Povezava je padla ali se koncala: kar je televizor drzal, mora zdaj gor.
            self._vnos.sprosti_vse()
            self._plosek.zapri()

    @staticmethod
    def _preberi_vrstico(s: socket.socket, najvec: int = 256, rok: Optional[float] = None) -> str:
        """Vrstica pozdrava; z `rok` (time.monotonic) mora priti cela do tedaj, sicer socket.timeout."""
        zbrano = b""
        while len(zbrano) < najvec:
            if rok is not None:
                ostane = rok - time.monotonic()
                if ostane <= 0:
                    raise socket.timeout("pozdrav ni prisel pravocasno")
                s.settimeout(ostane)
            b = s.recv(1)
            if not b or b == b"\n":
                break
            zbrano += b
        return zbrano.decode("utf-8", "replace")

    def _mediji(self):
        return getattr(self.drugi, "mediji", None) if self._cilj == "apps" and self.drugi is not None else None

    def _medij(self, odjemalec, dogodek: dict) -> None:
        """Ukaz za predvajalnik (predvajaj/pavza, previj). Najprej MPRIS; kjer ga ni, tipka."""
        m = self._mediji()
        ukaz = str(dogodek.get("ukaz", "") or "")
        try:
            sekund = float(dogodek.get("s", 0) or 0)
        except (TypeError, ValueError):
            sekund = 0.0
        if m is not None and m.ukaz(ukaz, sekund):
            # Pas na televizorju naj takoj pokaze novo stanje, ne sele ob naslednjem porocilu.
            stanje = m.stanje()
            if stanje is not None:
                self._obvesti(odjemalec, {"medij": stanje})
            return
        tipka = dogodek_v_tipko(dogodek)
        if tipka is not None:
            self._vnos.izvedi(tipka)

    def _porocaj_medij(self, odjemalec, slika: _ProcesSlike) -> None:
        """Vsako sekundo: stanje predvajalnika na locenem zaslonu (samo ko se spremeni)."""
        zadnje: Optional[dict] = None
        poslano = False
        while self._proces is slika and slika.poll() is None:
            m = self._mediji()
            stanje = m.stanje() if m is not None else None
            if stanje != zadnje or not poslano:
                if stanje is not None or poslano:
                    self._obvesti(odjemalec, {"medij": stanje})
                    poslano = True
                zadnje = stanje
            time.sleep(1.0)

    def _plosek_dogodek(self, dogodek: dict) -> bool:
        """Gumb ali os igralnega plosecka s televizorja. Vse drugo pusti vnosu (tipke, miska)."""
        if not isinstance(dogodek, dict):
            return False
        vrsta = str(dogodek.get("vrsta", "") or "")
        if vrsta == "plosek_gumb":
            return self._plosek.gumb(str(dogodek.get("gumb", "") or ""), bool(dogodek.get("dol")))
        if vrsta == "plosek_os":
            return self._plosek.os(str(dogodek.get("os", "") or ""), dogodek.get("vrednost"))
        return False

    def ustavi(self, seja: Optional[int] = None, pocakaj_s: float = 0.0) -> None:
        """Konca zajem in zapre vrata; zeton takoj ne velja vec.

        Nit seje, ki pospravlja za sabo, poda svojo stevilko `seja`: ce se je medtem zacela nova seja, klic ne
        naredi nicesar (sicer bi konec stare seje ustavil novo).

        Nit seje konca sama (povzetek meritev zapise sele, ko se crpalka ustavi). `pocakaj_s` > 0 jo pocaka najvec
        toliko - ob izhodu programa, da povzetek zadnje seje ni izgubljen. Privzeto ne caka nihce (nova seja,
        izklop, screen.stop); nit seje sama sebe nikoli."""
        with self._kljucavnica:
            if seja is not None and self._seja_st != seja:
                return
            nit = self._nit
            proces, zvocni, posluh, odjemalec = self._proces, self._zvocni, self._posluh, self._odjemalec
            prevzeti, self._prevzeti = self._prevzeti, []
            portal, self._portal = self._portal, None
            self._proces = None
            self._zvocni = None
            self._posluh = None
            self._odjemalec = None
            self._povezan = False
            self._zeton = ""
            self.vrata = 0
            self._tece_od = 0.0
        for _vticnica, dogodek, _seja in prevzeti:
            dogodek.set()                   # povezave, ki jih seja ni vec prevzela: Hub jih zapre
        self._vnos.sprosti_vse()
        self._plosek.zapri()
        for p in (proces, zvocni):
            _koncaj(p)
        if portal is not None:
            portal.zapri()          # GNOME ugasne oznako deljenja v zgornji vrstici
        # Niti seje lahko visijo na povezavi (pisanje televizorju, ki ne bere vec; branje vnosa). Konec zajema jih
        # ne zbudi; shutdown jih. Brez tega je stara seja zivela naprej in ob svojem koncu podrla naslednjo.
        _zapri(odjemalec)
        if posluh is not None:
            # Nit visi v accept(); samo close() je ne prebudi vedno, shutdown() pa jo.
            try:
                posluh.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                posluh.close()
            except Exception:
                pass
        if pocakaj_s > 0 and nit is not None and nit is not threading.current_thread():
            nit.join(pocakaj_s)


__all__ = ["Zaslon", "ukaz_ffmpeg", "vaapi_naprava", "KAKOVOSTI", "PRIVZETA_KAKOVOST",
           "presodi_kljucni", "OmejevalnikKljucnih", "KLJUCNI_OKNO_S", "KLJUCNI_NAJVEC",
           "OKVIR_ZIG", "ZIG_GLAVA", "ura_ms", "ZigiZvoka", "ZigiSlike", "zakasnitev_slike",
           "KMS_VTICNIK", "kms_na_voljo", "odpri_kms", "slika_kms", "odpri_sliko", "strazi_kms",
           "NAJVEC_HEVC", "hevc_vaapi_mozen", "izberi_tok", "glava_toka"]
