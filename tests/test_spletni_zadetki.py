"""Sprotni zadetki spleta v lupi (core/spletni_zadetki.py, lastnik 20. 10. 2026): ciscenje podatkov tuje strani in pravi
WebKitGTK 6.0 (Xvfb) z lokalnim streznikom, ki posnema strani Googla (z oglasom) in DuckDuckGo (zadetki sele z
JavaScriptom). Brez zaslona ali WebKita se zivi del preskoci."""
import os
import socket
import sys
import threading
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import spletni_zadetki as sz  # noqa: E402


def test_motor_iz_naslova():
    assert sz.motor_za("https://www.google.com/search?q=a") == "google"
    assert sz.motor_za("https://duckduckgo.com/?q=a") == "duckduckgo"
    assert sz.motor_za("https://search.brave.com/search?q=a") == "brave"
    assert sz.motor_za("https://example.org/?q=a") == ""


def test_ocisti_podatke_tuje_strani():
    surovo = [{"t": "ARSO  vreme", "u": "https://www.google.com/goto?url=x", "s": "Napoved\n vremena", "p": "https://vreme.arso.gov.si › napoved"},
              {"t": "zlo", "u": "javascript:alert(1)"}, {"t": "", "u": "https://a.si/"}, {"t": "datoteka", "u": "file:///etc/passwd"},
              "niz", {"t": "dolg", "u": "https://a.si/" + "x" * 3000},
              {"t": "Linux Mint", "u": "https://www.linuxmint.com/", "s": ""},
              {"t": "dvojnik", "u": "https://www.linuxmint.com/"},
              {"t": "tretji", "u": "https://b.si/"}, {"t": "cetrti", "u": "https://c.si/"}]
    z = sz.ocisti(surovo)
    assert [x["naslov"] for x in z] == ["ARSO vreme", "Linux Mint", "tretji"]
    assert z[0]["stran"] == "vreme.arso.gov.si"      # Google povezava prek /goto: stran iz prikazanega naslova
    assert z[0]["odlomek"] == "Napoved vremena"
    assert z[1]["stran"] == "linuxmint.com"
    assert sz.ocisti("ni seznam") == [] and sz.ocisti(None) == []


GOOGLE = """<html><body><div id="tads"><div class="MjjYud"><a href="https://oglas.si/"><h3>Oglas</h3></a></div></div>
<div id="rso"><div class="MjjYud"><a href="https://prvi.si/stran"><h3>Prvi zadetek</h3></a><cite>https://prvi.si › stran</cite>
<div class="VwiC3b">Odlomek prvega</div></div>
<div class="MjjYud"><a href="javascript:void(0)"><h3>Zlo</h3></a></div>
<div class="MjjYud"><a href="https://drugi.si/"><h3>Drugi zadetek</h3></a></div></div></body></html>"""
DDG = """<html><body><div id="r"></div><script>setTimeout(function(){document.getElementById('r').innerHTML=
'<article data-testid="result"><a data-testid="result-title-a" href="https://ddg-prvi.si/">DDG prvi</a><div data-result="snippet">Opis</div></article>'
},700)</script></body></html>"""


def _webkit():
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("WebKit", "6.0")
        from gi.repository import GLib, Gtk, WebKit
        return GLib, Gtk, WebKit
    except Exception:  # noqa: BLE001
        return None


