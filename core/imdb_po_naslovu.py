"""Id IMDb filma po naslovu in letu (Cinemeta, javni katalog Stremio brez kljuca).

Lastnik 24. 11. 2026 na testnem PC: Filmi v nacinu »⚡ Usenet« so bili prazni s sporocilom »indeksator ne odgovarja«,
ceprav je kljuc indeksatorja veljal. Vzrok: dodatek »Best Torrents« (fun.rfnx.workers.dev) daje filme z id-ji
movie_best_torrents_<n> brez IMDb; indeksator Usenet isce po IMDb, zato preverba zahteve sploh ni poslala (ni_imdb).
Tu poiscemo IMDb po naslovu: samo enak naslov (po normalizaciji) in enako leto (+-1); brez znanega leta samo, ce je
zadetek z enakim naslovom en sam. Raje nic kot napacen film.
"""
from __future__ import annotations

import json
import re
import threading
import unicodedata
import urllib.parse
from typing import Callable, Dict, Optional

ISKANJE = "https://v3-cinemeta.strem.io/catalog/movie/top/search=%s.json"
ROK_S = 6.0
NAJVEC_V_PREDPOMNILNIKU = 2000

_LETO_V_POTI = re.compile(r"[_-]((?:19|20)\d{2})(?=[/_.-])")
_IMDB = re.compile(r"^tt\d{5,10}$")


def normaliziraj(naslov: str) -> str:
    """Primerjava naslovov: brez naglasov, locil in velikih crk; »&« = »and«."""
    t = unicodedata.normalize("NFKD", str(naslov or "")).encode("ascii", "ignore").decode("ascii").lower()
    t = t.replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", t))


def leto_vnosa(item: dict) -> Optional[int]:
    """Leto iz vnosa kataloga; ce ga ni (dodatek da »0«), iz poti plakata (npr. .../wicker_2026/large-cover.jpg)."""
    try:
        leto = int(str(item.get("leto") or "0")[:4])
    except ValueError:
        leto = 0
    if 1880 <= leto <= 2100:
        return leto
    m = _LETO_V_POTI.search(str(item.get("slika") or ""))
    return int(m.group(1)) if m else None


def _leto_meta(meta: dict) -> Optional[int]:
    m = re.match(r"\s*(\d{4})", str(meta.get("releaseInfo") or meta.get("year") or ""))
    return int(m.group(1)) if m else None


def izberi(metas: list, naslov: str, leto: Optional[int]) -> Optional[str]:
    """Cista izbira iz odgovora Cinemete: id tt... ali None, ce zadetek ni zanesljiv."""
    cilj = normaliziraj(naslov)
    if not cilj:
        return None
    enaki = [m for m in metas if isinstance(m, dict) and _IMDB.match(str(m.get("id") or ""))
             and normaliziraj(m.get("name") or "") == cilj]
    if leto is not None:
        po_letu = [m for m in enaki if _leto_meta(m) is not None and abs(_leto_meta(m) - leto) <= 1]
        tocno = [m for m in po_letu if _leto_meta(m) == leto]
        izbor = tocno or po_letu
        return str(izbor[0]["id"]) if len(izbor) == 1 else None
    return str(enaki[0]["id"]) if len(enaki) == 1 else None


class Iskalnik:
    """Predpomnjeno iskanje (tudi »ni zadetka«), varno za vec niti. [zahteva](url, rok) vrne telo odgovora (bytes)."""

    def __init__(self, zahteva: Callable[[str, float], bytes]) -> None:
        self._zahteva = zahteva
        self._predpomnilnik: Dict[tuple, Optional[str]] = {}
        self._zaklep = threading.Lock()

    def poisci(self, naslov: str, leto: Optional[int]) -> Optional[str]:
        kljuc = (normaliziraj(naslov), leto)
        if not kljuc[0]:
            return None
        with self._zaklep:
            if kljuc in self._predpomnilnik:
                return self._predpomnilnik[kljuc]
        try:
            telo = self._zahteva(ISKANJE % urllib.parse.quote(str(naslov).strip(), safe=""), ROK_S)
            metas = json.loads(telo).get("metas") or []
        except Exception:  # noqa: BLE001 - mreza ali napacen odgovor: brez zadetka, brez zapisa (poskusimo kasneje)
            return None
        rezultat = izberi(metas, naslov, leto)
        with self._zaklep:
            if len(self._predpomnilnik) >= NAJVEC_V_PREDPOMNILNIKU:
                self._predpomnilnik.clear()
            self._predpomnilnik[kljuc] = rezultat
        return rezultat

    def za_vnos(self, item: dict) -> Optional[str]:
        """IMDb filma iz vnosa: ze znan imdb_id ali iskanje po naslovu in letu."""
        znan = str(item.get("imdb_id") or "")
        if _IMDB.match(znan):
            return znan
        return self.poisci(str(item.get("naslov") or item.get("name") or ""), leto_vnosa(item))
