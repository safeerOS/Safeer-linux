"""Stranska vrstica, iskalna lupa in Nastavitve skozi PRAVO stran (assets/os/index.html, os.js) in pravi most Safeer OS
v WebKitGTK 6.0 (Xvfb) - lastnik, 19. 10. 2026: »stranska vrstica in iskalna lupa morata ostati izven poti, a preprosto
dosegljivi«, »Nastavitve morajo odrazati celotne nastavitve operacijskega sistema«, Safeer Agent v Nastavitvah."""
import http.server
import json
import os
import tempfile
import threading
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOM = tempfile.mkdtemp(prefix="safeer-vrstica-zivo-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_DOM, ".config")
os.environ["XDG_CACHE_HOME"] = os.path.join(_DOM, ".cache")
os.environ["XDG_DATA_HOME"] = os.path.join(_DOM, ".local", "share")
os.makedirs(os.path.join(_DOM, ".cache"), exist_ok=True)

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import GLib, Gtk  # noqa: E402

Gtk.init()

import safeer_os as so  # noqa: E402
from core.agent import nastavitve as agent_nastavitve  # noqa: E402

PRAVE = ("_nov_pogled", "_na_sporocilo", "_obdelaj_klic", "_odgovori", "_js", "_dogodek", "_agent")


def _cakaj(pogoj, cas=10.0):
    kontekst = GLib.MainContext.default()
    rok = time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.005)
    return pogoj()


class _Nic:
    def __call__(self, *_a, **_k):
        return None

    def __getattr__(self, _ime):
        return _Nic()

    def __iter__(self):
        return iter(())


RAZPOLOZLJIVO = {"moduli": ["display", "keyboard", "mouse", "sound", "info"], "orodja": ["posodobitve", "uporabniki"],
                 "plosce": [], "imena": {}}


def _os_razred():
    imena = {ime: so.SafeerOS.__dict__[ime] for ime in PRAVE}

    class Os:
        posnetek = ""

        def __init__(self):
            self.pogledi, self._os_kontekst, self.razdelki, self.dogodki = [], None, [], []

        def __getattr__(self, ime):
            return _Nic()

        def _na_politiko(self, *_a):
            return False

        def _zacetek(self):
            return {"jezik": "sl", "sporocila": True, "platforma": "linux", "mape": [], "razlicica": "1.0.127",
                    "razpolozljivo": RAZPOLOZLJIVO, "agent": {"na_voljo": False}}

        def _odpri_razdelek(self, razdelek):
            self.razdelki.append(razdelek)
            return True

        def _katalog_most(self):
            class _K:
                @staticmethod
                def pozna(_m):
                    return False
            return _K()
    for ime, f in imena.items():
        setattr(Os, ime, f)
    return Os


class _Stran(unittest.TestCase):
    STRAN = "index.html"
    SIRINA, VISINA = 1260, 860      # xvfb-run: zaslon 1280 x 1024; meja traku je 1200 px

    def setUp(self):
        self._agent_mapa = tempfile.mkdtemp(prefix="safeer-agent-", dir=_DOM)
        self._prej = agent_nastavitve.MAPA
        agent_nastavitve.MAPA = self._agent_mapa
        self.addCleanup(setattr, agent_nastavitve, "MAPA", self._prej)
        self.os = _os_razred()()
        self.odpri(self.SIRINA, self.VISINA)

    def odpri(self, sirina, visina):
        self.pogled = self.os._nov_pogled(self.STRAN)
        self.okno = Gtk.Window()
        self.okno.set_default_size(sirina, visina)
        self.okno.set_child(self.pogled)
        self.okno.present()
        self.addCleanup(self.okno.destroy)
        self.assertTrue(_cakaj(lambda: self._js("!!window.SafeerOS && !!document.getElementById('gumbVrstica')") is True, 20))
        self.assertTrue(_cakaj(lambda: self._js("innerWidth") == sirina, 10), self._js("innerWidth"))
        # Odgovor »zacetek« je prisel (besedila prevedena).
        self.assertTrue(_cakaj(lambda: self._js("document.querySelector('[data-razdelek=nastavitve] span').textContent") == "Nastavitve", 10))

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

    def tipka(self, kljuc, **mod):
        self._js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown', %s)), 1"
                 % json.dumps(dict({"key": kljuc, "bubbles": True, "cancelable": True}, **mod)))


