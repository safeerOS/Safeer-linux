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
            # Namig enak naslovu bi pult pokazal dvakrat (»Sporočila / Sporočila«, lastnik 17. 10. 2026): takrat brez opisa.
            "ToolTip": GLib.Variant("(sa(iiay)ss)", (self.ikona_ime, [], self.naslov,
                                                     "" if self.namig.strip() == self.naslov.strip() else self.namig)),
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


#: Safeer Scit v pultu (besedila v vseh jezikih Safeer OS). {n}: stevilo blokiranih oziroma minut premora.
BESEDILA_SCITA = {
    "sl": {"naslov": "Safeer Ščit", "vklopljen": "Vklopljen – blokiranih {n}", "premor": "Na premoru še {n} min",
           "brez_omrezja": "Vklopljen – čaka na omrežje", "izklopljen": "Izklopljen",
           "ni_na_voljo": "Ni na voljo na tem računalniku", "napaka": "Napaka – odpri nastavitve Ščita",
           "pripravljam": "Vklapljam …", "izklapljam": "Izklapljam …", "vklopi": "Vklopi Ščit", "izklopi": "Izklopi Ščit",
           "nastavitve": "Nastavitve Ščita"},
    "en": {"naslov": "Safeer Shield", "vklopljen": "On – {n} blocked", "premor": "Paused for {n} more min",
           "brez_omrezja": "On – waiting for a network", "izklopljen": "Off",
           "ni_na_voljo": "Not available on this computer", "napaka": "Error – open Shield settings",
           "pripravljam": "Turning on …", "izklapljam": "Turning off …", "vklopi": "Turn Shield on", "izklopi": "Turn Shield off",
           "nastavitve": "Shield settings"},
    "de": {"naslov": "Safeer Schild", "vklopljen": "An – {n} blockiert", "premor": "Noch {n} Min. pausiert",
           "brez_omrezja": "An – wartet auf ein Netzwerk", "izklopljen": "Aus",
           "ni_na_voljo": "Auf diesem Computer nicht verfügbar", "napaka": "Fehler – Schild-Einstellungen öffnen",
           "pripravljam": "Wird eingeschaltet …", "izklapljam": "Wird ausgeschaltet …", "vklopi": "Schild einschalten", "izklopi": "Schild ausschalten",
           "nastavitve": "Schild-Einstellungen"},
    "es": {"naslov": "Escudo Safeer", "vklopljen": "Activado – {n} bloqueados", "premor": "En pausa {n} min más",
           "brez_omrezja": "Activado – esperando una red", "izklopljen": "Desactivado",
           "ni_na_voljo": "No disponible en este ordenador", "napaka": "Error – abre los ajustes del Escudo",
           "pripravljam": "Activando…", "izklapljam": "Desactivando…", "vklopi": "Activar el Escudo", "izklopi": "Desactivar el Escudo",
           "nastavitve": "Ajustes del Escudo"},
    "fr": {"naslov": "Bouclier Safeer", "vklopljen": "Activé – {n} bloqués", "premor": "En pause encore {n} min",
           "brez_omrezja": "Activé – en attente d'un réseau", "izklopljen": "Désactivé",
           "ni_na_voljo": "Indisponible sur cet ordinateur", "napaka": "Erreur – ouvrir les réglages du Bouclier",
           "pripravljam": "Activation…", "izklapljam": "Désactivation…", "vklopi": "Activer le Bouclier", "izklopi": "Désactiver le Bouclier",
           "nastavitve": "Réglages du Bouclier"},
    "it": {"naslov": "Scudo Safeer", "vklopljen": "Attivo – {n} bloccati", "premor": "In pausa per altri {n} min",
           "brez_omrezja": "Attivo – in attesa di una rete", "izklopljen": "Disattivato",
           "ni_na_voljo": "Non disponibile su questo computer", "napaka": "Errore – apri le impostazioni dello Scudo",
           "pripravljam": "Attivazione…", "izklapljam": "Disattivazione…", "vklopi": "Attiva lo Scudo", "izklopi": "Disattiva lo Scudo",
           "nastavitve": "Impostazioni dello Scudo"},
}

#: Napake Scita, ob katerih ikona pokaze napako (»ni_omrezja« ni napaka: Scit zacne, ko se racunalnik poveze).
NAPAKE_SCITA = ("pravilo", "vrata", "ni_resolved", "lastni_dns")


