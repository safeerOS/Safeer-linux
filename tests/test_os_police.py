"""Osebne police Medijskega centra (core/os_police.py, core/os_knjiznica.py, core/os_katalog.py): stevci predvajanj,
priljubljene, ogledano, naslednja epizoda in katere police se pokazejo na katerem zavihku."""
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from core import os_katalog as K
from core import os_knjiznica as KN
from core import os_police as P

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Pravila(unittest.TestCase):
    def test_kljuc_vnosa(self):
        self.assertEqual(P.kljuc_vnosa({"id": "x", "vrsta": "serija", "tmdb_id": 1399, "sezona": 2, "epizoda": 5}), "tmdb:tv:1399:2:5")
        self.assertEqual(P.kljuc_vnosa({"id": "x", "vrsta": "serija", "tmdb_id": "1399"}), "tmdb:tv:1399")
        self.assertEqual(P.kljuc_vnosa({"id": "x", "vrsta": "film", "tmdb_id": 603}), "tmdb:film:603")
        self.assertEqual(P.kljuc_vnosa({"id": "r1", "vrsta": "radio"}), "id:r1")
        self.assertEqual(P.kljuc_vnosa({"vrsta": "radio"}), "")
        self.assertEqual(P.kljuc_vnosa(None), "")

    def test_kljuc_v_strani_je_enak(self):
        """assets/os/os.js (kljucVnosa) mora dati iste kljuce kot jedro, sicer srcek na kartici ne bi ustrezal polici."""
        with open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8") as f:
            js = f.read()
        telo = js.split("function kljucVnosa(x) {", 1)[1].split("\n  }\n", 1)[0]
        for niz in ('"tmdb:tv:" + tmdb + ":" + s + ":" + e', '"tmdb:tv:" + tmdb', '"tmdb:film:" + tmdb', '"id:" + x.id'):
            self.assertIn(niz, telo)

    def test_prag_stetja(self):
        self.assertEqual(P.prag_stetja(0), 30)             # prenos v zivo: po 30 s
        self.assertEqual(P.prag_stetja(3600), 30)          # film: po 30 s
        self.assertEqual(P.prag_stetja(40), 20)            # kratka skladba: po polovici
        self.assertEqual(P.prag_stetja(None), 30)

    def test_ogledano_pri_90_odstotkih(self):
        self.assertFalse(P.je_ogledano(5399, 6000))
        self.assertTrue(P.je_ogledano(5400, 6000))
        self.assertFalse(P.je_ogledano(100, 0))           # brez dolzine (tok) ni nikoli ogledano

    def test_opis_je_ociscen(self):
        o = P.cisti_opis({"naslov": "A\nB", "slika": "javascript:alert(1)", "url": "file:///etc/passwd", "tmdb_id": "12",
                          "zlo": "x", "id": "i" * 5000})
        self.assertEqual(o["naslov"], "A B")
        self.assertNotIn("slika", o)
        self.assertNotIn("url", o)
        self.assertNotIn("zlo", o)
        self.assertEqual(o["tmdb_id"], 12)
        self.assertEqual(len(o["id"]), 2048)
        # Ozadje (Domov) samo s spletnim ali krajevnim naslovom, vir je besedilo, zvrst stevilka.
        o = P.cisti_opis({"ozadje": "javascript:x", "vir": "Vir\n1", "zanr": "878"})
        self.assertEqual((o.get("ozadje"), o["vir"], o["zanr"]), (None, "Vir 1", 878))
        self.assertEqual(P.cisti_opis({"ozadje": "https://s.test/o.jpg"})["ozadje"], "https://s.test/o.jpg")


