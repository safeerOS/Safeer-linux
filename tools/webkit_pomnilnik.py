#!/usr/bin/env python3
"""Koliko fizicnega pomnilnika zasedajo knjiznice WebKita v vseh procesih - meritev za paket safeer-webkit.

Vsota Pss iz /proc/*/smaps: Pss razdeli stran, ki jo ima vec procesov, med te procese, zato je vsota dejanska poraba.
Ko teceta Safeer OS in Safeer Browser, sta imela do 1.0.127~pred vsak svojo kopijo WebKita (/usr/lib/safeer-os/webkit,
/usr/lib/safeer-browser/webkit - razlicni datoteki, strani kode dvakrat); s skupnim paketom safeer-webkit
(/usr/lib/safeer-webkit, lastnik 19. 10. 2026) je datoteka ena in jedro strani kode deli. Pricakovano (meritev
18. 10. 2026 na testnem PC): ~60-70 MiB libwebkitgtk + ~30 MiB JavaScriptCore manj.

  sudo python3 tools/webkit_pomnilnik.py [VZOREC]     (root vidi vse procese; brez sudo samo svoje)

Primerjava: isti scenarij (oba programa, enake strani) pred posodobitvijo in po njej; izpis po datotekah in vsota.
"""
import glob
import re
import sys

PRIVZETO = r"(libwebkitgtk-6\.0|libjavascriptcoregtk-6\.0|libsoup-3\.0)\.so"
_GLAVA = re.compile(r"^[0-9a-f]+-[0-9a-f]+ ")


def izmeri(vzorec: str = PRIVZETO, proc: str = "/proc") -> tuple:
    """({datoteka: {"Rss": KiB, "Pss": KiB}}, stevilo procesov z vsaj eno tako preslikavo)."""
    iskanje = re.compile(vzorec)
    po_datoteki = {}
    procesi = set()
    for pot in glob.glob(proc + "/[0-9]*/smaps"):
        try:
            with open(pot, encoding="utf-8", errors="replace") as f:
                vrstice = f.read().splitlines()
        except OSError:
            continue
        datoteka = None
        for v in vrstice:
            if _GLAVA.match(v):
                deli = v.split(None, 5)
                datoteka = deli[5] if len(deli) == 6 and iskanje.search(deli[5]) else None
            elif datoteka and v[:4] in ("Rss:", "Pss:"):
                vnos = po_datoteki.setdefault(datoteka, {"Rss": 0, "Pss": 0})
                vnos[v[:3]] += int(v.split()[1])
                procesi.add(pot.rsplit("/", 2)[1])
    return po_datoteki, len(procesi)


def main(argv) -> int:
    po_datoteki, procesov = izmeri(argv[0] if argv else PRIVZETO)
    for datoteka, v in sorted(po_datoteki.items()):
        print("%-72s Rss %7.1f MiB  Pss %7.1f MiB" % (datoteka, v["Rss"] / 1024, v["Pss"] / 1024))
    print("SKUPAJ (%d procesov, %d datotek): Pss %.1f MiB"
          % (procesov, len(po_datoteki), sum(v["Pss"] for v in po_datoteki.values()) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
