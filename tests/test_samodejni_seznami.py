"""Samodejni seznami predvajanja (core/samodejni_seznami.py) in njihova pot skozi most kataloga (core/os_katalog.py):
prag skladb, pravilo 30 dni, zvrsti in izvajalci, stalen vrstni red, »Shrani kot seznam« in skriti predmeti menija."""
import json
import random
import tempfile
import time
import unittest
from pathlib import Path

from core import os_katalog as K
from core import os_knjiznica as KN
from core import samodejni_seznami as SS

ZDAJ = 1_800_000_000
DAN = 86400


def _skladba(i, **polja):
    s = {"id": "id:%d" % i, "naslov": "Skladba %02d" % i, "izvajalec": "Izvajalec %d" % (i % 3), "url": "https://tok.test/%d.mp3" % i}
    s.update(polja)
    return s


def _po_vrsti(seznami):
    return {(x["vrsta"], x["ime"]): x for x in seznami}


class Pravila(unittest.TestCase):
    def test_pod_pragom_ni_seznama(self):
        malo = [_skladba(i, n=3, zadnjic=ZDAJ - DAN) for i in range(SS.NAJMANJ - 1)]
        self.assertEqual(SS.sestavi(malo, ZDAJ), [])
        dovolj = [_skladba(i, n=3, zadnjic=ZDAJ - DAN) for i in range(SS.NAJMANJ)]
        self.assertIn(("najvec", ""), _po_vrsti(SS.sestavi(dovolj, ZDAJ)))

    def test_najvec_po_stevcu(self):
        skladbe = [_skladba(i, n=i + 1, zadnjic=ZDAJ - DAN) for i in range(10)]
        najvec = _po_vrsti(SS.sestavi(skladbe, ZDAJ))[("najvec", "")]
        self.assertEqual([s["id"] for s in najvec["skladbe"][:3]], ["id:9", "id:8", "id:7"])

    def test_pravilo_30_dni(self):
        stare = [_skladba(i, n=2, zadnjic=ZDAJ - 31 * DAN) for i in range(8)]
        nove = [_skladba(100 + i, n=5, zadnjic=ZDAJ - 29 * DAN) for i in range(8)]
        nikoli = [_skladba(200 + i) for i in range(8)]
        dolgo = _po_vrsti(SS.sestavi(stare + nove + nikoli, ZDAJ))[("dolgo", "")]
        self.assertEqual(sorted(s["id"] for s in dolgo["skladbe"]), sorted(s["id"] for s in stare))
        # Ce je stari le 7, seznama ni.
        self.assertNotIn(("dolgo", ""), _po_vrsti(SS.sestavi(stare[:7] + nove, ZDAJ)))

    def test_odkrij_samo_nikoli_predvajane_in_nazadnje_dodano(self):
        nikoli = [_skladba(i, dodano=ZDAJ - i) for i in range(9)]
        predvajane = [_skladba(50 + i, n=1, zadnjic=ZDAJ - DAN, dodano=ZDAJ) for i in range(9)]
        p = _po_vrsti(SS.sestavi(nikoli + predvajane, ZDAJ))
        self.assertEqual(sorted(s["id"] for s in p[("odkrij", "")]["skladbe"]), sorted(s["id"] for s in nikoli))
        self.assertEqual(p[("nazadnje", "")]["stevilo"], 18)
        self.assertEqual(p[("nazadnje", "")]["skladbe"][0]["dodano"], ZDAJ)

    def test_zvrsti_in_izvajalci(self):
        rock = [_skladba(i, zanr="Rock, Pop", izvajalec="Band A feat. Gost") for i in range(9)]
        jazz = [_skladba(20 + i, zanr="jazz", izvajalec="Kvartet") for i in range(8)]
        malo = [_skladba(40 + i, zanr="Polka", izvajalec="Ansambel") for i in range(3)]
        p = _po_vrsti(SS.sestavi(rock + jazz + malo, ZDAJ))
        self.assertEqual(p[("zanr", "Rock")]["stevilo"], 9)
        self.assertEqual(p[("zanr", "Pop")]["stevilo"], 9)
        self.assertEqual(p[("zanr", "jazz")]["stevilo"], 8)
        self.assertNotIn(("zanr", "Polka"), p)                       # pod pragom
        self.assertEqual(p[("izvajalec", "Band A")]["stevilo"], 9)    # »feat.« ne razbije izvajalca
        self.assertIn(("izvajalec", "Kvartet"), p)
        self.assertNotIn(("izvajalec", "Ansambel"), p)
        self.assertLessEqual(sum(1 for k in p if k[0] == "zanr"), SS.NAJVEC_ZVRSTI)

    def test_stalen_vrstni_red(self):
        skladbe = [_skladba(i, n=i % 4, zadnjic=ZDAJ - (i % 5) * DAN, dodano=ZDAJ - (i % 7), zanr="Rock") for i in range(40)]
        prvi = SS.sestavi(skladbe, ZDAJ)
        for seme in range(5):
            premesane = list(skladbe)
            random.Random(seme).shuffle(premesane)
            self.assertEqual(SS.sestavi(premesane, ZDAJ), prvi)

    def test_naslovnice_samo_prave_in_razlicne(self):
        skladbe = [_skladba(i, n=1, zadnjic=ZDAJ, slika="https://s.test/%d.jpg" % (i % 2)) for i in range(8)]
        skladbe += [_skladba(50, n=1, zadnjic=ZDAJ, slika="javascript:x")]
        najvec = _po_vrsti(SS.sestavi(skladbe, ZDAJ))[("najvec", "")]
        self.assertEqual(sorted(najvec["slike"]), ["https://s.test/0.jpg", "https://s.test/1.jpg"])

    def test_dvojnik_iz_dveh_virov_je_ena_skladba(self):
        skladbe = [_skladba(i, n=1, zadnjic=ZDAJ) for i in range(8)] + [_skladba(0, n=5, zadnjic=ZDAJ, slika="https://s.test/a.jpg")]
        najvec = _po_vrsti(SS.sestavi(skladbe, ZDAJ))[("najvec", "")]
        self.assertEqual(najvec["stevilo"], 8)
        self.assertEqual(najvec["skladbe"][0]["n"], 5)

    def test_najvec_skladb_in_brez_naslova(self):
        skladbe = [_skladba(i, n=1, zadnjic=ZDAJ) for i in range(80)] + [{"id": "x", "naslov": "", "url": "https://t.test/x.mp3"}]
        najvec = _po_vrsti(SS.sestavi(skladbe, ZDAJ))[("najvec", "")]
        self.assertEqual((najvec["stevilo"], len(najvec["skladbe"])), (SS.NAJVEC_SKLADB, SS.NAJVEC_SKLADB))

    def test_izvajalec_iz_imena(self):
        self.assertEqual(SS.izvajalec_iz_imena("03 - Izvajalec - Naslov.mp3"), "Izvajalec")
        self.assertEqual(SS.izvajalec_iz_imena("Izvajalec – Naslov.flac"), "Izvajalec")
        self.assertEqual(SS.izvajalec_iz_imena("Naslov.mp3"), "")


