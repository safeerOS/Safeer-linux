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


# ---------------------------------------------------------------------- bralnik (korak 2, del 3)

import threading  # noqa: E402
import time  # noqa: E402

from core import usenet_bralnik as B, usenet_nzb as NZ  # noqa: E402

MiB = 1024 * 1024


def objavi(*datoteke, del_bajtov=700 * 1024):
    o = G.Objava(del_bajtov)
    for ime, v in datoteke:
        o.dodaj(ime, v)
    return o


def preberi_vse(br, od=0, n=None):
    n = br.vir.velikost - od if n is None else n
    return B._beri_vse(br, od, n)


class Bralnik(unittest.TestCase):
    def setUp(self):
        self.bralniki = []

    def tearDown(self):
        for b in self.bralniki:
            b.zapri()

    def bralnik(self, o, profil=B.PROFILI["namizje"], izpusti=()):
        vir, _ = B.pripravi(NZ.razcleni(o.nzb(izpusti)), o.telo)
        b = B.Bralnik(o.telo, vir, profil)
        self.bralniki.append(b)
        return b

    def test_okno_vnaprej(self):
        self.assertEqual(B.okno_vnaprej(0, MiB, 16 * MiB), MiB)
        self.assertEqual(B.okno_vnaprej(3 * MiB, MiB, 16 * MiB), 6 * MiB)
        self.assertEqual(B.okno_vnaprej(100 * MiB, MiB, 16 * MiB), 16 * MiB)
        self.assertEqual(B.okno_vnaprej(-5, MiB, 16 * MiB), MiB)

    def test_zaporedno_in_skoki_gola_datoteka(self):
        film = G.Leno(9 * MiB + 12345, 3)
        b = self.bralnik(objavi(("Film.2026.mkv", film), ("Film.2026.nfo", G.Bajti(b"nfo")),
                                ("Film.2026.sample.mkv", G.Leno(MiB, 9))))
        self.assertEqual(b.vir.velikost, film.velikost)
        self.assertEqual(preberi_vse(b), film.beri(0, film.velikost))
        rng = random.Random(5)
        for _ in range(30):
            od = rng.randrange(film.velikost)
            n = rng.randrange(1, 3 * MiB)
            self.assertEqual(preberi_vse(b, od, n), film.beri(od, n), od)
        self.assertEqual(b.beri(film.velikost, 10), b"")

    def test_rar_store_cez_zvezke(self):
        film = G.Leno(7 * MiB + 77, 4)
        for razlicica in (4, 5):
            vols = G.zvezki_leno(razlicica, "Film.mkv", film, 2 * MiB + 1)
            o = objavi(*[("Film.part%d.rar" % (i + 1), z) for i, z in enumerate(vols)])
            b = self.bralnik(o)
            self.assertEqual((b.vir.velikost, b.vir.ime, len(b.vir.kosi)), (film.velikost, "Film.mkv", 4))
            for od in (0, 2 * MiB - 100, 2 * MiB + 1, 4 * MiB + 1 - 3, film.velikost - 10):
                self.assertEqual(preberi_vse(b, od, 300_000), film.beri(od, 300_000), (razlicica, od))

    def test_stisnjen_rar_zavrnjen_iz_enega_clanka(self):
        o = objavi(("Film.part1.rar", G.Bajti(G.rar5([("Film.mkv", 10 ** 9, os.urandom(900_000),
                                                         {"metoda": 3, "po": True})], vec=True, zadnji=False))),
                   ("Film.part2.rar", G.Bajti(os.urandom(900_000))))
        nzb = NZ.razcleni(o.nzb())
        self.assertEqual(B.preveri_izdajo(nzb, o.telo), R.STISNJEN)
        self.assertEqual(o.poslanih, 1, "odlocitev iz enega clanka")
        with self.assertRaises(R.NapakaRar) as e:
            B.pripravi(nzb, o.telo)
        self.assertEqual(e.exception.izid, R.STISNJEN)
        sif = objavi(("Film.rar", G.Bajti(G.rar4([("Film.mkv", 500, os.urandom(500), {"sifriran": True})]))))
        self.assertEqual(B.preveri_izdajo(NZ.razcleni(sif.nzb()), sif.telo), R.SIFRIRAN)
        gola = objavi(("Film.mkv", G.Leno(2 * MiB, 1)))
        self.assertEqual(B.preveri_izdajo(NZ.razcleni(gola.nzb()), gola.telo), R.OK)

    def test_okno_omejeno_po_skoku(self):
        film = G.Leno(64 * MiB, 8)
        o = objavi(("Film.mkv", film))
        b = self.bralnik(o)
        zacetek = o.poslano
        b.beri(40 * MiB, 64 * 1024)  # skok (npr. indeks na koncu): samo zacetno okno vnaprej
        G.pocakaj_mir(b)
        self.assertLessEqual(o.poslano - zacetek, 4 * 760 * 1024, "skok: segment + zacetno okno (1 MiB)")
        zacetek = o.poslano
        preberi_vse(b, 0, 8 * MiB)  # zaporedno 8 MiB: okno zraste na 16 MiB, ne vec
        G.pocakaj_mir(b)
        self.assertLessEqual(o.poslano - zacetek, (8 + 16 + 2) * MiB * 1.03)

    def test_skok_zavrze_cakajoca_branja(self):
        film = G.Leno(64 * MiB, 2)
        o = objavi(("Film.mkv", film))
        pocasi = threading.Event()

        def telo(mid):
            pocasi.wait(0.05)
            return o.telo(mid)
        vir, _ = B.pripravi(NZ.razcleni(o.nzb()), o.telo)
        b = B.Bralnik(telo, vir, B.Profil(16 * MiB, MiB, 64 * MiB, 2))
        self.bralniki.append(b)
        preberi_vse(b, 0, 8 * MiB)  # okno 16 MiB: ~23 segmentov caka
        prej = o.poslanih
        b.beri(50 * MiB, 1000)
        G.pocakaj_mir(b)
        self.assertLess(o.poslanih - prej, 10, "cakajoca branja pred skokom so zavrzena")

    def test_luknje(self):
        film = G.Leno(5 * 700 * 1024, 6)
        o = objavi(("Film.mkv", film))
        manjka = o.datoteke[0][2][2]  # 3. segment
        b = self.bralnik(o, izpusti=(manjka,))
        self.assertEqual(preberi_vse(b, 0, 1000), film.beri(0, 1000))
        with self.assertRaises(T.NapakaToka) as e:
            b.beri(2 * 700 * 1024 + 5, 10)
        self.assertEqual(e.exception.izid, T.LUKNJA)
        o.manjka.add(o.datoteke[0][2][3])  # ponudnik clanek ima v NZB, a ga je odstranil (430)
        with self.assertRaises(T.NapakaToka) as e:
            b.beri(3 * 700 * 1024 + 5, 10)
        self.assertEqual(e.exception.izid, T.LUKNJA)
        self.assertEqual(preberi_vse(b, 4 * 700 * 1024, 100), film.beri(4 * 700 * 1024, 100))

    def test_zapri_ne_caka_na_branje_v_teku(self):
        o = objavi(("Film.mkv", G.Leno(4 * MiB, 1)))
        vir, _ = B.pripravi(NZ.razcleni(o.nzb()), o.telo)
        sprosti = threading.Event()
        b = B.Bralnik(lambda mid: (sprosti.wait(10), o.telo(mid))[1], vir)
        izid = []
        t = threading.Thread(target=lambda: izid.append(self._napaka(lambda: b.beri(2 * MiB, 10))))
        t.start()
        time.sleep(0.1)
        zacetek = time.monotonic()
        b.zapri()
        self.assertLess(time.monotonic() - zacetek, 0.5, "zapri ne caka na zahtevo v teku")
        with self.assertRaises(T.NapakaToka) as e:
            b.beri(0, 10)
        self.assertEqual(e.exception.izid, T.ZAPRTO)
        sprosti.set()
        t.join(5)
        self.assertFalse(t.is_alive())

    def _napaka(self, fn):
        try:
            fn()
        except T.NapakaToka as e:
            return e.izid
        return None

    def test_lru_meja(self):
        o = objavi(("Film.mkv", G.Leno(40 * MiB, 5)))
        profil = B.Profil(2 * MiB, MiB, 6 * MiB, 2)
        b = self.bralnik(o, profil)
        preberi_vse(b)
        G.pocakaj_mir(b)
        self.assertLessEqual(b._lru_bajtov, b._lru_meja)
        self.assertLess(b._lru_meja, 40 * MiB)

    def test_promet_ogleda_najvec_1_5x(self):
        # 60 s ogleda pri 5,2 Mbit/s (kot Sintel v prototipu) iz 200 MiB filma; meritev s 700 MiB in NNTP je v
        # tools/meri_usenet_tok.py.
        for profil in ("namizje", "tv"):
            o = objavi(("Film.mkv", G.Leno(200 * MiB, 12)))
            b = self.bralnik(o, B.PROFILI[profil])
            pogledano = G.ogled(b.beri, b.vir.velikost, 5.2e6)
            G.pocakaj_mir(b)
            self.assertLessEqual(o.poslano / pogledano, 1.5, profil)

    def test_repr_brez_id(self):
        o = objavi(("Film.mkv", G.Leno(MiB, 1)))
        b = self.bralnik(o)
        self.assertNotIn("primer.invalid", repr(b) + repr(b.vir))


