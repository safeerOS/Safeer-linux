"""Seznami predvajanja Medijskega centra za druge naprave v Safeer Linku (ukaz `lists.get`).

Seznami so enaki na vseh uporabnikovih napravah v Linku (pravila: core/seznami_sink.py, na Androidu SeznamiPravila.kt).
Safeer OS svoje sezname prevzame sam (core/os_katalog.py), drugim napravam pa odgovarja Safeer Control, ker je on
povezan v Link tudi takrat, ko Safeer OS ni odprt. Control zato sezname samo BERE iz mape Medijskega centra - nic ne
pise, nic ne gre v oblak. Odgovor je enak kot MediaCenter.seznami_izvoz (core/os_media.py); enakost preverja test.

Modul namenoma ne uvaza core/os_media.py (katalog, viri, omrezje): Control je majhen proces v ozadju.
"""
from __future__ import annotations

import json
import os
from typing import Optional

DEJANJE = "lists.get"
ZMOZNOST = "lists"
STRAN = 100                      # isto kot seznami_sink.STRAN (sporocila Linka so omejena)
POLJA = ("naslov", "izvajalec", "youtube", "sekund", "slika", "url", "video", "android")


def skladba_za_napravo(s: dict, ozji: bool = False) -> dict:
    """Skladba za drugo napravo: samo POLJA in nikoli prijava osebnega streznika (zeton, geslo) v naslovu - tudi ce je
    v seznami.json ostala iz starejse razlicice ali z druge naprave (core/viri_sink.py, cista_skladba). Tok z racunom
    ponudnika samo napravi v ozjem krogu (`ozji`, viri_sink.skladba_za)."""
    from core import viri_sink
    cista = viri_sink.skladba_za(s, ozji)
    return {k: cista[k] for k in POLJA if k in cista}


def mapa() -> str:
    """Mapa Medijskega centra Safeer OS (ista kot os_programi.MAPA_NASTAVITEV + "/media")."""
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "safeer-os", "media")


def _beri(pot: str):
    try:
        with open(pot, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _seznami(koren: str) -> list:
    data = _beri(os.path.join(koren, "seznami.json"))
    if not isinstance(data, list):
        return []
    # Seznami racuna YouTube ("zaseben", core/youtube_racun.py) ostanejo na napravi.
    return [x for x in data if isinstance(x, dict) and x.get("ime") and isinstance(x.get("skladbe"), list)
            and not x.get("zaseben")]


def _izbrisani(koren: str) -> dict:
    data = _beri(os.path.join(koren, "seznami_izbrisani.json"))
    if not isinstance(data, dict):
        return {}
    return {str(k): int(v) for k, v in data.items() if isinstance(v, (int, float)) and v > 0}


def _viri(koren: str, ozji: bool = False) -> dict:
    """Moji viri za druge naprave (core/viri_sink.py): zapis, ki ga Medijski center pripravi sam - zasebnih dodatkov
    in cesar se ne pozna, v njem ni. Control ga samo prebere in preveri obliko; vire z racunom (Xtream z geslom) samo
    napravi v ozjem krogu (`ozji`, viri_sink.viri_za)."""
    from core import viri_sink
    return viri_sink.viri_za(_beri(os.path.join(koren, "viri_za_naprave.json")), ozji)


def izvoz(parametri: Optional[dict] = None, koren: Optional[str] = None, ozji: bool = False) -> dict:
    """Odgovor na `lists.get`: kazalo seznamov ({}) ali ena stran skladb seznama ({"ime", "od"}). `ozji`: sprasuje
    naprava v ozjem krogu tega racunalnika (core/link_dostop.v_ozjem_krogu) - samo ta dobi vire in tokove z racunom."""
    parametri = parametri if isinstance(parametri, dict) else {}
    koren = koren or mapa()
    ime = str(parametri.get("ime") or "")
    vsi = _seznami(koren)
    if not ime:
        return dict({"lists": [{"ime": x["ime"], "vir": x.get("vir") or "", "cas": int(x.get("cas") or 0),
                                "stevilo": len(x["skladbe"])} for x in vsi],
                     "deleted": _izbrisani(koren)}, **_viri(koren, ozji))
    sz = next((x for x in vsi if x["ime"] == ime), None)
    if not sz:
        return {"ime": ime, "stevilo": 0, "skladbe": []}
    try:
        od = max(0, int(parametri.get("od") or 0))
    except (TypeError, ValueError):
        od = 0
    skladbe = [skladba_za_napravo(s, ozji) for s in sz["skladbe"][od:od + STRAN] if isinstance(s, dict)]
    return {"ime": sz["ime"], "vir": sz.get("vir") or "", "cas": int(sz.get("cas") or 0), "stevilo": len(sz["skladbe"]),
            "od": od, "skladbe": skladbe}
