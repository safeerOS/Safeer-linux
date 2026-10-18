"""Nazadnje predvajano in »Nakljucno« skozi PRAVO stran (assets/os/index.html?predvajalnik=1, os.js, os.css) v WebKitGTK 6.0
(Xvfb). Most Safeer OS nadomesti majhen nadomestek window.SafeerOS z demo podatki (brez omrezja).

Lastnik, 18. 10. 2026: na Domov je glavno »Nazadnje predvajano« - zadnji seznam z »Nadaljuj«, ki zacne skladbo, kjer je
uporabnik ostal; plosca vrste ob »Nakljucno« kaze pravi vrstni red z oznako, skladba, ki igra, je poudarjena in vidna
(plosca se pomakne do nje); prenos v zivo na seznamu ima »V zivo«.
Zagon: xvfb-run -a python3 -m pytest -q tests/test_nazadnje_predvajano_zivo.py
Posnetki zaslona (neobvezno): SAFEER_POSNETKI=<mapa> - shrani domov-nazadnje-predvajano.png, vrsta-nakljucno.png in
vrsta-v-zivo.png."""
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

VNOSI = [{"id": "sz:%d" % i, "naslov": "Pesem %d" % (i + 1), "izvajalec": ("Alfa", "Beta", "Gama")[i % 3], "vrsta": "glasba",
          "vir": "Seznam"} for i in range(40)]
VNOSI[5]["v_zivo"] = True
IZVOR = {"tip": "seznam", "ref": "Vecerni rock", "ime": "Vecerni rock", "slike": []}
ODGOVORI = {
    "mediaPolice": {"priljubljene": [], "ogledano": [], "police": [],
                    "nazadnje_seznam": {"izvor": IZVOR, "mesto": 2, "skupaj": 40, "pozicija": 95, "cas": 1,
                                        "skladba": {"id": "sz:2", "naslov": "Pesem 3", "izvajalec": "Gama", "slika": ""}}},
    "mediaOdkrivanje": {"police": []},
    "mediaSamodejniSeznami": {"seznami": []},
    "mediaNazadnje:nadaljuj": {"izvor": IZVOR, "vnosi": VNOSI, "mesto": 2, "pozicija": 95, "red": []},
    "mediaNazadnje:zapomni": True,
}
NADOMESTEK = """window.__klici = [];
window.SafeerOS = { klic: function (m, a) {
  var o = %s; window.__klici.push([m, a || []]);
  var k = m + (a && typeof a[0] === "string" ? ":" + a[0] : ""), r = k in o ? o[k] : (m in o ? o[m] : null);
  if (m === "mediaPredvajaj") r = { id: a[0], naslov: "Pesem", izvajalec: "Alfa", vrsta: "glasba", zvok: true, native: true };
  return Promise.resolve(r == null ? null : JSON.parse(JSON.stringify(r)));
} };"""


