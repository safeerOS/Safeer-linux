"""Vse akcije GitHub v .github/workflows so pripete na commit (SHA), ne na premicno oznako (@v5), in prenosi modelov
v CI se preverijo z vsoto (tedenski pregled 4. 11. 2026, N2 in N9: govor.yml in webkit-razlicica.yml sta bila na @vN,
tiny.bin brez sha256sum -c)."""
import glob
import os
import re
import unittest

import yaml

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POTEKI = sorted(glob.glob(os.path.join(KOREN, ".github", "workflows", "*.yml")))


def _koraki(potek):
    for ime, posel in (potek.get("jobs") or {}).items():
        for korak in posel.get("steps") or []:
            yield ime, korak


class PripeteAkcije(unittest.TestCase):
    def test_uses_na_sha(self):
        self.assertTrue(POTEKI)
        slabe = []
        for pot in POTEKI:
            with open(pot, encoding="utf-8") as f:
                potek = yaml.safe_load(f)
            for posel, korak in _koraki(potek):
                uses = korak.get("uses")
                if uses and not uses.startswith("./") and not re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", uses):
                    slabe.append("%s:%s: %s" % (os.path.basename(pot), posel, uses))
        self.assertEqual(slabe, [])

    def test_pisanje_samo_v_poslu_ki_ga_potrebuje(self):
        for pot in POTEKI:
            with open(pot, encoding="utf-8") as f:
                potek = yaml.safe_load(f)
            with self.subTest(os.path.basename(pot)):
                self.assertNotEqual((potek.get("permissions") or {}).get("contents"), "write")

    def test_model_govora_preverjen(self):
        with open(os.path.join(KOREN, ".github", "workflows", "govor.yml"), encoding="utf-8") as f:
            besedilo = f.read()
        self.assertRegex(besedilo, r'echo "[0-9a-f]{64}  tiny\.bin" \| sha256sum -c -')
        self.assertLess(besedilo.index("sha256sum -c"), besedilo.index("-m tiny.bin"))


if __name__ == "__main__":
    unittest.main()
