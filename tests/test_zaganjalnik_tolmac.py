"""Zaganjalniki s profilom AppArmor (userns) ne zazenejo tujega tolmaca ali tuje kode (tedenski pregled 4. 11. 2026).

Profil packaging/apparmor/safeer-{browser,os,control} velja za /usr/bin/safeer* in ga podedujejo otroci. Prej je
zaganjalnik vzel PYTHON iz okolja (ali python3 po PATH, kjer je ~/.local/bin pred /usr/bin): PYTHON=/kjerkoli
/usr/bin/safeer-os je zagnal poljuben program z dovoljenjem za userns. Enako PYTHONPATH/PYTHONSTARTUP in mapa-povezava
na /usr/bin, ki je APP_DIR preusmerila v tujo mapo (logicni `pwd`).
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
ZAGANJALNIKI = {
    "safeer-os-launcher": ("safeer-os", "safeer_os.py"),
    "safeer-control-launcher": ("safeer-control", "safeer_control.py"),
    "safeer-launcher": ("safeer-browser", "safeer_brskalnik.py"),
    "safeerctl-launcher": ("safeer-control", "safeerctl.py"),
}


def _blok_tolmaca(besedilo: str) -> str:
    m = re.search(r'^case "\$APP_DIR" in\n    /usr/lib/\*\)\n.*?^esac\n', besedilo, re.S | re.M)
    assert m, "ni bloka izbire tolmaca"
    return m.group(0)


class TolmacZaganjalnika(unittest.TestCase):
    def test_sistemska_namestitev_prezre_python_in_python_spremenljivke(self):
        for ime in ZAGANJALNIKI:
            with self.subTest(ime):
                besedilo = (KOREN / "packaging" / ime).read_text(encoding="utf-8")
                skripta = _blok_tolmaca(besedilo) + 'printf "%s\\n" "$PY"; env | grep "^PYTHON" || true\n'
                for app_dir in ("/usr/lib/safeer-os", "/usr/lib/safeer-browser", "/usr/lib/safeer-control"):
                    izid = subprocess.run(["/bin/bash", "-c", skripta], capture_output=True, text=True, timeout=30,
                                          env={"PATH": "/tmp/tuje:/usr/bin:/bin", "APP_DIR": app_dir,
                                               "PYTHON": "/tmp/tuje/python3", "PYTHONPATH": "/tmp/tuje",
                                               "PYTHONSTARTUP": "/tmp/tuje/x.py"})
                    self.assertEqual(izid.stdout.split(), ["/usr/bin/python3"], izid.stderr)

    def test_razvojni_zagon_obdrzi_python(self):
        for ime in ZAGANJALNIKI:
            with self.subTest(ime):
                skripta = _blok_tolmaca((KOREN / "packaging" / ime).read_text(encoding="utf-8")) + 'echo "$PY"\n'
                izid = subprocess.run(["/bin/bash", "-c", skripta], capture_output=True, text=True, timeout=30,
                                      env={"PATH": "/usr/bin:/bin", "APP_DIR": "/home/razvoj/lib/safeer-os",
                                           "PYTHON": sys.executable})
                self.assertEqual(izid.stdout.strip(), sys.executable)

    def test_brez_python_iz_okolja_zunaj_bloka_in_brez_env_v_shebangu(self):
        for ime in ZAGANJALNIKI:
            with self.subTest(ime):
                besedilo = (KOREN / "packaging" / ime).read_text(encoding="utf-8")
                # /usr/bin/env bash bi bash poiskal po PATH klicatelja - ze ta bi tekel s profilom.
                self.assertTrue(besedilo.startswith("#!/bin/bash\n"))
                zunaj = besedilo.replace(_blok_tolmaca(besedilo), "")
                self.assertNotIn("${PYTHON", zunaj)
                self.assertNotRegex(zunaj, r'(?m)^[^#]*\bexec python3\b')
                prvi_py = zunaj.find('"$PY"')
                self.assertGreater(prvi_py, 0)
                self.assertLess(besedilo.find(_blok_tolmaca(besedilo)), besedilo.find('"$PY"'))

    def test_mapa_povezava_ne_preusmeri_tovora(self):
        """bin-povezava -> prava mapa: APP_DIR mora biti fizicni sosed zaganjalnika, ne <povezava>/../lib."""
        for ime, (mapa, vstop) in ZAGANJALNIKI.items():
            with self.subTest(ime), tempfile.TemporaryDirectory() as d:
                d = Path(os.path.realpath(d))
                (d / "pravi" / "bin").mkdir(parents=True)
                (d / "pravi" / "lib" / mapa).mkdir(parents=True)
                (d / "tuj" / "lib" / mapa).mkdir(parents=True)
                (d / "pravi" / "bin" / ime).write_text((KOREN / "packaging" / ime).read_text(encoding="utf-8"))
                (d / "pravi" / "lib" / mapa / vstop).write_text("print('PRAVI')\n")
                (d / "tuj" / "lib" / mapa / vstop).write_text("print('TUJ')\n")
                (d / "tuj" / "bin").symlink_to(d / "pravi" / "bin")
                izid = subprocess.run(["/bin/bash", str(d / "tuj" / "bin" / ime), "--version"], capture_output=True,
                                      text=True, timeout=60,
                                      env={"PATH": "/usr/bin:/bin", "HOME": str(d), "PYTHON": sys.executable,
                                           "SAFEER_NO_SCOPE": "1", "SAFEER_OS_BREZ_FLATPAKA": "1"})
                self.assertIn("PRAVI", izid.stdout, izid.stderr)
                self.assertNotIn("TUJ", izid.stdout)


if __name__ == "__main__":
    unittest.main()
