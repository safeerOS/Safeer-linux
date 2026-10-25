"""Izolacija okolja preizkusov (korenski conftest.py, naloga 48): zacasni HOME/XDG/TMPDIR in GSETTINGS_BACKEND
morajo veljati ze ob uvozu tests/conftest.py (ta uvozi varovala in core/), ne sele v pytest_configure."""
import os
import tempfile

_KLJUCI = ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "TMPDIR")


def test_okolje_izolirano_ze_ob_uvozu_conftest(okolje_ob_uvozu_conftest):
    mapa_teka = "/safeer-testi-%d-" % os.getpid()
    for k in _KLJUCI:
        pot = okolje_ob_uvozu_conftest[k]
        assert pot and mapa_teka in os.path.realpath(pot), (k, "ni izoliran ob uvozu")
        # Tudi med preizkusi samo v mapi teka. Preizkus sme nastaviti svojo mapo (zivi preizkusi ob uvozu modula, kar
        # pytest naredi ob zbiranju - pred vsemi preizkusi), zato enakost z vrednostjo ob uvozu ni pogoj: v polnem
        # teku je bila odvisna od vrstnega reda (CI 40193737914, 25. 10. 2026: XDG_CONFIG_HOME iz test_dock).
        assert mapa_teka in os.path.realpath(os.environ[k]), (k, os.environ[k], "ni vec v mapi teka")
    assert okolje_ob_uvozu_conftest["TMPDIR"] == os.environ["TMPDIR"]      # mapa teka je ena sama
    assert okolje_ob_uvozu_conftest["GSETTINGS_BACKEND"]


def test_tempfile_v_mapi_teka():
    assert "/safeer-testi-%d-" % os.getpid() in os.path.realpath(tempfile.gettempdir())
    assert os.path.expanduser("~") == os.environ["HOME"]
