"""Spotify v spodnjem traku Medijskega centra (lastnik, 17. 10. 2026: mini predvajalnik na dnu in »Predvajaj na …«).

Funkcije iz assets/os/os.js tecejo v node z laznim DOM in laznim klic(); en vir na traku naenkrat."""

import unittest

from tests.test_medijski_center_videz import _beri, _funkcija, _node

FUNKCIJE = ("skladbaKataloga", "zapriVrstoPlosco", "uskladiTrak", "spTrenutna", "spNaTraku", "drugVirIgra",
            "spUskladiTrak", "narisiSpTrak", "spZacni", "spUkazTraka", "spUstaviTrak", "spOpusti", "spOdDomacega",
            "spZanka", "casMedija")

OKOLJE = """
var el = {};
function $(id) { return el[id] || (el[id] = { id: id, hidden: true, disabled: false, value: 0, textContent: "", title: "",
  innerHTML: "", atr: {}, setAttribute: function (k, v) { this.atr[k] = v; }, focus: function () {},
  appendChild: function () {} }); }
var document = { body: { classList: { toggle: function () {} } }, activeElement: null,
  createElement: function () { return { remove: function () {} }; } };
var ura = 100000; Date.now = function () { return ura; };
var klici = [];
function klic(ime, arg) { klici.push([ime].concat(arg || [])); return { then: function (ok) { if (ok) ok(odgovor(ime)); return this; }, catch: function () {} }; }
var stanjeSp = null;
function odgovor(ime) { if (ime === "mediaSpStanje") return stanjeSp; return { ok: true }; }
var S = { mediaPredvajalnik: null, mediaDragging: false }, kat = { aktivni: null }, most = null;
var IZ = { z: null }, SafeerIzhod = { aktivna: function (z) { return z.aktivna; } };
var obvestila = [];
function obvesti(x) { obvestila.push(x); }
function t(k, o) { return o && o.ime ? k + ":" + o.ime : k; }
function svg(x) { return x; }
function nastaviSliko(img, url) { img.src = url; }
function zapriIzhode() { return false; }
function narisiGlasnostTraku() {}
function spNapaka(k) { obvestila.push("napaka:" + k); }
function narisiTrak() { if (!uskladiTrak()) return; if (spNaTraku()) narisiSpTrak(); }
function osveziSp() { return klic("mediaSpStanje").then(function (r) { if (r) { kat.sp = r; spUskladiTrak(r); } }); }
var ustavljenKatalog = 0;
function ustaviKatPredvajanje() { ustavljenKatalog++; kat.aktivni = null; }
var setTimeout = function () {}, intervali = [];
function setInterval(f) { intervali.push(f); return intervali.length; }
function clearInterval(i) { intervali[i - 1] = null; }
"""


