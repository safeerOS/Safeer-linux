"""Ikona v pladnju brez GTK3 (core/pladenj_sni.py): StatusNotifierItem in meni dbusmenu na zasebnem vodilu D-Bus.

Preverimo, kar pladenj namizja (xapp-sn-watcher v Linux Mint, KDE) res klice: prijavo pri strazarju, lastnosti ikone,
drevo menija, klik na postavko in osvezitev menija po spremembi. Brez dbus-daemon se preizkus preskoci.
"""

import os
import shutil
import sys
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

try:
    from gi.repository import Gio, GLib
except Exception:  # noqa: BLE001 - brez PyGObject
    Gio = None


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


@unittest.skipUnless(Gio is not None and shutil.which("dbus-daemon"), "potrebuje PyGObject in dbus-daemon")
class PladenjSni(unittest.TestCase):
    def setUp(self):
        self.vodilo_test = Gio.TestDBus.new(Gio.TestDBusFlags.NONE)
        self.vodilo_test.up()
        # Lastni povezavi (pladenj, odjemalec): skupno vodilo seje bi TestDBus.down() cakal 30 s.
        self.vodilo, self.pladenj_vodilo = (Gio.DBusConnection.new_for_address_sync(
            self.vodilo_test.get_bus_address(), Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None) for _ in range(2))
        # Lazni strazar: zabelezi prijavo ikone (kot xapp-sn-watcher).
        self.prijave = []
        info = Gio.DBusNodeInfo.new_for_xml(
            '<node><interface name="org.kde.StatusNotifierWatcher"><method name="RegisterStatusNotifierItem">'
            '<arg type="s" direction="in"/></method></interface></node>')

        def klic(_v, _p, _pot, _vm, metoda, parametri, k):
            self.prijave.append(parametri.unpack()[0])
            k.return_value(None)
        self.strazar = self.vodilo.register_object("/StatusNotifierWatcher", info.interfaces[0], klic, None, None)
        Gio.bus_own_name_on_connection(self.vodilo, "org.kde.StatusNotifierWatcher", Gio.BusNameOwnerFlags.NONE, None, None)

    def tearDown(self):
        try:
            self.pladenj.zapri()
        except Exception:  # noqa: BLE001
            pass
        self.vodilo.unregister_object(self.strazar)
        for v in (self.vodilo, self.pladenj_vodilo):
            v.close_sync(None)
        self.vodilo_test.down()

    def _klic(self, pot, vmesnik, metoda, parametri, vrsta):
        # Pladenj odgovarja v glavni zanki tega procesa: klic je asinhron, zanko vrtimo, dokler odgovor ne pride.
        izid = []
        self.vodilo.call(self.pladenj.ime_vodila, pot, vmesnik, metoda, parametri,
                         GLib.VariantType(vrsta) if vrsta else None, Gio.DBusCallFlags.NONE, 3000, None,
                         lambda v, r, *_a: izid.append(v.call_finish(r)), None)
        self.assertTrue(_pocakaj(lambda: bool(izid)), metoda)
        return izid[0]

    def test_ikona_meni_in_klik(self):
        from core.pladenj_sni import Pladenj, Postavka
        odpri, preklop, locilo, skrita = Postavka("Odpri"), Postavka("Zaženi ob prijavi", preklop=True), \
            Postavka(locilo=True), Postavka("Posodobi")
        skrita.hide()
        klici = []
        odpri.connect("activate", lambda *_a: klici.append("odpri"))
        preklop.connect("toggled", lambda p: klici.append(("preklop", p.get_active())))
        aktivacije = []
        self.pladenj = Pladenj("safeer-control", "Safeer Control", "safeer-control", [odpri, preklop, locilo, skrita],
                               ob_aktivaciji=lambda: aktivacije.append(1), vodilo=self.pladenj_vodilo)
        self.assertTrue(_pocakaj(lambda: self.prijave == [self.pladenj.ime_vodila]), self.prijave)

        lastnosti = self._klic("/StatusNotifierItem", "org.freedesktop.DBus.Properties", "GetAll",
                               GLib.Variant("(s)", ("org.kde.StatusNotifierItem",)), "(a{sv})").unpack()[0]
        self.assertEqual((lastnosti["Id"], lastnosti["IconName"], lastnosti["Menu"], lastnosti["ItemIsMenu"]),
                         ("safeer-control", "safeer-control", "/MenuBar", False))
        self.pladenj.nastavi_namig("Safeer Link: povezan")
        namig = self._klic("/StatusNotifierItem", "org.freedesktop.DBus.Properties", "Get",
                           GLib.Variant("(ss)", ("org.kde.StatusNotifierItem", "ToolTip")), "(v)").unpack()[0]
        self.assertEqual(namig[3], "Safeer Link: povezan")

        revizija, (koren, lastnosti_korena, otroci) = self._klic(
            "/MenuBar", "com.canonical.dbusmenu", "GetLayout", GLib.Variant("(iias)", (0, -1, [])),
            "(u(ia{sv}av))").unpack()
        self.assertEqual((koren, lastnosti_korena["children-display"]), (0, "submenu"))
        self.assertEqual([o[1].get("label") for o in otroci], ["Odpri", "Zaženi ob prijavi", None, "Posodobi"])
        self.assertEqual(otroci[1][1]["toggle-type"], "checkmark")
        self.assertEqual(otroci[1][1]["toggle-state"], 0)
        self.assertEqual(otroci[2][1]["type"], "separator")
        self.assertFalse(otroci[3][1]["visible"])

        # Klik v meniju: navadna postavka sprozi activate, preklop zamenja stanje in sprozi toggled.
        posodobitve = []
        self.vodilo.signal_subscribe(None, "com.canonical.dbusmenu", "LayoutUpdated", "/MenuBar", None,
                                     Gio.DBusSignalFlags.NONE, lambda *a: posodobitve.append(a[5].unpack()), None)
        for i in (1, 2):
            self._klic("/MenuBar", "com.canonical.dbusmenu", "Event",
                       GLib.Variant("(isvu)", (i, "clicked", GLib.Variant("i", 0), 0)), None)
        self.assertTrue(_pocakaj(lambda: len(klici) == 2 and posodobitve), (klici, posodobitve))
        self.assertEqual(klici, ["odpri", ("preklop", True)])
        self.assertGreater(posodobitve[-1][0], revizija)
        stanje = self._klic("/MenuBar", "com.canonical.dbusmenu", "GetProperty",
                            GLib.Variant("(is)", (2, "toggle-state")), "(v)").unpack()[0]
        self.assertEqual(stanje, 1)

        # handler_block: osvezitev iz programa (osvezi_samozagon) ne sme sprozit preklopa.
        i = preklop.connect("toggled", lambda *_a: klici.append("ne bi smel"))
        preklop.handler_block(i)
        preklop.set_active(False)
        self.assertNotIn("ne bi smel", klici)

        self._klic("/StatusNotifierItem", "org.kde.StatusNotifierItem", "Activate", GLib.Variant("(ii)", (0, 0)), None)
        self.assertTrue(_pocakaj(lambda: aktivacije == [1]))

    def test_ikona_iz_datoteke(self):
        from core.pladenj_sni import Pladenj
        ikona = os.path.join(KOREN, "assets", "icon.png")
        if not os.path.isfile(ikona):
            self.skipTest("ni assets/icon.png")
        self.pladenj = Pladenj("safeer-control", "Safeer Control", ikona, [], vodilo=self.pladenj_vodilo)
        lastnosti = self._klic("/StatusNotifierItem", "org.freedesktop.DBus.Properties", "GetAll",
                               GLib.Variant("(s)", ("org.kde.StatusNotifierItem",)), "(a{sv})").unpack()[0]
        self.assertEqual(lastnosti["IconName"], "")
        velikosti = [(s, v, len(b)) for s, v, b in lastnosti["IconPixmap"]]
        self.assertEqual(velikosti, [(32, 32, 32 * 32 * 4), (64, 64, 64 * 64 * 4)])


if __name__ == "__main__":
    unittest.main()
