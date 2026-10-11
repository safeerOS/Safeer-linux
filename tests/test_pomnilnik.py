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
