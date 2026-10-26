"""Safeer Player v mirovanju ne rise: na PRAVI strani (assets/os/index.html?predvajalnik=1, os.js, katalog.css) v
WebKitGTK 6.0 (Xvfb) po nalaganju kataloga ne tece nobena animacija; vrtavka se vrti samo med nalaganjem naslednje strani.

Lastnik, 26. 10. 2026: »Ko sem zaprl Safeer player, se je obremenitev procesorja zmanjšala.« Izmerjeno istega dne (Player iz
izvorne kode, Xvfb in weston headless z GPU, /proc po nitih, 3 ponovitve): Glasba odprta, nic ne predvaja - sestavljalnik
WebKita (eadedCompositor) ~145 budjenj/s in okno GTK ~60 slik/s; document.getAnimations() = [kat-vrti na .kat-vrtavka].
Vrtavka oznake konca mreze (neskoncno drsenje) se je vrtela ves cas, ko je imel katalog se kaj strani, ceprav je bila pod
robom zaslona in se nic ni nalagalo. Zaprto (skrito) okno je risanje ustavilo. Most Safeer OS nadomesti majhen nadomestek
window.SafeerOS z demo podatki (brez omrezja). Zagon: xvfb-run -a python3 -m pytest -q tests/test_predvajalnik_mirovanje_zivo.py"""
import json
import os
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import GLib, Gtk, WebKit  # noqa: E402
except (ImportError, ValueError) as _napaka:  # pragma: no cover - okolje brez GTK4/WebKit 6.0
    raise unittest.SkipTest("WebKitGTK 6.0 ni na voljo: %s" % _napaka)

#: Katalog z veliko stranmi (kot Glasba, Filmi, Radio z dodatki): po 40 vnosov, 50 strani. Stran > 1 odgovori takoj,
#: razen ko preizkus nalaganje zadrzi (window.__zadrzi) - takrat odgovor caka na window.__spusti().
NADOMESTEK = """(function () {
  var cakajo = [];
  window.__zadrzi = false;
  window.__spusti = function () { var c = cakajo; cakajo = []; c.forEach(function (f) { f(); }); };
  function stran(n) {
    var vnosi = [];
    for (var i = 0; i < 40; i++) vnosi.push({ id: "g:" + n + ":" + i, naslov: "Skladba " + n + "-" + i, izvajalec: "Izvajalec",
                                              vrsta: "glasba", vir: "Demo" });
    return { vnosi: vnosi, kljuc: "k" + n, skupaj_strani: 50, skupaj: 2000 };
  }
  window.SafeerOS = { klic: function (m, a) {
    if (m === "mediaKatalog") {
      var n = Number(a && a[3]) || 1;
      if (n > 1 && window.__zadrzi) return new Promise(function (res) { cakajo.push(function () { res(stran(n)); }); });
      return Promise.resolve(stran(n));
    }
    return Promise.resolve(null);
  } };
})();"""

TECE = """document.getAnimations().filter(function (a) { return a.playState === "running"; }).map(function (a) {
  var t = a.effect && a.effect.target; return (a.animationName || "?") + "@" + (t ? t.className : "?"); })"""


def _cakaj(pogoj, cas=15.0):
    kontekst, rok = GLib.MainContext.default(), time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.01)
    return pogoj()


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon (Xvfb)")
class PredvajalnikMirovanje(unittest.TestCase):
    def setUp(self):
        upr = WebKit.UserContentManager()
        upr.add_script(WebKit.UserScript.new(NADOMESTEK, WebKit.UserContentInjectedFrames.TOP_FRAME,
                                             WebKit.UserScriptInjectionTime.START, None, None))
        okno = Gtk.Window()
        okno.set_default_size(1280, 800)
        self.pogled = WebKit.WebView(user_content_manager=upr)
        okno.set_child(self.pogled)
        okno.present()
        self.addCleanup(okno.destroy)
        self.pogled.load_uri("file://" + os.path.join(KOREN, "assets", "os", "index.html") + "?predvajalnik=1&jezik=sl")
        self.assertTrue(_cakaj(lambda: self._js("!!document.querySelector('#mediaNavKategorije [data-kategorija=\"glasba\"]')")))
        self._js("document.querySelector('#mediaNavKategorije [data-kategorija=\"glasba\"]').click()")
        self.assertTrue(_cakaj(lambda: (self._js("document.querySelectorAll('#katMreza .kat-kartica').length") or 0) >= 40))
        # Opazovalec konca mreze nalozi strani, dokler oznaka ni dalec pod robom zaslona; nato je stran mirna.
        _cakaj(lambda: False, 1.5)

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

    def test_po_nalaganju_ne_tece_nobena_animacija(self):
        # Katalog ima se strani: oznaka konca mreze je v postavitvi (opazovalec), a nic se ne nalaga.
        self.assertFalse(self._js("document.getElementById('katNalaganje').hidden"))
        self.assertFalse(self._js("document.getElementById('katNalaganje').classList.contains('nalaga')"))
        self.assertEqual(self._js(TECE), [], "v mirovanju ne sme teci nobena animacija (vidno okno bi risalo ~60 slik/s)")

    def test_vrtavka_se_vrti_samo_med_nalaganjem(self):
        self._js("window.__zadrzi = true")
        self._js("document.getElementById('katNalaganje').scrollIntoView()")
        self.assertTrue(_cakaj(lambda: self._js("document.getElementById('katNalaganje').classList.contains('nalaga')")),
                        "ob drsenju do konca se naslednja stran nalaga")
        self.assertEqual(self._js("getComputedStyle(document.querySelector('#katNalaganje .kat-vrtavka')).visibility"), "visible")
        self.assertIn("kat-vrti@kat-vrtavka", self._js(TECE))
        # Stran je prisla: vrtavka obstane in se skrije, animacij ni vec.
        self._js("window.__zadrzi = false")
        self._js("window.__spusti()")
        self._js("document.getElementById('katMreza').scrollIntoView()")
        self.assertTrue(_cakaj(lambda: self._js(
            "!document.getElementById('katNalaganje').classList.contains('nalaga')")), "nalaganje se mora koncati")
        _cakaj(lambda: False, 1.0)
        self.assertEqual(self._js(TECE), [])


if __name__ == "__main__":
    unittest.main()
