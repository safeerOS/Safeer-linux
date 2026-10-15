"""Brez podvajanja vsebine: isti naslov iz Jellyfina (knjiznica, kanali vticnikov) in iz dodatkov Stremio je v katalogu
ENKRAT, kot ena kartica z vec viri (razlicice); prednost ima tok z uporabnikovega strežnika (lastnik, 15. 10. 2026).

Odgovori so realni po obliki (BaseItemDto Jellyfina z ProviderIds, SeriesId, ParentIndexNumber, IndexNumber; manifest in
katalog dodatka Stremio), omrezja ni (media_servers._request je zamenjan)."""
import json
import tempfile
import unittest
from unittest import mock

from core import media_servers as m
from core import os_media

JF = {"id": "streznik-aaaaaaaaaaaaaaaa", "ime": "Domaci Jellyfin", "user_id": "u1", "ponudnik": "jellyfin"}
ST = {"id": "streznik-bbbbbbbbbbbbbbbb", "ime": "Dodatek", "ponudnik": "stremio"}
BASE = "https://jf.test:8920"
DODATEK = "https://dodatek.example"

JF_ITEMS = {"Items": [
    {"Id": "m1", "Type": "Movie", "Name": "The Matrix", "ProductionYear": 1999, "MediaType": "Video",
     "ProviderIds": {"Imdb": "tt0133093", "Tmdb": "603"}},
    {"Id": "e1", "Type": "Episode", "Name": "Pilot", "SeriesName": "Breaking Bad", "SeriesId": "s1",
     "ParentIndexNumber": 1, "IndexNumber": 1, "MediaType": "Video", "ProviderIds": {"Imdb": "tt0959621", "Tvdb": "349232"}},
    {"Id": "e2", "Type": "Episode", "Name": "Cat's in the Bag...", "SeriesName": "Breaking Bad", "SeriesId": "s1",
     "ParentIndexNumber": 1, "IndexNumber": 2, "MediaType": "Video"},
    # Epizoda brez stevilke (posebna oddaja brez metapodatkov): ne povezemo je s kartico cele serije.
    {"Id": "e3", "Type": "Episode", "Name": "Neznano", "SeriesName": "Breaking Bad", "SeriesId": "s1", "MediaType": "Video"},
    {"Id": "m2", "Type": "Movie", "Name": "Domaci posnetek", "ProductionYear": 2024, "MediaType": "Video"},
    {"Id": "a1", "Type": "Audio", "Name": "Pesem", "MediaType": "Audio", "Album": "Album", "AlbumArtist": "Izvajalec"},
]}
JF_SERIJE = {"Items": [{"Id": "s1", "Type": "Series", "Name": "Breaking Bad",
                        "ProviderIds": {"Imdb": "tt0903747", "Tmdb": "1396", "Tvdb": "81189"}}]}
JF_KANALI = {"Items": [{"Id": "0123456789abcdef0123456789abcdef", "Name": "Kanal vticnika", "Type": "Channel"}]}
JF_KANAL_VSEBINA = {"Items": [
    {"Id": "c1", "Type": "Movie", "Name": "The Shawshank Redemption", "MediaType": "Video",
     "ProviderIds": {"Imdb": "tt0111161"}},
    {"Id": "c2", "Type": "Folder", "Name": "Mapa", "IsFolder": True},
]}

MANIFEST = {"id": "org.dodatek", "name": "Dodatek", "resources": ["catalog", "stream"], "types": ["movie", "series", "tv"],
            "catalogs": [{"type": "movie", "id": "top"}, {"type": "series", "id": "top"}, {"type": "tv", "id": "kanali"}]}
STREMIO = {
    "/manifest.json": MANIFEST,
    "/catalog/movie/top.json": {"metas": [
        {"id": "tt0133093", "type": "movie", "name": "The Matrix", "releaseInfo": "1999", "poster": "https://p.example/m.jpg"},
        {"id": "tt0111161", "type": "movie", "name": "The Shawshank Redemption", "releaseInfo": "1994"},
        {"id": "tmdb:550", "type": "movie", "name": "Fight Club", "releaseInfo": "1999"},
        {"id": "tt0068646", "type": "movie", "name": "The Godfather", "releaseInfo": "1972"}]},
    "/catalog/series/top.json": {"metas": [
        {"id": "tt0903747", "type": "series", "name": "Breaking Bad", "releaseInfo": "2008-2013"}]},
    "/catalog/tv/kanali.json": {"metas": [
        {"id": "iptv:1", "type": "tv", "name": "SI: POP TV HD"},
        {"id": "iptv:2", "type": "tv", "name": "Kanal A (SI)"},
        {"id": "iptv:3", "type": "tv", "name": "HR: Nova TV"}]},
}


