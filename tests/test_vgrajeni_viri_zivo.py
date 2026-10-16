"""Lastni vgrajeni viri v pravem WebKitGTK 6.0 (Xvfb, brez interneta): pravi most Safeer OS (_nov_pogled, MOST_JS z
zetonom, _na_sporocilo, _na_politiko, _vgrajeno_*) in prava komponenta assets/os/vgrajeno.js; tuja stran in komponenta
React tecejo s krajevnega strežnika HTTP (127.0.0.1).

Preverja (lastnik, 15. 10. 2026 - tuja stran je nezaupljiva):
  - okvir ne doseze mostu: sporocilo iz okvirja (tudi z izmisljenim zetonom) Safeer OS ne izvede;
  - okvir ne doseze strani Safeer OS (parent/top), ne navigira glavnega okvirja, brez »Dovoli pojavna okna« ne odpre okna;
  - zahteve iz okvirja gredo skozi filter vsebine (WebKit content blocker iz shrambe Spleta, isti FILTER_ID);
  - glavni okvir pogleda z mostom tuje strani ne prikaze;
  - komponenta React v peskovniku srcdoc: brez parent/top, mostu, piskotkov, localStorage in omrezja (CSP); props dobi,
    izrise se, JSX gre skozi lokalni Babel.
Zagon: xvfb-run -a python3 -m pytest -q tests/test_vgrajeni_viri_zivo.py (potreben PyGObject z Gtk 4 in WebKit 6.0).
"""
import http.server
import json
import os
import shutil
import socketserver
import tempfile
import threading
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOM = tempfile.mkdtemp(prefix="safeer-vgrajeni-zivo-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_DOM, ".config")
os.environ["XDG_CACHE_HOME"] = os.path.join(_DOM, ".cache")
os.environ["XDG_DATA_HOME"] = os.path.join(_DOM, ".local", "share")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import GLib, Gtk, WebKit  # noqa: F401
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        raise ImportError("brez zaslona")
    Gtk.init()
    import safeer_os as so
except (ImportError, ValueError) as _napaka:  # pragma: no cover - okolje brez GTK4/WebKit 6.0 ali zaslona
    raise unittest.SkipTest("WebKitGTK 6.0 ni na voljo: %s" % _napaka)

from core import os_vgrajeni_viri  # noqa: E402
from core.filter_lists import FILTER_ID  # noqa: E402

PRAVE = ("_nov_pogled", "_na_sporocilo", "_na_politiko", "_odgovori", "_js", "_vgrajeno_odprto",
         "_vgrajeno_scit_ustavi", "_vgrajeno_dovoli", "_vgrajeno_aktivno", "_vgrajeno_scit_pripravi",
         "_vgrajeno_filter", "_vgrajeno_novo_okno")


def _cakaj(pogoj, cas=10.0):
    kontekst = GLib.MainContext.default()
    rok = time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.005)
    return pogoj()


class _Strežnik(http.server.SimpleHTTPRequestHandler):
    zahteve: list = []
    porocila: list = []

    def log_message(self, *_a):
        pass

    def do_GET(self):  # noqa: N802
        type(self).zahteve.append(self.path)
        if self.path.startswith("/porocilo?"):
            from urllib.parse import unquote
            type(self).porocila.append(json.loads(unquote(self.path.split("?", 1)[1])))
            self.send_response(204)
            self.end_headers()
            return
        if self.path.endswith(".png"):
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            self.wfile.write(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                                           "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"))
            return
        if self.path.startswith("/zlo.html"):
            telo = ZLO.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(telo)))
            self.end_headers()
            self.wfile.write(telo)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<p>ok</p>")


