"""Safeer OS, Sporocila: sporocilo se da oznaciti in kopirati.

Do Safeer OS 0.4.65 je bila vsa stran neizberljiva (`body { user-select: none }`), sistemski meni pogleda je izklopljen
(`context-menu` -> True), mehurcek sporocila pa ni imel svojega menija - sporocila ni bilo mogoce kopirati.
Tu preverimo:
  - slog: besedilo mehurcka je izberljivo, ura ne; meni mehurcka obstaja;
  - logiko (node): podpis sporocila, kaj ob osvezitvi ostane na zaslonu, postavke menija, povezava (zavajajoci
    naslovi se ne ponudijo, postavka pove, kam povezava vodi);
  - risanje (node, lazni DOM): ob novem sporocilu stari mehurcki ostanejo isti elementi (izbor besedila se ne podre),
    pogled ne skoci, ce uporabnik bere starejsa sporocila ali kaj oznacuje;
  - odlozisce: dolgo sporocilo se ne odreze pri 8192 znakih, prazno besedilo odlozisca ne izprazni.
"""
import os
import re
import shutil
import subprocess
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


def _pravilo(css, izbirnik):
    """Vsebina pravila z natanko tem izbirnikom (prvo)."""
    m = re.search(r"(?:^|\})\s*" + re.escape(izbirnik) + r"\s*\{([^}]*)\}", css, re.M)
    return m.group(1) if m else ""


class Slog(unittest.TestCase):
    def setUp(self):
        self.css = _beri("assets", "os", "os.css")

    def test_besedilo_mehurcka_je_izberljivo(self):
        mehurcek = _pravilo(self.css, ".mehurcek")
        self.assertIn("-webkit-user-select: text", mehurcek)
        self.assertRegex(mehurcek, r"(?<!-)user-select: text")
        self.assertIn("cursor: text", mehurcek)

    def test_ura_ne_gre_v_izbor(self):
        ura = _pravilo(self.css, ".mehurcek time")
        self.assertIn("-webkit-user-select: none", ura)
        self.assertRegex(ura, r"(?<!-)user-select: none")

    def test_stran_kot_celota_ostane_neizberljiva(self):
        # Gumbi, kartice in napisi vmesnika se ob vlecenju z misko ne smejo oznacevati - izjema je besedilo sporocila.
        self.assertIn("user-select: none", _pravilo(self.css, "body"))

    def test_obroba_fokusa_s_tipkovnico(self):
        # Po kliku z misko brskalnik obrobe fokusa ne kaze vec, tudi ce se uporabnik potem premika s puscicami.
        self.assertIn("outline: 2px solid var(--zelena)", _pravilo(self.css, ".mehurcek.fokus-tipke:focus"))

    def test_postavka_menija_s_fokusom_je_vidna(self):
        # V zivo (zabojnik): po kliku z misko :focus-visible ne velja vec, postavka menija, odprtega s tipko Meni,
        # ni bila oznacena - uporabnik ni videl, katero bo sprozil Enter. Postavke dobijo fokus samo s tipkovnico.
        self.assertIn(".spor-meni button:hover, .spor-meni button:focus {", self.css)

    def test_kolesce_ne_premika_strani(self):
        # Kolesce na koncu seznama sporocil ne sme zaceti premikati cele strani.
        self.assertIn("overscroll-behavior: contain", _pravilo(self.css, ".pogovor-vsebina"))

    def test_meni_mehurcka(self):
        meni = _pravilo(self.css, ".spor-meni")
        self.assertIn("position: fixed", meni)
        self.assertIn("display: none", _pravilo(self.css, ".spor-meni[hidden]"))


class Stran(unittest.TestCase):
    def setUp(self):
        self.js = _beri("assets", "os", "os.js")
        self.html = _beri("assets", "os", "index.html")

    def test_meni_je_v_strani(self):
        self.assertRegex(self.html, r'<div class="spor-meni" id="sporocilaMeni" role="menu" hidden></div>')

    def test_dogodki(self):
        js = self.js
        for niz in ('$("sporocilaVsebina").addEventListener("contextmenu"',      # desni klik odpre nas meni
                    '$("sporocilaVsebina").addEventListener("keydown"',           # Ctrl+C, tipka Meni, puscici
                    'fokusNaMehurcek($("sporocilaVsebina"), sosed)',                 # puscici: pomik samo seznama
                    'document.addEventListener("copy"',                           # potrditev »Kopirano«
                    '$("sporocilaVsebina").addEventListener("scroll", obPomikuSporocil);',  # pomik zapre meni (nas popravek ne)
                    'if (p[1] === "odpri") odpriPovezavoSporocila(p[2]);',           # povezava: nov zavihek, razdelek Splet
                    # vrnitev v razdelek: nova sporocila odprtega pogovora se pokazejo
                    'if (razdelek === "sporocila") { sporocilaVrnitev = true; naloziSporocila(); sporocilaZanka(); }',
                    'naloziVsebinoPogovora(pogovor, true);',                         # odpiranje: pogled na zadnje sporocilo
                    'klic("kopiraj", [besedilo])'):
            self.assertIn(niz, js, niz)

    def test_osvezitev_ne_brise_mehurckov(self):
        # Prej: cilj.innerHTML = "" ob vsaki osvezitvi pogovora - izbor besedila je izginil vsakih 30 sekund.
        telo = self.js[self.js.index("  function naloziVsebinoPogovora(pogovor, odpiranje)"):self.js.index("  /* Po osvezitvi seznama")]
        self.assertIn("nacrtMehurckov(", telo)
        self.assertEqual(telo.count('innerHTML = ""'), 1, "brisanje vsega samo, kadar se pogovor res zamenja")

    def test_besedila_v_vseh_jezikih(self):
        besedila = _beri("assets", "os", "besedila.js")
        for kljuc in ("sporKopiraj", "sporKopirajIzbrano", "sporKopirano", "sporOdpriPovezavo"):
            self.assertEqual(len(re.findall(r'"%s":\s*"' % kljuc, besedila)), 6, kljuc)


