#!/usr/bin/env python3
"""Preverba kanalov IPTV na uporabnikovih seznamih: koliko jih deluje, koliko je zaklenjenih, mrtvih in »Not 24/7«.

Lastnik, 25. 10. 2026: »kar ne deluje, se naj nikoli vec ne prikaze«; ponovna preverba mrtvih ostane vklopljena,
dokler meritev ne pokaze, da se ne vracajo. Orodje zato vsakic zapise izid VSAKEGA kanala z casom v svojo datoteko
(<mapa>/<datum-ura>.json) in pove, koliko kanalov, ki so bili ob prejsnji preverbi mrtvi, zdaj deluje.

Datoteka ima samo odtis naslova (id), ime kanala in izid - naslovov tokov (lahko nosijo zetone) ne zapisemo.
Nastavitve uporabnika samo beremo (media.json); predpomnilnik preverb Safeer OS (kanali-preverba.json) ostane nedotaknjen.

    python3 tools/kanali_preverba.py --nastavitve ~/.config/safeer-os/media --izhod <mapa> [--samo-izbrani]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

KOREN = Path(__file__).resolve().parent.parent
if str(KOREN) not in sys.path:
    sys.path.insert(0, str(KOREN))

from core import kanali_iptv, os_media  # noqa: E402


def _prenesi(url: str) -> tuple:
    zahteva = urllib.request.Request(url, headers={"User-Agent": kanali_iptv.PRIVZETI_ODJEMALEC, "Accept": "*/*"})
    with urllib.request.urlopen(zahteva, timeout=30) as odgovor:
        return odgovor.read(os_media.MAX_DOWNLOAD + 1), odgovor.headers.get_content_type(), odgovor.geturl()


def _seznami(nastavitve: Path) -> list:
    data = json.loads((nastavitve / "media.json").read_text(encoding="utf-8"))
    izid = []
    for vir in data.get("viri") or []:
        if not isinstance(vir, dict) or not vir.get("url"):
            continue
        pot = urllib.parse.urlsplit(str(vir["url"])).path.lower()
        if pot.endswith((".m3u", ".m3u8")) or any(isinstance(x, dict) and x.get("iptv") for x in vir.get("vnosi") or []) \
                or "type=m3u" in str(vir["url"]).lower():
            izid.append(vir)
    return izid


def _izbira(nastavitve: Path, drzava: str) -> dict:
    try:
        d = json.loads((nastavitve / "tv-izbira.json").read_text(encoding="utf-8"))
        if isinstance(d, dict):
            return d
    except (OSError, ValueError):
        pass
    return kanali_iptv.privzeta_izbira(drzava)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--nastavitve", required=True, help="mapa media (media.json) Safeer OS - samo branje")
    ap.add_argument("--izhod", required=True, help="mapa za <datum-ura>.json")
    ap.add_argument("--samo-izbrani", action="store_true",
                    help="samo kanali izbranih drzav in jezikov javnih seznamov (kot TV v zivo); privzeto vsi")
    ap.add_argument("--drzava", default="", help="drzava uporabnika (privzeto iz regije sistema)")
    a = ap.parse_args(argv)
    nastavitve, izhod = Path(a.nastavitve).expanduser(), Path(a.izhod).expanduser()
    izhod.mkdir(parents=True, exist_ok=True)
    drzava = a.drzava.upper()
    if not drzava:
        from core import watch_providers
        drzava = watch_providers.detect_country("sl")
    izbira = _izbira(nastavitve, drzava)

    kanali, viri = [], []
    zacetek = time.monotonic()
    for vir in _seznami(nastavitve):
        stevci: dict = {}
        try:
            vsebina, vrsta, koncni = _prenesi(str(vir["url"]))
            vnosi = os_media.parse_payload(vsebina, vrsta, koncni, str(vir.get("id") or ""), str(vir.get("ime") or ""),
                                           stevci=stevci)
        except Exception as napaka:  # noqa: BLE001
            viri.append({"ime": vir.get("ime"), "napaka": type(napaka).__name__})
            continue
        javni = kanali_iptv.je_javni_seznam(str(vir["url"]))
        domace = False if javni else os_media.media_servers.je_domace_omrezje(urllib.parse.urlsplit(str(vir["url"])).hostname or "")
        vsi = [x for x in vnosi if x.get("iptv")]
        izbrani = [x for x in vsi if not javni or kanali_iptv.v_izbiri(x, izbira)]
        izbrani_idji = {id(x) for x in izbrani}
        za_preverbo = izbrani if a.samo_izbrani else vsi
        viri.append({"ime": vir.get("ime"), "javni": javni, "vnosov": len(vnosi), "kanalov": len(vsi),
                     "izbranih": len(izbrani), "ne_24_7": int(stevci.get("ne_24_7") or 0),
                     "ne_kanali": {v: sum(1 for x in vnosi if x.get("vrsta") == v) for v in {x.get("vrsta") for x in vnosi if not x.get("iptv")}}})
        for x in za_preverbo:
            kanali.append((x, vir.get("ime"), domace, id(x) in izbrani_idji))
    cas_seznamov = time.monotonic() - zacetek

    casi: dict = {}

    def preveri(url, glave, rok, domace):
        t0 = time.monotonic()
        try:
            return kanali_iptv.preveri_tok(url, glave, rok, domace)
        finally:
            casi[kanali_iptv.kljuc(url)] = round((time.monotonic() - t0) * 1000)

    with tempfile.TemporaryDirectory() as zacasna:
        preverba = kanali_iptv.PreverbaKanalov(Path(zacasna) / "preverba.json", preveri=preveri)
        zacetek = time.monotonic()
        preverba.preveri_v_ozadju((str(x["url"]), x.get("glave") or {}, domace) for x, _v, domace, _i in kanali)
        preverba.pocakaj(6 * 3600)
        prvi = {k: list(v) for k, v in preverba._beri().items()}
        # Kot Safeer OS: kanal brez odgovora v roku ali s prekinjeno povezavo se enkrat ponovi z daljsim rokom
        # (v programu po PONOVI_PO_S, tu takoj).
        ponovi = [(str(x["url"]), x.get("glave") or {}, domace) for x, _v, domace, _i in kanali
                  if preverba._za_ponovitev(prvi.get(kanali_iptv.kljuc(str(x["url"]))))]
        if ponovi:
            preverba.preveri_v_ozadju(ponovi)
            preverba.pocakaj(6 * 3600)
        cas_preverbe = time.monotonic() - zacetek
        zapisi = []
        for x, ime_vira, _domace, izbran in kanali:
            k = kanali_iptv.kljuc(str(x["url"]))
            zapis = preverba._beri().get(k) or ["neznano", "", 0]
            zapisi.append({"id": k, "ime": x.get("naslov"), "vir": ime_vira, "drzava": x.get("drzava"),
                           "jezik": x.get("jezik"), "izbran": izbran, "izid": zapis[0], "koda": zapis[1],
                           "prvi_izid": (prvi.get(k) or ["neznano", ""])[0] + ":" + (prvi.get(k) or ["", ""])[1],
                           "ms": casi.get(k), "cas": zapis[2]})

    povzetek = {"skupaj": len(zapisi)}
    for z in zapisi:
        povzetek[z["izid"]] = povzetek.get(z["izid"], 0) + 1
    povzetek["ne_24_7"] = sum(v.get("ne_24_7", 0) for v in viri)
    povzetek["ponovljenih"] = len(ponovi)
    povzetek["po_ponovitvi_deluje"] = sum(1 for z in zapisi if z["izid"] == "deluje" and not z["prvi_izid"].startswith("deluje"))
    izbrani_povzetek = {}
    for z in zapisi:
        if z["izbran"]:
            izbrani_povzetek[z["izid"]] = izbrani_povzetek.get(z["izid"], 0) + 1
    kode: dict = {}
    for z in zapisi:
        kode[z["koda"]] = kode.get(z["koda"], 0) + 1

    # Primerjava s prejsnjo preverbo: ali se mrtvi kanali vracajo (odlocitev o PONOVNO_PREVERI_MRTVE).
    prejsnje = sorted(p for p in izhod.glob("*.json") if p.name[:1].isdigit())
    primerjava = None
    if prejsnje:
        try:
            star = {z["id"]: z["izid"] for z in json.loads(prejsnje[-1].read_text(encoding="utf-8")).get("kanali", [])}
            primerjava = {"datoteka": prejsnje[-1].name,
                          "mrtvi_zdaj_delujejo": sum(1 for z in zapisi if star.get(z["id"]) == "mrtev" and z["izid"] == "deluje"),
                          "delujoci_zdaj_mrtvi": sum(1 for z in zapisi if star.get(z["id"]) == "deluje" and z["izid"] == "mrtev"),
                          "prej_mrtvih": sum(1 for z in zapisi if star.get(z["id"]) == "mrtev")}
        except (OSError, ValueError, KeyError):
            primerjava = None

    zdaj = _dt.datetime.now()
    izid = {"cas": zdaj.isoformat(timespec="seconds"), "drzava": drzava, "izbira": izbira,
            "samo_izbrani": bool(a.samo_izbrani), "rok_s": kanali_iptv.ROK_S, "vzporedno": kanali_iptv.VZPOREDNO,
            "cas_seznamov_s": round(cas_seznamov, 1), "cas_preverbe_s": round(cas_preverbe, 1),
            "viri": viri, "povzetek": povzetek, "izbrani": izbrani_povzetek, "kode": kode,
            "primerjava": primerjava, "kanali": zapisi}
    datoteka = izhod / (zdaj.strftime("%Y-%m-%d-%H%M") + ".json")
    datoteka.write_text(json.dumps(izid, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: izid[k] for k in ("cas", "cas_seznamov_s", "cas_preverbe_s", "viri", "povzetek", "izbrani",
                                           "kode", "primerjava")}, ensure_ascii=False, indent=1))
    print("zapisano:", datoteka)
    return 0


if __name__ == "__main__":
    sys.exit(main())
