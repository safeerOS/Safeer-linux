"""Izolacija okolja preizkusov (korenski conftest.py, naloga 48): zacasni HOME/XDG/TMPDIR in GSETTINGS_BACKEND
morajo veljati ze ob uvozu tests/conftest.py (ta uvozi varovala in core/), ne sele v pytest_configure."""
import os
import tempfile

_KLJUCI = ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "TMPDIR")


def test_okolje_izolirano_ze_ob_uvozu_conftest(okolje_ob_uvozu_conftest):
    for k in _KLJUCI:
        pot = okolje_ob_uvozu_conftest[k]
        assert pot and "/safeer-testi-%d-" % os.getpid() in os.path.realpath(pot), (k, "ni izoliran ob uvozu")
        assert pot == os.environ[k], k        # ista mapa tudi med preizkusi
    assert okolje_ob_uvozu_conftest["GSETTINGS_BACKEND"]


def test_tempfile_v_mapi_teka():
    assert "/safeer-testi-%d-" % os.getpid() in os.path.realpath(tempfile.gettempdir())
    assert os.path.expanduser("~") == os.environ["HOME"]
