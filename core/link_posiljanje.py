"""Posiljanje datotek s tega racunalnika na izbrano napravo v Safeer Linku.

Safeer OS (locen proces) poslje prek Controla (D-Bus ``Naprave.Poslji`` / ``Naprave.PosljiStanje``): uporabnik v
Datotekah povlece datoteke na napravo ali izbere »Poslji na napravo«. Vsaka datoteka gre po isti poti kot »Poslji
datoteko« v Controlu (``link_deljenje.poslji_datoteko``: oddaja sredisci, sredisce pove cilju, cilj jo prevzame in
preveri SHA-256); tu je samo vrsta z napredkom, ki jo stran bere.

Brez GTK in brez omrezja: funkcijo za oddajo dobi od klicatelja, zato je preizkusljiv sam.
"""

from __future__ import annotations

import os
import threading
import uuid
from typing import Callable, Dict, List, Optional, Tuple

#: Najvec datotek v enem posiljanju (izbira v Datotekah, skupaj z vsebino poslanih map).
NAJVEC_DATOTEK = 5000
#: Najvecja datoteka (link_hub_deljenje.NAJVECJA_DATOTEKA): prej 4 GB; zdaj meja le prostor na disku cilja.
NAJVECJA_DATOTEKA = 1024 ** 4
#: Koncanih posiljanj hranimo toliko, da stran se prebere zadnje stanje.
NAJVEC_KONCANIH = 20


def datoteke_mape(mapa: str, najvec: int) -> List[Tuple[str, str]]:
    """[(pot datoteke, relativna mapa)] vseh datotek v mapi; relativna mapa se zacne z imenom mape same.
    Simbolnim povezavam ne sledimo (zanka, datoteke zunaj mape); skrite datoteke in mape ostanejo doma."""
    koren = os.path.dirname(os.path.realpath(mapa))
    izid: List[Tuple[str, str]] = []
    for pot, mape, imena in os.walk(mapa, followlinks=False):
        mape[:] = sorted(m for m in mape if not m.startswith("."))
        for ime in sorted(imena):
            dat = os.path.join(pot, ime)
            if ime.startswith(".") or os.path.islink(dat) or not os.path.isfile(dat):
                continue
            izid.append((os.path.realpath(dat), os.path.relpath(os.path.realpath(pot), koren).replace(os.sep, "/")))
            if len(izid) >= najvec:
                return izid
    return izid


class Posiljka:
    def __init__(self, naprava: str, ime_naprave: str, poti: List[str], map_: int,
                 podmape: Optional[List[str]] = None) -> None:
        self.id = uuid.uuid4().hex
        self.naprava = naprava
        self.ime_naprave = ime_naprave
        self.poti = poti
        #: Relativna mapa vsake datoteke pri posiljanju cele mape ("" = datoteka sama).
        self.podmape = list(podmape) if podmape else [""] * len(poti)
        self.velikosti = [os.path.getsize(p) for p in poti]
        self.skupaj = sum(self.velikosti)
        self.mape = map_                # poslane mape (z vso vsebino)
        self.stanje = "posiljam"        # posiljam | poslano | napaka
        self.poslanih = 0
        self.ime = os.path.basename(poti[0]) if poti else ""
        self.bajtov = 0
        self.koda = ""
        self.sporocilo = ""
        self.zasedena_od = ""

    def slovar(self) -> dict:
        odstotek = 100 if self.stanje == "poslano" else (int(self.bajtov * 100 / self.skupaj) if self.skupaj else 0)
        return {"id": self.id, "stanje": self.stanje, "naprava": self.ime_naprave, "datotek": len(self.poti),
                "poslanih": self.poslanih, "ime": self.ime, "odstotek": max(0, min(100, odstotek)), "mape": self.mape,
                "koda": self.koda, "sporocilo": self.sporocilo, "zasedenaOd": self.zasedena_od}


