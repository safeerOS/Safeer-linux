"""Okno Nastavitve skozi PRAVO stran (assets/os/index.html?razdelek=nastavitve, os.js) in pravi most Safeer OS
(_nov_pogled, _na_sporocilo, _obdelaj_klic) v WebKitGTK 6.0 (Xvfb).

Popis 3.1 (18. 10. 2026): ploscici Omrezje in Zvok v oknu Nastavitve sta klicali odpriRazdelek, ta pa je na namizju
odprl staro glavno okno Safeer OS. Zdaj sta podstrani istega okna (Nazaj -> Nastavitve). Vodnik ob prvem zagonu,
ki ga je prej pokazalo samo glavno okno, odpre namizje v tem oknu (safeerOsPojdi »vodnik«)."""
import json
import os
import tempfile
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOM = tempfile.mkdtemp(prefix="safeer-nastavitve-zivo-")
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

PRAVE = ("_nov_pogled", "_na_sporocilo", "_obdelaj_klic", "_odgovori", "_js", "_dogodek")


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
    """Vse, cesar ta preizkus ne potrebuje: klic vrne None, atribut je spet _Nic."""

    def __call__(self, *_a, **_k):
        return None

    def __getattr__(self, _ime):
        return _Nic()

    def __iter__(self):
        return iter(())


def _os_razred():
    imena = {ime: so.SafeerOS.__dict__[ime] for ime in PRAVE}

    class Os:
        posnetek = ""

        def __init__(self):
            self.pogledi, self._os_kontekst, self.razdelki = [], None, []

        def __getattr__(self, ime):
            return _Nic()

        def _na_politiko(self, *_a):
            return False

        def _zacetek(self):
            return {"jezik": "sl", "sporocila": True, "platforma": "linux", "mape": [], "razlicica": "0.4.85",
                    "razpolozljivo": {"moduli": ["sound", "display"], "orodja": ["omrezje"]}}

        def _odpri_razdelek(self, razdelek):
            self.razdelki.append(razdelek)      # kar bi stran predala Safeer OS (na namizju: drugo okno)
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


class OknoNastavitev(unittest.TestCase):
    def setUp(self):
        self.os = _os_razred()()
        self.pogled = self.os._nov_pogled("index.html?razdelek=nastavitve&jezik=sl")
        self.okno = Gtk.Window()
        self.okno.set_default_size(1100, 760)
        self.okno.set_child(self.pogled)
        self.okno.present()
        self.addCleanup(self.okno.destroy)
        self.assertTrue(_cakaj(lambda: self._js("document.body.classList.contains('razdelek-nastavitve') && !!window.SafeerOS") is True, 20))
        self.assertTrue(_cakaj(lambda: self._js("!!document.querySelector('#skupineNastavitev .nastavitev')") is True, 10),
                        "ploscice nastavitev sistema")

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

    def _klikni_ploscico(self, ime):
        return self._js("""(function () {
            var b = Array.prototype.find.call(document.querySelectorAll('#skupineNastavitev .nastavitev'),
              function (x) { return x.textContent.trim() === %s; });
            if (!b) return false; b.click(); return true; })()""" % json.dumps(ime))

    def _viden(self, idr):
        return self._js("document.getElementById(%s).classList.contains('viden') && getComputedStyle(document.getElementById(%s)).display !== 'none'"
                        % (json.dumps(idr), json.dumps(idr)))

    def test_omrezje_in_zvok_v_istem_oknu(self):
        self.assertTrue(self._klikni_ploscico("Omrežne povezave"), "ploscica Omrezje")
        self.assertTrue(_cakaj(lambda: self._viden("r-omrezje") is True, 5), "Omrezje v oknu Nastavitve")
        self.assertFalse(self._viden("r-nastavitve"))
        self.assertEqual(self.os.razdelki, [], "nic ne gre Safeer OS (prej: odpriRazdelek -> staro glavno okno)")
        self._js("document.getElementById('gumbOmrezjeNazaj').click(), 1")
        self.assertTrue(_cakaj(lambda: self._viden("r-nastavitve") is True, 5), "Nazaj -> Nastavitve")
        self.assertTrue(self._klikni_ploscico("Zvok"), "ploscica Zvok")
        self.assertTrue(_cakaj(lambda: self._viden("r-zvok") is True, 5), "Zvok v oknu Nastavitve")
        self.assertEqual(self.os.razdelki, [])
        # Drug razdelek (npr. Sporocila) okno se vedno preda Safeer OS - na namizju svoje okno.
        self._js("window.safeerOsPojdi('sporocila'), 1")
        self.assertTrue(_cakaj(lambda: self.os.razdelki == ["sporocila"], 5), self.os.razdelki)

    def test_vodnik_iz_namizja(self):
        self.assertFalse(self._js("document.getElementById('slojVodnik').classList.contains('viden')"))
        self._js("window.safeerOsPojdi('vodnik'), 1")
        self.assertTrue(_cakaj(lambda: self._js("document.getElementById('slojVodnik').classList.contains('viden')") is True, 5))
        self.assertEqual(self._js("document.getElementById('vodnikKorak').textContent"), "Korak 1 od 5")
        # Na prvem koraku ni gumba Nazaj (prej viden zaradi .gumb {display}: klik je vodnik pokvaril - korak -1).
        self.assertEqual(self._js("getComputedStyle(document.getElementById('vodnikNazaj')).display"), "none")
        # Drugi ukaz (namizje znova zagnano) vodnika ne zacne znova pri prvem koraku.
        self._js("document.getElementById('vodnikNaprej').click(), 1")
        self._js("window.safeerOsPojdi('vodnik'), 1")
        self.assertEqual(self._js("document.getElementById('vodnikKorak').textContent"), "Korak 2 od 5")
        self.assertNotEqual(self._js("getComputedStyle(document.getElementById('vodnikNazaj')).display"), "none")
        # Zadnji korak: brez »Preskoci« in »Preskoci vodnik«.
        for _ in range(3):
            self._js("document.getElementById('vodnikNaprej').click(), 1")
        self.assertEqual(self._js("document.getElementById('vodnikKorak').textContent"), "Korak 5 od 5")
        self.assertEqual(self._js("getComputedStyle(document.getElementById('vodnikPreskoci')).display"), "none")
        self.assertEqual(self._js("getComputedStyle(document.getElementById('vodnikPreskociVse')).display"), "none")

    def test_sidro_posodobitve(self):
        self._js("window.safeerOsPojdi('nastavitve#blokPosodobitve'), 1")
        self.assertTrue(self._js("!!document.getElementById('blokPosodobitve').querySelector('#gumbPosodobi')"))


if __name__ == "__main__":
    unittest.main()
