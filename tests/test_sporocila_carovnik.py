"""Carovnik »Dodaj kanal« na Linuxu (12. 10. 2026): ponudniki z navodili in stranjo za geslo za aplikacije,
aplikacije po skupinah (tudi »Vec kanalov v eni aplikaciji«), Lastni API."""
import os
import re
import unittest

from core.sporocila import ponudniki

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def beri(*pot):
    with open(os.path.join(KOREN, *pot), encoding="utf-8") as d:
        return d.read()


class Ponudniki(unittest.TestCase):
    def test_strani_za_geslo_so_uradne_https(self):
        strani = {p["id"]: p.get("geslo_stran") for p in ponudniki.PONUDNIKI if p.get("geslo_stran")}
        self.assertEqual(strani, {"gmail": "https://myaccount.google.com/apppasswords",
                                  "yahoo": "https://login.yahoo.com/account/security",
                                  "icloud": "https://account.apple.com"})

    def test_aplikacije_po_skupinah(self):
        vrste = {a["vrsta"] for a in ponudniki.APLIKACIJE_SPOROCIL}
        self.assertEqual(vrste, {"posta", "klepet", "vec"})
        vec = [a["ime"] for a in ponudniki.APLIKACIJE_SPOROCIL if a["vrsta"] == "vec"]
        for ime in ("Thunderbird", "Ferdium", "Pidgin", "Delta Chat", "Beeper"):
            self.assertIn(ime, vec)
        for a in ponudniki.APLIKACIJE_SPOROCIL:
            for k in ("splet", "prenos"):
                self.assertTrue(not a[k] or a[k].startswith("https://"), (a["ime"], k))
            self.assertTrue(a["splet"] or a["prenos"], a["ime"])

    def test_vmesnik_in_most(self):
        js, html = beri("assets", "os", "os.js"), beri("assets", "os", "index.html")
        self.assertIn('klic("sporocilaPonudniki")', js)
        self.assertIn('"sporocilaPonudniki":', beri("safeer_os.py"))
        for idn in ("kanalPonudnikiMreza", "kanalAplikacijeMreza", "kanalApi", "kanalStranGesla"):
            self.assertIn('id="%s"' % idn, html)
        self.assertIn('["vec", "kanalAppVec"]', js)
        self.assertNotIn("otvoriSpletnoStran(", js, "na Linuxu odpre spletno stran odpriVSpletu")
        besedila = beri("assets", "os", "besedila.js")
        for k in ("kanalAppVec", "kanalStranGesla", "kanalCipGeslo", "navGmail", "kanalKjeImas"):
            self.assertRegex(besedila, r'"%s"\s*:' % k)


if __name__ == "__main__":
    unittest.main()
