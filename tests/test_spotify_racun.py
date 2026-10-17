"""Spotify v Medijskem centru (core/spotify_racun.py): kanal CDP, branje seznamov, Scit, zaznava oglasa, potekla prijava."""
import base64
import json
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import link_seznami, os_media, spotify_racun as sr  # noqa: E402

KOREN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _sled(i, ime, izvajalec="Izvajalec", ms=180000):
    return {"type": "track", "uri": "spotify:track:%022d" % i, "name": ime, "duration_ms": ms,
            "artists": [{"name": izvajalec, "uri": "spotify:artist:%022d" % (900 + i)}],
            "album": {"uri": "spotify:album:%022d" % (500 + i), "name": "Album",
                      "images": [{"url": "https://i.scdn.co/image/m%d" % i, "width": 300},
                                 {"url": "https://i.scdn.co/image/v%d" % i, "width": 640}]}}


# Spletni API (api.spotify.com/v1): playlists/{id}/tracks, me/tracks
V1_SEZNAM = {"items": [{"added_at": "2026-01-01", "track": _sled(1, "Prva")}, {"track": _sled(2, "Druga", "Drugi")},
                       {"track": None}], "next": None}
# GraphQL (pathfinder) fetchPlaylist - oblika spletne aplikacije (skrajsana)
PF_SEZNAM = {"data": {"playlistV2": {"__typename": "Playlist", "uri": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
    "name": "Top", "content": {"totalCount": 2, "items": [
        {"itemV2": {"__typename": "TrackResponseWrapper", "data": {
            "__typename": "Track", "uri": "spotify:track:4uLU6hMCjMI75M1A2tKUQC", "name": "Pesem A",
            "trackDuration": {"totalMilliseconds": 213000},
            "artists": {"items": [{"uri": "spotify:artist:1", "profile": {"name": "A1"}}, {"profile": {"name": "A2"}}]},
            "albumOfTrack": {"uri": "spotify:album:x", "coverArt": {"sources": [{"url": "https://i.scdn.co/image/a", "width": 64},
                                                                               {"url": "https://i.scdn.co/image/b", "width": 640}]}}}}},
        {"itemV2": {"data": {"__typename": "NotFound", "uri": "spotify:track:0000000000000000000000", "name": "x"}}},
        {"itemV2": {"data": {"__typename": "Episode", "uri": "spotify:episode:5Xt5DXGzch68nYYamXrNxZ", "name": "Epizoda",
                             "duration": {"totalMilliseconds": 3600000},
                             "podcastV2": {"data": {"name": "Oddaja X"}}}}}]}}}}
# GraphQL libraryV3: seznami in oddaje v knjiznici
PF_KNJIZNICA = {"data": {"me": {"libraryV3": {"totalCount": 3, "items": [
    {"item": {"_uri": "spotify:collection:tracks", "data": {"__typename": "PseudoPlaylist", "name": "Liked Songs"}}},
    {"item": {"_uri": "spotify:playlist:1111111111111111111111", "data": {"__typename": "Playlist", "name": "Moj seznam",
              "images": {"items": [{"sources": [{"url": "https://mosaic.scdn.co/640/a", "width": 640}]}]},
              "ownerV2": {"data": {"uri": "spotify:user:jaz", "name": "jaz"}}}}},
    {"item": {"_uri": "spotify:show:2222222222222222222222", "data": {"__typename": "Podcast", "name": "Podkast",
              "publisher": {"name": "Zalozba"}, "coverArt": {"sources": [{"url": "https://i.scdn.co/image/p"}]}}}}]}}}}
V1_SEZNAMI = {"items": [{"uri": "spotify:playlist:3333333333333333333333", "name": "Iz API", "tracks": {"total": 12},
                         "images": [{"url": "https://i.scdn.co/image/s"}], "owner": {"uri": "spotify:user:jaz"}}], "next": None}
V1_ODDAJE = {"items": [{"show": {"uri": "spotify:show:4444444444444444444444", "name": "Oddaja", "publisher": "Pub",
                                 "images": [{"url": "https://i.scdn.co/image/o"}]}}]}


GLOBOKO = {"uri": "spotify:track:1234567890", "name": "globoko"}
for _ in range(20):
    GLOBOKO = [GLOBOKO]


