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
        """Krog 85: vire za naprave zapise Medijski center (brez zasebnih dodatkov); Control jih samo prebere in preveri."""
        with open(os.path.join(self.mapa.name, "viri_za_naprave.json"), "w", encoding="utf-8") as f:
            json.dump({"sources": [{"tip": "stremio", "ime": "Dodatek", "naslov": "https://d.primer.si/manifest.json", "cas": 7, "zaseben": False},
                                   {"tip": "kodi", "ime": "x", "naslov": "https://k.primer.si"}, "smeti",
                                   {"tip": "url", "ime": "Podkast", "naslov": "https://p.primer.si/feed.xml", "cas": 0}],
                       "sources_deleted": {"stremio|https://star.primer.si/manifest.json": 9, "kodi|x": 3, "url|https://b.si": "x"}}, f)
        kazalo = link_seznami.izvoz({}, self.mapa.name)
        self.assertEqual(kazalo["sources"], [{"tip": "stremio", "ime": "Dodatek", "naslov": "https://d.primer.si/manifest.json", "cas": 7},
                                             {"tip": "url", "ime": "Podkast", "naslov": "https://p.primer.si/feed.xml", "cas": 0}])
        self.assertEqual(kazalo["sources_deleted"], {"stremio|https://star.primer.si/manifest.json": 9})
        self.assertNotIn("sources", link_seznami.izvoz({"ime": "Kratek"}, self.mapa.name))

    def test_brez_mape_ali_s_pokvarjeno_datoteko_je_kazalo_prazno(self):
        self.assertEqual(link_seznami.izvoz({}, os.path.join(self.mapa.name, "ni")),
                         {"lists": [], "deleted": {}, "sources": [], "sources_deleted": {}})
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


class RacunSamoOzjiKrog(unittest.TestCase):
    """Z Androida (VISOKO, 26. 10. 2026): seznam Xtream z geslom je sel z usklajevanjem virov (lists.get) vsem napravam
    z dovoljenjem »Predvajalnik«, geslo pa je bilo v vrstici Virov na zaslonu. Vir in tok z racunom gresta samo v ozji
    krog (core/viri_sink.za_ozji_krog), na zaslonu je samo gostitelj."""

    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        viri = [{"id": "pod", "url": PODKAST, "ime": "Podkast", "stevilo": 3, "napaka": "", "vnosi": [], "dodan": 5},
                {"id": "xt", "url": XTREAM, "ime": "Ponudnik", "stevilo": 3, "napaka": "", "vnosi": [], "dodan": 6}]
        with open(os.path.join(self.mapa.name, "media.json"), "w", encoding="utf-8") as f:
            json.dump({"viri": viri, "osebni_strezniki": []}, f)
        with open(os.path.join(self.mapa.name, "seznami.json"), "w", encoding="utf-8") as f:
            json.dump([{"ime": "TV", "cas": 7, "skladbe": [{"naslov": "Kanal", "url": KANAL_XTREAM},
                                                            {"naslov": "Javni", "url": "https://tok.primer.si/a.m3u8"}]}], f)
        self.mc = os_media.MediaCenter(self.mapa.name, roots=[])
        self.javni = {"tip": "url", "ime": "Podkast", "naslov": PODKAST, "cas": 5}
        self.racun = {"tip": "url", "ime": "Ponudnik", "naslov": XTREAM, "cas": 6}

    def test_vir_z_racunom_samo_ozjemu_krogu(self):
        self.assertEqual(self.mc.viri_izvoz()["sources"], [self.javni])
        self.assertEqual(self.mc.viri_izvoz(ozji=True)["sources"], [self.javni, self.racun])
        self.mc._viri_zapisi_izvoz()                                # zapis za Safeer Control (viri_za_naprave.json)
        self.assertEqual(link_seznami.izvoz({}, self.mapa.name)["sources"], [self.javni])
        self.assertEqual(link_seznami.izvoz({}, self.mapa.name, ozji=True)["sources"], [self.javni, self.racun])
        for ozji in (False, True):
            self.assertEqual(link_seznami.izvoz({}, self.mapa.name, ozji=ozji), self.mc.seznami_izvoz({}, ozji=ozji))
        self.assertNotIn("skrito-geslo", json.dumps(link_seznami.izvoz({}, self.mapa.name)))

    def test_izbris_vira_z_racunom_samo_ozjemu_krogu(self):
        izvoz = viri_sink.razdeli_izvoz([self.javni, self.racun], {"url|" + XTREAM: 9, "url|https://star.primer.si/f.xml": 8})
        self.assertEqual(viri_sink.viri_za(izvoz), {"sources": [self.javni],
                                                    "sources_deleted": {"url|https://star.primer.si/f.xml": 8}})
        self.assertEqual(viri_sink.viri_za(izvoz, True)["sources_deleted"],
                         {"url|https://star.primer.si/f.xml": 8, "url|" + XTREAM: 9})
        # Zapis starejse razlicice (brez delitve): vir in izbris z racunom ne gresta nikomur zunaj ozjega kroga.
        star = {"sources": [self.racun, self.javni], "sources_deleted": {"url|" + XTREAM: 3}}
        self.assertEqual(viri_sink.viri_za(star), {"sources": [self.javni], "sources_deleted": {}})

    def test_tok_z_racunom_v_seznamu_samo_ozjemu_krogu(self):
        for ozji, naslovi in ((False, [None, "https://tok.primer.si/a.m3u8"]),
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
                         [[PODKAST], [PODKAST, XTREAM], [PODKAST]])

    def test_na_zaslonu_samo_gostitelj(self):
        viri = {v["id"]: v for v in self.mc.sources() if v.get("id") in ("pod", "xt")}
        self.assertEqual((viri["xt"]["url_prikaz"], viri["pod"]["url_prikaz"]), ("ponudnik.test:8080", PODKAST))
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "assets", "os", "os.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn("var prikaz = source.url_prikaz !== undefined ? source.url_prikaz : source.url;", js)
        self.assertNotIn('ubezi(status + " · " + source.url)', js)


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
