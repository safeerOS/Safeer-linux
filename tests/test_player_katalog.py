"""Spletni katalog v domacem Safeer Playerju (core/os_player_katalog.py, core/os_player_gtk_katalog.py)."""
import json
import os
import re
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core import izvirni_jezik, os_player_katalog as pk

KOREN = Path(__file__).resolve().parent.parent


class TestIzbire(unittest.TestCase):
    def test_kategorije_kot_na_strani(self):
        js = (KOREN / "assets/os/os.js").read_text(encoding="utf-8")
        vrste = re.search(r"var KAT_VRSTE = \{([^}]*)\}", js).group(1)
        na_strani = {v for v in re.findall(r':\s*"([^"]*)"', vrste) if v}
        self.assertEqual({k for k, _ in pk.KATEGORIJE}, na_strani)

    def test_filmske_zvrsti_kot_na_strani(self):
        js = (KOREN / "assets/os/os.js").read_text(encoding="utf-8")
        blok = js[js.index("var KAT_FILMSKI_ZANRI"):js.index("var KAT_JEZIKI")]
        self.assertEqual([z for z, _ in pk.FILMSKE_ZVRSTI], re.findall(r'\["(\d+)"', blok))

    def test_razvrstitve_kot_jedro(self):
        from core import os_media
        self.assertEqual(tuple(k for k, _ in pk.RAZVRSTITVE), os_media.MediaCenter.RAZVRSTITVE)

    def test_vsi_jeziki_imajo_ime(self):
        self.assertEqual(set(izvirni_jezik.KODE) - set(pk.IMENA_JEZIKOV), set())
        seznam = pk.jeziki("sl")
        self.assertEqual(seznam[0], ("", "Vsi jeziki"))
        self.assertEqual([k for k, _ in seznam[1:3]], ["sl", "en"])
        self.assertEqual(len(seznam), len(izvirni_jezik.KODE) + 1)

    def test_skupina_zvrsti_in_jezik(self):
        self.assertEqual(pk.skupina_zvrsti("serija"), "film")
        self.assertEqual(pk.skupina_zvrsti("radio"), "radio")
        self.assertEqual(pk.skupina_zvrsti("video"), "")
        self.assertTrue(pk.jezik_velja("film"))
        self.assertFalse(pk.jezik_velja("radio"))
        self.assertEqual(pk.zvrsti("video"), [])
        self.assertEqual(pk.zvrsti("film")[0], ("", "Vse vsebine"))
        self.assertEqual(pk.zvrsti("glasba")[0], ("", "Vsa glasba"))
        self.assertGreater(len(pk.zvrsti("glasba")), 1)

    def test_argumenti(self):
        self.assertEqual(pk.argumenti("", "film", "35", 1, "", "en"), ["", "film", "35", 1, "", [], False, [], "en"])
        # jezik pri radiu ne velja; neznana vrsta/razvrstitev/jezik se ne preneseta naprej
        self.assertEqual(pk.argumenti("x", "radio", "", 0, "zz", "en")[1:], ["radio", "", 1, "", [], False, [], ""])
        self.assertEqual(pk.argumenti("", "nekaj", "", 2, "", "xx")[1], "vse")
        self.assertEqual(pk.argumenti("", "film", "", 1, "", "xx")[8], "")
        self.assertEqual(len(pk.argumenti("a" * 500)[0]), 120)

    def test_kartica(self):
        k = pk.kartica({"id": "a1", "naslov": "Film", "vrsta": "film", "leto": "1967", "vir": "Internet Archive · javna last",
                        "slika": "https://archive.org/services/img/x", "izvajalec": None})
        self.assertEqual((k["id"], k["naslov"], k["podnaslov"], k["ikona"]), ("a1", "Film", "1967 · Internet Archive", "video-x-generic"))
        self.assertTrue(k["slika"].startswith("https://"))
        # slika brez https se ne nalaga; radio ima svojo ikono; izvajalec pri glasbi
        self.assertEqual(pk.kartica({"slika": "http://x/y.jpg", "vrsta": "radio"})["slika"], "")
        self.assertEqual(pk.kartica({"vrsta": "radio"})["ikona"], "audio-x-generic")
        self.assertEqual(pk.kartica({"vrsta": "glasba", "izvajalec": "Ana"})["podnaslov"], "Ana")
        self.assertEqual(pk.kartica({"vrsta": "tv-v-zivo"})["podnaslov"], "V ŽIVO")

    def test_strani(self):
        self.assertEqual(pk.strani({"skupaj_strani": 17}), 17)
        self.assertEqual(pk.strani({}), 1)
        self.assertEqual(pk.strani(None), 1)


class TestPlakati(unittest.TestCase):
    def test_prenos_samo_https_in_omejitev(self):
        self.assertIsNone(pk.prenesi_sliko("http://primer.si/a.jpg"))
        self.assertIsNone(pk.prenesi_sliko("file:///etc/passwd"))

        class Odgovor:
            def __init__(self, n): self.n = n
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self, m): return b"x" * min(self.n, m)
        self.assertEqual(pk.prenesi_sliko("https://primer.si/a.jpg", odpri=lambda *a, **k: Odgovor(10)), b"x" * 10)
        velika = pk.NAJVEC_BAJTOV + 10
        self.assertIsNone(pk.prenesi_sliko("https://primer.si/a.jpg", odpri=lambda *a, **k: Odgovor(velika)))

    def test_predpomnilnik_omejen_in_rod(self):
        klici = []
        p = pk.Plakati(prenesi=lambda u: (klici.append(u), u.encode())[1], najvec=2)
        dobljeno, konec = [], threading.Event()

        def gotovo(url, podatki, rod):
            dobljeno.append((url, podatki, rod))
            if len(dobljeno) == 3:
                konec.set()
        for u in ("https://a/1", "https://a/2", "https://a/3"):
            p.zahtevaj(u, gotovo)
        self.assertTrue(konec.wait(5))
        self.assertIsNone(p.v_predpomnilniku("https://a/1"))      # najstarejsi je izpadel (najvec=2)
        self.assertEqual(p.v_predpomnilniku("https://a/3"), b"https://a/3")
        n = len(klici)
        p.zahtevaj("https://a/3", gotovo)                          # iz predpomnilnika, brez prenosa
        self.assertEqual(len(klici), n)
        p.ustavi()


