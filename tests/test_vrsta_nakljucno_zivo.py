"""Vrsta strani v Medijskem centru (lastnik, 18. 10. 2026):
- »Nakljucno« ima en premesan vrstni red - vsaka skladba enkrat, plosca vrste kaze prav ta red (prej je bila vsaka
  naslednja izzrebana posebej, tudi dvakrat ista, vrstnega reda pa ni bilo videti);
- prenos v zivo na seznamu je oznacen in ga samodejni prehod preskoci (sicer bi vrsta na njem obstala);
- seznam, odigran do konca, Safeer nadaljuje s seznamom, ki je po zvrsti najblizji - razen ce je uporabnik med
  poslusanjem kaj spremenil;
- skladba s seznama se zapomni za »Nazadnje predvajano« na Domov, junak ima »Nadaljuj«.
Funkcije os.js tecejo v node z nadomestki mostu (klic) in strani."""
import json
import os
import shutil
import subprocess
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8").read()
FUNKCIJE = ("novaVrsta", "premesaj", "premesajVrsto", "zacniOdZacetka", "redVrste", "jeVZivo", "vrstaPostaj", "naslednjiVVrsti",
            "zacetekKroga", "predvajajIzVrste", "zapomniMestoVrste", "nakljucnoVklopljeno", "nadaljujPodobni", "zacniSeznam",
            "oznaciZivo", "zapomniZadnjiSeznam", "izvorSeznama", "nastaviVrsto")


def _fn(ime):
    return "function %s(" % ime + JS.split("  function %s(" % ime, 1)[1].split("\n  }\n", 1)[0] + "\n  }\n"


OKOLJE = """
var VRSTA_ZGODOVINA_NAJVEC = 200;
var nast = {}, klici = [], odprto = [], odgovori = {}, skrit = 0, narisano = 0;
var kat = { vrsta: [], vrstaMesto: 0, vrstaZgodovina: [], vrstaNapake: 0, vrstaRed: null, vrstaIzvor: null,
            vrstaSpremenjena: false, vrstaSamodejno: false, vrstaIzSafeerja: false, vrstaZeton: 0, zivi: {}, aktivniId: "" };
var POL = { zadnjiSeznam: null }, S = { mediaFilter: "glasba", mediaQueueKey: "" };
var document = { querySelector: function () { return null; } };
function vrstaNastavitev(k, p) { return k in nast ? nast[k] : p; }
function narisiVrsto() { narisano++; }
function narisiMediaDomov() {}
function skrijKatTrak() { skrit++; }
function prekliciNaslednjo() {}
function el() { return {}; } function ubezi(x) { return x; } function t(k) { return k; }
function odpriKatalogVnos(id) { odprto.push(id); kat.aktivniId = id; }
function klic(m, a) {
  klici.push([m, a]);
  var k = m + ":" + (a && a[0]);
  return { then: function (ok) { var r = ok(k in odgovori ? JSON.parse(JSON.stringify(odgovori[k])) : null);
           return { then: function (f) { f(r); }, catch: function () {} }; }, catch: function () {} };
}
function skladbe(n, predpona, vrsta) {
  var s = []; for (var i = 0; i < n; i++) s.push({ id: predpona + i, naslov: "Pesem " + i, izvajalec: "A", vrsta: vrsta || "glasba" });
  return s;
}
"""


def _node(koda):
    if not shutil.which("node"):
        raise unittest.SkipTest("node ni namescen")
    vse = OKOLJE + "".join(_fn(f) for f in FUNKCIJE) + koda
    return json.loads(subprocess.run(["node", "-e", vse], capture_output=True, text=True, check=True).stdout)