def _jellyfin(url, headers=None, body=None, raw=None):
    pot = url.split("://", 1)[1].split("/", 1)[1].split("?")[0]
    if pot == "Items" and "Ids=" in url:
        return json.dumps(JF_SERIJE).encode()
    if pot == "Items":
        return json.dumps(JF_ITEMS).encode()
    if pot == "Channels":
        return json.dumps(JF_KANALI).encode()
    if pot == "Channels/0123456789abcdef0123456789abcdef/Items":
        return json.dumps(JF_KANAL_VSEBINA).encode()
    raise OSError("ni odgovora za " + url)


def _stremio(url, headers=None, body=None, raw=None):
    for kljuc, vrednost in STREMIO.items():
        if url == DODATEK + kljuc:
            return json.dumps(vrednost).encode()
    raise OSError("ni odgovora za " + url)


def _vrstice():
    with mock.patch.object(m, "_request", _jellyfin):
        jf = m.catalog("jellyfin", BASE, JF, "ZETON")
    with mock.patch.object(m, "_request", _stremio):
        st = m.catalog("stremio", DODATEK, ST, "")
    return jf, st


class JellyfinVrstice(unittest.TestCase):
    def test_ponudnikovi_idji_epizode_in_kanali(self):
        jf, _ = _vrstice()
        po_id = {v["id"].rsplit(":", 1)[1]: v for v in jf}
        self.assertEqual((po_id["m1"]["imdb_id"], po_id["m1"]["tmdb_id"]), ("tt0133093", 603))
        # Epizoda nosi id-je SERIJE (kot epizode dodatkov Stremio tt0903747:1:1), ne lastnega id-ja epizode.
        e1 = po_id["e1"]
        self.assertEqual((e1["imdb_id"], e1["tmdb_id"], e1["tvdb_id"], e1["sezona"], e1["epizoda"]),
                         ("tt0903747", 1396, 81189, 1, 1))
        self.assertEqual(e1["naslov"], "Breaking Bad – Pilot")
        self.assertNotIn("imdb_id", po_id["e3"])
        self.assertNotIn("epizoda", po_id["e3"])
        # Vsebina kanala vticnika (prek strežnika: Videos/{id}/stream?static=true), mape ne.
        self.assertEqual(po_id["c1"]["imdb_id"], "tt0111161")
        self.assertIn("/Videos/c1/stream?static=true", po_id["c1"]["url"])
        self.assertEqual(po_id["c1"]["skupina"], "Kanal vticnika")
        self.assertNotIn("c2", po_id)
        self.assertEqual(po_id["a1"]["vrsta"], "glasba")
        self.assertTrue(all(m.streznik_iz_id(v["id"]) == JF["id"] for v in jf))

    def test_stremio_tmdb_id(self):
        _, st = _vrstice()
        fight = next(v for v in st if v["naslov"] == "Fight Club")
        self.assertEqual(fight.get("tmdb_id"), 550)


