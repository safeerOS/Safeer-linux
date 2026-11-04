"""Scit proti skupnim primerom (tests/skupni-primeri/scit-pravila.json - ISTA datoteka v Android-tv, kjer jo preverja
tests/ScitSkupniPrimeriTest.kt). Lastnik 4. 11. 2026: »ni optimalno delati vec Scitov za razlicne OS« - pravilo,
spremenjeno samo na eni strani, tu ali tam pade. Preverja pot razresevalnika (Razresevalnik._odgovori) brez omrezja:
streznikov naprej ni, poslano naprej dobi SERVFAIL.

Primer z »neujemanje« in »linux« v »razlicno_na« je znana razlika do Androida: preskocen z izpisom; ce Linux postane
enak, preizkus pade, da se oznaka umakne (razlika ne sme ostati zapisana, ko je ni vec)."""
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_scit  # noqa: E402

PRIMERI = Path(__file__).resolve().parent / "skupni-primeri" / "scit-pravila.json"
PLATFORMA = "linux"


def poizvedba(ime: str) -> bytes:
    """Poizvedba DNS, kot jo poslje aplikacija: oznake med pikami (prazne izpuscene), bajti UTF-8."""
    telo = b"".join(struct.pack("B", len(o)) + o for o in (d.encode("utf-8") for d in ime.split(".") if d)) + b"\x00"
    return struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0) + telo + struct.pack("!HH", 1, 1)


class Shramba(dict):
    def get(self, k, d=None):
        return dict.get(self, k, d)

    def set(self, k, v):
        self[k] = v


class ScitSkupniPrimeri(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(PRIMERI.read_text(encoding="utf-8"))

    def setUp(self):
        self._mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self._mapa.cleanup)

    def _scit(self):
        """Pravi Scit in Seznami (NIKOLI, posodobitve, preverjanje, Webtor, groznje) z naborom iz skupnih seznamov."""
        sc = os_scit.Scit(Shramba(), mapa=self._mapa.name)
        s = os_scit.Seznami(self._mapa.name)
        sez = self.d["seznami"]
        s.nabor = os_scit.Nabor.iz_domen(
            [(d, "oglasi") for d in os_scit.razcleni_seznam("\n".join(sez["oglasi"]))]
            + [(d, "groznje") for d in os_scit.razcleni_seznam("\n".join(sez["groznje"]))])
        sc.seznami = s
        sc.razresevalnik = os_scit.Razresevalnik(sc._kategorija, lambda: [])
        return sc

    @staticmethod
    def _izid(sc, ime: str) -> str:
        odgovor = sc.razresevalnik._odgovori(poizvedba(ime), False)
        rcode = odgovor[3] & 0x0F if odgovor else None
        if rcode in (None, 2):
            return "spuscen"                      # poslano naprej (streznikov naprej v preizkusu ni: SERVFAIL)
        return "ustavljeno" if rcode == 3 else "rcode %d" % rcode

    def _preveri(self, p: dict, dobljeno, pricakovano, opis: str):
        if p.get("neujemanje") and PLATFORMA in p.get("razlicno_na", ["android", "linux"]):
            print("  PRESKOCENO (neujemanje) %s: %s; Linux da %s" % (opis, p["neujemanje"], dobljeno))
            self.assertNotEqual(dobljeno, pricakovano, "neujemanje odpravljeno - umakni oznako: " + opis)
            return
        self.assertEqual(dobljeno, pricakovano, opis)

    def test_verzija_in_seznami_pravila(self):
        """Krajevna imena, kanarcek, zasciteni gostitelji in trajanje izjeme so v kodi ISTI kot v skupnih primerih."""
        self.assertEqual(self.d["verzija"], 2)
        self.assertEqual(list(os_scit.KRAJEVNA), self.d["krajevna"])
        self.assertEqual(list(os_scit.KRAJEVNE_KONCNICE), self.d["krajevne_koncnice"])
        self.assertEqual(os_scit.KANAREK_DOH, self.d["kanarek_doh"])
        self.assertEqual(list(os_scit.ZASCITENI), self.d["zasciteni"])
        self.assertEqual(os_scit.IZJEMA_S, self.d["izjema_dni"] * 24 * 3600)

    def test_ustavljeno(self):
        sc = self._scit()
        for p in self.d["ustavljeno"]:
            with self.subTest(p["opis"]):
                self._preveri(p, self._izid(sc, p["ime"]), p["izid"], p["opis"])

    def test_izjeme(self):
        for p in self.d["izjeme"]:
            with self.subTest(p["opis"]):
                sc = self._scit()
                ura = [1_800_000_000.0]
                sc._ura = lambda: ura[0]
                # Dovoliti je mogoce samo nazadnje ustavljeno ime: najprej ga vprasa aplikacija, potem uporabnik spusti.
                self._izid(sc, p["izjema"])
                cista = os_scit.cista_domena(p["izjema"])
                sprejeta = bool(cista) and cista in sc.dovoli(p["izjema"])["izjeme"]
                ura[0] += p["dan"] * 24 * 3600
                self._preveri(p, (sprejeta, self._izid(sc, p["poizvedba"])), (p["sprejeta"], p["izid"]), p["opis"])

    def test_razresevalci_naprej(self):
        for p in self.d["razresevalci_naprej"]:
            with self.subTest(p["opis"]):
                sc = os_scit.Scit(Shramba(), mapa=self._mapa.name)      # uporabnik se ni izbral
                izbira, _ = sc.naprej()
                if izbira != "router":
                    izid = "tuj"                  # DoH k zunanjemu ponudniku
                elif p["krajevni"]:
                    izid = "krajevni"             # samo strezniki omrezja (v preizkusu jih ne vprasamo)
                else:
                    r = os_scit.Razresevalnik(lambda _i: None, lambda: [], sc._naprej)
                    r.sifrirano_naprej = lambda: sc.naprej()[0] != "router"
                    o = r._odgovori(poizvedba("a.example"), False)
                    izid = "brez_odgovora" if o is None else ("servfail" if (o[3] & 0x0F) == 2 else "rcode %d" % (o[3] & 0x0F))
                self._preveri(p, izid, p["izid"], p["opis"])


if __name__ == "__main__":
    unittest.main()
