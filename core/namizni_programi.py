"""Namizni programi kot kanali Sporocil (Viber, Signal Desktop; lastnik, 15. 10. 2026): ali je program namescen, kako
ga zazenemo in po cem prepoznamo njegovo okno. Splosno - vnos v katalogu (core/spletni_klepeti.py) so le podatki:
imena zaganjalnikov (.desktop), ukaz, vzorec za AppImage, razredi okna (WM_CLASS) in argumenti za zagon v X11.

Zazna vse tri oblike namestitve: paket (.desktop v mapah menija in izvrsljiva datoteka na poti), Flatpak (izvozi
/var/lib/flatpak in ~/.local/share/flatpak) in AppImage (~/Applications, ~/Prejemi oz. mapa prenosov, ~/Downloads ali
pot, ki jo je uporabnik izbral sam). V Flatpaku Safeer OS se program zazene na racunalniku (flatpak-spawn --host).
GTK-ja modul ne potrebuje.
"""
from __future__ import annotations

import configparser
import fnmatch
import os
import shlex
import shutil
import subprocess
from typing import List, Optional

from core import gostitelj

#: Mape, v katerih uporabniki navadno hranijo AppImage (poleg mape prenosov iz XDG).
MAPE_APPIMAGE = ("~/Applications", "~/Prejemi", "~/Downloads", "~/Prenosi", "~/.local/bin", "~/bin")


def _mape_vnosov() -> List[str]:
    from core import link_programi
    return link_programi._mape_vnosov()


def _beri_vnos(pot: str) -> Optional[dict]:
    b = configparser.RawConfigParser(interpolation=None, strict=False)
    b.optionxform = str
    try:
        with open(pot, encoding="utf-8", errors="replace") as f:
            b.read_file(f)
        v = b["Desktop Entry"]
    except Exception:  # noqa: BLE001 - pokvarjen ali neberljiv vnos
        return None
    try:
        ukaz = [d for d in shlex.split(v.get("Exec", "") or "") if not (d.startswith("%") and len(d) == 2)]
    except ValueError:
        ukaz = []
    return {"ukaz": ukaz, "razred": (v.get("StartupWMClass", "") or "").strip(), "ime": (v.get("Name", "") or "").strip()}


def _mape_appimage() -> List[str]:
    mape = [os.path.expanduser(m) for m in MAPE_APPIMAGE]
    try:
        prenosi = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=2).stdout.strip()
        if prenosi and prenosi not in mape:
            mape.append(prenosi)
    except (OSError, subprocess.SubprocessError):
        pass
    return mape


def je_izvrsljiva(pot: str) -> bool:
    return bool(pot) and os.path.isfile(pot) and os.access(pot, os.X_OK)


def najdi(program: dict, izbrana_pot: str = "", mape_vnosov: Optional[List[str]] = None,
          mape_appimage: Optional[List[str]] = None) -> Optional[dict]:
    """Namestitev programa ali None. Vrne {"oblika": "pot"|"vnos"|"ukaz"|"appimage", "ukaz": [...], "razredi": [...]}.
    Prednost: pot, ki jo je izbral uporabnik; zaganjalnik .desktop (paket ali Flatpak); ukaz na poti; AppImage."""
    razredi = [r for r in (program.get("razredi") or []) if r]
    argumenti = list(program.get("argumenti") or [])
    if izbrana_pot and je_izvrsljiva(izbrana_pot):
        return {"oblika": "pot", "ukaz": [izbrana_pot] + argumenti, "razredi": razredi}
    imena = set(program.get("vnosi") or [])
    for mapa in (mape_vnosov if mape_vnosov is not None else _mape_vnosov()):
        for ime in sorted(imena):
            pot = os.path.join(mapa, ime)
            if not os.path.isfile(pot):
                continue
            vnos = _beri_vnos(pot)
            if not vnos or not vnos["ukaz"]:
                continue
            r = ([vnos["razred"]] if vnos["razred"] else []) + [x for x in razredi if x != vnos["razred"]]
            return {"oblika": "vnos", "ukaz": vnos["ukaz"] + argumenti, "razredi": r, "vnos": pot}
    for ukaz in program.get("ukazi") or []:
        pot = shutil.which(ukaz)
        if pot:
            return {"oblika": "ukaz", "ukaz": [pot] + argumenti, "razredi": razredi}
    vzorci = [v.lower() for v in (program.get("appimage") or [])]
    if vzorci:
        for mapa in (mape_appimage if mape_appimage is not None else _mape_appimage()):
            try:
                imena_dat = sorted(os.listdir(mapa))
            except OSError:
                continue
            for ime in imena_dat:
                if any(fnmatch.fnmatch(ime.lower(), v) for v in vzorci) and je_izvrsljiva(os.path.join(mapa, ime)):
                    return {"oblika": "appimage", "ukaz": [os.path.join(mapa, ime)] + argumenti, "razredi": razredi}
    return None


def zazeni(najdba: dict) -> Optional[subprocess.Popen]:
    """Zazene program (v Flatpaku Safeer OS na racunalniku); None, ce ne gre. Program tece kot samostojen proces - ob
    koncu Safeer OS ga ne ustavimo (okno se vrne na namizje)."""
    ukaz = [gostitelj.na_gostitelju(d) if i == 0 else d for i, d in enumerate(najdba.get("ukaz") or [])]
    if not ukaz:
        return None
    if gostitelj.v_flatpaku():
        if not shutil.which("flatpak-spawn"):
            return None
        ukaz = ["flatpak-spawn", "--host", "--env=DISPLAY=" + os.environ.get("DISPLAY", "")] + ukaz
    try:
        return subprocess.Popen(ukaz, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                start_new_session=True)
    except OSError as e:
        print("[Sporocila] zagon programa:", e, flush=True)
        return None


def x11_seja() -> bool:
    """Ali je vgradnja okna mogoca (namizje X11). Na Waylandu se program odpre v svojem oknu ob Sporocilih."""
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or (os.environ.get("WAYLAND_DISPLAY")
                                                                       and not os.environ.get("DISPLAY")):
        return False
    return bool(os.environ.get("DISPLAY"))
