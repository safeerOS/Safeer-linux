"""Seznami predvajanja med napravami v Safeer Linku na Linuxu: Control odgovarja (lists.get), Safeer OS prevzema."""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
from unittest import mock

import pytest

from core import link_daljinec, link_dostop, link_seznami, os_media, seznami_sink, viri_sink
from tests.test_link_dostop import A, B, _Osnova

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

    def test_pokvarjen_zapis_ne_sesuje_medijskega_centra(self):
        """Pregled 51, Ê7: ne-stevilska oznaka selitve ali vnosi, ki niso seznam, so sesuli konstruktor; nedosegljiv
        media.json je selitev trajno preskocil (oznaka se je zapisala ob prvem shranjevanju)."""
        pot = os.path.join(self.mapa.name, "media.json")
        with open(pot, encoding="utf-8") as f:
            data = json.load(f)
        data["racuni_preseljeni"] = "abc"
        data["viri"][0]["vnosi"] = 5
        data["viri"][1]["stevilo"] = "x"
        with open(pot, "w", encoding="utf-8") as f:
            json.dump(data, f)
        mc = os_media.MediaCenter(self.mapa.name, roots=[])         # prej: ValueError iz konstruktorja
        self.assertNotIn("prejet-xt", [v["id"] for v in mc._load()["viri"]])
        self.assertEqual(mc._load()["racuni_preseljeni"], os_media.MediaCenter.PRESELITEV_RACUNOV)

    def test_nedosegljiv_zapis_selitev_odlozi_na_naslednji_zagon(self):
        pot = os.path.join(self.mapa.name, "media.json")
        os.replace(pot, pot + ".shranjen")
        os.mkdir(pot)                                               # OSError (IsADirectoryError), ne ValueError
        mc = os_media.MediaCenter(self.mapa.name, roots=[])
        self.assertFalse(mc._racuni_preseljeni)                     # oznaka se ne zapise: selitev ni stekla
        os.rmdir(pot)
        os.replace(pot + ".shranjen", pot)
        self.assertNotIn("prejet-xt", [v["id"] for v in self._mc()._load()["viri"]])      # ob naslednjem zagonu steče

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
            # Ê3: None kot false. Pregled 68, Ą3: »ozji« true brez dokaza (posiljatelj ni v ozjem krogu te naprave) kot false.
            for ozji, posiljatelj, pricakovano in ((None, "telefon", [JAVNI]), (False, "telefon", [JAVNI]),
                                                   (True, "", [JAVNI]), (True, "telefon", [XTREAM, POT, JAVNI])):
                klici = []
                kazalo = dict({"sources": viri, "sources_deleted": {}}, **({} if ozji is None else {"ozji": ozji}))
                with mock.patch.object(mc, "_prevzemi_vir", lambda v: klici.append(v["naslov"]) or (False, 0)):
                    mc.viri_uskladi(kazalo, posiljatelj)
                self.assertEqual(klici, pricakovano, (ozji, posiljatelj))

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


class _PrejetOsnova(unittest.TestCase):
    """Skupna priprava za preizkuse prejetih virov z racunom: sredisce brez omrezja, ki steje vsako povezavo."""

    LIST = b'#EXTM3U\n#EXTINF:-1 tvg-id="K1.si",Kanal 1\nhttp://ponudnik.test:8080/live/u/g/1.ts\n'

    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.mc = os_media.MediaCenter(self.mapa.name, roots=[])
        self.mc._kanali_spremenjeni = lambda viri=False: None
        self.povezave = []

        def prenesi(url):
            self.povezave.append(("prenos", url))
            return self.LIST, "audio/x-mpegurl", url
        self.mc._download = prenesi
        self.mc._izmeri_ping = lambda url: self.povezave.append(("ping", url))

        def omrezje(*a, **k):
            self.povezave.append(("omrezje", str(a)[:60]))
            raise OSError("preizkus: brez omrezja")
        for ime, cilj in (("socket.create_connection", omrezje), ("urllib.request.urlopen", omrezje)):
            zaplata = mock.patch(ime, cilj)
            zaplata.start()
            self.addCleanup(zaplata.stop)
        zaplata = mock.patch.object(os_media, "_resolve_embed_or_direct_source",
                                    lambda *a, **k: self.povezave.append(("rezerva", a[0])) or [])
        zaplata.start()
        self.addCleanup(zaplata.stop)

    def _prejmi(self, *viri, ozji=True, posiljatelj="telefon"):
        """`posiljatelj`: id naprave, ki odgovarja; preizkusi (conftest) imajo vsako izmisljeno napravo v ozjem krogu."""
        kazalo = {"sources": [{"tip": t, "ime": "TV", "naslov": n, "cas": 9} for t, n in viri], "sources_deleted": {},
                  "ozji": ozji}
        self.assertTrue(self.mc.viri_uskladi(kazalo, posiljatelj))

    def _prejmi_neznan(self, *viri):
        """Vir brez dokaza o ozjem krogu (add_source brez ozji_krog): fail-closed, caka uporabnikovo osvezitev."""
        for tip, naslov in viri:
            self.assertTrue(self.mc.add_source(naslov, "TV", prevzet={"tip": tip, "naslov": naslov, "cas": 9})["ok"])

    def _viri(self):
        return {v["link_naslov"]: v for v in self.mc._load()["viri"]}

    def _iztekel_premor(self, ident):
        """Premor po zavrnitvi je pretekel (pregled 68, Ą5: tudi uporabnikov »Osvezi« ga spostuje)."""
        podatki = self.mc._load()
        for v in podatki["viri"]:
            if v["id"] == ident and isinstance(v.get("zavrnjen"), dict):
                v["zavrnjen"]["ob"] = 1
        self.mc._save(podatki)


