"""Izvirni jezik naslovov (core/izvirni_jezik.py): ista pravila in isti primeri kot Safeer OS za Android
(tests/IzvirniJezikTest.kt), plus predpomnilnik in vprasanja Wikidati brez omrezja (vbrizgan odpiralec)."""
import io
import os
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse

from core import izvirni_jezik as j

Q = "http://www.wikidata.org/entity/"


def _vrstica(imdb, jezik="", drzava=""):
    return '"%s"\t%s\t%s' % (imdb, "<%s%s>" % (Q, jezik) if jezik else "", "<%s%s>" % (Q, drzava) if drzava else "")


class Pravila(unittest.TestCase):
    def test_seznam_jezikov(self):
        self.assertEqual(len(set(j.KODE)), len(j.KODE))
        self.assertTrue(all(len(k) == 2 and k == k.lower() for k in j.KODE))
        for jezik in j.JEZIKI:
            self.assertTrue(jezik.predmeti and jezik.drzave, jezik.koda)
            self.assertTrue(all(re.fullmatch(r"Q[0-9]+", q) for q in jezik.predmeti + jezik.drzave), jezik.koda)
        self.assertEqual(j.po_kodi("sl").predmeti, ("Q9063",))
        self.assertIsNone(j.po_kodi("xx"))

    def test_glavni_jezik(self):
        g = j.glavni
        # En sam jezik je glavni, tudi ce drzave ne poznamo.
        self.assertEqual(g(["Q1860"], ["Q30"]), ["en"])
        self.assertEqual(g(["Q9176"], []), ["ko"])
        # Vec jezikov: zmaga tisti, ki je doma v drzavi izvora (ameriski film z nekaj francoscine in japonscine).
        self.assertEqual(g(["Q150", "Q1860", "Q5287"], ["Q30", "Q145"]), ["en"])
        self.assertEqual(g(["Q652", "Q1860"], ["Q30"]), ["en"])
        self.assertEqual(g(["Q1860", "Q5287"], ["Q17"]), ["ja"])
        # Vec domacih jezikov: anglescina (ameriski film z nemskim soproducentom ni nemski film).
        self.assertEqual(g(["Q150", "Q188", "Q1860"], ["Q30", "Q183"]), ["en"])
        # Brez anglescine ostaneta oba (belgijski film v francoscini in nizozemscini).
        self.assertEqual(set(g(["Q150", "Q7411"], ["Q31"])), {"fr", "nl"})
        # Nobeden ni doma v drzavi izvora: anglescina, sicer vsi.
        self.assertEqual(g(["Q5287", "Q1860"], ["Q142"]), ["en"])
        self.assertEqual(set(g(["Q5287", "Q9176"], ["Q142"])), {"ja", "ko"})
        # Srbohrvascina: jugoslovanski film sodi pod hrvascino, srbscino in bosanscino; hrvaski samo pod hrvascino.
        self.assertEqual(set(g(["Q9301"], ["Q83286"])), {"hr", "sr", "bs"})
        self.assertEqual(g(["Q9301"], ["Q224"]), ["hr"])
        self.assertEqual(set(g(["Q9301"], [])), {"hr", "sr", "bs"})
        self.assertEqual(set(g(["Q9301", "Q9063"], ["Q83286"])), {"sl", "hr", "sr", "bs"})
        # Slovenski film.
        self.assertEqual(g(["Q9063"], ["Q215"]), ["sl"])
        # Kitajscina v vec predmetih (mandarinscina, kantonscina) je en jezik izbire.
        self.assertEqual(g(["Q9192", "Q9186"], ["Q8646"]), ["zh"])
        # Jezik, ki ga izbira ne ponuja, ali brez jezika: ne vemo.
        self.assertEqual(g(["Q123456789"], ["Q30"]), [])
        self.assertEqual(g([], ["Q30"]), [])

    def test_razlicice_jezika(self):
        """Wikidata pri filmih in serijah uporablja tudi razlicice jezika (»American English« pri Breaking Bad).
        Sodijo pod jezik sam - sicer bi naslov veljal za naslov neznanega jezika in se med izbiro ne bi pokazal."""
        g = j.glavni
        self.assertEqual(g(["Q7976"], ["Q30"]), ["en"])              # American English (resnicen primer: tt0903747)
        self.assertEqual(g(["Q7979"], ["Q145"]), ["en"])             # British English
        self.assertEqual(g(["Q7976", "Q1860"], ["Q30"]), ["en"])     # razlicica in jezik sam sta en jezik
        self.assertEqual(g(["Q7976", "Q1321"], ["Q30"]), ["en"])     # ameriska serija z nekaj spanscine
        self.assertEqual(g(["Q750553"], ["Q155"]), ["pt"])           # Brazilian Portuguese
        self.assertEqual(g(["Q387066"], ["Q39"]), ["de"])            # Swiss German
        self.assertEqual(g(["Q979914"], ["Q16"]), ["fr"])            # Quebec French
        self.assertEqual(g(["Q616620"], ["Q96"]), ["es"])            # Mexican Spanish
        self.assertEqual(g(["Q34147"], ["Q31"]), ["nl"])             # Flemish Dutch
        self.assertEqual(g(["Q29919"], []), ["ar"])                  # Egyptian Arabic
        self.assertEqual(g(["Q24841726"], ["Q148"]), ["zh"])         # Putonghua
        self.assertEqual(g(["Q36778", "Q9192"], ["Q865"]), ["zh"])   # tajvanski film: hokkien in mandarinscina
        self.assertEqual(g(["Q33845"], ["Q38"]), ["it"])             # neapeljscina: italijanska serija
        self.assertEqual(g(["Q178440"], []), ["fa"])                 # dari
        self.assertEqual(j.iz_paketa("?imdb\t?jezik\t?drzava\n" + _vrstica("tt0903747", "Q7976", "Q30")),
                         {"tt0903747": ["en"]})
        # Prvi predmet je jezik sam; isti predmet pri vec jezikih je samo srbohrvascina.
        vsi = [q for jezik in j.JEZIKI for q in jezik.predmeti]
        self.assertEqual(sorted(q for q in set(vsi) if vsi.count(q) > 1), ["Q9301"])
        self.assertEqual([j.po_kodi(k).predmeti[0] for k in ("en", "de", "pt", "zh", "ar")],
                         ["Q1860", "Q188", "Q5146", "Q7850", "Q13955"])

    def test_kode_virov(self):
        """Katalogi vodijo isti jezik pod vec kodami (TMDB: sh, cn, nb): izbira jih zajame."""
        self.assertEqual(j.kode_vira("sl"), ("sl",))
        self.assertEqual(j.kode_vira("hr"), ("hr", "sh"))
        self.assertEqual(j.kode_vira("zh"), ("zh", "cn"))
        self.assertEqual(j.kode_vira("no"), ("no", "nb", "nn"))
        self.assertTrue(j.ustreza("sh", "sr") and j.ustreza("sh", "bs") and j.ustreza("cn", "zh") and j.ustreza("sl", "sl"))
        self.assertFalse(j.ustreza("", "sl") or j.ustreza(None, "sl") or j.ustreza("en", "sl") or j.ustreza("sh", "sl"))
        self.assertTrue(set(j.SORODNE) <= set(j.KODE))

    def test_poizvedba_paket(self):
        p = j.poizvedba_paket(["tt0111161", "tt0111161", "tt1375666", "nm0000001", 'tt12" } DROP', "", "tt123"])
        self.assertIn('VALUES ?imdb { "tt0111161" "tt1375666" }', p)
        self.assertNotIn("nm0000001", p)
        self.assertNotIn("DROP", p)
        for lastnost in ("wdt:P345", "wdt:P364", "wdt:P495"):
            self.assertIn(lastnost, p)
        veliko = j.poizvedba_paket(["tt%07d" % i for i in range(1, 201)])
        self.assertEqual(len(re.findall(r'"tt[0-9]+"', veliko)), j.NAJVEC_V_PAKETU)
        self.assertLess(len(veliko), 4000)

    def test_odgovor_paketa(self):
        # Resnicen primer (4. 10. 2026): krizni produkt jezikov in drzav; neznan naslov manjka.
        odgovor = "\n".join(
            ["?imdb\t?jezik\t?drzava"]
            + [_vrstica("tt1375666", jz, d) for d in ("Q30", "Q145") for jz in ("Q150", "Q1860", "Q5287")]
            + [_vrstica("tt0361748", jz, d) for d in ("Q30", "Q183") for jz in ("Q150", "Q188", "Q1860")]
            + [_vrstica("tt0245429", "Q5287", "Q17"), _vrstica("tt0111161", "Q1860", "Q30"),
               _vrstica("tt6751668", "Q9176", "Q884"), _vrstica("tt7654321", "", "Q30"), _vrstica("tt7654322"),
               "", "smeti brez tabulatorja"])
        jeziki = j.iz_paketa(odgovor)
        self.assertEqual((jeziki["tt1375666"], jeziki["tt0361748"], jeziki["tt0245429"]), (["en"], ["en"], ["ja"]))
        self.assertEqual((jeziki["tt0111161"], jeziki["tt6751668"]), (["en"], ["ko"]))
        # Naslov, ki ga Wikidata pozna, a brez jezika: prazen seznam (ne vemo). Naslov, ki ga ni v odgovoru: manjka.
        self.assertEqual((jeziki["tt7654321"], jeziki["tt7654322"]), ([], []))
        self.assertNotIn("tt9999999", jeziki)
        self.assertEqual(len(jeziki), 7)
        self.assertEqual(j.iz_paketa(""), {})
        self.assertEqual(j.iz_paketa("?imdb\t?jezik\t?drzava\n"), {})

    def test_celica(self):
        self.assertEqual(j.celica("<http://www.wikidata.org/entity/Q42>"), "Q42")
        self.assertEqual(j.celica("2009"), "2009")
        self.assertEqual(j.celica('"a"^^<x>'), "a")
        self.assertEqual(j.celica('"Dolina \\"miru\\"\\tin \\\\ se"@sl'), 'Dolina "miru" in \\ se')

    def test_zapis_v_predpomnilniku(self):
        # Znan jezik velja dolgo, neznan nekaj dni; poskodovan zapis ali zapis iz prihodnosti ne velja.
        zdaj = 2_000 * 86_400
        self.assertEqual(j.iz_zapisa(j.v_zapis(["en"], zdaj), zdaj), ["en"])
        self.assertEqual(j.iz_zapisa(j.v_zapis(["hr", "sr", "bs"], zdaj), zdaj + 100 * 86_400), ["hr", "sr", "bs"])
        self.assertIsNone(j.iz_zapisa(j.v_zapis(["en"], zdaj), zdaj + j.ZNAN_VELJA + 1))
        self.assertEqual(j.iz_zapisa(j.v_zapis([], zdaj), zdaj + 86_400), [])
        self.assertIsNone(j.iz_zapisa(j.v_zapis([], zdaj), zdaj + j.NEZNAN_VELJA + 1))
        self.assertEqual(j.iz_zapisa(j.v_zapis(["xx", "en"], zdaj), zdaj), ["en"])
        for slab in (None, "", "en", "en;x", "en;1;2"):
            self.assertIsNone(j.iz_zapisa(slab, zdaj), slab)
        self.assertIsNone(j.iz_zapisa(j.v_zapis(["en"], zdaj + 5), zdaj))


