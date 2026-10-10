"""Izbira jezika vsebine poleg zvrsti (Medijski center): katalog, viri in most - brez omrezja.

Lastnik, 4. 10. 2026: "Pri video in glasbi se rabimo en filter glede na jezik vsebine, dodaj poleg zvrsti".
Pravila izvirnega jezika (Wikidata) so v tests/test_izvirni_jezik.py.
"""
import io
import json
import os
import re
import tempfile
import unittest
import urllib.parse

from core import izvirni_jezik, os_katalog, os_media
from core import zakoniti_viri as z

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class _LazniJeziki:
    """Namesto Wikidate: pove jezik znanih naslovov in si zapomni, za katere smo vprasali."""

    def __init__(self, znani):
        self.znani, self.vprasani = znani, []

    def jeziki(self, idji):
        idji = list(idji)
        self.vprasani.append(idji)
        return {i: self.znani.get(i, []) for i in idji}


class KatalogVJeziku(unittest.TestCase):
    def _center(self, td, zakoniti=(), osebni=()):
        center = os_media.MediaCenter(td, roots=[])
        center._ima_embed_vir = lambda data=None: False
        self.klici_virov = []

        def viri(*a, **k):
            self.klici_virov.append(a)
            return [dict(v) for v in zakoniti]
        center._zakoniti_viri.get = viri
        center._personal_items = lambda q: [dict(v) for v in osebni]
        center._izvirni_jeziki = _LazniJeziki({"tt0043703": ["sl"], "tt0111161": ["en"], "tt0054407": ["hr", "sr", "bs"]})
        center._koren_zaseben = lambda koren: {"https://javni.example": False, "https://zaseben.example": True}.get(koren)
        return center

    VIDEI = ({"naslov": "A", "vrsta": "video", "url": "https://framatube.org/w/1", "vir": "PeerTube · framatube.org", "jezik": "fr"},
             {"naslov": "B", "vrsta": "video", "url": "https://tilvids.com/w/2", "vir": "PeerTube · tilvids.com", "jezik": "en"},
             {"naslov": "C", "vrsta": "video", "url": "https://tilvids.com/w/3", "vir": "PeerTube · tilvids.com"})

    def test_izbran_jezik_pusti_samo_vsebino_v_tem_jeziku(self):
        with tempfile.TemporaryDirectory() as td:
            center = self._center(td, self.VIDEI)
            self.assertEqual(sorted(x["naslov"] for x in center.catalog("", "video")["vnosi"]), ["A", "B", "C"])
            fr = center.catalog("", "video", jezik="fr")
            self.assertEqual([x["naslov"] for x in fr["vnosi"]], ["A"])
            self.assertEqual(fr["skupaj"], 1)
            self.assertEqual([x["naslov"] for x in center.catalog("", "video", jezik="en")["vnosi"]], ["B"])
            # Vnos z neznanim jezikom se med izbiro ne kaze; jezik brez vsebine da prazen katalog (ne vsega).
            self.assertEqual(center.catalog("", "video", jezik="sl")["vnosi"], [])
            # Koda, ki je izbira ne ponuja, ne velja (katalog je tak kot brez izbire).
            self.assertEqual(len(center.catalog("", "video", jezik="xx")["vnosi"]), 3)
            self.assertEqual(len(center.catalog("", "video", jezik="'; DROP")["vnosi"]), 3)
            # Izbira gre do virov (PeerTube in Jamendo izbereta ze sama): cetrti parameter.
            self.assertEqual(self.klici_virov[1][3], "fr")
            self.assertEqual(self.klici_virov[0][2:], ("", ""))

    def test_naslovi_dodatkov_po_wikidati_brez_zasebnih(self):
        def dodatek(naslov, mid, koren="https://javni.example"):
            return {"id": "stremio:s1:movie:" + mid, "naslov": naslov, "vrsta": "film", "url": "stremio:%s|movie|%s" % (koren, mid),
                    "imdb_id": mid if mid.startswith("tt") else "", "vir": "Dodatek", "leto": 1951,
                    "stremio": {"koren": koren, "tip": "movie", "id": mid}}
        osebni = (dodatek("Kekec", "tt0043703"), dodatek("Kaznilnica odresitve", "tt0111161"),
                  dodatek("Signali nad mestom", "tt0054407"), dodatek("Brez id-ja", "abc:1"),
                  dodatek("Iz zasebnega dodatka", "tt7777777", "https://zaseben.example"),
                  dodatek("Iz neznanega dodatka", "tt8888888", "https://neznan.example"))
        with tempfile.TemporaryDirectory() as td:
            center = self._center(td, (), osebni)
            sl = center.catalog("", "film", jezik="sl")
            self.assertEqual([x["naslov"] for x in sl["vnosi"]], ["Kekec"])
            self.assertEqual(sl["vnosi"][0]["jezik"], "sl")
            # Wikidato vprasamo samo za javne id-je naslovov iz javnih dodatkov: zasebni (in dodatek, za katerega
            # se ne vemo, ali je zaseben) ostane na racunalniku.
            vprasani = center._izvirni_jeziki.vprasani[-1]
            self.assertEqual(sorted(vprasani), ["tt0043703", "tt0054407", "tt0111161"])
            # Jugoslovanski film je pod hrvascino, srbscino in bosanscino.
            for koda in ("hr", "sr", "bs"):
                self.assertEqual([x["naslov"] for x in center.catalog("", "film", jezik=koda)["vnosi"]], ["Signali nad mestom"], koda)
            # Brez izbire Wikidate ne sprasujemo.
            prej = len(center._izvirni_jeziki.vprasani)
            self.assertEqual(len(center.catalog("", "film")["vnosi"]), 6)
            self.assertEqual(len(center._izvirni_jeziki.vprasani), prej)
            # Izpad Wikidate ne podre kataloga: naslovi z neznanim jezikom se ne pokazejo.
            center._izvirni_jeziki.jeziki = lambda idji: (_ for _ in ()).throw(OSError("ni omrezja"))
            self.assertEqual(center.catalog("", "film", jezik="sl")["vnosi"], [])

    def test_jezik_vira_velja_tudi_za_sorodne_kode(self):
        filmi = ({"naslov": "Tko pjeva zlo ne misli", "vrsta": "film", "url": "https://t/1", "vir": "V", "jezik": "sh"},
                 {"naslov": "Kantonski", "vrsta": "film", "url": "https://t/2", "vir": "V", "jezik": "cn"},
                 {"naslov": "Mandarinski", "vrsta": "film", "url": "https://t/3", "vir": "V", "jezik": "zh"})
        with tempfile.TemporaryDirectory() as td:
            center = self._center(td, filmi)
            self.assertEqual([x["naslov"] for x in center.catalog("", "film", jezik="hr")["vnosi"]], ["Tko pjeva zlo ne misli"])
            self.assertEqual(sorted(x["naslov"] for x in center.catalog("", "film", jezik="zh")["vnosi"]), ["Kantonski", "Mandarinski"])

    def test_zdruzena_kartica_obdrzi_jezik_razlicice(self):
        zdruzeno = os_media.merge_duplicates([
            {"naslov": "Kekec", "vrsta": "film", "url": "https://a/1", "imdb_id": "tt0043703", "kakovost": "1080p", "locljivost": 1080},
            {"naslov": "Kekec", "vrsta": "film", "url": "https://b/1", "imdb_id": "tt0043703", "jezik": "sl"}])
        self.assertEqual(len(zdruzeno), 1)
        self.assertEqual(zdruzeno[0]["jezik"], "sl")

    def test_kljuc_pogleda_in_hitri_katalog(self):
        with tempfile.TemporaryDirectory() as td:
            center = self._center(td, self.VIDEI)
            brez = json.loads(center.kljuc_kataloga("", "video"))
            self.assertEqual(len(brez), 10, "brez izbire je kljuc tak kot prej (shranjeni pogledi ostanejo veljavni)")
            z_jezikom = json.loads(center.kljuc_kataloga("", "video", jezik="fr"))
            self.assertEqual(z_jezikom, brez + ["jezik:fr"])
            self.assertEqual(json.loads(center.kljuc_kataloga("", "video", jezik="xx")), brez)
            prvi = center.catalog_hitro("", "video", jezik="fr")
            self.assertEqual([x["naslov"] for x in prvi["vnosi"]], ["A"])
            self.assertFalse(prvi["iz_predpomnilnika"])
            drugi = center.catalog_hitro("", "video", jezik="fr")
            self.assertTrue(drugi["iz_predpomnilnika"])
            self.assertEqual([x["naslov"] for x in drugi["vnosi"]], ["A"])
            # Drug jezik in brez jezika sta druga pogleda.
            self.assertEqual([x["naslov"] for x in center.catalog_hitro("", "video", jezik="en")["vnosi"]], ["B"])
            self.assertEqual(len(center.catalog_hitro("", "video")["vnosi"]), 3)


