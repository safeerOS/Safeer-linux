"""Namizje QML sledi zamenjavi primarnega zaslona (prenosnik na TV prek HDMI: eDP ugasne, HDMI postane primarni).

Prej je bila povezana samo geometrija zacetnega zaslona, zato je namizje ostalo 1920x1080 na TV 2560x1440 (18. 10. 2026)."""

import pathlib
import unittest

KOREN = pathlib.Path(__file__).resolve().parents[1]


class MenjavaZaslona(unittest.TestCase):
    def setUp(self):
        self.lupina = (KOREN / "core" / "os_lupina.py").read_text(encoding="utf-8")
        self.os = (KOREN / "safeer_os.py").read_text(encoding="utf-8")

    def test_sledi_menjavi_primarnega_zaslona(self):
        for signal in ("primaryScreenChanged", "screenAdded", "screenRemoved"):
            self.assertIn("aplikacija.%s.connect" % signal, self.lupina)

    def test_signali_na_trenutnem_zaslonu(self):
        self.assertIn("def _spremljaj_zaslon", self.lupina)
        self.assertNotIn("_robovi_povezani", self.lupina)

    def test_gtk_sprememba_postavi_tudi_dock(self):
        self.assertIn("self._ob_spremembi_zaslonov(lupina._zaslon_spremenjen)", self.os)


if __name__ == "__main__":
    unittest.main()