class _Odgovor(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class Predpomnilnik(unittest.TestCase):
    """Vprasanja Wikidati z vbrizganim odpiralcem: kaj vprasamo, kaj si zapomnimo, kaj naredimo ob izpadu."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.datoteka = os.path.join(self.tmp.name, "mapa", "izvirni-jeziki.tsv")
        self.zahteve = []
        self.zaklep = threading.Lock()
        self.zdaj = [2_000 * 86_400.0]
        self.znani = {"tt0111161": ("Q1860", "Q30"), "tt0245429": ("Q5287", "Q17"), "tt0043703": ("Q9063", "Q36704")}
        self.napaka = None

    def tearDown(self):
        self.tmp.cleanup()

    def _odpri(self, zahteva, timeout=None):
        with self.zaklep:
            self.zahteve.append(zahteva)
        if self.napaka is not None:
            raise self.napaka
        poizvedba = urllib.parse.parse_qs(urllib.parse.urlsplit(zahteva.full_url).query)["query"][0]
        vrstice = ["?imdb\t?jezik\t?drzava"]
        for ident in re.findall(r'"(tt[0-9]+)"', poizvedba):
            if ident in self.znani:
                vrstice.append(_vrstica(ident, *self.znani[ident]))
        return _Odgovor("\n".join(vrstice).encode("utf-8"))

    def _nov(self):
        return j.IzvirniJeziki(self.datoteka, "0.4.51", odpri=self._odpri, ura=lambda: self.zdaj[0])

    def test_vprasa_enkrat_in_si_zapomni(self):
        viri = self._nov()
        self.assertIsNone(viri.znani("tt0111161"))
        izid = viri.jeziki(["tt0111161", "tt0245429", "tt9999999", "ni-id", "tt0111161"])
        self.assertEqual(izid, {"tt0111161": ["en"], "tt0245429": ["ja"], "tt9999999": []})
        self.assertEqual(len(self.zahteve), 1)
        z = self.zahteve[0]
        # Wikidata dobi samo javne id-je naslovov; odjemalec se predstavi, kot Wikidata prosi.
        self.assertTrue(z.full_url.startswith("https://query.wikidata.org/sparql?query="))
        self.assertEqual(z.get_header("User-agent"), "SafeerOS/0.4.51 (https://safeer.si)")
        self.assertEqual(z.get_header("Accept"), "text/tab-separated-values")
        self.assertNotIn("ni-id", urllib.parse.unquote(z.full_url))
        # Drugic iz predpomnilnika - tudi v novem primerku (po ponovnem zagonu) in tudi neznan naslov.
        self.assertEqual(viri.jeziki(["tt0111161", "tt9999999"]), {"tt0111161": ["en"], "tt9999999": []})
        nov = self._nov()
        self.assertEqual(nov.znani("tt0245429"), ["ja"])
        self.assertEqual(nov.jeziki(["tt0245429", "tt9999999"]), {"tt0245429": ["ja"], "tt9999999": []})
        self.assertEqual(len(self.zahteve), 1)
        # Neznanega vprasamo znova cez nekaj dni (Wikidata se dopolnjuje), znanega ne.
        self.zdaj[0] += j.NEZNAN_VELJA + 10
        self.znani["tt9999999"] = ("Q9063", "Q215")
        self.assertEqual(nov.jeziki(["tt0245429", "tt9999999"]), {"tt0245429": ["ja"], "tt9999999": ["sl"]})
        self.assertEqual(len(self.zahteve), 2)
        self.assertNotIn("tt0245429", urllib.parse.unquote(self.zahteve[1].full_url))

    def test_veliko_naslovov_gre_v_paketih(self):
        viri = self._nov()
        idji = ["tt%07d" % i for i in range(1, 2 * j.NAJVEC_V_PAKETU + 11)]
        izid = viri.jeziki(idji + ["tt0043703"])
        self.assertEqual(len(self.zahteve), 3)
        self.assertEqual(izid["tt0043703"], ["sl"])
        self.assertEqual(len(izid), len(idji) + 1)
        for z in self.zahteve:
            self.assertLess(len(z.full_url), 8000)

    def test_izpad_omrezja_ne_ustavi_kataloga_in_se_ne_zapise(self):
        viri = self._nov()
        self.napaka = OSError("ni omrezja")
        idji = ["tt%07d" % i for i in range(1, 5 * j.NAJVEC_V_PAKETU)]
        self.assertEqual(viri.jeziki(idji), {})
        # Po prvem izpadu ne sprasujemo znova in znova (najvec toliko zahtev, kot jih je slo hkrati).
        self.assertLessEqual(len(self.zahteve), 4)
        prej = len(self.zahteve)
        self.assertEqual(viri.jeziki(["tt0111161"]), {})
        self.assertEqual(len(self.zahteve), prej, "med premorom brez novih vprasanj")
        self.assertIsNone(viri.znani("tt0111161"), "naslov brez odgovora ostane nevprasan")
        # Po premoru spet vprasamo.
        self.napaka = None
        self.zdaj[0] += viri.PREMOR_PO_NAPAKI + 1
        self.assertEqual(viri.jeziki(["tt0111161"]), {"tt0111161": ["en"]})

    def test_prevec_vprasanj_spostuje_premor(self):
        viri = self._nov()
        self.napaka = urllib.error.HTTPError("https://query.wikidata.org/sparql", 429, "Too Many Requests",
                                             {"Retry-After": "300"}, io.BytesIO(b""))
        self.assertEqual(viri.jeziki(["tt0111161"]), {})
        self.napaka = None
        self.zdaj[0] += 200
        self.assertEqual(viri.jeziki(["tt0111161"]), {})
        self.assertEqual(len(self.zahteve), 1, "do konca premora brez vprasanj")
        self.zdaj[0] += 101
        self.assertEqual(viri.jeziki(["tt0111161"]), {"tt0111161": ["en"]})

    def test_poskodovana_datoteka_in_omejitev_velikosti(self):
        os.makedirs(os.path.dirname(self.datoteka))
        with open(self.datoteka, "w", encoding="utf-8") as d:
            d.write("smeti\n\ttt1\nnm0000001\ten;%d\ntt0111161\tde;%d\ntt0245429\tpokvarjeno\n" % (self.zdaj[0], self.zdaj[0]))
        viri = self._nov()
        self.assertEqual(viri.znani("tt0111161"), ["de"])           # veljaven zapis iz datoteke
        self.assertIsNone(viri.znani("tt0245429"))                   # pokvarjen zapis: vprasamo znova
        self.assertEqual(viri.jeziki(["tt0245429"]), {"tt0245429": ["ja"]})
        viri.NAJVEC_ZAPISOV = 50
        for i in range(120):
            viri._zapisi["tt%07d" % (i + 100)] = j.v_zapis(["en"], self.zdaj[0] - 1000 + i)
        viri._shrani()
        self.assertLessEqual(len(viri._zapisi), 50)
        self.assertIn("tt0000219", viri._zapisi)                     # najnovejsi ostanejo
        self.assertNotIn("tt0000100", viri._zapisi)
        with open(self.datoteka, encoding="utf-8") as d:
            self.assertEqual(len(d.read().splitlines()), len(viri._zapisi))


if __name__ == "__main__":
    unittest.main()
