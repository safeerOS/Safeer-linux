"""Mreza slicic z zastarelim zetonom ne sme zapreti vira (Global Link prek Huba, pot /cast/thumb/).

Zakaj: vsaka zavrnjena zahteva je »brez_zaupanja« (teza 20, PRAG 400): 20 zavrnjenih slicic v minuti zapre vir za
10 minut in z njim ves Link te naprave. Mreza slicic po zamenjavi zetona naredi desetine zahtev hkrati. Pregled
25. 10. 2026 (S3) je to popravil samo na Windows; Linux in skupna koda sta ostala brez popravka (17. 11. 2026).
"""
import types
import unittest

from core import link_hub_streznik, link_obramba

VIR = "192.0.2.10"


class _Ura:
    t = 1000.0

    def __call__(self):
        return self.t


class _Streznik:
    def zeton_velja(self, zeton):
        return zeton == "veljaven"


def _obravnava(obramba, zeton="zastarel"):
    h = object.__new__(link_hub_streznik._Obravnava)
    h.client_address = (VIR, 50000)
    h.headers = {"X-Safeer-Token": zeton}
    h.server = types.SimpleNamespace(obramba=obramba, datoteke=lambda: _Streznik())
    h._napaka = lambda *a, **k: None
    return h


class SliciceObramba(unittest.TestCase):
    def setUp(self):
        self.ura = _Ura()
        self.obramba = link_obramba.Obramba(ura=self.ura, ob_zapori=lambda *a: None, ob_napadu=lambda *a: None)
        getattr(link_hub_streznik, "_zavrnjene_slicice", {}).clear()

    def test_mreza_slicic_z_zastarelim_zetonom_ne_zapre_vira(self):
        for _ in range(60):
            _obravnava(self.obramba)._streznik_datotek("/cast/thumb/a")
            self.ura.t += 0.05
        self.assertFalse(self.obramba.zaprt(VIR), "60 zavrnjenih slicic v 3 s je zaprlo vir")

    def test_zavrnjena_datoteka_ni_slicica_in_steje_vsakic(self):
        for _ in range(25):
            _obravnava(self.obramba)._streznik_datotek("/cast/d/x")
            self.ura.t += 0.05
        self.assertTrue(self.obramba.zaprt(VIR))

    def test_veljaven_zeton_ne_steje(self):
        for _ in range(100):
            _obravnava(self.obramba, "veljaven")._streznik_datotek("/cast/thumb/a")
        self.assertFalse(self.obramba.zaprt(VIR))

    def test_ena_zavrnitev_na_rok_ostale_ne(self):
        self.assertTrue(link_hub_streznik._steje_zavrnjeno_slicico(VIR, 100.0))
        self.assertFalse(link_hub_streznik._steje_zavrnjeno_slicico(VIR, 100.0 + link_hub_streznik.ROK_SLICIC_S - 0.1))
        self.assertTrue(link_hub_streznik._steje_zavrnjeno_slicico(VIR, 100.0 + link_hub_streznik.ROK_SLICIC_S + 0.1))
        self.assertTrue(link_hub_streznik._steje_zavrnjeno_slicico("192.0.2.11", 100.0))
