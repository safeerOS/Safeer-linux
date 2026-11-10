"""Viri tokov dodatkov Stremio (lastnik 5. 11. 2026): zdruzeni dvojniki torrentov, razvrstitev po sejalcih in zdravje
dodatkov. Ciste funkcije v core/tok_izbira.py in core/media_servers.py (skupna koda z Windows), uporaba v
core/os_media.MediaCenter._stremio_tokovi_vseh. Brez interneta."""
import tempfile
import time
import unittest
from unittest import mock

from core import media_servers, os_media, skrivni_dodatki, tok_izbira

H = "a" * 40
Z = tok_izbira.Zmoznosti(visina=2160)


def _torrent(hash_=H, indeks=0, opis="", sledilniki=(), ime="", vir="Dodatek"):
    return {"url": "", "torrent": True, "hash": hash_, "indeks": indeks, "ime": ime, "sledilniki": list(sledilniki),
            "vir": vir, "kakovost": "", "opis": opis}


class Brez3dTests(unittest.TestCase):
    """Lastnik 10. 11. 2026: 3D izdaje ne prikazemo (film je bil v dveh polovicah slike)."""

    def test_oznake_3d(self):
        for b in ("Film.1998.1080p.3D.HSBS.BluRay.x264", "Film 1998 3D 1080p", "Film.1998.Half-SBS.1080p", "Film (1998) [3D] [H-SBS]",
                  "Film.1998.1080p.BluRay.SBS.x264", "Film.1998.3D.Half-OU.1080p", "RD+ 1080p\nFilm.1998.3D.mkv", "Film 3D",
                  "Jackass.3D.2010.1080p.3D.HSBS"):
            self.assertTrue(tok_izbira.je_3d(b), b)

    def test_naslov_s_3d_in_podobne_besede_niso_3d(self):
        for b in ("Film.1998.1080p.BluRay.x264", "Jackass.3D.2010.1080p.BluRay", "Step Up 3D (2010) 720p",
                  "Film.1998.1080p.x264-SBSGROUP", "R3D.2011.1080p", "Thou.Shalt.Not.1998.720p", "", None):
            self.assertFalse(tok_izbira.je_3d(b), b)

    def test_zdruzi_dvojnike_ne_vrne_3d(self):
        t3d = _torrent(hash_="b" * 40, opis="Film.1998.1080p.3D.HSBS 👤 900")
        rd3d = {"url": "https://x.test/3d.mkv", "opis": "RD+ 1080p", "ime": "Film.1998.Half-SBS.mkv"}
        navaden = _torrent(hash_="c" * 40, opis="Film.1998.720p 👤 5")
        self.assertEqual([t.get("hash") for t in tok_izbira.zdruzi_dvojnike([t3d, rd3d, navaden])], ["c" * 40])


