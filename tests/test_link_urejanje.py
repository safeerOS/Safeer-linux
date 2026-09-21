"""Urejanje deljenih datotek z naprav (core/link_urejanje.py + POST /d/<id> v core/link_datoteke.py)."""
import http.client
import json
import os
import shutil
import ssl
import struct
import sys
import tempfile
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_datoteke, link_urejanje  # noqa: E402

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def jpeg_z_exif(orientacija: int, vrstni_red: str = "MM") -> bytes:
    """Najmanjsi JPEG z APP1 Exif in samo oznako Orientation (kot ga zapise fotoaparat)."""
    vr = ">" if vrstni_red == "MM" else "<"
    tiff = vrstni_red.encode() + struct.pack(vr + "HI", 42, 8)
    ifd = struct.pack(vr + "H", 1) + struct.pack(vr + "HHI", 0x0112, 3, 1) + struct.pack(vr + "H", orientacija) + b"\x00\x00" + struct.pack(vr + "I", 0)
    exif = b"Exif\x00\x00" + tiff + ifd
    app1 = b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif
    return b"\xff\xd8" + app1 + b"\xff\xda\x00\x02" + b"\x00" * 8 + b"\xff\xd9"


def preberi_orientacijo(pot: str) -> int:
    with open(pot, "rb") as d:
        return link_urejanje._exif_orientacija(d.read())[2]


