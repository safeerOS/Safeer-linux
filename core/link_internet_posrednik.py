"""Safeer Internet Gateway - krajevni posrednik, izbira poti in nastavitve na racunalniku.

Programi govorijo s posrednikom na 127.0.0.1 (SOCKS5, SOCKS4a, HTTP CONNECT, navaden HTTP). Vsako
povezavo posrednik bodisi poveze neposredno (domaci internet dela) bodisi poslje skozi telefon v
Safeer Linku (core/link_internet.py). Ime gostitelja razresi tisti, ki povezavo odpre: ob izpadu
domacega interneta torej telefon po mobilnem omrezju - krajevni DNS takrat tako ali tako ne dela.

Nacini:
    izklopljeno   posrednika ni
    izpad         domaci internet dela -> neposredno; ne dela -> skozi telefon (Sonda)
    vedno         vse skozi telefon

Programi posrednika ne najdejo sami. Zato lahko Safeer za cas, ko gre promet skozi telefon, nastavi
sistemski posrednik namizja (core/sistemski_posrednik.py) in ga potem vrne, kot je bil. Za ukazno
vrstico `safeerctl internet env` izpise spremenljivke okolja.

Posrednik poslusa samo na 127.0.0.1 in sprejme samo programe istega uporabnika (uid iz /proc/net/tcp),
da drug uporabnik racunalnika ne porablja mobilnih podatkov telefona.
"""

from __future__ import annotations

import errno
import ipaddress
import json
import os
import select
import socket
import ssl
import struct
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

from core import link_internet

PRIVZETA_VRATA = 47890
POSKUSOV_VRAT = 10
NACINI = ("izklopljeno", "izpad", "vedno")
ZMOZNOST = "internet.gateway"
NAJVEC_GLAVE = 64 * 1024
ROK_ROKOVANJA_S = 15.0
ROK_NEPOSREDNO_S = 10.0
#: Cilji sonde: trije razlicni operaterji, samo rokovanje TCP (brez podatkov in brez DNS).
CILJI_SONDE = (("1.1.1.1", 443), ("9.9.9.9", 443), ("8.8.8.8", 443))
ROK_SONDE_S = 3.0
SONDA_DELA_S = 10.0
SONDA_NE_DELA_S = 5.0
#: Stran, ki pove javni naslov zahteve (Cloudflare, ista domena kot Safeer; brez tretjih storitev).
PREIZKUS_GOSTITELJ = "safeer.si"
PREIZKUS_POT = "/cdn-cgi/trace"
SHRANI_NA_S = 20.0


class NapakaZahteve(Exception):
    """Program je poslal nekaj, cesar posrednik ne razume ali ne dovoli."""


# ---------------------------------------------------------------------- zahteva programa

def _preberi_tocno(c: socket.socket, n: int) -> bytes:
    deli = b""
    while len(deli) < n:
        kos = c.recv(n - len(deli))
        if not kos:
            raise NapakaZahteve("povezava se je koncala sredi zahteve")
        deli += kos
    return deli


def _preberi_do_nicle(c: socket.socket, najvec: int = 512) -> bytes:
    deli = b""
    while True:
        b = _preberi_tocno(c, 1)
        if b == b"\x00":
            return deli
        deli += b
        if len(deli) > najvec:
            raise NapakaZahteve("predolgo polje")


def _vrata_v_mejah(port: int) -> int:
    if not 1 <= port <= 65535:
        raise NapakaZahteve("neveljavna vrata")
    return port


def _gostitelj(besedilo: str) -> str:
    h = besedilo.strip().strip("[]")
    if not h or len(h) > 253 or any(ord(z) <= 32 or z in "/\\@#?" for z in h):
        raise NapakaZahteve("neveljaven gostitelj")
    return h


class Zahteva:
    """Kam hoce program in kako mu odgovorimo v njegovem protokolu."""

    def __init__(self, host: str, port: int, uspeh: bytes, napaka: Callable[[str], bytes],
                 predpodatki: bytes = b"", protokol: str = "") -> None:
        self.host = host
        self.port = port
        self._uspeh = uspeh
        self._napaka = napaka
        self.predpodatki = predpodatki
        self.protokol = protokol

    def uspeh(self, c: socket.socket) -> None:
        if self._uspeh:
            c.sendall(self._uspeh)

    def napaka(self, c: socket.socket, razlog: str) -> None:
        try:
            c.sendall(self._napaka(razlog))
        except OSError:
            pass


_SOCKS5_KODE = {"dns_failed": 4, "connect_failed": 5, "timeout": 6, "no_path": 3, "no_mobile": 3, "link": 3,
                "old_provider": 3, "busy": 1, "busy_local": 1}


def _socks5_napaka(razlog: str) -> bytes:
    return bytes([5, _SOCKS5_KODE.get(razlog, 2), 0, 1, 0, 0, 0, 0, 0, 0])


