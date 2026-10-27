"""Posel v CI ne sme tiho izpasti, ker je preskocen oddaljen prednik (27. 10. 2026: tek 40433266503 zelen brez paketov
in brez preizkusov WebKita - webkit-deb-profil je bil preskocen ob ponovni rabi WebKita)."""
import os
import unittest

import yaml

POT = os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", "linux-packages.yml")


class PreskoceniPredniki(unittest.TestCase):
    def test_posel_za_pogojnim_prednikom_ima_svoj_pogoj(self):
        posli = yaml.safe_load(open(POT, encoding="utf-8"))["jobs"]

        def potrebe(ime):
            n = posli[ime].get("needs") or []
            return [n] if isinstance(n, str) else list(n)

        def predniki(ime, videni=None):
            videni = set() if videni is None else videni
            for p in potrebe(ime):
                if p not in videni:
                    videni.add(p)
                    predniki(p, videni)
            return videni

        manjka = []
        for ime in posli:
            # Pogojni prednik, ki ni neposredna potreba: njegov »skipped« brez lastnega if preskoci ta posel.
            oddaljeni = [p for p in predniki(ime) - set(potrebe(ime)) if posli[p].get("if")
                         and "refs/tags" not in str(posli[p]["if"])]
            if oddaljeni and "needs." not in str(posli[ime].get("if") or ""):
                manjka.append((ime, sorted(oddaljeni)))
        self.assertEqual(manjka, [])


if __name__ == "__main__":
    unittest.main()
