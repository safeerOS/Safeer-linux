#!/usr/bin/env python3
"""ruff samo za nove in spremenjene vrstice (izhodisce = osnovna veja; naloga 45).

    python3 tools/ruff_nove_vrstice.py OSNOVA          # npr. origin/gtk4 ali SHA osnove PR

Vzame datoteke .py, ki jih `git diff OSNOVA...HEAD` spremeni, pozene `ruff check --output-format json` (pravila iz
ruff.toml) in javi samo najdbe v dodanih ali spremenjenih vrsticah. Obstojeca koda ne pade nikoli. Izhod 1 ob najdbi.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from typing import Dict, List, Set

_GLAVA = re.compile(r"^\+\+\+ b/(.+)$")
_KOS = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def spremenjene_vrstice(diff: str) -> Dict[str, Set[int]]:
    """{datoteka: {stevilke dodanih/spremenjenih vrstic}} iz `git diff -U0`."""
    izid: Dict[str, Set[int]] = {}
    datoteka = None
    for vrstica in diff.splitlines():
        m = _GLAVA.match(vrstica)
        if m:
            datoteka = m.group(1)
            continue
        if vrstica.startswith("+++ /dev/null"):
            datoteka = None
            continue
        m = _KOS.match(vrstica)
        if m and datoteka:
            zacetek, dolzina = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            izid.setdefault(datoteka, set()).update(range(zacetek, zacetek + dolzina))
    return izid


def nove_najdbe(najdbe: List[dict], vrstice: Dict[str, Set[int]], koren: str = "") -> List[dict]:
    """Najdbe ruffa (JSON), ki so v spremenjenih vrsticah."""
    izid = []
    for n in najdbe:
        pot = n.get("filename", "")
        if koren and pot.startswith(koren.rstrip("/") + "/"):
            pot = pot[len(koren.rstrip("/")) + 1:]
        vrstica = (n.get("location") or {}).get("row")
        if vrstica in vrstice.get(pot, set()):
            izid.append(dict(n, filename=pot))
    return izid


def main(argv: List[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    osnova = argv[0]
    koren = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True,
                           timeout=60).stdout.strip()
    diff = subprocess.run(["git", "diff", "-U0", "--no-color", "--diff-filter=AM", osnova + "...HEAD", "--", "*.py"],
                          capture_output=True, text=True, check=True, cwd=koren, timeout=120).stdout
    vrstice = spremenjene_vrstice(diff)
    if not vrstice:
        print("ruff: ni spremenjenih datotek .py")
        return 0
    r = subprocess.run(["ruff", "check", "--output-format", "json", "--exit-zero", *sorted(vrstice)],
                       capture_output=True, text=True, cwd=koren, timeout=300)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return 2
    najdbe = nove_najdbe(json.loads(r.stdout or "[]"), vrstice, koren)
    for n in najdbe:
        print("::error file=%s,line=%s::%s %s" % (n["filename"], n["location"]["row"], n.get("code"), n.get("message")))
    print("ruff: %d najdb v novih vrsticah (%d datotek)" % (len(najdbe), len(vrstice)))
    return 1 if najdbe else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
