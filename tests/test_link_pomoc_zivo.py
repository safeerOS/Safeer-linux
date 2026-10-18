#!/usr/bin/env python3
"""»Pomagaj drugim napravam v Linku pri povezavi« na strani Safeer Linka v pravem WebKitu (pregled 18. 10. 2026).

Ob seznanitvi stran enkrat vprasa (privzeto da); pricakovano dejanje »Da, pomagaj« ima fokus, da je na daljincu dovolj
en pritisk na V redu. Odgovor gre v most (nastaviPomoc) in vprasanje izgine; stikalo ostane v razdelku »Povezava
zdoma«. Most je lazen (window.SafeerLink), stran in besedila so prava. Potrebuje zaslon in WebKitGTK 6.0.
"""

import json
import os
import unittest

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import GLib, Gtk, WebKit
except (ImportError, ValueError):  # brez WebKitGTK 6.0 preizkusa ni
    GLib = Gtk = WebKit = None

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRAN = os.path.join(KOREN, "assets", "link", "index.html")

MOST = """
window.__klici = [];
window.__pomoc = %s;
window.SafeerLink = {
  stanje: function () { return JSON.stringify({znan: true, seznanjen: true, povezan: true, hub: "wss://192.168.0.2:8990",
                                               naprava: "Racunalnik", id: "n-1", vKrogu: true, clanKroga: true}); },
  naprave: function () { return "[]"; },
  poveziSe: function () {},
  jezik: function () { return "sl"; },
  globalLinkStanje: function () { return "null"; },
  pomocStanje: function () { return JSON.stringify(window.__pomoc); },
  nastaviPomoc: function (v) { window.__klici.push(["nastaviPomoc", v]); window.__pomoc = {vklopljeno: !!v, vprasano: true};
                               setTimeout(function () { window.safeerLinkOdziv("pomoc", {}); }, 0); }
};
"""

STANJE_JS = """JSON.stringify({
  fokus: document.activeElement ? document.activeElement.id : "",
  vprasanje: !document.getElementById("panelPomocVprasanje").hidden,
  naslov: document.getElementById("pomocVprasanjeNaslov").textContent,
  stikalo: !document.getElementById("pomocVrstica").hidden,
  vklopljeno: document.getElementById("glPomoc").checked,
  klici: window.__klici
})"""


