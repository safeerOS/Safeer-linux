"""Sporocila Qt v nas dnevnik brez skrivnosti (core/qt_dnevnik.py, naloga 42). Brez pravega Qt: nadomestni QtCore."""
import io
import os
import sys
import threading
import types
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import qt_dnevnik  # noqa: E402


class Kontekst:
    file = "qrc:/os/Namizje.qml"
    line = 42


class QtDnevnik(unittest.TestCase):
    def setUp(self):
        qt_dnevnik._namescen["obravnava"] = None
        self.addCleanup(qt_dnevnik._namescen.__setitem__, "obravnava", None)

    def test_opozorilo_v_dnevnik_brez_zetona(self):
        tok = io.StringIO()
        dom = os.path.expanduser("~")
        qt_dnevnik.obravnavaj(1, Kontekst(), "Cannot open: https://jelly.example/Items/1/Images?api_key=SKRIVNO123456 "
                              "in %s/.cache/x.png" % dom, tok=tok)
        izpis = tok.getvalue()
        self.assertIn("[Qt opozorilo] qrc:/os/Namizje.qml:42 Cannot open: https://jelly.example/Items/1/Images?***", izpis)
        self.assertNotIn("SKRIVNO123456", izpis)
        if len(dom) > 1:
            self.assertNotIn(dom, izpis)

    def test_debug_prezrt_kriticno_zapisano(self):
        tok = io.StringIO()
        qt_dnevnik.obravnavaj(0, None, "qml: console.log", tok=tok)
        self.assertEqual(tok.getvalue(), "")
        qt_dnevnik.obravnavaj(types.SimpleNamespace(value=2), None, "QQuickWindow ni mogoce ustvariti", tok=tok)
        self.assertEqual(tok.getvalue(), "[Qt kriticno] QQuickWindow ni mogoce ustvariti\n")

    def test_dolgo_sporocilo_skrajsano_in_brez_napake(self):
        tok = io.StringIO()
        qt_dnevnik.obravnavaj(1, None, "x" * 10000, tok=tok)
        self.assertLess(len(tok.getvalue()), qt_dnevnik.NAJVEC_ZNAKOV + 100)

        class Pokvarjen(io.StringIO):
            def write(self, _s):
                raise OSError("zaprt stderr")
        qt_dnevnik.obravnavaj(1, None, "a", tok=Pokvarjen())      # ne sme vreci (Qt bi proces koncal)

    def test_iz_druge_niti(self):
        tok = io.StringIO()
        t = threading.Thread(target=lambda: qt_dnevnik.obravnavaj(1, None, "iz niti", tok=tok))
        t.start()
        t.join()
        self.assertIn("iz niti", tok.getvalue())

    def test_namesti_enkrat(self):
        klici = []
        QtCore = types.SimpleNamespace(qInstallMessageHandler=klici.append)
        self.assertTrue(qt_dnevnik.namesti(QtCore))
        self.assertTrue(qt_dnevnik.namesti(QtCore))
        self.assertEqual(klici, [qt_dnevnik.obravnavaj])

    def test_lupina_namesti_pred_aplikacijo(self):
        with open(os.path.join(KOREN, "core", "os_lupina.py"), encoding="utf-8") as f:
            s = f.read()
        self.assertLess(s.index("qt_dnevnik.namesti()"), s.index("_qt_app = QApplication.instance() or QApplication("))
        with open(os.path.join(KOREN, "packaging", "install_os_payload.sh"), encoding="utf-8") as f:
            self.assertIn(" qt_dnevnik ", f.read())


if __name__ == "__main__":
    unittest.main()
