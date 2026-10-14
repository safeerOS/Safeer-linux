"""Namizje QML se umakne pultom (lastnik 14. 10. 2026: pasica Minta je prekrivala iskanje)."""
import os

from core.os_lupina import robovi_delovnega_obmocja as r

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_pult_zgoraj_in_spodaj():
    assert r((0, 0, 1440, 900), (0, 30, 1440, 870)) == {"robZgoraj": 30, "robLevo": 0, "robSpodaj": 0, "robDesno": 0}
    assert r((0, 0, 1920, 1080), (0, 0, 1920, 1040)) == {"robZgoraj": 0, "robLevo": 0, "robSpodaj": 40, "robDesno": 0}
    assert r((1920, 0, 1920, 1080), (1960, 0, 1880, 1080))["robLevo"] == 40


def test_brez_delovnega_obmocja():
    assert set(r((0, 0, 1440, 900), (0, 0, 0, 0)).values()) == {0}


def test_qml_uporablja_robove():
    q = open(os.path.join(KOREN, "assets", "os", "qml", "Namizje.qml"), encoding="utf-8").read()
    assert "y: koren.robZgoraj + 18" in q and "vrhPanelov: robZgoraj + 104" in q and "koren.robSpodaj - 70" in q


def test_dock_plank():
    from core import os_dock
    nast = {"position": "'right'", "hide-mode": "'intelligent'", "icon-size": "40"}
    assert os_dock.rob_docka(beri=lambda k: nast.get(k, ""), tece=lambda: True) == ("right", 62)
    nast["hide-mode"] = "'auto'"
    assert os_dock.rob_docka(beri=lambda k: nast.get(k, ""), tece=lambda: True) == ("", 0)
    assert os_dock.rob_docka(beri=lambda k: "", tece=lambda: False) == ("", 0)
