"""Stevilo neprebranih in obvestila namiznih programov, vstavljenih v Sporocila - iz SPLOSNIH virov seje D-Bus, brez
kode za posamezen program (lastnik, 15. 10. 2026: »ce storitvam kaj manjka in to znamo resiti, resimo«).

Viri po prednosti (kanal uporabi prvega, ki ga program oddaja):
  1. com.canonical.Unity.LauncherEntry »Update« (app_uri application://<ime>.desktop; count, count-visible, urgent):
     oddajajo ga Electron (app.setBadgeCount), Telegram Desktop, Thunderbird ...; Plank ga bere za znacke docka.
  2. StatusNotifierItem (ikona v pladnju): stanje NeedsAttention pomeni vsaj eno neprebrano (stevila ne pove).
  3. org.freedesktop.Notifications.Notify tega programa (po app_name): steje obvestila, dokler uporabnik ne odpre
     kanala. Rezerva za programe brez 1. in 2. (Viber). Za to loceno povezavo naredimo za opazovalca vodila
     (BecomeMonitor).
  4. Naslov okna (core/spletni_klepeti.neprebrano) - to bere kanal sam.

Zasebnost vira 3 (pregled 15. 10. 2026): opazovalec vidi obvestila VSEH programov, ce ga ne omejimo. Zato:
  * tece samo, ko je vklopljen vsaj en kanal namiznega programa (nastavi_obvestila(imena); prazno = ustavljen);
  * pravila vodila so najozja mogoca - klic Notify z arg0 (app_name) natanko enim od imen vgrajenih programov
    (»arg0='Viber'«): vodilo nam drugih obvestil sploh ne poslje;
  * iz sporocila preberemo SAMO app_name; povzetka in besedila obvestila ne beremo, ne hranimo in ne izpisujemo.

Ta modul samo poslusa in javlja: ob_znacki(desktop_id, stevilo), ob_pladnju(ime_predmeta, potrebuje_pozornost),
ob_obvestilu(app_name). Pripis kanalu naredi klicatelj (core/os_kanali_sporocil.py).
"""
from __future__ import annotations

import re
from typing import Callable, Iterable, Optional

LAUNCHER = "com.canonical.Unity.LauncherEntry"
SNI = "org.kde.StatusNotifierItem"
OBVESTILA = "org.freedesktop.Notifications"
#: Najvec pravil opazovalca (dbus-daemon: max_match_rules_per_connection je 512; nasih nekaj imen je dovolj).
NAJVEC_PRAVIL = 32
#: Ime programa v pravilu: brez narekovajev in nadzornih znakov (pravila vodila so niz; ime ne sme pravila razsiriti).
_VARNO_IME = re.compile(r"^[A-Za-z0-9 ._+-]{1,64}$")


def pravila_obvestil(imena: Iterable[str]) -> list:
    """Pravila za BecomeMonitor: samo klici Notify z app_name (arg0) natanko enim od imen. Ime v obliki, kot jo ima
    katalog, in v obliki z veliko/malo zacetnico - app_name je obcutljiv na velikost crk (»Signal«, »signal«)."""
    izid, videna = [], set()
    for ime in imena or ():
        ime = str(ime or "").strip()
        for oblika in (ime, ime.lower(), ime[:1].upper() + ime[1:]):
            if oblika in videna or not _VARNO_IME.match(oblika):
                continue
            videna.add(oblika)
            izid.append("type='method_call',interface='%s',member='Notify',arg0='%s'" % (OBVESTILA, oblika))
    return izid[:NAJVEC_PRAVIL]


def desktop_id(app_uri: str) -> str:
    """application://signal-desktop.desktop -> signal-desktop.desktop (drugace prazno)."""
    s = str(app_uri or "")
    return s[len("application://"):] if s.startswith("application://") else ""


def stevilo_iz_lastnosti(lastnosti: dict) -> Optional[int]:
    """count/count-visible/urgent iz LauncherEntry.Update -> stevilo ali None (lastnosti stevila ni). count-visible
    False pomeni 0; urgent brez stevila pomeni vsaj 1."""
    if not isinstance(lastnosti, dict):
        return None
    vidno = lastnosti.get("count-visible")
    if "count" in lastnosti:
        try:
            n = max(0, int(lastnosti["count"]))
        except (TypeError, ValueError):
            n = 0
        if vidno is False:
            return 0
        return n
    if vidno is False:
        return 0
    if lastnosti.get("urgent") is True:
        return 1
    return None


