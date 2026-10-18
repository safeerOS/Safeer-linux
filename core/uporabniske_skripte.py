"""Skripte, ki jih uporabnik sam uvozi v Medijski center (JavaScript v strani Spotify, shell na zahtevo).

Safeer skript ne dostavlja, ne prenasa in ne priporoca: kar uporabnik uvozi in vklopi, je njegova odlocitev in njegova
odgovornost (lastnik, 18. 10. 2026). Uvozi jih izrecno iz datoteke, ki jo izbere, po opozorilu v vmesniku.

- JavaScript (.js): teče v strani Spotify v Safeer DRM, pred skriptami strani (kot uporabniske skripte v brskalniku).
  Uporabi se ob naslednjem zagonu Spotifyja v Medijskem centru. Nima dostopa do mosta Safeer OS (Python), samo do strani.
- Shell (.sh): teče samo na uporabnikov ukaz (gumb Zazeni), z njegovimi pravicami (bash, brez sudo), najvec 60 s;
  izpis in izhodna koda se pokazeta v vmesniku.

Shramba: <XDG_DATA_HOME>/safeer-os/skripte/ (kazalo.json in datoteke <id>.js / <id>.sh), samo za uporabnika (0700/0600).
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

NAJVEC_SKRIPT = 50
NAJVEC_BAJTOV = 256 * 1024
NAJVEC_IMEN = 80
CAS_SHELL_S = 60
NAJVEC_IZPISA = 4000
VRSTE = ("js", "sh")
_ID = re.compile(r"^[0-9a-f]{12}$")
_zaklep = threading.RLock()


def mapa() -> Path:
    """Mapa s skriptami (SAFEER_SKRIPTE_MAPA prepise pot, za preizkuse)."""
    pot = os.environ.get("SAFEER_SKRIPTE_MAPA")
    if pot:
        return Path(pot)
    osnova = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(osnova) / "safeer-os" / "skripte"


def _kazalo_pot() -> Path:
    return mapa() / "kazalo.json"


def _beri() -> List[Dict[str, Any]]:
    try:
        podatki = json.loads(_kazalo_pot().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    izid = []
    for s in podatki if isinstance(podatki, list) else []:
        if (isinstance(s, dict) and _ID.match(str(s.get("id", ""))) and s.get("vrsta") in VRSTE
                and isinstance(s.get("ime"), str)):
            izid.append({"id": s["id"], "ime": s["ime"][:NAJVEC_IMEN], "vrsta": s["vrsta"], "vklopljena": bool(s.get("vklopljena"))})
    return izid[:NAJVEC_SKRIPT]


def _zapisi(seznam: List[Dict[str, Any]]) -> None:
    m = mapa()
    m.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(m, 0o700)
    except OSError:
        pass
    zacasna = _kazalo_pot().with_suffix(".tmp")
    zacasna.write_text(json.dumps(seznam, ensure_ascii=False), encoding="utf-8")
    os.chmod(zacasna, 0o600)
    os.replace(zacasna, _kazalo_pot())


def _pot_skripte(s: Dict[str, Any]) -> Path:
    return mapa() / ("%s.%s" % (s["id"], s["vrsta"]))


def _ime(ime: Any, vrsta: str) -> str:
    ime = re.sub(r"[\x00-\x1f\x7f]", " ", str(ime or "")).strip()
    ime = os.path.basename(ime.replace("\\", "/")).strip() or ("skripta." + vrsta)
    return ime[:NAJVEC_IMEN]


def vrsta_iz_imena(ime: str) -> str:
    k = str(ime or "").lower().rsplit(".", 1)[-1]
    return k if k in VRSTE else ""


def preberi_pot(pot: Any) -> Dict[str, Any]:
    """Prebere skripto s poti, ki jo uporabnik vpise v vmesnik (npr. ~/Prejemi/skripta.js) - za tiste, ki datoteke v
    oknu za izbiro ne najdejo (lastnik, 18. 10. 2026). Samo branje: uvoz gre se vedno skozi opozorilo in uvozi().
    Dovoljena je samo navadna datoteka .js/.sh v domaci mapi, ne v skritih mapah (~/.ssh, ~/.config ...)."""
    besedilo = str(pot or "").strip()
    if not besedilo or len(besedilo) > 4096 or "\x00" in besedilo:
        return {"ok": False, "napaka": "pot"}
    dom = os.path.realpath(os.path.expanduser("~"))
    polna = os.path.realpath(os.path.expanduser(besedilo) if besedilo.startswith("~") else
                             (besedilo if os.path.isabs(besedilo) else os.path.join(dom, besedilo)))
    if not polna.startswith(dom + os.sep):
        return {"ok": False, "napaka": "pot"}
    if any(d.startswith(".") for d in os.path.relpath(polna, dom).split(os.sep)):
        return {"ok": False, "napaka": "pot"}
    if not vrsta_iz_imena(polna):
        return {"ok": False, "napaka": "vrsta"}
    try:
        if not os.path.isfile(polna):
            return {"ok": False, "napaka": "ni_datoteke"}
        if os.path.getsize(polna) > NAJVEC_BAJTOV:
            return {"ok": False, "napaka": "velikost"}
        with open(polna, "rb") as f:
            bajti = f.read(NAJVEC_BAJTOV + 1)
        vsebina = bajti.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return {"ok": False, "napaka": "ni_datoteke"}
    if len(bajti) > NAJVEC_BAJTOV or "\x00" in vsebina:
        return {"ok": False, "napaka": "velikost"}
    return {"ok": True, "ime": os.path.basename(polna), "vsebina": vsebina}


def seznam() -> List[Dict[str, Any]]:
    with _zaklep:
        return _beri()


def uvozi(ime: Any, vsebina: Any, vrsta: Any = "") -> Dict[str, Any]:
    """Uvozi skripto (privzeto izklopljeno). {"ok": True, "skripta": {...}} ali {"ok": False, "napaka": ...}."""
    if not isinstance(vsebina, str) or not vsebina.strip():
        return {"ok": False, "napaka": "prazno"}
    vrsta = str(vrsta or "") or vrsta_iz_imena(str(ime))
    if vrsta not in VRSTE:
        return {"ok": False, "napaka": "vrsta"}
    bajti = vsebina.encode("utf-8")
    if len(bajti) > NAJVEC_BAJTOV or b"\x00" in bajti:
        return {"ok": False, "napaka": "velikost"}
    with _zaklep:
        s = _beri()
        if len(s) >= NAJVEC_SKRIPT:
            return {"ok": False, "napaka": "preveliko_stevilo"}
        nova = {"id": secrets.token_hex(6), "ime": _ime(ime, vrsta), "vrsta": vrsta, "vklopljena": False}
        m = mapa()
        m.mkdir(parents=True, exist_ok=True)
        pot = _pot_skripte(nova)
        pot.write_bytes(bajti)
        os.chmod(pot, 0o600)
        _zapisi(s + [nova])
        return {"ok": True, "skripta": nova}


def _najdi(s: List[Dict[str, Any]], id_: Any) -> Optional[Dict[str, Any]]:
    return next((x for x in s if x["id"] == str(id_)), None)


def vklopi(id_: Any, da: Any) -> Dict[str, Any]:
    with _zaklep:
        s = _beri()
        x = _najdi(s, id_)
        if x is None:
            return {"ok": False, "napaka": "ni_skripte"}
        x["vklopljena"] = bool(da)
        _zapisi(s)
        return {"ok": True, "skripta": x}


def odstrani(id_: Any) -> Dict[str, Any]:
    with _zaklep:
        s = _beri()
        x = _najdi(s, id_)
        if x is None:
            return {"ok": False, "napaka": "ni_skripte"}
        try:
            _pot_skripte(x).unlink()
        except OSError:
            pass
        _zapisi([y for y in s if y["id"] != x["id"]])
        return {"ok": True}


def aktivne_js() -> List[Dict[str, str]]:
    """Vklopljene skripte JavaScript za stran Spotify: [{ime, koda}]."""
    izid = []
    with _zaklep:
        for x in _beri():
            if x["vrsta"] != "js" or not x["vklopljena"]:
                continue
            try:
                izid.append({"ime": x["ime"], "koda": _pot_skripte(x).read_text(encoding="utf-8")})
            except (OSError, ValueError):
                continue
    return izid


def zazeni_shell(id_: Any, cas: float = CAS_SHELL_S) -> Dict[str, Any]:
    """Zazene shell skripto na uporabnikov ukaz: bash <datoteka>, brez sudo, z mejo casa. Izpis (stdout+stderr) je okrnjen."""
    with _zaklep:
        x = _najdi(_beri(), id_)
        if x is None or x["vrsta"] != "sh":
            return {"ok": False, "napaka": "ni_skripte"}
        pot = _pot_skripte(x)
    if not pot.is_file():
        return {"ok": False, "napaka": "ni_skripte"}
    try:
        r = subprocess.run(["bash", str(pot)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           cwd=os.path.expanduser("~"), timeout=cas, text=True, errors="replace")
        izpis, koda = r.stdout or "", r.returncode
    except subprocess.TimeoutExpired as e:
        izpis = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return {"ok": False, "napaka": "cas", "izpis": izpis[-NAJVEC_IZPISA:]}
    except OSError:
        return {"ok": False, "napaka": "ni_bash"}
    return {"ok": koda == 0, "koda": koda, "izpis": izpis[-NAJVEC_IZPISA:]}
