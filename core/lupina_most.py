"""Most med lupino namizja (Safeer Shell, svoj proces) in Safeer OS - prenos prek vticnice Unix.

Lastnik, 18. 10. 2026 (moznost B): lupina namizja QML tece v svojem procesu, da sesutje ali zamrznitev Safeer OS
(Medijski center, GStreamer, WebKit, Python) ne podre namizja. QML ostane nespremenjen: Most.klic / odgovor / dogodek so
isti kot v enem procesu (core/os_lupina.py), zamenjan je samo prenos.

Vticnica: $XDG_RUNTIME_DIR/safeer-os/lupina.sock (mapa 0700, vticnica 0600, samo ta uporabnik), brez omrezja. Obe strani
preverita uid sogovornika (SO_PEERCRED). Okvir: 4 bajti dolzine (big-endian) + 1 bajt vrste + telo:

  K  klic       lupina -> OS   JSON {"k": id, "m": metoda, "a": [argumenti]}
  Z  zdravo     lupina -> OS   JSON {"razmerje": devicePixelRatio, "pid": pid}
  P  ping       lupina -> OS   4 bajti id (meritev zakasnitve, odgovor Q iz glavne zanke Safeer OS)
  O  odgovor    OS -> lupina   4 bajti id, 1 bajt ok, besedilo JSON (gre v QML nespremenjeno - brez ponovnega razclenjevanja)
  D  dogodek    OS -> lupina   2 bajta dolzine vrste, vrsta, besedilo JSON
  U  ukaz       OS -> lupina   JSON {"u": "aktiviraj" | ...}
  Q  pong       OS -> lupina   4 bajti id

Modul je brez Gtk in Qt: uvozita ga oba procesa.
"""
from __future__ import annotations

import json
import os
import socket
import struct
from typing import Any, List, Optional, Tuple

#: Najvecji okvir (seznam velike mape v Datotekah je nekaj MB); vecji pomeni napako ali zlorabo - povezava se prekine.
NAJVEC_OKVIR = 64 * 1024 * 1024
_GLAVA = struct.Struct(">I")
_ID = struct.Struct(">i")
_ODG = struct.Struct(">iB")
_VRSTA = struct.Struct(">H")


# ---------------------------------------------------------------------------------------------- poti
def mapa_izvajanja() -> str:
    """$XDG_RUNTIME_DIR/safeer-os (0700) - ena odlocitev z varuhom (core/varuh_procesov.mapa_izvajanja)."""
    from core import varuh_procesov
    return varuh_procesov.mapa_izvajanja()


def pot_vticnice() -> str:
    return os.environ.get("SAFEER_LUPINA_VTIC") or os.path.join(mapa_izvajanja(), "lupina.sock")


def pot_stanja_varuha() -> str:
    """Stanje varuha (core/varuh_procesov.py) za lupino: ali se Safeer OS zaganja, caka na pomnilnik ali je varuh obupal."""
    return os.path.join(mapa_izvajanja(), "varuh.json")


def beri_stanje_varuha(pot: Optional[str] = None) -> dict:
    try:
        with open(pot or pot_stanja_varuha(), encoding="utf-8") as d:
            s = json.load(d)
        return s if isinstance(s, dict) else {}
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------------------------------------- sogovornik
def sogovornik(sock: socket.socket) -> Tuple[int, int, int]:
    """(pid, uid, gid) procesa na drugi strani vticnice Unix (SO_PEERCRED)."""
    podatki = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    return struct.unpack("3i", podatki)


def nas_sogovornik(sock: socket.socket) -> bool:
    """Ali je na drugi strani ta uporabnik. Vticnica je ze 0600 v mapi 0700; preverba je druga varovalka."""
    try:
        return sogovornik(sock)[1] == os.getuid()
    except OSError:
        return False


# ---------------------------------------------------------------------------------------------- okvirji
def okvir(vrsta: bytes, telo: bytes = b"") -> bytes:
    return _GLAVA.pack(1 + len(telo)) + vrsta + telo


def _json(predmet: Any) -> bytes:
    return json.dumps(predmet, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def klic(klic_id: int, metoda: str, argumenti: list) -> bytes:
    return okvir(b"K", _json({"k": int(klic_id), "m": str(metoda), "a": list(argumenti)}))


def zdravo(podatki: dict) -> bytes:
    return okvir(b"Z", _json(podatki))


def ping(stevilka: int) -> bytes:
    return okvir(b"P", _ID.pack(int(stevilka)))


def pong(stevilka: int) -> bytes:
    return okvir(b"Q", _ID.pack(int(stevilka)))


def besedilo_json(podatki: Any) -> str:
    """Isto besedilo kot prej v QmlPogled (json.dumps, ensure_ascii=False, default=str) - QML ga razclenjuje sam."""
    return json.dumps(podatki, ensure_ascii=False, default=str)


def odgovor(klic_id: int, ok: bool, besedilo: str) -> bytes:
    return okvir(b"O", _ODG.pack(int(klic_id), 1 if ok else 0) + besedilo.encode("utf-8"))


def dogodek(vrsta: str, besedilo: str) -> bytes:
    v = str(vrsta).encode("utf-8")[:65535]
    return okvir(b"D", _VRSTA.pack(len(v)) + v + besedilo.encode("utf-8"))


def ukaz(podatki: dict) -> bytes:
    return okvir(b"U", _json(podatki))


def razcleni(vrsta: bytes, telo: bytes) -> Tuple[str, Any]:
    """(vrsta, vsebina): K/Z/U -> dict, P/Q -> id, O -> (id, ok, besedilo), D -> (vrsta, besedilo)."""
    if vrsta in (b"K", b"Z", b"U"):
        return vrsta.decode(), json.loads(telo.decode("utf-8"))
    if vrsta in (b"P", b"Q"):
        return vrsta.decode(), _ID.unpack(telo[:4])[0]
    if vrsta == b"O":
        klic_id, ok = _ODG.unpack(telo[:5])
        return "O", (klic_id, bool(ok), telo[5:].decode("utf-8"))
    if vrsta == b"D":
        n = _VRSTA.unpack(telo[:2])[0]
        return "D", (telo[2:2 + n].decode("utf-8"), telo[2 + n:].decode("utf-8"))
    raise ValueError("neznana vrsta okvirja %r" % vrsta)


class PrevelikOkvir(ValueError):
    pass


class Dekoder:
    """Okvirji iz toka bajtov (vticnica lahko vrne pol okvirja ali vec okvirjev naenkrat)."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def dodaj(self, podatki: bytes) -> List[Tuple[bytes, bytes]]:
        self._buf += podatki
        izid: List[Tuple[bytes, bytes]] = []
        while len(self._buf) >= 4:
            n = _GLAVA.unpack_from(self._buf, 0)[0]
            if n < 1 or n > NAJVEC_OKVIR:
                raise PrevelikOkvir(n)
            if len(self._buf) < 4 + n:
                break
            vrsta = bytes(self._buf[4:5])
            telo = bytes(self._buf[5:4 + n])
            del self._buf[:4 + n]
            izid.append((vrsta, telo))
        return izid
