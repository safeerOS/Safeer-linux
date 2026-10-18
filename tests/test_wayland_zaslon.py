"""Deljenje zaslona in vnos v Safeer Linku na Waylandu (portal) in na X11 z vec monitorji - brez pravega zaslona.

Zivi preizkus na GNOME 46 je tests/test_wayland_portal_zivo.py; tu je logika: prevod dogodkov televizorja v klice
RemoteDesktop, sestava ukaza zajema, izbira poti v link_zaslon/link_deljenje in hramba zetona obnovitve."""

import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

KOREN = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN))

from core import link_vnos, link_zaslon, portal_zaslon, zajem_pipewire  # noqa: E402

WAYLAND = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}


class LaznaSeja:
    """Seja portala brez D-Bus: zapise klice vnosa."""

    def __init__(self, vnos=True):
        self.vnos = vnos
        self.odprta = True
        self.fd = 7
        self.tok = {"vozlisce": 42, "sirina": 1920, "visina": 1080, "x": 0, "y": 0}
        self.klici = []
        self.zaprta = False

    def premik(self, dx, dy):
        self.klici.append(("premik", dx, dy)); return True

    def premik_na(self, x, y):
        self.klici.append(("premik_na", x, y)); return True

    def gumb(self, koda, dol):
        self.klici.append(("gumb", koda, dol)); return True

    def kolesce(self, korakov, vodoravno=False):
        self.klici.append(("kolesce", korakov)); return True

    def tipka(self, keysym, dol):
        self.klici.append(("tipka", keysym, dol)); return True

    def odpri(self):
        return dict(self.tok)

    def zapri(self):
        self.zaprta = True


class VnosPrekPortala(unittest.TestCase):
    def setUp(self):
        self.s = LaznaSeja()
        self.v = portal_zaslon.VnosPortal(self.s)

    def test_mozno_samo_z_dovoljenim_vnosom(self):
        self.assertTrue(self.v.mozno)
        self.assertFalse(portal_zaslon.VnosPortal(LaznaSeja(vnos=False)).mozno)

    def test_tipka_in_bliznjica(self):
        self.assertTrue(self.v.izvedi({"vrsta": "tipka", "tipka": "ok"}))
        self.assertEqual(self.s.klici, [("tipka", 0xFF0D, True), ("tipka", 0xFF0D, False)])
        self.s.klici.clear()
        self.assertTrue(self.v.izvedi({"vrsta": "tipka", "tipka": "kopiraj"}))      # ctrl+c
        self.assertEqual(self.s.klici, [("tipka", 0xFFE3, True), ("tipka", 0x63, True),
                                        ("tipka", 0x63, False), ("tipka", 0xFFE3, False)])
        self.assertFalse(self.v.izvedi({"vrsta": "tipka", "tipka": "rm -rf"}))    # ni na seznamu dovoljenega

    def test_besedilo_in_miska(self):
        self.assertTrue(self.v.izvedi({"vrsta": "besedilo", "besedilo": "Aš"}))
        self.assertEqual([k for k in self.s.klici if k[2]], [("tipka", 0x41, True), ("tipka", 0x1B9, True)])
        self.s.klici.clear()
        self.v.izvedi({"vrsta": "premik", "dx": 5, "dy": -3})
        self.v.izvedi({"vrsta": "tocka", "x": 100, "y": 200})
        self.v.izvedi({"vrsta": "klik", "gumb": "desni"})
        self.v.izvedi({"vrsta": "kolesce", "smer": "dol", "koliko": 3})
        self.v.izvedi({"vrsta": "gumb", "gumb": "levi", "dol": True})
        self.assertEqual(self.s.klici, [("premik", 5.0, -3.0), ("premik_na", 100.0, 200.0),
                                        ("gumb", 0x111, True), ("gumb", 0x111, False), ("kolesce", 3),
                                        ("gumb", 0x110, True)])

    def test_drzane_tipke_se_sprostijo(self):
        self.v.izvedi({"vrsta": "tipka_dol", "tipka": "gor"})
        self.assertEqual(self.v.drzane(), ["Up"])
        self.v.sprosti_vse()
        self.assertEqual(self.s.klici[-1], ("tipka", 0xFF52, False))


