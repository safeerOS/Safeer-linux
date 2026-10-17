"""Varuh pomnilnika spletnih procesov Spleta.

WebKit sam ustavi proces strani nad mejo (MemoryPressureSettings), a steje le svoj odtis pomnilnika. Puscanje
izrisovalnika DMA-BUF v WebKitGTK 2.54 (meritev 13. 10. 2026: 24ur.com ~90 MB/s, Intel Haswell in Iris Xe) tja ne
spada: proces je zrasel prek 2,8 GB, WebKit ga ni ustavil in sistem je moral ubijati programe (OOM). Varuh zato
vsakih nekaj sekund pogleda RSS nasih procesov WebKitWebProcess in tistega nad mejo ustavi; Splet nato stran nalozi
znova brez strojnega izrisa (os_splet._proces_pomnilnik).
"""
from __future__ import annotations

import os
import signal
from typing import Callable, Dict, List, Optional, Tuple

IME = "WebKitWebProces"   # /proc/PID/comm je omejen na 15 znakov


def _beri(pot: str) -> str:
    try:
        with open(pot, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _rss_mb(status: str) -> int:
    for vrstica in status.splitlines():
        if vrstica.startswith("VmRSS:"):
            try:
                return int(vrstica.split()[1]) // 1024
            except (IndexError, ValueError):
                return 0
    return 0


def _ppid(status: str) -> int:
    for vrstica in status.splitlines():
        if vrstica.startswith("PPid:"):
            try:
                return int(vrstica.split()[1])
            except (IndexError, ValueError):
                return 0
    return 0


def nasi_procesi(nas_pid: int, v_flatpaku: bool, proc: str = "/proc") -> List[Tuple[int, int]]:
    """(pid, RSS MB) procesov WebKitWebProcess tega programa. V Flatpaku so v nasem imenskem prostoru PID samo nasi;
    sicer mora biti nas proces med prednikoni (najvec 4 ravni: bwrap peskovnika WebKita)."""
    izid = []
    try:
        imena = os.listdir(proc)
    except OSError:
        return izid
    for ime in imena:
        if not ime.isdigit():
            continue
        if _beri(f"{proc}/{ime}/comm").strip() != IME:
            continue
        status = _beri(f"{proc}/{ime}/status")
        if not v_flatpaku:
            p, nas = _ppid(status), False
            for _ in range(4):
                if p == nas_pid:
                    nas = True
                    break
                if p <= 1:
                    break
                p = _ppid(_beri(f"{proc}/{p}/status"))
            if not nas:
                continue
        izid.append((int(ime), _rss_mb(status)))
    return izid


# Pravo puscanje (odlocitev lastnika 17. 10. 2026): proces mora biti nad mejo VZORCEV_RASTI zaporednih pregledov
# (pri pregledu vsakih 5 s ~20 s) in njegova poraba med njimi ne sme pasti (dovoljen 1 % nihanja). Zahtevna stran
# (JetStream 3.0: kratek vrh 2,7 GB, nato padec) tako ni ustavljena, puscanje DMA-BUF (~90 MB/s, ves cas raste) pa je.
VZORCEV_RASTI = 4


def _ves_cas_raste(vzorci: List[int]) -> bool:
    return len(vzorci) >= VZORCEV_RASTI and all(b >= a * 0.99 for a, b in zip(vzorci, vzorci[1:]))


def preglej(meja_mb: int, nas_pid: int, v_flatpaku: bool, ubij: Callable[[int, int], None] = os.kill,
            proc: str = "/proc", zgodovina: Optional[Dict[int, List[int]]] = None) -> Optional[int]:
    """Ustavi najvecji nas proces strani nad mejo; vrne njegov PID ali None. Z `zgodovina` (slovar, ki ga klicatelj
    hrani med pregledi) samo proces, ki je nad mejo zadnjih VZORCEV_RASTI pregledov in mu poraba ves cas raste."""
    procesi = nasi_procesi(nas_pid, v_flatpaku, proc)
    if zgodovina is not None:
        zivi = {pid for pid, _rss in procesi}
        for pid in [p for p in zgodovina if p not in zivi]:
            del zgodovina[pid]
        for pid, rss in procesi:
            if rss > meja_mb:
                zgodovina[pid] = (zgodovina.get(pid, []) + [rss])[-VZORCEV_RASTI:]
            else:
                zgodovina.pop(pid, None)
        procesi = [(pid, rss) for pid, rss in procesi if _ves_cas_raste(zgodovina.get(pid, []))]
    nad = [(rss, pid) for pid, rss in procesi if rss > meja_mb]
    if not nad:
        return None
    _rss, pid = max(nad)
    try:
        ubij(pid, signal.SIGKILL)
    except OSError:
        return None
    if zgodovina is not None:
        zgodovina.pop(pid, None)
    return pid
