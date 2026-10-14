"""Nastavitve predvajanja domacega predvajalnika (kot v Kodiju in VLC): zvocni posnetki, zamik zvoka in
podnapisov, izenacevalnik. Samo cisti izracuni in shramba - GStreamer in GTK sta v os_predvajalnik.py in safeer_os.py.

Pravila (lastnik, 14. 10. 2026):
- zamik zvoka in podnapisov velja samo za trenutni posnetek (naslednji zacne z 0, kot v VLC);
- izbrani jezik zvoka si zapomnimo in ga pri naslednjem videu izberemo sami, ce ga video ima;
- izenacevalnik (prednastavitev ali Po meri) ostane izbran tudi po ponovnem zagonu.
"""

from __future__ import annotations

import json
import os
from typing import Iterable, List, Optional

#: Korak tipk (J/K, G/H - kot v VLC) in gumbov v meniju, v milisekundah.
KORAK_TIPKA_MS = 50
KORAK_MENI_MS = 100
#: Meje: zvok +-10 s (kot Kodi), podnapisi +-60 s (napacna razlicica datoteke je lahko precej zamaknjena).
MEJA_ZVOK_MS = 10_000
MEJA_PODNAPISI_MS = 60_000

#: Sredisca pasov equalizer-10bands (GStreamer 1.24, izmerjeno: 30, 60, 120, 240, 480, 950 Hz, 1,9, 3,8, 7,5, 15 kHz).
PASOVI = ("30", "60", "120", "240", "480", "950", "1,9k", "3,8k", "7,5k", "15k")
#: Ojacitev pasu v dB; element dovoli -24..+12, za uporabnika je dovolj +-12.
NAJMANJ_DB, NAJVEC_DB = -12.0, 12.0

