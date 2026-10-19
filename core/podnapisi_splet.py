"""Podnapisi s spleta brez racuna: javni dodatek OpenSubtitles v3 za Stremio (opensubtitles-v3.strem.io).

Dodatek isce po IMDb oznaki (film ``tt0133093``, epizoda ``tt0903747:1:1``) in vrne povezave na datoteke, ki jih
strem.io ze pretvori v UTF-8 (glava x-reencoded-by, preverjeno 14. 10. 2026). Zahtevo posljemo samo, ko uporabnik
v predvajalniku izbere »Poisci na spletu« - sicer nihce ne izve, kaj gleda.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from typing import Callable, Iterable, List, Optional, Tuple

from core import podnapisi as _pn

NASLOV = "https://opensubtitles-v3.strem.io"
CAKAJ_S = 15
NAJVEC_REZULTATOV = 150
NAJVEC_NA_JEZIK = 12
#: Odgovor dodatka je JSON s seznamom; vec kot 2 MB ni odgovor, ki ga pricakujemo.
NAJVEC_ODGOVOR = 2 * 1024 * 1024

_RX_ID = re.compile(r"^(movie|series)/(tt\d{5,12})(?::(\d{1,4}):(\d{1,5}))?$")
_RX_IMDB = re.compile(r"(?<![a-z0-9])(tt\d{5,12})(?![0-9])")


def id_vnosa(item: dict) -> str:
    """Oznaka za iskanje (``movie/tt…`` ali ``series/tt…:S:E``) iz vnosa kataloga; prazno, ce je ne poznamo.

    Brez IMDb oznake moznosti v predvajalniku ne pokazemo (brez praznih gumbov)."""
    if not isinstance(item, dict):
        return ""
    stremio = item.get("stremio") if isinstance(item.get("stremio"), dict) else {}
    tip, ident = str(stremio.get("tip") or ""), str(stremio.get("id") or "")
    if not ident and str(item.get("url") or "").startswith("stremio:"):
        deli = (str(item["url"])[len("stremio:"):].split("|") + ["", ""])[:3]
        tip, ident = deli[1], deli[2]
    if tip in ("movie", "series") and _RX_ID.match("%s/%s" % (tip, ident)):
        # Serija brez izbrane epizode: katero epizodo predvajamo, ve sele dodatek - po sezoni/epizodi vnosa.
        if tip == "movie" or ":" in ident:
            return "%s/%s" % (tip, ident)
    m = _RX_IMDB.search(str(item.get("imdb_id") or "").lower())
    if not m:
        return ""
    try:
        sezona, epizoda = int(item.get("sezona") or 0), int(item.get("epizoda") or 0)
    except (TypeError, ValueError):
        sezona, epizoda = 0, 0
    if sezona > 0 and epizoda > 0:
        return "series/%s:%d:%d" % (m.group(1), sezona, epizoda)
    if str(item.get("vrsta") or "") in ("serija", "series"):
        return ""
    return "movie/%s" % m.group(1)


def naslov_iskanja(ident: str) -> str:
    """https://opensubtitles-v3.strem.io/subtitles/movie/tt0133093.json; neveljavna oznaka -> ""."""
    ident = str(ident or "").strip()
    if not _RX_ID.match(ident):
        return ""
    return "%s/subtitles/%s.json" % (NASLOV, urllib.parse.quote(ident, safe="/:"))


