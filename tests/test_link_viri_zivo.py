#!/usr/bin/env python3
"""Stran Safeer Linka v pravem WebKitu: ko naprava iz kroga ni sprejeta zaradi virov (core/link_viri.py), uporabnik
to vidi v svojem jeziku - na napravi, ki nima virov (koliko jih je zavrnila), in na napravi, ki je bila zavrnjena
(ime druge naprave; pri poti zdoma pripis, zakaj prek releja). Lastnik, 18. 10. 2026: ne tihe zavrnitve.

Most je lazen (window.SafeerLink), stran in besedila so prava. Potrebuje zaslon in WebKitGTK 6.0.
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
window.SafeerLink = {
  stanje: function () { return JSON.stringify({znan: true, seznanjen: true, povezan: true, hub: "wss://192.168.0.2:8990",
                                               naprava: "Racunalnik", id: "n-1", vKrogu: true, clanKroga: true}); },
  naprave: function () { return "[]"; },
  poveziSe: function () {},
  jezik: function () { return %s; },
  globalLinkStanje: function () { return JSON.stringify({vhod: {vklopljeno: false, vrata: 48990},
      poti: [{id: "n-0123456789abcdef", ime: "Pisarna", pot: "rele", ms: null, napaka: "ni_virov"}]}); },
  viriStanje: function () { return JSON.stringify(%s); }
};
"""

STANJE_JS = """JSON.stringify({
  vidno: !document.getElementById("opozoriloViri").hidden,
  besedilo: document.getElementById("opozoriloViriBesedilo").textContent,
  poti: document.getElementById("seznamGlobalLink").textContent
})"""


def _preberi(jezik: str, viri) -> dict:
    Gtk.init()
    okno = Gtk.Window()
    upravitelj = WebKit.UserContentManager()
    upravitelj.add_script(WebKit.UserScript.new(MOST % (json.dumps(jezik), json.dumps(viri)),
                                                WebKit.UserContentInjectedFrames.TOP_FRAME,
                                                WebKit.UserScriptInjectionTime.START, None, None))
    pogled = WebKit.WebView(user_content_manager=upravitelj)
    okno.set_child(pogled)
    okno.set_default_size(900, 900)
    okno.present()
    zanka = GLib.MainLoop()
    izid = {}

    def prebrano(v, rezultat):
        try:
            izid.update(json.loads(v.evaluate_javascript_finish(rezultat).to_string()))
        except Exception as napaka:  # noqa: BLE001
            izid["napaka"] = str(napaka)
        zanka.quit()

    def nalozeno(_v, dogodek):
        if dogodek == WebKit.LoadEvent.FINISHED:
            GLib.timeout_add(700, lambda: pogled.evaluate_javascript(STANJE_JS, -1, None, None, None, prebrano) and False)

    pogled.connect("load-changed", nalozeno)
    pogled.load_uri("file://" + STRAN)
    GLib.timeout_add_seconds(30, zanka.quit)
    zanka.run()
    okno.destroy()
    return izid


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(WebKit, "potrebuje WebKitGTK 6.0")
class ViriNaStrani(unittest.TestCase):
    def test_ta_naprava_brez_deskriptorjev_slovensko(self):
        s = _preberi("sl", {"tu": {"razlog": "deskriptorji", "kje": "neposredno", "zavrnjenih": 7}, "drugi": []})
        self.assertTrue(s.get("vidno"), s)
        self.assertIn("sistemsko mejo hkrati odprtih povezav", s["besedilo"])
        self.assertIn("zavrnjenih: 7", s["besedilo"])
        self.assertNotIn("{", s["besedilo"])

    def test_druga_naprava_nas_ni_sprejela_nemsko(self):
        s = _preberi("de", {"tu": {}, "drugi": ["Pisarna"]})
        self.assertTrue(s.get("vidno"), s)
        self.assertIn("„Pisarna“", s["besedilo"])
        self.assertIn("Ressourcen", s["besedilo"])
        self.assertIn("keine freien Ressourcen für eine direkte Verbindung", s["poti"])

    def test_brez_pomanjkanja_ni_opozorila(self):
        s = _preberi("en", None)
        self.assertFalse(s.get("vidno"), s)


class MostStrani(unittest.TestCase):
    """core/safeer_link: stanje virov gre na stran, zavrnitev druge naprave pokaze obvestilo (enkrat na proces)."""

    def test_stanje_virov_in_obvestilo(self):
        from unittest import mock
        try:
            from core import link_viri, safeer_link
        except Exception as e:  # noqa: BLE001 - brez GTK4/WebKit
            self.skipTest("safeer_link: %s" % e)
        link_viri.ponastavi()
        self.addCleanup(link_viri.ponastavi)
        self.assertIsNone(safeer_link.SafeerLink._viri_stanje())
        with mock.patch.object(link_viri, "POSLUSALCI", []), mock.patch.object(link_viri, "POSLUSALCI_DRUGIH", []):
            link_viri.zabelezi(link_viri.POMNILNIK, "naprava")
            link_viri.zavrnila_druga("Pisarna")
        st = safeer_link.SafeerLink._viri_stanje()
        self.assertEqual((st["tu"]["razlog"], st["drugi"]), (link_viri.POMNILNIK, ["Pisarna"]))
        poslano, odzivi = [], []
        lazni = mock.Mock(_jezik=lambda: "it", _aplikacija=lambda: None, _odziv=lambda v, p: odzivi.append(v))
        with mock.patch("core.obvestila.poslji", lambda naslov, telo, ident, app=None: poslano.append((naslov, telo))):
            safeer_link.SafeerLink._obvesti_zavrnitev_druge(lazni, "Pisarna")
        self.assertEqual(poslano, [link_viri.besedilo(link_viri.KODA, "it", ime="Pisarna")])
        self.assertEqual(odzivi, ["viri"])


if __name__ == "__main__":
    unittest.main()
