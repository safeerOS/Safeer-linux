"""D1 (pregled 5. 11. 2026): prenos vira Medijskega centra (MediaCenter._download) preveri vsak skok preusmeritve -
samo http(s), nikoli s https na http in z javnega streznika nikoli v domace omrezje. Zacetni http ostane (seznami IPTV)."""
import http.server
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_media  # noqa: E402


class _Streznik(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/vir.m3u":
            self.send_response(302)
            self.send_header("Location", "http://localhost:%d/skrito" % self.server.server_address[1])
            self.end_headers()
            return
        telo = b"#EXTM3U\n#EXTINF:-1,Kanal\nhttp://localhost/tok.ts\n"
        self.server.prebrano.append(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "audio/x-mpegurl")
        self.send_header("Content-Length", str(len(telo)))
        self.end_headers()
        self.wfile.write(telo)

    def log_message(self, *_a):
        pass


class Prenos(unittest.TestCase):
    def setUp(self):
        self.streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Streznik)
        self.streznik.prebrano = []
        self.nit = threading.Thread(target=self.streznik.serve_forever, daemon=True)
        self.nit.start()
        self.addCleanup(self._ustavi)
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.mc = os_media.MediaCenter(self.mapa.name, roots=[])

    def _ustavi(self):
        self.streznik.shutdown()
        self.streznik.server_close()
        self.nit.join(5)

    def test_javni_vir_ne_preusmeri_v_domace_omrezje(self):
        # 127.0.0.1 tu velja za javni streznik, localhost za domace omrezje.
        with mock.patch.object(os_media.media_servers, "je_domace_omrezje", lambda h: h == "localhost"):
            with self.assertRaises(urllib.error.HTTPError):
                self.mc._download("http://127.0.0.1:%d/vir.m3u" % self.streznik.server_address[1])
        self.assertEqual(self.streznik.prebrano, [], "zahteva v domace omrezje ne sme oditi")

    def test_preusmeritev_znotraj_domacega_omrezja_dela(self):
        telo, vrsta, koncni = self.mc._download("http://127.0.0.1:%d/vir.m3u" % self.streznik.server_address[1])
        self.assertTrue(telo.startswith(b"#EXTM3U"))
        self.assertEqual(self.streznik.prebrano, ["/skrito"])

    def test_vsak_skok(self):
        skok = os_media.PreverjenSkok()
        z = urllib.request.Request("https://seznam.example/a")
        for nov in ("http://seznam.example/b", "ftp://seznam.example/b", "file:///etc/passwd", "http://192.168.1.1/",
                    "https://127.0.0.1:8080/x"):
            with self.subTest(nov=nov), self.assertRaises(urllib.error.HTTPError):
                skok.redirect_request(z, None, 302, "Found", {}, nov)
        self.assertEqual(skok.redirect_request(z, None, 302, "Found", {}, "https://cdn.example/b").full_url,
                         "https://cdn.example/b")
        http_vir = urllib.request.Request("http://iptv.example/get.php")
        self.assertEqual(skok.redirect_request(http_vir, None, 302, "Found", {}, "http://cdn.example/b").full_url,
                         "http://cdn.example/b")


if __name__ == "__main__":
    unittest.main()
