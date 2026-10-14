"""Aplikacija Safeer OS v oknu (GNOME, KDE …) = isto namizje QML kot namizno okolje (lastnik, 14. 10. 2026)."""
import os
import unittest

from core import os_lupina
from besedila_namizja import besedila, stevilo  # noqa: E402 - skupni slovar namizja

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class VelikostOkna(unittest.TestCase):
    def test_kot_staro_glavno_okno(self):
        self.assertEqual(os_lupina.velikost_okna(1920, 1040), (1440, 900))
        self.assertEqual(os_lupina.velikost_okna(1366, 728), (1229, 655))
        self.assertEqual(os_lupina.velikost_okna(800, 600), (960, 620))   # najmanj minimum okna


class OknoQml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import PySide6  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("PySide6 ni namescen")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["test"])

    def _namizje(self, v_oknu):
        class Os:
            shramba = {}
        return os_lupina.Namizje(Os(), v_oknu=v_oknu)

    def test_okno_ima_rob_namizje_ne(self):
        from PySide6.QtCore import Qt
        okno = self._namizje(True)
        self.assertEqual(okno.okno.errors(), [])
        self.assertFalse(okno.okno.flags() & Qt.WindowType.FramelessWindowHint)
        self.assertEqual(okno.okno.title(), "Safeer OS")
        namizje = self._namizje(False)
        self.assertTrue(namizje.okno.flags() & Qt.WindowType.WindowStaysOnBottomHint)

    def test_gumb_nastavitve_samo_v_oknu(self):
        from PySide6.QtCore import QObject
        n = self._namizje(True)
        koren = n.okno.rootObject()
        gumb = koren.findChild(QObject, "gumbNastavitve")
        self.assertIsNotNone(gumb)
        self.assertFalse(gumb.property("visible"))
        koren.setProperty("vOknu", True)
        self.assertTrue(gumb.property("visible"))


class Zaprtje(OknoQml):
    def test_zaprtje_okna_poklice_ob_koncu(self):
        klici = []

        class Os:
            shramba = {}
        n = os_lupina.Namizje(Os(), ob_koncu=lambda: klici.append(1), v_oknu=True)
        n.okno.show()
        n.okno.close()
        self.assertEqual(klici, [1])


class Zagon(unittest.TestCase):
    def test_okno_iz_menija_odpre_qml(self):
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            vir = f.read()
        self.assertIn("self._ustvari_qml_okno()", vir)
        self.assertIn('app._qml_okno = "--okno" in sys.argv[1:]', vir)
        self.assertIn("v_oknu=True", vir)


if __name__ == "__main__":
    unittest.main()


class SkupineProgramov(unittest.TestCase):
    def test_imena_skupin_v_jeziku_vmesnika(self):
        import re
        qml = open(os.path.join(KOREN, "assets", "os", "qml", "Namizje.qml"), encoding="utf-8").read()
        for k in ("sk_pisarna", "sk_predstavnost", "sk_orodja", "sk_sistem", "sk_splet"):
            self.assertEqual(stevilo(k), 6, k)
        self.assertNotIn('"Predstavnost"', open(os.path.join(KOREN, "assets", "os", "qml", "Programi.qml"), encoding="utf-8").read())


class KratkaPot(OknoQml):
    def test_domaca_mapa_kot_tilda(self):
        class Os:
            shramba = {}
        n = os_lupina.Namizje(Os(), v_oknu=True)
        koren = n.okno.rootObject()
        koren.setProperty("dom", "/home/ana")
        from PySide6.QtCore import QMetaObject, Q_RETURN_ARG, Q_ARG
        def kp(p):
            return QMetaObject.invokeMethod(koren, "kratkaPot", Q_RETURN_ARG("QVariant"), Q_ARG("QVariant", p))
        self.assertEqual(kp("/home/ana/Dokumenti/a.odt"), "~/Dokumenti/a.odt")
        self.assertEqual(kp("/home/ana"), "~")
        self.assertEqual(kp("/home/anabela/x"), "/home/anabela/x")
        self.assertEqual(kp("/media/usb/x"), "/media/usb/x")


class PregledPopravki(unittest.TestCase):
    """Pregled kode 14. 10. 2026."""

    def test_obnova_ne_nalozi_zaprtega_pogleda(self):
        from core import os_stabilnost
        klici = []

        class P:
            def connect(self, _s, f):
                self.f = f

            def reload(self):
                klici.append(1)
        cakajo = []
        G = type("G", (), {"timeout_add": staticmethod(lambda _ms, f: cakajo.append(f))})
        W = type("W", (), {})
        p = P()
        os_stabilnost.obnovi_ob_padcu(W, G, p, "preizkus", "x")
        p.f(p, object())
        os_stabilnost.oznaci_zaprt(p)
        for f in cakajo:
            f()
        self.assertEqual(klici, [])

    def test_zaprto_okno_pocaka_druga_okna(self):
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            vir = f.read()
        self.assertIn("ob_koncu=lambda: GLib.idle_add(self._zaprto_qml_okno)", vir)
        del_ = vir[vir.index("def _zaprto_qml_okno"):]
        self.assertLess(del_.index("get_windows()"), del_.index("self._koncaj()"))

    def test_temno_brez_prijav(self):
        with open(os.path.join(KOREN, "safeer_mint.py"), encoding="utf-8") as f:
            self.assertIn("AUTH_SCRIPT_EXCLUSIONS)", f.read())


class DatotekeMeni(unittest.TestCase):
    def test_odpri_z_in_poslji(self):
        qml = open(os.path.join(KOREN, "assets", "os", "qml", "Datoteke.qml"), encoding="utf-8").read()
        for klic in ('"programiZaDatoteko"', '"odpriZ"', '"napraveZaPosiljanje"', '"posljiNapravi"', '"posljiStanje"'):
            self.assertIn(klic, qml)
        nam = open(os.path.join(KOREN, "assets", "os", "qml", "Namizje.qml"), encoding="utf-8").read()
        import re
        for k in ("odpriZ", "privzetProgram", "posljiNaNapravo", "posNiNaprav", "posPosiljam", "posPoslano", "posNapaka"):
            self.assertEqual(stevilo(k), 6, k)


class LupaUcenje(OknoQml):
    def test_naucen_zadetek_je_prvi(self):
        import time
        from PySide6.QtCore import QObject, QMetaObject, Q_ARG

        class Os:
            shramba = {}
        n = os_lupina.Namizje(Os(), v_oknu=True)
        z = n.okno.rootObject().findChild(QObject, "zadetki")
        self.assertIsNotNone(z)
        z.setProperty("izbire", [["calc", "program:org.gnome.Calculator.desktop", int(time.time()), False]])
        z.setProperty("zadnjiNiz", "calc")
        from PySide6.QtCore import Q_RETURN_ARG
        mesto = QMetaObject.invokeMethod(z, "najMesto", Q_RETURN_ARG("QVariant"),
                                         Q_ARG("QVariant", ["splet", "program:org.gnome.Calculator.desktop"]))
        self.assertEqual(mesto, 1)
        z.setProperty("zadnjiNiz", "drugo")
        mesto = QMetaObject.invokeMethod(z, "najMesto", Q_RETURN_ARG("QVariant"),
                                         Q_ARG("QVariant", ["splet", "program:org.gnome.Calculator.desktop"]))
        self.assertEqual(mesto, -1)
