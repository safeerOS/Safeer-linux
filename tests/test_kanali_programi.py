"""Namizni programi kot kanali Sporocil (Viber, Signal Desktop; lastnik, 15. 10. 2026) - brez pravih programov:
lazen program (tests/fixtures/lazni_program_okno.py, okno GTK4 z vnosom) v Xvfb.

core/vstavi_okno.py: vstavitev okna (XReparentWindow), sledenje velikosti, skrij/pokazi, fokus tipkovnice ob vstopu
miske (tipke XTest pridejo v program), vrnitev na namizje. core/namizni_programi.py: zaznava namestitve (.desktop s
StartupWMClass, ukaz na poti, AppImage, izbrana pot). core/znacke_programov.py: LauncherEntry, obvestila (D-Bus)."""
import ctypes
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAZNI = os.path.join(KOREN, "tests", "fixtures", "lazni_program_okno.py")

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from core import namizni_programi, vstavi_okno  # noqa: E402

Gtk.init()


def _cakaj(pogoj, cas=8.0):
    kontekst = GLib.MainContext.default()
    rok = time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.005)
    return pogoj()


def _x11():
    try:
        return vstavi_okno.X11()
    except OSError:
        return None


@unittest.skipUnless(os.environ.get("DISPLAY") and _x11() is not None, "potrebuje X11 (Xvfb)")
class Vstavljanje(unittest.TestCase):
    def setUp(self):
        self.otrok = subprocess.Popen([sys.executable, LAZNI, "6"], stdout=subprocess.PIPE, text=True)
        self.addCleanup(self._koncaj_otroka)
        self.assertEqual(self.otrok.stdout.readline().strip(), "pripravljen")
        self.x = vstavi_okno.X11()
        self.addCleanup(self.x.zapri)

    def _koncaj_otroka(self):
        self.otrok.terminate()
        try:
            self.otrok.wait(5)
        except subprocess.TimeoutExpired:
            self.otrok.kill()

    def test_vstavi_sledi_skrije_tipke_vrne(self):
        self.assertTrue(_cakaj(lambda: self.x.najdi(["SAFEER-lazni-program"]), 5), "iskanje po razredu brez velikosti crk")
        okno_programa = self.x.najdi(["safeer-lazni-program"])
        self.assertEqual(self.x.naslov(okno_programa), "(6) Lazni program")
        okno = Gtk.Window()
        okno.set_default_size(800, 600)
        skatla = Gtk.Box()
        skatla.append(Gtk.Label(label="stran"))
        mesto = Gtk.DrawingArea()
        mesto.set_hexpand(True)
        mesto.set_vexpand(True)
        skatla.append(mesto)
        okno.set_child(skatla)
        okno.present()
        self.addCleanup(okno.destroy)
        self.assertTrue(_cakaj(lambda: mesto.get_mapped()))
        v = vstavi_okno.VstavljenoOkno(Gtk, GLib, mesto)
        self.addCleanup(v.unici)
        self.assertTrue(v.vstavi(okno_programa))
        nase = vstavi_okno.Mesto(Gtk, mesto).xid_starsa()
        self.assertTrue(_cakaj(lambda: self.x.stars(okno_programa) == nase), "okno programa je v nasem oknu")
        # sledi velikosti gradnika
        okno.set_default_size(700, 500)
        _cakaj(lambda: False, 0.4)
        v.prilagodi()
        r = vstavi_okno.Mesto(Gtk, mesto).pravokotnik()
        a = vstavi_okno._XWindowAttributes()
        self.x.lib.XGetWindowAttributes(self.x.dpy, okno_programa, ctypes.byref(a))
        self.assertEqual((a.x, a.y, a.width, a.height), tuple(r))
        # skrij (drug kanal ali razdelek) in pokazi
        mesto.set_visible(False)
        self.assertTrue(_cakaj(lambda: self.x.stanje_prikaza(okno_programa) == vstavi_okno.IS_UNMAPPED, 2))
        mesto.set_visible(True)
        self.assertTrue(_cakaj(lambda: self.x.stanje_prikaza(okno_programa) == 2, 2))
        # tipkovnica: miska vstopi v vstavljeno okno -> fokus programu, tipke XTest pridejo v njegov vnos
        xtst = ctypes.cdll.LoadLibrary("libXtst.so.6")
        xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
        xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.x.lib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x.lib.XKeysymToKeycode.restype = ctypes.c_ubyte
        # Miska najprej na nas del okna (napis levo od vstavljenega okna), nato v vstavljeno okno - vstop je dogodek.
        lx, ly, _o = ctypes.c_int(), ctypes.c_int(), ctypes.c_ulong()
        self.x.lib.XTranslateCoordinates(self.x.dpy, nase, self.x.koren(), max(1, r[0] // 2), 5, ctypes.byref(lx),
                                         ctypes.byref(ly), ctypes.byref(_o))
        xtst.XTestFakeMotionEvent(self.x.dpy, -1, lx.value, ly.value, 0)
        self.x.lib.XFlush(self.x.dpy)
        _cakaj(lambda: False, 0.4)
        rx, ry = ctypes.c_int(), ctypes.c_int()
        self.x.lib.XTranslateCoordinates(self.x.dpy, okno_programa, self.x.koren(), 20, 20, ctypes.byref(rx),
                                         ctypes.byref(ry), ctypes.byref(_o))
        xtst.XTestFakeMotionEvent(self.x.dpy, -1, rx.value, ry.value, 0)
        self.x.lib.XFlush(self.x.dpy)
        _cakaj(lambda: False, 0.5)
        for crka in "safeer":
            kc = self.x.lib.XKeysymToKeycode(self.x.dpy, ord(crka))
            xtst.XTestFakeKeyEvent(self.x.dpy, kc, 1, 0)
            xtst.XTestFakeKeyEvent(self.x.dpy, kc, 0, 0)
        self.x.lib.XFlush(self.x.dpy)
        _cakaj(lambda: False, 0.8)
        # vrnitev na namizje: okno programa spet otrok korenskega okna, program tece naprej
        v.vrni()
        self.assertTrue(_cakaj(lambda: self.x.stars(okno_programa) == self.x.koren(), 2))
        self.assertIsNone(self.otrok.poll(), "program se ne ustavi")
        self._koncaj_otroka()
        izhod = self.otrok.stdout.read()
        self.assertIn("vnos:safeer", izhod, "tipke so prisle v vstavljeni program")


@unittest.skipUnless(os.environ.get("DISPLAY") and _x11() is not None, "potrebuje X11 (Xvfb)")
class KanalProgram(unittest.TestCase):
    """Cela pot: kanal iz kataloga (lazen vnos - samo podatki), zagon ob zagonu namizja, vgradnja v Sporocila,
    stevilo neprebranih iz naslova okna, ob koncu okno nazaj na namizje (program tece naprej)."""

    def test_kanal_program_od_zagona_do_konca(self):
        from unittest import mock
        from core import os_kanali_sporocil, spletni_klepeti
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa)
        ovoj = os.path.join(mapa, "lazni-program")
        with open(ovoj, "w") as f:
            f.write("#!/bin/sh\nexec %s %s 3\n" % (sys.executable, LAZNI))
        os.chmod(ovoj, 0o755)
        vnos = {"id": "lazni", "ime": "Lazni program", "vrsta": "klepet", "splet": "", "prenos": "https://primer.invalid/",
                "program": {"vnosi": [], "ukazi": [], "appimage": [], "razredi": ["safeer-lazni-program"], "argumenti": []}}
        self.addCleanup(lambda: subprocess.run(["pkill", "-f", LAZNI]))

        class _S(dict):
            def set(self, k, v):
                self[k] = v
        with mock.patch.object(spletni_klepeti, "KATALOG", spletni_klepeti.KATALOG + [vnos]), \
                mock.patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"}), \
                mock.patch.object(os_kanali_sporocil.KanaliSporocil, "_zacni_znacke"):
            k = os_kanali_sporocil.KanaliSporocil(Gtk, GLib, Gio, lambda: None, _S(), lambda: "sl", lambda *a: None,
                                                  lambda kid: None)
            self.assertTrue(k.katalog()[-1]["namescen"] is False, "brez izbrane poti program ni namescen")
            seznam = k.dodaj(katalog="lazni", pot=ovoj)
            self.assertEqual((seznam[0]["vrsta"], seznam[0]["namescen"]), ("program", True))
            self.assertTrue(_cakaj(lambda: k.zivi["lazni"].okno.okno, 15), "okno zagnanega programa je najdeno")
            self.assertEqual(k.kanali.najdi("lazni")["neprebrano"], 3, "stevilo iz naslova okna »(3) Lazni program«")
            okno = Gtk.Window()
            okno.set_default_size(800, 600)
            stran = Gtk.Label(label="Sporocila")
            prekrivanje = Gtk.Overlay()
            prekrivanje.set_child(stran)
            okno.set_child(prekrivanje)
            okno.present()
            self.addCleanup(okno.destroy)
            self.assertTrue(_cakaj(lambda: okno.get_mapped()))
            r = {"x": 200, "y": 60, "w": 560, "h": 500, "vw": 800, "vh": 600, "dpr": 1}
            self.assertEqual(k.pokazi(stran, prekrivanje, "lazni", r), {"ok": True, "vgrajeno": True})
            x = vstavi_okno.X11()
            self.addCleanup(x.zapri)
            w = k.zivi["lazni"].okno.okno
            nase = vstavi_okno.Mesto(Gtk, k.zivi["lazni"].gradnik).xid_starsa()
            self.assertTrue(_cakaj(lambda: x.stars(w) == nase, 5), "okno programa je v Sporocilih")
            k.koncaj()
            self.assertTrue(_cakaj(lambda: x.stars(w) == x.koren(), 3), "ob koncu nazaj na namizje")