def _socks5(c: socket.socket) -> Zahteva:
    _ver, n = _preberi_tocno(c, 2)
    metode = _preberi_tocno(c, n)
    if 0 not in metode:
        c.sendall(b"\x05\xff")
        raise NapakaZahteve("socks5: program zahteva prijavo")
    c.sendall(b"\x05\x00")
    ver, ukaz, _rez, vrsta = _preberi_tocno(c, 4)
    if ver != 5:
        raise NapakaZahteve("socks5: napacna razlicica")
    if vrsta == 1:
        host = socket.inet_ntoa(_preberi_tocno(c, 4))
    elif vrsta == 3:
        host = _gostitelj(_preberi_tocno(c, _preberi_tocno(c, 1)[0]).decode("latin-1"))
    elif vrsta == 4:
        host = socket.inet_ntop(socket.AF_INET6, _preberi_tocno(c, 16))
    else:
        c.sendall(bytes([5, 8, 0, 1, 0, 0, 0, 0, 0, 0]))
        raise NapakaZahteve("socks5: neznana vrsta naslova")
    port = struct.unpack("!H", _preberi_tocno(c, 2))[0]
    if ukaz != 1:
        c.sendall(bytes([5, 7, 0, 1, 0, 0, 0, 0, 0, 0]))
        raise NapakaZahteve("socks5: samo CONNECT")
    return Zahteva(host, _vrata_v_mejah(port), bytes([5, 0, 0, 1, 0, 0, 0, 0, 0, 0]), _socks5_napaka, protokol="socks5")


def _socks4(c: socket.socket) -> Zahteva:
    _ver, ukaz = _preberi_tocno(c, 2)
    port = struct.unpack("!H", _preberi_tocno(c, 2))[0]
    ip = _preberi_tocno(c, 4)
    _preberi_do_nicle(c)                                     # uporabnisko ime, ne rabimo ga
    if ip[:3] == b"\x00\x00\x00" and ip[3] != 0:
        host = _gostitelj(_preberi_do_nicle(c).decode("latin-1"))   # SOCKS4a: ime pride za imenom uporabnika
    else:
        host = socket.inet_ntoa(ip)
    zavrnitev = b"\x00\x5b\x00\x00\x00\x00\x00\x00"
    if ukaz != 1:
        c.sendall(zavrnitev)
        raise NapakaZahteve("socks4: samo CONNECT")
    return Zahteva(host, _vrata_v_mejah(port), b"\x00\x5a\x00\x00\x00\x00\x00\x00", lambda _r: zavrnitev, protokol="socks4")


_HTTP_KODE = {"timeout": "504 Gateway Timeout", "dns_failed": "502 Bad Gateway", "connect_failed": "502 Bad Gateway",
              "no_path": "503 Service Unavailable", "no_mobile": "503 Service Unavailable", "link": "503 Service Unavailable",
              "old_provider": "503 Service Unavailable", "busy": "503 Service Unavailable", "busy_local": "503 Service Unavailable"}


def _http_napaka(razlog: str) -> bytes:
    telo = ("Safeer Internet Gateway: %s\n" % razlog).encode("ascii", "replace")
    return ("HTTP/1.1 %s\r\nX-Safeer-Reason: %s\r\nContent-Type: text/plain\r\nContent-Length: %d\r\n"
            "Connection: close\r\n\r\n" % (_HTTP_KODE.get(razlog, "403 Forbidden"), razlog, len(telo))).encode("ascii") + telo


def _razdeli_cilj(cilj: str, privzeta_vrata: int) -> Tuple[str, int]:
    """`gostitelj[:vrata]` ali `[v6]:vrata`."""
    cilj = cilj.strip()
    if cilj.startswith("["):
        konec = cilj.find("]")
        if konec < 0:
            raise NapakaZahteve("neveljaven naslov")
        host = cilj[1:konec]
        ostanek = cilj[konec + 1:]
        port = int(ostanek[1:]) if ostanek.startswith(":") and ostanek[1:].isdigit() else privzeta_vrata
    elif cilj.count(":") == 1:
        host, _, p = cilj.partition(":")
        if not p.isdigit():
            raise NapakaZahteve("neveljavna vrata")
        port = int(p)
    else:
        host, port = cilj, privzeta_vrata
    return _gostitelj(host), _vrata_v_mejah(port)


