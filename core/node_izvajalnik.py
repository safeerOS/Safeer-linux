"""Node.js za programe Safeer OS: nas pripeti Node.js 22 LTS iz paketa .deb (lastnik: nacin »deb«).

Paket safeer-os ima Node.js v /usr/lib/safeer-os/node (packaging/node_vendor.py, razlicica in SHA-256 pripeta) - ne v
PATH in ne v /usr/bin, zato ne trci s sistemskim node (paket nodejs, nvm): ta ostane, kot ga ima uporabnik. Kdor v
Safeer OS ali Safeer Controlu potrebuje node (lokalni posrednik jezikovnih modelov za agenta, orodja), dobi pot in
okolje tu - nikoli `node` iz PATH na slepo.

Okolje: brez NODE_OPTIONS in NODE_PATH uporabnika (njegove nastavitve za njegov node ne smejo spremeniti nasega, npr.
--require tuje skripte) in brez nasih zasebnih poti WebKita (core/zasebni_webkit.py); nasa mapa bin je prva v PATH, da
otroci, ki klicejo `node`, dobijo istega.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Dict, List, Mapping, Optional

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: Najnizja glavna razlicica sistemskega node, ki ga sprejmemo, kadar nasega ni (izvorna koda, Flatpak, AppImage).
NAJMANJ = 22
#: Spremenljivke uporabnikovega node, ki jih nas node ne podeduje.
TUJE = ("NODE_OPTIONS", "NODE_PATH", "NPM_CONFIG_PREFIX")
_razlicice: Dict[str, int] = {}


def mapa(koren: Optional[str] = None) -> Optional[str]:
    """Mapa nasega Node.js (…/node z bin/node) ali None. Safeer Control iz /usr/lib/safeer-control uporabi tistega iz
    paketa safeer-os (en paket, en Node.js)."""
    koren = os.path.abspath(koren or KOREN)
    kandidati = [os.path.join(koren, "node")]
    if os.path.basename(koren) == "safeer-control":
        kandidati.append(os.path.join(os.path.dirname(koren), "safeer-os", "node"))
    for m in kandidati:
        if os.access(os.path.join(m, "bin", "node"), os.X_OK):
            return m
    return None


def glavna_razlicica(program: str) -> int:
    """Glavna razlicica node (npr. 22) ali 0, ce se ne zazene."""
    if program not in _razlicice:
        try:
            r = subprocess.run([program, "--version"], capture_output=True, text=True, timeout=15,
                               env=okolje(dodaj_v_pot=False))
            m = re.match(r"v(\d+)\.", r.stdout.strip()) if r.returncode == 0 else None
            _razlicice[program] = int(m.group(1)) if m else 0
        except (OSError, subprocess.SubprocessError):
            _razlicice[program] = 0
    return _razlicice[program]


def pot(koren: Optional[str] = None, sistemski: bool = True) -> Optional[str]:
    """Pot do node: najprej nas iz paketa; sistemski samo, ce nasega ni in je vsaj NAJMANJ (sicer None)."""
    m = mapa(koren)
    if m is not None:
        return os.path.join(m, "bin", "node")
    if sistemski:
        najden = shutil.which("node")
        if najden and glavna_razlicica(najden) >= NAJMANJ:
            return najden
    return None


def okolje(osnova: Optional[Mapping[str, str]] = None, dodaj_v_pot: bool = True,
           koren: Optional[str] = None) -> dict:
    """Okolje za node (glej opis modula)."""
    from core import zasebni_webkit
    o = zasebni_webkit.okolje_za_zunanje(osnova)
    for ime in TUJE:
        o.pop(ime, None)
    m = mapa(koren) if dodaj_v_pot else None
    if m is not None:
        poti = [p for p in o.get("PATH", "/usr/bin:/bin").split(os.pathsep) if p and p != os.path.join(m, "bin")]
        o["PATH"] = os.pathsep.join([os.path.join(m, "bin")] + poti)
    return o


def ukaz(argumenti: List[str], koren: Optional[str] = None) -> Optional[List[str]]:
    """[node, *argumenti] ali None, ce Node.js ni na voljo."""
    program = pot(koren)
    return [program, *argumenti] if program else None
