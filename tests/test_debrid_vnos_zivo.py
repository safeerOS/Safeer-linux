"""Okno »Debrid storitve« skozi PRAVO stran (assets/os/index.html?predvajalnik=1, os.js) v WebKitGTK 6.0 (Xvfb) in
PRAVI most core/debrid.most: klic strani gre v Python (delovna nit, kot os_katalog.izvedi), odgovor nazaj v stran.

Lastnik 25. 10. 2026: kljuc TorBox in indeksator Usenet (NZBFinder) na prenosniku kot na TV, s preverbo ob vnosu.
Preizkus tipka kljuc (Enter), med preverbo sta polje in gumb zaklenjena, izid je v vrstici stanja (role=status), fokus
se vrne v polje, kljuc ne ostane v strani. Kljuci so izmisljeni; zbirka skrivnosti je v pomnilniku.
Storitvi sta privzeto ponaredka; SAFEER_ZIVO_KLJUCI=1 vprasa PRAVI TorBox in nzbfinder.ws (izmisljen kljuc mora biti
zavrnjen). Zagon: xvfb-run -a python3 -m pytest -q tests/test_debrid_vnos_zivo.py"""
import json
import os
import threading
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import GLib, Gtk, WebKit  # noqa: E402
except (ImportError, ValueError) as _napaka:  # pragma: no cover - okolje brez GTK4/WebKit 6.0
    raise unittest.SkipTest("WebKitGTK 6.0 ni na voljo: %s" % _napaka)

from core import debrid, debrid_pravila as P  # noqa: E402

ZIVO = os.environ.get("SAFEER_ZIVO_KLJUCI") == "1"
KLJUC_TB = "0f0e0d0c-0b0a-0908-0706-050403020100"
KLJUC_IX = "0123456789abcdef0123456789abcdef"

#: Most strani: mediaDebrid gre v vrsto, ki jo preizkus izvede v Pythonu; ostalo vrne null (kot prazen katalog).
MOST = """window.__zahteve = []; window.__odg = {}; window.__n = 0; window.__napake = []; window.addEventListener("error", function (e) { window.__napake.push(String(e.message) + " @" + e.lineno); });
window.SafeerOS = { klic: function (m, a) {
  if (m !== "mediaDebrid") return Promise.resolve(null);
  var id = ++window.__n;
  return new Promise(function (r) { window.__odg[id] = r; window.__zahteve.push({ id: id, a: a }); });
} };"""


def _cakaj(pogoj, cas=15.0):
    kontekst, rok = GLib.MainContext.default(), time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.01)
    return pogoj()