class TmdbPoJeziku(unittest.TestCase):
    def _center(self, td):
        center = os_media.MediaCenter(td, roots=[])
        self.klici = []

        def tmdb(endpoint, params=None):
            self.klici.append((endpoint, dict(params or {})))
            vrsta = endpoint.rsplit("/", 1)[-1]
            return {"total_pages": 7 if vrsta == "movie" else 3,
                    "results": [{"id": "%s%d" % (vrsta[0], i), "title": "%s %d" % (vrsta, i)} for i in range(1, 4 if vrsta == "movie" else 3)]}
        center._tmdb = tmdb
        center._tmdb_vnos = lambda raw, source: {"naslov": raw["title"], "url": "https://t/" + raw["id"],
                                                 "vrsta": "serija" if raw["media_type"] == "tv" else "film"}
        return center

    def test_vse_film_in_serija_izmenicno(self):
        with tempfile.TemporaryDirectory() as td:
            center = self._center(td)
            vnosi, strani = center._tmdb_catalog({}, "", "vse", "", 2, "", "hr")
            self.assertEqual([k[0] for k in self.klici], ["/discover/movie", "/discover/tv"])
            for _endpoint, p in self.klici:
                # TMDB vodi srbohrvascino pod svojo kodo: izbira hrvascine jo zajame.
                self.assertEqual(p["with_original_language"], "hr|sh")
                self.assertEqual((p["page"], p["sort_by"], p["vote_count.gte"]), (2, "popularity.desc", 10))
            self.assertEqual([v["naslov"] for v in vnosi], ["movie 1", "tv 1", "movie 2", "tv 2", "movie 3"])
            self.assertEqual(strani, 7)

    def test_film_z_zvrstjo_in_razvrstitvijo(self):
        with tempfile.TemporaryDirectory() as td:
            center = self._center(td)
            vnosi, _ = center._tmdb_catalog({}, "", "film", "35", 1, "novo", "sl")
            self.assertEqual([k[0] for k in self.klici], ["/discover/movie"])
            p = self.klici[0][1]
            self.assertEqual((p["with_original_language"], p["with_genres"]), ("sl", "35"))
            self.assertEqual(p["sort_by"], "primary_release_date.desc")
            self.assertEqual(p["vote_count.gte"], 10, "nizek prag: slovenskih filmov je malo")
            self.assertEqual(len(vnosi), 3)
            # Anglescina ima naslovov dovolj: prag ostane.
            self.klici.clear()
            center._tmdb_catalog({}, "", "serija", "", 1, "novo", "en")
            self.assertEqual(self.klici[0][0], "/discover/tv")
            self.assertEqual(self.klici[0][1]["vote_count.gte"], 50)
            # »Vse« z zvrstjo: filmske zvrsti veljajo za filme (kot brez izbire jezika).
            self.klici.clear()
            center._tmdb_catalog({}, "", "vse", "35", 1, "", "sl")
            self.assertEqual([k[0] for k in self.klici], ["/discover/movie"])

    def test_iskanje_ostane_iskanje(self):
        with tempfile.TemporaryDirectory() as td:
            center = self._center(td)
            center._tmdb = lambda endpoint, params=None: (self.klici.append((endpoint, dict(params or {}))), {"results": []})[1]
            center._tmdb_catalog({}, "kekec", "film", "", 1, "", "sl")
            self.assertEqual(self.klici[0][0], "/search/multi")
            self.assertNotIn("with_original_language", self.klici[0][1])


