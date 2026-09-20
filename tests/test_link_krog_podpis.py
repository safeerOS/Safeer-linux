"""Preverjanje podpisa v krogu zaupanja: hub mora prijavo sprejeti samo s pravim kljucem.

To je zdaj kljucna tocka, ker je lahko hub tudi racunalnik: ce preverjanje popusti, se lahko v
domace omrezje vrine kdorkoli.
"""
import base64
import unittest

from core import link_krog


class Podpis(unittest.TestCase):
    def setUp(self):
        self.kljuc = link_krog.javni_kljuc_b64()
        self.podatki = link_krog.podatki_za_podpis("ab" * 32, "nonce-123", "n-0123456789abcdef")
        self.podpis = link_krog.podpisi(self.podatki)

    def test_pravi_podpis_je_sprejet(self):
        self.assertTrue(link_krog.preveri_podpis(self.kljuc, self.podatki, self.podpis))

    def test_drugi_podatki_padejo(self):
        drugi = link_krog.podatki_za_podpis("ab" * 32, "nonce-124", "n-0123456789abcdef")
        self.assertFalse(link_krog.preveri_podpis(self.kljuc, drugi, self.podpis))

    def test_drug_id_pade(self):
        """Podpis je vezan na id naprave: z njim se ni mogoce predstavljati kot nekdo drug."""
        drugi = link_krog.podatki_za_podpis("ab" * 32, "nonce-123", "n-ffffffffffffffff")
        self.assertFalse(link_krog.preveri_podpis(self.kljuc, drugi, self.podpis))

    def test_drug_odtis_huba_pade(self):
        """Podpis je vezan na odtis huba: ujet podpis ne velja pri drugem hubu."""
        drugi = link_krog.podatki_za_podpis("cd" * 32, "nonce-123", "n-0123456789abcdef")
        self.assertFalse(link_krog.preveri_podpis(self.kljuc, drugi, self.podpis))

    def test_pokvarjen_podpis_pade(self):
        pokvarjen = base64.b64encode(base64.b64decode(self.podpis)[:-1] + b"\x00").decode()
        self.assertFalse(link_krog.preveri_podpis(self.kljuc, self.podatki, pokvarjen))

    def test_prazno_in_smeti_padeta_mirno(self):
        for kljuc, podpis in (("", self.podpis), (self.kljuc, ""), ("ni-base64!", self.podpis),
                              (self.kljuc, "ni-base64!"), ("", "")):
            self.assertFalse(link_krog.preveri_podpis(kljuc, self.podatki, podpis), (kljuc[:8], podpis[:8]))

    def test_tuj_kljuc_pade(self):
        """Podpis s svojim kljucem ne sme veljati za kljuc druge naprave."""
        import subprocess, tempfile, os
        mapa = tempfile.mkdtemp(prefix="safeer-tuj-")
        try:
            kljuc = os.path.join(mapa, "k.pem")
            subprocess.run(["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", kljuc],
                           check=True, capture_output=True)
            der = subprocess.run(["openssl", "pkey", "-in", kljuc, "-pubout", "-outform", "DER"],
                                 check=True, capture_output=True).stdout
            tuj = base64.b64encode(der).decode("ascii")
        finally:
            import shutil
            shutil.rmtree(mapa, ignore_errors=True)
        self.assertNotEqual(tuj, self.kljuc)
        self.assertFalse(link_krog.preveri_podpis(tuj, self.podatki, self.podpis))


if __name__ == "__main__":
    unittest.main()