class RazclenjevanjeTest(unittest.TestCase):
    def test_skladbe_iz_spletnega_api(self):
        s = sr.skladbe_iz(V1_SEZNAM)
        self.assertEqual([x["naslov"] for x in s], ["Prva", "Druga"])
        self.assertEqual(s[0], {"naslov": "Prva", "izvajalec": "Izvajalec", "youtube": "", "slika": "https://i.scdn.co/image/v1",
                                "sekund": 180, "spotify": "spotify:track:%022d" % 1})

    def test_skladbe_iz_graphql(self):
        s = sr.skladbe_iz(PF_SEZNAM)
        self.assertEqual([x["naslov"] for x in s], ["Pesem A", "Epizoda"])      # NotFound izpuscen
        self.assertEqual((s[0]["izvajalec"], s[0]["sekund"], s[0]["slika"]), ("A1, A2", 213, "https://i.scdn.co/image/b"))
        self.assertEqual((s[1]["izvajalec"], s[1]["sekund"], s[1]["spotify"]),
                         ("Oddaja X", 3600, "spotify:episode:5Xt5DXGzch68nYYamXrNxZ"))

    def test_seznami_in_oddaje(self):
        self.assertEqual(sr.seznami_iz(PF_KNJIZNICA), [{"id": "1111111111111111111111", "ime": "Moj seznam",
                                                        "slika": "https://mosaic.scdn.co/640/a", "stevilo": 0}])
        self.assertEqual(sr.oddaje_iz(PF_KNJIZNICA), [{"id": "2222222222222222222222", "ime": "Podkast", "avtor": "Zalozba",
                                                       "slika": "https://i.scdn.co/image/p"}])
        self.assertEqual(sr.seznami_iz(V1_SEZNAMI)[0]["stevilo"], 12)
        self.assertEqual(sr.oddaje_iz(V1_ODDAJE)[0]["avtor"], "Pub")

    def test_spremenjen_odgovor_ne_sesuje(self):
        for o in (None, [], {}, {"data": None}, "niz", {"items": [{"track": {"uri": "spotify:track:x y", "name": "a"}}]},
                  GLOBOKO):
            self.assertEqual(sr.skladbe_iz(o), [])
            self.assertEqual(sr.seznami_iz(o), [])

    def test_cas(self):
        self.assertEqual([sr.cas_v_sekunde(x) for x in ("3:07", "1:02:03", "-0:42", "", "abc", None)], [187, 3723, 42, 0, 0, 0])

    def test_stanje(self):
        s = sr.stanje_iz({"naslov": "Pesem", "izvajalec": "A", "slika": "https://i.scdn.co/x", "igra": True,
                          "polozaj": "1:00", "trajanje": "-2:00", "glasnost": {"v": 0.5, "min": 0, "max": 1},
                          "povezava": "/track/abc", "zeton": "NIKOLI"})
        self.assertEqual(s, {"naslov": "Pesem", "izvajalec": "A", "slika": "https://i.scdn.co/x", "igra": True, "polozaj": 60,
                             "trajanje": 180, "glasnost": 0.5, "oglas": False, "utisano": False})
        self.assertEqual(sr.stanje_iz(None)["naslov"], "")
        self.assertEqual(sr.stanje_iz({"slika": "javascript:x", "napredek": {"v": 50, "min": 0, "max": 100},
                                       "trajanje": "2:00"})["polozaj"], 60)
        self.assertEqual(sr.stanje_iz({"slika": "javascript:x"})["slika"], "")


class OglasiTest(unittest.TestCase):
    def test_zaznava_oglasa(self):
        oglasi = [{"oglas_oznaka": True}, {"naslov": "Advertisement", "izvajalec": ""}, {"naslov": "x", "izvajalec": "Werbung"},
                  {"naslov": "Kupi", "povezava": "https://www.example.com/promo"}, {"naslov": "a", "povezava": "/ad/123"},
                  {"naslov": "Spotify Premium", "izvajalec": "Spotify", "povezava": ""}]
        for s in oglasi:
            self.assertTrue(sr.je_oglas(s), s)
        pesmi = [{"naslov": "Ad Astra", "izvajalec": "Band", "povezava": "/track/1"},
                 {"naslov": "Pesem", "izvajalec": "Spotify", "povezava": "/episode/2"},
                 {"naslov": "Adele", "izvajalec": "Adele", "povezava": "/track/3"},
                 {"naslov": "", "izvajalec": ""}, None, {"naslov": "x", "povezava": "https://open.spotify.com/track/4"}]
        for s in pesmi:
            self.assertFalse(sr.je_oglas(s), s)

    def test_pravila_scita(self):
        p = sr.pravila_scita()
        zavrni = ["https://adeventtracker.spotify.com/x", "https://spclient.wg.spotify.com/ads/v2/config",
                  "https://gew1-spclient.spotify.com/ad-logic/state/config", "https://pubads.g.doubleclick.net/gampad/ads"]
        pusti = ["https://api.spotify.com/v1/me/playlists", "https://api-partner.spotify.com/pathfinder/v2/query",
                 "https://spclient.wg.spotify.com/connect-state/v1/devices", "https://open.spotify.com/ads-info",
                 "https://audio-ak-spotify-com.akamaized.net/audio/x", "https://open.spotify.com/", "ni naslov", ""]
        for u in zavrni:
            self.assertTrue(sr.je_oglasna_zahteva(u, p), u)
        for u in pusti:
            self.assertFalse(sr.je_oglasna_zahteva(u, p), u)
        self.assertIn("upgrade-button", p["css"])

    def test_main_js_isto_pravilo(self):
        # main.js bere ista polja (gostitelji, poti, css) - oblika pravil je dogovor med Scitom in Safeer DRM.
        with open(os.path.join(KOREN, "assets", "safeer_drm", "main.js"), encoding="utf-8") as f:
            js = f.read()
        for kljuc in ("pravila.gostitelji", "pravila.poti", "pravila.css"):
            self.assertIn(kljuc, js)


