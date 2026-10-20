"""Zaganjalniki zazenejo Python z -s (odprta tocka pregleda 1.0.128).

Brez -s Python pred sistemske pakete (/usr/lib/python3/dist-packages) uvrsti uporabnikov site-packages
(~/.local/lib/python3.X/site-packages): paket, ki ga je uporabnik namestil s `pip install --user` (cryptography,
zeroconf, PyGObject ...), bi zamenjal sistemskega in program bi tekel na drugi kodi, kot je preizkusena. Zastavica -s ni
v okolju, zato jo dobijo tudi otroci, ki jih zazene varuh (Scit, lupina, Safeer OS) in ponovni zagoni
(core/okolje_procesa.python_ukaz). AppRun in AppRun-os imata PYTHONNOUSERSITE=1 ze od prej.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
#: zaganjalnik -> (mapa tovora v lib, vstopna skripta, argumenti)
ZAGANJALNIKI = {
    "safeer-os-launcher": ("safeer-os", "safeer_os.py", ["--version"]),
    "safeer-control-launcher": ("safeer-control", "safeer_control.py", ["--version"]),
    "safeer-launcher": ("safeer-browser", "safeer_brskalnik.py", ["--version"]),
    "safeerctl-launcher": ("safeer-control", "safeerctl.py", ["stanje"]),
}
IZPIS = "import sys; print('BREZ_UPORABNIKA=%d' % sys.flags.no_user_site)\n"


class Zaganjalniki(unittest.TestCase):
    def test_python_z_s(self):
        for ime, (mapa, vstop, argumenti) in ZAGANJALNIKI.items():
            with self.subTest(ime), tempfile.TemporaryDirectory() as d:
                d = Path(d)
                (d / "bin").mkdir()
                (d / "lib" / mapa).mkdir(parents=True)
                shutil.copy(KOREN / "packaging" / ime, d / "bin" / ime)
                (d / "lib" / mapa / vstop).write_text(IZPIS, encoding="utf-8")
                okolje = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(d), "PYTHON": sys.executable}
                izid = subprocess.run(["bash", str(d / "bin" / ime), *argumenti], capture_output=True, text=True,
                                      timeout=60, env=okolje)
                self.assertIn("BREZ_UPORABNIKA=1", izid.stdout, (izid.stdout, izid.stderr[-400:]))

    def test_vsak_klic_pythona_z_s(self):
        for ime in ZAGANJALNIKI:
            besedilo = (KOREN / "packaging" / ime).read_text(encoding="utf-8")
            klici = re.findall(r'(?<!=)(?:"\$PY"|"\$\{PYTHON:-python3\}")\s+(\S+)', besedilo)
            self.assertTrue(klici, ime)
            self.assertEqual({k for k in klici if k != "-s"}, set(), ime)

    def test_apprun_brez_uporabnikovega_site(self):
        for ime in ("AppRun", "AppRun-os"):
            self.assertIn("export PYTHONNOUSERSITE=1", (KOREN / "packaging" / ime).read_text(encoding="utf-8"), ime)


class Otroci(unittest.TestCase):
    def _pozeni(self, koda, *zastavice):
        izid = subprocess.run([sys.executable, *zastavice, "-c", koda], capture_output=True, text=True, timeout=60,
                              cwd=str(KOREN), env=dict(os.environ, PYTHONPATH=str(KOREN)))
        self.assertEqual(izid.returncode, 0, izid.stderr[-800:])
        return izid.stdout.strip().splitlines()[-1]

    def test_python_ukaz_prenese_s(self):
        koda = "from core import okolje_procesa as o; print(o.python_ukaz('/py'), o.python_niz('/a b.py', '/py'))"
        self.assertEqual(self._pozeni(koda, "-s"), "['/py', '-s'] \"/py\" -s \"/a b.py\"")
        self.assertEqual(self._pozeni(koda), "['/py'] \"/py\" \"/a b.py\"")

    def test_varuh_da_otrokom_s(self):
        koda = ("import sys, tempfile; from core import varuh_procesov as v\n"
                "p = v.sestavi(['--delovna'], %r, sys.executable, tempfile.mkdtemp())\n"
                "print(sorted({x.argv[1] for x in p}))" % str(KOREN))
        self.assertEqual(self._pozeni(koda, "-s"), "['-s']")


if __name__ == "__main__":
    unittest.main()
