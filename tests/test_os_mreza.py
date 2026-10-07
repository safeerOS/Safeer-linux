"""Medijski center Safeer OS: nobene police, ki bi jo bilo treba pomikati v desno.

Zahteva (7. 10. 2026): prikaz povsod kot pri Videu - izbire zgoraj, pod njimi mreža. V medijskem centru za računalnik
sta se v desno pomikali še dve stvari: polica »Na tvojih napravah« (plakati v eni vrsti) in vrstica zvrsti. Zdaj:
  - »Na tvojih napravah« je mreža kot katalog; pokaže dve vrstici, če je vsebine več, zadnje mesto zasede »Pokaži vse«;
  - zvrsti se prelomijo v več vrstic.
"""
import os
import re
import shutil
import subprocess
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


def pravilo(css, izbirnik):
    m = re.search(r"(?:^|\})\s*" + re.escape(izbirnik) + r"\s*\{([^}]*)\}", css, re.M)
    return m.group(1) if m else ""


class Slog(unittest.TestCase):
    def setUp(self):
        self.css = beri("assets", "os", "katalog.css")

    def test_katalog_nima_vodoravnih_polic(self):
        # Vodoravni pomik v medijskem centru pomeni polico; izbire in vsebina se morajo prelomiti ali biti mreža.
        self.assertNotRegex(self.css, r"overflow-x\s*:\s*(auto|scroll)")

    def test_na_tvojih_napravah_je_mreza_kot_katalog(self):
        vrsta = pravilo(self.css, ".kat-knjiznica-vrsta")
        self.assertIn("display: grid", vrsta)
        self.assertIn("grid-template-columns: repeat(auto-fill, minmax(145px, 1fr))", vrsta)
        self.assertNotIn("flex: 0 0 150px", self.css)

    def test_zvrsti_se_prelomijo(self):
        self.assertIn("flex-wrap:wrap", pravilo(self.css, ".kat-zanri").replace(" ", ""))