def _http(c: socket.socket) -> Zahteva:
    zbrano = b""
    while b"\r\n\r\n" not in zbrano:
        kos = c.recv(8192)
        if not kos:
            raise NapakaZahteve("http: povezava se je koncala sredi glave")
        zbrano += kos
        if len(zbrano) > NAJVEC_GLAVE:
            raise NapakaZahteve("http: prevelika glava")
    glava, _, ostanek = zbrano.partition(b"\r\n\r\n")
    vrstice = glava.decode("latin-1").split("\r\n")
    deli = vrstice[0].split(" ")
    if len(deli) != 3 or not deli[2].startswith("HTTP/"):
        raise NapakaZahteve("http: neveljavna prva vrstica")
    metoda, cilj, razlicica = deli
    if metoda.upper() == "CONNECT":
        host, port = _razdeli_cilj(cilj, 443)
        return Zahteva(host, port, b"HTTP/1.1 200 Connection established\r\n\r\n", _http_napaka, ostanek, "connect")
    if not cilj.lower().startswith("http://"):
        # Zahteva v obliki izvora (»GET / HTTP/1.1«): to ni posredniska zahteva, ampak nekdo, ki misli, da smo
        # spletni streznik (npr. spletna stran, ki klice 127.0.0.1). Ne posredujemo nikamor.
        c.sendall(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        raise NapakaZahteve("http: ni posredniska zahteva")
    brez_sheme = cilj[7:]
    naslov, posevnica, pot = brez_sheme.partition("/")
    host, port = _razdeli_cilj(naslov.rsplit("@", 1)[-1], 80)
    nove = ["%s /%s %s" % (metoda, pot, razlicica)]
    for v in vrstice[1:]:
        ime = v.split(":", 1)[0].strip().lower()
        if ime in ("proxy-connection", "proxy-authorization", "connection"):
            continue
        nove.append(v)
    # Ena zahteva na povezavo: po odgovoru streznik zapre, program za drug cilj odpre novo povezavo.
    nove.append("Connection: close")
    return Zahteva(host, port, b"", _http_napaka, ("\r\n".join(nove) + "\r\n\r\n").encode("latin-1") + ostanek, "http")


def preberi_zahtevo(c: socket.socket) -> Zahteva:
    """Prebere zahtevo programa; protokol prepozna po prvem bajtu."""
    prvi = c.recv(1, socket.MSG_PEEK)
    if not prvi:
        raise NapakaZahteve("prazna povezava")
    if prvi == b"\x05":
        return _socks5(c)
    if prvi == b"\x04":
        return _socks4(c)
    return _http(c)


def uid_odjemalca(naslov: Tuple[str, int], nasa_vrata: int, pot: str = "/proc/net/tcp") -> Optional[int]:
    """Uporabnik (uid), ki mu pripada krajevna povezava z izvornimi vrati `naslov[1]`. None, ce se ne da ugotoviti."""
    try:
        with open(pot, "r", encoding="ascii", errors="replace") as f:
            vrstice = f.read().splitlines()[1:]
    except OSError:
        return None
    for v in vrstice:
        polja = v.split()
        if len(polja) < 8:
            continue
        try:
            krajevna = int(polja[1].rsplit(":", 1)[1], 16)
            oddaljena = int(polja[2].rsplit(":", 1)[1], 16)
            if krajevna == naslov[1] and oddaljena == nasa_vrata:
                return int(polja[7])
        except (ValueError, IndexError):
            continue
    return None


# ---------------------------------------------------------------------- sonda domacega interneta

def _tcp_dosegljiv(cilj: Tuple[str, int], rok: float) -> bool:
    try:
        with socket.create_connection(cilj, timeout=rok):
            return True
    except OSError:
        return False


class Sonda:
    """Ali domaci internet dela. Dva zaporedna enaka izida spremenita stanje (en izgubljen paket ni izpad)."""

    def __init__(self, ob_spremembi: Callable[[bool], None], cilji=CILJI_SONDE,
                 dosegljiv: Callable[[Tuple[str, int], float], bool] = _tcp_dosegljiv) -> None:
        self.ob_spremembi = ob_spremembi
        self.cilji = tuple(cilji)
        self._dosegljiv = dosegljiv
        self.dela = True
        self.preverjeno = 0.0
        self._drugacnih = 0
        self._tece = False
        self._budilka = threading.Event()
        self._zaklep = threading.Lock()

    def krog(self) -> bool:
        """En krog: vsi cilji hkrati, dovolj je en uspeh."""
        uspeh = threading.Event()
        koncani = threading.Semaphore(0)

        def poskus(cilj) -> None:
            try:
                if self._dosegljiv(cilj, ROK_SONDE_S):
                    uspeh.set()
            finally:
                koncani.release()
        for c in self.cilji:
            threading.Thread(target=poskus, args=(c,), name="safeer-internet-sonda", daemon=True).start()
        rok = time.monotonic() + ROK_SONDE_S + 1.0
        for _ in self.cilji:
            if uspeh.is_set():
                break
            koncani.acquire(timeout=max(0.05, rok - time.monotonic()))
        return uspeh.is_set()

    def preveri(self, takoj: bool = False) -> bool:
        """Krog in presoja. `takoj=True`: ze en neuspel krog pomeni izpad (klicatelj je sam videl napako)."""
        ok = self.krog()
        spremenjeno = False
        with self._zaklep:
            self.preverjeno = time.time()
            if ok == self.dela:
                self._drugacnih = 0
            else:
                self._drugacnih += 1
                if self._drugacnih >= 2 or (takoj and not ok):
                    self.dela = ok
                    self._drugacnih = 0
                    spremenjeno = True
        if spremenjeno:
            try:
                self.ob_spremembi(ok)
            except Exception:  # noqa: BLE001
                pass
        return self.dela

    def zazeni(self) -> None:
        with self._zaklep:
            if self._tece:
                return
            self._tece = True
        threading.Thread(target=self._zanka, name="safeer-internet-sonda", daemon=True).start()

    def ustavi(self) -> None:
        with self._zaklep:
            self._tece = False
            self.dela = True
            self._drugacnih = 0
        self._budilka.set()

    def pospesi(self) -> None:
        self._budilka.set()

    def _zanka(self) -> None:
        while self._tece:
            self.preveri()
            self._budilka.wait(SONDA_DELA_S if self.dela and not self._drugacnih else SONDA_NE_DELA_S)
            self._budilka.clear()


# ---------------------------------------------------------------------- posrednik

class Posrednik:
    """Poslusalec na 127.0.0.1. Vsaka povezava dobi svojo nit; kam gre, odloci `usmeri`."""

    def __init__(self, usmeri: Callable[[socket.socket, Zahteva], None]) -> None:
        self._usmeri = usmeri
        self._poslusalec: Optional[socket.socket] = None
        self.vrata = 0
        self._tece = False

    @property
    def tece(self) -> bool:
        return self._tece

    def zazeni(self, vrata: int = PRIVZETA_VRATA) -> int:
        """Zacne poslusati. Vrne vrata (0, ce ni slo). Zasedena vrata -> naslednja."""
        if self._tece:
            return self.vrata
        for poskus in list(range(vrata, vrata + POSKUSOV_VRAT)) + [0]:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", poskus))
                s.listen(64)
            except OSError:
                s.close()
                continue
            self._poslusalec = s
            self.vrata = s.getsockname()[1]
            self._tece = True
            threading.Thread(target=self._sprejemaj, args=(s,), name="safeer-internet-posrednik", daemon=True).start()
            return self.vrata
        return 0

    def ustavi(self) -> None:
        self._tece = False
        s, self._poslusalec = self._poslusalec, None
        if s is not None:
            # Samo close() ne zbudi niti, ki caka v accept(): vticnica bi poslusala naprej, dokler kdo ne pride.
            for korak in (lambda: s.shutdown(socket.SHUT_RDWR), s.close):
                try:
                    korak()
                except OSError:
                    pass

    def _sprejemaj(self, s: socket.socket) -> None:
        s.settimeout(1.0)
        while self._tece and self._poslusalec is s:
            try:
                c, naslov = s.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._obravnavaj, args=(c, naslov), name="safeer-internet-povezava", daemon=True).start()
        try:
            s.close()
        except OSError:
            pass

    def _obravnavaj(self, c: socket.socket, naslov) -> None:
        try:
            uid = uid_odjemalca(naslov, self.vrata)
            if uid is not None and uid != os.getuid():
                c.close()
                return
            c.settimeout(ROK_ROKOVANJA_S)
            c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            zahteva = preberi_zahtevo(c)
        except (NapakaZahteve, OSError, ValueError, UnicodeError):
            try:
                c.close()
            except OSError:
                pass
            return
        try:
            self._usmeri(c, zahteva)
        except Exception:  # noqa: BLE001
            pass
        finally:
            try:
                c.close()
            except OSError:
                pass