# ---------------------------------------------------------------------- streznik HTTP Range (korak 2, del 4)

import http.client  # noqa: E402
import io  # noqa: E402
import logging  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import tempfile  # noqa: E402
import urllib.request  # noqa: E402
from contextlib import redirect_stderr  # noqa: E402
from unittest import mock  # noqa: E402

from core import usenet_nntp as N, usenet_streznik as S  # noqa: E402


class Obseg(unittest.TestCase):
    def test_obseg(self):
        n = 1000
        self.assertEqual(S.obseg(None, n), None)
        self.assertEqual(S.obseg("bytes=0-99", n), (0, 99))
        self.assertEqual(S.obseg("bytes=500-", n), (500, 999))
        self.assertEqual(S.obseg("bytes=-100", n), (900, 999))
        self.assertEqual(S.obseg("bytes=-5000", n), (0, 999))
        self.assertEqual(S.obseg("bytes=990-5000", n), (990, 999))
        self.assertEqual(S.obseg("bytes=1000-", n), S.NI_OBSEGA)
        self.assertEqual(S.obseg("bytes=-0", n), S.NI_OBSEGA)
        for prezri in ("bytes=0-1,5-6", "items=0-1", "bytes=5-1", "bytes=-", "bytes=a-b", "bytes=0-1\r\nX: y"):
            self.assertIsNone(S.obseg(prezri, n), prezri)

    def test_ime_poti(self):
        self.assertEqual(S.ime_poti("Film.2026.1080p.mkv"), "video.mkv")
        self.assertEqual(S.ime_poti("a.MP4"), "video.mp4")
        self.assertEqual(S.ime_poti("kljuc=abc123.exe"), "video.bin")
        self.assertEqual(S.ime_poti(None), "video.bin")


