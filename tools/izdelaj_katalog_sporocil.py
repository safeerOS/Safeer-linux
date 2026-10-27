#!/usr/bin/env python3
"""Katalog storitev za Sporocila iz ferdium-recipes (MIT) - SAMO podatki: ime, zacetni naslov, ociscena ikona SVG, vir.

Pravilo Safeerja »brez receptov za posamezne strani« (ROADMAP.md, CONTRIBUTING.md): iz recepta beremo samo
package.json (id, name, version, license, config.serviceURL) in icon.svg. Kode receptov (webview.js, index.js,
service.css, darkmode.css) skripta NE bere in NE prenasa.

Oblika vnosa je enaka kot core/spletni_klepeti.KATALOG (id, ime, vrsta, splet, prenos) z dodatnimi polji:
  ikona_svg  - ociscen SVG (varna_svg.ocisti) ali prazen niz, ce ikone ni bilo mogoce varno ocistiti;
  izmerjeno  - False: naslova lastnik se ni izmeril na WebKitGTK (KATALOG v spletni_klepeti.py je izmerjen 15. 10. 2026);
  obstojeci  - id vnosa v Safeerjevem KATALOG, ce gre za isto storitev (isti id ali isti gostitelj po preselitvi);
  vir        - repo, pot recepta, commit, razlicica recepta, licenca in povezava na recept pri tem commitu.

Uporaba:
  python3 izdelaj_katalog.py --recepti POT/ferdium-recipes [--safeer POT/Safeer-linux] [--izhod katalog.json] [--vse]
Brez --vse gre v katalog izbor spodaj (klepeti, posta, AI asistenti); z --vse vse primerne storitve kot vrsta »drugo«,
ce niso v izboru. Izhod je doloceni (enak vhod -> enaki bajti): brez casa izdelave, le datum commita.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.parse

_MAPA = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_MAPA, os.path.dirname(_MAPA)]          # mapa skripte in (v Safeer-linux/tools) koren repozitorija
try:
    from core.varna_svg import NevarnaSvg, ocisti          # v repozitoriju Safeer-linux (tools/)
except ImportError:
    from varna_svg import NevarnaSvg, ocisti               # samostojno (mapa naloge)

REPO = "https://github.com/ferdium/ferdium-recipes"
#: Najvecja ociscena ikona v katalogu (bajti). Vecje so skoraj vedno vgrajene rastrske slike (data:image/png) - katalog
#: ostane majhen, kanal pa ikono strani dobi kot doslej (core/ikone_strani), ko je dodan.
NAJVEC_IKONA = 64_000
KLEPET, POSTA, AI, DRUGO = "klepet", "posta", "ai", "drugo"

#: Izbor za Sporocila (id receptov v ferdium-recipes). Odlocitev o vrsti je nasa (recepti nimajo kategorij).
#: Ni izbrano: storitve samo s timskim naslovom ({teamId}) ali lastnim streznikom (Mattermost, Zulip ...: v Safeerju
#: jih uporabnik doda z lastnim naslovom), druzbena omrezja brez poudarka na sporocilih, orodja za delo.
IZBOR = {
    KLEPET: """whatsapp telegram messenger instagram-direct-messages discord msteams hangoutschat android-messages
               element schildichat cinny fluffychat snapchat twitter-dm linkedin threema wechat wire
               BlueBubbles airmessage bip chatwork dingtalk dialpad gitter google-voice groupme guilded irccloud
               keybase.io kiwiirc lineworks max mewe mightytext mysms pulse-sms reddit-chat revolt ring-central
               steamchat stoat tchap viva-engage voxer webex-teams xing xmpp zalo bale eitaa gap igap rubika
               soroushplus fluxer-gg""".split(),
    POSTA: """gmail fastmail posteo proton-mail tutanota yahoo-mail yandex-mail zoho icloud-mail infomaniak-mail
              mailbox.org mailfence office365-owa purelymail riseup spikenow onmail notion-mail thundermail
              epicmail""".split(),
    AI: """chatgpt claude-ai google-gemini perplexity mistral deepseek grok poe hugging-chat duckduckgo-ai-chat
           chatllm deepai lobe-chat""".split(),
}


def _git(pot: str, *ukaz: str) -> str:
    return subprocess.run(["git", "-C", pot, *ukaz], capture_output=True, text=True, check=True).stdout.strip()


def _varno_ovrednoti(vozel, imena: dict):
    """ast -> vrednost: samo literali, seznami, slovarji in znana imena konstant (KLEPET, POSTA ...)."""
    if isinstance(vozel, ast.Constant):
        return vozel.value
    if isinstance(vozel, ast.Name) and vozel.id in imena:
        return imena[vozel.id]
    if isinstance(vozel, (ast.List, ast.Tuple)):
        return [_varno_ovrednoti(e, imena) for e in vozel.elts]
    if isinstance(vozel, ast.Dict):
        return {_varno_ovrednoti(k, imena): _varno_ovrednoti(v, imena) for k, v in zip(vozel.keys, vozel.values)}
    raise ValueError("ni literal: %s" % ast.dump(vozel)[:80])


def beri_safeer(pot: str):
    """KATALOG in PRESELJENI iz core/spletni_klepeti.py (brez uvoza modula)."""
    with open(os.path.join(pot, "core", "spletni_klepeti.py"), encoding="utf-8") as f:
        drevo = ast.parse(f.read())
    imena, izid = {}, {}
    for v in drevo.body:
        cilji = v.targets if isinstance(v, ast.Assign) else [v.target] if isinstance(v, ast.AnnAssign) else []
        vrednost = getattr(v, "value", None)
        if vrednost is None:
            continue
        if len(cilji) == 1 and isinstance(cilji[0], ast.Tuple) and isinstance(vrednost, ast.Tuple):
            for c, x in zip(cilji[0].elts, vrednost.elts):
                if isinstance(c, ast.Name) and isinstance(x, ast.Constant):
                    imena[c.id] = x.value
        for c in cilji:
            if isinstance(c, ast.Name) and isinstance(vrednost, ast.Constant):
                imena[c.id] = vrednost.value
            if isinstance(c, ast.Name) and c.id in ("KATALOG", "PRESELJENI"):
                izid[c.id] = _varno_ovrednoti(vrednost, imena)
    return izid.get("KATALOG", []), izid.get("PRESELJENI", {})


_GOSTITELJ = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")


def poenoti_naslov(url: str) -> str:
    """Samo https, brez poverilnic, veljaven gostitelj; prazna pot -> »/« (kot spletni_klepeti.preveri_naslov).
    Neveljaven naslov -> prazen niz."""
    s = str(url or "").strip()
    if not s or "{" in s or any(c.isspace() for c in s):
        return ""
    try:
        d = urllib.parse.urlsplit(s)
        vrata = d.port
    except ValueError:
        return ""
    gost = (d.hostname or "").lower().rstrip(".")
    if d.scheme.lower() != "https" or d.username or d.password or "@" in d.netloc or not _GOSTITELJ.match(gost):
        return ""
    return urllib.parse.urlunsplit(("https", gost + (":%d" % vrata if vrata else ""), d.path or "/", d.query, d.fragment))


def gostitelj(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def izdelaj(recepti: str, safeer: str = "", vse: bool = False) -> dict:
    commit = _git(recepti, "rev-parse", "HEAD")
    datum = _git(recepti, "log", "-1", "--format=%cI")
    with open(os.path.join(recepti, "LICENSE.md"), encoding="utf-8") as f:
        licenca = f.read().strip()
    katalog_safeer, preseljeni = beri_safeer(safeer) if safeer else ([], {})
    safeer_po_id = {k["id"]: k for k in katalog_safeer}
    safeer_po_gost = {}
    for k in katalog_safeer:
        if k.get("splet"):
            safeer_po_gost.setdefault(gostitelj(k["splet"]), k["id"])
    vrsta_po_id = {rid: vrsta for vrsta, idji in IZBOR.items() for rid in idji}
    mapa = os.path.join(recepti, "recipes")
    vnosi, izpusceni = [], []
    for rid in sorted(os.listdir(mapa), key=str.casefold):
        pot = os.path.join(mapa, rid)
        if not os.path.isfile(os.path.join(pot, "package.json")):
            continue
        if rid not in vrsta_po_id and not vse:
            continue
        paket = json.load(open(os.path.join(pot, "package.json"), encoding="utf-8"))
        nastavitve = paket.get("config") or {}
        razlog = ""
        if paket.get("license") != "MIT":
            razlog = "licenca recepta ni MIT: %r" % paket.get("license")
        elif nastavitve.get("hasTeamId") and "{" in str(nastavitve.get("serviceURL") or ""):
            razlog = "naslov zahteva ime ekipe ({teamId})"
        splet = poenoti_naslov(nastavitve.get("serviceURL") or "") if not razlog else ""
        if not razlog and not splet:
            razlog = "ni stalnega naslova https: %r" % nastavitve.get("serviceURL")
        if razlog:
            if rid in vrsta_po_id:
                izpusceni.append({"id": rid, "razlog": razlog})
            continue
        preselitev = preseljeni.get(gostitelj(splet))
        if preselitev:
            splet = preselitev
        ikona, opomba, izvirnik_sha = "", "", ""
        pot_ikone = os.path.join(pot, "icon.svg")
        if os.path.isfile(pot_ikone):
            with open(pot_ikone, "rb") as f:
                surovo = f.read()
            izvirnik_sha = hashlib.sha256(surovo).hexdigest()
            try:
                ikona = ocisti(surovo)
                if len(ikona.encode("utf-8")) > NAJVEC_IKONA:
                    ikona, opomba = "", "ikona zavrnjena: vecja od %d B" % NAJVEC_IKONA
            except NevarnaSvg as napaka:
                opomba = "ikona zavrnjena: %s" % napaka.args[0]
        else:
            opomba = "recept nima icon.svg"
        obstojeci = rid if rid in safeer_po_id else safeer_po_gost.get(gostitelj(splet), "")
        vnos = {"id": rid, "ime": str(paket.get("name") or rid).strip()[:60], "vrsta": vrsta_po_id.get(rid, DRUGO),
                "splet": splet, "prenos": "", "ikona_svg": ikona, "izmerjeno": False, "obstojeci": obstojeci,
                "vir": {"repo": REPO, "recept": "recipes/%s" % rid, "commit": commit,
                        "razlicica": str(paket.get("version") or ""), "licenca": "MIT",
                        "povezava": "%s/tree/%s/recipes/%s" % (REPO, commit, urllib.parse.quote(rid)),
                        "ikona_sha256": izvirnik_sha}}
        if preselitev:
            vnos["vir"]["preseljeno_iz"] = poenoti_naslov(nastavitve.get("serviceURL"))
        if opomba:
            vnos["vir"]["opomba"] = opomba
        vnosi.append(vnos)
    manjkajo = sorted(set(vrsta_po_id) - {v["id"] for v in vnosi} - {i["id"] for i in izpusceni})
    for rid in manjkajo:
        izpusceni.append({"id": rid, "razlog": "recepta ni v repozitoriju"})
    return {
        "oblika": 1,
        "opis": "Katalog storitev za Sporocila (Safeer), izdelan iz ferdium-recipes: samo podatki (ime, naslov, "
                "ikona). Kode receptov ni.",
        "vir": {"repo": REPO, "commit": commit, "datum_commita": datum, "licenca": "MIT",
                "avtorske_pravice": next((v.strip() for v in licenca.splitlines() if v.startswith("Copyright")), ""),
                "licenca_besedilo": licenca,
                "znamke": "Imena in ikone storitev so znamke svojih lastnikov; licenca MIT velja za vsebino "
                          "repozitorija ferdium-recipes in ne daje pravic do znamk."},
        "izpusceni": sorted(izpusceni, key=lambda x: x["id"].casefold()),
        "katalog": vnosi,
    }


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--recepti", required=True, help="mapa s klonom ferdium-recipes")
    a.add_argument("--safeer", default="", help="mapa s Safeer-linux (KATALOG, PRESELJENI)")
    a.add_argument("--izhod", default="katalog-sporocila.json")
    a.add_argument("--vse", action="store_true", help="vse primerne storitve, ne le izbor")
    n = a.parse_args(argv)
    katalog = izdelaj(n.recepti, n.safeer, n.vse)
    with open(n.izhod, "w", encoding="utf-8") as f:
        json.dump(katalog, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    po_vrsti = {}
    for v in katalog["katalog"]:
        po_vrsti[v["vrsta"]] = po_vrsti.get(v["vrsta"], 0) + 1
    print("vnosov: %d %s, brez ikone: %d, izpusceni iz izbora: %d, commit %s" % (
        len(katalog["katalog"]), po_vrsti, sum(1 for v in katalog["katalog"] if not v["ikona_svg"]),
        len(katalog["izpusceni"]), katalog["vir"]["commit"][:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