# Tuja (zlonamerna) stran v okvirju: poskusi most, stran Safeer OS, glavni okvir, okno; nalozi oglas in navadno sliko.
ZLO = """<!doctype html><meta charset="utf-8"><body>
<img src="/oglas/pasica.png"><img src="/dovoljeno.png">
<script>
var r = {};
try { window.webkit.messageHandlers.safeerOs.postMessage(JSON.stringify({id: 1, m: "zazeni", a: ["xterm"]})); r.most = "poslano"; }
catch (e) { r.most = "ni: " + e; }
try { window.webkit.messageHandlers.safeerOs.postMessage(JSON.stringify({id: 2, m: "zazeni", a: ["x"], t: "ugibam"})); } catch (e) {}
try { r.parent = typeof window.parent.SafeerOS; } catch (e) { r.parent = "blokirano"; }
try { r.parentDom = window.parent.document.title; } catch (e) { r.parentDom = "blokirano"; }
try { window.top.location.href = "http://127.0.0.1:PORT/vrh"; r.top = "poskus"; } catch (e) { r.top = "blokirano"; }
try { r.okno = String(window.open("http://127.0.0.1:PORT/okno")); } catch (e) { r.okno = "blokirano"; }
r.zeton = (function () { try { return JSON.stringify(window.parent.SafeerOS); } catch (e) { return "blokirano"; } })();
setTimeout(function () {
  var slike = document.images; r.oglas = slike[0].naturalWidth; r.dovoljeno = slike[1].naturalWidth;
  r.origin = location.origin; r.cookie = (function () { try { document.cookie = "a=1"; return "ok"; } catch (e) { return "ni"; } })();
  new Image().src = "/porocilo?" + encodeURIComponent(JSON.stringify(r));
}, 800);
</script>"""

# Komponenta React (JSX): izrise props, poskusi vse, kar mora peskovnik preprečiti, in porocilo poslje kot »napaka«
# (edino sporocilo z besedilom, ki ga stran sprejme).
KOMPONENTA = """
import React from "react";
export default function Preizkus(props) {
  React.useEffect(function () {
    var r = { title: props.title, imdb: props.imdb, season: props.season };
    try { r.parent = typeof window.parent.SafeerOS; } catch (e) { r.parent = "blokirano"; }
    try { r.parentDom = window.parent.document.title; } catch (e) { r.parentDom = "blokirano"; }
    try { r.top = window.top.location.href; } catch (e) { r.top = "blokirano"; }
    try { window.webkit.messageHandlers.safeerOs.postMessage(JSON.stringify({id: 3, m: "zazeni", a: ["x"]})); r.most = "poslano"; }
    catch (e) { r.most = "ni"; }
    try { document.cookie = "a=1"; r.cookie = document.cookie; } catch (e) { r.cookie = "blokirano"; }
    try { localStorage.setItem("a", "1"); r.storage = "ok"; } catch (e) { r.storage = "blokirano"; }
    r.origin = String(self.origin);          // varnostni izvor (location.origin pri file: kaze naslov)
    var porocaj = function () { window.parent.postMessage({ safeerVgrajeno: 1, tip: "napaka", sporocilo: JSON.stringify(r) }, "*"); };
    try {
      fetch("http://127.0.0.1:PORT/fetch-iz-komponente").then(function () { r.fetch = "uspel"; porocaj(); },
                                                           function () { r.fetch = "blokirano"; porocaj(); });
    } catch (e) { r.fetch = "blokirano"; porocaj(); }
    window.parent.postMessage({ safeerVgrajeno: 1, tip: "vnosi", vnosi: [{ naslov: "Podvojen" }] }, "*");
  }, []);
  return <h1 id="naslov">{props.title}</h1>;
}
"""

# Ista politika vsebine kot assets/os/index.html (prebrana iz nje).
STRAN = """<!doctype html><html><head><meta charset="utf-8">CSP<title>Safeer OS preizkus</title></head><body>
<script src="vgrajeno.js"></script><script src="preizkus.js"></script></body></html>"""
# Skripta strani v datoteki: politika strani (script-src 'self') vrinjenih skript ne dovoli.
PREIZKUS_JS = """
window.dnevnik = []; window.napake = [];
SafeerVgrajeno.nastavi({ aktivno: function (da) { return SafeerOS.klic("vgrajenoAktivno", [da]); } });
window.knjiznica = function (ime) { return SafeerOS.klic("mediaVgrajenaKnjiznica", [ime]); };
"""


def _os_razred():
    imena = {ime: so.SafeerOS.__dict__[ime] for ime in PRAVE}

    class Os:
        posnetek = ""

        def __init__(self):
            import weakref
            self.pogledi, self._os_kontekst = [], None
            self._vgrajeni_pogledi = weakref.WeakSet()
            self._vgrajeni_cel_zaslon = weakref.WeakSet()
            self.klici, self.splet = [], []

        def _obdelaj_klic(self, pogled, id_, metoda, a):
            self.klici.append(metoda)
            if metoda == "vgrajenoAktivno":
                self._odgovori(pogled, id_, True, self._vgrajeno_aktivno(pogled, bool(a[0])))
            elif metoda == "mediaVgrajenaKnjiznica":
                self._odgovori(pogled, id_, True, os_vgrajeni_viri.knjiznica(str(a[0])))
            else:
                self._odgovori(pogled, id_, False, "ni v preizkusu")

        def _splet(self, naslov, *_a):
            self.splet.append(naslov)
            return True

        def _na_vlecene_podatke(self, *_a):
            return None
    for ime, f in imena.items():
        setattr(Os, ime, f)
    return Os


