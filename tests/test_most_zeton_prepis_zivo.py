"""Mostovi z zetonom (Splet, Safeer OS, Safeer Link) v pravem WebKitGTK 6.0: skripta strani, ki pred klicem mostu
prepise JSON.stringify, postMessage rokovalnika, Object.prototype.toJSON ali doda setter "t", zetona ne dobi
(napadalski pregled 5. 11. 2026). Sporocilo gre se vedno naprej z veljavnim zetonom. Brez zaslona ali WebKita se
preskoci."""
import json
import os
import sys
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

#: Skripta strani: prestreze vse, kar bi most lahko poklical z zetonom, in shrani v window.__ukradeno.
PAST = """<script>
(function(){
var u = window.__ukradeno = [], izvJ = JSON.stringify;
function zapisi(v){ try { u.push(typeof v === 'string' ? v : izvJ.call(JSON, v)); } catch(e) { u.push(String(v)); } }
JSON.stringify = function(v){ var s = izvJ.apply(JSON, arguments); u.push(String(s));
  try { u.push(String(arguments.callee.caller && arguments.callee.caller.arguments &&
                       Array.prototype.join.call(arguments.callee.caller.arguments, '|'))); } catch(e) {}
  return s; };
JSON.parse = (function(izv){ return function(s){ u.push(String(s)); return izv.apply(JSON, arguments); }; })(JSON.parse);
Object.defineProperty(Object.prototype, 't', {configurable: true, set: function(v){ u.push('t=' + v);
  Object.defineProperty(this, 't', {value: v, writable: true, enumerable: true, configurable: true}); }});
Object.prototype.toJSON = function(){ for (var k in this) { try { if (k !== 'toJSON') u.push(k + '=' + String(this[k])); } catch(e) {} } return this; };
try { var h = window.webkit.messageHandlers.%(ROK)s, p = Object.getPrototypeOf(h), izvP = p.postMessage;
  p.postMessage = function(s){ zapisi(s); return izvP.call(this, s); };
  h.postMessage = p.postMessage; } catch(e) { u.push('napaka:' + e); }
Reflect.apply = function(f, t, a){ zapisi(a); return Function.prototype.apply.call(f, t, a); };
})();
</script>"""


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
class ZetonOstaneVMostu(unittest.TestCase):
    def _poskusi(self, rokovalnik, most_js, klic, zeton, velja):
        GLib, Gtk, WebKit = _webkit()
        prejeto = []

        def sprejmi(_u, r):
            try:
                s = json.loads(r.to_string())
                if isinstance(s, str):
                    s = json.loads(s)
            except Exception:  # noqa: BLE001
                s = None
            prejeto.append(bool(isinstance(s, dict) and velja(s)))
        u = WebKit.UserContentManager()
        u.register_script_message_handler(rokovalnik, None)
        u.connect("script-message-received::" + rokovalnik, sprejmi)
        u.add_script(WebKit.UserScript(most_js, WebKit.UserContentInjectedFrames.TOP_FRAME,
                                       WebKit.UserScriptInjectionTime.START, None, None))
        pogled = WebKit.WebView(user_content_manager=u)
        okno = Gtk.Window()
        okno.set_child(pogled)
        okno.present()
        stran = "<html><body>" + PAST % {"ROK": rokovalnik} + "<script>" + klic + "</script></body></html>"
        pogled.load_html(stran, "file:///safeer/ui/preizkus.html")
        zanka = GLib.MainLoop()
        konec = GLib.get_monotonic_time() + 15_000_000
        izid = {}

        def ob_branju(p, r, *_a):
            try:
                izid["ukradeno"] = p.evaluate_javascript_finish(r).to_string()
            except Exception as e:  # noqa: BLE001
                izid["napaka"] = str(e)
            zanka.quit()

        def preveri():
            if prejeto or GLib.get_monotonic_time() >= konec:
                pogled.evaluate_javascript("Array.prototype.join.call(window.__ukradeno || [], '\\n')", -1,
                                           None, None, None, ob_branju)
                return False
            return True
        GLib.timeout_add(100, preveri)
        zanka.run()
        okno.destroy()
        self.assertEqual(prejeto, [True], "most ni poslal sporocila z veljavnim zetonom")
        self.assertNotIn("napaka", izid, izid)
        self.assertNotIn(zeton, izid.get("ukradeno", ""), "skripta strani je dobila zeton mostu")

    def test_splet(self):
        from core import os_splet
        self._poskusi("safeer", os_splet.MOST_JS, "SafeerSplet.poslji({dejanje: 'preizkus'});", os_splet.ZETON_MOSTU,
                      lambda s: s.get("t") == os_splet.ZETON_MOSTU and s.get("dejanje") == "preizkus")

    def test_safeer_os(self):
        import safeer_os
        self._poskusi("safeerOs", safeer_os.MOST_JS, "SafeerOS.klic('preizkus', [1, 'a']);", safeer_os.ZETON_MOSTU,
                      lambda s: safeer_os.zeton_velja(s) and s.get("m") == "preizkus" and s.get("a") == [1, "a"])

    def test_safeer_link(self):
        from core import safeer_link
        self._poskusi("safeerLink", safeer_link.MOST_JS, "SafeerLink.potrdiKodo('123456');", safeer_link.ZETON_MOSTU,
                      lambda s: safeer_link.zeton_velja(s) and s.get("m") == "potrdiKodo" and s.get("a") == ["123456"])


if __name__ == "__main__":
    unittest.main()
