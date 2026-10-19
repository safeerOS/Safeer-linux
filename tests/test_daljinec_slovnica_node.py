"""Hitri prevajalnik daljinca (assets/link/daljinec.js) v CI: pytest pozene node preizkus tests/test_daljinec_slovnica.js.

Do 19. 10. 2026 ga pytest ni klical, zato CI napak prevajalnika (utisaj/zvok, naslovi v stavku, fraze o napravi, pavza)
ni videl - preizkus je tekel samo rocno."""
import pathlib
import subprocess


def test_daljinec_slovnica_node():
    koren = pathlib.Path(__file__).resolve().parents[1]
    rezultat = subprocess.run(
        ["node", "tests/test_daljinec_slovnica.js"],
        cwd=koren,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert rezultat.returncode == 0, rezultat.stdout[-3000:] + rezultat.stderr[-2000:]
    assert "Vse v redu." in rezultat.stdout
