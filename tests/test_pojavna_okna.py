"""Pojavna okna: nezazelena blokirana, prijave in placila dovoljene (lastnik, 14. 10. 2026)."""
import os

from core import pojavna_okna as po

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRAN = "https://www.filmi-primer.si/film/1"


def test_prava_povezava_vedno():
    assert po.dovoli(STRAN, "https://oglasi.example/x", prava_povezava=True)


def test_prijave_in_placila_dovoljene():
    for cilj in ("https://accounts.google.com/o/oauth2/v2/auth?x=1", "https://login.microsoftonline.com/common/x",
                 "https://appleid.apple.com/auth/authorize", "https://www.paypal.com/checkoutnow?token=1",
                 "https://id.nekdo.si/login?next=/", "https://sso.podjetje.eu/oauth2/authorize",
                 "https://www.facebook.com/dialog/oauth", "about:blank"):
        assert po.dovoli(STRAN, cilj, prava_povezava=False), cilj


def test_ista_stran_dovoljena():
    assert po.dovoli("https://mail.google.com/x", "https://docs.google.com/y", False)
    assert po.dovoli("https://www.bbc.co.uk/a", "https://news.bbc.co.uk/b", False)


def test_tuja_stran_iz_skripte_blokirana():
    assert not po.dovoli(STRAN, "https://popunder.example/klik?id=7", False)
    assert not po.dovoli("https://a.co.uk/", "https://b.co.uk/", False)


def test_vedno_dovoli():
    dov = po.zapomni([], STRAN)
    assert dov == ["filmi-primer.si"]
    assert po.dovoli(STRAN, "https://popunder.example/klik", False, dov)
    assert po.zapomni(dov, STRAN) == ["filmi-primer.si"]


def test_besedila():
    k = set(po.BESEDILA["sl"])
    assert all(set(b) == k for b in po.BESEDILA.values())


def test_splet_uporablja_pravila_in_izbiro_dns():
    splet = open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8").read()
    assert "pojavna_okna.dovoli(" in splet and "_pojavno_blokirano" in splet
    assert '"popup_blokiraj"' in splet and '"doh_provider", dns' in splet


def test_naslov_ip():
    assert po.osnova("127.0.0.1") == "127.0.0.1"
    assert po.zapomni([], "http://192.168.1.5:8080/x") == ["192.168.1.5"]
