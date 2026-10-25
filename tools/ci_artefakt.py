#!/usr/bin/env python3
"""Artefakt gradnje s kljucem v imenu iz zaupanja vrednega teka CI tega repozitorija (lastnik 25. 10. 2026: nas WebKit
enkrat na kljuc, ne v vsaki veji znova).

actions/cache vidi samo predpomnilnik svoje veje in privzete veje (main), zato je vsaka nova veja nas WebKit prevedla
znova (oktober 2026: 243 gradenj, 468 ur). Artefakte repozitorija (90 dni) vidijo vse veje: gotov WebKit (.deb),
profila PGO in predpomnilnik flatpak-builderja so zato tudi artefakti z imenom iz kljuca gradnje. Gradnja gre v pakete,
zato je meja zaupanja zdruzitev v main, ne pravica pisanja v katerokoli vejo (neodvisni pregled 25. 10. 2026, M1-M3):
  - vir je tek tega repozitorija (head_repository; tek pull_request iz forka nikoli) in tega toka (polje path obvezno);
  - main in oznake izdaje (v*) vzamejo SAMO artefakt teka veje main ob potisku (event push), katerega
    commit je bil vrh refs/heads/main (dejavnost repozitorija: potisk ali zdruzitev na refs/heads/main) in je se v
    zgodovini main (primerjava s SHA veje, ne z dvoumnim imenom »main«). head_branch nosi tudi ime oznake: oznaka
    »main« na poljuben ali vmesni commit ne gre skozi (ponovni pregled 25. 10. 2026, N1); veja »v1-zlo« tudi ne;
  - druga veja vzame artefakt teka main (pot navzdol) ali teka ISTE veje (ista domena zaupanja: kdor potisne vejo, lahko
    spremeni tudi ta tok); artefakta druge veje nikoli. pull_request vzame artefakt main ali teka veje glave PR
    (GITHUB_HEAD_REF, potisk v ta repozitorij): PR iste veje ne gradi WebKita drugic (ponovni pregled N2); sam ne nalaga;
  - osvezitev (ponovno nalaganje artefakta, starejsega od 60 dni, pod tem tekom) samo v isti domeni (main iz main, veja
    iz iste veje): artefakt druge domene se pod tem tekom ne »opere« (M3);
  - artefakt za druge teke nalozi samo tek, ki je komu lahko vir (nalozi=true): potisk na main ali potisk/rocni zagon
    druge veje; oznaka, pull_request in rocni zagon na main ne. Profila PGO nalozi tudi pull_request, ker ju posel
    istega teka prenese (run-id tega teka); nihce drug jima ne zaupa (vir po tem pravilu). Ob oznaki se nic ne gradi.
SHA-256 ob artefaktu varuje celovitost prenosa (download-artifact razliko v povzetku le opozori), ne izvora; izvor varujejo
zgornja pravila. Utrjenost, zapis gradnje in preizkusi tecejo v vsakem teku na KONCNEM paketu, ne glede na vir gradnje.

Uporaba v koraku (GH_TOKEN; GITHUB_REPOSITORY, GITHUB_REPOSITORY_ID, GITHUB_REF, GITHUB_EVENT_NAME, GITHUB_HEAD_REF
postavi GitHub):
  python3 tools/ci_artefakt.py najdi IME [--tek ID]
    -> v $GITHUB_OUTPUT: ime, run_id (prazno = ni), ustvarjen, vir (main|veja), osvezi=true|false, nalozi=true|false
    --tek ID: samo artefakt tega teka; ce ni zaupanja vreden, korak pade (izrecna izbira se nikoli tiho ne zamenja).
Napaka API korak ustavi (ponovni zagon posla traja minute; tiha gradnja WebKita 2-3 h).
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Callable, NamedTuple, Optional

GLAVNA = "main"
DELOVNI_TOK = ".github/workflows/linux-packages.yml"
#: Artefakt potece po 90 dneh; starejsega od 60 dni tek iste domene nalozi znova, da se nespremenjena gradnja ne ponovi.
OSVEZI_PO_DNEH = 60
DOVOLJENI_ZNAKI = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
SHA = re.compile(r"^[0-9a-f]{40}$")
#: Najvec strani po 100 artefaktov z istim imenom (en kljuc; vec bi pomenilo napako v toku).
NAJVEC_STRANI = 10
PISANJE = ("push", "workflow_dispatch")


class Potrosnik(NamedTuple):
    """Tek, ki artefakt isce (GITHUB_REF, GITHUB_EVENT_NAME, pri pull_request se GITHUB_HEAD_REF)."""
    ref: str
    dogodek: str
    glava_pr: str = ""

    @property
    def veja(self) -> Optional[str]:
        """Ime veje pri potisku ali rocnem zagonu veje; oznaka in pull_request je nimata (nalaganje, osvezitev)."""
        if self.ref.startswith("refs/heads/") and self.dogodek in PISANJE:
            return self.ref[len("refs/heads/"):]
        return None

    @property
    def domaca_veja(self) -> Optional[str]:
        """Veja, katere teki so temu teku vir poleg main: ista veja; pri pull_request veja glave PR (ponovni pregled N2:
        isti commit ali isti kljuc je ta veja ze zgradila). Vir mora se vedno biti potisk ali rocni zagon TEGA
        repozitorija (vir()), zato PR iz forka z enakim imenom veje dobi le artefakt nase veje; nalaga ostane samo veja."""
        if self.veja is not None:
            return self.veja
        if self.dogodek == "pull_request" and self.glava_pr and not self.glava_pr.startswith("refs/") \
                and self.glava_pr != GLAVNA:
            return self.glava_pr
        return None

    @property
    def nalaga(self) -> bool:
        """Ali je artefakt tega teka komu lahko vir (main samo ob potisku, druga veja ob potisku ali rocnem zagonu)."""
        return self.veja is not None and (self.veja != GLAVNA or self.dogodek == "push")


def iz_glavne(tek: dict, api: Callable[[str], dict], repo: str, opozori: Callable[[str], None] = lambda s: None) -> bool:
    """Tek veje main ob potisku. head_branch nosi tudi ime oznake (tek oznake »main«, ki bi jo sprozil spremenjen tok v
    commitu oznake), zato (ponovni pregled 25. 10. 2026, N1):
      (a) primerjava s SHA veje refs/heads/main (git/ref/heads/main), ne z imenom »main«, ki je ob oznaki main dvoumno;
      (b) commit teka je bil vrh refs/heads/main (dejavnost repozitorija: push, pr_merge ...), ne le vmesni commit
          zdruzene veje, katerega tok ni nikoli tekel kot main. Brez dokaza (API nedosegljiv) vir ni zaupanja vreden."""
    if tek.get("head_branch") != GLAVNA or tek.get("event") != "push":
        return False
    sha = tek.get("head_sha") or ""
    if not SHA.match(sha):
        return False
    sha_main = str(((api("/repos/%s/git/ref/heads/%s" % (repo, GLAVNA)) or {}).get("object") or {}).get("sha") or "")
    if not SHA.match(sha_main):
        return False
    if api("/repos/%s/compare/%s...%s?per_page=1" % (repo, sha, sha_main)).get("status") not in ("ahead", "identical"):
        return False
    try:
        dejavnosti = api("/repos/%s/activity?ref=refs/heads/%s&per_page=100&time_period=quarter" % (repo, GLAVNA))
    except urllib.error.HTTPError as e:
        if e.code in (403, 404, 422):
            opozori("::warning::dejavnosti refs/heads/main ni mogoce prebrati (%s) - artefakt main ni dokazan" % e.code)
            return False
        raise
    return any(isinstance(d, dict) and d.get("after") == sha and d.get("ref") in (None, "refs/heads/" + GLAVNA)
               and d.get("activity_type") != "branch_deletion" for d in (dejavnosti if isinstance(dejavnosti, list) else []))


def vir(tek: dict, repo_id: str, potrosnik: Potrosnik, api: Callable[[str], dict], repo: str,
        opozori: Callable[[str], None] = lambda s: None) -> Optional[str]:
    """'veja' (ista veja), 'main' ali None, ce tek za tega potrosnika ni zaupanja vreden."""
    if str((tek.get("head_repository") or {}).get("id")) != str(repo_id):
        return None
    if tek.get("path") != DELOVNI_TOK:                   # manjkajoce polje = zavrnitev (pregled M8)
        return None
    veja = potrosnik.domaca_veja
    if (veja is not None and veja != GLAVNA and tek.get("head_branch") == veja and tek.get("event") in PISANJE):
        return "veja"
    if iz_glavne(tek, api, repo, opozori):
        return "main"
    return None


def _predpomnjen(api: Callable[[str], dict]) -> Callable[[str], dict]:
    """Isti klic API v enem iskanju enkrat (glava main, dejavnost, primerjava za vec kandidatov)."""
    shramba: dict = {}

    def klic(pot: str):
        if pot not in shramba:
            shramba[pot] = api(pot)
        return shramba[pot]
    return klic


def _api(zeton: str) -> Callable[[str], dict]:
    osnova = os.environ.get("GITHUB_API_URL", "https://api.github.com")

    def klic(pot: str) -> dict:
        zahteva = urllib.request.Request(osnova + pot, headers={
            "Authorization": "Bearer " + zeton, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "safeer-ci-artefakt"})
        with urllib.request.urlopen(zahteva, timeout=30) as odgovor:     # noqa: S310 - samo GitHub API iz okolja CI
            return json.load(odgovor)
    return klic


def najdi(ime: str, repo: str, repo_id: str, potrosnik: Potrosnik, api: Callable[[str], dict], tek: str = "",
          opozori: Callable[[str], None] = lambda s: None) -> Optional[dict]:
    """Najnovejsi nepotekel artefakt z imenom ime iz zaupanja vrednega teka: {run_id, ustvarjen, vir, veja, sha} ali None.
    tek: samo artefakt tega teka (izrecna izbira)."""
    if not ime or set(ime) - DOVOLJENI_ZNAKI:
        raise ValueError("neveljavno ime artefakta: %r" % ime)
    if tek and not tek.isdigit():
        raise ValueError("id teka ni stevilo: %r" % tek)
    api = _predpomnjen(api)
    kandidati = []
    for stran in range(1, NAJVEC_STRANI + 1):
        podatki = api("/repos/%s/actions/artifacts?name=%s&per_page=100&page=%d" % (repo, urllib.parse.quote(ime), stran))
        artefakti = podatki.get("artifacts", [])
        kandidati += [a for a in artefakti if a.get("name") == ime and not a.get("expired")]
        if len(artefakti) < 100:
            break
    else:
        opozori("::warning::%s: vec kot %d artefaktov z istim imenom - starejsi niso pregledani" % (ime, 100 * NAJVEC_STRANI))
    kandidati.sort(key=lambda a: a.get("created_at") or "", reverse=True)
    for a in kandidati:
        wr = a.get("workflow_run") or {}
        tek_id = wr.get("id")
        if not tek_id or (tek and str(tek_id) != tek):
            continue
        # Pregled N5: kandidat, ki po podatkih artefakta ne more biti vir, brez klica API (odlocitev je spodaj iz teka).
        if ("head_repository_id" in wr and str(wr["head_repository_id"]) != str(repo_id)) or \
                ("head_branch" in wr and wr["head_branch"] not in (GLAVNA, potrosnik.domaca_veja)):
            continue
        podatki_teka = api("/repos/%s/actions/runs/%s" % (repo, int(tek_id)))
        izvor = vir(podatki_teka, repo_id, potrosnik, api, repo, opozori)
        if izvor:
            return {"run_id": str(int(tek_id)), "ustvarjen": a.get("created_at") or "", "vir": izvor,
                    "veja": str(podatki_teka.get("head_branch") or ""), "sha": str(podatki_teka.get("head_sha") or "")}
        opozori("::warning::%s iz teka %s ni iz zaupanja vrednega teka za %s (repozitorij, tok, dogodek, veja) - ga ne "
                "uporabimo" % (ime, int(tek_id), potrosnik.ref))
    return None


def star(ustvarjen: str, zdaj: Optional[datetime] = None, dni: int = OSVEZI_PO_DNEH) -> bool:
    try:
        cas = datetime.strptime(ustvarjen, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return ((zdaj or datetime.now(timezone.utc)) - cas).total_seconds() > dni * 86400


def osvezi(izid: Optional[dict], potrosnik: Potrosnik, zdaj: Optional[datetime] = None) -> bool:
    """Ponovno nalaganje starega artefakta samo v isti domeni (pregled M3: sicer bi tek main opral artefakt veje)."""
    if not izid or not potrosnik.nalaga or not star(izid["ustvarjen"], zdaj):
        return False
    return izid["vir"] == "veja" or (izid["vir"] == "main" and potrosnik.veja == GLAVNA)


def main(argv: list) -> int:
    if len(argv) not in (2, 4) or argv[0] != "najdi" or (len(argv) == 4 and argv[2] != "--tek"):
        print(__doc__, file=sys.stderr)
        return 2
    ime, tek = argv[1], (argv[3] if len(argv) == 4 else "")
    potrosnik = Potrosnik(os.environ.get("GITHUB_REF", ""), os.environ.get("GITHUB_EVENT_NAME", ""),
                          os.environ.get("GITHUB_HEAD_REF", ""))
    try:
        izid = najdi(ime, os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_REPOSITORY_ID"], potrosnik,
                     _api(os.environ["GH_TOKEN"]), tek, opozori=print)
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        print("::error::%s: iskanje artefakta ni uspelo (%s) - ponovi posel" % (ime, e))
        return 1
    if tek and not izid:
        print("::error::tek %s nima zaupanja vrednega artefakta %s za %s" % (tek, ime, potrosnik.ref))
        return 1
    stari = osvezi(izid, potrosnik)
    vrstice = ["ime=" + ime, "run_id=" + (izid["run_id"] if izid else ""),
               "ustvarjen=" + (izid["ustvarjen"] if izid else ""), "vir=" + (izid["vir"] if izid else ""),
               "osvezi=" + ("true" if stari else "false"),
               "nalozi=" + ("true" if potrosnik.nalaga and (not izid or stari) else "false")]
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write("\n".join(vrstice) + "\n")
    if izid:
        print("::notice::%s iz teka %s (veja %s, commit %s, %s)" % (ime, izid["run_id"], izid["veja"], izid["sha"][:12],
                                                                     izid["ustvarjen"]))
    else:
        print("::notice::%s: zaupanja vrednega artefakta za %s ni - gradnja v tem teku" % (ime, potrosnik.ref))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
