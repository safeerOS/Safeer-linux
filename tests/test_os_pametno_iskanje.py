import pathlib
import subprocess


def test_pametno_iskanje_node():
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
