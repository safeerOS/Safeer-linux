"""Lokalni streznik HTTP Range za predvajalnik (mpv) - lasten pogon Usenet, korak 2 (lastnik 26. 10. 2026).

Namizje predvaja film z Useneta prek http://127.0.0.1:<nakljucna vrata>/<nakljucen zeton>/video.<koncnica>:
- SAMO 127.0.0.1 (nikoli 0.0.0.0 ali naslov v LAN); vrata izbere sistem.
- Pot nosi samo nakljucen zeton (secrets.token_urlsafe, 32 bajtov) - nikoli kljuc indeksatorja, geslo ponudnika ali
  message-id. Dodatek Usenet Ultimate je dal povezavo NZB s kljucem v naslov toka (prototip 25. 10. 2026) - ta pride v
  predvajalnik in njegove dnevnike; tega ne ponovimo. Zeton se primerja s hmac.compare_digest.
- Brez dnevnika zahtev (BaseHTTPRequestHandler bi pot z zetonom izpisal na stderr). Glava Host mora biti 127.0.0.1 ali
  localhost z nasimi vrati (stran v brskalniku s preusmeritvijo DNS ne doseze toka, tudi ce bi zeton uganila).
- SO_REUSEADDR izklopljen: na Windows bi drug proces lahko prevzel ista vrata.
- 206 z Content-Range, 200 brez (ali z neveljavnim/vecdelnim) Range, HEAD, 416 izven obsega (Content-Range bytes */N).
- Zapre se ob koncu predvajanja (zapri) ali sam po [nedejavnost_s] brez zahtev in brez odprte povezave; takrat
  zapre tudi bralnik (branje vnaprej se ustavi - ni prometa po koncu ogleda).
"""

from __future__ import annotations

import hmac
import logging
import re
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional, Tuple, Union

from .usenet_tok import NapakaToka

_log = logging.getLogger("safeer.usenet")

GOSTITELJ = "127.0.0.1"
KOS = 256 * 1024
NEDEJAVNOST_S = 300.0
_VRSTE = {".mkv": "video/x-matroska", ".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm",
          ".avi": "video/x-msvideo", ".ts": "video/mp2t", ".m2ts": "video/mp2t", ".mov": "video/quicktime",
          ".wmv": "video/x-ms-wmv", ".mpg": "video/mpeg", ".mpeg": "video/mpeg"}
_RANGE = re.compile(r"\Abytes=(\d{0,19})-(\d{0,19})\Z")
NI_OBSEGA = "416"


def obseg(glava: Optional[str], velikost: int) -> Union[None, str, Tuple[int, int]]:
    """Glava Range -> (zacetek, konec vkljucno), None (cela datoteka: brez, neveljavna ali vecdelna glava - RFC 9110
    14.2 jo sme prezreti) ali NI_OBSEGA (416)."""
    if not glava:
        return None
    m = _RANGE.match(glava.strip().replace(" ", ""))
    if not m:
        return None
    a, b = m.group(1), m.group(2)
    if not a and not b:
        return None
    if not a:  # zadnjih n bajtov
        n = int(b)
        if n == 0 or velikost == 0:
            return NI_OBSEGA
        return max(0, velikost - n), velikost - 1
    zacetek = int(a)
    konec = int(b) if b else velikost - 1
    if b and konec < zacetek:
        return None
    if zacetek >= velikost:
        return NI_OBSEGA
    return zacetek, min(konec, velikost - 1)


def ime_poti(ime: Optional[str]) -> str:
    """'video' + znana koncnica videa (predvajalnik prepozna obliko); nic drugega iz imena izdaje ne gre v naslov."""
    k = ("." + ime.rsplit(".", 1)[1].lower()) if ime and "." in ime else ""
    return "video" + (k if k in _VRSTE else ".bin")


