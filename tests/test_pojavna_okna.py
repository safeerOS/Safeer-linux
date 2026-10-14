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


def test_prijavna_pot_samo_na_prijavnem_strezniku_ali_isti_strani():
    """Pregled 14. 10. 2026: »https://ads.evil/auth/x« je veljal za prijavo."""
    for cilj in ("https://ads.evil/auth/x", "https://popunder.example/login?x=1", "https://track.example/oauth2/a"):
        assert not po.dovoli(STRAN, cilj, False), cilj
    assert po.dovoli(STRAN, "https://prijava.filmi-primer.si/login", False)     # stran odpiralca
    assert po.je_prijava("https://www.filmi-primer.si/sso/start", STRAN)
    assert not po.je_prijava("https://ads.evil/auth/x", STRAN)
    assert po.je_prijava("https://login.banka.si/oauth/authorize")


def test_splet_preveri_prazno_okno():
    splet = open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8").read()
    assert 'z["pojavno_prazno"] = (pogled.get_uri() or "", prava, izvor)' in splet
    assert 'z.pop("pojavno_prazno")' in splet


class Pregled(__import__("unittest").TestCase):
    """CI zaganja preizkuse z unittest (funkcij v slogu pytest ne vidi): novi preizkusi pregleda 14. 10. 2026."""

    def test_prijavna_pot(self):
        test_prijavna_pot_samo_na_prijavnem_strezniku_ali_isti_strani()
        test_prijave_in_placila_dovoljene()

    def test_prazno_okno(self):
        test_splet_preveri_prazno_okno()
