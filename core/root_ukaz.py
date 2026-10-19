"""Ukazi, ki tecejo kot root (pkexec): vedno z absolutnimi potmi.

pkexec program poisce po PATH KLICATELJA, se preden okolje pocisti (polkit 124, pkexec.c: g_find_program_in_path pred
clearenv). Ubuntu 24.04 / Mint 22 da ~/.local/bin na zacetek PATH, ce mapa obstaja - program, ki tece kot uporabnik, bi
tja odlozil svoj »install« ali »pkexec« in ob vpisu gesla dobil root (neodvisni pregled, 19. 10. 2026; isti model
napadalca kot pri namestitvi posodobitev iz ~/.cache). Zato: pkexec in program vedno z absolutno potjo.

V Flatpaku pkexec tece na gostitelju prek ovoja /app/host-bin/pkexec (packaging/flatpak_host_wrappers.sh), ki poklice
/usr/bin/pkexec; PATH peskovnika doloca paket, ne uporabnik. Program je pot na gostitelju.
"""
from __future__ import annotations

import os
from typing import List

PKEXEC = "/usr/bin/pkexec"

#: Programi, ki jih Safeer zazene kot root (poti na Linux Mint 22 / Ubuntu 24.04, preverjeno na testnem PC 19. 10. 2026).
SH = "/bin/sh"
INSTALL = "/usr/bin/install"
APT_GET = "/usr/bin/apt-get"
ADD_APT_REPOSITORY = "/usr/bin/add-apt-repository"
MINTSOURCES = "/usr/bin/mintsources"
LIGHTDM_SETTINGS = "/usr/bin/lightdm-settings"


def v_flatpaku() -> bool:
    return bool(os.environ.get("FLATPAK_ID")) or os.path.exists("/.flatpak-info")


def pkexec() -> str:
    """Ovoj gostitelja v Flatpaku, sicer /usr/bin/pkexec - nikoli iskanje po uporabnikovem PATH."""
    if v_flatpaku():
        return "/app/host-bin/pkexec"
    return PKEXEC


def na_voljo() -> bool:
    return os.access(pkexec(), os.X_OK)


def ukaz(program: str, *argumenti: str) -> List[str]:
    """[pkexec, program, argumenti...]; program mora biti absolutna pot (sicer ValueError)."""
    if not os.path.isabs(program):
        raise ValueError("program za root mora biti absolutna pot: %r" % program)
    return [pkexec(), program, *argumenti]
