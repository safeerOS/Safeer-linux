"""Gradnja .deb za WebKit: napacna vsota SHA-256 ali neuspel popravek mora ustaviti gradnjo (pregled 28. 10. 2026).

Funkciji prenesi in razpakiraj se izvedeta iz zgradi.sh v enakem okolju kot v skripti (set -euo pipefail,
inherit_errexit, klic znotraj $(...)), brez omrezja: arhiv je ze v mapi prenosov.
"""

import hashlib
import re
import subprocess
import tarfile
from pathlib import Path

ZGRADI = Path(__file__).resolve().parent.parent / "packaging" / "webkit-deb" / "zgradi.sh"


def _funkcija(ime: str) -> str:
    besedilo = ZGRADI.read_text()
    m = re.search(rf"^{ime}\(\) \{{.*?^\}}$", besedilo, re.S | re.M)
    assert m, ime
    return m.group(0)


def _glava() -> str:
    besedilo = ZGRADI.read_text()
    vrstice = besedilo.split("KOREN=", 1)[0].splitlines()
    return "\n".join(v for v in vrstice if v.startswith(("set ", "shopt ")))


def _pozeni(delo: Path, telo: str) -> subprocess.CompletedProcess:
    skripta = "\n".join([_glava(), f'DELO="{delo}"', _funkcija("prenesi"), _funkcija("razpakiraj"), telo, "echo KONEC"])
    return subprocess.run(["bash", "-c", skripta], capture_output=True, text=True, timeout=60)


def _arhiv(delo: Path) -> tuple[Path, str]:
    izvor = delo / "src" / "paket-1.0"
    izvor.mkdir(parents=True)
    (izvor / "a.txt").write_text("ena\n")
    (delo / "prenosi").mkdir(parents=True)
    arhiv = delo / "prenosi" / "paket-1.0.tar.xz"
    with tarfile.open(arhiv, "w:xz") as t:
        t.add(izvor, arcname="paket-1.0")
    return arhiv, hashlib.sha256(arhiv.read_bytes()).hexdigest()


def test_glava_ima_inherit_errexit():
    assert "shopt -s inherit_errexit" in _glava()
    assert "set -euo pipefail" in _glava()


def test_napacna_vsota_ustavi(tmp_path):
    _arhiv(tmp_path)
    r = _pozeni(tmp_path, 'X="$(prenesi https://primer.invalid/paket-1.0.tar.xz ' + "0" * 64 + ')"')
    assert r.returncode != 0
    assert "KONEC" not in r.stdout


def test_prava_vsota_gre_naprej(tmp_path):
    arhiv, sha = _arhiv(tmp_path)
    r = _pozeni(tmp_path, f'X="$(prenesi https://primer.invalid/paket-1.0.tar.xz {sha})"; echo "$X"')
    assert r.returncode == 0, r.stderr
    assert str(arhiv) in r.stdout and "KONEC" in r.stdout


def test_neuspel_popravek_ustavi(tmp_path):
    arhiv, _ = _arhiv(tmp_path)
    slab = tmp_path / "slab.patch"
    slab.write_text("--- a/ni.txt\n+++ b/ni.txt\n@@ -1 +1 @@\n-x\n+y\n")
    r = _pozeni(tmp_path, f'X="$(razpakiraj {arhiv} {slab})"')
    assert r.returncode != 0
    assert "KONEC" not in r.stdout


def test_dober_popravek_gre_naprej(tmp_path):
    arhiv, _ = _arhiv(tmp_path)
    dober = tmp_path / "dober.patch"
    dober.write_text("--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-ena\n+dva\n")
    r = _pozeni(tmp_path, f'X="$(razpakiraj {arhiv} {dober})"; cat "$X/a.txt"')
    assert r.returncode == 0, r.stderr
    assert "dva" in r.stdout
