"""Safeer OS in Safeer Control v enem procesu (core/en_proces.py, 12. 10. 2026)."""
import os
import subprocess
import tempfile
import threading
import unittest

from core import en_proces, link_predvajanje

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class NaGlavni(unittest.TestCase):
    def tearDown(self):
        en_proces.nastavi_os(None)
        en_proces.nastavi_control(None)

    def test_z_glavne_niti_takoj(self):
        self.assertEqual(en_proces.na_glavni(lambda: 7), 7)

    def test_iz_druge_niti_prek_glavne_zanke(self):
        from gi.repository import GLib
        zanka = GLib.MainLoop()
        izid, nit_klica = {}, {}

        def delo():
            def fn():
                nit_klica["glavna"] = threading.current_thread() is threading.main_thread()
                return 42
            izid["v"] = en_proces.na_glavni(fn, cas=5)
            GLib.idle_add(zanka.quit)
        threading.Thread(target=delo, daemon=True).start()
        GLib.timeout_add_seconds(10, zanka.quit)
        zanka.run()
        self.assertEqual(izid.get("v"), 42)
        self.assertTrue(nit_klica.get("glavna"))

    def test_brez_glavne_zanke_vrne_privzeto(self):
        izid = {}
        t = threading.Thread(target=lambda: izid.setdefault("v", en_proces.na_glavni(lambda: 1, cas=0.2, privzeto="cas")))
        t.start()
        t.join(3)
        self.assertEqual(izid.get("v"), "cas")

    def test_vgrajen(self):
        self.assertFalse(en_proces.vgrajen())
        en_proces.nastavi_os(object())
        self.assertFalse(en_proces.vgrajen())
        en_proces.nastavi_control(object())
        self.assertTrue(en_proces.vgrajen())


class PredvajanjeBrezDbus(unittest.TestCase):
    def tearDown(self):
        en_proces.nastavi_os(None)

    def test_control_vpraša_safeer_os_neposredno(self):
        klici = []

        def klic(metoda, argumenti):
            klici.append((metoda, argumenti))
            return {"ok": True, "stanje": "predvaja"}
        en_proces.nastavi_os(object(), klic=klic)
        self.assertTrue(link_predvajanje.safeer_os_tece())
        self.assertEqual(link_predvajanje.stanje_safeer_os()["stanje"], "predvaja")
        self.assertTrue(link_predvajanje.odstrani_prenos_safeer_os("abc") is not None)
        self.assertEqual(klici[0], ("Stanje", []))
        self.assertEqual(klici[-1][0], "OdstraniPrenos")

    def test_neuspeh_je_none(self):
        en_proces.nastavi_os(object(), klic=lambda m, a: {"ok": False})
        self.assertIsNone(link_predvajanje.stanje_safeer_os())


class Paket(unittest.TestCase):
    def test_safeer_os_nosi_control(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["bash", os.path.join(KOREN, "packaging", "install_os_payload.sh"), d + "/usr"],
                           check=True, capture_output=True)
            lib = os.path.join(d, "usr", "lib", "safeer-os")
            for pot in ("safeer_control.py", "core/en_proces.py", "core/safeer_link.py", "assets/link/index.html",
                        "packaging/VERSION_CONTROL", "packaging/VERSION_OS", "safeer_os.py"):
                self.assertTrue(os.path.isfile(os.path.join(lib, pot)), pot)


class Koda(unittest.TestCase):
    """Klici Safeer OS -> Control in Control -> Safeer OS ne smejo iti prek D-Bus samemu sebi."""

    def _beri(self, ime):
        with open(os.path.join(KOREN, ime), encoding="utf-8") as f:
            return f.read()

    def test_safeer_os(self):
        s = self._beri("safeer_os.py")
        for funkcija in ("def nastavi_zaupanje", "def nastavi_predajanje", "def control_dejanje", "def _control_naprave"):
            telo = s.split(funkcija, 1)[1].split("\ndef ", 1)[0]
            self.assertIn("en_proces.control_app()", telo, funkcija)
        self.assertIn("en_proces.nastavi_os(self, klic=self._predvajanje_neposredno)", s)
        self.assertIn("def _vgradi_control", s)

    def test_safeer_control(self):
        s = self._beri("safeer_control.py")
        self.assertIn('en_proces.os_app().activate_action("ponudba"', s)
        telo = s.split("def _znova_zazeni", 1)[1].split("\n    def ", 1)[0]
        self.assertLess(telo.index("if VGRAJEN"), telo.index("os.execv"))   # nikoli exec procesa Safeer OS


if __name__ == "__main__":
    unittest.main()
