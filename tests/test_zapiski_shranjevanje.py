"""Zapiski (pregled 5. 11. 2026): A5 - menjava, izbris, skrito okno ali odhod iz Zapiskov ne izgubijo zadnjih
znakov, ki so cakali 600 ms na shranjevanje; A4 - iskanje ob vsakem znaku ne bere in razclenjuje datoteke znova."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_zapiski  # noqa: E402

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Predpomnilnik(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.pot = os.path.join(self.mapa.name, "zapiski.json")
        self.z = os_zapiski.Zapiski(self.pot)

    def test_iskanje_ob_znakih_bere_datoteko_enkrat(self):
        self.z.shrani("", "Nakup", "mleko in kruh")
        izvirni = json.load
        with mock.patch.object(os_zapiski.json, "load", side_effect=izvirni) as branje:
            for niz in ("m", "ml", "mle", "mlek", "mleko"):
                self.assertEqual([x["naslov"] for x in self.z.seznam(niz)], ["Nakup"])
        self.assertEqual(branje.call_count, 1)

    def test_po_spremembi_sveze(self):
        prvi = self.z.shrani("", "Ena", "a")
        self.assertEqual(len(self.z.seznam("")), 1)
        self.z.shrani("", "Dva", "b")                       # nase pisanje
        self.assertEqual(len(self.z.seznam("")), 2)
        self.assertTrue(self.z.izbrisi(prvi["id"]))
        self.assertEqual([x["naslov"] for x in self.z.seznam("")], ["Dva"])
        # Datoteko je spremenil drug proces (druga velikost): naslednje branje je sveze.
        with open(self.pot, "w", encoding="utf-8") as f:
            json.dump({"zapiski": [{"id": "zx", "naslov": "Zunaj", "besedilo": "drug proces"}], "zadnji": ""}, f)
        self.assertEqual([x["naslov"] for x in self.z.seznam("")], ["Zunaj"])

    def test_pisanje_ne_spremeni_predpomnjenih_podatkov(self):
        self.z.shrani("", "Ena", "a")
        pred = self.z.seznam("")
        ogled = self.z._nalozi()
        self.z.shrani(pred[0]["id"], "Spremenjeno", "b")
        self.assertEqual(ogled["zapiski"][0]["naslov"], "Ena")    # klicatelj ogleda ima nespremenjeno kopijo
        self.assertEqual(self.z.dobi(pred[0]["id"])["naslov"], "Spremenjeno")


def _funkcija(js, ime):
    return "function %s(" % ime + js.split("  function %s(" % ime, 1)[1].split("\n  }\n", 1)[0] + "\n  }\n"


class ShraniTakoj(unittest.TestCase):
    def setUp(self):
        self.js = open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8").read()

    def test_menjava_zapiska_shrani_prejsnjega(self):
        from tests.test_medijski_center_videz import _node
        koda = r"""
        var polja = { zapisekNaslov: { value: "" }, zapisekBesedilo: { value: "" }, zapisekStanje: { textContent: "" },
                      zapisekUrejevalnik: { hidden: true }, zapisekPripni: { textContent: "" } };
        function $(id) { return polja[id]; }
        function t(x) { return x; }
        var casovniki = [];
        function setTimeout(f) { casovniki.push(f); return casovniki.length; }
        function clearTimeout(i) { if (i) casovniki[i - 1] = null; }
        function narisiViriZapiska() {} function naloziZapiske() {} function narisiPogledZapiska() {}
        var Z = { aktivni: null, casovnik: 0, pogled: false };
        var shranjeno = [], baza = { A: { id: "A", naslov: "A", besedilo: "" }, B: { id: "B", naslov: "B", besedilo: "bbb" } };
        function klic(metoda, a) {
          if (metoda === "zapisekShrani") shranjeno.push(a.slice(0, 3));
          var izid = metoda === "zapisekDobi" ? baza[a[0]] : {};
          return { then: function (f) { f(izid); return this; } };
        }
        """ + "".join(_funkcija(self.js, ime) for ime in ("odpriZapisek", "shraniZapisekKmalu", "shraniZapisekZdaj",
                                                          "shraniZapisek")) + r"""
        odpriZapisek("A");
        polja.zapisekBesedilo.value = "novo besedilo"; shraniZapisekKmalu();    // casovnik 600 ms se ni potekel
        odpriZapisek("B");
        var po_menjavi = shranjeno.slice();
        casovniki.forEach(function (f) { if (f) f(); });                     // stari casovnik ne sme vec shraniti
        console.log(JSON.stringify([po_menjavi, shranjeno, Z.aktivni.id, polja.zapisekBesedilo.value]));
        """
        po_menjavi, vse, aktivni, besedilo = _node(koda)
        self.assertEqual(po_menjavi, [["A", "A", "novo besedilo"]])
        self.assertEqual(vse, [["A", "A", "novo besedilo"]])
        self.assertEqual((aktivni, besedilo), ("B", "bbb"))

    def test_zadetek_iskanja_ne_prepise_novega_zapiska(self):
        # CodeRabbit 5. 11. 2026: safeerOsPojdi("zapisek:B") je nastavil Z.aktivni na B pred shranjevanjem, zato je
        # cakajoce besedilo zapiska A slo v zapisek B.
        from tests.test_medijski_center_videz import _node
        veja = self.js.split('    if (kam.indexOf("zapisek:") === 0) {\n', 1)[1].split("\n    }\n", 1)[0]
        koda = r"""
        var polja = { zapisekNaslov: { value: "" }, zapisekBesedilo: { value: "" }, zapisekStanje: { textContent: "" },
                      zapisekUrejevalnik: { hidden: true }, zapisekPripni: { textContent: "" } };
        function $(id) { return polja[id]; }
        function t(x) { return x; }
        var casovniki = [];
        function setTimeout(f) { casovniki.push(f); return casovniki.length; }
        function clearTimeout(i) { if (i) casovniki[i - 1] = null; }
        function narisiViriZapiska() {} function naloziZapiske() {} function narisiPogledZapiska() {}
        var Z = { aktivni: null, casovnik: 0, pogled: false };
        var shranjeno = [], baza = { A: { id: "A", naslov: "A", besedilo: "" }, B: { id: "B", naslov: "B", besedilo: "bbb" } };
        var cakajoci = [];
        function klic(metoda, a) {
          if (metoda === "zapisekShrani") shranjeno.push(a.slice(0, 3));
          var izid = metoda === "zapisekDobi" ? baza[a[0]] : {};
          return { then: function (f) { if (metoda === "zapisekDobi") cakajoci.push(function () { f(izid); });
                                        else f(izid); return this; } };
        }
        function pojdi() {}
        """ + "".join(_funkcija(self.js, ime) for ime in ("odpriZapisek", "shraniZapisekKmalu", "shraniZapisekZdaj",
                                                          "shraniZapisek")) + r"""
        function pojdiZapisek(kam) {
        """ + veja + r"""
        }
        odpriZapisek("A"); cakajoci.shift()();
        polja.zapisekBesedilo.value = "besedilo A"; shraniZapisekKmalu();     // casovnik 600 ms se ni potekel
        pojdiZapisek("zapisek:B");
        while (cakajoci.length) cakajoci.shift()();
        casovniki.forEach(function (f) { if (f) f(); });
        console.log(JSON.stringify([shranjeno, Z.aktivni.id, polja.zapisekBesedilo.value]));
        """
        vse, aktivni, besedilo = _node(koda)
        self.assertEqual(vse, [["A", "A", "besedilo A"]])
        self.assertEqual((aktivni, besedilo), ("B", "bbb"))

    def test_izbris_skrito_okno_in_odhod(self):
        izbris = self.js.split('$("zapisekIzbrisi").addEventListener("click", function () {', 1)[1].split("\n    });", 1)[0]
        self.assertLess(izbris.index("clearTimeout(Z.casovnik)"), izbris.index('klic("zapisekIzbrisi"'))
        self.assertIn('window.addEventListener("pagehide", shraniZapisekZdaj);', self.js)
        self.assertIn('if (document.visibilityState === "hidden") shraniZapisekZdaj();', self.js)
        self.assertIn('if (razdelek !== "zapiski") shraniZapisekZdaj();', _funkcija(self.js, "pojdi"))


if __name__ == "__main__":
    unittest.main()
