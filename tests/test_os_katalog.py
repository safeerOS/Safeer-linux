"""Katalog Medijskega centra na Linuxu (core/os_katalog.py): pravila predvajanja in most brez okna."""
import json
import os
import re
import tempfile
import unittest

from core import os_katalog as K

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class NacinPredvajanjaTests(unittest.TestCase):
    def test_skladba_s_seznama_gre_v_vgradni_predvajalnik(self):
        vnos = {"id": "seznam:abc", "youtube": "59o4m222aVw", "vrsta": "glasba", "url": "https://www.youtube.com/watch?v=59o4m222aVw"}
        self.assertEqual(K.nacin_predvajanja(vnos), "youtube")

    def test_neveljaven_posnetek_se_ne_predvaja(self):
        for posnetek in ("kratek", "59o4m222aVw&x=1", "../../etc/pa", "59o4m222aV<"):
            self.assertEqual(K.nacin_predvajanja({"id": "seznam:a", "youtube": posnetek}), "", posnetek)

    def test_tok_in_datoteka_gresta_v_domaci_predvajalnik(self):
        self.assertEqual(K.nacin_predvajanja({"url": "https://arhiv.test/film.mp4", "stran": "https://arhiv.test/film"}), "neposredno")
        self.assertEqual(K.nacin_predvajanja({"url": "https://tv.test/prenos.m3u8"}), "neposredno")
        self.assertEqual(K.nacin_predvajanja({"url": "file:///home/a/pesem.flac"}), "neposredno")
        self.assertEqual(K.nacin_predvajanja({"url": "", "pot": "/home/a/film.mkv"}), "neposredno")
        # Dodatek, ki toku doda glave (npr. Referer), vraca neposreden tok tudi brez koncnice.
        self.assertEqual(K.nacin_predvajanja({"url": "https://tok.test/abc", "glave": {"Referer": "https://tok.test/"}}), "neposredno")

    def test_zvocni_tok_brez_koncnice_potrdi_streznik(self):
        vnos = {"url": "https://radio.test/tok", "vrsta": "radio"}
        self.assertEqual(K.nacin_predvajanja(vnos, lambda _u: True), "neposredno")
        self.assertEqual(K.nacin_predvajanja(vnos, lambda _u: False), "vdelano")
        # Pri videu streznika ne sprasujemo: stran brez koncnice je spletna stran.
        klici = []
        self.assertEqual(K.nacin_predvajanja({"url": "https://video.test/oddaja", "vrsta": "film"}, lambda u: klici.append(u) or True), "vdelano")
        self.assertEqual(klici, [])

    def test_vdelani_predvajalniki_in_nevarne_sheme(self):
        self.assertEqual(K.nacin_predvajanja({"url": "https://www.youtube.com/embed/59o4m222aVw"}), "vdelano")
        self.assertEqual(K.nacin_predvajanja({"url": "https://player.vimeo.com/video/1"}), "vdelano")
        for naslov in ("javascript:alert(1)", "data:text/html,x", "magnet:?xt=urn:btih:abc", ""):
            self.assertEqual(K.nacin_predvajanja({"url": naslov}), "", naslov)

    def test_vrsta_in_naslov_za_predvajalnik(self):
        self.assertEqual(K.vrsta_predvajalnika({"vrsta": "radio"}), "radio")
        self.assertEqual(K.vrsta_predvajalnika({"vrsta": "tv-v-zivo"}), "tv")
        self.assertEqual(K.vrsta_predvajalnika({"vrsta": "glasba"}), "medij")
        self.assertEqual(K.vrsta_predvajalnika({"vrsta": "film"}), "video")
        self.assertEqual(K.naslov_za_predvajalnik({"naslov": "Pesem", "izvajalec": "Pevka", "vrsta": "glasba"}), "Pevka – Pesem")
        # Pri radiu je »izvajalec« drzava postaje in ne sodi v naslov.
        self.assertEqual(K.naslov_za_predvajalnik({"naslov": "Radio Ena", "izvajalec": "Slovenija", "vrsta": "radio"}), "Radio Ena")
        self.assertEqual(K.naslov_za_predvajalnik({"naslov": "Serija", "vrsta": "serija", "sezona": 2, "epizoda": 5}), "Serija · S02E05")
        self.assertEqual(K.naslov_za_predvajalnik({}), "Safeer")

    def test_podnapisi_samo_z_varnih_naslovov(self):
        vnos = {"podnapisi": [
            {"uri": "https://podnapisi.test/a.vtt", "jezik": "sl"},
            {"url": "http://podnapisi.test/b.vtt", "jezik": "en"},      # nesifrirano zunaj naprave: ne
            {"uri": "javascript:alert(1)"}, "ni slovar",
            {"uri": "http://127.0.0.1:8123/c.srt", "ime": "Krajevni"},
        ]}
        izid = K.podnapisi_vnosa(vnos)
        self.assertEqual([p[0] for p in izid], ["https://podnapisi.test/a.vtt", "http://127.0.0.1:8123/c.srt"])
        self.assertEqual(izid[0][2], "sl")
        self.assertEqual(izid[1][1], "Krajevni")