class Zaznava(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mapa)
        self.program = {"vnosi": ["primer.desktop"], "ukazi": ["safeer-ni-tega-ukaza"], "appimage": ["primer*.appimage"],
                        "razredi": ["PrimerPC"], "argumenti": ["--ozone-platform=x11"]}

    def _izvrsljiva(self, pot):
        with open(pot, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(pot, os.stat(pot).st_mode | stat.S_IXUSR)
        return pot

    def test_nic_namesceno(self):
        self.assertIsNone(namizni_programi.najdi(self.program, mape_vnosov=[self.mapa], mape_appimage=[self.mapa]))

    def test_vnos_z_razredom_okna(self):
        with open(os.path.join(self.mapa, "primer.desktop"), "w") as f:
            f.write("[Desktop Entry]\nType=Application\nName=Primer\nExec=/opt/primer/Primer %U\nStartupWMClass=Primer.PrimerPC\n")
        n = namizni_programi.najdi(self.program, mape_vnosov=[self.mapa], mape_appimage=[])
        self.assertEqual(n["oblika"], "vnos")
        self.assertEqual(n["ukaz"], ["/opt/primer/Primer", "--ozone-platform=x11"])
        self.assertEqual(n["razredi"][0], "Primer.PrimerPC", "StartupWMClass vnosa ima prednost")

    def test_appimage_in_izbrana_pot(self):
        ai = self._izvrsljiva(os.path.join(self.mapa, "Primer-1.2-x86_64.AppImage"))
        n = namizni_programi.najdi(self.program, mape_vnosov=[], mape_appimage=[self.mapa])
        self.assertEqual((n["oblika"], n["ukaz"][0]), ("appimage", ai))
        drugje = self._izvrsljiva(os.path.join(self.mapa, "kar.bin"))
        self.assertEqual(namizni_programi.najdi(self.program, drugje, mape_vnosov=[], mape_appimage=[])["oblika"], "pot")
        os.chmod(ai, 0o644)
        self.assertIsNone(namizni_programi.najdi(self.program, mape_vnosov=[], mape_appimage=[self.mapa]),
                          "neizvrsljiva datoteka ni namestitev")

    def test_katalog_viber_in_signal(self):
        from core import spletni_klepeti
        viber, signal = spletni_klepeti.po_id("viber"), spletni_klepeti.po_id("signal")
        # Testni PC 15. 10. 2026: Viber AppImage ima WM_CLASS »Viber.ViberPC« (ime Viber, razred ViberPC).
        self.assertIn("ViberPC", viber["program"]["razredi"])
        self.assertIn("org.signal.Signal.desktop", signal["program"]["vnosi"])
        self.assertIn("--ozone-platform=x11", signal["program"]["argumenti"], "Electron mora odpreti okno X11")
        self.assertEqual(signal["prenos"], "https://signal.org/download/", "Flatpak je neuraden - uradna stran")

    def test_wayland_ni_vgradnje(self):
        from unittest import mock
        with mock.patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}):
            self.assertFalse(namizni_programi.x11_seja())
        with mock.patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}):
            self.assertTrue(namizni_programi.x11_seja())


