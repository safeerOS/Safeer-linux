"""Izbira uradnega posnetka skladbe med zadetki iskanja YouTube.

Enako kot v Safeer OS (os/UradniPosnetek.kt, iste vrednosti in isti preizkusni primeri). Ideja iz projekta Musike
(licenca MIT, avtor Ernani1234): ocenjevanje zadetkov po izvajalcu, naslovu, trajanju in rdecih zastavicah;
napisano na novo, brez prevzete kode.

Nacelo: raje "ni posnetka" kot napacen posnetek (priredba, koncert, obozevalski nalog), zato mora biti nalagalec
izvajalcev lastni kanal (tudi "<Izvajalec>VEVO", "<Izvajalec> Official", "<Izvajalec> - Topic").
"""
from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple, Optional

_NI_POSNETEK = re.compile(
    r"\b(cover|karaoke|nightcore|8d|slowed|reverb|sped up|lyrics?|besedilo|tutorial|reaction|live|koncert|remix|"
    r"mashup|parody|parodija|instrumental|version|verzija|razlicica)\b")
_URADNI_VIDEO = re.compile(r"\b(official (music )?video|music video|videospot|uradni (video|videospot|posnetek))\b")
_NEVTRALEN_DODATEK = re.compile(r"official|uradni|video|audio|visualizer|visualiser|feat|ft|with|hd|4k|remaster")
_ZVOCNI = re.compile(r"\baudio\b")
_V_OKLEPAJIH = re.compile(r"\((.*?)\)|\[(.*?)\]")


class Zadetek(NamedTuple):
    id: str
    naslov: str
    kanal: str
    sekund: int


def ravno(s: str) -> str:
    """Male crke brez stresic, samo crke in stevke, en presledek."""
    d = "".join(c for c in unicodedata.normalize("NFD", s or "") if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", d.lower()).strip()


def golo(s: str) -> str:
    """Kot ravno, a brez oklepajev ("Trevo (Tu) (feat. X)" -> "trevo")."""
    return ravno(_V_OKLEPAJIH.sub(" ", s or ""))


def _strnjeno(s: str) -> str:
    return ravno(s).replace(" ", "")


def je_kanal_izvajalca(kanal: str, izvajalec: str) -> bool:
    iskan = _strnjeno(izvajalec)
    if not iskan:
        return False
    dovoljeni = {iskan, iskan + "vevo", iskan + "oficial", iskan + "official", iskan + "tv", iskan + "music",
                 iskan + "topic"}
    return any(_strnjeno(k) in dovoljeni for k in (kanal or "").split(","))


def ocena(z: Zadetek, naslov: str, izvajalec: str, sekund: int) -> Optional[int]:
    glavni = (izvajalec or "").split(",")[0].strip()
    if not je_kanal_izvajalca(z.kanal, glavni):
        return None
    iskan = golo(naslov)
    gol = golo(z.naslov)
    if not iskan or iskan not in gol:
        return None
    vse = ravno(z.naslov)
    rdece = bool(_NI_POSNETEK.search(ravno(naslov)))
    o = 0
    if gol.replace(golo(glavni), "").strip() == iskan:
        o += 2
    if sekund > 0 and z.sekund > 0:
        razlika = abs(z.sekund - sekund)
        o += 3 if razlika <= 10 else 1 if razlika <= 30 else -2 if razlika > 90 else 0
    # Koncert, priredba ali remix je drug posnetek: ce skladba sama tega ni, zadetek ne pride v postev.
    if not rdece and _NI_POSNETEK.search(vse):
        return None
    if _URADNI_VIDEO.search(vse):
        o += 3
    if _ZVOCNI.search(vse):
        o -= 1
    for m in _V_OKLEPAJIH.finditer(z.naslov):
        d = ravno(m.group(0))
        if not _NEVTRALEN_DODATEK.search(d) and d not in ravno(naslov):
            o -= 2
    return o


def izberi(zadetki: list, naslov: str, izvajalec: str, sekund: int) -> str:
    """Id najboljsega zadetka (med prvimi 10) ali ""; pri enakem izidu ostane prvi zadetek."""
    najboljsi: Optional[tuple] = None
    for z in list(zadetki)[:10]:
        o = ocena(z, naslov, izvajalec, sekund)
        if o is None:
            continue
        if najboljsi is None or o > najboljsi[1]:
            najboljsi = (z, o)
    return najboljsi[0].id if najboljsi else ""