class StranskaVrstica(_Stran):
    def _sirina(self, idr):
        return self._js("Math.round(document.getElementById(%s).getBoundingClientRect().width)" % json.dumps(idr))

    def sirina(self, idr, pricakovana):
        """Sirina po koncu prehoda (os.css: grid-template-columns .18s, ce zmanjsano gibanje ni vklopljeno)."""
        _cakaj(lambda: self._sirina(idr) == pricakovana, 2)
        return self._sirina(idr)

    def _levo(self, idr):
        return self._js("Math.round(document.getElementById(%s).getBoundingClientRect().left)" % json.dumps(idr))

    def test_siroko_okno_razsirjena_izbira_ostane(self):
        self._js("localStorage.clear(), 1")
        self.odpri(self.SIRINA, self.VISINA)      # shramba strani je skupna vsem preizkusom v procesu
        self.assertGreater(self._sirina("stranska"), 200)
        self.assertEqual(self._js("document.getElementById('gumbVrstica').getAttribute('aria-expanded')"), "true")
        self._js("document.getElementById('gumbVrstica').click(), 1")
        self.assertEqual(self.sirina("stranska", 76), 76, "trak z ikonami ostane viden")
        self.assertEqual(self._js("localStorage.getItem('safeer_vrstica')"), "skrcena")
        # Izbrani razdelek ostane oznacen; ime je v namigu in dostopnem imenu (napis je skrit).
        self.assertEqual(self._js("document.querySelector('#meni button.izbran').getAttribute('aria-label')"), "Domov")
        self.assertEqual(self._js("document.querySelector('#meni button.izbran').title"), "Domov")
        self.assertEqual(self._js("getComputedStyle(document.querySelector('#meni button span')).display"), "none")
        self.assertEqual(self._js("document.getElementById('gumbVrstica').getAttribute('aria-expanded')"), "false")
        # Po ponovnem zagonu (nova stran) ostane skrcena; Ctrl+B jo razsiri in izbiro pozabi (samodejno).
        self.odpri(self.SIRINA, self.VISINA)
        self.assertEqual(self.sirina("stranska", 76), 76)
        self.tipka("b", ctrlKey=True)
        self.assertEqual(self.sirina("stranska", 250), 250)
        self.assertEqual(self._js("localStorage.getItem('safeer_vrstica')"), "")
        self.assertEqual(self._js("document.activeElement.getAttribute('data-razdelek')"), "domov", "fokus na izbranem razdelku")

    def test_prej_skrita_postane_skrcena(self):
        self._js("localStorage.clear(), localStorage.setItem('safeer_vrstica_skrita', '1'), 1")
        self.odpri(self.SIRINA, self.VISINA)
        self.assertEqual(self.sirina("stranska", 76), 76)
        self.assertIsNone(self._js("localStorage.getItem('safeer_vrstica_skrita')"))
        self.assertFalse(self._js("!!document.getElementById('rocajVrstice') || !!document.getElementById('gumbSkrijVrstico')"))

    def test_ozko_okno_trak_in_plavajoca_vrstica(self):
        self._js("localStorage.clear(), 1")
        self.odpri(900, 700)
        self.assertEqual(self.sirina("stranska", 76), 76, "v ozkem oknu samodejno trak")
        levo = self._levo("glavno")
        self._js("document.getElementById('gumbVrstica').click(), 1")
        self.assertTrue(self._js("document.body.classList.contains('vrstica-plava')"))
        self.assertEqual(self.sirina("stranska", 280), 280)
        self.assertEqual(self._levo("glavno"), levo, "vsebina se ne premakne - vrstica plava nad njo")
        self.assertEqual(self._js("localStorage.getItem('safeer_vrstica')"), "", "zacasno - nic se ne shrani")
        # Escape zapre in vrne fokus gumbu.
        self.tipka("Escape")
        self.assertFalse(self._js("document.body.classList.contains('vrstica-plava')"))
        self.assertEqual(self._js("document.activeElement.id"), "gumbVrstica")
        # Izbira razdelka zapre plavajoco vrstico.
        self._js("document.getElementById('gumbVrstica').click(), document.querySelector('[data-razdelek=zapiski]').click(), 1")
        self.assertFalse(self._js("document.body.classList.contains('vrstica-plava')"))
        self.assertTrue(self._js("document.getElementById('r-zapiski').classList.contains('viden')"))
        # Klik mimo zapre, a se na vsebini ne izvede.
        self._js("document.getElementById('gumbVrstica').click(), 1")
        self._js("""(function () { window.__klik = 0; var c = document.getElementById('vsebina');
            c.addEventListener('click', function () { window.__klik++; });
            c.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true }));
            c.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); return 1; })()""")
        self.assertFalse(self._js("document.body.classList.contains('vrstica-plava')"))
        self.assertEqual(self._js("window.__klik"), 0)

    def test_lupa_zlozena_tipkanje_in_ctrl_k(self):
        self.assertFalse(self._js("document.getElementById('iskanjeLupa').classList.contains('razsirjena')"))
        ozka = self._sirina("iskanjeLupa")
        self.assertLessEqual(ozka, 380)
        self.assertEqual(self._js("document.getElementById('iskanje').placeholder"), "Išči …")
        # Tipkanje kjerkoli (fokus ni v polju) odpre lupo s tem znakom.
        self._js("document.activeElement.blur(), document.body.focus(), 1")
        self.tipka("w")
        self.assertEqual(self._js("document.getElementById('iskanje').value"), "w")
        self.assertEqual(self._js("document.activeElement.id"), "iskanje")
        self.assertTrue(self._js("document.getElementById('iskanjeLupa').classList.contains('razsirjena')"))
        self.assertTrue(_cakaj(lambda: (self._sirina("iskanjeLupa") or 0) > ozka + 100, 3), self._sirina("iskanjeLupa"))
        # Ctrl+T ali Alt+crka ne gresta v iskanje.
        self._js("(function(){var v=document.getElementById('iskanje'); v.value=''; v.dispatchEvent(new Event('input')); v.blur(); return 1;})()")
        self.tipka("t", ctrlKey=True)
        self.tipka("x", altKey=True)
        self.assertEqual(self._js("document.getElementById('iskanje').value"), "")
        self.assertFalse(self._js("document.getElementById('iskanjeLupa').classList.contains('razsirjena')"))
        # Ctrl+K: fokus v lupo od koderkoli.
        self.tipka("k", ctrlKey=True)
        self.assertEqual(self._js("document.activeElement.id"), "iskanje")


