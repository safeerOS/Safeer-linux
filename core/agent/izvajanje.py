"""Naloga -> dejanje Safeer Linka na pravi napravi. Izid je kratek stavek (nacelo: agent hrani rezultate, ne surovih
podatkov). Naprave in ukazi gredo skozi Izvajalca (Control: D-Bus Naprave.Seznam / Naprave.Ukaz), zato je modul
preizkusljiv brez omrezja."""
from __future__ import annotations

import json
import subprocess
import unicodedata
from dataclasses import dataclass
from typing import Callable, List, Optional

from core.agent.razumevanje import Naloga

#: naprava iz razumevanja -> platforme v Linku (Seznam: "platforma"; racunalnik: vrsta "control")
PLATFORME = {"tv": ("tv",), "tablica": ("tablet",), "telefon": ("phone",), "racunalnik": ("linux", "windows", "macos")}

KLJUC = {"pavza": "pause", "nadaljuj": "play", "ustavi": "stop"}
GLASNOST = {"glasnost_gor": "up", "glasnost_dol": "down", "utisaj": "mute"}


@dataclass
class Izid:
    ok: bool
    besedilo: str          # kratko, za uporabnika (in spomin agenta)
    naprava: str = ""


def _brez_sumnikov(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def izberi_napravo(naprave: List[dict], vrsta: str, tukaj: str = "") -> Optional[dict]:
    """Naprava za naloga.naprava: 'tukaj' je naprava, s katere pride ukaz; sicer prva naprava te vrste (ne ta)."""
    if vrsta == "tukaj":
        return next((n for n in naprave if str(n.get("id")) == tukaj), None)
    platforme = PLATFORME.get(vrsta, ())
    kandidati = [n for n in naprave if str(n.get("platforma") or "") in platforme
                 or (vrsta == "racunalnik" and n.get("vrsta") == "control")]
    return kandidati[0] if kandidati else None


def naslov_strani(kaj: str) -> str:
    k = kaj.strip()
    if not k:
        return ""
    if k.startswith(("http://", "https://")):
        return k
    if " " not in k and "." in k:
        return "https://" + k
    return "https://duckduckgo.com/?q=" + "+".join(k.split())


class Izvajalec:
    """Vmesnik do Linka; privzeto Safeer Control prek D-Bus (gdbus), na istem racunalniku."""

    def __init__(self, naprave: Optional[Callable[[], List[dict]]] = None,
                 ukaz: Optional[Callable[[str, str, dict], dict]] = None) -> None:
        self._naprave = naprave or _dbus_naprave
        self._ukaz = ukaz or _dbus_ukaz

    def naprave(self) -> List[dict]:
        try:
            return [n for n in self._naprave() if isinstance(n, dict)]
        except Exception:  # noqa: BLE001
            return []

    def ukaz(self, naprava: str, dejanje: str, parametri: dict) -> dict:
        try:
            r = self._ukaz(naprava, dejanje, parametri)
            return r if isinstance(r, dict) else {"ok": False}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": str(e)[:120]}


def izvedi(naloga: Naloga, izvajalec: Izvajalec, tukaj: str = "") -> Izid:
    d = naloga.dejanje
    if d == "ni_ukaz":
        return Izid(True, "To ni ukaz za napravo.")
    naprave = izvajalec.naprave()
    n = izberi_napravo(naprave, naloga.naprava, tukaj)
    if n is None:
        return Izid(False, f"Naprave »{naloga.naprava}« ni v Linku.")
    nid, ime = str(n.get("id")), str(n.get("ime") or n.get("id"))

    def izid(r: dict, uspeh: str) -> Izid:
        if r.get("ok"):
            return Izid(True, uspeh, ime)
        return Izid(False, f"{ime}: {r.get('message') or r.get('code') or 'ni uspelo'}", ime)

    if d in GLASNOST:
        return izid(izvajalec.ukaz(nid, "volume", {"direction": GLASNOST[d]}),
                    {"up": "Glasneje", "down": "Tišje", "mute": "Utišano"}[GLASNOST[d]] + f" na {ime}.")
    if d in KLJUC:
        return izid(izvajalec.ukaz(nid, "key", {"key": KLJUC[d]}),
                    {"pause": "Pavza", "play": "Nadaljujem", "stop": "Ustavljeno"}[KLJUC[d]] + f" na {ime}.")
    if d == "odpri_stran":
        url = naslov_strani(naloga.kaj)
        if not url:
            return Izid(False, "Katero stran naj odprem?", ime)
        return izid(izvajalec.ukaz(nid, "open_url", {"url": url}), f"Odpiram {naloga.kaj} na {ime}.")
    if d == "odpri_aplikacijo":
        r = izvajalec.ukaz(nid, "apps.list", {"icons": False, "limit": 60})
        programi = ((r.get("data") or {}).get("items") or []) if r.get("ok") else []
        if not programi:
            return Izid(False, f"{ime} ne deli programov (dovoli jih v Safeer Linku).", ime)
        iskano = _brez_sumnikov(naloga.kaj)
        zadetek = next((p for p in programi if _brez_sumnikov(str(p.get("name") or "")) == iskano), None) or \
            next((p for p in programi if iskano and iskano in _brez_sumnikov(str(p.get("name") or ""))), None)
        if zadetek is None:
            return Izid(False, f"Na {ime} ni programa »{naloga.kaj}«.", ime)
        return izid(izvajalec.ukaz(nid, "apps.launch", {"app": zadetek.get("id")}), f"Odpiram {zadetek.get('name')} na {ime}.")
    if d in ("isci", "predvajaj"):
        if not naloga.kaj:
            return Izid(False, "Kaj naj poiščem?" if d == "isci" else "Kaj naj predvajam?", ime)
        if str(n.get("platforma") or "") in PLATFORME["racunalnik"] or n.get("vrsta") == "control":
            # Racunalnik s Safeer OS: iskalna lupa (programi, datoteke, Medijski center, splet na enem mestu).
            return izid(izvajalec.ukaz(nid, "search.query", {"q": naloga.kaj}), f"Iščem »{naloga.kaj}« na {ime}.")
        # Televizor, telefon, tablica: iskanje na YouTubu (aplikacija, sicer stran).
        url = "https://www.youtube.com/results?search_query=" + "+".join(naloga.kaj.split())
        r = izvajalec.ukaz(nid, "open_in_app", {"package": "com.google.android.youtube", "url": url})
        if not r.get("ok"):
            r = izvajalec.ukaz(nid, "open_url", {"url": url})
        return izid(r, f"Na {ime} iščem »{naloga.kaj}« na YouTubu.")
    if d == "nadaljuj_na_napravi":
        return predaj(izvajalec, naprave, n, tukaj)
    return Izid(False, f"Tega (»{d}«) agent še ne zna.", ime)


def _cas(ms: int) -> str:
    s = max(0, int(ms) // 1000)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def _kaj_igra(izvajalec: Izvajalec, naprave: List[dict], tukaj: str, cilj_id: str):
    """Naprava, ki zdaj predvaja (najprej ta, s katere pride ukaz), in njeno `play.state`. Ce nic ne igra, nazadnje
    gledani video s shranjenim mestom (`last`). Vrne (naprava, stanje) ali (None, None)."""
    vrstni = sorted((x for x in naprave if str(x.get("id")) != cilj_id), key=lambda x: str(x.get("id")) != tukaj)
    zadnji = None
    for x in vrstni:
        r = izvajalec.ukaz(str(x.get("id")), "play.state", {})
        st = r.get("data") if r.get("ok") and isinstance(r.get("data"), dict) else {}
        if not isinstance(st.get("item"), dict):
            continue
        if st.get("playing"):
            return x, st
        if st.get("last") and zadnji is None:
            zadnji = (x, st)
    return zadnji or (None, None)


def predaj(izvajalec: Izvajalec, naprave: List[dict], cilj: dict, tukaj: str = "") -> Izid:
    """»Daj to na TV«: kar igra na izvoru, ponudi cilju (`play.offer`) od istega mesta. Na cilju se pokaze pasica
    Sprejmi/Zavrni - nic se ne zacne samo (nacelo predaje v Linku). Datoteka izvora gre prek `server_device`: cilj dobi
    svoj zeton pri izvoru, zeton tega racunalnika se ne prenasa."""
    cid, cime = str(cilj.get("id")), str(cilj.get("ime") or cilj.get("id"))
    izvor, st = _kaj_igra(izvajalec, naprave, tukaj, cid)
    if izvor is None:
        return Izid(False, "Nobena naprava zdaj ne predvaja ničesar, kar bi lahko nadaljeval.", cime)
    iid, iime = str(izvor.get("id")), str(izvor.get("ime") or izvor.get("id"))
    item = dict(st["item"])
    parametri = {"item": item, "position_ms": int(st.get("position_ms") or 0),
                 "duration_ms": int(st.get("duration_ms") or 0)}
    if st.get("server") or st.get("server_device"):
        parametri["server_device"] = str(st.get("server_device") or iid)
    r = izvajalec.ukaz(cid, "play.offer", parametri)
    d = r.get("data") if isinstance(r.get("data"), dict) else {}
    naslov = str(item.get("naslov") or "posnetek")
    if r.get("ok") and d.get("queued"):
        kje = "Odpri Safeer OS na " + cime + ", da ga sprejmeš." if d.get("shown") == "later" else "Sprejmi ga na " + cime + "."
        return Izid(True, f"»{naslov}« z {iime} ({_cas(parametri['position_ms'])}) sem ponudil na {cime}. {kje}", cime)
    if r.get("ok"):
        razlog = str(d.get("reason") or "")
        if razlog == "izklopljeno":
            return Izid(False, f"{cime} ne sprejema predaje (vklopi jo v Safeer Linku).", cime)
        return Izid(False, f"{cime} tega posnetka ne more predvajati.", cime)
    if str(r.get("code") or "") == "neznano_dejanje":
        return Izid(False, f"{cime} predaje še ne pozna (posodobi Safeer).", cime)
    return Izid(False, f"{cime}: {r.get('message') or r.get('code') or 'predaja ni uspela'}", cime)


def _gdbus(metoda: str, *arg: str) -> dict:
    ukaz = ["gdbus", "call", "--session", "-d", "io.github.memelandfaner.SafeerControl",
            "-o", "/io/github/memelandfaner/SafeerControl/naprave",
            "-m", "io.github.memelandfaner.SafeerControl.Naprave." + metoda] + list(arg)
    r = subprocess.run(ukaz, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise OSError(r.stderr.strip()[:120] or "gdbus")
    import ast
    return json.loads(ast.literal_eval(r.stdout.strip())[0])


def _dbus_naprave() -> List[dict]:
    d = _gdbus("Seznam")
    return d if isinstance(d, list) else d.get("naprave", [])


def _dbus_ukaz(naprava: str, dejanje: str, parametri: dict) -> dict:
    return _gdbus("Ukaz", naprava, dejanje, json.dumps(parametri, ensure_ascii=False))
