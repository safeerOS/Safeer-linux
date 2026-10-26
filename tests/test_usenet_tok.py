"""Lasten pogon Usenet, korak 2 (26. 10. 2026): preslikava odmikov (core/usenet_tok.py).

Deli so pravi clanki yEnc (usenet_yenc.kodiraj -> dekodiraj); resnica je razdelitev, s katero smo jih ustvarili - ne
nasa preslikava. message-id so izmisljeni (.invalid).
"""
import os
import random
import sys
import unittest

from core import usenet_tok as T, usenet_yenc as Y

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # usenet_gradnja (pomoc preizkusov)
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


# ---------------------------------------------------------------------- RAR store (korak 2, del 2)

from core import usenet_rar as R  # noqa: E402
import usenet_gradnja as G  # noqa: E402

#: Zacetki pravih arhivov WinRAR 7.x (26. 10. 2026, naklj. podatki 50 000 B »film.mkv«, besedilo »tekst.mkv«):
#: store prvi od treh zvezkov (-v20k), -m3 cel arhiv, -p (sifrirani podatki), -hp (sifrirane glave).
PRAVI_STORE_ZVEZEK1 = bytes.fromhex(
    "526172211a0701005f9b7b890b01050701060101a09f81007eac823d2602130be59e0104d0860320646aa5ee8000000866696c6d2e6d6b"
    "760a0302147611b50f65dd0182b70eee7f1a5039bef07ec2347f066ed08f5dc7512447e3404300026b6e545594a065685d64c4980bb8d4"
    "544a8721a99a01ad219e")
PRAVI_STISNJEN = bytes.fromhex(
    "526172211a070100f3e182eb0b0105070006010180808000a2a2b5972702030bbc800004a09603202b522a958003000974656b73742e6d"
    "6b760a0302f750efba0f65dd01c7a439340422fa33c54c9dc08a06412463016977bf323feb7b3bec57afc2e59a5392cff8f52575ea177a"
    "543fe902eb0ffa40bc63fe902f18ffa40bc61d77565103050400")
PRAVI_SIFRIRAN = bytes.fromhex(
    "526172211a070100ace31d7f0b01050700060101bc8783004e304b4c5702033cd0860304d0860320ccef46a68000000866696c6d2e6d6b"
    "76300100030f2cf6e6d893cc19dc045c4a2008174a62632af76574d2357e64d762915268ee8b4285842289177148bb5c1bf30a03021476"
    "11b50f65dd0174e05fea1fc471d748641223818eccbd7ec4a9999a65d53047ec149a71445cff6f7ba50a79a28ae5980113f1b9910ba7ad"
    "6d52a1398f")
PRAVI_SIFRIRANE_GLAVE = bytes.fromhex(
    "526172211a0701004014c85c21040000010fee7012d4fc342417698f75516688c3f9c49782d458f1fa85c2002af4ac61aa80c955184217"
    "7744a16141c4de998e")


class PraviRar(unittest.TestCase):
    """Odlocitev pred ponudbo iz prvih bajtov pravih arhivov WinRAR - neodvisno od nasega graditelja."""

    def test_preveri(self):
        self.assertEqual(R.preveri(PRAVI_STORE_ZVEZEK1), R.OK)
        self.assertEqual(R.preveri(PRAVI_STISNJEN), R.STISNJEN)
        self.assertEqual(R.preveri(PRAVI_SIFRIRAN), R.SIFRIRAN)
        self.assertEqual(R.preveri(PRAVI_SIFRIRANE_GLAVE), R.SIFRIRANE_GLAVE)

    def test_zvezek(self):
        z = R.razcleni_zvezek(PRAVI_STORE_ZVEZEK1, 20480)
        v = z.vnosi[0]
        self.assertEqual((z.razlicica, z.stevilka, z.vec_zvezkov), (5, 0, True))
        self.assertEqual((v.ime, v.odmik, v.dolzina, v.velikost, v.razdeljen_pred, v.razdeljen_po, v.store),
                         ("film.mkv", 67, 20325, 50000, False, True, True))

    def test_poskodovan_crc(self):
        b = bytearray(PRAVI_STORE_ZVEZEK1)
        b[40] ^= 1  # bajt v glavi datoteke
        self.assertEqual(R.preveri(bytes(b)), R.POSKODOVAN)


