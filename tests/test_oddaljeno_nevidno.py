"""Programi in datoteke z druge naprave samo na locenem zaslonu (lastnik, 13. 10. 2026): uporabnik za racunalnikom,
iz katerega crpamo, tega ne opazi. Brez locenega zaslona racunalnik zavrne - nikoli ne odpre na svojem zaslonu."""
import os
import tempfile
import unittest

from core import link_daljinec, link_dostop


class _Datoteke:
    def __init__(self, pot):
        self._pot = pot
        self.odprto = []

    def pot(self, oznaka):
        return self._pot if oznaka == "d1" else ""

    def odpri(self, oznaka):
        self.odprto.append(oznaka)
        return True


class _Drugi:
    def __init__(self):
        self.zagnano = []

    def zazeni_program(self, argv, opis=None):
        self.zagnano.append(argv)
        return True


class _Programi:
    vklopljeno = True

    def __init__(self, drugi=None):
        self.drugi = drugi
        self.zagnani = []

    def zazeni(self, oznaka):
        self.zagnani.append(oznaka)
        return True


class Nevidno(unittest.TestCase):
    def _izvedi(self, dejanje, parametri, datoteke=None, programi=None):
        izidi = []
        link_daljinec.izvedi_control(dejanje, parametri, lambda _u: None, izidi.append, datoteke=datoteke, programi=programi)
        return izidi[-1]

    def test_datoteka_na_locenem_zaslonu(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            d, drugi = _Datoteke(f.name), _Drugi()
            r = self._izvedi("files.open_locen", {"id": "d1"}, datoteke=d, programi=_Programi(drugi))
            self.assertTrue(r["ok"])
            self.assertEqual(drugi.zagnano, [["xdg-open", f.name]])
            self.assertEqual(d.odprto, [])          # nikoli na zaslonu uporabnika

    def test_brez_locenega_zaslona_zavrne(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            d = _Datoteke(f.name)
            r = self._izvedi("files.open_locen", {"id": "d1"}, datoteke=d, programi=_Programi(None))
            self.assertEqual((r["ok"], r.get("code")), (False, "ni_locenega_zaslona"))
            self.assertEqual(d.odprto, [])

    def test_program_brez_locenega_zaslona_zavrne(self):
        p = _Programi(None)
        r = self._izvedi("apps.launch_locen", {"app": "x"}, programi=p)
        self.assertEqual((r["ok"], r.get("code")), (False, "ni_locenega_zaslona"))
        self.assertEqual(p.zagnani, [])

    def test_program_z_locenim_zaslonom(self):
        p = _Programi(_Drugi())
        self.assertTrue(self._izvedi("apps.launch_locen", {"app": "x"}, programi=p)["ok"])
        self.assertEqual(p.zagnani, ["x"])

    def test_dovoljenja_in_oglas(self):
        self.assertIn("files.open_locen", link_daljinec.DEJANJA_DATOTEKE)
        self.assertIn("apps.launch_locen", link_daljinec.DEJANJA_PROGRAMI)
        vir = open(link_dostop.__file__, encoding="utf-8").read()
        self.assertIn('"files.open_locen"', vir)
        self.assertIn('"apps.launch_locen"', vir)


if __name__ == "__main__":
    unittest.main()