class Epizode(unittest.TestCase):
    def test_razclenitev_imena(self):
        self.assertEqual(P.epizoda_datoteke("/m/Moja.Serija.S01E02.1080p.mkv"), ("moja serija", 1, 2))
        self.assertEqual(P.epizoda_datoteke("/m/Moja Serija 2x10.mp4"), ("moja serija", 2, 10))
        # Leto v imenu ne loci serije.
        self.assertEqual(P.epizoda_datoteke("/m/Moja.Serija.2019.S01E03.mkv")[0], "moja serija")
        # Brez imena pred oznako: ime mape; mapa »Season 2« pove le sezono, serija je mapa nad njo.
        self.assertEqual(P.epizoda_datoteke("/m/Čarovnik/Season 2/S02E01.mkv"), ("carovnik", 2, 1))
        self.assertEqual(P.epizoda_datoteke("/m/Carovnik/S02E01.mkv"), ("carovnik", 2, 1))
        self.assertIsNone(P.epizoda_datoteke("/m/Film 2020.mkv"))

    def test_naslednja_lokalna_po_vrsti_in_prek_sezone(self):
        poti = ["/s/Serija S02E01.mkv", "/s/Serija S01E10.mkv", "/s/Serija S01E02.mkv", "/s/Serija S01E01.mkv",
                "/s/Druga S01E03.mkv", "/s/Serija S01E09.mkv"]
        self.assertEqual(P.naslednja_lokalna("/s/Serija S01E01.mkv", poti), "/s/Serija S01E02.mkv")
        self.assertEqual(P.naslednja_lokalna("/s/Serija S01E02.mkv", poti), "/s/Serija S01E09.mkv")   # manjkajoce preskoci
        self.assertEqual(P.naslednja_lokalna("/s/Serija S01E10.mkv", poti), "/s/Serija S02E01.mkv")   # nova sezona
        self.assertIsNone(P.naslednja_lokalna("/s/Serija S02E01.mkv", poti))                          # zadnja
        self.assertIsNone(P.naslednja_lokalna("/s/Druga S01E03.mkv", poti))                            # druga serija
        # E10 je za E9 (stevilsko, ne po abecedi).
        self.assertEqual(P.naslednja_lokalna("/s/Serija S01E09.mkv", poti), "/s/Serija S01E10.mkv")

    def test_naslednje_lokalne_za_polico(self):
        zdaj = 2_000_000_000
        vrstice = [
            {"pot": "/s/A S01E01.mkv", "ogledano": zdaj - 100, "pozicija": 0},
            {"pot": "/s/A S01E02.mkv", "ogledano": 0, "pozicija": 0},
            {"pot": "/s/B S01E01.mkv", "ogledano": zdaj - 50, "pozicija": 0},
            {"pot": "/s/B S01E02.mkv", "ogledano": 0, "pozicija": 600},     # ze »Nadaljuj«: ni naslednja
            {"pot": "/s/C S01E05.mkv", "ogledano": zdaj - 200 * 86400, "pozicija": 0},
            {"pot": "/s/C S01E06.mkv", "ogledano": 0, "pozicija": 0},       # serija pred vec kot 180 dnevi
            {"pot": "/s/D S01E01.mkv", "ogledano": zdaj - 10, "pozicija": 0},
            {"pot": "/s/D S01E02.mkv", "ogledano": zdaj - 5, "pozicija": 0},  # vse ogledano: nic
            {"pot": "/s/E S01E01.mkv", "ogledano": 0, "pozicija": 0},       # se ni gledana: nic
        ]
        izid = P.naslednje_lokalne(vrstice, zdaj)
        self.assertEqual([(v["pot"], cas) for v, cas in izid], [("/s/A S01E02.mkv", zdaj - 100)])

    def test_naslednja_v_katalogu(self):
        sezone = {1: 10, 2: 8, 3: 0}
        epizod = lambda s: sezone.get(s, 0)
        self.assertEqual(P.naslednja_kataloga(1, 3, epizod), (1, 4))
        self.assertEqual(P.naslednja_kataloga(1, 10, epizod), (2, 1))   # konec sezone -> nova sezona
        self.assertIsNone(P.naslednja_kataloga(2, 8, epizod))           # 3. sezona se ni izsla
        self.assertIsNone(P.naslednja_kataloga(0, 0, epizod))
        self.assertEqual(P.razcleni_kljuc_epizode("tmdb:tv:1399:2:5"), (1399, 2, 5))
        self.assertIsNone(P.razcleni_kljuc_epizode("tmdb:tv:1399"))