class Streznik(unittest.TestCase):
    def setUp(self):
        self.film = G.Leno(3 * MiB + 17, 21)
        self.o = objavi(("Film.Tajno.Ime.mkv", self.film))
        vir, _ = B.pripravi(NZ.razcleni(self.o.nzb()), self.o.telo)
        self.br = B.Bralnik(self.o.telo, vir)
        self.s = S.Streznik(self.br)
        self.addCleanup(self.s.zapri)

    def zahteva(self, metoda="GET", pot=None, glave=None):
        c = http.client.HTTPConnection("127.0.0.1", self.s.vrata, timeout=10)
        self.addCleanup(c.close)
        c.request(metoda, pot or self.s.url.split(str(self.s.vrata), 1)[1], headers=glave or {})
        r = c.getresponse()
        return r, r.read()

    def test_naslov_brez_skrivnosti(self):
        self.assertTrue(self.s.url.startswith("http://127.0.0.1:%d/" % self.s.vrata))
        self.assertGreaterEqual(len(self.s.zeton), 40)
        for zasebno in ("primer.invalid", "Tajno", "apikey", "nzb"):
            self.assertNotIn(zasebno, self.s.url)
        self.assertNotIn(self.s.zeton, repr(self.s))
        self.assertEqual(self.s._srv.socket.getsockname()[0], "127.0.0.1")
        with self.assertRaises(ValueError):
            S.Streznik(self.br, gostitelj="0.0.0.0")

    def test_range_head_416(self):
        r, b = self.zahteva(glave={"Range": "bytes=100-199"})
        self.assertEqual((r.status, r.getheader("Content-Range"), r.getheader("Content-Length")),
                         (206, "bytes 100-199/%d" % self.film.velikost, "100"))
        self.assertEqual(b, self.film.beri(100, 100))
        r, b = self.zahteva(glave={"Range": "bytes=-10"})
        self.assertEqual((r.status, b), (206, self.film.beri(self.film.velikost - 10, 10)))
        r, b = self.zahteva()
        self.assertEqual((r.status, r.getheader("Accept-Ranges"), b), (200, "bytes", self.film.beri(0, 10 ** 9)))
        r, b = self.zahteva("HEAD", glave={"Range": "bytes=0-"})
        self.assertEqual((r.status, r.getheader("Content-Length"), b), (206, str(self.film.velikost), b""))
        r, b = self.zahteva(glave={"Range": "bytes=%d-" % self.film.velikost})
        self.assertEqual((r.status, r.getheader("Content-Range")), (416, "bytes */%d" % self.film.velikost))
        r, _ = self.zahteva(glave={"Range": "bytes=0-1,4-5"})
        self.assertEqual(r.status, 200)

    def test_zavrnjeno(self):
        pravi = self.s.url.split(str(self.s.vrata), 1)[1]
        drug = "/" + "A" * len(self.s.zeton) + "/" + self.s.pot
        for pot in (drug, "/", pravi + "/x", "/" + self.s.zeton, pravi.replace("video.mkv", "video.mp4")):
            self.assertEqual(self.zahteva(pot=pot)[0].status, 404, pot)
        self.assertEqual(self.zahteva(glave={"Host": "zlo.example:%d" % self.s.vrata})[0].status, 404)
        self.assertEqual(self.zahteva("POST")[0].status, 405)

    def test_brez_dnevnika_zetona(self):
        napaka, zajem = io.StringIO(), []
        h = logging.Handler()
        h.emit = lambda z: zajem.append(z.getMessage())
        logging.getLogger("safeer.usenet").addHandler(h)
        self.addCleanup(logging.getLogger("safeer.usenet").removeHandler, h)
        with redirect_stderr(napaka):
            self.zahteva(glave={"Range": "bytes=0-9"})
            self.zahteva(pot="/napacno")
        self.assertNotIn(self.s.zeton, napaka.getvalue() + " ".join(zajem))

    def test_prekinjen_odjemalec_in_zapiranje(self):
        sock = socket.create_connection(("127.0.0.1", self.s.vrata))
        sock.sendall(("GET %s HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n\r\n"
                      % (self.s.url.split(str(self.s.vrata), 1)[1], self.s.vrata)).encode())
        sock.recv(1000)
        sock.close()  # predvajalnik zapre sredi telesa
        r, b = self.zahteva(glave={"Range": "bytes=0-9"})
        self.assertEqual(b, self.film.beri(0, 10))
        self.s.zapri()
        self.assertTrue(self.br.zaprt, "konec predvajanja zapre tudi bralnik")
        with self.assertRaises(OSError):
            urllib.request.urlopen(self.s.url, timeout=2)

    def test_samodejno_zapiranje_ob_nedejavnosti(self):
        konec = threading.Event()
        vir, _ = B.pripravi(NZ.razcleni(self.o.nzb()), self.o.telo)
        br = B.Bralnik(self.o.telo, vir)
        s = S.Streznik(br, nedejavnost_s=0.3, ob_koncu=konec.set)
        self.addCleanup(s.zapri)
        self.assertTrue(konec.wait(5))
        self.assertTrue(s.zaprt and br.zaprt)


