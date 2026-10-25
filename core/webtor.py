"""Webtor rezerva na namizju (skupna koda Linux in Windows, brez GTK) - kar TorBox nima pripravljenega, zacne teci prek
uporabnikovega osebnega dodatka Stremio Webtor, da uporabnik ne caka na prenos (lastnik 25. 10. 2026).

Ista pravila kot Safeer OS za Android (WebtorPravila.kt, Webtor.kt na veji webtor-rezerva; skupni primeri
tests/skupni-primeri/webtor-rezerva.json): dodatek vrne tok »url« = `https://webtor.io/token/<zeton>/stremio/resolve/<JWT>`
(JWT 72 h), ki s 302 preusmeri na izvirno datoteko (progresivno, Range). Ime toka ima predpono `[⚡TB]` (pri TorBoxu v
Webtor profilu pripravljen - podvaja nas TorBox), `[⚡WT]` (Webtor ga ima pripravljenega), `[WT]` (Webtor ga prenasa
sproti) ali `[P2P]` (brezplacni racun: posnetek z oglasom za paket).

Sonda (popravki neodvisnega pregleda Androida, Grok 25. 10. 2026, U4): preusmeritvam sledimo sami (najvec 5), vsak skok
samo po https, brez uporabnika v naslovu; ime gostitelja razresimo sami in zavrnemo zanko, zasebne (RFC 1918, ULA),
link-local, CGNAT in druge nejavne naslove (vsi naslovi imena morajo biti javni), povezemo pa se na PREVERJENI naslov IP
(brez druge razresitve - DNS rebinding med preverbo in povezavo ne gre). Predvajalnik dobi KONCNI naslov, ki ga je sonda
preverila (ne /resolve/ z zetonom), in mu ne sledi vec preusmeritvam (core/os_predvajalnik: automatic-redirect=False).
Koncni naslov je vezan na IP te naprave (Webtor primerja /24): ne shranjujemo ga in ne posiljamo drugim napravam.
"""
from __future__ import annotations

import base64
import binascii
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
import urllib.parse
from dataclasses import dataclass
from typing import Callable, Optional

ID_MANIFESTA = "org.stremio.webtor.io"
GOSTITELJ = "webtor.io"
#: Oznaka vira toka (ime storitve, ne prevajamo).
IME = "Webtor"
#: Prvi bajt toka pozneje od tega: naslednji vir. Hkrati skupni rok vseh sond Webtor ene izbire.
PRVI_BAJT_MS = 15_000
#: Ena izbira toka poskusi najvec toliko tokov Webtor.
NAJVEC_POSKUSOV = 2
NAJVEC_PREUSMERITEV = 5
UPORABNISKI_AGENT = "SafeerOS/1.0"

# Vrste toka po predponi imena.
TORBOX = "TORBOX"
PREDPOMNJEN = "PREDPOMNJEN"
PRENOS = "PRENOS"
P2P = "P2P"

# Izidi sonde.
#: 2xx, a ni video (naslovnica, glasba, napis): meritev na Androidu 25. 10. 15:25 - Webtor je za 3 od 3 filmov dal
#: datoteko image/jpeg ali MP3 iz istega torrenta. Naslednji vir.
NI_VIDEO = "NI_VIDEO"
PREDVAJAJ = "PREDVAJAJ"
NI_PAKETA = "NI_PAKETA"
NI_TOKA = "NI_TOKA"
OMEJITEV = "OMEJITEV"
PREPOCASI = "PREPOCASI"
NAPAKA = "NAPAKA"


def gostitelj(naslov: str) -> str:
    """Gostitelj naslova (male crke, brez vrat in uporabnika); "" = ni naslov http(s)."""
    n = str(naslov or "").strip()
    i = n.find("://")
    if i <= 0 or n[:i].lower() not in ("http", "https"):
        return ""
    g = re.split(r"[/?#]", n[i + 3:], 1)[0].rpartition("@")[2]
    return g.split(":", 1)[0].lower().rstrip(".")


def je_webtor(id_manifesta: Optional[str]) -> bool:
    """Samo `id` manifesta (dodatek si ga izbere sam) - za odlocitev uporabi je_webtor_dodatek."""
    return str(id_manifesta or "").strip() == ID_MANIFESTA


def je_webtor_dodatek(id_manifesta: Optional[str], osnova: str) -> bool:
    """Dodatek je Webtor samo, ce ima `id` Webtorja IN je osnova (prava ali nadomestek) natanko na https://webtor.io."""
    return je_webtor(id_manifesta) and str(osnova or "").strip().lower().startswith("https://") \
        and gostitelj(osnova) == GOSTITELJ


