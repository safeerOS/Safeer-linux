"""magnet.stream: racunalnik prenasa torrent, televizor dobi samo tok (core/link_datoteke.py, link_daljinec.py)."""
import http.client
import http.server
import os
import shutil
import ssl
import sys
import tempfile
import threading
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec, link_datoteke, os_torrent  # noqa: E402

VSEBINA = bytes(range(256)) * 64  # 16384 B
MAGNET = "magnet:?xt=urn:btih:" + "a" * 40 + "&dn=Film"


class _Lokalni(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_a):
        pass

    def do_HEAD(self):
        self._p(True)

    def do_GET(self):
        self._p(False)

    def _p(self, glava):
        a, b = 0, len(VSEBINA) - 1
        r = self.headers.get("Range")
        if r:
            x, y = r[6:].split("-")
            a = int(x)
            b = int(y) if y else b
        self.send_response(206 if r else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(b - a + 1))
        if r:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, len(VSEBINA)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        if not glava:
            self.wfile.write(VSEBINA[a:b + 1])


class _Torrenti:
    """Namesto rqbit: datoteke magneta in lokalni tok."""

    def __init__(self, vrata):
        self.vrata = vrata
        self.dodane = []

    def zazeni(self):
        pass

    def preberi(self, uri):
        return {"hash": "a" * 40, "ime": "Film", "uri": uri, "datoteke": [
            {"i": 0, "ime": "Film/vzorec.mp4", "velikost": 100, "vrsta": "video", "predvajljivo": True},
            {"i": 1, "ime": "Film/film.mkv", "velikost": 9000, "vrsta": "video", "predvajljivo": True},
            {"i": 2, "ime": "Film/namesti.exe", "velikost": 99999, "vrsta": "nevarno", "predvajljivo": False}]}

    def dodaj(self, uri, izbrane):
        self.dodane.append(list(izbrane))
        return 7

    def tok(self, tid, i):
        return "http://127.0.0.1:%d/t/skrito/film.mkv" % self.vrata

    def tece(self):
        return True

    def seznam(self):
        return [{"id": 7, "ime": "Film", "skupaj": 9100, "preneseno": 4550, "koncano": False, "hitrost_mibs": 1.5,
                 "datoteke": [{"i": 1, "ime": "Film/film.mkv", "vrsta": "video", "vkljucena": True},
                              {"i": 0, "ime": "Film/vzorec.mp4", "vrsta": "video", "vkljucena": False}]}]

    def magnet(self, tid):
        return MAGNET

    def odstrani(self, tid, z_datotekami=False):
        self.odstranjen = (tid, z_datotekami)
        return tid == 7


