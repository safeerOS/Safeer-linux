"""Sprotno pretvarjanje na racunalniku (core/link_sprotno.py): video.stream -> /live/<id> (fragmentiran MP4 raste),
ffmpeg bere izvirnik prek krajevnega posrednika (Range gre naprej), ustavitev, prostor, ukaz ffmpeg."""
import http.client
import http.server
import os
import shutil
import ssl
import stat
import sys
import tempfile
import threading
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec, link_datoteke, link_sprotno  # noqa: E402

IZVIRNIK = bytes(range(256)) * 128  # 32768 B "video"


class _Vir(http.server.BaseHTTPRequestHandler):
    """Izvirnik na HTTP z Range (kot streznik datotek naprave); belezi glave zahtev."""
    protocol_version = "HTTP/1.1"
    zahteve = []

    def log_message(self, *_a):
        pass

    def do_GET(self):
        _Vir.zahteve.append((self.path, self.headers.get("Range"), self.headers.get("X-Safeer-Token"),
                             self.headers.get("User-Agent"), self.headers.get("X-Safeer-Test")))
        a, b = 0, len(IZVIRNIK) - 1
        r = self.headers.get("Range")
        if r:
            x, y = r[6:].split("-")
            a = int(x); b = int(y) if y else b
        self.send_response(206 if r else 200)
        self.send_header("Content-Type", "video/x-matroska")
        self.send_header("Content-Length", str(b - a + 1))
        if r:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, len(IZVIRNIK)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.wfile.write(IZVIRNIK[a:b + 1])


LAZNI_FFMPEG = """#!/bin/sh
# Lazni ffmpeg: prebere vhod (zadnji -i) prek HTTP z Range (kot pravi), izhod (zadnji argument) pise po kosih.
vhod=""; izhod=""
while [ $# -gt 0 ]; do
  if [ "$1" = "-i" ]; then shift; vhod="$1"; fi
  izhod="$1"; shift
done
python3 - "$vhod" "$izhod" <<'EOF'
import sys, time, urllib.request
vhod, izhod = sys.argv[1], sys.argv[2]
r = urllib.request.Request(vhod, headers={"Range": "bytes=0-99"})
prvi = urllib.request.urlopen(r, timeout=10).read()
vse = urllib.request.urlopen(vhod, timeout=10).read()
assert prvi == vse[:100]
with open(izhod, "wb") as d:
    for i in range(0, len(vse), 4096):
        d.write(vse[i:i + 4096]); d.flush(); time.sleep(0.05)
EOF
"""