class _Odgovor(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class ViriVJeziku(unittest.TestCase):
    def setUp(self):
        self.naslovi = []

        def odpri(zahteva, timeout=None):
            self.naslovi.append(zahteva.full_url)
            if "api.jamendo.com" in zahteva.full_url:
                lang = urllib.parse.parse_qs(urllib.parse.urlsplit(zahteva.full_url).query).get("lang", [""])[0]
                return _Odgovor(json.dumps({"results": [
                    {"id": 1, "name": "Pesem", "artist_name": "Izvajalec", "audio": "https://a/1.mp3", "musicinfo": {"lang": lang or "en"}},
                    {"id": 2, "name": "Instrumental", "artist_name": "Izvajalec", "audio": "https://a/2.mp3", "musicinfo": {"lang": ""}},
                    {"id": 3, "name": "Brez podatkov", "artist_name": "Izvajalec", "audio": "https://a/3.mp3"}]}).encode())
            return _Odgovor(json.dumps({"data": []}).encode())
        self.viri = z.ZakonitiViri(opener=odpri)
        self.viri._video_hosts = lambda configured: ["tilvids.com"]

    def test_peertube(self):
        self.viri.videos()
        self.assertEqual(sorted(self.naslovi), sorted(
            "https://tilvids.com/api/v1/videos?sort=%s&count=18&nsfw=false&isLocal=true" % s
            for s in ("-trending", "-views", "-publishedAt")), "brez izbire so vprasanja taka kot prej")
        self.naslovi.clear()
        self.viri.videos("", None, "sl")
        self.assertEqual(len(self.naslovi), 3)
        for naslov in self.naslovi:
            self.assertIn("count=40&languageOneOf=sl&nsfw=false&isLocal=true", naslov)
        self.naslovi.clear()
        self.viri.videos("", None, "sl; DROP")           # neveljavna koda ne gre v naslov
        self.assertTrue(all("languageOneOf" not in n for n in self.naslovi))
        self.naslovi.clear()
        self.viri.videos("kekec", None, "sl")
        self.assertIn("languageOneOf=sl", self.naslovi[0])
        self.assertTrue(self.naslovi[0].startswith("https://sepiasearch.org/api/v1/search/videos?"))

    def test_jamendo(self):
        skladbe = self.viri.music("", "", "sl")
        p = urllib.parse.parse_qs(urllib.parse.urlsplit(self.naslovi[0]).query)
        self.assertEqual((p["lang"], p["include"], p["order"]), (["sl"], ["musicinfo"], ["popularity_total"]))
        self.assertEqual([(s["naslov"], s.get("jezik")) for s in skladbe],
                         [("Pesem", "sl"), ("Instrumental", None), ("Brez podatkov", None)])
        self.naslovi.clear()
        brez = self.viri.music()
        p = urllib.parse.parse_qs(urllib.parse.urlsplit(self.naslovi[0]).query)
        self.assertNotIn("lang", p)
        self.assertEqual(p["include"], ["musicinfo"], "jezik skladbe poznamo tudi brez izbire")
        self.assertEqual(brez[0]["jezik"], "en")
        self.naslovi.clear()
        self.viri.music("", "rock", "de")
        p = urllib.parse.parse_qs(urllib.parse.urlsplit(self.naslovi[0]).query)
        self.assertEqual((p["tags"], p["lang"]), (["rock"], ["de"]))
        self.naslovi.clear()
        # Neveljavna koda ne gre v naslov: vprasanje je isto kot brez izbire (pride iz predpomnilnika).
        self.assertEqual(self.viri.music("", "", "nemscina"), brez)
        self.assertEqual(self.naslovi, [])

    def test_get_poda_jezik_naprej(self):
        klici = []
        self.viri.videos = lambda *a: klici.append(("videos", a)) or []
        self.viri.music = lambda *a: klici.append(("music", a)) or []
        self.viri.radio = lambda *a: klici.append(("radio", a)) or []
        self.viri.javna_last = lambda *a: klici.append(("javna_last", a)) or []
        self.viri.get("", ["h"], "", "sl")
        self.assertEqual(dict(klici), {"videos": ("", ["h"], "sl"), "music": ("", "", "sl"), "radio": ("",), "javna_last": ("", "sl", "")})
        klici.clear()
        self.viri.get("", None, "rock", "sl")
        self.assertEqual(dict(klici), {"music": ("", "rock", "sl"), "radio": ("", "rock")})


class MostInPaket(unittest.TestCase):
    def test_most_poda_jezik_jedru(self):
        klici = []

        class Lazni:
            izbrana_drzava = "auto"

            def catalog_hitro(self, *a, **k):
                klici.append((a, k))
                return {"vnosi": []}

            def brez_nerazpolozljivih(self, r):
                return r

            def preveri_razpolozljivost(self, vnosi, ob):
                pass
        with tempfile.TemporaryDirectory() as td:
            katalog = os_katalog.Katalog(td, lambda *a: None, lambda f: f(), lambda *a, **k: True, lambda u: True,
                                         lambda a, b: True, lambda u: True)
            katalog._mc = Lazni()
            katalog._katalog(["", "film", "", 1, "", [], False, [], "sl"])
            katalog._katalog(["", "film", "", 1, "", [], False, []])          # starejsa stran: brez jezika
        self.assertEqual(klici[0][1]["jezik"], "sl")
        self.assertEqual(klici[1][1]["jezik"], "")

    def test_modul_je_v_tovoru_in_brez_odvisnosti(self):
        self.assertIn(" izvirni_jezik ", _beri("packaging", "install_os_payload.sh"))
        vir = _beri("core", "izvirni_jezik.py")
        # Isti modul uporablja Safeer OS za Windows: brez uvozov iz drugih delov Safeerja.
        self.assertIsNone(re.search(r"^\s*(from core|from \.|import core)", vir, re.M))
        self.assertEqual(izvirni_jezik.KODE[0], "sl")


class Vmesnik(unittest.TestCase):
    """Izbira »Vsi jeziki« poleg zvrsti na strani Medijskega centra."""

    def setUp(self):
        self.js = _beri("assets", "os", "os.js")
        self.html = _beri("assets", "os", "index.html")

    def test_seznam_jezikov_je_isti_kot_v_jedru(self):
        seznam = re.search(r"var KAT_JEZIKI = \[(.*?)\];", self.js, re.S).group(1)
        self.assertEqual(tuple(re.findall(r'"([a-z]{2})"', seznam)), izvirni_jezik.KODE)

    def test_izbira_stoji_pred_zvrstmi(self):
        vrstica = self.html.split('<div class="kat-zanri-vrstica">', 1)[1].split('<div class="kat-seznami"', 1)[0]
        self.assertLess(vrstica.index('id="mediaJezik"'), vrstica.index('id="mediaZanri"'))
        self.assertIn('<label class="kat-jezik" id="mediaJezikPolje" hidden>', vrstica)
        css = _beri("assets", "os", "katalog.css")
        self.assertIn(".kat-zanri-vrstica { display:flex", css)

    def test_kje_izbira_velja(self):
        velja = self.js.split("function jezikVelja(filter) {", 1)[1].split("}", 1)[0]
        for vrsta in ("vse", "film", "serija", "video", "glasba"):
            self.assertIn('filter === "%s"' % vrsta, velja)
        for vrsta in ("radio", "tv-v-zivo"):
            self.assertNotIn(vrsta, velja)
        # Odprt seznam predvajanja ni katalog: izbire ni in jezik se ne poda.
        self.assertIn('function izbranJezik() { return !kat.seznam && jezikVelja(kat.filter) ? (kat.jezikVsebine || "") : ""; }', self.js)

    def test_katalog_dobi_izbrani_jezik(self):
        self.assertIn("Object.keys(kat.izklopljeniJeziki), izbranJezik()])", self.js)
        izbira = self.js.split('ob("mediaJezik", "change", function () {', 1)[1].split("});", 1)[0]
        self.assertIn("kat.jezikVsebine = this.value; kat.page = 1;", izbira)
        # Kartice prejsnjega jezika takoj izginejo, katalog se nalozi znova.
        self.assertIn("kat.katalog = []; kat.nalozen = false;", izbira)
        self.assertIn("naloziKatalog();", izbira)

    def test_vrstni_red_in_imena_jezikov(self):
        izris = self.js.split("function narisiJezikVsebine() {", 1)[1].split("function osveziGumbViri()", 1)[0]
        self.assertIn('var prvi = [jezik, "en"]', izris)                      # jezik vmesnika in anglescina na vrhu
        self.assertIn("imeJezika(a).localeCompare(imeJezika(b)", izris)        # ostali po abecedi
        self.assertIn('new Option(t("katVsiJeziki"), "")', izris)
        self.assertIn('izbira.setAttribute("aria-label", t("katJezikVsebine"))', izris)
        # Ob menjavi jezika vmesnika se imena izpisejo znova.
        prevedi = self.js.split("function prevediKatalog() {", 1)[1].split("function katDogodek", 1)[0]
        self.assertIn("kat.jezikiZa = null; narisiJezikVsebine();", prevedi)

    def test_katalog_med_nalaganjem_ne_skace(self):
        """Uvodna plosca se med nalaganjem ne pokaze za hip; pri izbranem jeziku brez zadetkov je ni."""
        self.assertIn('if (kat.nalozen || list.length) $("r-media").classList.toggle("ima-katalog", list.length > 0 || !!izbranJezik());', self.js)
        self.assertNotIn('$("r-media").classList.toggle("ima-katalog", list.length > 0);', self.js)

    def test_prazen_katalog_pove_zakaj(self):
        self.assertIn('izbranJezik() ? t("katPraznoJezik", { jezik: imeJezika(kat.jezikVsebine, true) }) : t("katPrazno")', self.js)
        self.assertNotIn('data-t="katPrazno"', self.html)
        besedila = _beri("assets", "os", "besedila.js")
        for kljuc in ("katVsiJeziki", "katJezikVsebine", "katPraznoJezik"):
            self.assertEqual(besedila.count('"%s":' % kljuc), 6, kljuc)
        self.assertEqual(besedila.count("{jezik}"), 6)


if __name__ == "__main__":
    unittest.main()
