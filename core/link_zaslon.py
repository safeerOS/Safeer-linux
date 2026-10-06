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

import json
import math
import os
import shutil
import socket
import secrets
import ssl
import subprocess
import threading
import time
from typing import Dict, List, Optional

from core import link_vticnik
from core.link_datoteke import TLS_MAPA, zagotovi_potrdilo
from core.link_mediji import dogodek_v_tipko
from core.link_plosek import Plosek
from core.link_vnos import Vnos

#: Vrste okvirjev v pretoku.
OKVIR_SLIKA, OKVIR_ZVOK = 1, 2
#: Obvestilo racunalnika (JSON), npr. {"konec": "zaprto"}: na drugem zaslonu ni vec nobenega
#: programa. Starejsi televizorji okvir te vrste preskocijo.
OKVIR_OBVESTILO = 3
#: Koliko casa program na locenem zaslonu caka na televizor, ki je izginil, preden ga zapremo.
OSIROTELO_S = 90
#: Kako pogosto po koncu seje preverimo, ali je drugi zaslon prazen in lahko pospravimo zvok.
ZVOK_POSPRAVI_S = 5.0


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


def vaapi_naprava() -> Optional[str]:
    """Naprava za strojno kodiranje (Intel/AMD); None, kadar je ni."""
    for ime in ("renderD128", "renderD129"):
        pot = os.path.join("/dev/dri", ime)
        if os.path.exists(pot):
            return pot
    return None


def ukaz_ffmpeg(display: str, sirina: int, visina: int, izvor_sirina: int, izvor_visina: int,
                fps: int, bitrate: str, vaapi: Optional[str], ffmpeg: str = "ffmpeg",
                qp: int = 24, kodek: str = "h264", gop: int = 0) -> List[str]:
    """Ukaz za zajem in kodiranje. Strojno (VAAPI), ce je mogoce, sicer x264 brez zamika.

    `kodek`: "hevc" samo strojno (pri istem kvantizatorju manj bajtov); brez VAAPI vedno H.264.
    `gop`: razmik kljucnih slik v slikah; 0 = vsako sekundo (starejsi gledalec).
    Locen od zagona, da ga je mogoce preveriti v testu brez kamere in zaslona.
    """
    hevc = kodek == "hevc" and bool(vaapi)
    u = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
         "-f", "x11grab", "-draw_mouse", "1", "-framerate", str(fps),
         "-video_size", f"{izvor_sirina}x{izvor_visina}", "-i", display]
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
        u += ["-vaapi_device", vaapi,
              "-vf", f"{filter_lestvica}format=nv12,hwupload",
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
    zvocni_vticnik = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid()), "pulse", "native")
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