class TestZastavicaGtk(unittest.TestCase):
    def test_privzeto_spletni_player(self):
        import safeer_os
        with tempfile.TemporaryDirectory() as d, patch.object(safeer_os.os_programi, "MAPA_NASTAVITEV", d), \
                patch.dict(os.environ, {"SAFEER_PLAYER_GTK": ""}):
            self.assertFalse(safeer_os.player_gtk_vklopljen())
            Path(d, "player.json").write_text(json.dumps({"player_gtk": True}), encoding="utf-8")
            self.assertTrue(safeer_os.player_gtk_vklopljen())
            with patch.dict(os.environ, {"SAFEER_PLAYER_GTK": "0"}):
                self.assertFalse(safeer_os.player_gtk_vklopljen())
            Path(d, "player.json").write_text("{pokvarjeno", encoding="utf-8")
            self.assertFalse(safeer_os.player_gtk_vklopljen())
        with patch.dict(os.environ, {"SAFEER_PLAYER_GTK": "1"}):
            self.assertTrue(safeer_os.player_gtk_vklopljen())


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potreben zaslon")
class TestKatalogPogled(unittest.TestCase):
    def _cakaj(self, pogoj, cas=5.0):
        from gi.repository import GLib
        konec = time.monotonic() + cas
        ctx = GLib.MainContext.default()
        while time.monotonic() < konec and not pogoj():
            ctx.iteration(False)
            time.sleep(0.01)
        return pogoj()

    def test_nalozi_narisi_predvajaj(self):
        from core import os_player_gtk_katalog as g

        class LazniKatalog:
            def __init__(self): self.klici = []
            def izvedi(self, metoda, a):
                self.klici.append((metoda, a))
                if metoda == "mediaKatalog":
                    return {"kljuc": "k", "skupaj_strani": 3, "vnosi": [
                        {"id": "1", "naslov": "Prvi", "vrsta": "film", "leto": "1950"},
                        {"id": "2", "naslov": "Drugi", "vrsta": "film"}]}
                if metoda == "mediaPredvajaj":
                    return {"napaka_koda": "ni_toka"}
                return []
        lk, sporocila = LazniKatalog(), []
        pogled = g.KatalogPogled(predvajaj=lambda *a: True, sporocilo=sporocila.append, katalog=lk)
        pogled.izberi_vrsto("film")
        self.assertTrue(self._cakaj(lambda: len(pogled.mreza.get_children()) == 2))
        self.assertEqual(lk.klici[-1], ("mediaKatalog", ["", "film", "", 1, "", [], False, [], ""]))
        self.assertEqual(pogled.lbl_stran.get_text(), "Stran 1 od 3")
        self.assertFalse(pogled.btn_prejsnja.get_sensitive())
        pogled.izbira_jezika.set_active_id("en")
        self.assertTrue(self._cakaj(lambda: lk.klici[-1][1][8] == "en"))
        pogled.pojdi_na_stran(2)
        self.assertTrue(self._cakaj(lambda: lk.klici[-1][1][3] == 2))
        pogled.predvajaj_id("1", "Prvi")
        self.assertTrue(self._cakaj(lambda: any("ni na voljo" in s for s in sporocila)))
        pogled.ustavi()
        pogled.destroy()

    def test_star_odgovor_ne_rise(self):
        from core import os_player_gtk_katalog as g
        pogled = g.KatalogPogled(predvajaj=lambda *a: True, sporocilo=lambda s: None,
                                 katalog=type("K", (), {"izvedi": lambda s, m, a: {"vnosi": []}})())
        pogled._zahteva = 5
        pogled._narisi({"vnosi": [{"id": "x", "naslov": "Star"}]}, 4)
        self.assertEqual(len(pogled.mreza.get_children()), 0)
        pogled.destroy()

    def test_okno_preklopi_na_katalog(self):
        from core import os_player_gtk
        with patch("core.os_knjiznica.Knjiznica.seznam", return_value=[]), \
                patch("core.os_knjiznica.Knjiznica.tokovi", return_value=[]), \
                patch("core.os_player_gtk_katalog.KatalogPogled.nalozi"):
            okno = os_player_gtk.SafeerPlayerOkno()
            self.assertIsNone(okno.katalog_pogled)        # katalog se ne ustvari ob zagonu
            okno.preklopi_nacin("katalog")
            self.assertIsNotNone(okno.katalog_pogled)
            self.assertEqual(okno.sklad.get_visible_child_name(), "katalog")
            self.assertFalse(okno.kat_box.get_visible())
            okno.preklopi_nacin("zbirka")
            self.assertEqual(okno.sklad.get_visible_child_name(), "knjiznica")
            okno.destroy()


if __name__ == "__main__":
    unittest.main()