@unittest.skipUnless(shutil.which("node"), "node ni namescen")
class Logika(unittest.TestCase):
    """Ciste funkcije iz os.js pozenemo v node."""

    # Lazni DOM za risanje pogovora in meni mehurcka (dovolj za funkcije med mehurcekSporocila in naloziVsebinoPogovora).
    LAZNI_DOM = r"""
function El(oznaka) { this.oznaka = oznaka; this.children = []; this.hidden = true; this.scrollTop = 0; this.clientHeight = 200; this._besediloVozla = ""; this.style = {}; this.offsetWidth = 100; this.offsetHeight = 40;
  var r = {}; this.classList = { add: function (x) { r[x] = 1; }, remove: function (x) { delete r[x]; }, contains: function (x) { return !!r[x]; } }; }
El.prototype.appendChild = function (c) { this.children.push(c); c.parentNode = this; return c; };
El.prototype.removeChild = function (c) { this.children.splice(this.children.indexOf(c), 1); c.parentNode = null; return c; };
// Vstavljanje elementa, ki je ze v strani, je PREMIK (brskalnik pri tem podre izbor besedila v njem): stejemo jih.
var premikov = 0;
El.prototype.insertBefore = function (c, pred) {
  if (c.parentNode) { premikov++; c.parentNode.removeChild(c); }
  var i = pred ? this.children.indexOf(pred) : -1;
  if (i < 0) this.children.push(c); else this.children.splice(i, 0, c);
  c.parentNode = this; return c;
};
El.prototype.contains = function (n) { for (; n; n = n.parentNode) if (n === this) return true; return false; };
El.prototype.setAttribute = function () {};
El.prototype.addEventListener = function (vrsta, f) { (this._posl = this._posl || {})[vrsta] = f; };
El.prototype.focus = function (moznosti) { document.activeElement = this; this._fokusMoznosti = moznosti; };
El.prototype.getBoundingClientRect = function () { return this._okvir || { top: 0, bottom: 0 }; };
Object.defineProperty(El.prototype, "firstChild", { get: function () { return this.children[0] || null; } });
Object.defineProperty(El.prototype, "lastElementChild", { get: function () { return this.children[this.children.length - 1] || null; } });
Object.defineProperty(El.prototype, "innerHTML", { set: function (v) { if (v === "") this.children = []; }, get: function () { return ""; } });
Object.defineProperty(El.prototype, "textContent", { set: function (v) { this._besediloVozla = v; }, get: function () { return this._besediloVozla; } });
Object.defineProperty(El.prototype, "scrollHeight", { get: function () { return this.children.length * 60; } });
var vozli = { sporocilaVsebina: new El("div"), sporocilaMeni: new El("div") };
function $(id) { return vozli[id]; }
function el(oznaka, razred, html) { var e = new El(oznaka); e.className = razred || ""; if (html != null) e.html = html; return e; }
function ubezi(s) { return s; }
function kratekCas() { return "10:00"; }
function t(k) { return k; }
var obvestila = [], klici = [], osvezitev = 0, izbor = null, odgovor = [];
// Izid mostu po imenu klica (privzeto true); Error = zavrnjena obljuba. rocno: odgovore na sporocilaPogovor sprozi preizkus.
var izidi = {}, rocno = null;
function obvesti(b) { obvestila.push(b); }
function naloziSporocila() { osvezitev++; }
function narisiSporocila() {}
function klic(m, a) {
  klici.push([m, a]);
  if (m === "sporocilaPogovor") {
    if (rocno) return new Promise(function (r) { rocno.push(r); });
    if (odgovor instanceof Error) return Promise.reject(odgovor);
    return Promise.resolve(odgovor);
  }
  if (izidi[m] instanceof Error) return Promise.reject(izidi[m]);
  return Promise.resolve(m in izidi ? izidi[m] : true);
}
var document = { activeElement: null };
var window = { getSelection: function () { return izbor; }, innerWidth: 1200, innerHeight: 800 };
var S = { sporocilaAktivni: null, razdelek: "sporocila" };
var PREDVAJALNIK = false;      // glavno okno Safeer OS (Safeer Player odpira splet drugace: test_os_predvajalnik_okno)
function s(id, besedilo, smer) { return { id: id, smer: smer || "noter", cas: "2026-10-07T10:" + (id < 10 ? "0" : "") + id, besedilo: besedilo }; }
function cakaj() { return new Promise(function (r) { setTimeout(r, 0); }); }
"""

    # Pomik kot v brskalniku: omejen je na [0, visina vsebine - visina seznama]; ko se vsebina skrajsa, ga brskalnik
    # omeji sam. Mehurcki imajo svojo visino (_visina, privzeto 60), njihov polozaj na zaslonu sledi pomiku.
    MODEL_POMIKA = r"""
var cilj = vozli.sporocilaVsebina;
(function () {
  var st = 0;
  function visina(m) { return m._visina || 60; }
  function vsebina() { return cilj.children.reduce(function (v, m) { return v + visina(m); }, 0); }
  function omeji(v) { return Math.max(0, Math.min(v, vsebina() - cilj.clientHeight)); }
  Object.defineProperty(cilj, "scrollHeight", { get: function () { st = omeji(st); return Math.max(vsebina(), cilj.clientHeight); } });
  Object.defineProperty(cilj, "scrollTop", { get: function () { st = omeji(st); return st; }, set: function (v) { st = omeji(v); } });
  El.prototype.getBoundingClientRect = function () {
    if (this === cilj) return { top: 300, bottom: 300 + cilj.clientHeight };
    if (this.parentNode !== cilj) return this._okvir || { top: 0, bottom: 0 };
    var y = 0, i;
    for (i = 0; cilj.children[i] !== this; i++) y += visina(cilj.children[i]);
    return { top: 300 + y - cilj.scrollTop, bottom: 300 + y - cilj.scrollTop + visina(this) };
  };
})();
function vrh(m) { return m.getBoundingClientRect().top; }
function oznaci(m) { izbor = { isCollapsed: false, rangeCount: 1, anchorNode: m, focusNode: m, toString: function () { return "izbrano"; } }; }
"""

    def setUp(self):
        js = _beri("assets", "os", "os.js")
        self.ciste = js[js.index("  function podpisSporocila(s)"):js.index("  function mehurcekSporocila(s)")]
        self.risanje = js[js.index("  function mehurcekSporocila(s)"):js.index("  /* Po osvezitvi seznama")]
        self.splet = js[js.index("  var brezPeskovnikaOb = 0;"):js.index("  function odpriSplet(naslov, ime)")]
        self.usklajevanje = js[js.index("  /* Po osvezitvi seznama"):js.index("  var sporocilaCasovnik = 0;")]

    def _node(self, koda):
        subprocess.run(["node", "-e", koda], check=True, timeout=60)

    def _stran(self, koda, model=False):
        self._node('var assert = require("assert");\n' + self.LAZNI_DOM + self.splet + self.ciste + self.risanje
                   + self.usklajevanje + (self.MODEL_POMIKA if model else "")
                   + "(async function () {\n" + koda + "\n})().catch(function (e) { console.error(e); process.exit(1); });\n")

    def test_podpis(self):
        self._node('var assert = require("assert");\n' + self.ciste + r"""
var a = { id: "1", smer: "noter", cas: "2026-10-07T10:00:00", besedilo: "Živjo" };
assert.strictEqual(podpisSporocila(a), podpisSporocila(JSON.parse(JSON.stringify(a))));
assert.notStrictEqual(podpisSporocila(a), podpisSporocila(Object.assign({}, a, { besedilo: "Živjo!" })));
assert.notStrictEqual(podpisSporocila(a), podpisSporocila(Object.assign({}, a, { id: "2" })));
assert.notStrictEqual(podpisSporocila({ id: "1", besedilo: "a" }), podpisSporocila({ id: "", besedilo: "1a" }));
""")

    def test_nacrt_ohrani_mehurcke(self):
        """Kar je ze narisano in je v novem seznamu, ostane ISTI element na svojem mestu - tudi kadar sprememba ni samo
        na koncu (pozno dostavljeno sporocilo se uvrsti vmes, z vrha odpade staro, sporocilo se je spremenilo)."""
        self._stran(r"""
var cilj = vozli.sporocilaVsebina, crke = "abcdefgh";
function uporabi(seznam) {
  var nacrt = nacrtMehurckov(cilj, seznam), i;
  nacrt.odvec.forEach(function (m) { cilj.removeChild(m); });
  for (i = 0; i < nacrt.novi.length; i++) if (cilj.children[i] !== nacrt.novi[i]) cilj.insertBefore(nacrt.novi[i], cilj.children[i] || null);
  return nacrt;
}
for (var poskus = 0; poskus < 2000; poskus++) {
  // Stari seznam: urejen izbor sporocil. Novi: nekaj jih odpade (kjerkoli), nekaj novih se uvrsti kamorkoli, kaksno se spremeni.
  var stari = [], novi = [], i;
  for (i = 0; i < crke.length; i++) if (Math.random() < 0.6) stari.push(s(i, crke[i]));
  cilj.innerHTML = ""; stari.forEach(function (x) { cilj.appendChild(mehurcekSporocila(x)); });
  var elementi = cilj.children.slice();
  for (i = 0; i < crke.length; i++) {
    var bil = stari.filter(function (x) { return x.id === i; })[0];
    if (bil && Math.random() < 0.75) novi.push(Math.random() < 0.15 ? s(i, crke[i] + " popravljeno") : bil);
    else if (!bil && Math.random() < 0.4) novi.push(s(i, crke[i]));
  }
  premikov = 0;
  var nacrt = uporabi(novi), opis = JSON.stringify([stari, novi]);
  assert.deepStrictEqual(cilj.children.map(function (m) { return m._podpis; }), novi.map(podpisSporocila), opis);
  assert.strictEqual(premikov, 0, "mehurcek, ki ostane, se ne premakne: " + opis);
  elementi.forEach(function (m, j) {
    var ostane = novi.map(podpisSporocila).indexOf(podpisSporocila(stari[j])) >= 0;
    assert.strictEqual(cilj.children.indexOf(m) >= 0, ostane, "isti element ostane natanko takrat, ko je sporocilo se v seznamu: " + opis);
    assert.strictEqual(nacrt.odvec.indexOf(m) >= 0, !ostane, opis);
  });
  assert.strictEqual(enakiMehurcki(cilj, nacrt.novi), true);
}
// Dve sporocili z enakim podpisom (isti id, cas in besedilo): vsako dobi svoj mehurcek, nobeno ne izgine.
cilj.innerHTML = ""; [s(1, "a"), s(1, "a")].forEach(function (x) { cilj.appendChild(mehurcekSporocila(x)); });
var oba = cilj.children.slice();
uporabi([s(1, "a"), s(1, "a"), s(2, "b")]);
assert.ok(cilj.children.length === 3 && cilj.children[0] === oba[0] && cilj.children[1] === oba[1]);
// Zamenjan vrstni red (cas sporocila se ne spremeni brez spremembe podpisa, a izid mora biti vseeno pravi).
cilj.innerHTML = ""; [s(1, "a"), s(2, "b")].forEach(function (x) { cilj.appendChild(mehurcekSporocila(x)); });
uporabi([s(2, "b"), s(1, "a")]);
assert.deepStrictEqual(cilj.children.map(function (m) { return m._besedilo; }), ["b", "a"]);
// Tuj element med mehurcki (brez podpisa) odpade.
cilj.innerHTML = ""; cilj.appendChild(new El("div")); cilj.appendChild(mehurcekSporocila(s(1, "a")));
uporabi([s(1, "a")]);
assert.strictEqual(cilj.children.length, 1);
""")

    def test_meni_in_povezava(self):
        self._node('var assert = require("assert");\n' + self.ciste + r"""
assert.deepStrictEqual(postavkeMenijaSporocila("Živjo", ""), [["sporKopiraj", "kopiraj", "Živjo"]]);
assert.deepStrictEqual(postavkeMenijaSporocila("Živjo svet", "svet"),
  [["sporKopirajIzbrano", "kopiraj", "svet"], ["sporKopiraj", "kopiraj", "Živjo svet"]]);
// Izbrano je celo sporocilo: ene same stvari ne ponudimo dvakrat.
assert.deepStrictEqual(postavkeMenijaSporocila("Živjo", "Živjo"), [["sporKopiraj", "kopiraj", "Živjo"]]);
// Povezava: postavka nosi naslov, kot ga je razclenil brskalnik, in gostitelja za napis.
assert.deepStrictEqual(postavkeMenijaSporocila("https://safeer.si/os", ""),
  [["sporKopiraj", "kopiraj", "https://safeer.si/os"], ["sporOdpriPovezavo", "odpri", "https://safeer.si/os", "safeer.si"]]);
assert.deepStrictEqual(postavkeMenijaSporocila("glej https://safeer.si", ""), [["sporKopiraj", "kopiraj", "glej https://safeer.si"]]);
assert.deepStrictEqual(postavkeMenijaSporocila("", ""), []);
assert.deepStrictEqual(postavkeMenijaSporocila("", "ostanek izbora"), [["sporKopirajIzbrano", "kopiraj", "ostanek izbora"]]);
assert.deepStrictEqual(povezavaSporocila("  https://a.example/b?c=1 \n"), { naslov: "https://a.example/b?c=1", gostitelj: "a.example" });
assert.deepStrictEqual(povezavaSporocila("http://a.example"), { naslov: "http://a.example/", gostitelj: "a.example" });
// Telefonske tipkovnice zacnejo z veliko zacetnico: naslov je veljaven, gostitelj vedno z malimi crkami.
assert.deepStrictEqual(povezavaSporocila("Https://A.Example:8443/Pot"), { naslov: "https://a.example:8443/Pot", gostitelj: "a.example:8443" });
assert.deepStrictEqual(povezavaSporocila("HTTP://A.EXAMPLE"), { naslov: "http://a.example/", gostitelj: "a.example" });
// Stevilcni zapisi naslova: napis pokaze, kam povezava v resnici vodi.
assert.strictEqual(povezavaSporocila("http://2130706433/").gostitelj, "127.0.0.1");
assert.strictEqual(povezavaSporocila("http://0x7f.1/").gostitelj, "127.0.0.1");
// Tuja pisava v imenu gostitelja: napis je v obliki, kot jo uporabi brskalnik (ne crke, ki so videti kot latinske).
assert.strictEqual(povezavaSporocila("https://\u0430\u0440\u0440\u04cf\u0435.example/").gostitelj.indexOf("xn--"), 0);
["javascript:alert(1)", "file:///etc/passwd", "https://", "https://a.example b", "ftp://a.example", "a https://a.example",
 "https://a.example/<script>", "", null, undefined].forEach(function (b) { assert.strictEqual(povezavaSporocila(b), null, String(b)); });
assert.strictEqual(povezavaSporocila("https://a.example/" + new Array(3000).join("x")), null);
// Zavajajoci naslovi iz tujega besedila: brskalnik bi odprl drug gostitelj, kot ga uporabnik prebere.
[
  "https://www.banka.example@drugje.example/",                    // vse pred @ je uporabnisko ime
  "https://www.banka.example:443@drugje.example/",               // ... in geslo
  "https://uporabnik:geslo@a.example/",
  "https://www.banka.example\u2215prijava\u2215@drugje.example/",  // ulomkova crta namesto posevnice
  "https://a.example\\@drugje.example/",                         // posevnica nazaj
  "https://a.example/\\pot",
  "https://www.banka.example/\u202egro.etis@drugje.example/",     // obrnjena smer pisanja
  "https://a.example/pot\u202ecod.exe",
  "https://a.example/\u2066x\u2069",
  "https://a\u200b.example/",                                     // znak brez sirine
  "https://a.example/\u200dx",
  "https://a.example/\u2060x",
  "https://a.example/\u00adx",                                    // mehki vezaj
  "https://a.example/\ufeffx",
  "https://a.example/\u0001x",                                    // krmilni znak
  "https://a.example/\u007fx",
  "https://a.example/x\u00a0y",                                   // nedeljivi presledek
  "https://a.example/\u3000x",
  "https://a.example/\udb40\udc41x",                              // nevidne oznake
  "https://a.example/\ufe0fx",
  "https://a.example/\ufffdx"
].forEach(function (b) {
  assert.strictEqual(povezavaSporocila(b), null, JSON.stringify(b));
  assert.strictEqual(postavkeMenijaSporocila(b, "").length, 1, "samo »Kopiraj sporocilo«: " + JSON.stringify(b));
});
// Prazno uporabnisko ime ni zavajanje, a v brskalnik gre naslov brez njega.
assert.deepStrictEqual(povezavaSporocila("https://@a.example/x"), { naslov: "https://a.example/x", gostitelj: "a.example" });
// Dolg gostitelj: v napisu ostane viden KONEC (domena), ne zacetek, ki ga doloca posiljatelj.
var dolg = "www.banka.example." + new Array(8).join("abcdefgh.") + "drugje.example";
var napis = postavkeMenijaSporocila("https://" + dolg + "/", "")[1][3];
assert.ok(napis.length === 48 && napis[0] === "…" && /drugje\.example$/.test(napis), napis);
// Naslov IPv6 z vrati (do 47 znakov) ostane cel.
assert.strictEqual(postavkeMenijaSporocila("https://[2001:db8:1111:2222:3333:4444:5555:6666]:8443/", "")[1][3],
  "[2001:db8:1111:2222:3333:4444:5555:6666]:8443");
assert.strictEqual(gostiteljZaNapis("a.example"), "a.example");
""")

    def test_odpri_povezavo(self):
        """»Odpri povezavo«: nov zavihek vgrajenega brskalnika; razdelek Sporocila ni vec odprt (zanka ga ne osvezuje in
        novih sporocil ne oznaci kot prebrana); kadar se povezava ne odpre, uporabnik to izve."""
        self._stran(r"""
var meni = vozli.sporocilaMeni, m = mehurcekSporocila(s(1, "Https://A.Example/pot"));
vozli.sporocilaVsebina.appendChild(m);
pokaziMeniSporocila(m, 10, 10, false);
assert.strictEqual(meni.children.length, 2);
assert.strictEqual(meni.children[1].html, "sporOdpriPovezavo · a.example", "napis pove, kam povezava vodi");
meni.children[1]._posl.click(); await cakaj();
assert.deepStrictEqual(klici[klici.length - 1], ["splet", ["https://a.example/pot", true]]);
assert.strictEqual(S.razdelek, "splet", "brskalnik prekriva vsebino: razdelek Sporocila ni vec odprt");
assert.deepStrictEqual(obvestila, []);

// Gostitelj naslova ne odpre (odgovor false ni napaka obljube): uporabnik to izve, razdelek ostane.
S.razdelek = "sporocila"; izidi.splet = false;
assert.strictEqual(await odpriPovezavoSporocila("https://a.example/"), false);
assert.strictEqual(S.razdelek, "sporocila");
assert.deepStrictEqual(obvestila, ["niUspelo"]);

// Peskovnika ni: gostitelj je pojasnilo pravkar poslal sam - splosno obvestilo ga ne prekrije.
obvestila.length = 0; brezPeskovnikaOb = Date.now();
assert.strictEqual(await odpriPovezavoSporocila("https://a.example/"), false);
assert.deepStrictEqual(obvestila, []);
brezPeskovnikaOb = Date.now() - 1500;
await odpriPovezavoSporocila("https://a.example/");
assert.deepStrictEqual(obvestila, ["niUspelo"], "pojasnilo, starejse od sekunde, ne utisa poznejse napake");

// Uporabnik je med odpiranjem ze odsel drugam (klik v vrstici): razdelka mu ne spreminjamo.
obvestila.length = 0; izidi.splet = true; S.razdelek = "sporocila";
var odpiranje = odpriPovezavoSporocila("https://a.example/");
S.razdelek = "domov";
assert.strictEqual(await odpiranje, true);
assert.strictEqual(S.razdelek, "domov");
S.razdelek = "sporocila"; izidi.splet = false;

// Most odpove.
obvestila.length = 0; izidi.splet = new Error("ni mostu");
assert.strictEqual(await odpriPovezavoSporocila("https://a.example/"), false);
assert.deepStrictEqual(obvestila, ["niUspelo"]);
assert.strictEqual(S.razdelek, "sporocila");

// Drugi klici v Splet (priljubljene strani, katalog): brez novega zavihka, enako obvestilo ob zavrnitvi.
obvestila.length = 0; izidi.splet = true;
assert.strictEqual(await odpriVSpletu("https://b.example/"), true);
assert.deepStrictEqual(klici[klici.length - 1], ["splet", ["https://b.example/"]]);
izidi.splet = false;
assert.strictEqual(await odpriVSpletu("https://b.example/"), false);
assert.deepStrictEqual(obvestila, ["niUspelo"]);
""")

    def test_osvezitev_ohrani_mehurcke(self):
        """Lazni DOM: mehurcek, ki je ze na zaslonu, ob osvezitvi ostane ISTI element."""
        self._stran(r"""
var cilj = vozli.sporocilaVsebina;
var p = { kanal_id: "k", id: "p1", neprebrano: 2 };
S.sporocilaAktivni = p; odgovor = [s(1, "prvo"), s(2, "drugo", "ven")];
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(cilj.children.length, 2);
assert.strictEqual(cilj.children[0]._besedilo, "prvo");
assert.strictEqual(cilj.children[1].className, "mehurcek ven");
assert.strictEqual(cilj.children[0].children[0].textContent, "prvo");            // besedilo v svojem elementu
assert.strictEqual(cilj.children[0].children[1].oznaka, "time");                  // ura posebej (ne gre v izbor)
assert.strictEqual(cilj.scrollTop, cilj.scrollHeight, "odprt pogovor se pomakne na zadnje sporocilo");
assert.strictEqual(osvezitev, 1); assert.strictEqual(p.neprebrano, 0);
assert.deepStrictEqual(cilj.children.map(function (m) { return m.tabIndex; }), [-1, 0], "Tab pride na zadnje sporocilo");

// Novo sporocilo: stara mehurcka ostaneta ISTA elementa.
var prvi = cilj.children[0], drugi = cilj.children[1];
odgovor = [s(1, "prvo"), s(2, "drugo", "ven"), s(3, "tretje")];
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(cilj.children.length, 3);
assert.ok(cilj.children[0] === prvi && cilj.children[1] === drugi, "stara mehurcka nista bila narisana znova");
assert.strictEqual(cilj.scrollTop, cilj.scrollHeight, "na dnu: novo sporocilo se pokaze");
assert.deepStrictEqual(cilj.children.map(function (m) { return m.tabIndex; }), [-1, -1, 0]);

// Nic novega: nic se ne dotakne zaslona.
var tretji = cilj.children[2]; cilj.scrollTop = 7;
naloziVsebinoPogovora(p); await cakaj();
assert.ok(cilj.children.length === 3 && cilj.children[2] === tretji);
assert.strictEqual(cilj.scrollTop, 7, "brez novih sporocil se pogled ne premakne");

// Uporabnik bere starejsa sporocila (ni na dnu): novo sporocilo ga ne potegne dol.
cilj.scrollTop = 0; cilj.clientHeight = 60;
odgovor = odgovor.concat([s(4, "cetrto")]);
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(cilj.children.length, 4);
assert.strictEqual(cilj.scrollTop, 0, "pogled ostane, kjer uporabnik bere");

// Uporabnik pogovor odpre znova (klik v seznamu pogovorov, poslano sporocilo): pokaze se zadnje sporocilo,
// tudi ce so mehurcki se od prej na zaslonu in je bil pogled visje. (V zivo: po vrnitvi v Sporocila je odprt
// pogovor ostal na vrhu.) Osvezitev v ozadju (brez drugega argumenta) pogleda se naprej ne premika.
naloziVsebinoPogovora(p, true); await cakaj();
assert.strictEqual(cilj.scrollTop, cilj.scrollHeight, "odprt pogovor kaze zadnje sporocilo");
cilj.scrollTop = 0;
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(cilj.scrollTop, 0, "osvezitev v ozadju pogleda ne premakne");

// Na dnu, a oznacuje besedilo: pogled ne skoci med oznacevanjem.
cilj.clientHeight = 200; cilj.scrollTop = cilj.scrollHeight - cilj.clientHeight;
izbor = { isCollapsed: false, rangeCount: 1, anchorNode: cilj.children[1], focusNode: cilj.children[1], toString: function () { return "drug"; } };
var pred = cilj.scrollTop;
odgovor = odgovor.concat([s(5, "peto")]);
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(cilj.children.length, 5);
assert.strictEqual(cilj.scrollTop, pred, "med oznacevanjem pogled ne skoci");
assert.ok(cilj.children[1] === drugi, "oznaceni mehurcek je ostal isti element");
izbor = null;

// Okno zadnjih sporocil se premakne: z vrha odpade prvo, ostali ostanejo isti elementi.
odgovor = odgovor.slice(1).concat([s(6, "sesto")]);
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(cilj.children.length, 5);
assert.ok(cilj.children[0] === drugi && cilj.children.indexOf(prvi) < 0);
assert.strictEqual(cilj.children[4]._besedilo, "sesto");

// Spremenjeno sporocilo: nov mehurcek dobi samo to sporocilo, vsi drugi ostanejo isti elementi (izbor v njih ostane).
var stariTretji = cilj.children[1], ostali = [cilj.children[0], cilj.children[2], cilj.children[3], cilj.children[4]];
odgovor = odgovor.map(function (x) { return x.id === 3 ? s(3, "tretje, popravljeno") : x; });
premikov = 0;
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(cilj.children[1]._besedilo, "tretje, popravljeno");
assert.ok(cilj.children.indexOf(stariTretji) < 0, "spremenjeno sporocilo ima nov mehurcek");
assert.deepStrictEqual([cilj.children[0], cilj.children[2], cilj.children[3], cilj.children[4]], ostali);
assert.strictEqual(premikov, 0);

// Drug pogovor: vse novo, pogled na dno.
var q = { kanal_id: "k", id: "p2" }, stariElementi = cilj.children.slice();
S.sporocilaAktivni = q; odgovor = [s(1, "prvo")];
naloziVsebinoPogovora(q); await cakaj();
assert.strictEqual(cilj.children.length, 1);
assert.ok(stariElementi.indexOf(cilj.children[0]) < 0, "drug pogovor z enakim prvim sporocilom je vseeno narisan na novo");

// Odgovor za pogovor, ki ni vec odprt, se zavrze.
S.sporocilaAktivni = p; odgovor = [s(9, "pozno")];
naloziVsebinoPogovora(q); await cakaj();
assert.strictEqual(cilj.children[0]._besedilo, "prvo");

// Kopiranje: besedilo gre v odlozisce prek mostu, uporabnik dobi potrditev.
kopirajBesedilo("prvo"); await cakaj();
assert.deepStrictEqual(klici[klici.length - 1], ["kopiraj", ["prvo"]]);
assert.strictEqual(obvestila[obvestila.length - 1], "sporKopirano");
var prej = klici.length; kopirajBesedilo(""); await cakaj();
assert.strictEqual(klici.length, prej, "praznega besedila ne kopiramo (odlozisce ostane)");
""")

    def test_pogled_ne_skoci_ko_z_vrha_odpade_sporocilo(self):
        """Pogovor je na meji 50 sporocil: ob novem sporocilu z vrha odpade najstarejse. Brskalnik pomik ob krajsanju
        vsebine omeji sam; ce odstranjeno visino odstejemo se enkrat, pogled skoci za visino odpadlega sporocila
        (tretji neodvisni pregled, 7. 10. 2026)."""
        self._stran(r"""
var p = { kanal_id: "k", id: "p1" }, seznam = [], i;
for (i = 1; i <= 10; i++) seznam.push(s(i, "sporocilo " + i));
S.sporocilaAktivni = p; odgovor = seznam.slice();
naloziVsebinoPogovora(p, true); await cakaj();
cilj.children[0]._visina = 300;                       // dolgo sporocilo na vrhu: vsebina 300 + 9 * 60 = 840, seznam 200
assert.strictEqual(cilj.scrollHeight, 840);

// Uporabnik bere 100 px nad koncem (ni »na dnu«, zato ga novo sporocilo ne potegne dol).
cilj.scrollTop = 840 - 200 - 100;
var bere = cilj.children[7], kje = vrh(bere);
assert.ok(kje >= 300 && kje < 500, "sporocilo, ki ga bere, je vidno");
odgovor = seznam.slice(1).concat([s(11, "novo")]);    // z vrha odpade dolgo, na dnu pride novo
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(cilj.children.length, 10);
assert.strictEqual(vrh(bere), kje, "sporocilo, ki ga uporabnik bere, ostane na istem mestu");
assert.strictEqual(cilj.scrollTop, 240);

// Na dnu, a oznacuje besedilo: z vrha odpade visoko sporocilo, pogled ne skoci.
cilj.children[0]._visina = 240;                       // vsebina 240 + 9 * 60 = 780
cilj.scrollTop = cilj.scrollHeight;
assert.strictEqual(cilj.scrollTop, 580);
bere = cilj.children[8]; kje = vrh(bere); oznaci(bere);
seznam = odgovor.slice();
odgovor = seznam.slice(1).concat([s(12, "se eno")]);
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(vrh(bere), kje, "med oznacevanjem pogled ne skoci");
assert.strictEqual(cilj.scrollTop, 340);
izbor = null;

// Na dnu brez izbora: novo sporocilo se pokaze (tudi ko z vrha kaj odpade).
cilj.scrollTop = cilj.scrollHeight;
seznam = odgovor.slice();
odgovor = seznam.slice(1).concat([s(13, "zadnje")]);
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(cilj.scrollTop, cilj.scrollHeight - cilj.clientHeight, "na dnu ostane na dnu");
assert.ok(vrh(cilj.children[cilj.children.length - 1]) < 500, "novo sporocilo je vidno");
""", model=True)

    def test_pozno_sporocilo_se_uvrsti_vmes(self):
        """Sporocilo, ki je cakalo v vrsti, nosi posiljateljev cas in se uvrsti med ze prikazana. Do tega popravka se je
        ves pogovor narisal znova: izbor besedila je izginil in pogled je skocil na dno, kjer novega sporocila ni."""
        self._stran(r"""
var p = { kanal_id: "k", id: "p1" }, seznam = [], i;
for (i = 1; i <= 10; i++) seznam.push(s(2 * i, "sporocilo " + i));
S.sporocilaAktivni = p; odgovor = seznam.slice();
naloziVsebinoPogovora(p, true); await cakaj();
var elementi = cilj.children.slice();

// Uporabnik bere sredino pogovora in oznacuje besedilo; pozno sporocilo se uvrsti NAD tem, kar bere.
cilj.scrollTop = 200;
var bere = cilj.children[4], kje = vrh(bere); oznaci(bere);
pokaziMeniSporocila(bere, 10, 10, false);
assert.strictEqual(vozli.sporocilaMeni.hidden, false);
odgovor = seznam.slice(0, 2).concat([s(5, "pozno dostavljeno")], seznam.slice(2));
premikov = 0;
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(cilj.children.length, 11);
assert.strictEqual(cilj.children[2]._besedilo, "pozno dostavljeno");
assert.deepStrictEqual(cilj.children.filter(function (m) { return m !== cilj.children[2]; }), elementi, "vsi prejsnji mehurcki so isti elementi");
assert.strictEqual(premikov, 0, "noben prikazan mehurcek ni bil premaknjen (izbor besedila ostane)");
assert.strictEqual(vrh(bere), kje, "kar uporabnik bere, ostane na istem mestu");
assert.strictEqual(cilj.scrollTop, 260);
assert.strictEqual(vozli.sporocilaMeni.hidden, false, "meni sporocila, ki ostane, ostane odprt");
obPomikuSporocil();                                   // dogodek scroll, ki ga sprozi nas popravek pomika
assert.strictEqual(vozli.sporocilaMeni.hidden, false, "nas popravek pomika menija ne zapre");
sporocilaLastenPomikOb = Date.now() - 1000;           // pomik, ki ni nas (uporabnik premakne seznam)
obPomikuSporocil();
assert.strictEqual(vozli.sporocilaMeni.hidden, true, "uporabnikov pomik meni zapre");
izbor = null;

// Pozno sporocilo POD tem, kar bere: nic se ne premakne.
seznam = odgovor.slice(); cilj.scrollTop = 120; bere = cilj.children[3]; kje = vrh(bere);
odgovor = seznam.slice(0, 8).concat([s(15, "pozno, nizje")], seznam.slice(8));
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(cilj.children.length, 12);
assert.strictEqual(vrh(bere), kje);
assert.strictEqual(cilj.scrollTop, 120);

// Na dnu brez izbora: po spremembi sredi pogovora ostane na dnu.
seznam = odgovor.slice(); cilj.scrollTop = cilj.scrollHeight;
odgovor = seznam.slice(0, 1).concat([s(3, "se eno pozno")], seznam.slice(1));
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(cilj.scrollTop, cilj.scrollHeight - cilj.clientHeight);

// Sporocilo, ob katerem je odprt meni, odpade: meni se zapre.
var zadnji = cilj.children[cilj.children.length - 1];
pokaziMeniSporocila(zadnji, 10, 10, false);
odgovor = odgovor.slice(0, odgovor.length - 1);
naloziVsebinoPogovora(p); await cakaj();
assert.strictEqual(vozli.sporocilaMeni.hidden, true);
assert.ok(cilj.children.indexOf(zadnji) < 0);
""", model=True)

    def test_po_poslanem_sporocilu_pogled_na_dno(self):
        """Po posiljanju stran pogovor odpre znova (pogled na zadnje sporocilo) in osvezi seznam pogovorov. Ce seznam
        odgovori prej, pogovor zahteva se enkrat - z novim predmetom pogovora - in odgovor na prvo zahtevo se zavrze.
        Uporabnik, ki je pred posiljanjem bral starejsa sporocila, svojega sporocila ni videl."""
        self._stran(r"""
var p = { kanal_id: "k", id: "p1" }, seznam = [], i;
for (i = 1; i <= 10; i++) seznam.push(s(i, "sporocilo " + i));
S.sporocilaAktivni = p; odgovor = seznam.slice();
naloziVsebinoPogovora(p, true); await cakaj();
cilj.scrollTop = 0;                                   // bere starejsa sporocila
odgovor = seznam.concat([s(11, "moje sporocilo", "ven")]);
naloziVsebinoPogovora(p, true);                       // odpriPogovor po posiljanju
var nov = { kanal_id: "k", id: "p1" };                // isti pogovor iz osvezenega seznama (uskladiOdprtPogovor)
S.sporocilaAktivni = nov; naloziVsebinoPogovora(nov);
await cakaj();
assert.strictEqual(cilj.children[cilj.children.length - 1]._besedilo, "moje sporocilo");
assert.strictEqual(cilj.scrollTop, cilj.scrollHeight - cilj.clientHeight, "poslano sporocilo je vidno");
// Velja enkrat: naslednja osvezitev v ozadju pogleda ne premika vec.
cilj.scrollTop = 0;
odgovor = odgovor.concat([s(12, "odgovor")]);
naloziVsebinoPogovora(nov); await cakaj();
assert.strictEqual(cilj.scrollTop, 0);
// Zahteva za drug pogovor ne velja za tega.
var q = { kanal_id: "k", id: "p2" };
naloziVsebinoPogovora(q, true);                       // odgovor se zavrze (pogovor q ni odprt)
odgovor = odgovor.concat([s(13, "se en odgovor")]);
naloziVsebinoPogovora(nov); await cakaj();
assert.strictEqual(cilj.scrollTop, 0, "pogled na dno velja samo za pogovor, ki ga je uporabnik odprl");
""", model=True)

    def test_starejsi_odgovor_ne_povozi_novejsega(self):
        """Odgovori mostu ne pridejo nujno v vrstnem redu zahtev (pogovor bere delovna nit)."""
        self._stran(r"""
var cilj = vozli.sporocilaVsebina, p = { kanal_id: "k", id: "p1" };
S.sporocilaAktivni = p; odgovor = [s(1, "prvo")];
naloziVsebinoPogovora(p, true); await cakaj();
rocno = [];
naloziVsebinoPogovora(p);                             // starejsa zahteva (pred novim sporocilom)
naloziVsebinoPogovora(p);                             // novejsa zahteva
rocno[1]([s(1, "prvo"), s(2, "novo")]); await cakaj();
assert.strictEqual(cilj.children.length, 2);
rocno[0]([s(1, "prvo")]); await cakaj();              // zapozneli odgovor na starejso zahtevo
assert.strictEqual(cilj.children.length, 2, "novo sporocilo ne izgine z zaslona");
assert.strictEqual(cilj.children[1]._besedilo, "novo");
""")

    def test_vrnitev_v_razdelek_pokaze_nova_sporocila(self):
        """Uporabnik se vrne v Sporocila (iz brskalnika ali drugega razdelka), v odprtem pogovoru ga caka novo
        sporocilo. Branje pogovora sporocilo oznaci kot prebrano, zato ga mora uporabnik tudi videti: ob vrnitvi gre
        pogled na zadnje sporocilo. Osvezitev v ozadju (uporabnik je ves cas v razdelku) pogleda ne premika."""
        self._stran(r"""
var p = { kanal_id: "k", id: "p1", cas: "c1", zadnje_sporocilo: "sporocilo 10" }, seznam = [], i;
for (i = 1; i <= 10; i++) seznam.push(s(i, "sporocilo " + i));
S.sporocilaAktivni = p; odgovor = seznam.slice();
naloziVsebinoPogovora(p, true); await cakaj();
cilj.scrollTop = 0;                                   // pogled ni na koncu (bral je starejsa ali ga je brskalnik ponastavil)
function seznamZ(pogovor) { S.sporocilaSkupine = [{ oseba: { ime: "Oseba" }, pogovori: [pogovor] }]; }

// Vrnitev: novo neprebrano sporocilo se pokaze.
var nov = { kanal_id: "k", id: "p1", cas: "c2", zadnje_sporocilo: "novo", neprebrano: 1 };
seznamZ(nov); odgovor = seznam.concat([s(11, "novo")]);
sporocilaVrnitev = true;                              // to naredi pojdi("sporocila")
uskladiOdprtPogovor(); await cakaj();
assert.strictEqual(S.sporocilaAktivni, nov);
assert.strictEqual(cilj.children[cilj.children.length - 1]._besedilo, "novo");
assert.strictEqual(cilj.scrollTop, cilj.scrollHeight - cilj.clientHeight, "novo sporocilo je vidno");
assert.strictEqual(sporocilaVrnitev, false, "velja za eno osvezitev");

// Osvezitev v ozadju: pogled ostane, kjer uporabnik bere.
cilj.scrollTop = 0;
var nov2 = { kanal_id: "k", id: "p1", cas: "c3", zadnje_sporocilo: "se eno", neprebrano: 1 };
seznamZ(nov2); odgovor = odgovor.concat([s(12, "se eno")]);
uskladiOdprtPogovor(); await cakaj();
assert.strictEqual(cilj.children.length, 12);
assert.strictEqual(cilj.scrollTop, 0, "osvezitev v ozadju pogleda ne premakne");

// Vrnitev brez novega sporocila: nic se ne nalaga in nic ne premakne; zastavica se vseeno porabi.
var klicev = klici.length;
sporocilaVrnitev = true;
uskladiOdprtPogovor(); await cakaj();
assert.strictEqual(klici.length, klicev);
assert.strictEqual(sporocilaVrnitev, false);
assert.strictEqual(cilj.scrollTop, 0);

// Vrnitev, sprememba pa ni novo neprebrano sporocilo (npr. poslano z druge naprave): pogled ostane.
sporocilaVrnitev = true;
var nov3 = { kanal_id: "k", id: "p1", cas: "c4", zadnje_sporocilo: "moje", neprebrano: 0 };
seznamZ(nov3); odgovor = odgovor.concat([s(13, "moje", "ven")]);
uskladiOdprtPogovor(); await cakaj();
assert.strictEqual(cilj.children.length, 13);
assert.strictEqual(cilj.scrollTop, 0);
""", model=True)

    def test_napaka_mostu_ne_pusti_zastavice(self):
        """Zahteva po pogovoru odpove: »pogled na zadnje sporocilo« ne sme ostati v zraku in ob naslednji osvezitvi v
        ozadju premakniti pogleda."""
        self._stran(r"""
var p = { kanal_id: "k", id: "p1" }, seznam = [], i;
for (i = 1; i <= 10; i++) seznam.push(s(i, "sporocilo " + i));
S.sporocilaAktivni = p; odgovor = seznam.slice();
naloziVsebinoPogovora(p, true); await cakaj();
cilj.scrollTop = 0;
odgovor = new Error("most ne odgovori");
naloziVsebinoPogovora(p, true); await cakaj();       // uporabnik klikne pogovor, zahteva odpove
assert.strictEqual(cilj.children.length, 10, "na zaslonu ostane, kar je bilo");
odgovor = seznam.concat([s(11, "novo")]);
naloziVsebinoPogovora(p); await cakaj();             // naslednja osvezitev v ozadju
assert.strictEqual(cilj.children.length, 11);
assert.strictEqual(cilj.scrollTop, 0, "osvezitev v ozadju pogleda ne premakne");
""", model=True)

    def test_meni_s_tipkovnico_vrne_fokus(self):
        """Dejanje menija, sprozeno s tipkovnico, vrne fokus na sporocilo (prej je padel na telo strani)."""
        self._stran(r"""
var meni = vozli.sporocilaMeni, m = mehurcekSporocila({ id: 1, smer: "noter", cas: "2026-10-07T10:00", besedilo: "prvo sporocilo" });
vozli.sporocilaVsebina.appendChild(m);
// Tipka Meni: meni se odpre, fokus gre na prvo postavko.
m.focus();
pokaziMeniSporocila(m, 10, 10, true);
assert.strictEqual(meni.hidden, false);
assert.strictEqual(meni.children.length, 1);
assert.ok(document.activeElement === meni.children[0], "fokus na prvi postavki");
meni.children[0]._posl.click();                 // Enter na postavki
await cakaj();
assert.strictEqual(meni.hidden, true);
assert.deepStrictEqual(klici[klici.length - 1], ["kopiraj", ["prvo sporocilo"]]);
assert.ok(document.activeElement === m, "fokus se vrne na sporocilo");
assert.ok(m.classList.contains("fokus-tipke"), "in sporocilo ima vidno obrobo");
// Z misko: pritisk na postavko fokusa ne prestavlja (mousedown je preklican), zato ga tudi ne vracamo -
// izbor cez vec sporocil mora ostati.
var drugje = new El("input"); drugje.focus();
pokaziMeniSporocila(m, 10, 10, false);
assert.ok(document.activeElement === drugje);
meni.children[0]._posl.click();
await cakaj();
assert.ok(document.activeElement === drugje, "klik z misko fokusa ne premakne");
""")

    def test_puscice_premaknejo_samo_seznam(self):
        """Puscica na sosednje sporocilo: premakne se seznam sporocil, ne cela stran.

        V zivo (zabojnik, 7. 10. 2026): focus() na visok mehurcek je premaknil tudi stran - glava Safeer OS je sla
        delno z zaslona. Zato fokus brez pomika (preventScroll) in pomik samo seznama.
        """
        self._node('var assert = require("assert");\n' + self.LAZNI_DOM + self.splet + self.ciste + self.risanje + r"""
var cilj = vozli.sporocilaVsebina;
cilj._okvir = { top: 300, bottom: 700 };
function mehurcek(vrh, dno) { var m = new El("div"); m._okvir = { top: vrh, bottom: dno }; return m; }
// Nad vidnim delom in visji od seznama (dolgo sporocilo): njegov vrh pride tik pod vrh seznama.
var visok = mehurcek(-900, 250); cilj.scrollTop = 2000;
fokusNaMehurcek(cilj, visok);
assert.ok(document.activeElement === visok);
assert.deepStrictEqual(visok._fokusMoznosti, { preventScroll: true }, "brskalnik strani ne sme premikati");
assert.ok(visok.classList.contains("fokus-tipke"), "s tipkovnico izbrano sporocilo dobi vidno obrobo");
assert.strictEqual(cilj.scrollTop, 2000 - (300 + 900) - 8);
// Pod vidnim delom, kratek: pokaze se cel.
var spodnji = mehurcek(650, 760); cilj.scrollTop = 100;
fokusNaMehurcek(cilj, spodnji);
assert.strictEqual(cilj.scrollTop, 100 + (760 - 700) + 8);
// Pod vidnim delom, visji od seznama: pokaze se njegov zacetek, ne konec.
var dolg = mehurcek(650, 2000); cilj.scrollTop = 100;
fokusNaMehurcek(cilj, dolg);
assert.strictEqual(cilj.scrollTop, 100 + (650 - 300) - 8);
// Ze viden: nic se ne premakne. Visok, ki se zacne na vrhu seznama: tudi ne (ne skace nazaj).
var viden = mehurcek(320, 400); cilj.scrollTop = 55;
fokusNaMehurcek(cilj, viden);
assert.strictEqual(cilj.scrollTop, 55);
fokusNaMehurcek(cilj, mehurcek(304, 1500));
assert.strictEqual(cilj.scrollTop, 55);
fokusNaMehurcek(cilj, null);                       // ni soseda: brez napake
""")


