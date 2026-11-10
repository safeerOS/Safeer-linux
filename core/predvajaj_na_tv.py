"""»Predvajaj na TV« - posiljatelj na namizju (lastnik 10. 11. 2026: »da lahko iz telefona in racunalnika izberem, kateri
film zelim na TV gledati«).

Namizje poslje samo IDENTITETO vsebine (vrsta, id IMDb, sezona/epizoda, naslov, polozaj) z ukazom Linka ZMOZNOST po
obstojecem kanalu (Safeer Control, metoda Ukaz -> control.command); TV jo preveri sama (PredvajajNaTvPravila.kt) in
predvaja z LASTNIMI viri in racuni. O dostopu odloca TV (ozji krog). Ponudimo samo napravam v ozjem krogu, ki zmoznost
oglasajo. Odgovor TV je nezaupanja vreden: iz njega vzamemo samo ok in kratko kodo razloga (crke in podcrtaj) - nobenega
besedila, naslova ali ukaza; ime naprave je iz nasega seznama, ne iz odgovora."""
from __future__ import annotations

import json
import re
from typing import Callable, List, Optional

#: Ime zmoznosti in ukaza v Linku. TV ga se ne oglasa (10. 11. 2026) - stran TV ga doda (porocilo naloge).
ZMOZNOST = "media.play"
#: Polja sporocila (PredvajajNaTvPravila.sporocilo): drugih ne posljemo.
POLJA = ("vrsta", "id", "sezona", "epizoda", "naslov", "polozajMs")
VRSTE = ("film", "epizoda", "kanal")
#: Najdaljse polje: naslov do 200 znakov po pravilih TV, ostalo krajse; z rezervo, a brez neomejenega vnosa s strani.
NAJVEC_POLJA = 220
_KODA = re.compile(r"[A-Za-z_]{1,40}")


def naprave(seznam: Optional[dict]) -> List[dict]:
    """Naprave Linka (Control »Seznam«), ki jim smemo ponuditi »Predvajaj na«: ne ta naprava, ozji krog, zmoznost."""
    izid = []
    for n in (seznam or {}).get("naprave") or []:
        if not isinstance(n, dict) or not n.get("id") or n.get("ta") or not n.get("ozji"):
            continue
        if ZMOZNOST not in (n.get("zmoznosti") or []):
            continue
        izid.append({"id": str(n["id"]), "ime": str(n.get("ime") or n["id"])[:80]})
    return izid


def polja_sporocila(polja: object) -> Optional[dict]:
    """Samo dovoljena polja kot nizi omejene dolzine; None, ce sporocilo ni smiselno (vrsta ali id manjka)."""
    if not isinstance(polja, dict):
        return None
    izid = {}
    for k in POLJA:
        v = polja.get(k)
        if v is None:
            continue
        if not isinstance(v, str) or len(v) > NAJVEC_POLJA:
            return None
        izid[k] = v
    if izid.get("vrsta") not in VRSTE or not izid.get("id"):
        return None
    return izid


def koda_razloga(odgovor: dict) -> str:
    """Kratka koda iz odgovora TV (data.razlog ali koda Linka); vse drugo zavrzemo."""
    data = odgovor.get("data") if isinstance(odgovor.get("data"), dict) else {}
    for k in (data.get("razlog"), odgovor.get("koda")):
        if isinstance(k, str) and _KODA.fullmatch(k):
            return k
    return ""


def poslji(seznam: Callable[[], dict], ukaz: Callable[[str, str, str], dict], id_naprave: str, polja: object) -> dict:
    """Poslje ukaz ZMOZNOST napravi [id_naprave]; vrne {"ok", "razlog", "ime"}. Naprava mora biti v seznamu naprave()
    TUDI ob posiljanju (stran ne more poslati napravi zunaj kroga ali brez zmoznosti)."""
    cilj = next((n for n in naprave(seznam()) if n["id"] == str(id_naprave or "")), None)
    if cilj is None:
        return {"ok": False, "razlog": "ni_naprave", "ime": ""}
    p = polja_sporocila(polja)
    if p is None:
        return {"ok": False, "razlog": "napacna_zahteva", "ime": cilj["ime"]}
    try:
        odgovor = ukaz(cilj["id"], ZMOZNOST, json.dumps(p, ensure_ascii=False))
    except Exception:  # noqa: BLE001 - Control ali Link ne odgovori: razlog brez podrobnosti
        odgovor = {"ok": False, "koda": "napaka"}
    if not isinstance(odgovor, dict):
        odgovor = {"ok": False}
    ok = odgovor.get("ok") is True
    return {"ok": ok, "razlog": "" if ok else koda_razloga(odgovor), "ime": cilj["ime"]}
