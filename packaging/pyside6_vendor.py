#!/usr/bin/env python3
"""PySide6 (Qt Quick za lupino Safeer OS) v mapo paketa: packaging/pyside6_vendor.py <cilj> [mapa_predpomnilnika].

Linux Mint 22 PySide6 v svojih paketih nima (preverjeno 14. 10. 2026: apt-cache search pyside6), zato ga paket .deb
prinese sam - ista kolesa z istimi zgoscenimi vrednostmi kot Flatpak (io.github.memelandfaner.SafeerOS.yml, modul
python3-pyside6): en vir, brez razhajanja. Kolo je zip; razpakiramo ga v <cilj> (core/os_lupina.py ga doda na pot).
"""
import hashlib
import os
import re
import sys
import urllib.request
import zipfile

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(KOREN, "io.github.memelandfaner.SafeerOS.yml")


def kolesa() -> list:
    """[(url, sha256)] iz modula python3-pyside6 v manifestu Flatpak."""
    with open(MANIFEST, encoding="utf-8") as f:
        besedilo = f.read()
    m = re.search(r"- name: python3-pyside6\n(.*?)(?=\n  - name: )", besedilo, re.S)
    if not m:
        raise SystemExit("v manifestu ni modula python3-pyside6")
    pari = re.findall(r"url:\s*(\S+\.whl)\s*\n\s*sha256:\s*([0-9a-f]{64})", m.group(1))
    if len(pari) < 2:
        raise SystemExit("v modulu python3-pyside6 manjkajo kolesa")
    return pari


def prenesi(url: str, sha: str, mapa: str) -> str:
    os.makedirs(mapa, exist_ok=True)
    pot = os.path.join(mapa, url.rsplit("/", 1)[1])
    if not (os.path.isfile(pot) and _sha(pot) == sha):
        zacasna = pot + ".part"
        with urllib.request.urlopen(url, timeout=120) as o, open(zacasna, "wb") as f:
            while True:
                kos = o.read(1 << 20)
                if not kos:
                    break
                f.write(kos)
        if _sha(zacasna) != sha:
            os.remove(zacasna)
            raise SystemExit("napacna zgoscena vrednost: " + url)
        os.replace(zacasna, pot)
    return pot


def _sha(pot: str) -> str:
    h = hashlib.sha256()
    with open(pot, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    cilj = sys.argv[1]
    mapa = sys.argv[2] if len(sys.argv) > 2 else os.path.join(KOREN, "build", "cache", "pyside6")
    os.makedirs(cilj, exist_ok=True)
    for url, sha in kolesa():
        with zipfile.ZipFile(prenesi(url, sha, mapa)) as z:
            for clan in z.infolist():
                ime = clan.filename
                if ime.startswith("/") or ".." in ime.split("/"):
                    raise SystemExit("nevarna pot v kolesu: " + ime)
                # Metapodatki kolesa (.dist-info) ostanejo: importlib.metadata najde razlicico.
                z.extract(clan, cilj)
                pravice = (clan.external_attr >> 16) & 0o777
                if pravice:
                    os.chmod(os.path.join(cilj, ime), pravice)
    print("PySide6 v", cilj)


if __name__ == "__main__":
    main()
