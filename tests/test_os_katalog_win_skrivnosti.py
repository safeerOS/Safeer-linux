"""Gesla osebnih streznikov Medijskega centra na Windows (22. 11. 2026): Upravitelj poverilnic prek core/sporocila/skrivnosti,
ne libsecret (ga na Windows ni). Skupna koda Linux -> Windows (core/os_katalog.py)."""
import unittest
from unittest import mock

from core import os_katalog


class WinSkrivnosti(unittest.TestCase):
    def setUp(self):
        self.shramba = {}
        lazne = mock.Mock()
        lazne.shrani.side_effect = lambda k, v: self.shramba.__setitem__(k, v) or True
        lazne.preberi.side_effect = lambda k: self.shramba.get(k)
        lazne.pozabi.side_effect = lambda k: self.shramba.pop(k, None)
        self.lazne = lazne
        for p in (mock.patch.object(os_katalog.sys, "platform", "win32"),
                  mock.patch.object(os_katalog, "_win_skrivnosti", lambda: lazne),
                  mock.patch.object(os_katalog, "_zbirka", side_effect=AssertionError("libsecret na Windows"))):
            p.start()
            self.addCleanup(p.stop)

    def test_shrani_preberi_pozabi(self):
        oznaka = os_katalog.skrij("geslo123")
        self.assertTrue(oznaka.startswith("zbirka:"))
        kljuc = os_katalog._PREDPONA_WIN + oznaka[len("zbirka:"):]
        self.assertEqual(self.shramba, {kljuc: "geslo123"})       # v nastavitvah samo oznaka, geslo v shrambi
        self.assertEqual(os_katalog.razkrij(oznaka), "geslo123")
        os_katalog.pozabi(oznaka)
        self.assertEqual(self.shramba, {})
        with self.assertRaises(RuntimeError):
            os_katalog.razkrij(oznaka)

    def test_neuspesen_zapis_ni_tiho(self):
        self.lazne.shrani.side_effect = lambda k, v: False
        with self.assertRaises(RuntimeError):
            os_katalog.skrij("geslo")

    def test_prazno_in_tuja_oznaka(self):
        self.assertEqual(os_katalog.skrij(""), "")
        self.assertEqual(os_katalog.razkrij(""), "")
        with self.assertRaises(RuntimeError):
            os_katalog.razkrij("navadno-besedilo")
        os_katalog.pozabi("navadno-besedilo")                     # tuja oznaka: nic
        self.lazne.pozabi.assert_not_called()


if __name__ == "__main__":
    unittest.main()