class PrejetSeznamZRacunom(_PrejetOsnova):
    """Pregled 51, Ñ2 (z Androida): vir z racunom, ki ga naprava prejme z druge naprave (lists.get, »ozji«), se ob prejemu
    NE prenese - sicer bi vsaka naprava v krogu ob prvem usklajevanju poslala ponudniku zahtevo z geslom (zaklep racuna
    ali IP). Prenese ga naprava, kjer je bil dodan; druge, ko uporabnik osvezi vir (gumb »Osvezi«); samodejno
    osvezevanje cakajocega vira ne vidi, premor zavrnitve (I5) velja naprej."""

    def test_prejem_vira_z_racunom_ne_odpre_nobene_povezave(self):
        self._prejmi_neznan(("seznam", XTREAM_B), ("url", POT), ("seznam", "http://kratka.primer.test/abc"))
        self.assertEqual(self.povezave, [])
        viri = self._viri()
        self.assertEqual(sorted(viri), sorted([XTREAM_B, POT, "http://kratka.primer.test/abc"]))      # shranjeni, ne preskoceni
        self.assertTrue(all(v.get("caka_uporabnika") for v in viri.values()))
        self.assertTrue(all(v["stevilo"] == 0 and not v["vnosi"] and not v["napaka"] for v in viri.values()))
        # Vir brez prenosa ni ponudba naprej (Ê4) in cakajocega ne preverjajo samodejni poti.
        self.assertEqual(self.mc.viri_izvoz(ozji=True)["sources"], [])
        self.mc.refresh_stale(max_age=60)
        self.mc._vnosi_virov(self.mc._load(), "tv-v-zivo")
        for nit in threading.enumerate():
            if nit.name == "media-razclenitev":
                nit.join(5)
        self.assertEqual(self.povezave, [])

    def test_znan_javni_seznam_se_prenese_takoj(self):
        self._prejmi(("seznam", JAVNI))
        self.assertEqual([p for p in self.povezave if p[0] == "prenos"], [("prenos", JAVNI)])
        vir = self._viri()[JAVNI]
        self.assertEqual((vir["stevilo"], "caka_uporabnika" in vir), (1, False))

    def test_vir_neprepoznane_oblike_caka_ne_glede_na_vrsto(self):
        """Pregled 57, Ş1: odlocala je hevristika oblike naslova ali vrsta »seznam«: kratka povezava, zeton v poti in
        .../x.m3u vrste »url« so se ob prejemu takoj prenesli na vsaki napravi v ozjem krogu (zaklep racuna pri
        ponudniku). Zdaj caka vsak prejet vir, ki ni POZITIVNO znan javen - vrste, ki jo poslje druga naprava, ne
        presojamo (tudi »podkast« in »tok« ne)."""
        naslovi = ["http://kratka.primer.test/abc", "http://ponudnik.primer.test:8080/7f3a9c1e5b2d/tv",
                   "http://ponudnik.primer.test:8080/zeton123.m3u", "https://ponudnik.primer.test/m3u/zeton123.m3u",
                   "http://ponudnik.primer.test/c/00:1A:79:00:00:01", PODKAST, "https://podkast.primer.si/zasebno/zeton123"]
        for tip in ("url", "seznam", "podkast", "tok", "tok-hls"):
            for naslov in naslovi:
                with self.subTest(tip=tip, naslov=naslov):
                    self.setUp()
                    self._prejmi_neznan((tip, naslov))
                    self.assertEqual(self.povezave, [])                  # ne prenos, ne ping, ne rezerva, ne omrezje
                    vir = self._viri()[naslov]
                    self.assertTrue(vir.get("caka_uporabnika"), vir)
                    self.assertEqual((vir["stevilo"], vir["vnosi"], vir["napaka"]), (0, [], ""))
                    self.assertEqual(self.mc.viri_izvoz(ozji=True)["sources"], [])
                    self.mc.refresh_stale(max_age=60)
                    self.assertEqual(self.mc.refresh_all()["rezultati"], [])        # skupna osvezitev tudi ne
                    self.assertEqual(self.povezave, [])

    def test_znan_javni_vir_se_prenese_ne_glede_na_vrsto(self):
        for tip in ("url", "seznam"):
            with self.subTest(tip=tip):
                self.setUp()
                self._prejmi((tip, JAVNI))
                self.assertEqual([p for p in self.povezave if p[0] == "prenos"], [("prenos", JAVNI)])
                self.assertNotIn("caka_uporabnika", self._viri()[JAVNI])

    def test_uporabnikova_osvezitev_cakajocega_podkasta_prenese_enkrat(self):
        self._prejmi_neznan(("podkast", PODKAST))
        self.assertEqual(self.povezave, [])
        ident = self._viri()[PODKAST]["id"]
        self.assertTrue(self.mc.refresh_source(ident)["ok"])
        self.assertEqual([p[0] for p in self.povezave], ["prenos"])
        self.assertNotIn("caka_uporabnika", self._viri()[PODKAST])

    def test_lastni_vir_z_racunom_se_prenese_takoj(self):
        self.assertTrue(self.mc.add_source(XTREAM, "Moj")["ok"])
        self.assertEqual([p[0] for p in self.povezave if p[0] == "prenos"], ["prenos"])
        self.assertNotIn("caka_uporabnika", self.mc._load()["viri"][0])

    def test_uporabnikova_osvezitev_prenese_enkrat(self):
        self._prejmi_neznan(("seznam", XTREAM_B))
        ident = self._viri()[XTREAM_B]["id"]
        self.assertEqual(self.povezave, [])
        self.assertTrue(self.mc.refresh_source(ident)["ok"])
        self.assertEqual(self.povezave, [("prenos", self.mc._load()["viri"][0]["url"])])         # ena zahteva, uporabnikova
        vir = self._viri()[XTREAM_B]
        self.assertEqual((vir["stevilo"], "caka_uporabnika" in vir), (1, False))
        # Naslednja usklajevanja ne podvojijo in ne prenesejo znova.
        self.povezave.clear()
        self.assertFalse(self.mc.viri_uskladi({"sources": [{"tip": "seznam", "ime": "", "naslov": XTREAM_B, "cas": 9}],
                                               "sources_deleted": {}, "ozji": True}, "telefon"))
        self.assertEqual(self.povezave, [])

    def test_osvezitev_ki_ponudnik_zavrne_ima_premor(self):
        self._prejmi_neznan(("seznam", XTREAM_B))
        ident = self._viri()[XTREAM_B]["id"]
        self.mc._download = lambda url: (_ for _ in ()).throw(urllib.error.HTTPError(url, 403, "Forbidden", None, None))
        self.assertFalse(self.mc.refresh_source(ident)["ok"])
        vir = self._viri()[XTREAM_B]
        self.assertEqual((vir["zavrnjen"]["koda"], "caka_uporabnika" in vir), (403, True))      # Ş6: ostane
        self.assertGreater(self.mc._zavrnjen_do(vir), __import__("time").time())

    def test_neuspesna_osvezitev_ne_odstrani_oznake_caka(self):
        """Pregled 57, Ş6: oznaka »caka« je odpadla ze ob neuspeli osvezitvi, zato je refresh_stale vir od takrat sam
        ponavljal (pri kodi 0 vsakih 10 min, prvi dve napaki brez premora): naprava, ki racuna nikoli ni prebrala,
        je postala samodejni odjemalec racuna v tezavah. Oznako odstrani sele uspesna osvezitev."""
        self._prejmi_neznan(("seznam", XTREAM_B))
        ident = self._viri()[XTREAM_B]["id"]
        for napaka in (OSError("preizkus: brez povezave"), urllib.error.HTTPError("x", 500, "Napaka", None, None),
                       ValueError("preizkus: vir je prevelik")):
            with self.subTest(napaka=type(napaka).__name__):
                def prenesi(url, n=napaka):
                    self.povezave.append(("prenos", url))
                    raise n
                self.mc._download = prenesi
                self.povezave.clear()
                self._iztekel_premor(ident)
                self.assertFalse(self.mc.refresh_source(ident)["ok"])
                self.assertEqual(len(self.povezave), 1)                 # uporabnikova osvezitev: ena zahteva
                vir = self._viri()[XTREAM_B]
                self.assertTrue(vir.get("caka_uporabnika"), vir)
                self.assertTrue(vir["napaka"])                           # stran pokaze napako, ne »caka«
                self.povezave.clear()
                self.mc.refresh_stale(max_age=60)
                self.mc._vnosi_virov(self.mc._load(), "tv-v-zivo")
                for nit in threading.enumerate():
                    if nit.name == "media-razclenitev":
                        nit.join(5)
                self.assertEqual(self.povezave, [])                      # samodejna pota ga se vedno preskocita
        self.mc._download = lambda url: (self.LIST, "audio/x-mpegurl", url)
        self._iztekel_premor(ident)
        self.assertTrue(self.mc.refresh_source(ident)["ok"])
        vir = self._viri()[XTREAM_B]
        self.assertEqual(("caka_uporabnika" in vir, vir["stevilo"], vir["napaka"]), (False, 1, ""))

    def test_stran_pove_da_seznam_caka(self):
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "assets", "os", "os.js"), encoding="utf-8") as f:
            js = f.read()
        with open(os.path.join(koren, "assets", "os", "besedila.js"), encoding="utf-8") as f:
            besedila = f.read()
        self.assertIn("source.caka_uporabnika", js)
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            self.assertRegex(besedila, r"BESEDILA_OS\.%s, \{[^\n]*\"katVirCaka\": \"[^\"]{40,}\"" % jezik)