class _Zbirka:
    def __init__(self):
        self.z: dict = {}

    def skrij(self, s):
        k = "zbirka:%d" % (len(self.z) + 1000)
        self.z[k] = s
        return k

    def razkrij(self, k):
        return self.z[k]

    def pozabi(self, k):
        self.z.pop(k, None)


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon (Xvfb)")
class DebridVnos(unittest.TestCase):
    def setUp(self):
        self.zbirka = _Zbirka()
        nast = {"d": {}}
        self.d = debrid.Debrid(lambda: nast["d"], lambda x: nast.__setitem__("d", json.loads(json.dumps(x))),
                               self.zbirka.skrij, self.zbirka.razkrij, self.zbirka.pozabi)
        self.nast = nast
        upr = WebKit.UserContentManager()
        upr.add_script(WebKit.UserScript.new(MOST, WebKit.UserContentInjectedFrames.TOP_FRAME,
                                             WebKit.UserScriptInjectionTime.START, None, None))
        okno = Gtk.Window()
        okno.set_default_size(1280, 900)
        self.pogled = WebKit.WebView(user_content_manager=upr)
        okno.set_child(self.pogled)
        okno.present()
        self.addCleanup(okno.destroy)
        self.pogled.load_uri("file://" + os.path.join(KOREN, "assets", "os", "index.html") + "?predvajalnik=1&jezik=sl")
        # Stran je povezala dogodke (poveziDogodke), ko so gumbi kategorij Medijskega centra narisani.
        self.assertTrue(_cakaj(lambda: self._js("!!document.querySelector('#mediaNavKategorije [data-kategorija]')")))
        # Odpri okno, kot ga odpre izbira »Nastavitve debrida …« ob zvrsteh.
        self._js("(function () { var s = document.getElementById('mediaDebrid'); s.add(new Option('x', 'nastavitve'));"
                 " s.value = 'nastavitve'; s.dispatchEvent(new Event('change')); return 1; })()")
        self._streži()
        self.assertTrue(_cakaj(lambda: self._js("!!document.querySelector('#debridSeznam [data-id=\"torbox\"] input')")))
        self.assertTrue(self._js("document.getElementById('slojDebrid').classList.contains('viden')"))

    def _js(self, koda):
        izid = {}

        def konec(p, r, *_):
            try:
                izid["v"] = json.loads(p.evaluate_javascript_finish(r).to_string() or "null")
            except GLib.Error as e:  # pragma: no cover - napaka skripte pove preizkus
                izid["v"] = "napaka: %s" % e.message
        self.pogled.evaluate_javascript("JSON.stringify((%s)) || \"null\"" % koda, -1, None, None, None, konec, None)
        _cakaj(lambda: "v" in izid, 10)
        return izid.get("v")

    def _streži(self, cas=20.0):
        """Izvede cakajoce klice mediaDebrid v pravem mostu (delovna nit) in odgovor vrne strani."""
        konec = time.monotonic() + cas
        while time.monotonic() < konec:
            zahteve = self._js("window.__zahteve.splice(0)") or []
            if not zahteve:
                return
            for z in zahteve:
                izid = {}
                nit = threading.Thread(target=lambda a=z["a"]: izid.__setitem__("v", debrid.most(self.d, list(a))))
                nit.start()
                _cakaj(lambda: not nit.is_alive(), 20)
                self._js("(window.__odg[%d](%s), 1)" % (z["id"], json.dumps(izid.get("v"))))
            _cakaj(lambda: False, 0.1)

    def _vpisi(self, vrstica, vrednosti):
        """Vpise vrednosti v polja vrstice in pritisne Enter v zadnjem (kot uporabnik s tipkovnico)."""
        return self._js("""(function () {
          var p = document.querySelectorAll('#debridSeznam [data-id="%s"] input'), v = %s;
          for (var i = 0; i < v.length; i++) { p[i].focus(); p[i].value = v[i]; }
          p[v.length - 1].dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
          var g = document.querySelector('#debridSeznam [data-id="%s"] button');
          return { zaklenjeno: p[v.length - 1].disabled && g.disabled, zaseden: g.getAttribute('aria-busy'),
                   stanje: document.getElementById('debridStanjeVnosa').textContent,
                   vloga: document.getElementById('debridStanjeVnosa').getAttribute('role') };
        })()""" % (vrstica, json.dumps(vrednosti), vrstica))

    def _po(self, vrstica):
        return self._js("""(function () {
          var a = document.activeElement, v = document.querySelector('#debridSeznam [data-id="%s"]');
          return { stanje: document.getElementById('debridStanjeVnosa').textContent, opis: v.querySelector('small').textContent,
                   fokus_v_vrstici: v.contains(a), fokus_vrsta: a && a.type, vrednosti: Array.prototype.map.call(v.querySelectorAll('input'), function (p) { return p.value; }),
                   gumbi: Array.prototype.map.call(v.querySelectorAll('button'), function (b) { return [b.textContent, b.getAttribute('aria-label'), b.disabled]; }),
                   html: document.body.innerHTML };
        })()""" % vrstica)

    def test_torbox_zavrnjen_veljaven_in_odstranjen(self):
        pred = self._vpisi("torbox", [KLJUC_TB])
        self.assertEqual((pred["zaklenjeno"], pred["zaseden"], pred["stanje"], pred["vloga"]),
                         (True, "true", "Preverjam ključ …", "status"))
        preveri = mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_NEVELJAVEN, None))
        with (mock.MagicMock() if ZIVO else preveri):
            self._streži()
        po = self._po("torbox")
        self.assertTrue(po["stanje"].startswith("TorBox je ta ključ zavrnil – ni shranjen."), po["stanje"])
        self.assertIn("torbox.app", po["stanje"])
        self.assertEqual(self.zbirka.z, {})
        self.assertTrue(po["fokus_v_vrstici"])
        self.assertNotIn(KLJUC_TB, po["html"] + json.dumps(po["vrednosti"]))
        if ZIVO:
            return                                  # pravi TorBox: izmisljen kljuc je zavrnjen - dovolj
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, P.TORBOX_PRO)):
            self._vpisi("torbox", [KLJUC_TB])
            self._streži()
        po = self._po("torbox")
        self.assertEqual(po["stanje"], "Ključ TorBox je veljaven in shranjen (šifriran) · paket Pro.")
        self.assertEqual(po["opis"], "ključ vpisan ✓ · paket Pro")
        self.assertEqual(list(self.zbirka.z.values()), [KLJUC_TB])
        self.assertNotIn(KLJUC_TB, po["html"])
        self.assertEqual(po["gumbi"][1][:2], ["Odstrani ključ", "Odstrani ključ – TorBox"])
        self._js("(document.querySelectorAll('#debridSeznam [data-id=\"torbox\"] button')[1].click(), 1)")
        self._streži()
        po = self._po("torbox")
        self.assertEqual(po["stanje"], "Ključ TorBox je odstranjen s tega računalnika.")
        self.assertEqual((self.zbirka.z, len(po["gumbi"])), ({}, 1))
        self.assertTrue(po["fokus_v_vrstici"])

    def test_nzbfinder_zavrnjen_naslov_ostane(self):
        pred = self._vpisi("usenet", ["https://nzbfinder.ws", KLJUC_IX])
        self.assertEqual((pred["zaklenjeno"], pred["stanje"]), (True, "Preverjam ključ …"))
        preveri = mock.patch.object(debrid, "indeksator_preveri", return_value=P.PREVERBA_NEVELJAVEN)
        with (mock.MagicMock() if ZIVO else preveri):
            self._streži()
        po = self._po("usenet")
        self.assertEqual(po["stanje"], "Indeksator je ključ zavrnil – ni shranjen. Preveri ga na strani profila indeksatorja.")
        self.assertEqual(po["vrednosti"], ["https://nzbfinder.ws", ""])      # naslova ni treba tipkati znova
        self.assertEqual(po["fokus_vrsta"], "password")
        self.assertIn("nzbfinder.ws/profile", po["opis"])
        self.assertEqual(self.zbirka.z, {})
        self.assertNotIn(KLJUC_IX, po["html"])


if __name__ == "__main__":
    unittest.main()
