"""Zunanji programi ne podedujejo nasih zasebnih poti (core/zasebni_webkit.py, lastnik 18. 10. 2026).

Safeer OS ima v okolju GI_TYPELIB_PATH in GST_PLUGIN_PATH s predpono nasega WebKita (/usr/lib/safeer-webkit), AppImage
pa LD_LIBRARY_PATH, PYTHONHOME ... na $APPDIR. Program, ki ga uporabnik odpre iz Safeer OS, mora dobiti sistemsko okolje;
nasi pomozni procesi (Safeer Control, ponovni zagon) ga obdrzijo.
"""
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import zasebni_webkit as zw  # noqa: E402

W = "/usr/lib/safeer-webkit"   # paket safeer-webkit (od 19. 10. 2026); stare kopije glej spodaj


class OkoljeZaZunanje(unittest.TestCase):
    def test_deb_odstrani_samo_nase_poti(self):
        okolje = {
            "GI_TYPELIB_PATH": W + "/lib/girepository-1.0:/opt/moje/typelibi",
            "GST_PLUGIN_PATH": W + "/lib/gstreamer-1.0",
            "LD_LIBRARY_PATH": "/opt/moje/lib:" + W + "/lib",
            "PATH": "/usr/local/bin:/usr/bin",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
            "DISPLAY": ":0",
            "HOME": "/home/preizkus",
        }
        cisto = zw.okolje_za_zunanje(okolje)
        self.assertEqual(cisto["GI_TYPELIB_PATH"], "/opt/moje/typelibi")       # uporabnikova pot ostane
        self.assertNotIn("GST_PLUGIN_PATH", cisto)                              # samo nasa: spremenljivke ni
        self.assertEqual(cisto["LD_LIBRARY_PATH"], "/opt/moje/lib")
        for ime in ("PATH", "DBUS_SESSION_BUS_ADDRESS", "DISPLAY", "HOME"):
            self.assertEqual(cisto[ime], okolje[ime])
        self.assertIn(W, okolje["GI_TYPELIB_PATH"], "vhodni slovar ostane nespremenjen")

    def test_predpona_iz_nastavi_in_brskalnik(self):
        with mock.patch.object(zw, "_nastavljena", "/opt/safeer-preizkus/webkit"):
            cisto = zw.okolje_za_zunanje({"GI_TYPELIB_PATH": "/opt/safeer-preizkus/webkit/lib/girepository-1.0",
                                          "GST_PLUGIN_PATH": "/usr/lib/safeer-browser/webkit/lib/gstreamer-1.0:/x"})
        self.assertNotIn("GI_TYPELIB_PATH", cisto)
        self.assertEqual(cisto["GST_PLUGIN_PATH"], "/x")

    def test_appimage(self):
        a = "/tmp/.mount_SafeerXYZ"
        okolje = {
            "APPIMAGE": "/home/preizkus/Safeer-OS.AppImage", "APPDIR": a, "ARGV0": "Safeer-OS.AppImage", "OWD": "/home/p",
            "PATH": a + "/usr/bin:/usr/local/bin:/usr/bin",
            "LD_LIBRARY_PATH": a + "/usr/lib:" + a + "/usr/lib/x86_64-linux-gnu",
            "PYTHONHOME": a + "/usr", "PYTHONPATH": a + "/usr/lib/python3/dist-packages", "PYTHONNOUSERSITE": "1",
            "GI_TYPELIB_PATH": a + "/usr/lib/x86_64-linux-gnu/girepository-1.0",
            "GSETTINGS_SCHEMA_DIR": a + "/usr/share/glib-2.0/schemas",
            "XDG_DATA_DIRS": a + "/usr/share:/usr/local/share:/usr/share",
            "WEBKIT_EXEC_PATH": a + "/usr/lib/x86_64-linux-gnu/webkitgtk-6.0", "SAFEER_PORTABLE": "1",
        }
        cisto = zw.okolje_za_zunanje(okolje)
        self.assertEqual(cisto["PATH"], "/usr/local/bin:/usr/bin")
        self.assertEqual(cisto["XDG_DATA_DIRS"], "/usr/local/share:/usr/share")
        for ime in ("LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH", "GI_TYPELIB_PATH", "GSETTINGS_SCHEMA_DIR",
                    "WEBKIT_EXEC_PATH", "APPIMAGE", "APPDIR", "ARGV0", "OWD", "PYTHONNOUSERSITE", "SAFEER_PORTABLE"):
            self.assertNotIn(ime, cisto, ime)

    def test_flatpak_ostane_nedotaknjen(self):
        okolje = {"FLATPAK_ID": "io.github.memelandfaner.SafeerOS", "GI_TYPELIB_PATH": "/app/lib/girepository-1.0",
                  "LD_LIBRARY_PATH": "/app/lib", "PATH": "/app/host-bin:/app/bin:/usr/bin"}
        self.assertEqual(zw.okolje_za_zunanje(okolje), okolje)

    def test_mapa_z_istim_zacetkom_ni_nasa(self):
        okolje = {"LD_LIBRARY_PATH": W + "-drugo/lib:" + W + "/lib/../lib"}
        self.assertEqual(zw.okolje_za_zunanje(okolje)["LD_LIBRARY_PATH"], W + "-drugo/lib")