class BrezDvojnikov(unittest.TestCase):
    def _katalog(self, osebni, vrsta):
        with tempfile.TemporaryDirectory() as td:
            center = os_media.MediaCenter(td, roots=[])
            center._ima_embed_vir = lambda data=None: False
            center._zakoniti_viri.get = lambda *a, **k: []
            center._personal_items = lambda q: [dict(v) for v in osebni]
            return center.catalog("", vrsta)["vnosi"]

    def test_filmi_enkrat_lastni_streznik_prvi(self):
        jf, st = _vrstice()
        filmi = self._katalog(jf + st, "film")
        naslovi = [f["naslov"] for f in filmi]
        self.assertEqual(sorted(naslovi), sorted(set(naslovi)), naslovi)          # vsak naslov enkrat
        self.assertEqual(sorted(naslovi), ["Domaci posnetek", "Fight Club", "The Godfather", "The Matrix",
                                           "The Shawshank Redemption"])
        matrix = next(f for f in filmi if f["naslov"] == "The Matrix")
        self.assertTrue(matrix["url"].startswith(BASE + "/Videos/m1/stream"))      # tok z lastnega strežnika
        self.assertEqual(matrix["stevilo_razlicic"], 2)
        self.assertTrue(matrix["razlicice"][0].get("lastni"))
        self.assertTrue(matrix["razlicice"][1]["url"].startswith("stremio:"))
        self.assertEqual(matrix["viri"], ["Domaci Jellyfin", "Dodatek"])
        # Kanal vticnika in dodatek: isti film po IMDb, tok s strežnika.
        shaw = next(f for f in filmi if f["naslov"] == "The Shawshank Redemption")
        self.assertIn("/Videos/c1/stream", shaw["url"])
        self.assertEqual(shaw["stevilo_razlicic"], 2)

    def test_serija_in_epizode_streznika_ena_kartica(self):
        jf, st = _vrstice()
        serije = self._katalog(jf + st, "serija")
        bb = [s for s in serije if "Breaking Bad" in s["naslov"]]
        # Kartica serije iz dodatka + epizode s strežnika (z id-ji serije) = ena kartica; epizoda brez stevilke ostane.
        self.assertEqual(len([s for s in bb if s.get("epizoda")]), 0)
        kartica = next(s for s in bb if s["naslov"] == "Breaking Bad")
        self.assertTrue(kartica["url"].startswith(BASE + "/Videos/e1/stream"))      # prva epizoda s strežnika
        self.assertEqual(kartica["epizod_na_strezniku"], 2)
        self.assertEqual(kartica["tmdb_id"], 1396)
        self.assertTrue(any(r["url"].startswith("stremio:") for r in kartica["razlicice"]))
        self.assertIn("Domaci Jellyfin", kartica["viri"])
        self.assertEqual([s["naslov"] for s in bb if s is not kartica], ["Breaking Bad – Neznano"])

    def test_brez_kartice_serije_epizode_ostanejo(self):
        jf, _ = _vrstice()
        serije = self._katalog(jf, "serija")
        self.assertEqual(sorted((s.get("sezona"), s.get("epizoda")) for s in serije if s.get("epizoda")), [(1, 1), (1, 2)])

    def test_lastna_kartica_se_predvaja_takoj_in_se_ne_skrije(self):
        jf, st = _vrstice()
        kartica = next(f for f in os_media.merge_duplicates(jf + st) if f["naslov"] == "The Matrix")
        with tempfile.TemporaryDirectory() as td:
            center = os_media.MediaCenter(td, roots=[])
            center._dynamic_items[kartica["id"]] = kartica

            def ne_sprasuj(*a, **k):
                raise AssertionError("tok z lastnega strežnika ne caka na dodatke Stremio")
            center._stremio_tokovi_vseh = ne_sprasuj
            r = center.resolve(kartica["id"])
            self.assertTrue(r["url"].startswith(BASE + "/Videos/m1/stream"))
            self.assertTrue(all(v["url"].startswith("https://") for v in r["razlicice"]))
            # Dodatek je naslov nekoc oznacil kot »ni na voljo«: s strežnikom kartica ostane.
            stremio = dict(next(f for f in st if f["naslov"] == "The Matrix"), tmdb_id=603)
            center.oznaci_ni_na_voljo(stremio)
            self.assertTrue(center.znano_ni_na_voljo(kartica))
            self.assertEqual(len(center.brez_nerazpolozljivih({"vnosi": [kartica]})["vnosi"]), 1)
            self.assertEqual(len(center.brez_nerazpolozljivih({"vnosi": [stremio]})["vnosi"]), 0)

    def test_lastni_streznik_pred_boljso_kakovostjo(self):
        lastni = {"id": "server:%s:m1" % JF["id"], "naslov": "Film", "vrsta": "film", "url": BASE + "/Videos/m1/stream",
                  "imdb_id": "tt1234567", "vir": "JF"}
        tuj = {"id": "x", "naslov": "Film", "vrsta": "film", "url": "https://cdn.example/film.mkv", "locljivost": 2160,
               "imdb_id": "tt1234567", "vir": "Splet"}
        zdruzeno = os_media.merge_duplicates([tuj, lastni])
        self.assertEqual(len(zdruzeno), 1)
        self.assertEqual(zdruzeno[0]["url"], lastni["url"])
        # Brez lastnega strežnika ostane prejsnje pravilo (najboljsa kakovost).
        drugi = dict(tuj, url="https://drugi.example/film.mp4", locljivost=720)
        self.assertEqual(os_media.merge_duplicates([drugi, tuj])[0]["url"], tuj["url"])

    def test_isti_naslov_razlicni_id_ostane_dvakrat(self):
        a = {"id": "server:%s:a" % JF["id"], "naslov": "Dune", "vrsta": "film", "url": BASE + "/Videos/a/stream",
             "imdb_id": "tt0087182", "leto": 1984}
        b = {"id": "stremio:x", "naslov": "Dune", "vrsta": "film", "url": "stremio:%s|movie|tt1160419" % DODATEK,
             "imdb_id": "tt1160419", "leto": 2021}
        self.assertEqual(len(os_media.merge_duplicates([a, b])), 2)

    def test_tvdb_povezuje(self):
        a = {"id": "server:%s:s" % JF["id"], "naslov": "Serija X", "vrsta": "serija", "url": BASE + "/Videos/x/stream",
             "tvdb_id": 81189, "sezona": 1, "epizoda": 1}
        b = {"id": "y", "naslov": "Druga oznaka", "vrsta": "serija", "url": "stremio:%s|series|tvdb:81189:1:1" % DODATEK,
             "tvdb_id": 81189, "sezona": 1, "epizoda": 1}
        self.assertEqual(len(os_media.merge_duplicates([a, b])), 1)


