"""Metode mostu Safeer OS (slovarji v safeer_os.py) se ne smejo podvojiti: ob zdruzitvi vej (15. 10. 2026) sta dve
veji dodali »predogledDatoteke« z razlicnim pomenom in kasnejsi vnos je tiho prekril prvega.

Steje samo slovarje metod v razpecevalniku mostu (_obdelaj_klic: »glavna« in »ozadje«). Prej je stel vse slovarje z
vec kot 20 kljuci; ob zdruzitvi vej 18. 10. 2026 je slovar stanja, ki ga vrne _zacetek (kljuci so tam polja stanja,
npr. »namizje«, »samozagon«), presegel mejo in istoimenska polja so se steli kot podvojene metode."""
import ast
import collections
import os
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _slovarji_metod(drevo: ast.AST) -> list:
    for vozel in ast.walk(drevo):
        if isinstance(vozel, ast.FunctionDef) and vozel.name == "_obdelaj_klic":
            return [d for d in ast.walk(vozel) if isinstance(d, ast.Dict) and len(d.keys) > 20]
    return []


class MostBrezPodvojenih(unittest.TestCase):
    def test_imena_metod_so_enkratna(self):
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            drevo = ast.parse(f.read())
        slovarji = _slovarji_metod(drevo)
        self.assertGreaterEqual(len(slovarji), 2, "razpecevalnik mostu ima slovarja »glavna« in »ozadje«")
        stevec = collections.Counter()
        for slovar in slovarji:
            for k in slovar.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    stevec[k.value] += 1
        self.assertGreater(sum(stevec.values()), 100)
        self.assertEqual([k for k, n in stevec.items() if n > 1], [])

    def test_preizkus_ujame_podvojitev(self):
        """Podvojeno ime v enem slovarju ali med »glavna« in »ozadje« preizkus res najde."""
        kljuci = ", ".join(f'"m{i}": None' for i in range(25))
        vir = ("class A:\n    def _obdelaj_klic(self, a):\n"
               f"        glavna = {{{kljuci}, \"x\": None}}\n"
               f"        ozadje = {{{kljuci.replace('m', 'n')}, \"x\": None}}\n")
        stevec = collections.Counter(k.value for d in _slovarji_metod(ast.parse(vir)) for k in d.keys)
        self.assertEqual([k for k, n in stevec.items() if n > 1], ["x"])


if __name__ == "__main__":
    unittest.main()