def razlog_povezave(e: BaseException) -> str:
    if isinstance(e, socket.gaierror):
        return "dns_failed"
    if isinstance(e, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(e, OSError) and e.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN):
        return "no_path"
    return "connect_failed"


def prenasaj_neposredno(c: socket.socket, s: socket.socket, stej: Optional[Callable[[int, int], None]] = None) -> None:
    """Dve vticnici, bajti v obe smeri, dokler se obe ne koncata. Pol-zaprtje se prenese."""
    for v in (c, s):
        v.settimeout(None)
    odprti = {c: s, s: c}
    while odprti:
        try:
            berljivi, _, _ = select.select(list(odprti), [], [], link_internet.NEDEJAVNOST_S)
        except (OSError, ValueError):
            break
        if not berljivi:
            break
        for v in berljivi:
            drugi = odprti.get(v)
            if drugi is None:
                continue
            try:
                kos = v.recv(65536)
            except OSError:
                kos = b""
                odprti.clear()
                break
            if not kos:
                del odprti[v]
                try:
                    drugi.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
                continue
            try:
                drugi.sendall(kos)
            except OSError:
                odprti.clear()
                break
            if stej is not None:
                stej(len(kos) if v is c else 0, len(kos) if v is s else 0)
    for v in (s,):
        try:
            v.close()
        except OSError:
            pass


# ---------------------------------------------------------------------- upravitelj

def je_krajevni_cilj(host: str) -> bool:
    """Cilj v domacem omrezju: zasebni ali krajevni naslov, localhost, ime.local, ime brez pike (»tiskalnik«).

    Telefon do takega cilja ne more (in zasebne cilje zavraca), racunalnik pa. Tak promet gre zato vedno
    neposredno - sicer bi sistemski posrednik ob izpadu interneta odrezal se tiskalnik in usmerjevalnik."""
    h = (host or "").strip().strip("[]").lower().rstrip(".")
    if not h:
        return False
    if h == "localhost" or h.endswith(".localhost") or h.endswith(".local"):
        return True
    try:
        naslov = ipaddress.ip_address(h.split("%", 1)[0])
    except ValueError:
        return "." not in h and ":" not in h
    return naslov.is_private or naslov.is_loopback or naslov.is_link_local


def _danes() -> Tuple[str, str]:
    t = time.localtime()
    return time.strftime("%Y-%m-%d", t), time.strftime("%Y-%m", t)