class SpotifyTrak(unittest.TestCase):
    def setUp(self):
        self.js = _beri("assets", "os", "os.js")

    def _zazeni(self, koda):
        return _node(OKOLJE + "".join(_funkcija(self.js, f) for f in FUNKCIJE) + koda)

    def test_napake_predvajanja_tihe_prijava_ostane(self):
        """Lastnik 18. 10. 2026: napak predvajanja uporabnik ne vidi; prijava in Safeer DRM (ukrepa uporabnik) ostaneta,
        brskanje (odpiranje seznama) kaze vse."""
        sp = _funkcija(self.js, "spNapaka").replace("function spNapaka(", "function spNapakaPrava(")
        ukrepaj = "var SP_UKREPAJ = " + self.js.split("var SP_UKREPAJ = ", 1)[1].split(";", 1)[0] + ";\n"
        izid = self._zazeni(ukrepaj + sp + """
        t = function (k) { return "T:" + k; };
        ["stran", "ni_odziva", "neveljavno", "ne_tece", "napaka", "potekla", "ni_drm", "ni_prijave"].forEach(function (k) {
          spNapakaPrava(k, true); });
        var predvajanje = obvestila.slice(); obvestila.length = 0;
        spNapakaPrava("stran"); spNapakaPrava("ni_odziva");
        console.log(JSON.stringify([predvajanje, obvestila]));""")
        self.assertEqual(izid, [["T:spNapaka_potekla", "T:spNapaka_ni_drm", "T:spNapaka_ni_prijave"],
                                ["T:spNapaka_stran", "T:spNapaka_ni_odziva"]])
        for klic in ('spNapaka(item.sp_napaka, true)', 'if (x && x.napaka) spNapaka(x.napaka, true);'):
            self.assertIn(klic, self.js)

    def test_trak_pokaze_skladbo_in_predvajaj_na(self):
        izid = self._zazeni("""
        kat.spTrak = true;
        kat.sp = { tece: true, predvajanje: { naslov: "Pesem", izvajalec: "Izvajalec", slika: "https://i.scdn.co/a.jpg",
                   igra: true, polozaj: 30, trajanje: 120 } };
        IZ.z = { aktivna: { vrsta: "zvocnik", ime: "JBL BAR 300" } };
        narisiTrak();
        console.log(JSON.stringify([$("mediaPlayerBar").hidden, $("mediaBarNaslov").textContent, $("mediaBarVrsta").textContent,
          $("mediaBarPolozaj").hidden, $("mediaBarCas").textContent, $("mediaBarNapredek").value, $("mediaKatPremor").innerHTML,
          $("mediaPremesaj").hidden, $("mediaBarVrstaGumb").hidden, $("mediaPrejsnja").disabled]));""")
        self.assertEqual(izid, [False, "Pesem", "Izvajalec · Spotify · predvajaNa:JBL BAR 300", False, "0:30", 250, "premor",
                                True, True, False])

    def test_zacetek_ustavi_drug_vir_in_kaze_kartico(self):
        izid = self._zazeni("""
        S.mediaPredvajalnik = { naslov: "Radio 1", stanje: "predvaja" };
        kat.sp = { tece: true, predvajanje: { naslov: "Stara", igra: false } };
        stanjeSp = { tece: true, predvajanje: { naslov: "Stara", igra: true } };      // Spotify se ni zamenjal skladbe
        spZacni({ naslov: "Nova", izvajalec: "B", slika: "" });
        var r = [klici.some(function (k) { return k[0] === "predvajalnikUkaz" && k[1] === "ustavi"; }),
                 $("mediaBarNaslov").textContent, kat.spTrak];
        S.mediaPredvajalnik.stanje = "ustavljeno";
        ura += 1500; stanjeSp = { tece: true, predvajanje: { naslov: "Nova", izvajalec: "B", igra: true } }; osveziSp();
        r.push($("mediaBarNaslov").textContent, kat.spZacetna);
        console.log(JSON.stringify(r));""")
        self.assertEqual(izid, [True, "Nova", True, "Nova", None])

    def test_youtube_iz_kataloga_ustavi_trak(self):
        izid = self._zazeni("""
        kat.aktivni = { zvok: true, okno_youtube: true, naslov: "YT" }; kat.igra = true;
        spZacni({ naslov: "Pesem" });
        console.log(JSON.stringify([ustavljenKatalog, kat.aktivni]));""")
        self.assertEqual(izid, [1, None])

    def test_domaci_predvajalnik_ustavi_spotify(self):
        izid = self._zazeni("""
        kat.spTrak = true; kat.spOd = ura; kat.sp = { tece: true, predvajanje: { naslov: "Pesem", igra: true } };
        spOdDomacega({ naslov: "Radio 1", stanje: "predvaja" });      // staro stanje takoj po zagonu Spotifyja
        var r = [kat.spTrak];
        ura += 5000;
        spOdDomacega({ naslov: "Radio 1", stanje: "predvaja" });      // isto stanje ni nov zacetek
        r.push(kat.spTrak);
        spOdDomacega({ naslov: "Radio 1", stanje: "premor" });
        spOdDomacega({ naslov: "Radio 1", stanje: "predvaja" });      // uporabnik nadaljuje radio
        r.push(kat.spTrak, klici.filter(function (k) { return k[0] === "mediaSpUkaz" && k[1] === "ustavi"; }).length);
        console.log(JSON.stringify(r));""")
        self.assertEqual(izid, [True, True, False, 1])

    def test_spotify_prevzame_trak_samo_brez_drugega_vira(self):
        izid = self._zazeni("""
        var igra = { tece: true, predvajanje: { naslov: "Pesem", igra: true } }, r = [];
        S.mediaPredvajalnik = { naslov: "Datoteka", stanje: "predvaja" };
        spUskladiTrak(igra); r.push(!!kat.spTrak);
        S.mediaPredvajalnik.stanje = "ustavljeno";
        spUskladiTrak(igra); r.push(kat.spTrak);
        spUskladiTrak({ tece: false }); r.push(kat.spTrak, $("mediaPlayerBar").hidden);
        console.log(JSON.stringify(r));""")
        self.assertEqual(izid, [False, True, False, True])

    def test_zanka_tece_tudi_ko_razdelek_ni_viden(self):
        izid = self._zazeni("""
        kat.spTrak = true; kat.sp = { tece: true, predvajanje: { naslov: "Pesem", igra: true } };
        stanjeSp = kat.sp;
        spZanka(); intervali[0](); var r = [!!kat.spZanka, klici.length];
        stanjeSp = { tece: false }; intervali[0](); kat.sp = stanjeSp; intervali[0]();
        r.push(!!kat.spZanka);
        console.log(JSON.stringify(r));""")
        self.assertEqual(izid, [True, 1, False])

    def test_premor_takoj_in_ne_tece(self):
        izid = self._zazeni("""
        kat.spTrak = true; kat.sp = { tece: true, predvajanje: { naslov: "Pesem", igra: true } };
        stanjeSp = kat.sp;
        spUkazTraka("premor"); var r = [kat.sp.predvajanje.igra, $("mediaKatPremor").innerHTML];
        odgovor = function () { return { napaka: "ne_tece" }; };
        spUkazTraka("naprej"); r.push(kat.spTrak, obvestila.pop());
        console.log(JSON.stringify(r));""")
        self.assertEqual(izid, [False, "predvajaj", False, "napaka:ne_tece"])

    def test_gumbi_traka_in_prijava(self):
        self.assertIn('if (spNaTraku()) { spUkazTraka("cas", Number(this.value) / 1000); return; }', self.js)
        self.assertIn('if (spNaTraku()) { spPokaziRazdelek(false); return; }', self.js)
        # Po prijavi v Spletu (zavihek se zapre) Medijski center pokaze razdelek Spotify s seznami.
        self.assertIn("kat.spCas = 0; kat.spSeznami = null; spPokaziRazdelek(true); naloziSpotify(true);", self.js)
        telo = _funkcija(self.js, "spPokaziRazdelek")
        self.assertIn('pojdi("media");', telo)
        self.assertIn('izberiMedijskoKategorijo("glasba");', telo)
        besedila = _beri("assets", "os", "besedila.js")
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            vrstica = [v for v in besedila.splitlines() if v.startswith("Object.assign(BESEDILA_OS.%s, {\"spDelno\"" % jezik)]
            self.assertEqual(len(vrstica), 1, jezik)
            self.assertIn('"spPrijavaKoncana"', vrstica[0])


if __name__ == "__main__":
    unittest.main()
