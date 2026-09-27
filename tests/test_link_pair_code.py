"""Posredovanje kode nove naprave iz Safeer Linka v Safeer Control."""
import os
import sys
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import safeer_link  # noqa: E402


class PairCode(unittest.TestCase):
    def setUp(self):
        self.link = safeer_link.SafeerLink.__new__(safeer_link.SafeerLink)
        self.odzivi = []
        self.link._odziv = lambda vrsta, podatki: self.odzivi.append((vrsta, podatki))

    def test_pair_code_posreduje_kodo_cas_in_obvestilo(self):
        sporocilo = {"type": "pair.code", "payload": {
            "pair_id": "par-1", "name": "Telefon", "code": "123456", "expires_in_seconds": 180,
        }}
        with mock.patch.object(safeer_link.link_hub_streznik, "_obvestilo_kode") as obvestilo:
            self.link._na_sporocilo_huba(sporocilo)

        self.assertEqual(self.odzivi, [("kodaPrijave", {
            "id": "par-1", "ime": "Telefon", "koda": "123456", "velja": 180,
        })])
        obvestilo.assert_called_once_with("Telefon", "123456")

    def test_neveljavna_koda_se_ne_posreduje(self):
        with mock.patch.object(safeer_link.link_hub_streznik, "_obvestilo_kode") as obvestilo:
            self.link._na_sporocilo_huba({"type": "pair.code", "payload": {"code": "12x456"}})
        self.assertEqual(self.odzivi, [])
        obvestilo.assert_not_called()

    def test_pair_done_skrije_pravo_kodo(self):
        self.link._na_sporocilo_huba({"type": "pair.done", "payload": {"pair_id": "par-1"}})
        self.assertEqual(self.odzivi, [("kodaPrijave", {"id": "par-1", "koncano": True})])


if __name__ == "__main__":
    unittest.main()
