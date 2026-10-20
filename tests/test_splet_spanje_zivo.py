"""Spanje zavihkov, safeer://procesi in obnova omreznega procesa - zivo v WebKitGTK 6.0 (Xvfb), 18. 10. 2026.

Meri, kar trdi core/splet_spanje.py: koliko pomnilnika uspan zavihek sprosti, da se zbudi na istem naslovu in mestu,
da zasciteni zavihki (aktiven, vpisan obrazec, poslan obrazec, predvajanje, povezano okno) ne zaspijo, da spletna stran
safeer://procesi ne more uporabiti in da omrezni proces po obnovi obdrzi piskotke seje. Spletnih strani na internetu
ne odpira (lokalni streznik); nastavitve in piskotki so v zacasni mapi (nikoli v pravem profilu).
"""
import ctypes
import functools
import http.server
import json
import os
import re
import struct
import tempfile
import threading
import time
import unittest

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gdk, Gio, GLib, Gtk, WebKit  # noqa: E402

from core import splet_spanje  # noqa: E402
from core.config import ConfigManager  # noqa: E402
from core.os_splet import VdelaniSplet, omrezni_procesi_shrambe, pss_mb  # noqa: E402
from core.tab_monitor import web_processes_under  # noqa: E402

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEZKA = ("<!doctype html><title>Tezka</title><body style='height:6000px'><h1>tezka</h1>"
         "<script>window.x = new Array(2000000).fill(0).map(function (_, i) { return 'niz' + i; });</script></body>")
OBRAZEC = "<!doctype html><title>Obrazec</title><input id=i><p>obrazec</p>"
POST = "<!doctype html><title>Oddaja</title><form method=post action=/rezultat><input name=a value=1><button id=b>x</button></form>"
ZVOK = "<!doctype html><title>Zvok</title><audio id=a src=/ton.wav loop muted></audio>"
NAPAD = """<!doctype html><title>Napad</title><a id=a href="%(cilj)s">x</a><iframe src="%(cilj)s"></iframe><img src="%(cilj)s">
<script>fetch("%(cilj)s").catch(function () {}); setTimeout(function () { document.getElementById("a").click(); }, 200);
setTimeout(function () { location.href = "%(cilj)s"; }, 600); setTimeout(function () { history.pushState({}, "", "/n"); }, 900);
</script>"""


