"""Metode mostu Safeer OS (slovarji v safeer_os.py) se ne smejo podvojiti: ob zdruzitvi vej (15. 10. 2026) sta dve
veji dodali »predogledDatoteke« z razlicnim pomenom in kasnejsi vnos je tiho prekril prvega."""
import ast
import collections
import os
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class MostBrezPodvojenih(unittest.TestCase):
    def test_imena_metod_so_enkratna(self):
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            drevo = ast.parse(f.read())
        stevec = collections.Counter()
        for vozel in ast.walk(drevo):
            if isinstance(vozel, ast.Dict) and len(vozel.keys) > 20:
                for k in vozel.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        stevec[k.value] += 1
        self.assertGreater(sum(stevec.values()), 100)
        self.assertEqual([k for k, n in stevec.items() if n > 1], [])


if __name__ == "__main__":
    unittest.main()