ODDAJNIK = r"""
import sys, time
import gi
from gi.repository import Gio, GLib
sys.path.insert(0, sys.argv[1])
from core import znacke_programov
prejeto = []
p = znacke_programov.Poslusalec(Gio, GLib, ob_znacki=lambda d, n: prejeto.append(["znacka", d, n]),
                                ob_pladnju=lambda i, a: prejeto.append(["pladenj", i, a]),
                                ob_obvestilu=lambda a, s, b: prejeto.append(["obvestilo", a, s]))
v = Gio.bus_get_sync(Gio.BusType.SESSION, None)
v.emit_signal(None, "/primer", "com.canonical.Unity.LauncherEntry", "Update",
              GLib.Variant("(sa{sv})", ("application://primer.desktop", {"count": GLib.Variant("x", 5),
                                                                        "count-visible": GLib.Variant("b", True)})))
v.emit_signal(None, "/primer", "com.canonical.Unity.LauncherEntry", "Update",
              GLib.Variant("(sa{sv})", ("application://primer.desktop", {"count": GLib.Variant("x", 9),
                                                                        "count-visible": GLib.Variant("b", False)})))
# Lazni streznik obvestil (kot namizje) in klic Notify, kot ga naredi program
XML = ("<node><interface name='org.freedesktop.Notifications'><method name='Notify'>"
       "<arg type='s' direction='in'/><arg type='u' direction='in'/><arg type='s' direction='in'/>"
       "<arg type='s' direction='in'/><arg type='s' direction='in'/><arg type='as' direction='in'/>"
       "<arg type='a{sv}' direction='in'/><arg type='i' direction='in'/><arg type='u' direction='out'/>"
       "</method></interface></node>")
streznik = Gio.bus_get_sync(Gio.BusType.SESSION, None)
streznik = Gio.DBusConnection.new_for_address_sync(Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None),
    Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
streznik.register_object("/org/freedesktop/Notifications", Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0],
                         lambda c, s, p, i, m, a, inv: inv.return_value(GLib.Variant("(u)", (1,))), None, None)
streznik.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "RequestName",
                   GLib.Variant("(su)", ("org.freedesktop.Notifications", 0)), None, Gio.DBusCallFlags.NONE, 2000, None)
v.call("org.freedesktop.Notifications", "/org/freedesktop/Notifications", "org.freedesktop.Notifications", "Notify",
       GLib.Variant("(susssasa{sv}i)", ("Primer", 0, "", "Ana", "Zivjo", [], {}, -1)), None,
       Gio.DBusCallFlags.NONE, 2000, None, None, None)
k = GLib.MainContext.default(); rok = time.monotonic() + 3
while time.monotonic() < rok:
    k.iteration(False); time.sleep(0.01)
print(json.dumps(prejeto) if False else __import__("json").dumps(prejeto))
"""


