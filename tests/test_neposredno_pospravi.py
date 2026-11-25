"""Enojec sredisca (core/link_neposredno.zazeni_na_sredisci) ne sme teci v naslednji preizkus (CI 45663650141,
25. 11. 2026: izpis »vhod zaprt« sredi tujega preizkusa). Vrstni red preizkusov v tej datoteki je namenski."""
import threading

from core import link_neposredno as ln


def test_a_zazene_sredisce():
    s = ln.zazeni_na_sredisci(lambda: 0)
    assert s is ln.sredisce()
    assert any(t.name == "safeer-neposredno-sredisce" and t.is_alive() for t in threading.enumerate())


def test_b_naslednji_preizkus_ga_nima():
    assert ln.sredisce() is None
    assert not any(t.name == "safeer-neposredno-sredisce" and t.is_alive() for t in threading.enumerate())
