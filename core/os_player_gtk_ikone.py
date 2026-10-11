"""Ikone Safeer OS (IK v assets/os/os.js) za GTK poglede - iste crte kot na strani, brez lastnega nabora.

Stran risi ikone kot SVG s potjo iz IK in barvo besedila (stroke: currentColor). Tukaj iste poti preberemo iz os.js
in jih z isto debelino crte izrisemo v GdkPixbuf.
"""
from __future__ import annotations

import os
import re
from typing import Optional

POT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "os", "os.js")
_VNOS = re.compile(r'^\s*,?\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*"([^"]*)"')
_PREDPOMNILNIK: dict = {}


def preberi(pot: str = POT) -> dict[str, str]:
    """{ime: pot SVG} iz bloka ``var IK = { ... };`` v os.js."""
    izid: dict[str, str] = {}
    v_bloku = False
    with open(pot, encoding="utf-8") as f:
        for vrstica in f:
            if not v_bloku:
                v_bloku = vrstica.strip().startswith("var IK = {")
                continue
            if vrstica.strip().startswith("};"):
                break
            m = _VNOS.match(vrstica)
            if m:
                izid[m.group(1)] = m.group(2)
    return izid


def ikone() -> dict[str, str]:
    if "ik" not in _PREDPOMNILNIK:
        try:
            _PREDPOMNILNIK["ik"] = preberi()
        except OSError:
            _PREDPOMNILNIK["ik"] = {}
    return _PREDPOMNILNIK["ik"]


def svg(ime: str, barva: str = "#f0f4f3", debelina: float = 1.8) -> str:
    """SVG ikone kot na strani (viewBox 24, crta brez polnila); neznano ime: ikona datoteke."""
    ik = ikone()
    pot = ik.get(ime) or ik.get("datoteka", "")
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="%s" '
            'stroke-linecap="round" stroke-linejoin="round"><path d="%s"/></svg>' % (barva, debelina, pot))


def pixbuf(ime: str, velikost: int = 18, barva: str = "#f0f4f3"):
    """GdkPixbuf ikone (ali None, ce nalagalnik SVG ni namescen)."""
    kljuc = (ime, velikost, barva)
    if kljuc in _PREDPOMNILNIK:
        return _PREDPOMNILNIK[kljuc]
    slika = None
    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        nalagalnik = GdkPixbuf.PixbufLoader.new_with_type("svg")
        nalagalnik.set_size(velikost, velikost)
        nalagalnik.write(svg(ime, barva).encode("utf-8"))
        nalagalnik.close()
        slika = nalagalnik.get_pixbuf()
    except Exception as e:  # noqa: BLE001 - brez ikone gumb se vedno deluje (napis ostane)
        print("[SafeerPlayer] ikona", ime, e)
    _PREDPOMNILNIK[kljuc] = slika
    return slika


def slika(ime: str, velikost: int = 18, barva: str = "#f0f4f3") -> Optional[object]:
    """Gtk.Image ikone ali None."""
    from gi.repository import Gtk
    p = pixbuf(ime, velikost, barva)
    return Gtk.Image.new_from_pixbuf(p) if p is not None else None
