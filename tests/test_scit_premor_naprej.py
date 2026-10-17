"""Scit: streznik naprej (DoH), ki ne odgovori, ne zadrzi vsakega imena (CI Flatpak, 17. 10. 2026)."""

import time
import unittest
from unittest import mock

from core import os_scit


class TestPremorNaprej(unittest.TestCase):
    def test_po_odpovedi_naravnost_na_usmerjevalnik_nato_spet_poskus(self):
        klici = []

        def naprej(paket):
            klici.append(1)
            time.sleep(10)          # DoH, ki visi dlje od svojega roka
            return None

        r = os_scit.Razresevalnik(lambda ime: None, lambda: [])
        r.naprej = naprej
        with mock.patch.object(os_scit, "CAS_UPSTREAM", 0.2):
            z = time.monotonic()
            r._posreduj(b"\x12\x34" + b"\x00" * 30, False)
            self.assertLess(time.monotonic() - z, 1.0)          # trdi rok
            z = time.monotonic()
            for _ in range(5):
                r._posreduj(b"\x12\x34" + b"\x00" * 30, False)
            self.assertLess(time.monotonic() - z, 0.5)          # med premorom brez cakanja na DoH
            self.assertEqual(len(klici), 1)
            r._brez_naprej_do = 0.0                              # premor mimo: spet poskusi
            r._posreduj(b"\x12\x34" + b"\x00" * 30, False)
            self.assertEqual(len(klici), 2)

    def test_delujoc_naprej_odgovori(self):
        r = os_scit.Razresevalnik(lambda ime: None, lambda: [])
        r.naprej = lambda paket: paket[:2] + b"\x81\x80" + b"\x00" * 8
        self.assertEqual(r._posreduj(b"\x12\x34" + b"\x00" * 10, False)[:2], b"\x12\x34")


if __name__ == "__main__":
    unittest.main()
