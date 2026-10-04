#!/usr/bin/env python3
"""Gonilnik za preizkus Scita brez vmesnika (v vsebniku scit-odj, kot root).

Ukazi po FIFO /tmp/scit.cmd (ena vrstica = en ukaz), odgovori kot vrstice JSON v /tmp/scit.log:
  vklop | izklop | zagon (kot ob zagonu Safeer OS) | koncaj (kot ob izhodu) | stanje
  dovoli IME | blokiraj IME | premor MINUT | izhod (konec brez pospravljanja = sesutje)

Privzeto brez interneta: seznami se ne prenasajo, blokirani sta preizkusni domeni `preizkus.example` (oglasi) in
`nevarno.example` (lazna stran). Usmerjevalnik v preizkusu zanju odgovori z 172.31.95.66 in .68, zato se takoj vidi,
ali je poizvedba prisla mimo Scita.
`PRAVI_SEZNAMI=1` uporabi prave sezname (potrebuje internet).
"""
import json
import os
import sys
import time

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "/repo")
from core import os_scit  # noqa: E402

if os.environ.get("PRAVI_SEZNAMI") != "1":
    os_scit.VIRI = ()
    _izvirna = os_scit.Seznami.kategorija

    def _kategorija(self, ime):
        if ime == "preizkus.example" or ime.endswith(".preizkus.example"):
            return "oglasi"
        if ime == "nevarno.example" or ime.endswith(".nevarno.example"):
            return "phishing"
        return _izvirna(self, ime)

    os_scit.Seznami.kategorija = _kategorija


class Shramba:
    def __init__(self, pot):
        self.pot = pot
        try:
            with open(pot, encoding="utf-8") as f:
                self.d = json.load(f)
        except (OSError, ValueError):
            self.d = {}

    def get(self, k, privzeto=None):
        return self.d.get(k, privzeto)

    def set(self, k, v):
        self.d[k] = v
        with open(self.pot, "w", encoding="utf-8") as f:
            json.dump(self.d, f)


def kratko(s):
    izid = {k: s.get(k) for k in ("vklop", "mozno", "razlog", "tece", "napaka", "vmesniki", "strezniki", "blokiranih",
                                  "poizvedb", "domen", "izjeme", "premor") if k in s}
    izid["zadnje"] = [z["ime"] for z in s.get("zadnje", [])][:6]
    return izid


def main():
    cmd, dnevnik = "/tmp/scit.cmd", "/tmp/scit.log"
    if not os.path.exists(cmd):
        os.mkfifo(cmd)
    scit = os_scit.Scit(Shramba("/var/tmp/scit-shramba.json"), mapa="/var/tmp/scit-podatki")

    def zapisi(ukaz, izid):
        with open(dnevnik, "a", encoding="utf-8") as f:
            f.write(json.dumps({"cas": time.strftime("%H:%M:%S"), "ukaz": ukaz, "izid": izid}, ensure_ascii=False) + "\n")

    zapisi("start", kratko(scit.stanje()))
    while True:
        with open(cmd, encoding="utf-8") as f:
            for vrstica in f:
                deli = vrstica.split()
                if not deli:
                    continue
                u, a = deli[0], deli[1:]
                try:
                    if u == "vklop":
                        izid = kratko(scit.nastavi(True))
                    elif u == "izklop":
                        izid = kratko(scit.nastavi(False))
                    elif u == "zagon":
                        scit.zacni_ce_vklopljen()
                        time.sleep(4)
                        izid = kratko(scit.stanje())
                    elif u == "koncaj":
                        scit.koncaj()
                        izid = kratko(scit.stanje())
                    elif u == "dovoli":
                        izid = kratko(scit.dovoli(a[0], True))
                    elif u == "blokiraj":
                        izid = kratko(scit.dovoli(a[0], False))
                    elif u == "premor":
                        izid = kratko(scit.premor(float(a[0])))
                    elif u == "izhod":
                        zapisi(u, "konec brez pospravljanja")
                        os._exit(0)
                    else:
                        izid = kratko(scit.stanje())
                except Exception as e:  # noqa: BLE001
                    izid = {"izjema": "%s: %s" % (e.__class__.__name__, e)}
                zapisi(vrstica.strip(), izid)


if __name__ == "__main__":
    main()