class VirIzOzjegaKroga(_PrejetOsnova):
    """Lastnik, 26. 10. 2026 (vse naprave pripadajo uporabniku): prejet vir z racunom ali neznane oblike od naprave, ki nas
    ima v ozjem krogu, ne caka vec na »Osvezi«: viden je takoj, v ozadju se ne osvezuje, prva povezava (ena) je ob odprtju
    seznama na tej napravi, nato 24-urni predpomnilnik in najvec ena osvezitev na minuto; premor po napaki ostane. Brez
    dokaza o ozjem krogu ostane fail-closed (caka; razred PrejetSeznamZRacunom, ki ga ta podeduje, tega ne spreminja)."""

    NASLOVI = (("seznam", XTREAM_B), ("url", POT), ("seznam", "http://kratka.primer.test/abc"), ("podkast", PODKAST))

    def _pocakaj_niti(self):
        for nit in threading.enumerate():
            if nit.name in ("media-razclenitev", "media-prva-uporaba"):
                nit.join(5)

    def _odpri_katalog(self):
        """Uporabnik odpre vir (gumb »Odpri« v Virih, MediaCenter.odpri_vir); katalog sam povezave ne sprozi (Ą4)."""
        for v in self.mc._load()["viri"]:
            self.mc.odpri_vir(v["id"])
        self._pocakaj_niti()

    def _vir(self, naslov=XTREAM_B):
        return self._viri()[naslov]

    def _prenosi(self):
        return [p for p in self.povezave if p[0] == "prenos"]

    def test_vir_je_viden_takoj_in_brez_povezav_v_ozadju(self):
        self._prejmi(*self.NASLOVI, ozji=True)
        self.assertEqual(self.povezave, [])                          # ne prenos, ne ping, ne rezerva, ne omrezje
        viri = self._viri()
        self.assertEqual(sorted(viri), sorted(n for _t, n in self.NASLOVI))        # shranjeni in vidni
        for naslov, vir in viri.items():
            with self.subTest(naslov=naslov):
                self.assertTrue(vir.get("prvo_uporaba"), vir)
                self.assertTrue(vir.get("ozji_krog"), vir)
                self.assertNotIn("caka_uporabnika", vir)             # ne caka na »Osvezi«
                self.assertEqual((vir["stevilo"], vir["vnosi"], vir["napaka"]), (0, [], ""))
        self.assertTrue(all(v.get("prvo_uporaba") for v in self.mc.sources()))      # stran dobi stanje
        # Samodejne poti: nobene povezave (refresh_all, refresh_stale, iskalnik in stevci s preveri=False).
        self.mc.refresh_stale(max_age=60)
        self.assertEqual(self.mc.refresh_all()["rezultati"], [])
        self.mc._vnosi_virov(self.mc._load(), "tv-v-zivo", preveri=False)
        self.mc._vnosi_virov(self.mc._load(), "vse", preveri=False)
        self._pocakaj_niti()
        self.assertEqual(self.povezave, [])

    def test_prva_povezava_ob_odprtju_seznama_je_ena(self):
        self._prejmi(("seznam", XTREAM_B), ozji=True)
        url = self.mc._load()["viri"][0]["url"]
        self.assertEqual(self.povezave, [])
        for _ in range(3):                                           # trikrat zapored odprt vir = ena zahteva
            self.mc.odpri_vir(self._vir()["id"])
        self._pocakaj_niti()
        self.assertEqual([p[0] for p in self.povezave], ["prenos"], self.povezave)
        self.assertEqual(self._prenosi(), [("prenos", url)])
        vir = self._vir()
        self.assertEqual((vir["stevilo"], vir["napaka"], "prvo_uporaba" in vir, vir["ozji_krog"]), (1, "", False, True))
        self._odpri_katalog()
        self.assertEqual(len(self._prenosi()), 1)                    # po uspehu ne znova

    def test_katalog_ne_sprozi_povezave_nobenega_vira(self):
        """Pregled 68, Ą4: odprtje katere koli kategorije kataloga je prijavilo VSE cakajoce vire hkrati. Povezavo sprozi
        samo uporabnikovo odprtje tega vira (odpri_vir)."""
        self._prejmi(("seznam", XTREAM_B), ("url", POT), ("podkast", PODKAST), ozji=True)
        for kategorija in ("tv-v-zivo", "film", "glasba", "podkast", "vse"):
            self.mc._vnosi_virov(self.mc._load(), kategorija)
        self._pocakaj_niti()
        self.assertEqual(self.povezave, [])
        viri = self._viri()
        self.assertTrue(all(v.get("prvo_uporaba") for v in viri.values()))
        self.assertTrue(self.mc.odpri_vir(viri[POT]["id"])["zacet"])               # uporabnik odpre samo ta vir
        self._pocakaj_niti()
        self.assertEqual([p[0] for p in self.povezave], ["prenos"])
        self.assertEqual(self.povezave[0][1], viri[POT]["url"])
        po_odprtju = self._viri()
        self.assertEqual([k for k, v in po_odprtju.items() if v.get("prvo_uporaba")], [XTREAM_B, PODKAST])   # ostala cakata

    def test_odprtje_kategorije_sprozi_povezavo_samo_za_vire_te_kategorije(self):
        """Pregled 68, Ą4 (z uporabnikove strani, kot Android): uporabnik odpre TV v zivo in pricakuje svoje kanale. Prvo
        povezavo sprozi odprtje KATEGORIJE vira (seznam IPTV - TV v zivo, podkast - Glasba), samo za vire te kategorije;
        druga kategorija = 0 povezav; ponovno odprtje ne naredi nove zahteve (premor, 1/min)."""
        self._prejmi(("seznam", XTREAM_B), ("podkast", PODKAST), ozji=True)
        for druga in ("film", "serija", "radio", "vse", ""):
            self.assertEqual(self.mc.odpri_kategorijo(druga)["zacetih"], 0, druga)
        self._pocakaj_niti()
        self.assertEqual(self.povezave, [])                          # druga kategorija = 0 povezav
        self.assertEqual(self.mc.odpri_kategorijo("tv-v-zivo")["zacetih"], 1)
        self._pocakaj_niti()
        self.assertEqual(self._prenosi(), [("prenos", self._vir()["url"])])        # IPTV vir iz kroga = 1 povezava
        self.assertEqual(len(self.povezave), 1, self.povezave)       # podkast (Glasba) se ni dotaknil
        viri = self._viri()
        self.assertNotIn("prvo_uporaba", viri[XTREAM_B])
        self.assertTrue(viri[PODKAST].get("prvo_uporaba"))
        for _ in range(3):                                           # klik na zavihek znova in znova: brez nove zahteve
            self.mc.odpri_kategorijo("tv-v-zivo")
        self._pocakaj_niti()
        self.assertEqual(len(self.povezave), 1, self.povezave)
        self.assertEqual(self.mc.odpri_kategorijo("glasba")["zacetih"], 1)           # podkast ob odprtju svoje kategorije
        self._pocakaj_niti()
        self.assertEqual(len(self.povezave), 2, self.povezave)

    def test_odprtje_kategorije_ne_sprozi_vira_brez_dokaza_o_krogu(self):
        """Vir, ki caka uporabnika (fail-closed), se ob odprtju kategorije NE prebere - samo »Osvezi«."""
        self._prejmi_neznan(("seznam", XTREAM_B))
        self.assertTrue(self._vir().get("caka_uporabnika"))
        self.assertEqual(self.mc.odpri_kategorijo("tv-v-zivo")["zacetih"], 0)
        self._pocakaj_niti()
        self.assertEqual(self.povezave, [])

    def test_odprtje_kategorije_spostuje_premor_po_napaki(self):
        self._prejmi(("seznam", XTREAM_B), ozji=True)
        podatki = self.mc._load()
        podatki["viri"][0]["zavrnjen"] = {"koda": 401, "ob": __import__("time").time(), "n": 1}
        self.mc._save(podatki)
        self.assertEqual(self.mc.odpri_kategorijo("tv-v-zivo")["zacetih"], 0)
        self._pocakaj_niti()
        self.assertEqual(self.povezave, [])                          # premor: nobene zahteve ponudniku

    def test_prebran_vir_se_po_24_urah_osvezi_ob_odprtju_njegove_kategorije(self):
        self._prejmi(("seznam", XTREAM_B), ozji=True)
        self.mc.odpri_kategorijo("tv-v-zivo")
        self._pocakaj_niti()
        self.assertEqual(len(self._prenosi()), 1)
        self.mc.odpri_kategorijo("tv-v-zivo")                        # prebran pred trenutkom: brez nove zahteve
        self._pocakaj_niti()
        self.assertEqual(len(self._prenosi()), 1)
        podatki = self.mc._load()
        podatki["viri"][0].update(posodobljeno=1, zadnja_zahteva=1)
        self.mc._save(podatki)
        self.mc._prvo_poskusi.clear()                                # minila je ze vec kot minuta
        self.mc.odpri_kategorijo("film")                             # druga kategorija: se vedno nic
        self._pocakaj_niti()
        self.assertEqual(len(self._prenosi()), 1)
        self.mc.odpri_kategorijo("tv-v-zivo")                        # starejsi od 24 h in uporabnik odpre njegovo kategorijo
        self._pocakaj_niti()
        self.assertEqual(len(self._prenosi()), 2)

    def test_kategorijo_sprozi_samo_klik_uporabnika_v_vmesniku(self):
        """Obnova zaslona ob zagonu, predgrevanje in osvezevanje kataloga NE smejo klicati mostu za odprtje kategorije."""
        import re
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        js = open(os.path.join(koren, "assets", "os", "os.js"), encoding="utf-8").read()
        klici = [m.start() for m in re.finditer(r"odpriKategorijoViri\(", js)]
        self.assertEqual(len(klici), 3, klici)                       # definicija + klik na zavihek + klik »Vse«
        self.assertEqual(js.count('"mediaOdpriKategorijo"'), 1)
        for ime in ("zadnjaMedijskaKategorija", "uskladiKatalog", "naloziMedije"):
            telo = js[js.index("function %s(" % ime):]
            telo = telo[:telo.index("\n  function ")] if "\n  function " in telo else telo
            self.assertNotIn("odpriKategorijoViri", telo, ime)
        kat = open(os.path.join(koren, "core", "os_katalog.py"), encoding="utf-8").read()
        self.assertIn('"mediaOdpriKategorijo": "_odpri_kategorijo"', kat)
        predgrej = kat[kat.index("def _predgrej"):]
        self.assertNotIn("odpri_kategorijo", predgrej[:predgrej.index("\n    def ")])

    def test_gumb_odpri_samo_za_vir_ki_ga_je_treba_prebrati(self):
        self._prejmi(("seznam", XTREAM_B), ozji=True)
        vir = self.mc.sources()[0]
        self.assertTrue(vir.get("odpri"))
        self._odpri_katalog()
        self.assertFalse(self.mc.sources()[0].get("odpri"))                       # prebran v zadnjih 24 h
        podatki = self.mc._load()
        podatki["viri"][0]["posodobljeno"] = 1
        self.mc._save(podatki)
        self.assertTrue(self.mc.sources()[0].get("odpri"))                        # starejsi od 24 h
        self.assertEqual(self.mc.odpri_vir("ni-ga"), {"ok": False, "napaka": "ni_vira", "zacet": False})

    def test_osvezitev_najvec_enkrat_na_minuto_in_predpomnilnik_24_ur(self):
        self._prejmi(("seznam", XTREAM_B), ozji=True)
        ident = self._vir()["id"]
        self._odpri_katalog()
        self.assertEqual(len(self._prenosi()), 1)
        odgovor = self.mc.refresh_source(ident)                      # uporabnik takoj pritisne »Osvezi«: brez nove zahteve
        self.assertEqual((odgovor["ok"], odgovor.get("predpomnjeno"), len(self._prenosi())), (True, True, 1))

        def postari(**polja):
            podatki = self.mc._load()
            podatki["viri"][0].update(polja)
            self.mc._save(podatki)
        zdaj = __import__("time").time()
        postari(zadnja_zahteva=int(zdaj) - 61)                       # minuta mine: uporabnikova osvezitev velja
        self.assertTrue(self.mc.refresh_source(ident)["ok"])
        self.assertEqual(len(self._prenosi()), 2)
        # Pregled 68, Ą1: 24 h je meja, ne sprozilec - po prvi uporabi se vir v ozadju NE osvezuje nikoli.
        postari(zadnja_zahteva=int(zdaj) - 61, posodobljeno=int(zdaj) - 7 * 3600)       # starejse od 6 h, mlajse od 24 h
        self._odpri_katalog()
        self.assertEqual(len(self._prenosi()), 2)                    # 24-urni predpomnilnik: odprtje ne osvezi
        postari(posodobljeno=int(zdaj) - 25 * 3600)
        self.mc.refresh_stale()
        self.mc.refresh_stale(max_age=60)
        self.assertEqual(len(self._prenosi()), 2)                    # ozadje ne osvezi niti starejsega od 24 h
        self.mc.__dict__.get("_prvo_poskusi", {}).clear()            # (meja 1/min je ze preizkusena zgoraj)
        self._odpri_katalog()
        self.assertEqual(len(self._prenosi()), 3)                    # uporabnikovo odprtje: ena osvezitev
        self._odpri_katalog()
        self.assertEqual(len(self._prenosi()), 3)                    # takoj za tem je spet predpomnilnik

    def test_po_prvi_uporabi_ozadje_vira_ne_osvezuje_nikoli(self):
        """Pregled 68, Ą1: lastnik »v ozadju se ne osvezuje«; sicer bi N naprav, ki so seznam enkrat odprle, vsaka prijavila
        racun enkrat na dan z razlicnih naslovov IP (zaklep zaradi deljenja)."""
        self._prejmi(("seznam", XTREAM_B), ozji=True)
        self._odpri_katalog()
        self.assertEqual(len(self._prenosi()), 1)
        podatki = self.mc._load()
        podatki["viri"][0].update(posodobljeno=int(__import__("time").time()) - 30 * 24 * 3600, zadnja_zahteva=1)
        self.mc._save(podatki)
        for _ in range(3):
            self.mc.refresh_stale()
            self.mc.refresh_stale(max_age=60)
            self.mc._vnosi_virov(self.mc._load(), "tv-v-zivo", preveri=False)
            self.mc._vnosi_virov(self.mc._load(), "vse", preveri=False)
        self._pocakaj_niti()
        self.assertEqual(len(self._prenosi()), 1)                    # mesec star seznam: ozadje se ga ne dotakne

    def test_premor_po_napaki_ostane_tudi_ob_odpiranju_seznama(self):
        self._prejmi(("seznam", XTREAM_B), ozji=True)

        def zavrni(url):
            self.povezave.append(("prenos", url))
            raise urllib.error.HTTPError(url, 403, "Forbidden", None, None)
        self.mc._download = zavrni
        self._odpri_katalog()
        self.assertEqual(len(self._prenosi()), 1)
        vir = self._vir()
        self.assertEqual((vir["zavrnjen"]["koda"], vir.get("prvo_uporaba") is not None, "caka_uporabnika" in vir),
                         (403, True, False))
        self.assertGreater(self.mc._zavrnjen_do(vir), __import__("time").time())
        self.mc.__dict__.get("_prvo_poskusi", {}).clear()           # tudi brez omejitve na minuto: premor velja
        self._odpri_katalog()
        self.mc.refresh_stale(max_age=60)
        self.mc.refresh_all()
        self.assertEqual(len(self._prenosi()), 1)

    def test_osvezi_med_premorom_ne_naredi_zahteve_in_pove_cas(self):
        """Pregled 68, Ą5 (lastnikova prednost: nikoli zaklep racuna): uporabnikov »Osvezi« je obsel premor po zavrnitvi."""
        for lastni in (False, True):
            with self.subTest(lastni=lastni):
                self.setUp()
                if lastni:
                    self.assertTrue(self.mc.add_source(XTREAM, "Moj")["ok"])
                    ident = self.mc._load()["viri"][0]["id"]
                else:
                    self._prejmi_neznan(("seznam", XTREAM_B))
                    ident = self._viri()[XTREAM_B]["id"]

                def zavrni(url):
                    self.povezave.append(("prenos", url))
                    raise urllib.error.HTTPError(url, 403, "Forbidden", None, None)
                self.mc._download = zavrni
                self.povezave.clear()
                self.assertFalse(self.mc.refresh_source(ident)["ok"])
                self.assertEqual(len(self.povezave), 1)
                for _ in range(5):                                                # uporabnik pritiska »Osvezi«
                    odgovor = self.mc.refresh_source(ident)
                    self.assertEqual((odgovor["ok"], odgovor["napaka"]), (False, "premor"))
                    self.assertTrue(0 < odgovor["premor_s"] <= 601, odgovor)
                self.assertEqual(len(self.povezave), 1)                           # nobene nove prijave
                vir = next(v for v in self.mc.sources() if v["id"] == ident)
                self.assertTrue(0 < vir["premor_s"] <= 601)                       # vrstica pove, cez koliko casa
                self.mc.refresh_all()                                             # tudi »Osvezi vse« premora ne obide
                self.assertEqual(len(self.povezave), 1)
                self._iztekel_premor(ident)                                       # premor je pretekel: poskus velja
                self.assertFalse(self.mc.refresh_source(ident)["ok"])
                self.assertEqual(len(self.povezave), 2)
                self.assertTrue(next(v for v in self.mc.sources() if v["id"] == ident)["premor_s"] > 0)   # nov, daljsi premor

    def test_premor_ne_velja_za_javni_vir(self):
        """Javni seznam (brez racuna) se po zavrnitvi uporabniku ne zavrne: racuna ni, ki bi se zaklenil."""
        self.assertTrue(self.mc.add_source(JAVNI, "Javni")["ok"])
        ident = self.mc._load()["viri"][0]["id"]
        podatki = self.mc._load()
        podatki["viri"][0]["zavrnjen"] = {"koda": 429, "ob": int(__import__("time").time()), "n": 1}
        self.mc._save(podatki)
        self.povezave.clear()
        self.assertTrue(self.mc.refresh_source(ident)["ok"])
        self.assertEqual(len(self._prenosi()), 1)

    def test_sociasen_osvezi_in_prva_uporaba_naredita_eno_prijavo(self):
        """Pregled 68, Ą5: meja 1/min je bila zapisana sele ob shranjevanju, zato sta sociasna »Osvezi« in prva uporaba
        poslala dve zahtevi z geslom."""
        self._prejmi(("seznam", XTREAM_B), ozji=True)
        ident = self._vir()["id"]
        v_teku, nadaljuj = threading.Event(), threading.Event()

        def pocasen(url):
            self.povezave.append(("prenos", url))
            v_teku.set()
            nadaljuj.wait(5)
            return self.LIST, "audio/x-mpegurl", url
        self.mc._download = pocasen
        rezultati = []
        nit = threading.Thread(target=lambda: rezultati.append(self.mc.refresh_source(ident)))
        nit.start()
        self.assertTrue(v_teku.wait(5))
        drugi = self.mc.refresh_source(ident)                                  # sociasen »Osvezi«
        self.assertEqual((drugi["ok"], drugi.get("ze_tece")), (False, True))
        self.assertTrue(self.mc.odpri_vir(ident)["zacet"] in (True, False))    # prva uporaba med tem
        self._pocakaj_niti()
        self.assertEqual(len(self._prenosi()), 1)
        nadaljuj.set()
        nit.join(5)
        self.assertTrue(rezultati[0]["ok"])
        self.assertEqual(len(self._prenosi()), 1)                              # ena prijava
        self.assertEqual(self.mc.refresh_source(ident).get("predpomnjeno"), True)   # nato velja se 1/min

    def test_brez_povezave_ni_vec_kot_ena_zahteva_na_minuto(self):
        self._prejmi(("seznam", XTREAM_B), ozji=True)

        def odpadi(url):
            self.povezave.append(("prenos", url))
            raise OSError("preizkus: brez povezave")
        self.mc._download = odpadi
        for _ in range(4):
            self._odpri_katalog()
        self.assertEqual(len(self._prenosi()), 1)
        vir = self._vir()
        self.assertTrue(vir["napaka"] and vir.get("prvo_uporaba"), vir)          # napaka vidna, oznaka ostane
        self.assertEqual(self.mc.refresh_source(vir["id"])["ok"], False)         # tudi uporabnik: najvec ena na minuto
        self.assertEqual(len(self._prenosi()), 1)

    def test_prvo_uporabo_sprozi_samo_odprtje_seznama(self):
        """Seznam sprejetih virov v nastavitvah, iskalnik in stevci kategorij niso uporaba seznama."""
        self._prejmi(("seznam", XTREAM_B), ozji=True)
        self.mc.sources()
        self.mc.viri_izvoz(ozji=True)
        self.mc._vnosi_virov(self.mc._load(), "vse", preveri=False)
        self._pocakaj_niti()
        self.assertEqual(self.povezave, [])

    def test_zunaj_kroga_ostane_fail_closed(self):
        for ozji in (False, None):
            with self.subTest(ozji=ozji):
                self.setUp()
                kazalo = {"sources": [{"tip": t, "ime": "TV", "naslov": n, "cas": 9} for t, n in self.NASLOVI],
                          "sources_deleted": {}}
                if ozji is not None:
                    kazalo["ozji"] = ozji
                self.assertFalse(self.mc.viri_uskladi(kazalo))       # vira z racunom sploh ne prevzamemo
                self.assertEqual(self.mc._load().get("viri", []), [])
                self.assertEqual(self.povezave, [])
        # Vir, ki ga vseeno doda koda brez dokaza o ozjem krogu (neznan izvor), caka uporabnikovo osvezitev.
        self.setUp()
        self._prejmi_neznan(*self.NASLOVI)
        for vir in self._viri().values():
            self.assertTrue(vir.get("caka_uporabnika") and "prvo_uporaba" not in vir and "ozji_krog" not in vir, vir)
        self._odpri_katalog()
        self.mc.refresh_stale(max_age=60)
        self.assertEqual(self.mc.refresh_all()["rezultati"], [])
        self.assertEqual(self.povezave, [])

    def test_vir_ki_ga_odgovor_ne_potrdi_ne_more_sam_postati_ozji_krog(self):
        """Polje »ozji« postavi samo viri_uskladi iz odgovora naprave; naslov in vrsta iz seznama ga ne moreta."""
        kazalo = {"sources": [{"tip": "seznam", "ime": "TV", "naslov": XTREAM_B, "cas": 9, "ozji": True, "ozji_krog": True,
                               "prvo_uporaba": 1}], "sources_deleted": {}, "ozji": False}
        self.assertFalse(self.mc.viri_uskladi(kazalo))
        self.assertEqual(self.mc._load().get("viri", []), [])

    def test_javni_vir_iz_ozjega_kroga_se_prenese_takoj_kot_prej(self):
        self._prejmi(("seznam", JAVNI), ozji=True)
        self.assertEqual(self._prenosi(), [("prenos", JAVNI)])
        vir = self._viri()[JAVNI]
        self.assertEqual(("prvo_uporaba" in vir, "ozji_krog" in vir, vir["stevilo"]), (False, False, 1))

    def test_lastni_vir_ima_samo_rezervno_omejitev_brez_ozjega_kroga(self):
        self.assertTrue(self.mc.add_source(XTREAM, "Moj")["ok"])
        vir = self.mc._load()["viri"][0]
        self.assertEqual(("ozji_krog" in vir, "prvo_uporaba" in vir, "zadnja_zahteva" in vir), (False, False, False))

    def test_refresh_stale_spostuje_premor_po_napaki_vsakega_vira(self):
        """Samodejna osvezitev je prej gledala samo staro starost: vir z racunom, ki ga je ponudnik zavrnil, je dobil novo
        zahtevo ob vsakem klicu (premor je bral samo katalog)."""
        self.assertTrue(self.mc.add_source(XTREAM, "Moj")["ok"])
        podatki = self.mc._load()
        podatki["viri"][0].update(posodobljeno=1, zavrnjen={"koda": 403, "ob": int(__import__("time").time()), "n": 1})
        self.mc._save(podatki)
        self.povezave.clear()
        self.mc.refresh_stale(max_age=60)
        self.assertEqual(self.povezave, [])

    def test_stran_pove_da_seznam_caka_na_prvo_odprtje(self):
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "assets", "os", "os.js"), encoding="utf-8") as f:
            js = f.read()
        with open(os.path.join(koren, "assets", "os", "besedila.js"), encoding="utf-8") as f:
            besedila = f.read()
        self.assertIn("source.prvo_uporaba", js)
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            self.assertRegex(besedila, r"BESEDILA_OS\.%s, \{\"katVirPrvo\": \"[^\"]{40,}\"" % jezik)
        # Pregled 68 (Ą4, Ą5): gumb »Odpri« samo za ta vir, vrstica pove premor po zavrnitvi.
        self.assertIn("source.odpri", js)
        self.assertIn("mediaOdpriVir", js)
        self.assertIn("source.premor_s", js)
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            self.assertRegex(besedila, r"BESEDILA_OS\.%s, \{\"katVirPremor\": \"[^\"]*\{t\}[^\"]*\", \"katVirOdpri\": \"[^\"]+\"" % jezik)


