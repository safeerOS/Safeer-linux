"""»Nadaljuj z druge naprave« z racunalnika (core/link_predvajanje.py): play.state in play.stop."""
import os
import shutil
import sys
import tempfile
import unittest
import urllib.parse

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec, link_datoteke, link_predvajanje  # noqa: E402


class Predaja(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-predaja-")
        self.deljena = os.path.join(self.mapa, "Filmi")
        os.makedirs(os.path.join(self.deljena, "Serije"))
        self.film = os.path.join(self.deljena, "Serije", "e01 - Pilot.mkv")
        with open(self.film, "wb") as d:
            d.write(b"x" * 100)
        self.zunaj = os.path.join(self.mapa, "zasebno.mp4")
        with open(self.zunaj, "wb") as d:
            d.write(b"y" * 10)
        self.d = link_datoteke.Datoteke([self.deljena], tls_mapa=os.path.join(self.mapa, "tls"))
        self.stanje = {}
        self.ustavljeno = []

        def premor():
            self.ustavljeno.append(True)
            return True
        self.p = link_predvajanje.Predvajanje(lambda: self.stanje, premor, self.d, lambda: self.zadnji, lambda: self.deli)
        self.zadnji = None
        self.deli = True

    def tearDown(self):
        self.d.ustavi()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_datoteka_iz_deljene_mape_gre_s_streznikom_in_zetonom(self):
        self.stanje = {"stanje": "predvaja", "uri": "file://" + urllib.parse.quote(self.film), "naslov": "Pilot",
                       "vrsta": "video", "pozicija": 61.4, "trajanje": 2400.0}
        o = self.p.stanje("n-telefon", "")
        self.assertTrue(o["shared"] and o["playing"] and o["is_playing"])
        self.assertEqual((o["position_ms"], o["duration_ms"]), (61400, 2400000))
        self.assertEqual(o["item"]["id"], "share:0:Serije/e01 - Pilot.mkv")
        self.assertEqual(o["item"]["naslov"], "Pilot")
        self.assertTrue(o["item"]["video"])
        self.assertEqual(o["item"]["mime"], "video/x-matroska")
        s = o["server"]
        self.assertTrue(s["base_url"].startswith("https://") and s["fp"] and s["token"])
        self.assertEqual(o["item"]["zvok"], s["base_url"] + "/d/share%3A0%3ASerije%2Fe01%20-%20Pilot.mkv")
        self.assertEqual(o["item"]["povezava"], "")  # predvajalnik ne kaze naslova streznika
        self.assertTrue(self.d.streznik.tece())
        self.assertTrue(self.d.streznik.zeton_velja(s["token"]))
        self.assertNotIn("server_device", o)

    def test_premor_je_is_playing_false(self):
        self.stanje = {"stanje": "premor", "uri": "file://" + self.film, "naslov": "Pilot", "vrsta": "video",
                       "pozicija": 5, "trajanje": 100}
        o = self.p.stanje("n-telefon", "")
        self.assertTrue(o["playing"])
        self.assertFalse(o["is_playing"])

    def test_datoteka_zunaj_deljenih_map_ostane_doma(self):
        self.stanje = {"stanje": "predvaja", "uri": "file://" + self.zunaj, "naslov": "Zasebno", "vrsta": "video",
                       "pozicija": 10, "trajanje": 100}
        o = self.p.stanje("n-telefon", "")
        self.assertEqual(o, {"shared": True, "playing": False, "reason": "ni_deljeno"})
        self.assertFalse(self.d.streznik.tece())

    def test_brez_deljenih_map_in_brez_datotek(self):
        prazne = link_datoteke.Datoteke([], tls_mapa=os.path.join(self.mapa, "tls2"))
        p = link_predvajanje.Predvajanje(lambda: self.stanje, lambda: False, prazne)
        self.stanje = {"stanje": "predvaja", "uri": "file://" + self.film, "naslov": "Pilot", "vrsta": "video",
                       "pozicija": 10, "trajanje": 100}
        self.assertEqual(p.stanje("n-telefon", "")["reason"], "ni_deljeno")
        p = link_predvajanje.Predvajanje(lambda: self.stanje, lambda: False, None)
        self.assertEqual(p.stanje("n-telefon", "")["reason"], "ni_deljeno")

    def test_spletni_tok_gre_s_svojim_naslovom(self):
        self.stanje = {"stanje": "predvaja", "uri": "https://primer.si/tok/film.mp4", "naslov": "Film", "vrsta": "video",
                       "pozicija": 1, "trajanje": 2}
        o = self.p.stanje("n-telefon", "")
        self.assertTrue(o["playing"])
        self.assertEqual(o["item"]["zvok"], "https://primer.si/tok/film.mp4")
        self.assertEqual(o["item"]["id"], "https://primer.si/tok/film.mp4")
        self.assertEqual(o["item"]["povezava"], "https://primer.si/tok/film.mp4")
        self.assertTrue(o["item"]["video"])
        self.assertNotIn("server", o)
        self.assertFalse(self.d.streznik.tece())

    def test_tv_in_radio(self):
        self.stanje = {"stanje": "predvaja", "uri": "https://primer.si/tv.m3u8", "naslov": "RTV SLO 1", "vrsta": "tv",
                       "pozicija": 0, "trajanje": 0}
        o = self.p.stanje("n", "")
        self.assertEqual(o["item"]["kanal"], "RTV SLO 1")
        self.assertTrue(o["item"]["video"])
        self.stanje = {"stanje": "predvaja", "uri": "https://primer.si/radio", "naslov": "Val 202", "vrsta": "radio",
                       "pozicija": 0, "trajanje": 0}
        o = self.p.stanje("n", "")
        self.assertTrue(o["item"]["radio"])
        self.assertFalse(o["item"]["video"])

    def test_lokalni_posrednik_in_dvd_ostaneta_doma(self):
        for uri in ("http://127.0.0.1:43210/m/skrivnost/film.mkv", "http://localhost:5/x", "dvd:///dev/sr0"):
            self.stanje = {"stanje": "predvaja", "uri": uri, "naslov": "x", "vrsta": "video", "pozicija": 1, "trajanje": 2}
            self.assertEqual(self.p.stanje("n", "")["reason"], "ni_deljeno", uri)

    def test_datoteka_tretje_naprave_gre_z_id_naprave(self):
        self.stanje = {"stanje": "predvaja", "uri": "http://127.0.0.1:43210/m/skrivnost/film.mkv", "naslov": "Film",
                       "vrsta": "video", "pozicija": 30, "trajanje": 90, "naprava": "n-telefon2",
                       "oznaka": "media:video:17", "izvirnik": "https://192.168.0.5:4433/d/media%3Avideo%3A17"}
        o = self.p.stanje("n", "")
        self.assertTrue(o["playing"])
        self.assertEqual(o["server_device"], "n-telefon2")
        self.assertEqual(o["item"]["id"], "media:video:17")
        self.assertEqual(o["item"]["zvok"], "https://192.168.0.5:4433/d/media%3Avideo%3A17")
        self.assertNotIn("server", o)

    def test_nic_ne_igra_pove_zadnji_video(self):
        self.stanje = {"stanje": "ustavljeno"}
        self.zadnji = {"pot": self.film, "ime": "Pilot", "pozicija": 1500, "trajanje": 2400, "zadnjic": 1_700_000_000}
        o = self.p.stanje("n-telefon", "")
        self.assertFalse(o["playing"])
        self.assertTrue(o["last"])
        self.assertEqual((o["position_ms"], o["duration_ms"], o["when"]), (1500000, 2400000, 1_700_000_000_000))
        self.assertEqual(o["item"]["id"], "share:0:Serije/e01 - Pilot.mkv")
        self.assertIn("server", o)

    def test_nic_ne_igra_in_zadnji_zunaj_deljenih(self):
        self.stanje = None
        self.zadnji = {"pot": self.zunaj, "ime": "Zasebno", "pozicija": 10, "trajanje": 100, "zadnjic": 1}
        self.assertEqual(self.p.stanje("n", ""), {"shared": True, "playing": False})

    def test_izklop_deljenja(self):
        self.deli = False
        self.stanje = {"stanje": "predvaja", "uri": "file://" + self.film, "naslov": "Pilot", "vrsta": "video",
                       "pozicija": 10, "trajanje": 100}
        self.assertEqual(self.p.stanje("n", ""), {"shared": False})

    def test_ustavi_je_samo_premor(self):
        self.assertEqual(self.p.ustavi(), {"stopped": True})
        self.assertEqual(self.ustavljeno, [True])
        p = link_predvajanje.Predvajanje(lambda: None, lambda: (_ for _ in ()).throw(RuntimeError("ni")), None)
        self.assertEqual(p.ustavi(), {"stopped": False})

    def test_pot_iz_uri(self):
        self.assertEqual(link_predvajanje.pot_iz_uri("file:///tmp/a%20b.mkv"), "/tmp/a b.mkv")
        self.assertEqual(link_predvajanje.pot_iz_uri("/tmp/a.mkv"), "/tmp/a.mkv")
        self.assertEqual(link_predvajanje.pot_iz_uri("C:\\Filmi\\a.mkv"), "C:\\Filmi\\a.mkv")
        self.assertEqual(link_predvajanje.pot_iz_uri("https://x/a.mkv"), "")
        self.assertEqual(link_predvajanje.pot_iz_uri("file://streznik/a.mkv"), "")

    def test_daljinec_odgovori_v_ozadju(self):
        import threading
        self.stanje = {"stanje": "predvaja", "uri": "file://" + self.film, "naslov": "Pilot", "vrsta": "video",
                       "pozicija": 10, "trajanje": 100}
        izidi, koncano = [], threading.Event()

        def koncaj(i):
            izidi.append(i)
            koncano.set()
        link_daljinec.izvedi_control("play.state", {}, lambda _u: None, koncaj, datoteke=self.d, posiljatelj="n-telefon",
                                     predvajanje=self.p)
        self.assertTrue(koncano.wait(5))
        self.assertTrue(izidi[0]["ok"] and izidi[0]["data"]["playing"])
        koncano.clear()
        link_daljinec.izvedi_control("play.stop", {}, lambda _u: None, koncaj, predvajanje=self.p)
        self.assertTrue(koncano.wait(5))
        self.assertEqual(izidi[1]["data"], {"stopped": True})
        link_daljinec.izvedi_control("play.state", {}, lambda _u: None, koncaj)
        self.assertEqual(izidi[2]["code"], "ni_na_racunalniku")
        link_daljinec.izvedi_control("status", {}, lambda _u: None, koncaj, datoteke=self.d, predvajanje=self.p)
        self.assertIn("play.state", izidi[3]["data"]["actions"])
        link_daljinec.izvedi_control("status", {}, lambda _u: None, koncaj, datoteke=self.d)
        self.assertNotIn("play.state", izidi[4]["data"]["actions"])


class Knjiznica(unittest.TestCase):
    def test_zadnji_nedokoncan(self):
        from core import os_knjiznica
        mapa = tempfile.mkdtemp(prefix="safeer-knjiznica-")
        try:
            k = os_knjiznica.Knjiznica(os.path.join(mapa, "mediji.sqlite3"))
            a, b = os.path.join(mapa, "a.mkv"), os.path.join(mapa, "b.mkv")
            for pot in (a, b):
                with open(pot, "wb") as d:
                    d.write(b"x")
            with k._baza() as baza:
                baza.execute("INSERT INTO mediji (pot, naslov, vrsta, zadnjic, pozicija, trajanje) VALUES (?,?,?,?,?,?)",
                             (a, "A", "filmi", 100, 600, 7200))
                baza.execute("INSERT INTO mediji (pot, naslov, vrsta, zadnjic, pozicija, trajanje) VALUES (?,?,?,?,?,?)",
                             (b, "B", "serije", 200, 50, 1200))
                baza.execute("INSERT INTO mediji (pot, naslov, vrsta, zadnjic, pozicija, trajanje) VALUES (?,?,?,?,?,?)",
                             (os.path.join(mapa, "ni.mkv"), "Ni", "filmi", 300, 50, 1200))
            z = k.zadnji_nedokoncan()
            self.assertEqual((z["pot"], z["ime"], z["pozicija"], z["trajanje"], z["zadnjic"]), (b, "B", 50, 1200, 200))
            k.ponastavi_napredek(b)
            self.assertEqual(k.zadnji_nedokoncan()["pot"], a)
            k.ponastavi_napredek(a)
            self.assertIsNone(k.zadnji_nedokoncan())
        finally:
            shutil.rmtree(mapa, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