class InternetUpravitelj:
    """Nastavitve, posrednik, sonda in stanje »interneta prek telefona« na tem racunalniku."""

    def __init__(self, internet: link_internet.InternetPrekLinka, naprave: Callable[[], List[dict]],
                 pot_nastavitev: str, sistemski=None, obvesti: Optional[Callable[[str, dict], None]] = None,
                 sonda: Optional[Sonda] = None, krajevni_cilj: Optional[Callable[[str], bool]] = None) -> None:
        self.internet = internet
        #: Kateri cilji gredo vedno neposredno (domace omrezje). V preizkusih zamenljivo: ti ciljajo 127.0.0.1.
        self._krajevni_cilj = krajevni_cilj or je_krajevni_cilj
        self._naprave = naprave
        self.pot_nastavitev = pot_nastavitev
        self.sistemski = sistemski
        self._obvesti = obvesti
        self.sonda = sonda or Sonda(self._na_spremembo_fiksne)
        self.sonda.ob_spremembi = self._na_spremembo_fiksne
        self.posrednik = Posrednik(self._usmeri)
        self._zaklep = threading.RLock()
        self.nacin = "izklopljeno"
        self.naprava = ""
        self.pot = link_internet.POT_MOBILNA
        #: Dokler gre promet skozi telefon, je sistemski posrednik nas - privzeto, da programi delajo brez nastavljanja.
        self.sistemski_vklopljen = True
        self.vrata = PRIVZETA_VRATA
        #: Samo za diagnostiko (rocno v datoteki nastavitev): uporabi tudi telefon s protokolom 1, brez nadzora pretoka.
        self.stari_ponudniki = False
        self.prek_telefona = False
        self.zadnja_napaka = ""
        self.tokov_neposredno = 0
        self._poraba = {"dan": "", "dan_bajti": 0, "mesec": "", "mesec_bajti": 0}
        self._seja = 0
        #: Ali naj bo sistemski posrednik zdaj nas (zadnja oddana zahteva; izvede jo nit v ozadju).
        self._sistemski_zeljen: Optional[bool] = None
        self._sistemski_zaklep = threading.Lock()
        #: telefon -> do kdaj (monotonic) vemo, da na vprasanje ne odgovarja (starejsi Safeer OS).
        self._brez_odgovora: Dict[str, float] = {}
        self._shranjeno = 0.0
        self._umazano = False
        self._nalozi()
        internet.ob_prometu = self._na_promet
        internet.ob_stanju = self._na_stanje_ponudnika

    # ------------------------------------------------------------------ nastavitve

    def _nalozi(self) -> None:
        try:
            with open(self.pot_nastavitev, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            return
        if not isinstance(d, dict):
            return
        if d.get("nacin") in NACINI:
            self.nacin = d["nacin"]
        self.naprava = str(d.get("naprava") or "")
        if d.get("pot") in (link_internet.POT_MOBILNA, link_internet.POT_KATERAKOLI, link_internet.POT_WIFI):
            self.pot = d["pot"]
        self.sistemski_vklopljen = bool(d.get("sistemski", True))
        self.stari_ponudniki = d.get("stari_ponudniki") is True
        try:
            vrata = int(d.get("vrata") or PRIVZETA_VRATA)
            if 1024 <= vrata <= 65535:
                self.vrata = vrata
        except (TypeError, ValueError):
            pass
        p = d.get("poraba")
        if isinstance(p, dict):
            for k in ("dan", "mesec"):
                self._poraba[k] = str(p.get(k) or "")
            for k in ("dan_bajti", "mesec_bajti"):
                try:
                    self._poraba[k] = max(0, int(p.get(k) or 0))
                except (TypeError, ValueError):
                    pass

    def _shrani(self) -> None:
        with self._zaklep:
            d = {"nacin": self.nacin, "naprava": self.naprava, "pot": self.pot, "sistemski": self.sistemski_vklopljen,
                 "vrata": self.vrata, "poraba": dict(self._poraba)}
            if self.stari_ponudniki:
                d["stari_ponudniki"] = True
            self._umazano = False
            self._shranjeno = time.monotonic()
        try:
            os.makedirs(os.path.dirname(self.pot_nastavitev), exist_ok=True)
            zacasna = self.pot_nastavitev + ".tmp"
            with open(zacasna, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            os.replace(zacasna, self.pot_nastavitev)
        except OSError:
            pass

    def nastavi(self, nacin: Optional[str] = None, naprava: Optional[str] = None, sistemski: Optional[bool] = None,
                pot: Optional[str] = None) -> dict:
        with self._zaklep:
            if nacin is not None:
                if nacin not in NACINI:
                    return {"ok": False, "koda": "napacna_zahteva"}
                self.nacin = nacin
            if naprava is not None:
                self.naprava = str(naprava)
            if pot is not None:
                if pot not in (link_internet.POT_MOBILNA, link_internet.POT_KATERAKOLI, link_internet.POT_WIFI):
                    return {"ok": False, "koda": "napacna_zahteva"}
                self.pot = pot
            if sistemski is not None:
                self.sistemski_vklopljen = bool(sistemski)
        self._shrani()
        self.uveljavi()
        return self.stanje()

    # ------------------------------------------------------------------ zagon

    def uveljavi(self) -> None:
        """Posrednik, sonda in sistemski posrednik po trenutnih nastavitvah."""
        with self._zaklep:
            nacin = self.nacin
        if nacin == "izklopljeno":
            self.sonda.ustavi()
            self.posrednik.ustavi()
            self.internet.zapri_vse("disabled")
        else:
            vrata = self.posrednik.zazeni(self.vrata)
            if vrata and vrata != self.vrata:
                with self._zaklep:
                    self.vrata = vrata
                self._shrani()
            if not vrata:
                self.zadnja_napaka = "vrata"
            if nacin == "izpad":
                self.sonda.zazeni()
            else:
                self.sonda.ustavi()
        self.osvezi()

    def zazeni(self) -> None:
        if self.sistemski is not None:
            try:
                self.sistemski.ob_zagonu()
            except Exception:  # noqa: BLE001
                pass
        self.uveljavi()

    def ustavi(self) -> None:
        self.sonda.ustavi()
        self.posrednik.ustavi()
        self.internet.zapri_vse("shutdown")
        self._nastavi_prek_telefona(False, tiho=True)
        self._shrani()

    # ------------------------------------------------------------------ telefon in pot

    def telefoni(self) -> List[dict]:
        """Naprave v Linku, ki delijo internet."""
        izid = []
        for n in self._naprave() or []:
            if ZMOZNOST in (n.get("zmoznosti") or []):
                izid.append({"id": str(n.get("id") or ""), "ime": str(n.get("ime") or "")})
        return izid

    def telefon(self) -> Optional[str]:
        """Izbrani telefon, ce je v Linku; sicer prvi, ki deli internet."""
        vsi = self.telefoni()
        with self._zaklep:
            izbran = self.naprava
        for t in vsi:
            if t["id"] == izbran:
                return izbran
        return vsi[0]["id"] if vsi and not izbran else None

    def izberi_pot(self) -> str:
        with self._zaklep:
            nacin = self.nacin
        if nacin == "vedno":
            return "telefon"
        if nacin == "izpad" and not self.sonda.dela:
            return "telefon"
        return "neposredno"

    def _na_spremembo_fiksne(self, _dela: bool) -> None:
        self.osvezi()

    def _na_stanje_ponudnika(self, _naprava: str, _stanje: dict) -> None:
        self.osvezi()

    def osvezi(self) -> None:
        """Preracuna, ali gre promet zdaj skozi telefon (in s tem sistemski posrednik)."""
        with self._zaklep:
            nacin = self.nacin
        telefon = self.telefon()
        zeli = telefon is not None and (nacin == "vedno" or (nacin == "izpad" and not self.sonda.dela))
        self._nastavi_prek_telefona(zeli)

    def _nastavi_prek_telefona(self, zeli: bool, tiho: bool = False) -> None:
        with self._zaklep:
            if zeli == self.prek_telefona:
                spremenjeno = False
            else:
                self.prek_telefona = zeli
                spremenjeno = True
            sistemski = bool(zeli and self.sistemski_vklopljen and self.posrednik.tece)
            vrata = self.posrednik.vrata or self.vrata
            oddaj = self.sistemski is not None and sistemski != self._sistemski_zeljen
            self._sistemski_zeljen = sistemski
        if oddaj:
            # gsettings je pocasen (vec klicev): ne na bralni niti Linka. `tiho` = ob ustavitvi, takrat pocakamo.
            nit = threading.Thread(target=self._uveljavi_sistemski, args=(vrata,), name="safeer-internet-sistemski",
                                   daemon=True)
            nit.start()
            if tiho:
                nit.join(20.0)
        if spremenjeno and not tiho and self._obvesti is not None and self.nacin == "izpad":
            try:
                self._obvesti("prek_telefona" if zeli else "nazaj_doma", {"telefon": self.ime_telefona()})
            except Exception:  # noqa: BLE001
                pass

    def _uveljavi_sistemski(self, vrata: int) -> None:
        """Sistemski posrednik po zadnji zahtevi (zahteve si sledijo, zadnja velja)."""
        with self._sistemski_zaklep:
            with self._zaklep:
                zeli = bool(self._sistemski_zeljen)
            try:
                if zeli:
                    if not self.sistemski.vklopi(vrata):
                        self.zadnja_napaka = "sistemski"
                else:
                    self.sistemski.izklopi()
            except Exception:  # noqa: BLE001
                pass

    def ime_telefona(self) -> str:
        t = self.telefon()
        for n in self.telefoni():
            if n["id"] == t:
                return n["ime"]
        return ""

    # ------------------------------------------------------------------ promet

    def _na_promet(self, _naprava: str, _vrsta: str, gor: int, dol: int) -> None:
        n = gor + dol
        if not n:
            return
        dan, mesec = _danes()
        shrani = False
        with self._zaklep:
            if self._poraba["dan"] != dan:
                self._poraba["dan"], self._poraba["dan_bajti"] = dan, 0
            if self._poraba["mesec"] != mesec:
                self._poraba["mesec"], self._poraba["mesec_bajti"] = mesec, 0
            self._poraba["dan_bajti"] += n
            self._poraba["mesec_bajti"] += n
            self._seja += n
            self._umazano = True
            shrani = time.monotonic() - self._shranjeno > SHRANI_NA_S
        if shrani:
            self._shrani()

    def _usmeri(self, c: socket.socket, zahteva: Zahteva) -> None:
        if self._krajevni_cilj(zahteva.host):
            # Domace omrezje (tiskalnik, usmerjevalnik, NAS): vedno neposredno, tudi ko gre internet skozi telefon.
            razlog = self._neposredno(c, zahteva)
            if razlog is not None:
                zahteva.napaka(c, razlog)
            return
        pot = self.izberi_pot()
        if pot == "neposredno":
            razlog = self._neposredno(c, zahteva)
            if razlog is None:
                return
            with self._zaklep:
                izpad = self.nacin == "izpad"
            if not (izpad and razlog in ("timeout", "no_path", "dns_failed") and not self.sonda.preveri(takoj=True)):
                zahteva.napaka(c, razlog)
                return
            # Domaci internet je pravkar padel: ta povezava gre ze skozi telefon.
            self.osvezi()
        self._skozi_telefon(c, zahteva)

    def _neposredno(self, c: socket.socket, zahteva: Zahteva) -> Optional[str]:
        """Neposredna povezava. None = opravljeno; sicer razlog, zakaj se ni vzpostavila."""
        try:
            s = socket.create_connection((zahteva.host, zahteva.port), timeout=ROK_NEPOSREDNO_S)
        except Exception as e:  # noqa: BLE001
            return razlog_povezave(e)
        with self._zaklep:
            self.tokov_neposredno += 1
        try:
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            zahteva.uspeh(c)
            if zahteva.predpodatki:
                s.sendall(zahteva.predpodatki)
            prenasaj_neposredno(c, s)
        except OSError:
            pass
        finally:
            with self._zaklep:
                self.tokov_neposredno -= 1
            try:
                s.close()
            except OSError:
                pass
        return None

    def _skozi_telefon(self, c: socket.socket, zahteva: Zahteva) -> None:
        telefon = self.telefon()
        if telefon is None:
            self.zadnja_napaka = "ni_telefona"
            zahteva.napaka(c, "no_path")
            return
        if self.internet.protokol(telefon) < 2:
            # Telefon mora povedati, da zna nadzor pretoka. Brez odgovora je Safeer OS na njem starejsi (ali ga
            # ni); tega ne sprasujemo ob vsaki povezavi znova. Vprasamo VEDNO, tudi z diagnosticno zastavico:
            # tok brez oken proti ponudniku z okni obstane po prvih 128 KiB.
            zdaj = time.monotonic()
            if self._brez_odgovora.get(telefon, 0.0) <= zdaj and self.internet.vprasaj(telefon) is None:
                self._brez_odgovora[telefon] = zdaj + 30.0
            if self.internet.protokol(telefon) < 2 and not self.stari_ponudniki:
                self.zadnja_napaka = "old_provider"
                zahteva.napaka(c, "old_provider")
                return
        with self._zaklep:
            pot = self.pot
        tok, razlog = self.internet.odpri(telefon, zahteva.host, zahteva.port, c, pot)
        if tok is None:
            self.zadnja_napaka = razlog
            zahteva.napaka(c, razlog)
            return
        try:
            c.settimeout(ROK_ROKOVANJA_S)
            zahteva.uspeh(c)
        except OSError:
            tok.prekini("local")
            return
        self.zadnja_napaka = ""
        tok.zazeni(zahteva.predpodatki)
        tok.pocakaj()

    # ------------------------------------------------------------------ tunel in preizkus

    def tunel(self, host: str, port: int, naprava: str, pot: str, okna: Optional[bool] = None,
              cas: float = link_internet.ROK_ODPIRANJA_S) -> Tuple[Optional[socket.socket], Optional[link_internet.Tok], str]:
        """Vticnica, ki je skozi telefon povezana na `host:port` (za preizkus in lastne zahteve)."""
        a, b = socket.socketpair()
        tok, razlog = self.internet.odpri(naprava, host, port, b, pot, cas=cas, okna=okna)
        if tok is None:
            a.close()
            b.close()
            return None, None, razlog
        tok.zazeni()
        return a, tok, ""

    @staticmethod
    def _sled(vticnik: socket.socket, rok: float) -> Dict[str, str]:
        """GET /cdn-cgi/trace po TLS na ze povezani vticnici -> {ip, loc, ...}."""
        vticnik.settimeout(rok)
        kontekst = ssl.create_default_context()
        with kontekst.wrap_socket(vticnik, server_hostname=PREIZKUS_GOSTITELJ) as t:
            t.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: SafeerControl\r\nConnection: close\r\n\r\n"
                       % (PREIZKUS_POT, PREIZKUS_GOSTITELJ)).encode("ascii"))
            zbrano = b""
            while len(zbrano) < 65536:
                kos = t.recv(4096)
                if not kos:
                    break
                zbrano += kos
        glava, _, telo = zbrano.partition(b"\r\n\r\n")
        if not glava.startswith(b"HTTP/1.1 200") and not glava.startswith(b"HTTP/1.0 200"):
            raise OSError("odgovor " + glava[:32].decode("latin-1", "replace"))
        polja = {}
        for v in telo.decode("utf-8", "replace").splitlines():
            k, je, vrednost = v.partition("=")
            if je and k.strip().isalnum():
                polja[k.strip()] = vrednost.strip()
        return polja

    def preizkus(self, naprava: str = "", pot: str = "", stari: bool = False) -> dict:
        """Resnicna zahteva skozi telefon: pove, po katerem omrezju je sla in s katerim javnim naslovom."""
        telefon = naprava or self.telefon()
        if not telefon:
            return {"ok": False, "koda": "ni_telefona"}
        pot = pot or self.pot
        stanje = self.internet.vprasaj(telefon)
        if stanje is None and not stari:
            return {"ok": False, "koda": "old_provider", "naprava": telefon}
        if stanje is not None:
            if not stanje.get("enabled", True):
                return {"ok": False, "koda": "disabled", "naprava": telefon, "ponudnik": stanje}
            if str(stanje.get("permission") or "allowed") != "allowed":
                return {"ok": False, "koda": "permission_required" if stanje.get("permission") == "pending" else "denied",
                        "naprava": telefon, "ponudnik": stanje}
        izid: dict = {"ok": False, "naprava": telefon, "zahtevana_pot": pot, "ponudnik": stanje}
        zacetek = time.monotonic()
        vticnik, tok, razlog = self.tunel(PREIZKUS_GOSTITELJ, 443, telefon, pot, okna=None if stanje is not None else False)
        if vticnik is None or tok is None:
            izid["koda"] = razlog
            return izid
        izid["odprto_ms"] = int((time.monotonic() - zacetek) * 1000)
        izid["vrsta_poti"] = tok.vrsta_poti
        izid["pot_id"] = tok.pot_id
        try:
            sled = self._sled(vticnik, 20.0)
        except Exception as e:  # noqa: BLE001
            tok.prekini("local")
            izid["koda"] = "connect_failed"
            izid["sporocilo"] = str(e)[:160]
            return izid
        finally:
            try:
                vticnik.close()
            except OSError:
                pass
        izid["skupaj_ms"] = int((time.monotonic() - zacetek) * 1000)
        izid["naslov_prek_telefona"] = sled.get("ip", "")
        izid["drzava"] = sled.get("loc", "")
        izid["bajtov"] = tok.gor + tok.dol
        # Isto se neposredno: razlicna javna naslova dokazeta, da promet res zapusti telefon po drugi poti.
        try:
            with socket.create_connection((PREIZKUS_GOSTITELJ, 443), timeout=6.0) as s:
                izid["naslov_neposredno"] = self._sled(s, 10.0).get("ip", "")
        except Exception:  # noqa: BLE001
            izid["naslov_neposredno"] = ""
        izid["druga_pot"] = bool(izid["naslov_prek_telefona"]) and izid["naslov_prek_telefona"] != izid["naslov_neposredno"]
        izid["ok"] = bool(izid["naslov_prek_telefona"])
        if not izid["ok"]:
            izid["koda"] = "connect_failed"
        return izid

    # ------------------------------------------------------------------ stanje

    def stanje(self, vprasaj: bool = False) -> dict:
        telefon = self.telefon()
        ponudnik = None
        brez_odgovora = False
        if telefon:
            zdaj = time.monotonic()
            if vprasaj:
                ponudnik = self.internet.vprasaj(telefon)
                if ponudnik is None:
                    self._brez_odgovora[telefon] = zdaj + 30.0
                else:
                    self._brez_odgovora.pop(telefon, None)
            else:
                ponudnik = self.internet.znano_stanje(telefon)
            # Telefon oglasa deljenje, na vprasanje pa ne odgovori: na njem je starejsi Safeer OS (protokol 1).
            brez_odgovora = ponudnik is None and self._brez_odgovora.get(telefon, 0.0) > zdaj
        dan, mesec = _danes()
        with self._zaklep:
            poraba = {"seja": self._seja,
                      "danes": self._poraba["dan_bajti"] if self._poraba["dan"] == dan else 0,
                      "mesec": self._poraba["mesec_bajti"] if self._poraba["mesec"] == mesec else 0}
            izid = {"ok": True, "nacin": self.nacin, "naprava": self.naprava, "telefon": telefon or "",
                    "pot": self.pot, "prek_telefona": self.prek_telefona,
                    "posrednik": {"tece": self.posrednik.tece, "naslov": "127.0.0.1", "vrata": self.posrednik.vrata or self.vrata},
                    "fiksna": {"dela": self.sonda.dela, "preverjeno": self.sonda.preverjeno},
                    "tokovi": {"telefon": self.internet.stevilo_tokov(), "neposredno": self.tokov_neposredno},
                    "poraba": poraba, "napaka": self.zadnja_napaka,
                    "sistemski": {"vklopljen": self.sistemski_vklopljen,
                                  "podprt": bool(self.sistemski is not None and self.sistemski.podprt()),
                                  "nastavljen": bool(self.sistemski is not None and self.sistemski.nastavljen())}}
        izid["telefoni"] = self.telefoni()
        izid["ponudnik"] = ponudnik
        izid["brez_odgovora"] = brez_odgovora
        izid["protokol"] = self.internet.protokol(telefon) if telefon else 0
        return izid

    def okolje(self) -> Dict[str, str]:
        """Spremenljivke okolja za programe v ukazni vrstici."""
        vrata = self.posrednik.vrata or self.vrata
        http = "http://127.0.0.1:%d" % vrata
        return {"ALL_PROXY": "socks5h://127.0.0.1:%d" % vrata, "HTTPS_PROXY": http, "HTTP_PROXY": http,
                "https_proxy": http, "http_proxy": http, "NO_PROXY": "localhost,127.0.0.1,::1"}
