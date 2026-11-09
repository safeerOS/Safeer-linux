"""Izbor Debrid in ponudnik Usenet (CodeRabbit 9. 11. 2026): narisiDebrid ob prvem izrisu nalozi stanje ponudnika
(prej je do odprtja okna Viri kazal »Dodaj ponudnika«), unpNarisi po shranitvi ali odstranitvi takoj osvezi viden izbor.
Pravi funkciji iz os.js v node."""
import json
import os
import shutil
import subprocess
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _funkcija(js, ime):
    return "function %s(" % ime + js.split("  function %s(" % ime, 1)[1].split("\n  }\n", 1)[0] + "\n  }\n"


OKOLJE = r"""
function Seznam() { this.c = {}; }
Seznam.prototype.toggle = function (k, v) { this.c[k] = !!v; };
function El() { this.hidden = false; this.options = []; this.value = ""; this.textContent = ""; this.placeholder = "";
  this.classList = new Seznam(); this.atr = {}; }
El.prototype.add = function (o) { this.options.push(o); };
El.prototype.setAttribute = function (k, v) { this.atr[k] = v; };
Object.defineProperty(El.prototype, "innerHTML", { set: function () { this.options = []; } });
function Option(besedilo, vrednost) { this.text = besedilo; this.value = vrednost; }
var elementi = {};
function $(id) { return elementi[id] || (elementi[id] = new El()); }
function t(k) { return k; }
var odzivi = {}, klici = [];
function klic(ime, args) { klici.push(ime); return Promise.resolve(odzivi[ime]); }
function unpPozabiPonastavi() {}
function unpGumbi() {}
var UNP_SLABO = ["ne_velja"];
var debridStanje = null, debridNalagam = false, debridPrazno = 0;
var unp = { stanje: null, dela: false, nalagam: false };
function oznakaUsenet() {
  var o = $("mediaDebrid").options;
  for (var i = 0; i < o.length; i++) if (o[i].value === "usenet") return o[i].text;
  return null;
}
"""


class IzborUsenet(unittest.TestCase):
    def setUp(self):
        if not shutil.which("node"):
            raise unittest.SkipTest("node ni namescen")
        js = open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8").read()
        self.funkcije = _funkcija(js, "narisiDebrid") + _funkcija(js, "unpNarisi")

    def _node(self, koda):
        return json.loads(subprocess.run(["node", "-e", OKOLJE + self.funkcije + koda], capture_output=True, text=True,
                                         check=True, timeout=30).stdout)

    def test_shranjen_ponudnik_ob_prvem_izrisu(self):
        izid = self._node(r"""
        odzivi.mediaDebrid = { storitve: [] };
        odzivi.mediaUsenetPonudnik = { stanje: { vpisan: true, ime: "MojPonudnik", gostitelj: "news.example" } };
        narisiDebrid(true);
        setTimeout(function () { console.log(JSON.stringify([oznakaUsenet(), klici])); }, 20);
        """)
        self.assertEqual(izid[0], "MojPonudnik")
        self.assertEqual(izid[1].count("mediaUsenetPonudnik"), 1, "stanje ponudnika samo enkrat (brez zanke)")

    def test_po_odstranitvi_takoj_nova_oznaka(self):
        izid = self._node(r"""
        debridStanje = { storitve: [] };
        unp.stanje = { vpisan: true, ime: "MojPonudnik" };
        narisiDebrid(true);
        var prej = oznakaUsenet();
        unpNarisi({ vpisan: false }, true);
        var po = oznakaUsenet();
        $("mediaDebridPolje").hidden = true;
        unpNarisi({ vpisan: true, ime: "Drugi" }, true);       // skrit izbor se ne narise znova
        console.log(JSON.stringify([prej, po, oznakaUsenet(), klici]));
        """)
        self.assertEqual(izid[:3], ["MojPonudnik", "dodajPonudnikaUsenet", "dodajPonudnikaUsenet"])
        self.assertEqual(izid[3], [])


if __name__ == "__main__":
    unittest.main()
