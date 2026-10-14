"""Ikona v pladnju brez GTK3: StatusNotifierItem (org.kde.StatusNotifierItem) z menijem prek com.canonical.dbusmenu.

GTK4 nima Gtk.StatusIcon, XApp.StatusIcon pa potrebuje GTK3 (en proces ne sme naloziti GTK3 in GTK4 hkrati). Ikono SNI
kazejo Linux Mint (xapp-sn-watcher), KDE in GNOME z razsiritvijo AppIndicator. Vse je D-Bus (Gio), zato modul dela s
katerimkoli GTK in brez njega.

Postavke imajo isti vmesnik kot Gtk.MenuItem/CheckMenuItem v GTK3 (set_label, show, hide, set_sensitive, set_active,
get_active, connect("activate"/"toggled"), handler_block), da klicatelji ostanejo enaki.
"""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional

from gi.repository import Gio, GLib

SNI_POT = "/StatusNotifierItem"
MENI_POT = "/MenuBar"
STRAZAR = "org.kde.StatusNotifierWatcher"

VMESNIK = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="ContextMenu"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="Activate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="SecondaryActivate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="Scroll"><arg name="delta" type="i" direction="in"/><arg name="orientation" type="s" direction="in"/></method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus"><arg name="status" type="s"/></signal>
  </interface>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" name="parentId" direction="in"/><arg type="i" name="recursionDepth" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="u" name="revision" direction="out"/><arg type="(ia{sv}av)" name="layout" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" name="ids" direction="in"/><arg type="as" name="propertyNames" direction="in"/>
      <arg type="a(ia{sv})" name="properties" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" name="id" direction="in"/><arg type="s" name="name" direction="in"/><arg type="v" name="value" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" name="id" direction="in"/><arg type="s" name="eventId" direction="in"/>
      <arg type="v" name="data" direction="in"/><arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg type="a(isvu)" name="events" direction="in"/><arg type="ai" name="idErrors" direction="out"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" name="id" direction="in"/><arg type="b" name="needUpdate" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg type="ai" name="ids" direction="in"/><arg type="ai" name="updatesNeeded" direction="out"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <signal name="ItemsPropertiesUpdated">
      <arg type="a(ia{sv})" name="updatedProps"/><arg type="a(ias)" name="removedProps"/>
    </signal>
    <signal name="LayoutUpdated"><arg type="u" name="revision"/><arg type="i" name="parent"/></signal>
    <signal name="ItemActivationRequested"><arg type="i" name="id"/><arg type="u" name="timestamp"/></signal>
  </interface>
