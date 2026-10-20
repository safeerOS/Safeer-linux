"""Vklop Sporocil in posameznih kanalov (lastnik, 15. 10. 2026: »uporabnik si lahko sam vklopi ali izklopi komunikacijske
kanale in klepete, lahko tudi v celoti izklopi moznost Sporocila«).

Ena majhna datoteka zraven baze sporocil, ker jo berejo vsi deli, ki sporocila sprejemajo: Safeer OS (storitev, vdelani
klepeti, kuverta), Safeer Control (Safeer Chat po Linku) - tudi ce tecejo kot locen proces. Branje je vsakic sveze
(datoteka ima nekaj bajtov), zato sprememba velja takoj, brez ponovnega zagona.

Izklopljen kanal ostane na seznamu z vsemi nastavitvami in prijavo; samo ne tece (ne povezuje se, ne steje, ne obvesca).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from .identiteta import PRIVZETA_POT
from core import shramba_json

_zaklep = threading.Lock()


def _pot(pot=None) -> Path:
    return Path(pot) if pot else Path(PRIVZETA_POT).with_name("vklop.json")


def _beri(pot=None) -> dict:
    try:
        podatki = json.loads(_pot(pot).read_text("utf-8"))
        return podatki if isinstance(podatki, dict) else {}
    except (OSError, ValueError):
        return {}


def _pisi(podatki: dict, pot=None) -> None:
    p = _pot(pot)
    p.parent.mkdir(parents=True, exist_ok=True)
    shramba_json.zapisi_atomsko(p, podatki, indent=None)


def sporocila_vklopljena(pot=None) -> bool:
    """Ali je moznost Sporocila vklopljena (privzeto da)."""
    return _beri(pot).get("sporocila", True) is not False


def nastavi_sporocila(vklop: bool, pot=None) -> bool:
    with _zaklep:
        p = _beri(pot)
        p["sporocila"] = bool(vklop)
        _pisi(p, pot)
    return bool(vklop)


def izklopljeni_kanali(pot=None) -> set:
    v = _beri(pot).get("izklopljeni", [])
    return {str(x) for x in v} if isinstance(v, list) else set()


def kanal_vklopljen(kanal_id: str, pot=None) -> bool:
    """Kanal tece le, ce so Sporocila vklopljena in kanal ni izklopljen."""
    p = _beri(pot)
    if p.get("sporocila", True) is False:
        return False
    v = p.get("izklopljeni", [])
    return str(kanal_id) not in (v if isinstance(v, list) else [])


def nastavi_kanal(kanal_id: str, vklop: bool, pot=None) -> None:
    with _zaklep:
        p = _beri(pot)
        izkl = [str(x) for x in (p.get("izklopljeni", []) or []) if str(x) != str(kanal_id)]
        if not vklop:
            izkl.append(str(kanal_id))
        p["izklopljeni"] = izkl[-500:]
        _pisi(p, pot)


def pozabi_kanal(kanal_id: str, pot=None) -> None:
    """Odstranjen kanal ne ostane na seznamu izklopljenih."""
    nastavi_kanal(kanal_id, True, pot)
