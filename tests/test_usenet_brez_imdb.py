"""Lastnik 24. 11. 2026 (testni PC): Filmi v nacinu »⚡ Usenet« prazni s »indeksator ne odgovarja«, ceprav je kljuc
veljal. Dodatek »Best Torrents« daje filme brez IMDb (movie_best_torrents_<n>), Usenet isce po IMDb. Safeer zdaj
poisce IMDb po naslovu in letu (core/imdb_po_naslovu.py, Cinemeta); kar ostane brez IMDb, se ne sme kazati kot
»indeksator ne odgovarja«. Brez omrezja: Cinemeta in indeksator sta nadomestka."""
import json
import unittest

from core import imdb_po_naslovu as I, usenet_filter as UF, os_media
from test_usenet_filter import Indeksator, Ura, Vrsta, _rezultat

CINEMETA = [{"id": "tt29611136", "name": "Wicker", "releaseInfo": "2026"},
            {"id": "tt0324554", "name": "Wicker Park", "releaseInfo": "2004"},
            {"id": "tt0070917", "name": "The Wicker Man", "releaseInfo": "1973"},
            {"id": "tt0450345", "name": "The Wicker Man", "releaseInfo": "2006"}]


def _best(n, naslov, slika=""):
    ident = "movie_best_torrents_%d" % n
    return {"id": "stremio:b:movie:%s" % ident, "naslov": naslov, "vrsta": "film", "leto": "0", "imdb_id": "",
            "tmdb_id": 0, "slika": slika, "url": "stremio:https://fun.primer|movie|%s" % ident}


def _filter(iskalnik):
    ura, vrsta, ix = Ura(), Vrsta(), Indeksator()
    f = UF.UsenetFilter(None, ix, ura=ura, izvajalec=vrsta, spi=ura.spi)
    m = UF.FilterMreze(f, os_media.MediaCenter._kljuc_razpolozljivosti, os_media.MediaCenter._stremio_naslov_vnosa,
                       lambda: UF.tok_izbira.Zmoznosti(), imdb_filma=iskalnik)
    m.casovniki = False
    return m, vrsta, ix


class IzbiraPoNaslovu(unittest.TestCase):
    def test_enak_naslov_in_leto(self):
        self.assertEqual(I.izberi(CINEMETA, "Wicker", 2026), "tt29611136")
        self.assertEqual(I.izberi(CINEMETA, "wicker!", 2025), "tt29611136")          # leto +-1, locila
        self.assertIsNone(I.izberi(CINEMETA, "Wicker", 2010))                         # drugo leto: raje nic
        self.assertIsNone(I.izberi(CINEMETA, "The Wicker Man", None))                 # dva enaka naslova brez leta
        self.assertEqual(I.izberi(CINEMETA, "The Wicker Man", 2006), "tt0450345")
        self.assertIsNone(I.izberi(CINEMETA, "Wick", 2026))                           # delni naslov ni zadetek

    def test_leto_iz_poti_plakata(self):
        self.assertEqual(I.leto_vnosa({"leto": "0", "slika": "https://y.primer/movies/wicker_2026/large-cover.jpg"}), 2026)
        self.assertEqual(I.leto_vnosa({"leto": "1999"}), 1999)
        self.assertIsNone(I.leto_vnosa({"leto": "0", "slika": ""}))

    def test_iskalnik_predpomni_in_pove_ni(self):
        klici = []

        def zahteva(url, rok):
            klici.append(url)
            return json.dumps({"metas": CINEMETA}).encode()
        isk = I.Iskalnik(zahteva)
        self.assertEqual(isk.za_vnos(_best(0, "Wicker", ".../wicker_2026/large-cover.jpg")), "tt29611136")
        self.assertEqual(isk.za_vnos(_best(1, "Wicker", ".../wicker_2026/large-cover.jpg")), "tt29611136")
        self.assertEqual(len(klici), 1, "isti naslov in leto: en klic")
        self.assertEqual(isk.za_vnos({"imdb_id": "tt0137523", "naslov": "x"}), "tt0137523")
        self.assertEqual(len(klici), 1, "znan imdb_id brez klica")


class MrezaBrezImdb(unittest.TestCase):
    def test_film_brez_imdb_najde_imdb_po_naslovu(self):
        m, vrsta, ix = _filter(lambda item: "tt29611136" if item.get("naslov") == "Wicker" else None)
        m.prikazi("mreza", 1, _rezultat([_best(0, "Wicker")]), True)
        vrsta.pozeni()
        self.assertEqual(ix.klici, ["tt29611136"])
        r = m.preciscen(m.mreza, _rezultat([_best(0, "Wicker")]))
        self.assertEqual(len(r["vnosi"]), 1, "film je na voljo prek Useneta")

    def test_brez_imdb_ni_napacnega_sporocila(self):
        m, vrsta, ix = _filter(lambda item: None)
        m.prikazi("mreza", 1, _rezultat([_best(0, "Neznan film")]), True)
        vrsta.pozeni()
        self.assertEqual(ix.klici, [], "brez IMDb indeksatorja ne sprasujemo")
        r = m.preciscen(m.mreza, _rezultat([_best(0, "Neznan film")]))
        self.assertNotEqual(r["usenet_filter"]["prazno"], "ne_odgovarja",
                            "indeksator deluje - film le nima IMDb, ne smemo reci, da indeksator ne odgovarja")


if __name__ == "__main__":
    unittest.main()
