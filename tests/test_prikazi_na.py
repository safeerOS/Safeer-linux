"""»Prikazi na TV / na racunalniku« (lastnik, 11. 10. 2026): lupa prepozna cilj v nizu, izbrana naprava v Linku dobi
media.open in v svojem Medijskem centru poisce naslov. Vec naprav iste vrste: uporabnik izbere."""
import json
import os
import shutil
import subprocess
import sys
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec, link_dostop  # noqa: E402


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class TestCiljVLupi(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node ni namescen")
    def test_razclenitev(self):
        js = beri("assets", "os", "delovna.js")
        blok = js[js.index("  function ocenaPrograma(p, ql) {"):js.index("  function isci(q) {")]
        koda = """
var assert = require("assert");
var SafeerIskanje = require(process.argv[1]);
function t(k) { return k === "taRacunalnik" ? "Ta racunalnik" : k; }
var D = { naprave: [] }, P = { naprave: [] };
""" + blok + """
function c(q) { var r = ciljMedija(q); return r && [r.q, r.vrste.join(",")]; }
assert.deepStrictEqual(c("Jungle Book na TV"), ["Jungle Book", "tv"]);
assert.deepStrictEqual(c("prikaži Jungle Book na televizorju"), ["Jungle Book", "tv"]);
assert.deepStrictEqual(c("Pokaži Zvezdne steze na računalniku"), ["Zvezdne steze", "windows,linux,mac"]);
assert.deepStrictEqual(c("predvajaj Bohemian Rhapsody na tablici"), ["Bohemian Rhapsody", "tablet"]);
assert.deepStrictEqual(c("play Sintel on the TV"), ["Sintel", "tv"]);
assert.deepStrictEqual(c("zeige Sintel auf dem Fernseher"), ["Sintel", "tv"]);
assert.deepStrictEqual(c("pon Sintel en la tele"), ["Sintel", "tv"]);
assert.deepStrictEqual(c("mostra Sintel na TV"), ["Sintel", "tv"]);
assert.deepStrictEqual(c("abre Sintel no computador"), ["Sintel", "windows,linux,mac"]);
assert.deepStrictEqual(c("montre Sintel sur la télé"), ["Sintel", "tv"]);
assert.deepStrictEqual(c("riproduci Sintel sulla TV"), ["Sintel", "tv"]);
assert.deepStrictEqual(c("ouvre Sintel sur l'ordinateur"), ["Sintel", "windows,linux,mac"]);
assert.deepStrictEqual(c("prikaži na TV"), ["", "tv"], "brez naslova: lupa ne prikaze nicesar");
assert.strictEqual(ciljMedija("nastavitve zaslona"), null);
assert.strictEqual(ciljMedija("Tvornica"), null);
assert.deepStrictEqual(c("Na TV"), ["", "tv"], "sam cilj: brez naslova (lupa isce normalno)");
// Naprave: vse ustrezne; »na racunalniku« na racunalniku ponudi tudi tega
var naprave = [{ id: "a", ime: "Philips TV", platforma: "tv" }, { id: "b", ime: "Pisarna", platforma: "windows" },
               { id: "c", ime: "Tablica", platforma: "tablet" }];
assert.deepStrictEqual(napraveCilja(ciljMedija("x na tv"), naprave, true).map(function (n) { return n.id; }), ["a"]);
assert.deepStrictEqual(napraveCilja(ciljMedija("x na racunalniku"), naprave, true).map(function (n) { return n.id; }), ["", "b"]);
"""
        subprocess.run(["node", "-e", koda, os.path.join(KOREN, "assets", "os", "iskanje.js")], check=True)

    def test_vec_naprav_izbere_uporabnik(self):
        js = beri("assets", "os", "delovna.js")
        self.assertIn('return { vrsta: "naCilj", n: n, naslov: q, izberi: I.napraveCilja.length > 1 };', js)
        self.assertEqual(js.count('if (b && b._v.vrsta === "naCilj" && b._v.izberi'), 2)
        self.assertIn('klic("odpriMedijNa", [v.n.id, JSON.stringify(m)])', js)
        py = beri("safeer_os.py")
        self.assertIn('"odpriMedijNa": lambda:', py)
        self.assertIn('return _control_naprave("Ukaz", str(id_naprave or ""), "media.open",', py)


class TestMediaOpen(unittest.TestCase):
    def test_parametri(self):
        self.assertIsNone(link_daljinec.medij_iz_parametrov({"title": "  "}))
        m = link_daljinec.medij_iz_parametrov({"title": " Jungle  Book ", "kind": "film", "year": 1967})
        self.assertEqual(m, {"title": "Jungle Book", "kind": "film", "year": 1967})
        m = link_daljinec.medij_iz_parametrov({"title": "x" * 500, "kind": "rm -rf", "year": "1967"})
        self.assertEqual((len(m["title"]), m["kind"], m["year"]), (200, "", None))

    def test_odpre_safeer_os(self):
        with mock.patch.object(link_daljinec, "_safeer_os", return_value="/usr/bin/safeer-os"), \
                mock.patch("subprocess.Popen") as popen:
            izid = link_daljinec.odpri_medij({"title": "Sintel", "kind": "film"})
        self.assertTrue(izid["ok"])
        ukaz = popen.call_args[0][0]
        self.assertEqual(ukaz[:2], ["/usr/bin/safeer-os", "--medij-naprava"])
        self.assertEqual(json.loads(ukaz[2])["title"], "Sintel")
        with mock.patch.object(link_daljinec, "_safeer_os", return_value=""):
            self.assertEqual(link_daljinec.odpri_medij({"title": "Sintel"})["code"], "ni_safeer_os")

    def test_dovoljenje_in_stanje(self):
        # Odpiranje vsebine na tej napravi: isto dovoljenje kot magnet.open in open_url (predvajalnik).
        self.assertEqual(link_dostop.zahteva_dejanja("media.open"), link_dostop.zahteva_dejanja("magnet.open"))
        self.assertIn("DEJANJA_ISKANJE + DEJANJA_MEDIJ if _safeer_os()", beri("core", "link_daljinec.py"))

    def test_safeer_os(self):
        py = beri("safeer_os.py")
        self.assertIn('if "--medij-naprava" in sys.argv[1:]:', py)
        self.assertIn('Gio.SimpleAction.new("medij", GLib.VariantType.new("s"))', py)
        self.assertIn("self._odpri_predvajalnik(naslov)", py)
        # Iskanje v Medijskem centru (lupa, glas z druge naprave) odpre okno na celem zaslonu.
        self.assertIn("            okno.maximize()", py)
        self.assertIn("        self.okno_predvajalnik.maximize()", py)


if __name__ == "__main__":
    unittest.main()