class Vrtenje(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-vrtenje-")

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_exif_brez_izgube(self):
        for red in ("MM", "II"):
            p = os.path.join(self.mapa, f"foto-{red}.jpg")
            with open(p, "wb") as d:
                d.write(jpeg_z_exif(1, red))
            izvirnik = open(p, "rb").read()
            self.assertEqual(link_urejanje.zavrti(p, 90), "exif")
            self.assertEqual(preberi_orientacijo(p), 6)
            self.assertEqual(link_urejanje.zavrti(p, 90), "exif")
            self.assertEqual(preberi_orientacijo(p), 3)
            self.assertEqual(link_urejanje.zavrti(p, 270), "exif")
            self.assertEqual(preberi_orientacijo(p), 6)
            self.assertEqual(link_urejanje.zavrti(p, 270), "exif")
            self.assertEqual(preberi_orientacijo(p), 1)
            self.assertEqual(open(p, "rb").read(), izvirnik)  # slikovni podatki nedotaknjeni
        # lezeca fotografija s telefona (6 = zavrtena za 90 v desno) -> v levo je pokoncna (1)
        p = os.path.join(self.mapa, "lezeca.jpg")
        with open(p, "wb") as d:
            d.write(jpeg_z_exif(6))
        link_urejanje.zavrti(p, 270)
        self.assertEqual(preberi_orientacijo(p), 1)
        # zrcaljene vrednosti ostanejo zrcaljene
        with open(p, "wb") as d:
            d.write(jpeg_z_exif(2))
        link_urejanje.zavrti(p, 90)
        self.assertEqual(preberi_orientacijo(p), 7)

    def test_napacen_kot_in_ni_datoteke(self):
        p = os.path.join(self.mapa, "x.jpg")
        with open(p, "wb") as d:
            d.write(jpeg_z_exif(1))
        with self.assertRaises(link_urejanje.NapakaUrejanja):
            link_urejanje.zavrti(p, 45)
        with self.assertRaises(link_urejanje.NapakaUrejanja):
            link_urejanje.zavrti(os.path.join(self.mapa, "ni.jpg"), 90)

    @unittest.skipIf(Image is None, "Pillow ni namescen")
    def test_dekompresijska_bomba_se_ne_dekodira(self):
        p = os.path.join(self.mapa, "bomba.png")
        Image.new("1", (64, 64)).save(p)
        with mock.patch.object(link_urejanje, "NAJVEC_PIK", 64 * 64 - 1):
            with self.assertRaises(link_urejanje.NapakaUrejanja) as e:
                link_urejanje.zavrti(p, 90)
        self.assertEqual(str(e.exception), "prevelika")
        with mock.patch.object(link_urejanje, "NAJVEC_BAJTOV_SLIKE", 10):
            with self.assertRaises(link_urejanje.NapakaUrejanja):
                link_urejanje.zavrti(p, 90)
        self.assertEqual(link_urejanje.zavrti(p, 90), "pillow")  # v mejah dela naprej

    @unittest.skipIf(Image is None, "Pillow ni namescen")
    def test_pillow_png_in_jpeg_brez_exifa(self):
        p = os.path.join(self.mapa, "slika.png")
        s = Image.new("RGB", (4, 2), "white")
        s.putpixel((0, 0), (255, 0, 0))  # rdeca zgoraj levo
        s.save(p)
        self.assertEqual(link_urejanje.zavrti(p, 90), "pillow")
        with Image.open(p) as z:
            self.assertEqual(z.size, (2, 4))
            self.assertEqual(z.getpixel((1, 0)), (255, 0, 0))  # v desno: zgoraj levo -> zgoraj desno
        self.assertEqual(link_urejanje.zavrti(p, 270), "pillow")
        with Image.open(p) as z:
            self.assertEqual(z.size, (4, 2))
            self.assertEqual(z.getpixel((0, 0)), (255, 0, 0))
        j = os.path.join(self.mapa, "brez.jpg")
        Image.new("RGB", (6, 3), "blue").save(j, quality=90)
        self.assertEqual(link_urejanje.zavrti(j, 90), "pillow")
        with Image.open(j) as z:
            self.assertEqual(z.size, (3, 6))
        self.assertFalse(os.path.exists(j + ".safeer-vrtenje"))


class SmetiImeMapa(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-urejanje-")
        self.dom = os.path.join(self.mapa, "dom")
        os.makedirs(self.dom)
        self.okolje = mock.patch.dict(os.environ, {"XDG_DATA_HOME": self.dom})
        self.okolje.start()
        # brez gio: preverimo rocne Smeti po freedesktop
        self.gio = mock.patch("shutil.which", lambda ime: None)
        self.gio.start()

    def tearDown(self):
        self.gio.stop()
        self.okolje.stop()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_smeti(self):
        p = os.path.join(self.mapa, "posnetek.mp4")
        open(p, "wb").write(b"abc")
        link_urejanje.v_smeti(p)
        self.assertFalse(os.path.exists(p))
        smeti = os.path.join(self.dom, "Trash")
        self.assertEqual(os.listdir(os.path.join(smeti, "files")), ["posnetek.mp4"])
        info = open(os.path.join(smeti, "info", "posnetek.mp4.trashinfo"), encoding="utf-8").read()
        self.assertIn("[Trash Info]", info)
        self.assertIn("Path=" + p.replace(" ", "%20"), info)
        self.assertIn("DeletionDate=", info)
        # drugic isto ime: (1)
        open(p, "wb").write(b"def")
        link_urejanje.v_smeti(p)
        self.assertEqual(sorted(os.listdir(os.path.join(smeti, "files"))), ["posnetek (1).mp4", "posnetek.mp4"])
        with self.assertRaises(link_urejanje.NapakaUrejanja):
            link_urejanje.v_smeti(p)

    def test_preimenuj_in_premakni(self):
        p = os.path.join(self.mapa, "a.txt")
        open(p, "w").write("a")
        open(os.path.join(self.mapa, "b.txt"), "w").write("b")
        self.assertEqual(link_urejanje.preimenuj(p, "c.txt"), os.path.join(self.mapa, "c.txt"))
        with self.assertRaises(link_urejanje.NapakaUrejanja) as e:
            link_urejanje.preimenuj(os.path.join(self.mapa, "c.txt"), "b.txt")
        self.assertEqual(str(e.exception), "obstaja")
        for slabo in ("", ".", "..", ".skrito", "x/y", "x\\y", "a\x00b", "a\nb", "x" * 300):
            with self.assertRaises(link_urejanje.NapakaUrejanja, msg=repr(slabo)):
                link_urejanje.preimenuj(os.path.join(self.mapa, "c.txt"), slabo)
        pod = os.path.join(self.mapa, "pod")
        os.makedirs(pod)
        self.assertEqual(link_urejanje.premakni(os.path.join(self.mapa, "c.txt"), pod), os.path.join(pod, "c.txt"))
        self.assertTrue(os.path.exists(os.path.join(pod, "c.txt")))
        with self.assertRaises(link_urejanje.NapakaUrejanja):
            link_urejanje.premakni(os.path.join(self.mapa, "b.txt"), os.path.join(self.mapa, "ni"))
        with self.assertRaises(link_urejanje.NapakaUrejanja):
            link_urejanje.premakni(pod, os.path.join(pod))  # mapa vase
        self.assertEqual(link_urejanje.premakni(os.path.join(pod, "c.txt"), pod), os.path.join(pod, "c.txt"))  # ze tam


class Streznik(unittest.TestCase):
    """POST /d/<id>: zeton, meje, kode napak, nove oznake."""

    @classmethod
    def setUpClass(cls):
        cls.mapa = tempfile.mkdtemp(prefix="safeer-post-")
        cls.deljena = os.path.join(cls.mapa, "Slike")
        os.makedirs(os.path.join(cls.deljena, "Album"))
        with open(os.path.join(cls.deljena, "foto.jpg"), "wb") as d:
            d.write(jpeg_z_exif(6))
        with open(os.path.join(cls.deljena, "film.mp4"), "wb") as d:
            d.write(b"v" * 10)
        with open(os.path.join(cls.mapa, "zunaj.txt"), "w") as d:
            d.write("ne")
        cls.d = link_datoteke.Datoteke([cls.deljena], tls_mapa=os.path.join(cls.mapa, "tls"))
        o = cls.d.seznam("share:0:", "tv-1")
        cls.zeton = o["server"]["token"]
        cls.edit = o["edit"]

    @classmethod
    def tearDownClass(cls):
        cls.d.ustavi()
        shutil.rmtree(cls.mapa, ignore_errors=True)

    def _post(self, oznaka, telo, zeton=None, surovo=None):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        p = http.client.HTTPSConnection("127.0.0.1", self.d.streznik.vrata, context=ctx, timeout=5)
        podatki = surovo if surovo is not None else json.dumps(telo).encode("utf-8")
        glave = {"Content-Type": "application/json", "Content-Length": str(len(podatki))}
        if zeton is None:
            zeton = self.zeton
        if zeton:
            glave["X-Safeer-Token"] = zeton
        p.request("POST", "/d/" + oznaka, body=podatki, headers=glave)
        o = p.getresponse()
        telo = o.read()
        p.close()
        try:
            return o.status, json.loads(telo.decode("utf-8"))
        except ValueError:
            return o.status, telo

    def test_edit_v_seznamu(self):
        self.assertTrue(self.edit)
        self.assertNotIn("edit", self.d.seznam("", "tv-1") or {"edit": None}) if False else None
        self.assertFalse(self.d.seznam("", "tv-1")["edit"])  # koren (deljene mape same) se ne ureja

    def test_zeton_in_meje(self):
        self.assertEqual(self._post("share:0:film.mp4", {"op": "delete"}, zeton="")[0], 401)
        self.assertEqual(self._post("share:0:film.mp4", {"op": "delete"}, zeton="napacen")[0], 401)
        self.assertEqual(self._post("share:0:film.mp4", {"op": "xy"})[0], 400)
        self.assertEqual(self._post("share:0:film.mp4", None, surovo=b"{ni json")[0], 400)
        self.assertEqual(self._post("share:0:film.mp4", None, surovo=b"[]")[0], 400)
        self.assertEqual(self._post("share:0:film.mp4", None, surovo=b"x" * (link_datoteke.NAJVEC_TELESA + 1))[0], 413)
        self.assertEqual(self._post("share:0:../zunaj.txt", {"op": "delete"})[0], 404)
        self.assertEqual(self._post("share:0:ni.txt", {"op": "delete"})[0], 404)
        self.assertEqual(self._post("share:0:", {"op": "rename", "name": "x"})[0], 403)  # deljena mapa sama
        self.assertEqual(self._post("share:0:film.mp4", {"op": "rotate", "degrees": 90})[0], 400)  # ni slika
        self.assertTrue(os.path.exists(os.path.join(self.mapa, "zunaj.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.deljena, "film.mp4")))

    def test_ukazi(self):
        # vrtenje: exif, oznaka ostane ista
        st, o = self._post("share:0:foto.jpg", {"op": "rotate", "degrees": 270})
        self.assertEqual((st, o["ok"], o["how"], o["id"]), (200, True, "exif", "share:0:foto.jpg"))
        self.assertEqual(preberi_orientacijo(os.path.join(self.deljena, "foto.jpg")), 1)
        # preimenovanje -> nova oznaka
        st, o = self._post("share:0:foto.jpg", {"op": "rename", "name": "dopust.jpg"})
        self.assertEqual((st, o["id"], o["name"]), (200, "share:0:dopust.jpg", "dopust.jpg"))
        st, o = self._post("share:0:dopust.jpg", {"op": "rename", "name": "film.mp4"})
        self.assertEqual((st, o["napaka"]), (409, "obstaja"))
        # premik v podmapo; ven iz deljene mape ne gre
        st, o = self._post("share:0:dopust.jpg", {"op": "move", "folder": "share:0:Album"})
        self.assertEqual((st, o["id"]), (200, "share:0:Album/dopust.jpg"))
        self.assertEqual(self._post("share:0:Album/dopust.jpg", {"op": "move", "folder": "share:0:.."})[0], 404)
        self.assertEqual(self._post("share:0:Album/dopust.jpg", {"op": "move", "folder": "share:0:film.mp4"})[0], 400)
        # brisanje gre v Smeti (gio ali rocno) - datoteke ni vec v mapi
        with mock.patch("shutil.which", lambda ime: None), mock.patch.dict(os.environ, {"XDG_DATA_HOME": os.path.join(self.mapa, "dom")}):
            st, o = self._post("share:0:Album/dopust.jpg", {"op": "delete"})
        self.assertEqual((st, o["ok"]), (200, True))
        self.assertFalse(os.path.exists(os.path.join(self.deljena, "Album", "dopust.jpg")))
        self.assertTrue(os.path.exists(os.path.join(self.mapa, "dom", "Trash", "files", "dopust.jpg")))


if __name__ == "__main__":
    unittest.main()
