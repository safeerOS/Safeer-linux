"""Prenos datotek v Linku po koscih: nadaljevanje po prekinitvi, brez meje 4 GB, cele mape (lastnik, 11. 10. 2026).

Zgled je bil Blip (posiljanje velikih datotek z nadaljevanjem); protokol je nas in ostaja zdruzljiv s starejsimi
napravami: posiljatelj vprasa s HEAD /cast/file, koliko sredisce ze ima (starejse odgovori 404 in oddaja gre od
zacetka kot prej); cilj prevzem nadaljuje z Range (starejse sredisce vrne 200 in prevzem gre od zacetka).
"""
import hashlib
import io
import os
import tempfile
import threading
import time
import unittest
from unittest import mock

from core import link_deljenje, link_hub, link_hub_deljenje, link_hub_streznik, link_krog, link_posiljanje, link_tls


class _Prekinjen(io.RawIOBase):
    """Tok, ki po `n` bajtih vrze napako (izpad Wi-Fi sredi oddaje)."""

    def __init__(self, podatki: bytes, n: int) -> None:
        self.p, self.n, self.i = podatki, n, 0

    def read(self, k=-1):
        if self.i >= self.n:
            raise ConnectionResetError("povezava prekinjena")
        kos = self.p[self.i:min(self.n, self.i + (k if k > 0 else len(self.p)))]
        self.i += len(kos)
        return kos


