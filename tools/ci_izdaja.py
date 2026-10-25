#!/usr/bin/env python3
"""Paketi izdaje so natanko paketi zelenega teka veje za ISTI commit (lastnik 25. 10. 2026: »Izdaja je samo to, kar
preizkusim in recem, da lahko objavimo.«; AGENTS.md: paketi izdaje so artefakti zelenega teka veje za isti commit, ne
nova gradnja iz oznake).

Ob oznaki v* CI nicesar ne gradi (vsi posli razen release/beta-izdaja se preskocijo). Posel izdaje:
  najdi  -> tek tega repozitorija (head_repository), tega toka (path), dogodek push ali workflow_dispatch, head_sha ==
            commit oznake, zakljucek success, vsak posel iz POSLI_IZDAJE uspesen (ne preskocen) in vsi ARTEFAKTI
            nepotekli. Enak commit in enak tok = ista koda gradnje, zato velja meja zaupanja (pregled 25. 10. 2026, M1).
            Rocni zagon z vhodi, ki spremenijo gradnjo (pgo, pgo_profraw_run: drug profil PGO), artefakta paketi-izdaje
            ne nalozi, zato ga najdi nikoli ne izbere; vhodi.json to pri izdaji se enkrat preveri (API vhodov preteklega
            teka ne vrne). Ce takega teka ni, korak PADE z jasnim sporocilom - oznaka nikoli ne gradi.
            Ce je zelenih tekov istega commita vec (npr. v1.0.128: main in gtk4-deb-webkit, gradnje niso bit za bit enake),
            CI ne ve, katerega je lastnik preizkusil: korak PADE s seznamom tekov; izbira je rocni zagon na oznaki z vhodom
            izdaja_tek (IZDAJA_TEK), ki mora prestati iste preverbe. Najnovejsi tek ni privzet: to bi lahko bil nepreizkusen.
  preveri MAPA PAKETI-IZDAJE CILJ
         -> vsak paket iz SHA256SUMS teka obstaja in ima isto SHA-256, drugih paketov ni (AppImage ali neznana
            datoteka = napaka); nespremenjene kopije in isti SHA256SUMS v CILJ.
Uporaba v koraku: GH_TOKEN, IZDAJA_TEK (prazno ali id teka); GITHUB_REPOSITORY, GITHUB_REPOSITORY_ID, GITHUB_SHA,
GITHUB_RUN_ID, GITHUB_REF_NAME, GITHUB_OUTPUT (GitHub).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

DELOVNI_TOK = ".github/workflows/linux-packages.yml"
#: Posli, ki morajo biti v izvornem teku uspesni (prej needs poslov release/beta-izdaja) - izdaja ne nastane, ce na primer
#: namestitev na Linux Mintu (mint) ali preizkusi z nasim WebKitom padejo.
POSLI_IZDAJE = ("hitra-vrata", "preizkusi-webkit", "brskalnik", "safeer-os", "qt-xcb", "flatpak", "flatpak-brskalnik",
                "scit-lab", "mint", "debian", "paketi-izdaje")
#: Artefakti izvornega teka, ki jih izdaja prenese (paketi in seznam SHA-256).
ARTEFAKTI = ("brskalnik", "safeer-os", "flatpak", "flatpak-brskalnik", "paketi-izdaje")
PISANJE = ("push", "workflow_dispatch")
SHA = re.compile(r"^[0-9a-f]{40}$")
IME_PAKETA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+~-]*\.(deb|flatpak)$")
NAJVEC_STRANI = 10


class NapakaIzdaje(Exception):
    pass


def _strani(api: Callable[[str], dict], pot: str, kljuc: str) -> List[dict]:
    izid: List[dict] = []
    for stran in range(1, NAJVEC_STRANI + 1):
        podatki = api("%s%sper_page=100&page=%d" % (pot, "&" if "?" in pot else "?", stran))
        del_ = podatki.get(kljuc, [])
        izid += del_
        if len(del_) < 100:
            break
    return izid


def _posel_izdaje(ime: str) -> Optional[str]:
    """Ime posla v API (»mint (22)« za matriko) -> posel iz POSLI_IZDAJE ali None."""
    for posel in POSLI_IZDAJE:
        if ime == posel or ime.startswith(posel + " ("):
            return posel
    return None


def razlog_teka(tek: dict, repo_id: str, sha: str, tekoci: str) -> Optional[str]:
    """Razlog iz podatkov teka samega (repozitorij, tok, commit, dogodek, zakljucek) ali None."""
    if str(tek.get("id")) == str(tekoci):
        return "ta tek"
    if str((tek.get("head_repository") or {}).get("id")) != str(repo_id):
        return "drug repozitorij"
    if tek.get("path") != DELOVNI_TOK:
        return "drug tok (%s)" % tek.get("path")
    if tek.get("head_sha") != sha:
        return "drug commit"
    if tek.get("event") not in PISANJE:
        return "dogodek %s" % tek.get("event")
    if tek.get("status") != "completed" or tek.get("conclusion") != "success":
        return "ni zelen (%s/%s)" % (tek.get("status"), tek.get("conclusion"))
    return None


def zakaj_ne(tek: dict, repo_id: str, sha: str, tekoci: str, posli: List[dict], artefakti: List[dict]) -> Optional[str]:
    """Razlog, zakaj tek ni vir paketov izdaje, ali None, ce je."""
    razlog = razlog_teka(tek, repo_id, sha, tekoci)
    if razlog:
        return razlog
    uspesni: Dict[str, bool] = {}
    for p in posli:
        posel = _posel_izdaje(p.get("name") or "")
        if posel:
            uspesni[posel] = uspesni.get(posel, True) and p.get("conclusion") == "success"
    manjka = [p for p in POSLI_IZDAJE if not uspesni.get(p)]
    if manjka:
        return "posli niso uspesni: %s" % ", ".join(manjka)
    imena = {a.get("name") for a in artefakti if not a.get("expired")}
    manjka = [a for a in ARTEFAKTI if a not in imena]
    if manjka:
        return "ni artefaktov: %s" % ", ".join(manjka)
    return None


def najdi(repo: str, repo_id: str, sha: str, tekoci: str, api: Callable[[str], dict], izbran_tek: str = "",
          oznaka: str = "<oznaka>") -> dict:
    if not SHA.match(sha or ""):
        raise NapakaIzdaje("commit oznake ni SHA: %r" % sha)
    if izbran_tek and not izbran_tek.isdigit():
        raise NapakaIzdaje("izdaja_tek ni id teka: %r" % izbran_tek)
    teki = _strani(api, "/repos/%s/actions/workflows/linux-packages.yml/runs?head_sha=%s" % (repo, sha), "workflow_runs")
    teki.sort(key=lambda t: (t.get("created_at") or "", t.get("id") or 0), reverse=True)
    if izbran_tek:
        teki = [t for t in teki if str(t.get("id")) == izbran_tek]
        if not teki:
            raise NapakaIzdaje("izbrani tek %s ni tek toka %s za commit %s" % (izbran_tek, DELOVNI_TOK, sha))
    zavrnjeni, ustrezni = [], []
    for t in teki:
        razlog = razlog_teka(t, repo_id, sha, tekoci)
        if razlog:
            zavrnjeni.append("%s: %s" % (t.get("id"), razlog))
            continue
        posli = _strani(api, "/repos/%s/actions/runs/%d/jobs?filter=latest" % (repo, int(t["id"])), "jobs")
        artefakti = _strani(api, "/repos/%s/actions/runs/%d/artifacts" % (repo, int(t["id"])), "artifacts")
        razlog = zakaj_ne(t, repo_id, sha, tekoci, posli, artefakti)
        if razlog:
            zavrnjeni.append("%s: %s" % (t.get("id"), razlog))
            continue
        ustrezni.append(t)
    if not ustrezni:
        raise NapakaIzdaje("za commit %s ni zelenega teka veje (push ali rocni zagon brez vhodov gradnje, tok %s) s "
                           "paketi izdaje - oznaka nicesar ne gradi. Pocakaj na zelen tek veje tega commita, ga preizkusi "
                           "in ponovi ta posel. Pregledani teki: %s" % (sha, DELOVNI_TOK, "; ".join(zavrnjeni) or "nobenega"))
    if len(ustrezni) > 1:
        raise NapakaIzdaje("commit %s ima %d zelenih tekov s paketi izdaje (%s); paketi tekov niso enaki in CI ne ve, "
                           "katere je lastnik preizkusil. Izberi preizkuseni tek: gh workflow run linux-packages.yml --ref "
                           "%s -f izdaja_tek=<id>" % (sha, len(ustrezni), "; ".join(
                               "%s: veja %s, %s, %s" % (t["id"], t.get("head_branch"), t.get("event"), t.get("created_at"))
                               for t in ustrezni), oznaka))
    izbran = ustrezni[0]
    return {"run_id": str(int(izbran["id"])), "veja": str(izbran.get("head_branch") or ""),
            "dogodek": str(izbran.get("event") or ""), "ustvarjen": str(izbran.get("created_at") or "")}


def _sha256(pot: Path) -> str:
    h = hashlib.sha256()
    with open(pot, "rb") as f:
        for kos in iter(lambda: f.read(1 << 20), b""):
            h.update(kos)
    return h.hexdigest()


def _seznam(pot: Path) -> List[Tuple[str, str]]:
    vrstice = []
    for v in pot.read_text(encoding="utf-8").splitlines():
        if not v.strip():
            continue
        m = re.fullmatch(r"([0-9a-f]{64})  (\S+)", v)
        if not m or not IME_PAKETA.match(m.group(2)) or m.group(2).startswith("safeer-webkit_"):
            raise NapakaIzdaje("neveljavna vrstica v SHA256SUMS: %r" % v)
        vrstice.append((m.group(1), m.group(2)))
    if not vrstice:
        raise NapakaIzdaje("SHA256SUMS paketov izdaje je prazen")
    if len({ime for _, ime in vrstice}) != len(vrstice):
        raise NapakaIzdaje("podvojeno ime v SHA256SUMS")
    return vrstice


def preveri_vhode(pot: Path) -> None:
    """Rocni zagon samo s privzetimi vhodi (pgo in pgo_profraw_run spremenita profil PGO, torej gradnjo)."""
    vhodi = json.loads(pot.read_text(encoding="utf-8"))
    if vhodi.get("dogodek") not in PISANJE:
        raise NapakaIzdaje("paketi niso iz potiska ali rocnega zagona: %r" % vhodi.get("dogodek"))
    if vhodi.get("dogodek") == "workflow_dispatch" and (str(vhodi.get("pgo")) == "true" or vhodi.get("pgo_profraw_run")):
        raise NapakaIzdaje("rocni zagon z vhodi gradnje (pgo=%r, pgo_profraw_run=%r) ni vir izdaje"
                           % (vhodi.get("pgo"), vhodi.get("pgo_profraw_run")))


def preveri(mapa: Path, paketi_izdaje: Path, cilj: Path) -> List[Tuple[str, str]]:
    seznam = _seznam(paketi_izdaje / "SHA256SUMS")
    preveri_vhode(paketi_izdaje / "vhodi.json")
    najdeni: Dict[str, Path] = {}
    for p in sorted(mapa.rglob("*")):
        if not p.is_file() or paketi_izdaje in p.parents:
            continue
        if p.name.lower().endswith(".appimage"):
            raise NapakaIzdaje("AppImage med artefakti izdaje: %s" % p)
        if p.name.endswith((".deb", ".flatpak")) and not p.name.startswith("safeer-webkit_"):
            if p.name in najdeni:
                raise NapakaIzdaje("paket %s je dvakrat med artefakti" % p.name)
            najdeni[p.name] = p
    imena = {ime for _, ime in seznam}
    if set(najdeni) != imena:
        raise NapakaIzdaje("paketi se ne ujemajo s SHA256SUMS teka: manjka %s, odvec %s"
                           % (sorted(imena - set(najdeni)), sorted(set(najdeni) - imena)))
    cilj.mkdir(parents=True, exist_ok=True)
    for vsota, ime in seznam:
        dejanska = _sha256(najdeni[ime])
        if not hmac.compare_digest(dejanska, vsota):
            raise NapakaIzdaje("SHA-256 paketa %s se ne ujema (%s, v seznamu %s)" % (ime, dejanska, vsota))
        shutil.copyfile(najdeni[ime], cilj / ime)
        if not hmac.compare_digest(_sha256(cilj / ime), vsota):
            raise NapakaIzdaje("kopija %s se ne ujema" % ime)
    (cilj / "SHA256SUMS").write_text("".join("%s  %s\n" % v for v in seznam), encoding="utf-8")
    return seznam


def _api(zeton: str) -> Callable[[str], dict]:
    osnova = os.environ.get("GITHUB_API_URL", "https://api.github.com")

    def klic(pot: str) -> dict:
        zahteva = urllib.request.Request(osnova + pot, headers={
            "Authorization": "Bearer " + zeton, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "safeer-ci-izdaja"})
        with urllib.request.urlopen(zahteva, timeout=30) as odgovor:     # noqa: S310 - samo GitHub API iz okolja CI
            return json.load(odgovor)
    return klic


def main(argv: List[str]) -> int:
    try:
        if argv == ["najdi"]:
            izid = najdi(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_REPOSITORY_ID"], os.environ.get("GITHUB_SHA", ""),
                         os.environ.get("GITHUB_RUN_ID", ""), _api(os.environ["GH_TOKEN"]),
                         izbran_tek=os.environ.get("IZDAJA_TEK", "").strip(),
                         oznaka=os.environ.get("GITHUB_REF_NAME", "") or "<oznaka>")
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
                f.write("".join("%s=%s\n" % (k, izid[k]) for k in ("run_id", "veja", "dogodek", "ustvarjen")))
            print("::notice::paketi izdaje iz teka %s (veja %s, %s, %s) - v tem teku se nic ne gradi"
                  % (izid["run_id"], izid["veja"], izid["dogodek"], izid["ustvarjen"]))
            return 0
        if len(argv) == 4 and argv[0] == "preveri":
            seznam = preveri(Path(argv[1]), Path(argv[2]), Path(argv[3]))
            for vsota, ime in seznam:
                print("%s  %s" % (vsota, ime))
            return 0
    except NapakaIzdaje as e:
        print("::error::%s" % e)
        return 1
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        print("::error::paketi izdaje: %s - ponovi posel" % e)
        return 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
