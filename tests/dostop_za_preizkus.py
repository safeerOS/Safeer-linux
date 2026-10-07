"""Dostop naprav v preizkusih, ki preverjajo druge stvari (usmerjanje, prenos datotek, predajo, zaslon).

Ti preizkusi delajo z izmisljenimi napravami. Da ostanejo preizkusi tistega, kar preverjajo, so naprave v njih v ozjem
krogu racunalnika, zapis dovoljenj pa je v zacasni datoteki - nikoli v pravih nastavitvah uporabnika. Modul preizkusa
to vklopi z eno vrstico:

    from dostop_za_preizkus import setUpModule, tearDownModule  # noqa: F401

Velja pod unittestom (tako preizkuse pozene CI) in pod pytestom (tam tests/conftest.py naredi isto za vse preizkuse).
Sama dovoljenja preverja tests/test_link_dostop.py - s pravimi pravili, zato te vrstice nima.
"""
import os
import shutil
import tempfile
from unittest import mock

_popravki = []
_mapa = None


def setUpModule():
    global _mapa
    from core import link_dostop, link_hub_streznik
    _mapa = tempfile.mkdtemp(prefix="safeer-dostop-")
    link_dostop._za_preizkus(os.path.join(_mapa, "dostop.json"))
    for cilj, ime, vrednost in (
            (link_dostop, "zmoznosti", lambda device_id: set(link_dostop.VSE_ZMOZNOSTI) if device_id else set()),
            # Izmisljene naprave ne znajo zascite od naprave do naprave (pravilo bi sicer bralo pravi krog).
            (link_dostop, "zahteva_zascito", lambda device_id: False),
            (link_hub_streznik, "OMEJENE_ODDAJE", {})):
        popravek = mock.patch.object(cilj, ime, vrednost)
        popravek.start()
        _popravki.append(popravek)


def tearDownModule():
    global _mapa
    from core import link_dostop
    while _popravki:
        _popravki.pop().stop()
    link_dostop._za_preizkus(None)
    if _mapa:
        shutil.rmtree(_mapa, ignore_errors=True)
        _mapa = None
