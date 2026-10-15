"""Predpomnilnik priponk na disku: prenesen del, PDF iz LibreOffice in slicica - drugo odprtje brez omrezja in brez
ponovne pretvorbe (lastnik, 15. 10. 2026: »smiselen predpomnilnik v Sporocilih«).

Mesto: $XDG_CACHE_HOME/safeer-os/priloge (obicajno ~/.cache; mape 0700, datoteke 0600). Vnos je ena priponka:
  priloge/<kanal>/<mapa>/<UIDVALIDITY>/<UID + del>/
s kljucem (kanal_id, mapa, UIDVALIDITY, UID, del) - imena so zgoscena (nic osebnega v potih, nic ne uide iz mape).
* Meja velikosti (privzeto 500 MB): najdlje neuporabljeni vnosi gredo prvi (LRU po casu zadnje uporabe = mtime).
* Odstranjen kanal: izbrise se vse njegovo. Nova UIDVALIDITY mape: stari vnosi te mape ne veljajo vec (UID-ji so
  drugi) in se izbrisejo.
* Kar je uporabnik prenesel v Prejemi, se ne hrani se enkrat: vnos si zapomni pot v Prejemih (prejeto.json) in
  predogled bere od tam, dokler je datoteka tam in ima isto velikost.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from typing import Optional

NAJVEC = 500 * 1024 * 1024
_PREJETO = "prejeto.json"


def koren() -> str:
    pot = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"),
                       "safeer-os", "priloge")
    _mapa(pot)
    return pot


def _mapa(pot: str) -> str:
    os.makedirs(pot, mode=0o700, exist_ok=True)
    try:
        os.chmod(pot, 0o700)
    except OSError:
        pass
    return pot


def _h(*deli) -> str:
    return hashlib.sha256("\0".join(str(d) for d in deli).encode("utf-8")).hexdigest()[:20]


def _uidv(uidvalidity) -> str:
    v = re.sub(r"\D", "", str(uidvalidity or ""))[:20]
    return v or "0"


def mapa_vnosa(kanal_id: str, mapa: str, uidvalidity, uid: str, del_: str) -> str:
    """Mapa vnosa za kljuc (kanal_id, mapa, UIDVALIDITY, UID, del); ustvari jo z 0700."""
    k = koren()
    pot = k
    for d in (_h(kanal_id), _h(mapa), _uidv(uidvalidity), _h(uid, del_)):
        pot = _mapa(os.path.join(pot, d))
    return pot


def uporabi(pot: str) -> None:
    """Zabelezi uporabo (LRU): cas datoteke in njene mape vnosa."""
    zdaj = time.time()
    for p in (pot, os.path.dirname(pot)):
        try:
            os.utime(p, (zdaj, zdaj))
        except OSError:
            pass


def zapisi_prejeto(vnos: str, pot: str) -> None:
    """Datoteka je zdaj v Prejemih: kopija v predpomnilniku ni vec potrebna."""
    try:
        velikost = os.path.getsize(pot)
    except OSError:
        return
    cilj = os.path.join(vnos, _PREJETO)
    with open(cilj + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"pot": os.path.abspath(pot), "velikost": velikost}, f)
    os.chmod(cilj + ".tmp", 0o600)
    os.replace(cilj + ".tmp", cilj)


def prejeto(vnos: str) -> str:
    """Pot v Prejemih, ce je datoteka se tam z isto velikostjo; sicer ""."""
    try:
        with open(os.path.join(vnos, _PREJETO), encoding="utf-8") as f:
            z = json.load(f)
        pot = str(z.get("pot") or "")
        if pot and os.path.isfile(pot) and os.path.getsize(pot) == int(z.get("velikost") or -1):
            return pot
    except (OSError, ValueError, TypeError):
        pass
    return ""


def _vnosi(k: str):
    """(zadnja uporaba, velikost, mapa vnosa) za vse vnose (globina 4 pod korenom)."""
    izid = []
    for kanal in _podmape(k):
        for mapa in _podmape(kanal):
            for uidv in _podmape(mapa):
                for vnos in _podmape(uidv):
                    cas, velikost = 0.0, 0
                    for ime in os.listdir(vnos):
                        try:
                            st = os.lstat(os.path.join(vnos, ime))
                        except OSError:
                            continue
                        cas, velikost = max(cas, st.st_mtime), velikost + st.st_size
                    izid.append((cas, velikost, vnos))
    return izid


def _podmape(pot: str):
    try:
        return [os.path.join(pot, d) for d in os.listdir(pot) if os.path.isdir(os.path.join(pot, d))
                and not os.path.islink(os.path.join(pot, d))]
    except OSError:
        return []


def pocisti(najvec: int = NAJVEC) -> int:
    """LRU: dokler je vse skupaj vec kot `najvec`, gre najdlje neuporabljen vnos. Vrne izbrisanih vnosov."""
    vnosi = sorted(_vnosi(koren()))
    skupaj = sum(v[1] for v in vnosi)
    izbrisanih = 0
    for _cas, velikost, vnos in vnosi:
        if skupaj <= najvec:
            break
        shutil.rmtree(vnos, ignore_errors=True)
        skupaj -= velikost
        izbrisanih += 1
    _pocisti_prazne(koren())
    return izbrisanih


def _pocisti_prazne(k: str) -> None:
    for mapa, podmape, imena in os.walk(k, topdown=False):
        if mapa != k and not podmape and not imena:
            try:
                os.rmdir(mapa)
            except OSError:
                pass


def odstrani_kanal(kanal_id: str) -> None:
    shutil.rmtree(os.path.join(koren(), _h(kanal_id)), ignore_errors=True)


def velja(kanal_id: str, mapa: str, uidvalidity) -> int:
    """Mapa ima zdaj to UIDVALIDITY: vnosi z drugo (stari UID-ji) se izbrisejo. Vrne izbrisanih map UIDVALIDITY."""
    if not str(uidvalidity or "").strip():
        return 0
    pot = os.path.join(koren(), _h(kanal_id), _h(mapa))
    izbrisanih = 0
    for d in _podmape(pot):
        if os.path.basename(d) != _uidv(uidvalidity):
            shutil.rmtree(d, ignore_errors=True)
            izbrisanih += 1
    return izbrisanih


def slicica(pot: str, vnos: str, velikost: int = 256) -> Optional[str]:
    """Slicica slike v vnosu (slicica.jpg, 0600); None, ce je ni mogoce narediti (brez Pillow, poskodovana slika)."""
    cilj = os.path.join(vnos, "slicica.jpg")
    if os.path.isfile(cilj):
        uporabi(cilj)
        return cilj
    try:
        from PIL import Image, ImageOps
        Image.MAX_IMAGE_PIXELS = 120_000_000
        with Image.open(pot) as s:
            s = ImageOps.exif_transpose(s)
            s.thumbnail((velikost, velikost))
            if s.mode not in ("RGB", "L"):
                s = s.convert("RGB")
            s.save(cilj + ".tmp", "JPEG", quality=82)
        os.chmod(cilj + ".tmp", 0o600)
        os.replace(cilj + ".tmp", cilj)
        return cilj
    except Exception:  # noqa: BLE001
        try:
            os.remove(cilj + ".tmp")
        except OSError:
            pass
        return None
