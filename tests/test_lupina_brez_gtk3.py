"""Qt v procesu GTK4 ne sme naloziti teme GTK3 (core/os_lupina.brez_gtk_teme_qt) - testni PC 15. 10. 2026:
zagon iz seje Cinnamon, »cannot register existing type 'GtkWidget'«, lupina se ni izrisala."""
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class BrezGtkTeme(unittest.TestCase):
    def setUp(self):
        self.lupina = importlib.import_module("core.os_lupina")

    def test_cinnamon_brez_gtk3_med_ustvarjanjem_in_vrnjeno_po(self):
        okolje = {"XDG_CURRENT_DESKTOP": "X-Cinnamon", "DESKTOP_SESSION": "cinnamon", "QT_QPA_PLATFORMTHEME": "gtk3"}
        with mock.patch.dict(os.environ, okolje, clear=False):
            with self.lupina.brez_gtk_teme_qt():
                self.assertNotIn("XDG_CURRENT_DESKTOP", os.environ)
                self.assertNotIn("DESKTOP_SESSION", os.environ)
                self.assertEqual(os.environ["QT_QPA_PLATFORMTHEME"], "xdgdesktopportal")
            self.assertEqual(os.environ["XDG_CURRENT_DESKTOP"], "X-Cinnamon")
            self.assertEqual(os.environ["DESKTOP_SESSION"], "cinnamon")

    def test_uporabnikova_tema_ostane(self):
        with mock.patch.dict(os.environ, {"QT_QPA_PLATFORMTHEME": "kde"}, clear=False):
            with self.lupina.brez_gtk_teme_qt():
                self.assertEqual(os.environ["QT_QPA_PLATFORMTHEME"], "kde")

    def test_vrne_tudi_ob_napaki(self):
        with mock.patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "GNOME"}, clear=False):
            with self.assertRaises(RuntimeError):
                with self.lupina.brez_gtk_teme_qt():
                    raise RuntimeError("x")
            self.assertEqual(os.environ["XDG_CURRENT_DESKTOP"], "GNOME")


if __name__ == "__main__":
    unittest.main()