class Shramba(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.p = P.Police(self.mapa.name)

    def test_priljubljene_vklop_izklop_in_obstojnost(self):
        self.assertTrue(self.p.nastavi_priljubljeno("id:r1", True, {"naslov": "Radio Ena", "vrsta": "radio"}))
        self.assertTrue(self.p.nastavi_priljubljeno("pot:/m/film.mkv", True))
        self.assertFalse(self.p.nastavi_priljubljeno("zlo:x", True))           # neznana vrsta kljuca
        drugi = P.Police(self.mapa.name)                                       # nov zagon prebere isto datoteko
        self.assertEqual(set(drugi.kljuci_priljubljenih()), {"id:r1", "pot:/m/film.mkv"})
        self.assertTrue(drugi.je_priljubljena("id:r1"))
        self.assertFalse(drugi.nastavi_priljubljeno("id:r1", False))
        self.assertEqual(P.Police(self.mapa.name).kljuci_priljubljenih(), ["pot:/m/film.mkv"])
        # Atomaren zapis ne pusti zacasnih datotek.
        self.assertEqual(sorted(os.listdir(self.mapa.name)), ["priljubljene.json"])

    def test_priljubljenih_je_omejeno(self):
        for i in range(P.NAJVEC_PRILJUBLJENIH + 20):
            seznam = [{"k": "id:%d" % j, "t": j, "m": {}} for j in range(i + 1)]
        Path(self.mapa.name, "priljubljene.json").write_text(json.dumps({"v": seznam}))
        self.p.nastavi_priljubljeno("id:novo", True)
        kljuci = self.p.kljuci_priljubljenih()
        self.assertEqual(len(kljuci), P.NAJVEC_PRILJUBLJENIH)
        self.assertEqual(kljuci[0], "id:novo")

    def test_pokvarjena_datoteka_ni_napaka(self):
        Path(self.mapa.name, "priljubljene.json").write_text("{pokvarjeno")
        Path(self.mapa.name, "ogledano.json").write_text("[1, 2]")
        self.assertEqual(self.p.priljubljene(), [])
        self.assertEqual(self.p.ogledano(), {})

    def test_stevec_in_meja(self):
        self.assertEqual(self.p.stej("id:a", {"naslov": "A"}), 1)
        self.assertEqual(self.p.stej("id:a"), 2)
        self.assertEqual(self.p.opis("id:a")["naslov"], "A")
        d = {"id:%d" % i: {"n": 1, "t": i, "m": {}} for i in range(P.NAJVEC_PREDVAJANJ + 5)}
        Path(self.mapa.name, "predvajanja.json").write_text(json.dumps(d))
        self.p.stej("id:zadnji")
        vse = self.p.predvajanja()
        self.assertEqual(len(vse), P.NAJVEC_PREDVAJANJ)
        self.assertIn("id:zadnji", vse)
        self.assertNotIn("id:0", vse)                       # najstarejsi izpade

    def test_ogledano(self):
        self.assertTrue(self.p.nastavi_ogledano("tmdb:tv:1:1:1", True))
        self.assertIn("tmdb:tv:1:1:1", self.p.ogledano())
        self.assertFalse(self.p.nastavi_ogledano("tmdb:tv:1:1:1", False))
        self.assertNotIn("tmdb:tv:1:1:1", self.p.ogledano())


class Vidnost(unittest.TestCase):
    def test_police_zavihkov(self):
        self.assertEqual(P.POLICE_ZAVIHKOV["radio"], ("priljubljene", "najvec"))
        self.assertEqual(P.POLICE_ZAVIHKOV["filmi"], ("nadaljuj", "nazadnje", "priljubljene"))
        self.assertEqual(P.POLICE_ZAVIHKOV["glasba"], ("nadaljuj", "najvec", "nazadnje", "priljubljene"))
        self.assertNotIn("vse", P.POLICE_ZAVIHKOV)          # iskanje nima polic
        # Domov: vse osebne police in nazadnje predvajana glasba; slike imajo svoj zavihek.
        self.assertEqual(P.POLICE_ZAVIHKOV["domov"], ("nadaljuj", "nazadnje", "glasba", "najvec", "priljubljene"))
        self.assertNotIn("slike", P.VRSTE_ZAVIHKA["domov"])
        self.assertTrue({"film", "serija", "glasba", "radio", "tv-v-zivo"} <= P.VRSTE_ZAVIHKA["domov"])

    def test_domov_prazne_police_izpadejo(self):
        viri = {"nadaljuj": [], "nazadnje": [{"kljuc": "pot:/a.mkv", "vrsta": "filmi"}, {"kljuc": "pot:/b.jpg", "vrsta": "slike"}],
                "glasba": [], "najvec": [], "priljubljene": []}
        self.assertEqual(P.sestavi_police("domov", viri), [{"id": "nazadnje", "vnosi": [{"kljuc": "pot:/a.mkv", "vrsta": "filmi"}]}])
        self.assertEqual(P.sestavi_police("domov", {}), [])

    def test_prazne_police_izpadejo_in_vrste_se_filtrirajo(self):
        viri = {"priljubljene": [{"kljuc": "id:f", "vrsta": "film"}, {"kljuc": "id:r", "vrsta": "radio"}],
                "najvec": [], "nadaljuj": [{"kljuc": "id:f", "vrsta": "film"}]}
        self.assertEqual(P.sestavi_police("radio", viri), [{"id": "priljubljene", "vnosi": [{"kljuc": "id:r", "vrsta": "radio"}]}])
        filmi = P.sestavi_police("filmi", viri)
        self.assertEqual([p["id"] for p in filmi], ["nadaljuj", "priljubljene"])
        self.assertEqual(P.sestavi_police("filmi", viri, iskanje="mat"), [])
        self.assertEqual(P.sestavi_police("vse", viri), [])
        self.assertEqual(P.sestavi_police("tv", viri), [])

    def test_brez_dvojnikov_in_najvec_dvajset(self):
        vnosi = [{"kljuc": "id:%d" % (i // 2), "vrsta": "radio"} for i in range(80)]
        polica = P.sestavi_police("radio", {"priljubljene": vnosi})[0]["vnosi"]
        self.assertEqual(len(polica), P.NA_POLICI)
        self.assertEqual(len({v["kljuc"] for v in polica}), P.NA_POLICI)


class Knjiznica(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.k = KN.Knjiznica(Path(self.mapa.name) / "m.sqlite3")
        self.film = self._datoteka("Film.mkv")
        self.pesem = self._datoteka("Pesem.mp3")
        self.k.dodaj([self.film, self.pesem])

    def _datoteka(self, ime):
        pot = Path(self.mapa.name) / ime
        pot.write_bytes(b"x")
        return str(pot.resolve())

    def test_film_steje_enkrat_na_sejo_po_30_s(self):
        self.k.predvajano(self.film)
        self.k.shrani_napredek(self.film, 10, 6000)
        self.assertEqual(self.k.dobi(self.film)["predvajanj"], 0)        # 10 s ni ogled
        self.k.shrani_napredek(self.film, 35, 6000)
        self.k.shrani_napredek(self.film, 40, 6000)
        self.assertEqual(self.k.dobi(self.film)["predvajanj"], 1)
        self.k.predvajano(self.film)                                        # nov zacetek
        self.k.shrani_napredek(self.film, 45, 6000)
        self.assertEqual(self.k.dobi(self.film)["predvajanj"], 2)

    def test_skladba_steje_ob_zacetku(self):
        self.k.predvajano(self.pesem)
        self.k.predvajano(self.pesem)
        self.assertEqual(self.k.dobi(self.pesem)["predvajanj"], 2)
        self.assertEqual([v["pot"] for v in self.k.najveckrat()], [self.pesem])

    def test_ogledano_pri_90_odstotkih_in_rocno(self):
        self.k.shrani_napredek(self.film, 3000, 6000)
        self.assertFalse(self.k.dobi(self.film)["ogledano"])
        self.assertEqual([v["pot"] for v in self.k.nedokoncane()], [self.film])
        self.k.shrani_napredek(self.film, 5500, 6000)
        self.assertTrue(self.k.dobi(self.film)["ogledano"])
        self.assertTrue(self.k.nastavi_ogledano(self.film, False))
        self.assertFalse(self.k.dobi(self.film)["ogledano"])
        self.k.shrani_napredek(self.film, 3000, 6000)
        self.assertTrue(self.k.nastavi_ogledano(self.film, True))
        self.assertEqual(self.k.dobi(self.film)["pozicija"], 0)          # ogledan zacne od zacetka
        self.assertFalse(self.k.nastavi_ogledano(self.pesem, True))      # skladba nima »ogledano«

    def test_stara_baza_dobi_nova_stolpca(self):
        import sqlite3
        pot = Path(self.mapa.name) / "stara.sqlite3"
        with sqlite3.connect(pot) as b:
            b.execute("""CREATE TABLE mediji (pot TEXT PRIMARY KEY, naslov TEXT NOT NULL, vrsta TEXT NOT NULL,
                dodano INTEGER NOT NULL DEFAULT 0, zadnjic INTEGER NOT NULL DEFAULT 0)""")
            b.execute("INSERT INTO mediji(pot, naslov, vrsta) VALUES (?, 'Film', 'filmi')", (self.film,))
        v = KN.Knjiznica(pot).dobi(self.film)
        self.assertEqual((v["predvajanj"], v["ogledano"], v["pozicija"]), (0, 0, 0))


class _Mc:
    """Namesto os_media.MediaCenter: vnosi kataloga in sezone TMDB."""

    def __init__(self, vnosi, sezone=None):
        self.vnosi, self.sezone, self.epizode = vnosi, sezone or {}, []

    def resolve(self, ident):
        return self.vnosi.get(ident)

    def season(self, tmdb, s):
        n = self.sezone.get(s, 0)
        return {"epizode": [{"stevilka": i + 1, "naslov": "Ep %d" % (i + 1), "datum": "2020-01-01", "slika": ""} for i in range(n)]}

    def episode_item(self, tmdb, s, e, naslov=""):
        self.epizode.append((tmdb, s, e, naslov))
        ident = "ep%d%d" % (s, e)
        self.vnosi[ident] = {"id": ident, "vrsta": "serija", "tmdb_id": tmdb, "sezona": s, "epizoda": e,
                             "naslov": naslov, "url": "https://tok.test/%s.mp4" % ident}
        return self.vnosi[ident]


class MostPolic(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.dogodki, self.predvajano = [], []
        self.lokalna = KN.Knjiznica(Path(self.mapa.name) / "m.sqlite3")
        self.k = K.Katalog(str(Path(self.mapa.name) / "media"), dogodek=lambda v, p: self.dogodki.append((v, p)),
                           v_glavni=lambda delo: delo(), predvajaj=lambda *a: self.predvajano.append(a) or True,
                           vdelano=lambda u: True, youtube=lambda u, n: True, youtube_ukaz=lambda u: True,
                           lokalna=self.lokalna)
        ep = lambda s, e: {"id": "s%d%d" % (s, e), "vrsta": "serija", "tmdb_id": 77, "sezona": s, "epizoda": e,
                           "naslov": "Serija · Ep %d" % e, "url": "https://tok.test/s%d%d.mp4" % (s, e)}
        self.k._mc = _Mc({"s11": ep(1, 1), "s13": ep(1, 3),
                          "r": {"id": "r", "vrsta": "radio", "naslov": "Radio", "url": "https://radio.test/tok.mp3"}},
                         sezone={1: 3, 2: 2})

    def _pocakaj(self, vrsta):
        for _ in range(100):
            if any(v == vrsta for v, _p in self.dogodki):
                return next(p for v, p in self.dogodki if v == vrsta)
            time.sleep(0.02)
        self.fail("ni dogodka " + vrsta)

    def test_radio_steje_po_30_s_enkrat(self):
        self.k.izvedi("mediaPredvajaj", ["r"])
        uri = "https://radio.test/tok.mp3"
        self.k.shrani_napredek(uri, 10, 0)
        self.assertEqual(self.k.police.predvajanja()["id:r"]["n"], 0)
        self.k.shrani_napredek(uri, 31, 0)
        self.k.shrani_napredek(uri, 60, 0)
        self.assertEqual(self.k.police.predvajanja()["id:r"]["n"], 1)
        self.k.izvedi("mediaPredvajaj", ["r"])
        self.k.shrani_napredek(uri, 31, 0)
        self.k.shrani_napredek(uri, 31, 0)
        self.k.shrani_napredek(uri, 31, 0)
        self.assertEqual(self.k.police.predvajanja()["id:r"]["n"], 2)
        police = self.k.izvedi("mediaPolice", ["radio", ""])
        self.assertEqual([p["id"] for p in police["police"]], ["najvec"])
        self.assertEqual(police["police"][0]["vnosi"][0]["kljuc"], "id:r")

    def test_epizoda_pri_90_odstotkih_ogledana_in_naslednja_prek_sezone(self):
        self.k.izvedi("mediaPredvajaj", ["s13"])
        uri = "https://tok.test/s13.mp4"
        self.k.shrani_napredek(uri, 2200, 2400)
        self.assertIn("tmdb:tv:77:1:3", self.k.police.ogledano())
        self.k.konec(uri)
        ponudba = self._pocakaj("mediaNaslednja")
        self.assertEqual((ponudba["kljuc"], ponudba["naslov"], ponudba["podnaslov"]), ("tmdb:tv:77:2:1", "Serija", "S02E01 · Ep 1"))
        # Ponudbo porabi samo prvi pogled (drugo okno je ne zacne se enkrat).
        izid = self.k.izvedi("mediaNaslednjaPredvajaj", [ponudba["zeton"]])
        self.assertTrue(izid["native"])
        self.assertEqual(self.k._mc.epizode[-1][:3], (77, 2, 1))
        self.assertIsNone(self.k.izvedi("mediaNaslednjaPredvajaj", [ponudba["zeton"]]))
        self.assertIn(("mediaNaslednjaKonec", {"zeton": ponudba["zeton"]}), self.dogodki)

    def test_nadaljuj_in_naslednja_na_polici_serij(self):
        self.k.izvedi("mediaPredvajaj", ["s11"])
        self.k.shrani_napredek("https://tok.test/s11.mp4", 2300, 2400)     # ogledana
        police = self.k.izvedi("mediaPolice", ["serije", ""])
        nadaljuj = police["police"][0]
        self.assertEqual(nadaljuj["id"], "nadaljuj")
        self.assertEqual(nadaljuj["vnosi"][0]["kljuc"], "tmdb:tv:77:1:2")
        self.assertTrue(nadaljuj["vnosi"][0]["naslednja"])
        self.assertIn("tmdb:tv:77:1:1", police["ogledano"])
        # Nedokoncana epizoda iste serije je »Nadaljuj«, naslednje za to serijo ni.
        self.k.izvedi("mediaPredvajaj", ["s13"])
        self.k.shrani_napredek("https://tok.test/s13.mp4", 600, 2400)
        vnosi = self.k.izvedi("mediaPolice", ["serije", ""])["police"][0]["vnosi"]
        self.assertEqual([(v["kljuc"], v.get("naslednja", False)) for v in vnosi], [("tmdb:tv:77:1:3", False)])
        self.assertEqual(vnosi[0]["pozicija"], 600)
        # Na zavihku Radio ni polic serij; med iskanjem ni polic.
        self.assertEqual(self.k.izvedi("mediaPolice", ["radio", ""])["police"], [])
        self.assertEqual(self.k.izvedi("mediaPolice", ["serije", "abc"])["police"], [])

    def test_rocno_ogledano_pozabi_mesto(self):
        self.k.izvedi("mediaPredvajaj", ["s13"])
        self.k.shrani_napredek("https://tok.test/s13.mp4", 600, 2400)
        self.assertEqual(self.k.napredek_za("s13"), 600)
        self.assertEqual(self.k.izvedi("mediaOgledano", ["tmdb:tv:77:1:3", True]), {"ok": True, "ogledano": True})
        self.assertEqual(self.k.napredek_za("s13"), 0)
        self.assertEqual(self.k.izvedi("mediaOgledano", ["tmdb:tv:77:1:3", False]), {"ok": True, "ogledano": False})
        self.assertFalse(self.k.izvedi("mediaOgledano", ["tok:https://x", True])["ok"])

    def test_priljubljene_vseh_vrst(self):
        film = Path(self.mapa.name) / "Film.mkv"
        film.write_bytes(b"x")
        self.lokalna.dodaj([film])
        self.lokalna.dodaj_tok("Moja postaja", "https://radio.test/moja", "radio")
        pot = str(film.resolve())
        self.assertTrue(self.k.izvedi("mediaPriljubljena", ["pot:" + pot, True, {}]))
        self.assertFalse(self.k.izvedi("mediaPriljubljena", ["pot:/ni/v/knjiznici.mkv", True, {}]))
        self.assertTrue(self.k.izvedi("mediaPriljubljena", ["tok:https://radio.test/moja", True, {}]))
        self.assertTrue(self.k.izvedi("mediaPriljubljena", ["id:r", True, {"naslov": "Radio", "vrsta": "radio"}]))
        stanje = self.k.izvedi("mediaPolice", ["radio", ""])
        self.assertEqual(set(stanje["priljubljene"]), {"pot:" + pot, "tok:https://radio.test/moja", "id:r"})
        polica = stanje["police"][0]
        self.assertEqual(polica["id"], "priljubljene")
        self.assertEqual({v["kljuc"]: v["tip"] for v in polica["vnosi"]}, {"tok:https://radio.test/moja": "tok", "id:r": "katalog"})
        filmi = self.k.izvedi("mediaPolice", ["filmi", ""])["police"]
        self.assertEqual(filmi[-1]["vnosi"][0]["kljuc"], "pot:" + pot)
        # Odstranjena postaja ni vec na polici.
        self.lokalna.odstrani_tok("https://radio.test/moja")
        vnosi = self.k.izvedi("mediaPolice", ["radio", ""])["police"][0]["vnosi"]
        self.assertEqual([v["kljuc"] for v in vnosi], ["id:r"])
        self.assertFalse(self.k.izvedi("mediaPriljubljena", ["id:r", False]))

    def test_predvajana_postaja_iz_knjiznice_steje(self):
        self.lokalna.dodaj_tok("Moja postaja", "https://radio.test/moja", "radio")
        self.assertEqual(self.k.izvedi("mediaPredvajanTok", ["https://radio.test/moja"]), 1)
        self.assertEqual(self.k.izvedi("mediaPredvajanTok", ["https://radio.test/ni"]), 0)

    def test_krajevna_epizoda_ponudi_naslednjo_in_ni_dvojnega_predvajanja(self):
        mapa = Path(self.mapa.name) / "Serija"
        mapa.mkdir()
        poti = []
        for ime in ("Serija S01E01.mkv", "Serija S01E02.mkv", "Serija S02E01.mkv"):
            (mapa / ime).write_bytes(b"x")
            poti.append(str((mapa / ime).resolve()))
        self.lokalna.dodaj(poti)
        glavna, niti = threading.get_ident(), []
        epizode = self.lokalna.epizode
        self.lokalna.epizode = lambda *a: niti.append(threading.get_ident()) or epizode(*a)
        self.k.konec((mapa / "Serija S01E02.mkv").resolve().as_uri())
        ponudba = self._pocakaj("mediaNaslednja")
        # Branje knjiznice (do 5000 epizod, preverba datotek na NAS) ni na glavni niti (pregled 14. 10. 2026).
        self.assertTrue(niti and glavna not in niti)
        self.assertTrue(self.lokalna.dobi(poti[1])["ogledano"])
        self.assertEqual((ponudba["tip"], ponudba["pot"]), ("lokalno", poti[2]))
        # Uporabnik je medtem sam izbral drugo vsebino: ponudba ne zacne nicesar.
        self.k.izvedi("mediaPredvajaj", ["r"])
        self.assertIsNone(self.k.izvedi("mediaNaslednjaPredvajaj", [ponudba["zeton"]]))
        # Polica Serije: naslednja epizoda po ogledani (prek sezone).
        vnosi = self.k.izvedi("mediaPolice", ["serije", ""])["police"][0]["vnosi"]
        self.assertEqual([(v["pot"], v["naslednja"]) for v in vnosi], [(poti[2], True)])

    def test_nazadnje_dodana_glasba_po_albumih(self):
        album = Path(self.mapa.name) / "Album"
        album.mkdir()
        poti = []
        for ime in ("01 A.mp3", "02 B.mp3"):
            (album / ime).write_bytes(b"x")
            poti.append(str((album / ime).resolve()))
        self.lokalna.dodaj(poti)
        vnosi = self.k.izvedi("mediaPolice", ["glasba", ""])["police"][0]["vnosi"]
        self.assertEqual(len(vnosi), 1)
        self.assertEqual((vnosi[0]["naslov"], vnosi[0]["album"]), ("Album", True))

    # ---- Domov (lastnik, 14. 10. 2026): zacetna stran Medijskega centra
    def test_domov_brez_vsebine_nima_polic(self):
        self.assertEqual(self.k.izvedi("mediaPolice", ["domov", ""])["police"], [])

    def test_domov_nazadnje_predvajana_glasba_po_albumih_in_iz_kataloga(self):
        album = Path(self.mapa.name) / "Album"
        album.mkdir()
        poti = []
        for ime in ("01 A.mp3", "02 B.mp3"):
            (album / ime).write_bytes(b"x")
            poti.append(str((album / ime).resolve()))
        self.lokalna.dodaj(poti)
        self.lokalna.predvajano(poti[0])
        self.lokalna.predvajano(poti[1])
        self.k.police.zapomni("id:g1", {"id": "g1", "naslov": "Skladba iz kataloga", "vrsta": "glasba", "izvajalec": "Izvajalec"})
        self.k.police.zapomni("id:f1", {"id": "f1", "naslov": "Film", "vrsta": "film"})
        police = {p["id"]: p["vnosi"] for p in self.k.izvedi("mediaPolice", ["domov", ""])["police"]}
        glasba = police["glasba"]
        # Album z dvema predvajanima skladbama je ena kartica; film ni na polici glasbe.
        self.assertEqual(sorted(v["naslov"] for v in glasba), ["Album", "Skladba iz kataloga"])
        self.assertEqual([v for v in glasba if v["naslov"] == "Album"][0]["album"], True)
        # Na Domov so tudi nazadnje dodane datoteke (vse vrste razen slik).
        self.assertIn("nazadnje", police)

    def test_domov_opis_hrani_vir_ozadje_in_zvrst(self):
        self.k._mc.vnosi["fx"] = {"id": "fx", "vrsta": "film", "naslov": "Film X", "tmdb_id": 9, "leto": 2016, "vir": "Vir 1",
                                  "zanri": [878, 18], "ozadje": "https://slike.test/o.jpg", "url": "https://tok.test/fx.mp4"}
        self.k.izvedi("mediaPredvajaj", ["fx"])
        opis = self.k.police.opis("tmdb:film:9")
        self.assertEqual((opis["vir"], opis["ozadje"], opis["zanr"], opis["leto"]), ("Vir 1", "https://slike.test/o.jpg", 878, 2016))
        vnos = K.Katalog._vnos_opisa("tmdb:film:9", opis, {})
        for polje in ("vir", "ozadje", "zanr", "leto"):
            self.assertIn(polje, vnos)


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class Vmesnik(unittest.TestCase):
    """assets/os: police, meni kartice in ponudba naslednje epizode."""

    def setUp(self):
        self.js, self.html, self.css = _beri("assets", "os", "os.js"), _beri("assets", "os", "index.html"), _beri("assets", "os", "katalog.css")

    def test_kljuc_v_strani_izracunan_enako(self):
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("node ni namescen")
        telo = "function kljucVnosa(x) {" + self.js.split("function kljucVnosa(x) {", 1)[1].split("\n  }\n", 1)[0] + "\n}"
        vzorci = [{"id": "x", "vrsta": "serija", "tmdb_id": 1399, "sezona": 2, "epizoda": 5}, {"id": "x", "vrsta": "serija", "tmdb_id": 1399},
                  {"id": "x", "vrsta": "film", "tmdb_id": "603"}, {"id": "r1", "vrsta": "radio"}, {"vrsta": "radio"},
                  {"id": "y" * 600, "vrsta": "glasba"}]
        izid = subprocess.run(["node", "-e", telo + "\nconsole.log(JSON.stringify(%s.map(kljucVnosa)));" % json.dumps(vzorci)],
                              capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(izid), [P.kljuc_vnosa(v) for v in vzorci])

    def test_polica_skrita_brez_vsebine(self):
        telo = self.js.split("function narisiPolice() {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("c.hidden = !police.length;", telo)
        self.assertIn('<div class="media-police media-domov-del" id="mediaPolice" hidden></div>', self.html)
        self.assertIn(".media-police[hidden]", self.css)
        self.assertIn('klic("mediaPolice", [S.mediaFilter, S.mediaIskanje])', self.js)
        self.assertIn("if (!veckrat) naloziPolice();", self.js)

    def test_meni_kartice_s_tipkovnico_in_daljincem(self):
        self.assertIn('id="mediaKarticaMeni" role="menu" hidden', self.html)
        for niz in ('card.addEventListener("contextmenu"', 'e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")',
                    'e.key === "ArrowDown" || e.key === "ArrowUp"', 'b.setAttribute("role", "menuitem")',
                    'zapriMeniKartice(true)'):
            self.assertIn(niz, self.js)
        # Igralni plosek: Y odpre meni izbrane kartice.
        self.assertIn('gumbPloska("meni", g(3)', _beri("assets", "os", "kavc.js"))
        # Podrobnosti: prava gumba s stanjem.
        self.assertIn('srce.setAttribute("aria-pressed"', self.js)
        self.assertIn('og.setAttribute("aria-pressed"', self.js)

    def test_naslednja_epizoda_porabi_zeton(self):
        self.assertIn('id="naslEpPlosca" role="dialog"', self.html)
        self.assertIn('odpriKatalogVnos(null, ["mediaNaslednjaPredvajaj", [p.zeton], true]);', self.js)
        self.assertIn('klic("mediaNaslednjaPreklici", [p.zeton])', self.js)
        self.assertIn("@media (prefers-reduced-motion: reduce) { .media-naslednja { animation: none; }", self.css)

    def test_besedila_v_vseh_jezikih(self):
        bes = _beri("assets", "os", "besedila.js")
        for kljuc in ("policaNadaljujGledanje", "policaNadaljujPoslusanje", "policaNazadnje", "policaNajvec", "policaPriljubljene",
                      "policaPriljubljena", "policaNaslednja", "policaPredvajano", "priljubljenaDodaj", "priljubljenaOdstrani",
                      "priljubljenaDodano", "priljubljenaOdstranjeno", "ogledanoOznaci", "ogledanoOdznaci", "ogledanoOznaka",
                      "karticaMeni", "naslednjaNaslov", "naslednjaZdaj", "naslednjaNeZdaj", "naslednjaCez", "policaOstane"):
            self.assertEqual(bes.count('"%s":' % kljuc), 6, kljuc)
            self.assertIn(kljuc, self.js + self.html)

    def test_barve_iz_enega_vira(self):
        nove = self.css.split("/* Osebne police", 1)[1]
        # Nove barve so spremenljivke v os.css :root (--media-znacka, --media-merilo), ne trdo kodirane tu.
        self.assertNotRegex(nove, r"rgba?\(|#[0-9a-fA-F]{3,6}\b")
        self.assertIn("--media-znacka:", _beri("assets", "os", "tokens.css"))


if __name__ == "__main__":
    unittest.main()
