"""Varovalo preizkusov »vmesnik samo iz glavne niti« (tests/varovalo_niti.py) in en pomocnik za glavno nit (naloga 42).

Varovalo se preizkusi na imenskem prostoru Gio (typelib je povsod, kjer je gi) v locenem procesu: ovijanje ostane do
konca procesa in ne sme vplivati na druge preizkuse. Okolje procesa preizkusov se ne spreminja (env=)."""
import json
import os
import subprocess
import sys
import textwrap
import threading
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTI = os.path.join(KOREN, "tests")
sys.path.insert(0, KOREN)
sys.path.insert(0, TESTI)

import varovalo_niti  # noqa: E402

try:
    import gi  # noqa: F401
    from gi.repository import GLib, Gio  # noqa: F401
    IMA_GI = True
except Exception:  # noqa: BLE001 - brez gi se preizkus ovijanja preskoci
    IMA_GI = False

SKRIPT = textwrap.dedent("""
    import json, sys, threading
    sys.path[:0] = [%r, %r]
    from gi.repository import Gio, GLib
    import varovalo_niti
    varovalo_niti.PROSTORI_GI = ("Gio",)
    v = varovalo_niti.Varovalo()
    ovitih = v.namesti_nalozene()
    # Glavna nit: metoda, konstruktor, funkcija prostora, gradnja predmeta - brez krsitve, izidi pravilni.
    f = Gio.File.new_for_path("/tmp")
    izid = {"ovitih": ovitih, "pot": f.get_path(), "ime": Gio.SimpleAction.new("a", None).get_name(),
            "gradnja": Gio.SimpleAction(name="b").get_name(), "vrsta": bool(Gio.content_type_guess("a.txt", None)),
            "razlicica": GLib.MAJOR_VERSION}
    izid["glavna"] = len(v.krsitve)
    def nit():
        g = Gio.File.new_for_path("/etc")
        g.get_basename()
        Gio.content_type_guess("a.txt", None)
        Gio.SimpleAction(name="c")
    t = threading.Thread(target=nit, name="delavec-preizkus")
    t.start(); t.join()
    izid["krsitve"] = sorted({k.klic for k in v.krsitve})
    izid["niti"] = sorted({k.nit for k in v.krsitve})
    izid["mesto"] = all("varovalo-skript" in k.mesto or "<string>" in k.mesto or "line" in k.mesto for k in v.krsitve)
    izid["ponovno"] = v.namesti_nalozene()      # drugic se nic ne ovije dvakrat
    izid["povzetek"] = v.povzetek() or ""
    print(json.dumps(izid))
""") % (KOREN, TESTI)


@unittest.skipUnless(IMA_GI, "ni gi (PyGObject)")
class Varovalo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        okolje = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
        r = subprocess.run([sys.executable, "-c", SKRIPT], capture_output=True, text=True, timeout=60, env=okolje)
        if r.returncode != 0:
            raise AssertionError(r.stderr)
        cls.izid = json.loads(r.stdout.strip().splitlines()[-1])

    def test_glavna_nit_brez_krsitev_in_klici_delajo(self):
        self.assertGreater(self.izid["ovitih"], 100)
        self.assertEqual(self.izid["glavna"], 0)
        self.assertEqual(self.izid["pot"], "/tmp")
        self.assertEqual(self.izid["ime"], "a")
        self.assertEqual(self.izid["gradnja"], "b")
        self.assertTrue(self.izid["vrsta"])

    def test_druga_nit_zapisana(self):
        for klic in ("Gio.File.new_for_path", "Gio.File.get_basename", "Gio.content_type_guess"):
            self.assertIn(klic, self.izid["krsitve"])
        self.assertTrue(any(k.endswith("()") for k in self.izid["krsitve"]), "gradnja predmeta iz niti")
        self.assertEqual(self.izid["niti"], ["delavec-preizkus"])
        self.assertIn("Vmesnik izven glavne niti", self.izid["povzetek"])

    def test_ne_ovije_dvakrat(self):
        self.assertEqual(self.izid["ponovno"], 0)


