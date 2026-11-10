"""Klik na film predvaja takoj in »Predvajaj na TV« (lastnik 10. 11. 2026, popis #5 in #22; TV GlasbaActivity klik ->
izberiTok, meni kartice »Izberi vir«). Prave funkcije iz assets/os/os.js in pravila assets/os/predvajaj_na_tv_pravila.js v
node; Link je lazen (klic), brez omrezja in brez prave TV."""
import json
import os
import shutil
import subprocess
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _funkcija(js, ime):
    return "function %s(" % ime + js.split("  function %s(" % ime, 1)[1].split("\n  }\n", 1)[0] + "\n  }\n"


def _klik_kartice(js):
    """Telo card.onclick iz narisiKatalog (kartica kataloga)."""
    zacetek = js.index('      card.onclick = function () {\n        if (x.vrsta === "twitch-kanal") {')
    konec = js.index("\n      };\n", zacetek)
    return js[zacetek:konec] + "\n      };\n"


OKOLJE = r"""
function Seznam() { this.c = {}; }
Seznam.prototype.add = function (k) { this.c[k] = true; };
Seznam.prototype.remove = function (k) { delete this.c[k]; };
Seznam.prototype.toggle = function (k, v) { this.c[k] = !!v; };
function El(tag, razred, html) { this.tag = tag; this.className = razred || ""; this.html = html || ""; this.otroci = [];
  this.atr = {}; this.hidden = false; this.textContent_ = ""; this.classList = new Seznam(); this.posluh = {}; }
Object.defineProperty(El.prototype, "textContent", { get: function () { return this.textContent_ + this.otroci.map(function (o) { return o.textContent; }).join(""); },
  set: function (v) { this.textContent_ = String(v); this.otroci = []; } });
Object.defineProperty(El.prototype, "innerHTML", { set: function (v) { this.html = v; this.otroci = []; this.textContent_ = ""; } });
El.prototype.appendChild = function (o) { this.otroci.push(o); return o; };
El.prototype.setAttribute = function (k, v) { this.atr[k] = String(v); };
El.prototype.getAttribute = function (k) { return this.atr[k]; };
El.prototype.removeAttribute = function (k) { delete this.atr[k]; };
El.prototype.addEventListener = function (k, f) { this.posluh[k] = f; };
El.prototype.focus = function () { fokus.push(this); };
El.prototype.getBoundingClientRect = function () { return { left: 0, top: 0, bottom: 0 }; };
El.prototype.querySelector = function (s) { var r = null; (function isci(v) { v.otroci.forEach(function (o) {
  if (!r && s === "[role=menuitem]" && o.atr.role === "menuitem") r = o; if (!r) isci(o); }); })(this); return r; };
Object.defineProperty(El.prototype, "lastChild", { get: function () { return this.otroci[this.otroci.length - 1]; } });
function el(tag, razred, html) { var e = new El(tag, razred, html); if (html && html.indexOf("<") < 0) e.textContent_ = html; return e; }
// Besedilo gumba v meniju: zadnji <span>…</span> v html (ubezi je identiteta - preizkus vidi, kar bi bilo ubezano).
function napis(b) { var m = /<span>(.*)<\/span>$/.exec(b.html || ""); return m ? m[1] : b.textContent; }
function ubezi(x) { return String(x).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function svg() { return "<svg/>"; }
var elementi = {}, fokus = [], obvestila = [], klici = [], odzivi = {}, dejanja = [];
function $(id) { return elementi[id] || (elementi[id] = new El("div")); }
var jezik = "sl";
function t(k, z) { var b = (BESEDILA_OS[jezik] && BESEDILA_OS[jezik][k]); if (b == null) b = k;
  if (z) Object.keys(z).forEach(function (x) { b = b.split("{" + x + "}").join(z[x]); }); return b; }
function klic(ime, a) { klici.push([ime, a]); var o = odzivi[ime];
  if (o && o.zavrni) return Promise.reject(new Error("x"));
  return Promise.resolve(typeof o === "function" ? o(a) : o); }
function obvesti(b) { obvestila.push(String(b)); }
var obvestiloCas = 0;
function skrijObvestilo() { dejanja.push("skrij"); }
function postaviPlavajoce() {}
function zapriMeniKartice() { $("mediaKarticaMeni").hidden = true; return true; }
function jePriljubljena() { return false; } function jeOgledano() { return false; }
function preklopiPriljubljeno() {} function preklopiOgledano() {}
function odpriKatalogPodrobnosti(id, r, m) { dejanja.push(["podrobnosti", id, m || null]); }
function odpriTwitchKanal() { dejanja.push("twitch"); }
function nastaviVrsto() {} function narisiVrsto() {}
function katSplet() {} function spZacni() {} function odpriLokalno() {} function zapriKatalogPodrobnosti() {}
function narisiKatalog() {} function potrdiRoj() {} function spOpusti() {} function osveziKatTrak() {} function zapomniZadnjiSeznam() {}
var MEDIA_UKREPAJ = { ni_prostora: 1 };
var kat = { zahtevaVnosa: 0, zahtevaPredvajanja: 0, katalog: [], strani: [], vrsta: [] };
var window = {};
function pocakaj(f) { setTimeout(function () { setTimeout(function () { setTimeout(f, 0); }, 0); }, 0); }
"""


