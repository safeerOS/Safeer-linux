"""Nacin za kavc (pregled 5. 11. 2026): F8 - viden() izloci gumbe pod nedejavnim (inert) ali aria-hidden prednikom in s
prosojnostjo 0; F7 - premakni() brez cilja v smeri vrne false (puscica ostane strani). Prave funkcije iz kavc.js v node."""
import json
import os
import shutil
import subprocess
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _funkcija(js, ime):
    return "function %s(" % ime + js.split("  function %s(" % ime, 1)[1].split("\n  }\n", 1)[0] + "\n  }\n"


DOM = r"""
function El(ime, starsi, atr, slog, r) { this.ime = ime; this.parentElement = starsi || null; this.nodeType = 1;
  this.atr = atr || {}; this.slog = slog || {}; this.r = r || { left: 0, top: 0, width: 50, height: 20 };
  this.hidden = !!this.atr.hidden; this.disabled = false; }
El.prototype.getAttribute = function (k) { return k in this.atr ? this.atr[k] : null; };
El.prototype.closest = function (sel) {
  var deli = sel.split(",").map(function (x) { return x.trim(); });
  for (var n = this; n; n = n.parentElement) {
    if ((deli.indexOf("[hidden]") >= 0 && "hidden" in n.atr) || (deli.indexOf("[inert]") >= 0 && "inert" in n.atr) ||
        (deli.indexOf("[aria-hidden='true']") >= 0 && n.atr["aria-hidden"] === "true")) return n;
  }
  return null; };
El.prototype.getBoundingClientRect = function () { var r = this.r;
  return { left: r.left, top: r.top, width: r.width, height: r.height, right: r.left + r.width, bottom: r.top + r.height }; };
El.prototype.contains = function (o) { for (; o; o = o.parentElement) if (o === this) return true; return false; };
El.prototype.focus = function () { document.activeElement = this; };
El.prototype.scrollIntoView = function () {};
var window = { getComputedStyle: function (el) { return { visibility: el.slog.visibility || "visible",
  display: el.slog.display || "block", opacity: el.slog.opacity || "1" }; }, innerHeight: 1000 };
var document = { activeElement: null, body: null };
"""


class Izbor(unittest.TestCase):
    def setUp(self):
        if not shutil.which("node"):
            raise unittest.SkipTest("node ni namescen")
        self.js = open(os.path.join(KOREN, "assets", "os", "kavc.js"), encoding="utf-8").read()

    def _node(self, koda):
        return json.loads(subprocess.run(["node", "-e", koda], capture_output=True, text=True, check=True, timeout=30).stdout)

    def test_viden(self):
        koda = DOM + _funkcija(self.js, "viden") + r"""
        var telo = new El("body");
        var inert = new El("okno", telo, { inert: "" }), skrit = new El("okno", telo, { "aria-hidden": "true" });
        var prosojen = new El("okno", telo, {}, { opacity: "0" });
        console.log(JSON.stringify([viden(new El("g", telo)), viden(new El("g", inert)), viden(new El("g", skrit)),
                                    viden(new El("g", prosojen)), viden(new El("g", telo, {}, { opacity: "0" }))]));
        """
        self.assertEqual(self._node(koda), [True, False, False, False, False])

    def test_premakni_brez_cilja(self):
        koda = DOM + "".join(_funkcija(self.js, f) for f in ("viden", "sredina", "naslednji", "prvi", "izberi", "premakni")) + r"""
        var telo = new El("body"); document.body = telo;
        var a = new El("a", telo, {}, {}, { left: 0, top: 0, width: 50, height: 20 });
        var b = new El("b", telo, {}, {}, { left: 100, top: 0, width: 50, height: 20 });
        function kandidati() { return [a, b]; }
        a.focus();
        var desno = premakni("desno"), poDesno = document.activeElement === b;
        var spet = premakni("desno");                // za b ni nicesar vec desno
        console.log(JSON.stringify([desno, poDesno, spet, document.activeElement === b]));
        """
        self.assertEqual(self._node(koda), [True, True, False, True])


if __name__ == "__main__":
    unittest.main()