class VgradnjaYoutubeTests(unittest.TestCase):
    def test_naslov_vgradnje_samo_za_veljaven_posnetek(self):
        naslov = K.naslov_vgradnje("59o4m222aVw")
        self.assertTrue(naslov.startswith("https://www.youtube.com/embed/59o4m222aVw?"))
        self.assertIn("autoplay=1", naslov)
        self.assertTrue(K.je_naslov_vgradnje(naslov))
        for slab in ("", "abc", "59o4m222aVw/../x", "59o4m222aVw?x", None):
            self.assertEqual(K.naslov_vgradnje(slab), "", slab)

    def test_okno_sprejme_samo_vgradni_predvajalnik(self):
        for slab in ("http://127.0.0.1:8000/x?v=59o4m222aVw", "https://www.youtube.com/watch?v=59o4m222aVw",
                     "https://www.youtube.com.zlo.test/embed/59o4m222aVw", "https://www.youtube.com/embed/",
                     "https://www.youtube.com/embed/../watch", "https://zlo.test/embed/59o4m222aVw", ""):
            self.assertFalse(K.je_naslov_vgradnje(slab), slab)

    def test_izvor_je_isti_kot_na_windows(self):
        self.assertEqual(K.IZVOR_VGRADNJE, "https://safeer.si/")

    def test_skript_stanja_ne_doseze_mostu_safeer_os(self):
        """Skript v lahkem pogledu sme poslati samo stanje skladbe; mostu Safeer OS (safeerOs) v njem ni."""
        self.assertIn("messageHandlers.safeerSkladba", K.SKRIPT_SKLADBE)
        self.assertNotIn("safeerOs", K.SKRIPT_SKLADBE)
        self.assertEqual(K.STRANI_SKRIPTA_SKLADBE, ("https://www.youtube.com/embed/*",))

    def test_safeer_os_tuje_vsebine_ne_vgradi_v_svojo_stran(self):
        """Klici mostu Safeer OS so dosegljivi vsem okvirjem strani, zato stran Safeer OS ne sme vgrajevati tujih
        okvirjev: politika vsebine jih ne dovoli, skladba pa gre v locen lahki pogled."""
        with open(os.path.join(KOREN, "assets", "os", "index.html"), encoding="utf-8") as f:
            stran = f.read()
        politika = re.search(r'Content-Security-Policy" content="([^"]+)"', stran).group(1)
        self.assertNotIn("frame-src", politika)
        self.assertNotIn("<iframe", stran)
        self.assertRegex(politika, r"default-src 'none'|default-src 'self'")
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            okno = f.read()
        pogled = okno[okno.index("def _ustvari_medijski_pogled"):okno.index("def _katalog_youtube(")]
        self.assertIn('register_script_message_handler("safeerSkladba")', pogled)
        self.assertNotIn('"safeerOs"', pogled)
        self.assertIn("set_sandbox_enabled(True)", pogled)
        self.assertIn("new_ephemeral()", pogled)


class _LazniMc:
    def __init__(self, vnosi):
        self.vnosi = vnosi

    def resolve(self, ident):
        return self.vnosi.get(ident)