def razcleni(podatki, jeziki: Iterable[str] = ()) -> List[dict]:
    """Odgovor dodatka -> [{"url", "jezik" (ISO 639-1), "oznaka" (npr. BR), "ime", "id"}], uporabnikovi jeziki prvi.

    Samo povezave https; podvojene izpustimo; najvec NAJVEC_NA_JEZIK na jezik in NAJVEC_REZULTATOV skupaj."""
    if isinstance(podatki, (bytes, str)):
        try:
            podatki = json.loads(podatki)
        except ValueError:
            return []
    seznam = podatki.get("subtitles") if isinstance(podatki, dict) else None
    if not isinstance(seznam, list):
        return []
    videni, po_jeziku = set(), {}
    for s in seznam:
        if not isinstance(s, dict):
            continue
        url = str(s.get("url") or "")
        if not url.startswith("https://") or url in videni or len(url) > 2048:
            continue
        izvorni = str(s.get("lang") or "").lower()[:8]
        jezik = _pn.iso1(izvorni)
        if not jezik:
            continue
        videni.add(url)
        ime = str(s.get("subtitleFileName") or s.get("movieReleaseName") or "").strip()
        ime = re.sub(r"[\x00-\x1f]", "", ime)[:120]
        vnos = {"url": url, "jezik": jezik, "oznaka": "BR" if izvorni == "pob" else "",
                "ime": ime, "id": str(s.get("id") or "")[:24]}
        po_jeziku.setdefault(jezik, []).append(vnos)
    zeleni = [j for j in dict.fromkeys(_pn.iso1(j) for j in jeziki) if j]
    vrstni = [j for j in zeleni if j in po_jeziku] + sorted(j for j in po_jeziku if j not in zeleni)
    izid: List[dict] = []
    for j in vrstni:
        izid.extend(po_jeziku[j][:NAJVEC_NA_JEZIK])
    return izid[:NAJVEC_REZULTATOV]


def skupine(rezultati: List[dict]) -> List[Tuple[str, List[dict]]]:
    """[(jezik, [rezultati])] v vrstnem redu rezultatov (uporabnikovi jeziki prvi)."""
    izid: List[Tuple[str, List[dict]]] = []
    for r in rezultati:
        if izid and izid[-1][0] == r["jezik"]:
            izid[-1][1].append(r)
        else:
            izid.append((r["jezik"], [r]))
    return izid


def _odpri(url: str):
    zahteva = urllib.request.Request(url, headers={"User-Agent": "SafeerOS", "Accept": "application/json, */*"})
    return urllib.request.urlopen(zahteva, timeout=CAKAJ_S)  # noqa: S310 - samo https (preverjeno zgoraj)


def poisci(ident: str, jeziki: Iterable[str] = (), odpri: Callable = _odpri) -> List[dict]:
    """Rezultati za oznako; ob napaki omrezja dvigne OSError (klicatelj pokaze »ni dosegljivo«)."""
    url = naslov_iskanja(ident)
    if not url:
        return []
    with odpri(url) as o:
        podatki = o.read(NAJVEC_ODGOVOR + 1)
    if len(podatki) > NAJVEC_ODGOVOR:
        return []
    return razcleni(podatki, jeziki)


def mapa_predpomnilnika() -> str:
    return os.path.join((os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")), "safeer-os", "podnapisi")


def ime_datoteke(rezultat: dict) -> str:
    """Ime v predpomnilniku: kratek povzetek povezave + jezik + koncnica iz imena (privzeto .srt)."""
    koncnica = os.path.splitext(str(rezultat.get("ime") or ""))[1].lower()
    if koncnica not in _pn.PRIPONE:
        koncnica = ".srt"
    povzetek = hashlib.sha256(str(rezultat.get("url") or "").encode()).hexdigest()[:20]
    return "splet-%s.%s%s" % (povzetek, rezultat.get("jezik") or "xx", koncnica)


def prenesi(rezultat: dict, mapa: str = "", odpri: Callable = _odpri) -> str:
    """Prenese podnapis v predpomnilnik in vrne pot; ob napaki dvigne OSError ali ValueError."""
    url = str(rezultat.get("url") or "")
    if not url.startswith("https://"):
        raise ValueError("samo https")
    mapa = mapa or mapa_predpomnilnika()
    os.makedirs(mapa, exist_ok=True)
    cilj = os.path.join(mapa, ime_datoteke(rezultat))
    if os.path.isfile(cilj) and os.path.getsize(cilj) > 0:
        return cilj
    with odpri(url) as o:
        podatki = o.read(_pn.NAJVEC_BAJTOV + 1)
    if not podatki or len(podatki) > _pn.NAJVEC_BAJTOV:
        raise ValueError("datoteka ni podnapis")
    with open(cilj + ".tmp", "wb") as d:
        d.write(podatki)
    os.replace(cilj + ".tmp", cilj)
    return cilj


def jeziki_uporabnika(*jeziki: Optional[str]) -> List[str]:
    """Izbrani jezik podnapisov, jezik sistema, jezik vmesnika, anglescina - brez praznih in ponovitev."""
    return [j for j in dict.fromkeys(_pn.iso1(j) for j in list(jeziki) + ["en"]) if j]
