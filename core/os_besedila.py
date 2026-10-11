"""Besedila Safeer OS (assets/os/besedila.js) za domace (GTK) poglede - en vir prevodov za stran in GTK.

Stran nalozi besedila.js kot JavaScript (BESEDILA_OS[jezik][kljuc]); tukaj isto datoteko preberemo v Pythonu, zato
GTK Safeer Player nima svojega seznama prevodov in ostane usklajen s spletnim Medijskim centrom. Datoteka ima samo
dve obliki: blok ``xx: { kljuc:"besedilo", ["kljuc"]:"..." }`` v BESEDILA_OS in ``Object.assign(BESEDILA_OS.xx, {...});``.
"""
from __future__ import annotations

import os
import re
from typing import Optional

POT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "os", "besedila.js")
JEZIKI = ("sl", "en", "de", "es", "fr", "it")

_ZACETEK_BLOKA = re.compile(r'^\s{2}([a-z]{2}):\s*\{|Object\.assign\(BESEDILA_OS\.([a-z]{2}),')
_PAR = re.compile(r'(?:\[\s*"([^"]+)"\s*\]|"([^"]+)"|\b([A-Za-z_][A-Za-z0-9_]*))\s*:\s*"((?:[^"\\]|\\.)*)"')


_UBEZNICA = re.compile(r'\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)', re.S)
_ZNAKI = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def _niz_js(vsebina: str) -> str:
    """Vsebina niza JavaScript v navednicah (\\n, \\u00e9, \\x41, \\' ...) kot Pythonov niz."""
    def zamenjaj(m: "re.Match") -> str:
        u = m.group(1)
        if u[0] in "ux" and len(u) > 1:
            return chr(int(u[1:], 16))
        return _ZNAKI.get(u, u)
    return _UBEZNICA.sub(zamenjaj, vsebina)


def preberi(pot: str = POT) -> dict[str, dict[str, str]]:
    """{jezik: {kljuc: besedilo}} iz besedila.js. Vrstice so pripisane zadnjemu zacetemu bloku jezika."""
    izid: dict[str, dict[str, str]] = {}
    jezik: Optional[str] = None
    with open(pot, encoding="utf-8") as f:
        for vrstica in f:
            m = _ZACETEK_BLOKA.search(vrstica)
            if m:
                jezik = m.group(1) or m.group(2)
                vrstica = vrstica[m.end():]
            if jezik is None:
                continue
            slovar = izid.setdefault(jezik, {})
            for p in _PAR.finditer(vrstica):
                slovar[p.group(1) or p.group(2) or p.group(3)] = _niz_js(p.group(4))
    return izid


_PREDPOMNILNIK: dict[str, dict[str, dict[str, str]]] = {}


def besedila() -> dict[str, dict[str, str]]:
    if POT not in _PREDPOMNILNIK:
        try:
            _PREDPOMNILNIK[POT] = preberi(POT)
        except OSError:
            _PREDPOMNILNIK[POT] = {}
    return _PREDPOMNILNIK[POT]


def jezik_sistema() -> str:
    """Jezik vmesnika kot na strani: LANGUAGE/LANG, sicer slovenscina; samo podprti jeziki."""
    for spremenljivka in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        for del_ in str(os.environ.get(spremenljivka) or "").split(":"):
            koda = del_[:2].lower()
            if koda in JEZIKI:
                return koda
    return "sl"


class Prevajalnik:
    """t(kljuc, n=3) kot na strani: izbrani jezik, nato anglescina, nato kljuc sam; {ime} se zamenja."""

    def __init__(self, jezik: str = "") -> None:
        self.jezik = jezik if jezik in JEZIKI else jezik_sistema()

    def __call__(self, kljuc: str, **zamenjave) -> str:
        b = besedila()
        besedilo = b.get(self.jezik, {}).get(kljuc)
        if besedilo is None:
            besedilo = b.get("en", {}).get(kljuc, kljuc)
        for k, v in zamenjave.items():
            besedilo = besedilo.replace("{" + k + "}", str(v))
        return besedilo
