"""Zmoznosti naprav v Safeer Linku: en seznam imen in pomenov (register zmoznosti).

Naprava ob prijavi (`cast.register`, polje `capabilities`) pove, kaj zna. Imena so del protokola - ista na Linuxu,
Windows in Androidu -, zato so zbrana tu z opisom: `safeerctl capabilities` in vmesniki jih kazejo enako, test pa
ujame zmoznost, ki jo koda oglasa, v seznamu pa je ni (tests/test_safeerctl.py, RegisterZmoznosti).

Brez odvisnosti. Zmoznost pove, kaj naprava SPREJME ali PONUDI drugim - ne kaj je (televizor, telefon); vrsto naprave
povesta polji `platform` in `kind` iste prijave.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

#: ime zmoznosti -> (opis v slovenscini, opis v anglescini)
ZMOZNOSTI: Dict[str, Tuple[str, str]] = {
    "url": ("odpre spletni naslov, ki ji ga pošlješ", "opens a web address you send to it"),
    "text": ("sprejme besedilo", "receives text"),
    "file": ("sprejme datoteko", "receives a file"),
    "files": ("deli svoje datoteke (pregled in predvajanje z drugih naprav)", "shares its files (browse and play from other devices)"),
    "screen": ("pokaže zaslon, ki ga deli druga naprava", "shows a screen shared by another device"),
    "remote": ("sprejema ukaze daljinca", "accepts remote-control commands"),
    "media": ("predvaja medije, ki ji jih pošlješ", "plays media you send to it"),
    "control": ("upravljanje predvajanja (predvajaj, premor, ustavi)", "playback control (play, pause, stop)"),
    "volume": ("nastavitev glasnosti", "volume control"),
    "seek": ("premik po posnetku", "seeking in the recording"),
    "audio": ("predvaja zvok računalnika", "plays the computer's audio"),
    "apps": ("našteje in zažene svoje programe", "lists and launches its apps"),
    "desktop": ("pokaže svoje namizje na drugi napravi", "shows its desktop on another device"),
    "chat": ("Safeer Chat (sporočila med napravami)", "Safeer Chat (messages between devices)"),
    "magnet": ("odpre magnet povezavo", "opens a magnet link"),
    "torrent": ("prenaša torrente in jih pretaka drugim napravam", "downloads torrents and streams them to other devices"),
    "lists": ("usklajuje sezname predvajanja", "syncs playlists"),
    "sync": ("usklajuje zaznamke", "syncs bookmarks"),
    "internet.gateway": ("deli svojo internetno povezavo", "shares its internet connection"),
    "e2e1": ("ukaze in odgovore sprejema in pošilja zaščitene od naprave do naprave",
             "commands and their answers are protected device to device"),
}


def opis(ime: str, jezik: str = "sl") -> str:
    """Opis zmoznosti v jeziku vmesnika; neznana zmoznost (novejsa naprava) ostane pri svojem imenu."""
    par = ZMOZNOSTI.get(str(ime))
    if not par:
        return str(ime)
    return par[0] if jezik == "sl" else par[1]


def znane(zmoznosti: Iterable[str]) -> List[str]:
    """Zmoznosti naprave v vrstnem redu registra; neznane (iz novejse razlicice) na koncu, po abecedi."""
    dane = [str(z) for z in (zmoznosti or [])]
    urejene = [z for z in ZMOZNOSTI if z in dane]
    return urejene + sorted(set(z for z in dane if z not in ZMOZNOSTI))
