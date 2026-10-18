"""Odprt seznam predvajanja v Glasbi skozi PRAVO stran (assets/os/index.html?predvajalnik=1, os.js, katalog.css) v
WebKitGTK 6.0 (Xvfb). Most Safeer OS nadomesti majhen nadomestek window.SafeerOS z demo podatki (brez omrezja).

Lastnik, 18. 10. 2026 (TV 2560 x 1440): ob odprtem seznamu Spotify je bil nad skladbami razdelek »Na tem računalniku«
(narisiMedije ga je risal ne glede na odprt seznam), skladbe seznama pa ena ozka sredinska kolona (ovitek, naslov,
izvajalec in »+« drug pod drugim): .kat-kartica ima flex-direction: column, vrstica .kat-skladbe ga ni preklicala, ostanek
pravila brez izbirnika v katalog.css pa je izbrisal postavitev »+«. Izmerjeno pred popravkom (1920 x 1080): razdelek
viden, 1 stolpec, kartica 1562 x 158 px; po popravku: razdelek skrit, 3 stolpci vrstic po 58 px (2560: 5, 1280: 2).
Zagon: xvfb-run -a python3 -m pytest -q tests/test_seznam_glasbe_zivo.py"""
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

IZVAJALCI = ["Post Malone", "Eminem", "Juice WRLD", "Morgan Wallen", "Swae Lee"]
SKLADBE = [{"id": "sp:%d" % i, "naslov": "Skladba %d" % (i + 1), "izvajalec": IZVAJALCI[i % 5], "vrsta": "glasba",
            "sekund": 150 + i, "vir": "Spotify"} for i in range(50)]
LOKALNO = [{"vrsta": "glasba", "ime": "Izvajalec %d - Datoteka %d.mp3" % (i, i), "pot": "/glasba/%d.mp3" % i, "naVoljo": True}
           for i in range(12)]


def _odgovori(vrsta):
    seznam = {"ime": "Radio izvajalca", "vir": "Spotify", "vnosi": SKLADBE}
    if vrsta == "sp":
        seznam["sp"] = "spotify:playlist:demo"
    elif vrsta == "yt":
        seznam["yt"], seznam["vir"] = "PLdemo", "YouTube"
    else:
        seznam["vir"] = ""
    return {
        "knjiznicaMedijev": LOKALNO,
        "mediaSeznami": [{"ime": seznam["ime"], "stevilo": 50, "vir": seznam["vir"]}],
        "mediaSeznam": seznam,
        "mediaKatalog": {"vnosi": [], "kljuc": "k"},
        # Spotify: skladbo predvaja skrit Safeer DRM (spZacni), trak pokaze naslov.
        "mediaPredvajaj": {"spotify": True, "naslov": "Skladba 3", "izvajalec": "Juice WRLD"},
    }


NADOMESTEK = """window.SafeerOS = { klic: function (m, a) { var o = %s;
  return Promise.resolve(m in o ? JSON.parse(JSON.stringify(o[m])) : null); } };"""

STANJE = """(function () {
  var l = document.getElementById("katLokalnaGlasba"), m = document.getElementById("katMreza");
  var k = m.querySelectorAll(".kat-kartica"), r0 = k[0].getBoundingClientRect(), r1 = k[1].getBoundingClientRect();
  var plus = k[0].querySelector(".kat-na-seznam, .kat-odstrani"), rp = plus.getBoundingClientRect();
  return { lokalno: !l.hidden && l.getClientRects().length > 0, razred: m.className, kartic: k.length,
           smer: getComputedStyle(k[0]).flexDirection, visina: r0.height, sirina: r0.width, ista_vrsta: r0.top === r1.top,
           plus_poz: getComputedStyle(plus).position, plus_desno: r0.right - rp.right, plus_sredina: Math.abs((rp.top + rp.bottom) / 2 - (r0.top + r0.bottom) / 2),
           stolpcev: getComputedStyle(m).gridTemplateColumns.split(" ").length };
})()"""


