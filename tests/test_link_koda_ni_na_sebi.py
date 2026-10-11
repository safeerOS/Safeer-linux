"""Koda za prijavo se pokaze na drugih napravah, nikoli na tisti, ki jo mora vpisati (lastnik, 11. 10. 2026:
racunalnik, ki gosti Hub, je ob lastni prijavi pokazal isto kodo, kot jo je bilo treba vpisati vanj)."""
import unittest

from core import link_hub_streznik


class KodaNiNaSebi(unittest.TestCase):
    def setUp(self):
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id="n-0123456789abcdef")
        self.pokazane = []
        self.hub.ob_kodi = lambda ime, koda: self.pokazane.append((ime, koda))

    def test_tuja_naprava_kodo_pokaze_tu(self):
        self.assertIn("pair_id", self.hub.zacni_seznanitev("n-ffffffffffffffff-os", "Telefon"))
        self.assertEqual(len(self.pokazane), 1)

    def test_lastna_prijava_kode_ne_pokaze_tu(self):
        for i, naprava in enumerate(("n-0123456789abcdef-control", "n-0123456789abcdef")):
            self.assertIn("pair_id", self.hub.zacni_seznanitev(naprava, "Ta racunalnik %d" % i))
        self.assertEqual(self.pokazane, [])


class PrijavnoOkno(unittest.TestCase):
    def test_lastne_kode_ni_mogoce_vpisati_v_isto_napravo(self):
        import os
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "assets", "link", "link.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn('if (koda.length === 6 && koda === kodaTe) {', js)
        self.assertIn('besedilo(opombaId, t("kodaIstaNaprava"));', js)
        self.assertEqual(js.count('prijavaKodaNaslov: "'), 6)
        self.assertIn('prijavaKodaNaslov: "Vpiši kodo z druge naprave"', js)


if __name__ == "__main__":
    unittest.main()
