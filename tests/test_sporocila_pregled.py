"""Prenova nabiralnika Sporocil (16. 10. 2026, lastnik: »malo nepregledno«).

Seznam pogovorov | pogovor (+ pano z osebo): mape, kanal in oznake v plosci filtra, kanali kot znaki nad seznamom,
v vrstici avatar, ime, relativni cas, predogled, znak kanala in pika za neprebrano; v pogovoru »Povezani viri« (pravi
pogovori iste osebe), kanal odgovora in »Poslji« samo, ko je kaj poslati. Ozko: en stolpec z »Nazaj na seznam«.
Preverjamo strukturo, besedila v vseh jezikih, barve iz tokens.css (s kontrastom) in logiko v node.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
OS = KOREN / "assets" / "os"
JEZIKI = ("sl", "en", "de", "es", "fr", "it")
NOVI_KLJUCI = ("spIsci", "spFilter", "spFilterPrikazi", "spFilterKanal", "spPocistiFiltre", "spOdstraniFilter", "spPrek",
               "spOdgovarjasPrek", "spKanalOdgovora", "spNapisiOdgovor", "spPovezaniViri", "spNazajSeznam", "spPoslano",
               "spNeprebranih", "spIzberiOpis", "casZdaj", "casMin", "casVceraj")


def _beri(ime):
    return (OS / ime).read_text(encoding="utf-8")


def _funkcija(js, ime):
    """Besedilo funkcije »function ime(...) { ... }« iz os.js (do zaprtja prvega bloka na isti globini)."""
    z = js.index("  function %s(" % ime)
    k = js.index("\n  }\n", z) + 4
    return js[z:k]


def _tokeni():
    css = _beri("tokens.css")
    koren = css[css.index(":root {"):css.index("}", css.index(":root {"))]
    return dict(re.findall(r"(--[a-z0-9-]+):\s*([^;]+);", koren))


def _svetlost(hex_barva):
    h = hex_barva.strip().lstrip("#")
    kan = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    kan = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in kan]
    return 0.2126 * kan[0] + 0.7152 * kan[1] + 0.0722 * kan[2]


def _kontrast(a, b):
    la, lb = sorted((_svetlost(a), _svetlost(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class Struktura(unittest.TestCase):
    def setUp(self):
        self.html = _beri("index.html")
        z = self.html.index('<section class="razdelek" id="r-sporocila">')
        self.razdelek = self.html[z:self.html.index("<!-- SAFEER MEDIA -->", z)]

    def test_brez_glave_razdelka_in_stolpca_map(self):
        # Glava (naslov, opis, trije siroki gumbi) in stolpec map so vzeli ~200 px visine in ~200 px sirine.
        self.assertNotIn("sporocila-glava", self.razdelek)
        self.assertNotIn("nabiralnik-mape", self.razdelek)
        glava = self.razdelek[self.razdelek.index('class="seznam-glava"'):self.razdelek.index('class="seznam-iskanje"')]
        for i in ("sporocilaMapaNaslov", "sporocilaNovo", "sporocilaPisi", "sporocilaDodaj"):
            self.assertIn('id="%s"' % i, glava, i)

    def test_filter_v_plosci(self):
        self.assertIn('aria-controls="sporocilaFilterPlosca"', self.razdelek)
        z = self.razdelek.index('id="sporocilaFilterPlosca"')
        plosca = self.razdelek[z:self.razdelek.index('id="sporocilaAktivniFiltri"')]
        for i in ("sporocilaMape", "sporocilaFiltri", "sporocilaOznake", "sporocilaPocisti"):
            self.assertIn('id="%s"' % i, plosca, i)
        # »Vsi pogovori« je bil isti seznam kot »Prejeto« (pogovorUstreza ga ni locil) - podvojen gumb ni vec ponujen.
        self.assertNotIn('data-mapa="vsi"', self.razdelek)
        self.assertEqual(re.findall(r'data-mapa="vse"[^>]*aria-pressed="true"', plosca).__len__(), 1)

    def test_pogovor_in_vnos(self):
        for i in ("sporocilaNazaj", "vgrajenKanalSeznam", "sporocilaAvatar", "sporocilaPrazno", "panoViri",
                  "sporocilaVnosKanal", "sporocilaKanali", "sporocilaPoraba"):
            self.assertIn('id="%s"' % i, self.razdelek, i)
        self.assertIn('class="pogovor-okno brez-pogovora"', self.razdelek, "brez izbranega pogovora ni praznega vnosa")
        self.assertIn('data-ph="spNapisiOdgovor"', self.razdelek)
        # Gumbov za klic, video in emoji ni: noben kanal jih v Safeerju ne podpira (brez praznih gumbov).
        for beseda in ("klic", "video", "emoji"):
            self.assertNotRegex(self.razdelek.lower(), r'id="sporocila%s' % beseda)

    def test_gumbi_z_ikono_imajo_napis(self):
        # prevedi() da gumbu z data-naslov in brez besedila tudi aria-label.
        for i in ("sporocilaNovo", "sporocilaPisi", "sporocilaDodaj", "sporocilaFilterGumb", "sporocilaNazaj", "vgrajenKanalSeznam"):
            m = re.search(r'<button[^>]*id="%s"[^>]*>' % i, self.razdelek)
            self.assertTrue(m and "data-naslov=" in m.group(0), i)


class BesedilaInBarve(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node ni namescen")
    def test_novi_kljuci_v_vseh_jezikih(self):
        koda = _beri("besedila.js") + "\nprocess.stdout.write(JSON.stringify(BESEDILA_OS));"
        # besedila.js je predolg za argument ukazne vrstice: node ga bere s standardnega vhoda
        b = json.loads(subprocess.run(["node"], input=koda, check=True, capture_output=True, text=True, timeout=60).stdout)
        for j in JEZIKI:
            for k in NOVI_KLJUCI:
                self.assertTrue(str(b[j].get(k, "")).strip(), "%s.%s" % (j, k))
            self.assertIn("{n}", b[j]["casMin"], j)
            self.assertIn("{kanal}", b[j]["spPrek"], j)

    def test_barve_samo_iz_tokens(self):
        css = _beri("os.css")
        blok = css[css.index("/* ==== Nabiralnik Sporocil - prenova"):css.index("/* ==== konec: nabiralnik Sporocil ==== */")]
        self.assertNotRegex(blok, r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", "barve samo iz tokens.css")
        tokeni = _tokeni()
        for ime in set(re.findall(r"var\((--[a-z0-9-]+)", blok)) - {"--zacetnice", "--avatar"}:
            self.assertIn(ime, tokeni, ime)

    def test_kontrast(self):
        t = _tokeni()
        # besedilo v poslanem mehurcku in cas pod njim (WCAG AA za navadno besedilo)
        self.assertGreaterEqual(_kontrast(t["--mehurcek-ven-besedilo"], t["--mehurcek-ven"]), 4.5)
        self.assertGreaterEqual(_kontrast(t["--mehurcek-ven-medlo"], t["--mehurcek-ven"]), 4.5)
        # znak kanala in zacetnice na barvni podlagi (graficni element: vsaj 3 : 1)
        for k in ("--kanal-eposta", "--kanal-telegram", "--kanal-matrix", "--kanal-safeer", "--kanal-chatwoot", "--kanal-drugo"):
            self.assertGreaterEqual(_kontrast(t["--znak-besedilo"], t[k]), 3.0, k)


class ZnakiKanalov(unittest.TestCase):
    def test_vsak_adapter_ima_znak_in_barvo(self):
        vrste = set()
        for f in (KOREN / "core" / "sporocila").glob("*.py"):
            for m in re.finditer(r'class \w+\(Adapter\):(?:\n[^\n]*){0,3}?\n\s+vrsta = "([a-z_]+)"', f.read_text(encoding="utf-8")):
                vrste.add(m.group(1))
        self.assertTrue({"email", "matrix", "chatwoot", "safeer", "telegram_bot"} <= vrste, vrste)
        js, css = _beri("os.js"), _beri("os.css")
        znaki = js[js.index("var ZNAKI_KANALOV = {"):js.index("};", js.index("var ZNAKI_KANALOV = {"))]
        for v in vrste:
            self.assertRegex(znaki, r"\b%s:" % v, v)
            self.assertIn('[data-vrsta="%s"]' % v, css, v)


@unittest.skipUnless(shutil.which("node"), "node ni namescen")
class LogikaVNode(unittest.TestCase):
    def setUp(self):
        js = _beri("os.js")
        self.koda = ('var assert = require("assert"); var jezik = "sl"; var LOKALE = { sl: "sl-SI" }; var S = {};\n'
                     'var B = { casZdaj: "zdaj", casMin: "{n} min", casVceraj: "včeraj" };\n'
                     'function t(k, z) { var b = B[k] || k; Object.keys(z || {}).forEach(function (x) { b = b.split("{" + x + "}").join(z[x]); }); return b; }\n'
                     + _funkcija(js, "relativniCas") + _funkcija(js, "jeKlepet") + _funkcija(js, "pogovorUstreza"))

    def _node(self, koda):
        subprocess.run(["node", "-e", self.koda + koda], check=True, timeout=60)

    def test_relativni_cas(self):
        self._node(r"""