class Odlozisce(unittest.TestCase):
    def setUp(self):
        import safeer_os
        self.os_ = safeer_os

    def _kopiraj(self, besedilo):
        with mock.patch.object(self.os_, "Gtk") as gtk, mock.patch.object(self.os_, "Gdk"):
            izid = self.os_.SafeerOS._kopiraj(besedilo)
            return izid, gtk.Clipboard.get.return_value

    def test_dolgo_sporocilo_gre_celo(self):
        # Do 0.4.65: besedilo[:8192] (dovolj za magnet povezavo, premalo za dolgo e-sporocilo).
        besedilo = "Dolgo sporočilo. " * 2000
        izid, odlozisce = self._kopiraj(besedilo)
        self.assertTrue(izid)
        odlozisce.set_text.assert_called_once_with(besedilo, -1)
        odlozisce.store.assert_called_once()

    def test_prazno_besedilo_ne_izprazni_odlozisca(self):
        izid, odlozisce = self._kopiraj("")
        self.assertFalse(izid)
        odlozisce.set_text.assert_not_called()

    def test_zgornja_meja(self):
        izid, odlozisce = self._kopiraj("x" * (self.os_.NAJVEC_KOPIJE + 500))
        self.assertTrue(izid)
        self.assertEqual(len(odlozisce.set_text.call_args[0][0]), self.os_.NAJVEC_KOPIJE)


if __name__ == "__main__":
    unittest.main()
