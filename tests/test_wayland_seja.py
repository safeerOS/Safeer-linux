"""Seja Wayland (Ubuntu 24.04 GNOME, KDE, sway) - ena odlocitev v core/seja_prikaza.py (18. 10. 2026).

Na Waylandu je DISPLAY nastavljen (XWayland), zato je preverba »ali je DISPLAY« lazno kazala X11: zajem korena crn,
seznam oken samo programi XWayland, idle iz XWaylanda. Tu preverimo, da se vsi moduli odlocijo po seji."""

import os
import pathlib
import subprocess
import shutil
import sys
import unittest
from unittest import mock

KOREN = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN))

from core import seja_prikaza  # noqa: E402

GNOME_WAYLAND = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0",
                 "XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}
MINT_X11 = {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "X-Cinnamon"}


class Seja(unittest.TestCase):
    def test_vrsta(self):
        self.assertEqual(seja_prikaza.vrsta(GNOME_WAYLAND), "wayland")
        self.assertEqual(seja_prikaza.vrsta(MINT_X11), "x11")
        # sway iz konzole: brez XDG_SESSION_TYPE, a z WAYLAND_DISPLAY in XWaylandom - prej je veljal za X11
        self.assertEqual(seja_prikaza.vrsta({"WAYLAND_DISPLAY": "wayland-1", "DISPLAY": ":1"}), "wayland")
        self.assertEqual(seja_prikaza.vrsta({}), "")

    def test_namizje(self):
        self.assertEqual(seja_prikaza.namizje(GNOME_WAYLAND), "gnome")
        self.assertEqual(seja_prikaza.namizje(MINT_X11), "cinnamon")
        self.assertEqual(seja_prikaza.namizje({"XDG_CURRENT_DESKTOP": "KDE"}), "kde")
        self.assertEqual(seja_prikaza.namizje({"SWAYSOCK": "/run/x"}), "sway")
        self.assertEqual(seja_prikaza.namizje({"XDG_CURRENT_DESKTOP": "pop:GNOME"}), "gnome")

    def test_zmoznosti(self):
        w = seja_prikaza.zmoznosti(GNOME_WAYLAND, portal=lambda v: True)
        x = seja_prikaza.zmoznosti(MINT_X11, portal=lambda v: True)
        for kljuc in ("namizje", "seznam_oken", "vstavi_okno", "premik_oken", "rezervacija_roba", "zajem_x11",
                      "vnos_xdotool"):
            self.assertFalse(w[kljuc], kljuc)
            self.assertTrue(x[kljuc], kljuc)
        self.assertTrue(w["zajem_portal"] and w["vnos_portal"])
        self.assertFalse(x["zajem_portal"] or x["vnos_portal"])
        self.assertEqual(set(w), set(seja_prikaza.ZMOZNOSTI))
        # Brez portala na Waylandu ni zajema (vmesnik ga ne ponudi)
        self.assertFalse(seja_prikaza.zmoznosti(GNOME_WAYLAND, portal=lambda v: False)["zajem_portal"])


class X11NaWaylandu(unittest.TestCase):
    def test_povezava_zavrnjena(self):
        from core import x11
        with mock.patch.dict(os.environ, GNOME_WAYLAND, clear=False), \
                mock.patch.object(seja_prikaza, "gdk_x11", lambda: False):
            with self.assertRaises(OSError):
                x11.Povezava()
            with self.assertRaises(OSError):
                x11.Povezava(za_nasa_okna=True)
        # GDK prek XWaylanda (GDK_BACKEND=x11): nasa okna so X11 - lastnosti smemo nastaviti, korena pa ne brati
        with mock.patch.dict(os.environ, GNOME_WAYLAND, clear=False), \
                mock.patch.object(seja_prikaza, "gdk_x11", lambda: True):
            with self.assertRaises(OSError):
                x11.Povezava()

    def test_seznam_oken_ni_na_waylandu(self):
        from core import os_okna
        with mock.patch.dict(os.environ, GNOME_WAYLAND, clear=False):
            self.assertIsNone(os_okna._pridobi())
            self.assertFalse(os_okna.na_voljo())

    def test_vgradnja_samo_x11(self):
        from core import namizni_programi
        with mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-1", "DISPLAY": ":1"}, clear=True):
            self.assertFalse(namizni_programi.x11_seja())

    def test_nedejavnost_ne_iz_xwaylanda(self):
        """KDE/sway na Waylandu: XScreenSaver bi bral XWayland (vnos v programe Wayland ne steje) - 0, ne lazna ura."""
        from core import nova_razlicica

        class Gio:
            class BusType:
                SESSION = 0

            @staticmethod
            def bus_get_sync(*_a):
                raise RuntimeError("ni Mutterja")

        with mock.patch.dict(os.environ, GNOME_WAYLAND, clear=False), \
                mock.patch.object(nova_razlicica, "_nedejavnost_x11", lambda: 9999.0):
            self.assertEqual(nova_razlicica.nedejavnost_s(Gio, None), 0.0)
        with mock.patch.dict(os.environ, MINT_X11, clear=True), \
                mock.patch.object(nova_razlicica, "_nedejavnost_x11", lambda: 42.0):
            self.assertEqual(nova_razlicica.nedejavnost_s(Gio, None), 42.0)


