"""DVD brez zaščite v Safeer OS: slike ISO, mape VIDEO_TS in optični pogon (kot v VLC).

Predvaja GStreamer (resindvd, knjižnici libdvdnav/libdvdread) prek naslova ``dvd://<pot>``. Safeer ne
vsebuje in ne namešča ničesar, kar bi obšlo zaščito CSS; zaščiten disk se ne predvaja in uporabnik
dobi razumljivo sporočilo.
"""
from __future__ import annotations

import os
from typing import List, Optional

SEKTOR = 2048


def _mapa_video_ts(pot: str) -> Optional[str]:
    """Mapa, ki vsebuje VIDEO_TS (ali VIDEO_TS sama) -> mapa diska; sicer None."""
    pot = os.path.realpath(pot)
    if os.path.basename(pot).upper() == "VIDEO_TS.IFO" and os.path.isfile(pot):
        pot = os.path.dirname(pot)
    if os.path.basename(pot).upper() == "VIDEO_TS" and os.path.isdir(pot):
        pot = os.path.dirname(pot)
    if not os.path.isdir(pot):
        return None
    try:
        for ime in os.listdir(pot):
            if ime.upper() == "VIDEO_TS":
                mapa = os.path.join(pot, ime)
                if any(d.upper() == "VIDEO_TS.IFO" for d in os.listdir(mapa)):
                    return pot
    except OSError:
        return None
    return None


def je_dvd_iso(pot: str) -> bool:
    """Ali je slika ISO9660 z mapo VIDEO_TS v korenu (DVD-Video). Prebere le nekaj sektorjev."""
    try:
        with open(pot, "rb") as d:
            d.seek(16 * SEKTOR)
            pvd = d.read(SEKTOR)
            if len(pvd) < 190 or pvd[0] != 1 or pvd[1:6] != b"CD001":
                return False
            koren = pvd[156:190]
            lokacija = int.from_bytes(koren[2:6], "little")
            dolzina = min(int.from_bytes(koren[10:14], "little"), 64 * SEKTOR)
            d.seek(lokacija * SEKTOR)
            podatki = d.read(dolzina)
    except OSError:
        return False
    i = 0
    while i < len(podatki):
        n = podatki[i]
        if n == 0:
            i = (i // SEKTOR + 1) * SEKTOR       # zapis ne prečka meje sektorja
            continue
        ime_dolzina = podatki[i + 32] if i + 32 < len(podatki) else 0
        ime = podatki[i + 33:i + 33 + ime_dolzina].split(b";")[0].upper()
        if ime == b"VIDEO_TS":
            return True
        i += n
    return False


def je_dvd(pot: str) -> bool:
    return (os.path.isfile(pot) and pot.lower().endswith(".iso") and je_dvd_iso(pot)) or _mapa_video_ts(pot) is not None


def uri(pot: str) -> str:
    """Naslov za GStreamer: dvd://<slika ISO ali mapa diska ali naprava>.

    Pot ostane nekodirana: resindvd %20 ne dekodira (preverjeno 29. 9. 2026 z GStreamer 1.24)."""
    pot = os.path.realpath(pot)
    if os.path.isfile(pot) and pot.lower().endswith(".iso"):
        return "dvd://" + pot
    mapa = _mapa_video_ts(pot)
    if mapa:
        return "dvd://" + mapa
    if pot.startswith("/dev/"):
        return "dvd://" + pot
    raise ValueError("To ni DVD")


def naslov(pot: str) -> str:
    """Ime za prikaz: ISO brez končnice ali ime mape nad VIDEO_TS."""
    pot = os.path.realpath(pot)
    if pot.lower().endswith(".iso"):
        return os.path.splitext(os.path.basename(pot))[0].replace("_", " ")
    mapa = _mapa_video_ts(pot) or pot
    return os.path.basename(mapa).replace("_", " ") or "DVD"


def pogoni() -> List[dict]:
    """Optični pogoni in ali je v njih disk (/sys/block/sr*/size > 0)."""
    izid = []
    try:
        imena = sorted(n for n in os.listdir("/sys/block") if n.startswith("sr"))
    except OSError:
        return izid
    oznake = {}
    try:
        for o in os.listdir("/dev/disk/by-label"):
            oznake[os.path.realpath(os.path.join("/dev/disk/by-label", o))] = o.replace("\\x20", " ")
    except OSError:
        pass
    for ime in imena:
        try:
            with open("/sys/block/%s/size" % ime) as d:
                vstavljen = int(d.read().strip() or 0) > 0
        except (OSError, ValueError):
            vstavljen = False
        naprava = "/dev/" + ime
        izid.append({"naprava": naprava, "vstavljen": vstavljen, "ime": oznake.get(naprava, "") or "DVD"})
    return izid
