"""Enotski testi za upravljanje bližnjic v Cinnamonu (core/os_cinnamon_tipke.py)."""
import unittest
from unittest import mock

from core import os_cinnamon_tipke


class LazneNastavitve:
    def __init__(self, zacetne=None):
        self._podatki = dict(zacetne or {})

    def get_strv(self, kljuc):
        return list(self._podatki.get(kljuc, []))

    def set_strv(self, kljuc, vrednost):
        self._podatki[kljuc] = list(vrednost)

    def get_string(self, kljuc):
        return str(self._podatki.get(kljuc, ""))

    def set_string(self, kljuc, vrednost):
        self._podatki[kljuc] = str(vrednost)


class TestCinnamonTipke(unittest.TestCase):
    def setUp(self):
        self.nastavitve = {}

    def _dobi_ali_ustvari(self, shema, pot=None):
        kljuc = (shema, pot)
        if kljuc not in self.nastavitve:
            if shema == os_cinnamon_tipke.WM_SCHEMA:
                self.nastavitve[kljuc] = LazneNastavitve({"switch-input-source": ["<Super>space", "XF86Keyboard"]})
            elif shema == os_cinnamon_tipke.PARENT_SCHEMA:
                self.nastavitve[kljuc] = LazneNastavitve({"custom-list": []})
            else:
                self.nastavitve[kljuc] = LazneNastavitve()
        return self.nastavitve[kljuc]

    def test_idempotentnost_in_razresitev_spora(self):
        with mock.patch("gi.repository.Gio.Settings.new", side_effect=lambda s: self._dobi_ali_ustvari(s)), \
             mock.patch("gi.repository.Gio.Settings.new_with_path", side_effect=lambda s, p: self._dobi_ali_ustvari(s, p)):

            # 1. Prvi zagon
            uspeh1 = os_cinnamon_tipke.nastavi_globalno_bliznjico("Safeer Iskanje", "safeer-os --iskanje", ["<Super>space"])
            self.assertTrue(uspeh1)

            parent = self._dobi_ali_ustvari(os_cinnamon_tipke.PARENT_SCHEMA)
            self.assertEqual(parent.get_strv("custom-list"), ["custom0"])

            c0 = self._dobi_ali_ustvari(os_cinnamon_tipke.CUSTOM_SCHEMA, "/org/cinnamon/desktop/keybindings/custom-keybindings/custom0/")
            self.assertEqual(c0.get_string("name"), "Safeer Iskanje")
            self.assertEqual(c0.get_string("command"), "safeer-os --iskanje")
            self.assertEqual(c0.get_strv("binding"), ["<Super>space"])

            # Preverba, da je bil spor s stikalom tipkovnice odstranjen
            wm = self._dobi_ali_ustvari(os_cinnamon_tipke.WM_SCHEMA)
            self.assertEqual(wm.get_strv("switch-input-source"), ["XF86Keyboard"])

            # 2. Drugi zagon (idempotentnost: točno 1 vnos v custom-list)
            uspeh2 = os_cinnamon_tipke.nastavi_globalno_bliznjico("Safeer Iskanje", "safeer-os --iskanje", ["<Super>space"])
            self.assertTrue(uspeh2)
            self.assertEqual(parent.get_strv("custom-list"), ["custom0"])

    def test_uporabnikove_bliznjice_ne_prepise(self):
        with mock.patch("gi.repository.Gio.Settings.new", side_effect=lambda s: self._dobi_ali_ustvari(s)), \
             mock.patch("gi.repository.Gio.Settings.new_with_path", side_effect=lambda s, p: self._dobi_ali_ustvari(s, p)):

            # Nastavimo prvič
            os_cinnamon_tipke.nastavi_globalno_bliznjico("Safeer Iskanje", "safeer-os --iskanje", ["<Super>space"])

            # Uporabnik spremeni bližnjico na <Alt>F2
            c0 = self._dobi_ali_ustvari(os_cinnamon_tipke.CUSTOM_SCHEMA, "/org/cinnamon/desktop/keybindings/custom-keybindings/custom0/")
            c0.set_strv("binding", ["<Alt>F2"])

            # Ponovni zagon teme ob prijavi
            os_cinnamon_tipke.nastavi_globalno_bliznjico("Safeer Iskanje", "safeer-os --iskanje", ["<Super>space"])

            # Uporabnikova bližnjica mora ostati nespremenjena
            self.assertEqual(c0.get_strv("binding"), ["<Alt>F2"])


if __name__ == "__main__":
    unittest.main()
