"""Upravljanje globalnih bližnjic za Cinnamon (idempotentno nastavljanje)."""
import os
import sys
from typing import List, Optional

PARENT_SCHEMA = "org.cinnamon.desktop.keybindings"
CUSTOM_SCHEMA = "org.cinnamon.desktop.keybindings.custom-keybinding"
CUSTOM_PATH_BASE = "/org/cinnamon/desktop/keybindings/custom-keybindings"
WM_SCHEMA = "org.cinnamon.desktop.keybindings.wm"


def nastavi_globalno_bliznjico(ime: str, ukaz: str, bliznjice: List[str]) -> bool:
    """Idempotentno nastavi ali posodobi bližnjico v Cinnamonu brez podvajanja.
    Če bližnjica z istim imenom že obstaja, posodobi ukaz, ohrani pa uporabnikove tipke.
    Če ne obstaja, poišče prosti ID customX in ga doda v custom-list.
    Če bližnjica vključuje <Super>space, razreši morebiten spor s stikalom tipkovnice.
    """
    try:
        from gi.repository import Gio
    except ImportError:
        return False

    try:
        parent = Gio.Settings.new(PARENT_SCHEMA)
    except Exception:
        return False

    # Razrešitev morebitnega spora: če katera od zahtevanih bližnjic sovpada s switch-input-source
    try:
        wm = Gio.Settings.new(WM_SCHEMA)
        sis = list(wm.get_strv("switch-input-source"))
        posodobljeno = False
        for b in bliznjice:
            if b in sis:
                sis.remove(b)
                posodobljeno = True
        if posodobljeno:
            wm.set_strv("switch-input-source", sis)
    except Exception:
        pass

    custom_list = list(parent.get_strv("custom-list"))
    tarca_id = None

    for entry in custom_list:
        if not entry.startswith("custom"):
            continue
        pot = f"{CUSTOM_PATH_BASE}/{entry}/"
        try:
            s = Gio.Settings.new_with_path(CUSTOM_SCHEMA, pot)
            if s.get_string("name") == ime:
                tarca_id = entry
                # Uporabnikove bližnjice ne prepišemo, če so že nastavljene
                obstojece = list(s.get_strv("binding"))
                if not obstojece:
                    s.set_strv("binding", bliznjice)
                s.set_string("command", ukaz)
                return True
        except Exception:
            continue

    if not tarca_id:
        stevilke = []
        for entry in custom_list:
            if entry.startswith("custom"):
                try:
                    stevilke.append(int(entry.replace("custom", "")))
                except ValueError:
                    pass
        naslednja = 0
        while naslednja in stevilke:
            naslednja += 1
        tarca_id = f"custom{naslednja}"
        custom_list.append(tarca_id)
        parent.set_strv("custom-list", custom_list)

    pot = f"{CUSTOM_PATH_BASE}/{tarca_id}/"
    s = Gio.Settings.new_with_path(CUSTOM_SCHEMA, pot)
    s.set_string("name", ime)
    s.set_string("command", ukaz)
    s.set_strv("binding", bliznjice)
    return True


if __name__ == "__main__":
    ime = sys.argv[1] if len(sys.argv) > 1 else "Safeer Iskanje"
    ukaz = sys.argv[2] if len(sys.argv) > 2 else "safeer-os --iskanje"
    tipke = sys.argv[3:] if len(sys.argv) > 3 else ["<Super>space"]
    uspeh = nastavi_globalno_bliznjico(ime, ukaz, tipke)
    sys.exit(0 if uspeh else 1)
