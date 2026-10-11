"""Ponudniki programov v Safeer OS za Linux: uporabnik izbere, od kod bo namescal programe (lastnik, 11. 10. 2026).

Safeer nima svoje trgovine s programi in ne doloca ene same: seznam je po abecedi in brez priporocila, nic ni
privzeto. Ponudnik se namesti iz uradnega vira na uporabnikov klik - Flatpak iz Flathuba za tega uporabnika (brez
gesla) ali paket iz Mintovih/Ubuntujevih skladisc prek `pkexec apt-get install` (polkit vprasa za geslo). Snap Store je
na seznamu, a ga Safeer ne vklaplja: Linux Mint ima Snap izklopljen namenoma (/etc/apt/preferences.d/nosnap.pref),
odlocitev, ali ga vklopi, je uporabnikova. Ukazi so nespremenljivi: kaj se namesti, pride iz PONUDNIKI, nikoli s strani.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Callable, List, Optional

FLATHUB = ("flathub", "https://dl.flathub.org/repo/flathub.flatpakrepo")

#: vrsta: "flatpak" (oznaka na Flathubu), "apt" (paketi in ukaz za zagon), "snap" (samo razlaga, ne namescamo).
PONUDNIKI = [
    {"id": "bazaar", "ime": "Bazaar", "vrsta": "flatpak", "flatpak": "io.github.kolunmi.Bazaar",
     "stran": "https://flathub.org/apps/io.github.kolunmi.Bazaar"},
    {"id": "discover", "ime": "Discover", "vrsta": "apt", "paketi": ["plasma-discover", "plasma-discover-backend-flatpak"],
     "ukaz": ["plasma-discover"], "stran": "https://apps.kde.org/discover/"},
    {"id": "gearlever", "ime": "Gear Lever", "vrsta": "flatpak", "flatpak": "it.mijorus.gearlever",
     "stran": "https://flathub.org/apps/it.mijorus.gearlever"},
    {"id": "gnome-software", "ime": "GNOME Programi", "vrsta": "apt", "paketi": ["gnome-software", "gnome-software-plugin-flatpak"],
     "ukaz": ["gnome-software"], "stran": "https://apps.gnome.org/Software/"},
    {"id": "snap-store", "ime": "Snap Store", "vrsta": "snap", "stran": "https://linuxmint-user-guide.readthedocs.io/en/latest/snap.html"},
    {"id": "mintinstall", "ime": "Upravitelj programov", "vrsta": "apt", "paketi": ["mintinstall"],
     "ukaz": ["mintinstall"], "stran": "https://linuxmint-user-guide.readthedocs.io/en/latest/software.html"},
]
NOSNAP = "/etc/apt/preferences.d/nosnap.pref"


def _tek(ukaz: List[str], cas: int) -> tuple:
    try:
        r = subprocess.run(ukaz, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=cas)
        return r.returncode, r.stdout or ""
    except subprocess.TimeoutExpired:
        return 124, "cas je potekel"
    except OSError as e:
        return 127, str(e)


def _ponudnik(id_: str) -> Optional[dict]:
    return next((p for p in PONUDNIKI if p["id"] == str(id_ or "")), None)


def _apt_namescen(paket: str, tek: Callable) -> bool:
    koda, izpis = tek(["dpkg-query", "-W", "-f=${Status}", paket], 20)
    return koda == 0 and "install ok installed" in izpis


def namescen(p: dict, tek: Callable = _tek, najdi: Callable = shutil.which) -> bool:
    if p["vrsta"] == "flatpak":
        return bool(najdi("flatpak")) and tek(["flatpak", "info", p["flatpak"]], 20)[0] == 0
    if p["vrsta"] == "apt":
        return bool(najdi(p["ukaz"][0])) and _apt_namescen(p["paketi"][0], tek)
    if p["vrsta"] == "snap":
        if not najdi("snap"):
            return False
        return bool(najdi("snap-store")) or tek(["snap", "list", "snap-store"], 20)[0] == 0
    return False


def stanje(tek: Callable = _tek, najdi: Callable = shutil.which, nosnap: Optional[bool] = None) -> List[dict]:
    """Za stran: id, ime, vrsta, ali je namescen in ali ga Safeer zna namestiti (snap: ne, Mint ga blokira)."""
    blokiran = os.path.exists(NOSNAP) if nosnap is None else nosnap
    izid = []
    for p in PONUDNIKI:
        n = namescen(p, tek, najdi)
        mozno = p["vrsta"] == "flatpak" and bool(najdi("flatpak")) or p["vrsta"] == "apt" and bool(najdi("pkexec"))
        izid.append({"id": p["id"], "ime": p["ime"], "vrsta": p["vrsta"], "stran": p["stran"], "namescen": n,
                     "namestljiv": bool(mozno) and not n, "snap_blokiran": p["vrsta"] == "snap" and blokiran})
    return izid


def namesti(id_: str, tek: Callable = _tek, najdi: Callable = shutil.which) -> dict:
    """Namesti ponudnika na uporabnikov klik. Flatpak: --user (brez gesla); apt: pkexec (polkit vprasa za geslo)."""
    p = _ponudnik(id_)
    if p is None:
        return {"ok": False, "napaka": "ni_ponudnika"}
    if p["vrsta"] == "snap":
        return {"ok": False, "napaka": "snap"}
    if p["vrsta"] == "flatpak":
        if not najdi("flatpak"):
            return {"ok": False, "napaka": "ni_flatpak"}
        koda, izpis = tek(["flatpak", "remote-add", "--user", "--if-not-exists", FLATHUB[0], FLATHUB[1]], 120)
        if koda != 0:
            return {"ok": False, "napaka": "vir", "podrobnosti": izpis.strip()[-300:]}
        koda, izpis = tek(["flatpak", "install", "--user", "--noninteractive", "-y", FLATHUB[0], p["flatpak"]], 3600)
        if koda != 0:
            return {"ok": False, "napaka": "prostor" if "space" in izpis.lower() else "namestitev", "podrobnosti": izpis.strip()[-300:]}
        return {"ok": True, "id": p["id"]}
    if not najdi("pkexec"):
        return {"ok": False, "napaka": "ni_pkexec"}
    koda, izpis = tek(["pkexec", "apt-get", "install", "-y", *p["paketi"]], 1800)
    if koda in (126, 127):          # pkexec: uporabnik je okno za geslo zaprl ali ni pooblascen
        return {"ok": False, "napaka": "preklicano"}
    if koda != 0:
        return {"ok": False, "napaka": "namestitev", "podrobnosti": izpis.strip()[-300:]}
    return {"ok": True, "id": p["id"]}


def odpri(id_: str, popen: Callable = subprocess.Popen) -> bool:
    """Zazene namescenega ponudnika (ukaz iz PONUDNIKI)."""
    p = _ponudnik(id_)
    if p is None or p["vrsta"] == "snap":
        return False
    ukaz = ["flatpak", "run", p["flatpak"]] if p["vrsta"] == "flatpak" else p["ukaz"]
    try:
        popen(ukaz, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False
