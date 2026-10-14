"""Ena pot obvestil namizja (core/obvestila.py, lastnik 15. 10. 2026: »vse je en proces«).

Prej: Gio.Application.send_notification, surovi D-Bus Notify in notify-send s tremi imeni programa. Preverimo:
  - v kodi Safeer OS in Controla ni vec notify-send (v Flatpaku ga ni, vsako obvestilo je bil svoj proces);
  - s Safeer OS v procesu gre obvestilo prek njegove Gio.Application: stalen id, ikona safeer-os, gumbi delajo;
  - brez nje gre neposredno po D-Busu (lazni streznik obvestil na zasebnem vodilu): ime Safeer Control, zamenjava
    obvestila z istim id, gumb izvede klic;
  - prosnja za dostop (core/link_dostop) gre po isti poti in ima dejanja na obeh aplikacijah.
"""
import os
import re
import shutil
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from gi.repository import Gio, GLib
except Exception:  # noqa: BLE001 - brez PyGObject
    Gio = None

from core import en_proces, obvestila  # noqa: E402


def _pocakaj(pogoj, cas: float = 3.0) -> bool:
    kontekst = GLib.MainContext.default()
    konec = time.monotonic() + cas
    while time.monotonic() < konec:
        while kontekst.pending():
            kontekst.iteration(False)
        if pogoj():
            return True
        time.sleep(0.01)
    return pogoj()


class BrezNotifySend(unittest.TestCase):
    def test_koda_os_in_controla_ne_klice_notify_send(self):
        datoteke = [os.path.join(KOREN, "safeer_os.py"), os.path.join(KOREN, "safeer_control.py")]
        for mapa, _, imena in os.walk(os.path.join(KOREN, "core")):
            datoteke += [os.path.join(mapa, i) for i in imena if i.endswith(".py")]
        for pot in datoteke:
            with open(pot, encoding="utf-8") as f:
                vir = f.read()
            self.assertFalse(re.search(r"[\"']notify-send[\"']", vir), pot)

    def test_klicatelji_gredo_skozi_modul(self):
        for pot, niz in (("safeer_control.py", "obvestila.poslji("), ("core/safeer_link.py", "obvestila.poslji("),
                         ("core/link_hub_streznik.py", "obvestila.poslji("), ("core/link_dostop.py", "obvestila.poslji_gio(")):
            with open(os.path.join(KOREN, pot), encoding="utf-8") as f:
                self.assertIn(niz, f.read(), pot)


class _App:
    """Gio.Application v malem: dejanja in poslana obvestila."""

    def __init__(self):
        self.dejanja, self.poslana, self.umaknjena = {}, [], []

    def get_is_registered(self):
        return True

    def lookup_action(self, ime):
        return self.dejanja.get(ime)

    def add_action(self, d):
        self.dejanja[d.get_name()] = d

    def send_notification(self, ident, o):
        self.poslana.append((ident, o))

    def withdraw_notification(self, ident):
        self.umaknjena.append(ident)


@unittest.skipUnless(Gio is not None, "potrebuje PyGObject")
class PrekSafeerOS(unittest.TestCase):
    def setUp(self):
        self.os_app, self.control = _App(), _App()
        en_proces.nastavi_os(self.os_app)
        self.addCleanup(en_proces.nastavi_os, None)

    def test_obvestilo_gre_pod_safeer_os_z_gumbi(self):
        klici = []
        ident = obvestila.poslji("Naslov", "Besedilo", "safeer-x", gumbi=[("da", "Da", lambda: klici.append("da"))],
                                 privzeto=lambda: klici.append("klik"), app=self.control)
        self.assertEqual(ident, "safeer-x")
        self.assertEqual(self.control.poslana, [], "Control v procesu Safeer OS ne posilja svojih obvestil")
        self.assertEqual([i for i, _o in self.os_app.poslana], ["safeer-x"])
        dejanje = self.os_app.dejanja[obvestila.DEJANJE]
        dejanje.activate(GLib.Variant("s", "safeer-x|da"))
        dejanje.activate(GLib.Variant("s", "safeer-x|default"))
        dejanje.activate(GLib.Variant("s", "safeer-x|neznan"))
        dejanje.activate(GLib.Variant("s", "drug|da"))
        self.assertEqual(klici, ["da", "klik"])
        self.assertEqual(obvestila.ikona(self.control), "safeer-os")

    def test_isti_id_zamenja_gumbe_in_umik(self):
        klici = []
        obvestila.poslji("A", "", "safeer-y", gumbi=[("a", "A", lambda: klici.append("a"))])
        obvestila.poslji("B", "", "safeer-y", gumbi=[("b", "B", lambda: klici.append("b"))])
        self.os_app.dejanja[obvestila.DEJANJE].activate(GLib.Variant("s", "safeer-y|a"))
        self.os_app.dejanja[obvestila.DEJANJE].activate(GLib.Variant("s", "safeer-y|b"))
        self.assertEqual(klici, ["b"])
        obvestila.umakni("safeer-y")
        self.assertEqual(self.os_app.umaknjena, ["safeer-y"])
        self.os_app.dejanja[obvestila.DEJANJE].activate(GLib.Variant("s", "safeer-y|b"))
        self.assertEqual(klici, ["b"], "umaknjeno obvestilo nima vec gumbov")

    def test_prosnja_za_dostop_pod_safeer_os(self):
        from core import link_dostop
        link_dostop.registriraj_dejanja(self.control, Gio, GLib, mock.Mock(), mock.Mock(), mock.Mock())
        for app in (self.control, self.os_app):
            self.assertTrue({link_dostop.DEJANJE_DOVOLI, link_dostop.DEJANJE_ZAVRNI, link_dostop.DEJANJE_NAPRAVE}
                            <= set(app.dejanja))
        ident = link_dostop.poslji_obvestilo(self.control, Gio, GLib, {"jedro": "a" * 64, "ime": "Telefon", "zmoznost": "d"}, "sl")
        self.assertEqual([i for i, _o in self.os_app.poslana], [ident])
        self.assertEqual(self.control.poslana, [])


