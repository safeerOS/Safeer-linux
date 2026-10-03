"""Izbira toka (core/tok_izbira.py): rok veljavnosti povezave in "prvi tok mora res odgovoriti" (core/os_media.py,
core/media_servers.tok_odgovarja). Ista pravila kot TokIzbira.kt na Androidu (tests/TokIzbiraTest.kt)."""
import http.server
import os
import shutil
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import media_servers, os_media, tok_izbira  # noqa: E402

ZDAJ = 1_791_054_000                                     # 3. 10. 2026 19:00:00 UTC
PODPISANA = ("https://racun.shramba.example/mapa/film.mkv?X-Amz-Algorithm=AWS4-HMAC-SHA256"
             "&X-Amz-Credential=k%2F20261003%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20261003T161807Z"
             "&X-Amz-Expires=10800&X-Amz-Signature=abc&X-Amz-SignedHeaders=host")
TRAJNA = "https://datoteke.example/api/file/AbCd1234?download"
TV4K = tok_izbira.Zmoznosti(visina=2160)


class TestRokPovezave(unittest.TestCase):
    def test_podpisana_povezava(self):
        # Podpisana ob 16:18:07 za 3 ure: ob 19:00:00 velja se 18 min 7 s.
        self.assertEqual(tok_izbira.velja_se(PODPISANA, ZDAJ), 1087)
        self.assertFalse(tok_izbira.potekla(PODPISANA, ZDAJ))
        self.assertTrue(tok_izbira.potekla(PODPISANA, ZDAJ + 1030))
        self.assertTrue(tok_izbira.potekla(PODPISANA, ZDAJ + 1087))

    def test_drugi_zapisi(self):
        v = tok_izbira.velja_se
        self.assertEqual(v("https://storage.example/f.mp4?X-Goog-Date=20261003T180000Z&X-Goog-Expires=7200&X-Goog-Signature=x", ZDAJ), 3600)
        self.assertEqual(v("https://cdn.example/f.mkv?Expires=%d&Signature=x&Key-Pair-Id=y" % (ZDAJ + 500), ZDAJ), 500)
        self.assertEqual(v("https://cdn.example/f.mkv?token=abc&expires=%d" % (ZDAJ - 30), ZDAJ), -30)
        self.assertEqual(v("https://cdn.example/f.m3u8?hdnts=exp=%d~acl=/*~hmac=ff" % (ZDAJ + 60), ZDAJ), 60)
        self.assertEqual(v("https://cdn.example/f.m3u8?hdnts=st=1~exp=%d~hmac=ff" % (ZDAJ + 90), ZDAJ), 90)
        self.assertEqual(v("https://racun.blob.example/f.mkv?sv=2022&se=2026-10-03T20%3A00%3A00Z&sr=b&sig=x", ZDAJ), 3600)
        self.assertEqual(v("https://racun.blob.example/f.mkv?se=2026-10-03T19:30Z&sig=x", ZDAJ), 1800)
        self.assertEqual(v("https://x.example/f?X-Amz-Date=19700101T000000Z&X-Amz-Expires=0", 0), 0)
        self.assertEqual(v("https://x.example/f?X-Amz-Date=20240229T120000Z&X-Amz-Expires=60", 1_709_208_000), 60)

    def test_brez_roka(self):
        v = tok_izbira.velja_se
        for naslov in (TRAJNA, "https://cdn.example/f.mkv?id=1234567890&exp=12", "https://cdn.example/f.mkv?expires=never",
                       "https://cdn.example/f.mkv?X-Amz-Date=20261003T161807Z", "", None,
                       "https://cdn.example/f.mkv?X-Amz-Date=20261399T161807Z&X-Amz-Expires=60"):
            self.assertIsNone(v(naslov, ZDAJ), naslov)

    def test_vrstni_red(self):
        opis, naslov = (lambda t: t["opis"]), (lambda t: t["url"])
        par = [{"opis": "Dodatek 2160p [A] [4.63 GB] FILM.2020.2160p.HDR.HEVC.mkv", "url": PODPISANA},
               {"opis": "Dodatek 2160p [B] [4.63 GB] FILM.2020.2160p.HDR.HEVC.mkv", "url": TRAJNA}]
        # Brez naslova ostane vrstni red dodatka; z njim je trajna povezava pred casovno omejeno (ista datoteka).
        self.assertEqual(tok_izbira.uredi(par, opis, TV4K)[0]["url"], PODPISANA)
        self.assertEqual(tok_izbira.uredi(par, opis, TV4K, naslov, ZDAJ - 3600)[0]["url"], TRAJNA)
        # Casovno omejena 4K (velja se dve uri) ostane pred trajno 1080p: rok je le jezicek na tehtnici.
        visja = [{"opis": "Dodatek 1080p [2 GB] FILM.2020.1080p.mkv", "url": TRAJNA},
                 {"opis": "Dodatek 2160p [9 GB] FILM.2020.2160p.HEVC.mkv", "url": PODPISANA}]
        self.assertEqual(tok_izbira.uredi(visja, opis, TV4K, naslov, ZDAJ - 6000)[0]["url"], PODPISANA)
        # Tik pred iztekom: za drugimi iste locljivosti, a pred nizjo locljivostjo. Potekla: zadnja od vseh.
        trije = [{"opis": "Dodatek 2160p [5 GB] FILM.2020.2160p.HEVC.mkv", "url": PODPISANA},
                 {"opis": "Dodatek 2160p [20 GB] FILM.2020.2160p.HEVC.mkv", "url": TRAJNA},
                 {"opis": "Dodatek 1080p [2 GB] FILM.2020.1080p.mkv", "url": TRAJNA + "2"}]
        velikosti = lambda seznam: [t["opis"].split("[")[1].split("]")[0] for t in seznam]  # noqa: E731
        self.assertEqual(velikosti(tok_izbira.uredi(trije, opis, TV4K, naslov, ZDAJ)), ["20 GB", "5 GB", "2 GB"])
        self.assertEqual(velikosti(tok_izbira.uredi(trije, opis, TV4K, naslov, ZDAJ + 5000)), ["20 GB", "2 GB", "5 GB"])


