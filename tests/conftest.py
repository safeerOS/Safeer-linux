"""Skupne nastavitve preizkusov.

Dostop naprav (core/link_dostop): zapis dovoljenj je v preizkusih VEDNO v zacasni datoteki - nikoli v pravih nastavitvah
uporabnika. Obstojeci preizkusi preverjajo druge stvari (usmerjanje, prenos datotek, predajo) z izmisljenimi napravami,
zato so te v njih v ozjem krogu racunalnika. Preizkus, ki preverja sama dovoljenja, se oznaci s
`@pytest.mark.pravi_dostop` in dobi prava pravila nad praznim zacasnim zapisom.
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "pravi_dostop: preizkus s pravimi pravili dostopa naprav (core/link_dostop)")


@pytest.fixture(autouse=True)
def _dostop_naprav(tmp_path, monkeypatch, request):
    from core import link_dostop
    link_dostop._za_preizkus(str(tmp_path / "dostop.json"))
    if request.node.get_closest_marker("pravi_dostop") is None:
        from core import link_hub_streznik
        monkeypatch.setattr(link_dostop, "zmoznosti",
                            lambda device_id: set(link_dostop.VSE_ZMOZNOSTI) if device_id else set())
        # Izmisljene naprave ne znajo zascite od naprave do naprave (pravilo »samo zasciteno« bi sicer bralo pravi krog).
        monkeypatch.setattr(link_dostop, "zahteva_zascito", lambda device_id: False)
        monkeypatch.setattr(link_hub_streznik, "OMEJENE_ODDAJE", {})
    yield
    link_dostop._za_preizkus(None)
