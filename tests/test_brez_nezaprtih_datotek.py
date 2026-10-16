#!/usr/bin/env python3
"""Produkcijska koda ne bere in ne pise z open(...).read()/.write() brez with: datoteka ostane odprta do zbiralnika
smeti (pregled 16. 10. 2026). Preizkusi niso zajeti."""

import ast
import os
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IZPUSTI = {".git", "tests", "build", "__pycache__", "node_modules", ".flatpak-builder"}


def najdi() -> list:
    izid = []
    for koren, mape, datoteke in os.walk(KOREN):
        mape[:] = [m for m in mape if m not in IZPUSTI]
        for ime in datoteke:
            if not ime.endswith(".py"):
                continue
            pot = os.path.join(koren, ime)
            with open(pot, encoding="utf-8") as f:
                try:
                    drevo = ast.parse(f.read())
                except SyntaxError:
                    continue
            for v in ast.walk(drevo):
                if (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
                        and v.func.attr in ("read", "readlines", "readline", "write", "writelines")
                        and isinstance(v.func.value, ast.Call) and getattr(v.func.value.func, "id", "") == "open"):
                    izid.append("%s:%d" % (os.path.relpath(pot, KOREN), v.lineno))
    return izid


class PreizkusNezaprtihDatotek(unittest.TestCase):
    def test_brez_open_read_brez_with(self):
        self.assertEqual(najdi(), [])


if __name__ == "__main__":
    unittest.main()
