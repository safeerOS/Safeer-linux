"""Police odkrivanja na Domov Medijskega centra (lastnik, 17. 10. 2026: »Domov deluje zelo prazno in neprijetno«).

Pravila (core/os_police.sestavi_odkrivanje): ista vsebina samo enkrat (tudi ce jo ponudita dva vira), nikoli zasebni
dodatki, prazne police izpadejo. Most (core/os_katalog.Katalog._odkrivanje): katalog iz predpomnilnika takoj, pocasni
viri (Twitch, racuni) pridejo z dogodkom - Domov se ne caka. Brez okna in brez omrezja."""
import os
import re
import tempfile
import threading
import time
import unittest

from core import os_katalog, os_police

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(*pot):
    with open(os.path.join(KOREN, *pot), encoding="utf-8") as f:
        return f.read()


def film(i, naslov=None, **kw):
    return dict({"id": "tmdb:film:%d" % i, "tmdb_id": i, "vrsta": "film", "naslov": naslov or "Film %d" % i,
                 "slika": "https://image.tmdb.org/p/%d.jpg" % i}, **kw)


class SestaviOdkrivanje(unittest.TestCase):

    def test_ista_vsebina_samo_enkrat(self):
        viri = {
            "odkrij_filmi": [film(1), film(2), film(1)],
            # isti film iz drugega dodatka (drug id, brez TMDB) in isti TMDB na drugi polici: oboje izpade
            "odkrij_serije": [{"id": "stremio:x:tt1", "vrsta": "film", "naslov": "Film 2"}, film(1),
                              {"id": "tmdb:tv:9", "tmdb_id": 9, "vrsta": "serija", "naslov": "Serija"}],
        }
        police = os_police.sestavi_odkrivanje(viri)
        kljuci = [v["kljuc"] for p in police for v in p["vnosi"]]
        self.assertEqual(len(kljuci), len(set(kljuci)))
        self.assertEqual([v["naslov"] for v in police[0]["vnosi"]], ["Film 1", "Film 2"])
        self.assertEqual([v["naslov"] for v in police[1]["vnosi"]], ["Serija"])

    def test_brez_zasebnih_in_brez_osebnih(self):
        viri = {"odkrij_filmi": [film(1), film(2, id="stremio:zasebni:2"), film(3)]}
        police = os_police.sestavi_odkrivanje(viri, izkljuci=["tmdb:film:3"],
                                              zaseben=lambda d: str(d.get("id")).startswith("stremio:zasebni:"))
        self.assertEqual([v["naslov"] for v in police[0]["vnosi"]], ["Film 1"])

    def test_dvom_o_zasebnosti_izloci(self):
        def pokvarjena(_d):
            raise RuntimeError("baza zaklenjena")
        self.assertEqual(os_police.sestavi_odkrivanje({"odkrij_filmi": [film(1)]}, zaseben=pokvarjena), [])

    def test_prazne_izpadejo_in_vrstni_red(self):
        viri = {"odkrij_radio": [{"id": "radio:1", "vrsta": "radio", "naslov": "Val 202"}], "odkrij_filmi": [],
                "odkrij_twitch": [{"naslov": ""}, "smeti", None]}
        police = os_police.sestavi_odkrivanje(viri)
        self.assertEqual([(p["id"], p["zavihek"]) for p in police], [("odkrij_radio", "radio")])

    def test_najvec_na_polici_in_seznami_racunov(self):
        viri = {"odkrij_filmi": [film(i) for i in range(1, 60)],
                "odkrij_youtube": [{"tip": "yt-seznam", "id": "LL", "posebni": "LL", "naslov": "LL", "racun": 1},
                                   {"tip": "yt-seznam", "id": "LL", "posebni": "LL", "naslov": "LL", "racun": 1}],
                "odkrij_spotify": [{"tip": "sp-seznam", "id": "abc", "naslov": "Moj seznam"}]}
        police = {p["id"]: p for p in os_police.sestavi_odkrivanje(viri)}
        self.assertEqual(len(police["odkrij_filmi"]["vnosi"]), os_police.NA_POLICI_ODKRIVANJA)
        self.assertEqual([v["kljuc"] for v in police["odkrij_youtube"]["vnosi"]], ["yt:1:LL"])
        self.assertEqual(police["odkrij_spotify"]["vnosi"][0]["tip"], "sp-seznam")
        # kartica nosi samo, kar potrebujeta prikaz in obstojeci klik (odpriKatalogPodrobnosti, odpriTwitchKanal)
        self.assertNotIn("razlicice", os_police.kartica_odkrivanja(dict(film(1), razlicice=[{"url": "x"}])))


class _LazniMc:
    """Katalog iz predpomnilnika (takoj), Twitch pocasen (omrezje)."""

    def __init__(self, twitch_cakaj=0.0):
        self.izbrana_drzava = ""
        self.twitch_cakaj = twitch_cakaj
        self.klici = []
        self.spotify = type("Sp", (), {"stanje": lambda s: {"prijavljen": False}})()

    def catalog_hitro(self, query, kind, genre, page, ob_osvezitvi=None, **kw):
        self.klici.append((kind, kw.get("drzava_radia", "")))
        vnosi = {"film": [film(1), film(2)], "serija": [{"id": "tmdb:tv:5", "tmdb_id": 5, "vrsta": "serija", "naslov": "S"}],
                 "glasba": [], "radio": [{"id": "radio:1", "vrsta": "radio", "naslov": "Val 202"}]}[kind]
        return {"vnosi": vnosi, "iz_predpomnilnika": True}

    def brez_nerazpolozljivih(self, r):
        return r

    def twitch_katalog(self, q, k):
        time.sleep(self.twitch_cakaj)
        return {"vnosi": [{"id": "twitch:abc", "vrsta": "twitch", "naslov": "Prenos", "login": "abc"}]}

    def yt_stanje(self):
        return {"prijavljen": False}


