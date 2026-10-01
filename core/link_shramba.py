"""Skupni prostor v Safeer Linku (zakon solidarnosti, korak 2).

Racunalnik, ki mu zmanjkuje prostora, shrani datoteko na napravo v Linku z najvec prostora, ki ta
trenutek sme pomagati (`host.info` -> `pomoc`). Naprava datoteko prenese sama s tega racunalnika
(HTTPS, pripeto potrdilo, zeton), med prenosom racuna SHA-256 in jo objavi sele, ko se ujema
(`storage.put` / `storage.status`, Android Shramba.kt).

Original na racunalniku se NIKOLI ne izbrise sam: ko je kopija preverjena, uporabnik vidi, na kateri
napravi in v kateri mapi je, in sam potrdi izbris (ali obdrzi oboje). Izbrisemo le, ce se datoteka
medtem ni spremenila.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid
from typing import Callable, Dict, List, Optional

#: Naprava, ki shrani, mora imeti vsaj toliko prostora vec od datoteke (enako kot Shramba.kt).
REZERVA = 2 * 1024 * 1024 * 1024
#: Racunalniki zaenkrat ne sprejemajo datotek drugih (storage.put je na Androidu).
NAMIZNE = ("linux", "windows", "macos")


class Premik:
    def __init__(self, pot: str) -> None:
        self.id = uuid.uuid4().hex
        self.pot = os.path.realpath(pot)
        self.ime = os.path.basename(self.pot)
        st = os.stat(self.pot)
        self.velikost = st.st_size
        self.mtime = st.st_mtime
        self.stanje = "pripravljam"    # pripravljam | prenasam | kopija | napaka | izbrisano | obdrzano
        self.preneseno = 0
        self.napaka = ""
        self.cilj = ""
        self.cilj_ime = ""
        self.kje = ""
        self.sha256 = ""

    def slovar(self) -> dict:
        return {"id": self.id, "ime": self.ime, "pot": self.pot, "velikost": self.velikost, "stanje": self.stanje,
                "preneseno": self.preneseno, "napaka": self.napaka, "naprava": self.cilj_ime, "kje": self.kje}


def sha256_datoteke(pot: str) -> str:
    h = hashlib.sha256()
    with open(pot, "rb") as d:
        for kos in iter(lambda: d.read(1024 * 1024), b""):
            h.update(kos)
    return h.hexdigest()


def izberi_cilj(naprave: List[dict], vprasaj: Callable[[str, str, dict], dict], velikost: int) -> Optional[dict]:
    """Naprava z najvec prostega prostora, ki sme pomagati in ima prostor za datoteko + rezervo.
    `vprasaj(id, dejanje, parametri)` -> {"ok", "data"} (Link ukaz s cakanjem)."""
    najboljsa, najvec = None, -1
    for n in naprave:
        if n.get("ta") or "files" not in (n.get("zmoznosti") or []) or n.get("platforma") in NAMIZNE:
            continue
        r = vprasaj(n["id"], "host.info", {})
        d = r.get("data") if r.get("ok") else None
        if not isinstance(d, dict):
            continue
        if (d.get("pomoc") or {}).get("lahko") is False:
            continue
        prosto = int((d.get("disk") or {}).get("prosto", -1))
        if prosto < velikost + REZERVA:
            continue
        if prosto > najvec:
            najboljsa, najvec = n, prosto
    return najboljsa


class Shramba:
    """Premiki datotek na druge naprave; klice jih Safeer OS prek Controla (D-Bus Naprave.Shramba*)."""

    def __init__(self, naprave: Callable[[], List[dict]], vprasaj: Callable[[str, str, dict], dict],
                 datoteke, hub_url: Callable[[], str] = lambda: "", cakaj: float = 2.0) -> None:
        self.naprave = naprave
        self.vprasaj = vprasaj
        self.datoteke = datoteke
        self.hub_url = hub_url
        self.cakaj = cakaj
        self.premiki: Dict[str, Premik] = {}

    def zacni(self, pot: str) -> dict:
        if not pot or not os.path.isfile(pot):
            return {"ok": False, "koda": "ni_datoteke"}
        p = Premik(pot)
        self.premiki[p.id] = p
        threading.Thread(target=self._premakni, args=(p,), name="safeer-shramba", daemon=True).start()
        return {"ok": True, **p.slovar()}

    def stanje(self, id_: str) -> dict:
        p = self.premiki.get(id_)
        return {"ok": True, **p.slovar()} if p else {"ok": False, "koda": "ni_premika"}

    def izbrisi_original(self, id_: str) -> dict:
        """Uporabnik je potrdil izbris originala (kopija je preverjena in uporabnik ve, kje je)."""
        p = self.premiki.get(id_)
        if p is None or p.stanje != "kopija":
            return {"ok": False, "koda": "ni_kopije"}
        try:
            st = os.stat(p.pot)
        except OSError:
            return {"ok": False, "koda": "ni_datoteke"}
        if st.st_size != p.velikost or st.st_mtime != p.mtime:
            return {"ok": False, "koda": "spremenjena"}   # medtem spremenjena: kopija ni vec ista
        os.remove(p.pot)
        p.stanje = "izbrisano"
        return {"ok": True, **p.slovar()}

    def obdrzi(self, id_: str) -> dict:
        p = self.premiki.get(id_)
        if p is None:
            return {"ok": False, "koda": "ni_premika"}
        if p.stanje == "kopija":
            p.stanje = "obdrzano"
        return {"ok": True, **p.slovar()}

    def _premakni(self, p: Premik) -> None:
        try:
            p.sha256 = sha256_datoteke(p.pot)
            n = izberi_cilj(self.naprave(), self.vprasaj, p.velikost)
            if n is None:
                raise _Napaka("ni_naprave")
            p.cilj, p.cilj_ime = n["id"], n.get("ime") or n["id"]
            s = self.datoteke.streznik
            s.zazeni()
            from core import link_datoteke
            hub = self.hub_url() or ""
            naslov = link_datoteke.naslov_do_huba(hub) if hub else link_datoteke.krajevni_naslov()
            url = s.osnova(naslov) + s.dodaj_datoteko_toka(p.pot)
            r = self.vprasaj(p.cilj, "storage.put", {"url": url, "fp": s.odtis, "token": s.zeton_za(p.cilj),
                                                     "name": p.ime, "size": p.velikost, "sha256": p.sha256})
            if not r.get("ok"):
                raise _Napaka(str(r.get("koda") or "zavrnjeno"))
            opravilo = str((r.get("data") or {}).get("id") or "")
            p.stanje = "prenasam"
            brez_odgovora = 0
            while True:
                time.sleep(self.cakaj)
                r = self.vprasaj(p.cilj, "storage.status", {"id": opravilo})
                d = r.get("data") or {}
                if not r.get("ok") and not d:
                    brez_odgovora += 1
                    if brez_odgovora > 30:
                        raise _Napaka("naprava_ne_odgovori")
                    continue
                brez_odgovora = 0
                p.preneseno = int(d.get("done") or 0)
                if d.get("state") == "koncano":
                    p.kje = str(d.get("where") or "")
                    p.stanje = "kopija"
                    return
                if d.get("state") == "napaka":
                    raise _Napaka(str(d.get("error") or "napaka"))
        except _Napaka as e:
            p.napaka, p.stanje = str(e), "napaka"
        except Exception as e:  # noqa: BLE001 - premik ne sme podreti Controla
            p.napaka, p.stanje = str(e) or type(e).__name__, "napaka"


class _Napaka(Exception):
    pass
