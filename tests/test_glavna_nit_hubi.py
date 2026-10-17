"""Glavna nit GTK ne caka na iskanje Hubov (mDNS, 1,5 s).

Oznaka povezave v Spletu se osvezuje vsakih 5 s na glavni niti; na nepovezanem racunalniku je stanje_povezave()
vsakih 10 s cakalo 1,5 s na mDNS - namizje, Splet in Sporocila so zamrznili (zeroconf je na testnem racunalniku)."""
import os
import sys
import threading
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

import safeer_os  # noqa: E402


class IskanjeHubov(unittest.TestCase):
    def setUp(self):
        self.klicev = 0
        self.izpusti = threading.Event()

        def pocasno(cas):
            self.klicev += 1
            self.izpusti.wait(5)
            return [{"naslov": "wss://192.0.2.1:8990/ws", "ime": "TV"}]
        from core import link_hub, link_seja
        for p in (mock.patch.object(link_hub, "poisci_hube_mdns", pocasno),
                  mock.patch.object(link_seja, "povezava_velja", return_value=False),     # nepovezan racunalnik
                  mock.patch.object(link_seja, "zaupana", return_value=False),
                  mock.patch.object(link_seja, "brez_v_seji", return_value=False),
                  mock.patch.dict(safeer_os._hubi_cache, {"cas": 0.0, "hubi": []}),
                  mock.patch.object(safeer_os, "_podatki_controla", return_value={}),
                  mock.patch.object(safeer_os, "_ukaz_controla", return_value=""),
                  mock.patch.object(safeer_os, "_nastavitve_pladnja", return_value={})):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.izpusti.set)

    def _hitro(self, fn):
        zac = time.monotonic()
        izid = fn()
        self.assertLess(time.monotonic() - zac, 0.5)
        return izid

    def test_splet_ne_isce_hubov(self):
        izid = self._hitro(safeer_os._stanje_povezave_spleta)
        self.assertNotEqual(izid["stanje"], "povezan")
        self.assertEqual(self.klicev, 0)

    def test_glavna_nit_dobi_zadnje_znane_iskanje_v_ozadju(self):
        self.assertEqual(self._hitro(lambda: safeer_os.stanje_povezave("ozadje"))["hubi"], [])
        self._hitro(lambda: safeer_os.stanje_povezave("ozadje"))      # se isce: ne zacne drugega iskanja
        self.izpusti.set()
        konec = time.monotonic() + 5
        while not safeer_os._hubi_cache["hubi"] and time.monotonic() < konec:
            time.sleep(0.02)
        self.assertEqual(self.klicev, 1)
        self.assertEqual(self._hitro(lambda: safeer_os.stanje_povezave("ozadje"))["hubi"][0]["ime"], "TV")

    def test_delovna_nit_pocaka(self):
        self.izpusti.set()
        self.assertEqual(safeer_os.stanje_povezave()["hubi"][0]["ime"], "TV")


if __name__ == "__main__":
    unittest.main()
