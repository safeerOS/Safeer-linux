"""Miskin kazalec oddaljenega zaslona kot PODATEK, ne kot del slike (lastnik 25. 10. 2026: »dvojni kazalec«).

Gledalec z lastno misko (Windows, Linux) kaze svoj kazalec; ce je v sliki se kazalec racunalnika, sta dva - drugi zaostaja
za sliko. Gledalec, ki to zna, v `screen.start` poslje zmoznost KAZALEC; takrat zajem kazalca ne narise (x11grab
`-draw_mouse 0`), racunalnik pa ob vsaki spremembi poslje obvestilo (okvir 3, enako kot vir Windows od 9. 10. 2026,
navidezni_zaslon.py):

    {"kazalec": [x, y], "oblika": "puscica" | "besedilo" | ..., "viden": true}
    ob spremembi oblike se:  "slika": "data:image/png;base64,...", "vroca": [hx, hy]   (tocna slika kazalca)

x, y sta v tockah SLIKE (po pomanjsavi), slika kazalca je v tockah zaslona. Gledalec z misko nastavi svojemu kazalcu
obliko (sistemsko po imenu ali tocno sliko) in polozaja ne potrebuje; naprava brez miske (tablica, TV) narise kazalec
na polozaj (Android KazalecPogled). Imena oblik so ista kot pri viru Windows (zajem_zaslona._OBLIKE_KAZALCA).

X11: XFixes (GetCursorImage: polozaj, serijska stevilka, ime in slika) prek ctypes, v svoji povezavi do X.
Wayland: kazalec je v sliki portala (nacin EMBEDDED) - ta modul ga ne bere.
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.util
import struct
import zlib
from typing import Optional

ZMOZNOST = "kazalec"
#: Polozaj beremo vsakih toliko sekund (8 ms kot vir Windows): kazalec gledalca brez miske se premika takoj.
RAZMIK_S = 0.008
#: Vecje slike kazalca ne posljemo (sistemski kazalci so 24-64 px; vecje je napaka ali tuj program).
NAJVECJA_SLIKA = 128

#: Imena kazalcev X (jedro, Xcursor, CSS) -> ime, ki ga zna narisati vsak gledalec Safeer.
_IMENA = {
    "puscica": ("left_ptr", "default", "arrow", "top_left_arrow", "context-menu", "copy", "alias", "dnd-copy",
                "dnd-link", "dnd-none", "x-cursor"),
    "besedilo": ("xterm", "text", "ibeam", "vertical-text"),
    "cakanje": ("watch", "wait", "clock"),
    "puscica_cakanje": ("left_ptr_watch", "progress", "half-busy"),
    "kriz": ("crosshair", "cross", "tcross", "cell", "plus", "cross_reverse", "diamond_cross"),
    "velikost_nwse": ("nwse-resize", "nw-resize", "se-resize", "bottom_right_corner", "top_left_corner", "size_fdiag",
                      "bd_double_arrow"),
    "velikost_nesw": ("nesw-resize", "ne-resize", "sw-resize", "top_right_corner", "bottom_left_corner", "size_bdiag",
                      "fd_double_arrow"),
    "velikost_we": ("ew-resize", "col-resize", "e-resize", "w-resize", "sb_h_double_arrow", "h_double_arrow",
                    "left_side", "right_side", "size_hor", "split_h"),
    "velikost_ns": ("ns-resize", "row-resize", "n-resize", "s-resize", "sb_v_double_arrow", "v_double_arrow",
                    "top_side", "bottom_side", "size_ver", "split_v"),
    "premik": ("move", "fleur", "all-scroll", "size_all", "dnd-move", "grabbing", "closedhand"),
    "roka": ("pointer", "hand", "hand1", "hand2", "pointing_hand", "grab", "openhand"),
    "ne": ("not-allowed", "no-drop", "crossed_circle", "forbidden", "circle", "pirate"),
}
_IZ_IMENA = {x: oblika for oblika, imena in _IMENA.items() for x in imena}
OBLIKE = tuple(_IMENA)


def oblika(ime: Optional[str]) -> str:
    """Ime kazalca X -> ime oblike Safeer; neznano je »puscica« (tocna slika gre zraven)."""
    return _IZ_IMENA.get(str(ime or "").strip().lower(), "puscica")


def png(sirina: int, visina: int, argb) -> bytes:
    """Slika kazalca (ARGB, predhodno pomnozena alfa, kot jo da XFixes) -> PNG RGBA (brez knjiznic)."""
    vrstice = bytearray()
    for y in range(visina):
        vrstice.append(0)
        for x in range(sirina):
            p = int(argb[y * sirina + x]) & 0xFFFFFFFF
            a, r, g, b = p >> 24, (p >> 16) & 255, (p >> 8) & 255, p & 255
            if 0 < a < 255:             # predhodno pomnozeno -> navadna alfa
                r, g, b = min(255, r * 255 // a), min(255, g * 255 // a), min(255, b * 255 // a)
            vrstice += bytes((r, g, b, a))

    def kos(vrsta: bytes, podatki: bytes) -> bytes:
        return struct.pack(">I", len(podatki)) + vrsta + podatki + struct.pack(">I", zlib.crc32(vrsta + podatki))
    return (b"\x89PNG\r\n\x1a\n" + kos(b"IHDR", struct.pack(">IIBBBBB", sirina, visina, 8, 6, 0, 0, 0))
            + kos(b"IDAT", zlib.compress(bytes(vrstice), 6)) + kos(b"IEND", b""))


def v_sliki(x: int, y: int, odmik: tuple, izvor: tuple, slika: tuple) -> tuple:
    """Polozaj na zaslonu -> (x, y, viden) v tockah slike, ki jo posiljamo (deljeni monitor in pomanjsava)."""
    ix, iy = x - int(odmik[0]), y - int(odmik[1])
    iw, ih = max(1, int(izvor[0])), max(1, int(izvor[1]))
    viden = 0 <= ix < iw and 0 <= iy < ih
    sx, sy = int(slika[0]) / float(iw), int(slika[1]) / float(ih)
    return int(round(ix * sx)), int(round(iy * sy)), viden


class Sprememba:
    """Kaj od kazalca poslati: polozaj ob premiku, oblika (in slika) samo ob novi serijski stevilki. Brez GTK/X."""

    def __init__(self) -> None:
        self._polozaj = None
        self._serija = None

    def naslednje(self, stanje: dict, odmik: tuple, izvor: tuple, slika: tuple) -> Optional[dict]:
        x, y, viden = v_sliki(stanje["x"], stanje["y"], odmik, izvor, slika)
        viden = viden and stanje.get("viden", True)
        nova_oblika = stanje.get("serija") != self._serija
        if not nova_oblika and (x, y, viden) == self._polozaj:
            return None
        self._polozaj = (x, y, viden)
        sporocilo = {"kazalec": [x, y], "oblika": oblika(stanje.get("ime")), "viden": viden}
        if nova_oblika:
            self._serija = stanje.get("serija")
            if stanje.get("png"):
                sporocilo["slika"] = "data:image/png;base64," + base64.b64encode(stanje["png"]).decode("ascii")
                sporocilo["vroca"] = [int(stanje.get("xhot", 0)), int(stanje.get("yhot", 0))]
        return sporocilo


class _Slika(ctypes.Structure):
    _fields_ = [("x", ctypes.c_short), ("y", ctypes.c_short), ("width", ctypes.c_ushort),
                ("height", ctypes.c_ushort), ("xhot", ctypes.c_ushort), ("yhot", ctypes.c_ushort),
                ("cursor_serial", ctypes.c_ulong), ("pixels", ctypes.POINTER(ctypes.c_ulong)),
                ("atom", ctypes.c_ulong), ("name", ctypes.c_char_p)]


class KazalecX11:
    """Kazalec zaslona X11 prek XFixes; vsaka nit naj ima svojega (lastna povezava do X)."""

    def __init__(self, display: str) -> None:
        x11 = ctypes.util.find_library("X11")
        xf = ctypes.util.find_library("Xfixes")
        if not x11 or not xf:
            raise OSError("ni knjiznic X11/Xfixes")
        self._x = ctypes.cdll.LoadLibrary(x11)
        self._f = ctypes.cdll.LoadLibrary(xf)
        self._x.XOpenDisplay.restype = ctypes.c_void_p
        self._x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self._x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self._x.XFree.argtypes = [ctypes.c_void_p]
        self._f.XFixesQueryExtension.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
                                                 ctypes.POINTER(ctypes.c_int)]
        self._f.XFixesGetCursorImage.restype = ctypes.POINTER(_Slika)
        self._f.XFixesGetCursorImage.argtypes = [ctypes.c_void_p]
        self._serija = None
        self._viden = True
        self._dpy = self._x.XOpenDisplay(display.encode("utf-8") if display else None)
        if not self._dpy:
            raise OSError("zaslona X ni mogoce odpreti")
        a, b = ctypes.c_int(), ctypes.c_int()
        if not self._f.XFixesQueryExtension(self._dpy, ctypes.byref(a), ctypes.byref(b)):
            self.zapri()
            raise OSError("zaslon X nima razsiritve XFixes")

    def stanje(self) -> Optional[dict]:
        """{x, y, serija, ime, viden[, png, xhot, yhot]} - slika samo, ko se je kazalec zamenjal."""
        if not self._dpy:
            return None
        p = self._f.XFixesGetCursorImage(self._dpy)
        if not p:
            return None
        try:
            s = p.contents
            izid = {"x": int(s.x), "y": int(s.y), "serija": int(s.cursor_serial),
                    "ime": (s.name or b"").decode("utf-8", "replace")}
            if izid["serija"] != self._serija:
                self._serija = izid["serija"]
                w, h = int(s.width), int(s.height)
                if 0 < w <= NAJVECJA_SLIKA and 0 < h <= NAJVECJA_SLIKA and s.pixels:
                    piksli = s.pixels[:w * h]
                    self._viden = any(int(v) >> 24 for v in piksli)
                    izid.update(png=png(w, h, piksli), xhot=int(s.xhot), yhot=int(s.yhot))
            izid["viden"] = self._viden
            return izid
        finally:
            self._x.XFree(p)

    def zapri(self) -> None:
        if self._dpy:
            self._x.XCloseDisplay(self._dpy)
            self._dpy = None
