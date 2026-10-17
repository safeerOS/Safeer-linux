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

    def test_kuverta_sporocil_poleg_ikone_controla(self):
        """Kuverta Sporocil (Safeer OS) je SNI na lastni povezavi: v istem procesu kot ikona Controla (isti poti
        /StatusNotifierItem in /MenuBar), brez Qt. Nova ikona in namig se sporocita s signaloma; klik odpre plosco."""
        from core.pladenj_sni import Kuverta, Pladenj, lastno_vodilo
        ikona = os.path.join(KOREN, "assets", "icon.png")
        if not os.path.isfile(ikona):
            self.skipTest("ni assets/icon.png")
        self.pladenj = Pladenj("safeer-control", "Safeer Control", "safeer-control", [], vodilo=self.pladenj_vodilo)
        kliki = []
        vodilo_kuverte = lastno_vodilo(self.vodilo_test.get_bus_address())
        kuverta = Kuverta(lambda: kliki.append(1), "Sporočila", vodilo=vodilo_kuverte)
        try:
            self._kuverta(kuverta, ikona, kliki)
        finally:
            kuverta.zapri()
            vodilo_kuverte.close_sync(None)

    def _kuverta(self, kuverta, ikona, kliki):
        self.assertTrue(_pocakaj(lambda: len(self.prijave) == 2), self.prijave)
        self.assertEqual(set(self.prijave), {self.pladenj.ime_vodila, kuverta.pladenj.ime_vodila})
        signali = []
        self.vodilo.signal_subscribe(None, "org.kde.StatusNotifierItem", None, "/StatusNotifierItem", None,
                                     Gio.DBusSignalFlags.NONE, lambda *a: signali.append((a[1], a[4])), None)
        kuverta.nastavi(ikona, "Sporočila: 3 neprebranih")
        self.assertTrue(_pocakaj(lambda: {("NewIcon"), ("NewToolTip")} <= {s for _p, s in signali}), signali)
        pladenj_controla = self.pladenj
        self.pladenj = kuverta.pladenj           # _klic sprasuje self.pladenj
        lastnosti = self._klic("/StatusNotifierItem", "org.freedesktop.DBus.Properties", "GetAll",
                               GLib.Variant("(s)", ("org.kde.StatusNotifierItem",)), "(a{sv})").unpack()[0]
        self.assertEqual((lastnosti["Id"], lastnosti["IconName"], lastnosti["ToolTip"][3]),
                         ("safeer-os-sporocila", "", "Sporočila: 3 neprebranih"))
        self.assertEqual(len(lastnosti["IconPixmap"]), 2)
        self._klic("/StatusNotifierItem", "org.kde.StatusNotifierItem", "Activate", GLib.Variant("(ii)", (0, 0)), None)
        self._klic("/MenuBar", "com.canonical.dbusmenu", "Event",
                   GLib.Variant("(isvu)", (1, "clicked", GLib.Variant("i", 0), 0)), None)
        self.assertTrue(_pocakaj(lambda: kliki == [1, 1]), kliki)
        self.pladenj = pladenj_controla

    def test_scit_v_pultu(self):
        """Safeer Scit poleg kuverte (lastnik, 17. 10. 2026): svoja ikona SNI na lastni povezavi, namig »Safeer Scit« z
        opisom, levi klik odpre nastavitve Scita, meni Vklopi/Izklopi in Nastavitve Scita."""
        import tempfile
        from core.pladenj_sni import BESEDILA_SCITA, ScitPult, lastno_vodilo
        nastavitve, preklopi = [], []
        mapa = tempfile.mkdtemp(prefix="safeer-scit-")
        self.addCleanup(shutil.rmtree, mapa, True)
        vodilo_scita = lastno_vodilo(self.vodilo_test.get_bus_address())
        scit = ScitPult(BESEDILA_SCITA["sl"], lambda: nastavitve.append(1), preklopi.append, mapa, vodilo=vodilo_scita)
        try:
            self.pladenj = scit.pladenj
            self.assertTrue(_pocakaj(lambda: self.prijave == [scit.pladenj.ime_vodila]), self.prijave)
            scit.osvezi({"vklop": True, "tece": True, "mozno": True, "napaka": "", "blokiranih": 42})
            lastnosti = self._klic("/StatusNotifierItem", "org.freedesktop.DBus.Properties", "GetAll",
                                   GLib.Variant("(s)", ("org.kde.StatusNotifierItem",)), "(a{sv})").unpack()[0]
            self.assertEqual((lastnosti["Id"], lastnosti["Title"], lastnosti["ToolTip"][2], lastnosti["ToolTip"][3]),
                             ("safeer-os-scit", "Safeer Ščit", "Safeer Ščit", "Vklopljen – blokiranih 42"))
            self.assertEqual(len(lastnosti["IconPixmap"]), 2)
            drevo = self._klic("/MenuBar", "com.canonical.dbusmenu", "GetLayout",
                               GLib.Variant("(iias)", (0, -1, [])), "(u(ia{sv}av))").unpack()[1]
            napisi = [o[1].get("label") for o in drevo[2]]
            self.assertEqual(napisi, ["Izklopi Ščit", None, "Nastavitve Ščita"])
            self._klic("/StatusNotifierItem", "org.kde.StatusNotifierItem", "Activate", GLib.Variant("(ii)", (0, 0)), None)
            self._klic("/MenuBar", "com.canonical.dbusmenu", "Event",
                       GLib.Variant("(isvu)", (3, "clicked", GLib.Variant("i", 0), 0)), None)
            self.assertTrue(_pocakaj(lambda: nastavitve == [1, 1]), nastavitve)
            # Izklopi: preklop dobi False, med delom je postavka onemogocena (dvojni klik ne sprozi dveh preklopov).
            self._klic("/MenuBar", "com.canonical.dbusmenu", "Event",
                       GLib.Variant("(isvu)", (1, "clicked", GLib.Variant("i", 0), 0)), None)
            self.assertTrue(_pocakaj(lambda: preklopi == [False]), preklopi)
            self.assertFalse(scit.preklop.get_sensitive())
            self.assertEqual((scit.vrsta, scit.opis), ("pripravljam", "Izklapljam …"))
            scit.preklop.aktiviraj()
            self.assertEqual(preklopi, [False])
            scit.osvezi({"vklop": False, "tece": False, "mozno": True, "napaka": ""})
            self.assertEqual((scit.vrsta, scit.opis, scit.preklop.get_label()), ("izklopljen", "Izklopljen", "Vklopi Ščit"))
            scit.preklop.aktiviraj()
            self.assertEqual(preklopi, [False, True])
        finally:
            scit.zapri()
            vodilo_scita.close_sync(None)


