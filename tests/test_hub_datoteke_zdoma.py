"""Global Link pripelje samo do vrat Huba. Kar streznik datotek da doma (datoteka, slicica, urejanje, tokovi), mora
Hub dati pod /cast z istim zetonom in istimi pravili - zdoma mora delovati enako kot doma."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_datoteke, link_hub_streznik, link_tls  # noqa: E402
from dostop_za_preizkus import setUpModule, tearDownModule  # noqa: E402,F401 - naprave v teh preizkusih so v ozjem krogu

try:
    from PIL import Image
except Exception:  # noqa: BLE001 - brez Pillow se preizkusi slicic preskocijo
    Image = None


class PrekHubaKotDoma(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapa = tempfile.mkdtemp(prefix="safeer-zdoma-")
        cls.deljena = os.path.join(cls.mapa, "Slike")
        os.makedirs(os.path.join(cls.deljena, "Podmapa"))
        with open(os.path.join(cls.deljena, "zapis.txt"), "w", encoding="utf-8") as d:
            d.write("besedilo")
        if Image is not None:
            Image.new("RGB", (1600, 1200), (200, 40, 40)).save(os.path.join(cls.deljena, "slika.jpg"), quality=90)
        cls.tls = os.path.join(cls.mapa, "tls")
        cls.dat = link_datoteke.Datoteke([cls.deljena], tls_mapa=cls.tls)
        cls.dat.streznik.zazeni()
        cls.zeton = cls.dat.streznik.zeton_za("n-tv")
        # Hub z istim potrdilom kot streznik datotek (tako je v Controlu).
        cls.hub = link_hub_streznik.HubStreznik(tls_mapa=cls.tls)
        cls.hub._ze_gosti_lokalno = staticmethod(lambda: False)
        cls.hub.datoteke = cls.dat.streznik
        with mock.patch.object(link_hub_streznik, "PRIVZETA_VRATA", 0):
            assert cls.hub.zazeni()

    @classmethod
    def tearDownClass(cls):
        cls.hub.ustavi()
        cls.dat.ustavi()
        shutil.rmtree(cls.mapa, ignore_errors=True)

    def _zahteva(self, vrata, odtis, metoda, pot, telo=None, zeton=""):
        povezava = link_tls._PripetaHttps("127.0.0.1", vrata, odtis, 10.0)
        try:
            glave = {"X-Safeer-Token": zeton} if zeton else {}
            surovo = None
            if telo is not None:
                surovo = json.dumps(telo).encode("utf-8")
                glave["Content-Type"] = "application/json"
            povezava.request(metoda, pot, body=surovo, headers=glave)
            o = povezava.getresponse()
            return o.status, {k.lower(): v for k, v in o.getheaders()}, o.read()
        finally:
            povezava.close()

    def doma(self, metoda, pot, telo=None, zeton=None):
        s = self.dat.streznik
        return self._zahteva(s.vrata, s.odtis, metoda, pot, telo, self.zeton if zeton is None else zeton)

    def zdoma(self, metoda, pot, telo=None, zeton=None):
        return self._zahteva(self.hub.vrata, self.hub.odtis, metoda, "/cast" + pot, telo,
                             self.zeton if zeton is None else zeton)

    # ------------------------------------------------------------------ seznam
    def test_seznam_pove_cas_spremembe_in_pot_prek_huba(self):
        o = self.dat.seznam("share:0:", "n-tv")
        po_imenu = {v["name"]: v for v in o["items"]}
        self.assertIn("zapis.txt", po_imenu)
        for v in o["items"]:
            self.assertIsInstance(v.get("modified"), int, v["name"])
        self.assertAlmostEqual(po_imenu["zapis.txt"]["modified"],
                               os.path.getmtime(os.path.join(self.deljena, "zapis.txt")), delta=2)
        self.assertGreater(po_imenu["Podmapa"]["modified"], 0)
        # Naprava po tem polju ve, da sme zdoma tudi urejati (starejsi Control ga nima).
        self.assertEqual(o["server"]["hub"], 2)

    # ------------------------------------------------------------------ datoteka
    def test_datoteka_je_ista_po_obeh_poteh(self):
        a = self.doma("GET", "/d/share:0:zapis.txt")
        b = self.zdoma("GET", "/d/share:0:zapis.txt")
        self.assertEqual((a[0], a[2]), (200, b"besedilo"))
        self.assertEqual((b[0], b[2]), (200, b"besedilo"))

    # ------------------------------------------------------------------ slicice
    @unittest.skipIf(Image is None, "brez Pillow")
    def test_slicica_slike_je_ista_po_obeh_poteh(self):
        a = self.doma("GET", "/thumb/share:0:slika.jpg")
        b = self.zdoma("GET", "/thumb/share:0:slika.jpg")
        for koda, glave, telo in (a, b):
            self.assertEqual(koda, 200)
            self.assertEqual(glave.get("content-type"), "image/jpeg")
            with Image.open(io.BytesIO(telo)) as im:
                self.assertEqual(im.format, "JPEG")
                self.assertEqual(max(im.size), link_datoteke.SLICICA_ROB)
                self.assertEqual(im.size, (512, 384))          # razmerje 4:3 ostane
        self.assertEqual(a[2], b[2])

    @unittest.skipIf(Image is None, "brez Pillow")
    def test_slicica_glava_brez_telesa(self):
        koda, glave, telo = self.zdoma("HEAD", "/thumb/share:0:slika.jpg")
        self.assertEqual((koda, telo), (200, b""))
        self.assertGreater(int(glave.get("content-length", "0")), 200)

    def test_slicica_brez_zetona_ali_brez_slike(self):
        for klic in (self.doma, self.zdoma):
            self.assertEqual(klic("GET", "/thumb/share:0:slika.jpg", zeton="napacen")[0], 401)
            self.assertEqual(klic("GET", "/thumb/share:0:zapis.txt")[0], 404)        # besedilo nima slicice
            self.assertEqual(klic("GET", "/thumb/share:0:ni-je.jpg")[0], 404)
            self.assertEqual(klic("GET", "/thumb/share:0:../../etc/passwd")[0], 404)

    @unittest.skipIf(Image is None, "brez Pillow")
    def test_slicica_se_naredi_enkrat(self):
        pot = os.path.join(self.deljena, "slika.jpg")
        with mock.patch.object(link_datoteke, "_slicica_slike", wraps=link_datoteke._slicica_slike) as delo:
            with link_datoteke._slicice_kljuc:
                link_datoteke._slicice.clear()
            prva = link_datoteke.naredi_slicico(pot)
            druga = link_datoteke.naredi_slicico(pot)
        self.assertTrue(prva)
        self.assertEqual(prva, druga)
        self.assertEqual(delo.call_count, 1)

    # ------------------------------------------------------------------ urejanje
    def test_urejanje_prek_huba_kot_doma(self):
        for i, klic in enumerate((self.doma, self.zdoma)):
            ime = "za-preimenovanje-%d.txt" % i
            with open(os.path.join(self.deljena, ime), "w", encoding="utf-8") as d:
                d.write("x")
            koda, _g, telo = klic("POST", "/d/share:0:" + ime, {"op": "rename", "name": "novo-%d.txt" % i})
            odgovor = json.loads(telo)
            self.assertEqual((koda, odgovor.get("ok"), odgovor.get("name")), (200, True, "novo-%d.txt" % i), telo)
            self.assertEqual(odgovor.get("id"), "share:0:novo-%d.txt" % i)
            self.assertFalse(os.path.exists(os.path.join(self.deljena, ime)))
            self.assertTrue(os.path.exists(os.path.join(self.deljena, "novo-%d.txt" % i)))
            # Premik v podmapo po isti poti.
            koda, _g, telo = klic("POST", "/d/share:0:novo-%d.txt" % i, {"op": "move", "folder": "share:0:Podmapa"})
            self.assertEqual((koda, json.loads(telo).get("ok")), (200, True), telo)
            self.assertTrue(os.path.exists(os.path.join(self.deljena, "Podmapa", "novo-%d.txt" % i)))

    def test_urejanje_ista_pravila_po_obeh_poteh(self):
        for klic in (self.doma, self.zdoma):
            self.assertEqual(klic("POST", "/d/share:0:zapis.txt", {"op": "rename", "name": "x.txt"}, zeton="napacen")[0], 401)
            koda, _g, telo = klic("POST", "/d/share:0:zapis.txt", {"op": "format"})
            self.assertEqual((koda, json.loads(telo).get("napaka")), (400, "neznan_ukaz"))
            koda, _g, telo = klic("POST", "/d/share:0:ni-je.txt", {"op": "delete"})
            self.assertEqual((koda, json.loads(telo).get("napaka")), (404, "ni_datoteke"))
            # Deljene mape same naprava ne preimenuje in ne brise.
            koda, _g, telo = klic("POST", "/d/share:0:", {"op": "rename", "name": "Drugo"})
            self.assertEqual((koda, json.loads(telo).get("napaka")), (403, "ni_dovoljeno"))
        self.assertTrue(os.path.exists(os.path.join(self.deljena, "zapis.txt")))

    def test_urejanje_prek_huba_samo_za_datoteke(self):
        # POST na druge poti streznika datotek prek Huba ni urejanje: slicice in tokovi se samo berejo.
        self.assertIn(self.zdoma("POST", "/thumb/share:0:slika.jpg", {"op": "delete"})[0], (404, 405))
        self.assertIn(self.zdoma("POST", "/m/skrivnost/film.mkv", {"op": "delete"})[0], (404, 405))

    # ------------------------------------------------------------------ tokovi
    def test_tok_torrenta_in_sprotni_tok_prideta_do_streznika(self):
        # Neznana skrivnost oziroma tok: odgovori streznik datotek (z zetonom 404), ne Hub z »ni te poti«.
        for klic in (self.doma, self.zdoma):
            self.assertEqual(klic("GET", "/m/neznana-skrivnost/film.mkv")[0], 404)
            self.assertEqual(klic("GET", "/m/neznana-skrivnost/film.mkv", zeton="napacen")[0], 401)
            self.assertEqual(klic("GET", "/live/neznan-tok/index.m3u8", zeton="napacen")[0], 401)
            self.assertEqual(klic("GET", "/live/neznan-tok/index.m3u8")[0], 404)

    def test_hub_brez_datotek(self):
        self.hub.datoteke = None
        try:
            self.assertEqual(self.zdoma("GET", "/thumb/share:0:slika.jpg")[0], 404)
            self.assertEqual(self.zdoma("POST", "/d/share:0:zapis.txt", {"op": "delete"})[0], 404)
        finally:
            self.hub.datoteke = self.dat.streznik
        self.assertTrue(os.path.exists(os.path.join(self.deljena, "zapis.txt")))


if __name__ == "__main__":
    unittest.main()