class UkazZajema(unittest.TestCase):
    def test_zajem_pipewire_in_ffmpeg(self):
        s = LaznaSeja()
        ff = link_zaslon.ukaz_ffmpeg("", 1280, 720, 1280, 720, 30, "8M", None, "ffmpeg",
                                     vhod=portal_zaslon.vhod_ffmpeg(1280, 720, 30))
        self.assertNotIn("x11grab", ff)
        self.assertIn("rawvideo", ff)
        self.assertNotIn("scale=", " ".join(ff))         # GStreamer je sliko ze pomanjsal
        ukaz, dodatno = portal_zaslon.ukaz_zajema(s, 1280, 720, 30, ff)
        self.assertEqual(ukaz[1:3], ["-m", "core.zajem_pipewire"])
        self.assertEqual(ukaz[ukaz.index("--fd") + 1], "7")
        self.assertEqual(ukaz[ukaz.index("--") + 1:], ff)
        self.assertEqual(dodatno["pass_fds"], (7,))
        self.assertEqual(dodatno["cwd"], str(KOREN))

    def test_opis_cevi_enakomeren_ritem(self):
        opis = zajem_pipewire.opis_cevi(7, 42, 1920, 1080, 30, 9)
        self.assertIn("pipewiresrc fd=7 path=42", opis)
        self.assertIn("keepalive-time=33", opis)            # slika tudi brez spremembe na zaslonu
        self.assertIn("framerate=30/1", opis)
        self.assertIn("fdsink fd=9", opis)

    def test_x11_monitor_odmik(self):
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 30, "8M", None, odmik=(1920, 0))
        self.assertEqual(u[u.index("-i") + 1], ":0+1920,0")
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 30, "8M", None)
        self.assertEqual(u[u.index("-i") + 1], ":0")
        v = link_vnos.Vnos(display=":0", xdotool="/bin/true", odmik=(1920, 0))
        with mock.patch.object(v, "_pozeni", return_value=True) as pozeni:
            v.izvedi({"vrsta": "tocka", "x": 10, "y": 20})
        pozeni.assert_called_with(["mousemove", "--", "1930", "20"])


class LinkZaslonNaWaylandu(unittest.TestCase):
    def test_na_voljo_po_portalu(self):
        z = link_zaslon.Zaslon(vklopljeno=True, ffmpeg="/bin/true")
        with mock.patch.dict(os.environ, WAYLAND), \
                mock.patch.object(portal_zaslon, "zmoznosti", return_value={"zajem": True, "vnos": True}), \
                mock.patch.object(portal_zaslon, "gstreamer_pipewire", return_value=True):
            n = z.na_voljo()
        self.assertTrue(n["mozno"] and n["vnos"])
        self.assertEqual(n["seja"], "wayland")
        z2 = link_zaslon.Zaslon(vklopljeno=True, ffmpeg="/bin/true")
        with mock.patch.dict(os.environ, WAYLAND), \
                mock.patch.object(portal_zaslon, "zmoznosti", return_value={"zajem": False, "vnos": False}), \
                mock.patch.object(portal_zaslon, "gstreamer_pipewire", return_value=True):
            self.assertFalse(z2.na_voljo()["mozno"], "brez portala zajema ni (prej: crn XWayland)")

    def test_zacni_odpre_portal_in_ukaz_zajema(self):
        z = link_zaslon.Zaslon(vklopljeno=True, ffmpeg="/bin/true")
        lazna = LaznaSeja()
        try:
            with mock.patch.dict(os.environ, WAYLAND), \
                    mock.patch.object(portal_zaslon, "Seja", return_value=lazna), \
                    mock.patch.object(link_zaslon, "vaapi_naprava", return_value=None):
                seja = z.zacni("tv", "srednja", "desktop")
            self.assertEqual((seja["width"], seja["height"]), (1920, 1080))
            self.assertTrue(seja["input"])
            self.assertIs(z._portal, lazna)
            self.assertEqual(z._zajem_dodatno["pass_fds"], (7,))
            self.assertIsInstance(z._vnos, portal_zaslon.VnosPortal)
        finally:
            z.ustavi()
        self.assertTrue(lazna.zaprta, "konec seje zapre portal (GNOME ugasne oznako deljenja)")

    def test_zavrnitev_je_razumljiva_napaka(self):
        z = link_zaslon.Zaslon(vklopljeno=True, ffmpeg="/bin/true")

        class Zavrne(LaznaSeja):
            def odpri(self):
                raise portal_zaslon.NapakaPortala("zavrnjeno")
        with mock.patch.dict(os.environ, WAYLAND), mock.patch.object(portal_zaslon, "Seja", return_value=Zavrne()):
            with self.assertRaises(RuntimeError) as e:
                z.zacni("tv", "srednja", "desktop")
        self.assertEqual(str(e.exception), portal_zaslon.SPOROCILA["zavrnjeno"])


