"""Zakon solidarnosti: racunalnik pove svojo moc in ali sme pomagati (core/link_daljinec.py)."""
import os
import shutil
import sys
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec as l  # noqa: E402


def _napajanje(koren, ime, **datoteke):
    os.makedirs(os.path.join(koren, ime))
    for k, v in datoteke.items():
        with open(os.path.join(koren, ime, k), "w") as d:
            d.write(v)


class Solidarnost(unittest.TestCase):
    def setUp(self):
        self.koren = tempfile.mkdtemp(prefix="safeer-napajanje-")
        l._POMAGA["zadnje"] = True

    def tearDown(self):
        shutil.rmtree(self.koren, ignore_errors=True)

    def test_baterija_prenosnika(self):
        _napajanje(self.koren, "ACAD", type="Mains", online="0")
        _napajanje(self.koren, "BAT1", type="Battery", capacity="57", status="Discharging")
        self.assertEqual(l.baterija(self.koren), {"raven": 57, "polni": False})
        with open(os.path.join(self.koren, "ACAD", "online"), "w") as d:
            d.write("1")
        self.assertEqual(l.baterija(self.koren), {"raven": 57, "polni": True})  # na omrezju = kot polnjenje

    def test_namizni_brez_baterije(self):
        _napajanje(self.koren, "ACAD", type="Mains", online="1")
        self.assertEqual(l.baterija(self.koren), {})
        self.assertEqual(l.baterija(os.path.join(self.koren, "ni")), {})

    def test_pomoc_z_mejama(self):
        prosto = lambda m, v: ""  # noqa: E731
        self.assertTrue(l.pomoc({"raven": 45, "polni": False}, prosto)["lahko"])
        self.assertTrue(l.pomoc({"raven": 35, "polni": False}, prosto)["lahko"])   # med 30 in 40: ostane, kot je bilo
        self.assertEqual(l.pomoc({"raven": 29, "polni": False}, prosto), {"lahko": False, "razlog": "baterija"})
        self.assertFalse(l.pomoc({"raven": 35, "polni": False}, prosto)["lahko"])  # pod 40 se ne vrne
        self.assertTrue(l.pomoc({"raven": 35, "polni": True}, prosto)["lahko"])    # polnjenje vedno
        self.assertTrue(l.pomoc({"raven": 41, "polni": False}, prosto)["lahko"])
        self.assertTrue(l.pomoc({}, prosto)["lahko"])                               # namizni
        self.assertEqual(l.pomoc({}, lambda m, v: "preobremenjen"), {"lahko": False, "razlog": "preobremenjen"})

    def test_host_info_ima_pomoc(self):
        p = l.podatki_hosta()
        self.assertEqual(p["vrsta"], "racunalnik")
        self.assertIn(p["pomoc"]["lahko"], (True, False))


if __name__ == "__main__":
    unittest.main()
