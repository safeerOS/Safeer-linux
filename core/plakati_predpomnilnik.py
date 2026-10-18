"""Plakati in naslovnice, ki jih vir poda po navadnem http:// (npr. naslov IP brez TLS).

Stran Medijskega centra dovoli slike samo prek https, file: in data: (CSP v assets/os/index.html), zato se plakat z
naslovom http://... ni pokazal (serije vira Iracemaflix, 18. 10. 2026). Namesto da bi CSP razrahljali za vsak naslov na
spletu, sliko prenese Safeer OS sam (samo GET, najvec 3 MB, samo image/*, brez lokalnih naslovov in preusmeritev na
druge sheme) in jo shrani v predpomnilnik; stran dobi pot do datoteke.
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import socket
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

NAJVEC_BAJTOV = 3 * 1024 * 1024
NAJVEC_DATOTEK = 2000
CAS_S = 8
_PRIPONE = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
            "image/avif": ".avif"}
_zaklep = threading.Lock()


def mapa() -> Path:
    osnova = os.environ.get("SAFEER_PLAKATI_MAPA")
    if osnova:
        return Path(osnova)
    return Path(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")) / "safeer-os" / "plakati"


def _dovoljen_naslov(gostitelj: str) -> bool:
    """Brez povratne zanke in naslovov, ki jih uporabljajo storitve na tem racunalniku (127.x, ::1, link-local)."""
    try:
        naslovi = {i[4][0] for i in socket.getaddrinfo(gostitelj, None)}
    except OSError:
        return False
    for n in naslovi:
        try:
            ip = ipaddress.ip_address(n.split("%")[0])
        except ValueError:
            return False
        if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:
            return False
    return bool(naslovi)


class _BrezPreusmeritve(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        u = urllib.parse.urlsplit(newurl)
        if u.scheme not in ("http", "https") or not u.hostname or not _dovoljen_naslov(u.hostname):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _poscisti(m: Path) -> None:
    try:
        datoteke = sorted((p for p in m.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime)
    except OSError:
        return
    for p in datoteke[:max(0, len(datoteke) - NAJVEC_DATOTEK)]:
        try:
            p.unlink()
        except OSError:
            pass


def predpomni(url: str, cas: float = CAS_S) -> Optional[str]:
    """Pot do predpomnjene slike ali None. Naslov mora biti http(s)://."""
    u = urllib.parse.urlsplit(str(url or ""))
    if u.scheme not in ("http", "https") or not u.hostname or len(str(url)) > 2000:
        return None
    ime = hashlib.sha256(str(url).encode("utf-8")).hexdigest()[:32]
    m = mapa()
    for pripona in set(_PRIPONE.values()):
        obstojec = m / (ime + pripona)
        if obstojec.is_file():
            return str(obstojec)
    if not _dovoljen_naslov(u.hostname):
        return None
    try:
        odpiralnik = urllib.request.build_opener(_BrezPreusmeritve)
        zahteva = urllib.request.Request(str(url), headers={"User-Agent": "SafeerOS", "Accept": "image/*"})
        with odpiralnik.open(zahteva, timeout=cas) as odziv:
            vrsta = (odziv.headers.get_content_type() or "").lower()
            if vrsta not in _PRIPONE:
                return None
            podatki = odziv.read(NAJVEC_BAJTOV + 1)
    except Exception:  # noqa: BLE001 - omrezna napaka: plakata ni
        return None
    if not podatki or len(podatki) > NAJVEC_BAJTOV:
        return None
    with _zaklep:
        m.mkdir(parents=True, exist_ok=True)
        pot = m / (ime + _PRIPONE[vrsta])
        zacasna = m / (ime + ".part")
        zacasna.write_bytes(podatki)
        os.replace(zacasna, pot)
        _poscisti(m)
    return str(pot)
