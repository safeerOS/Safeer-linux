"""Delo za druge naprave v Safeer Linku: pomoc v zivo takoj, delo v ozadju samo na prostem racunalniku.

Lastnik 5. 11. 2026: »Ce je naprava povezana v Safeer Link in je prosta, je njena dolznost, da pomaga, kjer lahko.«
Pomoc je brez vklopa in brez vprasanj, zato mora biti »prosta« tako, da uporabnik racunalnika pomoci ne obcuti:

- pomoc v ZIVO (nekdo zdaj gleda: video.stream, magnet.stream ...) velja po zmogljivosti (core/link_daljinec.pomoc:
  procesor, pomnilnik, disk, baterija) - ce bi cakala, film na televizorju ne bi tekel;
- delo v OZADJU (shranjevanje datotek drugih naprav, pretvorba videa za kasneje: storage.put, video.transcode) pocaka,
  da uporabnik vsaj NEDEJAVNOST_S ni uporabljal tipkovnice ali miske. Kdor dela za racunalnikom, ne sme dobiti
  polnega diska ali ventilatorja zaradi tujega opravila, ki lahko pocaka.

Nedejavnost: Muffin (Cinnamon) ali Mutter (GNOME) IdleMonitor, sicer XScreenSaver na X11 (core/nova_razlicica), na
Windows GetLastInputInfo. Ce je namizje ne pove, stejemo, da je uporabnik morda dejaven: delo v ozadju raje pocaka.
"""
from __future__ import annotations

import sys
from typing import Dict, Optional

#: Prosta za delo v ozadju: vsaj toliko sekund brez tipkovnice in miske (lastnik 5. 11. 2026: 10 min).
NEDEJAVNOST_S = 600.0
#: Dejanja dela v ozadju (nihce ne caka nanje zdaj). Vse drugo je pomoc v zivo ali ukaz uporabnika druge naprave.
V_OZADJU = frozenset({"storage.put", "video.transcode"})
#: Razlog zavrnitve, ki ga naprava vidi (host.info -> pomoc.razlog_ozadja, odgovor na ukaz).
V_UPORABI = "v_uporabi"


def je_v_ozadju(dejanje: str) -> bool:
    return dejanje in V_OZADJU


def presodi(dejanje: str, zmogljivost: Dict[str, object], nedejaven_s: Optional[float]) -> Dict[str, object]:
    """Ali ta racunalnik zdaj prevzame `dejanje`: {lahko, razlog}. Cista funkcija (preizkus brez namizja).

    zmogljivost: izid core/link_daljinec.pomoc; nedejaven_s: sekunde brez vnosa ali None (namizje ne pove)."""
    if not (zmogljivost or {}).get("lahko", True):
        return {"lahko": False, "razlog": str((zmogljivost or {}).get("razlog") or "")}
    if not je_v_ozadju(dejanje):
        return {"lahko": True, "razlog": ""}
    if nedejaven_s is None or nedejaven_s < NEDEJAVNOST_S:
        return {"lahko": False, "razlog": V_UPORABI}
    return {"lahko": True, "razlog": ""}


def za_host_info(zmogljivost: Dict[str, object], nedejaven_s: Optional[float]) -> Dict[str, object]:
    """Polji za `host.info` -> `pomoc`: naprave po njiju izberejo pomocnika za delo v ozadju (link_shramba,
    link_pretvorba), pomoc v zivo pa se naprej po `lahko`."""
    izid = presodi("video.transcode", zmogljivost, nedejaven_s)
    return {"ozadje": bool(izid["lahko"]), "razlog_ozadja": str(izid["razlog"])}


def nedejavnost_s() -> Optional[float]:
    """Sekunde brez tipkovnice in miske ali None. Nikoli ne vrze napake."""
    try:
        if sys.platform == "win32":
            return _nedejavnost_windows()
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib
        from core import nova_razlicica
        return nova_razlicica.nedejavnost_s(Gio, GLib)
    except Exception:  # noqa: BLE001 - brez podatka delo v ozadju pocaka
        return None


def _nedejavnost_windows() -> Optional[float]:
    import ctypes

    class _Vnos(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    v = _Vnos()
    v.cbSize = ctypes.sizeof(_Vnos)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(v)):
        return None
    # Oba sta 32-bitna stevca milisekund: razlika po modulu 2^32 prezivi prelom po 49,7 dneh.
    return ((ctypes.windll.kernel32.GetTickCount() - v.dwTime) & 0xFFFFFFFF) / 1000.0
