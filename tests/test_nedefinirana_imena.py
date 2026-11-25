"""Nedefinirana imena v glavnem modulu (lastnik 25. 11. 2026: popravek zaslona v 0.4.95 se je ob zagonu sesul z
NameError: name 'which' is not defined, ceprav so preizkusi zaslona uspeli - pot ni bila izvedena). Pyflakes ujame
vsako ime, ki ni uvozeno, brez zagona programa."""
import pathlib
import subprocess
import sys

import pytest

KOREN = pathlib.Path(__file__).resolve().parent.parent


def test_safeer_os_brez_nedefiniranih_imen():
    pytest.importorskip("pyflakes")
    r = subprocess.run([sys.executable, "-m", "pyflakes", str(KOREN / "safeer_os.py")],
                       capture_output=True, text=True, timeout=120)
    napake = [v for v in r.stdout.splitlines() if "undefined name" in v]
    assert napake == [], "\n".join(napake)
