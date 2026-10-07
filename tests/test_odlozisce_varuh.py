"""Varuh odložišča: Ctrl+C brez izbranega besedila ne sme izprazniti odložišča.

WebKitGTK (izmerjeno na 2.52.6) ob ukazu Kopiraj brez izbora v odložišče zapiše prazno vsebino. Varuh
(core/odlozisce_varuh.py) ob dogodku copy to prekliče. Tu preverimo:
  - odločanje (node, lažno okno): kdaj varuh prekliče in kdaj se umakne (izbor, polje za vnos, stran z lastnim
    kopiranjem, zaprta senca, slika);
  - vrstni red: varuh teče za poslušalci strani, tudi ob drugem in tretjem dogodku;
  - vgradnjo: svoj svet skript, vsi okviri, začetek nalaganja; vsi pogledi WebKit v paketu ga dobijo.
Da prazno kopiranje odložišče v resnici pusti pri miru, se da izmeriti samo v živem pogledu (zapisnik kroga).
"""
import json
import os
import re
import shutil
import subprocess
import unittest
from unittest import mock

from core import odlozisce_varuh

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()

OGRODJE = r"""
var assert = require("assert");
function Okno() {
  var zajem = [], vzpon = [];
  var dok = { activeElement: { nodeType: 1, tagName: "BODY" }, designMode: "off", contentType: "text/html" };
  var okno = {
    _dok: dok, _zajem: zajem, _vzpon: vzpon,
    _izbor: { type: "None", rangeCount: 0, isCollapsed: true },
    getSelection: function () {
      var i = okno._izbor;
      if (i && !Object.prototype.hasOwnProperty.call(i, "toString")) i.toString = function () { return ""; };
      return i;
    },
    addEventListener: function (vrsta, fn, o) {
      assert.strictEqual(vrsta, "copy");
      var seznam = (o === true || (o && o.capture === true)) ? zajem : vzpon;
      if (seznam.some(function (x) { return x.fn === fn; })) return;      // isti poslusalec se ne podvoji (DOM)
      seznam.push({ fn: fn, once: !!(o && o.once) });
    },
    // Razposlje dogodek kot DOM: zajem na oknu, poslusalci strani na cilju/dokumentu, vzpon na oknu (seznam ob vstopu v fazo).
    poslji: function (e, stran) {
      e = Object.assign({ defaultPrevented: false, target: dok.activeElement, klicev: 0,
        preventDefault: function () { this.defaultPrevented = true; this.klicev++; },
        composedPath: function () { return [this.target]; } }, e || {});
      zajem.slice().forEach(function (x) { x.fn.call(okno, e); });
      if (stran) stran(e);
      vzpon.slice().forEach(function (x) { if (x.once) vzpon.splice(vzpon.indexOf(x), 1); x.fn.call(okno, e); });
      return e;
    },
  };
  return okno;
}
function zazeni(okno) { (new Function("window", "document", SKRIPTA))(okno, okno._dok); return okno; }
function el(ime, dodatno) { return Object.assign({ nodeType: 1, tagName: ime }, dodatno || {}); }
"""


