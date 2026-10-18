"""Skupne nastavitve preizkusov.

Dostop naprav (core/link_dostop): zapis dovoljenj je v preizkusih VEDNO v zacasni datoteki - nikoli v pravih nastavitvah
uporabnika. Obstojeci preizkusi preverjajo druge stvari (usmerjanje, prenos datotek, predajo) z izmisljenimi napravami,
zato so te v njih v ozjem krogu racunalnika. Preizkus, ki preverja sama dovoljenja, se oznaci s
`@pytest.mark.pravi_dostop` in dobi prava pravila nad praznim zacasnim zapisom.
"""
import gc
import os
import sys

import pytest

_izid = {}


def pytest_configure(config):
    config.addinivalue_line("markers", "pravi_dostop: preizkus s pravimi pravili dostopa naprav (core/link_dostop)")
    # Vsi preizkusi tecejo v enem procesu (GTK4 + WebKit, 18. 10. 2026). Samodejno zbiranje smeti bi lahko v delovni
    # niti (npr. doh_proxy._accept_loop) unicilo predmet GTK/WebKit - GObject sme koncati samo glavna nit, sicer
    # segfault (izmerjeno pri polnem teku). Zato smeti pobiramo sami, na glavni niti, po vsakem preizkusu.
    gc.disable()


@pytest.fixture(autouse=True)
def _smeti_na_glavni_niti():
    yield
    gc.collect()


def pytest_sessionfinish(session, exitstatus):
    _izid["koda"] = int(exitstatus)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    # Po porocilu in pospravljanju (korenski conftest pobrise zacasno mapo) proces koncamo brez Py_Finalize: tam je
    # sprostitev predmeta GObject iz globalne spremenljivke modula (g_object_unref v _PyModule_Clear) obvisela na
    # futexu - polni tek je izpisal porocilo in nato visel do casovne omejitve (gdb na posnetku jedra, 18. 10. 2026).
    if "koda" in _izid:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_izid["koda"])


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
