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
                    "999.999.999.999", "localhost:", "[TODO]", "010.0.0.1",
                    # 1.0.131 (pregled pomocnika S5, NIZKO; OpenAI krog C): vrata 1-65535, oznake brez »-« na robu,
                    # ne-spletne sheme, 0.0.0.0 in »::«, obmocje IPv6, uporabniski del pri izrecni shemi
                    "primer.si:99999", "primer.si:0", "-primer.si", "primer-.si", "nas-/", "tel:123", "sms:123",
                    "mailto:a@b.si", "0.0.0.0", "0.0.0.0:8000", "[::]", "[fe80::1%eth0]", "[fe80::1%eth0]:80",
                    "https://safeer.si@evil.com", "http://user:pass@a.si", "https://primer.si:99999/", "https://-primer.si/",
                    "http://a b.si", "https:// safeer.si"):
            with self.subTest(niz=niz):
                self.assertFalse(je_spletni_naslov(niz))
                self.assertTrue(naslov_ali_iskanje(niz, DDG).startswith(DDG), niz)

    def test_naslov(self):
        for niz, pricakovano in (("safeer.si", "https://safeer.si"), ("github.com/safeerOS", "https://github.com/safeerOS"),
                                 ("https://test/", "https://test/"), ("http://192.168.0.1/", "http://192.168.0.1/"),
                                 ("localhost:8080", "http://localhost:8080"), ("192.168.0.1", "http://192.168.0.1"),
                                 ("test:3000/pot", "https://test:3000/pot"), ("www.google.si/search?q=a b",
                                                                              None),
                                 ("xn--d1acufc.xn--p1ai", "https://xn--d1acufc.xn--p1ai"), ("šola.si", "https://šola.si"),
                                 ("example.zip", "https://example.zip"), ("localhost", "http://localhost"),
                                 ("[::1]:8080", "http://[::1]:8080"), ("lanacion.com.py", "https://lanacion.com.py"),
                                 ("safeer.si/navodila.md", "https://safeer.si/navodila.md"), ("nas/", "https://nas/"),
                                 ("10.0.0.1:8006", "http://10.0.0.1:8006"), ("printer.lan", "https://printer.lan"),
                                 # 1.0.131: izrecen naslov s presledkom za gostiteljem je naslov, presledek -> %20 (S3)
                                 ("https://safeer.si/reset?token=abc 123", "https://safeer.si/reset?token=abc%20123"),
                                 ("https://primer.si/a b", "https://primer.si/a%20b"),
                                 # IPv4, preslikan v IPv6: http samo za lokalni IPv4 (OpenAI krog C)
                                 ("[::ffff:192.168.0.1]", "http://[::ffff:192.168.0.1]"),
                                 ("[::ffff:8.8.8.8]", "https://[::ffff:8.8.8.8]"),
                                 ("primer.si:65535", "https://primer.si:65535"), ("a-b.si", "https://a-b.si"),
                                 ("https://test:8443/", "https://test:8443/")):
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
                   "a..b", "test.", "printer.lan", "http://192.168.0.1/",
                   # 1.0.131
                   "primer.si:99999", "primer.si:0", "primer.si:65535", "-primer.si", "primer-.si", "a-b.si", "nas-/",
                   "tel:123", "sms:123", "mailto:a@b.si", "test:3000/pot", "0.0.0.0", "0.0.0.0:8000", "[::]",
                   "[fe80::1%eth0]", "[fe80::1%eth0]:80", "[::ffff:192.168.0.1]", "https://safeer.si@evil.com",
                   "http://user:pass@a.si", "https://safeer.si/reset?token=abc 123", "http://a b.si",
                   "https://primer.si:99999/", "https://-primer.si/", "https:// safeer.si"]
        skripta = js[a:b] + "\nconsole.log(JSON.stringify(" + json.dumps(primeri) + ".map(jeSpletniNaslov)));"
        izid = json.loads(subprocess.run([node, "-e", skripta], capture_output=True, text=True, check=True).stdout)
        for niz, js_odlocitev in zip(primeri, izid):
            with self.subTest(niz=niz):
                self.assertEqual(js_odlocitev, je_spletni_naslov(niz), niz)
        self.assertIsNotNone(re.search(r"function vNaslov[\s\S]*?jeSpletniNaslov\(q\)", js[b:]))
        # Neodvisni pregled OpenAI 1.0.130: primerjaj tudi KONCNI naslov (ne le odlocitve) in robne primere.
        c = js.index("function crka(")
        naslovi = ["router.lan:8443?token=x", "router.lan:8443#x", "public.example:8443?token=s", "[2001:db8::1]:8443",
                   "[fe80::1]:80", "[fd00::5]", "172.20.1.1", "172.40.1.1", "8.8.8.8:53", "169.254.1.1",
                   "safeer.si", "localhost:8080", "192.168.0.1",
                   "[::1]:8080", "[::1]", "nas/", "github.com/safeerOS", "https://test/", "lanacion.com.py",
                   "safeer.si..", "[::::]", "[1:2:3:4:5:6:7:8:9]", "10.0.0.1:8006/admin?x=1",
                   # 1.0.131
                   "https://safeer.si/reset?token=abc 123", "https://primer.si/a  b", "[::ffff:192.168.0.1]",
                   "[::ffff:10.1.2.3]:8080", "[::ffff:8.8.8.8]", "tel:123", "0.0.0.0", "primer.si:99999",
                   "https://safeer.si@evil.com", "[fe80::1%eth0]"]
        skripta2 = ("var S = {iskalnik: 'duckduckgo'}; var ISKALNIKI = {duckduckgo: " + json.dumps(DDG) + "};\n"
                    + js[a:c] + "\nconsole.log(JSON.stringify(" + json.dumps(naslovi) + ".map(vNaslov)));")
        izid2 = json.loads(subprocess.run([node, "-e", skripta2], capture_output=True, text=True, check=True).stdout)
        from urllib.parse import unquote_plus
        for niz, js_naslov in zip(naslovi, izid2):
            with self.subTest(koncni=niz):
                py_naslov = naslov_ali_iskanje(niz, DDG)
                if py_naslov.startswith(DDG):      # iskanje: kodiranje presledkov se lahko razlikuje (+ / %20)
                    self.assertTrue(js_naslov.startswith(DDG), (niz, js_naslov))
                    self.assertEqual(unquote_plus(js_naslov[len(DDG):]), unquote_plus(py_naslov[len(DDG):]))
                else:
                    self.assertEqual(js_naslov, py_naslov, niz)
        # Neodvisni pregled OpenAI 1.0.130 (krog B, VISOKA): vrata ne dokazujejo domacega omrezja - brez sheme privzeto https
        # (zeton ne gre nesifriran), http samo za localhost in zasebne/loopback/link-local naslove IP.
        self.assertEqual(naslov_ali_iskanje("router.lan:8443?token=x", DDG), "https://router.lan:8443?token=x")
        self.assertEqual(naslov_ali_iskanje("public.example:8443?token=s", DDG), "https://public.example:8443?token=s")
        self.assertEqual(naslov_ali_iskanje("[2001:db8::1]:8443", DDG), "https://[2001:db8::1]:8443")
        self.assertEqual(naslov_ali_iskanje("192.168.0.1", DDG), "http://192.168.0.1")
        self.assertEqual(naslov_ali_iskanje("localhost:8080", DDG), "http://localhost:8080")
        # 1.0.131: zeton iz izrecnega naslova s presledkom ne gre iskalniku (S3); IPv4 v IPv6 kot IPv4 (krog C)
        self.assertEqual(naslov_ali_iskanje("https://safeer.si/reset?token=abc 123", DDG),
                         "https://safeer.si/reset?token=abc%20123")
        self.assertEqual(naslov_ali_iskanje("[::ffff:10.1.2.3]:8080", DDG), "http://[::ffff:10.1.2.3]:8080")
        self.assertEqual(naslov_ali_iskanje("tel:123", DDG), DDG + "tel%3A123")


if __name__ == "__main__":
    unittest.main()
