#!/usr/bin/env python3
"""Meritev hitrosti dekodiranja yEnc (core/usenet_yenc.py) - lasten pogon Usenet, korak 1 (25. 10. 2026).

Nakljucni podatki (privzeto 50 MiB) v clankih po 750 KiB (obicajna velikost dela na Usenetu), kodirani s
usenet_yenc.kodiraj; meri se samo dekodiranje s preverbo CRC32 (en proces, ena nit), vsaj 3 ponovitve.
Zagon iz korena repozitorija: python3 -I tools/meri_yenc.py [MiB] [ponovitev]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import usenet_yenc as Y  # noqa: E402

DEL = 750 * 1024


def main() -> None:
    mib = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    ponovitev = max(3, int(sys.argv[2]) if len(sys.argv) > 2 else 3)
    podatki = os.urandom(mib * 1024 * 1024)
    clanki = [Y.kodiraj(podatki[o:o + DEL], "meritev.bin", len(podatki), o // DEL + 1, None, o + 1)
              for o in range(0, len(podatki), DEL)]
    kodirano = sum(map(len, clanki))
    vec = 100.0 * (kodirano / len(podatki) - 1)
    print("podatki %d MiB, %d clankov, kodirano %.2f %% vec" % (mib, len(clanki), vec))
    for n in range(1, ponovitev + 1):
        zacetek = time.perf_counter()
        skupaj = 0
        for c in clanki:
            skupaj += len(Y.dekodiraj(c).podatki)
        cas = time.perf_counter() - zacetek
        assert skupaj == len(podatki)
        print("ponovitev %d: %.3f s, %.1f MB/s (%.1f MiB/s)" % (n, cas, skupaj / cas / 1e6, skupaj / cas / 1048576))
    print("obremenitev (1/5/15 min): %.2f %.2f %.2f" % os.getloadavg())


if __name__ == "__main__":
    main()