class Nakljucno(unittest.TestCase):
    def test_en_premesan_red_vsaka_skladba_enkrat_in_viden(self):
        r = _node("""
        nast.premesaj = "1"; nast.ponoviVse = "0";
        novaVrsta(skladbe(12, "s"), 3, null);
        var red = redVrste().slice(), igrano = [kat.vrstaMesto];
        while (predvajajIzVrste(1, true)) igrano.push(kat.vrstaMesto);
        console.log(JSON.stringify({ red: red, igrano: igrano }));""")
        self.assertEqual(r["red"][0], 3)                                # skladba, ki igra, je prva
        self.assertEqual(sorted(r["red"]), list(range(12)))             # vsaka enkrat
        self.assertEqual(r["igrano"], r["red"])                          # igra natanko prikazani red

    def test_predvajaj_vse_z_nakljucnim_zacne_s_prvo_premesanega_reda(self):
        r = _node("""
        nast.premesaj = "1"; var zacetki = {};
        for (var i = 0; i < 40; i++) { novaVrsta(skladbe(6, "s"), 0, null); zacniOdZacetka(); zacetki[kat.vrstaMesto] = 1;
          if (redVrste()[0] !== kat.vrstaMesto) throw new Error("red"); }
        console.log(JSON.stringify(Object.keys(zacetki).length));""")
        self.assertGreater(r, 1)

    def test_izklop_vrne_naravni_red_od_trenutne(self):
        r = _node("""
        nast.premesaj = "1"; novaVrsta(skladbe(5, "s"), 2, null);
        nast.premesaj = "0"; premesajVrsto();
        predvajajIzVrste(1, false);
        console.log(JSON.stringify([kat.vrstaRed, kat.vrstaMesto]));""")
        self.assertEqual(r, [None, 3])

    def test_plosca_kaze_premesan_red_z_oznako(self):
        telo = _fn("narisiVrstoTraku")
        self.assertIn("var red = imaVrsto ? redVrste() : [0]", telo)
        self.assertIn('$("mediaVrstaNacin").hidden = !nakljucno;', telo)
        self.assertIn("pomakniNaTrenutno();", telo)
        self.assertIn('if (zdaj) b.setAttribute("aria-current", "true");', telo)
        html = open(os.path.join(KOREN, "assets", "os", "index.html"), encoding="utf-8").read()
        self.assertIn('<span class="media-vrsta-nacin" id="mediaVrstaNacin" hidden><svg data-ikona="premesaj"></svg><span data-t="vrstaNakljucno"></span></span>', html)


class VZivo(unittest.TestCase):
    def test_samodejni_prehod_preskoci_prenos_v_zivo_uporabnik_ne(self):
        r = _node("""
        var s = skladbe(4, "s"); s[1].v_zivo = true; kat.zivi = { s2: 1 };
        novaVrsta(s, 0, null);
        var izid = [naslednjiVVrsti(1, true), naslednjiVVrsti(1, false)];
        console.log(JSON.stringify(izid));""")
        self.assertEqual(r, [3, 1])

    def test_vrsta_postaj_gre_na_naslednjo_postajo(self):
        r = _node("""
        novaVrsta(skladbe(3, "r", "radio"), 0, null);
        console.log(JSON.stringify(naslednjiVVrsti(1, true)));""")
        self.assertEqual(r, 1)

    def test_skladba_ki_se_izkaze_za_prenos_se_oznaci_in_preskoci(self):
        r = _node("""
        novaVrsta(skladbe(3, "s"), 0, null);
        predvajajIzVrste(1, true);                 // samodejno na s1
        oznaciZivo();                              // s1 je tok brez konca
        console.log(JSON.stringify([kat.zivi, odprto, klici.map(function (k) { return k[1][0]; })]));""")
        self.assertEqual(r[0], {"s1": 1})
        self.assertEqual(r[1], ["s1", "s2"])                             # takoj naprej na s2
        self.assertIn("zivo", r[2])

    def test_seznam_kaze_znacko_v_zivo(self):
        self.assertIn('(izSeznama && jeVZivo(x)) ? t("katVZivo") : ""', _fn("narisiKatalog"))

    def test_izbrana_od_uporabnika_igra_naprej(self):
        r = _node("""
        novaVrsta(skladbe(3, "s"), 0, null);
        predvajajIzVrste(1, false); oznaciZivo();
        console.log(JSON.stringify(odprto));""")
        self.assertEqual(r, ["s1"])


