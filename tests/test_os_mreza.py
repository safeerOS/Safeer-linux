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
        self.koda = js[js.index("  function knjiznicaNaVrsto(sirina)"):js.index("  function narisiKnjiznico()")]

    def test_dve_vrstici_in_pokazi_vse(self):
        subprocess.run(["node", "-e", 'var assert = require("assert");\n' + self.koda + r"""
// Koliko plakatov gre v vrsto (stolpec najmanj 145, razmik 14) - enako kot mreza kataloga.
assert.strictEqual(knjiznicaNaVrsto(145), 1);
assert.strictEqual(knjiznicaNaVrsto(303), 1);
assert.strictEqual(knjiznicaNaVrsto(304), 2);
assert.strictEqual(knjiznicaNaVrsto(940), 6);
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
        telo = js[js.index("  function narisiKnjiznico()"):js.index("  function predvajajIzKnjiznice(")]
        self.assertIn("knjiznicaVidnih(vnosi.length, naVrsto, kat.knjiznicaVse)", telo)
        self.assertIn("vnosi.slice(0, vidnih).forEach(", telo)
        self.assertIn('t("knjiznicaPokaziVse")', telo)


if __name__ == "__main__":
    unittest.main()
