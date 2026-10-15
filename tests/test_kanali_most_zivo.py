"""Vgrajeni kanali Sporocil skozi PRAVO stran (assets/os/index.html?razdelek=sporocila, os.js) in pravi most Safeer OS
(safeer_os.SafeerOS._nov_pogled, _na_sporocilo, _obdelaj_klic) v WebKitGTK 6.0 (Xvfb) - okno razdelka Sporocila.

Zivi preizkus 15. 10. 2026 (testni PC): klik »Dodaj v Sporocila« (WhatsApp) v carovniku ni naredil nicesar - klic
kanalDodaj je tekel v niti ozadja, ki je ustvarjala gradnike GTK in pogled WebKit (dovoljeno samo v glavni niti), in
odgovora ni bilo. Preizkus klikne gumb v strani in caka na viden izid (kanal na seznamu in v nastavitvah)."""
import json
import os
import tempfile
import threading
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOM = tempfile.mkdtemp(prefix="safeer-kanali-most-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_DOM, ".config")
os.environ["XDG_CACHE_HOME"] = os.path.join(_DOM, ".cache")
os.environ["XDG_DATA_HOME"] = os.path.join(_DOM, ".local", "share")
os.makedirs(os.path.join(_DOM, ".cache"), exist_ok=True)

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gdk, Gio, GLib, Gtk, WebKit  # noqa: E402

Gtk.init()

import safeer_os as so  # noqa: E402
from core import config as _config  # noqa: E402
from core import spletni_klepeti  # noqa: E402
from core.sporocila import ponudniki as _ponudniki  # noqa: E402
from core.sporocila import vklop  # noqa: E402

#: Metode pravega Safeer OS, skozi katere gre klic strani (most, razvrscanje v glavno nit ali ozadje, kanali).
PRAVE = ("_nov_pogled", "_na_sporocilo", "_obdelaj_klic", "_odgovori", "_js", "_kanali_klic", "_kanali",
         "_kanal_pokazi", "_prekrivanje_kanalov", "_kanali_dogodek", "_config_spleta", "_dogodek")


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
    """Vse, cesar ta preizkus ne potrebuje (Datoteke, Link, predvajalnik ...): klic vrne None, atribut je spet _Nic."""

    def __call__(self, *_a, **_k):
        return None

    def __getattr__(self, _ime):
        return _Nic()

    def __iter__(self):
        return iter(())


class _Sporocila(_Nic):
    ponudniki = staticmethod(lambda jezik="sl": _ponudniki.za_vmesnik(jezik))
    seznam = staticmethod(lambda *a: {"skupine": [], "kanali": []})


def _os_razred():
    imena = {ime: so.SafeerOS.__dict__[ime] for ime in PRAVE}

    class Os:
        posnetek = ""

        def __init__(self, splet):
            self.pogledi, self._prekrivanja, self._os_kontekst = [], {}, None
            self._kanali_sporocil, self._nastavitve_spleta = None, splet.config
            self.splet, self.sporocila = splet, _Sporocila()
            self.niti_gtk = []

        def __getattr__(self, ime):
            return _Nic()

        def _na_politiko(self, *_a):
            return False

        def _zacetek(self):
            return {"jezik": "sl", "sporocila": True, "platforma": "linux", "mape": []}

        def _jedro_spleta(self):
            if threading.current_thread() is not threading.main_thread():
                self.niti_gtk.append("_jedro_spleta")
            return self.splet

        def _osvezi_kuverto(self):
            return None

        def _katalog_most(self):
            class _K:
                @staticmethod
                def pozna(_m):
                    return False
            return _K()
    for ime, f in imena.items():
        setattr(Os, ime, f)
    return Os


class KanaliSkoziStran(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(_config.CONFIG_DIR, exist_ok=True)
        c = _config.ConfigManager()
        c.set("doh_enabled", False)
        c.set("secure_proxy_mode", "custom")
        c.set("secure_proxy_url", "http://127.0.0.1:9")     # brez omrezja: zaprta vrata
        c.set("easylist_enabled", False)
        from core.os_splet import VdelaniSplet
        cls.splet = VdelaniSplet(Gtk, Gdk, Gio, GLib, WebKit, KOREN, lambda: "sl", None, prvi_zavihek=False, config=c)

    def setUp(self):
        from unittest import mock
        p = mock.patch.object(vklop, "PRIVZETA_POT", os.path.join(_DOM, "sporocila.sqlite3"))
        p.start()
        self.addCleanup(p.stop)
        vklop.nastavi_sporocila(True)
        self.splet.config.set(spletni_klepeti.Kanali.KLJUC, [])
        self.os = _os_razred()(self.splet)
        self.addCleanup(lambda: self.os._kanali_sporocil and self.os._kanali_sporocil.ustavi_vse())
        self.pogled = self.os._nov_pogled("index.html?razdelek=sporocila&jezik=sl")
        self.okno = Gtk.Window()
        self.okno.set_default_size(1100, 760)
        self.okno.set_child(self.os._prekrivanje_kanalov(self.pogled))
        self.okno.present()
        self.addCleanup(self.okno.destroy)
        self.assertTrue(_cakaj(lambda: self._js("document.body.classList.contains('en-razdelek') && !!window.SafeerOS") is True, 20))
        _cakaj(lambda: False, 1.0)     # zacni(): dogodki gumbov in prvi klici mostu

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

    def test_dodaj_whatsapp_iz_carovnika(self):
        # »Dodaj kanal« -> Aplikacije -> »Dodaj v Sporocila« pri WhatsApp (pravi gumbi strani)
        self._js("document.getElementById('sporocilaDodaj').click(), 1")
        self._js("document.querySelector('#kanalVrstaIzbira [data-vrsta=aplikacije]').click(), 1")
        self.assertTrue(_cakaj(lambda: self._js("document.querySelectorAll('#kanalAplikacijeMreza .aplikacije-vrsta').length")
                               or 0, 10), "katalog v carovniku")
        kliknjen = self._js("""(function () {
            var v = Array.prototype.find.call(document.querySelectorAll('#kanalAplikacijeMreza .aplikacije-vrsta'),
              function (x) { return x.querySelector('.ime') && x.querySelector('.ime').textContent.indexOf('WhatsApp') === 0; });
            var g = v && v.querySelector('button.glavni'); if (!g) return false; g.click(); return true; })()""")
        self.assertTrue(kliknjen, "gumb »Dodaj v Sporocila« pri WhatsApp")
        self.assertTrue(_cakaj(lambda: any(k.get("katalog") == "whatsapp" for k in
                                           self.splet.config.get(spletni_klepeti.Kanali.KLJUC, []) or []), 10),
                        "kanal je shranjen v nastavitvah")
        self.assertTrue(_cakaj(lambda: self._js("!document.getElementById('slojKanal').classList.contains('viden')"), 5),
                        "carovnik se zapre")
        self.assertTrue(_cakaj(lambda: self._js(
            "!!document.querySelector('#sporocilaKanali .kanal-cip.vgrajen[data-kanal=whatsapp]')"), 5),
            "kanal je na seznamu kanalov")
        self.assertTrue(_cakaj(lambda: self._js("!document.getElementById('vgrajenKanal').hidden"), 5), "kanal je odprt")
        self.assertEqual(self.os.niti_gtk, [], "kanali (GTK, WebKit) samo v glavni niti")
        k = self.os._kanali_sporocil
        self.assertTrue(_cakaj(lambda: "whatsapp" in k.zivi and k.plasti, 5), "pogled kanala je nad stranjo")
        plast = next(iter(k.plasti.values()))
        self.assertTrue(plast["sklad"].get_visible())

    def test_neuspeh_pokaze_napako(self):
        # Neveljaven lasten naslov: carovnik ostane odprt z napako (nikoli tisina).
        self._js("document.getElementById('sporocilaDodaj').click(), 1")
        self._js("document.querySelector('#kanalVrstaIzbira [data-vrsta=aplikacije]').click(), 1")
        self.assertTrue(_cakaj(lambda: self._js("!!document.querySelector('#kanalAplikacijeMreza .svoj-url')"), 10))
        self._js("document.querySelector('#kanalAplikacijeMreza .svoj-url').value = 'javascript:alert(1)', 1")
        self._js("document.querySelector('#kanalAplikacijeMreza [data-svoj]').click(), 1")
        self.assertTrue(_cakaj(lambda: self._js("!document.getElementById('kanalNapaka').hidden"), 5), "napaka je vidna")
        self.assertTrue(self._js("document.getElementById('kanalNapaka').textContent.length > 0"))
        self.assertEqual(self.splet.config.get(spletni_klepeti.Kanali.KLJUC, []), [])


if __name__ == "__main__":
    unittest.main()
