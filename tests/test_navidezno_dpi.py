"""Navidezno namizje v DPI gledalca (lastnik 25. 10. 2026 09:13: »pri povecavi 125/150 % izvor nastavi DPI, ne bitnega
raztega«): izhod sway dobi samo celo merilo, ostanek gre v DPI pisav programa (core/link_sway.razdeli_merilo);
apps.launch z `view` nastavi velikost in merilo PRED zagonom programa."""
import unittest
from unittest import mock

from core import link_daljinec, link_sway


class Razdelitev(unittest.TestCase):
    def test_celo_merilo_in_pisave(self):
        self.assertEqual(link_sway.razdeli_merilo(1.0), (1, 1.0))
        self.assertEqual(link_sway.razdeli_merilo(1.25), (1, 1.25))
        self.assertEqual(link_sway.razdeli_merilo(1.5), (1, 1.5))
        self.assertEqual(link_sway.razdeli_merilo(2.0), (2, 1.0))
        self.assertEqual(link_sway.razdeli_merilo(2.5), (2, 1.25))
        for slabo in (None, "x", float("nan"), 0.5, -1):
            self.assertEqual(link_sway.razdeli_merilo(slabo), (1, 1.0), slabo)

    def test_okolje(self):
        self.assertEqual(link_sway.okolje_dpi(1.0), {})
        self.assertEqual(link_sway.okolje_dpi(1.25), {"GDK_DPI_SCALE": "1.25", "QT_FONT_DPI": "120"})
        self.assertEqual(link_sway.okolje_dpi(1.5)["QT_FONT_DPI"], "144")


class _Drugi(link_sway.DrugiZaslon):
    def __init__(self):
        self._osnova, self._pisava, self._merilo = 1.0, 1.0, 1.0
        self._urejena_platna = {}
        self.sirina, self.visina = 1920, 1080
        self.ukazi = []
        self._zagon = None

    def tece(self):
        return True

    def zazeni(self, sirina=1920, visina=1080):
        self.sirina, self.visina = sirina, visina
        return True

    def velikost(self, sirina, visina):
        self.sirina, self.visina = sirina, visina

    def uredi_platno(self):
        self.ukazi.append(("scale", self._osnova))

    def _msg(self, argumenti):
        self.ukazi.append(tuple(argumenti))
        return '[{"success": true}]'


class Zaslon(unittest.TestCase):
    def test_delno_merilo_izhod_celo_pisave_dpi(self):
        d = _Drugi()
        d.osnovno_merilo(1.25)
        self.assertEqual(d.ukazi, [], "izhod ostane 1 - brez bitnega raztega")
        self.assertEqual(d.okolje_programa(), {"GDK_DPI_SCALE": "1.25", "QT_FONT_DPI": "120"})
        d.osnovno_merilo(2.0)
        self.assertEqual(d.ukazi[-1], ("scale", 2.0))
        self.assertEqual(d.okolje_programa(), {})

    def test_program_dobi_dpi_v_ukazu(self):
        d = _Drugi()
        d.osnovno_merilo(1.5)
        with mock.patch.object(link_sway, "_okna_namizja", return_value=None), \
                mock.patch.object(link_sway.threading, "Thread"):
            self.assertTrue(d.zazeni_program(["xed"]))
        ukaz = [u for u in d.ukazi if u and u[0] == "exec"][0][1]
        self.assertTrue(ukaz.startswith("GDK_DPI_SCALE=1.5 QT_FONT_DPI=144 SAFEER_ZAGON="), ukaz)
        self.assertTrue(ukaz.endswith(" 'xed'"))

    def test_pogled_pred_zagonom(self):
        d = _Drugi()
        d.pripravi_za_gledalca({"w": 2560, "h": 1600, "scale": 1.25})
        self.assertEqual((d.sirina, d.visina), (2560, 1600))
        self.assertEqual(d.okolje_programa()["GDK_DPI_SCALE"], "1.25")
        d.pripravi_za_gledalca("ni pogled")
        self.assertEqual((d.sirina, d.visina), (2560, 1600))


class Daljinec(unittest.TestCase):
    def test_apps_launch_z_view_pripravi_zaslon(self):
        programi = mock.Mock()
        programi.zazeni.return_value = True
        programi.drugi = mock.Mock()
        izidi = []
        pogled = {"w": 1920, "h": 1200, "scale": 1.25}
        link_daljinec.izvedi_control("apps.launch", {"app": "app:xed.desktop", "view": pogled}, lambda _u: None,
                                     izidi.append, programi=programi)
        self.assertTrue(izidi[0]["ok"])
        programi.drugi.pripravi_za_gledalca.assert_called_once_with(pogled)
        programi.zazeni.assert_called_once_with("app:xed.desktop")
