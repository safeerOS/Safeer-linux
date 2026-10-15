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


def _pridobi(url: str, razresi, povezi) -> tuple:
    """GET slike brez piskotkov in Referer; vsaka preusmeritev (najvec 4) gre skozi isto preverbo. (tip, podatki)."""
    from urllib.parse import urljoin
    for _ in range(5):
        deli = _deli_url(url)
        if deli is None:
            return "", b""
        shema, ime, vrata, pot = deli
        ip = javni_naslov(ime, razresi)
        if not ip:
            return "", b""
        pov = povezi(ime, ip, vrata, shema == "https", CAS_S)
        try:
            pov.request("GET", pot, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
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


def prenesi_sliko(url: str, mapa: str, razresi=socket.getaddrinfo, povezi=_povezava) -> str:
    """Ena slika v `mapa` (ime = zgostitev naslova). Vrne pot ali "" (blokirano, ni slika, prevelika, napaka)."""
    if _deli_url(url) is None:
        return ""
    ime = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    for konc in set(_KONCNICE.values()):
        if os.path.isfile(os.path.join(mapa, ime + konc)):
            return os.path.join(mapa, ime + konc)
    try:
        tip, podatki = _pridobi(url, razresi, povezi)
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
                  razresi=socket.getaddrinfo, povezi=_povezava) -> Dict[str, str]:
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
        for u, pot in zip(izbrani, bazen.map(lambda x: prenesi_sliko(x, mapa, razresi, povezi), izbrani)):
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
