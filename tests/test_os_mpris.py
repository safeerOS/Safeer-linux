"""MPRIS (core/os_mpris.py): medijske tipke in zvocni applet vidijo domaci predvajalnik Safeer OS."""
import os
import shutil
import subprocess
import sys
import textwrap
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)
from core import os_mpris  # noqa: E402


class TestLastnosti(unittest.TestCase):
    def test_predvaja_video(self):
        l = os_mpris.lastnosti({"stanje": "predvaja", "naslov": "Sintel", "vrsta": "video", "indeks": 1, "skupaj": 3,
                                "trajanje": 888.0, "pozicija": 12.5, "izvor": "Telefon"})
        self.assertEqual(l["PlaybackStatus"], "Playing")
        self.assertEqual(l["Metadata"]["xesam:title"], "Sintel")
        self.assertEqual(l["Metadata"]["xesam:artist"], ["Telefon"])
        self.assertEqual(l["Metadata"]["mpris:length"], 888_000_000)
        self.assertEqual(l["Metadata"]["mpris:trackid"], "/si/safeer/os/skladba/1")
        self.assertTrue(l["CanGoNext"] and l["CanGoPrevious"] and l["CanSeek"] and l["CanPause"])

    def test_radio_v_zivo_nima_dolzine_in_skoka(self):
        l = os_mpris.lastnosti({"stanje": "predvaja", "naslov": "Val 202", "vrsta": "radio", "indeks": 0, "skupaj": 1, "trajanje": 55.0})
        self.assertNotIn("mpris:length", l["Metadata"])
        self.assertFalse(l["CanSeek"])
        self.assertFalse(l["CanGoNext"])
        self.assertFalse(l["CanGoPrevious"])

    def test_ustavljeno(self):
        l = os_mpris.lastnosti({"stanje": "ustavljeno", "naslov": "", "indeks": -1, "skupaj": 0})
        self.assertEqual(l["PlaybackStatus"], "Stopped")
        self.assertEqual(l["Metadata"], {"mpris:trackid": os_mpris.BREZ_SKLADBE})
        self.assertFalse(l["CanPlay"] or l["CanPause"] or l["CanSeek"])
        self.assertFalse(os_mpris.igra({"stanje": "ustavljeno"}))
        self.assertTrue(os_mpris.igra({"stanje": "premor"}))

    def test_slika_samo_z_varno_shemo(self):
        l = os_mpris.lastnosti({"stanje": "premor", "naslov": "x", "indeks": 0, "skupaj": 1, "slika": "javascript:alert(1)"})
        self.assertNotIn("mpris:artUrl", l["Metadata"])
        l = os_mpris.lastnosti({"stanje": "premor", "naslov": "x", "indeks": 0, "skupaj": 1, "slika": "https://example.org/a.jpg"})
        self.assertEqual(l["Metadata"]["mpris:artUrl"], "https://example.org/a.jpg")

    def test_vsaka_lastnost_ima_tip(self):
        l = os_mpris.lastnosti({"stanje": "predvaja", "naslov": "a", "indeks": 0, "skupaj": 1, "trajanje": 3, "slika": "file:///a.png"})
        for k in l:
            self.assertTrue(k == "Metadata" or k in os_mpris.TIPI, k)
        for k in l["Metadata"]:
            self.assertIn(k, os_mpris.TIPI_METAPODATKOV)
        for ime in os_mpris.TIPI:
            self.assertIn('name="%s"' % ime, os_mpris.XML)


SKRIPTA = textwrap.dedent('''
    import json, subprocess, sys, threading
    sys.path.insert(0, %r)
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
    from core import os_mpris
    stanje = {"stanje": "predvaja", "naslov": "Sintel", "vrsta": "video", "indeks": 0, "skupaj": 2, "trajanje": 100.0, "pozicija": 10.0}
    ukazi = []
    def ukaz(ime, vrednost=None):
        ukazi.append([ime, vrednost])
        if ime == "premor":
            stanje["stanje"] = "premor" if stanje["stanje"] == "predvaja" else "predvaja"
        if ime == "ustavi":
            stanje["stanje"] = "ustavljeno"
        GLib.idle_add(lambda: (m.osvezi(), False)[1])
        return True
    vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    m = os_mpris.Mpris(vodilo, lambda: dict(stanje), ukaz)
    m.osvezi()
    zanka = GLib.MainLoop()
    izid = {}
    def g(*a):
        return subprocess.run(["gdbus", *a], capture_output=True, text=True, timeout=10).stdout.strip()
    C = ["call", "--session", "--dest", os_mpris.IME, "--object-path", os_mpris.POT, "--method"]
    def delo():
        try:
            izid["status"] = g(*C, "org.freedesktop.DBus.Properties.Get", os_mpris.V_PREDVAJALNIK, "PlaybackStatus")
            izid["meta"] = g(*C, "org.freedesktop.DBus.Properties.Get", os_mpris.V_PREDVAJALNIK, "Metadata")
            izid["vse"] = g(*C, "org.freedesktop.DBus.Properties.GetAll", os_mpris.V_PREDVAJALNIK)
            izid["identiteta"] = g(*C, "org.freedesktop.DBus.Properties.Get", os_mpris.V_KOREN, "Identity")
            g(*C, os_mpris.V_PREDVAJALNIK + ".PlayPause")
            izid["po_premoru"] = g(*C, "org.freedesktop.DBus.Properties.Get", os_mpris.V_PREDVAJALNIK, "PlaybackStatus")
            g(*C, os_mpris.V_PREDVAJALNIK + ".Seek", "5000000")
            g(*C, os_mpris.V_PREDVAJALNIK + ".Next")
            g(*C, os_mpris.V_PREDVAJALNIK + ".Stop")
            import time; time.sleep(0.5)
            izid["po_ustavitvi"] = g("call", "--session", "--dest", "org.freedesktop.DBus", "--object-path", "/org/freedesktop/DBus",
                                     "--method", "org.freedesktop.DBus.NameHasOwner", os_mpris.IME)
        finally:
            izid["ukazi"] = ukazi
            GLib.idle_add(zanka.quit)
    threading.Thread(target=delo, daemon=True).start()
    GLib.timeout_add_seconds(25, zanka.quit)
    zanka.run()
    print(json.dumps(izid))
''')


@unittest.skipUnless(shutil.which("dbus-run-session") and shutil.which("gdbus"), "ni dbus-run-session/gdbus")
class TestNaVodilu(unittest.TestCase):
    def test_sistem_vidi_predvajalnik_in_ga_upravlja(self):
        try:
            import gi  # noqa: F401
        except ImportError:
            self.skipTest("ni PyGObject")
        import json
        r = subprocess.run(["dbus-run-session", "--", sys.executable, "-c", SKRIPTA % KOREN], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        izid = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertIn("'Playing'", izid["status"])
        self.assertIn("Sintel", izid["meta"])
        self.assertIn("int64 100000000", izid["meta"])
        self.assertIn("'CanSeek': <true>", izid["vse"])
        self.assertIn("'Position': <int64 10000000>", izid["vse"])
        self.assertIn("Safeer OS", izid["identiteta"])
        self.assertIn("'Paused'", izid["po_premoru"])
        self.assertEqual(izid["ukazi"], [["premor", None], ["skok", 15.0], ["naslednja", None], ["ustavi", None]])
        self.assertIn("false", izid["po_ustavitvi"], "ustavljen predvajalnik se mora umakniti z vodila")


if __name__ == "__main__":
    unittest.main()
