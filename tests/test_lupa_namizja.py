"""Iskalna lupa na namizju QML izven poti (lastnik, 19. 10. 2026): zlozena, dokler je ne uporabis; klik, Ctrl+K ali
tipkanje kjerkoli (kot Rofi) jo odpre; v njej je Safeer Agent. Namizje QML offscreen z laznim SafeerOS."""
import os
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class LupaNamizja(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import PySide6  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("PySide6 ni namescen")
        os.environ["QT_QPA_PLATFORM"] = os.environ.get("QT_QPA_PLATFORM") or "offscreen"  # rezervacija "" (okolje_procesa)
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["test"])

    def _pocakaj(self, pogoj, cas=4.0):
        from gi.repository import GLib
        from PySide6.QtCore import QCoreApplication
        konec = time.monotonic() + cas
        while time.monotonic() < konec:
            QCoreApplication.processEvents()
            GLib.MainContext.default().iteration(False)
            if pogoj():
                return True
            time.sleep(0.02)
        return pogoj()

    def _namizje(self, platforma="linux", lupa=None):
        import safeer_os as so
        from core import os_lupina
        klici = self.klici = []

        class Os:
            shramba = {}

            def _zacetek(self):
                return {"jezik": "sl", "platforma": platforma, "mape": [], "agent": {"na_voljo": False}}

            def _obdelaj_klic(self, pogled, klic_id, metoda, a):
                klici.append((metoda, a))
                odg = {"predvajalnikStanje": {}, "agentVprasaj": {"ok": True, "koda": "", "povzetek": "Utišano na Dnevna soba."}}
                if metoda == "priljubljenoSeznam" and lupa:
                    odg[metoda] = {"datoteke": [], "programi": [], "kategorije": {}, "nastavitve": {"lupa": lupa}, "rod": 1}
                pogled.qml_odgovor(klic_id, True, odg.get(metoda, []))
        for z in (mock.patch.object(so, "_jezik", return_value="sl"),
                  mock.patch.object(so, "videz_cinnamon", return_value={"naVoljo": True, "kontrast": False, "tekstOdstotek": 100})):
            z.start()
            self.addCleanup(z.stop)
        n = os_lupina.Namizje(Os(), v_oknu=True)
        self.addCleanup(n.okno.close)
        n.okno.resize(1280, 800)
        n.okno.show()
        self.koren = n.okno.rootObject()
        self.assertTrue(self._pocakaj(lambda: self.koren.property("platforma") == platforma))
        self.okno = n.okno
        return n

    def _el(self, ime):
        from PySide6.QtCore import QObject
        return self.koren.findChild(QObject, ime)

    def _tipka(self, kljuc, besedilo="", mod=None):
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QGuiApplication, QKeyEvent
        mod = mod or Qt.KeyboardModifier.NoModifier
        for vrsta in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QGuiApplication.sendEvent(self.okno, QKeyEvent(vrsta, kljuc, mod, besedilo))
        self._pocakaj(lambda: False, 0.3)

    def test_zlozena_privzeto_brez_skoka_panelov(self):
        from PySide6.QtCore import Qt
        self._namizje()
        k, iskanje, cipi, medijski, polje = self.koren, self._el("iskanje"), self._el("vrsticaCipov"), self._el("medijski"), self._el("iskalnoPolje")
        self.assertTrue(k.property("lupaZlozljiva"))
        self.assertTrue(self._pocakaj(lambda: not k.property("lupaOdprta") and iskanje.property("width") <= 300))
        self.assertEqual(iskanje.property("height"), 44)
        self.assertTrue(self._el("namigLupe").property("visible"), "namig Ctrl+K")
        # Cipi (Safeer Link, Sporocila) v isti vrstici desno od lupe; paneli zato 26 px visje kot prej (104 -> 80).
        sredina = k.property("sredinaLupe")
        self.assertAlmostEqual(cipi.property("y") + cipi.property("height") / 2, sredina, delta=1)
        self.assertGreater(cipi.property("x"), iskanje.property("x") + iskanje.property("width"))
        self.assertAlmostEqual(medijski.property("y"), 80, delta=1)
        vrh = medijski.property("y")
        # Tipkanje kjerkoli (fokus nima nobeno polje) odpre lupo s tem znakom - paneli ostanejo na mestu.
        self._tipka(Qt.Key.Key_R, "r")
        self._tipka(Qt.Key.Key_A, "a")
        self.assertEqual(polje.property("text"), "ra")
        self.assertTrue(polje.property("activeFocus") and k.property("lupaOdprta"))
        self.assertTrue(self._pocakaj(lambda: iskanje.property("width") > 500 and iskanje.property("height") == 54))
        self.assertAlmostEqual(iskanje.property("y") + iskanje.property("height") / 2, sredina, delta=1)
        self.assertEqual(medijski.property("y"), vrh)
        self.assertFalse(cipi.property("visible"), "cipi se umaknejo razsirjeni lupi")
        # Escape: najprej pocisti, nato lupo zlozi (fokus namizju).
        self._tipka(Qt.Key.Key_Escape)
        self.assertEqual(polje.property("text"), "")
        self.assertTrue(polje.property("activeFocus"))
        self._tipka(Qt.Key.Key_Escape)
        self.assertFalse(polje.property("activeFocus") or k.property("lupaOdprta"))
        self.assertTrue(self._pocakaj(lambda: iskanje.property("width") <= 300))
        # Ctrl+K odpre lupo od koderkoli; Ctrl+crka in presledek ne pisejo v lupo.
        self._tipka(Qt.Key.Key_Escape)
        self._tipka(Qt.Key.Key_T, "", Qt.KeyboardModifier.ControlModifier)
        self._tipka(Qt.Key.Key_Space, " ")
        self.assertEqual(polje.property("text"), "")
        self.assertFalse(k.property("lupaOdprta"))
        self._tipka(Qt.Key.Key_K, "", Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(polje.property("activeFocus") and k.property("lupaOdprta"))

    def _nikoli_prekrivanja(self, trajanje=0.6):
        """Ves cas (tudi med animacijo) so cipi desno od lupe in par je na sredini okna."""
        from gi.repository import GLib
        from PySide6.QtCore import QCoreApplication
        iskanje, cipi = self._el("iskanje"), self._el("vrsticaCipov")
        konec = time.monotonic() + trajanje
        while time.monotonic() < konec:
            QCoreApplication.processEvents()
            GLib.MainContext.default().iteration(False)
            desno = iskanje.property("x") + iskanje.property("width")
            self.assertGreaterEqual(cipi.property("x"), desno + 11, "cipi cez lupo")
            time.sleep(0.01)
        levo = iskanje.property("x")
        desno = self.koren.property("width") - cipi.property("x") - cipi.property("width")
        self.assertAlmostEqual(levo, desno, delta=2, msg="lupa in cipi skupaj na sredini")

    def test_cipi_nikoli_cez_lupo(self):
        """Testni PC 20. 10. 2026 (aplikacija v oknu 1130 x 720): ko je Safeer Link nasel naprave in je cip postal sirsi
        (»Safeer Link · 6 naprav«), se je cip 8-10 s prekrival z iskalnim poljem. Cipi zdaj sledijo dejanskemu desnemu robu
        lupe, zato prekrivanje ni mogoce - tudi med animacijo in ob spremembi velikosti okna."""
        self._namizje()
        k, iskanje = self.koren, self._el("iskanje")
        self.assertTrue(self._pocakaj(lambda: not k.property("lupaOdprta") and iskanje.property("width") <= 300))
        self._nikoli_prekrivanja(0.3)
        k.setProperty("napravVLinku", 6)          # cip se razsiri
        self._nikoli_prekrivanja()
        self.okno.resize(1130, 720)                # sprememba velikosti okna
        self._nikoli_prekrivanja()
        k.setProperty("napravVLinku", 0)          # cip se zozi
        self._nikoli_prekrivanja()

    def test_polje_programov_obdrzi_svoje_tipke(self):
        from PySide6.QtCore import QMetaObject, Qt
        self._namizje()
        polje_prog = self._el("poljeProgramov")
        QMetaObject.invokeMethod(polje_prog, "forceActiveFocus")
        self.assertTrue(self._pocakaj(lambda: polje_prog.property("activeFocus")))
        self._tipka(Qt.Key.Key_G, "g")
        self.assertEqual(polje_prog.property("text"), "g")
        self.assertEqual(self._el("iskalnoPolje").property("text"), "")

    def test_meni_lupa_kljukica_vidna(self):
        """Vnos »Zlozena iskalna lupa« v meniju namizja pokaze stanje: kljukica v barvi palete, ne pod besedilom (pregled
        19. 10. 2026: privzeti indikator sloga Basic je bil temno siv (#26282a) na temnem meniju in cez prve crke)."""
        from PySide6.QtCore import QMetaObject, Qt
        from PySide6.QtGui import QColor
        self._namizje()
        QMetaObject.invokeMethod(self._el("gumbNastavitve"), "forceActiveFocus")
        self._pocakaj(lambda: False, 0.2)
        self._tipka(Qt.Key.Key_Return)
        self.assertTrue(self._pocakaj(lambda: self._el("meniNamizja").property("visible")))
        m = self._el("meniLupa")
        ind, besedilo = m.property("indicator"), m.property("contentItem")
        self.assertTrue(m.property("checked"))
        self.assertTrue(ind.property("visible"))
        paleta = self.koren.property("paleta")
        paleta = paleta.toVariant() if hasattr(paleta, "toVariant") else paleta
        self.assertEqual(QColor(ind.property("color")).name(), QColor(paleta["poudarek"]).name())
        self.assertGreaterEqual(ind.property("x"), besedilo.property("x") + besedilo.property("contentWidth"), "ne cez besedilo")
        self.assertLessEqual(ind.property("x") + ind.property("width"), m.property("width"))

    def test_razsirjena_po_izbiri_kot_prej(self):
        self._namizje(lupa="razsirjena")
        k = self.koren
        self.assertTrue(self._pocakaj(lambda: not k.property("lupaZlozljiva")))
        self.assertTrue(k.property("lupaOdprta"))
        self.assertTrue(self._pocakaj(lambda: self._el("medijski").property("y") >= 104))
        self.assertFalse(self._el("namigLupe").property("visible"))

    def test_windows_ostane_kot_prej(self):
        self._namizje(platforma="windows")
        self.assertFalse(self.koren.property("lupaZlozljiva"))
        self.assertTrue(self.koren.property("lupaOdprta"))

    def test_safeer_agent_v_lupi(self):
        from PySide6.QtCore import Qt
        self._namizje()
        model = self._el("zadetkiModel")
        self._tipka(Qt.Key.Key_U, "u")
        self._tipka(Qt.Key.Key_T, "t")
        self.assertTrue(self._pocakaj(lambda: model.property("count") > 0))
        vrste = lambda: [model.get(i).property("vrsta").toString() for i in range(model.property("count"))]  # noqa: E731
        self.assertNotIn("agent", vrste(), "brez nastavljenega modela agenta v lupi ni")
        # Nastavitve -> Safeer Agent: dogodek »agent« (safeer_os._agent) - vnos se pokaze, besedilo lupe to pove.
        self.koren.setProperty("agentNaVoljo", True)
        self._tipka(Qt.Key.Key_I, "i")
        self.assertTrue(self._pocakaj(lambda: "agent" in vrste()))
        self.assertEqual(self._el("iskalnoPolje").property("placeholderText"), "Išči ali ukaži Safeer Agentu …")
        # Ctrl+Enter: stavek gre agentu (core/agent/storitev.vprasaj_tukaj).
        self._tipka(Qt.Key.Key_Return, "", Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(self._pocakaj(lambda: ("agentVprasaj", ["uti"]) in self.klici), self.klici[-5:])
        self.assertEqual(self._el("iskalnoPolje").property("text"), "")


if __name__ == "__main__":
    unittest.main()


def test_izbira_lupe_v_priljubljenih(tmp_path):
    """Izbira »Zlozena iskalna lupa« (Nastavitve -> Namizje, meni namizja) je v core/priljubljeno.py - en zapis za
    namizje QML in Nastavitve; privzeto zlozena, drugih vrednosti ni."""
    from core import priljubljeno
    p = priljubljeno.Priljubljeno(str(tmp_path / "priljubljeno.json"))
    assert p.stanje()["nastavitve"]["lupa"] == "zlozena"
    assert p.nastavi("lupa", "razsirjena")["nastavitve"]["lupa"] == "razsirjena"
    assert p.nastavi("lupa", "skrita")["nastavitve"]["lupa"] == "razsirjena"
    assert priljubljeno.Priljubljeno(str(tmp_path / "priljubljeno.json")).stanje()["nastavitve"]["lupa"] == "razsirjena"


def test_stikalo_v_nastavitvah():
    with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
        so = f.read()
    # Glavna nit: brez stanja priljubljenih (stat, fsync) - vedenje preverja tests/test_nastavitve_delov.py.
    assert 'izid["lupa"] = self._priljubljeno().nastavitev("lupa")' in so
    assert 'lupa = "zlozena" if vrednost else "razsirjena"' in so
    assert 'self._priljubljeno().nastavi("lupa", lupa)' in so