class LaznaProces:
    def __init__(self):
        self.koda = None

    def poll(self):
        return self.koda

    def terminate(self):
        self.koda = 0

    def wait(self, timeout=None):
        return self.koda

    def kill(self):
        self.koda = -9


class KanalTest(unittest.TestCase):
    """Kanal do Safeer DRM: ukaz cdp:<id>:<base64> v command.txt, odgovor (vrsta CDP) v events.jsonl - kot main.js."""

    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.mapa, ignore_errors=True))
        self.proces = LaznaProces()
        self.argumenti = []
        exe = os.path.join(self.mapa, "safeer-drm")
        open(exe, "w").close()
        self.zakrpe = [mock.patch.object(sr.safeer_drm, "izvrsljiva", return_value=sr.Path(exe)),
                       mock.patch.object(sr.safeer_drm, "uskladi_logiko"),
                       mock.patch.object(sr.safeer_drm, "koren", return_value=sr.Path(self.mapa)),
                       mock.patch.object(sr.safeer_drm, "v_peskovniku", return_value=False),
                       mock.patch.object(sr.safeer_drm, "v_flatpaku", return_value=False)]
        for z in self.zakrpe:
            z.start()
            self.addCleanup(z.stop)

        def zazeni(args, _okolje):
            self.argumenti = args
            return self.proces
        self.k = sr.Kanal(zazeni=zazeni, mapa=self.mapa)
        self.addCleanup(self.k.ustavi)

    def _streznik(self, odgovori):
        """Nadomestni main.js: prebere ukaze in zapise odgovore."""
        def tek():
            while self.proces.koda is None:
                if self.k.ukazi and os.path.exists(self.k.ukazi):
                    os.rename(self.k.ukazi, self.k.ukazi + ".r")
                    for vr in open(self.k.ukazi + ".r").read().splitlines():
                        if vr.startswith("cdp:"):
                            _, ident, b64 = vr.split(":")
                            izraz = json.loads(base64.b64decode(b64))["expression"]
                            odg = odgovori(izraz)
                            if odg is None:
                                continue          # brez odgovora (zastala stran)
                            odg = dict(odg, id=int(ident))
                            with open(self.k.stanje, "a") as f:
                                f.write(json.dumps({"type": "CDP", "detail": json.dumps(odg)}) + "\n")
                    os.unlink(self.k.ukazi + ".r")
                time.sleep(0.02)
        threading.Thread(target=tek, daemon=True).start()

    def test_zagon_skrit_s_scitom(self):
        self.assertEqual(self.k.zacni(False, True), "ok")
        a = self.argumenti
        self.assertIn("--url=https://open.spotify.com/", a)
        self.assertIn("--spotify=1", a)
        self.assertIn("--skrit=1", a)
        self.assertIn("--profile=" + os.path.join(self.mapa, "profil-spotify"), a)
        scit = [x for x in a if x.startswith("--scit=")]
        self.assertEqual(json.load(open(scit[0][7:]))["gostitelji"], sr.pravila_scita()["gostitelji"])
        self.assertFalse(any("remote-debugging" in x for x in a))     # brez vrat CDP
        # mapa seje je zasebna
        self.assertEqual(os.stat(self.k.seja).st_mode & 0o077, 0)

    def test_brez_scita_in_vidno(self):
        self.k.zacni(True, False)
        self.assertNotIn("--skrit=1", self.argumenti)
        self.assertFalse(any(x.startswith("--scit=") for x in self.argumenti))
        # ponoven zacni s skritim oknom poslje ukaz »skrij«, proces ostane
        self.assertEqual(self.k.zacni(False, False), "ok")
        self.assertIn("skrij", open(self.k.ukazi).read())

    def test_ni_drm(self):
        with mock.patch.object(sr.safeer_drm, "izvrsljiva", return_value=None):
            self.assertEqual(self.k.zacni(False, True), "ni_drm")

    def test_izvedi_odgovor_izjema_in_cas(self):
        self.k.zacni(False, True)

        def odgovori(izraz):
            if izraz == "document.title":
                return {"vrednost": "Spotify"}
            if izraz.startswith("throw"):
                return {"napaka": "izjema", "opis": "Error"}
            if izraz == "tiho":
                return {}
            return {"napaka": "cdp"}
        # »tiho« ne dobi odgovora (streznik ga preskoci)
        self._streznik(lambda i: odgovori(i) if i != "tiho" else None)
        self.assertEqual(self.k.izvedi("document.title", 3), "Spotify")
        with self.assertRaises(sr.SpremenjenaStran):
            self.k.izvedi("throw 1", 3)
        with self.assertRaises(sr.NiOdziva):
            self.k.izvedi("drugo", 3)
        with self.assertRaises(sr.NiOdziva):
            self.k.izvedi("tiho", 0.2)

    def test_pokvarjene_vrstice_in_ustavljen(self):
        for vr in ("", "{", "[]", json.dumps({"type": "CDP", "detail": "{"}), json.dumps({"type": "CDP", "detail": "{\"id\": \"x\"}"})):
            self.k.obdelaj(vr)
        with self.assertRaises(sr.NiOdziva):
            self.k.izvedi("document.title", 1)          # ne tece
        self.k.obdelaj(json.dumps({"type": "NAVIGATION_OK"}))
        self.assertTrue(self.k.nalozeno)

    def test_konec_procesa_pospravi_sejo(self):
        poklican = threading.Event()
        self.k.konec_cb = poklican.set
        self.k.zacni(False, True)
        seja = self.k.seja
        self.proces.koda = 0
        self.assertTrue(poklican.wait(3))
        self.assertFalse(os.path.exists(seja))


