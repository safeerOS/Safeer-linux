"""Profil oddaljenega zaslona po izmerjenih razmerah (core/link_zaslon_profil.py) in kazalec kot podatek
(core/link_kazalec.py): izbira profila, velikost, brezizgubni ukaz, ukaz brez kazalca v sliki, HEVC 4:4:4, opis."""
import os
import subprocess
import tempfile
import unittest
import zlib

from core import link_kazalec as lk
from core import link_zaslon as lz
from core import link_zaslon_profil as lp

ZICNO = {"vmesnik": "enp1s0", "vrsta": "ethernet", "hitrost_mbps": 1000}
VSE = ["kazalec", "izvorna", "brezizgubno", "444", "profil"]


class Profil(unittest.TestCase):
    def test_zicni_lan(self):
        p = lp.izberi(False, "ethernet", ZICNO, 0.4, VSE, hevc444=True)
        self.assertEqual((p["ime"], p["kodek"], p["izvorna"], p["pot"]), ("lan_zicno", "h264rgb", True, "neposredno"))
        self.assertEqual(lp.opis(p, 2560, 1440, 60), "LAN · 1 Gb/s · neposredno · 2560×1440 · 60 fps · brezizgubno")
        # Navidezno namizje (lastnik 25. 10. 2026): vrstica pove, da je navidezno, in DPI gledalca.
        self.assertEqual(lp.opis(p, 2560, 1600, 60, navidezno=True, merilo=1.25),
                         "LAN · 1 Gb/s · neposredno · navidezno namizje · 2560×1600 · 120 DPI · 60 fps · brezizgubno")
        self.assertNotIn("DPI", lp.opis(p, 1920, 1080, 60, navidezno=True))

    def test_zicni_brez_brezizgubnega_gledalca(self):
        p = lp.izberi(False, "ethernet", ZICNO, 0.4, ["izvorna", "444"], hevc444=True)
        self.assertEqual(p["kodek"], "hevc444")
        self.assertEqual(lp.izberi(False, "ethernet", ZICNO, 0.4, ["izvorna"], hevc444=True)["kodek"], "")

    def test_pogoji_zicnega(self):
        # Wi-Fi na kateri koli strani, pocasnejsa povezava ali velik zamik -> LAN, brez brezizgubnega.
        for gledalec, lokalno, rtt in (("wifi", ZICNO, 0.4), ("ethernet", dict(ZICNO, vrsta="wifi"), 0.4),
                                       ("ethernet", dict(ZICNO, hitrost_mbps=100), 0.4), ("ethernet", ZICNO, 9.0),
                                       ("", ZICNO, 0.4)):
            p = lp.izberi(False, gledalec, lokalno, rtt, VSE, hevc444=True)
            self.assertEqual(p["ime"], "lan", (gledalec, lokalno, rtt))
            self.assertEqual(p["kodek"], "hevc444")
        self.assertEqual(lp.izberi(False, "wifi", ZICNO, 0.4, VSE, hevc444=False)["kodek"], "")

    def test_zdoma(self):
        p = lp.izberi(True, "4g", ZICNO, 40.0, VSE, hevc444=True)
        self.assertEqual((p["ime"], p["kodek"], p["izvorna"], p["hitrost_mbps"]), ("zdoma", "", False, 0))
        self.assertTrue(lp.opis(p, 1920, 1080, 60).startswith("Global Link · prek središča"))

    def test_velikost(self):
        lan = lp.izberi(False, "ethernet", ZICNO, 0.4, ["izvorna"])
        self.assertEqual(lp.velikost((2560, 1440), lan, (1920, 1080)), (2560, 1440))
        self.assertEqual(lp.velikost((5120, 2880), lan, (1920, 1080)), (3840, 2160))
        star = lp.izberi(False, "ethernet", ZICNO, 0.4, [])
        self.assertEqual(lp.velikost((2560, 1440), star, (1920, 1080)), (1920, 1080), "stari gledalec: stara meja")
        self.assertEqual(lp.velikost((0, 0), lan, (1920, 1080)), (1920, 1080))

    def test_lokalno_omrezje(self):
        koren = tempfile.mkdtemp(prefix="safeer-net-")
        os.makedirs(os.path.join(koren, "enp1s0"))
        with open(os.path.join(koren, "enp1s0", "speed"), "w") as d:
            d.write("1000\n")
        os.makedirs(os.path.join(koren, "wlp2s0", "wireless"))

        def ip(dev):
            return lambda u, **kw: subprocess.CompletedProcess(u, 0, '[{"dst":"x","dev":"%s"}]' % dev, "")
        self.assertEqual(lp.lokalno_omrezje("192.168.0.20", ip("enp1s0"), koren),
                         {"vmesnik": "enp1s0", "vrsta": "ethernet", "hitrost_mbps": 1000})
        self.assertEqual(lp.lokalno_omrezje("192.168.0.20", ip("wlp2s0"), koren)["vrsta"], "wifi")
        self.assertEqual(lp.lokalno_omrezje("", ip("enp1s0"), koren)["vrsta"], "")

        def pade(u, **kw):
            raise OSError("ni ip")
        self.assertEqual(lp.lokalno_omrezje("192.168.0.20", pade, koren)["vrsta"], "")


