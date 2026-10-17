"""Vgrajeni spletni predvajalnik (YouTube s seznama, vdelana stran, Twitch v spletu) v oknu Medijskega centra.

Lastnik, 17. 10. 2026: »Predvajanje prek YouTuba je delovalo, samo je locen okno - to popravi.« Lahki medijski pogled
(safeer_os._ustvari_medijski_pogled) zato ni vec svoje okno Gtk, ampak plast nad stranjo Medijskega centra (Gtk.Overlay
okna Safeer Player ali glavnega okna): pas zgoraj (Nazaj na Medijski center, naslov, Celozaslonsko) in pod njim pogled.

»Nazaj« plast le skrije - zvok (glasba s seznama) igra naprej, mini predvajalnik pokaze skladbo, klik nanj plast spet
pokaze. Escape zapusti cel zaslon (predvajanje tece naprej), sicer je enak »Nazaj«; F11 preklopi cel zaslon.

Modul ne uvaza Gtk: dobi ga od klicatelja (safeer_os, GTK 4) - preizkusi ga zato poganjajo z laznim Gtk brez prikaza.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

#: Razred pasu za CSS (barve iz assets/os/tokens.css prek core/os_lupina.tokeni).
RAZRED_PASU = "safeer-medijski-pas"


def css_pasu(tokeni: dict) -> str:
    """CSS za pas iz barv tokens.css ({ime: (r, g, b, a)}); brez tokenov prazno (ostane tema GTK)."""
    def b(ime: str) -> str:
        r, g, m, a = tokeni[ime]
        return "rgba(%d,%d,%d,%.3f)" % (r, g, m, a)
    try:
        return (".%s { background: %s; color: %s; padding: 6px 10px; border-bottom: 1px solid %s; }\n"
                ".%s button { min-height: 32px; padding: 2px 12px; }\n"
                ".%s .safeer-medijski-naslov { font-weight: 600; }\n"
                % (RAZRED_PASU, b("ozadje"), b("besedilo"), b("rob"), RAZRED_PASU, RAZRED_PASU))
    except (KeyError, TypeError, ValueError):
        return ""


class MedijskaPlast:
    """Pas + pogled kot plast (overlay) v oknu Medijskega centra. Ena na proces; okno se lahko zamenja (postavi)."""

    def __init__(self, Gtk: Any, pogled: Any, besedilo: Callable[[str], str], ob_nazaj: Callable[[], Any]) -> None:
        self.Gtk = Gtk
        self.pogled = pogled
        self._ob_nazaj = ob_nazaj
        self.okno: Any = None
        self.prekrivanje: Any = None
        self.cel_zaslon = False
        self.koren = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.pas = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.pas.add_css_class(RAZRED_PASU)
        self.nazaj = Gtk.Button(label="\u2190 %s" % besedilo("nazaj_medijski_center"))
        self.nazaj.set_tooltip_text(besedilo("nazaj_medijski_center_namig"))
        self.nazaj.connect("clicked", lambda *_a: self.nazaj_v_center())
        self.naslov = Gtk.Label(label="")
        self.naslov.set_hexpand(True)
        self.naslov.set_xalign(0.0)
        self.naslov.add_css_class("safeer-medijski-naslov")
        try:
            import gi  # noqa: WPS433 - samo za skrajsanje dolgega naslova
            gi.require_version("Pango", "1.0")
            from gi.repository import Pango  # noqa: WPS433
            self.naslov.set_ellipsize(Pango.EllipsizeMode.END)
        except Exception:  # noqa: BLE001 - brez Pango (preizkus) naslov ni skrajsan
            pass
        self.cel = Gtk.Button(icon_name="view-fullscreen-symbolic")
        self.cel.set_tooltip_text(besedilo("celozaslonsko_f11"))
        self.cel.connect("clicked", lambda *_a: self.nastavi_cel_zaslon(not self.cel_zaslon))
        for g in (self.nazaj, self.naslov, self.cel):
            self.pas.append(g)
        pogled.set_hexpand(True)
        pogled.set_vexpand(True)
        self.koren.append(self.pas)
        self.koren.append(pogled)
        self.koren.set_visible(False)
        # Cel zaslon elementa (gumb v predvajalniku YouTuba): brez pasu nad videom.
        try:
            pogled.connect("enter-fullscreen", lambda *_a: (self.pas.set_visible(False), False)[1])
            pogled.connect("leave-fullscreen", lambda *_a: (self.pas.set_visible(not self.cel_zaslon), False)[1])
        except Exception:  # noqa: BLE001 - pogled brez teh signalov: pas ostane
            pass

    # ------------------------------------------------------------------ okno
    def postavi(self, okno: Any, prekrivanje: Any) -> None:
        """Plast v Gtk.Overlay okna `okno` (iz prejsnjega okna se umakne - en pogled, en predvajalnik)."""
        if prekrivanje is self.prekrivanje:
            self.okno = okno
            return
        if self.prekrivanje is not None:
            if self.cel_zaslon:
                self.nastavi_cel_zaslon(False)
            self.prekrivanje.remove_overlay(self.koren)
        prekrivanje.add_overlay(self.koren)
        self.okno, self.prekrivanje = okno, prekrivanje

    # ------------------------------------------------------------------ vidnost
    def je_vidna(self) -> bool:
        return bool(self.koren.get_visible())

    def nastavi_naslov(self, naslov: str) -> None:
        self.naslov.set_label(str(naslov or ""))
        self.naslov.set_tooltip_text(str(naslov or "") or None)

    def pokazi(self, naslov: Optional[str] = None) -> None:
        if naslov is not None:
            self.nastavi_naslov(naslov)
        self.koren.set_visible(True)
        try:
            self.pogled.grab_focus()
        except Exception:  # noqa: BLE001
            pass

    def skrij(self) -> None:
        """Plast izgine, pogled (in zvok v njem) ostane - tako kot okno, ki ga skrijemo."""
        if self.cel_zaslon:
            self.nastavi_cel_zaslon(False)
        self.koren.set_visible(False)

    def nazaj_v_center(self) -> None:
        self.skrij()
        self._ob_nazaj()

    # ------------------------------------------------------------------ cel zaslon
    def nastavi_cel_zaslon(self, vklop: bool) -> None:
        vklop = bool(vklop)
        if self.okno is None or vklop == self.cel_zaslon:
            return
        self.cel_zaslon = vklop
        self.pas.set_visible(not vklop)          # cel zaslon: samo video
        if vklop:
            self.okno.fullscreen()
        else:
            self.okno.unfullscreen()
        self.cel.set_icon_name("view-restore-symbolic" if vklop else "view-fullscreen-symbolic")

    def tipka(self, ime: str) -> bool:
        """Tipka okna (faza zajema, pred stranjo v pogledu). True = obdelana."""
        if not self.je_vidna():
            return False
        if ime == "Escape":
            if self.cel_zaslon:
                self.nastavi_cel_zaslon(False)   # Esc zapre cel zaslon, predvajanje tece naprej
            else:
                self.nazaj_v_center()
            return True
        if ime == "F11":
            self.nastavi_cel_zaslon(not self.cel_zaslon)
            return True
        return False