def _cakaj(pogoj, cas=15.0):
    kontekst, rok = GLib.MainContext.default(), time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.01)
    return pogoj()


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon (Xvfb)")
class SeznamGlasbe(unittest.TestCase):
    def _odpri(self, vrsta):
        upr = WebKit.UserContentManager()
        upr.add_script(WebKit.UserScript.new(NADOMESTEK % json.dumps(_odgovori(vrsta)), WebKit.UserContentInjectedFrames.TOP_FRAME,
                                             WebKit.UserScriptInjectionTime.START, None, None))
        okno = Gtk.Window()
        okno.set_default_size(1920, 1080)
        self.pogled = WebKit.WebView(user_content_manager=upr)
        okno.set_child(self.pogled)
        okno.present()
        self.addCleanup(okno.destroy)
        self.pogled.load_uri("file://" + os.path.join(KOREN, "assets", "os", "index.html") + "?predvajalnik=1&jezik=sl")
        self.assertTrue(_cakaj(lambda: self._js("!!document.querySelector('#mediaNavKategorije [data-kategorija=\"glasba\"]')")))
        self._js("document.querySelector('#mediaNavKategorije [data-kategorija=\"glasba\"]').click()")
        self.assertTrue(_cakaj(lambda: self._js("!!document.querySelector('.kat-seznam-kartica')")))
        # Pregled Glasbe: glasba s tega racunalnika je vidna.
        self.assertTrue(_cakaj(lambda: self._js("!document.getElementById('katLokalnaGlasba').hidden")))
        self._js("document.querySelector('.kat-seznam-kartica').click()")
        self.assertTrue(_cakaj(lambda: self._js("document.querySelectorAll('#katMreza.kat-skladbe .kat-kartica').length") == 50))
        # Odgovori mosta (knjiznica -> narisiMedije) lahko pridejo za odprtjem seznama: pocakamo, da se stran umiri.
        _cakaj(lambda: False, 1.0)

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

    def _preveri_vrstice(self, s):
        self.assertFalse(s["lokalno"], "»Na tem računalniku« ne sme biti v odprtem seznamu")
        self.assertEqual(s["kartic"], 50)
        self.assertEqual(s["smer"], "row")                   # ovitek, naslov in dolzina v eni vrstici
        self.assertLess(s["visina"], 80)                     # prej 158 px na skladbo
        self.assertGreaterEqual(s["stolpcev"], 2, s)         # vec stolpcev (prej 1 cez vso sirino); xvfb-run ima 1280 px
        self.assertTrue(s["ista_vrsta"], s)                  # vrstni red po vrsticah: 1 in 2 sta druga ob drugi
        self.assertEqual(s["plus_poz"], "absolute")          # »+« desno v vrstici, ne pod izvajalcem
        self.assertLess(s["plus_desno"], 24, s)
        self.assertLess(s["plus_sredina"], 3, s)

    def test_spotify_samo_skladbe_v_vrsticah_in_trenutna(self):
        self._odpri("sp")
        self._preveri_vrstice(self._js(STANJE))
        # Celozaslonski nacin (TV): html.kavc ima svojo mrezo plakatov - seznam ostane v vrsticah.
        self._js("document.documentElement.classList.add('kavc')")
        _cakaj(lambda: False, 0.3)
        self._preveri_vrstice(self._js(STANJE))
        # Skladba, ki igra (Spotify), je oznacena.
        self._js("document.querySelectorAll('#katMreza .kat-kartica')[2].click()")
        self.assertTrue(_cakaj(lambda: self._js(
            "Array.prototype.map.call(document.querySelectorAll('#katMreza [aria-current=\"true\"]'), function (k) { return k.getAttribute('data-id'); })") == ["sp:2"]))
        # »← Vsi seznami«: pregled Glasbe spet pokaze glasbo s tega racunalnika.
        self._js("document.querySelector('#mediaSeznami .kat-seznam-glava .gumb').click()")
        self.assertTrue(_cakaj(lambda: self._js(
            "!document.getElementById('katLokalnaGlasba').hidden && document.querySelectorAll('#katLokalnaGlasba .media-skladba').length") == 12))

    def test_youtube_in_svoj_seznam(self):
        for vrsta in ("yt", "svoj"):
            with self.subTest(vrsta=vrsta):
                self._odpri(vrsta)
                self._preveri_vrstice(self._js(STANJE))


if __name__ == "__main__":
    unittest.main()
