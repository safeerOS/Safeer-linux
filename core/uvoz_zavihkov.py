"""Uvoz odprtih zavihkov iz drugih brskalnikov (Chromium: Opera, Chrome, Brave, Edge, Chromium).

Chromium shrani sejo v datoteke Sessions/Session_* (oblika SNSS): zaporedje ukazov. Za vsak zavihek vzamemo
navigacijo na izbranem indeksu (trenutna stran), zaprte zavihke in okna izpustimo. Samo branje - datotek drugega
brskalnika ne spreminjamo.
"""
from __future__ import annotations

import glob
import os
import struct

# Ukazi seje Chromium (components/sessions/core/session_service_commands.cc)
UKAZ_NAVIGACIJA = 6          # kCommandUpdateTabNavigation: tab_id, indeks, url, ...
UKAZ_IZBRAN_INDEKS = 7       # kCommandSetSelectedNavigationIndex: tab_id, indeks
UKAZ_ZAVIHEK_ZAPRT = 16      # kCommandTabClosed
UKAZ_OKNO = 0                # kCommandSetTabWindow: window_id, tab_id
UKAZ_OKNO_ZAPRTO = 17        # kCommandWindowClosed

BRSKALNIKI = {
    "Opera": [".config/opera", ".config/opera-beta", ".config/opera-developer"],
    "Chrome": [".config/google-chrome/*"],
    "Brave": [".config/BraveSoftware/Brave-Browser/*"],
    "Chromium": [".config/chromium/*", "snap/chromium/common/chromium/*"],
    "Edge": [".config/microsoft-edge/*"],
    "Vivaldi": [".config/vivaldi/*"],
}


def _niz(podatki: bytes, zamik: int) -> tuple[str, int]:
    dolzina = struct.unpack_from("<i", podatki, zamik)[0]
    zamik += 4
    if dolzina < 0 or zamik + dolzina > len(podatki):
        raise ValueError("niz")
    niz = podatki[zamik:zamik + dolzina].decode("utf-8", "replace")
    return niz, zamik + ((dolzina + 3) & ~3)


def preberi_sejo(podatki: bytes) -> list[str]:
    """Naslovi odprtih zavihkov iz datoteke SNSS (v vrstnem redu prvega pojava zavihka)."""
    if podatki[:4] != b"SNSS":
        return []
    navigacije: dict[int, dict[int, str]] = {}
    izbran: dict[int, int] = {}
    zaprti: set[int] = set()
    okno_zavihka: dict[int, int] = {}
    zaprta_okna: set[int] = set()
    vrstni_red: list[int] = []
    i = 8
    while i + 3 <= len(podatki):
        velikost = struct.unpack_from("<H", podatki, i)[0]
        if velikost == 0 or i + 2 + velikost > len(podatki):
            break
        ukaz = podatki[i + 2]
        vsebina = podatki[i + 3:i + 2 + velikost]
        i += 2 + velikost
        try:
            if ukaz == UKAZ_NAVIGACIJA:
                # Pickle: uint32 velikost, int32 tab_id, int32 indeks, niz url
                tab, indeks = struct.unpack_from("<ii", vsebina, 4)
                url, _ = _niz(vsebina, 12)
                navigacije.setdefault(tab, {})[indeks] = url
                if tab not in vrstni_red:
                    vrstni_red.append(tab)
            elif ukaz == UKAZ_IZBRAN_INDEKS and len(vsebina) >= 8:
                tab, indeks = struct.unpack_from("<ii", vsebina, 0)
                izbran[tab] = indeks
            elif ukaz == UKAZ_ZAVIHEK_ZAPRT and len(vsebina) >= 4:
                zaprti.add(struct.unpack_from("<i", vsebina, 0)[0])
            elif ukaz == UKAZ_OKNO and len(vsebina) >= 8:
                okno, tab = struct.unpack_from("<ii", vsebina, 0)
                okno_zavihka[tab] = okno
            elif ukaz == UKAZ_OKNO_ZAPRTO and len(vsebina) >= 4:
                zaprta_okna.add(struct.unpack_from("<i", vsebina, 0)[0])
        except (struct.error, ValueError):
            continue
    izid = []
    for tab in vrstni_red:
        if tab in zaprti or okno_zavihka.get(tab) in zaprta_okna:
            continue
        nav = navigacije[tab]
        url = nav.get(izbran.get(tab, max(nav)), nav[max(nav)])
        if url.startswith(("http://", "https://")):
            from core.config import prikazni_naslov
            url = prikazni_naslov(url)
            if url not in izid:
                izid.append(url)
    return izid


def najdi_seje(domov: str | None = None) -> dict[str, str]:
    """{ime brskalnika: najnovejsa datoteka seje}."""
    domov = domov or os.path.expanduser("~")
    najdene = {}
    for ime, vzorci in BRSKALNIKI.items():
        datoteke = []
        for v in vzorci:
            for profil in glob.glob(os.path.join(domov, v)):
                datoteke += glob.glob(os.path.join(profil, "Sessions", "Session_*"))
                datoteke += glob.glob(os.path.join(profil, "Default", "Sessions", "Session_*"))
        if datoteke:
            najdene[ime] = max(datoteke, key=os.path.getmtime)
    return najdene


def odprti_zavihki(domov: str | None = None) -> dict[str, list[str]]:
    """{ime brskalnika: [naslovi odprtih zavihkov]} za vse najdene brskalnike."""
    izid = {}
    for ime, pot in najdi_seje(domov).items():
        try:
            with open(pot, "rb") as f:
                zavihki = preberi_sejo(f.read())
        except OSError:
            continue
        if zavihki:
            izid[ime] = zavihki
    return izid


def odprti_zavihki_v_mapi(mapa: str, ime: str) -> dict[str, list[str]]:
    """Kot odprti_zavihki, a samo v mapi, ki jo je izbral uporabnik (Flatpak: portal dokumentov). Najnovejsa seja do
    globine 3 (npr. BraveSoftware/Brave-Browser/Default/Sessions)."""
    datoteke = []
    for globina in range(4):
        datoteke += glob.glob(os.path.join(glob.escape(mapa), *(["*"] * globina), "Sessions", "Session_*"))
    if not datoteke:
        return {}
    try:
        with open(max(datoteke, key=os.path.getmtime), "rb") as f:
            zavihki = preberi_sejo(f.read())
    except OSError:
        return {}
    return {ime: zavihki} if zavihki else {}
