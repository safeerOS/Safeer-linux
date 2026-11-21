"""Videi YouTube kanala po vrsti: glasba, ostalo in kratki posnetki (Shorts).

Enako kot v Safeer OS (os/YoutubeKanalVrsta.kt, iste meje in isti preizkusni primeri, lastnik 21. 11. 2026): uporabniku se
pokazejo loceno, glasba kanala pa se predvaja zapored. YouTube kategorije videa v seznamu kanala ne da, zato odlocajo
trajanje in znacilnosti naslova ter kanala. Ob dvomu je posnetek OSTALO: napacna skladba v seznamu glasbe moti bolj kot
skladba med ostalim.
"""
from __future__ import annotations

import re
from typing import Optional

GLASBA = "glasba"
OSTALO = "ostalo"
KRATKI = "kratki"

KRATKI_NAJVEC_S = 60
GLASBA_PO_VZORCU_NAJMANJ_S = 100
GLASBA_NAJVEC_S = 12 * 60

_NI_GLASBA = re.compile(
    r"\b(podcast|interview|intervju|vlog|reaction|reakcija|trailer|tutorial|review|unboxing|episode|ep\.?\s*\d+|"
    r"behind the scenes|making of|track by track|how to|q&a|livestream|stream highlights|news|documentary|dokumentar|"
    r"oddaja|epizoda|tour|what'?s in|fridge|challenge|day in the life|diary|answers|asks|talks|meet and greet|"
    r"announcement|obvestilo)\b", re.IGNORECASE)
_JE_GLASBA = re.compile(
    r"\b(official (music )?video|official audio|lyric(s)? video|lyrics|audio|live (at|from|in)|acoustic|remix|"
    r"feat\.?|ft\.?|music video|videospot|single|album|cover)\b", re.IGNORECASE)
_IZVAJALEC_NASLOV = re.compile(r"^\S.{0,60}\s[-–—]\s\S.{0,100}$")


def trajanje(napis: Optional[str]) -> Optional[int]:
    """Trajanje iz napisa m:ss ali h:mm:ss; None, ce ni v tej obliki."""
    if napis is None:
        return None
    d = napis.strip().split(":")
    if len(d) not in (2, 3):
        return None
    if not (d[0].isascii() and d[0].isdigit()) or not 1 <= len(d[0]) <= 3:
        return None
    if any(len(x) != 2 or not (x.isascii() and x.isdigit()) for x in d[1:]):
        return None
    n = [int(x) for x in d]
    if any(x > 59 for x in n[1:]):
        return None
    return n[0] * 60 + n[1] if len(n) == 2 else n[0] * 3600 + n[1] * 60 + n[2]


def vrsta(naslov: str, kanal: str, trajanje_s: Optional[int], je_shorts: bool = False) -> str:
    if je_shorts or "#shorts" in naslov.lower() or (trajanje_s is not None and trajanje_s <= KRATKI_NAJVEC_S):
        return KRATKI
    if trajanje_s is not None and trajanje_s > GLASBA_NAJVEC_S:
        return OSTALO
    if _NI_GLASBA.search(naslov):
        return OSTALO
    k = kanal.strip().lower()
    glasbeni_kanal = k.endswith("- topic") or k.endswith("vevo")
    znacilnost = glasbeni_kanal or bool(_JE_GLASBA.search(naslov))
    # Brez znanega trajanja odloca samo izrazita znacilnost; z znanim je dovolj "Izvajalec - Naslov".
    if znacilnost:
        return GLASBA
    if trajanje_s is not None and trajanje_s >= GLASBA_PO_VZORCU_NAJMANJ_S and _IZVAJALEC_NASLOV.match(naslov.strip()):
        return GLASBA
    return OSTALO
