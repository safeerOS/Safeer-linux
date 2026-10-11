"""Lastnik, 11. 10. 2026: »Skrij plošco« je pri zadnji plosci ostal brez ucinka in ni bilo vidnega nacina, kako plosco
(npr. Programe) vrniti; glasbeni dodatek Stremio (skladbe kot »movie«) je napolnil Filme; glasba z diska je bila mreza
enakih kartic. Brez omrezja in brez GTK."""
import os
import re
import sys
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)
from core import media_servers  # noqa: E402


def _beri(pot):
    with open(os.path.join(KOREN, pot), encoding="utf-8") as f:
        return f.read()


class Plosce(unittest.TestCase):
    def test_skrij_vedno_deluje_in_polje_skritih(self):
        js, html = _beri("assets/os/delovna.js"), _beri("assets/os/delovna.html")
        telo = js.split("function nastaviSkrito(p, skrij) {", 1)[1].split("\n  }", 1)[0]
        self.assertNotIn("length >= 3", telo)          # brez »vsaj ena plosca ostane«
        self.assertIn('id="skritePlosce"', html)
        self.assertIn("function narisiSkritePlosce()", js)
        self.assertIn('p.classList.toggle("vse-skrito"', js)
        for jezik_vrstica in ('pokaziPlosco: "Pokaži ploščo {ime}"', 'pokaziPlosco: "Show the {ime} panel"'):
            self.assertIn(jezik_vrstica, js)


class GlasbeniDodatki(unittest.TestCase):
    def test_glasbeno_ime(self):
        for ime in ("Flix-Music", "Top Music", "Koncerti", "Last.fm", "lastfm charts", "VEVO", "Glasba"):
            self.assertTrue(media_servers.glasbeno_ime(ime), ime)
        for ime in ("Torrentio", "Cinemeta", "Musical Movies", "Popular", ""):
            self.assertFalse(media_servers.glasbeno_ime(ime), ime)

    def test_razred_kataloga(self):
        v = media_servers.stremio_vrsta_kataloga
        self.assertEqual(v("movie", "Flix-Music", "Top"), "glasba")
        self.assertEqual(v("channel", "", "Music videos"), "glasba")
        self.assertEqual(v("movie", "Torrentio", "Popular"), "film")
        self.assertEqual(v("tv", "Music TV", ""), "tv-v-zivo")     # kanali v zivo ostanejo, kjer so

    def test_izvajalec(self):
        self.assertEqual(media_servers._stremio_izvajalec({"cast": ["Olivia Rodrigo"]}), "Olivia Rodrigo")
        self.assertEqual(media_servers._stremio_izvajalec({"artist": "ADÉLA", "cast": ["x"]}), "ADÉLA")
        self.assertEqual(media_servers._stremio_izvajalec({}), "")


class SkladbeZDiska(unittest.TestCase):
    def test_seznam_skladb(self):
        js, css = _beri("assets/os/os.js"), _beri("assets/os/os.css")
        self.assertIn("function mediaSkladba(v)", js)
        self.assertIn('vrsta === "vse" && skladbe.length > 8', js)
        self.assertIn(".media-skladbe {", css)
        bes = _beri("assets/os/besedila.js")
        for j in ("sl", "en", "de", "es", "fr", "it"):
            self.assertTrue(re.search(r'BESEDILA_OS\.%s, \{"mediaVseSkladbe": "[^"]*\{n\}' % j, bes), j)


if __name__ == "__main__":
    unittest.main()
