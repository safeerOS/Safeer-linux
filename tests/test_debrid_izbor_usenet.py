"""Izbirnik virov Medijskega centra kot TV (lastnik 10. 11. 2026; TV GlasbaActivity, izbira »debrid«): ⚡ storitve,
»⚡ Usenet«, »⚡ Vsi viri«, »Brez«, »Nastavitve«. »⚡ Usenet« FILTRIRA mrezo (ukaz jedru »izbira«, mreza se nalozi znova);
okno Viri se odpre samo, ce ponudnika se ni (»Dodaj ponudnika«). Stanje ponudnika se nalozi ob prvem izrisu
(CodeRabbit 9. 11. 2026). Prave funkcije iz os.js in besedila iz besedila.js v node."""
import json
import os
import shutil
import subprocess
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: TV res/values-*/viri_strings.xml, os_debrid_izbira_vse (oznaka »⚡ Vsi viri« v izbirniku TV).
TV_VSI_VIRI = {"sl": "Vsi viri", "en": "All sources", "de": "Alle Quellen", "es": "Todas las fuentes",
               "fr": "Toutes les sources", "it": "Tutte le fonti"}


def _funkcija(js, ime):
    return "function %s(" % ime + js.split("  function %s(" % ime, 1)[1].split("\n  }\n", 1)[0] + "\n  }\n"


OKOLJE = r"""
function Seznam() { this.c = {}; }
Seznam.prototype.toggle = function (k, v) { this.c[k] = !!v; };
function El() { this.hidden = false; this.options = []; this.value_ = ""; this.textContent = ""; this.placeholder = "";
  this.classList = new Seznam(); this.atr = {}; }
El.prototype.add = function (o) { this.options.push(o); };
El.prototype.setAttribute = function (k, v) { this.atr[k] = v; };
El.prototype.scrollIntoView = function (o) { pomik.push(o); };
El.prototype.focus = function () { fokus.push(this); };
Object.defineProperty(El.prototype, "innerHTML", { set: function () { this.options = []; this.value_ = ""; } });
// Kot <select>: vrednost, ki je ni med moznostmi, ne izbere nicesar (selectedIndex -1).
Object.defineProperty(El.prototype, "value", {
  get: function () { return this.value_; },
  set: function (v) { this.value_ = this.options.some(function (o) { return o.value === v; }) ? v : ""; this.izbrano = this.options.map(function (o) { return o.value; }).indexOf(this.value_); } });
Object.defineProperty(El.prototype, "selectedIndex", { get: function () {
  var v = this.value_; return this.options.map(function (o) { return o.value; }).indexOf(v); } });
function Option(besedilo, vrednost) { this.text = besedilo; this.value = vrednost; }
var elementi = {}, pomik = [], fokus = [];
function $(id) { return elementi[id] || (elementi[id] = new El()); }
var window = { matchMedia: function (q) { return { matches: zmanjsano && q.indexOf("reduce") >= 0 }; } };
var zmanjsano = false;
""" + "%s" + r"""
var jezik = "sl";
function t(k, z) { var b = BESEDILA_OS[jezik][k]; if (b == null) b = BESEDILA_OS.en[k]; if (b == null) b = k;
  if (z) Object.keys(z).forEach(function (x) { b = b.split("{" + x + "}").join(z[x]); }); return b; }
var odzivi = {}, klici = [], odprto = [];
function klic(ime, args) { klici.push([ime, args]); return Promise.resolve(odzivi[ime]); }
function unpPozabiPonastavi() {}
function unpGumbi() {}
function odpriDebrid() { odprto.push("debrid"); }
function odpriKatViri() { odprto.push("viri"); }
function katVidno() { return true; }
function naloziKatalog() { odprto.push("katalog"); }
var kat = { filter: "film" };
var UNP_SLABO = ["ne_velja"];
var debridStanje = null, debridNalagam = false, debridPrazno = 0;
var unp = { stanje: null, dela: false, nalagam: false };
function moznosti() { return $("mediaDebrid").options.map(function (o) { return [o.value, o.text]; }); }
function izpisi(x) { setTimeout(function () { console.log(JSON.stringify(x())); }, 20); }
"""

TORBOX = '{ id: "torbox", ime: "TorBox", kljuc: true }'