class TokTorrenta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapa = tempfile.mkdtemp(prefix="safeer-tok-")
        cls.lokalni = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Lokalni)
        threading.Thread(target=cls.lokalni.serve_forever, daemon=True).start()
        cls.d = link_datoteke.Datoteke([], tls_mapa=os.path.join(cls.mapa, "tls"))

    @classmethod
    def tearDownClass(cls):
        cls.d.ustavi()
        cls.lokalni.shutdown()
        shutil.rmtree(cls.mapa, ignore_errors=True)

    def _zahteva(self, pot, glave=None, metoda="GET"):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        p = http.client.HTTPSConnection("127.0.0.1", self.d.streznik.vrata, context=ctx, timeout=5)
        p.request(metoda, pot, headers=glave or {})
        o = p.getresponse()
        telo = o.read()
        p.close()
        return o.status, dict((k.lower(), v) for k, v in o.getheaders()), telo

    def test_tok_prek_racunalnika(self):
        t = _Torrenti(self.lokalni.server_address[1])
        o = self.d.tok_torrenta(MAGNET, "tv-1", torrenti=t, zmogljivost=lambda m, v: "")
        self.assertEqual(t.dodane, [[1]])  # najvecji video, ne vzorec in nikoli program
        self.assertEqual((o["file"], o["name"]), (1, "film.mkv"))
        self.assertTrue(o["path"].startswith("/m/") and o["path"].endswith("/film.mkv"))
        self.assertTrue(o["server"]["base_url"].startswith("https://"))
        z = {"X-Safeer-Token": o["server"]["token"]}
        st, gl, telo = self._zahteva(o["path"], z)
        self.assertEqual((st, telo), (200, VSEBINA))
        st, gl, telo = self._zahteva(o["path"], {**z, "Range": "bytes=100-199"})
        self.assertEqual((st, telo, gl["content-range"]), (206, VSEBINA[100:200], "bytes 100-199/16384"))
        st, gl, telo = self._zahteva(o["path"], z, "HEAD")
        self.assertEqual((st, gl["content-length"], telo), (200, "16384", b""))
        # brez zetona, z napacnim ali z izmisljeno skrivnostjo nic
        self.assertEqual(self._zahteva(o["path"])[0], 401)
        self.assertEqual(self._zahteva(o["path"], {"X-Safeer-Token": "x"})[0], 401)
        self.assertEqual(self._zahteva("/m/izmisljeno/film.mkv", z)[0], 404)
        # izbrana datoteka; program ne
        self.assertEqual(self.d.tok_torrenta(MAGNET, "tv-1", datoteka=0, torrenti=t, zmogljivost=lambda m, v: "")["file"], 0)
        with self.assertRaises(os_torrent.NapakaTorrenta):
            self.d.tok_torrenta(MAGNET, "tv-1", datoteka=2, torrenti=t, zmogljivost=lambda m, v: "")
        with self.assertRaises(os_torrent.NapakaTorrenta):
            self.d.tok_torrenta("https://primer.si/x", "tv-1", torrenti=t)

    def test_prenosi_in_odstranitev(self):
        t = _Torrenti(self.lokalni.server_address[1])
        o = self.d.tok_torrenta(MAGNET, "tv-1", torrenti=t, zmogljivost=lambda m, v: "")
        self.assertEqual(self.d.prenosi_za_naprave(t)["items"], [{"id": 7, "name": "Film", "size": 9100, "done": 4550,
                         "finished": False, "speed_mibs": 1.5, "magnet": MAGNET, "file": 1}])
        self.assertTrue(self.d.odstrani_prenos(7, t))
        self.assertEqual(t.odstranjen, (7, True))  # z datotekami: na racunalniku ne ostane nic
        z = {"X-Safeer-Token": o["server"]["token"]}
        self.assertEqual(self._zahteva(o["path"], z)[0], 404)  # odstranjen tok ni vec dosegljiv
        self.assertFalse(self.d.odstrani_prenos(8, t))

    def test_ne_preobremeni_racunalnika(self):
        t = _Torrenti(self.lokalni.server_address[1])
        for razlog in ("preobremenjen", "malo_pomnilnika", "ni_prostora"):
            with self.assertRaises(os_torrent.NapakaTorrenta) as e:
                self.d.tok_torrenta(MAGNET, "tv-1", torrenti=t, zmogljivost=lambda m, v, r=razlog: r)
            self.assertEqual(str(e.exception), razlog)
        self.assertEqual(t.dodane, [])  # nic ni zacelo prenasati
        vprasano = []
        self.d.tok_torrenta(MAGNET, "tv-1", torrenti=t, zmogljivost=lambda m, v: vprasano.append(v) or "")
        self.assertEqual(vprasano, [9000])  # disk se preveri za velikost izbrane datoteke
        self.assertEqual(link_datoteke.prosta_zmogljivost(self.mapa, 10 ** 18), "ni_prostora")

    def test_samo_lokalni_tokovi(self):
        with self.assertRaises(ValueError):
            self.d.streznik.dodaj_tok("http://10.0.0.5:8000/x.mp4")
        with self.assertRaises(ValueError):
            self.d.streznik.dodaj_tok("file:///etc/passwd")

    def test_ukaz_in_stanje(self):
        izidi = []
        link_daljinec.izvedi_control("status", {}, lambda u: None, izidi.append, datoteke=self.d)
        self.assertIn("magnet.stream", izidi[-1]["data"]["actions"])
        link_daljinec.izvedi_control("status", {}, lambda u: None, izidi.append)
        self.assertNotIn("magnet.stream", izidi[-1]["data"]["actions"])
        link_daljinec.izvedi_control("magnet.stream", {"uri": "ni magnet"}, lambda u: None, izidi.append, datoteke=self.d)
        for _ in range(50):
            if izidi[-1].get("code") == "ni_magnet":
                break
            time.sleep(0.05)
        self.assertEqual((izidi[-1]["ok"], izidi[-1]["code"]), (False, "ni_magnet"))
        link_daljinec.izvedi_control("magnet.remove", {"id": "x"}, lambda u: None, izidi.append, datoteke=self.d)
        self.assertEqual(izidi[-1]["code"], "ni_prenosa")
        link_daljinec.izvedi_control("status", {}, lambda u: None, izidi.append, datoteke=self.d)
        self.assertTrue({"magnet.list", "magnet.remove"} <= set(izidi[-1]["data"]["actions"]))


if __name__ == "__main__":
    unittest.main()