class PosiljateljMoraBitiVOzjemKrogu(_PrejetOsnova):
    """Pregled 68, Ą3 (AGENTS.md: nic iz dohodnega sporocila ne sme podeliti dostopa): odgovor »ozji« je izjava posiljatelja,
    da ima NAS v svojem krogu. Dokaz je sele, da je posiljatelj v ozjem krogu TE naprave (core/link_dostop)."""

    def _kazalo(self, ozji=True):
        return {"sources": [{"tip": "seznam", "ime": "TV", "naslov": XTREAM_B, "cas": 9}], "sources_deleted": {}, "ozji": ozji}

    def test_posiljatelj_zunaj_kroga_z_ozji_true_ne_podeli_dostopa(self):
        for posiljatelj in ("", "neznana-naprava"):
            with self.subTest(posiljatelj=posiljatelj):
                self.setUp()
                with mock.patch("core.link_dostop.v_ozjem_krogu", lambda i: i == "domaca-naprava"):
                    self.assertFalse(self.mc.viri_uskladi(self._kazalo(True), posiljatelj))
                self.assertEqual(self.mc._load().get("viri", []), [])        # vira z racunom ne prevzamemo
                self.mc.refresh_stale()
                self._odpri_katalog_prazen()
                self.assertEqual(self.povezave, [])

    def test_posiljatelj_v_krogu_in_ozji_true_je_dokaz(self):
        with mock.patch("core.link_dostop.v_ozjem_krogu", lambda i: i == "domaca-naprava"):
            self.assertTrue(self.mc.viri_uskladi(self._kazalo(True), "domaca-naprava"))
        vir = self.mc._load()["viri"][0]
        self.assertTrue(vir.get("prvo_uporaba") and vir.get("ozji_krog"))
        self.assertEqual(self.povezave, [])

    def test_posiljatelj_v_krogu_brez_ozji_ni_dokaz(self):
        with mock.patch("core.link_dostop.v_ozjem_krogu", lambda i: True):
            for ozji in (False, None):
                self.assertFalse(self.mc.viri_uskladi(self._kazalo(ozji), "domaca-naprava"))
        self.assertEqual(self.mc._load().get("viri", []), [])

    def test_napaka_pri_preverbi_kroga_je_ne(self):
        def pade(_i):
            raise OSError("preizkus: zapis dovoljenj nedosegljiv")
        with mock.patch("core.link_dostop.v_ozjem_krogu", pade):
            self.assertFalse(self.mc.viri_uskladi(self._kazalo(True), "domaca-naprava"))
        self.assertEqual(self.mc._load().get("viri", []), [])

    def test_javni_vir_ne_potrebuje_dokaza(self):
        kazalo = {"sources": [{"tip": "seznam", "ime": "TV", "naslov": JAVNI, "cas": 9}], "sources_deleted": {}, "ozji": True}
        with mock.patch("core.link_dostop.v_ozjem_krogu", lambda i: False):
            self.assertTrue(self.mc.viri_uskladi(kazalo, ""))
        self.assertEqual([p[0] for p in self.povezave if p[0] == "prenos"], ["prenos"])

    def test_usklajevanje_nese_id_posiljatelja(self):
        """seznami_uskladi vzame id iz vprasaja (safeer_os._seznami_z_naprav ga pripne); brez njega dokaza ni."""
        def odgovor(parametri):
            return {"lists": [], "deleted": {}, "sources": self._kazalo(True)["sources"], "sources_deleted": {},
                    "ozji": True} if not parametri else None
        with mock.patch("core.link_dostop.v_ozjem_krogu", lambda i: i == "domaca-naprava"):
            self.assertFalse(self.mc.seznami_uskladi(odgovor))              # brez id: zunaj kroga
            self.assertEqual(self.mc._load().get("viri", []), [])
            odgovor.id_naprave = "tuja"
            self.assertFalse(self.mc.seznami_uskladi(odgovor))
            self.assertEqual(self.mc._load().get("viri", []), [])
            odgovor.id_naprave = "domaca-naprava"
            self.assertTrue(self.mc.seznami_uskladi(odgovor))
        self.assertTrue(self.mc._load()["viri"][0].get("prvo_uporaba"))

    def test_safeer_os_pripne_id_naprave_vprasaju(self):
        import safeer_os
        naprave = {"ok": True, "naprave": [{"id": "domaca-naprava", "zmoznosti": ["remote", "lists"]}]}
        ids = []

        def uskladi(vprasaj):
            ids.append(getattr(vprasaj, "id_naprave", None))
            return False
        with mock.patch.object(safeer_os, "_control_na_vodilu", return_value=True), \
                mock.patch.object(safeer_os.Gio, "bus_get_sync", return_value=object()), \
                mock.patch.object(safeer_os, "_control_naprave", return_value=naprave):
            safeer_os._seznami_z_naprav(uskladi)
        self.assertEqual(ids, ["domaca-naprava"])

    def _odpri_katalog_prazen(self):
        self.mc._vnosi_virov(self.mc._load(), "tv-v-zivo")
        for v in self.mc._load().get("viri", []):
            self.mc.odpri_vir(v["id"])
        for nit in threading.enumerate():
            if nit.name in ("media-razclenitev", "media-prva-uporaba"):
                nit.join(5)


