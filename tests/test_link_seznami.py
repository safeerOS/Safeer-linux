"""Seznami predvajanja med napravami v Safeer Linku na Linuxu: Control odgovarja (lists.get), Safeer OS prevzema."""
import json
import os
import tempfile
import unittest
from unittest import mock

from core import link_daljinec, link_seznami, os_media, seznami_sink, viri_sink

SKLADBE = [{"naslov": "Pesem %d" % i, "izvajalec": "Pevka", "youtube": "59o4m222aV%s" % "wxyz"[i % 4], "sekund": 200 + i,
            "slika": "https://i.ytimg.com/vi/x/hq.jpg", "interno": "ne gre naprej"} for i in range(230)]


class IzvozTests(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        with open(os.path.join(self.mapa.name, "seznami.json"), "w", encoding="utf-8") as f:
            json.dump([{"ime": "Uspešnice", "vir": "Spotify", "cas": 1790000000000, "skladbe": SKLADBE},
                       {"ime": "Kratek", "cas": 5, "skladbe": SKLADBE[:2]},
                       {"ime": "", "skladbe": []}, "smeti", {"ime": "Brez skladb"}], f)
        with open(os.path.join(self.mapa.name, "seznami_izbrisani.json"), "w", encoding="utf-8") as f:
            json.dump({"Star": 1780000000000, "Slab": "x", "Nic": 0}, f)

    def test_odgovor_je_enak_kot_v_jedru_medijskega_centra(self):
        """Control bere sam (brez jedra kataloga); odgovor mora biti do pike enak MediaCenter.seznami_izvoz."""
        mc = os_media.MediaCenter(self.mapa.name, roots=[])
        for parametri in ({}, None, {"ime": "Uspešnice"}, {"ime": "Uspešnice", "od": 100}, {"ime": "Uspešnice", "od": 200},
                          {"ime": "Uspešnice", "od": 5000}, {"ime": "Uspešnice", "od": "x"}, {"ime": "Uspešnice", "od": -5},
                          {"ime": "Kratek"}, {"ime": "Ni ga"}, {"ime": 5}, "smeti"):
            self.assertEqual(link_seznami.izvoz(parametri, self.mapa.name), mc.seznami_izvoz(parametri), parametri)
        self.assertEqual(link_seznami.STRAN, seznami_sink.STRAN)
        self.assertEqual(link_seznami.DEJANJE, seznami_sink.DEJANJE)

    def test_kazalo_in_strani(self):
        kazalo = link_seznami.izvoz({}, self.mapa.name)
        self.assertEqual([(x["ime"], x["stevilo"]) for x in kazalo["lists"]], [("Uspešnice", 230), ("Kratek", 2)])
        self.assertEqual(kazalo["deleted"], {"Star": 1780000000000})
        stran = link_seznami.izvoz({"ime": "Uspešnice", "od": 200}, self.mapa.name)
        self.assertEqual((stran["od"], len(stran["skladbe"]), stran["stevilo"]), (200, 30, 230))
        self.assertNotIn("interno", stran["skladbe"][0])           # naprej gredo samo znana polja

    def test_control_pove_tudi_moje_vire_ki_jih_pripravi_medijski_center(self):
        """Krog 85: vire za naprave zapise Medijski center (brez zasebnih dodatkov); Control jih samo prebere in preveri.
        Pregled 46, Ö1: napravi zunaj ozjega kroga samo pozitivno znani javni viri, tudi iz zapisa starejse razlicice."""
        iptv = {"tip": "seznam", "ime": "TV", "naslov": "https://iptv-org.github.io/iptv/countries/si.m3u", "cas": 4}
        with open(os.path.join(self.mapa.name, "viri_za_naprave.json"), "w", encoding="utf-8") as f:
            json.dump({"sources": [{"tip": "stremio", "ime": "Dodatek", "naslov": "https://d.primer.si/manifest.json", "cas": 7, "zaseben": False},
                                   {"tip": "kodi", "ime": "x", "naslov": "https://k.primer.si"}, "smeti",
                                   {"tip": "url", "ime": "Podkast", "naslov": "https://p.primer.si/feed.xml", "cas": 0}, iptv],
                       "sources_deleted": {"stremio|https://star.primer.si/manifest.json": 9, "kodi|x": 3, "url|https://b.si": "x",
                                           "seznam|https://iptv-org.github.io/iptv/stari.m3u": 2}}, f)
        kazalo = link_seznami.izvoz({}, self.mapa.name, ozji=True)
        self.assertEqual(kazalo["sources"], [{"tip": "stremio", "ime": "Dodatek", "naslov": "https://d.primer.si/manifest.json", "cas": 7},
                                             {"tip": "url", "ime": "Podkast", "naslov": "https://p.primer.si/feed.xml", "cas": 0}, iptv])
        self.assertEqual(kazalo["sources_deleted"], {"stremio|https://star.primer.si/manifest.json": 9,
                                                     "seznam|https://iptv-org.github.io/iptv/stari.m3u": 2})
        navaden = link_seznami.izvoz({}, self.mapa.name)
        self.assertEqual((navaden["sources"], navaden["sources_deleted"]),
                         ([iptv], {"seznam|https://iptv-org.github.io/iptv/stari.m3u": 2}))
        self.assertNotIn("sources", link_seznami.izvoz({"ime": "Kratek"}, self.mapa.name))

    def test_brez_mape_ali_s_pokvarjeno_datoteko_je_kazalo_prazno(self):
        self.assertEqual(link_seznami.izvoz({}, os.path.join(self.mapa.name, "ni")),
                         {"lists": [], "deleted": {}, "ozji": False, "sources": [], "sources_deleted": {}})
        with open(os.path.join(self.mapa.name, "seznami.json"), "w", encoding="utf-8") as f:
            f.write("{napol zapisano")
        self.assertEqual(link_seznami.izvoz({}, self.mapa.name)["lists"], [])

    def test_mapa_je_mapa_medijskega_centra_safeer_os(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/x"}):
            self.assertEqual(link_seznami.mapa(), "/tmp/x/safeer-os/media")

    def test_druga_naprava_prevzame_seznam_prek_izvoza(self):
        """Celotna pot: naprava B vprasa (lists.get) napravo A in dobi njen seznam s 230 skladbami po straneh."""
        with tempfile.TemporaryDirectory() as b:
            mc_b = os_media.MediaCenter(b, roots=[])
            self.assertTrue(mc_b.seznami_uskladi(lambda parametri: link_seznami.izvoz(parametri, self.mapa.name)))
            moji = {x["ime"]: x for x in mc_b._seznami_beri()}
            self.assertEqual(len(moji["Uspešnice"]["skladbe"]), 230)
            self.assertEqual(moji["Uspešnice"]["cas"], 1790000000000)
            self.assertFalse(mc_b.seznami_uskladi(lambda parametri: link_seznami.izvoz(parametri, self.mapa.name)))


XTREAM = "http://ponudnik.test:8080/get.php?username=uporabnik&password=skrito-geslo&type=m3u_plus"
KANAL_XTREAM = "http://ponudnik.test:8080/live/uporabnik/skrito-geslo/123.ts"
PODKAST = "https://podkast.primer.si/feed.xml"
JAVNI = "https://iptv-org.github.io/iptv/countries/si.m3u"


class RacunSamoOzjiKrog(unittest.TestCase):
    """Z Androida (VISOKO, 26. 10. 2026): seznam Xtream z geslom je sel z usklajevanjem virov (lists.get) vsem napravam
    z dovoljenjem »Predvajalnik«, geslo pa je bilo v vrstici Virov na zaslonu. Vir in tok z racunom gresta samo v ozji
    krog (core/viri_sink.za_ozji_krog), na zaslonu je samo gostitelj."""

    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        viri = [{"id": "pub", "url": JAVNI, "ime": "Javni", "stevilo": 3, "napaka": "", "vnosi": [], "dodan": 4},
                {"id": "pod", "url": PODKAST, "ime": "Podkast", "stevilo": 3, "napaka": "", "vnosi": [], "dodan": 5},
                {"id": "xt", "url": XTREAM, "ime": "Ponudnik", "stevilo": 3, "napaka": "", "vnosi": [], "dodan": 6}]
        with open(os.path.join(self.mapa.name, "media.json"), "w", encoding="utf-8") as f:
            json.dump({"viri": viri, "osebni_strezniki": []}, f)
        with open(os.path.join(self.mapa.name, "seznami.json"), "w", encoding="utf-8") as f:
            json.dump([{"ime": "TV", "cas": 7, "skladbe": [{"naslov": "Kanal", "url": KANAL_XTREAM},
                                                            {"naslov": "Javni", "url": "https://tok.primer.si/a.m3u8"}]}], f)
        self.mc = os_media.MediaCenter(self.mapa.name, roots=[])
        self.javni = {"tip": "url", "ime": "Javni", "naslov": JAVNI, "cas": 4}
        self.podkast = {"tip": "url", "ime": "Podkast", "naslov": PODKAST, "cas": 5}
        self.racun = {"tip": "url", "ime": "Ponudnik", "naslov": XTREAM, "cas": 6}

    def test_vir_z_racunom_samo_ozjemu_krogu(self):
        # Pregled 46, Ö1: zunaj ozjega kroga samo pozitivno znan javen vir - podkast ni znan, gre samo v ozji krog.
        self.assertEqual(self.mc.viri_izvoz()["sources"], [self.javni])
        self.assertEqual(self.mc.viri_izvoz(ozji=True)["sources"], [self.javni, self.podkast, self.racun])
        self.mc._viri_zapisi_izvoz()                                # zapis za Safeer Control (viri_za_naprave.json)
        self.assertEqual(link_seznami.izvoz({}, self.mapa.name)["sources"], [self.javni])
        self.assertEqual(link_seznami.izvoz({}, self.mapa.name, ozji=True)["sources"], [self.javni, self.podkast, self.racun])
        for ozji in (False, True):
            self.assertEqual(link_seznami.izvoz({}, self.mapa.name, ozji=ozji), self.mc.seznami_izvoz({}, ozji=ozji))
        self.assertNotIn("skrito-geslo", json.dumps(link_seznami.izvoz({}, self.mapa.name)))

    def test_izbris_vira_z_racunom_samo_ozjemu_krogu(self):
        star_javni = "url|https://iptv-org.github.io/iptv/stari.m3u"
        izvoz = viri_sink.razdeli_izvoz([self.javni, self.racun], {"url|" + XTREAM: 9, star_javni: 8,
                                                                   "url|https://star.primer.si/f.xml": 7})
        self.assertEqual(viri_sink.viri_za(izvoz), {"sources": [self.javni], "sources_deleted": {star_javni: 8}})
        self.assertEqual(viri_sink.viri_za(izvoz, True)["sources_deleted"],
                         {star_javni: 8, "url|" + XTREAM: 9, "url|https://star.primer.si/f.xml": 7})
        # Zapis starejse razlicice (brez delitve): vir in izbris z racunom ne gresta nikomur zunaj ozjega kroga.
        star = {"sources": [self.racun, self.javni], "sources_deleted": {"url|" + XTREAM: 3}}
        self.assertEqual(viri_sink.viri_za(star), {"sources": [self.javni], "sources_deleted": {}})

    def test_tok_z_racunom_v_seznamu_samo_ozjemu_krogu(self):
        # Pregled 46, Ö1: tok, ki ni pozitivno znan javen, samo ozjemu krogu.
        for ozji, naslovi in ((False, [None, None]),
                              (True, [KANAL_XTREAM, "https://tok.primer.si/a.m3u8"])):
            stran = link_seznami.izvoz({"ime": "TV"}, self.mapa.name, ozji=ozji)
            self.assertEqual([x.get("url") for x in stran["skladbe"]], naslovi)
            self.assertEqual(stran, self.mc.seznami_izvoz({"ime": "TV"}, ozji=ozji))

    def test_control_da_vir_z_racunom_samo_napravi_v_ozjem_krogu(self):
        from core import link_dostop
        self.mc._viri_zapisi_izvoz()
        izidi = []
        with mock.patch.object(link_seznami, "mapa", return_value=self.mapa.name), \
                mock.patch.object(link_dostop, "v_ozjem_krogu", lambda d: d == "n-ozji"):
            for kdo in ("n-predvajalnik", "n-ozji", ""):
                link_daljinec.izvedi_control("lists.get", {}, lambda _u: None, izidi.append, posiljatelj=kdo)
        self.assertEqual([[v["naslov"] for v in i["data"]["sources"]] for i in izidi],
                         [[JAVNI], [JAVNI, PODKAST, XTREAM], [JAVNI]])

    def test_na_zaslonu_samo_gostitelj(self):
        viri = {v["id"]: v for v in self.mc.sources() if v.get("id") in ("pub", "pod", "xt")}
        self.assertEqual((viri["xt"]["url_prikaz"], viri["pod"]["url_prikaz"], viri["pub"]["url_prikaz"]),
                         ("ponudnik.test:8080", "podkast.primer.si", JAVNI))
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "assets", "os", "os.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn("var prikaz = source.url_prikaz !== undefined ? source.url_prikaz : source.url;", js)
        self.assertNotIn('ubezi(status + " · " + source.url)', js)


class ObDvomuOzjiKrog(unittest.TestCase):
    """Pregled 46, Ö1: za_ozji_krog je bil hevristika, ki je ob neznani obliki odprla - vir z geslom v obliki, ki je ni
    prepoznala, je sel vsem napravam s »Predvajalnik« in na zaslon s celim naslovom. Zdaj ob dvomu ne: zunaj ozjega
    kroga in na zaslonu cel samo pozitivno znan javen vir (ali seznam, ki ga je uporabnik oznacil kot javnega)."""

    OBLIKE = {"pot": "http://ponudnik.primer.test:8080/playlist/uporabnik/skrito-geslo/m3u_plus",
              "get": "http://ponudnik.primer.test:8080/get/uporabnik/skrito-geslo/m3u",
              "zeton": "https://ponudnik.primer.test/m3u/skrito-geslo.m3u",
              "kratka": "https://kratka.primer.test/skritogeslo",
              "dodatek": "https://dodatek.primer.test/realdebrid=skrito-geslo/manifest.json"}
    TUJE = {"rtsp": "rtsp://uporabnik:skrito-geslo@kamera.primer.test:554/tok",
            "presledek": " http://ponudnik.primer.test:8080/get.php?username=uporabnik&password=skrito-geslo"}
    OZNACEN = "https://seznam.primer.test/tv.m3u"

    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        viri = [{"id": k, "url": u, "stevilo": 3, "napaka": "", "vnosi": [], "dodan": 10 + i}
                for i, (k, u) in enumerate(list(self.OBLIKE.items()) + list(self.TUJE.items()))]
        viri += [{"id": "oznacen", "url": self.OZNACEN, "javni": True, "stevilo": 3, "napaka": "", "vnosi": [], "dodan": 30},
                 {"id": "javni", "url": JAVNI, "stevilo": 3, "napaka": "", "vnosi": [], "dodan": 31}]
        with open(os.path.join(self.mapa.name, "media.json"), "w", encoding="utf-8") as f:
            json.dump({"viri": viri, "osebni_strezniki": []}, f)
        with open(os.path.join(self.mapa.name, "seznami.json"), "w", encoding="utf-8") as f:
            json.dump([{"ime": "TV", "cas": 7, "skladbe": [{"naslov": k, "url": u} for k, u in self.OBLIKE.items()]}], f)
        self.mc = os_media.MediaCenter(self.mapa.name, roots=[])

    def test_neznana_oblika_samo_ozjemu_krogu(self):
        self.mc._viri_zapisi_izvoz()
        for izvoz in (self.mc.viri_izvoz(), link_seznami.izvoz({}, self.mapa.name)):
            self.assertEqual([v["naslov"] for v in izvoz["sources"]], [self.OZNACEN, JAVNI])
            self.assertNotIn("skrito-geslo", json.dumps(izvoz))
            self.assertNotIn("javni", json.dumps(izvoz["sources"][0]))       # oznaka uporabnika ne gre napravam
        for izvoz in (self.mc.viri_izvoz(ozji=True), link_seznami.izvoz({}, self.mapa.name, ozji=True)):
            self.assertEqual({v["naslov"] for v in izvoz["sources"]}, set(self.OBLIKE.values()) | {self.OZNACEN, JAVNI})
        stran = link_seznami.izvoz({"ime": "TV"}, self.mapa.name)
        self.assertEqual([s.get("url") for s in stran["skladbe"]], [None] * len(self.OBLIKE))
        self.assertNotIn("skrito-geslo", json.dumps(stran))

    def test_izbris_neznane_oblike_samo_ozjemu_krogu(self):
        izbrisi = {"url|" + u: 5 for u in self.OBLIKE.values()}
        izvoz = viri_sink.razdeli_izvoz([], izbrisi)
        self.assertEqual(viri_sink.viri_za(izvoz)["sources_deleted"], {})
        self.assertEqual(viri_sink.viri_za(izvoz, True)["sources_deleted"], izbrisi)

    def test_na_zaslonu_samo_gostitelj(self):
        viri = {v["id"]: v for v in self.mc.sources()}
        for k in list(self.OBLIKE) + list(self.TUJE):
            with self.subTest(k):
                self.assertNotIn("skrito-geslo", viri[k]["url_prikaz"])
                self.assertTrue(viri[k]["url_prikaz"].endswith(".primer.test") or viri[k]["url_prikaz"].endswith(":8080")
                                or viri[k]["url_prikaz"].endswith(":554"), viri[k]["url_prikaz"])
        self.assertEqual((viri["oznacen"]["url_prikaz"], viri["javni"]["url_prikaz"]), (self.OZNACEN, JAVNI))

    def test_oznaka_ne_odpre_naslova_z_racunom(self):
        self.assertTrue(viri_sink.za_ozji_krog(XTREAM, True))
        self.assertEqual(viri_sink.prikaz_naslova(XTREAM, True), "ponudnik.test:8080")
        self.assertEqual(viri_sink.viri_za({"sources": [{"tip": "url", "ime": "", "naslov": XTREAM, "cas": 1, "javni": True}]}),
                         {"sources": [], "sources_deleted": {}})


class PoljaSeznamaZunajOzjegaKroga(unittest.TestCase):
    """Pregled 46, Ö2: polje »vir« seznama (kazalo in stran) je slo vsem napravam nespremenjeno, pri skladbi z racunom
    se je odstranil samo `url` - slika (logotip ponudnika z username=), zapis Androida in naslov z naslovom toka so
    ostali. Napravi zunaj ozjega kroga gredo samo pozitivno javna polja."""

    LOGO = "http://ponudnik.test:8080/images/logo.png?username=uporabnik&password=skrito-geslo"
    ANDROID = '{"url":"http:\\/\\/ponudnik.test:8080\\/live\\/uporabnik\\/skrito-geslo\\/1.ts","ime":"Kanal"}'
    GSON = '{"u":"http://ponudnik.test/k.ts?username\\u003duporabnik\\u0026password\\u003dskrito-geslo"}'
    YT = {"naslov": "Pesem", "izvajalec": "Pevka", "youtube": "59o4m222aVw", "sekund": 200,
          "slika": "https://i.ytimg.com/vi/59o4m222aVw/mqdefault.jpg",
          "android": '{"slika":"https:\\/\\/i.ytimg.com\\/vi\\/59o4m222aVw\\/mqdefault.jpg"}'}

    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        skladbe = [{"naslov": KANAL_XTREAM, "url": KANAL_XTREAM, "slika": self.LOGO, "android": self.ANDROID},
                   {"naslov": "Kanal 2", "izvajalec": "Ponudnik " + KANAL_XTREAM, "android": self.GSON}, self.YT]
        with open(os.path.join(self.mapa.name, "seznami.json"), "w", encoding="utf-8") as f:
            json.dump([{"ime": "TV", "vir": XTREAM, "cas": 7, "skladbe": skladbe},
                       {"ime": "Glasba", "vir": "YouTube", "cas": 8, "skladbe": [self.YT]}], f)
        self.mc = os_media.MediaCenter(self.mapa.name, roots=[])

    def test_vir_seznama_in_polja_skladbe_brez_gesla(self):
        for parametri in ({}, {"ime": "TV"}):
            for ozji in (False, True):
                with self.subTest(parametri=parametri, ozji=ozji):
                    izvoz = link_seznami.izvoz(parametri, self.mapa.name, ozji=ozji)
                    self.assertEqual(izvoz, self.mc.seznami_izvoz(parametri, ozji=ozji))
                    self.assertEqual("skrito-geslo" in json.dumps(izvoz), ozji)
        kazalo = link_seznami.izvoz({}, self.mapa.name)
        self.assertEqual([(x["ime"], x["vir"]) for x in kazalo["lists"]], [("TV", "ponudnik.test:8080"), ("Glasba", "YouTube")])
        stran = link_seznami.izvoz({"ime": "TV"}, self.mapa.name)
        self.assertEqual(stran["vir"], "ponudnik.test:8080")
        kanal, drugi, yt = stran["skladbe"]
        self.assertEqual(kanal, {"naslov": "ponudnik.test:8080"})
        self.assertEqual(drugi, {"naslov": "Kanal 2", "izvajalec": "Ponudnik ponudnik.test:8080"})
        self.assertEqual(yt, self.YT)                                       # javna slika in zapis z javno sliko ostaneta

    def test_ozji_krog_dobi_vse(self):
        stran = link_seznami.izvoz({"ime": "TV"}, self.mapa.name, ozji=True)
        self.assertEqual(stran["vir"], XTREAM)
        self.assertEqual((stran["skladbe"][0]["url"], stran["skladbe"][0]["slika"], stran["skladbe"][0]["android"]),
                         (KANAL_XTREAM, self.LOGO, self.ANDROID))

    def test_pravila_polj(self):
        self.assertEqual(viri_sink.vir_seznama_za("Spotify"), "Spotify")
        self.assertEqual(viri_sink.vir_seznama_za("Seznam: " + XTREAM), "")
        self.assertEqual(viri_sink.vir_seznama_za(XTREAM, True), XTREAM)
        self.assertFalse(viri_sink.zapis_androida_javen('{"password": "skrito-geslo"}'))
        self.assertFalse(viri_sink.zapis_androida_javen("//ponudnik.test/live/uporabnik/skrito-geslo/1.ts"))
        self.assertFalse(viri_sink.zapis_androida_javen(self.GSON))
        self.assertTrue(viri_sink.zapis_androida_javen('{"naslov": "Pesem", "avtor": "Pevka"}'))
        self.assertFalse(viri_sink.javna_slika("http://i.ytimg.com/vi/x/hq.jpg"))           # samo https
        self.assertFalse(viri_sink.javna_slika("https://i.ytimg.com.ponudnik.test/x.jpg"))


POT = "http://ponudnik.primer.test:8080/playlist/uporabnik/skrito-geslo/m3u_plus"
XTREAM_B = "http://drug.primer.test:8080/get.php?username=gost&password=skrito-geslo&type=m3u_plus"


class ZeRazposlaneKopije(unittest.TestCase):
    """Pregled 46, Ö3: starejse razlicice so vir z geslom dale vsem napravam s »Predvajalnik«; izbris vira z racunom
    zunaj ozjega kroga ne pride, zato ga je naprava obdrzala za vedno. Ob posodobitvi prejemnik prejete vire z racunom
    odstrani (brez zapisa izbrisa) in jih znova prevzame samo od naprave, ki ga ima v ozjem krogu; lastnik vira, ki je
    bil res ponujen navadnemu krogu, enkrat dobi opozorilo za menjavo gesla.
    Pregled 51, Ê2: opozorilo ne sme biti odvisno od javnega dela starega zapisa, od trenutnih naprav in od tega, da vir
    se obstaja; ne pokaze se samo, ce je dokazano, da vir nikoli ni sel ven (zapisa za naprave nikoli ni bilo ali vira
    nikoli nismo uspesno prebrali)."""

    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        kanal = [{"id": "k1", "iptv": True, "url": KANAL_XTREAM, "naslov": "Kanal"}]

        def vir(ident, url, **x):
            return dict({"id": ident, "url": url, "ime": ident, "stevilo": 3, "napaka": "", "dodan": 5, "vnosi": []}, **x)
        viri = [vir("lastni-xt", XTREAM, vnosi=kanal), vir("lastni-pot", POT, vnosi=kanal), vir("lastni-pod", PODKAST),
                vir("lastni-nov", "http://nov.primer.test/get.php?username=u&password=skrito-geslo", vnosi=kanal),
                vir("prejet-xt", XTREAM_B, link_naslov=XTREAM_B, link_tip="seznam"),
                vir("prejet-javni", JAVNI, link_naslov=JAVNI, link_tip="seznam")]
        strezniki = [{"id": "prejet-dodatek", "vrsta": "streznik", "ponudnik": "stremio", "ime": "Dodatek",
                      "url": "https://dodatek.primer.test", "link_naslov": "https://dodatek.primer.test/manifest.json",
                      "zaseben": False, "dodan": 5}]
        with open(os.path.join(self.mapa.name, "media.json"), "w", encoding="utf-8") as f:
            json.dump({"viri": viri, "osebni_strezniki": strezniki}, f)
        # Zapis starejse razlicice (brez delitve na »ozji«): vse je bilo ponujeno vsem napravam s Predvajalnik.
        with open(os.path.join(self.mapa.name, "viri_za_naprave.json"), "w", encoding="utf-8") as f:
            json.dump({"sources": [{"tip": "url", "ime": "", "naslov": n, "cas": 5}
                                   for n in (XTREAM, POT, PODKAST, XTREAM_B, JAVNI)], "sources_deleted": {}}, f)

    def _mc(self):
        # Brez zapisa dovoljenj naprav v Linku: opozorilo od trenutnih naprav ne zavisi (Ê2).
        return os_media.MediaCenter(self.mapa.name, roots=[])

    def _zapis(self, vsebina=None):
        pot = os.path.join(self.mapa.name, "viri_za_naprave.json")
        if vsebina is None:
            os.remove(pot)
        else:
            with open(pot, "w", encoding="utf-8") as f:
                f.write(vsebina if isinstance(vsebina, str) else json.dumps(vsebina))

    def test_prejeti_viri_z_racunom_gredo_brez_izbrisa(self):
        mc = self._mc()
        data = mc._load()
        self.assertEqual([v["id"] for v in data["viri"]], ["lastni-xt", "lastni-pot", "lastni-pod", "lastni-nov", "prejet-javni"])
        self.assertEqual(data["osebni_strezniki"], [])
        self.assertEqual(data["racuni_preseljeni"], os_media.MediaCenter.PRESELITEV_RACUNOV)
        # Brez zapisa izbrisa: izbris bi se razsiril nazaj na napravo, ki ga je poslala, in vir izbrisal lastniku.
        self.assertEqual(mc.viri_izvoz(ozji=True)["sources_deleted"], {})
        self.assertEqual(mc._viri_stanje()["izbrisani"], {})
        # Stari zapis za Control (geslo v javnem delu) je takoj zamenjan z razdeljenim.
        with open(os.path.join(self.mapa.name, "viri_za_naprave.json"), encoding="utf-8") as f:
            zapis = json.load(f)
        self.assertEqual([v["naslov"] for v in zapis["sources"]], [JAVNI])
        self.assertNotIn(XTREAM_B, json.dumps(zapis))

    def test_opozorilo_vsakemu_lastnemu_viru_z_geslom(self):
        mc = self._mc()
        opozorjeni = sorted(v["id"] for v in mc.sources() if v.get("deljeno_zunaj"))
        # Podkast nima gesla, prejetih ni vec. »lastni-nov« ni v starem zapisu, a to ne dokazuje, da ga ni dobila nobena
        # naprava (zapis se prepisuje ob spremembah): opozorilo (pregled 51, Ê2; prej samo xt in pot).
        self.assertEqual(opozorjeni, ["lastni-nov", "lastni-pot", "lastni-xt"])
        self.assertEqual(mc.potrdi_opozorilo_deljeno("lastni-xt"), {"ok": True})
        self.assertEqual(mc.potrdi_opozorilo_deljeno("ni-ga"), {"ok": False, "napaka": "ni_vira"})
        drugic = self._mc()                                     # naslednji zagon: selitev ne tece znova
        self.assertEqual(sorted(v["id"] for v in drugic.sources() if v.get("deljeno_zunaj")), ["lastni-nov", "lastni-pot"])

    def test_opozorilo_ne_zavisi_od_trenutnih_naprav(self):
        """Gost je bil ze odstranjen iz Linka (ali je dobil ozji krog), kopija gesla pa je se pri njem (Ê2)."""
        mc = self._mc()                                  # _mc: nobene naprave zunaj ozjega kroga
        self.assertTrue([v for v in mc.sources() if v.get("deljeno_zunaj")])
        self.assertNotIn("prejet-xt", [v["id"] for v in mc._load()["viri"]])

    def test_opozorilo_ko_je_stari_zapis_ze_razdeljen_ali_neberljiv(self):
        """Zapis iz razlicice 0f3f368 ima vir z geslom v delu »ozji«, ne v »sources«; neberljiv zapis ne dokazuje nic."""
        for vsebina in ({"sources": [], "sources_deleted": {},
                         "ozji": {"sources": [{"tip": "url", "ime": "", "naslov": XTREAM, "cas": 5}], "sources_deleted": {}}},
                        "{ni json", "[]", {}):
            with self.subTest(vsebina=str(vsebina)[:40]):
                self.setUp()
                self._zapis(vsebina)
                opozorjeni = sorted(v["id"] for v in self._mc().sources() if v.get("deljeno_zunaj"))
                self.assertEqual(opozorjeni, ["lastni-nov", "lastni-pot", "lastni-xt"])

    def test_brez_zapisa_za_naprave_je_dokazano_da_ni_sel_ven(self):
        """Nobene razlicice, ki bi zapis pisala, ni bilo: Control ni imel kaj ponuditi (core/link_seznami.py bere samo
        ta zapis), zato opozorila ni. Prejeti viri z geslom gredo z naprave vseeno."""
        self._zapis(None)
        mc = self._mc()
        self.assertEqual([v["id"] for v in mc.sources() if v.get("deljeno_zunaj")], [])
        self.assertNotIn("prejet-xt", [v["id"] for v in mc._load()["viri"]])

    def test_vir_ki_ga_nikoli_nismo_prebrali_ni_bil_ponujen(self):
        with open(os.path.join(self.mapa.name, "media.json"), encoding="utf-8") as f:
            data = json.load(f)
        data["viri"].append({"id": "nikoli", "url": XTREAM_B.replace("drug", "nov"), "ime": "n", "stevilo": 0,
                             "posodobljeno": 0, "napaka": "", "dodan": 5, "vnosi": []})
        with open(os.path.join(self.mapa.name, "media.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)
        opozorjeni = sorted(v["id"] for v in self._mc().sources() if v.get("deljeno_zunaj"))
        self.assertEqual(opozorjeni, ["lastni-nov", "lastni-pot", "lastni-xt"])

    IZBRISAN = "http://izbrisan.primer.test:8080/get.php?username=u&password=skrito-geslo&type=m3u_plus"

    def _izbrisani(self, kljuci):
        with open(os.path.join(self.mapa.name, "viri_sink.json"), "w", encoding="utf-8") as f:
            json.dump({"izbrisani": kljuci, "zavrnjeni": {}}, f)

    def test_izbrisan_vir_z_geslom_da_eno_splosno_opozorilo(self):
        """Lastnik je vir z geslom ze izbrisal, kopija pri gostu pa ostane (izbris z geslom zunaj ozjega kroga ni sel):
        vira ni vec, opozorilo je eno splosno (Ê2)."""
        self._izbrisani({"url|" + self.IZBRISAN: 9, "url|" + PODKAST: 8})
        mc = self._mc()
        self.assertEqual(mc.opozorila_virov(), {"izbrisani": True})
        self.assertEqual(self._mc().opozorila_virov(), {"izbrisani": True})          # dokler ga lastnik ne potrdi
        self.assertEqual(mc.potrdi_opozorilo_deljeno("*"), {"ok": True})
        self.assertEqual(mc.opozorila_virov(), {"izbrisani": False})
        self.assertEqual(self._mc().opozorila_virov(), {"izbrisani": False})         # nikoli vec

    def test_izbrisan_podkast_ali_brez_zapisa_ni_opozorila(self):
        self._izbrisani({"url|" + PODKAST: 8, "url|" + JAVNI: 7})
        self.assertEqual(self._mc().opozorila_virov(), {"izbrisani": False})
        self.setUp()
        self._izbrisani({"url|" + self.IZBRISAN: 9})
        self._zapis(None)                                # zapisa nikoli ni bilo: ni sel ven
        self.assertEqual(self._mc().opozorila_virov(), {"izbrisani": False})

    def test_selitev_samo_enkrat(self):
        self._mc()
        with open(os.path.join(self.mapa.name, "media.json"), encoding="utf-8") as f:
            data = json.load(f)
        data["viri"].append({"id": "spet", "url": XTREAM_B, "link_naslov": XTREAM_B, "stevilo": 3, "vnosi": []})
        with open(os.path.join(self.mapa.name, "media.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)          # znova prevzet od naprave, ki nas ima v ozjem krogu
        self.assertIn("spet", [v["id"] for v in self._mc()._load()["viri"]])

    def test_nova_namestitev_ne_seli(self):
        with tempfile.TemporaryDirectory() as prazna:
            mc = os_media.MediaCenter(prazna, roots=[])
            self.assertFalse(os.path.exists(os.path.join(prazna, "media.json")))
            with mc._lock:
                data = mc._load()
                data["viri"].append({"id": "p", "url": XTREAM_B, "link_naslov": XTREAM_B, "vnosi": []})
                mc._save(data)
            self.assertEqual(os_media.MediaCenter(prazna, roots=[])._load()["viri"][0]["id"], "p")

    def test_prevzem_po_odgovoru_naprave(self):
        with tempfile.TemporaryDirectory() as prazna:
            mc = os_media.MediaCenter(prazna, roots=[])
            viri = [{"tip": "seznam", "ime": "", "naslov": n, "cas": 9} for n in (XTREAM, POT, JAVNI)]
            for ozji, pricakovano in ((None, [JAVNI]), (False, [JAVNI]), (True, [XTREAM, POT, JAVNI])):    # Ê3: None kot false
                klici = []
                kazalo = dict({"sources": viri, "sources_deleted": {}}, **({} if ozji is None else {"ozji": ozji}))
                with mock.patch.object(mc, "_prevzemi_vir", lambda v: klici.append(v["naslov"]) or (False, 0)):
                    mc.viri_uskladi(kazalo)
                self.assertEqual(klici, pricakovano, ozji)

    def test_odgovor_pove_ozji_krog(self):
        mc = self._mc()
        for ozji in (False, True):
            kazalo = link_seznami.izvoz({}, self.mapa.name, ozji=ozji)
            self.assertIs(kazalo["ozji"], ozji)
            self.assertEqual(kazalo, mc.seznami_izvoz({}, ozji=ozji))
        self.assertNotIn("ozji", link_seznami.izvoz({"ime": "x"}, self.mapa.name))

    def test_opozorilo_na_strani(self):
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "assets", "os", "os.js"), encoding="utf-8") as f:
            js = f.read()
        with open(os.path.join(koren, "assets", "os", "besedila.js"), encoding="utf-8") as f:
            besedila = f.read()
        with open(os.path.join(koren, "core", "os_katalog.py"), encoding="utf-8") as f:
            katalog = f.read()
        self.assertIn('klic("mediaPotrdiOpozorilo", [source.id])', js)
        self.assertIn('if (source.deljeno_zunaj) {', js)
        self.assertIn('"mediaPotrdiOpozorilo": "_potrdi_opozorilo"', katalog)
        self.assertIn('"mediaOpozorilaViri": "_opozorila_virov"', katalog)           # splosno opozorilo za izbrisane (Ê2)
        self.assertIn('klic("mediaOpozorilaViri")', js)
        self.assertIn('klic("mediaPotrdiOpozorilo", ["*"])', js)
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            self.assertRegex(besedila, r"BESEDILA_OS\.%s, \{\"katVirGesloDeljeno\": \"[^\"]{40,}\", \"katVirGesloRazumem\"" % jezik)
            self.assertRegex(besedila, r"BESEDILA_OS\.%s, \{[^\n]*\"katVirGesloDeljenoIzbrisan\": \"[^\"]{40,}\"" % jezik)


class PrejetiViriNeGredoNaprej(unittest.TestCase):
    """Pregled 51, Ê4: ozji krog je dolocen na vsako napravo posebej (core/link_dostop.py). Vir z geslom, ki ga je ta
    naprava dobila od druge naprave, ne sme iti naprej v NJEN ozji krog - tam je lahko naprava, ki je lastnik vira ne
    pozna (skupni TV pri prenosniku). Naprej gre samo lastni vir in pozitivno znan javen."""

    def test_prejet_vir_z_geslom_ne_gre_v_izvoz(self):
        with tempfile.TemporaryDirectory() as mapa:
            def vir(ident, url, **x):
                return dict({"id": ident, "url": url, "ime": ident, "stevilo": 3, "napaka": "", "dodan": 5, "vnosi": []}, **x)
            viri = [vir("lastni", XTREAM), vir("prejet", XTREAM_B, link_naslov=XTREAM_B, link_tip="seznam"),
                    vir("prejet-javni", JAVNI, link_naslov=JAVNI, link_tip="seznam")]
            strezniki = [{"id": "dodatek-lastni", "vrsta": "streznik", "ponudnik": "stremio", "ime": "L", "zaseben": False,
                          "url": "https://lastni.primer.test", "dodan": 5},
                         {"id": "dodatek-prejet", "vrsta": "streznik", "ponudnik": "stremio", "ime": "P", "zaseben": False,
                          "url": "https://prejet.primer.test/realdebrid=skrito-geslo", "dodan": 5,
                          "link_naslov": "https://prejet.primer.test/realdebrid=skrito-geslo/manifest.json"}]
            with open(os.path.join(mapa, "media.json"), "w", encoding="utf-8") as f:
                json.dump({"viri": viri, "osebni_strezniki": strezniki, "racuni_preseljeni": 1}, f)
            mc = os_media.MediaCenter(mapa, roots=[])
            naslovi = sorted(v["naslov"] for v in mc.viri_izvoz(ozji=True)["sources"])
            self.assertEqual(naslovi, sorted([XTREAM, JAVNI, "https://lastni.primer.test/manifest.json"]))
            mc._viri_zapisi_izvoz()                                  # zapis za Control je enak
            with open(os.path.join(mapa, "viri_za_naprave.json"), encoding="utf-8") as f:
                zapis = f.read()
            for tuje in ("username=gost", "realdebrid"):
                self.assertNotIn(tuje, zapis)
                self.assertNotIn(tuje, json.dumps(mc.viri_izvoz(ozji=True)))


class GesloNiVPodatkihStrani(unittest.TestCase):
    """Pregled 46, Ö8: popravek VISOKE je naslov zakril samo v vrstici Virov - cel naslov z geslom je bil se vedno v
    podatkih strani (sources(): url, link_naslov; napaka z naslovom). Pregled 46, Ö4: viri_za_naprave.json (del
    »ozji« ima geslo) je 0600 kot media.json."""

    DODATEK = "https://dodatek.primer.test/realdebrid=skrito-geslo/manifest.json"

    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        viri = [{"id": "xt", "url": XTREAM, "ime": "Ponudnik", "stevilo": 3, "napaka": "", "vnosi": [], "dodan": 5},
                {"id": "pot", "url": POT, "ime": "Pot", "stevilo": 3, "napaka": "", "vnosi": [], "dodan": 5},
                {"id": "prejet", "url": XTREAM_B, "link_naslov": XTREAM_B, "ime": "Prejet", "stevilo": 3, "dodan": 5,
                 "napaka": "", "vnosi": []},
                {"id": "pub", "url": JAVNI, "ime": "Javni", "stevilo": 3, "napaka": "", "vnosi": [], "dodan": 5}]
        strezniki = [{"id": "dod", "vrsta": "streznik", "ponudnik": "stremio", "ime": "Dodatek", "url": self.DODATEK,
                      "zaseben": False, "dodan": 5}]
        with open(os.path.join(self.mapa.name, "media.json"), "w", encoding="utf-8") as f:
            json.dump({"viri": viri, "osebni_strezniki": strezniki, "racuni_preseljeni": 1}, f)
        self.mc = os_media.MediaCenter(self.mapa.name, roots=[])

    def test_podatki_strani_brez_gesla(self):
        from core import os_katalog
        k = os_katalog.Katalog(self.mapa.name, lambda *a: None, lambda f: f(), lambda *a, **kw: True, lambda u: True,
                               lambda *a: True, lambda u: True)
        k._mc = self.mc
        for viri in (k._viri([]), self.mc.vidni_viri()):
            self.assertNotIn("skrito-geslo", json.dumps(viri))
            po_id = {v["id"]: v for v in viri}
            self.assertEqual((po_id["xt"]["url_prikaz"], po_id["dod"]["url_prikaz"]), ("ponudnik.test:8080", "dodatek.primer.test"))
            self.assertEqual((po_id["pub"]["url"], po_id["pub"]["url_prikaz"]), (JAVNI, JAVNI))
        # Predvajanje in osvezitev imata naslov v Medijskem centru.
        self.assertIn(XTREAM, [v.get("url") for v in self.mc.sources()])

    def test_napaka_brez_naslova(self):
        self.mc._download = lambda url: (_ for _ in ()).throw(ValueError("unknown url type: %r" % url))
        self.assertFalse(self.mc.refresh_source("xt")["ok"])
        napaka = next(v for v in self.mc._load()["viri"] if v["id"] == "xt")["napaka"]
        self.assertIn("ponudnik.test:8080", napaka)
        self.assertNotIn("skrito-geslo", napaka)

    def test_zapis_za_naprave_samo_lastniku(self):
        self.mc._viri_zapisi_izvoz()
        self.assertEqual(os.stat(os.path.join(self.mapa.name, "viri_za_naprave.json")).st_mode & 0o777, 0o600)


class ControlTests(unittest.TestCase):
    def test_control_odgovori_na_lists_get(self):
        izidi = []
        with tempfile.TemporaryDirectory() as mapa, mock.patch.object(link_seznami, "mapa", return_value=mapa):
            with open(os.path.join(mapa, "seznami.json"), "w", encoding="utf-8") as f:
                json.dump([{"ime": "A", "cas": 7, "skladbe": SKLADBE[:3]}], f)
            link_daljinec.izvedi_control("lists.get", {}, lambda _u: None, izidi.append)
            link_daljinec.izvedi_control("lists.get", {"ime": "A", "od": 1}, lambda _u: None, izidi.append)
        self.assertTrue(izidi[0]["ok"])
        self.assertEqual(izidi[0]["data"]["lists"], [{"ime": "A", "vir": "", "cas": 7, "stevilo": 3}])
        self.assertEqual([s["naslov"] for s in izidi[1]["data"]["skladbe"]], ["Pesem 1", "Pesem 2"])

    def test_zmoznost_in_dejanje_samo_s_safeer_os(self):
        """Seznami so v Medijskem centru Safeer OS: brez njega Control zmoznosti "lists" ne oglasa."""
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "safeer_link.py"), encoding="utf-8") as f:
            koda = f.read()
        self.assertIn('(["lists"] if self.control and _magnet_na_voljo() else [])', koda)
        for os_namescen, pricakovano in (("/usr/bin/safeer-os", True), ("", False)):
            izidi = []
            with mock.patch.object(link_daljinec, "_safeer_os", return_value=os_namescen), \
                    mock.patch.object(link_daljinec, "_glasnost", return_value={"ok": False}):
                link_daljinec.izvedi_control("status", {}, lambda _u: None, izidi.append)
            self.assertEqual("lists.get" in izidi[0]["data"]["actions"], pricakovano)


class SafeerOsTests(unittest.TestCase):
    def test_vprasa_samo_naprave_ki_znajo_sezname(self):
        import safeer_os
        naprave = {"ok": True, "naprave": [
            {"id": "ta", "ta": True, "zmoznosti": ["remote", "lists"]},
            {"id": "telefon", "zmoznosti": ["url", "remote", "lists"]},
            {"id": "stara-tv", "zmoznosti": ["url", "remote"]},
            {"id": "brez-daljinca", "zmoznosti": ["lists"]},
        ]}
        klici = []

        def control(metoda, *a):
            klici.append((metoda, *a))
            if metoda == "Seznam":
                return naprave
            return {"ok": True, "data": {"lists": [], "deleted": {}}} if a[0] == "telefon" else {"ok": False}

        vprasani = []

        def uskladi(vprasaj):
            vprasani.append(vprasaj({}))
            return True
        with mock.patch.object(safeer_os, "_control_na_vodilu", return_value=True), \
                mock.patch.object(safeer_os.Gio, "bus_get_sync", return_value=object()), \
                mock.patch.object(safeer_os, "_control_naprave", side_effect=control):
            self.assertTrue(safeer_os._seznami_z_naprav(uskladi))
        self.assertEqual(vprasani, [{"lists": [], "deleted": {}}])
        self.assertEqual(klici, [("Seznam",), ("Ukaz", "telefon", "lists.get", "{}")])

    def test_controla_zaradi_seznamov_ne_zazene(self):
        import safeer_os
        with mock.patch.object(safeer_os, "_control_na_vodilu", return_value=False), \
                mock.patch.object(safeer_os.Gio, "bus_get_sync", return_value=object()), \
                mock.patch.object(safeer_os, "_control_naprave", side_effect=AssertionError("Control se ne sme zagnati")):
            self.assertFalse(safeer_os._seznami_z_naprav(lambda _v: True))


if __name__ == "__main__":
    unittest.main()
