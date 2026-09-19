"""Podatki o racunalniku (host.info): kaj televizor izve o moci racunalnika."""
import os
import sys
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec  # noqa: E402


class PodatkiHosta(unittest.TestCase):
    def test_vsebuje_zmogljivost_in_nic_osebnega(self):
        p = link_daljinec.podatki_hosta()
        self.assertIn("cpu", p)
        self.assertIn("ram", p)
        self.assertGreater(p["ram"]["skupaj"], 0)
        self.assertGreaterEqual(p["ram"]["skupaj"], p["ram"].get("prosto", 0))
        self.assertIn("disk", p)
        self.assertGreater(p["disk"]["skupaj"], 0)
        self.assertGreaterEqual(p["disk"]["skupaj"], p["disk"]["prosto"])
        self.assertGreaterEqual(p["cpu"].get("jedra", 0), 1)
        # Poti, imena map ali uporabnisko ime niso del odgovora.
        besedilo = str(p)
        self.assertNotIn(os.path.expanduser("~"), besedilo)

    def test_ukaz_vrne_podatke(self):
        izidi = []
        link_daljinec.izvedi_control("host.info", {}, lambda _u: None, izidi.append)
        i = izidi[0]
        self.assertTrue(i["ok"])
        self.assertIn("ram", i["data"])

    def test_stanje_nasteje_host_info(self):
        izidi = []
        link_daljinec.izvedi_control("status", {}, lambda _u: None, izidi.append)
        self.assertIn("host.info", izidi[0]["data"]["actions"])


if __name__ == "__main__":
    unittest.main()
