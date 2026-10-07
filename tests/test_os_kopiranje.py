"""Safeer OS, Sporocila: sporocilo se da oznaciti in kopirati.

Do Safeer OS 0.4.65 je bila vsa stran neizberljiva (`body { user-select: none }`), sistemski meni pogleda je izklopljen
(`context-menu` -> True), mehurcek sporocila pa ni imel svojega menija - sporocila ni bilo mogoce kopirati.
Tu preverimo:
  - slog: besedilo mehurcka je izberljivo, ura ne; meni mehurcka obstaja;
  - logiko (node): podpis sporocila, kaj ob osvezitvi ostane na zaslonu, postavke menija, povezava;
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
                    'naloziVsebinoPogovora(pogovor, true);',                         # odpiranje: pogled na zadnje sporocilo
                    'klic("kopiraj", [besedilo])'):
            self.assertIn(niz, js, niz)

    def test_osvezitev_ne_brise_mehurckov(self):
        # Prej: cilj.innerHTML = "" ob vsaki osvezitvi pogovora - izbor besedila je izginil vsakih 30 sekund.
        telo = self.js[self.js.index("  function naloziVsebinoPogovora(pogovor, odpiranje)"):self.js.index("  /* Po osvezitvi seznama")]
        self.assertIn("premikSporocil(", telo)
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
function obvesti(b) { obvestila.push(b); }
function naloziSporocila() { osvezitev++; }
function klic(m, a) { klici.push([m, a]); return Promise.resolve(m === "sporocilaPogovor" ? odgovor : true); }
var document = { activeElement: null };
var window = { getSelection: function () { return izbor; }, innerWidth: 1200, innerHeight: 800 };
var S = { sporocilaAktivni: null };
"""

    def setUp(self):
        js = _beri("assets", "os", "os.js")
        self.ciste = js[js.index("  function podpisSporocila(s)"):js.index("  function mehurcekSporocila(s)")]
        self.risanje = js[js.index("  function mehurcekSporocila(s)"):js.index("  /* Po osvezitvi seznama")]

    def _node(self, koda):
        subprocess.run(["node", "-e", koda], check=True, timeout=60)

    def test_podpis_in_premik(self):
        self._node('var assert = require("assert");\n' + self.ciste + r"""
var a = { id: "1", smer: "noter", cas: "2026-10-07T10:00:00", besedilo: "Živjo" };
assert.strictEqual(podpisSporocila(a), podpisSporocila(JSON.parse(JSON.stringify(a))));
assert.notStrictEqual(podpisSporocila(a), podpisSporocila(Object.assign({}, a, { besedilo: "Živjo!" })));
assert.notStrictEqual(podpisSporocila(a), podpisSporocila(Object.assign({}, a, { id: "2" })));
assert.notStrictEqual(podpisSporocila({ id: "1", besedilo: "a" }), podpisSporocila({ id: "", besedilo: "1a" }));
// Kaj ostane na zaslonu: [koliko z vrha odpade, od katerega novega dodajamo] ali null = narisi vse znova.
assert.strictEqual(premikSporocil(null, ["a"]), null);
assert.strictEqual(premikSporocil([], ["a"]), null);
assert.strictEqual(premikSporocil(["a"], []), null);
assert.deepStrictEqual(premikSporocil(["a", "b"], ["a", "b"]), [0, 2]);          // nic novega: nic se ne spremeni
assert.deepStrictEqual(premikSporocil(["a", "b"], ["a", "b", "c"]), [0, 2]);     // novo sporocilo na dnu
assert.deepStrictEqual(premikSporocil(["a", "b", "c"], ["b", "c", "d"]), [1, 2]); // okno zadnjih 50 se je premaknilo
assert.deepStrictEqual(premikSporocil(["a", "b", "c"], ["c", "d", "e"]), [2, 1]);
assert.strictEqual(premikSporocil(["a", "b"], ["a", "x", "c"]), null);           // spremenjeno sporocilo
assert.strictEqual(premikSporocil(["a", "b"], ["x", "y"]), null);
assert.strictEqual(premikSporocil([undefined, "b"], ["a", "b"]), null);          // tuj element med mehurcki
// Lastnost: z vrha odstranimo premik[0], dodamo novi od premik[1] naprej -> na zaslonu je natanko novi seznam.
var crke = "abcdef";
for (var poskus = 0; poskus < 3000; poskus++) {
  var stari = [], novi = [], i;
  for (i = Math.floor(Math.random() * 6); i > 0; i--) stari.push(crke[Math.floor(Math.random() * 6)] + i);
  novi = stari.slice(Math.floor(Math.random() * (stari.length + 1)));
  for (i = Math.floor(Math.random() * 4); i > 0; i--) novi.push("n" + i + poskus);
  if (Math.random() < 0.2 && novi.length) novi[Math.floor(Math.random() * novi.length)] = "drugo";
  var p = premikSporocil(stari, novi);
  if (p) assert.deepStrictEqual(stari.slice(p[0]).concat(novi.slice(p[1])), novi, JSON.stringify([stari, novi, p]));
}
""")

    def test_meni_in_povezava(self):
        self._node('var assert = require("assert");\n' + self.ciste + r"""
assert.deepStrictEqual(postavkeMenijaSporocila("Živjo", ""), [["sporKopiraj", "kopiraj", "Živjo"]]);
assert.deepStrictEqual(postavkeMenijaSporocila("Živjo svet", "svet"),
  [["sporKopirajIzbrano", "kopiraj", "svet"], ["sporKopiraj", "kopiraj", "Živjo svet"]]);
// Izbrano je celo sporocilo: ene same stvari ne ponudimo dvakrat.
assert.deepStrictEqual(postavkeMenijaSporocila("Živjo", "Živjo"), [["sporKopiraj", "kopiraj", "Živjo"]]);
assert.deepStrictEqual(postavkeMenijaSporocila("https://safeer.si/os", ""),
  [["sporKopiraj", "kopiraj", "https://safeer.si/os"], ["sporOdpriPovezavo", "odpri", "https://safeer.si/os"]]);
assert.deepStrictEqual(postavkeMenijaSporocila("glej https://safeer.si", ""), [["sporKopiraj", "kopiraj", "glej https://safeer.si"]]);
assert.deepStrictEqual(postavkeMenijaSporocila("", ""), []);
assert.deepStrictEqual(postavkeMenijaSporocila("", "ostanek izbora"), [["sporKopirajIzbrano", "kopiraj", "ostanek izbora"]]);
assert.strictEqual(povezavaSporocila("  https://a.example/b?c=1 \n"), "https://a.example/b?c=1");
assert.strictEqual(povezavaSporocila("http://a.example"), "http://a.example");
["javascript:alert(1)", "file:///etc/passwd", "https://", "https://a.example b", "ftp://a.example", "a https://a.example",
 "https://a.example/<script>", "", null, undefined].forEach(function (b) { assert.strictEqual(povezavaSporocila(b), "", String(b)); });
assert.strictEqual(povezavaSporocila("https://a.example/" + new Array(3000).join("x")), "");
""")

    def test_osvezitev_ohrani_mehurcke(self):
        """Lazni DOM: mehurcek, ki je ze na zaslonu, ob osvezitvi ostane ISTI element."""
        self._node('var assert = require("assert");\n' + self.LAZNI_DOM + self.ciste + self.risanje + r"""
function s(id, besedilo, smer) { return { id: id, smer: smer || "noter", cas: "2026-10-07T10:0" + id, besedilo: besedilo }; }
function cakaj() { return new Promise(function (r) { setTimeout(r, 0); }); }
var cilj = vozli.sporocilaVsebina;
(async function () {
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

  // Spremenjeno sporocilo: narisemo znova (vsebina mora biti prava).
  odgovor = odgovor.map(function (x) { return x.id === 3 ? s(3, "tretje, popravljeno") : x; });
  naloziVsebinoPogovora(p); await cakaj();
  assert.ok(cilj.children.indexOf(drugi) < 0, "po spremembi so mehurcki novi");
  assert.strictEqual(cilj.children[1]._besedilo, "tretje, popravljeno");

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
})().catch(function (e) { console.error(e); process.exit(1); });
""")

    def test_meni_s_tipkovnico_vrne_fokus(self):
        """Dejanje menija, sprozeno s tipkovnico, vrne fokus na sporocilo (prej je padel na telo strani)."""
        self._node('var assert = require("assert");\n' + self.LAZNI_DOM + self.ciste + self.risanje + r"""
function cakaj() { return new Promise(function (r) { setTimeout(r, 0); }); }
(async function () {
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
})().catch(function (e) { console.error(e); process.exit(1); });
""")

    def test_puscice_premaknejo_samo_seznam(self):
        """Puscica na sosednje sporocilo: premakne se seznam sporocil, ne cela stran.

        V zivo (zabojnik, 7. 10. 2026): focus() na visok mehurcek je premaknil tudi stran - glava Safeer OS je sla
        delno z zaslona. Zato fokus brez pomika (preventScroll) in pomik samo seznama.
        """
        self._node('var assert = require("assert");\n' + self.LAZNI_DOM + self.ciste + self.risanje + r"""
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
