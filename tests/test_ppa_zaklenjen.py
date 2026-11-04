"""Pot PPA (scripts/build_source_package.sh, ppa_upload.sh) je zaklenjena: zastarela razlicica, sistemski WebKitGTK in
brez AppArmor (tedenski pregled 4. 11. 2026, S17). Skripta mora koncati z jasno napako, preden karkoli zgradi ali poslje."""
import os
import subprocess
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PpaZaklenjen(unittest.TestCase):
    def test_skripti_koncata_z_razlogom_brez_dela(self):
        for ime in ("build_source_package.sh", "ppa_upload.sh"):
            with self.subTest(ime), tempfile.TemporaryDirectory() as d:
                # Kopija v prazno drevo: ce bi skripta kaj gradila, bi pisala v d/build.
                os.makedirs(os.path.join(d, "scripts"))
                with open(os.path.join(KOREN, "scripts", ime), encoding="utf-8") as f:
                    vsebina = f.read()
                pot = os.path.join(d, "scripts", ime)
                with open(pot, "w", encoding="utf-8") as f:
                    f.write(vsebina)
                izid = subprocess.run(["bash", pot, "ppa:primer/x"], capture_output=True, text=True, timeout=30,
                                      cwd=d, env={"PATH": "/usr/bin:/bin"})
                self.assertEqual(izid.returncode, 2, izid.stderr)
                self.assertIn("zaklenjena", izid.stderr)
                self.assertEqual(sorted(os.listdir(d)), ["scripts"])


if __name__ == "__main__":
    unittest.main()