class VgrajeniViriZivo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.koren = tempfile.mkdtemp(dir=_DOM)
        stran = os.path.join(cls.koren, "assets", "os")
        os.makedirs(stran)
        for ime in ("vgrajeno.js", "peskovnik.html"):
            shutil.copy(os.path.join(KOREN, "assets", "os", ime), stran)
        import re
        with open(os.path.join(KOREN, "assets", "os", "index.html"), encoding="utf-8") as d:
            csp = re.search(r'<meta http-equiv="Content-Security-Policy"[^>]*>', d.read()).group(0)
        with open(os.path.join(stran, "preizkus.html"), "w", encoding="utf-8") as d:
            d.write(STRAN.replace("CSP", csp))
        with open(os.path.join(stran, "preizkus.js"), "w", encoding="utf-8") as d:
            d.write(PREIZKUS_JS)
        cls.httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Strežnik)
        cls.httpd.daemon_threads = True
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        global ZLO, KOMPONENTA
        ZLO = ZLO.replace("PORT", str(cls.port))
        KOMPONENTA = KOMPONENTA.replace("PORT", str(cls.port))
        # Filter vsebine, kot ga prevede Splet (ista shramba, isti FILTER_ID): pravilo blokira /oglas/.
        from core.threat_intel import default_data_dir
        mapa = default_data_dir("safeer-mint").parent / "filter-lists" / "compiled"
        mapa.mkdir(parents=True, exist_ok=True)
        shramba = WebKit.UserContentFilterStore.new(str(mapa))
        pravila = json.dumps([{"trigger": {"url-filter": "/oglas/"}, "action": {"type": "block"}}])
        izid = {}
        shramba.save(FILTER_ID, GLib.Bytes.new(pravila.encode()), None,
                     lambda s, r, *_: izid.setdefault("f", s.save_finish(r)))
        assert _cakaj(lambda: "f" in izid, 20), "filter ni preveden"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def setUp(self):
        from unittest import mock
        p = mock.patch.object(so, "KOREN", self.koren)
        p.start()
        self.addCleanup(p.stop)
        _Strežnik.zahteve.clear()
        _Strežnik.porocila.clear()
        self.os = _os_razred()()
        self.pogled = self.os._nov_pogled("preizkus.html")
        self.okno = Gtk.Window()
        self.okno.set_default_size(900, 600)
        self.okno.set_child(self.pogled)
        self.okno.present()
        self.addCleanup(self.okno.destroy)
        self.assertTrue(_cakaj(lambda: self._js("!!window.SafeerOS && !!window.SafeerVgrajeno") is True, 20))

    def _js(self, koda):
        izid = {}

        def konec(p, r, *_):
            try:
                izid["v"] = json.loads(p.evaluate_javascript_finish(r).to_string() or "null")
            except Exception as e:  # noqa: BLE001
                izid["v"] = "napaka:%s" % e
        self.pogled.evaluate_javascript("JSON.stringify((%s)) || \"null\"" % koda, -1, None, None, None, konec, None)
        _cakaj(lambda: "v" in izid, 5)
        return izid.get("v")

    def test_tuja_stran_ne_doseze_mostu_in_gre_skozi_filter(self):
        url = "http://127.0.0.1:%d/zlo.html" % self.port
        self._js("window.h = SafeerVgrajeno.odpri({url: %s, title: 'Zlo', allowFullscreen: true}), 1" % json.dumps(url))
        self.assertTrue(_cakaj(lambda: _Strežnik.porocila, 15), "porocilo iz okvirja: %s" % _Strežnik.zahteve)
        r = _Strežnik.porocila[0]
        self.assertEqual(self.os.klici, ["vgrajenoAktivno"], "okvir ni izvedel nobenega klica mostu")
        self.assertTrue(getattr(self.os, "_most_zavrnjen", False), "most je sporocila okvirja zavrnil")
        self.assertEqual(r["parent"], "blokirano")
        self.assertEqual(r["parentDom"], "blokirano")
        self.assertEqual(r["zeton"], "blokirano")
        self.assertEqual(r["okno"], "null", "brez »Dovoli pojavna okna« ni okna")
        self.assertEqual(r["origin"], "http://127.0.0.1:%d" % self.port, "allow-same-origin: lasten izvor strani")
        self.assertEqual(r["oglas"], 0, "filter vsebine je ustavil /oglas/ v okvirju")
        self.assertEqual(r["dovoljeno"], 1)
        self.assertNotIn("/oglas/pasica.png", _Strežnik.zahteve)
        self.assertIn("/dovoljeno.png", _Strežnik.zahteve)
        _cakaj(lambda: False, 0.5)
        self.assertNotIn("/vrh", _Strežnik.zahteve, "okvir ni navigiral glavnega okvirja")
        self.assertNotIn("/okno", _Strežnik.zahteve)
        self.assertTrue(self.pogled.get_uri().startswith("file://"))
        self.assertEqual(self.os.splet, [])
        # Zaprtje: filter in dovoljenje okvirjev gresta s pogleda.
        self._js("window.h.zapri(), 1")
        self.assertTrue(_cakaj(lambda: not self.os._vgrajeno_odprto(self.pogled), 5))

    def test_glavni_okvir_ne_prikaze_tuje_strani(self):
        url = "http://127.0.0.1:%d/zlo.html" % self.port
        self._js("window.h = SafeerVgrajeno.odpri({url: %s, title: 'Zlo'}), 1" % json.dumps(url))
        self.assertTrue(_cakaj(lambda: self.os._vgrajeno_odprto(self.pogled), 5))
        self._js("location.href = 'http://127.0.0.1:%d/glavni', 1" % self.port)
        _cakaj(lambda: False, 1.5)
        self.assertTrue(self.pogled.get_uri().startswith("file://"), self.pogled.get_uri())
        self.assertTrue(self._js("!!window.SafeerVgrajeno"))

    def test_pojavno_okno_samo_z_dovoljenjem_v_spletu(self):
        # Okno brez klika uporabnika WebKit ustavi sam (javascript-can-open-windows-automatically = ne). Klik uporabnika
        # tu nadomestimo s to nastavitvijo; brez »Dovoli pojavna okna« okno ustavi peskovnik, z njim ga odpre Splet.
        self.pogled.get_settings().set_property("javascript-can-open-windows-automatically", True)
        global ZLO
        prej = ZLO
        self.addCleanup(lambda: globals().__setitem__("ZLO", prej))
        url = "http://127.0.0.1:%d/zlo.html" % self.port
        ZLO = "<script>window.open('http://127.0.0.1:%d/brez')</script>" % self.port
        self._js("window.h = SafeerVgrajeno.odpri({url: %s, title: 'Brez'}), 1" % json.dumps(url))
        self.assertTrue(_cakaj(lambda: "/zlo.html" in _Strežnik.zahteve, 10))
        _cakaj(lambda: False, 1.0)
        self.assertEqual(self.os.splet, [], "brez dovoljenja ni okna")
        self._js("window.h.zapri(), 1")
        ZLO = "<script>window.open('http://127.0.0.1:%d/prijava')</script>" % self.port
        self._js("window.h = SafeerVgrajeno.odpri({url: %s, title: 'Prijava', allowPopups: true}), 1" % json.dumps(url))
        self.assertTrue(_cakaj(lambda: self.os.splet, 10), "okno je odprl Splet")
        self.assertEqual(self.os.splet, ["http://127.0.0.1:%d/prijava" % self.port])
        self.assertNotIn("/prijava", _Strežnik.zahteve, "Medijski center okna ni nalozil sam")

    def test_komponenta_react_v_peskovniku(self):
        self._js("""window.h = SafeerVgrajeno.komponenta({koda: %s, title: 'Komponenta', knjiznica: window.knjiznica,
                     props: {title: 'Breaking Bad', imdb: 'tt0903747', season: '1'},
                     onReady: function () { window.dnevnik.push('pripravljen'); },
                     onError: function (s) { window.napake.push(s); }}), 1""" % json.dumps(KOMPONENTA))
        self.assertTrue(_cakaj(lambda: self._js("window.napake.length") or 0, 30), "porocilo komponente")
        r = json.loads(self._js("window.napake[0]"))
        self.assertIn("pripravljen", self._js("window.dnevnik"), "komponenta se je izrisala")
        self.assertEqual((r["title"], r["imdb"], r["season"]), ("Breaking Bad", "tt0903747", "1"), "props")
        self.assertEqual(r["parent"], "blokirano")
        self.assertEqual(r["parentDom"], "blokirano")
        self.assertEqual(r["top"], "blokirano")
        self.assertIn(r["cookie"], ("", "blokirano"), "piskotek se ne shrani (neprozoren izvor)")
        self.assertEqual(r["storage"], "blokirano")
        self.assertEqual(r["origin"], "null", "neprozoren izvor")
        self.assertEqual(r["fetch"], "blokirano")
        self.assertNotIn("/fetch-iz-komponente", _Strežnik.zahteve)
        self.assertEqual(self.os.klici.count("vgrajenoAktivno"), 1)
        self.assertNotIn("zazeni", self.os.klici)
        self.assertTrue(getattr(self.os, "_most_zavrnjen", False))
        self.assertIn("mediaVgrajenaKnjiznica", self.os.klici)          # babel le, ker koda ima JSX/import



    def test_komponenta_brez_jsx_brez_babla(self):
        koda = "function Pozdrav(props) { return React.createElement('b', null, props.title); }"
        self._js("""window.h = SafeerVgrajeno.komponenta({koda: %s, title: 'JS', knjiznica: function (ime) {
                     window.dnevnik.push('knjiznica:' + ime); return window.knjiznica(ime); }, props: {title: 'X'},
                     onReady: function () { window.dnevnik.push('pripravljen'); },
                     onError: function (s) { window.napake.push(s); }}), 1""" % json.dumps(koda))
        self.assertTrue(_cakaj(lambda: "pripravljen" in (self._js("window.dnevnik") or []), 15), self._js("window.napake"))
        self.assertEqual(sorted(x for x in self._js("window.dnevnik") if x.startswith("knjiznica:")),
                         ["knjiznica:react", "knjiznica:react-dom"], "Babel samo za JSX/import")
        self._js("window.h.zapri(), 1")
        self.assertTrue(_cakaj(lambda: not self.os._vgrajeno_odprto(self.pogled), 5))

