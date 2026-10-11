"""Telefon kot mikrofon za lupo racunalnika (lastnik, 11. 10. 2026): glas na telefonu -> search.query -> lupa
Safeer OS isce niz. Samo iskanje; nic se ne odpre samo od sebe."""
import os
import shutil
import subprocess
import sys
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec, link_dostop  # noqa: E402


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class TestTelefonMikrofon(unittest.TestCase):
    def test_niz_gre_v_safeer_os(self):
        with mock.patch.object(link_daljinec, "_safeer_os", return_value="/usr/bin/safeer-os"), \
                mock.patch("subprocess.Popen") as popen:
            izid = link_daljinec.isci_na_racunalniku("  odpri   nastavitve zaslona ")
        self.assertTrue(izid["ok"])
        self.assertEqual(popen.call_args[0][0], ["/usr/bin/safeer-os", "--isci-naprava", "odpri nastavitve zaslona"])

    def test_meje(self):
        with mock.patch.object(link_daljinec, "_safeer_os", return_value="/usr/bin/safeer-os"), \
                mock.patch("subprocess.Popen") as popen:
            self.assertFalse(link_daljinec.isci_na_racunalniku("   ")["ok"])
            link_daljinec.isci_na_racunalniku("x" * 1000)
            self.assertEqual(len(popen.call_args[0][0][2]), 200)
        with mock.patch.object(link_daljinec, "_safeer_os", return_value=""):
            self.assertEqual(link_daljinec.isci_na_racunalniku("zaslon")["code"], "ni_safeer_os")

    def test_izvedi_control(self):
        izidi = []
        with mock.patch.object(link_daljinec, "_safeer_os", return_value="/usr/bin/safeer-os"), \
                mock.patch("subprocess.Popen"):
            link_daljinec.izvedi_control("search.query", {"q": "zvok"}, lambda u: None, izidi.append)
        self.assertTrue(izidi[0]["ok"])
        self.assertIn('+ (DEJANJA_MAGNET + DEJANJA_SEZNAMI + DEJANJA_ISKANJE if _safeer_os() else [])',
                      beri("core", "link_daljinec.py"))

    def test_dovoljenje(self):
        # Iskanje upravlja racunalnik (pokaze namizje): enako dovoljenje kot tipke in drsenje.
        self.assertEqual(link_dostop.zahteva_dejanja("search.query"), link_dostop.zahteva_dejanja("key"))

    def test_daljinec_poslje_iskanje(self):
        js = beri("assets", "link", "daljinec.js")
        self.assertIn('stanje.isceNaRacunalniku = dejanja.indexOf("search.query") >= 0;', js)
        self.assertIn('ukaz("search.query", { q: cisto }', js)
        self.assertEqual(js.count('iscemNaRacunalniku: "'), 6)

    def test_safeer_os(self):
        py = beri("safeer_os.py")
        self.assertIn('if "--isci-naprava" in sys.argv[1:]:', py)
        self.assertIn('Gio.SimpleAction.new("isci", GLib.VariantType.new("s"))', py)
        self.assertIn('self._dogodek("iskanjeOdDrugod", {"q": niz}, self.pogled_delovna)', py)
        self.assertIn('else if (vrsta === "iskanjeOdDrugod") {', beri("assets", "os", "delovna.js"))

    @unittest.skipUnless(shutil.which("node"), "node ni namescen")
    def test_sintaksa(self):
        subprocess.run(["node", "--check", os.path.join(KOREN, "assets", "link", "daljinec.js")], check=True)


if __name__ == "__main__":
    unittest.main()
