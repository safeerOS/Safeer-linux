"""Uporabniske skripte v PRAVEM Spletu (core/os_splet.VdelaniSplet, WebKitGTK 6.0, Xvfb) - isti razred kot v Safeer OS
in GTK4 Safeer Browserju.

Dokaze, kar na papirju ni mogoce: skripta iz shrambe tece na lokalni strani, ki jo @match zajame, in ne na drugi;
stran ne vidi ne funkcij GM_ ne mostu shrambe; GM_setValue pride v shrambo; skripta »povsod« ne tece na zacetni strani
Spleta (file://.../ui/splet.html); izklop velja ob ponovnem nalaganju; oznaka v naslovni vrstici pove resnico; uvoz s
poti v oknu »Uporabniske skripte« doda in vklopi skripto sele po opozorilu."""
import http.server
import json
import os
import shutil
import socketserver
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import Gdk, Gio, GLib, Gtk, WebKit
except (ImportError, ValueError):  # brez WebKitGTK 6.0 preizkusa ni
    Gtk = WebKit = None

from core import uporabniske_skripte as us

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STRAN = b"""<!doctype html><html><head><title>zacetek</title></head><body>
<script>
window.addEventListener('load', function () {
  setTimeout(function () {
    var h = window.webkit && window.webkit.messageHandlers;
    document.title = 'us:' + (document.documentElement.getAttribute('data-safeer-us') || '0') +
                     ' gm:' + (typeof GM_addStyle) + ' most:' + (typeof (h && h.safeer_gm));
  }, 50);
});
</script></body></html>
"""

SKRIPTA = """// ==UserScript==
// @name        Preizkus Splet
// @match       http://127.0.0.1/a*
// @run-at      document-end
// @grant       GM_addStyle
// @grant       GM_getValue
// @grant       GM_setValue
// ==/UserScript==
GM_addStyle('body { outline: 0 }');
document.documentElement.setAttribute('data-safeer-us', '1');
GM_setValue('obiski', GM_getValue('obiski', 0) + 1);
"""

POVSOD = """// ==UserScript==
// @name        Povsod
// @match       *://*/*
// ==/UserScript==
document.documentElement.setAttribute('data-safeer-povsod', '1');
"""


class _Streznik(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(STRAN)))
        self.end_headers()
        self.wfile.write(STRAN)

    def log_message(self, *_a):
        pass


def _cakaj(pogoj, cas=15.0):
    kontekst = GLib.MainContext.default()
    rok = time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.01)
    return pogoj()