class Zaloga(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cas = [1000.0]
        self.z = link_hub_deljenje.Deljenje(mapa=lambda: os.path.join(self.tmp.name, "d"), ura=lambda: self.cas[0],
                                            prosto=lambda m: 10 * 1024 ** 4)
        self.vsebina = os.urandom(300_000)
        self.sha = hashlib.sha256(self.vsebina).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def _sprejmi(self, vhod, dolzina, odmik=0, sha=None):
        return self.z.sprejmi(vhod, dolzina, "film.mkv", "tv1", "pc1", self.sha if sha is None else sha,
                              skupaj=len(self.vsebina), odmik=odmik)

    def test_prekinjena_oddaja_se_nadaljuje(self):
        koda, odg, d = self._sprejmi(_Prekinjen(self.vsebina, 120_000), len(self.vsebina))
        self.assertEqual((koda, odg["koda"], odg["odmik"], d), (500, "prenos_prekinjen", 120_000, None))
        self.assertEqual(self.z.odmik("pc1", "tv1", self.sha, len(self.vsebina)), 120_000)
        self.assertEqual(self.z.odmik("pc2", "tv1", self.sha, len(self.vsebina)), 0, "tuj posiljatelj ne nadaljuje")
        koda, odg, d = self._sprejmi(io.BytesIO(self.vsebina[120_000:]), len(self.vsebina) - 120_000, odmik=120_000)
        self.assertEqual(koda, 200, odg)
        self.assertEqual(odg["sha256"], self.sha)
        with open(d.pot, "rb") as f:
            self.assertEqual(f.read(), self.vsebina)
        self.assertEqual(self.z.odmik("pc1", "tv1", self.sha, len(self.vsebina)), 0, "cela datoteka ni vec delna")

    def test_kratko_telo_in_napacen_odmik(self):
        koda, odg, _ = self._sprejmi(io.BytesIO(self.vsebina[:50_000]), len(self.vsebina))
        self.assertEqual((koda, odg["koda"], odg["odmik"]), (400, "ni_cela", 50_000))
        koda, odg, _ = self._sprejmi(io.BytesIO(self.vsebina[40_000:]), len(self.vsebina) - 40_000, odmik=40_000)
        self.assertEqual((koda, odg["koda"], odg["odmik"]), (409, "napacen_odmik", 50_000))
        # Nadaljevanje brez odtisa ni dovoljeno (sicer bi lahko kdo podtaknil drugo vsebino).
        koda, odg, _ = self._sprejmi(io.BytesIO(b"x"), len(self.vsebina) - 50_000, odmik=50_000, sha="")
        self.assertEqual(koda, 400)

    def test_nov_zacetek_zavrze_ostanek(self):
        self._sprejmi(io.BytesIO(self.vsebina[:50_000]), len(self.vsebina))
        koda, odg, d = self._sprejmi(io.BytesIO(self.vsebina), len(self.vsebina))
        self.assertEqual(koda, 200, odg)
        self.assertEqual(len(os.listdir(os.path.join(self.tmp.name, "d"))), 1, "stari ostanek je izbrisan")

    def test_napacen_odtis_na_koncu(self):
        self._sprejmi(io.BytesIO(self.vsebina[:50_000]), len(self.vsebina))
        drugo = bytearray(self.vsebina)
        drugo[-1] ^= 1
        koda, odg, _ = self._sprejmi(io.BytesIO(bytes(drugo[50_000:])), len(self.vsebina) - 50_000, odmik=50_000)
        self.assertEqual((koda, odg["koda"]), (400, "napacen_odtis"))
        self.assertEqual(os.listdir(os.path.join(self.tmp.name, "d")), [])

    def test_ostanek_po_eni_uri_izgine(self):
        self._sprejmi(io.BytesIO(self.vsebina[:50_000]), len(self.vsebina))
        self.cas[0] += link_hub_deljenje.DELNA_VELJA_S + 1
        self.z.pocisti()
        self.assertEqual(self.z.odmik("pc1", "tv1", self.sha, len(self.vsebina)), 0)
        self.assertEqual(os.listdir(os.path.join(self.tmp.name, "d")), [])

    def test_starejsi_posiljatelj_brez_ostanka(self):
        # Brez x-safeer-size (skupaj=None) je vse kot prej: okrnjena datoteka ne ostane.
        koda, odg, _ = self.z.sprejmi(io.BytesIO(self.vsebina[:50_000]), len(self.vsebina), "a.bin", "tv1", "pc1", self.sha)
        self.assertEqual((koda, odg["koda"]), (400, "ni_cela"))
        self.assertNotIn("odmik", odg)
        self.assertEqual(os.listdir(os.path.join(self.tmp.name, "d")), [])

    def test_brez_meje_4_gb(self):
        self.assertIsNone(self.z.preveri("velik.mkv", "tv1", 5 * 1024 ** 3), "5 GB gre, ce je prostor")
        self.assertEqual(self.z.preveri("velik.mkv", "tv1", link_hub_deljenje.NAJVECJA_DATOTEKA + 1)[0], 413)
        z = link_hub_deljenje.Deljenje(mapa=lambda: os.path.join(self.tmp.name, "e"), prosto=lambda m: 1024 ** 3)
        self.assertEqual(z.preveri("velik.mkv", "tv1", 5 * 1024 ** 3)[0], 507, "meja je prostor na disku")

    def test_mapa_v_tovoru(self):
        koda, _, d = self.z.sprejmi(io.BytesIO(b"abc"), 3, "a.txt", "tv1", "pc1", "", mapa="../Počitnice/./.skrito/2026")
        self.assertEqual(koda, 200)
        self.assertEqual(d.tovor()["dir"], "Počitnice/skrito/2026")
        _, _, d2 = self.z.sprejmi(io.BytesIO(b"abc"), 3, "b.txt", "tv1", "pc1", "")
        self.assertNotIn("dir", d2.tovor(), "brez mape ostane tovor kot prej")
        self.assertEqual(link_hub_deljenje.varna_mapa("/etc/../../x"), "etc/x")

    def test_obseg_prevzema(self):
        f = link_hub_streznik._Obravnava._zacetek_obsega
        self.assertEqual(f("bytes=100-", 1000), 100)
        for glava in ("", "bytes=0-", "bytes=100-200", "bytes=-100", "bytes=1000-", "items=5-", "bytes=1-2,5-"):
            self.assertEqual(f(glava, 1000), 0, glava)


class Posiljanje(unittest.TestCase):
    def test_cela_mapa_z_drevesom(self):
        with tempfile.TemporaryDirectory() as t:
            koren = os.path.join(t, "Počitnice")
            os.makedirs(os.path.join(koren, "Dan 1"))
            os.makedirs(os.path.join(koren, ".skrito"))
            for pot in ("a.jpg", "Dan 1/b.jpg", ".skrito/c.jpg", ".d.txt"):
                with open(os.path.join(koren, pot), "w") as f:
                    f.write("x")
            os.symlink("/etc/passwd", os.path.join(koren, "povezava"))
            klici = []
            p = link_posiljanje.Posiljanje(lambda n, pot, nap, mapa="": (klici.append((os.path.basename(pot), mapa)), (True, {}))[1])
            r = p.zacni("tv1", [koren])
            self.assertTrue(r["ok"], r)
            for _ in range(100):
                if p.stanje(r["id"])["stanje"] != "posiljam":
                    break
                time.sleep(0.02)
            self.assertEqual(p.stanje(r["id"])["stanje"], "poslano")
            self.assertEqual(sorted(klici), [("a.jpg", "Počitnice"), ("b.jpg", "Počitnice/Dan 1")])

    def test_brez_mape_klic_kot_prej(self):
        with tempfile.TemporaryDirectory() as t:
            pot = os.path.join(t, "a.txt")
            with open(pot, "w") as f:
                f.write("x")
            klici = []
            p = link_posiljanje.Posiljanje(lambda n, pot, nap: (klici.append(pot), (True, {}))[1])
            r = p.zacni("tv1", [pot])
            for _ in range(100):
                if p.stanje(r["id"])["stanje"] != "posiljam":
                    break
                time.sleep(0.02)
            self.assertEqual(p.stanje(r["id"])["stanje"], "poslano", "stari poslji brez argumenta mapa dela naprej")


class Prejemnik(unittest.TestCase):
    def test_podmapa_ne_more_ven(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(link_deljenje._ciljna_mapa(t, "../../etc"), os.path.join(t, "etc"))
            self.assertEqual(link_deljenje._ciljna_mapa(t, ""), t)
            self.assertTrue(os.path.isdir(os.path.join(t, "etc")))


class NadaljevanjeVZivo(unittest.TestCase):
    """Pravi Hub cez TLS: oddaja se prekine sredi poti in nadaljuje; prevzem se nadaljuje z Range."""

    A, B = "n-aaaaaaaaaaaaaaaa", "n-bbbbbbbbbbbbbbbb"

    @classmethod
    def setUpClass(cls):
        cls.streznik = link_hub_streznik.HubStreznik()
        if not cls.streznik.zazeni():
            raise unittest.SkipTest("huba ni bilo mogoce zagnati")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.streznik.hub.deljenje = link_hub_deljenje.Deljenje(mapa=lambda: os.path.join(cls.tmp.name, "zaloga"))
        cls.naslov = "wss://127.0.0.1:%d%s" % (cls.streznik.vrata, link_hub_streznik.POT_WS)
        cls.odtis = cls.streznik.odtis
        cls.clan = {"kljuc": link_krog.javni_kljuc_b64(), "ime": "Preizkus", "platforma": "linux"}

    @classmethod
    def tearDownClass(cls):
        cls.streznik.ustavi()
        cls.tmp.cleanup()

    def test_oddaja_in_prevzem_po_prekinitvi(self):
        lazni = mock.MagicMock()
        lazni.clan_za_id.return_value = self.clan
        lazni.json.return_value = {"v": 1, "clani": {}, "umiki": {}}
        with mock.patch.object(link_krog, "krog", return_value=lazni), \
                mock.patch.object(link_krog, "lahko_s_podpisom", return_value=True), \
                mock.patch.object(link_krog, "sprejmi", return_value=True):
            seja = link_hub.seja_s_podpisom(self.naslov, self.A, self.odtis, "Racunalnik")
            datoteke, prisla = [], threading.Event()
            p = link_hub.Povezava(self.naslov, "", self.B, "Tablica", odtis=self.odtis)
            p.v_krog = True
            p.ob_sporocilu = lambda s: (datoteke.append(s), prisla.set()) if s.get("type") == "share.file" else None
            self.assertTrue(p.poveži())
            try:
                time.sleep(0.5)
                vsebina = os.urandom(3 * 1024 * 1024)
                pot = os.path.join(self.tmp.name, "film.bin")
                with open(pot, "wb") as f:
                    f.write(vsebina)
                # Prvi PUT se prekine po ~1 MB (izpad Wi-Fi); drugi poskus vprasa HEAD in poslje le ostanek.
                izvirni = link_tls._PripetaHttps.send
                stanje = {"put": 0, "poslano": [0, 0, 0, 0, 0, 0]}
                delne = self.streznik.hub.deljenje._delne

                def send(self_, podatki):
                    if isinstance(podatki, (bytes, bytearray, memoryview)) and len(podatki) == link_deljenje.KOS:
                        i = stanje["put"]
                        if i == 0 and stanje["poslano"][0] + len(podatki) > 1024 * 1024:
                            # Izpad sele, ko je sredisce prebralo vse poslano: zaprt vtic poslje RST, ki zavrze, kar
                            # je se v medpomnilnikih jedra - koliko je nit sredisca prej prebrala, je bilo tekma
                            # (na obremenjenem stroju z 2 jedroma 18. 10. 2026 en sam kos, preizkus je padel).
                            konec = time.monotonic() + 10
                            while time.monotonic() < konec and not any(
                                    d.prejeto >= stanje["poslano"][0] for d in list(delne.values())):
                                time.sleep(0.01)
                            self_.sock.close()
                            raise ConnectionResetError("Wi-Fi je padel")
                        stanje["poslano"][i] += len(podatki)
                    return izvirni(self_, podatki)

                spanje = []
                stari_oddaja = link_deljenje._oddaja

                def oddaja(*a, **k):
                    try:
                        return stari_oddaja(*a, **k)
                    finally:
                        stanje["put"] += 1

                with mock.patch.object(link_tls._PripetaHttps, "send", send), \
                        mock.patch.object(link_deljenje, "_oddaja", oddaja):
                    ok, n = link_deljenje.poslji_datoteko(self.naslov, seja, self.odtis, self.A, self.B, pot,
                                                          mapa="Filmi/2026", spi=spanje.append)
                self.assertTrue(ok, n)
                self.assertEqual(stanje["put"], 2, "en prekinjen in en nadaljevan PUT")
                self.assertEqual(len(spanje), 1)
                # Sredisce je imelo vse, kar je prislo pred izpadom (~1 MB): drugi poskus poslje natanko ostanek.
                self.assertGreaterEqual(stanje["poslano"][0], 1024 * 1024 - link_deljenje.KOS)
                self.assertEqual(stanje["poslano"][1], len(vsebina) - stanje["poslano"][0],
                                 "drugi poskus poslje le ostanek, ne vse znova")
                self.assertTrue(prisla.wait(5))
                tovor = datoteke[-1]["payload"]
                self.assertEqual((tovor["size"], tovor["sha256"], tovor["dir"]),
                                 (len(vsebina), hashlib.sha256(vsebina).hexdigest(), "Filmi/2026"))

                # Prejemnik ima ze pol datoteke (prejsnji poskus): nadaljuje in dobi celo, v podmapi.
                mapa = os.path.join(self.tmp.name, "prejeto")
                os.makedirs(os.path.join(mapa, "Filmi", "2026"))
                with open(os.path.join(mapa, "Filmi", "2026", "film.bin.safeer-delno"), "wb") as f:
                    f.write(vsebina[:1_500_000])
                obsegi = []
                izvirni_obseg = link_hub_streznik._Obravnava._zacetek_obsega

                def obseg(glava, velikost):
                    obsegi.append(izvirni_obseg(glava, velikost))
                    return obsegi[-1]

                with mock.patch.object(link_deljenje, "enolicna_pot", lambda m, i: os.path.join(m, i)), \
                        mock.patch.object(link_hub_streznik._Obravnava, "_zacetek_obsega", staticmethod(obseg)):
                    cilj, razlog = link_deljenje.prevzemi_datoteko(self.naslov, self.odtis, tovor["path"], tovor["name"],
                                                                   tovor["sha256"], mapa=mapa, podmapa=tovor["dir"])
                self.assertTrue(cilj, razlog)
                self.assertEqual(cilj, os.path.join(mapa, "Filmi", "2026", "film.bin"))
                with open(cilj, "rb") as f:
                    self.assertEqual(f.read(), vsebina)
                self.assertFalse(os.path.exists(cilj + ".safeer-delno"))
                self.assertEqual(obsegi, [1_500_000], "sredisce je poslalo le ostanek (206)")
            finally:
                p.zapri()


if __name__ == "__main__":
    unittest.main()
