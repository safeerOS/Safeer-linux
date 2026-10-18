"""Nazadnje predvajano (lastnik, 18. 10. 2026): zadnji seznam na Domov z »Nadaljuj«, samodejno nadaljevanje s seznamom,
ki je po zvrsti najblizji, in skladbe s seznama, ki so prenos v zivo (core/nazadnje_predvajano.py, core/os_katalog.py)."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from core import nazadnje_predvajano as NP
from core import os_katalog as K
from core import os_knjiznica as KN


def _s(izvajalec, naslov, zanr=""):
    return {"izvajalec": izvajalec, "naslov": naslov, "zanr": zanr}


class Pravila(unittest.TestCase):
    def test_zvrsti_in_izvajalec(self):
        self.assertEqual(NP.zvrsti("Rock, Pop / Indie;rock"), ["rock", "pop", "indie"])
        self.assertEqual(NP.zvrsti(["Jazz", "Blues"]), ["jazz", "blues"])
        self.assertEqual(NP.glavni_izvajalec("Daft Punk feat. Pharrell"), "daft punk")
        self.assertEqual(NP.kljuc_skladbe(_s("A & B", "  Pesem ")), "a|pesem")

    def test_oznake_iz_skladbe_ali_izvajalca(self):
        izv = NP.zemljevid_izvajalcev([_s("A", "1", "Rock"), _s("A", "2", "Rock, Blues"), _s("B", "3", "")])
        self.assertEqual(NP.oznake(_s("X", "y", "Pop"), izv), {"pop": 1.0})
        o = NP.oznake(_s("A", "brez oznake"), izv)                     # zvrst izvajalca iz uporabnikove glasbe
        self.assertAlmostEqual(o["rock"], 1.5 / 2.0)
        self.assertAlmostEqual(o["blues"], 0.5 / 2.0)
        self.assertEqual(NP.oznake(_s("B", "x"), izv), {})

    def test_najblizji_po_zvrsti_brez_slisanih(self):
        izv = NP.zemljevid_izvajalcev([_s("A", "a", "Rock"), _s("B", "b", "Rock"), _s("C", "c", "Rock"),
                                       _s("D", "d", "Pop"), _s("E", "e", "Pop")])
        izteklo = {"kljuc": "seznam:R1", "skladbe": [_s("A", "1"), _s("B", "2")]}
        kandidati = [
            {"kljuc": "seznam:Pop", "skladbe": [_s("D", "1"), _s("E", "2")]},
            {"kljuc": "seznam:R1", "skladbe": [_s("A", "1"), _s("B", "2")]},
            {"kljuc": "seznam:R2", "skladbe": [_s("A", "1"), _s("C", "3")]},
        ]
        izbran = NP.izberi(izteklo, kandidati, izv)
        self.assertEqual(izbran["kljuc"], "seznam:R2")
        self.assertEqual(izbran["skladbe"], [_s("C", "3")])          # »A - 1« je bila ravno slisana
        self.assertAlmostEqual(izbran["podobnost"], 1.0)
        # Veriga: R2 je bil v tej verigi ze predvajan -> naslednji najblizji (Pop).
        self.assertEqual(NP.izberi(izteklo, kandidati, izv, izkljuci=["seznam:R2"])["kljuc"], "seznam:Pop")
        # Samodejni seznam »zanr« prinese svojo zvrst tudi skladbam brez oznake.
        kandidati.append({"kljuc": "samodejni:zanr:x", "zanr": "Rock", "skladbe": [_s("Q", "9")]})
        self.assertEqual(NP.izberi(izteklo, kandidati, izv, izkljuci=["seznam:R2"])["kljuc"], "samodejni:zanr:x")

    def test_brez_zvrsti_odlocijo_izvajalci_nato_zgodovina(self):
        izteklo = {"kljuc": "a", "skladbe": [_s("A", "1"), _s("B", "2")]}
        kandidati = [{"kljuc": "x", "skladbe": [_s("Z", "1")]}, {"kljuc": "y", "skladbe": [_s("B", "5")]},
                     {"kljuc": "w", "skladbe": [_s("W", "1")]}]
        self.assertEqual(NP.izberi(izteklo, kandidati, {})["kljuc"], "y")
        self.assertEqual(NP.izberi(izteklo, kandidati[::2], {}, zgodovina=["a", "w", "x"])["kljuc"], "w")
        self.assertEqual(NP.izberi(izteklo, kandidati[::2], {})["kljuc"], "x")      # stalen vrstni red
        self.assertIsNone(NP.izberi(izteklo, [{"kljuc": "z", "skladbe": [_s("A", "1")]}], {}))

    def test_izvor(self):
        self.assertIsNone(NP.cisti_izvor({"tip": "sp", "ref": "x"}))
        self.assertIsNone(NP.cisti_izvor({"tip": "seznam", "ref": ""}))
        i = NP.cisti_izvor({"tip": "yt", "ref": "PL1", "racun": 2, "ime": "Moj", "slike": ["javascript:x", "https://s/1.jpg",
                                                                                            "https://s/1.jpg"]})
        self.assertEqual(i, {"tip": "yt", "ref": "PL1", "ime": "Moj", "racun": 2, "slike": ["https://s/1.jpg"]})
        self.assertEqual(NP.kljuc_izvora(i), "yt:2:PL1")


class Shramba(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.n = NP.NazadnjePredvajano(self.mapa.name)

    def test_zapomni_verigo_in_zgodovino(self):
        a = {"tip": "seznam", "ref": "A", "ime": "A"}
        b = {"tip": "samodejni", "ref": "zanr:1", "vrsta": "zanr", "ime": "Rock"}
        self.assertTrue(self.n.zapomni(a, 3, {"id": "s3", "naslov": "T"}, 10, [3, 0, 1, 2, 4, 5, 6, 7, 8, 9]))
        z = self.n.zadnji()
        self.assertEqual((z["kljuc"], z["mesto"], z["skupaj"], z["skladba"]["id"], z["red"][0], z["veriga"]),
                         ("seznam:A", 3, 10, "s3", 3, []))
        self.n.zapomni(b, 0, {"id": "x"}, 5, None, samodejno=True)        # izbral Safeer: veriga
        self.assertEqual(self.n.zadnji()["veriga"], ["seznam:A"])
        self.n.zapomni(b, 1, {"id": "y"}, 5)                              # ista veriga, naslednja skladba
        self.assertEqual(self.n.zadnji()["veriga"], ["seznam:A"])
        self.n.zapomni(a, 0, {"id": "s0"}, 10)                            # izbral uporabnik: veriga od zacetka
        self.assertEqual(self.n.zadnji()["veriga"], [])
        self.assertEqual(self.n.zgodovina(), ["seznam:A", "samodejni:zanr:1"])
        self.assertFalse(self.n.zapomni({"tip": "sp", "ref": "x"}, 0, {}, 1))
        # Trajno: nova shramba na isti mapi.
        self.assertEqual(NP.NazadnjePredvajano(self.mapa.name).zadnji()["skladba"]["id"], "s0")

    def test_pozicija_samo_za_skladbo_ki_igra_in_zapis_najvec_na_15_s(self):
        self.n.zapomni({"tip": "seznam", "ref": "A"}, 0, {"id": "s0"}, 2)
        self.assertFalse(self.n.pozicija("drug", 50))
        self.assertTrue(self.n.pozicija("s0", 50))
        self.assertEqual(self.n.zadnji()["pozicija"], 50)
        self.assertEqual(json.loads(Path(self.n.pot).read_text())["zadnji"]["pozicija"], 0)   # zapis cez 15 s
        self.n._zapisano -= NP.PISI_NAJVEC_NA_S
        self.n.pozicija("s0", 65)
        self.assertEqual(json.loads(Path(self.n.pot).read_text())["zadnji"]["pozicija"], 65)

    def test_pozabi_zivi_in_pokvarjena_datoteka(self):
        self.n.zapomni({"tip": "seznam", "ref": "A"}, 0, {"id": "s0"}, 2)
        self.n.oznaci_zivo("s1")
        self.n.pozabi()
        self.assertIsNone(self.n.zadnji())
        self.assertEqual(self.n.zgodovina(), [])
        self.assertEqual(NP.NazadnjePredvajano(self.mapa.name).zivi(), {"s1"})
        Path(self.n.pot).write_text("{pokvarjeno", encoding="utf-8")
        self.assertIsNone(NP.NazadnjePredvajano(self.mapa.name).zadnji())


class MostKataloga(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.predvajano = []
        self.lokalna = KN.Knjiznica(Path(self.mapa.name) / "m.sqlite3")
        self.k = K.Katalog(str(Path(self.mapa.name) / "media"), dogodek=lambda v, p: None, v_glavni=lambda delo: delo(),
                           predvajaj=lambda *a: self.predvajano.append(a) or True, vdelano=lambda u: True,
                           youtube=lambda u, n: True, youtube_ukaz=lambda u: True, lokalna=self.lokalna)
        mc = self.k.mc

        def skladbe(izvajalci, od):
            return [{"naslov": "Pesem %d" % (od + i), "izvajalec": a, "url": "https://glasba.test/%d.mp3" % (od + i),
                     "slika": "https://glasba.test/%d.jpg" % (od + i)} for i, a in enumerate(izvajalci)]
        mc.shrani_seznam("Rock 1", skladbe(["Alfa", "Beta", "Alfa"], 0))
        mc.shrani_seznam("Pop", skladbe(["Delta", "Eta"], 10))
        mc.shrani_seznam("Rock 2", skladbe(["Gama", "Beta"], 20) + skladbe(["Alfa"], 0))
        # Zvrsti izvajalcev iz uporabnikove knjiznice (oznake datotek).
        mapa = Path(self.mapa.name) / "Glasba"
        mapa.mkdir()
        poti = []
        for a, z in (("Alfa", "Rock"), ("Beta", "Rock"), ("Gama", "Rock"), ("Delta", "Pop"), ("Eta", "Pop")):
            pot = mapa / ("%s - Posnetek.mp3" % a)
            pot.write_bytes(b"x")
            poti.append(str(pot.resolve()))
        self.lokalna.dodaj(poti)
        zvrst = {"Alfa": "Rock", "Beta": "Rock", "Gama": "Rock", "Delta": "Pop", "Eta": "Pop"}
        self.k._oznake_datoteke = lambda pot: (Path(pot).name.split(" - ")[0], zvrst[Path(pot).name.split(" - ")[0]])
        self.izvor = {"tip": "seznam", "ref": "Rock 1", "ime": "Rock 1", "slike": ["https://glasba.test/0.jpg"]}

    def _vnosi(self, ime):
        return self.k.izvedi("mediaSeznam", [ime])["vnosi"]

    def test_domov_kaze_zadnji_seznam_nadaljuj_tam_kjer_je_ostal(self):
        self.assertIsNone(self.k.izvedi("mediaPolice", ["domov", ""])["nazadnje_seznam"])
        vnosi = self._vnosi("Rock 1")
        self.assertTrue(self.k.izvedi("mediaNazadnje", ["zapomni", self.izvor, 1, vnosi[1], 3, None, False]))
        # Domaci predvajalnik javlja mesto v skladbi (shrani_napredek na 5 s).
        self.k.izvedi("mediaPredvajaj", [vnosi[1]["id"]])
        uri = self.predvajano[-1][0]
        self.k.shrani_napredek(uri, 95.0, 240.0)
        domov = self.k.izvedi("mediaPolice", ["domov", ""])["nazadnje_seznam"]
        self.assertEqual((domov["izvor"]["ime"], domov["mesto"], domov["poz"], domov["skupaj"], domov["pozicija"]), ("Rock 1", 1, 1, 3, 95))
        # Nakljucni red: Domov pove mesto v redu predvajanja (kot plosca vrste).
        self.k.izvedi("mediaNazadnje", ["zapomni", self.izvor, 1, vnosi[1], 3, [2, 0, 1], False])
        self.assertEqual(self.k.izvedi("mediaPolice", ["domov", ""])["nazadnje_seznam"]["poz"], 2)
        self.k.izvedi("mediaNazadnje", ["zapomni", self.izvor, 1, vnosi[1], 3, None, False])
        self.k.shrani_napredek(uri, 95.0, 240.0)
        r = self.k.izvedi("mediaNazadnje", ["nadaljuj"])
        self.assertEqual((r["mesto"], r["pozicija"], len(r["vnosi"])), (1, 95, 3))
        self.k.izvedi("mediaPredvajaj", [r["vnosi"][1]["id"]])
        self.assertEqual(self.predvajano[-1][3], 95)                        # skladba zacne na 95 s
        self.k.izvedi("mediaPredvajaj", [r["vnosi"][1]["id"]])
        self.assertEqual(self.predvajano[-1][3], 0)                         # samo enkrat

    def test_izbrisan_seznam_izgine_brez_napake(self):
        self.k.izvedi("mediaNazadnje", ["zapomni", self.izvor, 0, self._vnosi("Rock 1")[0], 3])
        self.k.mc.odstrani_seznam("Rock 1")
        self.assertIsNone(self.k.izvedi("mediaPolice", ["domov", ""])["nazadnje_seznam"])
        self.assertEqual(self.k.izvedi("mediaNazadnje", ["nadaljuj"]), {})

    def test_naslednji_je_najblizji_po_zvrsti_brez_slisanih(self):
        self.k.izvedi("mediaNazadnje", ["zapomni", self.izvor, 2, self._vnosi("Rock 1")[2], 3])
        r = self.k.izvedi("mediaNazadnje", ["naslednji"])
        self.assertEqual(r["izvor"]["ref"], "Rock 2")
        self.assertEqual([v["naslov"] for v in r["vnosi"]], ["Pesem 20", "Pesem 21"])   # »Alfa - Pesem 0« je bila slisana
        self.assertEqual(r["podobnost"], 1.0)
        # Safeer je izbral Rock 2: ob koncu Rock 2 ne nazaj na Rock 1 (veriga), ampak naprej.
        self.k.izvedi("mediaNazadnje", ["zapomni", r["izvor"], 0, r["vnosi"][0], 3, None, True])
        r2 = self.k.izvedi("mediaNazadnje", ["naslednji"])
        self.assertNotEqual(r2["izvor"]["ref"], "Rock 1")

    def test_naslednji_uporabi_sveze_zvrsti_brez_ponovnega_branja(self):
        """Konec seznama ne caka na ponovno branje knjiznice in streznikov, ce so zvrsti sveze (< 10 min)."""
        self.k.izvedi("mediaSkrij", ["polica:samodejni", True])      # skriti samodejni seznami niso kandidati
        self.k.izracunaj_samodejne()
        klici, prava = [], self.k._zberi_skladbe
        self.k._zberi_skladbe = lambda: klici.append(1) or prava()
        self.k.izvedi("mediaNazadnje", ["zapomni", self.izvor, 2, self._vnosi("Rock 1")[2], 3])
        self.assertEqual(self.k.izvedi("mediaNazadnje", ["naslednji"])["izvor"]["ref"], "Rock 2")
        self.assertEqual(klici, [])

    def test_skladba_v_zivo_je_oznacena(self):
        vnosi = self._vnosi("Pop")
        self.assertFalse(any(v.get("v_zivo") for v in vnosi))
        self.assertTrue(self.k.izvedi("mediaNazadnje", ["zivo", vnosi[0]["id"]]))
        self.assertEqual([bool(v.get("v_zivo")) for v in self._vnosi("Pop")], [True, False])


if __name__ == "__main__":
    unittest.main()
