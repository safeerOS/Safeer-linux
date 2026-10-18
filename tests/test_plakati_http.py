"""Plakati z naslovom http:// (npr. goli IP brez TLS) prenese Safeer OS sam: CSP strani dovoli samo https/file/data."""
import http.server
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from core import plakati_predpomnilnik as pp

KOREN = Path(__file__).resolve().parent.parent
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")


class _Streznik(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/ok.png":
            vrsta, telo = "image/png", PNG
        elif self.path == "/html":
            vrsta, telo = "text/html", b"<html></html>"
        else:
            vrsta, telo = "image/png", b"x" * (pp.NAJVEC_BAJTOV + 10)
        self.send_response(200)
        self.send_header("Content-Type", vrsta)
        self.send_header("Content-Length", str(len(telo)))
        self.end_headers()
        self.wfile.write(telo)

    def log_message(self, *a):
        pass


class TestPlakati(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="plakati-")
        os.environ["SAFEER_PLAKATI_MAPA"] = self.mapa
        self.s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Streznik)
        threading.Thread(target=self.s.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d" % self.s.server_address[1]

    def tearDown(self):
        self.s.shutdown()
        os.environ.pop("SAFEER_PLAKATI_MAPA", None)
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_lokalni_naslov_je_zavrnjen(self):
        self.assertIsNone(pp.predpomni(self.url + "/ok.png"))

    def test_prenese_slike_in_jih_predpomni(self):
        orig = pp._dovoljen_naslov
        pp._dovoljen_naslov = lambda g: True
        try:
            pot = pp.predpomni(self.url + "/ok.png")
            self.assertTrue(pot and pot.endswith(".png") and Path(pot).read_bytes() == PNG)
            self.s.shutdown()                         # drugi klic gre iz predpomnilnika
            self.assertEqual(pp.predpomni(self.url + "/ok.png"), pot)
        finally:
            pp._dovoljen_naslov = orig

    def test_ni_slika_ali_prevelika(self):
        orig = pp._dovoljen_naslov
        pp._dovoljen_naslov = lambda g: True
        try:
            self.assertIsNone(pp.predpomni(self.url + "/html"))
            self.assertIsNone(pp.predpomni(self.url + "/velika"))
            self.assertIsNone(pp.predpomni("file:///etc/passwd"))
            self.assertIsNone(pp.predpomni("ftp://x/y.png"))
        finally:
            pp._dovoljen_naslov = orig


class TestVezava(unittest.TestCase):
    def test_vmesnik_uporablja_predpomnilnik_za_http(self):
        js = (KOREN / "assets" / "os" / "os.js").read_text(encoding="utf-8")
        self.assertIn('klic("mediaPlakat"', js)
        self.assertIn("nastaviSliko(image, x.slika);", js)
        self.assertNotIn("image.src = x.slika;", js)
        self.assertIn('"mediaPlakat": "_plakat"', (KOREN / "core" / "os_katalog.py").read_text(encoding="utf-8"))
        self.assertIn("plakati_predpomnilnik", (KOREN / "packaging" / "install_os_payload.sh").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
