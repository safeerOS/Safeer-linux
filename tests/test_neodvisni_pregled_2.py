"""Neodvisni pregled 2 (19. 10. 2026, izvorna koda 1.0.128): vsak popravek ima preizkus, ki brez popravka pade."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_datoteke, link_gledalec, link_neposredno, link_sway  # noqa: E402
from core.sporocila import storitev  # noqa: E402


class GledalecBrezPotrdila(unittest.TestCase):
    def test_strezniku_brez_potrdila_je_napaka_gledalca(self):
        """getpeercert(binary_form=True) vrne None: prej TypeError iz hashlib, zdaj NapakaGledalca."""
        g = object.__new__(link_gledalec.Gledalec)
        g.seja = {"port": 1, "fp": "a" * 64}
        g.cas_povezave = 1.0
        varna = mock.Mock()
        varna.getpeercert.return_value = None
        kontekst = mock.Mock()
        kontekst.wrap_socket.return_value = varna
        with mock.patch.object(link_gledalec.socket, "create_connection", return_value=mock.Mock()), \
                mock.patch.object(link_gledalec.ssl, "SSLContext", return_value=kontekst):
            with self.assertRaises(link_gledalec.NapakaGledalca):
                g._odpri("127.0.0.1", 1.0)


class ImenaTabel(unittest.TestCase):
    def test_samo_dovoljene_tabele(self):
        for ime in ("kanali", "kanal_stanje", "odhodni", "sporocila_polno", "kanal_neprebrano", "oznake", "zvezdice"):
            self.assertEqual(storitev._tabela(ime), ime)
        for ime in ("sporocila; DROP TABLE kanali", "pogovori", "", "Kanali"):
            with self.assertRaises(ValueError):
                storitev._tabela(ime)


class NeposrednoJson(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.d = self._d.name

    def tearDown(self):
        self._d.cleanup()

    def test_branje_brez_datoteke_in_pokvarjeno_tiho(self):
        self.assertEqual(link_neposredno._beri_json(os.path.join(self.d, "ni.json")), {})
        p = os.path.join(self.d, "pokvarjeno.json")
        with open(p, "w") as f:
            f.write("{nedokoncano")
        izpis = io.StringIO()
        with redirect_stdout(izpis):
            self.assertEqual(link_neposredno._beri_json(p), {})
        self.assertEqual(izpis.getvalue(), "")

    def test_druga_napaka_gre_v_dnevnik(self):
        """Mapa namesto datoteke (IsADirectoryError, kot napacne pravice ali disk): prej tiho, zdaj v dnevniku."""
        izpis = io.StringIO()
        with redirect_stdout(izpis):
            self.assertEqual(link_neposredno._beri_json(self.d), {})
        self.assertIn("neposredno: branje", izpis.getvalue())

    def test_pisanje_vrne_izid_in_pospravi(self):
        p = os.path.join(self.d, "nastavitve.json")
        self.assertIs(link_neposredno._pisi_json(p, {"vklopljeno": True}), True)
        with open(p, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"vklopljeno": True})
        izpis = io.StringIO()
        with redirect_stdout(izpis):
            self.assertIs(link_neposredno._pisi_json(p, {"x": object()}), False)   # ni JSON
        self.assertIn("neposredno: pisanje", izpis.getvalue())
        self.assertFalse(os.path.exists(p + ".tmp"), "zacasna datoteka se pospravi")
        with open(p, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"vklopljeno": True}, "neuspelo pisanje ne pokvari prejsnjega")


class NamestitevLocenegaZaslona(unittest.TestCase):
    def test_opis_napake_pove_vzrok(self):
        r = subprocess.CompletedProcess(["pkexec"], 100, stdout="", stderr="E: Unable to locate package sway\n")
        self.assertEqual(link_sway.opis_napake(r), "E: Unable to locate package sway")
        r = subprocess.CompletedProcess(["pkexec"], 126, stdout=b"", stderr=b"x" * 1000)
        self.assertEqual(len(link_sway.opis_napake(r)), 400)
        self.assertEqual(link_sway.opis_napake(subprocess.CompletedProcess([], 1, "", "")), "")

    def test_control_pokaze_vzrok(self):
        with open(os.path.join(KOREN, "safeer_control.py"), encoding="utf-8") as f:
            vir = f.read()
        self.assertIn("link_sway.opis_napake(r)", vir)
        self.assertIn('besedilo(jezik, "locen_napaka") + ("\\n\\n" + opis if opis else "")', vir)


class IndeksDeljeneMape(unittest.TestCase):
    def test_samo_pozitiven_indeks_brez_vodilnih_nicel(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "A"), os.path.join(d, "B")
            os.makedirs(a)
            os.makedirs(b)
            for m in (a, b):
                with open(os.path.join(m, "x.txt"), "w") as f:
                    f.write("x")
            m = link_datoteke.DeljeneMape([a, b])
            self.assertEqual(m.razresi("share:0:x.txt")[1], os.path.realpath(os.path.join(a, "x.txt")))
            self.assertEqual(m.razresi("share:1:x.txt")[1], os.path.realpath(os.path.join(b, "x.txt")))
            for oznaka in ("share:-1:x.txt", "share:-2:x.txt", "share:01:x.txt", "share:+1:x.txt", "share: 1:x.txt"):
                self.assertIsNone(m.razresi(oznaka), oznaka)


if __name__ == "__main__":
    unittest.main()
