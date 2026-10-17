"""Racun YouTube v Medijskem centru (core/youtube_racun.py): piskotki Spleta, SAPISIDHASH in InnerTube z mock odgovori."""
import contextlib
import hashlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import link_seznami, os_media, youtube_racun as yr  # noqa: E402

SAPISID = "skrivnost-SAPISID-123"


def baza(mapa, vrstice):
    pot = os.path.join(mapa, "cookies.sqlite")
    c = sqlite3.connect(pot)
    c.execute("CREATE TABLE moz_cookies (id INTEGER PRIMARY KEY, name TEXT, value TEXT, host TEXT, path TEXT, expiry INTEGER, "
              "lastAccessed INTEGER, isSecure INTEGER, isHttpOnly INTEGER, sameSite INTEGER)")
    for ime, vrednost, gostitelj, potek in vrstice:
        c.execute("INSERT INTO moz_cookies (name, value, host, path, expiry) VALUES (?, ?, ?, '/', ?)",
                  (ime, vrednost, gostitelj, potek))
    c.commit()
    c.close()
    return pot


def prijavljena_baza(mapa):
    cez_leto = int(time.time()) + 365 * 86400
    return baza(mapa, [("SAPISID", SAPISID, ".youtube.com", cez_leto),
                       ("__Secure-3PAPISID", "tri-p", ".youtube.com", cez_leto),
                       ("SID", "sid-vrednost", ".youtube.com", cez_leto)])


def posnetek(vid, naslov):
    return {"playlistVideoRenderer": {"videoId": vid, "title": {"runs": [{"text": naslov}]},
                                      "shortBylineText": {"runs": [{"text": "Kanal"}]}}}


def nadaljuj(zeton):
    return {"continuationItemRenderer": {"continuationEndpoint": {"continuationCommand": {
        "token": zeton, "request": "CONTINUATION_REQUEST_TYPE_BROWSE"}}}}


KNJIZNICA = {"contents": {"richGridRenderer": {"contents": [
    {"richItemRenderer": {"content": {"lockupViewModel": {
        "contentId": "PLzasebni0001", "contentType": "LOCKUP_CONTENT_TYPE_PLAYLIST",
        "metadata": {"lockupMetadataViewModel": {"title": {"content": "Moj zasebni"}}}}}}},
    {"gridPlaylistRenderer": {"playlistId": "PLnenaveden02", "title": {"runs": [{"text": "Nenavedeni"}]}}},
    {"gridPlaylistRenderer": {"playlistId": "WL", "title": {"simpleText": "Watch later"}}},
]}}}
MENI = {"actions": [{"openPopupAction": {"popup": {"multiPageMenuRenderer": {"header": {"activeAccountHeaderRenderer": {
    "accountName": {"simpleText": "Ana Primer"}, "channelHandle": {"simpleText": "@ana"}}}}}}}]}
ODJAVLJEN = {"responseContext": {"mainAppWebResponseContext": {"loggedOut": True}}}


class MockInnerTube:
    """Odgovarja kot youtubei/v1 za prijavljenega uporabnika; zapise vsako zahtevo (naslov, glave, telo)."""

    def __init__(self, odgovori=None, status=200):
        self.zahteve = []
        self.odgovori = odgovori or {}
        self.status = status

    def __call__(self, naslov, glave, telo, _cas):
        o = json.loads(telo.decode("utf-8"))
        self.zahteve.append((naslov, glave, o))
        if self.status != 200:
            return self.status, ""
        kljuc = o.get("browseId") or o.get("continuation") or naslov.split("/youtubei/v1/")[1].split("?")[0]
        return 200, json.dumps(self.odgovori.get(kljuc, ODJAVLJEN))


def odgovori_racuna():
    return {
        "account/account_menu": MENI,
        "FEplaylist_aggregation": KNJIZNICA,
        "VLLL": {"contents": [{"playlistMetadataRenderer": {"title": "Liked videos"}},
                              posnetek("aaaaaaaaaa1", "Izvajalec - Prva"), posnetek("aaaaaaaaaa2", "Druga"), nadaljuj("Z1")]},
        "Z1": {"onResponseReceivedActions": [{"appendContinuationItemsAction": {"continuationItems": [
            posnetek("aaaaaaaaaa3", "Tretja"), nadaljuj("Z2")]}}]},
        "Z2": {"onResponseReceivedActions": [{"appendContinuationItemsAction": {"continuationItems": [
            posnetek("aaaaaaaaaa4", "Četrta")]}}]},
        "VLWL": {"contents": [{"playlistMetadataRenderer": {"title": "Watch later"}}, posnetek("bbbbbbbbbb1", "Pozneje")]},
    }


