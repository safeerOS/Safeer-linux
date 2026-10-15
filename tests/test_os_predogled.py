"""Okno predogleda (core/os_predogled.py) v zivem WebKitGTK 6.0 (Xvfb): PDF prek vgrajenega PDF.js, stran brez
JavaScripta za vse drugo in brez omrezja - oddaljena slika ali sledilni piksel ne pride do streznika, tudi ce bi
ciscenje HTML kaj spustilo (izmerjeno 15. 10. 2026 z lokalnim streznikom HTTP)."""
import http.server
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

try:
    gi.require_version("WebKit", "6.0")
    from gi.repository import Gdk, WebKit  # noqa: E402
except (ValueError, ImportError):  # pragma: no cover - sistem brez WebKitGTK 6.0
    WebKit = None

from core import os_predogled, predogled_datotek  # noqa: E402


def _cakaj(pogoj, cas=15.0) -> bool:
    konec = time.monotonic() + cas
    kontekst = GLib.MainContext.default()
    while time.monotonic() < konec:
        while kontekst.pending():
            kontekst.iteration(False)
        if pogoj():
            return True
        time.sleep(0.02)
    return False


class _Strezni(http.server.BaseHTTPRequestHandler):
    zahteve = []

    def do_GET(self):  # noqa: N802
        _Strezni.zahteve.append(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "image/gif")
        self.end_headers()
        self.wfile.write(b"GIF89a")

    def log_message(self, *_a):
        pass