@pytest.mark.pravi_dostop
class PosiljateljPoPravihDostopa(_Osnova):
    """Isto s pravimi pravili core/link_dostop (zacasni zapis dovoljenj): v ozjem krogu je samo naprava z izrecno privolitvijo."""

    def setUp(self):
        super().setUp()
        self.mapa2 = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa2.cleanup)
        self.mc = os_media.MediaCenter(self.mapa2.name, roots=[])
        self.mc._download = lambda url: (b'#EXTM3U\n#EXTINF:-1,K\nhttp://p.test:8080/live/u/g/1.ts\n', "audio/x-mpegurl", url)
        self.mc._izmeri_ping = lambda url: None
        self.mc._kanali_spremenjeni = lambda viri=False: None
        self.kazalo = {"sources": [{"tip": "seznam", "ime": "TV", "naslov": XTREAM_B, "cas": 9}], "sources_deleted": {}, "ozji": True}

    def test_samo_naprava_z_izrecno_privolitvijo_je_dokaz(self):
        self.assertTrue(link_dostop.nastavi(B, "dv"))                      # B ima nekaj dovoljenj, a ni v ozjem krogu
        self.assertFalse(self.mc.viri_uskladi(self.kazalo, B))             # ni v ozjem krogu (stikalo ga ni dalo)
        self.assertFalse(self.mc.viri_uskladi(self.kazalo, ""))
        self.assertEqual(self.mc._load().get("viri", []), [])
        self.assertTrue(link_dostop.nastavi_ozji_krog(A, "p"))             # izrecna privolitev uporabnika na tej napravi
        self.assertTrue(self.mc.viri_uskladi(self.kazalo, A))
        self.assertTrue(self.mc._load()["viri"][0].get("prvo_uporaba"))


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

    def test_dodaj_vir_ne_vrne_gesla_strani(self):
        """Pregled 57 (V7): odgovor »Dodaj vir« je nosil cel naslov z geslom (vir.url) nazaj strani."""
        from core import os_katalog
        k = os_katalog.Katalog(self.mapa.name, lambda *a: None, lambda f: f(), lambda *a, **kw: True, lambda u: True,
                               lambda *a: True, lambda u: True)
        k._mc = self.mc
        self.mc._izmeri_ping = lambda u: None
        self.mc._download = lambda u: (b"#EXTM3U\n#EXTINF:-1 tvg-id=\"K1.si\",Kanal 1\nhttp://ponudnik.test:8080/live/u/g/1.ts\n",
                                      "audio/x-mpegurl", u)
        for naslov in ("http://ponudnik.test:8080/get.php?username=novi&password=novo-geslo&type=m3u_plus", XTREAM):
            with self.subTest(naslov=naslov):                         # nov vir in podvojen vir
                r = k._dodaj_vir([naslov, "Ime"])
                self.assertIsInstance(r.get("vir"), dict)
                self.assertEqual(r["vir"]["url_prikaz"], "ponudnik.test:8080")
                for skrivnost in ("novo-geslo", "skrito-geslo"):
                    self.assertNotIn(skrivnost, json.dumps(r))

    def test_dodaj_vir_ob_napaki_ne_vrne_gesla_strani(self):
        """Pregled 63 (Ŷ2, V7): tudi neuspesno dodajanje z izjemo, ki nosi geslo (repr cilja z ' in "), ne nosi gesla v odgovoru."""
        import http.client
        from core import os_katalog
        k = os_katalog.Katalog(self.mapa.name, lambda *a: None, lambda f: f(), lambda *a, **kw: True, lambda u: True,
                               lambda *a: True, lambda u: True)
        k._mc = self.mc
        self.mc._izmeri_ping = lambda u: None
        naslov = "http://drug.test:8080/get.php?username=novi&password=novo'geslo\"x&type=m3u_plus"

        def prenesi(u):
            raise http.client.InvalidURL("URL can't contain control characters. %r (found at least ' ')" % u.partition("8080")[2])
        self.mc._download = prenesi
        r = k._dodaj_vir([naslov, "Ime"])
        self.assertFalse(r["ok"])
        for skrivnost in ("novo", "geslo", "novi"):
            self.assertNotIn(skrivnost, json.dumps(r))

    def test_napaka_brez_naslova(self):
        self.mc._download = lambda url: (_ for _ in ()).throw(ValueError("unknown url type: %r" % url))
        self.assertFalse(self.mc.refresh_source("xt")["ok"])
        napaka = next(v for v in self.mc._load()["viri"] if v["id"] == "xt")["napaka"]
        self.assertIn("ponudnik.test:8080", napaka)
        self.assertNotIn("skrito-geslo", napaka)

    def test_napaka_brez_sheme_je_zakrita(self):
        """Pregled 51, Ê5: http.client.InvalidURL (naslov s presledkom ali nadzornim znakom) nosi samo pot in poizvedbo
        zahteve, brez sheme in gostitelja: '/get.php?username=…&password=…' je bil na zaslonu in v media.json."""
        import http.client
        sporocila = ["URL can't contain control characters. '/get.php?username=uporabnik&password=skrito-geslo&type=m3u_plus' "
                     "(found at least ' ')", "URL can't contain control characters. %r (found at least '\\n')" % "/playlist/uporabnik/skrito-geslo/m3u_plus",
                     'Napaka: "/live/uporabnik/skrito-geslo/1.ts?token=skrito-geslo" ni dosegljiv']
        for sporocilo in sporocila:
            with self.subTest(sporocilo=sporocilo[:50]):
                self.mc._download = lambda url, s=sporocilo: (_ for _ in ()).throw(http.client.InvalidURL(s))
                self.assertFalse(self.mc.refresh_source("xt")["ok"])
                napaka = next(v for v in self.mc._load()["viri"] if v["id"] == "xt")["napaka"]
                self.assertNotIn("skrito-geslo", napaka)
                self.assertIn("URL can't contain control characters" if "control" in sporocilo else "ni dosegljiv", napaka)
                # Starejsi zapis v media.json: napaka na strani je zakrita tudi, ce ni v njem »://«.
                from core import os_media as om
                stran = om.vir_za_stran({"id": "xt", "url": XTREAM, "napaka": sporocilo})
                self.assertNotIn("skrito-geslo", json.dumps(stran))
        # Navadna sporocila ostanejo berljiva.
        self.assertEqual(viri_sink.zakrij_naslove("HTTP Error 404: Not Found", napaka=True), "HTTP Error 404: Not Found")
        # Naslov skladbe z navednicami in »&« ostane nespremenjen (zakrije se samo naslov s shemo).
        naslov = "Simon & Garfunkel - 'Mrs. Robinson' & \"Sound of Silence\" https://x.primer.test/pot?a=b"
        self.assertEqual(viri_sink.zakrij_naslove(naslov), naslov.replace("https://x.primer.test/pot?a=b", "x.primer.test"))
        self.assertEqual(viri_sink.zakrij_naslove("<urlopen error [Errno -2] Name or service not known>"),
                         "<urlopen error [Errno -2] Name or service not known>")

    def test_zapis_za_naprave_samo_lastniku(self):
        self.mc._viri_zapisi_izvoz()
        self.assertEqual(os.stat(os.path.join(self.mapa.name, "viri_za_naprave.json")).st_mode & 0o777, 0o600)