@unittest.skipUnless(shutil.which("dbus-run-session"), "potrebuje dbus-run-session")
class Znacke(unittest.TestCase):
    def test_launcher_entry_in_obvestila(self):
        from core import znacke_programov
        self.assertEqual(znacke_programov.desktop_id("application://signal-desktop.desktop"), "signal-desktop.desktop")
        self.assertEqual(znacke_programov.desktop_id("signal"), "")
        self.assertEqual(znacke_programov.stevilo_iz_lastnosti({"count": 3, "count-visible": True}), 3)
        self.assertEqual(znacke_programov.stevilo_iz_lastnosti({"count": 3, "count-visible": False}), 0)
        self.assertEqual(znacke_programov.stevilo_iz_lastnosti({"urgent": True}), 1)
        self.assertIsNone(znacke_programov.stevilo_iz_lastnosti({"progress": 0.5}))
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(ODDAJNIK)
        self.addCleanup(os.unlink, f.name)
        r = subprocess.run(["dbus-run-session", "--", sys.executable, f.name, KOREN], capture_output=True, text=True,
                           timeout=30)
        prejeto = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertIn(["znacka", "primer.desktop", 5], prejeto)
        self.assertIn(["znacka", "primer.desktop", 0], prejeto, "count-visible=false pomeni brez znacke")
        self.assertIn(["obvestilo", "Primer", "Ana"], prejeto, "vir 3: klic Notify programa")


if __name__ == "__main__":
    unittest.main()
