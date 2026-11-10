"""Varnost Linka, tocka 4 (pregled TV 10. 11. 2026): magnet.remove odstrani samo narocnik, ki je prenos prosil.
Brez omrezja in brez rqbit (nadomestek motorja iz tests/test_krog85)."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import link_daljinec, link_datoteke  # noqa: E402
from test_krog85 import A, B, _Prenosi  # noqa: E402


class OdstraniNarocnik(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-varnost-magnet-")
        self.raba = os.path.join(self.mapa, "raba-naprave.json")
        self.d = link_datoteke.Datoteke([], tls_mapa=os.path.join(self.mapa, "tls"))
        self.addCleanup(self.d.ustavi)
        self.addCleanup(shutil.rmtree, self.mapa, True)
        self.t = _Prenosi([A, B])
        link_datoteke.zabelezi_opis(A, {"title": "Film A"}, "tel-1", self.raba)
        link_datoteke.zabelezi_opis(B, None, "tv-2", self.raba)          # brez opisa: narocnik se vseeno zapise

    def test_samo_narocnik(self):
        self.assertFalse(self.d.odstrani_prenos(1, self.t, id_naprave="tv-2", pot_rabe=self.raba))
        self.assertFalse(self.d.odstrani_prenos(1, self.t, id_naprave="", pot_rabe=self.raba))
        self.assertEqual(self.t.odstranjeni, [])
        self.assertTrue(self.d.odstrani_prenos(1, self.t, id_naprave="tel-1", pot_rabe=self.raba))
        self.assertTrue(self.d.odstrani_prenos(2, self.t, id_naprave="tv-2", pot_rabe=self.raba))
        self.assertEqual(self.t.odstranjeni, [1, 2])

    def test_prenos_brez_zapisa_in_gledanje_racunalnika(self):
        t = _Prenosi([A, B, "c" * 40])
        self.assertFalse(self.d.odstrani_prenos(3, t, id_naprave="tel-1", pot_rabe=self.raba))   # nihce ga ni prosil
        self.d.gledanje = lambda: [{"hash": "d" * 40}]
        self.d.odstrani_gledanje = lambda h: True
        self.assertFalse(self.d.odstrani_prenos(link_datoteke.oznaka_gledanja("d" * 40), t, id_naprave="tel-1",
                                                pot_rabe=self.raba))
        self.assertEqual(t.odstranjeni, [])
        # Uporabnik tega racunalnika (brez id_naprave) sme kot doslej.
        self.assertTrue(self.d.odstrani_prenos(3, t))

    def test_ukaz_poda_posiljatelja(self):
        vir = open(link_daljinec.__file__, encoding="utf-8").read()
        self.assertIn("datoteke.odstrani_prenos(tid, id_naprave=posiljatelj)", vir)


if __name__ == "__main__":
    unittest.main()