class KanaliTvVZivo(unittest.TestCase):
    def _tvh(self, ime, uuid):
        return {"id": "tvh:%s:%s" % (JF["id"], uuid), "naslov": ime, "vrsta": "tv-v-zivo",
                "url": "http://192.168.1.5:9981/stream/channel/" + uuid, "vir": "Sprejemnik"}

    def test_isti_kanal_iz_sprejemnika_dodatka_in_seznama(self):
        _, st = _vrstice()
        kanali = [v for v in st if v["vrsta"] == "tv-v-zivo"]
        javni = [{"id": "z1", "naslov": "POP TV", "vrsta": "tv-v-zivo", "url": "https://javno.example/pop.m3u8", "drzava": "SI"},
                 {"id": "z2", "naslov": "POP TV +1", "vrsta": "tv-v-zivo", "url": "https://javno.example/pop1.m3u8", "drzava": "SI"}]
        zdruzeno = os_media.merge_duplicates(kanali + javni + [self._tvh("POP TV HD", "u1"), self._tvh("Nova TV", "u2")])
        po_imenu = {}
        for k in zdruzeno:
            po_imenu.setdefault(os_media.ime_kanala(k)[0], []).append(k)
        self.assertEqual(len(po_imenu["pop tv"]), 1)
        pop = po_imenu["pop tv"][0]
        self.assertEqual(pop["stevilo_razlicic"], 3)
        self.assertTrue(pop["url"].startswith("http://192.168.1.5:9981/"))       # lastni sprejemnik prvi
        self.assertEqual(len(po_imenu["pop tv plus 1"]), 1)                       # +1 je drug kanal
        self.assertEqual(len(po_imenu["kanal a"]), 1)
        # »Nova TV« iz sprejemnika (drzava neznana) in »HR: Nova TV« sta isti kanal - edina znana drzava je HR.
        self.assertEqual(len(po_imenu["nova tv"]), 1)

    def test_isto_ime_iz_dveh_drzav_ni_isti_kanal(self):
        a = {"id": "a", "naslov": "Sport 1", "vrsta": "tv-v-zivo", "url": "https://a.example/s.m3u8", "drzava": "DE"}
        b = {"id": "b", "naslov": "CZ: Sport 1", "vrsta": "tv-v-zivo", "url": "https://b.example/s.m3u8"}
        c = {"id": "c", "naslov": "Sport 1 FHD", "vrsta": "tv-v-zivo", "url": "https://c.example/s.m3u8"}
        zdruzeno = os_media.merge_duplicates([a, b, c])
        self.assertEqual(len(zdruzeno), 3)            # neznana drzava ob dveh znanih: ne ugibamo
        self.assertEqual(len(os_media.merge_duplicates([a, c])), 1)
        self.assertEqual(os_media.ime_kanala({"naslov": "[SI] Planet TV (1080p) HEVC"}), ("planet tv", "si"))
        self.assertEqual(os_media.ime_kanala({"naslov": "RTL - Living"}), ("rtl living", ""))


class IzbiraIzTmdb(unittest.TestCase):
    """Film ali epizoda, izbrana v podrobnostih (TMDB), predvaja tok z lastnega strežnika, ce ga ta ima."""

    def _center(self, td, jf):
        center = os_media.MediaCenter(td, roots=[])
        with open(td + "/media.json", "w", encoding="utf-8") as f:
            json.dump({"viri": [], "osebni_strezniki": [dict(ST, url=DODATEK + "/manifest.json")]}, f)
        center._server_cache[JF["id"] + ":"] = (0, jf)
        return center

    def test_film_in_epizoda(self):
        jf, _ = _vrstice()
        with tempfile.TemporaryDirectory() as td:
            center = self._center(td, jf)
            with mock.patch.dict(os_media.TMDB_TO_IMDB, {"603": "tt0133093", "1396": "tt0903747"}):
                film = center.movie_item(603, "The Matrix")
                ep = center.episode_item(1396, 1, 2, "Breaking Bad · Cat's in the Bag...")
                ni = center.episode_item(1396, 3, 1, "Breaking Bad · S3E1")
        self.assertTrue(film["url"].startswith(BASE + "/Videos/m1/stream"))
        self.assertEqual(film["stevilo_razlicic"], 2)                 # + dodatek Stremio
        self.assertTrue(ep["url"].startswith(BASE + "/Videos/e2/stream"))
        self.assertEqual(ep["stevilo_razlicic"], 2)
        self.assertTrue(ni["url"].startswith("stremio:"))             # epizode ni na strežniku: dodatek


if __name__ == "__main__":
    unittest.main()