def je_resolve_naslov(url: str) -> bool:
    """Naslov `https://webtor.io/.../resolve/...` (tok dodatka Webtor, prav ali kot nadomestek)."""
    u = str(url or "").strip()
    return u.lower().startswith("https://") and gostitelj(u) == GOSTITELJ and "/resolve/" in u.split("?", 1)[0]


_RX_PREDPONA = re.compile(r"^\s*\[\s*(⚡️?)?\s*(TB|WT|P2P)\s*]\s*", re.I)


def razcleni(ime: str) -> tuple:
    """Predpona imena toka -> (vrsta, ime brez predpone)."""
    ime = str(ime or "")
    m = _RX_PREDPONA.match(ime)
    if not m:
        return PRENOS, ime.strip()
    oznaka = m.group(2).upper()
    vrsta = TORBOX if oznaka == "TB" else P2P if oznaka == "P2P" else PREDPOMNJEN if m.group(1) else PRENOS
    return vrsta, ime[m.end():].strip()


def skrij(vrsta: str, imamo_torbox: bool) -> bool:
    """`[⚡TB]` podvaja nas TorBox (le, ce ga imamo), `[P2P]` je posnetek z oglasom za paket, ne film."""
    return vrsta == P2P or (vrsta == TORBOX and imamo_torbox)


def takoj(vrsta: str) -> bool:
    """Tok, ki se zacne takoj: `[⚡WT]` in `[⚡TB]`."""
    return vrsta in (PREDPOMNJEN, TORBOX)


_RX_HASH = re.compile(r"^[0-9a-f]{40}$")


def kljuc(hash_: Optional[str], idx: Optional[int]) -> Optional[tuple]:
    """Izdaja: (infoHash 40 hex, datoteka); -1 = datoteka ni znana."""
    h = str(hash_ or "").strip().lower()
    if not _RX_HASH.match(h):
        return None
    return h, (-1 if idx is None or idx < 0 else int(idx))


def iz_jwt(url: str) -> Optional[tuple]:
    """(hash, idx) iz JWT v naslovu `.../resolve/<JWT>` - samo za ujemanje izdaje (podpis preveri Webtor sam)."""
    pot = str(url or "").split("?", 1)[0].split("#", 1)[0]
    if "/resolve/" not in pot:
        return None
    deli = pot.split("/resolve/", 1)[1].split("/", 1)[0].split(".")
    if len(deli) != 3 or not deli[1]:
        return None
    try:
        t = deli[1].rstrip("=")
        telo = base64.urlsafe_b64decode(t + "=" * (-len(t) % 4)).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    h = re.search(r'"hash"\s*:\s*"([0-9a-fA-F]{40})"', telo)
    i = re.search(r'"idx"\s*:\s*"?(-?\d{1,6})', telo)
    return kljuc(h.group(1) if h else None, int(i.group(1)) if i else -1)


def vrstni_red(nasi: list, webtor: list, imamo_torbox: bool, samo_takoj: bool = False) -> list:
    """Vrstni red tokov Webtor (indeksi v `webtor` = [(kljuc, vrsta)]): najprej tisti, ki se ujemajo z NASIMI torrenti
    (v njihovem vrstnem redu - ista izdaja, isti hash IN ista datoteka), nato ostali, `[⚡WT]` pred `[WT]`. Skriti
    izpadejo; `samo_takoj`: samo `[⚡WT]`/`[⚡TB]`."""
    vidni = [i for i, (_k, v) in enumerate(webtor) if not skrij(v, imamo_torbox) and (not samo_takoj or takoj(v))]
    izbrani: list = []
    for k in nasi:
        if k is None:
            continue
        i = next((i for i in vidni if i not in izbrani and webtor[i][0] == k), None)
        if i is not None:
            izbrani.append(i)
    ostali = [i for i in vidni if i not in izbrani]
    return izbrani + [i for i in ostali if takoj(webtor[i][1])] + [i for i in ostali if not takoj(webtor[i][1])]


def odlocitev(koda: int, prvi_bajt_ms: Optional[int], potekel: bool) -> str:
    """402 = ni paketa, 404/410 = Webtor toka nima, 429 = omejitev; vse razen PREDVAJAJ pomeni: naslednji vir."""
    if koda == 402:
        return NI_PAKETA
    if koda in (404, 410):
        return NI_TOKA
    if koda == 429:
        return OMEJITEV
    if potekel:
        return PREPOCASI
    if 200 <= koda <= 299 and prvi_bajt_ms is not None:
        return PREDVAJAJ if prvi_bajt_ms <= PRVI_BAJT_MS else PREPOCASI
    return NAPAKA