class Posiljanje:
    def __init__(self, poslji: Callable[[str, str, Callable[[int], None]], Tuple[bool, Dict[str, str]]],
                 ime_naprave: Callable[[str], str] = lambda i: i) -> None:
        self._poslji = poslji
        self._ime_naprave = ime_naprave
        self._zaklep = threading.Lock()
        self._posiljke: Dict[str, Posiljka] = {}

    def zacni(self, naprava: str, poti: List[str]) -> dict:
        naprava = str(naprava or "").strip()
        if not naprava:
            return {"ok": False, "koda": "ni_naprave"}
        datoteke, podmape, mape = [], [], 0
        for p in poti if isinstance(poti, list) else []:
            p = os.path.realpath(str(p))
            if os.path.isdir(p):
                # Cela mapa (lastnik, 11. 10. 2026): vsaka datoteka z relativno mapo, cilj ustvari isto drevo.
                mape += 1
                for dat, pod in datoteke_mape(p, NAJVEC_DATOTEK + 1 - len(datoteke)):
                    if dat not in datoteke:
                        datoteke.append(dat)
                        podmape.append(pod)
            elif os.path.isfile(p) and p not in datoteke:
                datoteke.append(p)
                podmape.append("")
            if len(datoteke) > NAJVEC_DATOTEK:
                return {"ok": False, "koda": "prevec_datotek", "najvec": NAJVEC_DATOTEK}
        if not datoteke:
            return {"ok": False, "koda": "prazna_mapa" if mape else "ni_datoteke", "mape": mape}
        try:
            p = Posiljka(naprava, self._ime_naprave(naprava) or naprava, datoteke, mape, podmape)
        except OSError:
            return {"ok": False, "koda": "ni_datoteke"}
        if any(v > NAJVECJA_DATOTEKA for v in p.velikosti):
            return {"ok": False, "koda": "prevelika"}
        with self._zaklep:
            koncane = [i for i, x in self._posiljke.items() if x.stanje != "posiljam"]
            for i in koncane[:max(0, len(koncane) - NAJVEC_KONCANIH + 1)]:
                self._posiljke.pop(i, None)
            self._posiljke[p.id] = p
        threading.Thread(target=self._teci, args=(p,), name="safeer-posiljanje", daemon=True).start()
        return {"ok": True, **p.slovar()}

    def stanje(self, id_: str) -> dict:
        with self._zaklep:
            p = self._posiljke.get(str(id_ or ""))
        return {"ok": True, **p.slovar()} if p else {"ok": False, "koda": "ni_posiljke"}

    def _teci(self, p: Posiljka) -> None:
        opravljeno = 0
        for pot, velikost, podmapa in zip(p.poti, p.velikosti, p.podmape):
            p.ime = os.path.basename(pot)

            def napredek(odstotek: int, _o=opravljeno, _v=velikost) -> None:
                p.bajtov = _o + int(_v * max(0, min(100, int(odstotek))) / 100)

            try:
                # Brez mape klic ostane, kot je bil (tudi poslji, ki argumenta `mapa` ne pozna).
                ok, n = self._poslji(p.naprava, pot, napredek, mapa=podmapa) if podmapa else \
                    self._poslji(p.naprava, pot, napredek)
            except Exception as e:  # noqa: BLE001 - posiljanje ne sme podreti Controla
                ok, n = False, {"sporocilo": str(e) or type(e).__name__, "koda": "posiljanje_ni_uspelo", "zasedenaOd": ""}
            if not ok:
                n = n if isinstance(n, dict) else {}
                p.koda = str(n.get("koda") or "posiljanje_ni_uspelo")
                p.sporocilo = str(n.get("sporocilo") or "")
                p.zasedena_od = str(n.get("zasedenaOd") or "")
                p.stanje = "napaka"
                return
            opravljeno += velikost
            p.bajtov = opravljeno
            p.poslanih += 1
        p.stanje = "poslano"
