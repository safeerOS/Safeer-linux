"""Okno predogleda datotek v Safeer OS (GTK4 + WebKitGTK 6.0, v istem procesu kot vse drugo - core/en_proces.py).

Kaj pokazati, pove core/predogled_datotek.pripravi (brez GTK, skupno za vse dele Safeerja); to okno samo prikaze:
* PDF in pretvorjene dokumente z vgrajenim PDF.js WebKita (potrebuje JavaScript - zato pogled brez mostu),
* vse drugo kot stran brez JavaScripta (slike, besedilo, CSV, preciscen HTML, posredovana pisma).

Varnost: pogled nima mostu do Safeer OS (svoj UserContentManager brez sporocil), ima svojo kratkotrajno omrezno sejo
brez piskotkov, katere ves promet gre na zaprt posrednik (127.0.0.1:9 - oddaljena slika ali sledilni piksel ne pride
nikamor), premik na drugo stran je zavrnjen, povezava (http/https) pa se odpre v Spletu. Okno je eno: nova datoteka
zamenja prejsnjo, Esc ali Ctrl+W ga zapre.
"""
from __future__ import annotations

import os
import threading
from typing import Callable, Optional

from core import predogled_datotek

#: Zaprt posrednik: povezava se takoj zavrne (vrata 9 = discard; na 127.0.0.1 nihce ne poslusa).
ZAPRT_POSREDNIK = "http://127.0.0.1:9"


