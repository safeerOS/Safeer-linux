"""Tovor Safeer Browserja nima modulov, ki jih nobena koda ne uvozi (tedenski pregled 4. 11. 2026, N7), in nobena
datoteka tovora jih ne potrebuje (uvozi z ast kot v tests/test_tovor_uvozi.py)."""
import os
import subprocess
import tempfile
import unittest

from test_tovor_uvozi import uvozi_core

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MRTVI = ("link_data_transport", "reader", "youtube_fast")


class TovorBrskalnikaMrtvi(unittest.TestCase):
    def test_brez_mrtvih_in_nihce_jih_ne_uvozi(self):
        with tempfile.TemporaryDirectory() as d:
            okolje = {k: v for k, v in os.environ.items() if k != "SAFEER_DRM_TOVOR"}
            subprocess.run(["bash", os.path.join(KOREN, "packaging", "install_payload.sh"), d], check=True,
                           capture_output=True, timeout=120, env=okolje)
            lib = os.path.join(d, "lib", "safeer-browser")
            for ime in MRTVI:
                self.assertFalse(os.path.exists(os.path.join(lib, "core", ime + ".py")), ime)
            uvozeni = set()
            for koren, _mape, datoteke in os.walk(lib):
                for dat in datoteke:
                    if not dat.endswith(".py"):
                        continue
                    pot = os.path.join(koren, dat)
                    rel = os.path.relpath(pot, lib).split(os.sep)
                    raven = 0 if rel[0] != "core" else len(rel) - 1
                    uvozeni |= {m for m, _v, _n in uvozi_core(pot, raven)}
            self.assertEqual(sorted(uvozeni & set(MRTVI)), [])


if __name__ == "__main__":
    unittest.main()
