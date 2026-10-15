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


def podatki_gostitelja() -> str:
    """Uporabnikova mapa s podatki NA RACUNALNIKU (Smeti, zaganjalniki, ikone): v Flatpaku je XDG_DATA_HOME
    zasebna mapa peskovnika (~/.var/app/<id>/data), zato bi Safeer OS gledal v prazne Smeti, medtem ko gio trash
    datoteke odlozi v prave (preizkus na testnem PC 15. 10. 2026: »Smeti so prazne«, Razveljavi ni nasel nicesar).
    Flatpak hrani gostiteljevo vrednost v HOST_XDG_DATA_HOME."""
    if v_flatpaku():
        return os.environ.get("HOST_XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")


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


def tema_ikon(Gtk):
    """Privzeta tema ikon: GTK4 (na zaslon) ali GTK3; None, ce zaslona ni (GTK4 brez zaslona)."""
    if Gtk.get_major_version() >= 4:
        from gi.repository import Gdk
        zaslon = Gdk.Display.get_default()
        return Gtk.IconTheme.get_for_display(zaslon) if zaslon is not None else None
    return Gtk.IconTheme.get_default()


def nalozen_gtk():
    """Modul Gtk v razlicici, ki jo proces ze uporablja (Safeer OS 4, Safeer Browser 3); brez nje najprej 4.0.
    Druge razlicice ne vsiljujemo - ValueError bi pomenil, da ikon ni (prej: vedno 3.0)."""
    import gi
    if gi.get_required_version("Gtk") is None:
        for razlicica in ("4.0", "3.0"):
            try:
                gi.require_version("Gtk", razlicica)
                break
            except ValueError:
                continue
    from gi.repository import Gtk
    return Gtk


def ikona_iz_teme(ime: str, velikost: int) -> str:
    """Pot do datoteke ikone v temi ikon (kot jo najde namizje); '' ce je ni. GTK3 in GTK4, samo glavna nit."""
    try:
        Gtk = nalozen_gtk()
        tema = tema_ikon(Gtk)
        if tema is None:
            return ""
        if Gtk.get_major_version() >= 4:
            # GTK4 namesto manjkajoce vrne ikono »image-missing«, zato najprej has_icon.
            if not tema.has_icon(ime):
                return ""
            slika = tema.lookup_icon(ime, None, velikost, 1, Gtk.TextDirection.NONE, 0)
            datoteka = slika.get_file() if slika is not None else None
            pot = (datoteka.get_path() or "") if datoteka is not None else ""
        else:
            info = tema.lookup_icon(ime, velikost, 0)
            pot = (info.get_filename() or "") if info is not None else ""
        return pot if pot and os.path.isfile(pot) else ""
    except Exception:
        return ""


def dodaj_ikone_gostitelja(Gtk) -> None:
    """Tema ikon GTK naj najde tudi ikone programov, namescenih na racunalniku."""
    if not v_flatpaku():
        return
    try:
        tema = tema_ikon(Gtk)
        if tema is None:
            return
        for m in mape_gostitelja("icons") + mape_gostitelja("pixmaps"):
            if os.path.isdir(m):
                # GTK4: add_search_path; GTK3: append_search_path.
                (tema.add_search_path if hasattr(tema, "add_search_path") else tema.append_search_path)(m)
    except Exception:
        pass
