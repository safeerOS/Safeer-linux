"""Pregled Spleta 14. 10. 2026, zivo v WebKitGTK 6.0 (Xvfb): okvirji (srcdoc, data:, utm_), prenos blob:, prazno
pojavno okno, Safeer DRM samo iz glavnega okvirja in brez zagona, lokalna datoteka HTML."""
import functools
import http.server
import json
import os
import tempfile
import threading
import time
import unittest

import safeer_brskalnik as b
from gi.repository import GLib

STRAN = """<!doctype html><html><body>
<iframe id="s" srcdoc="<p>srcdoc-ok</p>"></iframe>
<iframe id="d" src="data:text/html,<p>data-ok</p>"></iframe>
<iframe id="u" src="/okvir.html?utm_source=x&amp;a=1"></iframe>
<iframe id="e" src="/eme.html"></iframe>
<a id="dl" download="zivjo.txt">prenos</a>
<script>
document.getElementById("dl").href = URL.createObjectURL(new Blob(["zivjo"], {type: "text/plain"}));
</script></body></html>"""
EME = """<!doctype html><script>
navigator.requestMediaKeySystemAccess("com.widevine.alpha", [{}]).catch(function () {});
try { window.top.webkit.messageHandlers.safeerDrm.postMessage("com.widevine.alpha"); } catch (e) {}
</script>"""


def _cakaj(pogoj, cas=8.0):
    kontekst = GLib.MainContext.default()
    rok = time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.01)
    return pogoj()


def _js(pogled, koda):
    izid = {}

    def konec(p, r, *_):
        try:
            izid["v"] = json.loads(p.evaluate_javascript_finish(r).to_json(0) or "null")
        except Exception as e:  # noqa: BLE001
            izid["v"] = "napaka: %s" % e
    pogled.evaluate_javascript(koda, -1, None, None, None, konec, None)
    _cakaj(lambda: "v" in izid, 5)
    return izid.get("v")