class KonecSeznama(unittest.TestCase):
    def test_konec_seznama_nadaljuje_s_podobnim(self):
        r = _node("""
        odgovori["mediaNazadnje:naslednji"] = { izvor: { tip: "seznam", ref: "Rock 2" }, vnosi: skladbe(2, "r2-") };
        novaVrsta(skladbe(2, "r1-"), 1, { tip: "seznam", ref: "Rock 1" });
        predvajajIzVrste(1, true);
        console.log(JSON.stringify([odprto, kat.vrstaIzvor.ref, kat.vrstaIzSafeerja]));""")
        self.assertEqual(r, [["r2-0"], "Rock 2", True])

    def test_podoben_seznam_se_ne_zacne_s_prenosom_v_zivo(self):
        r = _node("""
        var nov = skladbe(3, "r2-"); nov[0].v_zivo = true;
        odgovori["mediaNazadnje:naslednji"] = { izvor: { tip: "seznam", ref: "Rock 2" }, vnosi: nov };
        novaVrsta(skladbe(2, "r1-"), 1, { tip: "seznam", ref: "Rock 1" });
        predvajajIzVrste(1, true);
        console.log(JSON.stringify(odprto));""")
        self.assertEqual(r, ["r2-1"])

    def test_ce_je_uporabnik_kaj_spremenil_znova_od_zacetka(self):
        r = _node("""
        novaVrsta(skladbe(2, "r1-"), 1, { tip: "seznam", ref: "Rock 1" });
        kat.vrstaSpremenjena = true;
        predvajajIzVrste(1, true);
        console.log(JSON.stringify([odprto, klici.length]));""")
        self.assertEqual(r, [["r1-0"], 0])

    def test_brez_podobnega_seznama_znova_od_zacetka(self):
        r = _node("""
        novaVrsta(skladbe(2, "r1-"), 1, { tip: "seznam", ref: "Rock 1" });
        predvajajIzVrste(1, true);
        console.log(JSON.stringify([odprto, kat.vrstaIzvor.ref]));""")
        self.assertEqual(r, [["r1-0"], "Rock 1"])

    def test_prazna_vrsta_s_starim_izvorom_ne_nadaljuje(self):
        # Posamezna vsebina (polica, odkrivanje) izprazni vrsto; konec te vsebine ne sme zaceti podobnega seznama.
        r = _node("""
        novaVrsta(skladbe(2, "r1-"), 1, { tip: "seznam", ref: "Rock 1" });
        kat.vrsta = [];
        console.log(JSON.stringify([predvajajIzVrste(1, true), klici.length]));""")
        self.assertEqual(r, [False, 0])

    def test_vrsta_brez_seznama_kot_doslej(self):
        r = _node("""
        novaVrsta(skladbe(2, "k"), 1, null);
        predvajajIzVrste(1, true);
        console.log(JSON.stringify([odprto, klici.length]));""")
        self.assertEqual(r, [["k0"], 0])


class NazadnjePredvajano(unittest.TestCase):
    def test_skladba_s_seznama_se_zapomni(self):
        r = _node("""
        var s = skladbe(3, "s"); s[0].slika = "https://x/1.jpg";
        novaVrsta(s, 2, { tip: "seznam", ref: "Moj", ime: "Moj" });
        zapomniZadnjiSeznam();
        console.log(JSON.stringify([klici[0], POL.zadnjiSeznam.mesto]));""")
        metoda, arg = r[0]
        self.assertEqual((metoda, arg[0], arg[1]["ref"], arg[1]["slike"], arg[2], arg[3]["id"], arg[4]),
                         ("mediaNazadnje", "zapomni", "Moj", ["https://x/1.jpg"], 2, "s2", 3))
        self.assertEqual(r[1], 2)
        # Ob uspesnem zacetku skladbe s seznama (odpriKatalogVnos):
        self.assertIn("if (kat.vrstaIzvor && id && kat.vrsta[kat.vrstaMesto] === id) zapomniZadnjiSeznam();", JS)

    def test_izvor_seznama(self):
        r = _node("""console.log(JSON.stringify([izvorSeznama({ ime: "A", vnosi: [] }), izvorSeznama({ ime: "B", yt: "PL1", yt_racun: 1 }),
                   izvorSeznama({ ime: "C", sp: "spotify:x" }), izvorSeznama({ ime: "T", twitch: true })]));""")
        self.assertEqual(r, [{"tip": "seznam", "ref": "A", "ime": "A"}, {"tip": "yt", "ref": "PL1", "racun": 1, "ime": "B"}, None, None])

    def test_nadaljuj_v_istem_premesanem_redu(self):
        r = _node("""
        nast.premesaj = "1";
        zacniSeznam({ izvor: { tip: "seznam", ref: "A" }, vnosi: skladbe(4, "s"), red: [2, 0, 3, 1] }, 0, false);
        predvajajIzVrste(1, true);
        console.log(JSON.stringify([kat.vrstaRed, odprto]));""")
        self.assertEqual(r, [[2, 0, 3, 1], ["s0", "s3"]])

    def test_junak_domov_je_zadnji_seznam(self):
        junak = _fn("izbiraJunaka")
        self.assertIn('if (POL.zadnjiSeznam && POL.zadnjiSeznam.izvor) return { seznam: POL.zadnjiSeznam, polica: "predvajano" };', junak)
        self.assertIn('return prvi("nadaljuj") || prvi("glasba") || junakOdkrivanja();', junak)
        self.assertNotIn('prvi("nazadnje")', junak)                       # »Nazadnje dodano« ni vec glavno
        risanje = _fn("narisiJunakaSeznama")
        self.assertIn('t("policaNazadnjePredvajano")', risanje)
        self.assertIn('gumb.addEventListener("click", nadaljujZadnjiSeznam);', risanje)


if __name__ == "__main__":
    unittest.main()
