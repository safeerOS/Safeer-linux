#!/usr/bin/env python3
"""Artefakt gradnje s kljucem v imenu iz zaupanja vrednega teka CI tega repozitorija (lastnik 25. 10. 2026: nas WebKit
enkrat na kljuc, ne v vsaki veji znova).

actions/cache vidi samo predpomnilnik svoje veje in privzete veje (main), zato je vsaka nova veja nas WebKit prevedla
znova (oktober 2026: 237 gradenj, 457 ur). Artefakte repozitorija (90 dni) vidijo vse veje: gotov WebKit (.deb),
profil PGO in predpomnilnik flatpak-builderja so zato tudi artefakti z imenom iz kljuca gradnje. Gradnja gre v pakete,
zato samo iz zaupanja vrednega teka (isto pravilo kot profil PGO Flatpaka, posel webkit-pgo-profil, pregled 18. 10. 2026):
  - tek tega repozitorija (head_repository = ta repozitorij; tek pull_request iz forka nikoli),
  - dogodek push ali workflow_dispatch (oba zahtevata pravico pisanja), istega delovnega toka,
  - pri gradnji oznake izdaje (v*): veja main / gtk4-deb-webkit, oznaka v* ali tek ISTEGA commita (AGENTS.md: paketi
    izdaje so artefakti zelenega teka veje za isti commit).
Utrjenost, zapis gradnje in preizkusi tecejo v vsakem teku na KONCNEM paketu, ne glede na vir gradnje.

Uporaba v koraku (GH_TOKEN, IZDAJA=true|false; GITHUB_* postavi GitHub):
  python3 tools/ci_artefakt.py najdi IME   -> v $GITHUB_OUTPUT: ime, run_id (prazno = ni), ustvarjen, osvezi=true|false
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Callable, Optional

#: Veje, iz katerih gradnja oznake izdaje sme vzeti artefakt (enako kot profil PGO v linux-packages.yml).
VEJE_IZDAJE = ("main", "gtk4-deb-webkit")
DELOVNI_TOK = ".github/workflows/linux-packages.yml"
#: Artefakt potece po 90 dneh; starejsega od 60 dni tek nalozi znova, da se nespremenjena gradnja ne ponovi.
OSVEZI_PO_DNEH = 60
DOVOLJENI_ZNAKI = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


def zaupanja_vreden(tek: dict, repo_id: str, izdaja: bool, sha: str) -> bool:
    if str((tek.get("head_repository") or {}).get("id")) != str(repo_id):
        return False
    if tek.get("event") not in ("push", "workflow_dispatch"):
        return False
    if tek.get("path") and tek.get("path") != DELOVNI_TOK:
        return False
    if not izdaja:
        return True
    veja = tek.get("head_branch") or ""
    return veja in VEJE_IZDAJE or veja.startswith("v") or bool(sha and tek.get("head_sha") == sha)


def _api(zeton: str) -> Callable[[str], dict]:
    osnova = os.environ.get("GITHUB_API_URL", "https://api.github.com")

    def klic(pot: str) -> dict:
        zahteva = urllib.request.Request(osnova + pot, headers={
            "Authorization": "Bearer " + zeton, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "safeer-ci-artefakt"})
        with urllib.request.urlopen(zahteva, timeout=30) as odgovor:     # noqa: S310 - samo GitHub API iz okolja CI
            return json.load(odgovor)
    return klic


def najdi(ime: str, repo: str, repo_id: str, izdaja: bool, sha: str, api: Callable[[str], dict],
          opozori: Callable[[str], None] = lambda s: None) -> Optional[dict]:
    """Najnovejsi nepotekel artefakt z imenom ime iz zaupanja vrednega teka: {run_id, ustvarjen} ali None."""
    if not ime or set(ime) - DOVOLJENI_ZNAKI:
        raise ValueError("neveljavno ime artefakta: %r" % ime)
    podatki = api("/repos/%s/actions/artifacts?name=%s&per_page=100" % (repo, urllib.parse.quote(ime)))
    kandidati = sorted((a for a in podatki.get("artifacts", []) if a.get("name") == ime and not a.get("expired")),
                       key=lambda a: a.get("created_at") or "", reverse=True)
    for a in kandidati:
        tek_id = (a.get("workflow_run") or {}).get("id")
        if not tek_id:
            continue
        tek = api("/repos/%s/actions/runs/%s" % (repo, int(tek_id)))
        if zaupanja_vreden(tek, repo_id, izdaja, sha):
            return {"run_id": str(int(tek_id)), "ustvarjen": a.get("created_at") or ""}
        opozori("::warning::%s iz teka %s ni iz zaupanja vrednega teka (repozitorij, dogodek, veja) - ga ne uporabimo"
                % (ime, tek_id))
    return None


def star(ustvarjen: str, zdaj: Optional[datetime] = None, dni: int = OSVEZI_PO_DNEH) -> bool:
    try:
        cas = datetime.strptime(ustvarjen, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return ((zdaj or datetime.now(timezone.utc)) - cas).total_seconds() > dni * 86400


def main(argv: list) -> int:
    if len(argv) != 2 or argv[0] != "najdi":
        print(__doc__, file=sys.stderr)
        return 2
    ime = argv[1]
    izid = najdi(ime, os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_REPOSITORY_ID"],
                 os.environ.get("IZDAJA") == "true", os.environ.get("GITHUB_SHA", ""), _api(os.environ["GH_TOKEN"]),
                 opozori=print)
    vrstice = ["ime=" + ime, "run_id=" + (izid["run_id"] if izid else ""),
               "ustvarjen=" + (izid["ustvarjen"] if izid else ""),
               "osvezi=" + ("true" if izid and star(izid["ustvarjen"]) else "false")]
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write("\n".join(vrstice) + "\n")
    if izid:
        print("::notice::%s iz teka %s (%s)" % (ime, izid["run_id"], izid["ustvarjen"]))
    else:
        print("::notice::%s: zaupanja vrednega artefakta ni - gradnja v tem teku" % ime)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
