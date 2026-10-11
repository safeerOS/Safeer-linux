"""Domaci pogled na mostu Safeer OS (core/os_most_nativni.py) in pot skozi safeer_os._most_klic."""
import os
import unittest

from core import os_most_nativni


class NativniPogledTest(unittest.TestCase):
    def test_klic_odgovor_kot_na_strani(self):
        poslano = []
        p = os_most_nativni.NativniPogled(lambda pogled, id_, m, a: poslano.append((pogled, id_, m, a)))
        dobljeno, napake = [], []
        id_ = p.klic("mediaKatalog", ["", "film"], dobljeno.append, napake.append)
        self.assertEqual(poslano, [(p, id_, "mediaKatalog", ["", "film"])])
        p.odgovor(id_, True, {"vnosi": ({"id": 1},)})
        self.assertEqual(dobljeno, [{"vnosi": [{"id": 1}]}], "odgovor gre skozi JSON kot na strani")
        id2 = p.klic("x", [], dobljeno.append, napake.append)
        p.odgovor(id2, False, "neznano")
        self.assertEqual(napake, ["neznano"])
        p.odgovor(999, True, 1)            # neznan id: tiho

    def test_napaka_posiljanja_je_odgovor(self):
        def pade(*_a):
            raise RuntimeError("most ne dela")
        napake = []
        os_most_nativni.NativniPogled(pade).klic("x", [], None, napake.append)
        self.assertEqual(napake, ["most ne dela"])

    def test_dogodki_in_zaprtje(self):
        p = os_most_nativni.NativniPogled(lambda *a: None)
        eni, vsi = [], []
        p.naroci("mediaNiNaVoljo", eni.append)
        p.naroci("*", lambda v, d: vsi.append((v, d)))
        p.dogodek("mediaNiNaVoljo", {"idji": ("a",)})
        p.dogodek("drugo", 1)
        self.assertEqual(eni, [{"idji": ["a"]}])
        self.assertEqual(vsi, [("mediaNiNaVoljo", {"idji": ["a"]}), ("drugo", 1)])
        p.zapri()
        p.dogodek("mediaNiNaVoljo", {})
        self.assertEqual(len(eni), 1)
        self.assertFalse(p.odgovor(1, True, 1))


class MostVSafeerOS(unittest.TestCase):
    def setUp(self):
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "safeer_os.py"), encoding="utf-8") as f:
            self.vir = f.read()

    def test_stran_in_domaci_pogled_isti_most(self):
        sporocilo = self.vir[self.vir.index("def _na_sporocilo("):self.vir.index("def _most_klic(")]
        self.assertIn("self._most_klic(pogled, id_, metoda, a)", sporocilo)
        odgovori = self.vir[self.vir.index("def _odgovori("):self.vir.index("def _seznam_programov(")]
        self.assertIn("os_most_nativni.NativniPogled", odgovori)
        dogodek = self.vir[self.vir.index("def _dogodek("):self.vir.index("def _na_sporocilo(")]
        self.assertIn("p.dogodek(vrsta, podatki)", dogodek)
        js = self.vir[self.vir.index("def _js("):self.vir.index("def _odgovori(")]
        self.assertIn("continue", js)
