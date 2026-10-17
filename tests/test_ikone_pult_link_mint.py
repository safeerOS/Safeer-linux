"""Lastnik, 17. 10. 2026 (»vse da«): Safeer Control v pultu crtna ikona Linka (ne zelen scit) in ikone posodobitev brez
scita tudi s temo Mint-Y-Blue (brez Papirusa)."""
import os
import re

import pytest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IKONE = os.path.join(KOREN, "packaging", "tema-cinnamon", "ikone")


def test_tema_mint_y_podeduje_mint_in_ima_ikone_posodobitev():
    tema = os.path.join(IKONE, "Safeer-Mint-Y-Blue")
    with open(os.path.join(tema, "index.theme"), encoding="utf-8") as f:
        glava = f.read()
    assert "Name=Safeer-Mint-Y-Blue" in glava
    assert re.search(r"^Inherits=Mint-Y-Blue,", glava, re.M)
    for stanje in ("updates-available", "up-to-date", "checking", "error", "installing"):
        for ime in ("mintupdate-%s.svg" % stanje, "mintupdate-%s-symbolic.svg" % stanje):
            assert os.path.isfile(os.path.join(tema, "scalable", "status", ime)), ime


def test_safeer_cinnamon_izbere_mint_temo_brez_papirusa():
    with open(os.path.join(KOREN, "packaging", "tema-cinnamon", "safeer-cinnamon"), encoding="utf-8") as f:
        sh = f.read()
    assert 'IKONE_SAFEER_MINT="Safeer-Mint-Y-Blue"' in sh
    assert "icon-theme \"'$(tema_ikon_mint)'\"" in sh


def test_paket_namesti_obe_temi():
    with open(os.path.join(KOREN, "packaging", "install_cinnamon_payload.sh"), encoding="utf-8") as f:
        sh = f.read()
    assert "for IKT in Safeer-Papirus-Dark Safeer-Mint-Y-Blue" in sh


def test_ikona_linka(tmp_path):
    pytest.importorskip("cairo")
    from core.pladenj_sni import ikona_linka
    a, b = ikona_linka(True, str(tmp_path)), ikona_linka(False, str(tmp_path))
    assert a != b and os.path.getsize(a) > 0 and os.path.getsize(b) > 0
    assert ikona_linka(True, str(tmp_path)) == a          # iz predpomnilnika


def test_control_v_pultu_ne_uporablja_scita():
    with open(os.path.join(KOREN, "safeer_control.py"), encoding="utf-8") as f:
        vir = f.read()
    assert "ikona = self._ikona_pulta(False)" in vir
    assert "self.ikona.nastavi_ikono(self._ikona_pulta(bool(povezan)))" in vir
