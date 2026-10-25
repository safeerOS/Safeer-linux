"""Slicice datotek z naprav v Linku (core/link_slicice_naprav.py): streznik iz files.list, predpomnilnik po napravi,
oznaki, casu in velikosti, samo prave slike, najvec dve hkrati, meja predpomnilnika, naprava brez slicic."""
import os
import tempfile
import threading
import time
import unittest

from core import link_slicice_naprav as ls

STREZNIK = {"base_url": "https://192.168.0.20:8443", "fp": "ab" * 32, "token": "z"}
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 100


class Streznik(unittest.TestCase):
    def test_veljaven(self):
        self.assertTrue(ls.veljaven_streznik(STREZNIK))
        for slab in (None, {}, dict(STREZNIK, base_url="http://192.168.0.20:8443"), dict(STREZNIK, fp=""),
                     dict(STREZNIK, fp="nic"), dict(STREZNIK, token=""), dict(STREZNIK, base_url="https://192.0.2.1:1")):
            self.assertFalse(ls.veljaven_streznik(slab), slab)

    def test_vrsta(self):
        self.assertEqual(ls.vrsta_slike(JPEG), "jpg")
        self.assertEqual(ls.vrsta_slike(b"\x89PNG\r\n\x1a\nxx"), "png")
        self.assertEqual(ls.vrsta_slike(b"RIFF\0\0\0\0WEBPVP8 "), "webp")
        self.assertEqual(ls.vrsta_slike(b"<html>"), "")


class Predpomnilnik(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-slicice-")
        self.klici = []

    def prenesi(self, streznik, oznaka, rob):
        self.klici.append((oznaka, rob))
        return JPEG if oznaka.startswith("media:image") else b"<html>ni slike</html>"

    def test_prenos_in_predpomnilnik(self):
        s = ls.Slicice(self.mapa, self.prenesi)
        vnosi = [{"id": "media:image:1", "modified": 1792915200000, "size": 10}, {"id": "media:video:2", "size": 5}]
        r = s.dobi("n-tel", STREZNIK, vnosi)
        self.assertEqual(list(r), ["media:image:1"], "ne-slika se ne shrani")
        self.assertTrue(r["media:image:1"].endswith(".jpg") and os.path.isfile(r["media:image:1"]))
        self.assertEqual(s.dobi("n-tel", STREZNIK, vnosi), r)
        self.assertEqual(self.klici, [("media:image:1", 256), ("media:video:2", 256)], "drugic iz predpomnilnika, "
                         "naprava brez slicice se 10 min ne sprasuje")
        # Nova razlicica datoteke (cas spremembe) = nova slicica; druga naprava ima svoj kljuc.
        s.dobi("n-tel", STREZNIK, [{"id": "media:image:1", "modified": 1792915299000, "size": 10}])
        s.dobi("n-tab", STREZNIK, [{"id": "media:image:1", "modified": 1792915200000, "size": 10}])
        self.assertEqual(len(self.klici), 4)

    def test_slab_streznik_ali_oznaka(self):
        s = ls.Slicice(self.mapa, self.prenesi)
        self.assertEqual(s.dobi("n", dict(STREZNIK, fp=""), [{"id": "media:image:1"}]), {})
        self.assertEqual(s.dobi("n", STREZNIK, [{"id": ""}, {"id": "a\nb"}, "x", {"id": "m" * 600}]), {})
        self.assertEqual(self.klici, [])

    def test_najvec_dve_hkrati(self):
        hkrati, najvec = [0], [0]
        zaklep = threading.Lock()

        def pocasi(streznik, oznaka, rob):
            with zaklep:
                hkrati[0] += 1
                najvec[0] = max(najvec[0], hkrati[0])
            time.sleep(0.05)
            with zaklep:
                hkrati[0] -= 1
            return JPEG
        s = ls.Slicice(self.mapa, pocasi)
        niti = [threading.Thread(target=s.dobi, args=("n", STREZNIK, [{"id": "media:image:%d-%d" % (i, j)}
                                                                        for j in range(3)])) for i in range(4)]
        for n in niti:
            n.start()
        for n in niti:
            n.join()
        self.assertLessEqual(najvec[0], ls.HKRATI)

    def test_meja_predpomnilnika(self):
        s = ls.Slicice(self.mapa, lambda *a: JPEG + b"y" * 1000, najvec=3000)
        for i in range(10):
            s.dobi("n", STREZNIK, [{"id": "media:image:%d" % i}])
        skupaj = sum(os.path.getsize(os.path.join(k, i)) for k, _m, imena in os.walk(self.mapa) for i in imena)
        self.assertLessEqual(skupaj, 3000)

    def test_napaka_naprave(self):
        def pade(*a):
            raise OSError("ni povezave")
        self.assertEqual(ls.Slicice(self.mapa, pade).dobi("n", STREZNIK, [{"id": "media:image:1"}]), {})


if __name__ == "__main__":
    unittest.main()