class StanjeScita(unittest.TestCase):
    """Stanje Scita (os_scit.Scit.stanje()) -> ikona in opis v pultu, v vseh jezikih."""

    def test_vrsta_in_opis(self):
        from core.pladenj_sni import BESEDILA_SCITA, opis_scita, vrsta_scita
        b = BESEDILA_SCITA["sl"]
        primeri = [
            ({"vklop": True, "tece": True, "mozno": True, "napaka": "", "blokiranih": 7}, "vklopljen", "Vklopljen – blokiranih 7"),
            ({"vklop": True, "tece": True, "mozno": True, "napaka": "", "premor": 600}, "vklopljen", "Na premoru še 10 min"),
            ({"vklop": True, "tece": True, "mozno": True, "napaka": "ni_omrezja"}, "vklopljen", "Vklopljen – čaka na omrežje"),
            ({"vklop": True, "tece": False, "mozno": True, "napaka": ""}, "pripravljam", "Vklapljam …"),
            ({"vklop": False, "tece": False, "mozno": True, "napaka": ""}, "izklopljen", "Izklopljen"),
            ({"vklop": False, "tece": False, "mozno": False, "napaka": ""}, "izklopljen", "Ni na voljo na tem računalniku"),
            # Uporabnik je zavrnil geslo ob vklopu: napaka, ceprav Scit ni vklopljen.
            ({"vklop": False, "tece": False, "mozno": True, "napaka": "pravilo"}, "napaka", "Napaka – odpri nastavitve Ščita"),
            ({"vklop": True, "tece": False, "mozno": True, "napaka": "vrata"}, "napaka", "Napaka – odpri nastavitve Ščita"),
            ({}, "izklopljen", "Izklopljen"),
        ]
        for stanje, vrsta, opis in primeri:
            self.assertEqual(vrsta_scita(stanje), vrsta, stanje)
            self.assertEqual(opis_scita(stanje, vrsta, b), opis, stanje)
        self.assertEqual(vrsta_scita({"vklop": True, "tece": True}, zaposlen="izklop"), "pripravljam")
        self.assertEqual(opis_scita({"vklop": False}, "pripravljam", b, "vklop"), "Vklapljam …")

    def test_vsi_jeziki(self):
        from core.pladenj_sni import BESEDILA_SCITA
        self.assertEqual(sorted(BESEDILA_SCITA), ["de", "en", "es", "fr", "it", "sl"])
        for jezik, b in BESEDILA_SCITA.items():
            self.assertEqual(set(b), set(BESEDILA_SCITA["sl"]), jezik)
            self.assertIn("{n}", b["vklopljen"], jezik)
            self.assertIn("{n}", b["premor"], jezik)

    @unittest.skipUnless(Gio is not None, "potrebuje PyGObject")
    def test_ikone_razlicne(self):
        """Stiri stanja = stiri razlicne slike; nobena ni ikona Safeer Control ali Safeer OS (lastnik: Scit mora biti
        ocitno drugacen od zelenega scita Controla)."""
        import tempfile
        try:
            import cairo  # noqa: F401
        except ImportError:
            self.skipTest("ni pycairo")
        from core import os_lupina
        from core.pladenj_sni import ikona_scita
        mapa = tempfile.mkdtemp(prefix="safeer-scit-")
        barve = os_lupina.tokeni()
        self.assertIn("ok", barve)
        self.addCleanup(shutil.rmtree, mapa, True)
        slike = {}
        for vrsta in ("vklopljen", "izklopljen", "napaka", "pripravljam"):
            pot = ikona_scita(vrsta, mapa, barve=barve)
            with open(pot, "rb") as f:
                slike[vrsta] = f.read()
            self.assertTrue(slike[vrsta].startswith(b"\x89PNG"), vrsta)
            self.assertEqual(ikona_scita(vrsta, mapa, barve=barve), pot)     # iz predpomnilnika
        self.assertEqual(len(set(slike.values())), 4)
        gi_pixbuf = __import__("gi")
        gi_pixbuf.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        # Crtna ikona: sredina ploscice je prozorna (Control je poln zeleni scit na temni ploscici).
        p = GdkPixbuf.Pixbuf.new_from_file(os.path.join(mapa, "scit-v1-izklopljen.png"))
        tocke = p.get_pixels()
        vogal = tocke[2 * p.get_rowstride() + 2 * 4 + 3]
        self.assertEqual(vogal, 0)


if __name__ == "__main__":
    unittest.main()
