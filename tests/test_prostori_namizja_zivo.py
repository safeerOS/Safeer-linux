"""Prostori, krog 2, s PRAVIM upravljalnikom oken (Muffin v Xvfb): lokalna namizja (wmctrl) in vrstica gledalca naprave
(celozaslonsko, drzan Esc, Super+Tab nazaj v Prostore). Brez upravljalnika oken se preskoci.

Zagon (z nasim WebKitom, ker vrstica je v safeer_control.py):
GI_TYPELIB_PATH=/usr/lib/safeer-webkit/lib/girepository-1.0 LD_LIBRARY_PATH=/usr/lib/safeer-webkit/lib \\
xvfb-run -a -s "-screen 0 1600x900x24" dbus-run-session -- bash -c \\
  'GSETTINGS_BACKEND=memory muffin --replace >/dev/null 2>&1 & sleep 8; python3 -m pytest -q tests/test_prostori_namizja_zivo.py; kill %1'"""
import os
import shutil
import subprocess
import time
import unittest

if not os.environ.get("DISPLAY") or not shutil.which("wmctrl"):
    raise unittest.SkipTest("potrebuje X11 in wmctrl")
if subprocess.run(["wmctrl", "-m"], capture_output=True, timeout=5).returncode != 0:
    raise unittest.SkipTest("ni upravljalnika oken (zazeni muffin v Xvfb)")

from core import os_delovni_prostori as dp  # noqa: E402


def _cakaj(pogoj, rok=5.0):
    konec = time.monotonic() + rok
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(0.05)
    return pogoj()


class NamizjaZivo(unittest.TestCase):
    def setUp(self):
        self.n = dp.Namizja()
        self.zacetno = len(self.n.seznam())
        self.assertGreater(self.zacetno, 0)

    def tearDown(self):
        subprocess.run(["wmctrl", "-n", str(self.zacetno)], timeout=5)
        subprocess.run(["wmctrl", "-s", "0"], timeout=5)

    def test_preklop_in_novo(self):
        if self.zacetno < 2:
            subprocess.run(["wmctrl", "-n", "2"], timeout=5)
            self.assertTrue(_cakaj(lambda: len(self.n.seznam()) == 2))
        self.assertEqual(self.n.preklopi(1), {"ok": True, "st": 1})
        self.assertTrue(_cakaj(lambda: [x["st"] for x in self.n.seznam() if x["trenutno"]] == [1]))
        pred = len(self.n.seznam())
        r = self.n.dodaj()
        self.assertEqual(r, {"ok": True, "st": pred})
        self.assertTrue(_cakaj(lambda: [x["st"] for x in self.n.seznam() if x["trenutno"]] == [pred]))
        self.assertFalse(self.n.preklopi(pred + 5)["ok"])


class VrsticaZivo(unittest.TestCase):
    """_VrsticaGledalca iz safeer_control.py na pravem oknu GTK4 (upravljalnik oken izvede celozaslonsko)."""

    @classmethod
    def setUpClass(cls):
        try:
            import gi
            gi.require_version("Gtk", "4.0")
            gi.require_version("Gdk", "4.0")
            from gi.repository import Gdk, GLib, Gtk
        except (ImportError, ValueError) as e:
            raise unittest.SkipTest("potrebuje GTK4: %s" % e)
        cls.Gdk, cls.GLib, cls.Gtk = Gdk, GLib, Gtk
        Gtk.init()
        try:
            import safeer_control
        except Exception as e:  # noqa: BLE001 - brez WebKitGTK 6.0 se Control ne uvozi
            raise unittest.SkipTest("safeer_control se ne uvozi: %s" % e)
        cls.sc = safeer_control

    def _vrti(self, pogoj, rok=5.0):
        ctx = self.GLib.MainContext.default()
        konec = time.monotonic() + rok
        while time.monotonic() < konec:
            while ctx.pending():
                ctx.iteration(False)
            if pogoj():
                return True
            time.sleep(0.02)
        return pogoj()

    def test_esc_in_super_tab(self):
        Gtk, Gdk = self.Gtk, self.Gdk
        esc, prostori = [], []

        class _Control:
            nastavitve = {"ui_language": "sl"}
            ob_prostorih = None
        c = _Control()
        okno = Gtk.Window()
        okno.set_default_size(800, 500)
        prekrivnik = Gtk.Overlay()
        prekrivnik.set_child(Gtk.Box())
        okno.set_child(prekrivnik)
        v = self.sc._VrsticaGledalca(okno, prekrivnik, c, "Pisarna", ob_esc=lambda: esc.append(1),
                                     ob_besedilu=lambda _b: None, ob_datotekah=lambda _p: {"ok": True},
                                     id_naprave=lambda: "pc-1-control")
        okno.present()
        self.addCleanup(okno.destroy)
        self.assertEqual(v.gumb_celo.get_label(), "Celozaslonsko")
        okno.fullscreen()
        self.assertTrue(self._vrti(okno.is_fullscreen), "upravljalnik oken ni razpel okna")
        self.assertTrue(self._vrti(lambda: v.gumb_celo.get_label() == "Izhod iz celega zaslona"))
        # Kratek Esc gre napravi in okno ostane celozaslonsko.
        self.assertTrue(v._tipka_dol(None, Gdk.KEY_Escape, 0, 0))
        v._tipka_gor(None, Gdk.KEY_Escape, 0, 0)
        self.assertEqual(esc, [1])
        self.assertTrue(okno.is_fullscreen())
        # Vrstica se v celozaslonskem nacinu skrije in pokaze ob zgornjem robu.
        self.assertTrue(self._vrti(lambda: not v.razkrij.get_reveal_child(), 5))
        v._premik(None, 400, 2)
        self.assertTrue(v.razkrij.get_reveal_child())
        # Drzan Esc (casovnik) zapusti cel zaslon; spust po tem ne gre napravi.
        v._tipka_dol(None, Gdk.KEY_Escape, 0, 0)
        v._tipka_dol(None, Gdk.KEY_Escape, 0, 0)
        self.assertTrue(self._vrti(lambda: not okno.is_fullscreen(), 3))
        v._tipka_gor(None, Gdk.KEY_Escape, 0, 0)
        self.assertEqual(esc, [1])
        # V oknu Esc ni ujet (gre napravi po obicajni poti gledalca).
        self.assertFalse(v._tipka_dol(None, Gdk.KEY_Escape, 0, 0))
        # Super+Tab samo, ce Safeer OS ponuja Prostore.
        self.assertFalse(v._tipka_dol(None, Gdk.KEY_Tab, 0, Gdk.ModifierType.SUPER_MASK))
        c.ob_prostorih = prostori.append
        self.assertTrue(v._tipka_dol(None, Gdk.KEY_Tab, 0, Gdk.ModifierType.SUPER_MASK))
        self.assertTrue(v._tipka_dol(None, Gdk.KEY_Left, 0, Gdk.ModifierType.SUPER_MASK | Gdk.ModifierType.ALT_MASK))
        self.assertEqual(prostori, [{"smer": 1, "od": "pc-1-control"}, {"sosednji": -1, "od": "pc-1-control"}])


if __name__ == "__main__":
    unittest.main()
