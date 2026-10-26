"""Naloga 131: debrid storitve v Medijskem centru - TorBox, Real-Debrid, AllDebrid (kot Safeer OS za Android, naloge
119, 128, 129 in 130). Storitev torrent prenese namesto racunalnika (njegov IP ni v roju) in ga pretaka s svojega streznika.

Tu so samo ciste odlocitve brez omrezja (preizkus: tests/test_debrid_pravila.py); odjemalci in izbira so v core/debrid.py.

Iz dokumentacije (prebrano 24. 10. 2026, ne ugibano):
- TorBox: `https://api.torbox.app/v1/api`, glava `Authorization: Bearer <kljuc>`; checkcached (do 100 hashev naenkrat),
  createtorrent (60 nepredpomnjenih na uro), mylist, requestdl - SAMO ta zahteva kljuc kot parameter `token` (tak naslov se
  nikoli ne zapise in ne gre predvajalniku).
- Real-Debrid: `https://api.real-debrid.com/rest/1.0`, Bearer; addMagnet -> torrents/info -> selectFiles -> info
  (»downloaded«, links) -> unrestrict/link. Preverjanja predpomnjenja (instantAvailability) od novembra 2024 ni.
- AllDebrid: `https://api.alldebrid.com/v4`, Bearer; magnet/upload (`ready`) -> magnet/files -> link/unlock (link ali delayed).
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

TORBOX = "torbox"
REAL_DEBRID = "realdebrid"
ALLDEBRID = "alldebrid"

#: Privzeti vrstni red (ce uporabnik ne izbere prednostne storitve).
VSI = (TORBOX, REAL_DEBRID, ALLDEBRID)
#: Indeksator Usenet v pravilih kljucev (= usenet_pravila.VRSTA; ta modul ga ne uvozi - krozni uvoz).
INDEKSATOR = "usenet"

TORBOX_OSNOVA = "https://api.torbox.app/v1/api/torrents"
RD_OSNOVA = "https://api.real-debrid.com/rest/1.0"
AD_OSNOVA = "https://api.alldebrid.com/v4"

NAPAKA_KLJUC = "kljuc"
NAPAKA_MEJA = "meja"
NAPAKA_PAKET = "paket"
NAPAKA_NI_DATOTEKE = "ni_datoteke"
NAPAKA_PRENASA = "prenasa"
NAPAKA_STREZNIK = "streznik"
NAPAKA_NI_PREDPOMNJENO = "ni_predpomnjeno"

#: Oznaka pred imenom vira, ki ga ima storitev pripravljenega (takoj predvajljiv).
OZNAKA_PREDPOMNJEN = "⚡"


def ime(ponudnik: str) -> str:
    return {TORBOX: "TorBox", REAL_DEBRID: "Real-Debrid", ALLDEBRID: "AllDebrid"}.get(ponudnik, ponudnik)


def kje_kljuc(ponudnik: str) -> str:
    """Kje uporabnik dobi kljuc (prikaz ob vnosu)."""
    return {TORBOX: "torbox.app → Settings → API", REAL_DEBRID: "real-debrid.com/apitoken",
            ALLDEBRID: "alldebrid.com/apikeys"}.get(ponudnik, "")


_KLJUC = re.compile(r"[A-Za-z0-9_-]{16,128}")


def ocisti_kljuc(vnos: object) -> Optional[str]:
    """Kljuc, kot ga uporabnik prilepi: brez presledkov, 16-128 znakov, samo crke, stevke, '-' in '_'. Sicer None
    (prilepljena vrstica z naslovom ali presledki ni kljuc)."""
    k = str(vnos or "").strip()
    return k if _KLJUC.fullmatch(k) else None


def glava_avtorizacije(kljuc: str) -> str:
    return "Bearer " + kljuc


def vrstni_red(z_kljucem: Iterable[str], prednostna: Optional[str]) -> list[str]:
    """Storitve s kljucem; [prednostna] (ce ima kljuc) prva, ostale po VSI."""
    ima = [p for p in VSI if p in set(z_kljucem)]
    if prednostna in ima:
        return [prednostna] + [p for p in ima if p != prednostna]
    return ima


def aktivna(z_kljucem: Iterable[str], prednostna: Optional[str], izklopljeno: bool) -> Optional[str]:
    """Storitev, prek katere gredo torrenti (izbira »Debrid« ob zvrsteh). Privzeto prva s kljucem; [izklopljeno] =
    uporabnik je izbral »Brez debrida«. None = torrenti ne gredo prek debrida."""
    if izklopljeno:
        return None
    red = vrstni_red(z_kljucem, prednostna)
    return red[0] if red else None


def razlog_za_uporabnika(napake: Sequence[str]) -> str:
    """Ko nobena storitev ni dala povezave: najbolj pomenljiva napaka (kljuc > meja > paket > ni datoteke > ni
    predpomnjeno > prenasa > streznik)."""
    for n in (NAPAKA_KLJUC, NAPAKA_MEJA, NAPAKA_PAKET, NAPAKA_NI_DATOTEKE, NAPAKA_NI_PREDPOMNJENO, NAPAKA_PRENASA, NAPAKA_STREZNIK):
        if n in napake:
            return n
    return NAPAKA_STREZNIK


def poskusi_s_cakanjem(samo_predpomnjeno: bool, napake: Sequence[str]) -> bool:
    """Skupno pravilo (tests/skupni-primeri): vse storitve so rekle »ni predpomnjeno«. Za izbiro storitve, ki res caka,
    uporabi [cakalna_storitev] (Grokov pregled 25. 10. 2026)."""
    return not samo_predpomnjeno and bool(napake) and all(n == NAPAKA_NI_PREDPOMNJENO for n in napake)


def razlog_po_storitvah(napake: Sequence[tuple]) -> str:
    """Razlog za uporabnika iz (storitev, napaka) po vrstnem redu poskusov (prednostna prva) - kot Android
    (DebridPravila.razlogPoStoritvah, Grokov pregled 25. 10. 2026). Ce je katera storitev rekla »ni predpomnjeno«, je
    razlog to: ob cakanju jo bo ta storitev res prenesla ([cakalna_storitev]); zavrnjen kljuc, meja ali rok drugih tega
    ne preglasi. Prej je napaka druge storitve (npr. rok RD) preglasila »ni predpomnjeno« in cakanja ni bilo."""
    if any(n == NAPAKA_NI_PREDPOMNJENO for _p, n in napake):
        return NAPAKA_NI_PREDPOMNJENO
    return razlog_za_uporabnika([n for _p, n in napake])


def cakalna_storitev(samo_predpomnjeno: bool, napake: Sequence[tuple]) -> Optional[str]:
    """Storitev, ki torrent prenese, ko uporabnik dovoli cakanje (2. krog): prva po vrstnem redu, ki je rekla »ni
    predpomnjeno«. Prej je cakala samo prva storitev - ce je ta padla na roku ali kljucu, ni cakal nihce. None = nihce
    ne caka (»samo takoj« ali nobena storitev ni rekla »ni predpomnjeno«)."""
    if samo_predpomnjeno:
        return None
    return next((p for p, n in napake if n == NAPAKA_NI_PREDPOMNJENO), None)


def ponudnik_napake(napake: Sequence[tuple]) -> str:
    """Storitev, ki jo sporocilo napake imenuje: prva z napako, ki jo uporabnik vidi ([razlog_po_storitvah]). "" = ni
    poskusov."""
    if not napake:
        return ""
    razlog = razlog_po_storitvah(napake)
    return next((p for p, n in napake if n == razlog), napake[0][0])


# ---------------------------------------------------------------------- pospravljanje: brisemo samo svoje

#: Rezerva za locljivost ure streznika (glava Date je na sekundo): torrent, dodan najvec toliko pred odgovorom na nase
#: dodajanje, se steje za nasega. Primerjamo samo uri istega streznika - ura racunalnika ne odloca.
DODANO_REZERVA_MS = 10_000

_ISO_CAS = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")


def rd_dodano_ms(added: object) -> Optional[int]:
    """Real-Debrid »added« (torrents/info, ISO 8601, npr. 2026-10-25T01:02:03.000Z ali +01:00) v ms; brez pasu = UTC.
    None = ga ni ali ni berljiv."""
    from datetime import datetime, timedelta, timezone
    m = _ISO_CAS.match(str(added or "").strip())
    if not m:
        return None
    try:
        t = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    pas = m.group(2) or "Z"
    zamik = 0
    if pas != "Z":
        znak = -1 if pas[0] == "-" else 1
        hh, mm = int(pas[1:3]), int(pas[-2:])
        zamik = znak * (hh * 60 + mm)
    t = t.replace(tzinfo=timezone(timedelta(minutes=zamik)))
    return int(t.timestamp() * 1000)


def ad_dodano_ms(upload_date: object) -> Optional[int]:
    """AllDebrid »uploadDate« (magnet/status, sekunde Unix) v ms; None = ga ni."""
    try:
        v = int(upload_date)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return v * 1000 if v > 0 else None


def dodal_smo_mi(dodano_ms: Optional[int], odgovor_dodajanja_ms: Optional[int]) -> bool:
    """Ali je torrent dodal ta poskus (smemo ga izbrisati): cas dodajanja po uri streznika (RD »added«, AD »uploadDate«)
    ni starejsi od glave Date odgovora na nase dodajanje (ura istega streznika) z rezervo DODANO_REZERVA_MS. Torrenta,
    ki ga je minuto prej dodala druga naprava, ne izbrisemo. Neznan cas ali brez glave Date = ne."""
    return (dodano_ms is not None and odgovor_dodajanja_ms is not None and odgovor_dodajanja_ms > 0
            and dodano_ms >= odgovor_dodajanja_ms - DODANO_REZERVA_MS)


#: Najvec bajtov odgovora API debrid storitve (JSON) - ista meja kot Android (DebridPravila.NAJVEC_ODGOVORA, Grokov
#: pregled 25. 10. 2026: prej branje brez meje).
NAJVEC_ODGOVORA = 8 * 1024 * 1024


# ---------------------------------------------------------------------- preverba kljuca ob vnosu

#: Lastnik 25. 10. 2026 (kljuc TorBox na prenosniku kot na TV): kljuc preverimo ob vnosu z »user/me« (nic ne doda v
#: racun). Odgovor nosi tudi e-naslov racuna - iz njega vzamemo SAMO paket, nic ne gre v dnevnik ali vmesnik.
TORBOX_UPORABNIK = "https://api.torbox.app/v1/api/user/me"
#: Polje »plan« (TorBox API): 0 Free, 1 Essential, 2 Pro, 3 Standard. Usenet ima samo Pro.
TORBOX_PAKETI = {0: "Free", 1: "Essential", 2: "Pro", 3: "Standard"}
TORBOX_PRO = 2

#: Real-Debrid in AllDebrid: podatki racuna (nic ne doda v racun). Odgovor nosi uporabnisko ime in e-naslov - iz njega
#: vzamemo samo izid preverbe (Android DebridPravila.RD_UPORABNIK, AD_UPORABNIK).
RD_UPORABNIK = RD_OSNOVA + "/user"
AD_UPORABNIK = AD_OSNOVA + "/user"

#: Izidi preverbe (skupni primeri kljuci-preverba.json imajo Androidova imena velja/ne_velja - tekac jih preslika).
PREVERBA_VELJAVEN = "veljaven"
PREVERBA_NEVELJAVEN = "neveljaven"       # storitev je kljuc zavrnila: ne shranimo
PREVERBA_MEJA = "meja"                   # storitev odgovori »prevec zahtev« - kljuc je verjetno dober: nepreverjen
PREVERBA_NI_ODGOVORA = "ni_odgovora"     # brez povezave ali napaka streznika: nepreverjen, preverba znova
PREVERBA_OBLIKA = "oblika"               # to ni kljuc (presledki, naslov, prekratek, vzorec): ne shranimo

#: Stanje shranjenega kljuca - vezano na kljuc (odtis_stanja), nikoli med naprave.
STANJE_VELJA = "velja"
STANJE_NE_VELJA = "ne_velja"
STANJE_NEPREVERJEN = "nepreverjen"

#: Nepreverjen kljuc (izpad ob vpisu) preverimo znova najvec tako pogosto (Android PREVERI_ZNOVA_MS).
PREVERI_ZNOVA_S = 600.0

_KLJUC_TORBOX = re.compile(r"[A-Za-z0-9_-]{20,128}")     # Android TorBoxPravila.ocistiKljuc
_KLJUC_INDEKSATORJA = re.compile(r"[A-Za-z0-9_-]{8,128}")  # = usenet_pravila.ocisti_kljuc
_BESEDE_VZORCA = ("xxxxxx", "your_", "your-", "yourapi", "yourkey", "apikey", "api_key", "api-key", "kljuc", "example",
                  "placeholder")


def je_vzorec_kljuca(kljuc: object) -> bool:
    """Lastnik 25. 10. 2026: na eni napravi je bil v polje TorBox vpisan vzorec »XXXXXXXX-XXXX-…« in Safeer ga je shranil
    kot »kljuc vpisan ✓« (Android ga je nato z usklajevanjem raznesel po ozjem krogu). Vzorec iz navodil ali nadomestek,
    ne pravi kljuc: najvec 3 razlicni znaki, en znak v vsaj polovici crk in stevk ali besede vzorca. Nakljucni kljuci
    storitev (UUID, 20-52 znakov) imajo 10+ razlicnih znakov. Kot Android DebridPravila.jeVzorecKljuca (isDecimal =
    Kotlin isDigit, isalpha = isLetter)."""
    k = str(kljuc or "")
    z = "".join(c for c in k if c.isalpha() or c.isdecimal()).lower()
    if not z:
        return True
    pogostost = Counter(z)
    return (len(pogostost) <= 3 or max(pogostost.values()) * 2 >= len(z)
            or any(b in k.lower() for b in _BESEDE_VZORCA))


def kljuc_iz_vnosa(vnos: object, ponudnik: str) -> Optional[str]:
    """Vnos uporabnika ali prejet kljuc: oblika (TorBox 20-128 znakov, Real-Debrid in AllDebrid 16-128, indeksator
    Usenet 8-128; samo A-Z a-z 0-9 - _, presledki ob robu odpadejo) in ne vzorec. None = to ni kljuc (PREVERBA_OBLIKA)."""
    k = str(vnos or "").strip()
    oblika = _KLJUC_TORBOX if ponudnik == TORBOX else _KLJUC_INDEKSATORJA if ponudnik == INDEKSATOR else _KLJUC
    return k if oblika.fullmatch(k) and not je_vzorec_kljuca(k) else None


def preverba_iz_napake(vrsta: str) -> str:
    """Napaka storitve (NAPAKA_*) -> izid preverbe: zavrnjen kljuc ne velja; paket pomeni, da storitev kljuc pozna."""
    return {NAPAKA_KLJUC: PREVERBA_NEVELJAVEN, NAPAKA_MEJA: PREVERBA_MEJA,
            NAPAKA_PAKET: PREVERBA_VELJAVEN}.get(vrsta, PREVERBA_NI_ODGOVORA)


def stanje_po_preverbi(izid: str) -> Optional[str]:
    """Ali kljuc shranimo in s katerim stanjem: zavrnjen ali ne-kljuc ne (None); izpad ali meja ga ne zavrne (nepreverjen)."""
    return {PREVERBA_VELJAVEN: STANJE_VELJA, PREVERBA_MEJA: STANJE_NEPREVERJEN,
            PREVERBA_NI_ODGOVORA: STANJE_NEPREVERJEN}.get(izid)


def shrani_po_preverbi(izid: str) -> bool:
    """Kljuc shranimo, razen ce ni kljuc ali ga je storitev zavrnila (izpad storitve ne sme zavrniti dobrega kljuca)."""
    return stanje_po_preverbi(izid) is not None


def za_uskladitev(stanje: Optional[str]) -> bool:
    """Med naprave v ozjem krogu gre samo kljuc, ki ga je storitev potrdila. Namizje kljucev se ne usklajuje
    (secrets.sync ni): pravilo je tu, da ga uskladitev uporabi od prvega dne."""
    return stanje == STANJE_VELJA


def sprejmi_prejetega(izid: str) -> bool:
    """Prejet kljuc se uporabi samo, ce ga storitev potrdi tudi s te naprave - zavrnjen ne prepise veljavnega."""
    return izid == PREVERBA_VELJAVEN


def preveri_zdaj(stanje: Optional[str], zadnjic: float, zdaj: float) -> bool:
    """Ali kljuc brez stanja ali nepreverjen preverimo zdaj: najvec enkrat na PREVERI_ZNOVA_S za TA kljuc ([zadnjic] =
    zadnja preverba tega kljuca v s, 0 = se ni bil preverjen); ura nazaj = preveri. Veljaven in zavrnjen ne (zavrnjen
    se ne ponavlja - ponavljanje zavrnjenega kljuca lahko storitev steje kot napad in zaklene racun ali IP).
    Lastnik 26. 10. 2026 (»Nevarnost zaklepa racuna je prioriteta«): prej je bil kljuc brez stanja preverjen ob VSAKEM
    odprtju okna, dokler se stanje ni zapisalo - ce zapis ne uspe, je bil vsak klik nov klic storitve."""
    return stanje in (None, STANJE_NEPREVERJEN) and not 0 <= zdaj - zadnjic < PREVERI_ZNOVA_S


def samodejno_s_kljucem(stanje: Optional[str]) -> bool:
    """Ali kljuc uporabimo v klicu, ki ga ni sprozil uporabnik (⚡ checkcached ob seznamu virov, iskanje in prenos NZB
    Usenet, preverba Usenet »pripravljen«). Kljuca, ki ga je storitev zavrnila (»ne velja«), ne posiljamo znova sami:
    vsak tak klic je se en zavrnjen vpis pri storitvi (lastnik 26. 10. 2026: zaklep racuna). Uporabnik ga vpise znova;
    izrecno predvajanje ga se poskusi (uspeh ga vrne v »velja«)."""
    return stanje != STANJE_NE_VELJA


def odtis_stanja(kljuc: str) -> str:
    """Stanje velja za natanko ta kljuc (zamenjan kljuc nima stanja prejsnjega); kljuc iz odtisa ni berljiv.
    Isti odtis kot Android (SHA-256 s predpono, prvih 16 heks)."""
    return hashlib.sha256(("safeer-debrid-stanje|" + kljuc).encode("utf-8")).hexdigest()[:16]


def _niz(v: object) -> Optional[str]:
    return v if isinstance(v, str) and v not in ("", "null") else None


def _stevilo(v: object) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def torbox_preverba(http: int, odgovor: object) -> tuple:
    """Odgovor TORBOX_UPORABNIK -> (izid PREVERBA_*, paket ali None). Polja strogo: success mora biti true, plan stevilo
    >= 0 (iz odgovora samo paket - e-naslov racuna nikamor)."""
    j = odgovor if isinstance(odgovor, dict) else {}
    if 200 <= http < 300 and j.get("success") is True and isinstance(j.get("data"), dict):
        plan = _stevilo(j["data"].get("plan"))
        return PREVERBA_VELJAVEN, plan if plan is not None and plan >= 0 else None
    if not http:
        return PREVERBA_NI_ODGOVORA, None
    return preverba_iz_napake(torbox_vrsta_napake(http, _niz(j.get("error")))), None


def rd_preverba(http: int, odgovor: object) -> str:
    """Odgovor RD_UPORABNIK -> PREVERBA_*. VELJA samo s pozitivnim dokazom (Grokov pregled 36, D1, 26. 10. 2026): 2xx s
    podatkom racuna (id kot stevilo ali username kot niz) brez error_code. 2xx brez njiju ({} posrednika, prijavna stran
    javnega omrezja, ki ni JSON) ni potrditev - »ni odgovora«. 403 brez error_code ni odgovor Real-Debrida o kljucu, ampak
    pozarnega zidu, CDN ali blokade IP (VPN, podatkovni center) - »ni odgovora«; prej »velja« (rd_vrsta_napake: 403 =
    paket), zato je napacen kljuc dobil »kljuc velja ✓« in bi sel med naprave. error_code samo kot stevilo."""
    if not http:
        return PREVERBA_NI_ODGOVORA
    j = odgovor if isinstance(odgovor, dict) else None
    koda = _stevilo(j.get("error_code")) if j is not None else None
    if koda is None and 200 <= http < 300:
        racun = j is not None and (_stevilo(j.get("id")) is not None or _niz(j.get("username")) is not None)
        return PREVERBA_VELJAVEN if racun else PREVERBA_NI_ODGOVORA
    if koda is None and http == 403:
        return PREVERBA_NI_ODGOVORA
    return preverba_iz_napake(rd_vrsta_napake(http, koda))


def ad_preverba(http: int, odgovor: object) -> str:
    """Odgovor AD_UPORABNIK -> PREVERBA_*: status »success« velja; AllDebrid napako (AUTH_*) vrne tudi s HTTP 200."""
    j = odgovor if isinstance(odgovor, dict) else {}
    if 200 <= http < 300 and j.get("status") == "success":
        return PREVERBA_VELJAVEN
    if not http:
        return PREVERBA_NI_ODGOVORA
    e = j.get("error")
    return preverba_iz_napake(ad_vrsta_napake(http, _niz(e.get("code")) if isinstance(e, dict) else None))


def ime_paketa(paket: object) -> str:
    """Ime paketa TorBox za sporocilo; neznano stevilo -> »paket N«, brez paketa prazno."""
    if not isinstance(paket, int) or isinstance(paket, bool):
        return ""
    return TORBOX_PAKETI.get(paket, "paket %d" % paket)


# ---------------------------------------------------------------------- napake storitev

def torbox_vrsta_napake(http: int, koda: Optional[str]) -> str:
    """Zavrnjen kljuc je samo koda TorBox v telesu ali HTTP 401 (Grokov pregled 36, D1/D4, 26. 10. 2026): 403 BREZ kode
    TorBox ni odgovor TorBoxa o kljucu - api.torbox.app je za Cloudflare, ki zahtevo z IP VPN ali podatkovnega centra
    zavrne s 403 in stranjo HTML. Prej je tak 403 kljuc zavrnil ob vpisu in ga med uporabo trajno oznacil »ne velja«;
    403 s PLAN_RESTRICTED_FEATURE (npr. Usenet brez paketa Pro) je bil zavrnjen kljuc namesto paketa."""
    if koda in ("NO_AUTH", "BAD_TOKEN", "AUTH_ERROR") or http == 401:
        return NAPAKA_KLJUC
    if koda in ("ACTIVE_LIMIT", "COOLDOWN_LIMIT", "MONTHLY_LIMIT") or http == 429:
        return NAPAKA_MEJA
    if koda in ("PLAN_RESTRICTED_FEATURE", "DOWNLOAD_TOO_LARGE"):
        return NAPAKA_PAKET
    if koda in ("BOZO_TORRENT", "ITEM_NOT_FOUND", "LINK_OFFLINE"):
        return NAPAKA_NI_DATOTEKE
    return NAPAKA_STREZNIK


def rd_pripravljen(stanje: str) -> bool:
    return str(stanje or "").lower() == "downloaded"


def rd_koncna_napaka(stanje: str) -> bool:
    return str(stanje or "").lower() in ("error", "virus", "dead", "magnet_error")


def rd_vrsta_napake(http: int, koda: Optional[int]) -> str:
    """Koda Real-Debrid ima prednost pred HTTP (37 »disabled endpoint« pride tudi s 403, a ni stvar paketa)."""
    if koda == 8:
        return NAPAKA_KLJUC
    if koda in (9, 14, 20, 29):
        return NAPAKA_PAKET
    if koda in (5, 21, 23, 34, 36):
        return NAPAKA_MEJA
    if koda in (24, 28, 30, 35):
        return NAPAKA_NI_DATOTEKE
    if koda is not None:
        return NAPAKA_STREZNIK
    if http == 401:
        return NAPAKA_KLJUC
    if http == 403:
        return NAPAKA_PAKET
    if http == 429:
        return NAPAKA_MEJA
    return NAPAKA_STREZNIK


def ad_vrsta_napake(http: int, koda: Optional[str]) -> str:
    k = str(koda or "")
    if k.startswith("AUTH_") or http == 401:
        return NAPAKA_KLJUC
    if k in ("MUST_BE_PREMIUM", "MAGNET_MUST_BE_PREMIUM", "FREE_TRIAL_LIMIT_REACHED"):
        return NAPAKA_PAKET
    if k in ("MAGNET_TOO_MANY_ACTIVE", "MAGNET_TOO_MANY") or http in (429, 503):
        return NAPAKA_MEJA
    if k.startswith("MAGNET_INVALID") or k in ("MAGNET_NO_URI", "LINK_DOWN"):
        return NAPAKA_NI_DATOTEKE
    return NAPAKA_STREZNIK


# ---------------------------------------------------------------------- torrent in datoteke

_HEKS = re.compile(r"[0-9a-f]{40}")


def je_hash(h: object) -> bool:
    return bool(_HEKS.fullmatch(str(h or "").strip().lower()))


def magnet(hash_: str, ime_datoteke: str = "", sledilniki: Sequence[str] = ()) -> str:
    """Magnet iz hasha dodatka (Stremio infoHash), z imenom in sledilniki, ce jih dodatek da."""
    from urllib.parse import quote
    m = "magnet:?xt=urn:btih:" + str(hash_).strip().lower()
    if ime_datoteke:
        m += "&dn=" + quote(ime_datoteke, safe="")
    for s in list(sledilniki)[:20]:
        m += "&tr=" + quote(str(s), safe="")
    return m


@dataclass(frozen=True)
class Datoteka:
    id: int
    ime: str
    velikost: int
    mime: str = ""


_VIDEO = {"mkv", "mp4", "m4v", "avi", "webm", "mov", "ts", "m2ts", "wmv", "mpg", "mpeg"}
_ZVOK = {"mp3", "flac", "m4a", "aac", "ogg", "opus", "wav"}


def je_predvajljiva(d: Datoteka) -> bool:
    konc = d.ime.rsplit(".", 1)[-1].lower() if "." in d.ime else ""
    return d.mime.startswith(("video/", "audio/")) or konc in _VIDEO or konc in _ZVOK


def izberi_datoteko(datoteke: Sequence[Datoteka], indeks: Optional[int]) -> Optional[Datoteka]:
    """Datoteka, ki jo pove dodatek (fileIdx), ce je predvajljiva; sicer najvecja predvajljiva (film, ne vzorec)."""
    if indeks is not None and 0 <= indeks < len(datoteke) and je_predvajljiva(datoteke[indeks]):
        return datoteke[indeks]
    pred = [d for d in datoteke if je_predvajljiva(d)]
    return max(pred, key=lambda d: d.velikost) if pred else None


def torbox_pripravljen(stanje: str, koncano: bool, prisoten: bool) -> bool:
    return bool(koncano or prisoten or str(stanje or "").lower() in ("cached", "completed", "uploading"))


NAJVEC_NOVIH_NA_URO = 60
URA_S = 3600.0


def meja_novih_dovoli(casi: Sequence[float], zdaj: float) -> bool:
    """TorBox: najvec 60 NEPREDPOMNJENIH torrentov na uro na kljuc (predpomnjen se ne steje)."""
    return sum(1 for c in casi if 0 <= zdaj - c < URA_S) < NAJVEC_NOVIH_NA_URO


CAKAJ_NOVEGA_S = 180.0
CAKAJ_KORAK_S = 5.0

# ---------------------------------------------------------------------- naloga 130: ⚡ in samodejna izbira

#: Najvec hashev v eni preverbi predpomnjenja TorBox (checkcached).
NAJVEC_PREVERB = 100


def hashi_za_preverbo(hashi: Iterable[object]) -> list[str]:
    """Samo veljavni hashi (40 heks), mala crka, brez ponovitev, najvec NAJVEC_PREVERB."""
    izid: list[str] = []
    for h in hashi:
        v = str(h or "").strip().lower()
        if _HEKS.fullmatch(v) and v not in izid:
            izid.append(v)
        if len(izid) >= NAJVEC_PREVERB:
            break
    return izid


def torbox_naslov_predpomnjenih(hashi: Sequence[str]) -> str:
    return TORBOX_OSNOVA + "/checkcached?hash=" + ",".join(hashi) + "&format=object&list_files=false"


def predpomnjeni(kljuci_odgovora: Iterable[str], vprasani: Sequence[str]) -> set[str]:
    """Predpomnjeni iz odgovora checkcached (kljuci objekta `data`): samo tisti, ki smo jih vprasali."""
    v = set(vprasani)
    return {str(k).lower() for k in kljuci_odgovora if str(k).lower() in v}


def _je_pred(h: object, pred: set[str]) -> bool:
    return h is not None and str(h).lower() in pred


def predpomnjeni_naprej(hashi: Sequence[object], pred: set[str]) -> list[int]:
    """Indeksi: pripravljeni najprej, sicer red ostane (kakovost, kot jo je uredila tok_izbira)."""
    return [i for i, h in enumerate(hashi) if _je_pred(h, pred)] + [i for i, h in enumerate(hashi) if not _je_pred(h, pred)]


def samodejni_torrent(aktivna_storitev: Optional[str], hashi: Sequence[object], pred: set[str]) -> int:
    """Samodejno predvajanje: z aktivno storitvijo gre najboljsi pripravljen torrent pred neposrednimi povezavami.
    Vrne indeks v [hashi] ali -1 (obstojeca izbira)."""
    if aktivna_storitev is None:
        return -1
    return next((i for i, h in enumerate(hashi) if _je_pred(h, pred)), -1)


# ---------------------------------------------------------------------- najhitrejsa storitev (vec kljucev)

@dataclass(frozen=True)
class Meritev:
    """Meritev povezave storitve do tega racunalnika: [ping_ms] do prvega odgovora, [bajtov] v [cas_ms] po njem."""
    ponudnik: str
    ping_ms: int
    bajtov: int
    cas_ms: int

    @property
    def bitov_na_sekundo(self) -> int:
        return 0 if self.cas_ms <= 0 or self.bajtov <= 0 else self.bajtov * 8000 // self.cas_ms


MERITEV_BAJTOV = 3 * 1024 * 1024
MERITEV_S = 2.0
VZPOREDNO_ROK_S = 15.0
PODOBNA_HITROST = 0.85
MERITEV_VELJA_S = 7 * 24 * 3600.0


def najhitrejsa(meritve: Sequence[Meritev]) -> Optional[str]:
    """Najvisja hitrost prenosa; pri razliki pod 15 % odloci manjsi ping. None = nobena meritev ni uspela."""
    ok = [m for m in meritve if m.bitov_na_sekundo > 0]
    if not ok:
        return None
    najvec = max(m.bitov_na_sekundo for m in ok)
    return min((m for m in ok if m.bitov_na_sekundo >= najvec * PODOBNA_HITROST), key=lambda m: m.ping_ms).ponudnik


def opis_meritve(m: Meritev) -> str:
    mb = m.bitov_na_sekundo / 1_000_000
    hitrost = ("%.1f" % mb) if mb < 10 else str(int(mb))
    return "%s Mb/s · %d ms" % (hitrost, m.ping_ms)


def meritev_velja(kdaj: float, zdaj: float) -> bool:
    return 0 <= zdaj - kdaj < MERITEV_VELJA_S