class MostOdkrivanja(unittest.TestCase):

    def _katalog(self, mc):
        dogodki, prispelo = [], threading.Event()
        k = os_katalog.Katalog(tempfile.mkdtemp(), dogodek=lambda v, p: (dogodki.append((v, p)), prispelo.set()),
                               v_glavni=lambda f: f(), predvajaj=lambda *a: True, vdelano=lambda u: True,
                               youtube=lambda u, n: True, youtube_ukaz=lambda u: True)
        k._mc = mc
        k._je_zaseben_opis = lambda: (lambda d: str(d.get("id") or "").startswith("stremio:zasebni:"))
        return k, dogodki, prispelo

    def test_domov_takoj_pocasni_viri_z_dogodkom(self):
        mc = _LazniMc(twitch_cakaj=0.6)
        k, dogodki, prispelo = self._katalog(mc)
        zacetek = time.monotonic()
        r = k.izvedi("mediaOdkrivanje", ["SI", []])
        trajanje = time.monotonic() - zacetek
        # Meritev (17. 10. 2026, ta racunalnik): iz predpomnilnika ~0,15 s (rok cakanja), cilj < 300 ms.
        print("\n[meritev] mediaOdkrivanje iz predpomnilnika: %.0f ms" % (trajanje * 1000))
        self.assertLess(trajanje, 0.3)
        self.assertTrue(r["dopolnjujem"])
        self.assertEqual([p["id"] for p in r["police"]], ["odkrij_filmi", "odkrij_serije", "odkrij_radio"])
        self.assertTrue(prispelo.wait(3))
        vrsta, podatki = dogodki[-1]
        self.assertEqual(vrsta, "mediaOdkrivanje")
        self.assertIn("odkrij_twitch", [p["id"] for p in podatki["police"]])
        self.assertIn(("radio", "SI"), mc.klici)          # radio izbrane drzave (izbira na zavihku Radio)

    def test_drugic_iz_pomnilnika_brez_dvojnega_dogodka(self):
        mc = _LazniMc()
        k, dogodki, prispelo = self._katalog(mc)
        k.izvedi("mediaOdkrivanje", ["", []])
        time.sleep(0.3)
        n = len(dogodki)
        r = k.izvedi("mediaOdkrivanje", ["", ["tmdb:film:1"]])
        time.sleep(0.3)
        self.assertIn("odkrij_twitch", [p["id"] for p in r["police"]])       # Twitch iz pomnilnika (3 min)
        self.assertNotIn("Film 1", [v["naslov"] for p in r["police"] for v in p["vnosi"]])   # ze na osebni polici
        self.assertLessEqual(len(dogodki) - n, 1)

    def test_zasebno_nikoli(self):
        mc = _LazniMc()
        mc.catalog_hitro = lambda *a, **kw: {"vnosi": [film(7, id="stremio:zasebni:7"), film(8)]}
        k, _d, _p = self._katalog(mc)
        r = k.izvedi("mediaOdkrivanje", ["", []])
        time.sleep(0.2)
        naslovi = [v["naslov"] for p in k._odkrij_sestavi() + r["police"] for v in p["vnosi"]]
        self.assertNotIn("Film 7", naslovi)
        self.assertIn("Film 8", naslovi)

    def test_vir_z_napako_ne_podre_ostalih(self):
        mc = _LazniMc()
        mc.twitch_katalog = lambda q, k: (_ for _ in ()).throw(OSError("brez omrezja"))
        k, _d, _p = self._katalog(mc)
        r = k.izvedi("mediaOdkrivanje", ["", []])
        self.assertIn("odkrij_filmi", [p["id"] for p in r["police"]])


class Stran(unittest.TestCase):
    """Stran: police odkrivanja pod osebnimi, »Vse →«, obstojece poti klika, prevodi."""

    def test_stran(self):
        js, html = _beri("assets", "os", "os.js"), _beri("assets", "os", "index.html")
        self.assertIn('id="mediaOdkrivanje"', html)
        self.assertLess(html.index('id="mediaPolice"'), html.index('id="mediaOdkrivanje"'))
        self.assertIn('klic("mediaOdkrivanje", [kat.drzavaRadia || "", kljuci])', js)
        self.assertIn('if (vrsta === "mediaOdkrivanje" && podatki) prevzemiOdkrivanje(podatki);', js)
        telo = js[js.index("function kliknOdkrivanje"):js.index("function karticaOdkrivanja")]
        for pot in ("odpriYtSeznam(", "odpriSpSeznam(", "odpriTwitchKanal(", "odpriKatalogPodrobnosti(", "odpriKatalogVnos("):
            self.assertIn(pot, telo)
        self.assertNotIn('klic("mediaPredvajaj"', telo)          # brez nove logike predvajanja
        self.assertIn("|| junakOdkrivanja();", js)                # junak tudi brez zgodovine
        self.assertIn("media-polica-vse", js[js.index("function narisiOdkrivanje"):])

    def test_prevodi(self):
        bes = _beri("assets", "os", "besedila.js")
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            m = re.search(r'Object\.assign\(BESEDILA_OS\.%s, (\{"odkrijFilmi"[^\n]*\})\);' % jezik, bes)
            self.assertIsNotNone(m, jezik)
            for kljuc in ("odkrijFilmi", "odkrijSerije", "odkrijGlasba", "odkrijYoutube", "odkrijSpotify",
                          "odkrijTwitch", "odkrijRadio", "domovVec"):
                self.assertIn('"%s": "' % kljuc, m.group(1), (jezik, kljuc))


if __name__ == "__main__":
    unittest.main()
