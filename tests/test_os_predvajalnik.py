"""Prehodi čakalne vrste brez potrebe po zvočni napravi ali GTK seji."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.os_predvajalnik import Predvajalnik, Skladba, medij


class Element:
    def __init__(self):
        self.stanja = []
        self.lastnosti = {}
        self.skoki = []
        self.vodilo = SimpleNamespace(add_signal_watch=lambda: None,
                                     remove_signal_watch=lambda: None, connect=lambda *_: None)

    def get_bus(self):
        return self.vodilo

    def set_state(self, stanje):
        self.stanja.append(stanje)
        return "ok"

    def set_property(self, ime, vrednost):
        self.lastnosti[ime] = vrednost

    def get_property(self, ime):
        return self.lastnosti.get(ime, {"flags": 0x17, "n-text": 0, "current-text": -1}.get(ime))

    def emit(self, _signal, _i):
        return None

    def query_duration(self, _format):
        return True, 180_000_000_000

    def query_position(self, _format):
        return True, 25_000_000_000

    def seek_simple(self, format_, flags, target):
        self.skoki.append((format_, flags, target))
        return True


class PredvajalnikTests(unittest.TestCase):
    def setUp(self):
        self.element = Element()
        self.gst = SimpleNamespace(ElementFactory=SimpleNamespace(make=lambda *_: self.element),
                                   State=SimpleNamespace(NULL="null", PLAYING="playing", PAUSED="paused"),
                                   StateChangeReturn=SimpleNamespace(FAILURE="failure"),
                                   Format=SimpleNamespace(TIME="time"), SECOND=1_000_000_000,
                                   CLOCK_TIME_NONE=2**64 - 1,
                                   SeekFlags=SimpleNamespace(FLUSH=1, KEY_UNIT=2),
                                   MessageType=SimpleNamespace(EOS="eos", ERROR="error", ASYNC_DONE="async_done"))
        self.player = Predvajalnik(self.gst)

    def test_vrsta_napreduje_ob_koncu_in_se_ustavi(self):
        self.player.dodaj("https://example.test/ena.mp3")
        self.player.dodaj("https://example.test/dve.flac")
        self.assertEqual(self.player.trenutna.naslov, "ena.mp3")
        self.player._sporocilo(None, SimpleNamespace(type="eos"))
        self.assertEqual(self.player.trenutna.naslov, "dve.flac")
        self.player._sporocilo(None, SimpleNamespace(type="eos"))
        self.assertEqual(self.player.stanje, "ustavljeno")
        self.assertEqual(self.element.lastnosti["uri"], "https://example.test/dve.flac")

    def test_premor_in_napaka(self):
        self.player.dodaj("https://example.test/radio")
        self.player.premor()
        self.assertEqual(self.player.stanje, "premor")
        self.player.premor()
        self.assertEqual(self.player.stanje, "predvaja")
        napaka = SimpleNamespace(domain="gst-stream-error-quark", code=6)
        self.player._sporocilo(None, SimpleNamespace(type="error", parse_error=lambda: (napaka, "")))
        self.assertEqual(self.player.stanje, "napaka")
        self.assertEqual(self.player.napaka, "format")

    def test_napake_so_razumljive_kode(self):
        from core.os_predvajalnik import vrsta_napake, NAPAKE
        tok = SimpleNamespace(domain="gst-stream-error-quark", code=1)   # souphttpsrc: Internal data stream error
        self.assertEqual(vrsta_napake(tok, "https://neobstaja.invalid/tok.mp3"), "tok")
        self.assertEqual(vrsta_napake(SimpleNamespace(domain="gst-resource-error-quark", code=3), "file:///x.mp3"), "datoteka")
        self.assertEqual(vrsta_napake(SimpleNamespace(domain="gst-stream-error-quark", code=13), "https://a/b"), "zascita")
        self.assertEqual(vrsta_napake("x", "file:///x.mp3"), "splosno")
        for koda in ("tok", "datoteka", "format", "zascita", "zacetek", "splosno"):
            self.assertIn(koda, NAPAKE)

    def test_lokalni_uri_in_zavrnjene_sheme(self):
        with tempfile.TemporaryDirectory() as mapa:
            pot = Path(mapa) / "moja pesem.flac"
            pot.touch()
            self.assertEqual(medij(pot.as_uri()).naslov, pot.name)
        for uri in ("javascript:alert(1)", "file:///ne-obstaja.mp3", "https:///brez-gostitelja"):
            with self.assertRaises(ValueError):
                medij(uri)

    def test_tv_tok_brez_koncnice_ostane_oznacen_v_zivo(self):
        self.player.dodaj("https://example.test/live/channel?id=7", vrsta="tv")
        self.assertEqual(self.player.trenutna.vrsta, "tv")
        self.assertEqual(self.element.lastnosti["uri"], "https://example.test/live/channel?id=7")
        with self.assertRaises(ValueError):
            self.player.dodaj("https://example.test/live", vrsta="neznano")

    def test_premik_po_posnetku_in_zascita_prenosa_v_zivo(self):
        self.player.dodaj("https://example.test/film.mp4")
        self.assertEqual(self.player.podatki()["pozicija"], 25)
        self.assertEqual(self.player.podatki()["trajanje"], 180)
        self.assertTrue(self.player.skok(999))
        self.assertEqual(self.element.skoki[-1], ("time", 3, 180_000_000_000))
        self.player.dodaj("https://example.test/live.m3u8", predvajaj=True, vrsta="tv")
        self.assertFalse(self.player.skok(15))
        self.assertEqual(len(self.element.skoki), 1)
        self.player.dodaj("https://example.test/radio", predvajaj=True, vrsta="radio", naslov="Radio Svet")
        self.assertEqual(self.player.podatki()["naslov"], "Radio Svet")
        self.assertFalse(self.player.skok(15))

    def test_nadaljevanje_pocaka_na_trajanje_in_se_izvede_enkrat(self):
        koncano = []
        self.player.konec = koncano.append
        self.player.dodaj("https://example.test/film.mp4", zacetek=72)
        self.assertEqual(self.element.skoki, [])
        self.player._sporocilo(None, SimpleNamespace(type="async_done"))
        self.assertEqual(self.element.skoki[-1], ("time", 3, 72_000_000_000))
        self.player._sporocilo(None, SimpleNamespace(type="async_done"))
        self.assertEqual(len(self.element.skoki), 1)
        self.player._sporocilo(None, SimpleNamespace(type="eos"))
        self.assertEqual(koncano, ["https://example.test/film.mp4"])

    def test_lokalni_video_nadaljuje_od_shranjenega_polozaja(self):
        self.player.dodaj("https://example.test/film.mp4", vrsta="video", zacetek=72)
        self.player._sporocilo(None, SimpleNamespace(type="async_done"))
        self.assertEqual(self.element.skoki[-1], ("time", 3, 72_000_000_000))

    def test_nov_album_zamenja_prejsnjo_cakalno_vrsto(self):
        self.player.dodaj("https://example.test/stara.mp3")
        album = [Skladba("https://example.test/ena.mp3", "Ena"),
                 Skladba("https://example.test/dve.mp3", "Dve")]
        self.assertTrue(self.player.zamenjaj_vrsto(album))
        self.assertEqual(self.player.podatki()["skupaj"], 2)
        self.assertEqual(self.player.trenutna.naslov, "Ena")
        self.player._sporocilo(None, SimpleNamespace(type="eos"))
        self.assertEqual(self.player.trenutna.naslov, "Dve")

    def test_album_zacne_pri_izbrani_in_zna_nazaj(self):
        album = [Skladba("https://example.test/ena.mp3", "Ena"),
                 Skladba("https://example.test/dve.mp3", "Dve")]
        self.assertTrue(self.player.zamenjaj_vrsto(album, 1))
        self.assertEqual(self.player.trenutna.naslov, "Dve")
        self.assertFalse(self.player.naslednja())
        self.assertTrue(self.player.prejsnja())
        self.assertEqual(self.player.trenutna.naslov, "Ena")
        self.assertFalse(self.player.zamenjaj_vrsto(album, 2))


if __name__ == "__main__":
    unittest.main()


class PodnapisiTests(unittest.TestCase):
    def setUp(self):
        self.element = Element()
        self.gst = SimpleNamespace(ElementFactory=SimpleNamespace(make=lambda *_: self.element),
                                   State=SimpleNamespace(NULL="null", PLAYING="playing", PAUSED="paused", READY="ready"),
                                   StateChangeReturn=SimpleNamespace(FAILURE="failure"),
                                   Format=SimpleNamespace(TIME="time"), SECOND=1_000_000_000,
                                   CLOCK_TIME_NONE=2**64 - 1,
                                   SeekFlags=SimpleNamespace(FLUSH=1, KEY_UNIT=2),
                                   MessageType=SimpleNamespace(EOS="eos", ERROR="error", ASYNC_DONE="async_done"))
        self.player = Predvajalnik(self.gst)
        self.shranjeno = []
        self.player.shrani_podnapise = self.shranjeno.append
        self.player.jezik_sistema = "sl"

    def video(self, *podnapisi):
        return Skladba("https://example.test/film.mkv", "film", "video", podnapisi=tuple(podnapisi))

    def test_edini_podnapis_se_vklopi_sam(self):
        self.player.zamenjaj_vrsto([self.video(("https://example.test/film.srt", "film.srt", "", ""))])
        self.assertEqual(self.element.lastnosti["suburi"], "https://example.test/film.srt")
        self.assertTrue(self.element.lastnosti["flags"] & 4)
        # Ko playbin pozna tokove, izbere dodano datoteko (zadnji tok besedila).
        self.element.lastnosti["n-text"] = 2
        self.player._sporocilo(None, SimpleNamespace(type="async_done"))
        self.assertEqual(self.element.lastnosti["current-text"], 1)

    def test_jezik_sistema_med_vec_podnapisi(self):
        self.player.zamenjaj_vrsto([self.video(("https://e.test/a.srt", "film.en.srt", "en", ""),
                                               ("https://e.test/b.srt", "film.sl.srt", "sl", ""))])
        self.assertEqual(self.element.lastnosti["suburi"], "https://e.test/b.srt")

    def test_izklop_velja_za_naslednje_videe(self):
        self.player.zamenjaj_vrsto([self.video(("https://e.test/a.srt", "film.srt", "", ""))])
        self.assertTrue(self.player.izberi_podnapise("izklop"))
        self.assertFalse(self.element.lastnosti["flags"] & 4)
        self.assertEqual(self.shranjeno[-1]["izklop"], True)
        self.player.zamenjaj_vrsto([self.video(("https://e.test/c.srt", "drugi.srt", "", ""))])
        self.assertIsNone(self.element.lastnosti["suburi"])
        self.assertFalse(self.element.lastnosti["flags"] & 4)

    def test_druga_datoteka_nadaljuje_na_istem_mestu(self):
        self.player.zamenjaj_vrsto([self.video(("https://e.test/a.srt", "film.en.srt", "en", ""),
                                               ("https://e.test/b.srt", "film.de.srt", "de", ""))])
        self.assertTrue(self.player.izberi_podnapise("z:1"))
        self.assertEqual(self.element.lastnosti["suburi"], "https://e.test/b.srt")
        self.assertIn("ready", self.element.stanja)
        self.assertEqual(self.player._cakaj_zacetek, 25)
        self.assertEqual(self.shranjeno[-1], {"izklop": False, "jezik": "de"})
        izbira = self.player.podnapisi()
        self.assertEqual([m["kljuc"] for m in izbira["moznosti"]], ["z:0", "z:1"])

    def test_nevaren_naslov_podnapisa_zavrnemo(self):
        self.player.zamenjaj_vrsto([self.video(("javascript:alert(1)", "x.srt", "", ""))])
        self.assertEqual(self.player.trenutna.podnapisi, ())

    def test_podnapis_popravimo_pred_nalaganjem(self):
        self.player.nit = False
        self.player.pripravi_podnapis = lambda uri, ime: "file:///cache/" + ime
        self.player.zamenjaj_vrsto([self.video(("http://127.0.0.1:9/t/x/film.srt", "film.srt", "", ""))])
        self.assertEqual(self.element.lastnosti["suburi"], "file:///cache/film.srt")

    def test_priprava_v_ozadju_nalozi_na_istem_mestu(self):
        klici = []
        self.player.v_glavni = lambda f: klici.append(f)
        self.player.pripravi_podnapis = lambda uri, ime: "file:///cache/" + ime
        import threading
        dogodek = threading.Event()
        izvirna = self.player._pripravi_v_ozadju

        def sinhrono(uri, ime, indeks, k):
            self.player._pripravljeni[uri] = self.player.pripravi_podnapis(uri, ime)
            klici.append(lambda: self.player._podnapis_pripravljen(indeks, k))
            dogodek.set()
        self.player._pripravi_v_ozadju = sinhrono
        self.player.zamenjaj_vrsto([self.video(("http://127.0.0.1:9/t/x/film.srt", "film.srt", "", ""))])
        self.assertIsNone(self.element.lastnosti["suburi"])       # še ni pripravljen
        klici.pop()()
        self.assertEqual(self.element.lastnosti["suburi"], "file:///cache/film.srt")
        self.assertIn("ready", self.element.stanja)
        self.assertTrue(izvirna)