class OknoNastavitev(_Stran):
    STRAN = "index.html?razdelek=nastavitve&jezik=sl"
    SIRINA, VISINA = 1100, 760

    def setUp(self):
        super().setUp()
        self.assertTrue(_cakaj(lambda: self._js("document.querySelectorAll('#skupineNastavitev .nastavitev').length") == 7, 10))

    def _vidne(self):
        return self._js("""Array.prototype.filter.call(document.querySelectorAll('#r-nastavitve .nastavitev, #r-nastavitve .stikalo'),
            function (e) { return e.offsetParent !== null; }).map(function (e) { return e.textContent.trim(); })""")

    def test_iskanje_po_nastavitvah(self):
        self._js("(function(){var v=document.getElementById('nastavitveIskanje'); v.value='tipkovnica'; v.dispatchEvent(new Event('input')); return 1;})()")
        self.assertEqual(self._vidne(), ["Tipkovnica"])
        # Tudi po anglesko (ime vnosa v vseh jezikih: angleski del je v kljucnih besedah).
        self._js("(function(){var v=document.getElementById('nastavitveIskanje'); v.value='display'; v.dispatchEvent(new Event('input')); return 1;})()")
        self.assertEqual(self._vidne(), ["Zasloni"])
        # Brez zadetka: sporocilo; Escape pocisti in vrne vse.
        self._js("(function(){var v=document.getElementById('nastavitveIskanje'); v.focus(); v.value='qqzz'; v.dispatchEvent(new Event('input')); return 1;})()")
        self.assertEqual(self._vidne(), [])
        self.assertEqual(self._js("document.getElementById('nastavitveNiZadetkov').hidden"), False)
        self.tipka("Escape")
        self.assertEqual(self._js("document.getElementById('nastavitveIskanje').value"), "")
        self.assertGreater(len(self._vidne()), 7)
        # Tipkanje kjerkoli v oknu Nastavitve gre v iskanje Nastavitev (prej v skrito lupo glavnega okna).
        self._js("document.activeElement.blur(), 1")
        self.tipka("z")
        self.assertEqual(self._js("document.activeElement.id"), "nastavitveIskanje")
        self.assertEqual(self._js("document.getElementById('nastavitveIskanje').value"), "z")

    def test_enter_v_iskanju_odpre_ne_preklopi(self):
        """Enter v iskanju Nastavitev odpre najdeno nastavitev, stikala pa ne preklopi - samo fokus nanj (pregled 19. 10.
        2026: »wifi« + Enter je izklopil Wi-Fi v hitrih nastavitvah, »beta« + Enter vklopil beta kanal). Najprej vnos, ki
        ustreza sam: »zvok« je Zvok, ne prvi vnos skupine »Zaslon in zvok« (Zasloni)."""
        self._js("(function(){var v=document.getElementById('nastavitveIskanje'); v.focus(); v.value='beta'; v.dispatchEvent(new Event('input')); return 1;})()")
        self.tipka("Enter")
        self.assertEqual(self._js("document.getElementById('stikaloBeta').getAttribute('aria-checked')"), "false")
        self.assertEqual(self._js("document.activeElement.id"), "stikaloBeta")
        self._js("""(function () { window.__kliknjeni = [];
            document.addEventListener('click', function (e) { var b = e.target.closest && e.target.closest('.nastavitev');
                if (b) { window.__kliknjeni.push(b.textContent.trim()); e.stopPropagation(); e.preventDefault(); } }, true);
            var v = document.getElementById('nastavitveIskanje'); v.focus(); v.value = 'zvok'; v.dispatchEvent(new Event('input'));
            return 1; })()""")
        self.assertIn("Zasloni", self._vidne(), "skupina ustreza po naslovu - ostane cela")
        self.tipka("Enter")
        self.assertEqual(self._js("window.__kliknjeni"), ["Zvok"])

    def test_safeer_agent(self):
        self.assertTrue(_cakaj(lambda: self._js("document.getElementById('agentStanje').textContent")
                               == "Ni nastavljen – vpiši naslov modela spodaj.", 5))
        # Ne-http(s) se zavrne z jasnim razlogom; nic se ne shrani.
        self._js("document.getElementById('agentNaslovVnos').value = 'ftp://192.0.2.7', document.getElementById('agentShrani').click(), 1")
        self.assertTrue(_cakaj(lambda: self._js("document.getElementById('agentNapaka').hidden") is False, 5))
        self.assertEqual(self._js("document.getElementById('agentNapaka').textContent"), "Naslov se mora začeti s http:// ali https://.")
        self.assertFalse(os.path.exists(os.path.join(self._agent_mapa, "naslov")))

        class Rokovalnik(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                ok = self.path == "/v1/models"
                self.send_response(200 if ok else 404)
                self.end_headers()
                if ok:
                    self.wfile.write(b'{"data": [{"id": "gemma-3-4b-it.gguf"}]}')

            def log_message(self, *_a):
                pass
        streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Rokovalnik)
        threading.Thread(target=streznik.serve_forever, daemon=True).start()
        self.addCleanup(streznik.server_close)
        self.addCleanup(streznik.shutdown)
        naslov = "http://127.0.0.1:%d" % streznik.server_address[1]
        self._js("document.getElementById('agentNaslovVnos').value = %s, document.getElementById('agentShrani').click(), 1" % json.dumps(naslov))
        self.assertTrue(_cakaj(lambda: self._js("document.getElementById('agentStanje').textContent") == "Dosegljiv · gemma-3-4b-it.gguf", 10),
                        self._js("document.getElementById('agentStanje').textContent"))
        with open(os.path.join(self._agent_mapa, "naslov"), encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), naslov)
        # Lupa ve, da je agent na voljo (dogodek »agent«): bliznjica Ctrl+Enter je med bliznjicami.
        self.assertTrue(_cakaj(lambda: "Ctrl+Enter" in (self._js("document.getElementById('bliznjice').textContent") or ""), 5))
        # Izklop: stanje pove »Izklopljen«, naslov ostane.
        self._js("document.getElementById('stikaloAgent').click(), 1")
        self.assertTrue(_cakaj(lambda: self._js("document.getElementById('agentStanje').textContent") == "Izklopljen", 5))
        self.assertTrue(os.path.exists(os.path.join(self._agent_mapa, "izklopljen")))
        self.assertNotIn("Ctrl+Enter", self._js("document.getElementById('bliznjice').textContent"))
        # Ustavljen streznik: »Model ni dosegljiv.« (nic laznega).
        self._js("document.getElementById('stikaloAgent').click(), 1")
        streznik.shutdown()
        streznik.server_close()
        self._js("document.getElementById('agentPreveri').click(), 1")
        self.assertTrue(_cakaj(lambda: self._js("document.getElementById('agentStanje').textContent") == "Model ni dosegljiv.", 10))


if __name__ == "__main__":
    unittest.main()