class ZagonPrekGio(unittest.TestCase):
    """Pravi zagon prek Gio.AppLaunchContext (kot meni, »Odpri z«, privzeti program): otrok nasih poti nima."""

    def test_otrok_nima_nasih_poti(self):
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib
        with tempfile.TemporaryDirectory() as d:
            izpis = os.path.join(d, "okolje")
            okolje = {"GI_TYPELIB_PATH": W + "/lib/girepository-1.0", "GST_PLUGIN_PATH": "/x:" + W + "/lib/gstreamer-1.0"}
            with mock.patch.dict(os.environ, okolje):
                kontekst = zw.kontekst_za_zunanje(Gio)
                vidi = dict(v.split("=", 1) for v in kontekst.get_environment())
                self.assertNotIn("GI_TYPELIB_PATH", vidi)
                self.assertEqual(vidi.get("GST_PLUGIN_PATH"), "/x")
                program = Gio.AppInfo.create_from_commandline(
                    "sh -c 'env > %s'" % izpis, "preizkus", Gio.AppInfoCreateFlags.NONE)
                self.assertTrue(program.launch([], kontekst))
                # Nas proces ostane, kot je (WebKit spletnemu procesu poda dav1ddec).
                self.assertEqual(os.environ["GST_PLUGIN_PATH"], okolje["GST_PLUGIN_PATH"])
            konec = time.monotonic() + 20
            while time.monotonic() < konec and not (os.path.exists(izpis) and os.path.getsize(izpis)):
                GLib.MainContext.default().iteration(False)
                time.sleep(0.05)
            time.sleep(0.2)
            with open(izpis, encoding="utf-8") as f:
                otrok = dict(v.split("=", 1) for v in f.read().splitlines() if "=" in v)
        self.assertNotIn("GI_TYPELIB_PATH", otrok)
        self.assertEqual(otrok.get("GST_PLUGIN_PATH"), "/x")

    def test_subprocess_z_okoljem(self):
        with mock.patch.dict(os.environ, {"LD_LIBRARY_PATH": W + "/lib"}):
            r = subprocess.run([sys.executable, "-c", "import os; print(os.environ.get('LD_LIBRARY_PATH', '-'))"],
                               capture_output=True, text=True, env=zw.okolje_za_zunanje(), timeout=30)
        self.assertEqual(r.stdout.strip(), "-")


class ZaganjalisciUporabljajoCistoOkolje(unittest.TestCase):
    """Vsa mesta, kjer Safeer OS odpre program uporabnika, podajo cisto okolje (varuje pred novim zagonom brez njega)."""

    MESTA = {
        "core/os_programi.py": ["def zazeni("],
        "core/os_odpri_z.py": ["def odpri_z("],
        "core/os_datoteke.py": ["def odpri(", "def pokazi_v_mapi("],
        "core/namizni_programi.py": ["def zazeni("],
        "core/link_programi.py": ["def zazeni("],
        "core/uporabniske_skripte.py": ["def zazeni_shell("],
        "core/os_sistem.py": ["def _v_ozadju("],
        "core/os_media.py": ["def odpri("],
        "core/os_dock.py": ["def osvezi("],
        "core/os_splet.py": ["def _zunanji_program_nadaljuj(", "def _odpri_datoteko("],
        "safeer_os.py": ["def _zazeni_orodje(", "def _zazeni_vnos_z(", "def _odpri_v_brskalniku("],
        "safeer_control.py": ["def odpri_naslov("],
    }

    def test_vsa_mesta(self):
        for datoteka, funkcije in self.MESTA.items():
            with open(os.path.join(KOREN, datoteka), encoding="utf-8") as d:
                vir = d.read()
            for funkcija in funkcije:
                self.assertIn(funkcija, vir, "%s: ni %s" % (datoteka, funkcija))
                i = vir.index(funkcija)
                konec = vir.find("\n    def ", i + 1)
                konec2 = vir.find("\ndef ", i + 1)
                telo = vir[i:min(k for k in (konec, konec2, len(vir)) if k > 0)]
                self.assertTrue("okolje_za_zunanje()" in telo or "kontekst_za_zunanje(" in telo
                                or "_kontekst_zunanjega()" in telo, "%s %s" % (datoteka, funkcija))

    def test_sway_drugi_zaslon(self):
        with open(os.path.join(KOREN, "core", "link_sway.py"), encoding="utf-8") as d:
            vir = d.read()
        self.assertEqual(vir.count("zasebni_webkit.okolje_za_zunanje()"), 2)
        self.assertNotIn("for k, v in os.environ.items() if k not in", vir)


if __name__ == "__main__":
    unittest.main()
