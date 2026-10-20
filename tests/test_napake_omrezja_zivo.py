"""Samodejna ponovitev ob prekinjeni povezavi v pravem WebKitGTK 6.0 (Xvfb). Lastnik, 20. 10. 2026: Google iskanje v
Spletu je pokazalo »Strani trenutno ni mogoce odpreti« (povezava prekinjena), ponovni poskus je delal - samodejno se je
prej ponovilo samo iskanje DuckDuckGo. Streznik prvo povezavo zapre brez odgovora (WebKit: g-io-error-quark 34
»Connection terminated unexpectedly«, izmerjeno), drugo postrezi. POST obrazca se nikoli ne ponovi.
Brez zaslona ali WebKita se preskoci."""
import os
import socket
import sys
import threading
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)


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
    """Prvih `prekini` povezav zapre brez odgovora, potem odgovori 200. Belezi metode zahtev."""

    def __init__(self, prekini):
        self.prekini = prekini
        self.metode = []
        self.vtic = socket.socket()
        self.vtic.bind(("127.0.0.1", 0))
        self.vtic.listen(8)
        self.vrata = self.vtic.getsockname()[1]
        threading.Thread(target=self._tek, daemon=True).start()

    def _tek(self):
        while True:
            try:
                c, _ = self.vtic.accept()
            except OSError:
                return
            with c:
                glava = c.recv(65536)
                if not glava:
                    continue
                self.metode.append(glava.split(b" ", 1)[0].decode())
                if self.prekini > 0:
                    self.prekini -= 1
                    continue
                telo = b"<title>ok</title>ok"
                c.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\nContent-Length: %d\r\n\r\n"
                          % len(telo) + telo)

    def zapri(self):
        self.vtic.close()


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(_webkit() is not None, "potrebuje WebKitGTK")
class PonovitevVZivo(unittest.TestCase):
    def _nalozi(self, streznik, nalozi, cakaj_s=15):
        GLib, Gtk, WebKit = _webkit()
        from core.network_errors import NetworkErrorHandler
        pogled = WebKit.WebView()
        okno = Gtk.Window()
        okno.set_child(pogled)
        okno.present()
        NetworkErrorHandler(pogled, "sl")
        zanka = GLib.MainLoop()
        naslovi = []

        # Naslov (notify::title) pride lahko sele po LoadEvent.FINISHED - zbiramo ga ob vsaki spremembi.
        pogled.connect("notify::title", lambda p, _s: naslovi.append(p.get_title() or ""))
        nalozi(pogled)
        konec = GLib.get_monotonic_time() + cakaj_s * 1_000_000

        def preveri():
            if "ok" in naslovi or GLib.get_monotonic_time() > konec:
                zanka.quit()
                return False
            return True
        GLib.timeout_add(100, preveri)
        zanka.run()
        # Se 2,5 s: morebitna nepricakovana ponovitev (POST) bi prisla v tem casu.
        GLib.timeout_add(2500, lambda: (zanka.quit(), False)[1])
        zanka.run()
        okno.destroy()
        return naslovi

    def test_prekinjen_get_se_sam_ponovi(self):
        s = _Streznik(prekini=1)
        try:
            naslovi = self._nalozi(s, lambda p: p.load_uri("http://127.0.0.1:%d/search?q=say%%20maybe" % s.vrata))
        finally:
            s.zapri()
        self.assertIn("ok", naslovi, "stran se po prekinjeni povezavi ni sama nalozila: %r, zahteve %r" % (naslovi, s.metode))
        self.assertEqual(s.metode, ["GET", "GET"])

    def test_dvakrat_prekinjen_get_se_vedno_nalozi(self):
        s = _Streznik(prekini=2)
        try:
            naslovi = self._nalozi(s, lambda p: p.load_uri("http://127.0.0.1:%d/" % s.vrata))
        finally:
            s.zapri()
        self.assertIn("ok", naslovi)
        self.assertEqual(s.metode, ["GET", "GET", "GET"])

    def test_vztrajna_napaka_pokaze_stran_napake(self):
        s = _Streznik(prekini=99)
        try:
            naslovi = self._nalozi(s, lambda p: p.load_uri("http://127.0.0.1:%d/" % s.vrata), cakaj_s=6)
        finally:
            s.zapri()
        self.assertEqual(len(s.metode), 3, "najvec dve samodejni ponovitvi: %r" % s.metode)
        self.assertTrue(any("Strani trenutno ni mogoče odpreti" in n for n in naslovi), naslovi)

    def test_post_obrazca_se_ne_ponovi(self):
        s = _Streznik(prekini=99)
        obrazec = ('<form method="post" action="http://127.0.0.1:%d/poslji"><input name="a" value="1"></form>'
                   '<script>document.forms[0].submit()</script>' % s.vrata)
        try:
            self._nalozi(s, lambda p: p.load_html(obrazec, "http://127.0.0.1:%d/" % s.vrata), cakaj_s=6)
        finally:
            s.zapri()
        self.assertEqual(s.metode, ["POST"], "POST obrazca se ne sme samodejno ponoviti (ne kot POST ne kot GET)")



@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(_webkit() is not None, "potrebuje WebKitGTK")
class PonovitevBrezVirov(PonovitevVZivo):
    """Kot zgoraj, a kot nas WebKit 2.54 v paketih (brez resource-load-started, izmerjeno 20. 10. 2026): metodo
    navigacije pove decide-policy. Sistemski WebKit v CI ima signal se, zato ga tu skrijemo."""

    def setUp(self):
        from unittest import mock
        zaplata = mock.patch("core.network_errors._ima_vire", lambda _v: False)
        zaplata.start()
        self.addCleanup(zaplata.stop)


if __name__ == "__main__":
    unittest.main()
