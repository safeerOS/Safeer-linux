"""A3 (pregled 5. 11. 2026): plosca sporocil seznam zgradi znova (novo sporocilo, oznaka, izbris, iskanje) - fokus
ostane na istem gumbu iste vrstice in drsenje na istem mestu. Pravo skripto pozenemo v node z majhnim laznim DOM."""
import json
import os
import shutil
import subprocess
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOM = r"""
function Vozel(tag) { this.tagName = String(tag || "").toUpperCase(); this.children = []; this.atr = {}; this.parentNode = null;
  this._razredi = []; var self = this; this.style = {}; this.scrollTop = 0; this.poslusalci = {};
  this.classList = { add: function (c) { if (self._razredi.indexOf(c) < 0) self._razredi.push(c); },
                     toggle: function (c, da) { var i = self._razredi.indexOf(c); if (da === undefined) da = i < 0;
                       if (da && i < 0) self._razredi.push(c); if (!da && i >= 0) self._razredi.splice(i, 1); },
                     contains: function (c) { return self._razredi.indexOf(c) >= 0; } }; }
Object.defineProperty(Vozel.prototype, "className", { get: function () { return this._razredi.join(" "); },
  set: function (v) { this._razredi = String(v).split(/\s+/).filter(Boolean); } });
Object.defineProperty(Vozel.prototype, "textContent", { get: function () { return this._besedilo || ""; },
  set: function (v) { this.children.forEach(function (c) { c.parentNode = null; }); this.children = []; this._besedilo = v;
                      this.scrollTop = 0; } });
Object.defineProperty(Vozel.prototype, "innerHTML", { set: function () {}, get: function () { return ""; } });
Vozel.prototype.appendChild = function (o) { o.parentNode = this; this.children.push(o); return o; };
Vozel.prototype.setAttribute = function (k, v) { this.atr[k] = String(v); };
Vozel.prototype.getAttribute = function (k) { return k in this.atr ? this.atr[k] : null; };
Vozel.prototype.hasAttribute = function (k) { return k in this.atr; };
Vozel.prototype.addEventListener = function (v, f) { (this.poslusalci[v] = this.poslusalci[v] || []).push(f); };
Vozel.prototype.focus = function () { document.activeElement = this; };
Vozel.prototype.contains = function (o) { for (; o; o = o.parentNode) if (o === this) return true; return false; };
function ujema(v, sel) {
  var m = /^([a-z]*)(?:\.([\w-]+))?(?:\[([\w-]+)\])?$/.exec(sel);
  return (!m[1] || v.tagName === m[1].toUpperCase()) && (!m[2] || v.classList.contains(m[2])) && (!m[3] || v.hasAttribute(m[3]));
}
Vozel.prototype.querySelectorAll = function (sel) { var izid = [];
  (function hodi(v) { v.children.forEach(function (c) { if (ujema(c, sel)) izid.push(c); hodi(c); }); })(this); return izid; };
Vozel.prototype.querySelector = function (sel) { return this.querySelectorAll(sel)[0] || null; };
Vozel.prototype.closest = function (sel) { for (var v = this; v; v = v.parentNode) if (ujema(v, sel)) return v; return null; };
var idji = {};
["naslov", "iskanje", "novo", "vse", "zapri", "zavSporocila", "zavEposta", "seznam", "obvestilo"].forEach(function (i) {
  idji[i] = new Vozel(i === "seznam" ? "ul" : i === "iskanje" ? "input" : "button"); idji[i].value = ""; });
var document = { activeElement: null, documentElement: {}, visibilityState: "visible", addEventListener: function () {},
  getElementById: function (i) { return idji[i]; }, createElement: function (t) { return new Vozel(t); } };
var location = { search: "?jezik=sl" };
var kanal = { vrsta: "matrix", dejanja: ["prebrano", "neprebrano", "zvezdica", "brez_zvezdice", "izbrisi"] };
var pogovori = [1, 2, 3, 4].map(function (i) { return { id: "p" + i, kanal_id: "k", kanal: kanal, cas: "2026-11-0" + (5 - i),
  zadnje_sporocilo: "s" + i, neprebrano: i === 2 ? 1 : 0 }; });
var window = { SafeerOS: { klic: function (m) { return m === "sporocilaSeznam" ? { skupine: [{ oseba: { ime: "Ana" }, pogovori: pogovori }], kanali: [kanal] } : {}; } } };
"""


class Fokus(unittest.TestCase):
    def test_fokus_in_drsenje_ostaneta(self):
        if not shutil.which("node"):
            raise unittest.SkipTest("node ni namescen")
        skripta = open(os.path.join(KOREN, "assets", "os", "sporocila-plosca.js"), encoding="utf-8").read()
        koda = DOM + skripta + r"""
        setTimeout(function () {
          var seznam = idji.seznam, li = seznam.children[1];
          var gumbi = li.querySelectorAll("button");
          gumbi[1].focus();                          // prvo dejanje druge vrstice (»Oznaci kot prebrano«)
          seznam.scrollTop = 120;
          idji.iskanje.poslusalci.input[0]();        // narisi() znova
          var a = document.activeElement, novLi = a && a.closest("li[data-kljuc]");
          var izid = [novLi ? novLi.getAttribute("data-kljuc") : null, novLi ? novLi.querySelectorAll("button").indexOf(a) : -1,
                      seznam.scrollTop, novLi !== li];
          console.log(JSON.stringify(izid));
        }, 20);
        """
        izid = json.loads(subprocess.run(["node", "-e", koda], capture_output=True, text=True, check=True, timeout=30).stdout)
        self.assertEqual(izid, ["k\u0001p2", 1, 120, True])


if __name__ == "__main__":
    unittest.main()
