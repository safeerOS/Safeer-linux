"""Slicica namizja za preklopnik Prostori (`screen.thumb`, krog 2): dovoljenje kot deljenje zaslona, samo X11, en zajem
naenkrat, zadnja velja kratek cas, odgovor gre prek Linka kot JPEG data URL; dostop zahteva zmoznost zaslona."""
import base64
import subprocess
import threading
import unittest
from unittest import mock

from core import link_daljinec, link_dostop, link_prostori, link_zaslon

# Najmanjsa glava JPEG: SOI + SOF0 (visina 180, sirina 320) - dovolj za branje mer.
JPEG = b"\xff\xd8\xff\xc0\x00\x11\x08\x00\xb4\x01\x40\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01\xff\xd9"


class _Zagon:
    def __init__(self, izhod=JPEG, koda=0):
        self.izhod, self.koda, self.klici = izhod, koda, []

    def __call__(self, ukaz, **kw):
        self.klici.append(ukaz)
        return subprocess.CompletedProcess(ukaz, self.koda, self.izhod, b"")


class Slicica(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict("os.environ", {"DISPLAY": ":0"}, clear=False)
        p.start()
        self.addCleanup(p.stop)
        p2 = mock.patch("core.seja_prikaza.je_wayland", return_value=False)
        p2.start()
        self.addCleanup(p2.stop)

    def test_ukaz(self):
        u = link_zaslon.ukaz_slicice("/usr/bin/ffmpeg", ":0", 320)
        self.assertEqual(u[0], "/usr/bin/ffmpeg")
        self.assertIn("x11grab", u)
        self.assertEqual(u[u.index("-frames:v") + 1], "1")
        self.assertEqual(u[u.index("-draw_mouse") + 1], "0")
        self.assertIn("scale=320:-2:flags=bilinear", u)
        self.assertIn("scale=640:-2:flags=bilinear", link_zaslon.ukaz_slicice("f", ":0", 99999))

    def test_dovoljenje_in_wayland(self):
        z = link_zaslon.Zaslon(ffmpeg="/usr/bin/ffmpeg", vklopljeno=False)
        self.assertEqual(z.slicica(zazeni=_Zagon()), {"ok": False, "koda": "ni_dovoljeno"})
        z.vklopljeno = True
        with mock.patch("core.seja_prikaza.je_wayland", return_value=True):
            self.assertEqual(z.slicica(zazeni=_Zagon()), {"ok": False, "koda": "ni_brez_potrditve"})

    def test_slika_in_predpomnilnik(self):
        z = link_zaslon.Zaslon(ffmpeg="/usr/bin/ffmpeg", vklopljeno=True)
        zagon = _Zagon()
        r = z.slicica(zazeni=zagon)
        self.assertTrue(r["ok"])
        self.assertEqual((r["data"]["width"], r["data"]["height"]), (320, 180))
        self.assertEqual(base64.b64decode(r["data"]["image"].split(",", 1)[1]), JPEG)
        # Odgovor je tak, kot ga sprejme preklopnik na drugi strani.
        self.assertIsNotNone(link_prostori.veljavna_slicica(r["data"]))
        z.slicica(zazeni=zagon)
        self.assertEqual(len(zagon.klici), 1, "druga naprava v istem trenutku dobi isto sliko")

    def test_napaka_zajema(self):
        z = link_zaslon.Zaslon(ffmpeg="/usr/bin/ffmpeg", vklopljeno=True)
        self.assertEqual(z.slicica(zazeni=_Zagon(izhod=b"<html>")), {"ok": False, "koda": "napaka"})
        self.assertEqual(z.slicica(zazeni=_Zagon(koda=1)), {"ok": False, "koda": "napaka"})

        def obvisi(ukaz, **kw):
            raise subprocess.TimeoutExpired(ukaz, kw.get("timeout"))
        self.assertEqual(z.slicica(zazeni=obvisi), {"ok": False, "koda": "napaka"})

    def test_en_zajem_naenkrat(self):
        z = link_zaslon.Zaslon(ffmpeg="/usr/bin/ffmpeg", vklopljeno=True)
        z._slicica_zaklep.acquire()
        try:
            self.assertEqual(z.slicica(zazeni=_Zagon()), {"ok": False, "koda": "zasedeno"})
        finally:
            z._slicica_zaklep.release()


class Dejanje(unittest.TestCase):
    def _izvedi(self, zaslon):
        izid, gotovo = {}, threading.Event()

        def koncaj(r):
            izid.update(r)
            gotovo.set()
        link_daljinec.izvedi_control("screen.thumb", {}, lambda _u: None, koncaj, zaslon=zaslon)
        self.assertTrue(gotovo.wait(5))
        return izid

    def test_prek_daljinca(self):
        class _Z:
            def slicica(self, sirina=320):
                return {"ok": True, "data": {"image": "data:image/jpeg;base64,/9j/", "width": sirina, "height": 180}}
        r = self._izvedi(_Z())
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["data"]["width"], 320)

    def test_brez_zaslona_in_zavrnjeno(self):
        self.assertEqual(self._izvedi(None).get("code"), "ni_na_racunalniku")

        class _Ne:
            def slicica(self, sirina=320):
                return {"ok": False, "koda": "ni_dovoljeno"}
        r = self._izvedi(_Ne())
        self.assertFalse(r.get("ok"))
        self.assertEqual(r.get("code"), "ni_dovoljeno")
        # Preklopnik na drugi strani tako napravo dolgo ne sprasuje (koda iz "code").
        s = link_prostori.Slicice(lambda: 0.0)
        self.assertEqual(s.dobi("pc", lambda: r), {"ok": False, "koda": "ni_dovoljeno"})
        self.assertGreaterEqual(s._z["pc"]["naslednjic"], link_prostori.SLICICA_NI_S)

    def test_dostop_zahteva_zaslon(self):
        self.assertEqual(link_dostop.zahteva_dejanja("screen.thumb"), link_dostop.ZASLON)
        self.assertIn("screen.thumb", link_daljinec.DEJANJA_ZASLON)


if __name__ == "__main__":
    unittest.main()