def _otroci(g):
    o = g.get_first_child()
    while o is not None:
        yield o
        yield from _otroci(o)
        o = o.get_next_sibling()


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(WebKit, "potrebuje WebKitGTK 6.0")
class SkripteVSpletu(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Gtk.init()
        cls.mapa = tempfile.mkdtemp(prefix="safeer-skripte-zivo-")
        cls.stara_mapa = os.environ.get("SAFEER_SKRIPTE_MAPA")
        os.environ["SAFEER_SKRIPTE_MAPA"] = os.path.join(cls.mapa, "skripte")
        cls.id = us.uvozi("preizkus.user.js", SKRIPTA, "js")["skripta"]["id"]
        us.vklopi(cls.id, True)
        socketserver.TCPServer.allow_reuse_address = True
        cls.streznik = socketserver.TCPServer(("127.0.0.1", 0), _Streznik)
        cls.vrata = cls.streznik.server_address[1]
        threading.Thread(target=cls.streznik.serve_forever, daemon=True).start()

        from core import config as _config
        nastavitve = os.path.join(cls.mapa, "settings.json")
        Path(nastavitve).write_text(json.dumps({"doh_enabled": False, "doh_provider": "disabled",
                                                "easylist_enabled": False, "first_run_completed": True}))
        with mock.patch.object(_config, "CONFIG_DIR", cls.mapa), mock.patch.object(_config, "CONFIG_FILE", nastavitve):
            cls.c = _config.ConfigManager()
        from core.os_splet import VdelaniSplet
        with mock.patch("core.threat_intel.skupna", side_effect=RuntimeError("brez vira groženj v preizkusu")):
            cls.splet = VdelaniSplet(Gtk, Gdk, Gio, GLib, WebKit, KOREN, lambda: "sl", None, prvi_zavihek=False,
                                     config=cls.c)
        cls.okno = Gtk.Window()
        cls.okno.set_default_size(900, 700)
        cls.okno.set_child(cls.splet.gradnik)
        cls.okno.present()

    @classmethod
    def tearDownClass(cls):
        for z in list(cls.splet.zavihki):
            try:
                cls.splet.zapri_zavihek(z["pogled"])
            except Exception:  # noqa: BLE001
                pass
        cls.okno.destroy()
        _cakaj(lambda: False, 0.3)
        cls.streznik.shutdown()
        cls.streznik.server_close()
        if cls.stara_mapa is None:
            os.environ.pop("SAFEER_SKRIPTE_MAPA", None)
        else:
            os.environ["SAFEER_SKRIPTE_MAPA"] = cls.stara_mapa
        shutil.rmtree(cls.mapa, ignore_errors=True)

    def naslov(self, pot):
        return "http://127.0.0.1:%d/%s" % (self.vrata, pot)

    def odpri(self, pot):
        self.splet.nov_zavihek(self.naslov(pot))
        pogled = self.splet.trenutni()
        self.assertTrue(_cakaj(lambda: (pogled.get_title() or "").startswith("us:")), pogled.get_title())
        return pogled

    def js(self, pogled, koda):
        izid = {}
        pogled.evaluate_javascript(koda, -1, None, None, None,
                                   lambda p, r: izid.setdefault("v", p.evaluate_javascript_finish(r).to_string()))
        self.assertTrue(_cakaj(lambda: "v" in izid, 5))
        return izid["v"]

    def test_1_tece_na_ujemajoci_strani_v_locenem_svetu(self):
        pogled = self.odpri("a?x=1")
        self.assertEqual(pogled.get_title(), "us:1 gm:undefined most:undefined")
        # oznaka v naslovni vrstici: katere skripte tecejo na tej strani
        znak = self.splet.skripte.znak
        self.assertTrue(znak.get_visible())
        self.assertEqual(znak.get_label(), "JS 1")
        self.assertIn("Preizkus Splet", znak.get_tooltip_text())
        self.assertTrue(znak.get_focusable())                      # dosegljiva s tipkovnico (Tab), Enter odpre okno
        # GM_setValue gre po mostu v shrambo (samo za to skripto)
        self.assertTrue(_cakaj(lambda: us.vrednosti(self.id).get("obiski") == 1, 5), us.vrednosti(self.id))
        # nov posnetek vrednosti (osvezi_vse po 400 ms) skripte v isti strani ne pozene znova
        _cakaj(lambda: False, 1.2)
        self.assertEqual(us.vrednosti(self.id).get("obiski"), 1)
        # naslednje nalaganje vidi shranjeno vrednost (GM_getValue iz posnetka)
        pogled.reload()
        self.assertTrue(_cakaj(lambda: us.vrednosti(self.id).get("obiski") == 2, 10), us.vrednosti(self.id))

    def test_2_ne_tece_na_drugi_strani(self):
        pogled = self.odpri("b")
        self.assertEqual(pogled.get_title(), "us:0 gm:undefined most:undefined")
        self.assertFalse(self.splet.skripte.znak.get_visible())
        # nazaj na zavihek, kjer tece: oznaka sledi izbranemu zavihku
        self.splet.izberi(self.splet.zavihki[0]["pogled"])
        self.assertTrue(self.splet.skripte.znak.get_visible())

    def test_3_povsod_ne_pomeni_notranjih_strani(self):
        sid = us.uvozi("povsod.user.js", POVSOD, "js")["skripta"]["id"]
        us.vklopi(sid, True)                     # poslusalec shrambe osvezi zavihke v glavni niti
        try:
            self.assertTrue(_cakaj(lambda: len(self.splet.skripte.pripravljene()) == 2, 5))
            pogled = self.odpri("b")
            self.assertEqual(self.js(pogled, "document.documentElement.getAttribute('data-safeer-povsod')"), "1")
            self.splet.nov_zavihek("")             # zacetna stran Spleta (file://.../ui/splet.html)
            domaca = self.splet.trenutni()
            self.assertTrue(_cakaj(lambda: (domaca.get_uri() or "").endswith("/ui/splet.html")
                                   and not domaca.is_loading()), domaca.get_uri())
            self.assertEqual(self.js(domaca, "String(document.documentElement.getAttribute('data-safeer-povsod'))"),
                             "null")
            self.assertFalse(self.splet.skripte.znak.get_visible())
        finally:
            us.odstrani(sid)

    def test_4_izklop_velja_ob_ponovnem_nalaganju(self):
        pogled = self.odpri("a")
        us.vklopi(self.id, False)
        try:
            self.assertTrue(_cakaj(lambda: not self.splet.skripte.pripravljene(), 5))
            pogled.reload()
            self.assertTrue(_cakaj(lambda: pogled.get_title() == "us:0 gm:undefined most:undefined"),
                            pogled.get_title())
            self.assertFalse(self.splet.skripte.znak.get_visible())
        finally:
            us.vklopi(self.id, True)

    def test_5_okno_uvoz_s_poti_po_opozorilu(self):
        dom = tempfile.mkdtemp(prefix="safeer-dom-")
        stari_dom = os.environ.get("HOME")
        os.environ["HOME"] = dom
        self.addCleanup(shutil.rmtree, dom, True)
        self.addCleanup(lambda: os.environ.__setitem__("HOME", stari_dom) if stari_dom is not None
                        else os.environ.pop("HOME", None))
        os.makedirs(os.path.join(dom, "Prejemi"))
        pot = os.path.join(dom, "Prejemi", "uvoz.user.js")
        Path(pot).write_text(POVSOD.replace("Povsod", "Uvozena"), encoding="utf-8")
        self.splet.skripte.pokazi()
        okno = self.splet.skripte._okno
        self.addCleanup(lambda: okno.destroy() if self.splet.skripte._okno is not None else None)
        besedila = [g.get_text() for g in _otroci(okno) if isinstance(g, Gtk.Label)]
        self.assertTrue(any(us.mapa().as_posix() in b for b in besedila))          # celotna pot shrambe
        self.assertTrue(any("Preizkus Splet" == b for b in besedila))
        vnos = next(g for g in _otroci(okno) if isinstance(g, Gtk.Entry))
        self.assertTrue(os.path.isabs(vnos.get_placeholder_text()))                  # primer s celotno potjo
        vnos.set_text(pot)
        vnos.emit("activate")                     # Enter v polju
        # opozorilo pred dodajanjem; brez potrditve se nic ne shrani
        gumbi = {g.get_label(): g for g in _otroci(okno) if isinstance(g, Gtk.Button)}
        self.assertIn("Dodaj in vklopi", gumbi)
        self.assertEqual(len(us.seznam()), 1)
        gumbi["Dodaj in vklopi"].emit("clicked")
        nova = [s for s in us.skripte_js(KOREN) if s["naslov"] == "Uvozena"]
        self.assertEqual(len(nova), 1)
        self.assertTrue(nova[0]["vklopljena"])
        stikala = [g for g in _otroci(okno) if isinstance(g, Gtk.Switch)]
        self.assertEqual(len(stikala), 2)
        okno.destroy()
        us.odstrani(nova[0]["id"])

    def test_6_urejevalnik_nova_in_sprememba(self):
        pred = set(Gtk.Window.list_toplevels())
        self.splet.skripte.uredi(None)                          # »Nova skripta …«: predloga z glavo
        ured = next(w for w in Gtk.Window.list_toplevels() if w not in pred)
        koda = next(g for g in _otroci(ured) if isinstance(g, Gtk.TextView))
        b = koda.get_buffer()
        self.assertIn("==UserScript==", b.get_text(b.get_start_iter(), b.get_end_iter(), True))
        b.set_text(POVSOD.replace("Povsod", "Iz urejevalnika"))
        ured.odgovor(Gtk.ResponseType.OK)
        nova = [s for s in us.skripte_js(KOREN) if s["naslov"] == "Iz urejevalnika"]
        self.assertEqual(len(nova), 1)
        self.assertTrue(nova[0]["vklopljena"])
        # sprememba obstojece: ista skripta (id, vklop), nova koda
        pred = set(Gtk.Window.list_toplevels())
        self.splet.skripte.uredi(nova[0]["id"])
        ured = next(w for w in Gtk.Window.list_toplevels() if w not in pred)
        koda = next(g for g in _otroci(ured) if isinstance(g, Gtk.TextView))
        koda.get_buffer().set_text(POVSOD.replace("Povsod", "Spremenjena").replace("*://*/*", "https://example.com/*"))
        ured.odgovor(Gtk.ResponseType.OK)
        s = next(x for x in us.skripte_js(KOREN) if x["id"] == nova[0]["id"])
        self.assertEqual((s["naslov"], s["vklopljena"], s["pripravljeno"]["dovoljeni"]),
                         ("Spremenjena", True, ["https://example.com/*"]))
        us.odstrani(s["id"])


if __name__ == "__main__":
    unittest.main()