class SapisidhashTest(unittest.TestCase):
    def test_izracun(self):
        cas = 1700000000
        pricakovano = hashlib.sha1(("%d %s https://www.youtube.com" % (cas, SAPISID)).encode()).hexdigest()
        glava = yr.sapisidhash({"SAPISID": SAPISID}, cas)
        self.assertEqual(glava, "SAPISIDHASH %d_%s" % (cas, pricakovano))

    def test_dodatni_deli_in_brez_prijave(self):
        glava = yr.sapisidhash({"SAPISID": "a", "__Secure-1PAPISID": "b", "__Secure-3PAPISID": "c"}, 5)
        self.assertTrue(glava.startswith("SAPISIDHASH 5_"))
        self.assertIn(" SAPISID1PHASH 5_", glava)
        self.assertIn(" SAPISID3PHASH 5_", glava)
        # Samo __Secure-3PAPISID (brez SAPISID) tudi zadostuje; brez obeh ni glave.
        self.assertTrue(yr.sapisidhash({"__Secure-3PAPISID": "c"}, 5).startswith("SAPISIDHASH 5_"))
        self.assertEqual(yr.sapisidhash({"SID": "x"}, 5), "")


class PiskotkiTest(unittest.TestCase):
    def test_bere_samo_veljavne_piskotke_youtube(self):
        with tempfile.TemporaryDirectory() as mapa:
            zdaj = int(time.time())
            pot = baza(mapa, [("SAPISID", "dobro", ".youtube.com", zdaj + 1000),
                              ("STAR", "potekel", ".youtube.com", zdaj - 10),
                              ("SEJA", "seja", "www.youtube.com", 0),
                              ("TUJ", "ne", ".notyoutube.com", zdaj + 1000),
                              ("GOOGLE", "ne", ".google.com", zdaj + 1000),
                              ("MUSIC", "ne", "music.youtube.com", zdaj + 1000)])
            p = yr.beri_piskotke(pot)
        self.assertEqual(p, {"SAPISID": "dobro", "SEJA": "seja"})
        self.assertTrue(yr.prijavljen(p))

    def test_manjkajoca_ali_pokvarjena_baza(self):
        with tempfile.TemporaryDirectory() as mapa:
            self.assertEqual(yr.beri_piskotke(os.path.join(mapa, "ni.sqlite")), {})
            pokvarjena = os.path.join(mapa, "cookies.sqlite")
            with open(pokvarjena, "w") as f:
                f.write("to ni sqlite")
            izhod = io.StringIO()
            with contextlib.redirect_stdout(izhod):
                self.assertEqual(yr.beri_piskotke(pokvarjena), {})

    def test_pot_je_shramba_spleta(self):
        from core import config
        self.assertEqual(yr.pot_piskotkov(), os.path.join(config.CONFIG_DIR, "cookies.sqlite"))