def _cakaj(pogoj, cas=15.0):
    kontekst, rok = GLib.MainContext.default(), time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.01)
    return pogoj()


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon (Xvfb)")
class NazadnjePredvajanoStran(unittest.TestCase):
    def setUp(self):
        upr = WebKit.UserContentManager()
        upr.add_script(WebKit.UserScript.new(NADOMESTEK % json.dumps(ODGOVORI), WebKit.UserContentInjectedFrames.TOP_FRAME,
                                             WebKit.UserScriptInjectionTime.START, None, None))
        okno = Gtk.Window()
        okno.set_default_size(1600, 900)
        # Locena seja brez diska: nastavitev »Nakljucno« (localStorage) ne ostane med zagoni preizkusa.
        self.pogled = WebKit.WebView(user_content_manager=upr, network_session=WebKit.NetworkSession.new_ephemeral())
        okno.set_child(self.pogled)
        okno.present()
        self.addCleanup(okno.destroy)
        self.pogled.load_uri("file://" + os.path.join(KOREN, "assets", "os", "index.html") + "?predvajalnik=1&jezik=sl")
        self.assertTrue(_cakaj(lambda: self._js("!!document.getElementById('mediaJunakPredvajaj')")), "junak z »Nadaljuj«")
        _cakaj(lambda: False, 0.8)                                    # slike in pisave

    def _js(self, koda):
        izid = {}

        def konec(p, r, *_):
            try:
                izid["v"] = json.loads(p.evaluate_javascript_finish(r).to_string() or "null")
            except GLib.Error as e:  # pragma: no cover
                izid["v"] = "napaka: %s" % e.message
        self.pogled.evaluate_javascript("JSON.stringify((%s)) || \"null\"" % koda, -1, None, None, None, konec, None)
        _cakaj(lambda: "v" in izid, 10)
        return izid.get("v")

    def _posnetek(self, ime):
        mapa = os.environ.get("SAFEER_POSNETKI")
        if not mapa:
            return
        izid = {}
        self.pogled.get_snapshot(WebKit.SnapshotRegion.VISIBLE, WebKit.SnapshotOptions.NONE, None,
                                 lambda p, r, *_: izid.setdefault("t", p.get_snapshot_finish(r)), None)
        self.assertTrue(_cakaj(lambda: "t" in izid, 10))
        os.makedirs(mapa, exist_ok=True)
        izid["t"].save_to_png(os.path.join(mapa, ime))

    def test_domov_nadaljuj_in_nakljucna_vrsta(self):
        junak = self._js("""(function () { var j = document.getElementById('mediaJunak'), r = j.getBoundingClientRect();
          return { vidno: !j.hidden && r.height > 100, oznaka: j.querySelector('.media-junak-oznaka').textContent,
                   naslov: j.querySelector('h2').textContent, pod: j.querySelector('.media-junak-pod').textContent,
                   meta: j.querySelector('.media-junak-meta').textContent, gumb: document.getElementById('mediaJunakPredvajaj').textContent,
                   gumbov: j.querySelectorAll('button').length }; })()""")
        self.assertEqual((junak["oznaka"], junak["naslov"], junak["gumb"], junak["gumbov"]),
                         ("Nazadnje predvajano", "Vecerni rock", "Nadaljuj", 1), junak)
        self.assertTrue(junak["vidno"])
        self.assertEqual(junak["pod"], "Pesem 3 — Gama")
        self.assertIn("Skladba 3 od 40", junak["meta"])
        self._posnetek("domov-nazadnje-predvajano.png")
        # Nadaljuj: jedro da seznam in mesto, stran zacne skladbo, kjer je uporabnik ostal.
        self._js("document.getElementById('mediaJunakPredvajaj').click()")
        self.assertTrue(_cakaj(lambda: self._js("window.__klici.filter(function (k) { return k[0] === 'mediaPredvajaj'; }).map(function (k) { return k[1][0]; })") == ["sz:2"]))
        self.assertTrue(_cakaj(lambda: self._js("!document.getElementById('mediaPlayerBar').hidden")))
        self.assertTrue(_cakaj(lambda: self._js("window.__klici.some(function (k) { return k[0] === 'mediaNazadnje' && k[1][0] === 'zapomni' && k[1][3].id === 'sz:2'; })")))
        # Nakljucno + plosca vrste: premesan red z oznako, trenutna poudarjena in vidna; prenos v zivo oznacen.
        self._js("document.getElementById('mediaPremesaj').click()")
        self._js("document.getElementById('mediaBarVrstaGumb').click()")
        self.assertTrue(_cakaj(lambda: self._js("!document.getElementById('mediaVrstaPlosca').hidden")))
        # Rocno izberemo 30. vrstico premesanega reda: plosca se mora pomakniti do nje.
        self._js("document.querySelectorAll('#mediaVrsta .media-vrsta-vnos')[29].click()")
        _cakaj(lambda: False, 0.5)
        s = self._js("""(function () { var p = document.getElementById('mediaVrstaPlosca'), v = p.querySelectorAll('.media-vrsta-vnos'),
            i = Array.prototype.findIndex.call(v, function (x) { return x.getAttribute('aria-current') === 'true'; }),
            rp = p.getBoundingClientRect(), ri = v[i].getBoundingClientRect(),
            zivi = Array.prototype.filter.call(v, function (x) { return x.classList.contains('zivo'); });
          return { oznaka: !document.getElementById('mediaVrstaNacin').hidden && document.getElementById('mediaVrstaNacin').textContent,
                   vrstic: v.length, trenutna: i, odmik: p.scrollTop,
                   vidna: ri.top >= document.getElementById('mediaVrstaNacin').getBoundingClientRect().bottom && ri.bottom <= rp.bottom,
                   oznakaVidna: document.getElementById('mediaVrstaNacin').getBoundingClientRect().top >= rp.top,
                   zivo: zivi.length === 1 && zivi[0].querySelector('small').textContent,
                   red: Array.prototype.map.call(v, function (x) { return x.querySelector('b').textContent; }) }; })()""")
        self.assertEqual(s["oznaka"], "Naključni vrstni red")
        self.assertEqual((s["vrstic"], s["trenutna"]), (40, 29))
        self.assertTrue(s["vidna"] and s["odmik"] > 0 and s["oznakaVidna"], s)
        self.assertTrue(self._js("!document.getElementById('mediaVrstaPlosca').hidden"))   # izbira plosce ne zapre
        self.assertTrue(str(s["zivo"]).startswith("V živo"), s)
        self.assertNotEqual(s["red"], ["Pesem %d" % (i + 1) for i in range(40)])          # pravi premesan red
        self.assertEqual(sorted(s["red"]), sorted("Pesem %d" % (i + 1) for i in range(40)))
        self._posnetek("vrsta-nakljucno.png")
        self._js("(function () { var p = document.getElementById('mediaVrstaPlosca'), z = p.querySelector('.media-vrsta-vnos.zivo');"
                 " p.scrollTop += z.getBoundingClientRect().top - p.getBoundingClientRect().top - 120; })()")
        _cakaj(lambda: False, 0.3)
        self._posnetek("vrsta-v-zivo.png")


if __name__ == "__main__":
    unittest.main()
