#!/usr/bin/env python3
"""Podpisan seznam beta razlicic (razlicice-beta.json + .sig) za Beta kanal Safeer OS (docs/BETA.md).

Lastnik ga pozene na racunalniku s kljucem, s katerim se podpisuje razlicice.json (key id »safeer-razlicice-2026-10«,
ki ga ni v nobenem repozitoriju), ko je predizdaja na GitHubu objavljena:

    gh release download v1.0.128-beta.1 --repo safeerOS/Safeer-linux --dir <mapa>
    python3 tools/beta_seznam.py --oznaka v1.0.128-beta.1 --mapa <mapa> --kljuc <zasebni kljuc> --izhod <mapa izhoda>

Obe datoteki iz <mapa izhoda> gresta na https://safeer.si/os/ (ob razlicice.json). Orodje samo izracuna SHA-256 vsakega
paketa in ga primerja s SHA256SUMS izdaje; pred zapisom preveri, da je predizdaja na GitHubu objavljena (ne osnutek)
in da imajo njene datoteke iste velikosti; podpis preveri z javnim kljucem, ki ga ima program (core/os_posodobitve.KLJUCI).
Podpis ima lasten kontekst (KONTEKST_BETA): beta seznam noben odjemalec ne sprejme kot stabilnega.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import os_posodobitve as op  # noqa: E402

REPO = "safeerOS/Safeer-linux"
KEY_ID = "safeer-razlicice-2026-10"
OZNAKA = re.compile(r"v(\d+\.\d+\.\d+(-beta\.\d+))")
_VRSTICA_VSOT = re.compile(r"([0-9a-f]{64}) [ *](.+)")


class Napaka(Exception):
    """Seznam ni bil zapisan (razlog v besedilu)."""


def _sha256(pot: str) -> str:
    h = hashlib.sha256()
    with open(pot, "rb") as f:
        for kos in iter(lambda: f.read(1 << 20), b""):
            h.update(kos)
    return h.hexdigest()


def vsote(mapa: str) -> Dict[str, str]:
    """{ime: sha256} iz SHA256SUMS izdaje (ki ga naredi posel beta-izdaja)."""
    pot = os.path.join(mapa, "SHA256SUMS")
    if not os.path.isfile(pot):
        raise Napaka("v mapi ni SHA256SUMS izdaje")
    izid = {}
    with open(pot, encoding="utf-8") as f:
        for vrstica in f:
            m = _VRSTICA_VSOT.fullmatch(vrstica.rstrip("\n"))
            if m:
                izid[m.group(2)] = m.group(1)
    return izid


def zgradi_seznam(oznaka: str, mapa: str, zdaj: datetime, dni: int = 30, repo: str = REPO,
                  novo: Optional[Dict[str, str]] = None) -> dict:
    """Seznam beta razlicic iz paketov v `mapa` (SHA-256 izracunan tu in enak kot v SHA256SUMS)."""
    m = OZNAKA.fullmatch(oznaka)
    if not m:
        raise Napaka("oznaka mora biti vX.Y.Z-beta.N: %s" % oznaka)
    brskalnik, konec = m.group(1), m.group(2)
    imena = sorted(os.listdir(mapa))
    os_debi = [re.fullmatch(r"safeer-os_(.+)_amd64\.deb", i) for i in imena]
    os_razlicice = sorted({x.group(1) for x in os_debi if x})
    if len(os_razlicice) != 1 or not os_razlicice[0].endswith(konec):
        raise Napaka("v mapi mora biti natanko en safeer-os_*%s_amd64.deb (najdeno: %s)" % (konec, os_razlicice or "nic"))
    razlicica_os = os_razlicice[0]
    sums = vsote(mapa)
    prenos = "https://github.com/%s/releases/download/%s/" % (repo, oznaka)

    def vnos(ime: str) -> dict:
        pot = os.path.join(mapa, ime)
        if not os.path.isfile(pot):
            raise Napaka("manjka paket %s" % ime)
        sha = _sha256(pot)
        if sums.get(ime) != sha:
            raise Napaka("SHA-256 paketa %s se ne ujema s SHA256SUMS izdaje" % ime)
        d = {"url": prenos + ime, "sha256": sha, "velikost": os.path.getsize(pot)}
        if not op.veljavna_datoteka(d):
            raise Napaka("vnos %s ni veljaven" % ime)
        return d

    # WebKit je od 20. 10. 2026 vgrajen v vsak paket .deb (ni vec "webkit_deb"); aplikacija Safeer OS (safeer-os-app) ima
    # svoj paket "deb_app" - posodobitev aplikacije nikoli ne prenese namiznega okolja (core/os_posodobitve.py).
    linux = {
        "safeer-os": {"razlicica": razlicica_os, "deb": vnos("safeer-os_%s_amd64.deb" % razlicica_os),
                      "deb_app": vnos("safeer-os-app_%s_amd64.deb" % razlicica_os),
                      "flatpak": vnos("Safeer-OS-%s-x86_64.flatpak" % razlicica_os)},
        "safeer-browser": {"razlicica": brskalnik, "deb": vnos("safeer-browser_%s_amd64.deb" % brskalnik),
                           "flatpak": vnos("Safeer-Browser-%s-x86_64.flatpak" % brskalnik)},
    }
    # AppImage samo, ce je v izdaji (od 1.0.132 se ne gradi, dokler ne nosi nasega WebKita - linux-packages.yml,
    # SAFEER_APPIMAGE). Brez vnosa uporabnik AppImage dobi stran s prenosi, ne polovicne posodobitve.
    for kljuc, ime in (("safeer-os", "Safeer-OS-%s-x86_64.AppImage" % razlicica_os),
                       ("safeer-browser", "Safeer-Browser-%s-x86_64.AppImage" % brskalnik)):
        if os.path.isfile(os.path.join(mapa, ime)) or ime in sums:     # v SHA256SUMS, a manjka: napaka (vnos)
            linux[kljuc]["appimage"] = vnos(ime)
    novo = {k: str(v) for k, v in (novo or {}).items() if v}
    if novo:
        linux["novo"] = novo
    cas = zdaj.astimezone(timezone.utc).replace(microsecond=0)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return {"kanal": op.KANAL_BETA, "oznaka": oznaka, "generirano": cas.strftime(fmt), "izdano": cas.strftime(fmt),
            "potece": (cas + timedelta(days=dni)).strftime(fmt), "linux": linux,
            "stran": "https://github.com/%s/releases/tag/%s" % (repo, oznaka)}


def podpisi(seznam: dict, zasebni_kljuc, key_id: str = KEY_ID) -> tuple:
    """(bajti razlicice-beta.json, bajti .sig). zasebni_kljuc: cryptography Ed25519PrivateKey."""
    podatki = json.dumps(seznam, ensure_ascii=False, indent=1).encode("utf-8") + b"\n"
    sig = zasebni_kljuc.sign(op.KONTEKST_BETA + podatki)
    podpis = json.dumps([{"alg": "ed25519", "key_id": key_id, "sig": base64.b64encode(sig).decode("ascii")}]).encode("ascii")
    return podatki, podpis


def preveri_na_githubu(oznaka: str, seznam: dict, repo: str = REPO, odpri=urllib.request.urlopen) -> None:
    """Predizdaja mora biti objavljena (osnutka API brez prijave ne vrne) in imeti iste datoteke in velikosti."""
    try:
        with odpri("https://api.github.com/repos/%s/releases/tags/%s" % (repo, oznaka), timeout=20) as o:
            izdaja = json.loads(o.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise Napaka("predizdaja %s na GitHubu ni objavljena ali ni dosegljiva (%s)" % (oznaka, e)) from None
    if izdaja.get("draft") or not izdaja.get("prerelease"):
        raise Napaka("izdaja %s mora biti objavljena predizdaja (prerelease), ne osnutek in ne stabilna" % oznaka)
    velikosti = {a.get("name"): a.get("size") for a in izdaja.get("assets") or []}
    for paket in seznam["linux"].values():
        for kljuc in ("deb", "deb_app", "flatpak", "appimage"):
            d = paket.get(kljuc) if isinstance(paket, dict) else None
            if d:
                ime = d["url"].rsplit("/", 1)[1]
                if velikosti.get(ime) != d["velikost"]:
                    raise Napaka("datoteka %s na GitHubu manjka ali ima drugo velikost" % ime)


def nalozi_kljuc(pot: str):
    """Zasebni kljuc Ed25519: PEM (PKCS8) ali 32-bajtno seme (surovo ali base64)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    with open(pot, "rb") as f:
        surovo = f.read()
    if b"-----BEGIN" in surovo:
        return serialization.load_pem_private_key(surovo, password=None)
    if len(surovo) == 32:
        return Ed25519PrivateKey.from_private_bytes(surovo)
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(surovo.strip(), validate=True))


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    a.add_argument("--oznaka", required=True, help="oznaka predizdaje, npr. v1.0.128-beta.1")
    a.add_argument("--mapa", required=True, help="mapa s paketi in SHA256SUMS izdaje (gh release download)")
    a.add_argument("--kljuc", required=True, help="zasebni kljuc za razlicice.json (PEM ali 32-bajtno seme)")
    a.add_argument("--key-id", default=KEY_ID)
    a.add_argument("--izhod", required=True)
    a.add_argument("--dni", type=int, default=30, help="koliko dni seznam velja (privzeto 30)")
    a.add_argument("--repo", default=REPO)
    for j in ("sl", "en", "de", "es", "fr", "it"):
        a.add_argument("--novo-" + j, default="", help="kratko »kaj je novo« (%s)" % j)
    a.add_argument("--brez-githuba", action="store_true", help="ne preveri objave na GitHubu (samo preizkus)")
    arg = a.parse_args(argv)
    try:
        novo = {j: getattr(arg, "novo_" + j) for j in ("sl", "en", "de", "es", "fr", "it")}
        seznam = zgradi_seznam(arg.oznaka, arg.mapa, datetime.now(timezone.utc), arg.dni, arg.repo, novo)
        if not arg.brez_githuba:
            preveri_na_githubu(arg.oznaka, seznam, arg.repo)
        podatki, podpis = podpisi(seznam, nalozi_kljuc(arg.kljuc), arg.key_id)
        try:   # isti preverbi kot v programu: kar bi odjemalec zavrnil, se ne zapise
            op.preveri_podpis(podatki, podpis, None, op.KONTEKST_BETA)
        except op.NapakaPodpisa:
            raise Napaka("kljuc ni tisti, ki mu program zaupa (core/os_posodobitve.KLJUCI)") from None
        op.preveri_svezino(json.loads(podatki))
    except Napaka as e:
        print("beta_seznam: " + str(e), file=sys.stderr)
        return 1
    os.makedirs(arg.izhod, exist_ok=True)
    for ime, vsebina in (("razlicice-beta.json", podatki), ("razlicice-beta.json.sig", podpis)):
        with open(os.path.join(arg.izhod, ime), "wb") as f:
            f.write(vsebina)
    print("Zapisano: %s (Safeer OS %s, velja do %s). Obe datoteki na https://safeer.si/os/."
          % (os.path.join(arg.izhod, "razlicice-beta.json"), seznam["linux"]["safeer-os"]["razlicica"], seznam["potece"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