class LazniKanal:
    """Stran Spotify brez Safeer DRM: odgovori na izraze iz core/spotify_racun.py."""

    def __init__(self, stanje=None, pf=None, api=None):
        self.vidno = False
        self.nalozeno = True
        self._tece = False
        self.stanje = stanje if stanje is not None else {"zeton": True, "predvajalnik": True, "prijava": False, "ime": "Ana"}
        self.pf = pf or {}
        self.api = api or {}
        self.izrazi = []
        self.ukazi = []
        self.konec_cb = None

    def tece(self):
        return self._tece

    def zacni(self, vidno, scit, piskotki=None):
        self._tece, self.vidno, self.scit, self.piskotki = True, vidno, scit, piskotki
        return "ok"

    def ustavi(self):
        self._tece = False

    def ukaz(self, vr):
        self.ukazi.append(vr)

    @staticmethod
    def profil():
        return sr.Path(tempfile.gettempdir()) / "ni-profila-spotify-preizkus"

    def izvedi(self, izraz, cas=15):
        self.izrazi.append(izraz)
        if izraz == sr.STANJE_JS:
            return self.stanje
        m = re.search(r"S\.pf\((\"[^\"]+\"), (\{.*?\})\); \}\)\(\)$", izraz)
        if m:
            ime, sprem = json.loads(m.group(1)), json.loads(m.group(2))
            o = self.pf.get(ime)
            if callable(o):
                o = o(sprem)
            return o if o is not None else {"status": 0, "napaka": "ni_vzorca"}
        m = re.search(r"S\.klic\((\"[^\"]+\")\)", izraz)
        if m:
            o = self.api.get(json.loads(m.group(1)))
            return o if o is not None else {"status": 404, "podatki": None}
        if "history.pushState" in izraz:
            return "ok"
        if "tracklist-row" in izraz:
            return "vrstica"
        return True