</node>"""


class Postavka:
    """Postavka menija v pladnju z vmesnikom Gtk.MenuItem (preklop=True: Gtk.CheckMenuItem, locilo=True: SeparatorMenuItem)."""

    def __init__(self, label: str = "", preklop: bool = False, locilo: bool = False) -> None:
        self.id = 0
        self.preklop, self.locilo = preklop, locilo
        self._label, self._vidna, self._omogocena, self._aktivna = label, True, True, False
        self._klici: Dict[int, tuple] = {}
        self._blokirani: set = set()
        self._naslednji = 1
        self._meni: Optional["Pladenj"] = None

    # -- signali (kot GObject)
    def connect(self, signal: str, fn: Callable, *argumenti) -> int:
        i = self._naslednji
        self._naslednji += 1
        self._klici[i] = (signal, fn, argumenti)
        return i

    def handler_block(self, i: int) -> None:
        self._blokirani.add(i)

    def handler_unblock(self, i: int) -> None:
        self._blokirani.discard(i)

    def _sprozi(self, signal: str) -> None:
        for i, (s, fn, argumenti) in list(self._klici.items()):
            if s == signal and i not in self._blokirani:
                fn(self, *argumenti)

    def _spremenjena(self) -> None:
        if self._meni is not None:
            self._meni.osvezi_meni()

    # -- vmesnik Gtk.MenuItem / CheckMenuItem
    def set_label(self, label: str) -> None:
        self._label = str(label)
        self._spremenjena()

    def get_label(self) -> str:
        return self._label

    def set_visible(self, vidna: bool) -> None:
        self._vidna = bool(vidna)
        self._spremenjena()

    def get_visible(self) -> bool:
        return self._vidna

    def show(self) -> None:
        self.set_visible(True)

    def hide(self) -> None:
        self.set_visible(False)

    def set_sensitive(self, omogocena: bool) -> None:
        self._omogocena = bool(omogocena)
        self._spremenjena()

    def get_sensitive(self) -> bool:
        return self._omogocena

    def set_active(self, aktivna: bool) -> None:
        if bool(aktivna) == self._aktivna:
            return
        self._aktivna = bool(aktivna)
        self._spremenjena()
        self._sprozi("toggled")

    def get_active(self) -> bool:
        return self._aktivna

    def aktiviraj(self) -> None:
        """Klik v meniju: preklop zamenja stanje (toggled), navadna postavka sprozi activate."""
        if self.locilo or not self._omogocena:
            return
        if self.preklop:
            self.set_active(not self._aktivna)
        self._sprozi("activate")

    def lastnosti(self) -> dict:
        if self.locilo:
            return {"type": GLib.Variant("s", "separator"), "visible": GLib.Variant("b", self._vidna)}
        d = {"label": GLib.Variant("s", self._label), "enabled": GLib.Variant("b", self._omogocena),
             "visible": GLib.Variant("b", self._vidna)}
        if self.preklop:
            d["toggle-type"] = GLib.Variant("s", "checkmark")
            d["toggle-state"] = GLib.Variant("i", 1 if self._aktivna else 0)
        return d


def _slikovne_tocke(pot: str) -> list:
    """Ikona iz datoteke kot IconPixmap (ARGB32 v omreznem vrstnem redu), v dveh velikostih."""
    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        izvor = GdkPixbuf.Pixbuf.new_from_file(pot)
    except Exception:  # noqa: BLE001 - brez slike ikona ostane samo z imenom
        return []
    izid = []
    for velikost in (32, 64):
        slika = izvor.scale_simple(velikost, velikost, GdkPixbuf.InterpType.BILINEAR)
        if slika is None:
            continue
        if not slika.get_has_alpha():
            slika = slika.add_alpha(False, 0, 0, 0)
        tocke, vrstica, sirina, visina = slika.get_pixels(), slika.get_rowstride(), slika.get_width(), slika.get_height()
        argb = bytearray(sirina * visina * 4)
        for y in range(visina):
            for x in range(sirina):
                i = y * vrstica + x * 4
                j = (y * sirina + x) * 4
                argb[j], argb[j + 1], argb[j + 2], argb[j + 3] = tocke[i + 3], tocke[i], tocke[i + 1], tocke[i + 2]
        izid.append((sirina, visina, bytes(argb)))
    return izid


class Pladenj:
    """Ikona StatusNotifierItem z menijem; ob_aktivaciji: levi klik na ikono."""

    _stevec = 0

    def __init__(self, ime: str, naslov: str, ikona: str, postavke: List[Postavka],
                 ob_aktivaciji: Optional[Callable[[], None]] = None, vodilo: Optional[Gio.DBusConnection] = None) -> None:
        self.ime, self.naslov = ime, naslov
        self.ikona_ime = "" if os.path.isabs(ikona) else ikona
        self.ikona_slika = _slikovne_tocke(ikona) if os.path.isabs(ikona) else []
        self.namig = ""
        self.ob_aktivaciji = ob_aktivaciji
        self.postavke = list(postavke)
        for i, p in enumerate(self.postavke, start=1):
            p.id, p._meni = i, self
        self.revizija = 1
        self._osvezitev = 0
        self._registracije: list = []
        self._ime_id = 0
        self._straza_id = 0
        Pladenj._stevec += 1
        self.ime_vodila = "org.kde.StatusNotifierItem-%d-%d" % (os.getpid(), Pladenj._stevec)
        self.vodilo = vodilo or Gio.bus_get_sync(Gio.BusType.SESSION, None)
        info = Gio.DBusNodeInfo.new_for_xml(VMESNIK)
        # Brez funkcije za lastnosti GDBus klice org.freedesktop.DBus.Properties poslje v _klic (Get/GetAll).
        self._registracije.append(self.vodilo.register_object(SNI_POT, info.lookup_interface("org.kde.StatusNotifierItem"),
                                                              self._klic, None, None))
        self._registracije.append(self.vodilo.register_object(MENI_POT, info.lookup_interface("com.canonical.dbusmenu"),
                                                              self._klic, None, None))
        self._ime_id = Gio.bus_own_name_on_connection(self.vodilo, self.ime_vodila, Gio.BusNameOwnerFlags.NONE, None, None)
        # Strazar (pladenj namizja) se lahko zazene za nami ali znova (ponovni zagon Cinnamona): vsakic se prijavimo.
        self._straza_id = Gio.bus_watch_name_on_connection(self.vodilo, STRAZAR, Gio.BusNameWatcherFlags.NONE,
                                                           self._strazar_je, None)

    # ------------------------------------------------------------------ javni vmesnik
    def nastavi_ikono(self, ikona: str) -> None:
        """Nova ikona (ime iz teme ali absolutna pot do slike); pladenj jo prebere ob signalu NewIcon."""
        self.ikona_ime = "" if os.path.isabs(ikona) else ikona
        self.ikona_slika = _slikovne_tocke(ikona) if os.path.isabs(ikona) else []
        self._signal(SNI_POT, "org.kde.StatusNotifierItem", "NewIcon", None)

    def nastavi_namig(self, besedilo: str) -> None:
        self.namig = str(besedilo or "")
        self._signal(SNI_POT, "org.kde.StatusNotifierItem", "NewToolTip", None)

    def osvezi_meni(self) -> None:
        """Sprememba postavke: en LayoutUpdated na obhod zanke, tudi ce se jih spremeni vec hkrati."""
        if self._osvezitev:
            return

        def zdaj() -> bool:
            self._osvezitev = 0
            self.revizija += 1
            self._signal(MENI_POT, "com.canonical.dbusmenu", "LayoutUpdated", GLib.Variant("(ui)", (self.revizija, 0)))
            return False
        self._osvezitev = GLib.idle_add(zdaj)

    def zapri(self) -> None:
        for r in self._registracije:
            try:
                self.vodilo.unregister_object(r)
            except Exception:  # noqa: BLE001
                pass
        self._registracije = []
        if self._straza_id:
            Gio.bus_unwatch_name(self._straza_id)
            self._straza_id = 0
        if self._ime_id:
            Gio.bus_unown_name(self._ime_id)
            self._ime_id = 0

    # ------------------------------------------------------------------ D-Bus
    def _strazar_je(self, vodilo, _ime, _lastnik) -> None:
        vodilo.call(STRAZAR, "/StatusNotifierWatcher", STRAZAR, "RegisterStatusNotifierItem",
                    GLib.Variant("(s)", (self.ime_vodila,)), None, Gio.DBusCallFlags.NONE, 5000, None, None)

    def _signal(self, pot: str, vmesnik: str, ime: str, parametri) -> None:
        try:
            self.vodilo.emit_signal(None, pot, vmesnik, ime, parametri)
        except Exception:  # noqa: BLE001 - vodilo je zaprto (izhod)
            pass

    def _lastnosti_sni(self) -> dict:
        return {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", self.ime),
            "Title": GLib.Variant("s", self.naslov),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            "IconName": GLib.Variant("s", self.ikona_ime),
            "IconPixmap": GLib.Variant("a(iiay)", self.ikona_slika),
            "OverlayIconName": GLib.Variant("s", ""),
            "AttentionIconName": GLib.Variant("s", ""),
            "IconThemePath": GLib.Variant("s", ""),
            "ToolTip": GLib.Variant("(sa(iiay)ss)", (self.ikona_ime, [], self.naslov, self.namig)),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", MENI_POT),
        }

    @staticmethod
    def _lastnosti_menija() -> dict:
        return {"Version": GLib.Variant("u", 3), "TextDirection": GLib.Variant("s", "ltr"),
                "Status": GLib.Variant("s", "normal"), "IconThemePath": GLib.Variant("as", [])}

    def _postavka(self, i: int) -> Optional[Postavka]:
        return self.postavke[i - 1] if 1 <= i <= len(self.postavke) else None

    def _lastnosti_postavke(self, i: int) -> dict:
        if i == 0:
            return {"children-display": GLib.Variant("s", "submenu")}
        p = self._postavka(i)
        return p.lastnosti() if p is not None else {}

    def _drevo(self, i: int) -> tuple:
        otroci = [GLib.Variant("(ia{sv}av)", (p.id, p.lastnosti(), [])) for p in self.postavke] if i == 0 else []
        return (i, self._lastnosti_postavke(i), otroci)

    def _klic(self, _vodilo, _posiljatelj, pot, vmesnik, metoda, parametri, klic) -> None:
        try:
            a = parametri.unpack()
            if vmesnik == "org.freedesktop.DBus.Properties":
                lastnosti = self._lastnosti_sni() if pot == SNI_POT else self._lastnosti_menija()
                if metoda == "GetAll":
                    klic.return_value(GLib.Variant("(a{sv})", (lastnosti,)))
                elif metoda == "Get" and a[1] in lastnosti:
                    klic.return_value(GLib.Variant("(v)", (lastnosti[a[1]],)))
                else:
                    klic.return_dbus_error("org.freedesktop.DBus.Error.InvalidArgs", "Lastnost ne obstaja")
                return
            if metoda in ("Activate", "SecondaryActivate"):
                klic.return_value(None)
                if self.ob_aktivaciji is not None:
                    self.ob_aktivaciji()
                return
            if metoda in ("ContextMenu", "Scroll"):
                klic.return_value(None)   # meni pokaze pladenj sam (dbusmenu)
                return
            if metoda == "GetLayout":
                klic.return_value(GLib.Variant("(u(ia{sv}av))", (self.revizija, self._drevo(int(a[0])))))
                return
            if metoda == "GetGroupProperties":
                ids = list(a[0]) or [0] + [p.id for p in self.postavke]
                klic.return_value(GLib.Variant("(a(ia{sv}))", ([(i, self._lastnosti_postavke(i)) for i in ids
                                                                 if i == 0 or self._postavka(i) is not None],)))
                return
            if metoda == "GetProperty":
                v = self._lastnosti_postavke(int(a[0])).get(a[1])
                if v is None:
                    klic.return_dbus_error("org.freedesktop.DBus.Error.InvalidArgs", "Lastnost ne obstaja")
                else:
                    klic.return_value(GLib.Variant("(v)", (v,)))
                return
            if metoda == "Event":
                klic.return_value(None)
                self._dogodek(int(a[0]), str(a[1]))
                return
            if metoda == "EventGroup":
                napake = [int(d[0]) for d in a[0] if self._postavka(int(d[0])) is None]
                klic.return_value(GLib.Variant("(ai)", (napake,)))
                for d in a[0]:
                    self._dogodek(int(d[0]), str(d[1]))
                return
            if metoda == "AboutToShow":
                klic.return_value(GLib.Variant("(b)", (False,)))
                return
            if metoda == "AboutToShowGroup":
                klic.return_value(GLib.Variant("(aiai)", ([], [])))
                return
            klic.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", metoda)
        except Exception as e:  # noqa: BLE001 - klic mora vedno dobiti odgovor
            try:
                klic.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(e))
            except Exception:  # noqa: BLE001 - odgovor je ze poslan
                pass

    def _dogodek(self, i: int, vrsta: str) -> None:
        p = self._postavka(i)
        if p is not None and vrsta == "clicked":
            p.aktiviraj()


def lastno_vodilo(naslov: Optional[str] = None) -> Gio.DBusConnection:
    """Lastna povezava z vodilom seje. Ikona SNI ima stalni poti (/StatusNotifierItem, /MenuBar): drugo ikono v istem
    procesu (kuverta poleg ikone Controla) lahko objavimo samo na drugi povezavi."""
    naslov = naslov or Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
    return Gio.DBusConnection.new_for_address_sync(
        naslov, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None, None)


class Kuverta:
    """Kuverta Sporocil v pultu Safeer OS (StatusNotifierItem, brez Qt in brez GTK3): ikona s stevilom neprebranih,
    levi klik ali postavka menija odpre plosco Sporocil. Vmesnik kot prejsnja os_lupina.Kuverta: nastavi(pot, opis)."""

    def __init__(self, ob_kliku: Callable[[], None], napis: str, vodilo: Optional[Gio.DBusConnection] = None) -> None:
        self._postavka = Postavka(napis)
        self._postavka.connect("activate", lambda *_a: ob_kliku())
        self.pladenj = Pladenj("safeer-os-sporocila", napis, "mail-unread-symbolic", [self._postavka],
                               ob_aktivaciji=ob_kliku, vodilo=vodilo or lastno_vodilo())

    def nastavi(self, pot_png: str, opis: str) -> None:
        self.pladenj.nastavi_ikono(pot_png)
        self.pladenj.nastavi_namig(opis)

    def zapri(self) -> None:
        self.pladenj.zapri()


__all__ = ["Postavka", "Pladenj", "Kuverta", "lastno_vodilo"]
