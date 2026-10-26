"""Lasten pogon Usenet, korak 2 (26. 10. 2026): preslikava odmikov (core/usenet_tok.py).

Deli so pravi clanki yEnc (usenet_yenc.kodiraj -> dekodiraj); resnica je razdelitev, s katero smo jih ustvarili - ne
nasa preslikava. message-id so izmisljeni (.invalid).
"""
import os
import random
import unittest

from core import usenet_tok as T, usenet_yenc as Y
from core.usenet_nzb import Datoteka, Segment


def deli_datoteke(podatki, velikosti):
    """[(odmik, bajti)] po danih velikostih delov."""
    izid, o = [], 0
    for v in velikosti:
        izid.append((o, podatki[o:o + v]))
        o += v
    assert o == len(podatki)
    return izid


def clanki(podatki, velikosti, ime="film.mkv"):
    """{stevilka: DelYenc} - vsak del kodiran in dekodiran kot s streznika."""
    n = len(velikosti)
    return {i + 1: Y.dekodiraj(Y.kodiraj(b, ime, len(podatki), i + 1, n, o + 1))
            for i, (o, b) in enumerate(deli_datoteke(podatki, velikosti))}


def datoteka(stevilke, manjka=0, ime="film.mkv"):
    return Datoteka(ime, ("alt.binaries.test",), tuple(Segment(n, 1000, "d%d.Aa@primer.invalid" % n) for n in stevilke),
                    manjka)


def najdi(p, deli, odmik, iskanj=T.NAJVEC_ISKANJ):
    """Kot bralnik: beri ugibani segment, vnesi razpon, ponavljaj do natancnega. (stevilka, odmik, branj)."""
    for branj in range(iskanj):
        u = p.poisci(odmik)
        if u.natancno:
            return u.stevilka, u.odmik, branj
        p.vnesi(u.stevilka, deli[u.stevilka])
    raise AssertionError("ni konvergiralo")


def resnica(velikosti, odmik):
    o = 0
    for i, v in enumerate(velikosti):
        if odmik < o + v:
            return i + 1, odmik - o
        o += v
    raise AssertionError


