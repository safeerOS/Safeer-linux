"""Samodejni seznami predvajanja Medijskega centra (lastnik, 14. 10. 2026): iz uporabnikove prave glasbe, krajevno,
brez oblaka in brez racuna.

Cista pravila (brez okna, omrezja in diska): vhod so skladbe, ki jih je jedro ze zbralo (krajevna knjiznica,
skladbe iz osebnih streznikov - Navidrome, Funkwhale, Jellyfin ... - in skladbe iz kataloga, ki jih je uporabnik
predvajal), izhod so seznami. Seznam z manj kot NAJMANJ skladbami se ne pokaze. Vrstni red je vedno enak za enake
podatke (brez nakljucnega mesanja ob vsakem izrisu); mesa samo gumb »Premesaj« v predvajalniku.

Skladba (slovar):
  id        stalen kljuc skladbe ("pot:<pot>" za datoteko, sicer id vnosa kataloga)
  naslov, izvajalec, zanr (lahko vec, locenih z vejico, podpicjem ali posevnico), slika, url, pot
  dodano    kdaj je skladba prisla v knjiznico (unix s, 0 = ni znano)
  zadnjic   kdaj je bila nazadnje predvajana (unix s, 0 = nikoli)
  n         kolikokrat je bila predvajana
  sekund    dolzina (0 = ni znana)

Seznam: {"id", "vrsta", "ime", "stevilo", "slike" (do 4 razlicne prave naslovnice), "skladbe" (najvec NAJVEC_SKLADB)}.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

#: Seznam z manj skladbami se ne pokaze (lastnik: »samo, ce ima vsaj ~8 skladb«).
NAJMANJ = 8
#: Najvec skladb na seznamu (vrsta predvajanja ostane obvladljiva, kartica hitra).
NAJVEC_SKLADB = 50
#: »Dolgo nisi poslusal«: predvajano prej, ne pa v zadnjih 30 dneh.
DOLGO_DNI = 30
#: Koliko seznamov po zvrsti in po izvajalcu (najvecji prvi).
NAJVEC_ZVRSTI = 3
NAJVEC_IZVAJALCEV = 3
#: Seznami se racunajo v ozadju najvec enkrat na 10 minut (kot predgrevanje kataloga).
OSVEZI_S = 600

_LOCILA_ZVRSTI = re.compile(r"\s*[,;/|]\s*")
_LOCILA_IZVAJALCA = re.compile(r"\s*(?:,|;|&| feat\.? | ft\.? | x )\s*", re.I)


def _celo(v) -> int:
    try:
        return max(0, int(v or 0))
    except (TypeError, ValueError):
        return 0


def _niz(v, meja: int = 300) -> str:
    return str(v or "").replace("\n", " ").strip()[:meja]


def ocisti(skladba: dict) -> dict:
    """Samo znana polja, omejene dolzine; slika samo s spletnim ali krajevnim naslovom."""
    slika = _niz(skladba.get("slika"), 2048)
    if not slika.startswith(("https://", "http://", "file://")):
        slika = ""
    return {"id": _niz(skladba.get("id"), 2100), "naslov": _niz(skladba.get("naslov")), "izvajalec": _niz(skladba.get("izvajalec")),
            "zanr": _niz(skladba.get("zanr")), "slika": slika, "url": _niz(skladba.get("url"), 2048),
            "pot": _niz(skladba.get("pot"), 4096), "dodano": _celo(skladba.get("dodano")), "zadnjic": _celo(skladba.get("zadnjic")),
            "n": _celo(skladba.get("n")), "sekund": _celo(skladba.get("sekund"))}


def izvajalec_iz_imena(ime: str) -> str:
    """»Izvajalec - Naslov.mp3« -> »Izvajalec« (enako kot mediaSkladbaImena v os.js); sicer prazno."""
    cisto = re.sub(r"\.[a-z0-9]{2,4}$", "", str(ime or ""), flags=re.I).replace("_", " ").strip()
    m = re.match(r"^(?:\d{1,3}[\s.\-]+)?(.{1,80}?)\s+[-–—]\s+(.+)$", cisto)
    return m.group(1).strip() if m else ""


def _kljuc(niz: str) -> str:
    return " ".join(str(niz or "").casefold().split())


def _zvrsti(skladba: dict) -> list:
    videne, izid = set(), []
    for z in _LOCILA_ZVRSTI.split(skladba.get("zanr") or ""):
        k = _kljuc(z)
        if k and k not in videne and len(k) <= 40:
            videne.add(k)
            izid.append(z.strip())
    return izid


def _glavni_izvajalec(skladba: dict) -> str:
    deli = [d for d in _LOCILA_IZVAJALCA.split(skladba.get("izvajalec") or "") if d.strip()]
    return deli[0].strip() if deli else ""


def _id_seznama(vrsta: str, ime: str = "") -> str:
    if not ime:
        return vrsta
    return vrsta + ":" + hashlib.sha1(_kljuc(ime).encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


def _po_naslovu(s: dict) -> tuple:
    return (_kljuc(s["izvajalec"]), _kljuc(s["naslov"]), s["id"])


def _seznam(vrsta: str, skladbe: list, ime: str = "") -> dict:
    slike, videne = [], set()
    for s in skladbe:
        if s["slika"] and s["slika"] not in videne:
            videne.add(s["slika"])
            slike.append(s["slika"])
            if len(slike) == 4:
                break
    return {"id": _id_seznama(vrsta, ime), "vrsta": vrsta, "ime": ime, "stevilo": min(len(skladbe), NAJVEC_SKLADB), "slike": slike,
            "skladbe": skladbe[:NAJVEC_SKLADB]}


def sestavi(skladbe: Iterable[dict], zdaj: float, najmanj: int = NAJMANJ) -> list:
    """Vsi samodejni seznami, ki imajo vsaj [najmanj] skladb, v stalnem vrstnem redu."""
    po_id: dict = {}
    for surova in skladbe:
        if not isinstance(surova, dict):
            continue
        s = ocisti(surova)
        if not s["id"] or not s["naslov"] or not (s["url"] or s["pot"]):
            continue
        prej = po_id.get(s["id"])
        if prej is None:
            po_id[s["id"]] = s
        else:     # ista skladba iz dveh virov (knjiznica in polica): ena, z vec podatki
            for k in ("n", "zadnjic", "dodano", "sekund"):
                prej[k] = max(prej[k], s[k])
            for k in ("izvajalec", "zanr", "slika", "url", "pot"):
                prej[k] = prej[k] or s[k]
    vse = sorted(po_id.values(), key=_po_naslovu)
    meja = int(zdaj) - DOLGO_DNI * 86400
    izid = []
    najvec = sorted((s for s in vse if s["n"] > 0), key=lambda s: (-s["n"], -s["zadnjic"]) + _po_naslovu(s))
    izid.append(_seznam("najvec", najvec))
    nazadnje = sorted((s for s in vse if s["dodano"] > 0), key=lambda s: (-s["dodano"],) + _po_naslovu(s))
    izid.append(_seznam("nazadnje", nazadnje))
    dolgo = sorted((s for s in vse if s["n"] > 0 and 0 < s["zadnjic"] < meja), key=lambda s: (-s["n"], s["zadnjic"]) + _po_naslovu(s))
    izid.append(_seznam("dolgo", dolgo))
    # Zvrsti in izvajalci: skupine z vsaj [najmanj] skladbami, najvecje prve (enako veliki po abecedi).
    zvrsti: dict = {}
    for s in vse:
        for z in _zvrsti(s):
            zvrsti.setdefault(_kljuc(z), (z, []))[1].append(s)
    vrsta_zvrsti = sorted((v for v in zvrsti.values() if len(v[1]) >= najmanj), key=lambda v: (-len(v[1]), _kljuc(v[0])))
    for ime, sk in vrsta_zvrsti[:NAJVEC_ZVRSTI]:
        izid.append(_seznam("zanr", sorted(sk, key=lambda s: (-s["n"],) + _po_naslovu(s)), ime))
    izvajalci: dict = {}
    for s in vse:
        a = _glavni_izvajalec(s)
        if a:
            izvajalci.setdefault(_kljuc(a), (a, []))[1].append(s)
    vrsta_izv = sorted((v for v in izvajalci.values() if len(v[1]) >= najmanj),
                       key=lambda v: (-sum(s["n"] for s in v[1]), -len(v[1]), _kljuc(v[0])))
    for ime, sk in vrsta_izv[:NAJVEC_IZVAJALCEV]:
        izid.append(_seznam("izvajalec", sorted(sk, key=lambda s: (-s["n"],) + _po_naslovu(s)), ime))
    odkrij = sorted((s for s in vse if s["n"] == 0 and s["zadnjic"] == 0), key=lambda s: (-s["dodano"],) + _po_naslovu(s))
    izid.append(_seznam("odkrij", odkrij))
    return [x for x in izid if x["stevilo"] >= najmanj]


def povzetek(seznami: list) -> list:
    """Za stran: brez skladb (kartica potrebuje ime, stevilo in naslovnice)."""
    return [{k: x[k] for k in ("id", "vrsta", "ime", "stevilo", "slike")} for x in seznami]