# ---------------------------------------------------------------------- konec do konca (korak 2, del 6)

try:
    import test_usenet_nntp as TN
except ImportError:  # pragma: no cover
    TN = None


@unittest.skipUnless(TN is not None and shutil.which("openssl"), "brez openssl ni laznega streznika NNTP")
class KonecDoKonca(unittest.TestCase):
    """NZB -> Bazen (TLS, lazni streznik iz test_usenet_nntp) -> bralnik -> streznik Range -> bajti kot izvirnik."""

    @classmethod
    def setUpClass(cls):
        cls._mapa = tempfile.TemporaryDirectory()
        TN.ustvari_potrdila(cls._mapa.name)

    @classmethod
    def tearDownClass(cls):
        cls._mapa.cleanup()

    def setUp(self):
        N._ZAVRNJENI.clear()
        self.addCleanup(N._ZAVRNJENI.clear)
        if hasattr(N, "nastavi_shrambo_zapaha"):
            N.nastavi_shrambo_zapaha(os.path.join(self._mapa.name, "zapah-%d" % id(self)))
            self.addCleanup(N.nastavi_shrambo_zapaha, None)

    def tek(self, objava):
        with mock.patch.object(TN, "CLANKI", objava):
            srv = TN.LazniStreznik(self._mapa.name)
            self.addCleanup(srv.ustavi)
            bazen = N.Bazen("127.0.0.1", srv.vrata, uporabnik=TN.UPORABNIK, geslo=TN.GESLO, povezav=4,
                            kontekst=__import__("ssl").create_default_context(cafile=os.path.join(self._mapa.name, "ca.pem")),
                            rok_povezave=5.0, rok=10.0)
            self.addCleanup(bazen.zapri)
            nzb = NZ.razcleni(objava.nzb())
            self.assertEqual(B.preveri_izdajo(nzb, bazen.telo), R.OK)
            vir, _ = B.pripravi(nzb, bazen.telo)
            br = B.Bralnik(bazen.telo, vir, B.PROFILI["namizje"])
            s = S.Streznik(br)
            self.addCleanup(s.zapri)
            film = objava.film
            for delez in (0.0, 0.5, 0.9):
                od = int(film.velikost * delez)
                req = urllib.request.Request(s.url, headers={"Range": "bytes=%d-%d" % (od, od + 1_500_000)})
                with urllib.request.urlopen(req, timeout=20) as r:
                    self.assertEqual(r.status, 206)
                    self.assertEqual(r.read(), film.beri(od, 1_500_001), delez)
            s.zapri()
            self.assertTrue(br.zaprt)
            self.assertNotIn(TN.GESLO, s.url)

    def test_gola_datoteka(self):
        o = objavi(("Film.mkv", G.Leno(12 * MiB + 3, 31)))
        o.film = o.datoteke[0][1]
        self.tek(o)

    def test_rar_store(self):
        film = G.Leno(12 * MiB + 3, 32)
        o = objavi(*[("Film.part%d.rar" % (i + 1), z) for i, z in enumerate(G.zvezki_leno(5, "Film.mkv", film, 5 * MiB))])
        o.film = film
        self.tek(o)


if __name__ == "__main__":
    unittest.main()