class OknoPredogleda:
    def __init__(self, Gtk, Gdk, GLib, WebKit, jezik: Callable[[], str],
                 odpri_povezavo: Optional[Callable[[str], None]] = None,
                 odpri_v_programu: Optional[Callable[[str], bool]] = None,
                 pokazi_v_mapi: Optional[Callable[[str], bool]] = None):
        self.Gtk, self.Gdk, self.GLib, self.WebKit = Gtk, Gdk, GLib, WebKit
        self._jezik = jezik
        self._odpri_povezavo = odpri_povezavo
        self._odpri_v_programu = odpri_v_programu
        self._pokazi_v_mapi = pokazi_v_mapi
        self._okno = None
        self._pogled = None
        self._seja = None
        self._rod = 0                 # vsak prikaz dobi svojo stevilko: pozen rezultat starega ne povozi novega
        self._pot = ""                # datoteka, ki jo okno kaze (za »Odpri v programu«)
        self._nevarno = False
        self._shranjeno = ""
        self._prenesi: Optional[Callable[[], str]] = None
        self._slike: Optional[dict] = None

    # ------------------------------------------------------------------ besedila
    def _t(self, kljuc: str, **z) -> str:
        return predogled_datotek.besedilo(kljuc, self._jezik(), **z)

    # ------------------------------------------------------------------ okno
    def _ustvari(self, stars) -> None:
        Gtk = self.Gtk
        okno = Gtk.Window(title="", modal=False)
        if stars is not None:
            okno.set_transient_for(stars)
            try:
                s, v = stars.get_width(), stars.get_height()
            except Exception:  # noqa: BLE001
                s, v = 0, 0
            okno.set_default_size(max(720, int(s * 0.85)) if s else 1000, max(560, int(v * 0.88)) if v else 780)
        else:
            okno.set_default_size(1000, 780)
        from gi.repository import Pango
        glava = Gtk.HeaderBar()
        self._naslov = Gtk.Label(ellipsize=Pango.EllipsizeMode.MIDDLE)
        self._naslov.add_css_class("title")
        self._podnaslov = Gtk.Label(ellipsize=Pango.EllipsizeMode.END)
        self._podnaslov.add_css_class("subtitle")
        naslov = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        naslov.append(self._naslov)
        naslov.append(self._podnaslov)
        glava.set_title_widget(naslov)
        self._gumb_prenesi = Gtk.Button(label=self._t("prenesi"))
        self._gumb_prenesi.add_css_class("suggested-action")
        self._gumb_prenesi.connect("clicked", lambda *_: self._na_prenesi())
        self._gumb_odpri = Gtk.Button(label=self._t("odpri"))
        self._gumb_odpri.connect("clicked", lambda *_: self._na_odpri())
        self._gumb_mapa = Gtk.Button(label=self._t("mapa"))
        self._gumb_mapa.connect("clicked", lambda *_: self._na_mapo())
        glava.pack_end(self._gumb_prenesi)
        glava.pack_end(self._gumb_odpri)
        glava.pack_end(self._gumb_mapa)
        okno.set_titlebar(glava)
        # Vrstica »Slike so skrite« (HTML pismo z oddaljenimi slikami): gradnik GTK nad vsebino, ne del strani -
        # besedilo pisma je ne more ponarediti ali »klikniti« namesto uporabnika.
        self._okvir = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._vrstica = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, margin_start=12, margin_end=12,
                                margin_top=6, margin_bottom=6)
        self._vrstica_napis = Gtk.Label(xalign=0, hexpand=True, wrap=True)
        self._gumb_slike = Gtk.Button(label="")
        self._gumb_slike.connect("clicked", lambda *_: self._na_slike(False))
        self._gumb_vedno = Gtk.Button(label="")
        self._gumb_vedno.connect("clicked", lambda *_: self._na_slike(True))
        for g in (self._vrstica_napis, self._gumb_slike, self._gumb_vedno):
            self._vrstica.append(g)
        self._vrstica.set_visible(False)
        self._okvir.append(self._vrstica)
        okno.set_child(self._okvir)
        bliznjice = Gtk.ShortcutController()
        bliznjice.set_scope(Gtk.ShortcutScope.MANAGED)
        for tipka in ("Escape", "<Control>w"):
            bliznjice.add_shortcut(Gtk.Shortcut.new(Gtk.ShortcutTrigger.parse_string(tipka),
                                                    Gtk.CallbackAction.new(lambda *_a: (self.zapri(), True)[1])))
        okno.add_controller(bliznjice)
        okno.connect("close-request", lambda *_: (self._ob_zaprtju(), False)[1])
        self._okno = okno

    def _ob_zaprtju(self) -> None:
        self._rod += 1
        self._okno, self._pogled = None, None

    def zapri(self) -> None:
        if self._okno is not None:
            self._okno.close()

    def odprto(self) -> bool:
        return self._okno is not None

    def _nov_pogled(self, javascript: bool):
        """Pogled brez mostu in brez omrezja (glej opis modula)."""
        WebKit = self.WebKit
        if self._seja is None:
            self._seja = WebKit.NetworkSession.new_ephemeral()
            self._seja.set_proxy_settings(WebKit.NetworkProxyMode.CUSTOM,
                                          WebKit.NetworkProxySettings.new(ZAPRT_POSREDNIK, None))
            self._seja.connect("download-started", self._na_prenos)
        pogled = WebKit.WebView(network_session=self._seja, user_content_manager=WebKit.UserContentManager())
        n = pogled.get_settings()
        n.set_property("enable-javascript", bool(javascript))
        for ime, vrednost in (("enable-javascript-markup", bool(javascript)), ("enable-developer-extras", False),
                              ("allow-file-access-from-file-urls", False), ("allow-universal-access-from-file-urls", False),
                              ("enable-webgl", False), ("enable-html5-database", False), ("enable-html5-local-storage", False),
                              ("javascript-can-open-windows-automatically", False), ("enable-media", False)):
            try:
                n.set_property(ime, vrednost)
            except TypeError:
                pass
        pogled.connect("decide-policy", self._na_politiko)
        pogled.connect("create", lambda *_a: None)        # novo okno (target=_blank): ne odpremo ga
        pogled.set_hexpand(True)
        pogled.set_vexpand(True)
        return pogled

    def _na_politiko(self, _pogled, odlocitev, vrsta) -> bool:
        WebKit = self.WebKit
        try:
            if vrsta not in (WebKit.PolicyDecisionType.NAVIGATION_ACTION, WebKit.PolicyDecisionType.NEW_WINDOW_ACTION):
                return False
            akcija = odlocitev.get_navigation_action()
            naslov = akcija.get_request().get_uri() or ""
            if naslov.startswith(("http://", "https://")):
                # Klik na povezavo v PDF ali pismu: v Spletu, ne v predogledu (brez omrezja).
                odlocitev.ignore()
                if akcija.is_user_gesture() and self._odpri_povezavo is not None:
                    self._odpri_povezavo(naslov)
                return True
            if vrsta == WebKit.PolicyDecisionType.NEW_WINDOW_ACTION:
                odlocitev.ignore()
                return True
            if naslov.startswith(("file://", "webkit-pdfjs-viewer://", "about:", "data:", "blob:")):
                return False
        except Exception:  # noqa: BLE001
            pass
        odlocitev.ignore()
        return True

    def _na_prenos(self, _seja, prenos) -> None:
        """Gumb »Prenesi« v PDF.js: v Prejemi z edinstvenim imenom (nic se ne prepise)."""
        from core import os_sporocila, splet_prenosi

        def cilj(p, predlog) -> bool:
            p.set_destination(splet_prenosi.edinstvena_pot(os_sporocila.mapa_prejemov(),
                                                           predogled_datotek.varno_ime(predlog or "dokument.pdf")))
            return True
        prenos.connect("decide-destination", cilj)

    # ------------------------------------------------------------------ prikaz
    def odpri(self, naslov: str, stars=None, podnaslov: str = "", prenesi: Optional[Callable[[], str]] = None,
              nevarno: bool = False) -> int:
        """Odpre (ali dvigne) okno in pokaze »Pripravljam predogled …«. Vrne stevilko prikaza za pokazi()."""
        if self._okno is None:
            self._ustvari(stars)
        self._rod += 1
        self._pot, self._shranjeno, self._prenesi, self._nevarno = "", "", prenesi, bool(nevarno)
        self._okno.set_title(naslov)
        self._naslov.set_text(naslov)
        self._podnaslov.set_text(podnaslov)
        self._gumb_prenesi.set_label(self._t("prenesi"))
        self._gumb_odpri.set_label(self._t("odpri"))
        self._gumb_mapa.set_label(self._t("mapa"))
        self._gumb_prenesi.set_visible(prenesi is not None)
        self._gumb_prenesi.set_sensitive(True)
        self._gumb_odpri.set_visible(False)
        self._gumb_mapa.set_visible(False)
        self._slike = None
        self._vrstica.set_visible(False)
        self._nalozi_html(predogled_datotek.stran_sporocila(self._t("pripravljam"), "", self._jezik(), nalaganje=True), "")
        self._okno.present()
        return self._rod

    def _nalozi_html(self, html: str, osnova: str) -> None:
        pogled = self._nov_pogled(False)
        pogled.load_html(html, osnova or "about:blank")
        self._zamenjaj(pogled)

    def _zamenjaj(self, pogled) -> None:
        if self._pogled is not None and self._pogled.get_parent() is self._okvir:
            self._okvir.remove(self._pogled)
        self._okvir.append(pogled)
        self._pogled = pogled

    def pokazi(self, rod: int, izid: dict, pot: str = "", slike: Optional[dict] = None) -> bool:
        """Rezultat predogled_datotek.pripravi (klic v glavni niti). Vrne False, ce je okno vmes zaprto ali zamenjano.
        slike: {"skritih", "posiljatelj", "prikazi": fn(vedno)} - vrstica »Prikazi slike« nad HTML pismom."""
        if self._okno is None or rod != self._rod:
            return False
        self._slike = slike if slike and int(slike.get("skritih") or 0) > 0 else None
        if self._slike is not None:
            self._vrstica_napis.set_text(self._t("slike_vrstica"))
            self._gumb_slike.set_label(self._t("slike_prikazi"))
            od = str(self._slike.get("posiljatelj") or "")
            self._gumb_vedno.set_label(self._t("slike_vedno", od=od))
            self._gumb_vedno.set_visible(bool(od))
            self._gumb_slike.set_sensitive(True)
            self._gumb_vedno.set_sensitive(True)
        self._vrstica.set_visible(self._slike is not None)
        self._pot = pot if pot and os.path.isfile(pot) else ""
        self._gumb_odpri.set_visible(bool(self._pot) and self._odpri_v_programu is not None)
        self._gumb_mapa.set_visible(bool(self._pot) and self._prenesi is None and self._pokazi_v_mapi is not None)
        if izid.get("nacin") == "pdf" and izid.get("pot"):
            pogled = self._nov_pogled(True)              # PDF.js je JavaScript (vgrajen v WebKit, ne iz datoteke)
            pogled.load_uri(self.GLib.filename_to_uri(os.path.abspath(izid["pot"]), None))
            self._zamenjaj(pogled)
        else:
            self._nalozi_html(str(izid.get("html") or ""), str(izid.get("osnova") or ""))
        return True

    def _na_slike(self, vedno: bool) -> None:
        if self._slike is None:
            return
        self._gumb_slike.set_sensitive(False)
        self._gumb_vedno.set_sensitive(False)
        self._slike["prikazi"](vedno)

    def napaka(self, rod: int, besedilo: str) -> None:
        if self._okno is None or rod != self._rod:
            return
        self._nalozi_html(predogled_datotek.stran_sporocila(self._t("brez_naslov"), besedilo, self._jezik()), "")

    def odpri_datoteko(self, pot: str, stars=None) -> None:
        """Predogled krajevne datoteke (Datoteke, namizje): priprava v ozadju, prikaz v glavni niti."""
        ime = os.path.basename(pot)
        rod = self.odpri(ime, stars, nevarno=predogled_datotek.je_nevarna(ime))
        jezik = self._jezik()

        def delo() -> None:
            izid = predogled_datotek.pripravi(pot, ime, "", jezik)
            self.GLib.idle_add(lambda: (self.pokazi(rod, izid, pot), False)[1])
        threading.Thread(target=delo, name="safeer-predogled", daemon=True).start()

    # ------------------------------------------------------------------ gumbi
    def _na_prenesi(self) -> None:
        if self._prenesi is None:
            return
        if self._shranjeno:
            self._na_mapo()
            return
        rod, prenesi = self._rod, self._prenesi
        self._gumb_prenesi.set_sensitive(False)

        def delo() -> None:
            try:
                pot = prenesi() or ""
            except Exception:  # noqa: BLE001
                pot = ""
            self.GLib.idle_add(lambda: (self._ob_shranjenem(rod, pot), False)[1])
        threading.Thread(target=delo, name="safeer-predogled-prenos", daemon=True).start()

    def _ob_shranjenem(self, rod: int, pot: str) -> None:
        if self._okno is None or rod != self._rod:
            return
        self._gumb_prenesi.set_sensitive(True)
        if pot:
            self._shranjeno = pot
            self._podnaslov.set_text(self._t("shranjeno", ime=os.path.basename(pot)))
            self._gumb_prenesi.set_label(self._t("mapa"))
        else:
            self._podnaslov.set_text(self._t("napaka"))

    def _na_mapo(self) -> None:
        pot = self._shranjeno or self._pot
        if pot and self._pokazi_v_mapi is not None:
            self._pokazi_v_mapi(pot)

    def _na_odpri(self) -> None:
        if not self._pot or self._odpri_v_programu is None:
            return
        if not self._nevarno:
            self._odpri_v_programu(self._pot)
            return
        # Program, skripta ali dokument z makri: odpre se samo po izrecni potrditvi (kot opozorilo v Gmailu).
        Gtk, pot = self.Gtk, self._pot
        try:
            dialog = Gtk.AlertDialog(message=self._t("nevarno_naslov"),
                                     detail=self._t("nevarno", ime=os.path.basename(pot)))
            dialog.set_buttons([self._t("zapri"), self._t("odpri")])
            dialog.set_cancel_button(0)
            dialog.set_default_button(0)

            def izbrano(d, izid) -> None:
                try:
                    if d.choose_finish(izid) == 1:
                        self._odpri_v_programu(pot)
                except Exception:  # noqa: BLE001 - preklic
                    pass
            dialog.choose(self._okno, None, izbrano)
        except Exception:  # noqa: BLE001 - brez Gtk.AlertDialog (GTK < 4.10) nevarne datoteke ne odpremo
            pass