class MostKatalogaTests(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.dogodki, self.predvajano, self.vdelano, self.yt, self.ukazi = [], [], [], [], []
        self.k = K.Katalog(
            self.mapa.name, dogodek=lambda v, p: self.dogodki.append((v, p)), v_glavni=lambda delo: delo(),
            predvajaj=lambda *a: self.predvajano.append(a) or True, vdelano=lambda u: self.vdelano.append(u) or True,
            youtube=lambda u, n: self.yt.append((u, n)) or True, youtube_ukaz=lambda u: self.ukazi.append(u) or True)

    def _vnosi(self, **vnosi):
        self.k._mc = _LazniMc(vnosi)

    def test_metode_mostu_obstajajo(self):
        for metoda, ime in K.Katalog.METODE.items():
            self.assertTrue(metoda.startswith("media"), metoda)
            self.assertTrue(callable(getattr(self.k, ime)), ime)
        self.assertTrue(self.k.pozna("mediaKatalog"))
        self.assertFalse(self.k.pozna("zazeni"))
        self.assertFalse(self.k.pozna("__init__"))

    def test_film_iz_arhiva_gre_v_predvajalnik_ceprav_ima_stran(self):
        self._vnosi(f1={"id": "f1", "vrsta": "film", "naslov": "Film", "url": "https://arhiv.test/film.mp4", "stran": "https://arhiv.test/o-filmu"})
        izid = self.k.izvedi("mediaPredvajaj", ["f1"])
        self.assertTrue(izid["native"])
        self.assertFalse(izid["zvok"])
        self.assertEqual(self.predvajano[0][:3], ("https://arhiv.test/film.mp4", "video", "Film"))
        self.assertTrue(self.predvajano[0][5])           # video odpre okno

    def test_prenos_samo_na_strani_izdajatelja_ostane_strani(self):
        self._vnosi(t1={"id": "t1", "vrsta": "tv-v-zivo", "url": "https://tv.test/v-zivo", "stran": "https://tv.test/v-zivo"})
        izid = self.k.izvedi("mediaPredvajaj", ["t1"])
        self.assertNotIn("native", izid)
        self.assertEqual((self.predvajano, self.vdelano, self.yt), ([], [], []))

    def test_napaka_vira_se_ne_predvaja(self):
        self._vnosi(x={"id": "x", "napaka_koda": "ni_toka", "naslov": "Film"})
        self.assertEqual(self.k.izvedi("mediaPredvajaj", ["x"])["napaka_koda"], "ni_toka")
        self.assertIsNone(self.k.izvedi("mediaPredvajaj", ["ni"]))
        self.assertEqual(self.predvajano, [])

    def test_nepredvajljiv_naslov_javi_da_ni_toka(self):
        self._vnosi(m={"id": "m", "vrsta": "film", "url": "magnet:?xt=urn:btih:abc"})
        self.assertEqual(self.k.izvedi("mediaPredvajaj", ["m"])["napaka_koda"], "ni_toka")

    def test_radio_je_zvok_brez_okna(self):
        self._vnosi(r={"id": "r", "vrsta": "radio", "naslov": "Radio", "url": "https://radio.test/tok.mp3"})
        izid = self.k.izvedi("mediaPredvajaj", ["r"])
        self.assertTrue(izid["zvok"])
        self.assertEqual(self.predvajano[0][1], "radio")
        self.assertFalse(self.predvajano[0][5])
        self.k.konec("https://radio.test/tok.mp3")
        self.assertIn(("mediaKonec", {"id": "r"}), self.dogodki)

    def test_skladba_youtube_in_konec_sprozi_naslednjo(self):
        self._vnosi(**{"seznam:a": {"id": "seznam:a", "vrsta": "glasba", "naslov": "Pesem", "izvajalec": "Pevka", "youtube": "59o4m222aVw"}})
        izid = self.k.izvedi("mediaPredvajaj", ["seznam:a"])
        self.assertTrue(izid["okno_youtube"] and izid["zvok"])
        self.assertEqual(self.yt, [(K.naslov_vgradnje("59o4m222aVw"), "Pevka – Pesem")])
        # Konec brez predvajanja (stran se sele nalaga) ne sprozi nicesar.
        self.k.yt_sporocilo(json.dumps({"stanje": 0}))
        self.assertEqual(self.dogodki, [])
        self.k.yt_sporocilo(json.dumps({"stanje": 1}))
        self.k.yt_sporocilo(json.dumps({"stanje": 1}))
        self.k.yt_sporocilo(json.dumps({"stanje": 2}))
        self.k.yt_sporocilo(json.dumps({"stanje": 1}))
        self.k.yt_sporocilo(json.dumps({"stanje": 0}))
        self.k.yt_sporocilo(json.dumps({"stanje": 0}))    # ponovljeno sporocilo ne preskoci skladbe
        self.assertEqual(self.dogodki, [
            ("mediaYt", {"id": "seznam:a", "igra": True}), ("mediaYt", {"id": "seznam:a", "igra": False}),
            ("mediaYt", {"id": "seznam:a", "igra": True}), ("mediaKonec", {"id": "seznam:a"})])

    def test_napaka_vgradnje_in_smeti_v_sporocilu(self):
        self._vnosi(**{"seznam:a": {"id": "seznam:a", "vrsta": "glasba", "naslov": "Pesem", "youtube": "59o4m222aVw"}})
        self.k.izvedi("mediaPredvajaj", ["seznam:a"])
        for smeti in ("", "ni json", "[1,2]", "{\"stanje\": \"1\"}", "{\"napaka\": 1}", "x" * 5000):
            self.k.yt_sporocilo(smeti)
        self.assertEqual(self.dogodki, [])
        self.k.yt_sporocilo(json.dumps({"napaka": True, "koda": "vgradnja<script>"}))
        self.assertEqual(self.dogodki, [("mediaYtNapaka", {"id": "seznam:a"})])
        self.k.yt_sporocilo(json.dumps({"stanje": 1}))     # po napaki skladba ni vec aktivna
        self.assertEqual(len(self.dogodki), 1)

    def test_sporocilo_stare_skladbe_ne_vpliva_na_novo_izbiro(self):
        self._vnosi(**{"seznam:a": {"id": "seznam:a", "vrsta": "glasba", "naslov": "A", "youtube": "59o4m222aVw"},
                       "r": {"id": "r", "vrsta": "radio", "naslov": "Radio", "url": "https://radio.test/tok.mp3"}})
        self.k.izvedi("mediaPredvajaj", ["seznam:a"])
        self.k.yt_sporocilo(json.dumps({"stanje": 1}))
        self.k.izvedi("mediaPredvajaj", ["r"])
        self.dogodki.clear()
        self.k.yt_sporocilo(json.dumps({"stanje": 0}))
        self.assertEqual(self.dogodki, [])

    def test_ukazi_vgradnega_predvajalnika(self):
        self.assertTrue(self.k.izvedi("mediaYtUkaz", ["pauseVideo"]))
        self.assertTrue(self.k.izvedi("mediaYtUkaz", ["zapri"]))
        self.assertFalse(self.k.izvedi("mediaYtUkaz", ["loadVideoById"]))
        self.assertEqual(self.ukazi, ["pauseVideo", "zapri"])

    def test_zaprto_okno_ustavi_vrsto(self):
        self._vnosi(**{"seznam:a": {"id": "seznam:a", "vrsta": "glasba", "naslov": "A", "youtube": "59o4m222aVw"}})
        self.k.izvedi("mediaPredvajaj", ["seznam:a"])
        self.k.yt_zaprt()
        self.k.yt_zaprt()
        self.assertEqual(self.dogodki, [("mediaYtZaprt", {"id": "seznam:a"})])

    def test_napredek_filma(self):
        self._vnosi(f1={"id": "f1", "vrsta": "film", "naslov": "Film", "url": "https://arhiv.test/film.mp4"})
        self.k.izvedi("mediaPredvajaj", ["f1"])
        uri = "https://arhiv.test/film.mp4"
        self.k.shrani_napredek(uri, 5, 6000)             # prvih nekaj sekund si ne zapomnimo
        self.assertEqual(self.k.napredek_za("f1"), 0)
        self.k.shrani_napredek(uri, 1234.7, 6000)
        self.assertEqual(self.k.napredek_za("f1"), 1234)
        self.k.izvedi("mediaPredvajaj", ["f1"])
        self.assertEqual(self.predvajano[-1][3], 1234)   # nadaljuje, kjer je ostal
        self.k.shrani_napredek(uri, 5990, 6000)          # tik pred koncem: naslednjic od zacetka
        self.assertEqual(self.k.napredek_za("f1"), 0)
        self.k.shrani_napredek(uri, 100, 6000)
        self.k.konec(uri)
        self.assertEqual(self.k.napredek_za("f1"), 0)
        self.assertNotIn(("mediaKonec", {"id": "f1"}), self.dogodki)   # film ne sprozi »naslednje skladbe«
        self.k.shrani_napredek("https://neznano.test/x.mp4", 100, 600)  # ni iz kataloga: nic


class _LaznaKnjiznica:
    """Namesto core/knjiznica_kroga.Knjiznica: vrne, kar bi vrnil Link."""

    def __init__(self):
        self.odgovor, self.odstranjeni = {"ok": False, "koda": "ni_prenosa"}, []

    def seznam(self):
        return [{"kljuc": "a" * 40, "naslov": "Film"}]

    def predvajaj(self, kljuc):
        return self.odgovor

    def odstrani(self, kljuc):
        self.odstranjeni.append(kljuc)
        return True


class PolicaTests(unittest.TestCase):
    """Polica »Na tvojih napravah«: most do knjiznice kroga (seznam, predvajanje, odstranitev)."""

    STREZNIK = {"base_url": "https://192.168.0.9:8443/", "fp": "AA", "token": "zeton"}

    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.predvajano, self.knj = [], _LaznaKnjiznica()
        self.k = K.Katalog(self.mapa.name, dogodek=lambda v, p: None, v_glavni=lambda delo: delo(),
                           predvajaj=lambda *a: self.predvajano.append(a) or True, vdelano=lambda u: True,
                           youtube=lambda u, n: True, youtube_ukaz=lambda u: True, knjiznica=self.knj)

    def test_brez_linka_je_polica_prazna(self):
        k = K.Katalog(self.mapa.name, dogodek=lambda v, p: None, v_glavni=lambda delo: delo(), predvajaj=lambda *a: True,
                      vdelano=lambda u: True, youtube=lambda u, n: True, youtube_ukaz=lambda u: True)
        self.assertEqual(k.izvedi("mediaKnjiznica", []), [])
        self.assertIsNone(k.izvedi("mediaKnjiznicaPredvajaj", ["a" * 40]))
        self.assertFalse(k.izvedi("mediaKnjiznicaOdstrani", ["a" * 40]))

    def test_seznam_in_odstranitev_gresta_v_knjiznico(self):
        self.assertEqual(self.k.izvedi("mediaKnjiznica", [])[0]["naslov"], "Film")
        self.assertTrue(self.k.izvedi("mediaKnjiznicaOdstrani", ["a" * 40]))
        self.assertEqual(self.knj.odstranjeni, ["a" * 40])

    def test_film_z_druge_naprave_gre_skozi_lokalni_pretok_in_se_nadaljuje(self):
        self.knj.odgovor = {"ok": True, "vnos": {"kljuc": "a" * 40, "naslov": "Film", "vrsta": "film", "ref": "stremio:s1:movie:tt1"},
                            "tok": {"server": self.STREZNIK, "path": "/magnet/abcdef0123456789", "name": "Film.mkv"}}
        r = self.k.izvedi("mediaKnjiznicaPredvajaj", ["a" * 40])
        self.assertEqual((r["native"], r["id"], r["naslov"]), (True, "stremio:s1:movie:tt1", "Film"))
        uri, vrsta, ime, zacetek, podnapisi, prikazi = self.predvajano[0]
        self.assertRegex(uri, r"^http://127\.0\.0\.1:\d+/")       # predvajalnik bere lokalni naslov, ne naprave z zetonom
        self.assertNotIn("zeton", uri)
        self.assertEqual((vrsta, ime, zacetek, prikazi), ("video", "Film", 0, True))
        self.k.shrani_napredek(uri, 300, 6000)
        self.k.izvedi("mediaKnjiznicaPredvajaj", ["a" * 40])
        self.assertEqual(self.predvajano[-1][3], 300)             # nadaljuje pod oznako izvirnega naslova
        self.assertEqual(self.k.napredek_za("stremio:s1:movie:tt1"), 300)

    def test_tok_ki_ni_tok_torrenta_se_ne_predvaja(self):
        for streznik, pot in ((self.STREZNIK, "/d/disk:%2Fetc%2Fpasswd"), (dict(self.STREZNIK, base_url="https://8.8.8.8"), "/magnet/abcdef0123456789")):
            self.knj.odgovor = {"ok": True, "vnos": {"kljuc": "a" * 40, "naslov": "Film", "vrsta": "film"}, "tok": {"server": streznik, "path": pot}}
            self.assertEqual(self.k.izvedi("mediaKnjiznicaPredvajaj", ["a" * 40]), {"napaka_koda": "napaka"})
        self.assertEqual(self.predvajano, [])

    def test_napaka_naprave_je_kratka_koda(self):
        self.knj.odgovor = {"ok": False, "koda": "ni_prostora"}
        self.assertEqual(self.k.izvedi("mediaKnjiznicaPredvajaj", ["a" * 40]), {"napaka_koda": "ni_prostora"})

    def test_prenos_tega_racunalnika_gre_naravnost_iz_torrenta(self):
        class Mc:
            def __init__(self):
                self.vnosi = {}

            def knjiznica_vnos(self, v):
                self.vnosi["knjiznica:" + v["kljuc"]] = {"id": v.get("ref") or "knjiznica:" + v["kljuc"], "naslov": v["naslov"], "vrsta": "film",
                                                         "url": "http://127.0.0.1:5555/t/x/Film.mkv"}

            def resolve(self, ident):
                return self.vnosi.get(ident)
        self.k._mc = Mc()
        self.knj.odgovor = {"ok": True, "tukaj": {"kljuc": "b" * 40, "naslov": "Moj film", "vrsta": "film", "ref": "r1"}}
        r = self.k.izvedi("mediaKnjiznicaPredvajaj", ["b" * 40])
        self.assertEqual((r["native"], r["id"]), (True, "r1"))
        self.assertEqual(self.predvajano[0][:3], ("http://127.0.0.1:5555/t/x/Film.mkv", "video", "Moj film"))

    def test_stran_ima_besedila_police_v_vseh_jezikih(self):
        with open(os.path.join(KOREN, "assets", "os", "besedila.js"), encoding="utf-8") as f:
            besedila = f.read()
        with open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8") as f:
            kljuci = set(re.findall(r'\bt\("(knjiznica[A-Za-z0-9_]+)"', f.read()))
        self.assertGreaterEqual(len(kljuci), 8)
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            bloki = "\n".join(re.findall(r"Object\.assign\(BESEDILA_OS\.%s, \{(.*?)\}\);" % jezik, besedila, re.S))
            for kljuc in kljuci:
                self.assertIn('"%s":' % kljuc, bloki, "%s manjka v %s" % (kljuc, jezik))


class TovorTests(unittest.TestCase):
    def test_katalog_je_v_paketu(self):
        with open(os.path.join(KOREN, "packaging", "install_os_payload.sh"), encoding="utf-8") as f:
            tovor = f.read()
        for modul in ("os_katalog", "os_media", "knjiznica_kroga", "media_servers", "tok_izbira", "watch_providers", "zakoniti_viri",
                      "uvoz_seznama", "seznami_sink", "link_pretok"):
            self.assertRegex(tovor, r"\b%s\b" % modul)
        self.assertTrue(os.path.exists(os.path.join(KOREN, "assets", "os", "katalog.css")))

    def test_stran_ima_besedila_kataloga_v_vseh_jezikih(self):
        with open(os.path.join(KOREN, "assets", "os", "besedila.js"), encoding="utf-8") as f:
            besedila = f.read()
        with open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8") as f:
            koda = f.read()
        kljuci = set(re.findall(r'\bt\("(kat[A-Za-z0-9_]+)"', koda))
        self.assertGreater(len(kljuci), 30)
        jeziki = ("sl", "en", "de", "es", "fr", "it")
        for jezik in jeziki:
            bloki = "\n".join(re.findall(r"Object\.assign\(BESEDILA_OS\.%s, \{(.*?)\}\);" % jezik, besedila, re.S))
            manjka = sorted(k for k in kljuci if not re.search(r'"?\b%s"?\s*:' % re.escape(k), bloki))
            self.assertEqual(manjka, [], jezik)


if __name__ == "__main__":
    unittest.main()