class _Streznik(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path.startswith("/film"):
            self.send_response(206 if self.headers.get("Range") else 200)
            self.send_header("Content-Type", "video/x-matroska")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"\x1a\x45")
        elif self.path.startswith("/stran"):
            telo = b"<html>Datoteke ni vec.</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(telo)))
            self.end_headers()
            self.wfile.write(telo)
        else:
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, *a):
        pass


class TestPrviTokOdgovarja(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Streznik)
        threading.Thread(target=cls.streznik.serve_forever, daemon=True).start()
        cls.koren = "http://127.0.0.1:%d" % cls.streznik.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.streznik.shutdown()
        cls.streznik.server_close()

    def test_tok_odgovarja(self):
        self.assertTrue(media_servers.tok_odgovarja(self.koren + "/film.mkv"))
        self.assertFalse(media_servers.tok_odgovarja(self.koren + "/potekla.mkv"))        # 403
        self.assertFalse(media_servers.tok_odgovarja(self.koren + "/stran"))              # stran HTML namesto posnetka
        self.assertFalse(media_servers.tok_odgovarja("http://127.0.0.1:9/film.mkv", rok=1))   # nihce ne poslusa
        self.assertFalse(media_servers.tok_odgovarja("http://javno.example/film.mkv"))    # http zunaj doma ni dovoljen

    def test_zivi_naprej(self):
        mapa = tempfile.mkdtemp()
        try:
            mc = os_media.MediaCenter(mapa, roots=[])
            mrtvi = {"url": self.koren + "/potekla.mkv"}
            stran = {"url": self.koren + "/stran"}
            zivi = {"url": self.koren + "/film.mkv"}
            # Brez vklopa (preizkusi, orodja) ni nobene zahteve in vrstni red ostane.
            self.assertEqual(mc._zivi_naprej([mrtvi, zivi]), [mrtvi, zivi])
            mc.preveri_tokove = True
            self.assertEqual(mc._zivi_naprej([mrtvi, zivi]), [zivi, mrtvi])
            self.assertEqual(mc._zivi_naprej([mrtvi, stran, zivi, mrtvi]), [zivi, mrtvi, stran, mrtvi])
            self.assertEqual(mc._zivi_naprej([zivi, mrtvi]), [zivi, mrtvi])
            # Noben ne odgovori: vrstni red ostane (predvajalnik pove napako). Cetrtega ne sprasujemo vec.
            self.assertEqual(mc._zivi_naprej([mrtvi, stran]), [mrtvi, stran])
            self.assertEqual(mc._zivi_naprej([mrtvi, stran, mrtvi, zivi]), [mrtvi, stran, mrtvi, zivi])
            self.assertEqual(mc._zivi_naprej([mrtvi]), [mrtvi])
        finally:
            shutil.rmtree(mapa, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