class ZdruziDvojnikeTests(unittest.TestCase):
    def test_isti_hash_in_indeks_en_vnos(self):
        a = _torrent(opis="Torrentio 1080p", sledilniki=["udp://a:1", "udp://b:2"], vir="A")
        b = _torrent(opis="Komet 1080p x265 DDP 5.1 💾 2.1 GB 👤 57", sledilniki=["udp://B:2 ", "udp://c:3"],
                     ime="Film.2020.1080p.mkv", vir="B")
        neposredni = {"url": "https://x.test/f.mkv", "opis": "1080p"}
        izid = tok_izbira.zdruzi_dvojnike([neposredni, a, b])
        self.assertEqual(len(izid), 2)
        self.assertIs(izid[0], neposredni)                     # mesto prvega ostane
        t = izid[1]
        self.assertEqual(t["vir"], "B")                        # najbolj opisan tok
        self.assertEqual(t["sledilniki"], ["udp://B:2", "udp://c:3", "udp://a:1"])   # brez dvojnikov (velikost crk)
        self.assertEqual(t["sejalci"], 57)
        self.assertNotIn("sejalci", a)                         # vhod ostane nespremenjen

    def test_najvec_sejalcev_in_ime_iz_drugega(self):
        a = _torrent(opis="2160p HDR HEVC DTS 💾 20 GB 👤 4", ime="")
        b = _torrent(opis="2160p 👤 120", ime="Film.mkv")
        t = tok_izbira.zdruzi_dvojnike([a, b])[0]
        self.assertEqual(t["opis"], a["opis"])
        self.assertEqual(t["sejalci"], 120)
        self.assertEqual(t["ime"], "Film.mkv")

    def test_sledilniki_najvec_30(self):
        a = _torrent(sledilniki=["udp://a%d:1" % i for i in range(20)])
        b = _torrent(sledilniki=["udp://b%d:1" % i for i in range(20)])
        self.assertEqual(len(tok_izbira.zdruzi_dvojnike([a, b])[0]["sledilniki"]), tok_izbira.NAJVEC_SLEDILNIKOV)

    def test_drug_indeks_in_neposredni_ostanejo(self):
        a, b = _torrent(indeks=0), _torrent(indeks=1)
        rd1 = {"url": "https://rd.test/1", "hash": H, "opis": "[RD+] 1080p"}
        rd2 = {"url": "https://ad.test/1", "hash": H, "opis": "[AD+] 1080p"}
        self.assertEqual(len(tok_izbira.zdruzi_dvojnike([a, b, rd1, rd2])), 4)

    def test_brez_znanih_sejalcev_ni_polja(self):
        self.assertNotIn("sejalci", tok_izbira.zdruzi_dvojnike([_torrent(), _torrent()])[0])


class SejalciTests(unittest.TestCase):
    opis = staticmethod(lambda t: t["opis"])

    def test_nic_sejalcev_na_konec_ne_skrito(self):
        tokovi = [{"opis": "2160p HEVC English 👤 0"}, {"opis": "480p"}, {"opis": "720p Italian 👤 40"}]
        izid = tok_izbira.uredi(tokovi, self.opis, Z, zelen_jezik="en")
        self.assertEqual(len(izid), 3)
        self.assertEqual(izid[-1]["opis"], "2160p HEVC English 👤 0")

    def test_malo_sejalcev_za_tokovi_z_vec(self):
        tokovi = [{"opis": "2160p English 👤 2"}, {"opis": "720p 👤 3"}, {"opis": "1080p English 👤 1"}]
        izid = [t["opis"] for t in tok_izbira.uredi(tokovi, self.opis, Z, zelen_jezik="en")]
        self.assertEqual(izid, ["720p 👤 3", "2160p English 👤 2", "1080p English 👤 1"])

    def test_neznano_nevtralno(self):
        tokovi = [{"opis": "720p 👤 500"}, {"opis": "1080p"}]
        self.assertEqual(tok_izbira.uredi(tokovi, self.opis, Z)[0]["opis"], "1080p")

    def test_zdruzeni_sejalci_stejejo(self):
        # Opis najbolj opisanega pravi 0, drug dodatek je za isti torrent videl 80: tok ni na koncu.
        tokovi = [{"opis": "1080p HEVC DDP 💾 2 GB 👤 0", "sejalci": 80}, {"opis": "720p"}]
        self.assertEqual(tok_izbira.uredi(tokovi, self.opis, Z)[0]["sejalci"], 80)

    def test_neposreden_tok_ni_roj(self):
        # Debrid povezava z opisom izvirnega torrenta (0 sejalcev): pripravljen 2160p ostane pred 480p.
        tokovi = [{"url": "https://d.test/480", "opis": "480p 👤 50"},
                  {"url": "https://d.test/2160", "opis": "2160p HEVC 👤 0"}]
        self.assertEqual(tok_izbira.uredi(tokovi, self.opis, Z)[0]["url"], "https://d.test/2160")
        self.assertEqual(tok_izbira.sejalci_toka(tokovi[1], tokovi[1]["opis"]), -1)
        # Torrent (brez url) z 0 sejalci ostane na koncu.
        self.assertEqual(tok_izbira.sejalci_toka({"url": "", "torrent": True}, "👤 0"), 0)
        # Webtor prenasa iz roja: sejalci ostanejo.
        self.assertEqual(tok_izbira.sejalci_toka({"url": "https://w.test/r", "webtor": "prenos"}, "👤 0"), 0)