class NastavitveInPolicaZivo(unittest.TestCase):
    """Prava stran Medijskega centra (index.html?predvajalnik=1, os.js, besedila.js, vgrajeno.js) in pravi Katalog
    (core/os_katalog.py) v zacasni mapi: dodajanje vira z obvestilom, meritev, ploscica na Domov, podvojen vir,
    »Preizkusi« predloge in odprtje ploscice v okvirju (Escape zapre)."""

    @classmethod
    def setUpClass(cls):
        cls.httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Strežnik)
        cls.httpd.daemon_threads = True
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def setUp(self):
        from core import os_katalog
        _Strežnik.zahteve.clear()
        Os = _os_razred()
        test = self

        class OsStran(Os):
            def _obdelaj_klic(self, pogled, id_, metoda, a):
                self.klici.append(metoda)
                if metoda == "vgrajenoAktivno":
                    self._odgovori(pogled, id_, True, self._vgrajeno_aktivno(pogled, bool(a[0])))
                elif metoda == "zacetek":
                    self._odgovori(pogled, id_, True, {"jezik": "sl", "platforma": "linux", "mape": []})
                elif test.katalog.pozna(metoda):
                    def delo():
                        try:
                            self._odgovori(pogled, id_, True, test.katalog.izvedi(metoda, a))
                        except Exception as e:  # noqa: BLE001
                            self._odgovori(pogled, id_, False, str(e))
                    threading.Thread(target=delo, daemon=True).start()
                else:
                    self._odgovori(pogled, id_, False, "ni v preizkusu")

            def _dogodek(self, vrsta, podatki, pogled=None):
                koda = "window.safeerOsDogodek && window.safeerOsDogodek(%s, %s);" % (json.dumps(vrsta), json.dumps(podatki))
                GLib.idle_add(lambda: (self._js(koda, test.pogled), False)[1])
        self.os = OsStran()
        self.katalog = os_katalog.Katalog(tempfile.mkdtemp(dir=_DOM), self.os._dogodek, lambda f: f(),
                                          *(lambda *a, **k: True,) * 4)
        self.pogled = self.os._nov_pogled("index.html?predvajalnik=1&jezik=sl")
        self.okno = Gtk.Window()
        self.okno.set_default_size(1280, 800)
        self.okno.set_child(self.pogled)
        self.okno.present()
        self.addCleanup(self.okno.destroy)
        self.assertTrue(_cakaj(lambda: self._js("!!window.SafeerOS && !!document.getElementById('vgrObrazec')") is True, 20))
        self.assertTrue(_cakaj(lambda: "mediaVgrajeniViri" in self.os.klici, 10), self.os.klici)

    _js = VgrajeniViriZivo._js

    def _vnesi(self, ime, url):
        self._js("""(function () { document.getElementById('slojKatViri').classList.add('viden');
            document.getElementById('vgrIme').value = %s; document.getElementById('vgrUrl').value = %s;
            document.getElementById('vgrObrazec').requestSubmit(); return 1; })()""" % (json.dumps(ime), json.dumps(url)))

    def test_dodaj_stran_obvestilo_meritev_ploscica(self):
        self.assertTrue(_cakaj(lambda: "Še nimaš lastnih virov" in (self._js("document.getElementById('vgrSeznam').textContent") or ""), 5))
        self.assertIn("lastno odgovornost", self._js("document.querySelector('.vgr-odgovornost').textContent"))
        url = "http://127.0.0.1:%d/stran" % self.port
        self._vnesi("Moja stran", url)
        self.assertTrue(_cakaj(lambda: self._js("document.getElementById('slojVgrOdgovornost').classList.contains('viden')"), 5),
                        "obvestilo ob prvem viru")
        self.assertNotIn("mediaVgrajenVirShrani", self.os.klici, "brez potrditve se vir ne shrani")
        self._js("document.getElementById('vgrOdgPotrdi').click(), 1")
        self.assertTrue(_cakaj(lambda: "ms ·" in (self._js("document.getElementById('vgrSeznam').textContent") or ""), 10),
                        self._js("document.getElementById('vgrSeznam').textContent"))
        # Ploscica na Domov (Safeer Player se odpre na Domov) - odpre okvir v Medijskem centru.
        self._js("document.getElementById('slojKatViri').classList.remove('viden'), 1")
        self._js("window.safeerOsPojdi && window.safeerOsPojdi('media'), 1")
        self.assertTrue(_cakaj(lambda: self._js("!document.getElementById('mediaVgrajenePloscice').hidden && "
                                                 "document.querySelectorAll('.vgr-ploscica').length") == 1, 10))
        self._js("document.querySelector('.vgr-ploscica').click(), 1")
        self.assertTrue(_cakaj(lambda: "/stran" in _Strežnik.zahteve, 10), "okvir je nalozil stran: %s %s %s" % (
            self.os.klici[-6:], self._js("document.querySelector('.vgrajeno-sloj iframe') && document.querySelector('.vgrajeno-sloj iframe').src"),
            _Strežnik.zahteve))
        self.assertTrue(self._js("!!document.querySelector('.vgrajeno-sloj iframe[sandbox]')"))
        self._js("window.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'})), 1")
        self.assertTrue(_cakaj(lambda: self._js("!document.querySelector('.vgrajeno-sloj')"), 5), "Escape zapre vir")
        self.assertTrue(_cakaj(lambda: not self.os._vgrajeno_odprto(self.pogled), 5))
        # Isti naslov drugic: »Ta vir že imaš.«
        self._js("document.getElementById('vgrSporocilo').textContent = '', 1")
        self._vnesi("Se enkrat", "http://127.0.0.1:%d/stran/" % self.port)
        self.assertTrue(_cakaj(lambda: self._js("document.getElementById('vgrSporocilo').textContent") == "Ta vir že imaš.", 5))
        # Preizkusi predloge.
        self._js("""(function () { document.getElementById('vgrUrl').value = 'http://127.0.0.1:%d/e/{type}/{imdb}';
            document.getElementById('vgrPreizkusi').click(); return 1; })()""" % self.port)
        self.assertTrue(_cakaj(lambda: "Film: http://127.0.0.1:%d/e/movie/tt0111161" % self.port in
                               (self._js("document.getElementById('vgrSporocilo').textContent") or ""), 5),
                        self._js("document.getElementById('vgrSporocilo').textContent"))

if __name__ == "__main__":
    unittest.main()
