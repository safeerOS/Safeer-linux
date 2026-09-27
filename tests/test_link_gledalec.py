import json

import pytest

from core.link_gledalec import (NapakaGledalca, RazclenjevalnikOkvirjev,
                                preslikaj_tipko, razcleni_odgovor)


ODTIS = "ab:" * 31 + "ab"


def test_razcleni_odgovor_screen_start():
    r = razcleni_odgovor({"ok": True, "data": {"port": 4321, "fp": ODTIS, "token": "enkraten", "v": 2}})
    assert r["port"] == 4321
    assert r["fp"] == "ab" * 32
    assert r["token"] == "enkraten"


def test_razcleni_zavrnitev_ohrani_sporocilo():
    with pytest.raises(NapakaGledalca, match="Dovoljenje"):
        razcleni_odgovor({"ok": False, "message": "Dovoljenje ni bilo potrjeno"})


def test_okvirji_lahko_pridejo_po_delih_in_skupaj():
    p = RazclenjevalnikOkvirjev()
    prvi = bytes([1]) + (4).to_bytes(4, "big") + b"h264"
    drugi = bytes([3]) + (2).to_bytes(4, "big") + b"{}"
    assert p.dodaj(prvi[:3]) == []
    assert p.dodaj(prvi[3:] + drugi) == [(1, b"h264"), (3, b"{}")]


def test_okvir_zavrne_preveliko_telo():
    with pytest.raises(NapakaGledalca):
        RazclenjevalnikOkvirjev().dodaj(bytes([1]) + (9 * 1024 * 1024).to_bytes(4, "big"))


def test_preslikava_tipk_in_sumnikov():
    assert preslikaj_tipko("Control_L", dol=True) == {"vrsta": "tipka_dol", "tipka": "ctrl"}
    assert preslikaj_tipko("Control_L", dol=False) == {"vrsta": "tipka_gor", "tipka": "ctrl"}
    assert preslikaj_tipko("Return", dol=True) == {"vrsta": "tipka_dol", "tipka": "vnasalka"}
    assert preslikaj_tipko("ccaron", "č", True) == {"vrsta": "besedilo", "besedilo": "č"}
    assert preslikaj_tipko("ccaron", "č", False) is None
