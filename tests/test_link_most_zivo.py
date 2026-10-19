"""Most safeerLink v pravem WebKitGTK 6.0 (Xvfb): stran Linka klice SafeerLink z zetonom, okvir drugega izvora pa
mostu ne doseze (core/safeer_link.ZETON_MOSTU, drugi neodvisni pregled 19. 10. 2026). Brez zaslona ali WebKita se
preskoci."""
import json
import os
import sys
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

#: Glavni okvir poklice SafeerLink.zapri(); okvir drugega izvora (data:) poskusi poslati »seznani« neposredno in
#: poklicati parent.SafeerLink.poisciHub().
STRAN = """<html><body><script>window.SafeerLink.zapri();</script>
<iframe src="data:text/html,<script>try{window.webkit.messageHandlers.safeerLink.postMessage(JSON.stringify({m:'seznani',a:[]}))}catch(e){}
try{parent.SafeerLink.poisciHub()}catch(e){}</script>"></iframe></body></html>"""


def _webkit():
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("WebKit", "6.0")
        from gi.repository import GLib, Gtk, WebKit
        return GLib, Gtk, WebKit
    except Exception:  # noqa: BLE001
        return None


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(_webkit() is not None, "potrebuje WebKitGTK")
class MostLinkaVZivo(unittest.TestCase):
    def test_okvir_drugega_izvora_ne_doseze_mostu(self):
        GLib, Gtk, WebKit = _webkit()
        from core import safeer_link
        prejeto = []

        def sprejmi(_u, r):
            s = json.loads(r.to_string())
            prejeto.append((s.get("m"), safeer_link.zeton_velja(s)))
        u = WebKit.UserContentManager()
        u.register_script_message_handler("safeerLink", None)
        u.connect("script-message-received::safeerLink", sprejmi)
        u.add_script(WebKit.UserScript(safeer_link.MOST_JS, WebKit.UserContentInjectedFrames.TOP_FRAME,
                                       WebKit.UserScriptInjectionTime.START, None, None))
        pogled = WebKit.WebView(user_content_manager=u)
        okno = Gtk.Window()
        okno.set_child(pogled)
        okno.present()
        pogled.load_html(STRAN, "file:///safeer/assets/link/index.html")
        zanka = GLib.MainLoop()
        GLib.timeout_add(2500, lambda: (zanka.quit(), False)[1])
        zanka.run()
        okno.destroy()
        # Glavni okvir: z zetonom. Okvir drugega izvora: njegovo sporocilo nima zetona, SafeerLink starsa ni dosegljiv.
        self.assertIn(("zapri", True), prejeto)
        self.assertNotIn(("seznani", True), prejeto)
        self.assertNotIn("poisciHub", [m for m, _z in prejeto])
        self.assertEqual([m for m, z in prejeto if z], ["zapri"])


if __name__ == "__main__":
    unittest.main()
