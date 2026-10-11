"""Widevine: stran odpre namesceni brskalnik z Widevine (core/drm.py) - brez pravih programov."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import drm  # noqa: E402


class Brskalnik(unittest.TestCase):
    def test_brave_prvi(self):
        ima = {"google-chrome", "brave-browser"}
        self.assertEqual(drm.najdi_brskalnik(lambda u: "/usr/bin/" + u if u in ima else None),
                         ("Brave", ["brave-browser"]))

    def test_flatpak_in_nic(self):
        self.assertEqual(drm.najdi_brskalnik(lambda u: "/usr/bin/flatpak" if u == "flatpak" else None,
                                             lambda app: app == "com.brave.Browser"),
                         ("Brave", ["flatpak", "run", "com.brave.Browser"]))
        self.assertIsNone(drm.najdi_brskalnik(lambda u: None, lambda app: False))


class Preusmeritev(unittest.TestCase):
    def setUp(self):
        self.ura, self.zagnano = [100.0], []
        self.p = drm.Preusmeritev(najdi=lambda: ("Brave", ["brave-browser"]), zazeni=self.zagnano.append,
                                  ura=lambda: self.ura[0])

    def test_enkrat_na_stran(self):
        self.assertEqual(self.p.odpri("https://www.netflix.com/watch/1"), ("odprto", "Brave"))
        self.assertEqual(self.zagnano, [["brave-browser", "https://www.netflix.com/watch/1"]])
        self.assertEqual(self.p.odpri("https://www.netflix.com/watch/1")[0], "ze")
        self.ura[0] += 31
        self.assertEqual(self.p.odpri("https://www.netflix.com/watch/1")[0], "odprto")

    def test_samo_https(self):
        for url in ("file:///etc/passwd", "http://x.si/", "javascript:alert(1)", ""):
            self.assertEqual(self.p.odpri(url)[0], "neveljavno")
        self.assertEqual(self.zagnano, [])

    def test_brez_brskalnika(self):
        p = drm.Preusmeritev(najdi=lambda: None, zazeni=self.zagnano.append)
        self.assertEqual(p.odpri("https://www.disneyplus.com/")[0], "ni")
        self.assertIn("Brave", drm.besedilo_obvestila("ni", ""))
        self.assertIn("Brave", drm.besedilo_obvestila("odprto", "Brave"))

    def test_skripta_le_widevine_in_playready(self):
        self.assertIn("widevine|playready", drm.SKRIPTA)
        self.assertIn("izvirna.apply(this, arguments)", drm.SKRIPTA)
        self.assertIn('"NotSupportedError"', drm.SKRIPTA)


if __name__ == "__main__":
    unittest.main()