class RacunTest(unittest.TestCase):
    def test_brez_prijave_ni_zahtev(self):
        with tempfile.TemporaryDirectory() as mapa:
            it = MockInnerTube(odgovori_racuna())
            r = yr.Racun(baza(mapa, []), it)
            self.assertEqual(r.stanje(), {"prijavljen": False, "ime": "", "seznami": [], "racuni": [], "potekla": False})
            with self.assertRaises(yr.PoteklaPrijava):
                r.seznam("LL")
        self.assertEqual(it.zahteve, [])

    def test_stanje_ime_in_seznami(self):
        with tempfile.TemporaryDirectory() as mapa:
            it = MockInnerTube(odgovori_racuna())
            s = yr.Racun(prijavljena_baza(mapa), it).stanje()
        self.assertTrue(s["prijavljen"])
        self.assertEqual(s["ime"], "Ana Primer")
        self.assertEqual([x["id"] for x in s["seznami"]], ["LL", "WL", "LM", "PLzasebni0001", "PLnenaveden02"])
        self.assertEqual(s["seznami"][3]["ime"], "Moj zasebni")
        naslov, glave, telo = it.zahteve[0]
        self.assertTrue(naslov.startswith("https://www.youtube.com/youtubei/v1/account/account_menu"))
        self.assertTrue(glave["Authorization"].startswith("SAPISIDHASH "))
        self.assertEqual((glave["Origin"], glave["X-Origin"], glave["X-Goog-AuthUser"]),
                         ("https://www.youtube.com", "https://www.youtube.com", "0"))
        self.assertIn("SAPISID=" + SAPISID, glave["Cookie"])
        self.assertEqual(telo["context"]["client"]["clientName"], "WEB")
        self.assertTrue(all(z[0].startswith("https://www.youtube.com/") for z in it.zahteve))

    def test_knjiznica_ko_agregacije_ni(self):
        odgovori = dict(odgovori_racuna(), FEplaylist_aggregation={"contents": {}}, FElibrary=KNJIZNICA)
        with tempfile.TemporaryDirectory() as mapa:
            s = yr.Racun(prijavljena_baza(mapa), MockInnerTube(odgovori)).stanje()
        self.assertIn("PLnenaveden02", [x["id"] for x in s["seznami"]])

    def test_vseckani_z_nadaljevanjem(self):
        with tempfile.TemporaryDirectory() as mapa:
            it = MockInnerTube(odgovori_racuna())
            sz = yr.Racun(prijavljena_baza(mapa), it).seznam("LL")
        self.assertEqual(sz["ime"], "Liked videos")
        self.assertEqual([s["youtube"] for s in sz["skladbe"]], ["aaaaaaaaaa1", "aaaaaaaaaa2", "aaaaaaaaaa3", "aaaaaaaaaa4"])
        self.assertEqual((sz["skladbe"][0]["izvajalec"], sz["skladbe"][0]["naslov"]), ("Izvajalec", "Prva"))
        self.assertEqual([z[2].get("browseId") or z[2].get("continuation") for z in it.zahteve], ["VLLL", "Z1", "Z2"])

    def test_pozneje(self):
        with tempfile.TemporaryDirectory() as mapa:
            sz = yr.Racun(prijavljena_baza(mapa), MockInnerTube(odgovori_racuna())).seznam("WL")
        self.assertEqual([s["youtube"] for s in sz["skladbe"]], ["bbbbbbbbbb1"])

    def test_nadaljevanje_do_najvec(self):
        odgovori = {"VLPLvelik": {"contents": [posnetek("v%010d" % 0, "P0"), nadaljuj("S1")]}}
        for i in range(1, 30):
            odgovori["S%d" % i] = {"x": [posnetek("v%010d" % (j + i * 100), "P") for j in range(100)] + [nadaljuj("S%d" % (i + 1))]}
        with tempfile.TemporaryDirectory() as mapa, mock.patch.object(yr.uvoz_seznama, "NAJVEC", 250):
            it = MockInnerTube(odgovori)
            sz = yr.Racun(prijavljena_baza(mapa), it).seznam("PLvelik")
        self.assertEqual(len(sz["skladbe"]), 250)
        self.assertEqual(len(it.zahteve), 4)

    def test_potekla_prijava(self):
        with tempfile.TemporaryDirectory() as mapa:
            pot = prijavljena_baza(mapa)
            # YouTube piskotkov ne sprejme vec: odgovor »loggedOut« ali 401.
            s = yr.Racun(pot, MockInnerTube({})).stanje()
            self.assertEqual((s["prijavljen"], s["potekla"]), (False, True))
            self.assertTrue(yr.Racun(pot, MockInnerTube(status=401)).stanje()["potekla"])
            with self.assertRaises(yr.PoteklaPrijava):
                yr.Racun(pot, MockInnerTube({})).seznam("LL")

    def test_spremenjen_odgovor_ne_sesuje(self):
        with tempfile.TemporaryDirectory() as mapa:
            pot = prijavljena_baza(mapa)
            r = yr.Racun(pot, lambda *_a: (200, "<html>ni json</html>"))
            self.assertTrue(r.stanje()["potekla"])
            izhod = io.StringIO()
            with contextlib.redirect_stdout(izhod):
                s = yr.Racun(pot, lambda *_a: (500, "")).stanje()
        self.assertTrue(s["prijavljen"] and s["napaka"])
        self.assertNotIn(SAPISID, izhod.getvalue())
        self.assertNotIn("SAPISIDHASH", izhod.getvalue())

    def test_neveljaven_id(self):
        with tempfile.TemporaryDirectory() as mapa:
            it = MockInnerTube(odgovori_racuna())
            self.assertIsNone(yr.Racun(prijavljena_baza(mapa), it).seznam("../x?y"))
        self.assertEqual(it.zahteve, [])

    def test_brez_preusmeritev(self):
        # Piskotki in Authorization ne smejo slediti preusmeritvi na drug streznik.
        self.assertIsNone(yr._BrezPreusmeritev().redirect_request(None, None, 302, "Found", {}, "https://drugje.example/"))


