"""Katalog YouTube Music brez prijave: skladbe, albumi, izvajalci in album po vrsti.

Enako kot v Safeer OS (os/YoutubeGlasba.kt in YoutubeGlasbaOmrezje.kt; lastnik 21. 11. 2026). Ideja iz projekta Musike
(licenca MIT, avtor Ernani1234); napisano na novo, brez prevzete kode in brez Nodea ali yt-dlp: neposredno InnerTube
(odjemalec WEB_REMIX, odgovor v anglescini, da so vrste "Song", "Album", "Artist" stalne).
Razclenjevanje je loceno od omrezja, da ga preizkusimo brez interneta.
"""
from __future__ import annotations

import json
import re
from typing import Any, NamedTuple, Optional

from core import youtube_kanal_vrsta

NAJVEC_ELEMENTOV = 30
_ODJEMALEC = "WEB_REMIX"
_RAZLICICA = "1.20261110.01.00"
_ID_ALBUMA = re.compile(r"^MPRE[\w-]{6,60}$")
_ID_IZVAJALCA = re.compile(r"^UC[\w-]{22}$")
_ID_POSNETKA = re.compile(r"^[\w-]{11}$")

SKLADBA = "skladba"
ALBUM = "album"
IZVAJALEC = "izvajalec"


class Element(NamedTuple):
    vrsta: str
    id: str
    naslov: str
    podnaslov: str


class AlbumSkladba(NamedTuple):
    id: str
    naslov: str
    sekund: int


class Album(NamedTuple):
    id: str
    naslov: str
    izvajalec: str
    leto: str
    skladbe: list


def _kontekst() -> dict:
    return {"client": {"clientName": _ODJEMALEC, "clientVersion": _RAZLICICA, "hl": "en"}}


def zahteva_iskanja(q: str) -> dict:
    return {"context": _kontekst(), "query": (q or "")[:200]}


def zahteva_albuma(id_albuma: str) -> dict:
    return {"context": _kontekst(), "browseId": id_albuma}


def je_id_albuma(id_albuma: str) -> bool:
    return bool(_ID_ALBUMA.match(id_albuma or ""))


def _besedilo(o: Any) -> str:
    runs = (o or {}).get("runs") if isinstance(o, dict) else None
    return "".join(str(r.get("text", "")) for r in (runs or []) if isinstance(r, dict))


def _vrstice(d: Any) -> list:
    izhod: list = []

    def hodi(x: Any, globina: int) -> None:
        if globina > 40:
            return
        if isinstance(x, list):
            for v in x:
                hodi(v, globina + 1)
        elif isinstance(x, dict):
            v = x.get("musicResponsiveListItemRenderer")
            if isinstance(v, dict):
                izhod.append(v)
                return
            for y in x.values():
                hodi(y, globina + 1)

    hodi(d, 0)
    return izhod


def _stolpec(v: dict, i: int) -> str:
    st = v.get("flexColumns") or []
    if i >= len(st):
        return ""
    return _besedilo(((st[i] or {}).get("musicResponsiveListItemFlexColumnRenderer") or {}).get("text"))


def razclen_iskanje(d: Any) -> list:
    """Skladbe, albumi in izvajalci; ostalo (videi, epizode, seznami, podcasti, profili) izpusti."""
    izhod: list = []
    for v in _vrstice(d):
        if len(izhod) >= NAJVEC_ELEMENTOV:
            break
        naslov = _stolpec(v, 0).strip()
        deli = [p.strip() for p in _stolpec(v, 1).split(" • ") if p.strip()]
        if not naslov or not deli:
            continue
        vrsta, podnaslov = deli[0], " • ".join(deli[1:])
        brskanje = (((v.get("navigationEndpoint") or {}).get("browseEndpoint")) or {}).get("browseId") or ""
        posnetek = (v.get("playlistItemData") or {}).get("videoId") or ""
        if vrsta == "Song" and _ID_POSNETKA.match(posnetek):
            izhod.append(Element(SKLADBA, posnetek, naslov, podnaslov))
        elif vrsta in ("Album", "EP", "Single") and _ID_ALBUMA.match(brskanje):
            izhod.append(Element(ALBUM, brskanje, naslov, podnaslov))
        elif vrsta == "Artist" and _ID_IZVAJALCA.match(brskanje):
            izhod.append(Element(IZVAJALEC, brskanje, naslov, podnaslov))
    return izhod


def _glava(d: Any) -> Optional[dict]:
    if isinstance(d, list):
        for v in d:
            g = _glava(v)
            if g:
                return g
    elif isinstance(d, dict):
        g = d.get("musicResponsiveHeaderRenderer")
        if isinstance(g, dict):
            return g
        for y in d.values():
            g = _glava(y)
            if g:
                return g
    return None


def razclen_album(d: Any, id_albuma: str) -> Optional[Album]:
    """Album z vsemi skladbami po vrsti (skladbe brez predvajalnega id-ja so nerazpolozljive in jih ni)."""
    g = _glava(d) or {}
    naslov = _besedilo(g.get("title")).strip()
    skladbe = []
    for v in _vrstice(d):
        vid = (v.get("playlistItemData") or {}).get("videoId") or ""
        ime = _stolpec(v, 0).strip()
        if not _ID_POSNETKA.match(vid) or not ime:
            continue
        fiksni = v.get("fixedColumns") or []
        cas = _besedilo((((fiksni[0] if fiksni else {}) or {}).get("musicResponsiveListItemFixedColumnRenderer") or {}).get("text"))
        skladbe.append(AlbumSkladba(vid, ime, youtube_kanal_vrsta.trajanje(cas) or 0))
    if not naslov or not skladbe:
        return None
    izvajalec = _besedilo(g.get("straplineTextOne")).strip()
    leto = ""
    for p in (x.strip() for x in _besedilo(g.get("subtitle")).split(" • ")):
        if re.match(r"^(19|20)\d\d$", p):
            leto = p
    return Album(id_albuma, naslov, izvajalec, leto, skladbe)


# ---------------------------------------------------------------------- omrezje (klic z delovne niti)

def _post(url: str, telo: dict) -> Any:
    from core import uvoz_seznama
    try:
        return json.loads(uvoz_seznama._beri(url, youtube=True, telo=telo))
    except Exception:
        return None


def isci(q: str) -> list:
    if not (q or "").strip():
        return []
    d = _post("https://music.youtube.com/youtubei/v1/search?prettyPrint=false", zahteva_iskanja(q))
    return razclen_iskanje(d) if d else []


def album(id_albuma: str) -> Optional[Album]:
    if not je_id_albuma(id_albuma):
        return None
    d = _post("https://music.youtube.com/youtubei/v1/browse?prettyPrint=false", zahteva_albuma(id_albuma))
    return razclen_album(d, id_albuma) if d else None
