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

    def test_pocasen_naprej_ne_preseze_roka_resolved(self):
        """CI 8ac36e9: DoH je odgovarjal 2,5 s, systemd-resolved (rok ~750 ms) je presel na usmerjevalnik mimo Scita.
        Odgovor mora priti v ROK_NAPREJ (+ usmerjevalnik); pocasen, a delujoc DoH ne sprozi premora."""
        def naprej(paket):
            time.sleep(1.0)
            return paket[:2] + b"\x81\x80" + b"\x00" * 8

        r = os_scit.Razresevalnik(lambda ime: None, lambda: [])
        r.naprej = naprej
        with mock.patch.object(r, "_vprasaj_usmerjevalnik", return_value=b"\x12\x34usmerjevalnik"):
            z = time.monotonic()
            odgovor = r._posreduj(b"\x12\x34" + b"\x00" * 30, False)
            self.assertLess(time.monotonic() - z, 0.7)
        self.assertEqual(odgovor, b"\x12\x34usmerjevalnik")
        time.sleep(1.2)                                          # DoH je odgovoril v ozadju
        self.assertEqual(getattr(r, "_brez_naprej_do", 0.0), 0.0, "delujoc DoH ne gre v premor")

    def test_mnogo_hkratnih_hitrih_ne_sprozi_premora(self):
        """Neodvisni pregled 19. 10. 2026: meja 8 hkratnih poizvedb je ze ob nalaganju navadne strani (5 imen x A in
        AAAA) za 30 s preklopila DNS na nesifrirano. Delujoc DoH, 20 hkratnih poizvedb: vse dobijo odgovor DoH."""
        import threading

        def naprej(paket):
            time.sleep(0.15)
            return paket[:2] + b"\x81\x80" + b"\x00" * 8

        r = os_scit.Razresevalnik(lambda ime: None, lambda: [])
        r.naprej = naprej
        odgovori = []
        with mock.patch.object(r, "_vprasaj_usmerjevalnik", return_value=b"\x12\x34usmerjevalnik"):
            niti = [threading.Thread(target=lambda: odgovori.append(r._posreduj(b"\x12\x34" + b"\x00" * 30, False)))
                    for _ in range(20)]
            for n in niti:
                n.start()
            for n in niti:
                n.join(5)
        self.assertEqual(len(odgovori), 20)
        self.assertNotIn(b"\x12\x34usmerjevalnik", odgovori, "nobena poizvedba ne gre mimo Scita")
        self.assertEqual(getattr(r, "_brez_naprej_do", 0.0), 0.0, "delujoc DoH ne gre v premor")

    def test_prekrivajoce_poizvedbe_ne_sprozijo_premora(self):
        """Brskanje: poizvedbe se prekrivajo ves cas (stevilo cakajocih nikoli ne pade na 0). Prej je cas cakanja tekel
        od prve poizvedbe in po CAS_UPSTREAM sprozil premor, ceprav je vsaka dobila odgovor v 0,15 s."""
        import threading

        def naprej(paket):
            time.sleep(0.15)
            return paket[:2] + b"\x81\x80" + b"\x00" * 8

        r = os_scit.Razresevalnik(lambda ime: None, lambda: [])
        r.naprej = naprej
        odgovori = []
        with mock.patch.object(os_scit, "CAS_UPSTREAM", 0.4), \
                mock.patch.object(r, "_vprasaj_usmerjevalnik", return_value=b"\x12\x34usmerjevalnik"):
            niti = []
            konec = time.monotonic() + 1.2
            while time.monotonic() < konec:
                n = threading.Thread(target=lambda: odgovori.append(r._posreduj(b"\x12\x34" + b"\x00" * 30, False)))
                n.start()
                niti.append(n)
                time.sleep(0.05)
            for n in niti:
                n.join(5)
        self.assertNotIn(b"\x12\x34usmerjevalnik", odgovori)
        self.assertEqual(getattr(r, "_brez_naprej_do", 0.0), 0.0)

    def test_delujoc_naprej_odgovori(self):
        r = os_scit.Razresevalnik(lambda ime: None, lambda: [])
        r.naprej = lambda paket: paket[:2] + b"\x81\x80" + b"\x00" * 8
        self.assertEqual(r._posreduj(b"\x12\x34" + b"\x00" * 10, False)[:2], b"\x12\x34")


if __name__ == "__main__":
    unittest.main()