class Sprotno(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapa = tempfile.mkdtemp(prefix="safeer-sprotno-")
        cls.vir = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Vir)
        threading.Thread(target=cls.vir.serve_forever, daemon=True).start()
        cls.d = link_datoteke.Datoteke([], tls_mapa=os.path.join(cls.mapa, "tls"))
        cls.ffmpeg = os.path.join(cls.mapa, "ffmpeg")
        with open(cls.ffmpeg, "w", encoding="utf-8") as f:
            f.write(LAZNI_FFMPEG)
        os.chmod(cls.ffmpeg, os.stat(cls.ffmpeg).st_mode | stat.S_IEXEC)
        cls.s = link_sprotno.Sprotno(mapa=os.path.join(cls.mapa, "pretok"), ffmpeg=cls.ffmpeg, vaapi=lambda: None)

    @classmethod
    def tearDownClass(cls):
        cls.d.ustavi()
        cls.vir.shutdown()
        shutil.rmtree(cls.mapa, ignore_errors=True)

    def _zahteva(self, pot, glave=None, metoda="GET"):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        p = http.client.HTTPSConnection("127.0.0.1", self.d.streznik.vrata, context=ctx, timeout=15)
        p.request(metoda, pot, headers=glave or {})
        o = p.getresponse()
        telo = o.read()
        p.close()
        return o.status, dict((k.lower(), v) for k, v in o.getheaders()), telo

    def test_tok_za_napravo(self):
        url = "http://127.0.0.1:%d/d/share:0:film.mkv" % self.vir.server_address[1]
        o = self.s.zacni({"url": url, "token": "zeton-vira", "name": "Film.mkv", "duration_ms": 60000, "size": 32768,
                          "mime": "video/hevc", "width": 3840, "height": 2160}, "tv-1", self.d.streznik)
        self.assertTrue(o["url"].startswith("https://") and "/live/" in o["url"])
        self.assertEqual(len(o["fp"]), 64)
        pot = "/live/" + o["url"].rsplit("/", 1)[1]
        st, gl, telo = self._zahteva(pot, {"X-Safeer-Token": o["token"]})
        self.assertEqual(st, 200)
        self.assertEqual(gl.get("content-type"), "video/mp4")
        self.assertEqual(telo, IZVIRNIK)   # cel "pretvorjeni" tok, prebran sproti, ko je rasel
        # ffmpeg je izvirnik bral prek posrednika: Range in zeton naprave sta sla naprej, naslov je ostal skrit
        self.assertTrue(any(r[1] == "bytes=0-99" and r[2] == "zeton-vira" for r in _Vir.zahteve), _Vir.zahteve)
        self.assertTrue(all(r[0] == "/d/share:0:film.mkv" for r in _Vir.zahteve))
        st, _, _ = self._zahteva(pot, {"X-Safeer-Token": o["token"]}, "HEAD")
        self.assertEqual(st, 200)
        self.assertEqual(self._zahteva(pot)[0], 401)                                   # brez zetona nic
        self.assertEqual(self._zahteva("/live/ni-takega", {"X-Safeer-Token": o["token"]})[0], 404)
        self.assertTrue(self.s.stanje(o["id"])["done"])
        self.assertTrue(self.s.ustavi_ukaz(o["id"]))
        self.assertFalse(self.s.ustavi_ukaz(o["id"]))
        self.assertEqual(self._zahteva(pot, {"X-Safeer-Token": o["token"]})[0], 404)   # po ustavitvi toka ni vec

    def test_glave_toka_gredo_izvirniku(self):
        """Stremio proxyHeaders: pomocnik poslje glave toka izvirniku (UA toka namesto 'Safeer Control')."""
        _Vir.zahteve.clear()
        url = "http://127.0.0.1:%d/d/share:0:film.mkv" % self.vir.server_address[1]
        o = self.s.zacni({"url": url, "name": "Film.mkv", "duration_ms": 1000, "size": 32768,
                          "headers": {"User-Agent": "SafeerTest/1.0", "X-Safeer-Test": "da", "Range": "bytes=5-9",
                                      "Zlo": "a\r\nb", "": "x"}}, "tv-1", self.d.streznik)
        pot = "/live/" + o["url"].rsplit("/", 1)[1]
        st, _gl, telo = self._zahteva(pot, {"X-Safeer-Token": o["token"]})
        self.assertEqual(st, 200)
        self.assertEqual(telo, IZVIRNIK)
        self.assertTrue(all(r[3] == "SafeerTest/1.0" and r[4] == "da" for r in _Vir.zahteve), _Vir.zahteve)
        self.assertTrue(any(r[1] == "bytes=0-99" for r in _Vir.zahteve))     # Range doloca bralec, ne glave toka
        self.assertEqual(link_sprotno.glave_zahteve({"A": "b", "Host": "x", "C": "d\n"}), {"A": "b"})
        self.s.ustavi_ukaz(o["id"])

    def test_zahteva_in_prostor(self):
        with self.assertRaises(link_sprotno.NapakaPretoka) as e:
            self.s.zacni({"url": "ftp://x/y", "name": "a"}, "tv-1", self.d.streznik)
        self.assertEqual(str(e.exception), "napacna_zahteva")
        with self.assertRaises(link_sprotno.NapakaPretoka) as e:
            self.s.zacni({"url": "https://x/y", "fp": "kratek", "name": "a"}, "tv-1", self.d.streznik)
        self.assertEqual(str(e.exception), "napacna_zahteva")
        brez = link_sprotno.Sprotno(mapa=os.path.join(self.mapa, "p2"), ffmpeg="/ne/obstaja/ffmpeg", vaapi=lambda: None)
        with self.assertRaises(link_sprotno.NapakaPretoka) as e:
            brez.zacni({"url": "https://x/y", "name": "a"}, "tv-1", self.d.streznik)
        self.assertEqual(str(e.exception), "ni_ffmpeg")
        # Prostor: 100 dni videa ne gre v predpomnilnik
        with self.assertRaises(link_sprotno.NapakaPretoka) as e:
            self.s.zacni({"url": "https://x/y", "name": "a", "duration_ms": 100 * 24 * 3600 * 1000}, "tv-1", self.d.streznik)
        self.assertEqual(str(e.exception), "ni_prostora")

    def test_ukaz_ffmpeg(self):
        u = self.s.ukaz("http://127.0.0.1:1/x", "/tmp/o.mp4", 0, 0, 2160, "/dev/dri/renderD128")
        self.assertIn("h264_vaapi", u)
        self.assertIn("scale_vaapi=w=-2:h=1080:format=nv12", u)
        self.assertNotIn("-ss", u)
        u = self.s.ukaz("http://127.0.0.1:1/x", "/tmp/o.mp4", 90500, 5_000_000, 720, None)
        self.assertEqual(u[u.index("-ss") + 1], "90.500")
        self.assertIn("libx264", u)
        self.assertNotIn("scale", " ".join(u))          # 720p ne povecujemo
        self.assertEqual(u[u.index("-b:v") + 1], "5000000")
        self.assertIn("frag_keyframe+empty_moov+default_base_moof", u)
        self.assertEqual(u[-1], "/tmp/o.mp4")
        # Windows: Media Foundation (programsko, v sistemu) in strojni nvenc/amf; brez podatka 5 Mb/s pri 1080p
        u = self.s.ukaz("http://127.0.0.1:1/x", "o.mp4", 0, 0, 2160, None, "h264_mf")
        self.assertIn("h264_mf", u)
        self.assertEqual(u[u.index("-b:v") + 1], "5000000")
        self.assertEqual(u[u.index("-rate_control") + 1], "cbr")
        self.assertNotIn("-hw_encoding", u)
        u = self.s.ukaz("http://127.0.0.1:1/x", "o.mp4", 0, 0, 720, None, "h264_mf")
        self.assertEqual(u[u.index("-b:v") + 1], "3000000")
        u = self.s.ukaz("http://127.0.0.1:1/x", "o.mp4", 0, 4_000_000, 2160, None, "h264_nvenc")
        self.assertIn("h264_nvenc", u)
        self.assertEqual(u[u.index("-b:v") + 1], "4000000")
        self.assertIn("scale=-2:'min(ih,1080)'", u)
        self.assertEqual(self.s.programski_kodirnik(), "h264_mf" if os.name == "nt" else "libx264")

    def test_bitna_hitrost_kot_android(self):
        # 4K HEVC 92 MB / 60 s = 12,3 Mb/s x 1,6 -> omejeno na 8 Mb/s pri 1080p
        self.assertEqual(link_sprotno.bitna_hitrost(92116620, 60000, 3840, 2160), 8_000_000)
        self.assertEqual(link_sprotno.bitna_hitrost(0, 60000, 1920, 1080), 0)
        self.assertEqual(link_sprotno.bitna_hitrost(3_750_000, 60000, 1920, 1080), 2_000_000)   # 0,5 Mb/s x 1,6 < 2 Mb/s

    def test_host_info_in_dejanja(self):
        k = self.s.kodirniki()
        self.assertFalse(k["strojno"])
        self.assertEqual(k["kodirniki"][0]["vrsta"], "avc")
        self.assertIn({"vrsta": "hevc", "sirina": 8192, "visina": 4320}, k["dekodirniki"])
        self.assertEqual(link_daljinec.DEJANJA_PRETOK, ["video.stream", "video.stream_stop", "video.stream_status"])


if __name__ == "__main__":
    unittest.main()
