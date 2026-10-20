#!/usr/bin/env python3
"""Vrata izdaje: brez zapisa neodvisnega pregleda drugega ponudnika ni izdaje (lastnik, 20. 10. 2026: »pravila
namesto navodil« - zamisel iz og/Omnigent: kaj gre v izdajo, odloca koda, ne navodilo agentu).

    tools/preveri_pregled.py OZNAKA [COMMIT]     npr. tools/preveri_pregled.py v1.0.129

Zahteva docs/pregledi/<OZNAKA>.md z glavo (vrstice »Kljuc: vrednost« pred prvo prazno vrstico):

    Izdaja: v1.0.129
    Commit: 1a2b3c4                      # pregledani commit
    Pregledovalec: Gemini prek Pi        # kdo je pregledal
    Ponudnik: google                     # ponudnik modela pregledovalca (ne anthropic: kodo pise Claude)
    Odprte kriticne in visoke: 0         # stevilo neodpravljenih najdb resnosti kriticno/visoko

Pregledani commit mora biti prednik COMMIT (privzeto HEAD) in od njega do COMMIT se smejo spremeniti samo datoteke
izdaje (zapis pregleda, opombe, stevilke razlicic, metainfo, README). Vsaka druga sprememba po pregledu = nov pregled.
Izhodna koda 0 = izdaja sme naprej; sicer razlog na stderr.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

KOREN = Path(__file__).resolve().parents[1]
#: Ponudniki, ki ne stejejo kot neodvisni: avtor kode je Claude (Anthropic).
AVTORJI = {"anthropic", "claude"}
#: Kar se sme spremeniti po pregledu (zapis pregleda, opombe in stevilke razlicic za izdajo).
DOVOLJENO_PO_PREGLEDU = (
    re.compile(r"^docs/pregledi/"),
    re.compile(r"^docs/releases/"),
    re.compile(r"^RELEASE_NOTES[^/]*$"),
    re.compile(r"^packaging/VERSION(_[A-Z]+)?$"),
    re.compile(r"^io\.github\.memelandfaner\.[A-Za-z]+\.metainfo\.xml$"),
    re.compile(r"^README(\.[a-z]{2})?\.md$"),
)
OBVEZNO = ("Izdaja", "Commit", "Pregledovalec", "Ponudnik", "Odprte kriticne in visoke")


def glava(besedilo: str) -> Dict[str, str]:
    polja: Dict[str, str] = {}
    for vrstica in besedilo.splitlines():
        if not vrstica.strip():
            break
        if ":" in vrstica:
            kljuc, vrednost = vrstica.split(":", 1)
            polja[kljuc.strip()] = vrednost.split("#", 1)[0].strip()
    return polja


def _git(*argumenti: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(KOREN), *argumenti], capture_output=True, text=True)


def napake(oznaka: str, commit: str = "HEAD", besedilo: Optional[str] = None) -> List[str]:
    """Seznam razlogov, zakaj izdaja ne sme naprej (prazen = sme)."""
    if not re.fullmatch(r"v\d+\.\d+\.\d+(-beta\.\d+)?", oznaka):
        return ["oznaka %r ni oblike vX.Y.Z ali vX.Y.Z-beta.N" % oznaka]
    pot = "docs/pregledi/%s.md" % oznaka
    if besedilo is None:
        # Zapis iz commita izdaje (ne iz delovne kopije): v izdajo gre tisto, kar je v commitu.
        r = _git("show", "%s:%s" % (commit, pot))
        if r.returncode != 0:
            return ["ni zapisa neodvisnega pregleda %s v %s" % (pot, commit)]
        besedilo = r.stdout
    p = glava(besedilo)
    izid = ["v glavi zapisa manjka »%s:«" % k for k in OBVEZNO if not p.get(k)]
    if izid:
        return izid
    if p["Izdaja"] != oznaka:
        izid.append("zapis je za %s, ne za %s" % (p["Izdaja"], oznaka))
    # Podniz, ne celoten niz (Kimi pregled 20. 10. 2026: »Claude prek Anthropic« je sel skozi).
    if any(a in p["Ponudnik"].lower() for a in AVTORJI):
        izid.append("pregledovalec ni neodvisen: ponudnik %s je ponudnik avtorja kode" % p["Ponudnik"])
    if not re.fullmatch(r"\d+", p["Odprte kriticne in visoke"]) or int(p["Odprte kriticne in visoke"]) != 0:
        izid.append("odprte kriticne/visoke najdbe: %s (mora biti 0)" % p["Odprte kriticne in visoke"])
    pregledan = p["Commit"]
    if not re.fullmatch(r"[0-9a-f]{7,40}", pregledan):
        return izid + ["Commit %r ni zgoscena vrednost commita" % pregledan]
    if _git("merge-base", "--is-ancestor", pregledan, commit).returncode != 0:
        return izid + ["pregledani commit %s ni prednik %s (ali ga ni v repozitoriju)" % (pregledan, commit)]
    r = _git("diff", "--name-only", pregledan, commit)
    if r.returncode != 0:
        return izid + ["git diff %s..%s: %s" % (pregledan, commit, r.stderr.strip())]
    po = [d for d in r.stdout.splitlines() if d and not any(v.match(d) for v in DOVOLJENO_PO_PREGLEDU)]
    if po:
        izid.append("po pregledu spremenjeno (potreben nov pregled): " + ", ".join(po[:10]) + (" ..." if len(po) > 10 else ""))
    return izid


def main(argv: List[str]) -> int:
    if not argv or len(argv) > 2:
        print(__doc__, file=sys.stderr)
        return 2
    razlogi = napake(argv[0], argv[1] if len(argv) > 1 else "HEAD")
    for r in razlogi:
        print("preveri_pregled: " + r, file=sys.stderr)
    if not razlogi:
        print("preveri_pregled: %s ima neodvisni pregled - izdaja sme naprej" % argv[0])
    return 1 if razlogi else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
