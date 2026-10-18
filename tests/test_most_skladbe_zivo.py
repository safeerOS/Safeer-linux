"""Most skladbe lahkega medijskega pogleda v pravem WebKitGTK 6.0 (Xvfb): Safeer OS sprejme samo sporocilo releja v
glavnem okvirju strani posnetka (safeer_os.namesti_most_skladbe), ne skript strani ali podokvirjev.

Pregled 18. 10. 2026: rokovalnik »safeerSkladba« je bil v glavnem svetu dosegljiv vsakemu okvirju (oglasni iframe v
vgradnji je lahko javil »konec« ali napako in preskocil skladbo); WebKitGTK sporocilu okvirja ne doda (signal nosi
samo JSCValue). Izmerjeno ob popravku: stara pot je sprejela 3 ponarejena sporocila (stran, srcdoc, data:), nova 0."""
import json
import os
import time
import unittest

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import GLib, Gtk, WebKit  # noqa: E402

import safeer_os  # noqa: E402

STRAN = """<!doctype html><html><body>
<div id="movie_player"></div>
<script>
var p = document.getElementById("movie_player");
p.getPlayerState = function () { return 1; };
p.addEventListener = function () {};
try { window.webkit.messageHandlers.safeerSkladba.postMessage('{"stanje":0,"v":"59o4m222aVw","od":"stran"}'); document.title = "poslal"; }
catch (e) { document.title = "ni"; }
</script>
<iframe srcdoc="<script>try{window.webkit.messageHandlers.safeerSkladba.postMessage('{&quot;stanje&quot;:0,&quot;v&quot;:&quot;59o4m222aVw&quot;}')}catch(e){}</script>"></iframe>
<iframe src="data:text/html,<script>try{window.webkit.messageHandlers.safeerSkladba.postMessage('{&quot;stanje&quot;:0}')}catch(e){};try{parent.document.dispatchEvent(new CustomEvent('safeer-skladba',{detail:'{&quot;stanje&quot;:0}'}))}catch(e){}</script>"></iframe>
</body></html>"""


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon (Xvfb)")
class MostSkladbe(unittest.TestCase):
    def test_samo_rele_glavnega_okvirja(self):
        prejeto = []
        upravitelj = WebKit.UserContentManager()
        safeer_os.namesti_most_skladbe(upravitelj, lambda _u, v: prejeto.append(json.loads(v.to_string())))
        okno = Gtk.Window()
        pogled = WebKit.WebView(user_content_manager=upravitelj)
        okno.set_child(pogled)
        okno.present()
        self.addCleanup(okno.destroy)
        pogled.load_html(STRAN, "https://www.youtube.com/embed/59o4m222aVw?autoplay=1")
        kontekst, rok = GLib.MainContext.default(), time.monotonic() + 15
        while time.monotonic() < rok and not prejeto:
            if not kontekst.iteration(False):
                time.sleep(0.01)
        rok = time.monotonic() + 2                    # se cas za morebitna ponarejena sporocila
        while time.monotonic() < rok:
            if not kontekst.iteration(False):
                time.sleep(0.01)
        self.assertEqual(pogled.get_title(), "ni")    # skripta strani mostu ne vidi
        self.assertTrue(prejeto)
        self.assertTrue(all(x == {"stanje": 1, "v": "59o4m222aVw"} for x in prejeto), prejeto)


if __name__ == "__main__":
    unittest.main()