class _Streznik:
    def __init__(self, strani, molci=False):
        self.strani, self.molci = strani, molci
        self.vtic = socket.socket()
        self.vtic.bind(("127.0.0.1", 0))
        self.vtic.listen(8)
        self.vrata = self.vtic.getsockname()[1]
        self.zahteve = []
        threading.Thread(target=self._tek, daemon=True).start()

    def _tek(self):
        while True:
            try:
                c, _ = self.vtic.accept()
            except OSError:
                return
            # Vsaka povezava v svoji niti: WebKit odpre tudi povezavo vnaprej (brez zahteve), ki bi zaporedni streznik
            # zadrzala in naslednja zahteva bi cakala do roka.
            threading.Thread(target=self._streci, args=(c,), daemon=True).start()

    def _streci(self, c):
        with c:
            glava = c.recv(65536).decode("latin1")
            if not glava:
                return
            pot = glava.split(" ")[1] if " " in glava else "/"
            self.zahteve.append(pot)
            if self.molci:
                threading.Event().wait(30)         # nikoli ne odgovori: rok
                return
            telo = self.strani.get(pot.split("?")[0], "").encode()
            c.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\nContent-Length: %d\r\n\r\n"
                      % len(telo) + telo)


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(_webkit() is not None, "potrebuje WebKitGTK")
class PredogledVZivo(unittest.TestCase):
    def _isci(self, streznik, pot, motor, cakaj=10):
        GLib, Gtk, WebKit = _webkit()
        p = sz.PredogledIskanja(Gtk, WebKit, GLib, WebKit.NetworkSession.new_ephemeral())
        self.addCleanup(p.zapri)
        izid = []
        zanka = GLib.MainLoop()
        p.isci("http://127.0.0.1:%d%s" % (streznik.vrata, pot), lambda r: (izid.append(r), zanka.quit()), motor=motor)
        GLib.timeout_add(cakaj * 1000, lambda: (zanka.quit(), False)[1])
        zanka.run()
        return p, izid

    def test_google_brez_oglasa_in_zla(self):
        s = _Streznik({"/search": GOOGLE})
        p, izid = self._isci(s, "/search?q=a", "google")
        self.assertEqual(len(izid), 1)
        self.assertEqual([(z["naslov"], z["url"], z["stran"]) for z in izid[0]],
                         [("Prvi zadetek", "https://prvi.si/stran", "prvi.si"), ("Drugi zadetek", "https://drugi.si/", "drugi.si")])
        self.assertEqual(izid[0][0]["odlomek"], "Odlomek prvega")
        # Isti niz znova: iz predpomnilnika, brez nove zahteve.
        stevilo = len(s.zahteve)
        drugi = []
        p.isci("http://127.0.0.1:%d/search?q=a" % s.vrata, drugi.append, motor="google")
        self.assertEqual(drugi, [izid[0]])
        self.assertEqual(len(s.zahteve), stevilo)

    def test_duckduckgo_zadetki_sele_z_javascriptom(self):
        s = _Streznik({"/": DDG})
        _p, izid = self._isci(s, "/?q=a", "duckduckgo")
        self.assertEqual([z["naslov"] for z in izid[0]], ["DDG prvi"])

    def test_rok_vrne_prazno(self):
        s = _Streznik({}, molci=True)
        stari = sz.ROK_S
        sz.ROK_S = 1.0
        try:
            _p, izid = self._isci(s, "/search?q=a", "google", cakaj=5)
        finally:
            sz.ROK_S = stari
        self.assertEqual(izid, [[]])

    def test_novejse_iskanje_prekine_starejse(self):
        GLib, Gtk, WebKit = _webkit()
        s = _Streznik({"/search": GOOGLE})
        p = sz.PredogledIskanja(Gtk, WebKit, GLib, WebKit.NetworkSession.new_ephemeral())
        self.addCleanup(p.zapri)
        prvo, drugo = [], []
        zanka = GLib.MainLoop()
        p.isci("http://127.0.0.1:%d/search?q=a" % s.vrata, prvo.append, motor="google")
        p.isci("http://127.0.0.1:%d/search?q=ab" % s.vrata, lambda r: (drugo.append(r), zanka.quit()), motor="google")
        GLib.timeout_add(10000, lambda: (zanka.quit(), False)[1])
        zanka.run()
        self.assertEqual(prvo, [[]])                      # starejse takoj prazno (lupa ga zavrze)
        self.assertEqual(len(drugo[0]), 2)


if __name__ == "__main__":
    unittest.main()
