"""Safeer OS v Flatpaku: programi, ikone in zagon na racunalniku (gostitelju), ne v peskovniku.

Flatpak je glavna pot distribucije (lastnik, 12. 10. 2026). V peskovniku je /usr runtime GNOME, sistem
racunalnika pa je (z dovoljenjem --filesystem=host-os:ro) pod /run/host/usr. Zato:
  - zaganjalnike in ikone programov beremo tudi iz /run/host/usr/...,
  - program zazenemo na gostitelju (flatpak-spawn --host gio launch <pot na gostitelju>), s potjo, kot jo vidi
    gostitelj (/run/host/usr/... -> /usr/...).
Zunaj Flatpaka so vse funkcije brez ucinka (vrnejo izvirne poti).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import List, Sequence

PREDPONA = "/run/host"


def v_flatpaku() -> bool:
    return bool(os.environ.get("FLATPAK_ID")) and os.path.exists("/.flatpak-info")


def mape_gostitelja(podmapa: str) -> List[str]:
    """Npr. podmapa "applications" -> ["/run/host/usr/share/applications", "/run/host/usr/local/share/applications"]."""
    if not v_flatpaku():
        return []
    return [os.path.join(PREDPONA, "usr", "share", podmapa), os.path.join(PREDPONA, "usr", "local", "share", podmapa)]


def na_gostitelju(pot: str) -> str:
    """Pot, kot jo vidi gostitelj: /run/host/usr/x -> /usr/x; druge poti (domaca mapa, /var/lib/flatpak) enake."""
    pot = str(pot or "")
    if pot == PREDPONA or pot.startswith(PREDPONA + "/"):
        return pot[len(PREDPONA):] or "/"
    return pot


def zazeni_vnos(pot: str, datoteke: Sequence[str] = ()) -> bool:
    """Zazene zaganjalnik (.desktop) na gostitelju, po zelji z datotekami. Samo v Flatpaku."""
    if not v_flatpaku() or not shutil.which("flatpak-spawn"):
        return False
    ukaz = ["flatpak-spawn", "--host", "--env=DISPLAY=" + os.environ.get("DISPLAY", ""),
            "gio", "launch", na_gostitelju(pot)] + [na_gostitelju(d) for d in datoteke]
    try:
        subprocess.Popen(ukaz, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except Exception:
        return False


def dodaj_ikone_gostitelja(Gtk) -> None:
    """Tema ikon GTK naj najde tudi ikone programov, namescenih na racunalniku."""
    if not v_flatpaku():
        return
    try:
        tema = Gtk.IconTheme.get_default()
        for m in mape_gostitelja("icons") + mape_gostitelja("pixmaps"):
            if os.path.isdir(m):
                tema.append_search_path(m)
    except Exception:
        pass
