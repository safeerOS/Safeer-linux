"""Nazaj na daljincu v brskalniku: prejsnja stran, razen kadar je video cez cel zaslon."""
import json
import unittest
from unittest import mock

from core import link_fokus, link_sway


class Drugi:
    def __init__(self, polno):
        self.polno = polno

    def _msg(self, argumenti, vrsta):
        okno = {"focused": True, "pid": 4242, "fullscreen_mode": self.polno,
                "rect": {"x": 0, "y": 0, "width": 800, "height": 600}}
        return json.dumps({"nodes": [{"nodes": [okno]}]})


class BrskalnikNaStrani(unittest.TestCase):
    def fokus(self, polno):
        f = link_fokus.Fokus.__new__(link_fokus.Fokus)
        f.drugi = Drugi(polno)
        return f

    def test_brskalnik_v_oknu(self):
        with mock.patch.object(link_sway, "_je_spletni_brskalnik", return_value=True):
            self.assertTrue(self.fokus(0).brskalnik_na_strani())

    def test_video_cez_cel_zaslon_ostane_escape(self):
        with mock.patch.object(link_sway, "_je_spletni_brskalnik", return_value=True):
            self.assertFalse(self.fokus(1).brskalnik_na_strani())

    def test_drug_program(self):
        with mock.patch.object(link_sway, "_je_spletni_brskalnik", return_value=False):
            self.assertFalse(self.fokus(0).brskalnik_na_strani())

    def test_firefox_je_spletni_brskalnik(self):
        self.assertTrue(link_sway._ime_brskalnika("/usr/lib/firefox/firefox-bin", link_sway.BRSKALNIKI + link_sway.FIREFOXI))
        # Za zastavice Chromiuma in zapiranje ob koncu seje Firefox ostane izvzet.
        self.assertFalse(link_sway._ime_brskalnika("/usr/lib/firefox/firefox-bin"))

    def test_okno_se_vedno_najde(self):
        self.assertEqual(self.fokus(0)._okno(), (4242, 0, 0, 800, 600))


if __name__ == "__main__":
    unittest.main()
