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
import queue
import re
import socket
import struct
import tempfile
import threading
import time
from typing import Callable, Dict, Iterable, Optional, Tuple
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
#: Najvecja stranica prejete slicice (dogovor: rob 128-512). 2 MB PNG lahko v glavi napove 30000 x 30000 pik (~3,6 GB
#: pri dekodiranju v Safeer OS) - tako ne shranimo (sedmi pregled, naloga 6, 25. 10. 2026).
NAJVEC_ROB_PREJETE = 1024


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


def dimenzije_slike(bajti: bytes) -> Optional[Tuple[int, int]]:
    """(sirina, visina) iz glave JPEG (SOFn), PNG (IHDR) ali WebP (VP8, VP8L, VP8X); None, ce glave ni mogoce prebrati."""
    try:
        if bajti[:8] == b"\x89PNG\r\n\x1a\n" and bajti[12:16] == b"IHDR":
            return struct.unpack(">II", bajti[16:24])
        if bajti[:4] == b"RIFF" and bajti[8:12] == b"WEBP":
            vrsta = bajti[12:16]
            if vrsta == b"VP8X":
                return (int.from_bytes(bajti[24:27], "little") + 1, int.from_bytes(bajti[27:30], "little") + 1)
            if vrsta == b"VP8L" and bajti[20:21] == b"\x2f":
                b = int.from_bytes(bajti[21:25], "little")
                return ((b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1)
            if vrsta == b"VP8 " and bajti[23:26] == b"\x9d\x01\x2a":
                s_, v_ = struct.unpack("<HH", bajti[26:30])
                return (s_ & 0x3FFF, v_ & 0x3FFF)
            return None
        if bajti[:2] == b"\xff\xd8":
            i = 2
            while i + 9 < len(bajti):
                if bajti[i] != 0xFF:
                    return None
                oznaka = bajti[i + 1]
                if oznaka == 0xFF:
                    i += 1
                    continue
                if oznaka in (0xD8, 0x01) or 0xD0 <= oznaka <= 0xD7:
                    i += 2
                    continue
                dolzina = struct.unpack(">H", bajti[i + 2:i + 4])[0]
                if 0xC0 <= oznaka <= 0xCF and oznaka not in (0xC4, 0xC8, 0xCC):
                    visina, sirina = struct.unpack(">HH", bajti[i + 5:i + 9])
                    return (sirina, visina)
                i += 2 + dolzina
    except (struct.error, IndexError, ValueError):
        return None
    return None


def ustrezna_slicica(bajti: bytes) -> str:
    """Vrsta slike ('jpg', 'png', 'webp'), ce je to slicica razumne velikosti; sicer '' (ne shranimo)."""
    konc = vrsta_slike(bajti)
    if not konc:
        return ""
    dim = dimenzije_slike(bajti)
    if dim is None or not (0 < dim[0] <= NAJVEC_ROB_PREJETE and 0 < dim[1] <= NAJVEC_ROB_PREJETE):
        return ""
    return konc


def kljuc(id_naprave: str, oznaka: str, spremenjeno, velikost) -> str:
    return hashlib.sha256(("%s\n%s\n%s\n%s" % (id_naprave, oznaka, spremenjeno, velikost)).encode("utf-8")).hexdigest()


def prenesi_https(streznik: dict, oznaka: str, rob: int = ROB, rok_s: float = ROK_S) -> Optional[bytes]:
    """GET /thumb/<oznaka>?s=<rob> s pripetim potrdilom naprave in zetonom; None, ce slicice ni. Preusmeritvam ne
    sledimo (zahteva nosi zeton - AGENTS.md). Ves prenos ima skupen rok `rok_s`: naprava, ki posilja po en bajt, ga
    ne raztegne (prej je rok veljal za vsak recv posebej - sedmi pregled, naloga 6)."""
    from core import link_tls
    konec = time.monotonic() + rok_s
    u = urlparse(str(streznik.get("base_url")))
    povezava = link_tls._PripetaHttps(u.hostname, u.port or 443, str(streznik.get("fp") or ""), rok_s)

    def prekini() -> None:
        # Ob roku prekinemo tudi branje, ki ravno caka (en read lahko sestavlja vec recv - pregled 11, N6).
        sock = getattr(povezava, "sock", None)
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
    casovnik = threading.Timer(rok_s, prekini)
    casovnik.daemon = True
    casovnik.start()
    try:
        pot = (u.path.rstrip("/") + "/thumb/" + quote(str(oznaka), safe="")) + "?s=%d" % int(rob)
        povezava.request("GET", pot, headers={"X-Safeer-Token": str(streznik.get("token") or "")})
        odgovor = povezava.getresponse()
        if odgovor.status != 200:
            return None
        bajti = bytearray()
        while len(bajti) <= NAJVEC_ODGOVOR:
            ostane = konec - time.monotonic()
            if ostane <= 0:
                return None
            if povezava.sock is not None:
                povezava.sock.settimeout(ostane)
            kos = odgovor.read(min(64 * 1024, NAJVEC_ODGOVOR + 1 - len(bajti)))
            if not kos:
                break
            bajti += kos
        if time.monotonic() >= konec:
            return None
        return bytes(bajti) if len(bajti) <= NAJVEC_ODGOVOR else None
    except OSError:
        return None                     # tudi prekinitev ob roku
    finally:
        casovnik.cancel()
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
            konc = ustrezna_slicica(bajti or b"")
            if not konc:
                with self._zaklep:
                    if len(self._neuspelo) > 5000:
                        self._neuspelo.clear()
                    self._neuspelo[k] = time.monotonic() + PREMOR_NEUSPEHA_S
                return None
            try:
                return oznaka, self._shrani(k, konc, bajti)
            except OSError as e:          # poln disk, mapa ni dosegljiva: ikona ostane, klicatelj ne dobi izjeme
                print("[SafeerOS] slicice naprave ni bilo mogoce shraniti:", type(e).__name__, flush=True)
                return None
        # Skupen rok `rok` za klicatelja: pocasna naprava ga ne zadrzi. Prenos, ki do roka ni koncan, tece v ozadju do
        # svojega roka (ROK_S, prekine ga casovnik) in je v predpomnilniku ob naslednjem klicu. Niti so demonske in ne
        # vzamejo novih nalog po roku: zapiranje Safeer OS ne caka nanje (pregled 11, N6).
        vrsta: "queue.Queue" = queue.Queue()
        for par in manjka:
            vrsta.put(par)
        koncane: Dict[str, str] = {}
        zaklep = threading.Lock()

        def delavec() -> None:
            while time.monotonic() < konec:
                try:
                    par = vrsta.get_nowait()
                except queue.Empty:
                    return
                try:
                    r = eno(par)
                except Exception:  # noqa: BLE001 - ena slicica ne podre ostalih
                    r = None
                if r:
                    with zaklep:
                        koncane[r[0]] = r[1]
        niti = [threading.Thread(target=delavec, name="safeer-slicice-naprav", daemon=True)
                for _ in range(min(HKRATI, len(manjka)))]
        for n in niti:
            n.start()
        for n in niti:
            n.join(max(0.0, konec - time.monotonic()))
        with zaklep:
            izid.update(koncane)
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
                    if ime.endswith(".part"):
                        continue          # zapis, ki ravno tece v drugi niti (os.replace bi sicer padel)
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