class Ukazi(unittest.TestCase):
    def test_brezizgubni(self):
        u = lp.ukaz_brezizgubno("ffmpeg", ":0", 2560, 1440, 60, (0, 0), kazalec_v_sliki=False)
        self.assertEqual(u[u.index("-c:v") + 1], "libx264rgb")
        self.assertEqual(u[u.index("-qp") + 1], "0")
        self.assertEqual(u[u.index("-draw_mouse") + 1], "0")
        self.assertEqual(u[u.index("-video_size") + 1], "2560x1440")
        self.assertNotIn("scale", " ".join(u), "brez pomanjsave")
        self.assertIn(":0+1920,0", lp.ukaz_brezizgubno("ffmpeg", ":0", 2560, 1440, 60, (1920, 0)))

    def test_kazalec_in_444(self):
        u = lz.ukaz_ffmpeg(":0", 2560, 1440, 2560, 1440, 60, "24M", "/dev/dri/renderD128", "ffmpeg", 16,
                           kodek="hevc", kazalec_v_sliki=False, barve444=True)
        self.assertEqual(u[u.index("-draw_mouse") + 1], "0")
        self.assertEqual(u[u.index("-vf") + 1], "format=vuyx,hwupload")
        self.assertEqual(u[u.index("-profile:v") + 1], "rext")
        # 4:4:4 samo brez pomanjsave in samo HEVC; privzeto kazalec v sliki (stari gledalci).
        u2 = lz.ukaz_ffmpeg(":0", 1920, 1080, 2560, 1440, 60, "24M", "/dev/dri/renderD128", "ffmpeg", 16,
                            kodek="hevc", barve444=True)
        self.assertEqual(u2[u2.index("-profile:v") + 1], "main")
        self.assertEqual(u2[u2.index("-draw_mouse") + 1], "1")

    def test_hevc444_preizkus(self):
        lz._HEVC444.clear()
        klici = []

        def zazeni(u, **kw):
            klici.append(u)
            return subprocess.CompletedProcess(u, 0, b"", b"")
        self.assertTrue(lz.hevc444_mozen("ffmpeg", "/dev/dri/x", zazeni))
        self.assertTrue(lz.hevc444_mozen("ffmpeg", "/dev/dri/x", zazeni))
        self.assertEqual(len(klici), 1, "izid velja za proces")
        self.assertFalse(lz.hevc444_mozen("ffmpeg", None, zazeni))
        lz._HEVC444.clear()


class Kazalec(unittest.TestCase):
    def test_oblike(self):
        self.assertEqual(lk.oblika("left_ptr"), "puscica")
        self.assertEqual(lk.oblika("xterm"), "besedilo")
        self.assertEqual(lk.oblika("pointer"), "roka")
        self.assertEqual(lk.oblika("nwse-resize"), "velikost_nwse")
        self.assertEqual(lk.oblika("neznano-ime"), "puscica")
        self.assertEqual(lk.oblika(None), "puscica")
        # Ista imena kot vir Windows (zajem_zaslona._OBLIKE_KAZALCA).
        self.assertEqual(set(lk.OBLIKE), {"puscica", "besedilo", "cakanje", "kriz", "velikost_nwse", "velikost_nesw",
                                          "velikost_we", "velikost_ns", "premik", "roka", "puscica_cakanje", "ne"})

    def test_png(self):
        # 2x1: neprosojna rdeca in polprosojna (predhodno pomnozena) bela.
        p = lk.png(2, 1, [0xFFFF0000, 0x80808080])
        self.assertTrue(p.startswith(b"\x89PNG\r\n\x1a\n"))
        i = p.index(b"IDAT")
        dolzina = int.from_bytes(p[i - 4:i], "big")
        self.assertEqual(zlib.decompress(p[i + 4:i + 4 + dolzina]), bytes([0, 255, 0, 0, 255, 255, 255, 255, 128]))

    def test_v_sliki(self):
        self.assertEqual(lk.v_sliki(1280, 720, (0, 0), (2560, 1440), (1920, 1080)), (960, 540, True))
        self.assertEqual(lk.v_sliki(100, 10, (1920, 0), (2560, 1440), (2560, 1440))[2], False, "na drugem monitorju")

    def test_sprememba(self):
        s = lk.Sprememba()
        st = {"x": 10, "y": 20, "serija": 1, "ime": "xterm", "viden": True, "png": b"PNG", "xhot": 3, "yhot": 7}
        prvo = s.naslednje(st, (0, 0), (100, 100), (100, 100))
        self.assertEqual((prvo["kazalec"], prvo["oblika"], prvo["vroca"]), ([10, 20], "besedilo", [3, 7]))
        self.assertTrue(prvo["slika"].startswith("data:image/png;base64,"))
        self.assertIsNone(s.naslednje(dict(st, png=None), (0, 0), (100, 100), (100, 100)), "brez spremembe nic")
        drugo = s.naslednje({"x": 11, "y": 20, "serija": 1, "ime": "xterm", "viden": True}, (0, 0), (100, 100), (100, 100))
        self.assertEqual(drugo, {"kazalec": [11, 20], "oblika": "besedilo", "viden": True}, "premik brez slike")
        skrit = s.naslednje({"x": 11, "y": 20, "serija": 2, "ime": "", "viden": False}, (0, 0), (100, 100), (100, 100))
        self.assertFalse(skrit["viden"])


if __name__ == "__main__":
    unittest.main()
