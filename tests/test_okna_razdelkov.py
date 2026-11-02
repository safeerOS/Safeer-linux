"""Razdelki odprejo svoja okna in Usenet je viden v Medijskem centru (lastnik 2. 11. 2026 04:24-05:16)."""
import os
import re
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class OknaRazdelkov(unittest.TestCase):
    def test_glavno_okno_odpre_predvajalnik_in_okna_razdelkov(self):
        js = beri("assets", "os", "os.js")
        self.assertIn('S.zacetek.mostOkna && !EN_RAZDELEK', js, "samo glavno okno preusmeri (ne okno razdelka samo nase)")
        self.assertIn('klic("odpriPredvajalnik", [])', js)
        self.assertIn('klic("odpriOknoRazdelka", [razdelek])', js)

    def test_most_ima_metodi(self):
        py = beri("safeer_os.py")
        self.assertIn('"odpriOknoRazdelka": lambda: self._odpri_okno_razdelka(', py)
        self.assertIn('"odpriPredvajalnik": lambda: self._odpri_predvajalnik(', py)
        self.assertIn('"mostOkna": True', py)
        self.assertIn("def _odpri_okno_razdelka(self", py)
        self.assertIn("def _odpri_predvajalnik(self", py)

    def test_api_indeksator_v_vseh_jezikih(self):
        b = beri("assets", "os", "besedila.js")
        pricakovano = {"sl": "API indeksator", "en": "Indexer API", "de": "Indexer-API", "es": "API del indexador",
                       "fr": "API de l'indexeur", "it": "API dell'indicizzatore"}
        for jezik, ime in pricakovano.items():
            m = re.findall(r'BESEDILA_OS\.%s, \{"usenetIme": "([^"]*)"' % jezik, b)
            self.assertTrue(m, jezik)
            self.assertEqual(m[-1], ime, jezik)
        self.assertNotIn("Usenet (prek TorBoxa)", b)


if __name__ == "__main__":
    unittest.main()
