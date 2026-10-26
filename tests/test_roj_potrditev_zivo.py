"""Izbira pred rojem skozi PRAVO stran (assets/os/index.html?predvajalnik=1, os.js, os.css) v WebKitGTK 6.0 (Xvfb).

Lastnik 25. 10. 2026 (naloga 21, tocka 3 - kot Android opozoriPredRojem): ko ima film samo torrente in debrida ni (ali
Webtor ni dal toka), jedro vrne napaka_koda=p2p_potrditev; stran pokaze izbiro, privzeti fokus je Preklici, »Predvajaj
neposredno« poslje mediaPredvajaj [id, {p2p: true}], »Poskusi znova cez minuto« po 60 s vprasa znova (brez p2p).
Most Safeer OS je nadomestek z demo podatki (brez omrezja). Zagon: xvfb-run -a python3 -m pytest -q tests/test_roj_potrditev_zivo.py"""
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
NADOMESTEK = """window.__klici = []; window.__dolgi = [];
var __st = window.setTimeout;
window.setTimeout = function (f, ms) { if (ms === 60000) { window.__dolgi.push(f); return 0; } return __st.apply(window, arguments); };
window.SafeerOS = { klic: function (m, a) {
  var o = %s; window.__klici.push([m, a || []]);
  var k = m + (a && typeof a[0] === "string" ? ":" + a[0] : ""), r = k in o ? o[k] : (m in o ? o[m] : null);
  if (m === "mediaPredvajaj") r = (a[1] && a[1].p2p === true)
    ? { id: a[0], naslov: "Film", vrsta: "glasba", zvok: true, native: true }
    : { id: a[0], naslov: "Film", vrsta: "film", napaka_koda: "p2p_potrditev", p2p: { webtor: true, debrid: false } };
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
class RojPotrditevStran(unittest.TestCase):
    def setUp(self):
        upr = WebKit.UserContentManager()
        upr.add_script(WebKit.UserScript.new(NADOMESTEK % json.dumps(ODGOVORI), WebKit.UserContentInjectedFrames.TOP_FRAME,
                                             WebKit.UserScriptInjectionTime.START, None, None))
        okno = Gtk.Window()
        okno.set_default_size(1600, 900)
        self.pogled = WebKit.WebView(user_content_manager=upr, network_session=WebKit.NetworkSession.new_ephemeral())
        okno.set_child(self.pogled)
        okno.present()
        self.addCleanup(okno.destroy)
        self.pogled.load_uri("file://" + os.path.join(KOREN, "assets", "os", "index.html") + "?predvajalnik=1&jezik=sl")
        self.assertTrue(_cakaj(lambda: self._js("!!document.getElementById('mediaJunakPredvajaj')")), "junak z »Nadaljuj«")
        _cakaj(lambda: False, 0.5)

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

    def _predvajanja(self):
        return self._js("window.__klici.filter(function (k) { return k[0] === 'mediaPredvajaj'; }).map(function (k) { return k[1]; })")

    def _okno(self):
        return self._js("""(function () { var s = document.getElementById('slojRoj'), g = function (i) { return document.getElementById(i); };
          return { vidno: s.classList.contains('viden') && s.getBoundingClientRect().width > 0, fokus: document.activeElement && document.activeElement.id,
                   naslov: g('rojNaslov').textContent, opis: g('rojOpis').textContent, neposredno: g('rojNeposredno').textContent,
                   znova: !g('rojZnova').hidden && g('rojZnova').getBoundingClientRect().width > 0,
                   torbox: !g('rojTorbox').hidden && g('rojTorbox').getBoundingClientRect().width > 0,
                   vloga: s.querySelector('[role=alertdialog]') && s.querySelector('[role=alertdialog]').getAttribute('aria-modal') }; })()""")

    def test_izbira_pred_rojem(self):
        self._js("document.getElementById('mediaJunakPredvajaj').click()")
        self.assertTrue(_cakaj(lambda: (self._okno() or {}).get("vidno")), "okno izbire pred rojem")
        _cakaj(lambda: (self._okno() or {}).get("fokus") == "rojPreklici", 2)
        o = self._okno()
        self.assertEqual((o["fokus"], o["naslov"], o["vloga"]), ("rojPreklici", "Tvoj naslov IP bo viden", "true"), o)
        self.assertEqual(o["neposredno"], "Predvajaj neposredno – tvoj naslov IP bo viden v roju")
        self.assertTrue(o["znova"] and o["torbox"], o)                 # dodatek Webtor in brez debrida
        self.assertEqual(self._predvajanja(), [["sz:2"]])
        # Poskusi znova cez minuto: po 60 s isto vprasanje znova (brez p2p), okno se pokaze spet.
        self._js("document.getElementById('rojZnova').click()")
        self.assertFalse(self._okno()["vidno"])
        self.assertEqual(self._js("window.__dolgi.length"), 1)
        self._js("window.__dolgi.shift()()")
        self.assertTrue(_cakaj(lambda: len(self._predvajanja()) == 2 and (self._okno() or {}).get("vidno")))
        self.assertEqual(self._predvajanja()[1], ["sz:2"])
        # Predvajaj neposredno: izrecen p2p, okno se zapre, predvajanje se zacne.
        self._js("document.getElementById('rojNeposredno').click()")
        self.assertTrue(_cakaj(lambda: len(self._predvajanja()) == 3))
        self.assertEqual(self._predvajanja()[2], ["sz:2", {"p2p": True}])
        self.assertFalse(self._okno()["vidno"])
        self.assertTrue(_cakaj(lambda: self._js("!document.getElementById('mediaPlayerBar').hidden")))
        self.assertEqual(self._js("window.__napake || []"), [])

    def test_preklici_ne_odpre_roja(self):
        self._js("document.getElementById('mediaJunakPredvajaj').click()")
        self.assertTrue(_cakaj(lambda: (self._okno() or {}).get("vidno")))
        self._js("document.getElementById('rojPreklici').click()")
        _cakaj(lambda: False, 0.5)
        self.assertFalse(self._okno()["vidno"])
        self.assertEqual(self._predvajanja(), [["sz:2"]])               # nobenega klica s p2p


if __name__ == "__main__":
    unittest.main()
