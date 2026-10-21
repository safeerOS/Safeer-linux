"""Naslovna vrstica Spleta in Safeer Browserja je tudi iskalno polje (lastnik 21. 10. 2026: »test« je odprl
https://test/ - »Strani trenutno ni mogoče odpreti« - namesto iskanja)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.config import je_spletni_naslov, naslov_ali_iskanje  # noqa: E402

DDG = "https://duckduckgo.com/?q="


class TestNaslovnaVrstica(unittest.TestCase):
    def test_iskanje(self):
        for niz in ("test", "vreme", "vreme ljubljana", "python 3.12", "3.12", "racun.pdf", "izvid krvi.pdf",
                    "slika.JPG", "?safeer.si", "ime@posta.si", "kaj je safeer", "c++", "about:blank", "javascript:alert(1)",
                    "a..b", ".si", "test.", "1.2.3", "router", "safeer os linux"):
            with self.subTest(niz=niz):
                self.assertFalse(je_spletni_naslov(niz))
                self.assertTrue(naslov_ali_iskanje(niz, DDG).startswith(DDG), niz)

    def test_naslov(self):
        for niz, pricakovano in (("safeer.si", "https://safeer.si"), ("github.com/safeerOS", "https://github.com/safeerOS"),
                                 ("https://test/", "https://test/"), ("http://192.168.0.1/", "http://192.168.0.1/"),
                                 ("localhost:8080", "http://localhost:8080"), ("192.168.0.1", "https://192.168.0.1"),
                                 ("test:3000/pot", "http://test:3000/pot"), ("www.google.si/search?q=a b",
                                                                              None),
                                 ("xn--d1acufc.xn--p1ai", "https://xn--d1acufc.xn--p1ai"), ("šola.si", "https://šola.si"),
                                 ("example.zip", "https://example.zip"), ("localhost", "https://localhost"),
                                 ("[::1]:8080", "http://[::1]:8080")):
            with self.subTest(niz=niz):
                if pricakovano is None:            # presledek: vedno iskanje, tudi ce je spredaj domena
                    self.assertFalse(je_spletni_naslov(niz))
                    continue
                self.assertTrue(je_spletni_naslov(niz))
                self.assertEqual(naslov_ali_iskanje(niz, DDG), pricakovano)

    def test_vprasaj_spredaj_isce_brez_vprasaja(self):
        self.assertEqual(naslov_ali_iskanje("?safeer.si", DDG), DDG + "safeer.si")
        self.assertEqual(naslov_ali_iskanje("  vreme ljubljana ", DDG), DDG + "vreme+ljubljana")
        self.assertEqual(naslov_ali_iskanje("   ", DDG), "")

    def test_splet_uporablja_naslov_ali_iskanje(self):
        """Splet (core/os_splet.VdelaniSplet._vnesi_naslov) ne sme vec klicati samo normalize_web_url na vpisu."""
        koren = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        vir = open(os.path.join(koren, "core", "os_splet.py"), encoding="utf-8").read()
        zacetek = vir.index("def _vnesi_naslov")
        telo = vir[zacetek:vir.index("\n    def ", zacetek + 10)]
        self.assertIn("naslov_ali_iskanje(", telo)
        self.assertNotIn("normalize_web_url(besedilo)", telo)


if __name__ == "__main__":
    unittest.main()