class KlikPredvaja(unittest.TestCase):
    def setUp(self):
        if not shutil.which("node"):
            raise unittest.SkipTest("node ni namescen")
        pot = os.path.join(KOREN, "assets", "os")
        js = open(os.path.join(pot, "os.js"), encoding="utf-8").read()
        self.koda = (open(os.path.join(pot, "besedila.js"), encoding="utf-8").read() + "\n" +
                     open(os.path.join(pot, "predvajaj_na_tv_pravila.js"), encoding="utf-8").read() + "\n" + OKOLJE +
                     "".join(_funkcija(js, ime) for ime in (
                         "odpriKatalogVnos", "razlogNeuspeha", "obvestiNeuspeh", "predvajajFilmTakoj", "izberiVirFilma",
                         "naloziNapraveZaPredvajanje", "imdbVnosa", "poljaFilma", "poljaEpizode", "besediloPredvajanjaNa",
                         "predvajajNa", "postavkePredvajajNa", "odpriMeniNaprav", "gumbPredvajajNa", "odpriMeniKartice"))
                     + "var PNT = { naprave: [], cas: 0, nalagam: false, cakajo: [] };\n"
                     + "function kartica(x) { var card = new El('div'); x = x;\n" + _klik_kartice(js).replace("card.onclick", "card.klik")
                     + "  return card; }\n")

    def _node(self, koda):
        r = subprocess.run(["node", "-"], input=self.koda + koda, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        return json.loads(r.stdout)

    # ---------------------------------------------------------------- #5 klik na film
    def test_klik_na_film_predvaja_takoj(self):
        izid = self._node(r"""
        odzivi.mediaFilm = { id: "vnos-1" };
        odzivi.mediaPredvajaj = { id: "vnos-1", url: "https://cdn/x.mkv", naslov: "F" };
        kartica({ id: "tmdb:1", vrsta: "film", tmdb_id: 7, naslov: "Film" }).klik();
        pocakaj(function () { console.log(JSON.stringify([klici, dejanja, kat.aktivni ? kat.aktivni.url : null])); });
        """)
        self.assertEqual(izid[0], [["mediaFilm", [7, "Film"]], ["mediaPredvajaj", ["vnos-1"]]])
        self.assertEqual(izid[1], [], "podrobnosti se NE odprejo")
        self.assertEqual(izid[2], "https://cdn/x.mkv")

    def test_film_iz_dodatka_brez_tmdb(self):
        izid = self._node(r"""
        odzivi.mediaPredvajaj = { id: "s:1", url: "https://cdn/y.mkv" };
        kartica({ id: "s:1", vrsta: "film", url: "stremio:https://d|movie|tt0000001" }).klik();
        pocakaj(function () { console.log(JSON.stringify(klici)); });
        """)
        self.assertEqual(izid, [["mediaPredvajaj", ["s:1"]]])

    def test_serija_odpre_epizode(self):
        izid = self._node(r"""
        kartica({ id: "tmdb:tv:2", vrsta: "serija", tmdb_id: 2, naslov: "S" }).klik();
        pocakaj(function () { console.log(JSON.stringify([klici, dejanja])); });
        """)
        self.assertEqual(izid, [[], [["podrobnosti", "tmdb:tv:2", None]]])

    def test_neuspeh_razlog_in_izberi_vir(self):
        izid = self._node(r"""
        var rez = [];
        odzivi.mediaFilm = { id: "v" };
        var primeri = [null, { napaka_koda: "tok" }, { napaka_koda: "debrid_ni_predpomnjeno" }, { napaka_koda: "ni_toka", vrsta: "film", id: "v" },
                       { napaka_koda: "nekaj" }];
        var i = 0;
        function naslednji() {
          if (i >= primeri.length) { console.log(JSON.stringify(rez)); return; }
          var p = primeri[i++];
          odzivi.mediaPredvajaj = p; dejanja.length = 0;
          var o = $("obvestilo"); o.otroci = []; o.textContent_ = "";
          kartica({ id: "tmdb:1", vrsta: "film", tmdb_id: 7, naslov: "Film" }).klik();
          pocakaj(function () {
            var g = o.otroci[1];
            rez.push([o.otroci[0] ? o.otroci[0].textContent : null, g ? g.textContent : null]);
            if (g) g.posluh.click();
            rez.push(dejanja.slice());
            naslednji();
          });
        }
        naslednji();
        """)
        besedila = [r[0] for r in izid[0::2]]
        self.assertEqual(besedila, ["Filma ni bilo mogoče predvajati: viri se niso odzvali.",
                                    "Filma ni bilo mogoče predvajati: izbrani vir se ni začel predvajati.",
                                    "Filma ni bilo mogoče predvajati: storitev debrid vira ni pripravila.",
                                    "Filma ni bilo mogoče predvajati: noben vir ga zdaj ne ponuja.",
                                    "Filma ni bilo mogoče predvajati."])
        self.assertTrue(all(r[1] == "Izberi vir" for r in izid[0::2]))
        # Gumb odpre podrobnosti z odprtim seznamom virov.
        for d in izid[1::2]:
            self.assertEqual(d, ["skrij", ["podrobnosti", "tmdb:1", {"izberiVir": True}]])

    def test_drugi_klici_ostanejo_tihi(self):
        # Polica, vrsta, naslednja epizoda: brez moznosti izberiVir ni novega obvestila (kot prej).
        izid = self._node(r"""
        odzivi.mediaPredvajaj = { napaka_koda: "tok" };
        odpriKatalogVnos("x");
        pocakaj(function () { console.log(JSON.stringify([obvestila, $("obvestilo").otroci.length])); });
        """)
        self.assertEqual(izid, [[], 0])

    # ---------------------------------------------------------------- meni kartice
    def _meni(self, naprave, x='{ id: "tmdb:1", vrsta: "film", tmdb_id: 7, naslov: "Film", imdb_id: "tt0133093" }'):
        return self._node(r"""
        PNT.naprave = %s; PNT.cas = Date.now();
        var card = new El("div"); card._opis = { kljuc: "k", naslov: "Film", film: %s };
        odpriMeniKartice(card);
        var m = $("mediaKarticaMeni");
        var postavke = m.otroci.filter(function (b) { return b.atr.role === "menuitem"; });
        console.log(JSON.stringify([postavke.map(napis), m.hidden, fokus.length]));
        """ % (json.dumps(naprave), x))

    def test_meni_ena_tv(self):
        izid = self._meni([{"id": "tv1", "ime": "Dnevna TV"}])
        self.assertEqual(izid[0][:3], ["Podrobnosti", "Izberi vir", "Predvajaj na: Dnevna TV"])
        self.assertFalse(izid[1])
        self.assertEqual(izid[2], 1, "fokus na prvi postavki")

    def test_meni_brez_tv_ali_brez_imdb(self):
        self.assertNotIn("Predvajaj na", " ".join(self._meni([])[0]))
        brez = self._meni([{"id": "tv1", "ime": "TV"}], '{ id: "tmdb:1", vrsta: "film", tmdb_id: 7, naslov: "Film" }')
        self.assertEqual(brez[0][:2], ["Podrobnosti", "Izberi vir"])
        self.assertNotIn("Predvajaj na", " ".join(brez[0]))

    def test_vec_tv_podmeni(self):
        izid = self._node(r"""
        PNT.naprave = [{ id: "a", ime: "Dnevna" }, { id: "b", ime: "<b>Spalnica</b>" }]; PNT.cas = Date.now();
        odzivi.predvajajNaNapravi = { ok: true };
        var card = new El("div"); card._opis = { kljuc: "k", naslov: "Film", film: { id: "x", vrsta: "film", imdb_id: "tt0133093", naslov: "Film" } };
        odpriMeniKartice(card);
        var m = $("mediaKarticaMeni");
        var vec = m.otroci.filter(function (b) { return napis(b) === "Predvajaj na TV …"; })[0];
        var haspopup = vec.atr["aria-haspopup"];
        vec.posluh.click({ stopPropagation: function () {} });
        var imena = m.otroci.filter(function (b) { return b.atr.role === "menuitem"; }).map(napis);
        m.otroci.filter(function (b) { return b.atr.role === "menuitem"; })[1].posluh.click();
        pocakaj(function () { console.log(JSON.stringify([haspopup, imena, klici, obvestila])); });
        """)
        self.assertEqual(izid[0], "menu")
        self.assertEqual(izid[1], ["Dnevna", "&lt;b&gt;Spalnica&lt;/b&gt;"])        # ime je ubezano
        self.assertEqual(izid[2], [["predvajajNaNapravi", ["b", {"vrsta": "film", "id": "tt0133093", "naslov": "Film", "polozajMs": "0"}]]])
        self.assertEqual(izid[3][-1], "Predvajanje se je začelo na <b>Spalnica</b>.")

    # ---------------------------------------------------------------- #22 posiljanje in izid
    def test_odgovor_tv_samo_besedilo(self):
        izid = self._node(r"""
        var n = { id: "tv1", ime: "Dnevna TV" }, polja = { vrsta: "film", id: "tt0133093", naslov: "Film" };
        var odgovori = [{ ok: true, ime: "Ponarejeno" }, { ok: "true" }, { ok: false, razlog: "NI_V_KROGU" },
                        { ok: false, razlog: "<img src=x onerror=alert(1)>", message: "<script>x</script>" },
                        { ok: false, razlog: "cas" }, null];
        var i = 0;
        function naslednji() {
          if (i >= odgovori.length) { console.log(JSON.stringify(obvestila.filter(function (o) { return o.indexOf("Pošiljam") < 0; }))); return; }
          odzivi.predvajajNaNapravi = odgovori[i++];
          predvajajNa(n, polja);
          pocakaj(naslednji);
        }
        naslednji();
        """)
        self.assertEqual(izid, ["Predvajanje se je začelo na Dnevna TV.",
                                "Pošiljanje na Dnevna TV ni uspelo.",
                                "Dnevna TV ni začel predvajanja: Naprava ni v ožjem krogu.",
                                "Pošiljanje na Dnevna TV ni uspelo.",
                                "Dnevna TV se ni odzval. Preveri, ali je vklopljen in v Safeer Linku.",
                                "Pošiljanje na Dnevna TV ni uspelo."])

    def test_neveljavna_identiteta_se_ne_poslje(self):
        izid = self._node(r"""
        predvajajNa({ id: "tv1", ime: "TV" }, { vrsta: "film", id: "tt12" });
        predvajajNa({ id: "tv1", ime: "TV" }, { vrsta: "epizoda", id: "tt0133093", sezona: "1", epizoda: "0" });
        pocakaj(function () { console.log(JSON.stringify([klici, obvestila])); });
        """)
        self.assertEqual(izid[0], [])
        self.assertEqual(izid[1], ["Neveljaven identifikator vsebine.", "Neveljavna sezona ali epizoda."])

    def test_identiteta_vnosa(self):
        izid = self._node(r"""
        console.log(JSON.stringify([
          poljaFilma({ naslov: "A", url: "stremio:https://d|movie|tt0000001" }),
          poljaFilma({ naslov: "B", razlicice: [{ url: "https://x" }, { url: "stremio:https://d|movie|tt0000002" }] }),
          poljaFilma({ naslov: "C", url: "stremio:https://d|series|tt0000003" }),
          poljaFilma({ naslov: "D", imdb_id: "tt12" }),
          poljaEpizode({ naslov: "S", imdb_id: "tt0000004" }, 2, { stevilka: 5, naslov: "E" })]));
        """)
        self.assertEqual(izid, [{"vrsta": "film", "id": "tt0000001", "naslov": "A"},
                                {"vrsta": "film", "id": "tt0000002", "naslov": "B"}, None, None,
                                {"vrsta": "epizoda", "id": "tt0000004", "sezona": "2", "epizoda": "5", "naslov": "S · E"}])

    def test_naprave_iz_mostu_omejene(self):
        izid = self._node(r"""
        odzivi.napraveZaPredvajanje = [{ id: "a", ime: "TV" }, { id: 5, ime: "slabo" }, null, { id: "b" }];
        var poklicano = 0;
        naloziNapraveZaPredvajanje(function () { poklicano++; });
        naloziNapraveZaPredvajanje(function () { poklicano++; });      // v teku: brez drugega klica mostu
        pocakaj(function () { console.log(JSON.stringify([PNT.naprave, poklicano, klici.length])); });
        """)
        self.assertEqual(izid, [[{"id": "a", "ime": "TV"}], 2, 1])

    def test_gumb_na_strani_filma(self):
        izid = self._node(r"""
        PNT.naprave = [{ id: "a", ime: "TV" }]; PNT.cas = Date.now();
        odzivi.predvajajNaNapravi = { ok: true };
        var g = gumbPredvajajNa({ vrsta: "film", id: "tt0133093", naslov: "F" });
        var brez = gumbPredvajajNa(null);
        g.onclick({ stopPropagation: function () {} });
        pocakaj(function () { console.log(JSON.stringify([g.hidden, napis(g), brez.hidden, klici[0]])); });
        """)
        self.assertEqual(izid[:3], [False, "Predvajaj na: TV", True])
        self.assertEqual(izid[3][0], "predvajajNaNapravi")


class PravilaNode(unittest.TestCase):
    def test_pravila_predvajaj_na_tv(self):
        if not shutil.which("node"):
            raise unittest.SkipTest("node ni namescen")
        r = subprocess.run(["node", "tests/test_predvajaj_na_tv_pravila.js"], cwd=KOREN, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
        self.assertIn("VSE OK", r.stdout)

    def test_stran_nalozi_pravila_pred_os_js(self):
        html = open(os.path.join(KOREN, "assets", "os", "index.html"), encoding="utf-8").read()
        self.assertLess(html.index('<script src="predvajaj_na_tv_pravila.js"></script>'), html.index('<script src="os.js"></script>'))


if __name__ == "__main__":
    unittest.main()