@unittest.skipUnless(shutil.which("node"), "node ni namescen")
class Logika(unittest.TestCase):
    def setUp(self):
        js = beri("assets", "os", "os.js")
        self.koda = js[js.index("  function knjiznicaNaVrsto(sirina)"):js.index("  function narisiKnjiznico(")]

    def test_dve_vrstici_in_pokazi_vse(self):
        subprocess.run(["node", "-e", 'var assert = require("assert");\n' + self.koda + r"""
// Racun iz sirine mreze (rezerva): stolpec najmanj 145, razmik 14, mreza ima levo in desno 2 px roba (katalog.css).
// Izmerjeno v WebKitGTK (7. 10. 2026): mreza, siroka 304..307 px, ima EN stolpec, 940 px pet - prejsnji racun je roba
// spregledal in v takih pasovih nastel stolpec vec (tri vrstice namesto dveh).
assert.strictEqual(knjiznicaNaVrsto(145), 1);
assert.strictEqual(knjiznicaNaVrsto(303), 1);
assert.strictEqual(knjiznicaNaVrsto(307), 1);
assert.strictEqual(knjiznicaNaVrsto(308), 2);
assert.strictEqual(knjiznicaNaVrsto(466), 2);
assert.strictEqual(knjiznicaNaVrsto(467), 3);
assert.strictEqual(knjiznicaNaVrsto(940), 5);
assert.strictEqual(knjiznicaNaVrsto(944), 6);
// Stevilo stolpcev pove brskalnik (izracunani slog mreze); racun velja, kadar ga ne pove (razdelek se ni prikazan).
var slog = "";
var window = { getComputedStyle: function () { if (slog === "napaka") throw new Error("ni sloga"); return { gridTemplateColumns: slog }; } };
slog = "150.5px 150.5px 150.5px";
assert.strictEqual(knjiznicaStolpcev({ clientWidth: 940 }), 3, "velja slog, ne racun");
slog = "145px";
assert.strictEqual(knjiznicaStolpcev({ clientWidth: 940 }), 1);
["none", "", "repeat(auto-fill, minmax(145px, 1fr))", "napaka"].forEach(function (x) {
  slog = x;
  assert.strictEqual(knjiznicaStolpcev({ clientWidth: 940 }), 5, "rezerva: " + x);
  assert.strictEqual(knjiznicaStolpcev({ clientWidth: 0 }), 6, "sirina se ni znana: " + x);
});
// Sirina mreze se spremeni tudi brez spremembe okna (stran dobi drsnik, ko se pod knjiznico narise katalog): ce se
// stevilo stolpcev pri tem spremeni, se knjiznica narise znova.
var opazovalci = [], risov = 0, kat = { knjiznicaVse: false };
function ResizeObserver(f) { this.f = f; this.cilji = []; opazovalci.push(this); }
ResizeObserver.prototype.observe = function (e) { this.cilji.push(e); };
ResizeObserver.prototype.disconnect = function () { this.odklopljen = true; };
function narisiKnjiznico() { risov++; }
var mreza = { clientWidth: 470 };
slog = "150px 150px 150px";
opazujKnjiznico(mreza, 3);
assert.strictEqual(opazovalci.length, 1);
assert.deepStrictEqual(opazovalci[0].cilji, [mreza]);
opazovalci[0].f();
assert.strictEqual(risov, 0, "stevilo stolpcev je enako: nic");
slog = "225px 225px";                                  // stran je dobila drsnik, mreza ima stolpec manj
opazovalci[0].f();
assert.strictEqual(risov, 1);
// Varovalka: stran, ki bi z drsnikom nihala, ne sme vrteti risanja (najvec trije risi v sekundi).
for (var k = 0; k < 10; k++) opazovalci[0].f();
assert.strictEqual(risov, 3);
// Nov ris: prejsnji opazovalec se odklopi.
opazujKnjiznico({ clientWidth: 470 }, 2);
assert.ok(opazovalci[0].odklopljen && opazovalci.length === 2);
// »Pokaži vse«: stevilo stolpcev ni pomembno, ne opazujemo.
kat.knjiznicaVse = true;
opazujKnjiznico(mreza, 3);
assert.ok(opazovalci[1].odklopljen && opazovalci.length === 2);
kat.knjiznicaVse = false;
// Pogon brez ResizeObserver: brez napake.
ResizeObserver = undefined;
opazujKnjiznico(mreza, 3);
assert.strictEqual(opazovalci.length, 2);
assert.strictEqual(knjiznicaNaVrsto(0), 6, "sirina se ni znana (razdelek se ni prikazan): privzetih 6, ne 1");
assert.strictEqual(knjiznicaNaVrsto(undefined), 6);
// Dve vrstici; ce je vsebine vec, zadnje mesto zasede »Pokaži vse«.
assert.strictEqual(knjiznicaVidnih(0, 6, false), 0);
assert.strictEqual(knjiznicaVidnih(5, 6, false), 5);
assert.strictEqual(knjiznicaVidnih(12, 6, false), 12);       // natanko dve vrstici: vse, brez »Pokaži vse«
assert.strictEqual(knjiznicaVidnih(13, 6, false), 11);       // 11 plakatov + »Pokaži vse«
assert.strictEqual(knjiznicaVidnih(40, 6, false), 11);
assert.strictEqual(knjiznicaVidnih(40, 6, true), 40);        // razsirjeno
assert.strictEqual(knjiznicaVidnih(3, 1, false), 1);         // zelo ozko okno: 1 plakat + »Pokaži vse«
for (var n = 0; n < 60; n++) for (var v = 1; v < 9; v++) {
  var k = knjiznicaVidnih(n, v, false);
  assert.ok(k <= n && k + (k < n ? 1 : 0) <= v * 2, n + "/" + v);   // nikoli vec kot dve vrstici
  assert.ok(n === 0 || k >= 1);
}
"""], check=True, timeout=60)


class Stran(unittest.TestCase):
    def test_besedila_v_vseh_jezikih(self):
        besedila = beri("assets", "os", "besedila.js")
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            for kljuc in ("knjiznicaPokaziVse", "knjiznicaPokaziManj"):
                self.assertRegex(besedila, r'Object\.assign\(BESEDILA_OS\.%s, \{[^\n]*"%s": "[^"]+"' % (jezik, kljuc), jezik + " " + kljuc)

    def test_risanje_uporablja_pravilo(self):
        js = beri("assets", "os", "os.js")
        telo = js[js.index("  function narisiKnjiznico("):js.index("  function predvajajIzKnjiznice(")]
        self.assertIn("var naVrsto = knjiznicaStolpcev(vrsta), vidnih = knjiznicaVidnih(vnosi.length, naVrsto, kat.knjiznicaVse);", telo)
        # Stran dobi drsnik sele, ko se pod knjiznico narise katalog: stevilo stolpcev spremlja opazovalec sirine.
        self.assertIn("    opazujKnjiznico(vrsta, naVrsto);\n  }\n", telo)
        self.assertNotIn("narisiKnjiznico(true)", js)
        self.assertIn("vnosi.slice(0, vidnih).forEach(", telo)
        self.assertIn('t("knjiznicaPokaziVse")', telo)


if __name__ == "__main__":
    unittest.main()
