"""Odjemalec oddaljenega namizja Safeer Link.

Modul nima odvisnosti od GTK ali GStreamerja. Skrbi samo za protokol, pripenjanje
TLS potrdila in preslikavo vhodnih dogodkov; zato ga je mogoce preveriti brez zaslona.
"""

from __future__ import annotations

import hashlib
import json
import socket
import ssl
import struct
import threading
from dataclasses import dataclass
from typing import Callable, Dict, Iterator, Optional, Tuple


OKVIR_SLIKA = 1
OKVIR_ZVOK = 2
OKVIR_OBVESTILO = 3
NAJVECJI_OKVIR = 8 * 1024 * 1024


class NapakaGledalca(RuntimeError):
    """Napaka protokola ali varnostnega preverjanja."""


def normalen_odtis(odtis: str) -> str:
    """Odtis SHA-256 pretvori v 64 malih sestnajstiskih znakov."""
    cist = "".join(z for z in str(odtis or "").lower() if z in "0123456789abcdef")
    if len(cist) != 64:
        raise NapakaGledalca("Neveljaven odtis potrdila.")
    return cist


def razcleni_odgovor(odgovor: dict) -> dict:
    """Preveri odgovor ukaza screen.start in vrne podatke seje."""
    if not isinstance(odgovor, dict):
        raise NapakaGledalca("Naprava je vrnila neveljaven odgovor.")
    if odgovor.get("ok") is False:
        raise NapakaGledalca(str(odgovor.get("message") or "Naprava je zahtevo zavrnila."))
    podatki = odgovor.get("data") if isinstance(odgovor.get("data"), dict) else odgovor
    try:
        vrata = int(podatki.get("port"))
    except (TypeError, ValueError):
        vrata = 0
    zeton = str(podatki.get("token") or "")
    if not 1 <= vrata <= 65535 or not zeton or len(zeton) > 512:
        raise NapakaGledalca("Odgovor naprave nima veljavne seje zaslona.")
    return {
        **podatki,
        "port": vrata,
        "fp": normalen_odtis(str(podatki.get("fp") or "")),
        "token": zeton,
    }


class RazclenjevalnikOkvirjev:
    """Sprotno razclenjevanje okvirjev vrste + dolzine + telesa."""

    def __init__(self, najvec: int = NAJVECJI_OKVIR) -> None:
        self._podatki = bytearray()
        self.najvec = najvec

    def dodaj(self, kos: bytes) -> list[Tuple[int, bytes]]:
        if kos:
            self._podatki.extend(kos)
        izid = []
        while len(self._podatki) >= 5:
            vrsta = self._podatki[0]
            dolzina = int.from_bytes(self._podatki[1:5], "big")
            if dolzina <= 0 or dolzina > self.najvec:
                raise NapakaGledalca("Neveljavna dolzina okvirja.")
            if len(self._podatki) < 5 + dolzina:
                break
            telo = bytes(self._podatki[5:5 + dolzina])
            del self._podatki[:5 + dolzina]
            izid.append((vrsta, telo))
        return izid


TIPKE = {
    "Return": "vnasalka", "KP_Enter": "vnasalka", "Escape": "ubezna",
    "BackSpace": "vracalka", "Delete": "brisalka", "Tab": "tabulator",
    "space": "presledek", "Left": "levo", "Right": "desno", "Up": "gor", "Down": "dol",
    "Page_Up": "stran_gor", "Page_Down": "stran_dol", "Home": "zacetek", "End": "konec",
    "Control_L": "ctrl", "Control_R": "ctrl", "Alt_L": "alt", "Alt_R": "alt",
    "Shift_L": "shift", "Shift_R": "shift", "Super_L": "super", "Super_R": "super",
}
for _st in range(1, 13):
    TIPKE["F%d" % _st] = "f%d" % _st