class Zaslon:
    """Deljenje zaslona racunalnika s televizorjem: ena seja naenkrat, samo na uporabnikov ukaz."""

    ZMOZNOST = "desktop"

    def __init__(self, tls_mapa: str = TLS_MAPA, ffmpeg: Optional[str] = None,
                 vklopljeno: bool = False) -> None:
        self.tls_mapa = tls_mapa
        #: Uporabnik mora deljenje zaslona vklopiti v Safeer Controlu; privzeto je izklopljeno.
        self.vklopljeno = bool(vklopljeno)
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
        self._proces: Optional[subprocess.Popen] = None
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
        self._vnosov = 0
        self._tece_od = 0.0
        self._povezan = False
        self._kljucavnica = threading.Lock()

    # ------------------------------------------------------------------ stanje

    def na_voljo(self) -> dict:
        """Ali ta racunalnik sploh zna deliti zaslon in s cim."""
        display = os.environ.get("DISPLAY", "")
        vaapi = vaapi_naprava()
        return {
            "dovoljeno": self.vklopljeno,
            "mozno": bool(self.ffmpeg) and bool(display),
            "ffmpeg": bool(self.ffmpeg),
            "zaslon": display,
            "strojno": bool(vaapi),
            "zvok": bool(privzeti_monitor()),
            "vnos": self._vnos.mozno,
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
              omrezje: str = "") -> dict:
        """Pripravi sejo: odpre TLS vrata in caka televizor. Zajem se zacne sele, ko se ta javi.

        `pogled`: povrsina naprave, ki gleda (`view` iz `screen.start`). Loceni zaslon dobi njeno obliko in
        velikost; pravega zaslona racunalnika ne spreminjamo nikoli.
        `prek_huba`: gledalec zna po sliko tudi do vrat Huba (pot `/cast/desktop`, Global Link). Po kateri poti res
        pride, vemo sele ob povezavi: takrat izberemo kodek (kodek_za_pot) in stopnjo (kakovost_za_pot).
        `omrezje`: omrezje naprave, ki gleda (`net`: wifi, ethernet, 5g, 4g ...); po njem je umerjena kakovost zdoma."""
        if not self.vklopljeno:
            raise RuntimeError("Deljenje zaslona ni vklopljeno")
        if not self.ffmpeg:
            raise RuntimeError("Na tem racunalniku ni ffmpeg")
        display = os.environ.get("DISPLAY", "")
        if not display:
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
        if na_drugem:
            # Drugi zaslon je natanko tako velik, kot ga naprava prikaze: brez prevzorcenja in brez crnih robov.
            # Naprava, ki pove svojo povrsino, dobi zaslon v svoji obliki; starejsa velikost iz kakovosti.
            izvor = velikost_za_gledalca(pogled, (k["sirina"], k["visina"]))
            self.drugi.velikost(*izvor)
            merilo = merilo_za_gledalca(pogled, izvor)
            if hasattr(self.drugi, "osnovno_merilo"):
                self.drugi.osnovno_merilo(merilo)
            sirina, visina = int(izvor[0]), int(izvor[1])
        else:
            izvor = _zaslon_geometrija(display) or (NAJVEC_SIRINA, NAJVEC_VISINA)
            sirina, visina = self._prilagodi(izvor, k["sirina"], k["visina"])
        with self._kljucavnica:
            self._kakovost = kakovost if kakovost in KAKOVOSTI else PRIVZETA_KAKOVOST
            self._naprava = id_naprave
            self._zeton = secrets.token_urlsafe(24)
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
            if na_drugem:
                self._cilj = "apps"
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
            else:
                self._cilj = "desktop"
                self._okolje_zajema = None
                self._zvok_vir = privzeti_monitor()
                self._vnos = Vnos(display=display)
                vaapi = vaapi_naprava()
                self._kodek = izberi_kodek(kodeki, lambda: hevc_mozen(self.ffmpeg, vaapi))
                ukaz = ukaz_ffmpeg(display, sirina, visina, izvor[0], izvor[1], int(k["fps"]),
                                   str(k["bitrate"]), vaapi, self.ffmpeg, int(k["qp"]),
                                   kodek=self._kodek, gop=gop)
                self._strojno = bool(vaapi)

                def sestavi(kodek, raven):
                    return ukaz_ffmpeg(display, sirina, visina, izvor[0], izvor[1], int(raven["fps"]),
                                       str(raven["bitrate"]), vaapi, self.ffmpeg, int(raven["qp"]),
                                       kodek=kodek, gop=gop)
            self._nit = threading.Thread(target=self._streci, args=(posluh, ctx, ukaz, seja_st, sestavi),
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
        while time.monotonic() < konec:
            # Gledalec zdoma ne pride na ta vrata, ampak do Huba; povezavo, ki jo je Hub ze sprejel (TLS z istim
            # potrdilom) in nadgradil, dobimo tu - zeton je preveril prevzemi().
            prevzet = self._vzemi_prevzetega()
            if prevzet is not None:
                try:
                    link_vticnik.brez_zamika(prevzet[0])
                except Exception:  # noqa: BLE001 - nastavitev vticnice je dodatek
                    pass
                return prevzet
            posluh.settimeout(max(0.05, min(PREVERI_PREVZETE_S, konec - time.monotonic())))
            try:
                surov, _ = posluh.accept()
            except socket.timeout:
                continue
            odjemalec = None
            try:
                surov.settimeout(ROKOVANJE_S)
                # Slika in zvok sta drobni, pogosti okvirji: vsak naj gre takoj, ne sele po potrditvi prejsnjega.
                link_vticnik.brez_zamika(surov)
                odjemalec = ctx.wrap_socket(surov, server_side=True)
                pozdrav = self._preberi_vrstico(odjemalec)
                zeton = self._zeton
                if zeton and pozdrav.startswith("SAFEER-ZASLON ") and secrets.compare_digest(
                        pozdrav.split(" ", 1)[1].strip().encode("utf-8"), zeton.encode("utf-8")):
                    return odjemalec, None
            except (OSError, ssl.SSLError, ValueError):
                pass
            _zapri(odjemalec if odjemalec is not None else surov)
        return None

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
                sestavi=None) -> None:
        odjemalec = None
        konec_prevzete = None
        slika = zvok = None
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
            kodek_poti = kodek_za_pot(kodek_seje, prek)
            raven_poti = kakovost_za_pot(raven_ime, prek, self._omrezje)
            if sestavi is not None and (kodek_poti, raven_poti) != (kodek_seje, raven_ime) \
                    and int(KAKOVOSTI[raven_poti]["fps"]) == int(self._slika["fps"]):
                ukaz = sestavi(kodek_poti, KAKOVOSTI[raven_poti])
                kodek_seje, raven_ime = kodek_poti, raven_poti
            glava = {"v": 2, "w": self._slika["width"], "h": self._slika["height"],
                     "fps": self._slika["fps"], "kodek": kodek_seje,
                     "qp": int(KAKOVOSTI[raven_ime]["qp"]) if self._strojno else 0, "kakovost": raven_ime,
                     "zvok": {"hz": ZVOK_HZ, "kanali": ZVOK_KANALI, "oblika": "s16le"} if self._zvok_vir else None,
                     "vnos": self._vnos.mozno, "plosek": self._plosek.mozno()}
            odjemalec.sendall((json.dumps(glava) + "\n").encode("utf-8"))
            odjemalec.settimeout(None)
            # Sliko in zvok piseta dve niti, vnos bere tretja: vticnica TLS tega sama ne prenese
            # (core/link_vticnik.py). Ovita vticnica obenem jamci, da gre vsak okvir (en sendall) ven cel.
            # Branje sme cakati poljubno dolgo - televizor med gledanjem ne posilja nicesar -, pisanje pa ne.
            odjemalec = link_vticnik.zavaruj(odjemalec)
            if isinstance(odjemalec, link_vticnik.VarnaTls):
                odjemalec.nastavi_rok_pisanja(ROK_PISANJA_S)

            niti = []
            with self._kljucavnica:
                if self._seja_st != seja or self._posluh is not posluh:
                    return                  # medtem ustavljeno ali pa se je zacela nova seja
                # Zajem zazenemo pod kljucem in ga takoj vpisemo: ustavi() ga tako vedno najde.
                slika = subprocess.Popen(ukaz, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                         stdin=subprocess.DEVNULL, bufsize=0, env=self._okolje_zajema)
                self._proces = slika
                self._odjemalec = odjemalec
                self._povezan = True
                self._kodek = kodek_seje
                self._kakovost = raven_ime
                prebrano = [0, False]       # bajtov slike in ali je bila v toku ze kaka enota NAL
                niti.append(threading.Thread(target=self._crpaj,
                                             args=(slika, OKVIR_SLIKA, odjemalec, 32 * 1024, prebrano),
                                             name="safeer-zaslon-slika", daemon=True))
                if self._zvok_vir:
                    try:
                        zvok = subprocess.Popen(ukaz_zvok(self._zvok_vir, self.ffmpeg), stdout=subprocess.PIPE,
                                                stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, bufsize=0)
                        self._zvocni = zvok
                        # Zvok beremo v majhnih koscih (10 ms), da ne caka za veliko sliko.
                        niti.append(threading.Thread(target=self._crpaj, args=(zvok, OKVIR_ZVOK, odjemalec, 1920),
                                                     name="safeer-zaslon-zvok", daemon=True))
                    except Exception:
                        zvok = self._zvocni = None
            # Vnos tece nazaj po isti povezavi; brati ga moramo sproti, sicer se vticnica zamasi.
            niti.append(threading.Thread(target=self._beri_vnos, args=(odjemalec,),
                                         name="safeer-zaslon-vnos", daemon=True))
            if self._cilj == "apps" and self.drugi is not None:
                niti.append(threading.Thread(target=self._strazi_prazno, args=(odjemalec, slika),
                                             name="safeer-zaslon-prazno", daemon=True))
                if hasattr(self.drugi, "mediji"):
                    niti.append(threading.Thread(target=self._porocaj_medij, args=(odjemalec, slika),
                                                 name="safeer-zaslon-medij", daemon=True))
            for n in niti:
                n.start()
            niti[0].join()          # dokler tece slika, tece seja
            self._preveri_hevc(slika, kodek_seje, prebrano)
        except (OSError, ssl.SSLError, ValueError):
            pass
        finally:
            # Najprej shutdown: druge niti (zvok, vnos) drzijo vticnico in sam close televizorju
            # ne bi poslal konca - ta bi gledal zamrznjeno sliko.
            _zapri(odjemalec)
            if konec_prevzete is not None:
                konec_prevzete.set()        # nit Huba, ki je povezavo predala, se vrne
            _koncaj(slika)
            _koncaj(zvok)
            # Seja pospravi samo za sabo. Ce se je medtem zacela nova (televizor se je povezal znova), je ta nit
            # prej ustavila in podrla tudi njo: ustavi() ne loci, cigav je zajem, ki ga konca.
            with self._kljucavnica:
                moja = self._seja_st == seja
                if self._odjemalec is odjemalec:
                    self._odjemalec = None
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

    def _strazi_prazno(self, odjemalec, slika: subprocess.Popen) -> None:
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
    def _preveri_hevc(slika: subprocess.Popen, kodek: str, prebrano) -> None:
        """Zajem s HEVC, ki konca SAM in brez ene same enote NAL, na tem racunalniku ne deluje (kratek preizkus z
        ffmpeg je sicer uspel): do ponovnega zagona Controla ostanemo pri H.264. Naprava sejo zahteva znova sama.
        Zajem, ki smo ga ustavili mi (konec seje), ima negativno kodo izhoda in ne steje."""
        if kodek != "hevc" or prebrano[1]:
            return
        try:
            koda = slika.wait(timeout=1.0)
        except Exception:  # noqa: BLE001 - zajem se tece: to ni odpoved kodirnika
            return
        if isinstance(koda, int) and koda >= 0:
            hevc_odpovedal()
            print("[zaslon] zajem s HEVC ni dal slike (koda %d): do ponovnega zagona ostanemo pri H.264" % koda,
                  flush=True)

    def _crpaj(self, proces: subprocess.Popen, vrsta: int, odjemalec, kos: int, prebrano=None) -> None:
        """Bere en vir (slika ali zvok) in ga v okvirjih poslje televizorju. Vsak okvir je en `sendall`
        na oviti vticnici, ta pa jamci, da se okvirja dveh virov nikoli ne prepleteta.

        Kljucavnica za pisanje je tako del povezave in ne vec del tega objekta: prej je pisanje stare seje, ki je
        obstalo (televizor je izginil brez slovesa), drzalo kljucavnico tudi novi seji - televizor se je povezal
        znova, slike pa ni dobil, dokler jedro stare povezave ni opustilo."""
        tihih = 0
        try:
            while True:
                podatki = proces.stdout.read(kos)
                if not podatki:
                    break
                if prebrano is not None:
                    prebrano[0] += len(podatki)
                    if not prebrano[1] and ZACETEK_NAL in podatki:
                        prebrano[1] = True
                if vrsta == OKVIR_ZVOK:
                    # Popolna tisina (sami nicelni bajti): po kratkem repu je ne posiljamo - 1,5 Mb/s za nic.
                    if podatki.count(0) == len(podatki):
                        tihih += 1
                        if tihih > ZVOK_REP_TISINE:
                            continue
                    else:
                        tihih = 0
                odjemalec.sendall(_okvir(vrsta, podatki))
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

    def _beri_vnos(self, odjemalec) -> None:
        """Dogodki televizorja (ena vrstica JSON na dogodek). Kar ni na seznamu dovoljenega, pade."""
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
                    except ValueError:
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
    def _preberi_vrstico(s: socket.socket, najvec: int = 256) -> str:
        zbrano = b""
        while len(zbrano) < najvec:
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

    def _porocaj_medij(self, odjemalec, slika: subprocess.Popen) -> None:
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

    def ustavi(self, seja: Optional[int] = None) -> None:
        """Konca zajem in zapre vrata; zeton takoj ne velja vec.

        Nit seje, ki pospravlja za sabo, poda svojo stevilko `seja`: ce se je medtem zacela nova seja, klic ne
        naredi nicesar (sicer bi konec stare seje ustavil novo)."""
        with self._kljucavnica:
            if seja is not None and self._seja_st != seja:
                return
            proces, zvocni, posluh, odjemalec = self._proces, self._zvocni, self._posluh, self._odjemalec
            prevzeti, self._prevzeti = self._prevzeti, []
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


__all__ = ["Zaslon", "ukaz_ffmpeg", "vaapi_naprava", "KAKOVOSTI", "PRIVZETA_KAKOVOST"]
