"""Nabiralnik Sporocil na Linuxu: mape, oznake, iskanje pri osebi, pano z osebo (preneseno s Safeer OS za Windows)."""
import re
import unittest
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
OS = KOREN / "assets" / "os"


class NabiralnikMost(unittest.TestCase):
    def test_most_ima_vse_metode(self):
        koda = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
        for metoda, klic in (("sporocilaPreimenuj", "preimenuj_osebo"), ("sporocilaZdruzi", "zdruzi_osebi"),
                             ("sporocilaRazdruzi", "razdruzi_osebo"), ("sporocilaOznake", "nastavi_oznake"),
                             ("sporocilaOsebe", "osebe"), ("sporocilaIsciPri", "isci_pri_osebi")):
            self.assertRegex(koda, r'"%s":[^\n]*self\.sporocila\.%s' % (metoda, klic), metoda)

    def test_zaledje_ima_metode(self):
        import core.os_sporocila as m
        razred = [v for v in vars(m).values() if isinstance(v, type) and hasattr(v, "isci_pri_osebi")]
        self.assertTrue(razred)
        for ime in ("preimenuj_osebo", "zdruzi_osebi", "razdruzi_osebo", "nastavi_oznake", "osebe", "isci_pri_osebi"):
            self.assertTrue(hasattr(razred[0], ime), ime)


class NabiralnikVmesnik(unittest.TestCase):
    def setUp(self):
        self.html = (OS / "index.html").read_text(encoding="utf-8")
        self.js = (OS / "os.js").read_text(encoding="utf-8")
        self.css = (OS / "os.css").read_text(encoding="utf-8")

    def test_elementi_obstajajo(self):
        for i in ("sporocilaMape", "sporocilaOznake", "sporocilaIskanje", "sporocilaFiltri", "sporocilaPano",
                  "sporocilaPanoVsebina", "sporocilaPodnaslov", "panoIskanjeVnos", "panoZadetki", "panoOznakaObrazec",
                  "panoPreimenuj", "panoZdruzi", "slojOseba", "obrazecOseba", "osebaIme", "osebaIzbira", "sporocilaMeni"):
            self.assertIn('id="%s"' % i, self.html, i)
        # vsak id samo enkrat
        for i in re.findall(r'id="([^"]+)"', self.html):
            self.assertEqual(self.html.count('id="%s"' % i), 1, i)

    def test_js_klice_most_in_ohrani_kopiranje(self):
        for m in ("sporocilaIsciPri", "sporocilaOznake", "sporocilaPreimenuj", "sporocilaZdruzi", "sporocilaRazdruzi"):
            self.assertIn('klic("%s"' % m, self.js, m)
        for f in ("pogovorUstreza", "narisiPano", "narisiOznakeMape", "isciPriOsebi", "odpriOsebaSloj",
                  "mehurcekSporocila", "pokaziMeniSporocila", "odpriCakajociPogovor"):
            self.assertIn("function %s(" % f, self.js, f)
        # Linux ohrani pametno osvezevanje mehurckov (izbor besedila in meni se ne podreta)
        self.assertIn("nacrtMehurckov(cilj, seznam)", self.js)
        self.assertIn('naloziVsebinoPogovora(pogovor, true)', self.js)

    def test_zadetek_iskanja_ne_trci_z_zadetkom_iskalnika(self):
        self.assertIn("zadetek-iskanja", self.js)
        self.assertNotIn('.mehurcek.zadetek {', self.css)
        self.assertIn("#slojOseba .plosca", self.css)


if __name__ == "__main__":
    unittest.main()
