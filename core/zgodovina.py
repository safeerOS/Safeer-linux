"""Zgodovina brskanja (skupna Spletu in Safeer Browserju: history.json v mapi nastavitev, ista oblika)."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime

NAJVEC = 500


def nalozi(pot: str) -> list:
    try:
        with open(pot, encoding="utf-8") as f:
            podatki = json.load(f)
        return podatki if isinstance(podatki, list) else []
    except (OSError, ValueError):
        return []


def dodaj(pot: str, naslov: str, ime: str = "") -> bool:
    """Doda obisk na vrh (zaporedni obisk iste strani le posodobi). Zapis je atomaren (dva programa)."""
    if not naslov.startswith(("http://", "https://")):
        return False
    vnos = {"title": ime or naslov, "url": naslov, "time": datetime.now().strftime("%d.%m.%Y %H:%M")}
    zgodovina = nalozi(pot)
    if zgodovina and zgodovina[0].get("url") == naslov:
        zgodovina[0].update(vnos)
    else:
        zgodovina.insert(0, vnos)
    try:
        os.makedirs(os.path.dirname(pot) or ".", exist_ok=True)
        fd, zacasna = tempfile.mkstemp(dir=os.path.dirname(pot) or ".", prefix=".history-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(zgodovina[:NAJVEC], f, indent=2, ensure_ascii=False)
        os.replace(zacasna, pot)
        return True
    except OSError:
        return False


def isci(zapisi: list, niz: str) -> list:
    niz = (niz or "").strip().lower()
    if not niz:
        return list(zapisi)
    return [z for z in zapisi if niz in str(z.get("title", "")).lower() or niz in str(z.get("url", "")).lower()]
