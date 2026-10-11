"""Iskalna lupa namizja se uci iz izbir (lastnik, 11. 10. 2026): core/os_lupa.py hrani izbire samo na tem
racunalniku, delovna.js iz njih razvrsti zadetke in izbere prvega; statistika meri, kako pogosto je lupa takoj prava."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import os_lupa  # noqa: E402


class TestShramba(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.pot = os.path.join(self.mapa, "lupa.json")

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_zapomni_in_statistika(self):
        u = os_lupa.Ucenje(self.pot)
        self.assertEqual(u.statistika()["izbir"], 0)
        self.assertIsNone(u.statistika()["prvi_odstotek"])
        self.assertTrue(u.zapomni("nap", "program:cinnamon-settings-power.desktop", True))
        self.assertTrue(u.zapomni("zas", "program:cinnamon-settings-display.desktop", False))
        self.assertFalse(u.zapomni("", "splet", True), "prazen niz se ne hrani")
        self.assertFalse(u.zapomni("x", "", True))
        st = u.statistika()
        self.assertEqual((st["izbir"], st["prvi_odstotek"]), (2, 50.0))
        # Shranjeno na disk in prebrano znova (nov proces).
        u2 = os_lupa.Ucenje(self.pot)
        self.assertEqual([z[:2] for z in u2.podatki()["izbire"]],
                         [["nap", "program:cinnamon-settings-power.desktop"], ["zas", "program:cinnamon-settings-display.desktop"]])

    def test_omejitve_in_drug_proces(self):
        a, b = os_lupa.Ucenje(self.pot), os_lupa.Ucenje(self.pot)
        a.zapomni("a" * 500, "k" * 1000, False)
        b.zapomni("bb", "splet", True)          # b ne izbrise zapisa, ki ga je medtem dodal a
        izbire = os_lupa.Ucenje(self.pot).izbire
        self.assertEqual(len(izbire), 2)
        self.assertEqual(len(izbire[0][0]), os_lupa.NAJDALJSI_NIZ)
        self.assertEqual(len(izbire[0][1]), os_lupa.NAJDALJSI_KLJUC)
        for i in range(os_lupa.NAJVEC + 20):
            a.zapomni("n%d" % i, "splet", False)
        self.assertEqual(len(os_lupa.Ucenje(self.pot).izbire), os_lupa.NAJVEC)

    def test_pokvarjena_datoteka_in_pozabi(self):
        with open(self.pot, "w", encoding="utf-8") as f:
            f.write(json.dumps({"izbire": [["ok", "splet", 1, True], ["slab"], "x", ["a", 1, 2, 3]]}))
        u = os_lupa.Ucenje(self.pot)
        self.assertEqual(u.izbire, [["ok", "splet", 1, True]])
        self.assertTrue(u.pozabi())
        self.assertEqual(os_lupa.Ucenje(self.pot).izbire, [])
        with open(self.pot, "w") as f:
            f.write("{nic")
        self.assertEqual(os_lupa.Ucenje(self.pot).izbire, [])


class TestDelovnaJs(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node ni namescen")
    def test_razvrscanje_po_ucenju(self):
        with open(os.path.join(KOREN, "assets", "os", "delovna.js"), encoding="utf-8") as f:
            js = f.read()
        blok = js[js.index("  function ocenaPrograma(p, ql) {"):js.index("  function isci(q) {")]
        zdaj = int(time.time())
        koda = """
var assert = require("assert");
var SafeerIskanje = require(process.argv[1]);
function t(k) { return k; }
var D = { naprave: [] }, P = { naprave: [] };
""" + blok + """
var ZDAJ = %d;
var prg = function (id, ime) { return { vrsta: "program", p: { id: id, ime: ime } }; };
var splet = { vrsta: "splet", q: "nap" };
var moc = prg("cinnamon-settings-power.desktop", "Upravljanje porabe energije");
var nap = prg("napajalnik.desktop", "Napajalnik");
assert.strictEqual(kljucZadetka(moc), "program:cinnamon-settings-power.desktop");
assert.strictEqual(kljucZadetka({ vrsta: "datoteka", d: { pot: "/x/a.txt" } }), "datoteka:/x/a.txt");
assert.strictEqual(nizUcenja("  Napájanje   Mreže "), "napajanje mreze");
// Brez ucenja: program, katerega ime se z nizom zacne.
assert.strictEqual(privzetiZadetek([splet, nap, moc], "nap", naucenaOcena("nap", ZDAJ)), 1);
// Uporabnik je pri »napajanje« izbral nastavitev: pri »nap« (zacetek) je ta prva, razvrscanje jo da na vrh.
U.izbire = [["napajanje", "program:cinnamon-settings-power.desktop", ZDAJ - 60, false]];
var N = naucenaOcena("nap", ZDAJ);
assert.ok(N["program:cinnamon-settings-power.desktop"] > 0.99);
assert.strictEqual(privzetiZadetek([splet, nap, moc], "nap", N), 2);
assert.deepStrictEqual(poUcenju([nap, moc], N, kljucZadetka), [moc, nap]);
assert.deepStrictEqual(poUcenju([nap, splet], N, kljucZadetka), [nap, splet], "brez ocene: vrstni red ostane");
// Drug niz (ni zacetek ne nadaljevanje) ne steje; enak niz steje dvojno; stara izbira (90 dni) je pod pragom.
assert.deepStrictEqual(naucenaOcena("zvok", ZDAJ), {});
U.izbire = [["nap", "splet", ZDAJ, false]];
assert.strictEqual(naucenaOcena("nap", ZDAJ)["splet"], 2);
assert.strictEqual(privzetiZadetek([splet, nap], "nap", naucenaOcena("nap", ZDAJ)), 0, "naucen splet ostane splet");
U.izbire = [["napajanje", "program:napajalnik.desktop", ZDAJ - 90 * 86400, false]];
assert.strictEqual(privzetiZadetek([splet, moc, nap], "nap", naucenaOcena("nap", ZDAJ)), 1, "pozabljeno: ime odloci");
// Enoznakovni zapis ne velja za daljsi niz (»n« bi sicer veljal za vse).
U.izbire = [["n", "program:napajalnik.desktop", ZDAJ, false]];
assert.deepStrictEqual(naucenaOcena("nap", ZDAJ), {});
""" % zdaj
        subprocess.run(["node", "-e", koda, os.path.join(KOREN, "assets", "os", "iskanje.js")], check=True)

    def test_izbire_gredo_v_ucenje(self):
        with open(os.path.join(KOREN, "assets", "os", "delovna.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn("  function izberiZadetek(v) {\n    zapomniIzbiro(v);", js)
        self.assertIn('klic("lupaZapomni", [ql, k, prvi])', js)
        self.assertIn('klic("lupaUcenje").then(', js)
        self.assertIn("I.izbran = privzetiZadetek(I.zadetki.map(function (b) { return b._v; }), I.zadnji, I.nauceno);", js)
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            py = f.read()
        for m in ('"lupaUcenje":', '"lupaZapomni":', '"lupaPozabi":'):
            self.assertIn(m, py)
        with open(os.path.join(KOREN, "packaging", "install_os_payload.sh"), encoding="utf-8") as f:
            self.assertIn(" os_lupa ", f.read())


if __name__ == "__main__":
    unittest.main()
