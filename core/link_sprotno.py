"""Zakon solidarnosti, korak 5 na racunalniku: sprotno pretvarjanje za napravo, ki videa ne zna predvajati.

Naprava (televizor s Full HD dekodirnikom, telefon brez AV1 ...) poslje `video.stream` {url, fp?, token?, name,
mime?, width?, height?, seek_ms?, duration_ms?, size?}. Racunalnik izvirnik bere sproti (pripeto TLS s
potrdilom naprave ali racunalnika, ki video deli), ga s ffmpeg pretvori v H.264/AAC (strojno VAAPI, sicer
x264) v fragmentiran MP4, ki raste v predpomnilniku, in ga streze na `/live/<id>` streznika datotek
(link_datoteke): {id, url, fp, token}. Ko ga nihce ne bere vec ali ko bi zmanjkalo prostora, se ustavi.
`video.stream_stop` {id} ustavi takoj. Isti protokol kot Pretok.kt na Androidu. (link_pretok.py je nekaj drugega:
krajevni posrednik za predvajanje datotek z drugih naprav v lokalnem predvajalniku.)

ffmpeg izvirnika ne bere sam (pripetega potrdila ne zna preveriti): bere ga prek krajevnega posrednika
(127.0.0.1, skrivna pot, `Range` gre naprej), ki edini govori s pripetim virom.
"""
from __future__ import annotations

import http.client
import http.server
import os
import secrets
import shutil
import subprocess
import threading
import time
import urllib.parse
import uuid
from typing import Callable, Dict, List, Optional

MB = 1024 * 1024
VISINA = 1080
BREZ_BRALCA_S = 60.0
NAJVEC_TOKOV = 8
VELIKOST_KOSA = 256 * 1024


class NapakaPretoka(Exception):
    """Kratka koda za napravo (napacna_zahteva, ni_ffmpeg, preobremenjen, ni_prostora, napaka)."""


def mapa_predpomnilnika() -> str:
    return os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "safeer-control", "pretok")


