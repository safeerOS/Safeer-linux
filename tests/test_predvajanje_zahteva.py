"""M1/M3 (pregled 5. 11. 2026): velja samo zadnja zahteva predvajanja. Pocasna razresitev (debrid) po novem kliku ali
po preklicu (mediaPreklici) ne odpre predvajalnika; dva hitra klika ne zazeneta dveh predvajanj. Brez omrezja."""
import contextlib
import io
import os
import sys
import tempfile
import threading
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_katalog  # noqa: E402

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ZadnjaZahteva(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.igrano: list = []
        self.k = os_katalog.Katalog(self.mapa.name, lambda *a: None, lambda f: f(),
                                    lambda uri, *a, **kw: self.igrano.append(uri) or True, lambda u: True,
                                    lambda *a: True, lambda u: True)
        self.pocasi = threading.Event()        # prvi vnos se razresuje, dokler preizkus tega ne spusti
        self.zacel = threading.Event()

        def resolve(ident, **_kw):
            if ident == "pocasen":
                self.zacel.set()
                self.pocasi.wait(5)
            return {"id": ident, "vrsta": "film", "naslov": ident, "url": "https://vir.test/%s.mp4" % ident}
        self.k._mc = types.SimpleNamespace(resolve=resolve, uporabi_izbiro=lambda item: item, _dynamic_items={})

    def _v_ozadju(self, metoda, a):
        izid: dict = {}

        def delo():
            with contextlib.redirect_stdout(io.StringIO()):
                izid["v"] = self.k.izvedi(metoda, a)
        nit = threading.Thread(target=delo, daemon=True)
        nit.start()
        self.assertTrue(self.zacel.wait(5))
        return nit, izid

    def test_dva_klika_igra_samo_drugi(self):
        nit, prvi = self._v_ozadju("mediaPredvajaj", ["pocasen"])
        with contextlib.redirect_stdout(io.StringIO()):
            drugi = self.k.izvedi("mediaPredvajaj", ["hiter"])
        self.pocasi.set()
        nit.join(5)
        self.assertFalse(nit.is_alive())
        self.assertEqual(self.igrano, ["https://vir.test/hiter.mp4"])
        self.assertTrue(drugi and drugi.get("native"))
        self.assertIsNone(prvi["v"])

    def test_preklic_ne_igra_nic(self):
        nit, prvi = self._v_ozadju("mediaPredvajaj", ["pocasen"])
        self.assertTrue(self.k.izvedi("mediaPreklici", []))
        self.pocasi.set()
        nit.join(5)
        self.assertEqual(self.igrano, [])
        self.assertIsNone(prvi["v"])

    def test_brez_tekmeca_igra(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(self.k.izvedi("mediaPredvajaj", ["hiter"]).get("native"))
        self.assertEqual(self.igrano, ["https://vir.test/hiter.mp4"])

    def test_stran_preklice_ob_opustitvi_in_ustavitvi(self):
        js = open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8").read()
        for ime in ("function opustiKatVrsto() {", "function ustaviKatPredvajanje() {"):
            telo = js.split(ime, 1)[1].split("\n  }", 1)[0]
            self.assertIn("prekliciKatZahtevo();", telo, ime)
        self.assertIn('klic("mediaPreklici", [])', js)



class EpizodaZadnjiKlik(unittest.TestCase):
    """M2: mediaEpizoda pred odpriKatalogVnos - pocasnejsi odgovor prejsnjega klika ne zacne napacne epizode."""

    def test_pocasen_odgovor_prve_epizode_ne_zacne(self):
        from tests.test_medijski_center_videz import _funkcija, _node
        js = open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8").read()
        koda = r"""
        function Vozel() { this.otroci = []; this.atr = {}; this.classList = { add: function () {}, toggle: function () {} }; }
        Vozel.prototype.appendChild = function (o) { this.otroci.push(o); return o; };
        Vozel.prototype.setAttribute = function (k, v) { this.atr[k] = v; };
        Vozel.prototype.getAttribute = function (k) { return this.atr[k]; };
        Vozel.prototype.querySelectorAll = function () { return []; };
        var vozli = { mediaSezone: new Vozel(), mediaEpizode: new Vozel(), mediaEpizodeNaslov: new Vozel() };
        function $(id) { return vozli[id]; }
        var predvajaj = [];
        function el(tag, razred) { var v = new Vozel(); if (tag === "button" && razred === "gumb glavni") predvajaj.push(v); return v; }
        var document = { createElement: function () { return new Vozel(); } };
        function ubezi(x) { return x; } function t(x) { return x; } function svg() { return ""; }
        function gumbOgledanoEpizode() { return new Vozel(); }
        function zapriKatalogPodrobnosti() {} function narisiVrsto() {} function narisiRazlicice() {}
        var kat = { zahtevaVnosa: 0, vrsta: [] };
        var odprto = [];
        function odpriKatalogVnos(id) { kat.zahtevaVnosa++; odprto.push(id); }
        var cakajo = [];
        function klic(metoda, a) {
          if (metoda === "mediaSezona") return { then: function (f) { f({ epizode: [{ stevilka: 1, naslov: "A" }, { stevilka: 2, naslov: "B" }] }); } };
          return { then: function (f) { cakajo.push(f); } };
        }
        """ + _funkcija(js, "naloziKatalogSezono") + r"""
        naloziKatalogSezono({ tmdb_id: 5, id: "s", naslov: "S" }, 1, null);
        predvajaj[0].onclick(); predvajaj[1].onclick();
        cakajo[1]({ id: "ep2" });        // druga epizoda odgovori prva
        cakajo[0]({ id: "ep1" });        // prva prepozno: ne sme zaceti
        console.log(JSON.stringify([predvajaj.length, odprto]));
        """
        self.assertEqual(_node(koda), [2, ["ep2"]])


if __name__ == "__main__":
    unittest.main()
