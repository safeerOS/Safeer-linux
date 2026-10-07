"""Prisilni temni način Safeer Browserja (uporabniški slog z barvnim filtrom): stran mora biti po njem temna in berljiva.

Tretji neodvisni pregled, 7. 10. 2026 - izmerjeno v WebKitGTK 2.52.6 (preizkusni zabojnik, štiri vrste strani brez
svojega ozadja): filter na korenskem elementu obrne tudi njegovo ozadje. Slog je ozadje nastavil na »temno« #121212, ki
je bilo po filtru svetlo (#d0d0d0); privzeto črno besedilo je po filtru svetlo (#dddddd) - stran brez svojega ozadja je
bila svetla s svetlim besedilom. Stran s temno barvno shemo (belo privzeto besedilo) je bila po filtru svetla s temnim
besedilom - »temni način« jo je posvetlil. Osnova pogleda (bela ali temna) pri tem nima vloge.
"""
import re
import unittest

from core import adblock


def po_filtru(siva: int) -> int:
    """Siva vrednost 0..255 po filtru iz sloga: invert(90%) in contrast(92%) (zasuk odtenka sivin ne spremeni)."""
    v = siva / 255.0
    v = v * (1 - 2 * 0.9) + 0.9
    v = (v - 0.5) * 0.92 + 0.5
    return round(v * 255)


class Slog(unittest.TestCase):
    def setUp(self):
        self.css = adblock.FORCE_DARK_MODE_CSS
        self.koren = re.search(r"html\s*\{([^}]*)\}", self.css).group(1)

    def test_filter_kot_izmerjen(self):
        self.assertIn("filter: invert(90%) hue-rotate(180deg) contrast(92%) !important;", self.koren)
        self.assertEqual(po_filtru(0x12), 0xd0)       # izmerjeno: prejšnje »temno« ozadje je bilo po filtru #d0d0d0
        self.assertEqual(po_filtru(0x00), 0xdd)       # izmerjeno: privzeto črno besedilo je po filtru #dddddd

    def test_ozadje_pred_filtrom_je_belo(self):
        m = re.search(r"background-color:\s*#([0-9a-fA-F]{6})\s*!important", self.koren)
        self.assertIsNotNone(m, "ozadje korenskega elementa mora biti določeno (stran ga morda nima)")
        barva = m.group(1).lower()
        self.assertEqual(barva, "ffffff")
        self.assertLess(po_filtru(int(barva[:2], 16)), 0x30, "po filtru temno")
        self.assertGreater(po_filtru(0) - po_filtru(int(barva[:2], 16)), 150, "privzeto besedilo je na njem berljivo")

    def test_barvna_shema_strani_je_svetla(self):
        # Stran s temno shemo ima belo privzeto besedilo in temno osnovo; filter bi oboje obrnil v svetlo stran.
        self.assertRegex(self.koren, r"color-scheme:\s*light\s*!important")

    def test_slike_se_obrnejo_nazaj(self):
        self.assertRegex(self.css, r"img, video, canvas[^{]*\{\s*filter: invert\(100%\) hue-rotate\(180deg\) !important;")


if __name__ == "__main__":
    unittest.main()