class _Tihi(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


class Zivo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapa = tempfile.mkdtemp()
        for ime, vsebina in (("index.html", STRAN), ("eme.html", EME), ("okvir.html", "<p>okvir</p>"),
                             ("ok.html", "<p>ok</p>"), ("oglas.html", "<p>oglas</p>"),
                             ("video.html", '<video src="/ni-datoteke.mp4" muted autoplay></video>')):
            with open(os.path.join(cls.mapa, ime), "w", encoding="utf-8") as f:
                f.write(vsebina)
        cls.streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Tihi, directory=cls.mapa))
        threading.Thread(target=cls.streznik.serve_forever, daemon=True).start()
        cls.koren = "http://127.0.0.1:%d" % cls.streznik.server_address[1]
        cls.app = b.SafeerBrskalnik()
        # Lasten ID: vsi preizkusi tecejo v enem procesu na vodilu seje - drugi primerek z istim ID je padel z
        # »already exported ... org.gtk.Application«, pravi tekoci Safeer Browser pa bi prevzel klic (18. 10. 2026).
        cls.app.set_application_id(b.APP_ID + ".PreizkusPregled")
        cls.app.register(None)
        cls.app._ustvari()
        cls.s = cls.app.splet
        cls.ponudbe, cls.vdelave = [], []
        # Zabelezimo, kaj bi DRM storil (pravega Safeer DRM v preizkusu ne zaganjamo).
        cls.s._drm_ponudi = lambda p, u, sum_=False: cls.ponudbe.append((u, sum_))
        cls.s._drm_vdelaj = lambda p, u: cls.vdelave.append(u) or True
        cls.prenosi = []
        cls.s.seja.connect("download-started", lambda _k, prenos: (cls.prenosi.append(prenos), prenos.cancel()))
        cls.app.okno.present()

    @classmethod
    def tearDownClass(cls):
        cls.app.okno.destroy()
        cls.streznik.shutdown()

    def _nov(self, pot):
        p = self.s.nov_zavihek(self.koren + pot)
        self.assertTrue(_cakaj(lambda: not p.is_loading() and (p.get_uri() or "").startswith(self.koren), 10))
        _cakaj(lambda: False, 1.5)       # okvirji
        return p

    def test_okvirji_ostanejo_v_strani(self):
        p = self._nov("/index.html")
        self.assertEqual(p.get_uri(), self.koren + "/index.html")      # okvir z utm_ ni zamenjal zavihka
        self.assertEqual(_js(p, 'document.getElementById("s").contentDocument.body.textContent'), "srcdoc-ok")
        self.assertIn("utm_source=x", _js(p, 'document.getElementById("u").contentWindow.location.href'))

    def test_drm_samo_glavni_okvir_in_brez_zagona(self):
        n = len(self.ponudbe)
        p = self._nov("/index.html")
        self.assertEqual(self.ponudbe[n:], [])        # okvir eme.html: nic (tudi neposreden postMessage ne)
        self.assertEqual(_js(p, 'typeof (window.webkit && window.webkit.messageHandlers.safeerDrm)'), "undefined")
        _js(p, 'navigator.requestMediaKeySystemAccess("com.widevine.alpha", [{}]).catch(function(){}); 1')
        self.assertTrue(_cakaj(lambda: len(self.ponudbe) > n, 3))
        self.assertEqual(self.ponudbe[n], (self.koren + "/index.html", False))
        self.assertEqual(self.vdelave, [])            # brez klika se nic ne zazene

    def test_video_z_napako_le_ponudi(self):
        """Sum (napaka zapisa) iz locenega sveta: samo ponudba (sum=True), nic se ne zazene."""
        n = len(self.ponudbe)
        self._nov("/video.html")
        self.assertTrue(_cakaj(lambda: len(self.ponudbe) > n, 8))
        self.assertEqual(self.ponudbe[n], (self.koren + "/video.html", True))
        self.assertEqual(self.vdelave, [])

    def test_blob_prenos(self):
        p = self._nov("/index.html")
        n = len(self.prenosi)
        _js(p, 'document.getElementById("dl").click(); 1')
        self.assertTrue(_cakaj(lambda: len(self.prenosi) > n, 5))

    def test_prazno_pojavno_okno_gre_skozi_pravila(self):
        p = self._nov("/ok.html")
        p.get_settings().set_javascript_can_open_windows_automatically(True)
        self.s.config.set("popup_blokiraj", True)
        n = len(self.s.zavihki)
        tuj = self.koren.replace("127.0.0.1", "localhost") + "/oglas.html"
        _js(p, 'var w = window.open(""); w.location = %s; 1' % json.dumps(tuj))
        self.assertTrue(_cakaj(lambda: self.s._pojavno is not None and self.s._pojavno[1] == tuj, 5))
        self.assertTrue(_cakaj(lambda: len(self.s.zavihki) == n, 3))       # prazen zavihek zaprt
        # Ista stran (npr. prijava v oknu): ostane odprto.
        _js(p, 'var w = window.open(""); w.location = %s; 1' % json.dumps(self.koren + "/okvir.html"))
        self.assertTrue(_cakaj(lambda: any((z["pogled"].get_uri() or "").endswith("/okvir.html")
                                           for z in self.s.zavihki), 5))

    def test_brisanje_ob_izhodu_pocaka_webkit(self):
        """Safeer OS ob izhodu (os_splet.pocisti_vse_ob_izhodu): WebKit brisanje konca pred rokom. Samo predpomnilnik -
        preizkus ne sme brisati piskotkov v nastavitvah, kjer tece."""
        from core import os_splet
        prej = self.s.config.get("brisi_ob_izhodu", [])
        self.s.config.set("brisi_ob_izhodu", ["predpomnilnik"])
        try:
            t0 = time.monotonic()
            self.assertTrue(os_splet.pocisti_vse_ob_izhodu([self.s], GLib, cas=5))
            self.assertLess(time.monotonic() - t0, 5)
        finally:
            self.s.config.set("brisi_ob_izhodu", prej)

    def test_lokalna_datoteka_html(self):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
            f.write("<title>lokalno</title><p>lokalno</p>")
        try:
            uri = GLib.filename_to_uri(f.name, None)
            self.assertFalse(self.s.odpri(uri))               # sporocilo strani ali druge naprave: ne
            self.assertTrue(self.s.odpri(uri, lokalno=True))  # »Odpri z«, naslovna vrstica
            p = self.s.trenutni()
            self.assertTrue(_cakaj(lambda: p.get_uri() == uri and not p.is_loading(), 5))
            self.assertEqual(_js(p, "document.title"), "lokalno")
            self.assertFalse(self.s.odpri("file:///ni/take/datoteke.html", lokalno=True))
            n = len(self.s.zavihki)
            self.assertTrue(self.s.odpri_povezavo(uri, lokalno=True))     # drugi zagon: nov zavihek
            self.assertEqual(len(self.s.zavihki), n + 1)
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