class MedijskiCenterRacunTest(unittest.TestCase):
    def _mc(self, mapa):
        m = os_media.MediaCenter(os.path.join(mapa, "media"), roots=[])
        m._yt_racun = yr.Racun(prijavljena_baza(mapa), MockInnerTube(odgovori_racuna()))
        return m

    def test_predvajanje_in_shranjevanje_gre_na_naprave(self):
        """Lastnik 17. 10. 2026: prijava enkrat, seznami racuna na vseh uporabnikovih napravah (Link)."""
        with tempfile.TemporaryDirectory() as mapa:
            m = self._mc(mapa)
            sz = m.yt_seznam("LL")
            self.assertEqual((sz["yt"], len(sz["vnosi"]), sz["yt_racun"]), ("LL", 4, 0))
            vnos = m.resolve(sz["vnosi"][1]["id"])
            self.assertEqual(vnos["url"], "https://www.youtube.com/watch?v=aaaaaaaaaa2")
            r = m.yt_shrani("LL")
            self.assertEqual((r["ok"], r["stevilo"]), (True, 4))
            self.assertEqual([x["ime"] for x in m.seznami()], ["Liked videos"])
            self.assertEqual([x["ime"] for x in m.seznami_izvoz({})["lists"]], ["Liked videos"])

    def test_samodejno_usklajevanje_ne_vrne_izbrisanega(self):
        with tempfile.TemporaryDirectory() as mapa:
            m = self._mc(mapa)
            m._yt_zapisi("Moj seznam", [{"naslov": "A", "izvajalec": "B", "youtube": "aaaaaaaaaa1"}])
            self.assertEqual([x["ime"] for x in m.seznami()], ["Moj seznam"])
            m.odstrani_seznam("Moj seznam")
            m._yt_zapisi("Moj seznam", [{"naslov": "A", "izvajalec": "B", "youtube": "aaaaaaaaaa1"}])
            self.assertEqual(m.seznami(), [])

    def test_vec_racunov(self):
        with tempfile.TemporaryDirectory() as mapa:
            r = yr.Racun(prijavljena_baza(mapa), MockInnerTube(odgovori_racuna()))
            st = r.stanje()
            # Mock vrne isto ime za vsak indeks: drugi racun ne obstaja, ostane en racun.
            self.assertEqual(len(st["racuni"]), 1)
            self.assertTrue(all(x.get("racun") == 0 for x in st["seznami"]))

    def test_potekla_in_brez_prijave(self):
        with tempfile.TemporaryDirectory() as mapa:
            m = os_media.MediaCenter(os.path.join(mapa, "media"), roots=[])
            m._yt_racun = yr.Racun(prijavljena_baza(mapa), MockInnerTube({}))
            self.assertEqual(m.yt_seznam("LL"), {"napaka": "potekla"})
            self.assertEqual(m.yt_shrani("LL"), {"napaka": "ni_mogoce"})
            m._yt_racun = yr.Racun(os.path.join(mapa, "ni.sqlite"), MockInnerTube({}))
            self.assertFalse(m.yt_stanje()["prijavljen"])
            # Brez prijave uvoz zasebnega seznama pove razlog kot doslej.
            self.assertEqual(m.uvozi_seznam("https://www.youtube.com/playlist?list=LL"), {"napaka": "zaseben"})

    def test_prijavljen_uvozi_zaseben_seznam(self):
        with tempfile.TemporaryDirectory() as mapa:
            m = self._mc(mapa)
            r = m.uvozi_seznam("https://www.youtube.com/playlist?list=LL")
            self.assertEqual((r["ime"], r["stevilo"]), ("Liked videos", 4))
            self.assertTrue(m._seznami_beri()[0]["zaseben"])


class VmesnikTest(unittest.TestCase):
    def test_besedila_v_vseh_jezikih(self):
        import re
        koren = os.path.join(os.path.dirname(__file__), "..")
        with open(os.path.join(koren, "assets", "os", "os.js"), encoding="utf-8") as f:
            koda = f.read()
        with open(os.path.join(koren, "assets", "os", "besedila.js"), encoding="utf-8") as f:
            besedila = f.read()
        kljuci = set(re.findall(r'\bt\("(yt[A-Z][A-Za-z]+)"', koda))
        self.assertGreater(len(kljuci), 10)
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            bloki = "\n".join(re.findall(r"Object\.assign\(BESEDILA_OS\.%s, \{(.*?)\}\);" % jezik, besedila, re.S))
            for kljuc in kljuci:
                self.assertIn('"%s":' % kljuc, bloki, "%s manjka v %s" % (kljuc, jezik))
        # Prijava samo na gumb (Splet, Google); nic samodejnega ob odprtju Medijskega centra.
        self.assertIn('klic("splet", [YT_PRIJAVA, true])', koda)
        self.assertIn(yr.PRIJAVA, koda)


if __name__ == "__main__":
    unittest.main()
