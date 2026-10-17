"""Hitrost Medijskega centra z dodatki Stremio (17. 10. 2026, testni PC: iskanje »dune« 76 s, katalog 10 s).

Katalogi enega dodatka se nalozijo hkrati, manifest je v pomnilniku, strezniki/dodatki se vprasajo hkrati in star
odgovor (do 6 h) se vrne takoj ter osvezi v ozadju.
"""
import json
import tempfile
import threading
import time
import unittest
from unittest import mock

from core import media_servers as ms
from core import os_media

SRV = {"id": "s1", "ime": "Dodatek"}


def _dodatek(zakasnitev, stevec):
    manifest = {"id": "a", "name": "Dodatek",
                "catalogs": [{"type": "movie", "id": "k%d" % i} for i in range(4)]}

    def fake(url, *a, **k):
        if url.endswith("/manifest.json"):
            stevec["manifest"] = stevec.get("manifest", 0) + 1
            return json.dumps(manifest).encode()
        time.sleep(zakasnitev)
        i = url.rsplit("/k", 1)[1].split(".")[0]
        return json.dumps({"metas": [{"id": "tt%s" % i, "name": "Film %s" % i}]}).encode()
    return fake


class KatalogiHkrati(unittest.TestCase):
    def test_stirje_pocasni_katalogi_hkrati_in_vrstni_red_ostane(self):
        stevec = {}
        with mock.patch.object(ms, "_request", _dodatek(0.4, stevec)):
            t0 = time.monotonic()
            izid = ms.catalog("stremio", "https://dodatek.primer/manifest.json", SRV, "")
            trajanje = time.monotonic() - t0
        self.assertEqual([x["naslov"] for x in izid], ["Film 0", "Film 1", "Film 2", "Film 3"])
        self.assertLess(trajanje, 1.2, "katalogi naj se nalagajo hkrati (zaporedno bi bilo 1,6 s)")

    def test_manifest_iz_pomnilnika_preverba_pa_sveza(self):
        stevec = {}
        with mock.patch.object(ms, "_request", _dodatek(0, stevec)):
            ms.catalog("stremio", "https://dodatek.primer/manifest.json", SRV, "")
            ms.catalog("stremio", "https://dodatek.primer/manifest.json", SRV, "")
            self.assertEqual(stevec["manifest"], 1)
            ms.stremio_manifest("https://dodatek.primer/manifest.json", sveze=True)
            self.assertEqual(stevec["manifest"], 2)

    def test_pokvarjen_katalog_ne_ustavi_drugih(self):
        def fake(url, *a, **k):
            if url.endswith("/manifest.json"):
                return json.dumps({"id": "a", "catalogs": [{"type": "movie", "id": "dobri"},
                                                           {"type": "movie", "id": "slab"}]}).encode()
            if "slab" in url:
                raise OSError("rok potekel")
            return json.dumps({"metas": [{"id": "tt1", "name": "Dober"}]}).encode()
        with mock.patch.object(ms, "_request", fake):
            izid = ms.catalog("stremio", "https://dodatek.primer/manifest.json", SRV, "")
        self.assertEqual([x["naslov"] for x in izid], ["Dober"])