class ZdravjeTests(unittest.TestCase):
    def setUp(self):
        self.cas = [1000.0]
        self.z = media_servers.ZdravjeDodatkov(ura=lambda: self.cas[0])

    def test_tri_zaporedni_neuspehi_kazen_10_min(self):
        for _ in range(2):
            self.z.neuspeh("k")
        self.assertFalse(self.z.zadrzan("k"))
        self.z.neuspeh("k")
        self.assertTrue(self.z.zadrzan("k"))
        self.cas[0] += 599
        self.assertTrue(self.z.zadrzan("k"))
        self.cas[0] += 2
        self.assertFalse(self.z.zadrzan("k"))                  # po kazni ena poskusna zahteva

    def test_podaljsevanje_do_ure(self):
        kazni = []
        for _ in range(8):
            self.z.neuspeh("k")
            kazni.append(self.z._stanje["k"][1] - self.cas[0])
        self.assertEqual(kazni[2:], [600, 1200, 2400, 3600, 3600, 3600])
        for _ in range(3000):                                  # dolgo pokvarjen dodatek brez kljuca: brez preliva
            self.z.neuspeh("k")
        self.assertEqual(self.z._stanje["k"][1] - self.cas[0], 3600)

    def test_uspeh_ponastavi(self):
        for _ in range(3):
            self.z.neuspeh("k")
        self.z.uspeh("k")
        self.assertFalse(self.z.zadrzan("k"))
        self.assertEqual(self.z.zaporedni("k"), 0)
        self.z.neuspeh("k")
        self.assertFalse(self.z.zadrzan("k"))

    def test_dodatek_s_kljucem(self):
        # Izmisljen kljuc (ni pravi): Torrentio z debrid kljucem v nastavitvah naslova.
        self.assertTrue(media_servers.stremio_dodatek_s_kljucem(
            "https://torrentio.strem.fun/realdebrid=" + "Q" * 52 + "|sort=qualitysize"))
        self.assertFalse(media_servers.stremio_dodatek_s_kljucem("https://torrentio.strem.fun"))

    def test_preskoci_samo_s_kljucem(self):
        for _ in range(3):
            self.z.neuspeh("k")
        self.assertTrue(self.z.preskoci("k", True))
        self.assertFalse(self.z.preskoci("k", False))
        self.assertFalse(self.z.preskoci("drug", True))


class PrazenOdgovorTests(unittest.TestCase):
    def test_prazno_telo_ni_odgovor_tega_nimam(self):
        for telo in (b"", b"  ", b"{}", b"[]", b"<html>"):
            with mock.patch.object(media_servers, "_request", lambda *a, **k: telo):
                with self.assertRaises(media_servers.PrazenOdgovor):
                    media_servers.stremio_tokovi("https://d.test", "movie", "tt0000001")
        with mock.patch.object(media_servers, "_request", lambda *a, **k: b'{"streams": []}'):
            self.assertEqual(media_servers.stremio_tokovi("https://d.test", "movie", "tt0000001"), [])

    def test_streams_ni_seznam_je_okvara(self):
        # null/false/{}/niz ni "tega nimam" (prej `or []` = uspeh pokvarjenega dodatka).
        for telo in (b'{"streams": null}', b'{"streams": false}', b'{"streams": {}}', b'{"streams": "x"}', b'{"streams": 0}'):
            with mock.patch.object(media_servers, "_request", lambda *a, t=telo, **k: t):
                with self.assertRaises(media_servers.PrazenOdgovor, msg=telo):
                    media_servers.stremio_tokovi("https://d.test", "movie", "tt0000001")


