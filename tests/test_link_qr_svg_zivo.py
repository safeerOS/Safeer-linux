#!/usr/bin/env python3
"""Koda QR na strani Safeer Linka (assets/link/link.js, vstaviSvg) v pravem WebKitu.

Pregled 16. 10. 2026: SVG kode QR je stran vstavljala z innerHTML. SVG sicer narise program sam (python3-qrcode),
a niz s <script>, on* ali javascript: bi se izvedel v strani z mostom do zaledja. Zdaj ga stran razcleni kot
image/svg+xml in odstrani vse, kar lahko izvaja kodo. Preizkus pokaze, da prava koda QR ostane enaka in da se
nevaren SVG ne izvede. Potrebuje zaslon in WebKitGTK 6.0 (kot Safeer Control), zato se brez njiju preskoci.
"""

import json
import os
import re
import unittest

# Na ravni modula: tools/razdeli_teste.py preizkus tako uvrsti v skupino GTK 4 (CI: Ubuntu 24.04 z WebKitGTK 6.0).
try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import GLib, Gtk, WebKit
except (ImportError, ValueError):  # brez WebKitGTK 6.0 preizkusa ni
    GLib = Gtk = WebKit = None

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRAN_JS = os.path.join(KOREN, "assets", "link", "link.js")

NEVAREN = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 9 9">'
           '<script>window.__x.push("script")</script>'
           '<foreignObject><img xmlns="http://www.w3.org/1999/xhtml" src="x" onerror="window.__x.push(\'fo\')"/>'
           '</foreignObject>'
           '<a href="javascript:window.__x.push(\'a\')"><path d="M0,0H1V1H0z"/></a>'
           '<path id="ostane" onclick="window.__x.push(\'on\')" style="fill:red" fill="url(http://primer.invalid/x)" '
           'xlink:href="javascript:window.__x.push(\'xl\')" d="M1,1H2V2H1z"/>'
           '<animate attributeName="href" to="javascript:window.__x.push(\'anim\')"/>'
           '<set attributeName="onclick" to="window.__x.push(\'set\')"/></svg>')


def _funkcija() -> str:
    with open(STRAN_JS, encoding="utf-8") as f:
        vir = f.read()
    najdba = re.search(r"\n  var SVG_NS = .*?\n  function vstaviSvg\(.*?\n  }\n", vir, re.S)
    if not najdba:
        raise AssertionError("vstaviSvg ni v link.js")
    return najdba.group(0)


def _qr() -> str:
    from core import link_hub
    svg = link_hub.qr_svg("https://safeer.si/p#i=0123456789abcdef01234567&s=" + "0" * 32)
    return svg or ('<?xml version="1.0" encoding="UTF-8"?><svg width="41mm" height="41mm" viewBox="0 0 41 41" '
                   'xmlns="http://www.w3.org/2000/svg"><path d="M2,2H3V3H2z" id="qr-path" fill="#000000"/></svg>')


def stran() -> str:
    """Samostojna stran HTML, ki pozene vstaviSvg na primerih in izid zapise v <pre id="izid"> (JSON)."""
    primeri = {"qr": _qr(), "nevaren": NEVAREN, "html": "<html><body>x</body></html>",
               "brez_ns": '<svg viewBox="0 0 1 1"><path d="M0,0H1V1H0z"/></svg>', "pokvarjen": "<svg"}
    return """<!doctype html><html><head><meta charset="utf-8"></head><body><div id="okvir"><span>prej</span></div>
<pre id="izid"></pre><script>
window.__x = [];
%s
var primeri = %s, izid = {};
Object.keys(primeri).forEach(function (k) {
  var okvir = document.getElementById("okvir");
  okvir.innerHTML = "<span>prej</span>";
  var ok = vstaviSvg(okvir, primeri[k]);
  var svg = okvir.querySelector("svg");
  izid[k] = { ok: ok, prej: !!okvir.querySelector("span"), svg: !!svg && svg.namespaceURI === SVG_NS,
              viewBox: svg ? svg.getAttribute("viewBox") : null, oznake: svg ? svg.outerHTML.match(/<[a-zA-Z]+/g) : [],
              d: svg ? Array.prototype.map.call(svg.querySelectorAll("path"), function (p) { return p.getAttribute("d"); }) : [],
              atributi: svg ? Array.prototype.concat.apply([], Array.prototype.map.call(svg.querySelectorAll("*"),
                function (e) { return Array.prototype.map.call(e.attributes, function (a) { return a.name; }); })) : [] };
  if (svg) Array.prototype.forEach.call(svg.querySelectorAll("*"), function (e) {
    e.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
});
setTimeout(function () {
  izid.izvedeno = window.__x;
  document.getElementById("izid").textContent = JSON.stringify(izid);
}, 300);
</script></body></html>""" % (_funkcija(), json.dumps(primeri).replace("</", "<\\/"))


def preveri(test: unittest.TestCase, izid: dict) -> None:
    qr = izid["qr"]
    test.assertTrue(qr["ok"] and qr["svg"] and not qr["prej"])
    test.assertEqual(qr["viewBox"].split()[:2], ["0", "0"])
    pricakovano = re.findall(r' d="([^"]+)"', _qr())
    test.assertEqual(qr["d"], pricakovano, "koda QR se ne sme spremeniti")
    nevaren = izid["nevaren"]
    test.assertTrue(nevaren["ok"])
    test.assertEqual(nevaren["oznake"], ["<svg", "<path"])
    test.assertEqual(nevaren["d"], ["M1,1H2V2H1z"])
    test.assertEqual(sorted(nevaren["atributi"]), ["d", "id"])
    test.assertEqual(izid["izvedeno"], [])
    for k in ("html", "brez_ns", "pokvarjen"):
        test.assertFalse(izid[k]["ok"], k)
        test.assertTrue(izid[k]["prej"], k + ": okvir ostane nespremenjen")


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(WebKit, "potrebuje WebKitGTK 6.0")
class PreizkusQrSvgVWebKitu(unittest.TestCase):
    def test_qr_ostane_nevaren_svg_se_ne_izvede(self):
        Gtk.init()
        okno = Gtk.Window()
        pogled = WebKit.WebView()
        okno.set_child(pogled)
        okno.present()
        zanka = GLib.MainLoop()
        izid = {}

        def beri(*_a):
            def konec(v, rezultat):
                try:
                    izid["o"] = v.evaluate_javascript_finish(rezultat).to_string()
                except Exception as napaka:  # noqa: BLE001
                    izid["o"] = "napaka: %s" % napaka
                if izid["o"]:
                    zanka.quit()
            pogled.evaluate_javascript('document.getElementById("izid").textContent', -1, None, None, None, konec)
            return bool(not izid.get("o"))

        def nalozeno(v, dogodek):
            if dogodek == WebKit.LoadEvent.FINISHED:
                GLib.timeout_add(400, beri)

        pogled.connect("load-changed", nalozeno)
        pogled.load_html(stran(), "about:blank")
        GLib.timeout_add_seconds(20, zanka.quit)
        zanka.run()
        okno.destroy()
        self.assertTrue(izid.get("o"), "stran ni odgovorila")
        preveri(self, json.loads(izid["o"]))


if __name__ == "__main__":
    unittest.main()
