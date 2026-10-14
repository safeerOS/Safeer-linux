"""Ozadje sistema iz namizja QML (tudi v Flatpaku) in rezerva WebKit, ko se QML ne nalozi (pregled 14. 10. 2026)."""
import os
import types

import pytest

from core import gostitelj, os_lupina


def test_flatpak_pise_z_ovojem_gsettings_in_potjo_gostitelja(monkeypatch):
    monkeypatch.setattr(gostitelj, "v_flatpaku", lambda: True)
    monkeypatch.setattr(os_lupina.os.path, "exists", lambda p: p == "/app/host-bin/gsettings")
    ukazi = []
    ok = os_lupina.nastavi_ozadje_sistema("/run/host/usr/share/backgrounds/safeer/safeer jezero.jpg",
                                          zazeni=lambda argv: ukazi.append(argv) or True)
    assert ok
    assert ukazi == [["/app/host-bin/gsettings", "set", "org.cinnamon.desktop.background", "picture-uri",
                      "file:///usr/share/backgrounds/safeer/safeer%20jezero.jpg"]]


def test_domaca_pot_ostane_enaka():
    assert os_lupina.uri_ozadja("/home/u/Slike/č.png") == "file:///home/u/Slike/%C4%8D.png"


def test_deb_gio_sync(monkeypatch):
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

    class Vir:
        def lookup(self, shema, rek):
            return object()

    lazni = types.SimpleNamespace(Settings=Nastavitve,
                                  SettingsSchemaSource=types.SimpleNamespace(get_default=lambda: Vir()))
    monkeypatch.setattr(gostitelj, "v_flatpaku", lambda: False)
    monkeypatch.setattr(gi.repository, "Gio", lazni, raising=False)
    assert os_lupina.nastavi_ozadje_sistema("/usr/share/backgrounds/safeer/a.jpg")
    assert klici == [("new", "org.cinnamon.desktop.background"),
                     ("set", "picture-uri", "file:///usr/share/backgrounds/safeer/a.jpg"), ("sync",)]


def test_deb_brez_sheme_ne_pise(monkeypatch):
    import gi.repository
    lazni = types.SimpleNamespace(SettingsSchemaSource=types.SimpleNamespace(
        get_default=lambda: types.SimpleNamespace(lookup=lambda *_: None)))
    monkeypatch.setattr(gostitelj, "v_flatpaku", lambda: False)
    monkeypatch.setattr(gi.repository, "Gio", lazni, raising=False)
    assert os_lupina.nastavi_ozadje_sistema("/x.jpg") is False


@pytest.fixture(scope="module")
def qt():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(["test"])


@pytest.mark.parametrize("v_oknu", [False, True])
def test_napaka_qml_sprozi_izjemo_v_obeh_nacinih(qt, tmp_path, monkeypatch, v_oknu):
    pokvarjen = tmp_path / "Namizje.qml"
    pokvarjen.write_text("import QtQuick\nItem { to ni qml", encoding="utf-8")
    monkeypatch.setattr(os_lupina, "QML", pokvarjen)

    class Os:
        shramba = {}
    with pytest.raises(RuntimeError):
        os_lupina.Namizje(Os(), v_oknu=v_oknu)


def test_delovna_ima_rezervo_webkit(monkeypatch):
    """Izjema v Namizje() ali pokazi() (npr. brez primarnega zaslona) ne sesuje procesa: vrne False -> delovna.html."""
    import safeer_os

    class Lupina:
        def __init__(self, *_a, **_k):
            self.pogled = object()
            self.okno = types.SimpleNamespace(hide=lambda: skrito.append(1))

        def pokazi(self):
            raise AttributeError("'NoneType' object has no attribute 'geometry'")
    skrito = []
    monkeypatch.setattr(safeer_os.os_lupina, "Namizje", Lupina)
    lazni = types.SimpleNamespace(lupina="x", pogled_delovna="x", _qml_pogled="x", hold=lambda: None,
                                  _ob_spremembi_zaslonov=lambda f: None)
    assert safeer_os.SafeerOS._ustvari_qml_namizje(lazni) is False
    assert lazni.lupina is None and lazni.pogled_delovna is None and skrito == [1]

    def ne_nalozi(*_a, **_k):
        raise RuntimeError("namizje QML se ni naložilo")
    monkeypatch.setattr(safeer_os.os_lupina, "Namizje", ne_nalozi)
    assert safeer_os.SafeerOS._ustvari_qml_namizje(lazni) is False
    vir = open(safeer_os.__file__, encoding="utf-8").read()
    delovna = vir[vir.index("    def _ustvari_delovno(self)"):]
    delovna = delovna[:delovna.index('_nov_pogled("delovna.html?')]
    assert "and self._ustvari_qml_namizje():" in delovna and "os_lupina.Namizje(self)" not in delovna