var zdaj = new Date(2026, 9, 16, 12, 0, 0);
function pred(min) { return new Date(zdaj.getTime() - min * 60000).toISOString(); }
assert.strictEqual(relativniCas(pred(0.2), zdaj), "zdaj");
assert.strictEqual(relativniCas(pred(16), zdaj), "16 min");
assert.strictEqual(relativniCas(pred(59), zdaj), "59 min");
assert.match(relativniCas(pred(125), zdaj), /^\d{1,2}[:.]\d{2}$/);            // danes: ura
assert.strictEqual(relativniCas(new Date(2026, 9, 15, 20, 0).toISOString(), zdaj), "včeraj");
assert.notStrictEqual(relativniCas(new Date(2026, 9, 12, 9, 0).toISOString(), zdaj), "");   // ta teden: dan
assert.match(relativniCas(new Date(2025, 0, 3).toISOString(), zdaj), /2025/);  // lani: z letnico
assert.strictEqual(relativniCas("", zdaj), "");
assert.strictEqual(relativniCas("ni-datum", zdaj), "");
""")

    def test_filter_po_kanalu_in_mapi(self):
        self._node(r"""
var sk = { oseba: { ime: "Ana Demo" } };
var e = { kanal_id: "e1", kanal: { vrsta: "email", ime: "demo@example.test" }, neprebrano: 2, oznake: [] };
var m = { kanal_id: "mx", kanal: { vrsta: "matrix", ime: "Matrix" }, neprebrano: 0, oznake: ["služba"], zadnji_ven: true };
S.sporocilaFilter = "kanal:e1"; assert.ok(pogovorUstreza(sk, e)); assert.ok(!pogovorUstreza(sk, m));
S.sporocilaFilter = "klepet"; assert.ok(!pogovorUstreza(sk, e)); assert.ok(pogovorUstreza(sk, m));
S.sporocilaFilter = ""; S.sporocilaMapa = "neprebrano"; assert.ok(pogovorUstreza(sk, e)); assert.ok(!pogovorUstreza(sk, m));
S.sporocilaMapa = "oznaka:služba"; assert.ok(!pogovorUstreza(sk, e)); assert.ok(pogovorUstreza(sk, m));
S.sporocilaMapa = "osnutki"; assert.ok(!pogovorUstreza(sk, e));
S.sporocilaMapa = "vse"; S.sporocilaNiz = "matrix"; assert.ok(!pogovorUstreza(sk, e)); assert.ok(pogovorUstreza(sk, m));
""")


class Vedenje(unittest.TestCase):
    def setUp(self):
        self.js = _beri("os.js")

    def test_poslji_samo_z_vsebino(self):
        f = _funkcija(self.js, "posodobiPoslji")
        self.assertIn("!S.sporocilaAktivni", f)
        self.assertIn("vnos.value.trim()", f)
        self.assertIn('$("sporocilaBesedilo").addEventListener("input", posodobiPoslji)', self.js)

    def test_brez_statusa_na_spletu_in_dvojne_kljukice(self):
        # Noben kanal ne sporoca prisotnosti ali »prebrano« pri prejemniku: tega ne prikazemo.
        f = _funkcija(self.js, "odpriPogovor")
        self.assertNotIn("naSpletu", f)
        m = _funkcija(self.js, "mehurcekSporocila")
        self.assertIn('s.stanje === "poslano"', m)
        self.assertNotIn("prebrano", m)

    def test_povezani_viri_samo_pravi_pogovori(self):
        f = _funkcija(self.js, "pogovoriOsebe")
        self.assertIn("S.sporocilaSkupine", f)
        self.assertIn("pogovoriOsebe(oseba)", _funkcija(self.js, "narisiPano"))
        self.assertIn("pogovoriOsebe(oseba)", _funkcija(self.js, "narisiKanalOdgovora"))

    def test_osvezitev_ohrani_fokus_vrstice(self):
        f = _funkcija(self.js, "narisiSporocila")
        self.assertIn("document.activeElement", f)
        self.assertIn('getAttribute("data-kljuc") === fokus', f)

    def test_tipkovnica(self):
        for niz in ('$("sporocilaSeznam").addEventListener("keydown"', "ArrowDown", 'e.key === "Escape") { e.preventDefault(); e.stopPropagation(); odpriFilter(false)',
                    '$("sporocilaNazaj").addEventListener("click", nazajNaSeznam)'):
            self.assertIn(niz, self.js, niz)


if __name__ == "__main__":
    unittest.main()
