# -*- coding: utf-8 -*-
"""Skok po gumbih s krizcem (core/link_fokus.py): izbira naslednjega elementa v smeri."""
import unittest

from core.link_fokus import izberi


def gumb(x, y):
    return (float(x), float(y), x - 10, y - 10, 20, 20)


# Mreza 3 x 3 kot tipkovnica kalkulatorja, razmik 100.
MREZA = [gumb(x, y) for y in (100, 200, 300) for x in (100, 200, 300)]


class Izbira(unittest.TestCase):
    def test_sosed_v_vsaki_smeri(self):
        sredina = (200.0, 200.0)
        self.assertEqual(izberi(MREZA, sredina, "desno")[:2], (300.0, 200.0))
        self.assertEqual(izberi(MREZA, sredina, "levo")[:2], (100.0, 200.0))
        self.assertEqual(izberi(MREZA, sredina, "gor")[:2], (200.0, 100.0))
        self.assertEqual(izberi(MREZA, sredina, "dol")[:2], (200.0, 300.0))

    def test_na_robu_ni_skoka(self):
        self.assertIsNone(izberi(MREZA, (300.0, 200.0), "desno"))

    def test_raje_v_isti_vrsti_kot_diagonalno(self):
        elementi = [gumb(260, 120), gumb(330, 200)]
        self.assertEqual(izberi(elementi, (200.0, 200.0), "desno")[:2], (330.0, 200.0))

    def test_desno_ne_zamenja_vrste(self):
        """Na koncu vrste desno ne skoci v drugo vrsto; tja gre uporabnik s tipko dol."""
        self.assertIsNone(izberi([gumb(230, 50)], (200.0, 200.0), "desno"))
        self.assertIsNone(izberi([gumb(260, 240)], (200.0, 200.0), "levo"))

    def test_vrsta_z_razlicno_visokimi_elementi(self):
        visok = (300.0, 200.0, 280, 170, 40, 60)          # sega od 170 do 230
        self.assertEqual(izberi([visok], (200.0, 205.0), "desno")[:2], (300.0, 200.0))

    def test_gor_tudi_izven_stozca(self):
        """Gor in dol najdeta element tudi zamaknjen vstran, ce drugega ni."""
        self.assertEqual(izberi([gumb(400, 150)], (200.0, 200.0), "gor")[:2], (400.0, 150.0))

    def test_neznana_smer(self):
        self.assertIsNone(izberi(MREZA, (200.0, 200.0), "naprej"))


if __name__ == "__main__":
    unittest.main()
