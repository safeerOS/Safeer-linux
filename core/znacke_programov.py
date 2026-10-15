"""Stevilo neprebranih in obvestila namiznih programov, vstavljenih v Sporocila - iz SPLOSNIH virov seje D-Bus, brez
kode za posamezen program (lastnik, 15. 10. 2026: »ce storitvam kaj manjka in to znamo resiti, resimo«).

Viri po prednosti (kanal uporabi prvega, ki ga program oddaja):
  1. com.canonical.Unity.LauncherEntry »Update« (app_uri application://<ime>.desktop; count, count-visible, urgent):
     oddajajo ga Electron (app.setBadgeCount), Telegram Desktop, Thunderbird ...; Plank ga bere za znacke docka.
  2. StatusNotifierItem (ikona v pladnju): stanje NeedsAttention pomeni vsaj eno neprebrano (stevila ne pove).
  3. org.freedesktop.Notifications.Notify tega programa (po app_name): steje obvestila, dokler uporabnik ne odpre
     kanala. Za to se loceno povezavo naredimo za opazovalca vodila (BecomeMonitor) - samo za klice Notify.
  4. Naslov okna (core/spletni_klepeti.neprebrano) - to bere kanal sam.

Ta modul samo poslusa in javlja: ob_znacki(desktop_id, stevilo), ob_pladnju(ime_predmeta, potrebuje_pozornost),
ob_obvestilu(app_name, povzetek, besedilo). Pripis kanalu naredi klicatelj (core/os_kanali_sporocil.py).
"""
from __future__ import annotations

from typing import Callable, Optional

LAUNCHER = "com.canonical.Unity.LauncherEntry"
SNI = "org.kde.StatusNotifierItem"
OBVESTILA = "org.freedesktop.Notifications"


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
                 ob_obvestilu: Callable[[str, str, str], None] = None, naslov_vodila: str = "") -> None:
        self.Gio, self.GLib = Gio, GLib
        self.ob_znacki, self.ob_pladnju, self.ob_obvestilu = ob_znacki, ob_pladnju, ob_obvestilu
        self.vodilo = None
        self.opazovalec = None
        self._narocila: list = []
        try:
            self.vodilo = (Gio.DBusConnection.new_for_address_sync(
                naslov_vodila, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
                if naslov_vodila else Gio.bus_get_sync(Gio.BusType.SESSION, None))
        except Exception as e:  # noqa: BLE001 - brez seje D-Bus (preizkusi, Flatpak brez vodila)
            print("[Sporocila] vodilo seje:", e, flush=True)
            return
        self._naslov = naslov_vodila
        F = Gio.DBusSignalFlags.NONE
        self._narocila.append(self.vodilo.signal_subscribe(None, LAUNCHER, "Update", None, None, F, self._launcher))
        self._narocila.append(self.vodilo.signal_subscribe(None, SNI, "NewStatus", None, None, F, self._sni_stanje))
        if ob_obvestilu is not None:
            self._zacni_opazovanje()

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
    def _zacni_opazovanje(self) -> None:
        """Loceno povezavo naredi za opazovalca (BecomeMonitor): vidi samo klice Notify, nic drugega."""
        Gio = self.Gio
        try:
            naslov = self._naslov or Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
            self.opazovalec = Gio.DBusConnection.new_for_address_sync(
                naslov, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                None, None)
            self.opazovalec.add_filter(self._filter)
            self.opazovalec.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus.Monitoring",
                                      "BecomeMonitor",
                                      self.GLib.Variant("(asu)", (["type='method_call',interface='%s',member='Notify'"
                                                                   % OBVESTILA], 0)),
                                      None, Gio.DBusCallFlags.NONE, 2000, None)
        except Exception as e:  # noqa: BLE001 - vodilo ne dovoli opazovanja: vir 3 ni na voljo
            print("[Sporocila] opazovanje obvestil ni mogoce:", e, flush=True)
            self.opazovalec = None

    def _filter(self, _povezava, sporocilo, dohodno):
        try:
            if (dohodno and sporocilo.get_member() == "Notify" and sporocilo.get_interface() == OBVESTILA):
                telo = sporocilo.get_body()
                if telo is not None and telo.n_children() >= 5:
                    app = telo.get_child_value(0).get_string()
                    povzetek = telo.get_child_value(3).get_string()
                    besedilo = telo.get_child_value(4).get_string()
                    self.GLib.idle_add(lambda: (self.ob_obvestilu(app, povzetek, besedilo), False)[1])
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
        if self.opazovalec is not None:
            try:
                self.opazovalec.close_sync(None)
            except Exception:  # noqa: BLE001
                pass
            self.opazovalec = None
