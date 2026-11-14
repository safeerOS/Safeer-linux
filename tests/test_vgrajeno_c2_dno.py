"""Vgrajeno dno C2 najemnisko vohunske opreme: blokada NEODVISNO od podpisanega feeda (core/adblock.py)."""
import unittest

from core import adblock, scit_gostitelji


class VgrajenoDnoC2(unittest.TestCase):
    def test_stevilo_in_oblika(self):
        # 84 domen iz Zero Breach Toolkit (CC0, commit 3b6e48f0); vse male crke, brez sheme in poti
        self.assertEqual(len(adblock.ZASILNE_MERCENARY_C2), 84)
        for d in adblock.ZASILNE_MERCENARY_C2:
            self.assertEqual(d, d.lower())
            self.assertNotIn("/", d)
            self.assertNotIn(":", d)
            self.assertIn(".", d)

    def test_noben_vnos_ni_googlov_koren_ne_skupni_gostitelj(self):
        # dno obide filter sme_gostitelj: vnos pod googleapis/web.app/... bi ga obsel (slepi pregled 14. 11. 2026)
        for d in adblock.ZASILNE_MERCENARY_C2:
            self.assertEqual(scit_gostitelji.vrsta(d), scit_gostitelji.NAVADEN, d)

    def test_dno_blokira_brez_feeda(self):
        # noben feed ni registriran razen dna: blokada mora veljati
        self.assertTrue(adblock.is_threat_domain("https://awake-wood.io/"))
        self.assertTrue(adblock.is_threat_domain("https://forti.external-muki.com/pot?x=1"))
        self.assertTrue(adblock.is_threat_domain("https://poddomena.awake-wood.io/"))

    def test_kontrola_legitimne_strani_niso_blokirane(self):
        for url in ("https://rtvslo.si/", "https://www.24ur.com/", "https://github.com/", "https://hetq.org/",
                    "https://awake-wood.io.example.org/", "https://notawake-wood.io/"):
            self.assertFalse(adblock.is_threat_domain(url), url)

    def test_kriticna_kategorija_blokira_tudi_na_bancni_strani(self):
        # botnet_c2 je v CRITICAL_THREAT_CATEGORIES: matcher dna deluje tudi, ko je gostitelj »prava banka«
        self.assertEqual(adblock._mercenary_c2_matcher("https://awake-wood.io/"), "botnet_c2")
        self.assertIn("botnet_c2", adblock.CRITICAL_THREAT_CATEGORIES)
        orig = adblock.is_real_bank_host
        adblock.is_real_bank_host = lambda u: True
        try:
            self.assertTrue(adblock.is_threat_domain("https://awake-wood.io/"))
        finally:
            adblock.is_real_bank_host = orig

    def test_matcher_je_registriran_enkrat(self):
        self.assertEqual(adblock._extra_threat_matchers.count(adblock._mercenary_c2_matcher), 1)


if __name__ == "__main__":
    unittest.main()