def preslikaj_tipko(ime: str, besedilo: str = "", dol: Optional[bool] = None) -> Optional[dict]:
    """GTK-jevo ime tipke spremeni v dogodek protokola.

    Znaki se posljejo kot besedilo UTF-8, zato ostanejo sumniki in drugi znaki celi.
    Krmilke ter posebne tipke se posljejo kot pritisnjena/spuscena tipka.
    """
    oznaka = TIPKE.get(str(ime or ""))
    if oznaka:
        if dol is None:
            return {"vrsta": "tipka", "tipka": oznaka}
        return {"vrsta": "tipka_dol" if dol else "tipka_gor", "tipka": oznaka}
    if dol is not False and besedilo and all(ord(z) >= 32 for z in besedilo):
        return {"vrsta": "besedilo", "besedilo": besedilo}
    return None


@dataclass
class Glava:
    sirina: int
    visina: int
    fps: int
    podatki: dict


class Gledalec:
    """Ena TLS seja oddaljenega zaslona."""

    def __init__(self, naslov: str, seja: dict, cas_povezave: float = 8.0) -> None:
        self.naslov = str(naslov or "")
        self.seja = razcleni_odgovor(seja)
        self.cas_povezave = cas_povezave
        self.vticnica: Optional[ssl.SSLSocket] = None
        self._pisanje = threading.Lock()

    @staticmethod
    def _vrstica(vhod, najvec: int = 4096) -> bytes:
        zbrano = bytearray()
        while len(zbrano) < najvec:
            znak = vhod.recv(1)
            if not znak or znak == b"\n":
                break
            zbrano.extend(znak)
        if not zbrano or len(zbrano) >= najvec:
            raise NapakaGledalca("Streznik ni vrnil veljavne glave.")
        return bytes(zbrano)

    def povezi(self) -> Glava:
        if not self.naslov:
            raise NapakaGledalca("Naprava nima omreznega naslova.")
        surova = socket.create_connection((self.naslov, self.seja["port"]), self.cas_povezave)
        surova.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        kontekst = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        kontekst.check_hostname = False
        kontekst.verify_mode = ssl.CERT_NONE
        try:
            varna = kontekst.wrap_socket(surova, server_hostname=self.naslov)
            dejanski = hashlib.sha256(varna.getpeercert(binary_form=True)).hexdigest()
            if dejanski != self.seja["fp"]:
                raise NapakaGledalca("Odtis potrdila se ne ujema.")
            varna.sendall(("SAFEER-ZASLON " + self.seja["token"] + "\n").encode("utf-8"))
            podatki = json.loads(self._vrstica(varna).decode("utf-8"))
            if not isinstance(podatki, dict):
                raise ValueError
            self.vticnica = varna
            return Glava(max(1, int(podatki.get("w", 1920))), max(1, int(podatki.get("h", 1080))),
                         max(1, int(podatki.get("fps", 30))), podatki)
        except Exception:
            try:
                surova.close()
            except OSError:
                pass
            raise

    def okvirji(self) -> Iterator[Tuple[int, bytes]]:
        vticnica = self.vticnica
        if vticnica is None:
            raise NapakaGledalca("Gledalec ni povezan.")
        while True:
            glava = self._preberi_natanko(vticnica, 5)
            vrsta, dolzina = glava[0], struct.unpack(">I", glava[1:])[0]
            if dolzina <= 0 or dolzina > NAJVECJI_OKVIR:
                raise NapakaGledalca("Neveljavna dolzina okvirja.")
            yield vrsta, self._preberi_natanko(vticnica, dolzina)

    @staticmethod
    def _preberi_natanko(vticnica, koliko: int) -> bytes:
        deli = bytearray()
        while len(deli) < koliko:
            kos = vticnica.recv(koliko - len(deli))
            if not kos:
                raise NapakaGledalca("Povezava z napravo je bila prekinjena.")
            deli.extend(kos)
        return bytes(deli)

    def poslji(self, dogodek: dict) -> None:
        if self.vticnica is None:
            return
        vrstica = json.dumps(dogodek, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        with self._pisanje:
            self.vticnica.sendall(vrstica)

    def zapri(self) -> None:
        vticnica, self.vticnica = self.vticnica, None
        if vticnica is not None:
            try:
                vticnica.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                vticnica.close()
            except OSError:
                pass


__all__ = ["Gledalec", "Glava", "NapakaGledalca", "RazclenjevalnikOkvirjev", "razcleni_odgovor",
           "preslikaj_tipko", "normalen_odtis", "OKVIR_SLIKA", "OKVIR_ZVOK", "OKVIR_OBVESTILO"]
