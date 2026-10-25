#!/usr/bin/env python3
"""Zivi preizkus poti Webtor na namizju brez vmesnika (pravilo 1.0.129: »popravljeno« sele po uporabnikovi poti v zivo).

Nacina:
  --naslov URL [URL ...]   sonda (core/webtor.sonda, prava mreza) -> koncni preverjeni naslov -> nas predvajalnik
                           (core/os_predvajalnik.Predvajalnik, GStreamer, brez preusmeritev). Javni posnetki s
                           preusmeritvijo (npr. archive.org) - preveri isto pot sonda -> predvajalnik kot pri Webtorju.
  --webtor tt... [tt ...]  prava uporabnikova pot: dodatki iz KOPIJE nastavitev Medijskega centra (v prave nastavitve in
                           v zbirko skrivnosti se nic ne zapise), MediaCenter.resolve -> Webtor -> sonda -> predvajalnik.
                           Brez uporabnikovega dodatka Webtor pove, kaj manjka.
Predvajanje je tiho in brez okna (audio-sink in video-sink sta fakesink, glasnost 0), vsak poskus ima rok, na koncu se
predvajalnik ustavi in zapre. Meri: cas izbire do koncnega naslova, do prvega dekodiranega okvirja, ali predvajanje
tece --sekund s brez zastoja. Izpis: ena vrstica JSON na poskus - brez naslovov in zetonov (samo gostitelj).
Primer: python3 tools/webtor_meritev.py --ponovitve 3 --naslov https://archive.org/download/<id>/<datoteka>.mp4
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

KOREN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOREN))

ZASTOJ_S = 2.0          # polozaj se toliko casa ne premakne = zastoj


def _gostitelj(url: str) -> str:
    return (urllib.parse.urlsplit(str(url or "")).hostname or "")


def predvajaj(url: str, sekund: float, tok: dict | None = None, rok_slike_s: float = 30.0) -> dict:
    """Tiho predvajanje v nasem predvajalniku z istimi podatki kot safeer_os._katalog_predvajaj (glave toka, druge
    razlicice, brez preusmeritev za preverjen koncni naslov); meri prvo sliko in zastoje. Prvi tek 25. 10. brez glav je
    dal 429 (streznik toka brez Referer vedno 429) - to je bila napaka meritve, ne poti."""
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import GLib, Gst
    from core import os_predvajalnik
    Gst.init(None)
    p = os_predvajalnik.Predvajalnik(Gst)
    zanka = GLib.MainLoop()
    izid: dict = {"slika_ms": None, "predvajano_s": 0.0, "zastoji": 0, "medpomnjenje": 0, "napaka": "", "razlicic": 0}
    tok = tok if isinstance(tok, dict) else {"brez_preusmeritev": True}
    zacetek = time.monotonic()
    prva = threading.Event()

    def okvir(*_a) -> None:
        if not prva.is_set():
            izid["slika_ms"] = int((time.monotonic() - zacetek) * 1000)
            prva.set()
    slika = Gst.ElementFactory.make("fakesink", "meritev-slika")
    slika.set_property("sync", True)
    slika.set_property("signal-handoffs", True)
    slika.connect("handoff", okvir)
    zvok = Gst.ElementFactory.make("fakesink", "meritev-zvok")
    zvok.set_property("sync", True)
    p.element.set_property("video-sink", slika)
    p.element.set_property("audio-sink", zvok)
    p.element.set_property("volume", 0.0)
    p.element.set_property("mute", True)
    p.zakasni = lambda _ms, f: GLib.idle_add(lambda: f() and False)

    polno = {"da": True}

    def sporocilo(_v, s) -> None:
        if s.type == Gst.MessageType.BUFFERING:
            odstotek = s.parse_buffering()
            if odstotek < 100 and polno["da"] and prva.is_set():
                izid["medpomnjenje"] += 1          # prehod polno -> praznjenje (ne vsako sporocilo)
            polno["da"] = odstotek >= 100
        elif s.type == Gst.MessageType.ERROR:
            # Pred prvo sliko predvajalnik sam tiho poskusi naslednjo razlicico (kot pri uporabniku) - samo stejemo.
            napaka, _dbg = s.parse_error()
            izid["napake_pred_sliko" if not prva.is_set() else "napaka"] = "%s:%s" % (napaka.domain, napaka.code)
    p.vodilo.connect("message", sporocilo)
    stanje = {"polozaj": -1.0, "mirno_od": None, "od_slike": None}

    def tik() -> bool:
        zdaj = time.monotonic()
        if not prva.is_set():
            if zdaj - zacetek > rok_slike_s or p.stanje in ("ustavljeno", "napaka"):
                izid["napaka"] = izid.get("napake_pred_sliko") or "ni_slike"
                zanka.quit()
                return False
            return True
        izid.setdefault("razlicica", int(getattr(p, "_razlicica", 0)))
        stanje["od_slike"] = stanje["od_slike"] or zdaj
        ok, pol = p.element.query_position(Gst.Format.TIME)
        pol = pol / 1e9 if ok else stanje["polozaj"]
        if pol > stanje["polozaj"] + 0.05:
            stanje["polozaj"], stanje["mirno_od"] = pol, None
        elif stanje["mirno_od"] is None:
            stanje["mirno_od"] = zdaj
        elif zdaj - stanje["mirno_od"] >= ZASTOJ_S:
            izid["zastoji"] += 1
            stanje["mirno_od"] = zdaj
        izid["predvajano_s"] = round(max(0.0, stanje["polozaj"]), 1)
        if zdaj - stanje["od_slike"] >= sekund or izid["napaka"]:
            zanka.quit()
            return False
        return True
    GLib.timeout_add(250, tik)
    nadomestni = os_predvajalnik.cisti_nadomestne(tok.get("nadomestni"))
    izid["razlicic"] = len(nadomestni)
    p.zamenjaj_vrsto([os_predvajalnik.Skladba(url, "meritev", "video", glave=os_predvajalnik.cisti_glave(tok.get("glave")),
                                              nadomestni=nadomestni, preusmeritve=not tok.get("brez_preusmeritev"))])
    try:
        zanka.run()
    finally:
        p.zapri()
        p.element.set_state(Gst.State.NULL)
    return izid


def naslov(url: str, sekund: float) -> dict:
    from core import webtor
    zacetek = time.monotonic()
    s = webtor.sonda(url)
    izid = {"nacin": "naslov", "gostitelj": _gostitelj(url), "koncni_gostitelj": s.gostitelj, "izid": s.izid,
            "posoda": s.posoda, "vsebina": s.vsebina, "sonda_ms": int((time.monotonic() - zacetek) * 1000)}
    if s.izid == webtor.PREDVAJAJ and s.koncni:
        p = predvajaj(s.koncni, sekund)
        izid.update(p)
        if p["slika_ms"] is not None:
            izid["izbira_do_slike_ms"] = izid["sonda_ms"] + p["slika_ms"]
    return izid


def webtor_pot(idji: list, sekund: float) -> list:
    """Prava pot uporabnika iz kopije nastavitev Medijskega centra (prave nastavitve ostanejo nespremenjene)."""
    from core import os_katalog, os_media, skrivni_dodatki, webtor
    vir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "safeer-os" / "media"
    if not (vir / "media.json").is_file():
        return [{"nacin": "webtor", "napaka": "ni_nastavitev_medijskega_centra"}]
    mapa = tempfile.mkdtemp(prefix="safeer-webtor-meritev-")
    try:
        for ime in ("media.json", "debrid.json"):
            if (vir / ime).is_file():
                shutil.copy2(vir / ime, Path(mapa) / ime)
        pomnilnik: dict = {}

        def sifriraj(v: str) -> str:            # samo v pomnilniku: v zbirko skrivnosti se nic ne zapise
            k = "mem:%d" % len(pomnilnik)
            pomnilnik[k] = v
            return k

        def desifriraj(v: str) -> str:
            return pomnilnik[v] if v in pomnilnik else os_katalog.razkrij(v)
        mc = os_media.MediaCenter(mapa, roots=[], secret_encryptor=sifriraj, secret_decryptor=desifriraj)
        koreni = [os_media.media_servers._stremio_koren(str(s.get("url") or "")) for s in mc._stremio_strezniki()]
        wt = [k for k in koreni if mc._je_webtor_koren(k)]
        if not wt:
            return [{"nacin": "webtor", "napaka": "ni_dodatka_webtor", "dodatkov": len(koreni),
                     "kljuc_debrid": bool(mc.debrid.aktivna())}]
        izidi = []
        for tt in idji:
            ident = "meritev:" + tt
            mc._dynamic_items[ident] = {"id": ident, "naslov": tt, "vrsta": "film", "url": "stremio:%s|movie|%s" % (wt[0], tt)}
            zacetek = time.monotonic()
            r = mc.resolve(ident) or {}
            izid = {"nacin": "webtor", "id": tt, "izbira_ms": int((time.monotonic() - zacetek) * 1000),
                    "pot": "webtor" if r.get("webtor") else "debrid" if r.get("debrid") else
                    (r.get("napaka_koda") or ("neposredno" if str(r.get("url") or "").startswith("https://") else "drugo")),
                    "koncni_gostitelj": _gostitelj(r.get("url"))}
            if r.get("url") and not skrivni_dodatki.je_nadomestek(str(r["url"])) and str(r["url"]).startswith("https://"):
                p = predvajaj(str(r["url"]), sekund, os_katalog.tok_za_predvajalnik(r, str(r["url"])))
                izid.update(p)
                if p["slika_ms"] is not None:
                    izid["izbira_do_slike_ms"] = izid["izbira_ms"] + p["slika_ms"]
            izidi.append(izid)
        return izidi
    finally:
        skrivni_dodatki.pozabi_vse()
        shutil.rmtree(mapa, ignore_errors=True)   # zacasna kopija tega preizkusa (ne lastnikove datoteke)


def main(argv: list) -> int:
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--naslov", nargs="*", default=[])
    a.add_argument("--webtor", nargs="*", default=[])
    a.add_argument("--ponovitve", type=int, default=1)
    a.add_argument("--sekund", type=float, default=30.0)
    n = a.parse_args(argv)
    for ponovitev in range(1, max(1, n.ponovitve) + 1):
        for url in n.naslov:
            print(json.dumps(dict(naslov(url, n.sekund), ponovitev=ponovitev), ensure_ascii=False), flush=True)
        if n.webtor:
            for izid in webtor_pot(n.webtor, n.sekund):
                print(json.dumps(dict(izid, ponovitev=ponovitev), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