class RacunTest(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.mapa, ignore_errors=True))

    def _racun(self, kanal, na_voljo=True):
        return sr.Racun(self.mapa, kanal=kanal, na_voljo=lambda: na_voljo, straza=False)

    def test_brez_drm(self):
        r = self._racun(LazniKanal(), na_voljo=False)
        st = r.stanje()
        self.assertEqual((st["drm"], st["prijavljen"], st["tece"]), (False, False, False))
        self.assertEqual(r.seznami(), {"napaka": "ni_drm"})
        self.assertEqual(r.prijava(), {"napaka": "ni_drm"})
        self.assertEqual(r.seznam("vseckane"), {"napaka": "ni_drm"})
        with mock.patch.object(sr.safeer_drm, "prenesi_v_ozadju") as prenos:
            self.assertEqual(r.prenesi()["prenos"], "tece")
            prenos.assert_called_once()
            prenos.call_args[0][0](False)
        self.assertEqual(r.stanje()["prenos"], "napaka")

    def test_seznami_iz_graphql(self):
        k = LazniKanal(pf={"libraryV3": {"status": 200, "podatki": PF_KNJIZNICA}})
        r = self._racun(k)
        izid = r.seznami()
        self.assertEqual([x["ime"] for x in izid["seznami"]], ["Moj seznam"])
        self.assertEqual([x["ime"] for x in izid["oddaje"]], ["Podkast"])
        self.assertEqual(izid["ime"], "Ana")
        self.assertTrue(k.scit)            # Scit privzeto vklopljen
        self.assertTrue(json.load(open(os.path.join(self.mapa, "spotify.json")))["prijavljen"])

    def test_seznami_rezerva_spletni_api(self):
        k = LazniKanal(api={"me/playlists?limit=50": {"status": 200, "podatki": V1_SEZNAMI},
                            "me/shows?limit=50": {"status": 200, "podatki": V1_ODDAJE}})
        izid = self._racun(k).seznami()
        self.assertEqual(([x["ime"] for x in izid["seznami"]], [x["ime"] for x in izid["oddaje"]]), (["Iz API"], ["Oddaja"]))

    def test_seznam_z_zamiki(self):
        def stran(sprem):
            zacetek = sprem["offset"]
            if zacetek >= 250:
                return {"status": 200, "podatki": {"data": {"items": []}}}
            return {"status": 200, "podatki": {"items": [{"track": _sled(i, "S%d" % i)} for i in range(zacetek, min(zacetek + 100, 250))]}}
        k = LazniKanal(pf={"fetchPlaylist": stran})
        sz = self._racun(k).seznam("1111111111111111111111")
        self.assertEqual(len(sz["skladbe"]), 250)
        self.assertEqual(sz["kontekst"], "spotify:playlist:1111111111111111111111")
        self.assertIn('"uri": "spotify:playlist:1111111111111111111111"', "".join(k.izrazi))

    def test_vseckane_odpre_stran_ko_vzorca_ni(self):
        k = LazniKanal()
        klici = []
        orig = k.izvedi

        def izvedi(izraz, cas=15):
            if "history.pushState" in izraz:
                klici.append(izraz)
                k.pf["fetchLibraryTracks"] = {"status": 200, "podatki": V1_SEZNAM}
            return orig(izraz, cas)
        k.izvedi = izvedi
        sz = self._racun(k).seznam("vseckane")
        self.assertEqual(len(sz["skladbe"]), 2)
        self.assertIn('"/collection/tracks"', klici[0])

    def test_spremenjena_stran(self):
        r = self._racun(LazniKanal())
        with mock.patch.object(sr.time, "sleep"):
            self.assertEqual(r.seznam("vseckane"), {"napaka": "stran"})
        self.assertEqual(r.seznam("../x"), {"napaka": "neveljavno"})
        # stran brez nase skripte ali predvajalnika: SpremenjenaStran, ne sesutje
        r2 = self._racun(LazniKanal(stanje={"skripta": False}))
        with mock.patch.object(sr.time, "sleep"):
            self.assertEqual(r2.seznami(), {"napaka": "stran"})

    def test_potekla_prijava(self):
        k = LazniKanal(pf={"libraryV3": {"status": 401, "podatki": None}})
        r = self._racun(k)
        self.assertEqual(r.seznami(), {"napaka": "potekla"})
        # stran pokaze gumb Prijava: prej prijavljen -> potekla
        k2 = LazniKanal(stanje={"zeton": True, "predvajalnik": True, "prijava": True})
        r2 = self._racun(k2)
        self.assertEqual(r2.seznami(), {"napaka": "potekla"})
        st = r2.stanje()
        self.assertEqual((st["prijavljen"], st["potekla"]), (False, True))

    def test_nikoli_prijavljen(self):
        k = LazniKanal(stanje={"zeton": True, "predvajalnik": True, "prijava": True})
        self.assertEqual(self._racun(k).seznami(), {"napaka": "ni_prijave"})

    def test_prijava_v_spletu_in_prenos_piskotkov(self):
        """Lastnik 17. 10. 2026: prijava v Spletu (Google tam deluje), ne v Safeer DRM (»brskalnik ni varen«)."""
        k = LazniKanal(stanje={"zeton": True, "predvajalnik": True, "prijava": False})
        r = self._racun(k)
        izid = r.prijava()
        self.assertTrue(izid["ok"] and izid["splet"].startswith("https://accounts.spotify.com/"))
        self.assertFalse(k.tece())                     # Safeer DRM se za prijavo ne zazene
        with mock.patch.object(sr, "piskotki_spleta", lambda pot=None: []):
            self.assertEqual(r.prijava_iz_spleta(), {"prijavljen": False})
        piskotki = [{"name": "sp_dc", "value": "x", "domain": ".spotify.com", "path": "/", "expirationDate": 0,
                     "secure": True, "httpOnly": True}]
        with mock.patch.object(sr, "piskotki_spleta", lambda pot=None: piskotki), \
                mock.patch.object(sr.threading, "Thread"):
            self.assertEqual(r.prijava_iz_spleta(), {"prijavljen": True})
        self.assertTrue(k.tece() and not k.vidno)
        self.assertEqual(k.piskotki, piskotki)
        self.assertTrue(r.stanje()["prijavljen"])

    def test_piskotki_spleta_samo_spotify(self):
        import sqlite3, tempfile, time as _t
        with tempfile.TemporaryDirectory() as mapa:
            pot = os.path.join(mapa, "cookies.sqlite")
            b = sqlite3.connect(pot)
            b.execute("CREATE TABLE moz_cookies (id INTEGER PRIMARY KEY, name TEXT, value TEXT, host TEXT, path TEXT,"
                      " expiry INTEGER, lastAccessed INTEGER, isSecure INTEGER, isHttpOnly INTEGER, sameSite INTEGER)")
            for ime, gost, potek in (("sp_dc", ".spotify.com", int(_t.time()) + 999), ("SID", ".youtube.com", 0),
                                     ("star", ".spotify.com", 5)):
                b.execute("INSERT INTO moz_cookies (name, value, host, path, expiry, isSecure, isHttpOnly) VALUES (?,?,?,?,?,1,1)",
                          (ime, "v", gost, "/", potek))
            b.commit(); b.close()
            c = sr.piskotki_spleta(pot)
        self.assertEqual([x["name"] for x in c], ["sp_dc"])
        self.assertTrue(sr.prijavljen_v_spletu(c))

    def test_straza_utisa_oglas(self):
        k = LazniKanal()
        r = self._racun(k)
        k.zacni(False, True)
        r.straza_korak({"naslov": "Advertisement", "igra": True})
        self.assertTrue(any("utisaj(true)" in x for x in k.izrazi))
        self.assertTrue(any("control-button-skip-forward" in x for x in k.izrazi))
        self.assertTrue(r.predvajanje()["oglas"])
        r.straza_korak({"naslov": "Pesem", "izvajalec": "A", "povezava": "/track/1", "igra": True})
        self.assertTrue(any("utisaj(false)" in x for x in k.izrazi))
        # Scit izklopljen: oglas ostane (nic utisanja)
        k.izrazi.clear()
        r.nastavi_scit(False)
        r.straza_korak({"naslov": "Advertisement", "igra": True})
        self.assertFalse(any("utisaj" in x for x in k.izrazi))
        self.assertFalse(r.scit())

    def test_upravljanje(self):
        k = LazniKanal()
        r = self._racun(k)
        self.assertEqual(r.upravljaj("premor"), {"napaka": "ne_tece"})
        k.zacni(False, True)
        self.assertEqual(r.upravljaj("naprej"), {"ok": True})
        self.assertIn('"control-button-skip-forward"', k.izrazi[-1])
        self.assertEqual(r.upravljaj("cas", 0.5), {"ok": True})
        self.assertIn('"playback-progressbar", 0.5', k.izrazi[-1])
        self.assertEqual(r.upravljaj("glasnost", 7), {"ok": True})
        self.assertIn('"volume-bar", 1.0', k.izrazi[-1])
        self.assertEqual(r.upravljaj("brisi"), {"napaka": "neveljavno"})
        self.assertEqual(r.upravljaj("cas", "x"), {"napaka": "neveljavno"})

    def test_ustavi_ne_zazene_znova(self):
        """»ustavi« je premor samo, ce Spotify res igra (sveze stanje), tudi ce ga poklicemo dvakrat zapored."""
        k = LazniKanal(stanje={"zeton": True, "predvajalnik": True, "naslov": "Pesem", "igra": True})
        r = self._racun(k)
        k.zacni(False, True)
        klik = '"control-button-playpause"'
        self.assertEqual(r.upravljaj("ustavi"), {"ok": True})
        self.assertEqual(sum(klik in x and x != sr.STANJE_JS for x in k.izrazi), 1)
        k.stanje = dict(k.stanje, igra=False)              # stran je ustavljena; straza tega se ni prebrala
        r._predvajanje = {"naslov": "Pesem", "igra": True}
        self.assertEqual(r.upravljaj("ustavi"), {"ok": True})
        self.assertEqual(sum(klik in x and x != sr.STANJE_JS for x in k.izrazi), 1)
        self.assertFalse(r._predvajanje["igra"])

    def test_predvajaj(self):
        k = LazniKanal()
        r = self._racun(k)
        self.assertEqual(r.predvajaj("spotify:track:4uLU6hMCjMI75M1A2tKUQC", "spotify:playlist:1111111111111111111111"), {"ok": True, "delno": False})
        self.assertIn('"/playlist/1111111111111111111111"', "".join(k.izrazi))
        self.assertIn('"/track/4uLU6hMCjMI75M1A2tKUQC"', k.izrazi[-1])
        self.assertEqual(r.predvajaj("spotify:episode:5Xt5DXGzch68nYYamXrNxZ", "spotify:show:2222222222222222222222")["ok"], True)
        self.assertIn('"/episode/5Xt5DXGzch68nYYamXrNxZ"', "".join(k.izrazi[-3:]))
        self.assertEqual(r.predvajaj("javascript:alert(1)", ""), {"napaka": "neveljavno"})
        self.assertEqual(r.predvajaj("spotify:track:\"); x(\"", "collection"), {"napaka": "neveljavno"})

    def test_odjava_izbrise_profil(self):
        k = LazniKanal()
        os.makedirs(k.profil(), exist_ok=True)
        r = self._racun(k)
        r.seznami()
        self.assertEqual(r.odjava(), {"ok": True})
        self.assertFalse(os.path.exists(k.profil()))
        self.assertFalse(r.stanje()["prijavljen"])

    def test_nastavitve_brez_skrivnosti(self):
        r = self._racun(LazniKanal(pf={"libraryV3": {"status": 200, "podatki": PF_KNJIZNICA}}))
        r.seznami()
        r.nastavi_scit(True)
        self.assertEqual(set(json.load(open(os.path.join(self.mapa, "spotify.json")))), {"scit", "prijavljen"})


