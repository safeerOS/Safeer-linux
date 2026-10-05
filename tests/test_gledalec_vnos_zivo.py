#!/usr/bin/env python3
"""Okno gledalca Safeer Controla: en klik na sliko zaslona = en dotik na napravi (živi preizkus v pravem WebKitu).

Okno vbrizga GLEDALEC_VNOS_JS (klik -> ukaz input.tap po Safeer Linku). Stran gledalca s središča na Androidu ima
od 27. 9. 2026 na sliki svoje poslušalce miške (klik -> POST .../input -> isti ukaz). Izmerjeno 5. 10. 2026: en klik
sta poslali OBE poti. Tu naložimo stran z enakimi poslušalci, kot jih ima stran z Androida (namesto zahteve šteje),
vbrizgamo skripto iz safeer_control.py in sprožimo dogodke miške na sliki.

Preizkus potrebuje zaslon in WebKitGTK, zato se brez njiju preskoči.
"""

import json
import os
import re
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTROL = os.path.join(KOREN, "safeer_control.py")

# Slika 200 x 100 v oknu 800 x 600 (object-fit: contain): zgoraj in spodaj ostane po 100 px črnega roba.
SLIKA = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='100'%3E%3C/svg%3E"
STRAN = """<!doctype html><html><head><meta charset="utf-8"><title>gledalec</title>
<style>html,body{margin:0;height:100%%;background:#000;overflow:hidden}
img{position:absolute;inset:0;width:100%%;height:100%%;object-fit:contain}</style></head><body>
<img id="zaslon" src="%s" alt="" draggable="false">
<script>
// Poslušalci strani gledalca s središča na Androidu (HubTokovi.STRAN_GLEDALCA); namesto fetch(.../input) štejemo.
var s=document.getElementById('zaslon'); window.__stran=[];
function tocka(e){var r=s.getBoundingClientRect();var t=e.changedTouches?e.changedTouches[0]:e;
  var x=(t.clientX-r.left)/r.width,y=(t.clientY-r.top)/r.height;return [Math.min(1,Math.max(0,x)),Math.min(1,Math.max(0,y))];}
var zacetna=null;
function dol(e){e.preventDefault();zacetna=tocka(e);}
function gor(e){e.preventDefault();if(!zacetna)return;var koncna=tocka(e),dx=koncna[0]-zacetna[0],dy=koncna[1]-zacetna[1];
  window.__stran.push((Math.abs(dx)<0.02&&Math.abs(dy)<0.02)?'tap':'swipe');zacetna=null;}
s.addEventListener('mousedown',dol); s.addEventListener('mouseup',gor);
</script></body></html>""" % SLIKA


def _dogodki(tocke) -> str:
    """JS: mousedown na prvi točki, mouseup na zadnji (deleži okna); vrne, kaj so naredili poslušalci strani."""
    return """(function(){var s=document.getElementById('zaslon'), t=%s;
function d(vrsta, p){s.dispatchEvent(new MouseEvent(vrsta,{bubbles:true,cancelable:true,button:0,
  clientX:p[0]*window.innerWidth,clientY:p[1]*window.innerHeight}));}
d('mousedown', t[0]); d('mouseup', t[t.length-1]); return JSON.stringify(window.__stran);})()""" % json.dumps(tocke)


def _webkit():
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("WebKit2", "4.1")
        from gi.repository import GLib, Gtk, WebKit2
        return GLib, Gtk, WebKit2
    except Exception:  # noqa: BLE001 - brez WebKitGTK (npr. repozitorij za Windows) preizkusa ni
        return None