@unittest.skipUnless(shutil.which("node"), "node ni namescen")
class Odlocanje(unittest.TestCase):
    def _node(self, koda):
        subprocess.run(["node", "-e", "var SKRIPTA = %s;\n%s\n%s" % (json.dumps(odlozisce_varuh.SKRIPTA), OGRODJE, koda)],
                       check=True, timeout=60)

    def test_brez_izbora_preklice(self):
        self._node(r"""
var o = zazeni(Okno());
assert.strictEqual(o.poslji().defaultPrevented, true);                        // nic izbranega, fokus na strani
o._izbor = { type: "Caret", rangeCount: 1, isCollapsed: true };
assert.strictEqual(o.poslji().defaultPrevented, true);                        // kazalka v besedilu strani
o._dok.activeElement = el("BUTTON");
assert.strictEqual(o.poslji().defaultPrevented, true);                        // fokus na gumbu
o._dok.activeElement = el("INPUT", { type: "checkbox" });
assert.strictEqual(o.poslji().defaultPrevented, true);                        // potrditveno polje ni polje za besedilo
o._dok.activeElement = null;
assert.strictEqual(o.poslji({ target: null }).defaultPrevented, true);
""")

    def test_izbor_in_polja_pusti_pri_miru(self):
        self._node(r"""
var o = zazeni(Okno());
o._izbor = { type: "Range", rangeCount: 1, isCollapsed: false };
assert.strictEqual(o.poslji().defaultPrevented, false);                       // izbrano besedilo kopira brskalnik
o._izbor = { type: "Caret", rangeCount: 1, isCollapsed: false };              // izbor brez besedila (slika): ne ugibamo
assert.strictEqual(o.poslji().defaultPrevented, false);
o._izbor = { type: "None", rangeCount: 0, isCollapsed: true };
[el("INPUT", { type: "text" }), el("INPUT", { type: "" }), el("INPUT", {}), el("input", { type: "SEARCH" }),
 el("TEXTAREA"), el("DIV", { isContentEditable: true })].forEach(function (polje) {
  o._dok.activeElement = polje;
  assert.strictEqual(o.poslji().defaultPrevented, false, polje.tagName + " " + polje.type);
});
o._dok.activeElement = el("BODY");
assert.strictEqual(o.poslji({ target: el("TEXTAREA") }).defaultPrevented, false);   // cilj dogodka je polje
assert.strictEqual(o.poslji({ target: el("DIV"), composedPath: function () { return [el("INPUT", { type: "text" })]; } })
  .defaultPrevented, false);                                                       // polje v odprti senci
o._dok.designMode = "on";
assert.strictEqual(o.poslji().defaultPrevented, false);                       // cel dokument je urejevalnik
o._dok.designMode = "off"; o._dok.contentType = "image/png";
assert.strictEqual(o.poslji().defaultPrevented, false);                       // samostojna slika: Kopiraj kopira sliko
o._dok.contentType = "text/html";
assert.strictEqual(o.poslji().defaultPrevented, true);
""")

    def test_izbor_v_senci_po_besedilu(self):
        # Izbor navadnega besedila v senci je navzven videti strnjen (izmerjeno 7. 10. 2026 na 2.52.6: type=Range,
        # isCollapsed=true, String(izbor) = izbrano besedilo). Vrsta izbora je lastnost izdaje pogona; besedilo pove resnico.
        self._node(r"""
var o = zazeni(Okno());
o._izbor = { type: "None", rangeCount: 0, isCollapsed: true, toString: function () { return "gama"; } };
assert.strictEqual(o.poslji().defaultPrevented, false);
o._izbor = { type: "Caret", rangeCount: 1, isCollapsed: true, toString: function () { return "delta" } };
assert.strictEqual(o.poslji().defaultPrevented, false);
o._izbor = { type: "Caret", rangeCount: 1, isCollapsed: true, toString: function () { return ""; } };
assert.strictEqual(o.poslji().defaultPrevented, true);                        // kazalka brez besedila: ni kaj kopirati
o._izbor = { type: "None", rangeCount: 0, isCollapsed: true, toString: function () { throw new Error("pokvarjen"); } };
assert.strictEqual(o.poslji().defaultPrevented, true);                        // izjema ne podre varuha
""")

    def test_senca(self):
        self._node(r"""
var o = zazeni(Okno());
// Odprta senca: gledamo element, ki ima fokus v njej.
o._dok.activeElement = el("MOJ-OBRAZEC", { shadowRoot: { activeElement: el("INPUT", { type: "text" }) } });
assert.strictEqual(o.poslji().defaultPrevented, false);
o._dok.activeElement = el("MOJ-OBRAZEC", { shadowRoot: { activeElement: el("BUTTON") } });
assert.strictEqual(o.poslji().defaultPrevented, true);
o._dok.activeElement = el("MOJ-OBRAZEC", { shadowRoot: { activeElement: el("DRUG-EL", { shadowRoot: { activeElement: el("TEXTAREA") } }) } });
assert.strictEqual(o.poslji().defaultPrevented, false);
// Lasten element brez dostopne sence: morda zaprta senca s poljem - ne posegamo.
o._dok.activeElement = el("MOJ-OBRAZEC", { shadowRoot: null });
assert.strictEqual(o.poslji().defaultPrevented, false);
o._dok.activeElement = el("BODY");
assert.strictEqual(o.poslji({ target: el("X-POLJE", { shadowRoot: null }) }).defaultPrevented, false);
""")

    def test_stran_z_lastnim_kopiranjem(self):
        self._node(r"""
var o = zazeni(Okno());
// Stran (preglednica, risalnik) dogodek obdela sama na dokumentu: varuh ne klice preventDefault se enkrat.
var e = o.poslji(null, function (d) { d.podatki = "LASTNA-KOPIJA"; d.preventDefault(); });
assert.strictEqual(e.klicev, 1);
assert.strictEqual(e.podatki, "LASTNA-KOPIJA");
// Poslusalec strani na oknu, dodan po nalaganju: varuh mora priti na vrsto ZA njim (vsakic znova).
var vrstni = [];
o.addEventListener("copy", function (d) { vrstni.push("stran:" + d.defaultPrevented); });
for (var i = 0; i < 3; i++) {
  e = o.poslji();
  assert.strictEqual(e.defaultPrevented, true);
  assert.strictEqual(e.klicev, 1);
}
assert.deepStrictEqual(vrstni, ["stran:false", "stran:false", "stran:false"]);
// Stran, ki dogodek ustavi (stopPropagation), varuha ne poklice; naslednji dogodek gre spet skozenj.
assert.strictEqual(o._vzpon.length, 1);          // med dogodki je na oknu samo poslusalec strani
""")

    def test_dvojna_vgradnja_ne_podvoji(self):
        # Sorodni pogledi si delijo upravitelja vsebine: skripta se lahko vgradi veckrat.
        self._node(r"""
var o = Okno(); zazeni(o); zazeni(o); zazeni(o);
assert.strictEqual(o._zajem.length, 1);
var e = o.poslji();
assert.strictEqual(e.klicev, 1);
""")


