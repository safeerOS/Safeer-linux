"""Slicice datotek z drugih naprav v Safeer Linku za Datoteke (lastnik 25. 10. 2026: »tudi za povezane naprave«).

Naprava (telefon, tablica, TV, racunalnik) strezne slicico slike ali videa na `GET <base_url>/thumb/<id>?s=<rob>` z
zetonom (`X-Safeer-Token`) in pripetim potrdilom (`fp`) - oboje pride v odgovoru na `files.list` (polje `server`).
Dogovor je skupen z Windows (outputs/windows-tema/za-android-datoteke.md, tocka 3.6) in Androidom (veja link-datoteke,
DatotekeStreznik `/thumb/<id>?s=` 128-512, ETag): rob 256, odgovor JPEG/PNG/WebP, najvec 2 MB, rok 8 s, najvec 2 hkrati;
predpomnilnik na disku po kljucu naprava + oznaka + cas spremembe + velikost (nova razlicica datoteke = nova slicica),
najvec 200 MB. Racunalnik s Safeer Controlom `?s=` prezre in poslje svojo velikost (link_datoteke.naredi_slicico).

Ta modul je brez GTK. Streznik vzame klicatelj iz SVOJEGA zadnjega odgovora `files.list` (stran ga ne more podtakniti),
dovoljenje (ozji krog) preveri klicatelj (safeer_os.slicice_naprave), naprava pa ob vsaki zahtevi se sama (zeton).
Brez domacega naslova (samo Global Link, 192.0.2.1) slicic zaenkrat ne prosimo - ostane ikona (nepreverjena pot Huba).
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Iterable, Optional
from urllib.parse import quote, urlparse

ROB = 256
NAJVEC_ODGOVOR = 2 * 1024 * 1024
ROK_S = 8.0
HKRATI = 2
NAJVEC_PREDPOMNILNIK = 200 * 1024 * 1024
#: Toliko vnosov najvec v enem klicu (ena stran Datotek).
NAJVEC_VNOSOV = 80
#: Naprava, ki slicice ne da (stara, datoteka brez slicice), toliko casa ni vprasana znova za isto datoteko.
PREMOR_NEUSPEHA_S = 600.0
#: Naslov brez domacega omrezja (Android: samo prek sredisca) - slicic ne prosimo.
BREZ_LAN = "192.0.2.1"
_ODTIS = re.compile(r"^[0-9A-Fa-f:]{40,128}$")
_KONCNICE = ("jpg", "png", "webp")


def veljaven_streznik(streznik) -> bool:
    """Streznik iz files.list: https, gostitelj, odtis, zeton - sicer ga ne uporabimo."""
    if not isinstance(streznik, dict):
        return False
    u = urlparse(str(streznik.get("base_url") or ""))
    fp = str(streznik.get("fp") or "")
    try:
        u.port
    except ValueError:
        return False
    return (u.scheme == "https" and bool(u.hostname) and u.hostname != BREZ_LAN and bool(_ODTIS.match(fp))
            and bool(str(streznik.get("token") or "")))


def vrsta_slike(bajti: bytes) -> str:
    """'jpg', 'png', 'webp' ali '' (ni slika - ne shranimo)."""
    if bajti[:3] == b"\xff\xd8\xff":
        return "jpg"
    if bajti[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if bajti[:4] == b"RIFF" and bajti[8:12] == b"WEBP":
        return "webp"
    return ""


def kljuc(id_naprave: str, oznaka: str, spremenjeno, velikost) -> str:
    return hashlib.sha256(("%s\n%s\n%s\n%s" % (id_naprave, oznaka, spremenjeno, velikost)).encode("utf-8")).hexdigest()


def prenesi_https(streznik: dict, oznaka: str, rob: int = ROB) -> Optional[bytes]:
    """GET /thumb/<oznaka>?s=<rob> s pripetim potrdilom naprave in zetonom; None, ce slicice ni. Preusmeritvam ne
    sledimo (zahteva nosi zeton - AGENTS.md)."""
    from core import link_tls
    u = urlparse(str(streznik.get("base_url")))
    povezava = link_tls._PripetaHttps(u.hostname, u.port or 443, str(streznik.get("fp") or ""), ROK_S)
    try:
        pot = (u.path.rstrip("/") + "/thumb/" + quote(str(oznaka), safe="")) + "?s=%d" % int(rob)
        povezava.request("GET", pot, headers={"X-Safeer-Token": str(streznik.get("token") or "")})
        odgovor = povezava.getresponse()
        if odgovor.status != 200:
            return None
        bajti = odgovor.read(NAJVEC_ODGOVOR + 1)
        return bajti if len(bajti) <= NAJVEC_ODGOVOR else None
    finally:
        povezava.close()


class Slicice:
    """Predpomnilnik slicic naprav na disku in prenos (najvec HKRATI hkrati za vse klicatelje skupaj)."""

    def __init__(self, mapa: str, prenesi: Optional[Callable] = None, najvec: int = NAJVEC_PREDPOMNILNIK) -> None:
        self.mapa = mapa
        self._prenesi = prenesi or prenesi_https
        self._najvec = najvec
        self._mesta = threading.BoundedSemaphore(HKRATI)
        self._zaklep = threading.Lock()
        self._neuspelo: Dict[str, float] = {}
        #: Ocena velikosti predpomnilnika (bajti); None = se ni presteta. Cel pregled mape samo ob prvem zapisu in ko
        #: ocena preseze mejo - ne ob vsaki slicici (20 000 datotek pri 200 MB).
        self._ocena: Optional[int] = None

    def _pot(self, k: str) -> Optional[str]:
        for konc in _KONCNICE:
            p = os.path.join(self.mapa, k[:2], "%s.%s" % (k, konc))
            if os.path.isfile(p):
                return p
        return None

    def dobi(self, id_naprave: str, streznik: dict, vnosi: Iterable[dict], rok: float = 6.0) -> Dict[str, str]:
        """{oznaka: pot_slicice} za vnose [{id, modified, size}] - iz predpomnilnika ali prenesene (do roka)."""
        izid: Dict[str, str] = {}
        if not veljaven_streznik(streznik):
            return izid
        konec = time.monotonic() + rok
        manjka = []
        for v in list(vnosi or [])[:NAJVEC_VNOSOV]:
            if not isinstance(v, dict):
                continue
            oznaka = str(v.get("id") or "")
            if not oznaka or len(oznaka) > 512 or "\n" in oznaka or "\r" in oznaka:
                continue
            k = kljuc(id_naprave, oznaka, v.get("modified") or v.get("mtime") or "", v.get("size") or "")
            pot = self._pot(k)
            if pot:
                izid[oznaka] = pot
            elif time.monotonic() >= self._neuspelo.get(k, 0.0):
                manjka.append((oznaka, k))
        if not manjka:
            return izid

        def eno(par):
            oznaka, k = par
            cakaj = konec - time.monotonic()
            if cakaj <= 0 or not self._mesta.acquire(timeout=cakaj):
                return None
            try:
                try:
                    bajti = self._prenesi(streznik, oznaka, ROB)
                except Exception as e:  # noqa: BLE001 - nedosegljiva naprava: ikona ostane
                    print("[SafeerOS] slicica naprave:", type(e).__name__, flush=True)
                    bajti = None
            finally:
                self._mesta.release()
            konc = vrsta_slike(bajti or b"")
            if not konc:
                with self._zaklep:
                    if len(self._neuspelo) > 5000:
                        self._neuspelo.clear()
                    self._neuspelo[k] = time.monotonic() + PREMOR_NEUSPEHA_S
                return None
            return oznaka, self._shrani(k, konc, bajti)
        with ThreadPoolExecutor(max_workers=HKRATI, thread_name_prefix="safeer-slicice-naprav") as delavci:
            for r in delavci.map(eno, manjka):
                if r:
                    izid[r[0]] = r[1]
        return izid

    def _shrani(self, k: str, konc: str, bajti: bytes) -> str:
        mapa = os.path.join(self.mapa, k[:2])
        os.makedirs(mapa, mode=0o700, exist_ok=True)
        cilj = os.path.join(mapa, "%s.%s" % (k, konc))
        fd, zacasna = tempfile.mkstemp(dir=mapa, suffix=".part")
        try:
            with os.fdopen(fd, "wb") as d:
                d.write(bajti)
            os.replace(zacasna, cilj)
        except OSError:
            try:
                os.remove(zacasna)
            except OSError:
                pass
            raise
        with self._zaklep:
            self._ocena = None if self._ocena is None else self._ocena + len(bajti)
            preveri = self._ocena is None or self._ocena > self._najvec
        if preveri:
            self._pocisti()
        return cilj

    def _pocisti(self) -> None:
        """Nad mejo: najstarejse (po casu dostopa/spremembe) brisemo, dokler ne pade pod 80 % meje."""
        with self._zaklep:
            datoteke = []
            skupaj = 0
            for koren, _mape, imena in os.walk(self.mapa):
                for ime in imena:
                    p = os.path.join(koren, ime)
                    try:
                        s = os.stat(p)
                    except OSError:
                        continue
                    datoteke.append((max(s.st_atime, s.st_mtime), s.st_size, p))
                    skupaj += s.st_size
            if skupaj > self._najvec:
                for _cas, vel, p in sorted(datoteke):
                    try:
                        os.remove(p)
                    except OSError:
                        continue
                    skupaj -= vel
                    if skupaj <= self._najvec * 0.8:
                        break
            self._ocena = skupaj
