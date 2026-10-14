"""CI poganja preizkuse GTK 3 in GTK 4 v loceni procesih (tools/razdeli_teste.py, 14. 10. 2026)."""
import importlib.util
import os
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("razdeli_teste", os.path.join(KOREN, "tools", "razdeli_teste.py"))
razdeli_teste = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(razdeli_teste)


class Razdelitev(unittest.TestCase):
    def test_skupini(self):
        gtk3, gtk4, oboje = razdeli_teste.razdeli()
        self.assertEqual(oboje, [], "preizkus ne sme uvoziti GTK 3 in GTK 4 hkrati")
        self.assertIn("test_control", gtk4)            # uvozi safeer_control
        self.assertIn("test_packaging", gtk4)          # Safeer OS uvozi v podprocesu
        self.assertIn("test_bank_guard", gtk3)         # brskalnik (safeer_mint, GTK 3)
        self.assertIn("test_razdeli_teste", gtk3)      # brez GTK: tece na obeh
        self.assertFalse(set(gtk3) & set(gtk4))
        vsi = {d[:-3] for d in os.listdir(os.path.join(KOREN, "tests")) if d.startswith("test_") and d.endswith(".py")}
        self.assertEqual(set(gtk3) | set(gtk4), vsi, "noben preizkus ne izpade")


if __name__ == "__main__":
    unittest.main()
