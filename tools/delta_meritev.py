#!/usr/bin/env python3
"""Meritev prenosa samo spremenjenih kosov (»Nadaljuj na drugi napravi«, core/link_delta).

Podani sta dve razlicici iste datoteke: STARA (kar druga naprava ze ima) in NOVA (kar ima ta naprava zdaj). Izpise,
koliko bajtov bi sel prenos prek Safeer Linka z delto (manjkajoci kosi + opis kosov) proti celi datoteki, koliko zahtev
bi bilo in koliko casa vzame racunanje opisov na tem racunalniku.

    python3 tools/delta_meritev.py stara.pcraft nova.pcraft [--json]
    python3 tools/delta_meritev.py --vstavi 10 datoteka   # sintetika: NOVA = STARA z 10 bajti, vstavljenimi na sredini

Nic ne gre na omrezje; isti razrez uporabljata streznik in odjemalec.
"""
import argparse
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import link_delta  # noqa: E402


def _berljivo(b: float) -> str:
    for enota in ("B", "KB", "MB", "GB"):
        if b < 1024 or enota == "GB":
            return ("%.0f %s" % (b, enota)) if enota == "B" else ("%.1f %s" % (b, enota))
        b /= 1024.0
    return str(b)


def izmeri(m_stara: dict, m_nova: dict) -> dict:
    o = link_delta.ocena(m_nova, [m_stara])
    opis = len(json.dumps(m_nova, separators=(",", ":")).encode("utf-8"))
    o["opis_bajtov"] = opis
    o["preneseno"] = o["podatki"] + opis
    o["delez_lokalno"] = round(1 - o["podatki"] / o["velikost"], 4) if o["velikost"] else 1.0
    o["prihranek"] = round(1 - o["preneseno"] / o["velikost"], 4) if o["velikost"] else 0.0
    return o


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("datoteki", nargs="+", help="STARA NOVA (ali ena datoteka z --vstavi)")
    p.add_argument("--vstavi", type=int, default=0, help="NOVA = STARA s toliko bajti, vstavljenimi na sredini")
    p.add_argument("--json", action="store_true", help="izpis kot JSON")
    a = p.parse_args(argv)
    t0 = time.perf_counter()
    if a.vstavi:
        with open(a.datoteki[0], "rb") as d:
            stara = d.read()
        sredina = len(stara) // 2
        nova = stara[:sredina] + os.urandom(a.vstavi) + stara[sredina:]
        m_stara = link_delta.manifest_toka(io.BytesIO(stara).read)
        t1 = time.perf_counter()
        m_nova = link_delta.manifest_toka(io.BytesIO(nova).read)
    else:
        if len(a.datoteki) != 2:
            p.error("podaj STARO in NOVO datoteko (ali --vstavi N in eno datoteko)")
        m_stara = link_delta.manifest(a.datoteki[0])
        t1 = time.perf_counter()
        m_nova = link_delta.manifest(a.datoteki[1])
    t2 = time.perf_counter()
    o = izmeri(m_stara, m_nova)
    o["cas_opisa_stare_s"] = round(t1 - t0, 3)
    o["cas_opisa_nove_s"] = round(t2 - t1, 3)
    o["numpy"] = link_delta._np is not None
    if a.json:
        print(json.dumps(o, indent=2))
        return 0
    print("Velikost nove razlicice:   %s (%d kosov)" % (_berljivo(o["velikost"]), o["kosov"]))
    print("Kosov ze na drugi napravi:  %d (%.1f %% bajtov)" % (o["kosov_lokalno"], o["delez_lokalno"] * 100))
    print("Po omrezju z delto:         %s = podatki %s + opis kosov %s, %d zahtev za obsege"
          % (_berljivo(o["preneseno"]), _berljivo(o["podatki"]), _berljivo(o["opis_bajtov"]), o["zahtev"]))
    print("Po omrezju brez delte:      %s" % _berljivo(o["velikost"]))
    print("Prihranek:                  %.1f %%" % (o["prihranek"] * 100))
    print("Cas opisa (stara / nova):   %.2f s / %.2f s (%s)"
          % (o["cas_opisa_stare_s"], o["cas_opisa_nove_s"], "numpy" if o["numpy"] else "cisti Python"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
