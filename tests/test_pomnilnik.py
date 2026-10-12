"""core/pomnilnik.py: omejitev aren, obrezovanje, meja pomnilnika WebKita (brez GTK)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import pomnilnik  # noqa: E402


class Pomnilnik(unittest.TestCase):
    def test_glibc(self):
        self.assertTrue(pomnilnik.omeji_arene(2))
        self.assertTrue(pomnilnik.obrezuj() in (True, False))

    def test_kontekst_brez_podpore(self):
        class W:
            class WebContext:
                def __init__(self, **k):
                    self.k = k
        self.assertEqual(pomnilnik.kontekst(W, 100, website_data_manager="m").k, {"website_data_manager": "m"})

    def test_kontekst_z_mejo(self):
        nastavljeno = []

        class S:
            def set_memory_limit(self, mb):
                nastavljeno.append(mb)

        class W:
            class MemoryPressureSettings:
                @staticmethod
                def new():
                    return S()

            class WebContext:
                def __init__(self, **k):
                    self.k = k
        k = pomnilnik.kontekst(W, 220)
        self.assertEqual(nastavljeno, [220])
        self.assertIn("memory_pressure_settings", k.k)


if __name__ == "__main__":
    unittest.main()


class FilterBrezPretvorbe(unittest.TestCase):
    def test_preskoci_shranjen_seznam(self):
        import tempfile
        from core.filter_lists import FilterListAgent
        d = tempfile.mkdtemp()
        klici = []
        a = FilterListAgent(d, on_rules=lambda p, v: klici.append(v), fetch=lambda *a: (304, b"", "", ""), first_delay=999)
        a._write(b"[Adblock Plus 2.0]\n||oglas.example^\n" * 50, "", "")
        a.skip_saved = True
        a.start(); a.loaded.wait(5); a.stop()
        self.assertEqual(klici, [], "preveden seznam se ob zagonu ne pretvarja znova")
        self.assertEqual(a.list_sha256, a.saved_sha256())


class KompaktenIndeks(unittest.TestCase):
    def test_enako_kot_prej(self):
        from core import signed_feed as f
        i = f.ThreatIndex([("zlo.example", "domain", "phishing", 0), ("sub.zlo.example", "domain", "malware", 0),
                           ("gost.example", "hostname", "botnet_c2", 0), ("https://ok.example/pot", "url", "phishing", 0),
                           ("1.2.3.4", "ipv4", "malware", 0)])
        self.assertEqual(i.match_host("zlo.example"), "phishing")
        self.assertEqual(i.match_host("a.b.zlo.example"), "phishing")
        self.assertEqual(i.match_host("x.sub.zlo.example"), "malware")       # huje zmaga
        self.assertEqual(i.match_host("gost.example"), "botnet_c2")
        self.assertIsNone(i.match_host("x.gost.example"))                     # hostname ni domena
        self.assertIsNone(i.match_host("dobro.example"))
        self.assertEqual(i.match_host("1.2.3.4"), "malware")
        self.assertEqual(i.match_url("https://ok.example/pot"), "phishing")
        self.assertIsNone(i.match_url("https://ok.example/drugo"))
        self.assertEqual(i.match_url("https://WWW.zlo.example/x"), "phishing")
        self.assertEqual(i.size, 5)


class TlakOmrezja(unittest.TestCase):
    def test_nastavi_za_omrezne_procese(self):
        from core import pomnilnik
        klici = []

        class S:
            @staticmethod
            def new():
                return S()

            def set_memory_limit(self, mb):
                klici.append(("meja", mb))

        class WDM:
            @staticmethod
            def set_memory_pressure_settings(s):
                klici.append(("omrezje", type(s).__name__))

        class W:
            MemoryPressureSettings = S
            WebsiteDataManager = WDM
        self.assertTrue(pomnilnik.tlak_omrezja(W, 160))
        self.assertEqual(klici, [("meja", 160), ("omrezje", "S")])

    def test_brez_podpore(self):
        from core import pomnilnik

        class W:
            pass
        self.assertFalse(pomnilnik.tlak_omrezja(W, 160))

    def test_klic_pred_prvim_pogledom(self):
        import os
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for ime in ("safeer_os.py", "safeer_control.py"):
            with open(os.path.join(koren, ime), encoding="utf-8") as f:
                s = f.read()
            self.assertLess(s.index("pomnilnik.tlak_omrezja(WebKit2, 160)"), s.index("WebKit2.WebView("), ime)
