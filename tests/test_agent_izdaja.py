"""Safeer Agent je izlocen iz uradne izdaje (lastnik, 5. 11. 2026): ena zastavica core/agent.NA_VOLJO_V_IZDAJI. Z False ga
uporabnik ne vidi nikjer - ne v iskalni lupi (QML in os.js), ne v Nastavitvah, ne kot zmoznost ali ukaz v Safeer Linku -
tudi ce je naslov modela shranjen ali v okolju. Z True dela kot prej."""
import os

import pytest

from core import agent, link_daljinec, safeer_link
from core.agent import nastavitve, razumevanje, storitev

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


@pytest.fixture(autouse=True)
def mapa(monkeypatch, tmp_path):
    monkeypatch.setattr(nastavitve, "MAPA", str(tmp_path / "safeer-agent"))
    monkeypatch.delenv("SAFEER_AGENT", raising=False)
    nastavitve.lupa_zapomni(None, "")
    yield tmp_path / "safeer-agent"
    nastavitve.lupa_zapomni(None, "")


def test_izdaja_brez_agenta():
    assert agent.NA_VOLJO_V_IZDAJI is False, "Agent je izlocen iz izdaje (lastnik, 5. 11. 2026)"


def test_izlocen_nikjer_ni_viden(monkeypatch):
    monkeypatch.setattr(agent, "NA_VOLJO_V_IZDAJI", False)
    nastavitve._pisi("naslov", "http://192.0.2.7:8085")
    assert razumevanje.naslov_modela() == ""
    assert nastavitve.stanje()["na_voljo"] is False
    klici = []
    monkeypatch.setattr(nastavitve, "dosegljivost", lambda *a, **k: klici.append(a) or {"dosegljiv": True})
    assert nastavitve.lupa_na_voljo() == {"na_voljo": False} and klici == []        # niti v omrezje
    assert storitev.vprasaj_tukaj("utisaj televizor")["koda"] == "ni_modela"
    assert safeer_link._agent_na_voljo() is False                                   # zmoznost »agent« v Linku


def test_z_zastavico_dela_kot_prej(monkeypatch):
    monkeypatch.setattr(agent, "NA_VOLJO_V_IZDAJI", True)
    nastavitve._pisi("naslov", "http://192.0.2.7:8085")
    assert razumevanje.naslov_modela() == "http://192.0.2.7:8085"
    assert nastavitve.stanje()["na_voljo"] is True
    assert safeer_link._agent_na_voljo() is True


def test_ukaz_z_druge_naprave_zavrnjen():
    so = _beri("core", "link_daljinec.py")
    veja = so.split("elif d in DEJANJA_AGENT:", 1)[1].split("elif ", 1)[0]
    assert veja.index("agent.v_izdaji()") < veja.index("storitev.vprasaj(")
    assert "agent.ask" in link_daljinec.DEJANJA_AGENT


def test_nastavitve_in_lupa_skrijeta():
    html = _beri("assets", "os", "index.html")
    assert '<h2 data-t="agentNaslov" id="naslovAgent" hidden>' in html
    assert 'id="blokAgent" data-iskanje-blok hidden>' in html
    js = _beri("assets", "os", "os.js")
    assert '["naslovAgent", "blokAgent"].forEach(function (i) { if ($(i)) $(i).hidden = !z.agentIzdaja; });' in js
    so = _beri("safeer_os.py")
    assert '"agentIzdaja": self._agent("izdaja"),' in so
    # Lupa (QML in os.js) pokaze vnos samo z agentLupa -> lupa_na_voljo -> naslov_modela (prazen zunaj izdaje).
    assert '"agentLupa": lambda: self._agent("lupa"),' in so