class NapakaViraFailClosed(unittest.TestCase):
    """Pregled 57, Ş5: zakrivanje napake (Ê5) je bilo fail-open. Geslo z ' ali " je prekinilo ujemanje (repr zapise niz v
    "…" ali z \\'), rez na 180 znakov je bil PRED zakrivanjem in je odrezal zakljucno navednico, presledek v cilju je
    prekinil naslov. Zdaj: najprej tocno ujemanje skrivnosti vira, nato naslov s shemo do presledka, nato cilj do
    zakljucne navednice ali konca - ne glede na zapis izjeme; sele nato rez."""

    GESLA = ("skrito'geslo", "skrito'geslo\"dva", "skrito\"geslo", "skrito geslo", "skrito\\geslo", "skrito'")
    SKRIVNO = ("skrito", "geslo", "uporabnik")

    @staticmethod
    def _url(geslo, dolg=False):
        return "http://ponudnik.test:8080/get.php?username=uporabnik&password=%s&type=m3u_plus%s" % (
            geslo, "&pad=" + "x" * 300 if dolg else "")

    @staticmethod
    def _izjema_cilja(url):
        """Prava izjema http.client (naslov s presledkom ali nadzornim znakom): nosi samo pot in poizvedbo, z repr."""
        import http.client
        cilj = url.partition("8080")[2]
        try:
            http.client.HTTPConnection("ponudnik.test").putrequest("GET", cilj)
        except http.client.InvalidURL as e:
            return e
        raise AssertionError("pricakovana izjema InvalidURL za " + repr(cilj))

    def _izjeme(self, url):
        yield "InvalidURL", self._izjema_cilja(url + " ")             # presledek na koncu: http.client zavrne cilj
        yield "unknown url type", ValueError("unknown url type: %r" % url)
        yield "brez repr", ValueError("Napaka pri %s: ni dosegljiv" % url)

    def _vir(self, url):
        mapa = tempfile.TemporaryDirectory()
        self.addCleanup(mapa.cleanup)
        with open(os.path.join(mapa.name, "media.json"), "w", encoding="utf-8") as f:
            json.dump({"viri": [{"id": "xt", "url": url, "ime": "Ponudnik", "stevilo": 0, "napaka": "", "vnosi": [],
                                 "dodan": 5}], "osebni_strezniki": [], "racuni_preseljeni": 1}, f)
        return os_media.MediaCenter(mapa.name, roots=[])

    def _preveri(self, napaka, kje):
        self.assertTrue(napaka, kje)
        self.assertLessEqual(len(napaka), 300, kje)
        for skrivnost in self.SKRIVNO:
            self.assertNotIn(skrivnost, napaka, "%s: %r" % (kje, napaka))

    def test_osvezitev_ne_pusti_gesla_na_zaslon_in_v_media_json(self):
        for geslo in self.GESLA:
            for dolg in (False, True):
                url = self._url(geslo, dolg)
                mc = self._vir(url)
                for ime, izjema in self._izjeme(url):
                    with self.subTest(geslo=geslo, dolg=dolg, izjema=ime):
                        def prenesi(u, i=izjema):
                            raise i
                        mc._download = prenesi
                        self.assertFalse(mc.refresh_source("xt")["ok"])
                        napaka = next(v for v in mc._load()["viri"] if v["id"] == "xt")["napaka"]
                        self._preveri(napaka, "media.json")
                        self._preveri(os_media.vir_za_stran({"id": "xt", "url": url, "napaka": napaka})["napaka"], "stran")

    def test_zakrivanje_ne_zavisi_od_reza_ali_zapisa_izjeme(self):
        """Tudi besedilo, ki je bilo ze odrezano (starejsi zapis v media.json), je zakrito brez skrivnosti vira."""
        for geslo in self.GESLA:
            for dolg in (False, True):
                url = self._url(geslo, dolg)
                for ime, izjema in self._izjeme(url):
                    for rez in (60, 100, 180, 100000):
                        with self.subTest(geslo=geslo, izjema=ime, rez=rez):
                            zakrito = viri_sink.zakrij_naslove(str(izjema)[:rez], napaka=True)       # brez znanih skrivnosti
                            self._preveri(zakrito, "rez")

    def test_navadna_sporocila_ostanejo_berljiva(self):
        for sporocilo in ("HTTP Error 404: Not Found", "<urlopen error [Errno 111] Connection refused>", "Vir je prevelik.",
                          "<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local "
                          "issuer certificate (_ssl.c:1000)>", "Ponudnik ni vrnil seznama.", "The read operation timed out",
                          "Predloga potrebuje {tmdbId} ali {imdbId} in pot /movie/ ali /tv/.",
                          "'utf-8' codec can't decode byte 0xff in position 0: invalid start byte"):
            self.assertEqual(viri_sink.zakrij_naslove(sporocilo, napaka=True), sporocilo)


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