def _wav() -> bytes:
    n = 8000
    podatki = bytes(128 + (40 if (i // 20) % 2 else -40) for i in range(n))
    return (b"RIFF" + struct.pack("<I", 36 + n) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, 8000, 8000, 1, 8)
            + b"data" + struct.pack("<I", n) + podatki)


class _Streznik(http.server.BaseHTTPRequestHandler):
    posti = []
    napad = ""

    def log_message(self, *a):
        pass

    def _poslji(self, telo, vrsta="text/html", glave=()):
        b = telo if isinstance(telo, bytes) else telo.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", vrsta)
        self.send_header("Content-Length", str(len(b)))
        for k, v in glave:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        pot = self.path.split("?")[0]
        if pot == "/tezka.html":
            self._poslji(TEZKA)
        elif pot == "/obrazec.html":
            self._poslji(OBRAZEC)
        elif pot == "/post.html":
            self._poslji(POST)
        elif pot == "/zvok.html":
            self._poslji(ZVOK)
        elif pot == "/ton.wav":
            self._poslji(_wav(), "audio/wav")
        elif pot == "/napad.html":
            self._poslji(NAPAD % {"cilj": _Streznik.napad})
        elif pot == "/piskotek":
            self._poslji("<!doctype html><title>Piskotek</title>", glave=(
                ("Set-Cookie", "seja=1; Path=/"), ("Set-Cookie", "trajen=1; Max-Age=3600; Path=/")))
        elif pot == "/preveri":
            self._poslji("<!doctype html><title>%s</title>" % (self.headers.get("Cookie") or "brez"))
        else:
            self._poslji("<!doctype html><title>Prazno</title>")

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        _Streznik.posti.append(self.path)
        self._poslji("<!doctype html><title>Rezultat</title>")


def _cakaj(pogoj, cas=10.0):
    kontekst = GLib.MainContext.default()
    rok = time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.01)
    return bool(pogoj())


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


def _vsota_pss() -> float:
    return sum(pss_mb(p) for p in web_processes_under(os.getpid()))


class _Tipkovnica:
    """Prave tipke prek XTEST (isTrusted v strani) - samo za Xvfb preizkusa."""

    def __init__(self):
        self.x11 = ctypes.CDLL("libX11.so.6")
        self.xtst = ctypes.CDLL("libXtst.so.6")
        self.x11.XOpenDisplay.restype = ctypes.c_void_p
        self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x11.XStringToKeysym.restype = ctypes.c_ulong
        self.x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
        self.x11.XKeysymToKeycode.restype = ctypes.c_ubyte
        self.x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        self.x11.XFlush.argtypes = [ctypes.c_void_p]
        self.x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.dpy = self.x11.XOpenDisplay(None)

    def fokus(self, okno):
        gi.require_version("GdkX11", "4.0")
        from gi.repository import GdkX11  # noqa: F401
        self.x11.XSetInputFocus(self.dpy, okno.get_surface().get_xid(), 1, 0)
        self.x11.XFlush(self.dpy)

    def vpisi(self, besedilo):
        for znak in besedilo:
            koda = self.x11.XKeysymToKeycode(self.dpy, self.x11.XStringToKeysym(znak.encode()))
            self.xtst.XTestFakeKeyEvent(self.dpy, koda, 1, 0)
            self.xtst.XTestFakeKeyEvent(self.dpy, koda, 0, 0)
            self.x11.XFlush(self.dpy)
            _cakaj(lambda: False, 0.05)

    def zapri(self):
        if self.dpy:
            self.x11.XCloseDisplay(self.dpy)
            self.dpy = None


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "brez zaslona (xvfb-run)")
class SpanjeZivo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapa = tempfile.mkdtemp()
        with open(os.path.join(cls.mapa, "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"doh_enabled": False, "check_default_browser": False}, f)
        cfg = ConfigManager()
        cfg.config_dir, cfg.config_file = cls.mapa, os.path.join(cls.mapa, "settings.json")
        cfg.settings = cfg.load_settings()
        cls.streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Streznik)
        threading.Thread(target=cls.streznik.serve_forever, daemon=True).start()
        cls.koren = "http://127.0.0.1:%d" % cls.streznik.server_address[1]
        cls.okno = Gtk.Window()
        cls.okno.set_default_size(1100, 760)
        cls.s = VdelaniSplet(Gtk, Gdk, Gio, GLib, WebKit, KOREN, lambda: "sl", None, stars=cls.okno, config=cfg)
        cls.okno.set_child(cls.s.gradnik)
        cls.okno.present()
        cls.sp = cls.s.spanje
        cls.meritve = {}

    @classmethod
    def tearDownClass(cls):
        print("\n[meritve spanja]", json.dumps(cls.meritve, ensure_ascii=False))
        for z in list(cls.s.zavihki):
            try:
                cls.s.zapri_zavihek(z["pogled"])
            except Exception:  # noqa: BLE001
                pass
        cls.s.koncaj()
        cls.okno.destroy()
        cls.streznik.shutdown()
        _cakaj(lambda: False, 0.5)

    def _odpri(self, pot, nov=True):
        p = self.s.nov_zavihek(self.koren + pot) if nov else self.s.trenutni()
        if not nov:
            p.load_uri(self.koren + pot)
        self.assertTrue(_cakaj(lambda: not p.is_loading() and (p.get_uri() or "").startswith(self.koren + pot), 15))
        return p

    def _z(self, p):
        return self.s._zavihek(p)

    def test_1_uspan_zavihek_sprosti_pomnilnik_in_se_zbudi_na_istem_mestu(self):
        a = self._odpri("/tezka.html")
        _js(a, "window.scrollTo(0, 2345); 1")
        self.assertEqual(_js(a, "window.scrollY"), 2345)
        self._odpri("/obrazec.html")                    # tezka gre v ozadje
        za = self._z(a)
        ident = za["spanje"]["id"]
        # Sonda (40 ms racunanja v pogledu) najde proces zavihka v ozadju.
        self.assertTrue(_cakaj(lambda: self.sp.nadzor.pid_of(ident) > 0, 20), "sonda ni nasla procesa")
        pid = self.sp.nadzor.pid_of(ident)
        pss_zavihka = pss_mb(pid)
        self.assertGreater(pss_zavihka, 150)            # res proces tezke strani (2 milijona nizov)
        pred = _vsota_pss()
        self.assertTrue(self.sp.uspavaj(za, "preizkus"))
        self.assertTrue(_cakaj(lambda: not os.path.exists("/proc/%d" % pid), 5))   # pravi proces je koncan
        _cakaj(lambda: False, 1.0)
        po = _vsota_pss()
        self.meritve.update(pss_zavihka_mib=round(pss_zavihka), vsota_pred_mib=round(pred), vsota_po_mib=round(po),
                            sprosceno_mib=round(pred - po))
        self.assertGreater(pred - po, 150)
        self.assertEqual(a.get_uri() or "", "")                                     # WebKit pozabi naslov ...
        self.assertEqual(splet_spanje.naslov_pogleda(a), self.koren + "/tezka.html")   # ... mi ne
        self.assertEqual(za["naslov"].get_text(), "Tezka")
        self.assertTrue(za["vrstica"].has_css_class("splet-tab-spi"))
        self.assertIn("Spi", za["vrstica"].get_tooltip_text())
        vrstica = next(v for v in self.sp.vrstice() if v["id"] == ident)
        self.assertTrue(vrstica["sleeping"])
        # Uspan zavihek: brez procesa - CPU in pomnilnik (zdaj, povprecje, vrh) in niti so »—« (od 1.0.127 sest stolpcev).
        self.assertIn('Tezka</td>' + '<td>—</td>' * 7 + '<td>spi</td>', self.sp.stran_procesov())
        # Ctrl+Shift+T in seja ob zaprtju vidita naslov uspanega zavihka.
        self.s._zapomni_zaprt(a)
        self.assertEqual(self.s._zaprti[-1], self.koren + "/tezka.html")
        t0 = time.monotonic()
        self.s.izberi(a)
        self.assertTrue(_cakaj(lambda: a.get_uri() == self.koren + "/tezka.html" and not a.is_loading(), 15))
        self.assertTrue(_cakaj(lambda: _js(a, "window.scrollY") == 2345, 5))
        self.meritve["zbujanje_s"] = round(time.monotonic() - t0, 2)
        self.assertFalse(za["vrstica"].has_css_class("splet-tab-spi"))
        self.assertFalse(za["spanje"]["spi"])
        # Cena nadzora (vsaki 2 s): branje /proc za vse spletne procese in vzorec vseh zavihkov.
        sonda = self.sp._sondiraj
        self.sp._sondiraj = lambda *_a: None
        try:
            t = time.perf_counter()
            for _ in range(50):
                self.sp._nadzor(self.s)
            self.meritve["nadzor_ms"] = round((time.perf_counter() - t) * 1000 / 50, 2)
        finally:
            self.sp._sondiraj = sonda
        self.assertLess(self.meritve["nadzor_ms"], 20)

    def test_2_zasciteni_zavihki_ne_zaspijo(self):
        tipke = _Tipkovnica()
        try:
            o = self._odpri("/obrazec.html")
            o.grab_focus()
            tipke.fokus(self.okno)
            _js(o, "document.getElementById('i').focus(); 1")
            tipke.vpisi("abc")
            self.assertTrue(_cakaj(lambda: _js(o, "document.getElementById('i').value") == "abc", 5))
        finally:
            tipke.zapri()
        zo = self._z(o)
        self.assertTrue(_cakaj(lambda: any(u for u, _m in zo["spanje"]["okvirji"].values()), 5))
        self.assertFalse(self.sp.uspavaj(zo, "aktiven"))          # aktiven (viden) zavihek nikoli
        p = self._odpri("/post.html")
        _js(p, "document.getElementById('b').click(); 1")
        self.assertTrue(_cakaj(lambda: p.get_title() == "Rezultat", 10))
        posti = len(_Streznik.posti)
        m = self._odpri("/zvok.html")
        _js(m, "document.getElementById('a').play(); 1")          # kot klik »Predvajaj«
        self.assertTrue(_cakaj(lambda: any(mm for _u, mm in self._z(m)["spanje"]["okvirji"].values()), 8))
        self.assertIn("media", splet_spanje.razlogi_zascite(self.sp._stanje(self._z(m))))   # med predvajanjem
        self._odpri("/obrazec.html")                               # vsi trije gredo v ozadje
        self.assertIn("form", splet_spanje.razlogi_zascite(self.sp._stanje(zo)))
        self.assertFalse(self.sp.uspavaj(zo, "preizkus"))
        self.assertIn("post", splet_spanje.razlogi_zascite(self.sp._stanje(self._z(p))))
        self.assertFalse(self.sp.uspavaj(self._z(p), "preizkus"))
        # Tiho (utisano) predvajanje WebKit 6.0 v skriti strani ustavi sam (izmerjeno 18. 10. 2026); ko je ustavljeno,
        # zavihek sme zaspati. Slisen zvok tece naprej in ga varuje is_playing_audio.
        self.assertTrue(_cakaj(lambda: _js(m, "document.getElementById('a').paused") is True, 8))
        self.assertTrue(_cakaj(lambda: "media" not in splet_spanje.razlogi_zascite(self.sp._stanje(self._z(m))), 8))
        self.meritve["tiho_predvajanje_v_ozadju_ustavljeno"] = True
        self.assertEqual(len(_Streznik.posti), posti)              # obrazec ni bil poslan znova
        # Povezano okno (window.open) deli proces z odpiralcem: ne zaspi nobeden, dokler sta odprta oba.
        odp = self._odpri("/tezka.html")
        okno = self.s.nov_zavihek(povezan=odp)
        okno.load_uri(self.koren + "/obrazec.html")
        self.assertTrue(_cakaj(lambda: not okno.is_loading() and okno.get_title() == "Obrazec", 10))
        zadnji = self._odpri("/obrazec.html")
        self.assertIn("linked", splet_spanje.razlogi_zascite(self.sp._stanje(self._z(odp))))
        self.assertFalse(self.sp.uspavaj(self._z(odp), "preizkus"))
        self.assertFalse(self.sp.uspavaj(self._z(okno), "preizkus"))
        self.s.zapri_zavihek(okno)            # izbere sosednji zavihek (odpiralca) - nazaj na zadnjega
        self.s.izberi(zadnji)
        self.assertEqual(splet_spanje.razlogi_zascite(self.sp._stanje(self._z(odp))), [])
        self.assertTrue(self.sp.uspavaj(self._z(odp), "preizkus"))     # okno zaprto: odpiralec sme
        stran = self.sp.stran_procesov()
        self.assertIn("urejen obrazec", stran)
        self.assertIn("poslan obrazec", stran)

    def test_3_procesi_samo_za_uporabnika(self):
        zrtev = self._odpri("/obrazec.html")
        ident = self._z(zrtev)["spanje"]["id"]
        # Napadalec pozna celo trenutni kljuc - shema je zanj vseeno nedosegljiva.
        _Streznik.napad = "safeer://procesi?zapri=%s&k=%s" % (ident, self.sp._kljuc)
        n = self._odpri("/napad.html")
        _cakaj(lambda: False, 2.0)
        self.assertIsNotNone(self._z(zrtev))                       # zavihek ni zaprt
        self.assertTrue((n.get_uri() or "").startswith(self.koren))
        self.assertTrue(self.sp.odpri_procese("procesi"))          # uporabnik vpise »procesi«
        self.assertTrue(_cakaj(lambda: n.get_title() == "Safeer · Procesi" and not n.is_loading(), 10))
        self.assertEqual(n.get_uri(), "safeer://procesi")
        povezava = _js(n, "(document.querySelector('a[href*=\"spi=%s\"]') || {}).href || ''" % ident)
        self.assertIn("&k=", povezava)
        _js(n, "document.querySelector('a[href*=\"spi=%s\"]').click(); 1" % ident)
        self.assertTrue(_cakaj(lambda: self._z(zrtev)["spanje"]["spi"], 10))
        # Ista povezava se enkrat (Nazaj, osvezitev): kljuc je porabljen, nic se ne zgodi.
        self.s.izberi(zrtev)
        self.assertTrue(_cakaj(lambda: not self._z(zrtev)["spanje"]["spi"] and not zrtev.is_loading(), 10))
        self.s.izberi(n)
        n.load_uri(povezava)
        _cakaj(lambda: not n.is_loading(), 5)
        _cakaj(lambda: False, 1.0)
        self.assertFalse(self._z(zrtev)["spanje"]["spi"])
        # Meni Spleta: »Procesi« pred nastavitvami odpre stran v novem zavihku.
        meni = self.s._meni()
        dejanja = [meni.get_item_attribute_value(i, "action").get_string() for i in range(meni.get_n_items())]
        self.assertLess(dejanja.index("splet.procesi"), dejanja.index("splet.nastavitve"))
        self.assertEqual(meni.get_item_attribute_value(dejanja.index("splet.procesi"), "label").get_string(), "Procesi")
        n_pred = len(self.s.zavihki)
        self.assertTrue(self.s.gradnik.activate_action("splet.procesi", None))
        self.assertEqual(len(self.s.zavihki), n_pred + 1)
        nov = self.s.trenutni()
        self.assertTrue(_cakaj(lambda: nov.get_uri() == "safeer://procesi" and not nov.is_loading(), 10))

    def test_4_omrezni_proces_po_obnovi_obdrzi_piskotke_seje(self):
        from unittest import mock
        from core import splet_spanje
        zaplata = mock.patch.object(splet_spanje, "RECIKLIRANJE_OMREZNEGA", True)   # v 1.0.129 izklopljeno
        zaplata.start()
        self.addCleanup(zaplata.stop)
        p = self._odpri("/piskotek")
        piskotki = os.path.join(self.s.config.config_dir, "cookies.sqlite")
        self.assertTrue(_cakaj(lambda: bool(omrezni_procesi_shrambe(piskotki)), 5))
        pid = omrezni_procesi_shrambe(piskotki)[0]
        pred = pss_mb(pid)
        izid = []
        self.sp.recikliraj_omrezni(pid, pred, ob_koncu=izid.append)
        self.assertTrue(_cakaj(lambda: bool(izid), 10))
        self.assertFalse(os.path.exists("/proc/%d" % pid))
        self.assertGreaterEqual(izid[0], 1)                        # vsaj piskotek »seja« (brez roka)
        p.load_uri(self.koren + "/preveri")
        self.assertTrue(_cakaj(lambda: not p.is_loading() and p.get_title() not in ("", "Piskotek"), 10))
        self.assertIn("seja=1", p.get_title())
        self.assertIn("trajen=1", p.get_title())
        novi = omrezni_procesi_shrambe(piskotki)
        self.assertTrue(novi and novi[0] != pid)
        self.meritve.update(omrezni_pred_mib=round(pred), omrezni_nov_mib=round(pss_mb(novi[0])))

    def test_5_stran_pokaze_ves_program_s_povprecjem_in_vrhom(self):
        """1.0.127: poleg zavihkov se glavni, omrezni in drugi procesi programa, povprecje in vrh zadnje ure (vzorci
        ure storitev, tu dva rocno) in strosek vzorca."""
        from core import poraba_zgodovina
        self._odpri("/tezka.html")
        self._odpri("/obrazec.html")                    # tezka gre v ozadje: sonda najde njen proces
        # Zavihki iz prejsnjih preizkusov tudi cakajo na sondo (ena na 2 s): pocakamo na katerikoli zavihek s procesom.
        self.assertTrue(_cakaj(lambda: any(v["pid"] for v in self.sp.vrstice()), 40), "sonda ni nasla procesa")
        z = poraba_zgodovina.skupna()
        z.vzorci()
        _cakaj(lambda: False, 1.0)
        n = z.vzorci()
        self.meritve.update(vzorec_ms=round(z.zadnji_s * 1000, 2), vzorec_cpu_ms=round(z.zadnji_cpu_s * 1000, 2),
                            procesov_v_vzorcu=n)
        # Vzorec vseh procesov drevesa je poceni (stat + statm): meri se cas CPU, ne ure - v polnem naboru na 2 jedrih je
        # cas ure stel tudi cakanje na jedro (60 ms). Drevo preizkusa ima tudi procese prejsnjih preizkusov (224 namesto
        # 108 samo s tem), zato meja na proces: 0,5 ms, tj. 50 ms za Splet s 17 zavihki (108 procesov s peskovniki).
        self.assertGreater(n, 1)
        self.assertLess(z.zadnji_cpu_s, 0.0005 * n)
        _cakaj(lambda: False, 3.5)                      # nadzor zavihkov (2 s) ima svez vzorec procesa
        stran = self.sp.stran_procesov()
        self.assertIn("vsi procesi", stran)
        self.assertIn("omrežni proces", stran)
        self.assertIn("glavni proces", stran)
        self.assertIn("spletni procesi zavihkov", stran)
        self.assertIn("Povprečje in vrh veljata za zadnjo uro", stran)
        naslov = next(v["title"] for v in self.sp.vrstice() if v["pid"])
        vrstica = stran.split(">%s</td>" % naslov, 1)[1].split("</tr>", 1)[0]
        celice = re.findall(r"<td[^>]*>([^<]*)</td>", vrstica)
        self.assertNotEqual(celice[1], "—", vrstica)    # povprecje CPU iz zgodovine
        self.assertTrue(celice[4].endswith("MB") or celice[4].endswith("GB"), vrstica)   # povprecje pomnilnika
        self.assertTrue(celice[5].endswith("MB") or celice[5].endswith("GB"), vrstica)   # vrh pomnilnika


if __name__ == "__main__":
    unittest.main()
