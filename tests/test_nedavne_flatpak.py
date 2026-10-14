"""Nedavno v Flatpaku: seznam racunalnika (~/.local/share), ne prazen seznam peskovnika (14. 10. 2026)."""
import os
import unittest

import safeer_os


class Nedavne(unittest.TestCase):
    def test_flatpak_bere_seznam_racunalnika(self):
        self.assertEqual(safeer_os.datoteka_nedavnih({"FLATPAK_ID": "x"}, "/home/u"),
                         os.path.join("/home/u", ".local", "share", "recently-used.xbel"))

    def test_brez_flatpaka_privzeto(self):
        self.assertEqual(safeer_os.datoteka_nedavnih({}, "/home/u"), "")

    def test_vse_poti_gredo_prek_upravitelja(self):
        with open(safeer_os.__file__, encoding="utf-8") as f:
            vir = f.read()
        self.assertEqual(vir.count("Gtk.RecentManager.get_default()"), 2)   # samo rezerva v _nedavni

    def test_upravitelj_z_datoteko(self):
        import tempfile
        from gi.repository import Gtk
        with tempfile.TemporaryDirectory() as d:
            m = Gtk.RecentManager(filename=os.path.join(d, "r.xbel"))
            self.assertEqual(m.get_property("filename"), os.path.join(d, "r.xbel"))


if __name__ == "__main__":
    unittest.main()
