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
    return [x for x in data if isinstance(x, dict) and x.get("ime") and isinstance(x.get("skladbe"), list)]


def _izbrisani(koren: str) -> dict:
    data = _beri(os.path.join(koren, "seznami_izbrisani.json"))
    if not isinstance(data, dict):
        return {}
    return {str(k): int(v) for k, v in data.items() if isinstance(v, (int, float)) and v > 0}


def _viri(koren: str) -> dict:
    """Moji viri za druge naprave (core/viri_sink.py): zapis, ki ga Medijski center pripravi sam - zasebnih dodatkov
    in cesar se ne pozna, v njem ni. Control ga samo prebere in preveri obliko."""
    from core import viri_sink
    data = _beri(os.path.join(koren, "viri_za_naprave.json"))
    data = data if isinstance(data, dict) else {}
    viri = [v for v in (data.get("sources") if isinstance(data.get("sources"), list) else [])[:viri_sink.NAJVEC_VIROV]
            if viri_sink.cist_vir(v)]
    return {"sources": [{k: v[k] for k in ("tip", "ime", "naslov", "cas") if k in v} for v in viri],
            "sources_deleted": viri_sink.cisti_izbrisi(data.get("sources_deleted"))}


def izvoz(parametri: Optional[dict] = None, koren: Optional[str] = None) -> dict:
    """Odgovor na `lists.get`: kazalo seznamov ({}) ali ena stran skladb seznama ({"ime", "od"})."""
    parametri = parametri if isinstance(parametri, dict) else {}
    koren = koren or mapa()
    ime = str(parametri.get("ime") or "")
    vsi = _seznami(koren)
    if not ime:
        return dict({"lists": [{"ime": x["ime"], "vir": x.get("vir") or "", "cas": int(x.get("cas") or 0),
                                "stevilo": len(x["skladbe"])} for x in vsi],
                     "deleted": _izbrisani(koren)}, **_viri(koren))
    sz = next((x for x in vsi if x["ime"] == ime), None)
    if not sz:
        return {"ime": ime, "stevilo": 0, "skladbe": []}
    try:
        od = max(0, int(parametri.get("od") or 0))
    except (TypeError, ValueError):
        od = 0
    skladbe = [{k: s[k] for k in POLJA if k in s} for s in sz["skladbe"][od:od + STRAN] if isinstance(s, dict)]
    return {"ime": sz["ime"], "vir": sz.get("vir") or "", "cas": int(sz.get("cas") or 0), "stevilo": len(sz["skladbe"]),
            "od": od, "skladbe": skladbe}
