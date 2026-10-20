import unittest
from gi.repository import Gio, GLib
from core.network_errors import can_retry_search, error_html

class NetworkErrorTests(unittest.TestCase):
    def test_only_first_safe_search_get_retries(self):
        error = GLib.Error.new_literal(Gio.tls_error_quark(), 'Peer closed connection', Gio.TlsError.EOF)
        url='https://duckduckgo.com/?q=test'
        self.assertTrue(can_retry_search(url,'GET',error,False))
        reported=GLib.Error.new_literal(Gio.tls_error_quark(),'The TLS connection was non-properly terminated',Gio.TlsError.NOT_TLS)
        self.assertTrue(can_retry_search(url,'GET',reported,False))
        self.assertFalse(can_retry_search(url,'POST',error,False))
        # Dve samodejni ponovitvi (core/network_errors.ZAMIKI_PONOVITVE), potem stran napake; od 20. 10. 2026 za vse
        # GET navigacije s prehodno napako, ne samo za iskanje DuckDuckGo.
        self.assertTrue(can_retry_search(url,'GET',error,1))
        self.assertFalse(can_retry_search(url,'GET',error,2))
        badcert=GLib.Error.new_literal(Gio.tls_error_quark(),'Bad certificate',Gio.TlsError.BAD_CERTIFICATE)
        self.assertFalse(can_retry_search(url,'GET',badcert,False))
    def test_error_page_does_not_replay_forms_or_allow_certificates(self):
        self.assertNotIn('href=',error_html('https://example.org/','POST'))
        self.assertNotIn('href=',error_html('https://example.org/','GET',True))
        self.assertIn('&quot;',error_html('https://example.org/?q="test"','GET'))
        self.assertNotIn('<script>',error_html('https://example.org/','GET'))

    def test_recovery_keeps_previous_uri_and_does_not_override_new_navigation(self):
        from unittest.mock import patch
        from core.network_errors import NetworkErrorHandler, WebKit2
        class View:
            def __init__(self): self.loaded=[]
            def connect(self,*args): pass
            def load_uri(self,uri): self.loaded.append(uri)
            def get_uri(self): return 'about:blank'
        url='https://duckduckgo.com/?q=test'
        error=GLib.Error.new_literal(Gio.tls_error_quark(),'EOF',Gio.TlsError.NOT_TLS)
        v=View();h=NetworkErrorHandler(v);h.requests[url]='GET';callbacks=[]
        with patch('core.network_errors.GLib.timeout_add',side_effect=lambda delay,cb: callbacks.append(cb) or 1):
            self.assertTrue(h.load_failed(v,WebKit2.LoadEvent.STARTED,url,error))
        callbacks.pop()();self.assertEqual(v.loaded,[url])
        h.retried.clear()
        with patch('core.network_errors.GLib.timeout_add',side_effect=lambda delay,cb: callbacks.append(cb) or 1):
            h.load_failed(v,WebKit2.LoadEvent.STARTED,url,error)
        h.load_changed(v,WebKit2.LoadEvent.STARTED)
        callbacks.pop()();self.assertEqual(v.loaded,[url])


def test_jeziki_napake():
    from core.network_errors import BESEDILA
    assert set(BESEDILA) == {"sl", "en", "de", "es", "fr", "it"}
    assert "Try again" in error_html("https://example.org/", "GET", jezik="en")
    assert 'lang="sl"' in error_html("https://example.org/", "GET")


def test_prehodne_napake_vseh_strani_se_ponovijo():
    """Lastnik 20. 10. 2026: Google iskanje - povezava prekinjena; prej samo DuckDuckGo."""
    from core.network_errors import je_prehodna, opis_napake
    zaprta = GLib.Error.new_literal(Gio.io_error_quark(), "Connection terminated unexpectedly", Gio.IOErrorEnum.PARTIAL_INPUT)
    ponastavljena = GLib.Error.new_literal(Gio.io_error_quark(), "Connection reset by peer", Gio.IOErrorEnum.CONNECTION_CLOSED)
    posrednik = GLib.Error.new_literal(Gio.io_error_quark(), "SOCKSv5", Gio.IOErrorEnum.PROXY_FAILED)
    url = "https://www.google.com/search?q=say%20maybe"
    for napaka in (zaprta, ponastavljena, posrednik):
        assert je_prehodna(napaka)
        assert can_retry_search(url, "GET", napaka, 0)
        assert can_retry_search(url, "GET", napaka, 1)
        assert not can_retry_search(url, "GET", napaka, 2)
        assert not can_retry_search(url, "POST", napaka, 0)
        assert not can_retry_search(url, None, napaka, 0)
    assert not can_retry_search("file:///etc/passwd", "GET", zaprta, 0)
    badcert = GLib.Error.new_literal(Gio.tls_error_quark(), "Bad certificate", Gio.TlsError.BAD_CERTIFICATE)
    assert not je_prehodna(badcert)
    ni_datoteke = GLib.Error.new_literal(Gio.io_error_quark(), "Not found", Gio.IOErrorEnum.NOT_FOUND)
    assert not je_prehodna(ni_datoteke)
    assert opis_napake(zaprta) == "g-io-error-quark 34"
    assert "g-io-error-quark 34" in error_html(url, "GET", koda=opis_napake(zaprta))
    assert "<b>" not in error_html(url, "GET", koda="<b>")


def test_metoda_iz_odlocitve_in_preusmeritve():
    """6.0 nima resource-load-started: metoda glavne navigacije iz decide-policy; preusmerjen GET ostane GET, POST
    obrazca (tudi preusmerjen) se ne ponovi."""
    from core.network_errors import NetworkErrorHandler
    class Pogled:
        def connect(self, *a): pass
        def load_uri(self, uri): pass
    h = NetworkErrorHandler(Pogled())
    for brez_virov in (True, False):
        h._brez_virov = lambda: brez_virov
        h.requests = {"https://www.google.com/search?q=a": "GET"}
        assert h._metoda("https://www.google.com/search?q=a&sei=x") == "GET"
        h.requests = {"https://example.org/poslji": "POST"}
        assert h._metoda("https://example.org/hvala") is None
    h.requests = {"https://www.google.com/search?q=a": "GET"}
    assert h._metoda("https://www.google.com/search?q=a&sei=x") == "GET"
    h.requests = {"https://example.org/poslji": "POST"}
    assert h._metoda("https://example.org/hvala") is None
    assert h._metoda("https://example.org/poslji") == "POST"


def test_splet_vidi_odlocitve_pred_politiko():
    """_politika v os_splet odlocitve obravnava in vrne True (ustavi signal) - NetworkErrorHandler mora biti prikljucen
    PRED njo, sicer ne vidi metode navigacije."""
    import os
    s = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "os_splet.py"),
             encoding="utf-8").read()
    assert s.index("NetworkErrorHandler(pogled") < s.index('pogled.connect("decide-policy", self._politika)')