class _LazniWebKit:
    class UserContentInjectedFrames:
        ALL_FRAMES = "vsi"
        TOP_FRAME = "glavni"

    class UserScriptInjectionTime:
        START = "zacetek"
        END = "konec"


class Vgradnja(unittest.TestCase):
    def test_svoj_svet_vsi_okviri_zacetek(self):
        W = mock.MagicMock()
        W.UserContentInjectedFrames = _LazniWebKit.UserContentInjectedFrames
        W.UserScriptInjectionTime = _LazniWebKit.UserScriptInjectionTime
        upravitelj = mock.MagicMock()
        self.assertTrue(odlozisce_varuh.dodaj(W, upravitelj))
        W.UserScript.new_for_world.assert_called_once_with(
            odlozisce_varuh.SKRIPTA, "vsi", "zacetek", odlozisce_varuh.SVET, None, None)
        upravitelj.add_script.assert_called_once_with(W.UserScript.new_for_world.return_value)

    def test_brez_svetov_gre_v_glavnega(self):
        W = mock.MagicMock()
        W.UserContentInjectedFrames = _LazniWebKit.UserContentInjectedFrames
        W.UserScriptInjectionTime = _LazniWebKit.UserScriptInjectionTime
        W.UserScript.new_for_world.side_effect = AttributeError("ni svetov")
        upravitelj = mock.MagicMock()
        self.assertTrue(odlozisce_varuh.dodaj(W, upravitelj))
        W.UserScript.assert_called_once_with(odlozisce_varuh.SKRIPTA, "vsi", "zacetek", None, None)
        upravitelj.add_script.assert_called_once_with(W.UserScript.return_value)

    def test_napaka_ne_podre_pogleda(self):
        W = mock.MagicMock()
        upravitelj = mock.MagicMock()
        upravitelj.add_script.side_effect = RuntimeError("ni slo")
        self.assertFalse(odlozisce_varuh.dodaj(W, upravitelj))

    def test_skripta_ne_bere_odlozisca_in_ne_poslja(self):
        s = odlozisce_varuh.SKRIPTA
        for prepovedano in ("clipboardData", "navigator.clipboard", "fetch(", "XMLHttpRequest", "postMessage", "getData"):
            self.assertNotIn(prepovedano, s, prepovedano)

    def test_modul_je_v_tovorih(self):
        # Seznama modulov v tovorih Safeer OS in Control sta rocna: brez modula uvoz v namesceni aplikaciji pade.
        # (Safeer Browser kopira celo mapo core.)
        for skripta in ("install_os_payload.sh", "install_control_payload.sh"):
            self.assertRegex(beri("packaging", skripta), re.compile(r"for modul in [^;]*\bodlozisce_varuh\b[^;]*; do", re.S), skripta)
        self.assertIn('"$ROOT/core"', beri("packaging", "install_payload.sh"))

    def test_vsi_pogledi_ga_dobijo(self):
        # Lupina Safeer OS in medijski pogled; vgrajeni brskalnik; Safeer Browser (vsi pogledi gredo skozi
        # setup_webview_settings); okno Safeer Link in gledalec deljenega zaslona v Controlu.
        self.assertGreaterEqual(beri("safeer_os.py").count("odlozisce_varuh.dodaj(WebKit2, upravitelj)"), 2)
        self.assertIn("odlozisce_varuh.dodaj(W, upravitelj)", beri("core", "os_splet.py"))
        mint = beri("safeer_mint.py")
        nastavitve = mint[mint.index("    def setup_webview_settings(self, webview):"):]
        nastavitve = nastavitve[:nastavitve.index("\n    def ", 10)]
        self.assertIn("odlozisce_varuh.dodaj(WebKit2, webview.get_user_content_manager())", nastavitve)
        self.assertIn("odlozisce_varuh.dodaj(WebKit2, upravitelj)", beri("safeer_control.py"))
        self.assertIn("odlozisce_varuh.dodaj(WebKit2, upravitelj)", beri("core", "safeer_link.py"))
        # Vsak nov pogled v Safeer Browserju gre skozi setup_webview_settings (zavihki, stranska vrstica, tipkovnica).
        pogledov = mint.count("WebKit2.WebView.new_with_context(") + mint.count("WebKit2.WebView.new_with_related_view(")
        self.assertGreaterEqual(mint.count("self.setup_webview_settings("), 3)
        self.assertEqual(pogledov, 4, "nov pogled WebKit v safeer_mint.py: preveri, da dobi varuha odlozisca")


if __name__ == "__main__":
    unittest.main()
