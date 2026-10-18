"""Funkcije brskalnika v Spletu (prej samo v Safeer Browserju GTK3), 14. 10. 2026."""
import datetime
import os
import tempfile

import gi
gi.require_version("Gtk", "4.0")

from core import zgodovina

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_bliznjice_kot_firefox():
    from core.os_splet import blizjica
    assert blizjica("g", True) == "najdi-naprej" and blizjica("g", True, True) == "najdi-nazaj"
    assert blizjica("F3") == "najdi-naprej" and blizjica("F3", shift=True) == "najdi-nazaj"
    assert blizjica("p", True) == "natisni" and blizjica("F11") == "celozaslonsko" and blizjica("m", True) == "utisaj"


def test_zgodovina_odstrani_in_pocisti():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "history.json")
    zgodovina.dodaj(p, "https://a.si/")
    zgodovina.dodaj(p, "https://b.si/")
    assert zgodovina.odstrani(p, "https://a.si/") == 1
    assert [z["url"] for z in zgodovina.nalozi(p)] == ["https://b.si/"]
    star = {"title": "s", "url": "https://star.si/", "time": "01.01.2020 10:00"}
    zgodovina._shrani(p, zgodovina.nalozi(p) + [star])
    assert zgodovina.pocisti(p, datetime.datetime.now() - datetime.timedelta(hours=1)) == 1
    assert zgodovina.nalozi(p) == [star]
    assert zgodovina.pocisti(p) == 1 and zgodovina.nalozi(p) == []


def test_splet_ima_funkcije():
    s = open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8").read()
    for niz in ("PrintOperation.new(p).run_dialog", "search_next()", "count_matches(", "set_is_muted(not",
                "delete_portal(obstojeci", "zgodovina.odstrani(", "gumb_povecave", 'if not self.odpri_zapisek:'):
        assert niz in s, niz


def test_stevilo_zadetkov():
    from core.os_splet import stevilo_zadetkov as z
    assert [z(n, "sl") for n in (1, 2, 3, 5, 101, 102)] == ["1 zadetek", "2 zadetka", "3 zadetki", "5 zadetkov",
                                                             "101 zadetek", "102 zadetka"]
    assert z(1, "en") == "1 match" and z(4, "de") == "4 Treffer"


def test_napake_omrezja_v_gtk4():
    from core import network_errors as ne
    assert ne.WebKit2.__name__.endswith("WebKit")          # WebKitGTK 6.0, ne WebKit2 4.1
    assert "Poskusi znova" in ne.error_html("https://example.org/", "GET")
    s = open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8").read()
    assert "NetworkErrorHandler(pogled" in s


def test_napaka_posrednika_je_stran():
    import socket
    from core.doh_proxy import LocalDoHProxy
    a, b = socket.socketpair()
    LocalDoHProxy._napaka_502(a, "Strani s tem imenom ni bilo mogoče najti (DNS). / The site name could not be found (DNS).")
    odgovor = b.recv(65536).decode("utf-8")
    assert "text/html; charset=utf-8" in odgovor and "<h1>Strani s tem imenom" in odgovor and "<script" not in odgovor


def test_kontekstni_meni_kot_firefox():
    s = open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8").read()
    assert 'pogled.connect("context-menu", self._kontekstni_meni)' in s
    assert "dejanje == A.COPY and povezava and not izbor" in s and "new_from_gaction(self._dejanje_zavihek" in s
