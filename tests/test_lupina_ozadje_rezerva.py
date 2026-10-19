"""Ozadje sistema iz namizja QML (tudi v Flatpaku) in rezerva WebKit, ko se QML ne nalozi (pregled 14. 10. 2026).

unittest (ne pytest-funkcije): CI skupino GTK4 poganja z `python3 -m unittest`."""
import os
import tempfile
import types
import unittest
from unittest import mock

from core import gostitelj, os_lupina


class OzadjeSistema(unittest.TestCase):
    def test_flatpak_pise_z_ovojem_gsettings_in_potjo_gostitelja(self):
        ukazi = []
        with mock.patch.object(gostitelj, "v_flatpaku", return_value=True), \
                mock.patch.object(os_lupina.os.path, "exists", lambda p: p == "/app/host-bin/gsettings"):
            ok = os_lupina.nastavi_ozadje_sistema("/run/host/usr/share/backgrounds/safeer/safeer jezero.jpg",
                                                  zazeni=lambda argv: ukazi.append(argv) or True)
        self.assertTrue(ok)
        self.assertEqual(ukazi, [["/app/host-bin/gsettings", "set", "org.cinnamon.desktop.background", "picture-uri",
                                  "file:///usr/share/backgrounds/safeer/safeer%20jezero.jpg"]])

    def test_domaca_pot_ostane_enaka(self):
        self.assertEqual(os_lupina.uri_ozadja("/home/u/Slike/č.png"), "file:///home/u/Slike/%C4%8D.png")

    def test_deb_gio_sync(self):
        """Zunaj Flatpaka: Gio.Settings.set_string in nato sync(), da takojsnje branje vidi novo vrednost."""
        import gi.repository
        klici = []

        class Nastavitve:
            @staticmethod
            def new(shema):
                klici.append(("new", shema))
                return Nastavitve()

            def set_string(self, k, v):
                klici.append(("set", k, v))

            @staticmethod
            def sync():
                klici.append(("sync",))

        lazni = types.SimpleNamespace(Settings=Nastavitve, SettingsSchemaSource=types.SimpleNamespace(
            get_default=lambda: types.SimpleNamespace(lookup=lambda *_: object())))
        with mock.patch.object(gostitelj, "v_flatpaku", return_value=False), \
                mock.patch.object(gi.repository, "Gio", lazni, create=True):
            self.assertTrue(os_lupina.nastavi_ozadje_sistema("/usr/share/backgrounds/safeer/a.jpg"))
        self.assertEqual(klici, [("new", "org.cinnamon.desktop.background"),
                                 ("set", "picture-uri", "file:///usr/share/backgrounds/safeer/a.jpg"), ("sync",)])

    def test_deb_brez_sheme_ne_pise(self):
        import gi.repository
        lazni = types.SimpleNamespace(SettingsSchemaSource=types.SimpleNamespace(
            get_default=lambda: types.SimpleNamespace(lookup=lambda *_: None)))
        with mock.patch.object(gostitelj, "v_flatpaku", return_value=False), \
                mock.patch.object(gi.repository, "Gio", lazni, create=True):
            self.assertIs(os_lupina.nastavi_ozadje_sistema("/x.jpg"), False)


class NapakaQml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import PySide6  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("PySide6 ni namescen")
        os.environ["QT_QPA_PLATFORM"] = os.environ.get("QT_QPA_PLATFORM") or "offscreen"  # rezervacija "" (okolje_procesa)
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["test"])

    def test_napaka_qml_sprozi_izjemo_v_obeh_nacinih(self):
        class Os:
            shramba = {}
        with tempfile.TemporaryDirectory() as d:
            pokvarjen = os.path.join(d, "Namizje.qml")
            with open(pokvarjen, "w", encoding="utf-8") as f:
                f.write("import QtQuick\nItem { to ni qml")
            for v_oknu in (False, True):
                with mock.patch.object(os_lupina, "QML", pokvarjen), self.assertRaises(RuntimeError):
                    os_lupina.Namizje(Os(), v_oknu=v_oknu)


class RezervaWebKit(unittest.TestCase):
    def test_delovna_ima_rezervo_webkit(self):
        """Izjema v Namizje() ali pokazi() (npr. brez primarnega zaslona) ne sesuje procesa: vrne False -> delovna.html."""
        import safeer_os
        skrito = []

        class Lupina:
            def __init__(self, *_a, **_k):
                self.pogled = object()
                self.okno = types.SimpleNamespace(hide=lambda: skrito.append(1))

            def pokazi(self):
                raise AttributeError("'NoneType' object has no attribute 'geometry'")
        lazni = types.SimpleNamespace(lupina="x", pogled_delovna="x", _qml_pogled="x", hold=lambda: None,
                                      _ob_spremembi_zaslonov=lambda f: None)
        with mock.patch.object(safeer_os.os_lupina, "Namizje", Lupina):
            self.assertIs(safeer_os.SafeerOS._ustvari_qml_namizje(lazni), False)
        self.assertTrue(lazni.lupina is None and lazni.pogled_delovna is None and skrito == [1])

        def ne_nalozi(*_a, **_k):
            raise RuntimeError("namizje QML se ni naložilo")
        with mock.patch.object(safeer_os.os_lupina, "Namizje", ne_nalozi):
            self.assertIs(safeer_os.SafeerOS._ustvari_qml_namizje(lazni), False)
        with open(safeer_os.__file__, encoding="utf-8") as f:
            vir = f.read()
        delovna = vir[vir.index("    def _ustvari_delovno(self)"):]
        delovna = delovna[:delovna.index('_nov_pogled("delovna.html?')]
        self.assertIn("and self._ustvari_qml_namizje():", delovna)
        self.assertNotIn("os_lupina.Namizje(self)", delovna)


if __name__ == "__main__":
    unittest.main()
