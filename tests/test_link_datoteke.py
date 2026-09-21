"""Deljene mape Safeer Controla za televizor (core/link_datoteke.py): oznake, varnost poti, streznik z obsegi."""
import hashlib
import http.client
import os
import shutil
import ssl
import sys
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec, link_datoteke  # noqa: E402


class Mape(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-datoteke-")
        self.deljena = os.path.join(self.mapa, "Filmi")
        os.makedirs(os.path.join(self.deljena, "Serije"))
        with open(os.path.join(self.deljena, "film.mp4"), "wb") as d:
            d.write(b"x" * 1000)
        with open(os.path.join(self.deljena, "glasba.mp3"), "wb") as d:
            d.write(b"y" * 10)
        with open(os.path.join(self.deljena, ".skrita.mp4"), "wb") as d:
            d.write(b"z")
        with open(os.path.join(self.deljena, "Serije", "e01.mkv"), "wb") as d:
            d.write(b"e" * 5)
        # simbolna povezava ven iz deljene mape se ne sme videti
        with open(os.path.join(self.mapa, "skrivnost.txt"), "w") as d:
            d.write("ne")
        os.symlink(os.path.join(self.mapa, "skrivnost.txt"), os.path.join(self.deljena, "povezava.txt"))
        self.m = link_datoteke.DeljeneMape([self.deljena, "/ne/obstaja", self.deljena])

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_koren_in_vrste(self):
        self.assertEqual(len(self.m.poti), 1)  # neobstojece in podvojene odpadejo
        koren = self.m.seznam("")
        self.assertEqual(koren, [{"id": "share:0:", "name": "Filmi", "type": "folder"}])
        vnosi = self.m.seznam("share:0:")
        imena = [v["name"] for v in vnosi]
        self.assertEqual(imena, ["Serije", "film.mp4", "glasba.mp3"])  # mape najprej, skrite in tuje povezave ne
        self.assertEqual(vnosi[1]["type"], "video")
        self.assertEqual(vnosi[1]["size"], 1000)
        self.assertEqual(vnosi[1]["mime"], "video/mp4")
        self.assertEqual(vnosi[2]["type"], "audio")
        self.assertEqual(vnosi[0]["id"], "share:0:Serije")
        self.assertEqual([v["name"] for v in self.m.seznam("share:0:Serije")], ["e01.mkv"])

    def test_poti_ven_ne_gredo(self):
        for oznaka in ("share:0:../skrivnost.txt", "share:0:/../skrivnost.txt", "share:1:", "share:x:", "nekaj",
                       "share:0:povezava.txt", "share:0:.skrita.mp4"):
            r = self.m.razresi(oznaka)
            self.assertTrue(r is None or r[1].startswith(self.deljena + os.sep) and "skrivnost" not in r[1]
                            or oznaka == "share:0:.skrita.mp4", oznaka)
        self.assertIsNone(self.m.razresi("share:0:../skrivnost.txt"))
        self.assertIsNone(self.m.razresi("share:0:povezava.txt"))
        self.assertIsNone(self.m.razresi("share:0:.skrita.mp4"))  # skrite datoteke tudi po imenu ne
        self.assertIsNone(self.m.seznam("share:0:film.mp4"))  # datoteka ni mapa
        self.assertEqual(link_datoteke.vrsta_datoteke("A.JPG"), "image")
        self.assertEqual(link_datoteke.vrsta_datoteke("x.pdf"), "file")


class CelDisk(unittest.TestCase):
    """Tudi "cel disk za TV" ne da skritih map (.ssh, .gnupg, piskotki), ceprav naprava pot ugane."""

    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-disk-")
        os.makedirs(os.path.join(self.mapa, ".ssh"))
        os.makedirs(os.path.join(self.mapa, "Slike"))
        for pot in (".ssh/id_ed25519", "Slike/a.jpg", ".bashrc"):
            with open(os.path.join(self.mapa, pot), "w") as d:
                d.write("x")
        os.symlink(os.path.join(self.mapa, ".ssh"), os.path.join(self.mapa, "Slike", "kljuci"))
        self.m = link_datoteke.DeljeneMape([], ves_disk=True)

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_skrite_poti_niso_dosegljive(self):
        for rel in (".ssh/id_ed25519", ".ssh", ".bashrc", "Slike/kljuci/id_ed25519", "Slike/../.ssh/id_ed25519"):
            self.assertIsNone(self.m.razresi("disk:" + os.path.join(self.mapa, rel)), rel)
        self.assertIsNotNone(self.m.razresi("disk:" + os.path.join(self.mapa, "Slike/a.jpg")))


class Streznik(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapa = tempfile.mkdtemp(prefix="safeer-streznik-")
        cls.deljena = os.path.join(cls.mapa, "Slike")
        os.makedirs(cls.deljena)
        cls.vsebina = bytes(range(256)) * 40  # 10240 B
        with open(os.path.join(cls.deljena, "slika.png"), "wb") as d:
            d.write(cls.vsebina)
        cls.d = link_datoteke.Datoteke([cls.deljena], tls_mapa=os.path.join(cls.mapa, "tls"))

    @classmethod
    def tearDownClass(cls):
        cls.d.ustavi()
        shutil.rmtree(cls.mapa, ignore_errors=True)

    def _zahteva(self, pot, metoda="GET", glave=None):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        p = http.client.HTTPSConnection("127.0.0.1", self.d.streznik.vrata, context=ctx, timeout=5)
        p.request(metoda, pot, headers=glave or {})
        der = p.sock.getpeercert(binary_form=True)
        o = p.getresponse()
        telo = o.read()
        p.close()
        return o.status, dict((k.lower(), v) for k, v in o.getheaders()), telo, hashlib.sha256(der).hexdigest()

    def test_seznam_zazene_streznik_in_da_zeton(self):
        o = self.d.seznam("", "tv-1")
        self.assertTrue(o["shared"])
        self.assertNotIn("server", o)  # koren ima samo mape: streznika se ne rabimo
        self.assertFalse(self.d.streznik.tece())
        o = self.d.seznam("share:0:", "tv-1", "wss://127.0.0.1:8990/cast/ws")
        self.assertEqual(o["items"][0]["type"], "image")
        s = o["server"]
        self.assertTrue(self.d.streznik.tece())
        self.assertTrue(s["base_url"].startswith("https://"))
        self.assertEqual(len(s["fp"]), 64)
        self.assertEqual(self.d.seznam("share:0:", "tv-1")["server"]["token"], s["token"])  # ista naprava, isti zeton
        self.assertNotEqual(self.d.seznam("share:0:", "tv-2")["server"]["token"], s["token"])
        with self.assertRaises(FileNotFoundError):
            self.d.seznam("share:0:ni", "tv-1")

        zeton = s["token"]
        # potrdilo je tisto z odtisom iz odgovora
        st, gl, telo, odtis = self._zahteva("/d/share:0:slika.png", glave={"X-Safeer-Token": zeton})
        self.assertEqual(odtis, s["fp"])
        self.assertEqual(st, 200)
        self.assertEqual(telo, self.vsebina)
        self.assertEqual(gl["content-type"], "image/png")
        self.assertEqual(gl["accept-ranges"], "bytes")
        # zeton samo v glavi: v naslovu (?t=) bi ostal v dnevnikih in zgodovini
        self.assertEqual(self._zahteva("/d/share:0:slika.png?t=" + zeton)[0], 401)
        # obsegi
        st, gl, telo, _ = self._zahteva("/d/share:0:slika.png", glave={"X-Safeer-Token": zeton, "Range": "bytes=100-199"})
        self.assertEqual(st, 206)
        self.assertEqual(telo, self.vsebina[100:200])
        self.assertEqual(gl["content-range"], "bytes 100-199/10240")
        st, _, telo, _ = self._zahteva("/d/share:0:slika.png", glave={"X-Safeer-Token": zeton, "Range": "bytes=10000-"})
        self.assertEqual((st, telo), (206, self.vsebina[10000:]))
        st, _, telo, _ = self._zahteva("/d/share:0:slika.png", glave={"X-Safeer-Token": zeton, "Range": "bytes=-16"})
        self.assertEqual((st, telo), (206, self.vsebina[-16:]))
        st, gl, _, _ = self._zahteva("/d/share:0:slika.png", glave={"X-Safeer-Token": zeton, "Range": "bytes=99999-"})
        self.assertEqual((st, gl["content-range"]), (416, "bytes */10240"))
        st, gl, telo, _ = self._zahteva("/d/share:0:slika.png", "HEAD", {"X-Safeer-Token": zeton})
        self.assertEqual((st, gl["content-length"], telo), (200, "10240", b""))
        # brez zetona ali z napacnim nic; tuje poti nic
        self.assertEqual(self._zahteva("/d/share:0:slika.png")[0], 401)
        self.assertEqual(self._zahteva("/d/share:0:slika.png", glave={"X-Safeer-Token": "x"})[0], 401)
        self.assertEqual(self._zahteva("/d/share:0:../../etc/passwd", glave={"X-Safeer-Token": zeton})[0], 404)
        self.assertEqual(self._zahteva("/nekaj", glave={"X-Safeer-Token": zeton})[0], 404)

    def test_ukaz_files_list_v_controlu(self):
        izidi = []
        link_daljinec.izvedi_control("files.list", {"folder": ""}, lambda u: None, izidi.append,
                                     datoteke=self.d, posiljatelj="tv-9")
        self.assertTrue(izidi[-1]["ok"])
        self.assertEqual(izidi[-1]["data"]["items"][0]["name"], "Slike")
        link_daljinec.izvedi_control("files.list", {"folder": "share:0:ni"}, lambda u: None, izidi.append, datoteke=self.d)
        self.assertEqual(izidi[-1]["code"], "ni_mape")
        link_daljinec.izvedi_control("files.list", {}, lambda u: None, izidi.append)
        self.assertEqual(izidi[-1]["code"], "ni_na_racunalniku")
        link_daljinec.izvedi_control("status", {}, lambda u: None, izidi.append, datoteke=self.d)
        self.assertIn("files.list", izidi[-1]["data"]["actions"])
        self.assertEqual(izidi[-1]["data"]["shared_folders"], 1)
        prazne = link_datoteke.Datoteke([], tls_mapa=os.path.join(self.mapa, "tls2"))
        link_daljinec.izvedi_control("files.list", {}, lambda u: None, izidi.append, datoteke=prazne)
        self.assertTrue(izidi[-1]["ok"])
        self.assertFalse(izidi[-1]["data"]["shared"])

    def test_nastavi_shrani(self):
        shranjeno = []
        d = link_datoteke.Datoteke([], tls_mapa=os.path.join(self.mapa, "tls3"))
        d.ob_spremembi = shranjeno.append
        d.dodaj(self.deljena)
        d.dodaj(self.deljena)
        self.assertEqual(shranjeno[-1], [self.deljena])
        d.odstrani(0)
        self.assertEqual(shranjeno[-1], [])


if __name__ == "__main__":
    unittest.main()