def rok_sonde(zacetek_prve: Optional[int], zdaj: int, poskusov: int) -> int:
    """Koliko ms ima naslednja sonda v eni izbiri toka: skupaj najvec PRVI_BAJT_MS in najvec NAJVEC_POSKUSOV sond."""
    if poskusov >= NAJVEC_POSKUSOV:
        return 0
    if zacetek_prve is None:
        return PRVI_BAJT_MS
    return max(0, PRVI_BAJT_MS - (zdaj - zacetek_prve))


# ------------------------------------------------------------------ glavni video

VIDEO_KONCNICE = frozenset({".mkv", ".mp4", ".m4v", ".avi", ".webm", ".mov", ".ts", ".m2ts", ".mts", ".wmv", ".mpg",
                            ".mpeg", ".ogv", ".flv"})
#: Manjsa datoteka ni film ali epizoda (vzorec, napovednik); 30 MB je pod najmanjso epizodo SD.
NAJMANJ_VIDEO = 30 * 1024 * 1024
_RX_VZOREC = re.compile(r"(?<![a-z0-9])(sample|trailer|teaser|preview|extras?|featurette|vzorec)(?![a-z0-9])", re.I)


def je_glavni_video(ime: str, velikost: Optional[int] = None) -> Optional[bool]:
    """Ali je datoteka toka glavni video (ne vzorec, ne slika, ne glasba): po imenu (behaviorHints.filename ali konec
    poti) in velikosti. None = ne vemo (ni imena)."""
    ime = str(ime or "").strip().rsplit("/", 1)[-1]
    if velikost is not None and 0 < int(velikost) < NAJMANJ_VIDEO:
        return False
    if not ime:
        return None
    pika = ime.rfind(".")
    koncnica = ime[pika:].lower() if pika > 0 else ""
    if not koncnica or len(koncnica) > 6:
        return None
    if koncnica not in VIDEO_KONCNICE:
        return False
    return not _RX_VZOREC.search(ime)


#: Vrste vsebine, ki so lahko video posoda (ali neoznacena datoteka).
_VSEBINA_VIDEO = ("video/", "application/octet-stream", "binary/octet-stream", "application/x-matroska", "application/mp4")


def je_video_vsebina(vrsta: str) -> bool:
    """Content-Type toka: video/* ali octet-stream (Webtor in CDN-ji); image/*, audio/*, text/* niso."""
    v = str(vrsta or "").split(";", 1)[0].strip().lower()
    return bool(v) and v.startswith(_VSEBINA_VIDEO)


def posoda(zacetek: bytes) -> str:
    """Video posoda po prvih bajtih: "mkv" (EBML 1A45DFA3, tudi WebM), "mp4" (atom ftyp/moov/mdat na odmiku 4),
    "ts" (sinhronizacija 0x47 na 0 in 188), "avi" (RIFF....AVI ); "" = ni video posode (JPEG, MP3, HTML ...)."""
    b = bytes(zacetek or b"")
    if b[:4] == b"\x1a\x45\xdf\xa3":
        return "mkv"
    if len(b) >= 8 and b[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"free"):
        return "mp4"
    if len(b) >= 189 and b[0] == 0x47 and b[188] == 0x47:
        return "ts"
    if b[:4] == b"RIFF" and b[8:12] == b"AVI ":
        return "avi"
    return ""


#: Toliko bajtov zahteva sonda (Range): dva paketa MPEG-TS (188) za zanesljivo prepoznavo posode.
PRVIH_BAJTOV = 376


# ------------------------------------------------------------------ Scit

#: Stalne izjeme Scita za Webtor - samo pred seznami OGLASOV, nikoli pred seznami grozenj (core/os_scit._kategorija).
#: Pregled Grok U10: ozko, natancni gostitelji (Android ima tu se vse poddomene obeh domen).
_IZJEME_TOCNE = frozenset({"webtor.io", "api.webtor.io"})
_RX_GOSTITELJ_TOKA = re.compile(r"^abra--[a-z0-9-]{1,63}\.api\.cosmic-crab\.buzz$")