class StrezikiHkratiInStarOdgovor(unittest.TestCase):
    def _center(self, strezniki):
        center = os_media.MediaCenter(tempfile.mkdtemp(), roots=[], secret_encryptor=lambda s: s,
                                      secret_decryptor=lambda s: s)
        # Dodatki, za katere je ze znano, da niso zasebni (kot jih zapise add_server) - brez branja manifesta.
        center._load = lambda: {"osebni_strezniki": [dict(s, zaseben=False) for s in strezniki]}
        center._cinemeta_items = lambda *a, **k: []
        return center

    def test_strezniki_hkrati(self):
        strezniki = [{"id": "s%d" % i, "ponudnik": "stremio", "url": "https://d%d" % i, "ime": "D%d" % i}
                     for i in range(3)]
        center = self._center(strezniki)

        def katalog(provider, url, server, secret, query=""):
            time.sleep(0.4)
            return [{"id": server["id"], "naslov": server["ime"]}]
        with mock.patch.object(os_media.media_servers, "catalog", katalog):
            t0 = time.monotonic()
            izid = center._personal_items("")
            trajanje = time.monotonic() - t0
        self.assertEqual([x["naslov"] for x in izid], ["D0", "D1", "D2"])
        self.assertLess(trajanje, 1.0)

    def test_star_odgovor_takoj_osvezitev_v_ozadju(self):
        center = self._center([{"id": "s1", "ponudnik": "stremio", "url": "https://d", "ime": "D"}])
        center._server_cache["s1:"] = (time.time() - 3600, [{"id": "star", "naslov": "Star"}])
        osvezeno = threading.Event()

        def katalog(*a, **k):
            time.sleep(0.3)
            osvezeno.set()
            return [{"id": "nov", "naslov": "Nov"}]
        with mock.patch.object(os_media.media_servers, "catalog", katalog):
            t0 = time.monotonic()
            izid = center._personal_items("")
            self.assertLess(time.monotonic() - t0, 0.2, "star odgovor se vrne takoj")
            self.assertEqual([x["naslov"] for x in izid], ["Star"])
            self.assertTrue(osvezeno.wait(3))
            for _ in range(50):
                if center._server_cache["s1:"][1][0]["naslov"] == "Nov":
                    break
                time.sleep(0.02)
        self.assertEqual(center._server_cache["s1:"][1][0]["naslov"], "Nov")

    def test_mrtev_dodatek_ne_zadrzi_iskanja(self):
        strezniki = [{"id": "ziv", "ponudnik": "stremio", "url": "https://z", "ime": "Ziv"},
                     {"id": "mrtev", "ponudnik": "stremio", "url": "https://m", "ime": "Mrtev"}]
        center = self._center(strezniki)
        center.STREZNIKI_ROK_S = 0.5
        klici = {"mrtev": 0}

        def katalog(provider, url, server, secret, query=""):
            if server["id"] == "mrtev":
                klici["mrtev"] += 1
                time.sleep(1.0)
                raise OSError("rok potekel")
            return [{"id": "z1", "naslov": "Ziv film"}]
        with mock.patch.object(os_media.media_servers, "catalog", katalog), \
                mock.patch.object(os_media.media_servers, "ujema_iskanje", lambda item, q: True):
            t0 = time.monotonic()
            self.assertEqual([x["naslov"] for x in center._personal_items("film")], ["Ziv film"])
            self.assertLess(time.monotonic() - t0, 0.9, "ne cakamo mrtvega dodatka dlje od roka")
            time.sleep(0.8)            # mrtvi se v ozadju izteče in zapomni napako
            t0 = time.monotonic()
            center._personal_items("film")
            self.assertLess(time.monotonic() - t0, 0.3, "zapomnjena napaka: ne vprasamo ga znova")
        self.assertEqual(klici["mrtev"], 1)


class VrstniRedIskanja(unittest.TestCase):
    def test_tocen_naslov_prvi(self):
        u = os_media._ujemanje_naslova
        self.assertEqual(u("Breaking Bad", "breaking bad"), 0)
        self.assertEqual(u("Breaking Bad (2008)", "Breaking  Bad"), 0)
        self.assertEqual(u("Breaking Bad: Original Minisodes", "breaking bad"), 1)
        self.assertEqual(u("No Half Measures: Creating the Final Season of Breaking Bad", "breaking bad"), 2)
        naslovi = ["No Half Measures: Creating the Final Season of Breaking Bad", "Breaking Bad: Original Minisodes",
                   "Breaking Bad"]
        self.assertEqual(sorted(naslovi, key=lambda n: u(n, "breaking bad"))[0], "Breaking Bad")


if __name__ == "__main__":
    unittest.main()
