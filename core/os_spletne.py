"""Preverjanje uporabnikovih spletnih aplikacij v Safeer OS."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

#: Spletne aplikacije, ki jih Safeer OS pokaze, dokler uporabnik ne shrani svojih (isti kot PRIVZETE_SPLETNE v os.js -
#: preverja tests/test_namizje_vse_iz_os.py). Namizje QML jih je prej skrilo (popis 3.1, 18. 10. 2026).
PRIVZETE = (("YouTube", "https://www.youtube.com"), ("RTV 365", "https://365.rtvslo.si"),
            ("Gmail", "https://mail.google.com"), ("Wikipedia", "https://www.wikipedia.org"))
#: Najvec spletnih aplikacij (isto kot shraniSpletne v os.js in pocisti).
MEJA = 24


def normaliziraj_naslov(naslov: str) -> str:
    """Vrne kanonicni HTTP(S) naslov ali prazen niz.

    Fragment ni del spletnega vira, privzeta vrata in odvecna koncna poševnica pa ne smejo
    omogociti, da uporabnik isti vir doda veckrat.
    """
    surov = str(naslov or "").strip()
    try:
        deli = urlsplit(surov)
        shema = deli.scheme.lower()
        if shema not in ("http", "https") or not deli.hostname:
            return ""
        gostitelj = deli.hostname.lower()
        try:
            vrata = deli.port
        except ValueError:
            return ""
        if ":" in gostitelj and not gostitelj.startswith("["):
            gostitelj = "[" + gostitelj + "]"
        if vrata and not ((shema == "http" and vrata == 80) or (shema == "https" and vrata == 443)):
            gostitelj += ":" + str(vrata)
        pot = deli.path.rstrip("/")
        return urlunsplit((shema, gostitelj, pot, deli.query, ""))
    except (TypeError, ValueError):
        return ""


def pocisti(seznam, meja: int = 24) -> list[dict[str, str]]:
    """Odstrani neveljavne vnose; ohrani tudi preverjeno vrsto medijskega vira."""
    cisti: list[dict[str, str]] = []
    videni: set[str] = set()
    for vnos in seznam if isinstance(seznam, list) else []:
        if not isinstance(vnos, dict):
            continue
        ime = str(vnos.get("ime", ""))[:40].strip()
        naslov = normaliziraj_naslov(str(vnos.get("url", ""))[:300])
        if not ime or not naslov or naslov in videni:
            continue
        videni.add(naslov)
        cist = {"ime": ime, "url": naslov}
        vrsta = str(vnos.get("vrsta", ""))
        if vrsta in ("video", "glasba", "filmi", "serije", "tv", "radio"):
            cist["vrsta"] = vrsta
        cisti.append(cist)
        if len(cisti) >= meja:
            break
    return cisti


def vidne(shranjene) -> list[dict[str, str]]:
    """Seznam, ki ga uporabnik vidi: shranjen (tudi prazen, ce je vse odstranil) ali privzeti."""
    if isinstance(shranjene, list):
        return pocisti(shranjene, MEJA)
    return [{"ime": ime, "url": url} for ime, url in PRIVZETE]


def iz_vnosa(besedilo: str) -> str:
    """Naslov, kot ga uporabnik natipka (»mail.google.com«): brez sheme dobi https://, gostitelj brez sheme mora imeti
    piko (kot normalizirajNaslov v os.js). Neveljaven naslov vrne prazen niz."""
    s = str(besedilo or "").strip()[:300]
    s_shemo = bool(re.match(r"(?i)^https?://", s))
    naslov = normaliziraj_naslov(s if s_shemo else "https://" + s)
    if not naslov or (not s_shemo and "." not in (urlsplit(naslov).hostname or "")):
        return ""
    return naslov


def dodaj(shranjene, ime: str, naslov: str) -> tuple[list[dict[str, str]], str]:
    """(nov seznam, napaka): napaka »naslov« (neveljaven), »ze« (ze dodan), »polno« (MEJA) ali "" (dodano na konec)."""
    seznam = vidne(shranjene)
    url = iz_vnosa(naslov)
    if not url:
        return seznam, "naslov"
    if any(normaliziraj_naslov(a["url"]) == url for a in seznam):
        return seznam, "ze"
    if len(seznam) >= MEJA:
        return seznam, "polno"
    ime = str(ime or "").strip()[:40] or re.sub(r"^www\.", "", urlsplit(url).hostname or "")
    return seznam + [{"ime": ime, "url": url}], ""


def odstrani(shranjene, naslov: str) -> list[dict[str, str]]:
    url = normaliziraj_naslov(naslov)
    return [a for a in vidne(shranjene) if normaliziraj_naslov(a["url"]) != url]