class MedijskiCenterTest(unittest.TestCase):
    def test_shranjen_seznam_je_zaseben_in_ne_gre_v_link(self):
        with tempfile.TemporaryDirectory() as mapa:
            m = os_media.MediaCenter(os.path.join(mapa, "media"), roots=[])
            m._spotify = sr.Racun(os.path.join(mapa, "media"), straza=False, na_voljo=lambda: True,
                                  kanal=LazniKanal(pf={"fetchPlaylist": {"status": 200, "podatki": PF_SEZNAM}}))
            sz = m.sp_seznam("1111111111111111111111", "Moj seznam")
            self.assertEqual((sz["ime"], sz["sp"], len(sz["vnosi"])), ("Moj seznam", "1111111111111111111111", 2))
            vnos = m.resolve(sz["vnosi"][0]["id"])
            self.assertEqual((vnos["spotify"], vnos["spotify_kontekst"]),
                             ("spotify:track:4uLU6hMCjMI75M1A2tKUQC", "spotify:playlist:1111111111111111111111"))
            with mock.patch.object(m, "poisci_posnetke"):
                r = m.sp_shrani("1111111111111111111111")
            self.assertEqual((r["ok"], r["stevilo"]), (True, 2))
            self.assertTrue(m._seznami_beri()[0]["zaseben"])
            self.assertEqual(m.seznami_izvoz({})["lists"], [])
            self.assertEqual(link_seznami.izvoz({}, os.path.join(mapa, "media"))["lists"], [])
            self.assertEqual(m.sp_shrani("drug"), {"napaka": "ni_mogoce"})

    def test_napaka_brez_prijave(self):
        with tempfile.TemporaryDirectory() as mapa:
            m = os_media.MediaCenter(os.path.join(mapa, "media"), roots=[])
            m._spotify = sr.Racun(os.path.join(mapa, "media"), straza=False, na_voljo=lambda: False, kanal=LazniKanal())
            self.assertEqual(m.sp_seznam("vseckane"), {"napaka": "ni_drm"})
            # obstojeci uvoz javnih seznamov ostane (Spotify brez prijave): razlog kot doslej
            self.assertEqual(m.uvozi_seznam("ni povezava"), {"napaka": "ni_seznam"})


class SafeerDrmTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(KOREN, "assets", "safeer_drm", "main.js"), encoding="utf-8") as f:
            self.js = f.read()

    def test_cdp_brez_vrat_in_samo_evaluate(self):
        # CDP prek webContents.debugger; vrata razhroscevanja samo za meritve (SAFEER_DRM_CDP), nikoli za Spotify.
        self.assertIn("webContents.debugger", self.js)
        self.assertIn("'Runtime.evaluate'", self.js)
        self.assertNotIn("remote-debugging-port', '0'", self.js)
        izvedi = self.js[self.js.index("function izvediCdp"):self.js.index("function obdelajUkaz")]
        self.assertEqual(re.findall(r"sendCommand\('([A-Za-z.]+)'", izvedi), ["Runtime.evaluate"])

    def test_zeton_nikoli_v_dnevnik(self):
        for vr in re.findall(r"zapisi\([^;]*", self.js):
            self.assertNotRegex(vr, r"zeton|zadnji|authorization|Bearer|requestHeaders", vr)
        self.assertNotIn("console.log(zeton", self.js)

    def test_zacetna_skripta_se_razcleni(self):
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("ni node")
        koda = ("const s=require('fs').readFileSync(process.argv[1],'utf8');"
                "const a=s.indexOf('const SPOTIFY_ZACETEK = `'),b=s.indexOf('})();`;',a)+7;"
                "const k=eval(s.slice(a+'const SPOTIFY_ZACETEK = '.length,b));"
                "global.window={fetch:function(){}};global.XMLHttpRequest=function(){};"
                "['open','setRequestHeader','send'].forEach(n=>XMLHttpRequest.prototype[n]=function(){});"
                "global.HTMLMediaElement=function(){};HTMLMediaElement.prototype.play=function(){};"
                "eval(k);const S=window.__safeerSpotify;"
                "window.fetch('https://api-partner.spotify.com/pathfinder/v2/query',{headers:{authorization:'Bearer abcdefghijklmnopqrstuvwxyz'},"
                "body:JSON.stringify({operationName:'fetchPlaylist',variables:{uri:'u'},extensions:{persistedQuery:{sha256Hash:'a'.repeat(64)}}})});"
                "S.klic('../x').then(r=>console.log(JSON.stringify([S.imaZeton(),S.vzorci(),r.napaka,Object.isFrozen(S)])));")
        izid = subprocess.run(["node", "-e", koda, os.path.join(KOREN, "assets", "safeer_drm", "main.js")],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(izid.returncode, 0, izid.stderr)
        self.assertEqual(json.loads(izid.stdout), [True, ["fetchPlaylist"], "pot", True])


class VmesnikTest(unittest.TestCase):
    def test_besedila_v_vseh_jezikih(self):
        with open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8") as f:
            koda = f.read()
        with open(os.path.join(KOREN, "assets", "os", "besedila.js"), encoding="utf-8") as f:
            besedila = f.read()
        kljuci = set(re.findall(r'\bt\("((?:sp[A-Z]|scitSpotify)[A-Z_a-z]*)"', koda))
        # napake (spNapaka_<koda>) sestavi spNapaka(); vse kode, ki jih vrne core/spotify_racun.py
        kljuci |= {"spNapaka_" + k for k in ("stran", "ni_odziva", "ni_drm", "potekla", "ni_prijave", "prazen",
                                            "neveljavno", "ne_tece", "napaka")}
        self.assertGreater(len(kljuci), 25)
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            bloki = "\n".join(re.findall(r"Object\.assign\(BESEDILA_OS\.%s, \{(.*?)\}\);" % jezik, besedila, re.S))
            for kljuc in kljuci:
                self.assertIn('"%s":' % kljuc, bloki, "%s manjka v %s" % (kljuc, jezik))
        self.assertIn("Spotify v pogojih prepoveduje izogibanje oglasom; zaščito lahko izklopiš v nastavitvah Ščita.", besedila)

    def test_metode_mostu(self):
        from core import os_katalog
        for metoda in ("mediaSpStanje", "mediaSpSeznami", "mediaSpSeznam", "mediaSpShrani", "mediaSpPrijava",
                       "mediaSpOdjava", "mediaSpPrenesi", "mediaSpUkaz", "mediaSpScit"):
            self.assertTrue(hasattr(os_katalog.Katalog, os_katalog.Katalog.METODE[metoda]), metoda)


if __name__ == "__main__":
    unittest.main()