def _zazeni(pomoc: dict, koraki) -> list:
    """Nalozi stran z laznim mostom; po vsakem koraku (JS) prebere stanje. Vrne seznam stanj."""
    Gtk.init()
    okno = Gtk.Window()
    upravitelj = WebKit.UserContentManager()
    upravitelj.add_script(WebKit.UserScript.new(MOST % json.dumps(pomoc), WebKit.UserContentInjectedFrames.TOP_FRAME,
                                                WebKit.UserScriptInjectionTime.START, None, None))
    pogled = WebKit.WebView(user_content_manager=upravitelj)
    okno.set_child(pogled)
    okno.set_default_size(900, 900)
    okno.present()
    zanka = GLib.MainLoop()
    stanja = []
    vrsta = [None] + list(koraki)

    def naslednji():
        if not vrsta:
            zanka.quit()
            return False
        korak = vrsta.pop(0)

        def prebrano(v, rezultat):
            try:
                stanja.append(json.loads(v.evaluate_javascript_finish(rezultat).to_string()))
            except Exception as napaka:  # noqa: BLE001
                stanja.append({"napaka": str(napaka)})
            GLib.timeout_add(300, naslednji)

        def po_koraku(*_a):
            pogled.evaluate_javascript(STANJE_JS, -1, None, None, None, prebrano)
        if korak:
            pogled.evaluate_javascript(korak, -1, None, None, None, lambda *_a: GLib.timeout_add(300, po_koraku))
        else:
            po_koraku()
        return False

    def nalozeno(_v, dogodek):
        if dogodek == WebKit.LoadEvent.FINISHED:
            GLib.timeout_add(700, naslednji)

    pogled.connect("load-changed", nalozeno)
    pogled.load_uri("file://" + STRAN)
    GLib.timeout_add_seconds(30, zanka.quit)
    zanka.run()
    okno.destroy()
    return stanja


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(WebKit, "potrebuje WebKitGTK 6.0")
class PomocDrugimNapravam(unittest.TestCase):
    def test_vprasanje_ob_seznanitvi_fokus_na_da_in_odgovor(self):
        stanja = _zazeni({"vklopljeno": True, "vprasano": False},
                         ['document.getElementById("gumbPomocNe").click()'])
        self.assertEqual(len(stanja), 2, stanja)
        prej, potem = stanja
        self.assertTrue(prej["vprasanje"], prej)
        self.assertEqual(prej["naslov"], "Pomagaj drugim napravam v Linku pri povezavi?")
        self.assertEqual(prej["fokus"], "gumbPomocDa", "pricakovano dejanje ima fokus (daljinec)")
        self.assertTrue(prej["stikalo"] and prej["vklopljeno"], "privzeto vklopljeno")
        self.assertEqual(potem["klici"], [["nastaviPomoc", False]])
        self.assertFalse(potem["vprasanje"], "vprasanje se ne ponovi")
        self.assertFalse(potem["vklopljeno"])

    def test_ze_vprasan_samo_stikalo(self):
        stanja = _zazeni({"vklopljeno": False, "vprasano": True},
                         ['var s = document.getElementById("glPomoc"); s.checked = true;'
                          ' s.dispatchEvent(new Event("change"));'])
        prej, potem = stanja
        self.assertFalse(prej["vprasanje"])
        self.assertTrue(prej["stikalo"])
        self.assertFalse(prej["vklopljeno"])
        self.assertEqual(potem["klici"], [["nastaviPomoc", True]])



class MostStrani(unittest.TestCase):
    """Most strani (core/safeer_link): izbira se shrani, Hub sosedom takoj poslje nov seznam, stran se osvezi."""

    def test_nastavi_pomoc(self):
        import types
        from unittest import mock
        try:
            from core import link_mesh, safeer_link
        except Exception as e:  # noqa: BLE001 - brez GTK4/WebKit
            self.skipTest("safeer_link: %s" % e)
        hub = mock.Mock()
        odzivi = []
        lazni = types.SimpleNamespace(_hub_gostitelj=types.SimpleNamespace(streznik=types.SimpleNamespace(hub=hub)),
                                      _odziv=lambda vrsta, _p: odzivi.append(vrsta))
        with mock.patch.object(link_mesh, "shrani_pomoc") as shrani:
            safeer_link.SafeerLink._nastavi_pomoc(lazni, False)
        shrani.assert_called_once_with(False)
        hub.osvezi_pomoc.assert_called_once_with()
        self.assertEqual(odzivi, ["pomoc"])
        with open(safeer_link.__file__, encoding="utf-8") as f:
            vir = f.read()
        for kos in ('pomocStanje: function ()', 'nastaviPomoc: function (vklop)', '"pomoc": self._pomoc_stanje()',
                    '"nastaviPomoc": lambda: self._v_ozadju('):
            self.assertIn(kos, vir)

    def test_besedila_v_vseh_jezikih(self):
        with open(os.path.join(KOREN, "assets", "link", "link.js"), encoding="utf-8") as f:
            js = f.read()
        blok = js.split("var BESEDILA_POMOC = {", 1)[1].split("\n  };", 1)[0]
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            del_ = blok.split("\n    %s: {" % jezik, 1)[1].split("\n    }", 1)[0]
            for kljuc in ("pomocIme", "pomocVprasanje", "pomocOpis", "pomocDa", "pomocNe"):
                self.assertIn(kljuc + ":", del_, (jezik, kljuc))


if __name__ == "__main__":
    unittest.main()