@unittest.skipIf(WebKit is None or not Gtk.init_check(), "WebKitGTK 6.0 ali zaslon ni na voljo")
class OknoPredogleda(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.m = Path(self.d.name)
        self.povezave = []
        self.okno = os_predogled.OknoPredogleda(Gtk, Gdk, GLib, WebKit, lambda: "sl",
                                                odpri_povezavo=self.povezave.append,
                                                odpri_v_programu=lambda p: True, pokazi_v_mapi=lambda p: True)

    def tearDown(self):
        self.okno.zapri()
        _cakaj(lambda: not self.okno.odprto(), 2)
        self.d.cleanup()

    def _nalozeno(self):
        return _cakaj(lambda: self.okno._pogled is not None and not self.okno._pogled.is_loading()
                      and self.okno._pogled.get_estimated_load_progress() >= 1.0)

    def test_html_brez_javascripta_in_brez_omrezja(self):
        streznik = http.server.HTTPServer(("127.0.0.1", 0), _Strezni)
        threading.Thread(target=streznik.serve_forever, daemon=True).start()
        try:
            _Strezni.zahteve = []
            naslov = "http://127.0.0.1:%d/sled.gif" % streznik.server_address[1]
            rod = self.okno.odpri("pismo.html")
            # Surov HTML mimo ciscenja (najslabsi primer): slika s streznika in skripta.
            html = '<p id="p">x</p><img src="%s"><script>document.title="js"</script>' % naslov
            self.assertTrue(self.okno.pokazi(rod, {"nacin": "html", "html": html, "osnova": ""}))
            self.assertTrue(self._nalozeno())
            _cakaj(lambda: False, 1.5)                      # cas za morebitno zahtevo slike
            self.assertEqual(_Strezni.zahteve, [])          # zaprt posrednik: nic ne gre ven
            self.assertFalse(self.okno._pogled.get_settings().get_enable_javascript())
            self.assertNotEqual(self.okno._pogled.get_title(), "js")
        finally:
            streznik.shutdown()

    def test_pdf_z_vgrajenim_pdfjs(self):
        pdf = self.m / "a.pdf"
        # Najmanjsi veljaven PDF z eno stranjo.
        pdf.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
                        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF")
        rod = self.okno.odpri("a.pdf")
        self.assertTrue(self.okno.pokazi(rod, predogled_datotek.pripravi(str(pdf)), str(pdf)))
        self.assertTrue(self._nalozeno())
        self.assertTrue(self.okno._pogled.get_settings().get_enable_javascript())    # PDF.js potrebuje JS
        self.assertTrue(self.okno._pogled.get_uri().startswith("file://"))
        self.assertTrue(self.okno._gumb_odpri.get_visible())

    def test_pozen_rezultat_ne_povozi_novega(self):
        rod1 = self.okno.odpri("prva.txt")
        rod2 = self.okno.odpri("druga.txt")
        self.assertFalse(self.okno.pokazi(rod1, {"nacin": "html", "html": "<p>stara</p>"}))
        self.assertTrue(self.okno.pokazi(rod2, {"nacin": "html", "html": "<p>nova</p>"}))

    def test_prenos_v_glavi(self):
        shranjeno = self.m / "x.pdf"
        shranjeno.write_bytes(b"x")
        self.okno.odpri("x.pdf", prenesi=lambda: str(shranjeno))
        self.assertTrue(self.okno._gumb_prenesi.get_visible())
        self.okno._na_prenesi()
        self.assertTrue(_cakaj(lambda: self.okno._shranjeno == str(shranjeno), 5))
        self.assertEqual(self.okno._gumb_prenesi.get_label(), predogled_datotek.besedilo("mapa", "sl"))


class Politika(unittest.TestCase):
    """Odlocitev o premiku strani brez WebKita (nadomestki): povezava gre v Splet samo ob kliku uporabnika."""

    @unittest.skipIf(WebKit is None, "WebKitGTK 6.0 ni na voljo")
    def test_povezava_v_splet_drugo_zavrnjeno(self):
        povezave = []
        okno = os_predogled.OknoPredogleda(Gtk, None, GLib, WebKit, lambda: "sl", odpri_povezavo=povezave.append)

        class Odl:
            def __init__(self, uri, kretnja=True):
                self.uri, self.kretnja, self.zavrnjeno = uri, kretnja, False

            def get_navigation_action(self):
                o = self

                class A:
                    def get_request(self):
                        class R:
                            def get_uri(self):
                                return o.uri
                        return R()

                    def is_user_gesture(self):
                        return o.kretnja
                return A()

            def ignore(self):
                self.zavrnjeno = True
        nav = WebKit.PolicyDecisionType.NAVIGATION_ACTION
        for uri, zavrnjeno in (("https://safeer.si/", True), ("file:///tmp/a.pdf", False),
                               ("webkit-pdfjs-viewer://pdfjs/web/viewer.html", False), ("ftp://x/y", True),
                               ("javascript:alert(1)", True)):
            o = Odl(uri)
            okno._na_politiko(None, o, nav)
            self.assertEqual(o.zavrnjeno, zavrnjeno, uri)
        self.assertEqual(povezave, ["https://safeer.si/"])
        o = Odl("https://sled.example/", kretnja=False)                # samodejna preusmeritev, ne klik
        okno._na_politiko(None, o, nav)
        self.assertTrue(o.zavrnjeno)
        self.assertEqual(povezave, ["https://safeer.si/"])


class Most(unittest.TestCase):
    """Most Safeer OS za priponke: priloge samo kot obstojece datoteke, predogled iz istega okna za vse dele."""

    def test_opis_prilog_in_velikost(self):
        import safeer_os
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.pdf").write_bytes(b"x" * 1500)
            (Path(d) / "mapa").mkdir()
            opis = safeer_os._opis_prilog([str(Path(d) / "a.pdf"), str(Path(d) / "mapa"), str(Path(d) / "ni.txt")])
        self.assertEqual([(o["ime"], o["velikost"]) for o in opis], [("a.pdf", 1500)])
        self.assertEqual(safeer_os._velikost_napis(2_500_000), "2,4 MB")
        self.assertEqual(safeer_os._velikost_napis(0), "")

    def test_metode_mostu(self):
        py = (Path(__file__).resolve().parents[1] / "safeer_os.py").read_text(encoding="utf-8")
        for metoda in ("sporocilaPredogled", "sporocilaIzvirnik", "predogledDatoteke", "sporocilaPrenesiPriponko",
                       "sporocilaPrenesiVse", "sporocilaSlicicaPriponke", "opisPrilog", "izberiPriloge"):
            self.assertIn('"%s":' % metoda, py, metoda)
        # Odpiranje priponke v programu je samo v oknu predogleda (s potrditvijo za nevarne), ne neposredno s strani.
        self.assertNotIn('"sporocilaOdpriPriponko"', py)


if __name__ == "__main__":
    unittest.main()
