#!/usr/bin/env python3
"""Mesecno porocilo CI Safeer-linux iz GitHub API (lastnik 25. 10. 2026: »za veliko gradnje je relativno malo uspehov,
to bova morala zelo izboljsati« - vsak mesec izmerimo, ali se je izboljsalo).

Isto kot rocna analiza oktobra 2026 (926 tekov, 144 padlih, 243 gradenj WebKita = 468 h): teki po izidu, posli nad 45 min
(gradnje WebKita) in njihove ure, vzroki padcev po poslu in koraku, veje z najvec padci, ter cas do prve napake in do
zelenega teka (cilj hitrih vrat: prva napaka preizkusa v minutah, ne po urah gradnje).

Uporaba:  python3 tools/ci_porocilo.py 2026-10 [--do 2026-10-25] [--repo safeerOS/Safeer-linux]
                                       [--predpomnilnik MAPA] [--izhod POROCILO.md]
Dostop: GH_TOKEN ali GITHUB_TOKEN v okolju (samo branje: actions:read), sicer prijavljeni `gh api`.
Koncani teki se shranijo v --predpomnilnik (nespremenljivi), ponovni zagon jih ne prenasa znova.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Callable, Dict, Iterable, List, Optional

DELOVNI_TOK = "linux-packages.yml"
DOLG_POSEL_MIN = 45
GRADNJE = ("webkit-", "flatpak")


def _cas(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _minute(posel: dict) -> float:
    a, b = _cas(posel.get("started_at")), _cas(posel.get("completed_at"))
    if not a or not b or b < a:
        return 0.0
    return (b - a).total_seconds() / 60


def _prvi_padli_korak(posel: dict) -> str:
    for k in posel.get("steps") or []:
        if k.get("conclusion") == "failure":
            return k.get("name") or "?"
    return "(brez padlega koraka: %s)" % (posel.get("conclusion") or "?")


def _ura(m: float) -> str:
    return "%.0f h" % (m / 60) if m >= 90 else "%.0f min" % m


def porocilo(teki: List[dict], posli: Dict[int, List[dict]], naslov: str) -> str:
    """Markdown iz tekov (actions/runs) in poslov po teku (actions/runs/<id>/jobs)."""
    izidi = Counter(t.get("conclusion") or t.get("status") or "?" for t in teki)
    vrstice = ["# CI Safeer-linux %s - izmerjeno z GitHub API %s" % (naslov, datetime.now(timezone.utc).strftime("%d. %m. %Y %H:%M UTC")),
               "", "Tok: .github/workflows/%s." % DELOVNI_TOK, "", "## Teki",
               "- %d tekov: %d uspesnih, %d padlih, %d preklicanih%s." % (
                   len(teki), izidi.get("success", 0), izidi.get("failure", 0), izidi.get("cancelled", 0),
                   "".join(", %d %s" % (n, k) for k, n in sorted(izidi.items())
                           if k not in ("success", "failure", "cancelled")))]
    uspesnost = 100.0 * izidi.get("success", 0) / max(1, len(teki) - izidi.get("cancelled", 0))
    vrstice.append("- Uspesnost brez preklicanih: %.0f %%." % uspesnost)
    vsi_posli = [p for pp in posli.values() for p in pp]
    ure = sum(_minute(p) for p in vsi_posli)
    vrstice.append("- Racunanje vseh poslov: %s." % _ura(ure))

    dolgi = [p for p in vsi_posli if _minute(p) > DOLG_POSEL_MIN]
    gradnje = [p for p in dolgi if (p.get("name") or "").startswith(GRADNJE)]
    teki_z_gradnjo = {p.get("run_id") for p in gradnje}
    vrstice.append("- %d tekov je gradilo WebKit (posel webkit-*/flatpak* nad %d min); %d takih poslov = %s." % (
        len(teki_z_gradnjo), DOLG_POSEL_MIN, len(gradnje), _ura(sum(_minute(p) for p in gradnje))))
    po_imenu: Dict[str, List[dict]] = defaultdict(list)
    for p in dolgi:
        po_imenu[p.get("name") or "?"].append(p)
    if po_imenu:
        vrstice.append("- Po poslih (>%d min): " % DOLG_POSEL_MIN + ", ".join(
            "%s %d (%s; %d/%d/%d)" % (ime, len(pp), _ura(sum(_minute(p) for p in pp)),
                                      sum(p.get("conclusion") == "success" for p in pp),
                                      sum(p.get("conclusion") == "failure" for p in pp),
                                      sum(p.get("conclusion") == "cancelled" for p in pp))
            for ime, pp in sorted(po_imenu.items(), key=lambda x: -sum(_minute(p) for p in x[1]))) +
            " (uspesni/padli/preklicani).")

    # Cas do prve napake (padli teki) in do zelenega (uspesni) - cilj hitrih vrat.
    do_napake, do_zelenega = [], []
    for t in teki:
        zacetek = _cas(t.get("run_started_at") or t.get("created_at"))
        if not zacetek:
            continue
        if t.get("conclusion") == "failure":
            konci = [_cas(p.get("completed_at")) for p in posli.get(t["id"], []) if p.get("conclusion") == "failure"]
            konci = [k for k in konci if k]
            if konci:
                do_napake.append((min(konci) - zacetek).total_seconds() / 60)
        elif t.get("conclusion") == "success" and _cas(t.get("updated_at")):
            do_zelenega.append((_cas(t["updated_at"]) - zacetek).total_seconds() / 60)
    vrstice += ["", "## Cas do izida"]
    if do_napake:
        vrstice.append("- Do prve napake (padli teki, %d): mediana %s, najhitreje %s, najkasneje %s." % (
            len(do_napake), _ura(median(do_napake)), _ura(min(do_napake)), _ura(max(do_napake))))
    if do_zelenega:
        vrstice.append("- Do zelenega teka (%d): mediana %s." % (len(do_zelenega), _ura(median(do_zelenega))))
    # Enotski preizkusi (koraki »Unit tests*«: prej v poslu safeer-os po gradnji WebKita, od 25. 10. 2026 hitra-vrata in
    # preizkusi-webkit): kdaj se zacnejo, koliko trajajo in kdaj je znana prva napaka preizkusa.
    zacetki, trajanja, napake = [], [], []
    for t in teki:
        zacetek = _cas(t.get("run_started_at") or t.get("created_at"))
        koraki = [k for p in posli.get(t["id"], []) for k in p.get("steps") or []
                  if (k.get("name") or "").startswith("Unit tests") and _cas(k.get("started_at"))]
        if not zacetek or not koraki:
            continue
        zacetki.append((min(_cas(k["started_at"]) for k in koraki) - zacetek).total_seconds() / 60)
        trajanja += [_minute(k) for k in koraki if k.get("conclusion") in ("success", "failure")]
        padli_k = [_cas(k.get("completed_at")) for k in koraki if k.get("conclusion") == "failure" and k.get("completed_at")]
        if padli_k:
            napake.append((min(padli_k) - zacetek).total_seconds() / 60)
    if zacetki:
        vrstice.append("- Enotski preizkusi (%d tekov): zacetek mediana %s po zacetku teka (najkasneje %s), korak traja "
                       "mediana %s." % (len(zacetki), _ura(median(zacetki)), _ura(max(zacetki)),
                                        _ura(median(trajanja)) if trajanja else "?"))
    if napake:
        vrstice.append("- Prva napaka enotskega preizkusa (%d tekov): mediana %s po zacetku teka, najkasneje %s." % (
            len(napake), _ura(median(napake)), _ura(max(napake))))

    padli = [t for t in teki if t.get("conclusion") == "failure"]
    vzroki = Counter()
    for t in padli:
        for p in posli.get(t["id"], []):
            if p.get("conclusion") == "failure":
                vzroki["%s :: %s" % (p.get("name"), _prvi_padli_korak(p))] += 1
    vrstice += ["", "## Vzroki %d padlih tekov (posel in korak, ki je padel)" % len(padli)]
    vrstice += ["- %d %s" % (n, v) for v, n in vzroki.most_common(15)]
    preizkusi = sum(n for v, n in vzroki.items() if "Unit tests" in v or v.startswith(("hitra-vrata", "preizkusi-webkit")))
    vrstice.append("- Od tega nasi enotski preizkusi: %d." % preizkusi)
    veje = Counter(t.get("head_branch") for t in padli)
    if veje:
        vrstice.append("- Veje z najvec padci: " + ", ".join("%s %d" % (v, n) for v, n in veje.most_common(5)) + ".")
    return "\n".join(vrstice) + "\n"


# ------------------------------------------------------------------------------------------------ GitHub API
def api_gh(pot: str) -> dict:
    """Brez zetona v okolju: prijavljeni GitHub CLI (zeton ostane v gh, ne v tem procesu)."""
    r = subprocess.run(["gh", "api", pot.lstrip("/")], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise SystemExit("gh api %s: %s" % (pot, (r.stderr or r.stdout).strip()[:300]))
    return json.loads(r.stdout)


def api_iz_zetona(zeton: str) -> Callable[[str], dict]:
    def klic(pot: str) -> dict:
        zahteva = urllib.request.Request("https://api.github.com" + pot, headers={
            "Authorization": "Bearer " + zeton, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "safeer-ci-porocilo"})
        with urllib.request.urlopen(zahteva, timeout=60) as o:     # noqa: S310 - samo api.github.com
            return json.load(o)
    return klic


def _obdobja(od: datetime, do: datetime, dni: int = 7) -> Iterable[str]:
    """Iskanje tekov vrne najvec 1000 zadetkov: mesec po tednih."""
    while od < do:
        konec = min(do, od + timedelta(days=dni))
        yield "%s..%s" % (od.strftime("%Y-%m-%dT%H:%M:%SZ"), (konec - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        od = konec


def teki_obdobja(api: Callable[[str], dict], repo: str, od: datetime, do: datetime) -> List[dict]:
    teki: Dict[int, dict] = {}
    for obdobje in _obdobja(od, do):
        stran = 1
        while True:
            d = api("/repos/%s/actions/workflows/%s/runs?per_page=100&page=%d&created=%s" % (
                repo, DELOVNI_TOK, stran, urllib.parse.quote(obdobje)))
            for t in d.get("workflow_runs", []):
                teki[t["id"]] = t
            if len(d.get("workflow_runs", [])) < 100:
                break
            stran += 1
    return sorted(teki.values(), key=lambda t: t["id"])


def posli_teka(api: Callable[[str], dict], repo: str, tek: dict, predpomnilnik: Optional[Path]) -> List[dict]:
    pot = predpomnilnik / ("%d.json" % tek["id"]) if predpomnilnik else None
    if pot and pot.is_file():
        return json.loads(pot.read_text(encoding="utf-8"))
    posli, stran = [], 1
    while True:
        d = api("/repos/%s/actions/runs/%d/jobs?per_page=100&page=%d" % (repo, tek["id"], stran))
        posli += d.get("jobs", [])
        if len(d.get("jobs", [])) < 100:
            break
        stran += 1
    if pot and tek.get("status") == "completed":
        pot.write_text(json.dumps(posli), encoding="utf-8")
    return posli


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("mesec", help="LLLL-MM")
    ap.add_argument("--do", help="zadnji dan (LLLL-MM-DD), privzeto konec meseca")
    ap.add_argument("--repo", default="safeerOS/Safeer-linux")
    ap.add_argument("--predpomnilnik", help="mapa za koncane teke (JSON poslov)")
    ap.add_argument("--izhod", help="datoteka Markdown (privzeto standardni izhod)")
    a = ap.parse_args(argv)
    od = datetime.strptime(a.mesec + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
    naslednji = (od + timedelta(days=32)).replace(day=1)
    do = naslednji if not a.do else datetime.strptime(a.do, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    predpomnilnik = Path(a.predpomnilnik) if a.predpomnilnik else None
    if predpomnilnik:
        predpomnilnik.mkdir(parents=True, exist_ok=True)
    zeton = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    api = api_iz_zetona(zeton) if zeton else api_gh
    teki = teki_obdobja(api, a.repo, od, min(do, naslednji))
    posli = {t["id"]: posli_teka(api, a.repo, t, predpomnilnik) for t in teki}
    naslov = "%s (%s-%s)" % (a.mesec, od.strftime("%d. %m."), (min(do, naslednji) - timedelta(days=1)).strftime("%d. %m. %Y"))
    besedilo = porocilo(teki, posli, naslov)
    if a.izhod:
        Path(a.izhod).write_text(besedilo, encoding="utf-8")
    else:
        sys.stdout.write(besedilo)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
