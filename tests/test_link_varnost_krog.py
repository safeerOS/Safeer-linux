"""Varnost Linka, tocka 2 (pregled TV 10. 11. 2026): krog zaupanja od sredisca (trust.update) in sosedov (mesh.trust).
Umaknjene naprave ne vrne nepodpisan novejsi vnos, ne vrne se s svojim podpisom, umaknjen clan ne podpisuje, ponarejen
podpis znanega podpisnika ne velja, drug kljuc znanega clana samo s podpisom. Kljuci so zacasni (openssl), brez omrezja."""
import base64
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from core import link_kripto, link_krog


def _kljuc(mapa, ime):
    pot = os.path.join(mapa, ime + ".pem")
    subprocess.run(["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", pot], check=True,
                   capture_output=True)
    der = subprocess.run(["openssl", "pkey", "-in", pot, "-pubout", "-outform", "DER"], check=True,
                         capture_output=True).stdout
    return pot, base64.b64encode(der).decode("ascii")


def _vnos(pot_podpisnika, device_id, kljuc, dodano, dodal, platforma="tv"):
    v = {"kljuc": kljuc, "ime": device_id, "platforma": platforma, "dodano": dodano, "dodal": dodal}
    if pot_podpisnika:
        v["podpis"] = base64.b64encode(link_kripto.podpisi(
            pot_podpisnika, link_krog.podatki_clana(device_id, kljuc, platforma, dodano, dodal))).decode("ascii")
    return v


class KrogOdSredisca(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-varnost-krog-")
        self.hub_pot, self.hub = _kljuc(self.mapa, "hub")
        self.tv_pot, self.tv = _kljuc(self.mapa, "tv")
        self.k = link_krog.Krog()
        # Krog: hub (sam sebe) in TV, ki jo je dodal hub; TV je nato umaknjena.
        self.k.zdruzi({"clani": {"hub": _vnos(self.hub_pot, "hub", self.hub, 100.0, "hub"),
                                 "tv": _vnos(self.hub_pot, "tv", self.tv, 101.0, "hub")}})
        self.k.zdruzi({"umiki": {"tv": {"umaknjeno": 102.0, "umaknil": "hub"}}})
        self.assertFalse(self.k.je_clan("tv"))

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_nepodpisan_novejsi_vnos_ne_izbrise_umika(self):
        self.assertFalse(self.k.zdruzi({"clani": {"tv": _vnos(None, "tv", self.tv, 200.0, "hub")}}))
        self.assertFalse(self.k.je_clan("tv"))
        self.assertIn("tv", self.k.json()["umiki"])

    def test_umaknjena_se_ne_vrne_s_svojim_podpisom(self):
        self.assertFalse(self.k.zdruzi({"clani": {"tv": _vnos(self.tv_pot, "tv", self.tv, 200.0, "tv")}}))
        self.assertFalse(self.k.je_clan("tv"))

    def test_vrnitev_s_podpisom_istega_kljuca_pod_drugim_id(self):
        # Isti kljuc je v krogu se pod drugim (veljavnim) id-jem: ne sme podpisati vrnitve umaknjenega id-ja.
        self.k.zdruzi({"clani": {"tv-stari": _vnos(self.hub_pot, "tv-stari", self.tv, 150.0, "hub")}})
        self.assertTrue(self.k.je_clan("tv-stari"))
        self.assertFalse(self.k.zdruzi({"clani": {"tv": _vnos(self.tv_pot, "tv", self.tv, 200.0, "tv-stari")}}))
        self.assertFalse(self.k.je_clan("tv"))

    def test_vrnitev_s_podpisom_veljavnega_clana_zacne_prazno(self):
        klici = []
        with mock.patch.object(link_krog, "_po_umiku", side_effect=lambda j, z=None, v=None: klici.append(v)), \
                mock.patch.object(link_krog, "_krog", self.k):
            self.assertTrue(self.k.zdruzi({"clani": {"tv": _vnos(self.hub_pot, "tv", self.tv, 200.0, "hub")}}))
        self.assertTrue(self.k.je_clan("tv"))
        # core/link_dostop.ob_umiku_iz_kroga dobi napravo, ki se vraca, s casom umika: vse dano pred umikom gre.
        self.assertEqual(klici, [{link_krog.id_iz_kljuca(self.tv): 102.0}])

    def test_ponarejen_podpis_znanega_podpisnika(self):
        nov_pot, nov = _kljuc(self.mapa, "nov")
        vnos = _vnos(self.hub_pot, "nov", nov, 300.0, "hub")
        vnos["dodano"] = 301.0                       # podpis velja za drug cas vpisa
        self.assertFalse(self.k.zdruzi({"clani": {"nov": vnos}}))
        self.assertFalse(self.k.je_clan("nov"))

    def test_drug_kljuc_znanega_clana_samo_s_podpisom(self):
        drug_pot, drug = _kljuc(self.mapa, "drug")
        self.assertFalse(self.k.zdruzi({"clani": {"hub": _vnos(None, "hub", drug, 300.0, "hub")}}))
        self.assertEqual(self.k.clan("hub")["kljuc"], self.hub)

    def test_nov_clan_od_sredisca_brez_podpisa_ostane_mogoc(self):
        # Prva seznanitev: naprava kroga se ne pozna, zato podpisa ne more preveriti (kot doslej).
        nov_pot, nov = _kljuc(self.mapa, "telefon")
        self.assertTrue(self.k.zdruzi({"clani": {"telefon": _vnos(None, "telefon", nov, 300.0, "neznan")}}))
        self.assertTrue(self.k.je_clan("telefon"))

    def test_umaknjen_clan_ne_podpisuje_pri_sosedih(self):
        nov_pot, nov = _kljuc(self.mapa, "vsiljivec")
        self.assertFalse(self.k.zdruzi({"clani": {"vsiljivec": _vnos(self.tv_pot, "vsiljivec", nov, 300.0, "tv")}},
                                       preveri_podpise=True))
        self.assertFalse(self.k.je_clan("vsiljivec"))


if __name__ == "__main__":
    unittest.main()
