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


class SpletOb(unittest.TestCase):
    def test_skritje_sprazni_predpomnilnik(self):
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            s = f.read()
        telo = s.split("def _skrij_splet_na_namizju", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("sprazni_predpomnilnik()", telo)
        self.assertIn("timeout_add_seconds(60, self._sprosti_splet_na_namizju)", telo)

    def test_predpomnilnik_brez_zapiranja_zavihkov(self):
        from core import os_splet

        class Upr:
            klici = []

            def clear(self, *a):
                self.klici.append(a)

        class Kontekst:
            def get_website_data_manager(self):
                return Upr()

        class W:
            class WebsiteDataTypes:
                MEMORY_CACHE = 1
        splet = os_splet.VdelaniSplet.__new__(os_splet.VdelaniSplet)
        splet.kontekst, splet.WebKit2, splet.zavihki = Kontekst(), W, ["a", "b"]
        self.assertTrue(splet.sprazni_predpomnilnik())
        self.assertEqual(Upr.klici[0][0], 1)
        self.assertEqual(splet.zavihki, ["a", "b"])


class DrugaAplikacija(unittest.TestCase):
    def test_vgrajen_control_je_gio_application(self):
        """Drugi Gtk.Application v istem procesu se ne registrira (GLib 2.80); Control v procesu Safeer OS je zato
        Gio.Application, okna pa doda Safeer OS."""
        koda = ("import os, sys; os.environ['SAFEER_CONTROL_VGRAJEN']='1'; sys.path.insert(0, %r); "
                "import safeer_control as c; from gi.repository import Gio, Gtk; "
                "print(issubclass(c.SafeerControl, Gtk.Application), issubclass(c.SafeerControl, Gio.Application))" % KOREN)
        izid = subprocess.run(["python3", "-c", koda], capture_output=True, text=True, timeout=60)
        self.assertEqual(izid.stdout.strip().splitlines()[-1], "False True", izid.stderr[-500:])
        with open(os.path.join(KOREN, "safeer_control.py"), encoding="utf-8") as f:
            s = f.read()
        self.assertEqual(s.count("self._dodaj_okno("), 3)
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            self.assertIn('os.environ.pop("SAFEER_CONTROL_VGRAJEN", None)', f.read())


class OmrezniProcesSpleta(unittest.TestCase):
    """libsoup 3.4.4-5ubuntu0.9 pusca povezave prek posrednika: ob sprostitvi Spleta koncamo njegov omrezni proces."""

    def _splet(self):
        from core import os_splet
        s = os_splet.VdelaniSplet.__new__(os_splet.VdelaniSplet)
        s.zavihki, s.aktivni = [], None
        return s, os_splet

    def test_konca_samo_zapomnjeni_proces(self):
        from unittest import mock
        s, os_splet = self._splet()
        s._omrezni_pid = 4242
        klici = []

        class GLib:
            @staticmethod
            def get_monotonic_time():
                return 0

            @staticmethod
            def timeout_add(_ms, fn):
                klici.append(fn)
        s.GLib = GLib
        with mock.patch.object(os_splet, "omrezni_procesi", side_effect=[{4242, 77}, {4242, 77}, {77, 5000}]), \
                mock.patch.object(os_splet.os, "kill") as kill:
            self.assertTrue(s.koncaj_omrezni_proces())
            self.assertIsNone(s._omrezni_pid)
            klici[0]()                     # WebKit je zagnal novega: tudi temu sledimo
        kill.assert_called_once_with(4242, 15)
        self.assertEqual(s._omrezni_pid, 5000)

    def test_ne_ubije_tujega(self):
        from unittest import mock
        s, os_splet = self._splet()
        s._omrezni_pid = 4242          # ze koncan; PID ni vec omrezni proces tega procesa
        with mock.patch.object(os_splet, "omrezni_procesi", return_value={77}), \
                mock.patch.object(os_splet.os, "kill") as kill:
            self.assertFalse(s.koncaj_omrezni_proces())
        kill.assert_not_called()
        s._omrezni_pid = None
        with mock.patch.object(os_splet.os, "kill") as kill:
            self.assertFalse(s.koncaj_omrezni_proces())
        kill.assert_not_called()

    def test_sprostitev_konca_omrezni(self):
        from unittest import mock
        s, os_splet = self._splet()
        with mock.patch.object(os_splet.VdelaniSplet, "koncaj_omrezni_proces") as k:
            s.sprosti_zavihke()
        k.assert_called_once()

    def test_proces_iz_ustvarjanja_konteksta(self):
        """Omrezni proces se zazene ze ob ustvarjanju konteksta - primerjamo s stanjem pred tem."""
        from unittest import mock
        s, os_splet = self._splet()
        s._omrezni_pred, s._stevec = {1}, 0
        klici = []

        class GLib:
            @staticmethod
            def get_monotonic_time():
                return 0

            @staticmethod
            def timeout_add(_ms, fn):
                klici.append(fn)
        s.GLib = GLib
        with mock.patch.object(os_splet, "omrezni_procesi", return_value={1, 55}), \
                mock.patch.object(os_splet.VdelaniSplet, "_nov_pogled", side_effect=RuntimeError("konec")):
            with self.assertRaises(RuntimeError):
                s.nov_zavihek("")
            klici[0]()
        self.assertEqual(s._omrezni_pid, 55)

    def test_iskanje_brez_zacetnega_atributa(self):
        """12. 10. v zivo: AttributeError '_omrezni_pid' v iskanju ob prvem zavihku."""
        from unittest import mock
        s, os_splet = self._splet()
        klici = []

        class GLib:
            @staticmethod
            def get_monotonic_time():
                return 0

            @staticmethod
            def timeout_add(_ms, fn):
                klici.append(fn)
        s.GLib = GLib
        s._stevec = 0
        with mock.patch.object(os_splet, "omrezni_procesi", side_effect=[{1}, {1, 99}]), \
                mock.patch.object(os_splet.VdelaniSplet, "_nov_pogled", side_effect=RuntimeError("konec")):
            with self.assertRaises(RuntimeError):
                s.nov_zavihek("")
            self.assertFalse(klici[0]())          # nasel nov proces -> konec iskanja
        self.assertEqual(s._omrezni_pid, 99)