def vrsta_scita(stanje: dict, zaposlen: str = "") -> str:
    """Stanje Scita (os_scit.Scit.stanje()) za ikono v pultu: vklopljen, izklopljen, napaka ali pripravljam.
    zaposlen: »vklop« ali »izklop«, ko preklop iz pulta se tece."""
    s = stanje or {}
    if zaposlen:
        return "pripravljam"
    if s.get("napaka") in NAPAKE_SCITA or (s.get("vklop") and not s.get("mozno", True)):
        return "napaka"
    if not s.get("vklop"):
        return "izklopljen"
    # Vklopljen, a razresevalnik se zaganja (zacetek seje) - ni napaka.
    return "vklopljen" if s.get("tece") or s.get("napaka") == "ni_omrezja" else "pripravljam"


def opis_scita(stanje: dict, vrsta: str, besedila: dict, zaposlen: str = "") -> str:
    s = stanje or {}
    if vrsta == "pripravljam" and zaposlen == "izklop":
        return besedila["izklapljam"]
    if vrsta == "vklopljen":
        if s.get("napaka") == "ni_omrezja":
            return besedila["brez_omrezja"]
        if int(s.get("premor") or 0) > 0:
            return besedila["premor"].format(n=max(1, (int(s["premor"]) + 59) // 60))
        return besedila["vklopljen"].format(n=int(s.get("blokiranih") or 0))
    if vrsta == "izklopljen" and s.get("mozno") is False:
        return besedila["ni_na_voljo"]
    return besedila[vrsta]


def ikona_scita(vrsta: str, mapa: str, velikost: int = 48, barve: Optional[dict] = None) -> str:
    """Ikona Scita za pult: crtni scit (kot ostale ikone pulta, vidna na temnem pultu), v njem stanje - kljukica
    (vklopljen), precrtano (izklopljen), klicaj (napaka), tri pike (pripravljam). Namenoma ne poln zeleni scit na
    ploscici kot ikona Safeer Control. barve: os_lupina.tokeni() (assets/os/tokens.css) - poda jih Safeer OS, ker je ta
    modul tudi v tovoru Controla brez os_lupina. Narise cairo, vrne pot do PNG v predpomnilniku."""
    import cairo
    t = barve or {}
    barva = lambda ime, privzeta: tuple(x / 255.0 for x in t.get(ime, privzeta)[:3])  # noqa: E731
    svetla, medla = barva("besedilo", (234, 242, 255)), barva("tise", (147, 169, 196))
    os.makedirs(mapa, exist_ok=True)
    pot = os.path.join(mapa, "scit-v1-%s.png" % vrsta)
    if os.path.isfile(pot):
        return pot
    v = float(velikost)
    p = cairo.ImageSurface(cairo.FORMAT_ARGB32, velikost, velikost)
    c = cairo.Context(p)
    c.scale(v / 48.0, v / 48.0)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    # Obris kot znak Safeer (assets/os/znak.svg), na mrezi 48.
    c.move_to(24, 4)
    c.line_to(40, 10)
    c.line_to(40, 22)
    c.curve_to(40, 32.5, 33.5, 40, 24, 44.5)
    c.curve_to(14.5, 40, 8, 32.5, 8, 22)
    c.line_to(8, 10)
    c.close_path()
    c.set_line_width(3.6)
    c.set_source_rgb(*(medla if vrsta in ("izklopljen", "pripravljam") else svetla))
    c.stroke()
    if vrsta == "vklopljen":
        c.set_source_rgb(*barva("ok", (127, 224, 182)))
        c.set_line_width(4.6)
        c.move_to(16, 24)
        c.line_to(22, 30)
        c.line_to(32, 18)
        c.stroke()
    elif vrsta == "izklopljen":
        c.set_source_rgb(*medla)
        c.set_line_width(3.6)
        c.move_to(6, 42)
        c.line_to(42, 6)
        c.stroke()
    elif vrsta == "napaka":
        c.set_source_rgb(*barva("rdeca", (255, 107, 107)))
        c.set_line_width(4.8)
        c.move_to(24, 14)
        c.line_to(24, 26)
        c.stroke()
        c.arc(24, 33.5, 2.9, 0, 6.2832)
        c.fill()
    else:
        c.set_source_rgb(*medla)
        for x in (17, 24, 31):
            c.arc(x, 24, 2.6, 0, 6.2832)
            c.fill()
    zacasna = pot + ".tmp"
    p.write_to_png(zacasna)
    os.replace(zacasna, pot)
    return pot


def ikona_linka(povezan: bool, mapa: str, velikost: int = 48) -> str:
    """Ikona Safeer Control (Safeer Link) za pult: crtni racunalnik in telefon, povezana s piko na crti - v istem slogu
    kot Scit in ikone pulta, ne poln zeleni scit (lastnik, 17. 10. 2026: v pultu so bili trije scitje - Control,
    Scit, posodobitve). Brez povezave medla. Narise cairo, vrne pot do PNG v predpomnilniku."""
    import cairo
    svetla, medla, zelena = (234 / 255, 242 / 255, 1.0), (147 / 255, 169 / 255, 196 / 255), (127 / 255, 224 / 255, 182 / 255)
    os.makedirs(mapa, exist_ok=True)
    pot = os.path.join(mapa, "link-v1-%s.png" % ("povezan" if povezan else "ni"))
    if os.path.isfile(pot):
        return pot
    v = float(velikost)
    p = cairo.ImageSurface(cairo.FORMAT_ARGB32, velikost, velikost)
    c = cairo.Context(p)
    c.scale(v / 48.0, v / 48.0)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_source_rgb(*(svetla if povezan else medla))
    c.set_line_width(3.4)

    def okvir(x, y, s, h, r):
        c.new_sub_path()
        c.arc(x + s - r, y + r, r, -1.5708, 0)
        c.arc(x + s - r, y + h - r, r, 0, 1.5708)
        c.arc(x + r, y + h - r, r, 1.5708, 3.1416)
        c.arc(x + r, y + r, r, 3.1416, 4.7124)
        c.close_path()
    okvir(4, 9, 25, 18, 2.5)       # zaslon racunalnika
    c.stroke()
    c.move_to(11, 33)               # podstavek
    c.line_to(22, 33)
    c.stroke()
    okvir(33, 17, 12, 22, 2.5)      # telefon
    c.stroke()
    c.move_to(37.5, 35)
    c.line_to(40.5, 35)
    c.stroke()
    # povezava: crta od racunalnika do telefona s piko
    c.set_source_rgb(*(zelena if povezan else medla))
    c.set_line_width(2.6)
    c.move_to(29, 22)
    c.line_to(33, 22)
    c.stroke()
    c.arc(16.5, 18, 3.2, 0, 6.2832)
    c.fill()
    zacasna = pot + ".tmp"
    p.write_to_png(zacasna)
    os.replace(zacasna, pot)
    return pot


class ScitPult:
    """Safeer Scit v pultu poleg kuverte (StatusNotifierItem, isti sklad kot Kuverta): ikona kaze stanje, namig
    »Safeer Scit« z opisom, levi klik odpre nastavitve Scita; meni Vklopi/Izklopi in Nastavitve Scita.
    ob_preklopu(vklop) naj Scit vklopi ali izklopi (obstojeca logika z vprasanjem za geslo) in potem poklice osvezi."""

    def __init__(self, besedila: dict, ob_nastavitvah: Callable[[], None], ob_preklopu: Callable[[bool], None],
                 mapa: str, vodilo: Optional[Gio.DBusConnection] = None, barve: Optional[dict] = None) -> None:
        self.besedila, self.mapa, self.barve = besedila, mapa, barve
        self.vrsta, self.opis = "", ""
        self._stanje: dict = {}
        self._ob_preklopu = ob_preklopu
        self.preklop = Postavka(besedila["vklopi"])
        self.preklop.connect("activate", lambda *_a: self._preklopi())
        self.nastavitve = Postavka(besedila["nastavitve"])
        self.nastavitve.connect("activate", lambda *_a: ob_nastavitvah())
        self.pladenj = Pladenj("safeer-os-scit", besedila["naslov"], ikona_scita("izklopljen", mapa, barve=barve),
                               [self.preklop, Postavka(locilo=True), self.nastavitve],
                               ob_aktivaciji=ob_nastavitvah, vodilo=vodilo or lastno_vodilo())

    def _preklopi(self) -> None:
        vklop = not self._stanje.get("vklop")
        if self.vrsta == "pripravljam" or (vklop and self._stanje.get("mozno") is False):
            return
        self.osvezi(self._stanje, zaposlen="vklop" if vklop else "izklop")
        self._ob_preklopu(vklop)

    def osvezi(self, stanje: dict, zaposlen: str = "") -> None:
        self._stanje = dict(stanje or {})
        vrsta = vrsta_scita(self._stanje, zaposlen)
        opis = opis_scita(self._stanje, vrsta, self.besedila, zaposlen)
        self.preklop.set_label(self.besedila["izklopi" if self._stanje.get("vklop") else "vklopi"])
        self.preklop.set_sensitive(vrsta != "pripravljam" and
                                   (bool(self._stanje.get("vklop")) or self._stanje.get("mozno") is not False))
        if vrsta != self.vrsta:
            self.vrsta = vrsta
            self.pladenj.nastavi_ikono(ikona_scita(vrsta, self.mapa, barve=self.barve))
        if opis != self.opis:
            self.opis = opis
            self.pladenj.nastavi_namig(opis)

    def zapri(self) -> None:
        self.pladenj.zapri()


__all__ = ["Postavka", "Pladenj", "Kuverta", "ScitPult", "BESEDILA_SCITA", "vrsta_scita", "opis_scita", "ikona_scita",
           "lastno_vodilo"]