class MostKataloga(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.dogodki = []
        self.lokalna = KN.Knjiznica(Path(self.mapa.name) / "m.sqlite3")
        self.k = K.Katalog(str(Path(self.mapa.name) / "media"), dogodek=lambda v, p: self.dogodki.append((v, p)),
                           v_glavni=lambda delo: delo(), predvajaj=lambda *a: True, vdelano=lambda u: True,
                           youtube=lambda u, n: True, youtube_ukaz=lambda u: True, lokalna=self.lokalna)
        album = Path(self.mapa.name) / "Glasba" / "Album"
        album.mkdir(parents=True)
        (album / "cover.jpg").write_bytes(b"x")
        self.poti = []
        for i in range(9):
            pot = album / ("Izvajalec - Skladba %d.mp3" % i)
            pot.write_bytes(b"x")
            self.poti.append(str(pot.resolve()))
        self.lokalna.dodaj(self.poti)

    def test_seznami_iz_knjiznice_predvajanje_in_shrani(self):
        seznami = self.k.izracunaj_samodejne()
        p = _po_vrsti(seznami)
        odkrij = p[("odkrij", "")]
        self.assertEqual(odkrij["stevilo"], 9)
        self.assertTrue(odkrij["slike"][0].startswith("file://") and odkrij["slike"][0].endswith("/cover.jpg"))
        self.assertIn(("izvajalec", "Izvajalec"), p)                       # izvajalec iz imena datoteke
        self.assertEqual(odkrij["skladbe"][0]["naslov"], "Skladba 0")       # brez »Izvajalec - « v naslovu
        self.assertIn(("mediaSamodejniOsvezeni", None), self.dogodki)
        # Most: povzetek brez skladb, nato skladbe kot vnosi kataloga in predvajanje.
        self.k._samodejni["cas"] = time.time()                               # svez: brez ozadne niti v preizkusu
        povzetek = self.k.izvedi("mediaSamodejniSeznami", [])
        self.assertNotIn("skladbe", povzetek["seznami"][0])
        vnosi = self.k.izvedi("mediaSamodejniSeznam", [odkrij["id"]])["vnosi"]
        self.assertEqual(len(vnosi), 9)
        self.assertTrue(vnosi[0]["id"].startswith("samodejno-lokalno:"))
        self.assertTrue(self.k.izvedi("mediaPredvajaj", [vnosi[0]["id"]]).get("native"))
        # Predvajanje steje knjiznica (ne polica): odkrij izgubi skladbo, polic ne podvaja.
        self.assertEqual(sum(v["predvajanj"] for v in self.lokalna.glasba()), 1)
        self.assertEqual(self.k.police.predvajanja(), {})
        izid = self.k.izvedi("mediaSamodejniShrani", [odkrij["id"], "Odkrij"])
        self.assertEqual((izid["ok"], izid["stevilo"]), (True, 9))
        shranjen = json.loads((Path(self.mapa.name) / "media" / "seznami.json").read_text(encoding="utf-8"))[0]
        self.assertEqual(shranjen["ime"], "Odkrij")
        self.assertTrue(all(s["url"].startswith("file:") for s in shranjen["skladbe"]))
        self.assertEqual(self.k.izvedi("mediaSamodejniShrani", ["ni-ga", "X"]), {"napaka": "ni_mogoce"})

    def test_osvezitev_najvec_enkrat_na_10_minut(self):
        zacetki = []
        self.k.izracunaj_samodejne = lambda: zacetki.append(1) or []
        self.k.izvedi("mediaSamodejniSeznami", [])
        for _ in range(50):
            if zacetki:
                break
            time.sleep(0.02)
        self.k.izvedi("mediaSamodejniSeznami", [])
        time.sleep(0.1)
        self.assertEqual(len(zacetki), 1)
        self.assertEqual(SS.OSVEZI_S, 600)

    def test_skriti_predmeti_menija(self):
        self.assertEqual(self.k.izvedi("mediaSkrito", []), [])
        self.assertEqual(self.k.izvedi("mediaSkrij", ["kat:tv", True]), ["kat:tv"])
        self.assertEqual(self.k.izvedi("mediaSkrij", ["vir:abc123", True]), ["kat:tv", "vir:abc123"])
        self.assertIn(("mediaSkrito", ["kat:tv", "vir:abc123"]), self.dogodki)
        self.assertEqual(self.k.izvedi("mediaSkrij", ["kat:tv", False]), ["vir:abc123"])
        for napacen in ("kat:domov", "kat:../x", "", "nekaj:tv"):
            with self.assertRaises(ValueError):
                self.k.izvedi("mediaSkrij", [napacen, True])
        # Obstojno (nastavitve Medijskega centra, ne localStorage): nov most istega imenika vidi isto.
        drugi = K.Katalog(str(Path(self.mapa.name) / "media"), dogodek=lambda v, p: None, v_glavni=lambda d: d(),
                          predvajaj=lambda *a: True, vdelano=lambda u: True, youtube=lambda u, n: True,
                          youtube_ukaz=lambda u: True, lokalna=self.lokalna)
        self.assertEqual(drugi.izvedi("mediaSkrito", []), ["vir:abc123"])


if __name__ == "__main__":
    unittest.main()
