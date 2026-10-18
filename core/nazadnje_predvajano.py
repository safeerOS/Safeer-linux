"""Nazadnje predvajano (lastnik, 18. 10. 2026): zadnji seznam predvajanja je glavna vsebina Domov z gumbom »Nadaljuj«
(skladba in mesto v njej, kjer je uporabnik ostal). Ko seznam odigra do konca in uporabnik med poslusanjem ni nicesar
spremenil, Safeer sam izbere seznam, ki je po zvrsti najblizji, in nadaljuje.

Shramba: nazadnje_seznam.json v mapi podatkov Medijskega centra (atomaren zapis):
  {"zadnji": {"izvor", "kljuc", "mesto", "skupaj", "skladba", "pozicija", "cas", "red", "veriga"} | None,
   "zgodovina": [kljuc izvora, ...]  nazadnje poslusani seznami, najnovejsi prvi (najvec NAJVEC_ZGODOVINE)
   "zivi": [id skladbe, ...]}        skladbe s seznamov, ki so se izkazale za prenos v zivo (oznaka »V zivo«)

Izvor seznama (kar stran pozna):
  {"tip": "seznam", "ref": ime}                    uporabnikov seznam predvajanja (core/os_media.MediaCenter.seznam)
  {"tip": "samodejni", "ref": id, "vrsta": ...}    samodejni seznam (core/samodejni_seznami.py)
  {"tip": "yt", "ref": id, "racun": n}             seznam racuna YouTube (prebere se z omrezja)
Spotify (skrit Safeer DRM vodi svoj kontekst) in Twitch nista seznama za nadaljevanje.

»Najblizji po zvrsti« - samo iz podatkov, ki jih Safeer ze ima (brez oblaka in brez novih vprasanj omrezju):
  1. Oznake skladbe: njena zvrst (oznaka datoteke ali »zanri« vnosa kataloga oziroma streznika); ce je nima, zvrsti
     njenega izvajalca v uporabnikovi glasbi (zemljevid izvajalec -> zvrsti iz vseh znanih skladb). Samodejni seznam
     vrste »zanr« doda svojo zvrst vsaki svoji skladbi. Vsaka skladba tehta 1, razdeljeno med njene zvrsti.
  2. Profil seznama = vsota oznak njegovih skladb.
  3. Podobnost = kosinusna podobnost profilov (0 .. 1). Pri enaki podobnosti odloci vec skupnih izvajalcev (Jaccard),
     nato seznam, ki ga je uporabnik nazadnje poslusal (zgodovina), nato stalen vrstni red kandidatov.
  4. Kandidati: uporabnikovi seznami in samodejni seznami (ce jih ni skril), razen izteklega in seznamov, ki so bili v
     tej verigi samodejnega nadaljevanja ze predvajani (ce so bili vsi, se veriga zacne znova). Iz kandidata izpadejo
     skladbe, ki so bile v izteklem seznamu (izvajalec + naslov) - nic dvakrat zapored; kandidat brez skladb izpade.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional

from core.viri_sink import brez_prijave

DATOTEKA = "nazadnje_seznam.json"
TIPI = ("seznam", "samodejni", "yt")
VRSTE_SAMODEJNIH = ("najvec", "nazadnje", "dolgo", "zanr", "izvajalec", "odkrij")
NAJVEC_ZGODOVINE = 20
NAJVEC_ZIVIH = 300
NAJVEC_SKLADB = 500
#: Mesto v skladbi se zapise najvec enkrat na 15 s (ob vsaki novi skladbi takoj): izpad elektrike izgubi najvec 15 s.
PISI_NAJVEC_NA_S = 15.0

_LOCILA_ZVRSTI = re.compile(r"\s*[,;/|]\s*")
_LOCILA_IZVAJALCA = re.compile(r"\s*(?:,|;|&| feat\.? | ft\.? | x )\s*", re.I)


def _celo(v: Any) -> int:
    try:
        return max(0, int(v or 0))
    except (TypeError, ValueError):
        return 0


def _niz(v: Any, meja: int = 300) -> str:
    return str(v or "").replace("\n", " ").strip()[:meja]


def _slika(v: Any) -> str:
    s = _niz(v, 2048)
    return brez_prijave(s) if s.startswith(("https://", "http://", "file://")) else ""


def kljuc_imena(niz: Any) -> str:
    return " ".join(str(niz or "").casefold().split())


def zvrsti(niz: Any) -> list:
    """»Rock, Pop / Indie« -> ["rock", "pop", "indie"] (brez dvojnikov, najvec 40 znakov na zvrst)."""
    if isinstance(niz, (list, tuple)):
        niz = ",".join(str(x) for x in niz if isinstance(x, str))
    izid = []
    for z in _LOCILA_ZVRSTI.split(str(niz or "")):
        k = kljuc_imena(z)
        if k and len(k) <= 40 and k not in izid:
            izid.append(k)
    return izid


def glavni_izvajalec(niz: Any) -> str:
    deli = [d for d in _LOCILA_IZVAJALCA.split(str(niz or "")) if d.strip()]
    return kljuc_imena(deli[0]) if deli else ""


def kljuc_skladbe(s: dict) -> str:
    """Ista skladba na dveh seznamih (izvajalec + naslov): po izteklem seznamu je naslednji ne zaigra znova."""
    return glavni_izvajalec(s.get("izvajalec")) + "|" + kljuc_imena(s.get("naslov"))


def zemljevid_izvajalcev(skladbe: Iterable[dict]) -> dict:
    """izvajalec -> Counter zvrsti iz vseh uporabnikovih skladb, ki zvrst imajo."""
    izid: dict = {}
    for s in skladbe:
        if not isinstance(s, dict):
            continue
        a, z = glavni_izvajalec(s.get("izvajalec")), zvrsti(s.get("zanr"))
        if a and z:
            stevec = izid.setdefault(a, Counter())
            for g in z:
                stevec[g] += 1.0 / len(z)
    return izid


def oznake(skladba: dict, izvajalci: dict) -> dict:
    z = zvrsti(skladba.get("zanr"))
    if z:
        return {g: 1.0 / len(z) for g in z}
    stevec = izvajalci.get(glavni_izvajalec(skladba.get("izvajalec")))
    vsota = sum(stevec.values()) if stevec else 0
    return {g: n / vsota for g, n in stevec.items()} if vsota else {}


def profil(skladbe: list, izvajalci: dict, zvrst_seznama: str = "") -> dict:
    p: Counter = Counter()
    for s in skladbe:
        for g, w in oznake(s, izvajalci).items():
            p[g] += w
    for g in zvrsti(zvrst_seznama):
        p[g] += float(len(skladbe))
    return dict(p)


def podobnost(a: dict, b: dict) -> float:
    skalar = sum(w * b.get(g, 0.0) for g, w in a.items())
    na, nb = math.sqrt(sum(w * w for w in a.values())), math.sqrt(sum(w * w for w in b.values()))
    return skalar / (na * nb) if na and nb else 0.0


def _izvajalci(skladbe: list) -> set:
    return {a for a in (glavni_izvajalec(s.get("izvajalec")) for s in skladbe) if a}


def izberi(izteklo: dict, kandidati: list, izvajalci: dict, zgodovina: Iterable[str] = (),
           izkljuci: Iterable[str] = ()) -> Optional[dict]:
    """Najblizji seznam po zvrsti (glej opis modula).

    izteklo: {"kljuc", "skladbe", "zanr"}; kandidat: {"kljuc", "izvor", "skladbe", "zanr"}. Vrne kopijo kandidata s
    »skladbe« brez ze slisanih in »podobnost«; None, ce ni nobenega."""
    slisane = {kljuc_skladbe(s) for s in izteklo.get("skladbe") or []}
    p0 = profil(izteklo.get("skladbe") or [], izvajalci, izteklo.get("zanr") or "")
    a0 = _izvajalci(izteklo.get("skladbe") or [])
    zgodovina = list(zgodovina)
    mesto_v_zgodovini = {k: i for i, k in reversed(list(enumerate(zgodovina)))}
    izkljuci = set(izkljuci) | {izteklo.get("kljuc")}
    najboljsi = None
    for i, k in enumerate(kandidati):
        if k.get("kljuc") in izkljuci:
            continue
        ostale = [s for s in k.get("skladbe") or [] if kljuc_skladbe(s) not in slisane]
        if not ostale:
            continue
        cos = podobnost(p0, profil(k["skladbe"], izvajalci, k.get("zanr") or ""))
        ak = _izvajalci(k["skladbe"])
        jac = len(a0 & ak) / len(a0 | ak) if (a0 | ak) else 0.0
        ocena = (round(cos, 6), round(jac, 6), -mesto_v_zgodovini.get(k["kljuc"], len(zgodovina) + 1), -i)
        if najboljsi is None or ocena > najboljsi[0]:
            najboljsi = (ocena, dict(k, skladbe=ostale, podobnost=round(cos, 4)))
    return najboljsi[1] if najboljsi else None


def cisti_izvor(izvor: Any) -> Optional[dict]:
    if not isinstance(izvor, dict):
        return None
    tip, ref = _niz(izvor.get("tip"), 20), _niz(izvor.get("ref"), 400)
    if tip not in TIPI or not ref:
        return None
    d = {"tip": tip, "ref": ref, "ime": _niz(izvor.get("ime"), 120)}
    if tip == "yt":
        d["racun"] = min(_celo(izvor.get("racun")), 50)
    if tip == "samodejni" and izvor.get("vrsta") in VRSTE_SAMODEJNIH:
        d["vrsta"] = izvor["vrsta"]
    slike = []
    for s in (izvor.get("slike") or [])[:8] if isinstance(izvor.get("slike"), list) else []:
        s = _slika(s)
        if s and s not in slike:
            slike.append(s)
    d["slike"] = slike[:4]
    return d


def kljuc_izvora(izvor: dict) -> str:
    if izvor["tip"] == "yt":
        return "yt:%d:%s" % (izvor.get("racun", 0), izvor["ref"])
    return "%s:%s" % (izvor["tip"], izvor["ref"])


def _cista_skladba(s: Any) -> dict:
    s = s if isinstance(s, dict) else {}
    return {"id": _niz(s.get("id"), 400), "naslov": _niz(s.get("naslov"), 200), "izvajalec": _niz(s.get("izvajalec"), 200),
            "slika": _slika(s.get("slika"))}


class NazadnjePredvajano:
    """Shramba zadnjega seznama, zgodovine seznamov in znanih prenosov v zivo (varno za vec niti)."""

    def __init__(self, mapa: str | Path) -> None:
        self.pot = Path(mapa) / DATOTEKA
        self._zaklep = threading.RLock()
        self._podatki: Optional[dict] = None
        self._zapisano = 0.0

    def _beri(self) -> dict:
        if self._podatki is None:
            try:
                d = json.loads(self.pot.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                d = {}
            d = d if isinstance(d, dict) else {}
            zadnji = d.get("zadnji")
            if not (isinstance(zadnji, dict) and cisti_izvor(zadnji.get("izvor"))):
                zadnji = None
            self._podatki = {"zadnji": zadnji,
                             "zgodovina": [str(k) for k in d.get("zgodovina") or [] if isinstance(k, str)][:NAJVEC_ZGODOVINE],
                             "zivi": [str(k) for k in d.get("zivi") or [] if isinstance(k, str)][:NAJVEC_ZIVIH]}
        return self._podatki

    def _pisi(self) -> None:
        zacasna = self.pot.with_name(".%s.%d.%d.tmp" % (DATOTEKA, os.getpid(), threading.get_ident()))
        try:
            self.pot.parent.mkdir(parents=True, exist_ok=True)
            zacasna.write_text(json.dumps(self._podatki, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(zacasna, self.pot)
            self._zapisano = time.monotonic()
        except OSError:
            try:
                zacasna.unlink()
            except OSError:
                pass

    def zadnji(self) -> Optional[dict]:
        with self._zaklep:
            z = self._beri()["zadnji"]
            return json.loads(json.dumps(z)) if z else None

    def zgodovina(self) -> list:
        with self._zaklep:
            return list(self._beri()["zgodovina"])

    def zivi(self) -> set:
        with self._zaklep:
            return set(self._beri()["zivi"])

    def zapomni(self, izvor: Any, mesto: Any, skladba: Any, skupaj: Any, red: Any = None, samodejno: bool = False) -> bool:
        """Skladba seznama je zacela igrati. samodejno: seznam je izbral Safeer (veriga samodejnega nadaljevanja)."""
        izvor = cisti_izvor(izvor)
        if izvor is None:
            return False
        skupaj = min(_celo(skupaj), NAJVEC_SKLADB)
        k = kljuc_izvora(izvor)
        red = [x for x in red if isinstance(x, int) and 0 <= x < skupaj][:NAJVEC_SKLADB] if isinstance(red, list) else []
        with self._zaklep:
            d = self._beri()
            prej = d["zadnji"]
            if prej and prej.get("kljuc") == k:
                veriga = list(prej.get("veriga") or [])
            elif prej and samodejno:
                veriga = (list(prej.get("veriga") or []) + [prej.get("kljuc")])[-NAJVEC_ZGODOVINE:]
            else:
                veriga = []
            d["zadnji"] = {"izvor": izvor, "kljuc": k, "mesto": min(_celo(mesto), max(0, skupaj - 1)), "skupaj": skupaj,
                           "skladba": _cista_skladba(skladba), "pozicija": 0, "cas": int(time.time()),
                           "red": red if len(red) == skupaj else [], "veriga": veriga}
            d["zgodovina"] = ([k] + [x for x in d["zgodovina"] if x != k])[:NAJVEC_ZGODOVINE]
            self._pisi()
            return True

    def pozicija(self, ident: str, sekunde: float) -> bool:
        """Mesto v skladbi, ki igra (domaci predvajalnik javlja na 5 s); zapis najvec na PISI_NAJVEC_NA_S."""
        with self._zaklep:
            z = self._beri()["zadnji"]
            if not z or not ident or (z.get("skladba") or {}).get("id") != ident:
                return False
            z["pozicija"] = _celo(sekunde)
            if time.monotonic() - self._zapisano >= PISI_NAJVEC_NA_S:
                self._pisi()
            return True

    def pozabi(self) -> None:
        """Seznama ni vec (izbrisan, prazen): na Domov ga ne kazemo (kar ne gre, ne prikazemo)."""
        with self._zaklep:
            d = self._beri()
            if d["zadnji"]:
                d["zgodovina"] = [x for x in d["zgodovina"] if x != d["zadnji"].get("kljuc")]
                d["zadnji"] = None
                self._pisi()

    def oznaci_zivo(self, ident: str) -> bool:
        ident = _niz(ident, 400)
        if not ident:
            return False
        with self._zaklep:
            d = self._beri()
            if ident in d["zivi"]:
                return True
            d["zivi"] = ([ident] + d["zivi"])[:NAJVEC_ZIVIH]
            self._pisi()
            return True
