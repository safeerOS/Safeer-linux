"""Pokvarjen seznam groznj (lastnik, 13. 11. 2026): brskanje ne zastane, seznam se popravi sam, ne v zanki."""
import os
import pathlib
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import os_scit, threat_intel  # noqa: E402


class _Shramba:
    """Nadomestek SignedFeedStore: iskanje vrze izjemo (pokvarjeno kazalo), nalaganje ne uspe."""

    def __init__(self, mapa, nalozi_ok=False):
        self.mapa = mapa
        self.nalozi_ok = nalozi_ok
        self.klici = []
        self.last_error = ""

    def installed_version(self):
        return 7

    def _index_path(self, ver):
        return pathlib.Path(self.mapa) / ("threats-%d-index.bin" % ver)

    def match_host(self, host, sme=None):
        raise ValueError("pokvarjeno kazalo")

    def load(self):
        self.klici.append("load")
        return self.nalozi_ok

    def update(self):
        self.klici.append("update")
        return True


def _storitev(mapa, nalozi_ok=False):
    s = threat_intel.ThreatIntelService(mapa)
    s.store = _Shramba(mapa, nalozi_ok)
    return s


def _pocakaj(s):
    t = s._popravilo_nit
    if t is not None:
        t.join(5)


def test_popravilo_zgradi_kazalo_znova_in_prenese_nov_paket_ce_paket_ni_berljiv():
    with tempfile.TemporaryDirectory() as m:
        s = _storitev(m)
        kazalo = s.store._index_path(7)
        open(kazalo, "wb").write(b"smeti")
        assert s.popravi("ValueError") is True
        _pocakaj(s)
        assert not os.path.exists(kazalo)                 # izpeljano kazalo je zavrzeno
        assert s.store.klici == ["load", "update"]        # nalaganje ni uspelo -> nov, preverjen paket


def test_popravilo_ne_prenasa_ce_paket_po_novem_kazalu_deluje():
    with tempfile.TemporaryDirectory() as m:
        s = _storitev(m, nalozi_ok=True)
        s.popravi("ValueError")
        _pocakaj(s)
        assert s.store.klici == ["load"]
        assert s.store.last_error == ""


def test_popravilo_ni_zanka():
    with tempfile.TemporaryDirectory() as m:
        s = _storitev(m)
        assert s.popravi("a") is True
        _pocakaj(s)
        assert s.popravi("b") is False                    # znotraj POPRAVILO_RAZMIK
        assert s.store.klici == ["load", "update"]
        s.POPRAVILO_RAZMIK = 0.0
        assert s.popravi("c") is True                     # po razmiku spet dovoljeno
        _pocakaj(s)


def test_match_pri_pokvarjenem_seznamu_ne_vrze_in_sprozi_popravilo():
    with tempfile.TemporaryDirectory() as m:
        s = _storitev(m)
        assert s.match("primer.si") is None               # fail-open: brskanje ne zastane
        _pocakaj(s)
        assert s.popravil == 1 and s.store.klici[0] == "load"


def test_scit_kategorija_je_fail_open_in_sprozi_popravilo():
    with tempfile.TemporaryDirectory() as m:
        sez = os_scit.Seznami(m, prenesi_fn=lambda *a: (0, b"", ""), kljuc_fn=lambda: None)
        s = _storitev(m)
        s.loaded.set()
        sez.storitev = s
        assert sez.kategorija("zlobna.primer.si") is None  # ne blokira vsega in ne vrze
        _pocakaj(s)
        assert s.popravil == 1 and "load" in s.store.klici


def test_scit_zasciten_gostitelj_ostane_fail_closed_in_sprozi_popravilo():
    with tempfile.TemporaryDirectory() as m:
        sez = os_scit.Seznami(m, prenesi_fn=lambda *a: (0, b"", ""), kljuc_fn=lambda: None)
        s = _storitev(m)
        s.loaded.set()
        sez.storitev = s
        assert sez.kategorija_groznje("zlobna.primer.si") == "groznje"
        _pocakaj(s)
        assert s.popravil == 1
