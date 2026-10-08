#!/usr/bin/env python3
"""Zivi preizkus stevca scita v pravem WebKitu (zunanji pregled 8. 10. 2026, tocka 4).

Dokaze, ki jih na papirju ni:
  1. kozmeticna skripta (loceni svet) RES skrije oglas (DOM dela tudi v locenem svetu);
  2. njen stevec RES pride do Pythona prek rokovalnika locenega sveta (safeer_stevec);
  3. stran v GLAVNEM svetu rokovalnika safeer_stevec NE doseze (ne more napihniti stevca);
  4. stran, ki posije increment prek glavnega rokovalnika (safeer), stevca NE napihne.

Potrebuje zaslon, zato se v CI (brez DISPLAY) preskoci.
"""
import http.server
import os
import socketserver
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import adblock  # noqa: E402

# Stran: en oglas (selektor .ad-unit iz GENERIC_COSMETIC) + poskus ponarejanja iz glavnega sveta.
STRAN = b"""<!doctype html>
<html><head><title>zacetek</title></head><body>
<div class="ad-unit" id="oglas">OGLAS</div>
<div id="vsebina">prava vsebina</div>
<script>
  // Stran poskusa napihniti stevec na oba nacina (oboje mora spodleteti):
  try { window.webkit.messageHandlers.safeer_stevec.postMessage({action:'increment_ads', count:50}); } catch(e) {}
  try { window.webkit.messageHandlers.safeer.postMessage({action:'increment_ads', count:50}); } catch(e) {}
</script>
</body></html>
"""


class Streznik(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(STRAN)))
        self.end_headers()
        self.wfile.write(STRAN)

    def log_message(self, *args):
        pass


@unittest.skipIf(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"),
                 "zivi WebKit preizkus samo lokalno (v CI pusti spletni proces, ki moti druge teste)")
@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
class StevecVZivo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        socketserver.TCPServer.allow_reuse_address = True
        cls.streznik = socketserver.TCPServer(("127.0.0.1", 0), Streznik)
        cls.vrata = cls.streznik.server_address[1]
        cls.nit = threading.Thread(target=cls.streznik.serve_forever, daemon=True)
        cls.nit.start()

    @classmethod
    def tearDownClass(cls):
        cls.streznik.shutdown()
        cls.streznik.server_close()

    def test_stevec_in_skritje(self):
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("WebKit2", "4.1")
        from gi.repository import Gtk, WebKit2, GLib  # noqa: F401

        prejeto = {"stevec": 0, "glavni": 0}
        upravitelj = WebKit2.UserContentManager()
        # Glavni rokovalnik (kot v izdelku): increment tu ne sme vec steti.
        upravitelj.register_script_message_handler("safeer")

        def ob_glavnem(_u, r):
            import json
            from core.os_splet import razcleni_sporocilo
            try:
                d = json.loads(r.get_js_value().to_json(0))
            except Exception:
                return
            # Kot v izdelku: glavni rokovalnik gre skozi razcleni_sporocilo, ki increment zavrne (vrne None).
            s = razcleni_sporocilo(d)
            if s and s.get("action") in ("increment_ads", "increment_threats"):
                prejeto["glavni"] += 1   # NE bi se smelo zgoditi (razcleni_sporocilo increment zavrne)
        upravitelj.connect("script-message-received::safeer", ob_glavnem)

        # Stevec v locenem svetu.
        upravitelj.register_script_message_handler_in_world(adblock.STEVEC_MOST, adblock.STEVEC_SVET)

        def ob_stevcu(_u, r):
            import json
            s = adblock.preveri_stevec(json.loads(r.get_js_value().to_json(0)))
            if s and s["action"] == "increment_ads":
                prejeto["stevec"] += s["count"]
        upravitelj.connect("script-message-received::" + adblock.STEVEC_MOST, ob_stevcu)

        # Kozmeticna skripta v locenem svetu (kot v izdelku).
        upravitelj.add_script(WebKit2.UserScript.new_for_world(
            adblock.GENERIC_COSMETIC_SCRIPT, WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            WebKit2.UserScriptInjectionTime.END, adblock.STEVEC_SVET, None, None))

        pogled = WebKit2.WebView.new_with_user_content_manager(upravitelj)
        okno = Gtk.OffscreenWindow()
        okno.add(pogled)
        okno.show_all()

        izid = {}
        zanka = GLib.MainLoop()

        def preveri_dom():
            # Je oglas odstranjen, prava vsebina pa ostane?
            pogled.run_javascript(
                "JSON.stringify({oglas: !!document.getElementById('oglas'), vsebina: !!document.getElementById('vsebina')})",
                None, ob_js, None)

        def ob_js(p, res, _d):
            import json
            try:
                v = p.run_javascript_finish(res).get_js_value().to_string()
                izid.update(json.loads(v))
            except Exception as e:
                izid["napaka"] = str(e)
            zanka.quit()

        def ob_nalaganju(_p, dogodek):
            if dogodek == WebKit2.LoadEvent.FINISHED:
                GLib.timeout_add(1500, lambda: (preveri_dom(), False)[1])

        pogled.connect("load-changed", ob_nalaganju)
        GLib.timeout_add_seconds(20, lambda: (izid.setdefault("napaka", "IZTEK"), zanka.quit())[1])
        pogled.load_uri(f"http://127.0.0.1:{self.vrata}/")
        zanka.run()
        okno.destroy()

        self.assertNotIn("napaka", izid, f"napaka v zivem preizkusu: {izid.get('napaka')}")
        self.assertFalse(izid.get("oglas"), "oglas (.ad-unit) ni bil odstranjen iz locenega sveta")
        self.assertTrue(izid.get("vsebina"), "prava vsebina je izginila")
        self.assertGreaterEqual(prejeto["stevec"], 1, "stevec iz locenega sveta ni prisel do Pythona")
        self.assertEqual(prejeto["glavni"], 0, "stran je napihnila stevec prek glavnega rokovalnika")


if __name__ == "__main__":
    unittest.main()
