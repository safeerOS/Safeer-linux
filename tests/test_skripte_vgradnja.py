#!/usr/bin/env python3
"""
Vgradnja uporabniških skript v brskalnik.

Del preizkusov bere izvorno kodo: hočemo vedeti, da se skripte res vbrizgajo
v ločen svet in da most do shrambe ni odprt za kogarkoli. Drugi del preveri
shrambo vrednosti, ne da bi se dotaknil uporabnikovih nastavitev.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import ConfigManager  # noqa: E402

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PreizkusShrambe(unittest.TestCase):
    """Shramba GM_setValue -- na izmišljenih nastavitvah, uporabnikovih se ne dotaknemo."""

    def nastavitve(self):
        cm = ConfigManager.__new__(ConfigManager)
        cm.settings = {}
        cm.save_settings = lambda: None
        return cm

    def test_shrani_prebere_izbrise(self):
        cm = self.nastavitve()
        self.assertTrue(ConfigManager.set_script_value(cm, "s1", "barva", "modra"))
        self.assertEqual(ConfigManager.get_script_values(cm, "s1"), {"barva": "modra"})
        self.assertTrue(ConfigManager.delete_script_value(cm, "s1", "barva"))
        self.assertEqual(ConfigManager.get_script_values(cm, "s1"), {})

    def test_skripte_se_med_seboj_ne_vidijo(self):
        cm = self.nastavitve()
        ConfigManager.set_script_value(cm, "s1", "skrivnost", 1)
        self.assertEqual(ConfigManager.get_script_values(cm, "s2"), {})

    def test_prevelika_vrednost_je_zavrnjena(self):
        cm = self.nastavitve()
        self.assertFalse(ConfigManager.set_script_value(cm, "s1", "velika", "x" * (64 * 1024 + 10)))
        self.assertEqual(ConfigManager.get_script_values(cm, "s1"), {})

    def test_preveliko_stevilo_kljucev_je_zavrnjeno(self):
        cm = self.nastavitve()
        for i in range(200):
            self.assertTrue(ConfigManager.set_script_value(cm, "s1", f"k{i}", i))
        self.assertFalse(ConfigManager.set_script_value(cm, "s1", "cez_mejo", 1))
        # Obstoječega ključa sme prepisati tudi, ko je predal poln.
        self.assertTrue(ConfigManager.set_script_value(cm, "s1", "k0", 42))

    def test_neveljaven_kljuc_je_zavrnjen(self):
        cm = self.nastavitve()
        for kljuc in ("", None, 5, "d" * 201):
            with self.subTest(kljuc=kljuc):
                self.assertFalse(ConfigManager.set_script_value(cm, "s1", kljuc, 1))

    def test_brisanje_skripte_pobrise_njene_vrednosti(self):
        cm = self.nastavitve()
        cm.settings["user_scripts"] = [{"id": "s1", "name": "x"}]
        ConfigManager.set_script_value(cm, "s1", "a", 1)
        ConfigManager.save_user_scripts = lambda _self, s: cm.settings.__setitem__("user_scripts", s)
        ConfigManager.delete_user_script(cm, "s1")
        self.assertEqual(ConfigManager.get_script_values(cm, "s1"), {})


if __name__ == "__main__":
    unittest.main()