class IzborUsenet(unittest.TestCase):
    def setUp(self):
        if not shutil.which("node"):
            raise unittest.SkipTest("node ni namescen")
        js = open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8").read()
        self.funkcije = "".join(_funkcija(js, ime) for ime in ("narisiDebrid", "unpNarisi", "zmanjsanoGibanje", "izbranDebrid"))
        self.besedila = open(os.path.join(KOREN, "assets", "os", "besedila.js"), encoding="utf-8").read()

    def _node(self, koda):
        okolje = OKOLJE % self.besedila
        # Besedila so dolga (vec kot meja ukazne vrstice): koda gre po standardnem vhodu.
        izid = subprocess.run(["node", "-"], input=okolje + self.funkcije + koda, capture_output=True, text=True, timeout=30)
        self.assertEqual(izid.returncode, 0, izid.stderr[-2000:])
        return json.loads(izid.stdout)

    def test_moznosti_in_vrstni_red_kot_tv(self):
        izid = self._node(r"""
        debridStanje = { storitve: [%s], aktivna: "torbox", usenet_lastni: true, usenet_izbran: false };
        unp.stanje = { vpisan: true, ime: "Moj" };
        narisiDebrid(true);
        izpisi(function () { return [moznosti(), $("mediaDebrid").value]; });
        """ % TORBOX)
        self.assertEqual(izid[0], [["torbox", "⚡ TorBox"], ["usenet", "⚡ Usenet"], ["vsi", "⚡ Vsi viri"],
                                   ["brez", "Brez debrida"], ["nastavitve", izid[0][4][1]]])
        self.assertEqual(izid[1], "torbox")

    def test_vsi_viri_v_vseh_jezikih(self):
        for jez, tv in TV_VSI_VIRI.items():
            izid = self._node(r"""
            jezik = "%s";
            debridStanje = { storitve: [%s], aktivna: "torbox", usenet_lastni: true, usenet_izbran: true };
            unp.stanje = { vpisan: true };
            narisiDebrid(true);
            izpisi(function () { return [moznosti()[2], $("mediaDebrid").value]; });
            """ % (jez, TORBOX))
            self.assertEqual(izid[0], ["vsi", "⚡ " + tv], jez)
            self.assertEqual(izid[1], "vsi", jez)                     # izbran Usenet + storitev = Vsi viri

    def test_izbran_samo_usenet(self):
        izid = self._node(r"""
        debridStanje = { storitve: [], aktivna: "", usenet_lastni: true, usenet_izbran: true };
        unp.stanje = { vpisan: true };
        narisiDebrid(true);
        izpisi(function () { return [moznosti().map(function (o) { return o[0]; }), $("mediaDebrid").value]; });
        """)
        self.assertEqual(izid, [["usenet", "nastavitve"], "usenet"])

    def test_usenet_filtrira_ne_odpre_virov(self):
        izid = self._node(r"""
        odzivi.mediaDebrid = { storitve: [%s], aktivna: "", usenet_lastni: true, usenet_izbran: true };
        debridStanje = { storitve: [%s], aktivna: "torbox", usenet_lastni: true };
        unp.stanje = { vpisan: true };
        izbranDebrid("usenet");
        izpisi(function () { return [klici, odprto, $("mediaDebrid").value]; });
        """ % (TORBOX, TORBOX))
        self.assertEqual(izid[0], [["mediaDebrid", ["izbira", "usenet"]]])
        self.assertEqual(izid[1], ["katalog"])                     # mreza znova (filter), okno Viri NE
        self.assertEqual(izid[2], "usenet")

    def test_brez_in_vsi_ukaza(self):
        izid = self._node(r"""
        odzivi.mediaDebrid = { storitve: [%s], aktivna: "torbox", usenet_lastni: true };
        debridStanje = odzivi.mediaDebrid; unp.stanje = { vpisan: true };
        izbranDebrid("brez"); izbranDebrid("vsi"); izbranDebrid("torbox");
        izpisi(function () { return klici.map(function (k) { return k[1]; }); });
        """ % TORBOX)
        self.assertEqual(izid, [["izbira", ""], ["izbira", "vsi"], ["izbira", "torbox"]])

    def test_brez_ponudnika_dodaj_odpre_vire(self):
        izid = self._node(r"""
        debridStanje = { storitve: [], usenet_lastni: false };
        unp.stanje = { vpisan: false };
        narisiDebrid(true);
        var m = moznosti().map(function (o) { return o[0]; });
        zmanjsano = true;
        izbranDebrid("dodaj_usenet");
        izpisi(function () { return [m, odprto, klici, pomik]; });
        """)
        self.assertEqual(izid[0], ["", "dodaj_usenet", "nastavitve"])
        self.assertEqual(izid[1], ["viri"])
        self.assertEqual(izid[2], [])
        self.assertEqual(izid[3][0]["behavior"], "auto")             # zmanjsano gibanje: brez gladkega drsenja

    def test_shranjen_ponudnik_ob_prvem_izrisu(self):
        izid = self._node(r"""
        odzivi.mediaDebrid = { storitve: [], usenet_lastni: true };
        odzivi.mediaUsenetPonudnik = { stanje: { vpisan: true, ime: "MojPonudnik", gostitelj: "news.example" } };
        narisiDebrid(true);
        izpisi(function () { return [moznosti().map(function (o) { return o[1]; }),
                                     klici.map(function (k) { return k[0]; })]; });
        """)
        self.assertEqual(izid[0][0], "⚡ Usenet")
        self.assertEqual(izid[1].count("mediaUsenetPonudnik"), 1, "stanje ponudnika samo enkrat (brez zanke)")

    def test_po_odstranitvi_ponudnika_znova_stanje_jedra(self):
        izid = self._node(r"""
        debridStanje = { storitve: [], usenet_lastni: true };
        unp.stanje = { vpisan: true, ime: "MojPonudnik" };
        narisiDebrid(true);
        var prej = moznosti().map(function (o) { return o[0]; });
        odzivi.mediaDebrid = { storitve: [], usenet_lastni: false };
        unpNarisi({ vpisan: false }, true);
        izpisi(function () { return [prej, moznosti().map(function (o) { return o[0]; }),
                                     klici.map(function (k) { return k[0]; })]; });
        """)
        self.assertEqual(izid[0], ["usenet", "nastavitve"])
        self.assertEqual(izid[1], ["", "dodaj_usenet", "nastavitve"])
        self.assertEqual(izid[2], ["mediaDebrid"])


if __name__ == "__main__":
    unittest.main()
