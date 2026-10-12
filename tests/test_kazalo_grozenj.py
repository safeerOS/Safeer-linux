"""Kazalo groženj na disku (mmap) in ena storitev na proces (12. 10. 2026, manj RAM-a v Safeer OS)."""
import json
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from core import threat_intel
from core.threat_intel import ThreatIntelService, _load_feed_module

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "signed_feed"
KEY = json.loads((FIXTURES / "public_key.json").read_text())
TRUSTED = {KEY["key_id"]: KEY["public_key"]}
feed = _load_feed_module()

PRAVILA = [("zlo.example", "domain", "malware", 0), ("c2.example.net", "hostname", "botnet_c2", 0),
           ("203.0.113.9", "ipv4", "phishing", 0), ("https://scam.example/pot?x=1", "url", "scam", 0),
           ("oglas.example", "domain", "ads", 0)]


class Kazalo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pot = os.path.join(self.tmp.name, "threats-1-index.bin")
        self.sha = "ab" * 32

    def tearDown(self):
        self.tmp.cleanup()

    def test_enaki_zadetki_kot_v_pomnilniku(self):
        v_pomnilniku = feed.ThreatIndex(PRAVILA)
        self.assertTrue(v_pomnilniku.shrani(self.pot, self.sha))
        z_diska = feed.ThreatIndex.nalozi(self.pot, self.sha)
        self.assertIsNotNone(z_diska)
        self.assertEqual(z_diska.size, len(PRAVILA))
        for vprasanje in ("https://zlo.example/", "https://a.b.zlo.example/x", "http://c2.example.net/",
                          "http://203.0.113.9/", "https://scam.example/pot?x=1", "https://scam.example/pot",
                          "https://oglas.example/", "https://cisto.example/", "notaurl"):
            self.assertEqual(z_diska.match_url(vprasanje), v_pomnilniku.match_url(vprasanje), vprasanje)
        for gostitelj in ("zlo.example", "x.zlo.example", "c2.example.net", "203.0.113.9", "nic.example"):
            self.assertEqual(z_diska.match_host(gostitelj), v_pomnilniku.match_host(gostitelj), gostitelj)

    def test_drug_paket_ali_poskodba_ni_kazalo(self):
        feed.ThreatIndex(PRAVILA).shrani(self.pot, self.sha)
        self.assertIsNone(feed.ThreatIndex.nalozi(self.pot, "cd" * 32))      # kazalo drugega paketa
        with open(self.pot, "r+b") as f:
            f.seek(100)
            b = f.read(1)
            f.seek(100)
            f.write(bytes([b[0] ^ 0xFF]))
        self.assertIsNone(feed.ThreatIndex.nalozi(self.pot, self.sha))        # kontrolna vsota
        self.assertIsNone(feed.ThreatIndex.nalozi(os.path.join(self.tmp.name, "ni.bin"), self.sha))

    def test_prazno_kazalo(self):
        feed.ThreatIndex().shrani(self.pot, self.sha)
        prazno = feed.ThreatIndex.nalozi(self.pot, self.sha)
        self.assertIsNone(prazno.match_url("https://zlo.example/"))


class FixtureServer:
    def __init__(self, scenario):
        self.scenario = scenario

    def fetch(self, url, limit):
        name = f"{self.scenario}-latest.json" if url.endswith("/latest.json") else f"{self.scenario}-bundle.json"
        return (FIXTURES / name).read_bytes()


class Shramba(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _storitev(self):
        return ThreatIntelService(self.tmp.name, trusted_keys=TRUSTED, base_urls=["https://intel.test"],
                                  fetch=FixtureServer("valid-100").fetch)

    def test_posodobitev_zapise_kazalo_in_ponovni_zagon_ga_uporabi(self):
        prva = self._storitev()
        self.assertTrue(prva.update_now())
        kazala = list(Path(self.tmp.name).glob("threats-*-index.bin"))
        self.assertEqual(len(kazala), 1)
        primer = "https://malware.example/"
        pricakovano = prva.match(primer)
        druga = self._storitev()
        with unittest.mock.patch.object(feed, "verify_bundle", side_effect=AssertionError("JSON ne sme v razclembo")):
            self.assertTrue(druga.store.load())
        self.assertEqual(druga.match(primer), pricakovano)
        self.assertEqual(druga.status()["rules"], prva.status()["rules"])

    def test_poskodovan_paket_se_vedno_zavrnjen(self):
        prva = self._storitev()
        self.assertTrue(prva.update_now())
        paket = next(Path(self.tmp.name).glob("threats-*-bundle.json"))
        podatki = bytearray(paket.read_bytes())
        podatki[10] ^= 0x01
        paket.write_bytes(bytes(podatki))
        druga = self._storitev()
        self.assertFalse(druga.store.load())        # kazalo ne obide preverjanja paketa


class Skupna(unittest.TestCase):
    def test_ena_storitev_na_mapo(self):
        with tempfile.TemporaryDirectory() as d, \
                unittest.mock.patch.object(ThreatIntelService, "start", return_value=True) as zagon:
            a = threat_intel.skupna(d)
            b = threat_intel.skupna(d + "/")
            self.assertIs(a, b)
            self.assertEqual(zagon.call_count, 1)
            threat_intel._SKUPNE.clear()


if __name__ == "__main__":
    unittest.main()