def rezerva(mapa: str) -> int:
    """Prostor, ki ga racunalnik vedno obdrzi zase: 10 % diska, 512 MB-2 GB (kot Pretvorba na Androidu)."""
    try:
        st = os.statvfs(mapa)
        return max(512 * MB, min(2048 * MB, st.f_blocks * st.f_frsize // 10))
    except OSError:
        return 2048 * MB


def prosto(mapa: str) -> int:
    try:
        st = os.statvfs(mapa)
        return st.f_bavail * st.f_frsize
    except OSError:
        return -1


def bitna_hitrost(velikost: int, trajanje_ms: int, sirina: int, visina: int) -> int:
    """Bitna hitrost izhoda (b/s) kot Pretvorba.bitnaHitrost: izvirnik x 1,6, 2-8 Mb/s pri 1080p; 0 = neznano."""
    if velikost <= 0 or trajanje_ms <= 0:
        return 0
    vir = velikost * 8000.0 / trajanje_ms
    izhod_visina = VISINA if visina > VISINA else max(1, visina)
    izhod_sirina = sirina * VISINA / visina if (visina > VISINA and sirina > 0) else max(1.0, float(sirina))
    delez = min(1.0, max(0.1, (izhod_sirina * izhod_visina) / (1920.0 * 1080.0)))
    return int(min(8_000_000.0 * delez, max(2_000_000.0 * delez, vir * 1.6)))


# ----------------------------------------------------------------------------- krajevni posrednik vira

class _Vir:
    """Izvirnik: pripeto HTTPS (odtis + zeton) ali navaden HTTP; vsaka zahteva nova povezava (Range gre naprej)."""

    def __init__(self, url: str, odtis: str, zeton: str) -> None:
        self.url = url
        self.odtis = odtis
        self.zeton = zeton

    def povezava(self) -> http.client.HTTPConnection:
        u = urllib.parse.urlparse(self.url)
        if u.scheme == "https":
            from core import link_tls
            if self.odtis:
                return link_tls._PripetaHttps(u.hostname or "", u.port or 443, self.odtis, 30.0)
            return http.client.HTTPSConnection(u.hostname or "", u.port or 443, timeout=30.0)
        return http.client.HTTPConnection(u.hostname or "127.0.0.1", u.port or 80, timeout=30.0)

    def pot(self) -> str:
        u = urllib.parse.urlparse(self.url)
        return (u.path or "/") + ("?" + u.query if u.query else "")


class _Posrednik(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # noqa: D401
        return

    def do_HEAD(self):  # noqa: N802
        self._naprej(True)

    def do_GET(self):  # noqa: N802
        self._naprej(False)

    def _naprej(self, samo_glava: bool) -> None:
        sprotno: Sprotno = self.server.sprotno  # type: ignore[attr-defined]
        vir = sprotno.vir_za(self.path.split("?")[0].strip("/"))
        if vir is None:
            self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers()
            return
        glave = {}
        if vir.zeton:
            glave["X-Safeer-Token"] = vir.zeton
        if self.headers.get("Range"):
            glave["Range"] = self.headers["Range"]
        glave["User-Agent"] = "Safeer Control"
        p = None
        try:
            p = vir.povezava()
            p.request("HEAD" if samo_glava else "GET", vir.pot(), headers=glave)
            r = p.getresponse()
            self.send_response(r.status)
            for ime in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                if r.getheader(ime):
                    self.send_header(ime, r.getheader(ime))
            self.send_header("Connection", "close")
            self.end_headers()
            if samo_glava:
                return
            while True:
                kos = r.read(VELIKOST_KOSA)
                if not kos:
                    break
                self.wfile.write(kos)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            if p is not None:
                try:
                    p.close()
                except Exception:  # noqa: BLE001
                    pass


class _PosrednikStreznik(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# ----------------------------------------------------------------------------- tok

class Tok:
    def __init__(self, ime: str, datoteka: str) -> None:
        self.id = str(uuid.uuid4())
        self.ime = ime
        self.datoteka = datoteka
        self.skrivnost = secrets.token_urlsafe(18)
        self.proces: Optional[subprocess.Popen] = None
        self.koncano = False
        self.napaka = ""
        self.zadnji_bralec = time.time()
        self.bralcev = 0
        self.zacetek = time.time()
        self.strojno = False
        self.kljucavnica = threading.Lock()

    def json(self) -> dict:
        return {"id": self.id, "name": self.ime, "done": self.koncano, "error": self.napaka,
                "bytes": os.path.getsize(self.datoteka) if os.path.exists(self.datoteka) else 0,
                "readers": self.bralcev, "hw": self.strojno}


class Sprotno:
    """Vsi sprotni tokovi tega racunalnika (en pretvornik naenkrat) in krajevni posrednik za ffmpeg."""

    def __init__(self, mapa: Optional[str] = None, ffmpeg: Optional[str] = None,
                 vaapi: Optional[Callable[[], Optional[str]]] = None) -> None:
        self.mapa = mapa or mapa_predpomnilnika()
        self._ffmpeg = ffmpeg
        self._vaapi = vaapi
        self.tokovi: Dict[str, Tok] = {}
        self._viri: Dict[str, _Vir] = {}
        self._kljucavnica = threading.Lock()
        self._posrednik: Optional[_PosrednikStreznik] = None
        self._straza_tece = False

    # ---- orodja

    def ffmpeg(self) -> str:
        pot = self._ffmpeg or shutil.which("ffmpeg") or ""
        return pot if pot and os.path.isfile(pot) else ""

    def vaapi(self) -> Optional[str]:
        if self._vaapi is not None:
            return self._vaapi()
        try:
            from core import link_zaslon
            return link_zaslon.vaapi_naprava()
        except Exception:  # noqa: BLE001
            return None

    def kodirniki(self) -> dict:
        """Za host.info: {strojno, kodirniki:[{vrsta, sirina, visina}], dekodirniki:[...]} ali {} brez ffmpeg."""
        if not self.ffmpeg():
            return {}
        strojno = bool(self.vaapi())
        return {"strojno": strojno, "ffmpeg": True,
                "kodirniki": [{"vrsta": "avc", "sirina": 4096, "visina": 2304}],
                "dekodirniki": [{"vrsta": v, "sirina": 8192, "visina": 4320}
                                for v in ("avc", "hevc", "vp9", "vp8", "av1", "mpeg4", "mpeg2video", "h263")]}

    # ---- posrednik

    def _zazeni_posrednik(self) -> int:
        with self._kljucavnica:
            if self._posrednik is None:
                s = _PosrednikStreznik(("127.0.0.1", 0), _Posrednik)
                s.sprotno = self  # type: ignore[attr-defined]
                threading.Thread(target=s.serve_forever, name="safeer-pretok-posrednik", daemon=True).start()
                self._posrednik = s
            return self._posrednik.server_address[1]

    def vir_za(self, skrivnost: str) -> Optional[_Vir]:
        with self._kljucavnica:
            for k, v in self._viri.items():
                if secrets.compare_digest(k, skrivnost):
                    return v
        return None

    # ---- ukazi

    def zacni(self, p: dict, posiljatelj: str, streznik) -> dict:
        """`video.stream` -> {id, url, fp, token}; `streznik` je link_datoteke.StreznikDatotek (zazenemo ga, ce ne tece)."""
        url = str(p.get("url") or "")
        odtis = str(p.get("fp") or "")
        zeton = str(p.get("token") or "")
        ime = os.path.basename(str(p.get("name") or "")).strip()[:120] or "video"
        if not (url.startswith("https://") or url.startswith("http://")):
            raise NapakaPretoka("napacna_zahteva")
        if odtis and len(odtis) != 64:
            raise NapakaPretoka("napacna_zahteva")
        if not self.ffmpeg():
            raise NapakaPretoka("ni_ffmpeg")
        trajanje_ms = int(p.get("duration_ms") or 0)
        velikost = int(p.get("size") or 0)
        sirina = int(p.get("width") or 0)
        visina = int(p.get("height") or 0)
        seek_ms = max(0, int(p.get("seek_ms") or 0))
        os.makedirs(self.mapa, exist_ok=True)
        # En tok naenkrat: drugi bi oba zatikala. Tok, ki ga nihce ne bere vec, umaknemo.
        with self._kljucavnica:
            zivi = [t for t in self.tokovi.values() if not t.koncano and not t.napaka]
        for t in zivi:
            if time.time() - t.zadnji_bralec < BREZ_BRALCA_S:
                raise NapakaPretoka("preobremenjen")
            self.ustavi(t)
        # Prostor: ocena izhoda (najvec 8 Mb/s) + rezerva racunalnika.
        ocena = (8_000_000 // 8) * max(0, trajanje_ms - seek_ms) // 1000 * 12 // 10
        pr = prosto(self.mapa)
        if 0 <= pr < ocena + rezerva(self.mapa):
            raise NapakaPretoka("ni_prostora")
        for f in os.listdir(self.mapa):
            pot = os.path.join(self.mapa, f)
            if all(t.datoteka != pot for t in self.tokovi.values()):
                try:
                    os.remove(pot)
                except OSError:
                    pass
        t = Tok(ime, os.path.join(self.mapa, uuid.uuid4().hex + ".mp4"))
        vrata = self._zazeni_posrednik()
        with self._kljucavnica:
            self._viri[t.skrivnost] = _Vir(url, odtis, zeton)
            self.tokovi[t.id] = t
            while len(self.tokovi) > NAJVEC_TOKOV:
                star = next(iter(self.tokovi))
                self.ustavi(self.tokovi.pop(star))
        streznik.sprotno = self   # streznik datotek streze /live/<id> iz tega Sprotno (v testih svoj primerek)
        streznik.zazeni()
        from core.link_datoteke import krajevni_naslov
        osnova = streznik.osnova(krajevni_naslov())
        bitna = bitna_hitrost(velikost, trajanje_ms, sirina, visina)
        threading.Thread(target=self._pretvarjaj, args=(t, f"http://127.0.0.1:{vrata}/{t.skrivnost}", seek_ms, bitna, visina,
                                                         max(0, trajanje_ms - seek_ms)),
                         name="safeer-pretok", daemon=True).start()
        self._zazeni_strazo()
        return {"id": t.id, "url": f"{osnova}/live/{t.id}", "fp": streznik.odtis, "token": streznik.zeton_za(posiljatelj or "naprava")}

    def ustavi_ukaz(self, id_toka: str) -> bool:
        with self._kljucavnica:
            t = self.tokovi.pop(str(id_toka or ""), None)
        if t is None:
            return False
        self.ustavi(t)
        return True

    def stanje(self, id_toka: str) -> Optional[dict]:
        t = self.tokovi.get(str(id_toka or ""))
        return t.json() if t else None

    def ustavi(self, t: Tok) -> None:
        t.koncano = True
        pr = t.proces
        if pr is not None and pr.poll() is None:
            try:
                pr.terminate()
                try:
                    pr.wait(3)
                except subprocess.TimeoutExpired:
                    pr.kill()
            except OSError:
                pass
        with self._kljucavnica:
            self._viri.pop(t.skrivnost, None)
        if t.bralcev == 0:
            try:
                os.remove(t.datoteka)
            except OSError:
                pass

    # ---- ffmpeg

    def ukaz(self, vhod: str, izhod: str, seek_ms: int, bitna: int, visina_vira: int, vaapi: Optional[str]) -> List[str]:
        """Ukaz ffmpeg: strojno (VAAPI dekodiranje + kodiranje, CQP - edini nacin na Intelovem LP vhodu) ali x264.
        Najvec 1080p, manjsega ne povecujemo; fragmentiran MP4 (2 s), da ga naprava bere sproti."""
        u = [self.ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
        if seek_ms > 0:
            u += ["-ss", f"{seek_ms / 1000:.3f}"]
        lestvica = visina_vira <= 0 or visina_vira > VISINA
        if vaapi:
            u += ["-hwaccel", "vaapi", "-hwaccel_device", vaapi, "-hwaccel_output_format", "vaapi", "-i", vhod]
            u += ["-vf", (f"scale_vaapi=w=-2:h={VISINA}:format=nv12" if lestvica else "scale_vaapi=format=nv12")]
            u += ["-c:v", "h264_vaapi", "-rc_mode", "CQP", "-qp", "23", "-profile:v", "high"]
        else:
            u += ["-i", vhod]
            if lestvica:
                u += ["-vf", f"scale=-2:'min(ih,{VISINA})'"]
            u += ["-c:v", "libx264", "-preset", "veryfast", "-profile:v", "high", "-pix_fmt", "yuv420p"]
            if bitna > 0:
                u += ["-b:v", str(bitna), "-maxrate", str(int(bitna * 1.5)), "-bufsize", str(bitna * 2)]
            else:
                u += ["-crf", "22"]
        u += ["-c:a", "aac", "-b:a", "160k", "-ac", "2", "-sn", "-dn", "-map", "0:v:0", "-map", "0:a:0?",
              "-f", "mp4", "-movflags", "frag_keyframe+empty_moov+default_base_moof", "-frag_duration", "2000000", izhod]
        return u

    def _cel(self, datoteka: str, velikost: int, pricakovano_ms: int) -> bool:
        if velikost <= MB:
            return False
        if pricakovano_ms <= 0:
            return True
        ffprobe = shutil.which("ffprobe") or os.path.join(os.path.dirname(self.ffmpeg()), "ffprobe")
        try:
            izpis = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", datoteka],
                                   capture_output=True, text=True, timeout=15).stdout.strip()
            return float(izpis) * 1000 >= pricakovano_ms * 0.95
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return False

    def _pretvarjaj(self, t: Tok, vhod: str, seek_ms: int, bitna: int, visina_vira: int, pricakovano_ms: int = 0) -> None:
        vaapi = self.vaapi()
        for poskus, naprava in enumerate([vaapi, None] if vaapi else [None]):
            if t.koncano:
                return
            t.strojno = naprava is not None
            try:
                t.proces = subprocess.Popen(self.ukaz(vhod, t.datoteka, seek_ms, bitna, visina_vira, naprava),
                                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            except OSError as e:
                t.napaka = "napaka"; t.koncano = True
                _zapisi(f"pretok {t.ime}: ffmpeg se ni zagnal ({e})")
                return
            _, err = t.proces.communicate()
            koda = t.proces.returncode
            velikost = os.path.getsize(t.datoteka) if os.path.exists(t.datoteka) else 0
            if t.koncano:
                return
            # VAAPI ob koncu vira javi "Cannot allocate memory" (koda 244), ceprav je izhod cel: izhod stejemo za
            # uspeh, ce je dolg vsaj 95 % pricakovanega (ffprobe) ali - brez podatka o trajanju - vecji od 1 MB.
            if koda == 0 or self._cel(t.datoteka, velikost, pricakovano_ms):
                _zapisi(f"pretok {t.ime}: koncan ({velikost} B, {'VAAPI' if naprava else 'x264'}, koda {koda})")
                t.koncano = True
                return
            _zapisi(f"pretok {t.ime}: {'VAAPI' if naprava else 'x264'} ni uspel (koda {koda}): {(err or b'').decode('utf-8', 'replace').strip()[:300]}")
            try:
                os.remove(t.datoteka)
            except OSError:
                pass
        t.napaka = "napaka"
        t.koncano = True

    # ---- strezba /live/<id> (klice link_datoteke)

    def postrezi(self, obravnava, id_toka: str, samo_glava: bool) -> None:
        t = self.tokovi.get(str(id_toka or ""))
        if t is None:
            telo = b"ni takega toka"
            obravnava.send_response(404); obravnava.send_header("Content-Type", "text/plain")
            obravnava.send_header("Content-Length", str(len(telo))); obravnava.end_headers(); obravnava.wfile.write(telo)
            return
        obravnava.send_response(200)
        obravnava.send_header("Content-Type", "video/mp4")
        obravnava.send_header("Transfer-Encoding", "chunked")
        obravnava.send_header("Cache-Control", "no-store")
        obravnava.send_header("Connection", "close")
        obravnava.end_headers()
        if samo_glava:
            return
        with t.kljucavnica:
            t.bralcev += 1
        poslano = 0
        cakam = 0
        try:
            while True:
                t.zadnji_bralec = time.time()
                dolzina = os.path.getsize(t.datoteka) if os.path.exists(t.datoteka) else 0
                if dolzina > poslano:
                    with open(t.datoteka, "rb") as d:
                        d.seek(poslano)
                        while poslano < dolzina:
                            kos = d.read(min(VELIKOST_KOSA, dolzina - poslano))
                            if not kos:
                                break
                            obravnava.wfile.write(b"%x\r\n" % len(kos) + kos + b"\r\n")
                            poslano += len(kos)
                    obravnava.wfile.flush()
                    cakam = 0
                    continue
                if t.koncano:
                    break
                cakam += 1
                if cakam > 600:   # 60 s brez novih podatkov: pretvornik je obstal
                    break
                time.sleep(0.1)
            obravnava.wfile.write(b"0\r\n\r\n")
            obravnava.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with t.kljucavnica:
                t.bralcev -= 1
            t.zadnji_bralec = time.time()
            if t.koncano and t.bralcev == 0 and t.napaka:
                try:
                    os.remove(t.datoteka)
                except OSError:
                    pass

    # ---- straza

    def _zazeni_strazo(self) -> None:
        with self._kljucavnica:
            if self._straza_tece:
                return
            self._straza_tece = True
        threading.Thread(target=self._straza, name="safeer-pretok-straza", daemon=True).start()

    def _straza(self) -> None:
        while True:
            time.sleep(5)
            with self._kljucavnica:
                tokovi = list(self.tokovi.values())
            if not any(not t.koncano for t in tokovi):
                with self._kljucavnica:
                    self._straza_tece = False
                return
            for t in tokovi:
                if t.koncano:
                    continue
                if t.bralcev == 0 and time.time() - t.zadnji_bralec > BREZ_BRALCA_S:
                    _zapisi(f"pretok {t.ime}: nihce ga ne bere, ustavljam")
                    self.ustavi(t)
                elif 0 <= prosto(self.mapa) < rezerva(self.mapa):
                    _zapisi(f"pretok {t.ime}: zmanjkalo prostora, ustavljam")
                    t.napaka = "ni_prostora"
                    self.ustavi(t)


def _zapisi(besedilo: str) -> None:
    try:
        from core import os_stabilnost
        os_stabilnost.zapisi("safeer-control", besedilo)
    except Exception:  # noqa: BLE001
        pass


_SPROTNO: Optional[Sprotno] = None
_SPROTNO_KLJUC = threading.Lock()


def sprotno() -> Sprotno:
    """En Sprotno na proces (Control)."""
    global _SPROTNO
    with _SPROTNO_KLJUC:
        if _SPROTNO is None:
            _SPROTNO = Sprotno()
        return _SPROTNO