class RarStore(unittest.TestCase):
    def setUp(self):
        self.film = os.urandom(70_001)

    def preberi(self, vols, kosi):
        return b"".join(vols[k.zvezek][k.odmik:k.odmik + k.dolzina] for k in kosi)

    def test_vec_zvezkov_rar4_in_rar5(self):
        for razlicica in (4, 5):
            vols = G.zvezki(razlicica, "Film.2026.1080p.mkv", self.film, 25_000)
            self.assertEqual(len(vols), 3)
            zv = [R.razcleni_zvezek(v) for v in vols]
            self.assertTrue(all(z.razlicica == razlicica and z.vec_zvezkov for z in zv))
            ime, velikost, kosi = R.sestavi(zv)
            self.assertEqual((ime, velikost, len(kosi)), ("Film.2026.1080p.mkv", len(self.film), 3))
            self.assertEqual(self.preberi(vols, kosi), self.film)
            self.assertEqual(R.preveri(vols[0][:4096]), R.OK, razlicica)

    def test_vzorec_in_nfo_ob_filmu(self):
        for gradi in (G.rar4, G.rar5):
            arh = gradi([("info.nfo", 3, b"nfo", {}), ("sample.mkv", 500, os.urandom(500), {}),
                         ("film.mkv", len(self.film), self.film, {})])
            ime, velikost, kosi = R.sestavi([R.razcleni_zvezek(arh)])
            self.assertEqual(ime, "film.mkv")
            self.assertEqual(self.preberi([arh], kosi), self.film)

    def test_zavrni_stisnjen_sifriran_glave(self):
        for gradi, metoda in ((G.rar4, 0x33), (G.rar5, 3)):
            stisnjen = gradi([("film.mkv", 100_000, self.film[:500], {"metoda": metoda})])
            self.assertEqual(R.preveri(stisnjen[:4096]), R.STISNJEN)
            with self.assertRaises(R.NapakaRar) as e:
                R.sestavi([R.razcleni_zvezek(stisnjen)])
            self.assertEqual(e.exception.izid, R.STISNJEN)
            sifriran = gradi([("film.mkv", 500, self.film[:500], {"sifriran": True})])
            self.assertEqual(R.preveri(sifriran), R.SIFRIRAN)
            self.assertEqual(R.preveri(gradi([], sifrirane_glave=True)), R.SIFRIRANE_GLAVE)

    def test_odlocitev_iz_prvega_segmenta(self):
        # film v zvezku je za glavo: prvih 300 B zadosca za odlocitev, ce je glava v njih; sicer »nepopolno«
        vol = G.zvezki(5, "film.mkv", self.film, 40_000)[0]
        self.assertEqual(R.preveri(vol[:300]), R.OK)
        self.assertEqual(R.preveri(vol[:30]), R.NEPOPOLNO)
        self.assertEqual(R.preveri(b"\x1aE\xdf\xa3" + bytes(100)), R.NI_RAR)  # mkv

    def test_napacen_vrstni_red_in_manjkajoc_zvezek(self):
        for razlicica in (4, 5):
            zv = [R.razcleni_zvezek(v) for v in G.zvezki(razlicica, "film.mkv", self.film, 25_000)]
            for slabo in ([zv[1], zv[0], zv[2]], [zv[0], zv[2]], zv[:2]):
                with self.assertRaises(R.NapakaRar) as e:
                    R.sestavi(slabo)
                self.assertEqual(e.exception.izid, R.NESKLADNO)
            drug = [R.razcleni_zvezek(v) for v in G.zvezki(razlicica, "drug.mkv", self.film, 25_000)]
            with self.assertRaises(R.NapakaRar):
                R.sestavi([zv[0], drug[1], zv[2]])

    def test_zlonamerne_glave(self):
        rar5 = G.rar5([("film.mkv", 10, b"0123456789", {})])
        # velikost glave 2 MiB + 1 (meja specifikacije), neskoncna veriga, glava pred glavno
        prevelika = G.PODPIS5 + b"\0\0\0\0" + G.vint(R.NAJVEC_GLAVA5 + 1)
        self.assertEqual(R.preveri(prevelika + bytes(10)), R.POSKODOVAN)
        brez_glavne = G.PODPIS5 + G.glava5_datoteke("film.mkv", 10, b"0123456789")
        self.assertEqual(R.preveri(brez_glavne), R.POSKODOVAN)
        vint11 = G.PODPIS5 + b"\0\0\0\0" + b"\xff" * 11
        self.assertEqual(R.preveri(vint11), R.POSKODOVAN)
        brez_glavne4 = G.PODPIS4 + G.glava4_datoteke("a", 1, b"a")
        self.assertEqual(R.preveri(brez_glavne4), R.POSKODOVAN)
        self.assertEqual(R.preveri(rar5), R.OK)
        # ime s potjo in nevarnimi znaki gre skozi varno_ime
        z = R.razcleni_zvezek(G.rar5([("..\\..\\Windows\\a<b>.mkv", 1, b"x", {})]))
        self.assertEqual(z.vnosi[0].ime, "a_b_.mkv")

    def test_rar4_velika_datoteka_in_unicode_ime(self):
        arh = G.rar4([("film.mkv", 5 * 2 ** 32 + 7, b"abc", {"velika": True, "unicode": True})])
        v = R.razcleni_zvezek(arh).vnosi[0]
        self.assertEqual((v.ime, v.velikost, v.dolzina), ("film.mkv", 5 * 2 ** 32 + 7, 3))

    def test_vrstni_red_zvezkov(self):
        self.assertEqual(R.vrstni_red_zvezkov(["a.part03.rar", "a.part01.rar", "a.part02.rar"]), [1, 2, 0])
        self.assertEqual(R.vrstni_red_zvezkov(["A.r01", "a.rar", "a.r00"]), [1, 2, 0])
        self.assertIsNone(R.vrstni_red_zvezkov(["a.part1.rar", "a.part3.rar"]))  # manjka
        self.assertIsNone(R.vrstni_red_zvezkov(["a.rar", "b.r00"]))  # druga osnova
        self.assertIsNone(R.vrstni_red_zvezkov(["a.rar", "a.part2.rar"]))  # mesana shema
        self.assertIsNone(R.vrstni_red_zvezkov(["a.mkv"]))


if __name__ == "__main__":
    unittest.main()