#: Prednastavitve v dB (po zgledu VLC, zmernejse - vrh +6 dB). Vrstni red je vrstni red v meniju.
PREDNASTAVITVE = {
    "ravno": (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    "bas": (6, 5, 4, 2, 0, 0, 0, 0, 0, 0),
    "glas": (-3, -2, -1, 1, 3, 4, 3, 1, 0, -1),
    "klasika": (0, 0, 0, 0, 0, 0, -3, -3, -3, -5),
    "rock": (4, 3, -2, -4, -1, 2, 4, 5, 5, 5),
    "elektronska": (5, 3, 0, -3, -3, 0, 5, 6, 6, 5),
}
PO_MERI = "po_meri"
IZBIRE_IZENACEVALNIKA = tuple(PREDNASTAVITVE) + (PO_MERI,)


# ------------------------------------------------------------------ zamik

def premakni_zamik(trenutni_ms: int, korak_ms: int, meja_ms: int) -> int:
    """Nov zamik v ms, omejen na +-meja. Vrednost ostane na mrezi koraka 50 ms (tipke in meni se ne razhajata)."""
    try:
        nov = int(trenutni_ms) + int(korak_ms)
    except (TypeError, ValueError):
        nov = 0
    nov = int(round(nov / KORAK_TIPKA_MS)) * KORAK_TIPKA_MS
    return max(-int(meja_ms), min(int(meja_ms), nov))


def besedilo_zamika(ms: int) -> str:
    """"+150 ms", "−1,25 s", "0 ms" - kratko za OSD in meni (pravi minus, vejica kot v slovenscini)."""
    ms = int(ms or 0)
    if ms == 0:
        return "0 ms"
    znak = "+" if ms > 0 else "−"
    a = abs(ms)
    if a < 1000:
        return "%s%d ms" % (znak, a)
    return "%s%s s" % (znak, ("%.2f" % (a / 1000)).rstrip("0").rstrip(".").replace(".", ","))


def av_offset_ns(zamik_zvoka_ms: int) -> int:
    """playbin av-offset: pozitivna vrednost zamakne sliko (zvok prej). Nas zamik zvoka pomeni, za koliko zvok zamudi
    (kot v VLC: K = +50 ms), zato obratni predznak - preverjeno na ts-offset v playsinku (GStreamer 1.24)."""
    return -int(zamik_zvoka_ms) * 1_000_000


def text_offset_ns(zamik_podnapisov_ms: int) -> int:
    """playbin text-offset: pozitivno = podnapisi kasneje (kot H v VLC)."""
    return int(zamik_podnapisov_ms) * 1_000_000


# ------------------------------------------------------------------ zvocni posnetki

#: Opis kodeka iz oznake GStreamerja (audio-codec) -> kratko ime, kot ga pozna uporabnik. Vrstni red je pomemben
#: (E-AC-3 pred AC-3, TrueHD pred Dolby).
_KODEKI = (
    ("e-ac-3", "E-AC3"), ("eac3", "E-AC3"), ("ac-3", "AC3"), ("ac3", "AC3"), ("a/52", "AC3"),
    ("truehd", "TrueHD"), ("dts", "DTS"), ("aac", "AAC"), ("opus", "Opus"), ("vorbis", "Vorbis"),
    ("flac", "FLAC"), ("layer 3", "MP3"), ("mp3", "MP3"), ("layer 2", "MP2"), ("pcm", "PCM"),
    ("alac", "ALAC"), ("wma", "WMA"),
)


def kratek_kodek(opis: str) -> str:
    o = str(opis or "").lower()
    if not o:
        return ""
    for del_, ime in _KODEKI:
        if del_ in o:
            return ime
    return str(opis).strip()[:16]


def opis_kanalov(kanali: int) -> str:
    try:
        n = int(kanali or 0)
    except (TypeError, ValueError):
        return ""
    return {0: "", 1: "Mono", 2: "Stereo", 3: "2.1", 6: "5.1", 7: "6.1", 8: "7.1"}.get(n, "%d ch" % n if n > 0 else "")


def ime_zvocnega_toka(stevilka: int, jezik: str = "", kodek: str = "", kanali: int = 0, naslov: str = "",
                      jezik_vmesnika: str = "sl", privzeto: str = "{n}") -> str:
    """"Slovenščina · AC3 5.1", "English · Komentar · AAC Stereo"; brez podatkov "Zvok 2" (privzeto z {n})."""
    from core import podnapisi as _pn
    koda = _pn.iso1(jezik)
    ime = _pn.ime_jezika(koda, jezik_vmesnika) if koda else ""
    tehnika = " ".join(x for x in (kratek_kodek(kodek), opis_kanalov(kanali)) if x)
    naslov = str(naslov or "").strip()[:60]
    if naslov and ime and naslov.lower() == ime.lower():
        naslov = ""
    deli = [x for x in (ime, naslov, tehnika) if x]
    return " · ".join(deli) if deli else str(privzeto).replace("{n}", str(int(stevilka) + 1))


def izberi_po_jeziku(jeziki_tokov: Iterable[str], zeleni: Iterable[str]) -> int:
    """Indeks prvega toka v najbolj zelenem jeziku; -1, ce nobenega (ostane privzeti tok datoteke)."""
    from core import podnapisi as _pn
    toki = [_pn.iso1(j) for j in jeziki_tokov]
    for z in zeleni:
        z = _pn.iso1(z)
        if z and z in toki:
            return toki.index(z)
    return -1


# ------------------------------------------------------------------ izenacevalnik

def _omeji(db) -> float:
    try:
        v = float(db)
    except (TypeError, ValueError):
        return 0.0
    if v != v:          # NaN
        return 0.0
    return max(NAJMANJ_DB, min(NAJVEC_DB, v))


def ojacitve(izbira: str, po_meri: Optional[Iterable] = None) -> List[float]:
    """Deset ojacitev v dB za izbiro; neznana izbira je Ravno, Po meri vzame uporabnikove vrednosti."""
    if izbira == PO_MERI:
        vrednosti = list(po_meri or ())[:10]
        return [_omeji(v) for v in vrednosti] + [0.0] * (10 - len(vrednosti))
    return [float(v) for v in PREDNASTAVITVE.get(izbira, PREDNASTAVITVE["ravno"])]


def predojacitev(ojacitve_db: Iterable[float]) -> float:
    """Glasnost (linearno) pred izhodom: najvecji dvig odstejemo, da glasba ne poci (kot predojacitev v VLC)."""
    vrh = max([0.0] + [float(x) for x in ojacitve_db])
    return 10 ** (-vrh / 20)


# ------------------------------------------------------------------ shramba

def _pot() -> str:
    return os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "safeer-os", "predvajalnik.json")


def privzete() -> dict:
    return {"zvok_jezik": "", "izenacevalnik": "ravno", "po_meri": [0.0] * 10}


def nalozi(pot: str = "") -> dict:
    n = privzete()
    try:
        with open(pot or _pot(), encoding="utf-8") as d:
            podatki = json.load(d)
    except (OSError, ValueError):
        return n
    if not isinstance(podatki, dict):
        return n
    from core import podnapisi as _pn
    n["zvok_jezik"] = _pn.iso1(podatki.get("zvok_jezik"))
    if podatki.get("izenacevalnik") in IZBIRE_IZENACEVALNIKA:
        n["izenacevalnik"] = podatki["izenacevalnik"]
    if isinstance(podatki.get("po_meri"), list):
        n["po_meri"] = ojacitve(PO_MERI, podatki["po_meri"])
    return n


def shrani(n: dict, pot: str = "") -> None:
    pot = pot or _pot()
    cisto = {"zvok_jezik": str(n.get("zvok_jezik") or "")[:3],
             "izenacevalnik": n.get("izenacevalnik") if n.get("izenacevalnik") in IZBIRE_IZENACEVALNIKA else "ravno",
             "po_meri": ojacitve(PO_MERI, n.get("po_meri"))}
    try:
        os.makedirs(os.path.dirname(pot), exist_ok=True)
        with open(pot + ".tmp", "w", encoding="utf-8") as d:
            json.dump(cisto, d)
        os.replace(pot + ".tmp", pot)
    except OSError:
        pass
