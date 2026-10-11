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


def _velikost_mb(besedilo: str) -> float:
    """»11.9 MB« / »1.1 GB« / »812 kB« -> MB (0, ce ni stevila)."""
    import re
    m = re.match(r"\s*([\d.,]+)\s*([kMG])B", besedilo or "")
    if not m:
        return 0.0
    v = float(m.group(1).replace(",", "."))
    return round(v / 1024 if m.group(2) == "k" else v * 1024 if m.group(2) == "G" else v, 1)


def _remote_info(ref: str, tek: Callable) -> dict:
    """Polja iz `flatpak remote-info` (sistemski Flathub, sicer uporabnikov)."""
    for nam in ("--system", "--user"):
        koda, izpis = tek(["flatpak", "remote-info", nam, FLATHUB[0], ref], 60)
        if koda == 0:
            polja = {}
            for v in izpis.splitlines():
                k, _, vr = v.partition(":")
                if vr and k.strip() and k.strip() not in polja:
                    polja[k.strip()] = vr.strip()
            return polja
    return {}


SAMODEJNO_MINT = "/var/lib/linuxmint/mintupdate-automatic-upgrades-enabled"


def samodejne_posodobitve(vrsta: str, tek: Callable = _tek, obstaja: Callable = os.path.exists) -> bool:
    """Ali bo Upravitelj posodobitev (Linux Mint) ta program posodabljal sam - to je uporabnikova nastavitev v Mintu,
    ne Safeerjeva. apt: samodejne nadgradnje vklopljene; flatpak: te in »auto-update-flatpaks«."""
    if not obstaja(SAMODEJNO_MINT):
        return False
    if vrsta != "flatpak":
        return True
    koda, izpis = tek(["gsettings", "get", "com.linuxmint.updates", "auto-update-flatpaks"], 10)
    return koda == 0 and izpis.strip() == "true"


def podrobnosti(id_: str, tek: Callable = _tek, najdi: Callable = shutil.which, obstaja: Callable = os.path.exists) -> dict:
    """Kaj natanko se bo namestilo, od kod in koliko - uporabnik to vidi PRED namestitvijo (lastnik, 11. 10. 2026:
    »uporabnik vedno ve, kaj se namesca«). Nic se ne namesti; samo branje (flatpak remote-info, apt-get -s)."""
    p = _ponudnik(id_)
    if p is None:
        return {"ok": False, "napaka": "ni_ponudnika"}
    if p["vrsta"] == "flatpak":
        i = _remote_info(p["flatpak"], tek)
        if not i:
            return {"ok": False, "napaka": "ni_podatkov"}
        izid = {"ok": True, "vrsta": "flatpak", "vir": "Flathub", "za": "uporabnik", "geslo": False,
                "paketi": [{"ime": p["flatpak"], "razlicica": i.get("Version", ""), "prenos_mb": _velikost_mb(i.get("Download", ""))}],
                "licenca": i.get("License", "")}
        okolje = i.get("Runtime", "")
        if okolje:
            if tek(["flatpak", "info", okolje], 20)[0] != 0:
                r = _remote_info(okolje.split("/")[0] + "//" + okolje.split("/")[-1], tek) if "/" in okolje else {}
                izid["paketi"].append({"ime": okolje, "razlicica": r.get("Version", ""), "prenos_mb": _velikost_mb(r.get("Download", "")),
                                       "okolje": True})
        izid["prenos_mb"] = round(sum(x["prenos_mb"] for x in izid["paketi"]), 1)
        izid["samodejno"] = samodejne_posodobitve("flatpak", tek, obstaja)
        return izid
    if p["vrsta"] == "apt":
        koda, izpis = tek(["env", "LANG=C", "apt-get", "-s", "install", *p["paketi"]], 120)
        if koda != 0:
            return {"ok": False, "napaka": "ni_podatkov"}
        paketi = []
        for v in izpis.splitlines():
            if v.startswith("Inst "):
                deli = v.split()
                razl = deli[2].strip("(") if len(deli) > 2 and deli[2].startswith("(") else (deli[3].strip("(") if len(deli) > 3 else "")
                paketi.append({"ime": deli[1], "razlicica": razl})
        koda, uri = tek(["env", "LANG=C", "apt-get", "install", "--print-uris", "-y", "-qq", *p["paketi"]], 120)
        bajti = 0
        for v in (uri or "").splitlines():
            deli = v.split()
            if len(deli) >= 3 and deli[2].isdigit():
                bajti += int(deli[2])
        return {"ok": True, "vrsta": "apt", "vir": "Linux Mint / Ubuntu", "za": "sistem", "geslo": True,
                "paketi": paketi, "prenos_mb": round(bajti / 1048576, 1), "samodejno": samodejne_posodobitve("apt", tek, obstaja)}
    return {"ok": False, "napaka": "snap"}


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
