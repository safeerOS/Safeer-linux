import json

import pytest

from core.link_gledalec import (NapakaGledalca, RazclenjevalnikOkvirjev,
                                izberi_ponor, niz_cevovoda, preslikaj_tipko,
                                preslikaj_tocko, razcleni_odgovor)


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


def test_cevovod_ima_h264_caps_in_gtk3_ponor():
    cevovod = niz_cevovoda("gtksink")
    assert "appsrc name=vir is-live=true format=time" in cevovod
    assert "video/x-h264" in cevovod
    assert "stream-format=(string)byte-stream" in cevovod
    assert "alignment=(string)au" in cevovod
    assert "! h264parse ! avdec_h264 ! videoconvert ! gtksink name=ponor sync=false" in cevovod


def test_izbira_ponora_daje_prednost_gtk3_in_pozna_zasilnega():
    assert izberi_ponor(lambda ime: ime in {"gtksink", "glimagesink"}) == "gtksink"
    assert izberi_ponor(lambda ime: ime == "glimagesink") == "glimagesink"
    with pytest.raises(NapakaGledalca, match="gtksink in glimagesink"):
        izberi_ponor(lambda _ime: False)


def test_preslikava_tocke_izpusti_crne_robove():
    # Slika 16:9 v kvadratnem widgetu ima crna robova zgoraj in spodaj.
    assert preslikaj_tocko(500, 500, 1000, 1000, 1920, 1080) == pytest.approx((960, 540))
    assert preslikaj_tocko(500, 100, 1000, 1000, 1920, 1080) is None
