"""Lokalni zapiski Safeer OS brez odvisnosti od GTK.

Zapiski so shranjeni v enem JSON-u. Omembe so navadne povezave Markdown
``[@ime](cilj)`` na splet, datoteko, program ali drug zapisek.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from typing import Optional

from core.iskalni_kljuc import kljuc as kljuc_iskanja

NAJVEC_ZAPISKOV = 2000
NAJVEC_BESEDILA = 200_000
NAJVEC_NASLOVA = 160
_OMEMBA = re.compile(r"\[@([^\]]{1,160})\]\(([^)\s]{1,2048})\)")


def _cas() -> int:
    return int(time.time())


def omembe(besedilo: str) -> list[dict]:
    """Vrne enolične, veljavne omembe iz besedila."""
    izid, videne = [], set()
    for ime, cilj in _OMEMBA.findall(besedilo or ""):
        if cilj in videne:
            continue
        videne.add(cilj)
        vrsta = ("stran" if cilj.startswith(("https://", "http://")) else
                 cilj.split(":")[1] if cilj.startswith("safeer:") and cilj.count(":") >= 2 else "")
        if vrsta:
            izid.append({"ime": ime, "cilj": cilj, "vrsta": vrsta})
    return izid


class Zapiski:
    """Nitno varna shramba zapiskov v datoteki JSON."""

    def __init__(self, pot: str):
        self.pot = os.fspath(pot)
        self._kljuc = threading.Lock()

    def _nalozi(self) -> dict:
        try:
            with open(self.pot, "r", encoding="utf-8") as datoteka:
                podatki = json.load(datoteka)
            if isinstance(podatki, dict) and isinstance(podatki.get("zapiski"), list):
                return podatki
        except (OSError, ValueError):
            pass
        return {"zapiski": [], "zadnji": ""}

    def _shrani(self, podatki: dict) -> None:
        os.makedirs(os.path.dirname(self.pot) or ".", exist_ok=True)
        zacasna = self.pot + ".tmp"
        with open(zacasna, "w", encoding="utf-8") as datoteka:
            json.dump(podatki, datoteka, ensure_ascii=False, indent=1)
        os.replace(zacasna, self.pot)

    @staticmethod
    def _povzetek(zapisek: dict) -> dict:
        besedilo = _OMEMBA.sub(lambda m: "@" + m.group(1), zapisek.get("besedilo", ""))
        return {
            "id": zapisek["id"],
            "naslov": zapisek.get("naslov") or "Brez naslova",
            "odlomek": " ".join(besedilo.split())[:160],
            "spremenjeno": zapisek.get("spremenjeno", 0),
            "pripet": bool(zapisek.get("pripet")),
        }

    def seznam(self, iskano: str = "") -> list[dict]:
        with self._kljuc:
            zapiski = self._nalozi()["zapiski"]
        besede = kljuc_iskanja(iskano).split() if iskano else []
        if besede:
            # Brez sumnikov in velikih crk; vec besed v poljubnem vrstnem redu, ujemati se morajo vse.
            def ujema(z: dict) -> bool:
                seno = kljuc_iskanja(z.get("naslov", "") + "\n" + z.get("besedilo", ""))
                return all(b in seno for b in besede)
            zapiski = [z for z in zapiski if ujema(z)]
        zapiski = sorted(zapiski, key=lambda z: (not z.get("pripet"), -int(z.get("spremenjeno") or 0)))
        return [self._povzetek(z) for z in zapiski]

    def zadnji(self) -> str:
        with self._kljuc:
            podatki = self._nalozi()
        ident = str(podatki.get("zadnji") or "")
        return ident if any(z.get("id") == ident for z in podatki["zapiski"]) else ""

    def dobi(self, ident: str) -> Optional[dict]:
        with self._kljuc:
            podatki = self._nalozi()
        zapisek = next((z for z in podatki["zapiski"] if z.get("id") == ident), None)
        if not zapisek:
            return None
        povratne = [self._povzetek(z) for z in podatki["zapiski"]
                    if z.get("id") != ident and ("safeer:zapisek:" + ident) in z.get("besedilo", "")]
        return dict(zapisek, omembe=omembe(zapisek.get("besedilo", "")), povratne=povratne)

    def shrani(self, ident: str, naslov: str, besedilo: str, pripet: Optional[bool] = None) -> dict:
        naslov = str(naslov or "").strip()[:NAJVEC_NASLOVA]
        besedilo = str(besedilo or "")[:NAJVEC_BESEDILA]
        with self._kljuc:
            podatki = self._nalozi()
            zapisek = next((z for z in podatki["zapiski"] if z.get("id") == ident), None) if ident else None
            if zapisek is None:
                if len(podatki["zapiski"]) >= NAJVEC_ZAPISKOV:
                    raise ValueError("Doseženo je največje število zapiskov.")
                zapisek = {"id": "z" + secrets.token_hex(6), "ustvarjeno": _cas()}
                podatki["zapiski"].append(zapisek)
            zapisek.update(naslov=naslov, besedilo=besedilo, spremenjeno=_cas())
            if pripet is not None:
                zapisek["pripet"] = bool(pripet)
            podatki["zadnji"] = zapisek["id"]
            self._shrani(podatki)
        return self._povzetek(zapisek)

    def izbrisi(self, ident: str) -> bool:
        with self._kljuc:
            podatki = self._nalozi()
            prej = len(podatki["zapiski"])
            podatki["zapiski"] = [z for z in podatki["zapiski"] if z.get("id") != ident]
            if len(podatki["zapiski"]) == prej:
                return False
            if podatki.get("zadnji") == ident:
                podatki["zadnji"] = ""
            self._shrani(podatki)
        return True
