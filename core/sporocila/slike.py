"""Oddaljene slike v HTML pismih prek zascite Safeer (kot posrednik slik v Gmailu).

Privzeto so skrite (posiljatelj ne izve, kdaj in kje je bilo pismo odprto). Ko jih uporabnik pokaze, jih prenese
Safeer sam - ne pogled predogleda, ki ostane brez omrezja, JavaScripta in mostu (core/os_predogled.py):
* brez piskotkov, brez Referer, splosen User-Agent; samo http(s) in samo javni naslovi (slika v pismu ne sme
  dosegati usmerjevalnika ali naprav v domacem omrezju). Ime se razresi enkrat, povezava gre na preverjeni IP
  (SNI, potrdilo in Host ostanejo ime) - DNS rebinding (drug odgovor ob povezavi) ne pride v domace omrezje;
* sledilni piksli: slike 1x1 (po atributih in po dejanski velikosti), znani sledilni naslovi in domene s seznamov
  oglasov/groženj Safeerja (je_blokirano, poda Safeer OS) se ne prenesejo ali ne pokazejo;
* najvec NAJVEC_SLIK slik po najvec NAJVEC_BAJTOV, samo vrste image/*; shranijo se v vnos pisma v predpomnilniku.
Izbira »Vedno prikazi od« se hrani lokalno po naslovu posiljatelja (DovoljeniPosiljatelji).
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Iterable, Optional
from urllib.parse import quote, urlsplit

NAJVEC_SLIK = 40
NAJVEC_BAJTOV = 5 * 1024 * 1024
CAS_S = 10
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) Safeer"

#: Znani sledilni naslovi v pismih (odprtje pisma): gostitelj ali pot.
_SLEDILNI_GOSTITELJI = ("doubleclick.net", "google-analytics.com", "mailtrack.io", "mailtrack.com", "track.hubspot.com",
                        "t.sidekickopen", "pixel.mailchimp", "open.convertkit", "trk.klclick", "click.mlsend",
                        "pixel.wp.com", "mandrillapp.com", "mcusercontent", "tracking.", "pixel.", "beacon.",
                        "emltrk.com", "bananatag.com", "yesware.com", "streak.com", "mixmax.com", "getnotify.com")
_SLEDILNE_POTI = re.compile(r"/(wf/open|open\.(gif|png|php|aspx?)|track(ing)?/open|pixel(\.gif|\.png)?|beacon|"
                            r"e/o/|o\.gif|trk|imp(ression)?\.gif|t\.gif|1x1\.(gif|png))(\b|/|\?|$)", re.I)


def je_sledilec(url: str, je_blokirano: Optional[Callable[[str], bool]] = None) -> bool:
    try:
        deli = urlsplit(url)
    except ValueError:
        return True
    gost = (deli.hostname or "").lower()
    if any(g in gost for g in _SLEDILNI_GOSTITELJI) or _SLEDILNE_POTI.search(deli.path or ""):
        return True
    if je_blokirano is not None:
        try:
            return bool(je_blokirano(url))
        except Exception:  # noqa: BLE001
            return False
    return False


def javni_naslov(gostitelj: str, razresi=socket.getaddrinfo) -> str:
    """Ime razresi ENKRAT in vrne prvi naslov, ce so VSI dobljeni naslovi javni (ne 127.*, 10.*, 192.168.*, fe80::);
    sicer "". Povezava gre potem na ta naslov (glej _povezava) - drugo razresevanje (DNS rebinding) je ne preusmeri."""
    try:
        naslovi = [i[4][0] for i in razresi(gostitelj, None)]
    except (OSError, UnicodeError):
        return ""
    try:
        if naslovi and all(ipaddress.ip_address(n.split("%")[0]).is_global for n in naslovi):
            return naslovi[0]
    except ValueError:
        pass
    return ""


def javni_gostitelj(gostitelj: str, razresi=socket.getaddrinfo) -> bool:
    return bool(javni_naslov(gostitelj, razresi))


def _deli_url(url: str):
    """(shema, ime, vrata, pot) ali None za nedovoljen naslov (ne http(s), uporabnik/geslo, slaba vrata)."""
    try:
        deli = urlsplit(url)
        vrata = deli.port
    except ValueError:
        return None
    if deli.scheme not in ("http", "https") or not deli.hostname or deli.username or deli.password:
        return None
    pot = (deli.path or "/") + ("?" + deli.query if deli.query else "")
    return deli.scheme, deli.hostname, vrata or (443 if deli.scheme == "https" else 80), pot


def _povezava(ime: str, ip: str, vrata: int, https: bool, cas: float):
    """Povezava na ze preverjeni IP; ime ostane za glavo Host, SNI in preverjanje potrdila (http.client, ssl)."""
    import http.client
    import ssl
    if https:
        pov = http.client.HTTPSConnection(ime, vrata, timeout=cas, context=ssl.create_default_context())
    else:
        pov = http.client.HTTPConnection(ime, vrata, timeout=cas)
    # http.client se poveze s self._create_connection((self.host, port)) in nato (HTTPS) ovije vticnico s
    # server_hostname=self.host: zamenjamo samo naslov vticnice - ime za SNI in potrdilo ostane.
    pov._create_connection = lambda naslov, *a, **k: socket.create_connection((ip, naslov[1]), *a, **k)
    return pov


def _majhna(podatki: bytes) -> bool:
    """Sledilni piksel po vsebini: slika do 2x2 tock. GIF in PNG beremo iz glave sami (Pillow ni nujen), drugo s Pillow."""
    import struct
    if podatki[:6] in (b"GIF87a", b"GIF89a") and len(podatki) >= 10:
        s, v = struct.unpack("<HH", podatki[6:10])
        return s <= 2 and v <= 2
    if podatki[:8] == b"\x89PNG\r\n\x1a\n" and len(podatki) >= 24:
        s, v = struct.unpack(">II", podatki[16:24])
        return s <= 2 and v <= 2
    try:
        import io
        from PIL import Image
        with Image.open(io.BytesIO(podatki)) as s:
            return s.width <= 2 and s.height <= 2
    except Exception:  # noqa: BLE001
        return len(podatki) < 120 and podatki[:4] in (b"GIF8", b"\x89PNG")


_KONCNICE = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp",
             "image/svg+xml": ".svg", "image/avif": ".avif", "image/bmp": ".bmp"}


# ---------------------------------------------------------------------------------------------- posrednik
# Ce je uporabnik nastavil posrednika (Safeer secure_proxy_mode ali sistemski), slike gredo PREK njega - neposredna
# povezava bi razkrila naslov IP, ki ga je hotel skriti. Posrednik ime razresi sam; zascito domacega omrezja
# preverimo za ime pred zahtevo. Posrednika, ki ga ne znamo (npr. SOCKS4, PAC), ne obidemo: slike se ne nalozijo.
_PODPRTI_POSREDNIKI = ("http", "https", "socks5", "socks5h", "socks")


def posrednik_okolja(url: str) -> str:
    """Posrednik iz okolja (http_proxy, https_proxy, all_proxy); "" = neposredno. Safeer OS poda boljsega
    (nastavitev Spleta in sistemske nastavitve namizja, glej safeer_os._posrednik_slik)."""
    from urllib.request import getproxies, proxy_bypass
    try:
        deli = urlsplit(url)
        if deli.hostname and proxy_bypass(deli.hostname):
            return ""
        vsi = getproxies()
        return str(vsi.get(deli.scheme) or vsi.get("all") or "")
    except Exception:  # noqa: BLE001
        return ""


def _beri_do(vticnica, konec: bytes, najvec: int = 16384) -> bytes:
    podatki = b""
    while konec not in podatki:
        kos = vticnica.recv(1024)
        if not kos:
            raise OSError("posrednik je prekinil")
        podatki += kos
        if len(podatki) > najvec:
            raise OSError("predolg odgovor posrednika")
    return podatki


def _beri_n(vticnica, n: int) -> bytes:
    podatki = b""
    while len(podatki) < n:
        kos = vticnica.recv(n - len(podatki))
        if not kos:
            raise OSError("posrednik je prekinil")
        podatki += kos
    return podatki


def _socks5(vticnica, ime: str, vrata: int, uporabnik: str = "", geslo: str = "") -> None:
    """RFC 1928 CONNECT z imenom (ATYP 3: posrednik razresi sam), po potrebi prijava RFC 1929."""
    import struct
    metode = b"\x00\x02" if uporabnik else b"\x00"
    vticnica.sendall(b"\x05" + bytes([len(metode)]) + metode)
    odg = _beri_n(vticnica, 2)
    if odg[0] != 5 or odg[1] == 0xFF:
        raise OSError("SOCKS5: posrednik zavrne")
    if odg[1] == 2:
        u, g = uporabnik.encode("utf-8")[:255], geslo.encode("utf-8")[:255]
        vticnica.sendall(b"\x01" + bytes([len(u)]) + u + bytes([len(g)]) + g)
        if _beri_n(vticnica, 2)[1] != 0:
            raise OSError("SOCKS5: prijava zavrnjena")
    ime_b = ime.encode("idna")[:255]
    vticnica.sendall(b"\x05\x01\x00\x03" + bytes([len(ime_b)]) + ime_b + struct.pack(">H", vrata))
    glava = _beri_n(vticnica, 4)
    if glava[1] != 0:
        raise OSError("SOCKS5: povezava zavrnjena")
    _beri_n(vticnica, {1: 4, 4: 16}.get(glava[3], 0) or _beri_n(vticnica, 1)[0])
    _beri_n(vticnica, 2)


def _povezava_prek(posrednik: str, ime: str, vrata: int, https: bool, cas: float, odpri_vticnico=None):
    """Povezava do ime:vrata prek posrednika. Vrne (povezava, absolutna_pot): pri HTTP posredniku in http cilju gre
    zahteva v absolutni obliki (GET http://ime/...), sicer je povezava tunel (CONNECT ali SOCKS5)."""
    import base64
    import http.client
    import ssl
    from urllib.parse import unquote
    odpri_vticnico = odpri_vticnico or socket.create_connection
    d = urlsplit(posrednik if "://" in posrednik else "http://" + posrednik)
    shema = (d.scheme or "http").lower()
    if shema not in _PODPRTI_POSREDNIKI or not d.hostname:
        raise OSError("posrednika ne znamo uporabiti")
    p_vrata = d.port or {"http": 8080, "https": 443}.get(shema, 1080)
    uporabnik, geslo = unquote(d.username or ""), unquote(d.password or "")

    def do_posrednika():
        v = odpri_vticnico((d.hostname, p_vrata), cas)
        if shema == "https":
            v = ssl.create_default_context().wrap_socket(v, server_hostname=d.hostname)
        return v

    if shema in ("http", "https") and not https:
        pov = http.client.HTTPConnection(d.hostname, p_vrata, timeout=cas)
        pov._create_connection = lambda *_a, **_k: do_posrednika()
        if uporabnik:
            pov._safeer_glave = {"Proxy-Authorization": "Basic " + base64.b64encode(
                ("%s:%s" % (uporabnik, geslo)).encode("utf-8")).decode("ascii")}
        return pov, True

    def tunel(*_a, **_k):
        v = do_posrednika()
        try:
            if shema.startswith("socks"):
                _socks5(v, ime, vrata, uporabnik, geslo)
            else:
                zahteva = "CONNECT %s:%d HTTP/1.1\r\nHost: %s:%d\r\n" % (ime, vrata, ime, vrata)
                if uporabnik:
                    zahteva += "Proxy-Authorization: Basic %s\r\n" % base64.b64encode(
                        ("%s:%s" % (uporabnik, geslo)).encode("utf-8")).decode("ascii")
                v.sendall((zahteva + "\r\n").encode("utf-8"))
                vrstica = _beri_do(v, b"\r\n\r\n").split(b"\r\n", 1)[0].split()
                if len(vrstica) < 2 or vrstica[1] != b"200":
                    raise OSError("posrednik ni odprl tunela")
            return v
        except Exception:
            v.close()
            raise
    if https:
        pov = http.client.HTTPSConnection(ime, vrata, timeout=cas, context=ssl.create_default_context())
    else:
        pov = http.client.HTTPConnection(ime, vrata, timeout=cas)
    pov._create_connection = tunel          # TLS do slike (SNI, potrdilo) gre skozi tunel z imenom
    return pov, False


def _pridobi(url: str, razresi, povezi, posrednik=None, povezi_prek=_povezava_prek) -> tuple:
    """GET slike brez piskotkov in Referer; vsaka preusmeritev (najvec 4) gre skozi isto preverbo. (tip, podatki).
    posrednik(url) -> naslov posrednika ali "" (neposredno, na preverjeni IP)."""
    from urllib.parse import urljoin
    for _ in range(5):
        deli = _deli_url(url)
        if deli is None:
            return "", b""
        shema, ime, vrata, pot = deli
        ip = javni_naslov(ime, razresi)          # zascita domacega omrezja: vedno, tudi ko razresi posrednik
        if not ip:
            return "", b""
        prek = posrednik(url) if posrednik is not None else ""
        glave = {"User-Agent": USER_AGENT, "Accept": "image/*"}
        if prek:
            pov, absolutno = povezi_prek(prek, ime, vrata, shema == "https", CAS_S)
            if absolutno:
                pot = "http://%s:%d%s" % (ime, vrata, pot)
                glave["Host"] = ime if vrata == 80 else "%s:%d" % (ime, vrata)
                glave.update(getattr(pov, "_safeer_glave", {}))
        else:
            pov = povezi(ime, ip, vrata, shema == "https", CAS_S)
        try:
            pov.request("GET", pot, headers=glave)
            odg = pov.getresponse()
            if odg.status in (301, 302, 303, 307, 308):
                cilj = odg.getheader("Location") or ""
                if not cilj:
                    return "", b""
                url = urljoin(url, cilj)
                continue
            if odg.status != 200:
                return "", b""
            tip = str(odg.getheader("Content-Type") or "").split(";")[0].strip().lower()
            if tip not in _KONCNICE:
                return "", b""
            return tip, odg.read(NAJVEC_BAJTOV + 1)
        finally:
            pov.close()
    return "", b""


def prenesi_sliko(url: str, mapa: str, razresi=socket.getaddrinfo, povezi=_povezava, posrednik=None,
                  povezi_prek=_povezava_prek) -> str:
    """Ena slika v `mapa` (ime = zgostitev naslova). Vrne pot ali "" (blokirano, ni slika, prevelika, napaka)."""
    if _deli_url(url) is None:
        return ""
    ime = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    for konc in set(_KONCNICE.values()):
        if os.path.isfile(os.path.join(mapa, ime + konc)):
            return os.path.join(mapa, ime + konc)
    try:
        tip, podatki = _pridobi(url, razresi, povezi, posrednik, povezi_prek)
    except Exception:  # noqa: BLE001 - omrezje, potrdilo: slike pac ni
        return ""
    if not tip or len(podatki) > NAJVEC_BAJTOV or not podatki or _majhna(podatki):
        return ""
    pot = os.path.join(mapa, ime + _KONCNICE[tip])
    with open(pot + ".tmp", "wb") as f:
        f.write(podatki)
    os.chmod(pot + ".tmp", 0o600)
    os.replace(pot + ".tmp", pot)
    return pot


def prenesi_slike(naslovi: Iterable[str], mapa: str, je_blokirano: Optional[Callable[[str], bool]] = None,
                  razresi=socket.getaddrinfo, povezi=_povezava, posrednik=posrednik_okolja,
                  povezi_prek=_povezava_prek) -> Dict[str, str]:
    """{url: file:// naslov} za slike, ki so prestale zascito (vzporedno, najvec NAJVEC_SLIK)."""
    izbrani = []
    for u in naslovi:
        if u not in izbrani and not je_sledilec(u, je_blokirano):
            izbrani.append(u)
        if len(izbrani) >= NAJVEC_SLIK:
            break
    izid: Dict[str, str] = {}
    if not izbrani:
        return izid
    with ThreadPoolExecutor(max_workers=6) as bazen:
        for u, pot in zip(izbrani, bazen.map(lambda x: prenesi_sliko(x, mapa, razresi, povezi, posrednik, povezi_prek), izbrani)):
            if pot:
                izid[u] = "file://" + quote(os.path.abspath(pot))
    return izid


class DovoljeniPosiljatelji:
    """»Vedno prikazi slike od …«: naslovi posiljateljev v lokalni datoteki (0600), s preklicem."""

    def __init__(self, pot: str):
        self.pot = pot
        self._zaklep = threading.Lock()

    @staticmethod
    def _kljuc(naslov: str) -> str:
        return str(naslov or "").strip().lower()

    def _beri(self) -> list:
        try:
            with open(self.pot, encoding="utf-8") as f:
                v = json.load(f)
            return [str(x) for x in v] if isinstance(v, list) else []
        except (OSError, ValueError):
            return []

    def seznam(self) -> list:
        with self._zaklep:
            return sorted(self._beri())

    def dovoljen(self, naslov: str) -> bool:
        return bool(self._kljuc(naslov)) and self._kljuc(naslov) in self.seznam()

    def nastavi(self, naslov: str, dovoli: bool) -> list:
        k = self._kljuc(naslov)
        if "@" not in k or len(k) > 320:
            raise ValueError("Neveljaven naslov")
        with self._zaklep:
            vsi = set(self._beri())
            (vsi.add if dovoli else vsi.discard)(k)
            os.makedirs(os.path.dirname(self.pot) or ".", exist_ok=True)
            with open(self.pot + ".tmp", "w", encoding="utf-8") as f:
                json.dump(sorted(vsi), f)
            os.chmod(self.pot + ".tmp", 0o600)
            os.replace(self.pot + ".tmp", self.pot)
            return sorted(vsi)