class Zetoni(unittest.TestCase):
    def test_zeton_shranjen_zasebno_in_pobrisan_ob_zavrnitvi(self):
        with tempfile.TemporaryDirectory() as d:
            pot = os.path.join(d, "safeer-control", "portal-zaslon.json")
            portal_zaslon._pisi_zeton(pot, "vnos", "abc")
            self.assertEqual(json.load(open(pot)), {"vnos": "abc"})
            self.assertEqual(os.stat(pot).st_mode & 0o777, 0o600)
            portal_zaslon._pisi_zeton(pot, "vnos", "")
            self.assertEqual(json.load(open(pot)), {})


class Deljenje(unittest.TestCase):
    def test_zajem_na_voljo_wayland(self):
        from core import link_deljenje
        with mock.patch.dict(os.environ, WAYLAND), \
                mock.patch.object(portal_zaslon, "zmoznosti", return_value={"zajem": True}), \
                mock.patch.object(portal_zaslon, "gstreamer_pipewire", return_value=True):
            self.assertEqual(link_deljenje.DeljenjeZaslona.zajem_na_voljo(), (True, ""))
        with mock.patch.dict(os.environ, WAYLAND), \
                mock.patch.object(portal_zaslon, "zmoznosti", return_value={"zajem": False}), \
                mock.patch.object(portal_zaslon, "gstreamer_pipewire", return_value=True):
            ok, razlog = link_deljenje.DeljenjeZaslona.zajem_na_voljo()
            self.assertFalse(ok)
            self.assertIn("portal", razlog)

    def test_kode_napak_imajo_prevode(self):
        js = (KOREN / "assets" / "link" / "link.js").read_text(encoding="utf-8")
        self.assertEqual(js.count("napZajemPotrdi:"), 6)          # sl, en, de, es, fr, it
        self.assertIn('p.koda === "zajem_ni_potrjen"', js)
        vir = (KOREN / "core" / "link_deljenje.py").read_text(encoding="utf-8")
        self.assertIn('"zavrnjeno": "dovoljenje_zavrnjeno", "rok": "zajem_ni_potrjen"', vir)


class OknaNamizjaSway(unittest.TestCase):
    def test_wmctrl_samo_na_x11(self):
        from core import link_sway
        with mock.patch.dict(os.environ, WAYLAND), mock.patch.object(link_sway.shutil, "which", return_value="/x"):
            self.assertIsNone(link_sway._pidi_na_namizju())
            self.assertIsNone(link_sway._okna_namizja())


if __name__ == "__main__":
    unittest.main()


class BesediloNiMoznost(unittest.TestCase):
    def test_besedilo_dve_crtici(self):
        """Besedilo »--« s televizorja se vpise, ne izgine kot moznost xdotool (pregled kode 18. 10. 2026)."""
        s = LaznaSeja()
        v = portal_zaslon.VnosPortal(s)
        self.assertTrue(v.izvedi({"vrsta": "besedilo", "besedilo": "--"}))
        self.assertEqual([k[1] for k in s.klici if k[2]], [0x2D, 0x2D])
        s.klici.clear()
        self.assertTrue(v.izvedi({"vrsta": "klik", "gumb": "levi", "dvojni": True}))
        self.assertEqual(len([k for k in s.klici if k[2]]), 2)
