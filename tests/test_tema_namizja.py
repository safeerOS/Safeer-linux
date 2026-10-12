"""Spletne strani sledijo temi namizja; dialogi Spleta se odprejo nad oknom, v katerem je Splet."""
import unittest
from pathlib import Path
from unittest import mock

from core import os_tema_namizja as t

KOREN = Path(__file__).resolve().parents[1]


class _Nast:
    def __init__(self, ime):
        self.props = type("P", (), {"gtk_theme_name": ime, "gtk_application_prefer_dark_theme": False})()


class JeTemno(unittest.TestCase):
    def _gtk(self, ime):
        n = _Nast(ime)
        return type("Gtk", (), {"Settings": type("S", (), {"get_default": staticmethod(lambda: n)})}), n

    def test_portal_odloci(self):
        gtk, _ = self._gtk("Mint-Y")
        with mock.patch.object(t, "_portal", return_value=1), mock.patch.object(t, "_gsettings", return_value="prefer-light"):
            self.assertTrue(t.je_temno(gtk, None, None))
        with mock.patch.object(t, "_portal", return_value=2), mock.patch.object(t, "_gsettings", return_value="prefer-dark"):
            self.assertFalse(t.je_temno(gtk, None, None))

    def test_brez_portala_gsettings(self):
        gtk, _ = self._gtk("Mint-Y")
        with mock.patch.object(t, "_portal", return_value=0), mock.patch.object(t, "_gsettings", return_value="prefer-dark"):
            self.assertTrue(t.je_temno(gtk, None, None))

    def test_ime_teme_safeer_cinnamon_je_temna(self):
        for ime, pricakovano in (("Safeer-Cinnamon", True), ("Mint-Y-Dark-Aqua", True), ("Mint-Y", False)):
            gtk, _ = self._gtk(ime)
            with mock.patch.object(t, "_portal", return_value=None), mock.patch.object(t, "_gsettings", return_value="default"):
                self.assertEqual(t.je_temno(gtk, None, None), pricakovano, ime)

    def test_uskladi_nastavi_gtk(self):
        gtk, n = self._gtk("Safeer-Cinnamon")
        with mock.patch.object(t, "_portal", return_value=None), mock.patch.object(t, "_gsettings", return_value=None):
            self.assertTrue(t.uskladi(gtk, None, None))
        self.assertTrue(n.props.gtk_application_prefer_dark_theme)


class Povezano(unittest.TestCase):
    def test_safeer_os_sledi_temi(self):
        self.assertIn("os_tema_namizja.sledi(Gtk, Gio, GLib)", (KOREN / "safeer_os.py").read_text(encoding="utf-8"))

    def test_safeer_cinnamon_nastavi_portal(self):
        s = (KOREN / "packaging" / "tema-cinnamon" / "safeer-cinnamon").read_text(encoding="utf-8")
        self.assertIn("org.x.apps.portal:color-scheme", s)
        self.assertIn("pisi org.x.apps.portal:color-scheme \"'prefer-dark'\"", s)

    def test_dialogi_spleta_nad_oknom_spleta(self):
        s = (KOREN / "core" / "os_splet.py").read_text(encoding="utf-8")
        self.assertNotIn("transient_for=self.stars", s)
        self.assertIn("def _okno_za_dialog(self)", s)


if __name__ == "__main__":
    unittest.main()