def je_stalna_izjema_scita(ime: str) -> bool:
    """Gostitelj API Webtorja ali gostitelj toka `abra--<id>.api.cosmic-crab.buzz` (porocilo webtor/porocilo-rezerva.md)."""
    d = str(ime or "").strip().lower().rstrip(".")
    return d in _IZJEME_TOCNE or bool(_RX_GOSTITELJ_TOKA.match(d))


def scit_dovoljena(ime: str, naucene: dict, zdaj: int) -> bool:
    """Domena je med izjemami: stalna ali naucena NATANKO in se veljavna ob `zdaj` (skupni primeri z Androidom)."""
    d = str(ime or "").strip().lower().strip(".")
    if not d:
        return False
    return je_stalna_izjema_scita(d) or int((naucene or {}).get(d) or 0) > zdaj


# ------------------------------------------------------------------ sonda

def javen_ip(naslov: str) -> bool:
    """Naslov IP je javen: ne zanka, ne zasebno omrezje (RFC 1918, ULA), ne link-local, ne CGNAT, ne vecvrocno."""
    try:
        a = ipaddress.ip_address(str(naslov).split("%", 1)[0])
    except ValueError:
        return False
    a = getattr(a, "ipv4_mapped", None) or a
    if a.version == 6:
        for vgrajen in (getattr(a, "sixtofour", None), (getattr(a, "teredo", None) or (None, None))[1]):
            if vgrajen is not None and not javen_ip(str(vgrajen)):
                return False
    return bool(a.is_global) and not a.is_multicast


class ZasebenNaslov(OSError):
    """Ime se razresi v nejaven naslov - sonda ga zavrne (ne v domace omrezje, ne v zanko)."""


def razresi(gostitelj_: str, vrata: int) -> str:
    """Prvi naslov IP imena; ce je kateri od naslovov nejaven, ZasebenNaslov (napadalec bi lahko dal javnega in
    zasebnega)."""
    naslovi = [i[4][0] for i in socket.getaddrinfo(gostitelj_, vrata, type=socket.SOCK_STREAM)]
    if not naslovi:
        raise OSError("ni naslova")
    if not all(javen_ip(n) for n in naslovi):
        raise ZasebenNaslov("nejaven naslov")
    return naslovi[0]


class _PovezavaNaIp(http.client.HTTPSConnection):
    """HTTPS na ze preverjen naslov IP; SNI in preverba potrdila za ime gostitelja."""

    def __init__(self, gostitelj_: str, ip: str, vrata: int, rok: float) -> None:
        super().__init__(gostitelj_, vrata, timeout=rok, context=ssl.create_default_context())
        self._ip = ip

    def connect(self) -> None:
        surova = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(surova, server_hostname=self.host)


def zahteva(naslov: str, gostitelj_: str, ip: str, vrata: int, rok: float) -> tuple:
    """GET prvih PRVIH_BAJTOV (Range) brez samodejnih preusmeritev -> (koda, Location ali None, prvi bajti,
    Content-Type)."""
    d = urllib.parse.urlsplit(naslov)
    pot = (d.path or "/") + ("?" + d.query if d.query else "")
    c = _PovezavaNaIp(gostitelj_, ip, vrata, rok)
    try:
        c.request("GET", pot, headers={"Range": "bytes=0-%d" % (PRVIH_BAJTOV - 1), "Accept-Encoding": "identity",
                                       "Accept": "*/*", "User-Agent": UPORABNISKI_AGENT})
        r = c.getresponse()
        lokacija = r.getheader("Location")
        bajti = r.read(PRVIH_BAJTOV) if 200 <= r.status <= 299 else b""
        return int(r.status), lokacija, bajti, str(r.getheader("Content-Type") or "")
    finally:
        c.close()


@dataclass(frozen=True)
class Sonda:
    """Izid sonde: koda HTTP (0 = ni odgovora), cas do prvega bajta (None = ga ni bilo), iztek roka, gostitelj zadnjega
    skoka, KONCNI preverjeni naslov (samo ob 2xx s prvim bajtom) in razlog zavrnitve (brez naslova, za dnevnik)."""
    koda: int = 0
    prvi_bajt_ms: Optional[int] = None
    potekel: bool = False
    gostitelj: str = ""
    koncni: Optional[str] = None
    razlog: str = ""
    #: Video posoda iz prvih bajtov ("mkv", "mp4", "ts", "avi"; "" = ni video ali ni odgovora).
    posoda: str = ""

    @property
    def izid(self) -> str:
        izid = odlocitev(self.koda, self.prvi_bajt_ms, self.potekel)
        if izid == PREDVAJAJ and (not self.posoda or not self.koncni):
            return NI_VIDEO
        return izid