class VsiDodatkiTests(unittest.TestCase):
    """MediaCenter._stremio_tokovi_vseh: dvojniki, preskok dodatka s kljucem v kazni, dodatek v kazni ne zadrzi."""

    def setUp(self):
        mapa = tempfile.TemporaryDirectory()
        self.addCleanup(mapa.cleanup)
        self.mc = os_media.MediaCenter(mapa.name, roots=[], secret_decryptor=lambda s: s)
        self.mc.zasebno = True
        self.klici: list = []
        self.odgovori: dict = {}
        self.kljuc: set = set()
        dodatki = ["https://a.test", "https://b.test", "https://c.test"]
        zakrpe = [
            mock.patch.object(self.mc, "_stremio_strezniki",
                              lambda: [{"url": k + "/manifest.json", "ime": k[8:9]} for k in dodatki]),
            mock.patch.object(media_servers, "stremio_tokovi", self._tokovi),
            mock.patch.object(skrivni_dodatki, "je_nadomestek", lambda k: k in self.kljuc),
            # Windows nima rezerve Webtor (create=True): ista datoteka preizkusa v obeh repozitorijih.
            mock.patch.object(self.mc, "_oznaci_webtor", lambda k, t: t, create=True),
        ]
        for z in zakrpe:
            z.start()
            self.addCleanup(z.stop)

    def _tokovi(self, koren, tip, ident):
        self.klici.append(koren)
        o = self.odgovori.get(koren, [])
        if callable(o):
            return o()
        return [dict(t) for t in o]

    def _vsi(self):
        return self.mc._stremio_tokovi_vseh("https://a.test", "movie", "tt0000001")

    def test_dvojniki_iz_razlicnih_dodatkov(self):
        self.odgovori = {"https://a.test": [_torrent(opis="1080p 👤 5", sledilniki=["udp://a:1"])],
                         "https://b.test": [_torrent(opis="1080p x265 💾 2 GB 👤 90", sledilniki=["udp://b:1"])],
                         "https://c.test": [_torrent(hash_="b" * 40, opis="720p")]}
        izid = self._vsi()
        self.assertEqual(len(izid), 2)
        self.assertEqual(izid[0]["sejalci"], 90)
        self.assertEqual(sorted(izid[0]["sledilniki"]), ["udp://a:1", "udp://b:1"])

    def _pokvarjen(self):
        raise media_servers.PrazenOdgovor("x")

    def test_dodatek_s_kljucem_v_kazni_preskocen(self):
        self.kljuc = {"https://b.test"}
        self.odgovori = {"https://a.test": [{"url": "https://x.test/f.mkv", "opis": "1080p"}],
                         "https://b.test": self._pokvarjen}
        for _ in range(3):
            self._vsi()
        self.assertEqual(self.klici.count("https://b.test"), 3)
        self._vsi()
        self.assertEqual(self.klici.count("https://b.test"), 3)       # cetrtic ga ne vprasamo (zaklep racuna)
        self.assertFalse(self.mc._tokovi_odgovor.vsi)                 # preskok ni »tega ni«
        self.mc._zdravje_dodatkov()._stanje["https://b.test"] = (3, 0.0)   # kazen je potekla
        self.odgovori["https://b.test"] = []
        self._vsi()
        self.assertEqual(self.klici.count("https://b.test"), 4)
        self.assertEqual(self.mc._zdravje_dodatkov().zaporedni("https://b.test"), 0)   # uspeh ponastavi

    def test_dodatek_brez_kljuca_v_kazni_vprasan_a_ne_zadrzi(self):
        self.mc.TOKOVI_ROK_S = 3.0
        self.odgovori = {"https://a.test": [{"url": "https://x.test/f.mkv", "opis": "1080p"}],
                         "https://c.test": self._pokvarjen}
        for _ in range(3):
            self._vsi()

        def pocasen():
            time.sleep(1.5)
            return [{"url": "https://c.test/f.mkv", "opis": "720p"}]
        self.odgovori["https://c.test"] = pocasen
        zacetek = time.monotonic()
        izid = self._vsi()
        self.assertLess(time.monotonic() - zacetek, 1.0)              # brez zdravja bi cakali 1,5 s
        self.assertEqual([t["url"] for t in izid], ["https://x.test/f.mkv"])
        self.assertEqual(self.klici.count("https://c.test"), 4)       # brez kljuca ga vseeno vprasamo
        konec = time.monotonic() + 3
        while self.mc._zdravje_dodatkov().zaporedni("https://c.test") and time.monotonic() < konec:
            time.sleep(0.05)
        self.assertEqual(self.mc._zdravje_dodatkov().zaporedni("https://c.test"), 0)   # pozni uspeh ponastavi


if __name__ == "__main__":
    unittest.main()
