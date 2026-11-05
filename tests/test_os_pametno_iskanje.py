import pathlib
import shutil
import subprocess

import pytest


def test_pametno_iskanje_node():
    # Kot drugi preizkusi JS (test_link_paketi_zaslona): brez node preskok, ne FileNotFoundError (testni PC 5. 11. 2026).
    # V CI je node namescen (actions/setup-node).
    if not shutil.which("node"):
        pytest.skip("node ni namescen")
    koren = pathlib.Path(__file__).resolve().parents[1]
    rezultat = subprocess.run(
        ["node", "tests/test_os_pametno_iskanje.js"],
        cwd=koren,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert rezultat.returncode == 0, rezultat.stdout + rezultat.stderr