@unittest.skipUnless(os.path.isfile(CONTROL), "Safeer Control za Linux")
@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(_webkit() is not None, "potrebuje WebKitGTK")
class KlikVOknuGledalca(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CONTROL, encoding="utf-8") as f:
            cls.skripta = re.search(r'GLEDALEC_VNOS_JS = r"""(.*?)"""', f.read(), re.S).group(1)

    def _klikni(self, tocke, s_skripto=True):
        """Vrne (kaj je poslala stran, kaj je poslala vbrizgana skripta Controla)."""
        GLib, Gtk, WebKit2 = _webkit()
        ukazi = []
        upravitelj = WebKit2.UserContentManager()
        upravitelj.register_script_message_handler("safeerVnos")
        upravitelj.connect("script-message-received::safeerVnos",
                           lambda _u, r: ukazi.append(json.loads(r.get_js_value().to_string())))
        if s_skripto:
            upravitelj.add_script(WebKit2.UserScript(self.skripta, WebKit2.UserContentInjectedFrames.TOP_FRAME,
                                                     WebKit2.UserScriptInjectionTime.END, None, None))
        pogled = WebKit2.WebView.new_with_user_content_manager(upravitelj)
        okno = Gtk.OffscreenWindow()
        okno.set_default_size(800, 600)
        okno.add(pogled)
        okno.show_all()
        zanka = GLib.MainLoop()
        izid = {}

        novi = hasattr(pogled, "evaluate_javascript")        # WebKitGTK 2.40+; starejsi ima run_javascript

        def po_dogodkih(_p, rezultat):
            try:
                vrednost = (pogled.evaluate_javascript_finish(rezultat) if novi
                            else pogled.run_javascript_finish(rezultat).get_js_value())
                izid["stran"] = json.loads(vrednost.to_string())
            except Exception as e:  # noqa: BLE001
                izid["napaka"] = str(e)
            GLib.timeout_add(300, lambda: (zanka.quit(), False)[1])      # sporocila skripte pridejo za odgovorom

        def sprozi():
            if novi:
                pogled.evaluate_javascript(_dogodki(tocke), -1, None, None, None, po_dogodkih)
            else:
                pogled.run_javascript(_dogodki(tocke), None, po_dogodkih)
            return False

        def ob_nalaganju(_p, dogodek):
            if dogodek == WebKit2.LoadEvent.FINISHED:
                GLib.timeout_add(400, sprozi)

        pogled.connect("load-changed", ob_nalaganju)
        pogled.load_html(STRAN, "https://naprava.test/cast/screen/abc/view")
        GLib.timeout_add(10000, lambda: (zanka.quit(), False)[1])
        zanka.run()
        okno.destroy()
        self.assertNotIn("napaka", izid, izid)
        self.assertIn("stran", izid, "stran se ni naložila ali ni odgovorila")
        return izid["stran"], ukazi

    def test_stran_sama_poslje_dotik(self):
        """Brez okna Controla (zavihek brskalnika): poslušalci strani delajo - po tem vemo, da preizkus meri pravo stvar."""
        stran, ukazi = self._klikni([[0.5, 0.5]], s_skripto=False)
        self.assertEqual((stran, ukazi), (["tap"], []))

    def test_en_klik_je_en_dotik(self):
        stran, ukazi = self._klikni([[0.5, 0.5]])
        self.assertEqual(stran, [], "stran dotika ne sme poslati se enkrat")
        self.assertEqual(len(ukazi), 1, ukazi)
        self.assertEqual(ukazi[0]["d"], "input.tap")
        self.assertAlmostEqual(ukazi[0]["p"]["x"], 0.5, places=2)
        self.assertAlmostEqual(ukazi[0]["p"]["y"], 0.5, places=2)

    def test_poteg_je_en_poteg(self):
        stran, ukazi = self._klikni([[0.25, 0.5], [0.75, 0.5]])
        self.assertEqual(stran, [])
        self.assertEqual([u["d"] for u in ukazi], ["input.swipe"])
        self.assertAlmostEqual(ukazi[0]["p"]["x1"], 0.25, places=2)
        self.assertAlmostEqual(ukazi[0]["p"]["x2"], 0.75, places=2)

    def test_klik_na_crni_rob_ni_dotik(self):
        """Stran bi klik zunaj slike prestavila na rob zaslona naprave; iz okna Controla tak klik ne gre nikamor."""
        stran, ukazi = self._klikni([[0.5, 0.05]])
        self.assertEqual((stran, ukazi), ([], []))

    def test_koordinate_so_delez_slike_ne_okna(self):
        # Slika 2:1 v oknu 4:3 zavzema srednji dve tretjini visine: 0,25 visine okna je 0,125 visine slike.
        _stran, ukazi = self._klikni([[0.5, 0.25]])
        self.assertEqual(len(ukazi), 1, ukazi)
        self.assertAlmostEqual(ukazi[0]["p"]["y"], 0.125, places=2)


if __name__ == "__main__":
    unittest.main()