class Poslusalec:
    """Poslusa vire na vodilu seje (Gio). Brez seje D-Bus ne naredi nicesar."""

    def __init__(self, Gio, GLib, ob_znacki: Callable[[str, int], None] = None,
                 ob_pladnju: Callable[[str, bool], None] = None,
                 ob_obvestilu: Callable[[str], None] = None, naslov_vodila: str = "") -> None:
        self.Gio, self.GLib = Gio, GLib
        self.ob_znacki, self.ob_pladnju, self.ob_obvestilu = ob_znacki, ob_pladnju, ob_obvestilu
        self.vodilo = None
        self.opazovalec = None
        self._naslov = naslov_vodila
        #: Imena programov (casefold), katerih obvestila stejemo; prazno = opazovalec ne tece.
        self.imena_obvestil: frozenset = frozenset()
        self._narocila: list = []
        try:
            self.vodilo = (Gio.DBusConnection.new_for_address_sync(
                naslov_vodila, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
                if naslov_vodila else Gio.bus_get_sync(Gio.BusType.SESSION, None))
        except Exception as e:  # noqa: BLE001 - brez seje D-Bus (preizkusi, Flatpak brez vodila)
            print("[Sporocila] vodilo seje:", e, flush=True)
            return
        F = Gio.DBusSignalFlags.NONE
        self._narocila.append(self.vodilo.signal_subscribe(None, LAUNCHER, "Update", None, None, F, self._launcher))
        self._narocila.append(self.vodilo.signal_subscribe(None, SNI, "NewStatus", None, None, F, self._sni_stanje))

    # ------------------------------------------------------------------ 1. LauncherEntry
    def _launcher(self, _v, _posiljatelj, _pot, _vmesnik, _signal, parametri, *_a) -> None:
        try:
            app_uri, lastnosti = parametri.unpack()
        except Exception:  # noqa: BLE001
            return
        did = desktop_id(app_uri)
        n = stevilo_iz_lastnosti(lastnosti)
        if did and n is not None and self.ob_znacki is not None:
            self.ob_znacki(did, n)

    # ------------------------------------------------------------------ 2. StatusNotifierItem
    def _sni_stanje(self, vodilo, posiljatelj, pot, _vmesnik, _signal, parametri, *_a) -> None:
        try:
            stanje = str(parametri.unpack()[0])
        except Exception:  # noqa: BLE001
            return

        def prebrano(v, rezultat, *_):
            try:
                ime = str(v.call_finish(rezultat).unpack()[0])
            except Exception:  # noqa: BLE001 - predmet brez lastnosti Id
                return
            if self.ob_pladnju is not None:
                self.ob_pladnju(ime, stanje == "NeedsAttention")
        vodilo.call(posiljatelj, pot, "org.freedesktop.DBus.Properties", "Get",
                    self.GLib.Variant("(ss)", (SNI, "Id")), self.GLib.VariantType.new("(v)"),
                    self.Gio.DBusCallFlags.NONE, 2000, None, prebrano)

    # ------------------------------------------------------------------ 3. obvestila (opazovalec Notify)
    def nastavi_obvestila(self, imena: Iterable[str]) -> bool:
        """Obvestila katerih programov stejemo (app_name). Prazno: opazovalec se ustavi. Ob spremembi imen se opazovalec
        naredi znova (pravil opazovalca ni mogoce spremeniti). Vrne, ali opazovalec tece."""
        nova = frozenset(str(i).casefold() for i in (imena or ()) if str(i or "").strip())
        pravila = pravila_obvestil(imena) if self.ob_obvestilu is not None else []
        if nova == self.imena_obvestil and (self.opazovalec is not None) == bool(pravila):
            return self.opazovalec is not None
        self._ustavi_opazovanje()
        self.imena_obvestil = nova if pravila else frozenset()
        if pravila and self.vodilo is not None:
            self._zacni_opazovanje(pravila)
        return self.opazovalec is not None

    def _zacni_opazovanje(self, pravila: list) -> None:
        """Loceno povezavo naredi za opazovalca (BecomeMonitor) s pravili pravila_obvestil (samo Notify izbranih
        programov)."""
        Gio = self.Gio
        try:
            naslov = self._naslov or Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
            self.opazovalec = Gio.DBusConnection.new_for_address_sync(
                naslov, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                None, None)
            self.opazovalec.add_filter(self._filter)
            self.opazovalec.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus.Monitoring",
                                      "BecomeMonitor", self.GLib.Variant("(asu)", (list(pravila), 0)),
                                      None, Gio.DBusCallFlags.NONE, 2000, None)
        except Exception as e:  # noqa: BLE001 - vodilo ne dovoli opazovanja (npr. Flatpak): vir 3 ni na voljo
            print("[Sporocila] opazovanje obvestil ni mogoce:", e, flush=True)
            self._ustavi_opazovanje()

    def _ustavi_opazovanje(self) -> None:
        if self.opazovalec is not None:
            try:
                self.opazovalec.close_sync(None)
            except Exception:  # noqa: BLE001
                pass
            self.opazovalec = None

    def _filter(self, _povezava, sporocilo, dohodno):
        try:
            if (dohodno and sporocilo.get_member() == "Notify" and sporocilo.get_interface() == OBVESTILA):
                telo = sporocilo.get_body()
                if telo is not None and telo.n_children() >= 1:
                    # Samo app_name (arg0); povzetka in besedila obvestila ne beremo (zasebnost).
                    app = telo.get_child_value(0).get_string()
                    if app.casefold() in self.imena_obvestil and self.ob_obvestilu is not None:
                        self.GLib.idle_add(lambda: (self.ob_obvestilu(app), False)[1])
                return None      # opazovani klic ni za nas: ne obdelujemo ga naprej
        except Exception:  # noqa: BLE001 - filter ne sme podreti povezave
            pass
        return sporocilo         # ostalo (odgovor na BecomeMonitor) gre naprej, sicer klic caka do poteka

    def ustavi(self) -> None:
        for n in self._narocila:
            try:
                self.vodilo.signal_unsubscribe(n)
            except Exception:  # noqa: BLE001
                pass
        self._narocila = []
        self._ustavi_opazovanje()
        self.imena_obvestil = frozenset()