class FlatpakZaslon(unittest.TestCase):
    def test_prazen_display_ne_gre_na_gostitelja(self):
        """Flatpak s fallback-x11 na Waylandu nima DISPLAY: prazen --env=DISPLAY= bi gostitelju vzel pravega."""
        from core import gostitelj
        with mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"}, clear=True):
            self.assertEqual(gostitelj.env_zaslona(), ["--env=WAYLAND_DISPLAY=wayland-0"])
        with mock.patch.dict(os.environ, {"DISPLAY": ":0"}, clear=True):
            self.assertEqual(gostitelj.env_zaslona(), ["--env=DISPLAY=:0"])
        for pot in ("core/namizni_programi.py", "core/os_dock.py", "core/safeer_drm.py", "core/gostitelj.py"):
            self.assertNotIn('"--env=DISPLAY=" + os.environ', (KOREN / pot).read_text(encoding="utf-8"), pot)

    def test_ovoji_brez_praznega_zaslona(self):
        skripta = (KOREN / "packaging" / "flatpak_host_wrappers.sh").read_text(encoding="utf-8")
        self.assertIn('${DISPLAY:+"--env=DISPLAY=$DISPLAY"}', skripta)
        self.assertNotIn('--env=DISPLAY="${DISPLAY:-}"', skripta)


class SafeerOsNaWaylandu(unittest.TestCase):
    def setUp(self):
        self.vir = (KOREN / "safeer_os.py").read_text(encoding="utf-8")

    def test_namizje_postane_okno(self):
        self.assertIn("wayland_okno = seja_prikaza.je_wayland() and not posnetek and not v_oknu", self.vir)
        self.assertIn('app._qml_okno = ("--okno" in sys.argv[1:] or wayland_okno)', self.vir)

    def test_delovna_samo_storitve(self):
        self.assertIn("self._delovna_v_ozadju = True", self.vir)
        self.assertIn("if seja_prikaza.je_wayland():\n            # Wayland: delovne povrsine pod okni ni", self.vir)


class Lupina(unittest.TestCase):
    def test_platforma_qt(self):
        from core import os_lupina
        self.assertEqual(os_lupina.platforma_qt(GNOME_WAYLAND), "wayland;xcb")
        self.assertEqual(os_lupina.platforma_qt({"WAYLAND_DISPLAY": "wayland-1"}), "wayland;xcb")
        self.assertEqual(os_lupina.platforma_qt(MINT_X11), "xcb")

    def test_dostopnost_gnome(self):
        """GNOME Dostopnost: vecje besedilo (1,25), visok kontrast, animacije - namizje QML jih prevzame."""
        from core import os_lupina

        class Shema:
            def has_key(self, k):
                return True

        class Vir:
            def lookup(self, ime, _r):
                return Shema()

        class Nastavitve:
            def __init__(self, ime):
                self.ime = ime

            def get_double(self, k):
                return 1.25

            def get_boolean(self, k):
                return True

        class Gio:
            class SettingsSchemaSource:
                @staticmethod
                def get_default():
                    return Vir()

            class Settings:
                new = Nastavitve

        class Gtk:
            class Settings:
                @staticmethod
                def get_default():
                    return mock.Mock(get_property=lambda ime: False)

        d = os_lupina.dostopnost_sistema(Gio, Gtk)
        self.assertEqual(d, {"tekstOdstotek": 125, "kontrast": True, "gibanje": False})
        self.assertEqual(os_lupina.merilo_besedila(d["tekstOdstotek"], 1.0), 1.25)

    def test_qml_spostuje_zmanjsano_gibanje(self):
        mapa = KOREN / "assets" / "os" / "qml"
        for f in mapa.glob("*.qml"):
            s = f.read_text(encoding="utf-8")
            for vrstica in s.splitlines():
                if "Behavior on " in vrstica and "Animation" in vrstica:
                    self.assertIn("enabled: koren.gibanje", vrstica, f.name)
                if "add: Transition" in vrstica:
                    self.assertIn("enabled: koren.gibanje", vrstica, f.name)
        n = (mapa / "Namizje.qml").read_text(encoding="utf-8")
        self.assertIn('property bool gibanje: typeof Gibanje === "undefined" ? true : !!Gibanje', n)
        self.assertIn("if (!koren.gibanje && vstop.running) vstop.complete()", n)
        self.assertIn('setContextProperty("Gibanje"', (KOREN / "core" / "os_lupina.py").read_text(encoding="utf-8"))


@unittest.skipUnless(shutil.which("Xvfb") and shutil.which("xrandr"), "brez Xvfb/xrandr")
class VecMonitorjevX11(unittest.TestCase):
    """RandR 1.5: monitorji, kazalec in zajem enega monitorja (Xvfb z dvema navideznima monitorjema)."""

    def test_monitorji_kazalec_zajem(self):
        koda = r'''
import os, subprocess, sys
sys.path.insert(0, sys.argv[1])
from core import x11
p = x11.Povezava()
subprocess.run(["xrandr", "--setmonitor", "LEVI", "1280/340x1024/270+0+0", "none"], check=True)
subprocess.run(["xrandr", "--setmonitor", "DESNI", "1280/340x1024/270+1280+0", "none"], check=True)
m = p.monitorji()
assert {"LEVI", "DESNI"} <= {x["ime"] for x in m}, m
# Xvfb obdrzi se samodejni monitor izhoda (cez oba): izbere se najmanjsi, ki tocko vsebuje
assert x11.monitor_za_tocko(m, (1500, 300))["ime"] == "DESNI"
assert x11.monitor_za_tocko(m, (100, 100))["ime"] == "LEVI"
s, v, rgb = p.zajemi((1280, 0, 1280, 1024))
assert (s, v, len(rgb)) == (1280, 1024, 1280 * 1024 * 3), (s, v)
assert p.zajemi((5000, 0, 10, 10)) is None
print("OK")
'''
        r = subprocess.run(["xvfb-run", "-a", "-s", "-screen 0 2560x1024x24", sys.executable, "-c", koda, str(KOREN)],
                           capture_output=True, text=True, timeout=60,
                           env={k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE")})
        self.assertIn("OK", r.stdout, r.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
