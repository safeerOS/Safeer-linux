"""Preverjanje uporabnikovih spletnih aplikacij v Safeer OS."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


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
    """Odstrani neveljavne in podvojene vnose, pri tem pa ohrani prvi uporabnikov vnos."""
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
        cisti.append({"ime": ime, "url": naslov})
        if len(cisti) >= meja:
            break
    return cisti
