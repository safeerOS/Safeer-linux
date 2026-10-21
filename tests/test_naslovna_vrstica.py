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
                    "a..b", ".si", "test.", "1.2.3", "router", "safeer os linux", "point.md", "readme.md",
                    "999.999.999.999", "localhost:", "[TODO]", "010.0.0.1"):
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
                                 ("[::1]:8080", "http://[::1]:8080"), ("lanacion.com.py", "https://lanacion.com.py"),
                                 ("safeer.si/navodila.md", "https://safeer.si/navodila.md"), ("nas/", "https://nas/"),
                                 ("10.0.0.1:8006", "http://10.0.0.1:8006"), ("printer.lan", "https://printer.lan")):
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


    def test_zacetna_stran_spleta_isto_pravilo(self):
        """Pregled pomocnika 1.0.130 (S2): iskalno polje zacetne strani Spleta (ui/splet.js) je imelo svoje pravilo
        (»racun.pdf« -> https://racun.pdf, »intranet:8080« -> iskanje). Obe izvedbi se morata odlocati enako."""
        import json
        import re
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("ni node")
        koren = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        js = open(os.path.join(koren, "ui", "splet.js"), encoding="utf-8").read()
        a = js.index("var KONCNICE_NE_DOMENE")
        b = js.index("function vNaslov")
        primeri = ["test", "vreme ljubljana", "python 3.12", "3.12", "racun.pdf", "point.md", "lanacion.com.py",
                   "safeer.si", "safeer.si/navodila.md", "github.com/safeerOS", "https://test/", "localhost:8080",
                   "localhost:", "localhost", "192.168.0.1", "999.999.999.999", "010.0.0.1", "10.0.0.1:8006",
                   "[::1]", "[::1]:8080", "[TODO]", "nas/", "intranet:8080", "?safeer.si", "ime@posta.si",
                   "javascript:alert(1)", "about:blank", "šola.si", "xn--d1acufc.xn--p1ai", "example.zip", "c++",
                   "a..b", "test.", "printer.lan", "http://192.168.0.1/"]
        skripta = js[a:b] + "\nconsole.log(JSON.stringify(" + json.dumps(primeri) + ".map(jeSpletniNaslov)));"
        izid = json.loads(subprocess.run([node, "-e", skripta], capture_output=True, text=True, check=True).stdout)
        for niz, js_odlocitev in zip(primeri, izid):
            with self.subTest(niz=niz):
                self.assertEqual(js_odlocitev, je_spletni_naslov(niz), niz)
        self.assertIsNotNone(re.search(r"function vNaslov[\s\S]*?jeSpletniNaslov\(q\)", js[b:]))


if __name__ == "__main__":
    unittest.main()
