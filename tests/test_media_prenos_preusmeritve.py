"""D1 (pregled 5. 11. 2026): prenos vira Medijskega centra (MediaCenter._download) preveri vsak skok preusmeritve -
samo http(s), nikoli s https na http in z javnega streznika nikoli v domace omrezje. Zacetni http ostane (seznami IPTV)."""
import http.server
import os
import socket
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
        if self.path in ("/vir.m3u", "/k-cilju.m3u"):
            self.send_response(302)
            gostitelj = "localhost" if self.path == "/vir.m3u" else "cilj.test"
            self.send_header("Location", "http://%s:%d/skrito" % (gostitelj, self.server.server_address[1]))
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
        with mock.patch.object(os_media.media_servers, "je_domace_omrezje", lambda h: h == "localhost"), \
                mock.patch.object(os_media, "_ni_javen", lambda n: False):
            with self.assertRaises(urllib.error.HTTPError):
                self.mc._download("http://127.0.0.1:%d/vir.m3u" % self.streznik.server_address[1])
        self.assertEqual(self.streznik.prebrano, [], "zahteva v domace omrezje ne sme oditi")

    def test_preusmeritev_znotraj_domacega_omrezja_dela(self):
        telo, vrsta, koncni = self.mc._download("http://127.0.0.1:%d/vir.m3u" % self.streznik.server_address[1])
        self.assertTrue(telo.startswith(b"#EXTM3U"))
        self.assertEqual(self.streznik.prebrano, ["/skrito"])

    def _dns(self, slovar):
        """Lazen DNS: ime -> seznam naslovov (vsi hkrati); druga imena gredo v pravi getaddrinfo."""
        izvirni = socket.getaddrinfo

        def getaddrinfo(g, v, *a, **k):
            if g in slovar:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (n, v or 0)) for n in slovar[g]]
            return izvirni(g, v, *a, **k)
        return mock.patch.object(socket, "getaddrinfo", getaddrinfo)

    def test_ime_z_javnim_in_zasebnim_naslovom_zavrnjeno(self):
        # CodeRabbit 5. 11. 2026: prej je veljalo »vsi naslovi zasebni«, zato je ime z enim javnim in enim zasebnim
        # naslovom preslo, povezava pa je ob odpovedi javnega poskusila zasebnega.
        skok = os_media.PreverjenSkok()
        z = urllib.request.Request("https://seznam.example/a")
        with self._dns({"seznam.example": ["93.184.215.14"], "mesan.example": ["93.184.215.15", "192.168.1.10"]}):
            with self.assertRaises(urllib.error.HTTPError):
                skok.redirect_request(z, None, 302, "Found", {}, "https://mesan.example/b")

    def test_povezava_na_preverjen_naslov_brez_ponovnega_razresevanja(self):
        # DNS rebinding: ime se razresi enkrat na skok; ce bi se povezava razresila znova, dobi mrtev 127.0.0.2.
        vrata = self.streznik.server_address[1]
        prazna = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        prazna.bind(("127.0.0.2", vrata))       # zasedi ista vrata na 127.0.0.2, a brez poslusanja (zavrnjeno)
        self.addCleanup(prazna.close)
        dns = {"vir.test": ["127.0.0.1", "127.0.0.2", "127.0.0.2"], "cilj.test": ["127.0.0.1", "127.0.0.2", "127.0.0.2"]}
        izvirni = socket.getaddrinfo
        klici = []

        def getaddrinfo(g, v, *a, **k):
            if g in dns:
                klici.append(g)
                n = dns[g].pop(0) if len(dns[g]) > 1 else dns[g][0]
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (n, v or 0))]
            return izvirni(g, v, *a, **k)
        with mock.patch.object(socket, "getaddrinfo", getaddrinfo):
            telo, vrsta, koncni = self.mc._download("http://vir.test:%d/k-cilju.m3u" % vrata)
        self.assertTrue(telo.startswith(b"#EXTM3U"))
        self.assertEqual(self.streznik.prebrano, ["/skrito"])
        self.assertEqual(klici, ["vir.test", "cilj.test"], "vsako ime skoka se razresi natanko enkrat")

    def test_vsak_skok(self):
        skok = os_media.PreverjenSkok()
        varni = mock.patch.object(os_media, "_naslovi_skoka", lambda g, v: [g] if g[0].isdigit() else ["93.184.215.14"])
        varni.start()
        self.addCleanup(varni.stop)
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
