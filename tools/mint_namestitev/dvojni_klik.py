#!/usr/bin/env python3
"""Dvoklik v Linux Mintu: preveri pakete .deb tako, kot jih preveri namestitveni program ob dvokliku.

Mint 22.1 in novejsi odpre .deb s Captainom, starejsi z GDebi. Oba paket preverita s python-apt
(apt.debfile.DebPackage.check): vsaka odvisnost (Depends, Pre-Depends) mora biti ze namescena ali v skladiscih,
sicer je gumb Namesti siv (»Odvisnost ni razresena«). Priporocenih paketov (Recommends) ne bereta, Breaks novega
paketa tudi ne. Do Safeer OS 0.4.75 je bil safeer-os odvisen od safeer-control, ki ni v nobenem skladiscu: dvoklik je
padel, `apt-get install` z obema paketoma pa ne - zato ta preizkus.

    dvojni_klik.py PAKET.deb [PAKET.deb ...]     izhodna koda 0, ce se da vsak paket namestiti z dvoklikom

Tece kot root v vsebniku Linux Minta (tools/mint_namestitev/v_vsebniku.sh); potrebuje python3-apt.
"""
import sys


def preveri(pot: str, apt_modul=None) -> str:
    """"" ce se paket da namestiti z dvoklikom, sicer razlog (isto besedilo, kot ga pokazeta Captain in GDebi)."""
    if apt_modul is None:
        import apt
        import apt.debfile  # noqa: F401 - DebPackage
        apt_modul = apt
    # Svez predpomnilnik za vsak paket: preverba oznaci odvisnosti za namestitev in bi sicer vplivala na naslednjega.
    deb = apt_modul.debfile.DebPackage(pot, cache=apt_modul.Cache())
    if deb.check():
        return ""
    return str(getattr(deb, "_failure_string", "") or "").strip() or "paketa ni mogoce namestiti"


def main(poti, apt_modul=None) -> int:
    if not poti:
        print("uporaba: dvojni_klik.py PAKET.deb [PAKET.deb ...]")
        return 2
    napake = 0
    for pot in poti:
        razlog = preveri(pot, apt_modul)
        print(("OK      %s" % pot) if not razlog else ("NAPAKA  %s: %s" % (pot, razlog)))
        napake += bool(razlog)
    return 1 if napake else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