class _Strezba(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    allow_reuse_port = False


class Streznik:
    """En film na 127.0.0.1. [bralnik] ima beri(odmik, n), zapri() in vir.velikost (usenet_bralnik.Bralnik)."""

    def __init__(self, bralnik, ime: Optional[str] = None, gostitelj: str = GOSTITELJ,
                 nedejavnost_s: float = NEDEJAVNOST_S, ob_koncu: Optional[Callable[[], None]] = None):
        if gostitelj != GOSTITELJ:
            raise ValueError("usenet streznik: samo 127.0.0.1")
        self.bralnik = bralnik
        self.velikost = int(bralnik.vir.velikost)
        self.zeton = secrets.token_urlsafe(32)
        self.pot = ime_poti(ime if ime is not None else getattr(bralnik.vir, "ime", None))
        self._vrsta = _VRSTE.get("." + self.pot.rsplit(".", 1)[1], "application/octet-stream")
        self._nedejavnost_s = float(nedejavnost_s)
        self._ob_koncu = ob_koncu
        self._zaklep = threading.Lock()
        self._odprtih = 0
        self._zadnja = time.monotonic()
        self._zaprt = False
        self._srv = _Strezba((GOSTITELJ, 0), self._razred())
        self.vrata = self._srv.server_address[1]
        self.url = "http://%s:%d/%s/%s" % (GOSTITELJ, self.vrata, self.zeton, self.pot)
        self._nit = threading.Thread(target=self._srv.serve_forever, kwargs={"poll_interval": 0.2},
                                     name="safeer-usenet-http", daemon=True)
        self._nit.start()
        self._varuh = threading.Thread(target=self._pazi, name="safeer-usenet-http-varuh", daemon=True)
        self._varuh.start()

    def __repr__(self) -> str:
        return "Streznik(127.0.0.1:%d, %s)" % (self.vrata, "zaprt" if self._zaprt else "odprt")  # brez zetona

    def __enter__(self) -> "Streznik":
        return self

    def __exit__(self, *_a) -> None:
        self.zapri()

    @property
    def zaprt(self) -> bool:
        return self._zaprt

    def _pazi(self) -> None:
        while not self._zaprt:
            time.sleep(min(1.0, max(0.05, self._nedejavnost_s / 4)))
            with self._zaklep:
                miruje = self._odprtih == 0 and time.monotonic() - self._zadnja > self._nedejavnost_s
            if miruje:
                _log.info("usenet streznik: zaprt po nedejavnosti")
                self.zapri()

    def zapri(self) -> None:
        """Konec predvajanja: streznik in bralnik zaprta (vrata prosta, branje vnaprej ustavljeno)."""
        with self._zaklep:
            if self._zaprt:
                return
            self._zaprt = True
        threading.Thread(target=self._srv.shutdown, daemon=True).start()  # shutdown caka na serve_forever
        try:
            self._srv.socket.close()
        except OSError:
            pass
        self.bralnik.zapri()
        if self._ob_koncu is not None:
            try:
                self._ob_koncu()
            except Exception:  # noqa: BLE001 - klic klicatelja ne sme podreti zapiranja
                _log.exception("usenet streznik: ob_koncu")

    # -------------------------------------------------------------- zahteve
    def _razred(self):
        streznik = self

        class Obdelava(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "Safeer"
            sys_version = ""

            def log_message(self, *_a) -> None:  # pot nosi zeton: nikoli v dnevnik
                pass

            def setup(self) -> None:
                super().setup()
                with streznik._zaklep:
                    streznik._odprtih += 1
                    streznik._zadnja = time.monotonic()

            def finish(self) -> None:
                try:
                    super().finish()
                finally:
                    with streznik._zaklep:
                        streznik._odprtih -= 1
                        streznik._zadnja = time.monotonic()

            def _prazno(self, koda: int, glave: Tuple = ()) -> None:
                self.send_response(koda)
                for k, v in glave:
                    self.send_header(k, v)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _dovoljeno(self) -> bool:
                pot = self.path.split("?", 1)[0]
                deli = pot.split("/")
                pravi = len(deli) == 3 and deli[0] == "" and hmac.compare_digest(
                    deli[1].encode("ascii", "replace"), streznik.zeton.encode("ascii")) and deli[2] == streznik.pot
                gost = (self.headers.get("Host") or "").strip().lower()
                return pravi and gost in ("127.0.0.1:%d" % streznik.vrata, "localhost:%d" % streznik.vrata)

            def _odgovori(self, telo: bool) -> None:
                with streznik._zaklep:
                    streznik._zadnja = time.monotonic()
                if streznik._zaprt or not self._dovoljeno():
                    self._prazno(404)
                    return
                n = streznik.velikost
                o = obseg(self.headers.get("Range"), n)
                if o == NI_OBSEGA:
                    self._prazno(416, (("Content-Range", "bytes */%d" % n), ("Accept-Ranges", "bytes")))
                    return
                zacetek, konec = (0, n - 1) if o is None else o
                self.send_response(200 if o is None else 206)
                self.send_header("Content-Type", streznik._vrsta)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-store")
                if o is not None:
                    self.send_header("Content-Range", "bytes %d-%d/%d" % (zacetek, konec, n))
                self.send_header("Content-Length", str(max(0, konec - zacetek + 1)))
                self.end_headers()
                if not telo:
                    return
                poz = zacetek
                try:
                    while poz <= konec:
                        kos = streznik.bralnik.beri(poz, min(KOS, konec - poz + 1))
                        if not kos:
                            break
                        self.wfile.write(kos)
                        poz += len(kos)
                        with streznik._zaklep:
                            streznik._zadnja = time.monotonic()
                except NapakaToka as e:
                    _log.info("usenet streznik: branje prekinjeno (%s)", e.izid)
                except (ConnectionError, socket.timeout, OSError):
                    pass  # predvajalnik je zaprl povezavo (skok, konec)
                if poz <= konec:
                    self.close_connection = True  # obljubljene dolzine ni bilo: predvajalnik naj odpre znova

            def do_GET(self) -> None:  # noqa: N802
                self._odgovori(True)

            def do_HEAD(self) -> None:  # noqa: N802
                self._odgovori(False)

            def _ni_dovoljeno(self) -> None:
                self._prazno(405, (("Allow", "GET, HEAD"),))

            do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _ni_dovoljeno  # noqa: N815

        return Obdelava