class Nacin(unittest.TestCase):
    def test_iz_okolja(self):
        self.assertEqual(varovalo_niti.Varovalo.iz_okolja({}).nacin, "strogo")
        self.assertEqual(varovalo_niti.Varovalo.iz_okolja({"SAFEER_VAROVALO_NITI": "porocilo"}).nacin, "porocilo")
        self.assertFalse(varovalo_niti.Varovalo.iz_okolja({"SAFEER_VAROVALO_NITI": "0"}).vklopljeno)
        self.assertEqual(varovalo_niti.Varovalo.iz_okolja({"SAFEER_VAROVALO_NITI": "kaj"}).nacin, "strogo")

    def test_conftest_podre_preizkus(self):
        with open(os.path.join(TESTI, "conftest.py"), encoding="utf-8") as f:
            s = f.read()
        self.assertIn("_varovalo.namesti_nalozene()", s)
        self.assertIn('if krsitve and _varovalo.nacin == "strogo":\n        pytest.fail(', s)
        self.assertEqual(set(varovalo_niti.PROSTORI_GI) & {"Gtk", "Gdk", "WebKit"}, {"Gtk", "Gdk", "WebKit"})
        self.assertIn(("PySide6.QtQuick", "QQuickView"), varovalo_niti.RAZREDI_QT)

    def test_razred_qt_nadomestek(self):
        """Ovijanje razreda (pot za Qt): klic iz druge niti zapisan, iz glavne ne; signal ni ovit (ni v razredu)."""
        class Okno:
            def setTitle(self, t):  # noqa: N802 - ime kot v Qt
                self.naslov = t
                return t

        v = varovalo_niti.Varovalo()
        self.assertGreaterEqual(v.ovij_razred(Okno, lambda c: c is Okno, "QtQuick"), 1)
        o = Okno()
        self.assertEqual(o.setTitle("a"), "a")
        self.assertEqual(v.krsitve, [])
        t = threading.Thread(target=lambda: o.setTitle("b"), name="qt-delavec")
        t.start()
        t.join()
        self.assertEqual([k.klic for k in v.krsitve], ["QtQuick.Okno.setTitle"])
        self.assertEqual(o.naslov, "b")


@unittest.skipUnless(IMA_GI, "ni gi (PyGObject)")
class EnPomocnik(unittest.TestCase):
    def test_teamwork_uporabi_en_proces(self):
        with open(os.path.join(KOREN, "core", "link_teamwork.py"), encoding="utf-8") as f:
            s = f.read()
        telo = s[s.index("def na_glavni_niti("):s.index("def _razlog_diska(")]
        self.assertIn("en_proces.na_glavni(delo, cas=rok_s, privzeto=None, prednost=GLib.PRIORITY_DEFAULT)", telo)
        self.assertNotIn("threading.Event()", telo)

    def test_lastnik_zanke_ne_caka_nase(self):
        """Nit, ki vrti privzeto zanko, delo izvede takoj (prej v en_proces cakanje do roka)."""
        from gi.repository import GLib
        from core import en_proces
        izid = {}

        def nit():
            kontekst = GLib.MainContext.default()
            if not kontekst.acquire():
                izid["napaka"] = "zanka zasedena"
                return
            try:
                izid["v"] = en_proces.na_glavni(lambda: threading.current_thread().name, cas=0.5, privzeto="rok")
            finally:
                kontekst.release()
        t = threading.Thread(target=nit, name="lastnik-zanke")
        t.start()
        t.join(5)
        self.assertNotIn("napaka", izid)
        self.assertEqual(izid.get("v"), "lastnik-zanke")

    def test_iz_niti_na_glavno(self):
        from gi.repository import GLib
        from core import en_proces
        zanka = GLib.MainLoop()
        izid = {}

        def nit():
            izid["v"] = en_proces.na_glavni(lambda: threading.current_thread() is threading.main_thread(), cas=5,
                                            prednost=GLib.PRIORITY_DEFAULT)
            GLib.idle_add(zanka.quit)
        threading.Thread(target=nit, daemon=True).start()
        GLib.timeout_add_seconds(10, zanka.quit)
        zanka.run()
        self.assertIs(izid.get("v"), True)


class KatalogNaGlavni(unittest.TestCase):
    def test_katalog_pred_nitjo(self):
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            s = f.read()
        i = s.index("def delo_katalog():")
        self.assertIn("katalog = self._katalog_most()", s[i - 400:i])
        self.assertIn("katalog.izvedi(metoda, a)", s[i:i + 300])
        self.assertNotIn("self._katalog_most().izvedi", s[i:i + 300])


if __name__ == "__main__":
    unittest.main()