@unittest.skipUnless(Gio is not None and shutil.which("dbus-daemon"), "potrebuje PyGObject in dbus-daemon")
class PoDBusu(unittest.TestCase):
    """Brez Safeer OS v procesu: org.freedesktop.Notifications (lazni streznik na zasebnem vodilu seje)."""

    def setUp(self):
        en_proces.nastavi_os(None)
        self.vodilo_test = Gio.TestDBus.new(Gio.TestDBusFlags.NONE)
        self.vodilo_test.up()
        self.streznik = Gio.DBusConnection.new_for_address_sync(
            self.vodilo_test.get_bus_address(), Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        self.klici = []
        info = Gio.DBusNodeInfo.new_for_xml(
            '<node><interface name="org.freedesktop.Notifications"><method name="Notify">'
            '<arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/>'
            '<arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="as" direction="in"/>'
            '<arg type="a{sv}" direction="in"/><arg type="i" direction="in"/><arg type="u" direction="out"/></method>'
            '<method name="CloseNotification"><arg type="u" direction="in"/></method>'
            '<signal name="ActionInvoked"><arg type="u"/><arg type="s"/></signal></interface></node>')

        def klic(_v, _p, _pot, _vm, metoda, parametri, k):
            self.klici.append((metoda, parametri.unpack()))
            k.return_value(GLib.Variant("(u)", (7,)) if metoda == "Notify" else None)
        self.reg = self.streznik.register_object("/org/freedesktop/Notifications", info.interfaces[0], klic, None, None)
        Gio.bus_own_name_on_connection(self.streznik, "org.freedesktop.Notifications", Gio.BusNameOwnerFlags.NONE, None, None)
        # Modul drzi svojo povezavo z vodilom seje (Gio.bus_get_sync): v preizkusu je to zasebno vodilo.
        self.seja = Gio.DBusConnection.new_for_address_sync(
            self.vodilo_test.get_bus_address(), Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        p = mock.patch.object(obvestila, "_dejanja_narocena", False)
        p.start()
        self.addCleanup(p.stop)
        p2 = mock.patch.object(Gio, "bus_get_sync", lambda *_a: self.seja)
        p2.start()
        self.addCleanup(p2.stop)

    def tearDown(self):
        self.streznik.unregister_object(self.reg)
        for v in (self.streznik, self.seja):
            v.close_sync(None)
        self.vodilo_test.down()

    def test_notify_zamenjava_in_gumb(self):
        izvedeno = []
        obvestila.poslji("Naslov", "Telo", "safeer-z", gumbi=[("odpri", "Odpri", lambda: izvedeno.append(1))], cas_ms=5000)
        self.assertTrue(_pocakaj(lambda: len(self.klici) == 1))
        metoda, (ime, zamenjaj, ikona, naslov, telo, dejanja, namigi, cas) = self.klici[0]
        self.assertEqual((metoda, ime, zamenjaj, ikona, naslov, telo, dejanja, cas),
                         ("Notify", "Safeer Control", 0, "safeer-control", "Naslov", "Telo", ["odpri", "Odpri"], 5000))
        self.assertIn("urgency", namigi)
        self.assertTrue(_pocakaj(lambda: 7 in obvestila._dejanja))
        obvestila.poslji("Naslov 2", "", "safeer-z")
        self.assertTrue(_pocakaj(lambda: len(self.klici) == 2))
        self.assertEqual(self.klici[1][1][1], 7, "isti id zamenja obvestilo (replaces_id)")
        self.streznik.emit_signal(None, "/org/freedesktop/Notifications", "org.freedesktop.Notifications",
                                  "ActionInvoked", GLib.Variant("(us)", (7, "odpri")))
        self.assertTrue(_pocakaj(lambda: izvedeno == [1]))
        obvestila.umakni("safeer-z")
        self.assertTrue(_pocakaj(lambda: ("CloseNotification", (7,)) in self.klici))


if __name__ == "__main__":
    unittest.main()