def sonda(url: str, rok_ms: int = PRVI_BAJT_MS, *, razresi_fn: Callable[[str, int], str] = razresi,
          zahteva_fn: Callable[..., tuple] = zahteva, ura: Callable[[], float] = time.monotonic) -> Sonda:
    """Prvi bajt toka `url` (pravi naslov, ne nadomestek) v najvec `rok_ms` skupaj. Blokira - z delovne niti."""
    zacetek = ura()
    naslov = str(url or "")
    g = gostitelj(naslov)
    for skok in range(NAJVEC_PREUSMERITEV + 1):
        ostane = rok_ms / 1000.0 - (ura() - zacetek)
        if ostane <= 0:
            return Sonda(potekel=True, gostitelj=g, razlog="rok")
        try:
            d = urllib.parse.urlsplit(naslov)
            vrata = d.port or 443
        except ValueError:
            return Sonda(gostitelj=g, razlog="naslov")
        g = (d.hostname or "").lower().rstrip(".")
        if d.scheme != "https" or not g or d.username is not None or d.password is not None or "\\" in d.netloc:
            return Sonda(gostitelj=g, razlog="ni_https")
        try:
            ip = razresi_fn(g, vrata)
        except ZasebenNaslov:
            return Sonda(gostitelj=g, razlog="zasebni_naslov")
        except OSError:
            return Sonda(gostitelj=g, razlog="dns")
        if not javen_ip(ip):
            return Sonda(gostitelj=g, razlog="zasebni_naslov")
        ostane = rok_ms / 1000.0 - (ura() - zacetek)
        if ostane <= 0:
            return Sonda(potekel=True, gostitelj=g, razlog="rok")
        try:
            koda, lokacija, bajti, vsebina = zahteva_fn(naslov, g, ip, vrata, ostane)
        except (socket.timeout, TimeoutError):
            return Sonda(potekel=True, gostitelj=g, razlog="rok")
        except (OSError, http.client.HTTPException, ValueError):
            if rok_ms / 1000.0 - (ura() - zacetek) <= 0:
                return Sonda(potekel=True, gostitelj=g, razlog="rok")
            return Sonda(gostitelj=g, razlog="omrezje")
        if 300 <= koda <= 399:
            if not lokacija:
                return Sonda(koda=koda, gostitelj=g, razlog="preusmeritev")
            if skok >= NAJVEC_PREUSMERITEV:
                return Sonda(koda=koda, gostitelj=g, razlog="preusmeritve")
            try:
                naslov = urllib.parse.urljoin(naslov, str(lokacija).strip())
            except ValueError:
                return Sonda(koda=koda, gostitelj=g, razlog="naslov")
            continue
        if not 200 <= koda <= 299 or not bajti:
            return Sonda(koda=koda, gostitelj=g)
        ms = int((ura() - zacetek) * 1000)
        # Ni dovolj kode 206: Content-Type mora biti video ali octet-stream IN prvi bajti video posoda (Webtor je za
        # napacno datoteko torrenta vrnil naslovnico JPEG ali MP3 - Android, 25. 10. 2026).
        if not je_video_vsebina(vsebina):
            return Sonda(koda=koda, prvi_bajt_ms=ms, gostitelj=g, razlog="vsebina")
        vrsta = posoda(bajti)
        if not vrsta:
            return Sonda(koda=koda, prvi_bajt_ms=ms, gostitelj=g, razlog="posoda")
        if je_glavni_video(urllib.parse.unquote(urllib.parse.urlsplit(naslov).path)) is False:
            return Sonda(koda=koda, prvi_bajt_ms=ms, gostitelj=g, razlog="datoteka", posoda=vrsta)
        return Sonda(koda=koda, prvi_bajt_ms=ms, gostitelj=g, koncni=naslov, posoda=vrsta)
    return Sonda(gostitelj=g, razlog="preusmeritve")


def oznaka_toka(tok: dict) -> tuple:
    """(vrsta, ime) toka dodatka Webtor iz imena, ki ga je dal dodatek (polje `vir` je prva vrstica imena)."""
    return razcleni(str(tok.get("vir") or ""))


def opis_za_dnevnik(s: Sonda) -> str:
    """Brez naslova in zetona: samo izid, koda, gostitelj in cas."""
    return json.dumps({"izid": s.izid, "koda": s.koda, "gostitelj": s.gostitelj, "ms": s.prvi_bajt_ms,
                       "razlog": s.razlog, "posoda": s.posoda}, ensure_ascii=False)
