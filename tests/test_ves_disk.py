"""Brskanje po celem racunalniku (core/link_datoteke.py): samo z dovoljenjem in brez lukenj."""
import os
import shutil
import sys
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_datoteke  # noqa: E402


class VesDisk(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.mapa, "podmapa"))
        with open(os.path.join(self.mapa, "film.mp4"), "w") as d:
            d.write("x")
        with open(os.path.join(self.mapa, ".skrito"), "w") as d:
            d.write("x")

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_izklopljeno_ne_pozna_oznak_diska(self):
        m = link_datoteke.DeljeneMape([self.mapa])
        self.assertIsNone(m.razresi("disk:" + self.mapa))
        self.assertIsNone(m.seznam("disk:" + self.mapa))
        self.assertTrue(all(not v["id"].startswith("disk:") for v in m.koren()))

    def test_vklopljeno_ponudi_domaco_mapo_in_koren(self):
        m = link_datoteke.DeljeneMape([self.mapa], ves_disk=True)
        oznake = [v["id"] for v in m.koren()]
        self.assertIn("disk:/", oznake)
        self.assertTrue(any(o.startswith("disk:" + os.path.realpath(os.path.expanduser("~"))) for o in oznake))

    def test_vsebina_mape_z_oznako_diska(self):
        m = link_datoteke.DeljeneMape([], ves_disk=True)
        vnosi = m.seznam("disk:" + self.mapa)
        imena = [v["name"] for v in vnosi]
        self.assertEqual(imena, ["podmapa", "film.mp4"])          # mape najprej
        self.assertNotIn(".skrito", imena)                        # skrite ostanejo skrite
        self.assertTrue(vnosi[0]["id"].startswith("disk:"))
        self.assertEqual(vnosi[1]["type"], "video")

    def test_koren_brez_sistemskih_map(self):
        m = link_datoteke.DeljeneMape([], ves_disk=True)
        imena = [v["name"] for v in (m.seznam("disk:/") or [])]
        for sistemska in ("proc", "sys", "dev"):
            self.assertNotIn(sistemska, imena)

    def test_brez_map_a_z_dovoljenjem_seznam_ni_prazen(self):
        d = link_datoteke.Datoteke([], ves_disk=True)
        odgovor = d.seznam("", "tv-test")
        self.assertTrue(odgovor["shared"])
        self.assertTrue(odgovor["items"])

    def test_brez_map_in_brez_dovoljenja_ni_nicesar(self):
        d = link_datoteke.Datoteke([])
        odgovor = d.seznam("", "tv-test")
        self.assertFalse(odgovor["shared"])
        self.assertEqual(odgovor["items"], [])

    def test_preklop_velja_takoj(self):
        d = link_datoteke.Datoteke([])
        self.assertIsNone(d.mape.razresi("disk:" + self.mapa))
        d.nastavi_ves_disk(True)
        self.assertIsNotNone(d.mape.razresi("disk:" + self.mapa))
        d.nastavi_ves_disk(False)
        self.assertIsNone(d.mape.razresi("disk:" + self.mapa))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class OdpriNaRacunalniku(unittest.TestCase):
    """`files.open`: datoteko odpre racunalnik s svojim programom, televizor jo vidi prek zaslona."""

    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.datoteka = os.path.join(self.mapa, "zapis.txt")
        with open(self.datoteka, "w") as d:
            d.write("x")

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_neznane_oznake_ne_odpremo(self):
        d = link_datoteke.Datoteke([self.mapa])
        self.assertFalse(d.odpri("disk:" + self.datoteka))      # brez dovoljenja za ves disk
        self.assertFalse(d.odpri("share:9:karkoli"))
        self.assertFalse(d.odpri(""))

    def test_ukaz_brez_modula_razumljiva_napaka(self):
        from core import link_daljinec
        izidi = []
        link_daljinec.izvedi_control("files.open", {"id": "share:0:"}, lambda u: None, izidi.append)
        self.assertFalse(izidi[0]["ok"])
        self.assertEqual(izidi[0]["code"], "ni_na_racunalniku")

    def test_ukaz_z_neveljavno_oznako(self):
        from core import link_daljinec
        d = link_datoteke.Datoteke([self.mapa])
        izidi = []
        link_daljinec.izvedi_control("files.open", {"id": "share:7:x"}, lambda u: None, izidi.append, datoteke=d)
        self.assertFalse(izidi[0]["ok"])
        self.assertEqual(izidi[0]["code"], "ni_datoteke")

    def test_files_open_je_v_zmoznostih(self):
        from core import link_daljinec
        self.assertIn("files.open", link_daljinec.DEJANJA_DATOTEKE)