class Preslikava(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(26)

    def test_enakomerno_prvi_segment_zadostuje(self):
        velikosti = [300] * 3 + [100]
        podatki = os.urandom(sum(velikosti))
        deli = clanki(podatki, velikosti)
        p = T.Preslikava(datoteka(range(1, 5)), deli[1])
        self.assertEqual((p.velikost, p.celota, p.del_bajtov, p.manjkajo), (1000, 4, 300, ()))
        for odmik in range(0, 1000, 7):
            st, k, branj = najdi(p, deli, odmik)
            self.assertEqual((st, k), resnica(velikosti, odmik))
            self.assertLessEqual(branj, 1, "enakomerna objava: ugib je pravi segment")
            self.assertEqual(deli[st].podatki[k], podatki[odmik])

    def test_neenakomerno_najde_v_nekaj_branjih(self):
        # dve objavi v enem NZB (vsaka s svojim zadnjim krajsim delom) in nakljucne velikosti
        for velikosti in ([300, 300, 120, 300, 300, 300, 80], [self.rng.randint(50, 400) for _ in range(60)]):
            podatki = os.urandom(sum(velikosti))
            deli = clanki(podatki, velikosti)
            for odmik in [0, len(podatki) - 1] + [self.rng.randrange(len(podatki)) for _ in range(40)]:
                p = T.Preslikava(datoteka(range(1, len(velikosti) + 1)), deli[1])
                st, k, branj = najdi(p, deli, odmik)
                self.assertEqual((st, k), resnica(velikosti, odmik), velikosti)
                self.assertEqual(deli[st].podatki[k], podatki[odmik])

    def test_luknja_v_nzb(self):
        velikosti = [200] * 5
        deli = clanki(os.urandom(1000), velikosti)
        p = T.Preslikava(datoteka([1, 2, 4, 5], manjka=1), deli[1])
        self.assertEqual(p.manjkajo, (3,))
        self.assertTrue(p.ima_luknje)
        with self.assertRaises(T.NapakaToka) as e:
            p.poisci(450)
        self.assertEqual(e.exception.izid, T.LUKNJA)
        self.assertEqual(najdi(p, deli, 650)[:2], (4, 50))
        self.assertEqual(p.segmenti_okna(300, 400), [2, 4], "okno preskoci manjkajoci segment")
        with self.assertRaises(T.NapakaToka):
            p.segment(3)

    def test_luknja_na_koncu_iz_yenc_total(self):
        # NZB ima 3 segmente, yEnc pravi total=5: zadnja dva manjkata
        deli = clanki(os.urandom(1000), [200] * 5)
        p = T.Preslikava(datoteka([1, 2, 3]), deli[1])
        self.assertEqual((p.celota, p.manjkajo), (5, (4, 5)))
        with self.assertRaises(T.NapakaToka) as e:
            p.poisci(999)
        self.assertEqual(e.exception.izid, T.LUKNJA)

    def test_prvi_segment_manjka(self):
        deli = clanki(os.urandom(1000), [250] * 4)
        p = T.Preslikava(datoteka([2, 3, 4], manjka=0), deli[2])
        self.assertEqual(p.manjkajo, (1,))
        self.assertEqual(najdi(p, deli, 999)[:2], (4, 249))
        with self.assertRaises(T.NapakaToka):
            p.poisci(10)

    def test_enodelna_datoteka(self):
        podatki = os.urandom(777)
        d = Y.dekodiraj(Y.kodiraj(podatki, "a.mkv"))
        p = T.Preslikava(datoteka([1]), d)
        self.assertEqual((p.celota, p.del_bajtov), (1, 777))
        self.assertEqual(p.poisci(776), T.Ugib(1, 776, True))

    def test_izven_in_neskladno(self):
        deli = clanki(os.urandom(1000), [250] * 4)
        p = T.Preslikava(datoteka(range(1, 5)), deli[1])
        for odmik in (-1, 1000, 10 ** 12):
            with self.assertRaises(T.NapakaToka) as e:
                p.poisci(odmik)
            self.assertEqual(e.exception.izid, T.IZVEN)
        drug = clanki(os.urandom(1200), [300] * 4)
        with self.assertRaises(T.NapakaToka) as e:
            p.vnesi(2, drug[2])  # druga velikost datoteke
        self.assertEqual(e.exception.izid, T.NESKLADNO)
        with self.assertRaises(T.NapakaToka):
            p.vnesi(3, deli[2])  # razpon segmenta 2 kot segment 3: prekriva segment 1? ne - sosednja se ne stikata
        self.assertEqual(p.znani(), {1: (0, 250)}, "zavrnjen vnos ne spremeni sider")
        with self.assertRaises(T.NapakaToka):
            T.Preslikava(datoteka(range(1, 2000)), deli[1])  # 1999 segmentov za 1000 B

    def test_ciste_funkcije(self):
        # 10 segmentov po 100, zadnji 50 (950 B)
        self.assertEqual(T.poisci(950, 10, 100, {1: (0, 100)}, 949), T.Ugib(10, 49, False))
        self.assertEqual(T.poisci(950, 10, None, {}, 0), T.Ugib(1, 0, False))
        self.assertEqual(T.segmenti_okna(950, 10, 100, {1: (0, 100)}, 150, 300), [2, 3, 4, 5])
        self.assertEqual(T.segmenti_okna(950, 10, 100, {1: (0, 100)}, 900, 10 ** 9), [10])
        self.assertEqual(T.segmenti_okna(950, 10, 100, {}, 950, 100), [])
        self.assertEqual(T.razpon(950, 10, 100, {1: (0, 100)}, 10), (900, 50, False))
        # sidri: 1 = [0,100), 4 = [500,600): vmes 2 segmenta na 400 B -> po 200
        z = {1: (0, 100), 4: (500, 100)}
        self.assertEqual(T.poisci(1000, 6, 100, z, 320), T.Ugib(3, 20, False))
        self.assertEqual(T.razpon(1000, 6, 100, z, 2), (100, 200, False))

    def test_repr_brez_id(self):
        deli = clanki(os.urandom(1000), [250] * 4)
        p = T.Preslikava(datoteka(range(1, 5)), deli[1])
        self.assertNotIn("primer.invalid", repr(p))
        self.assertNotIn("primer.invalid", str(T.NapakaToka(T.LUKNJA)))


if __name__ == "__main__":
    unittest.main()
