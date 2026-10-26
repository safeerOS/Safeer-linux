"""Prenos samo spremenjenih kosov (core/link_delta, core/link_nadaljuj, /kosi/ na strezniku datotek).

»Nadaljuj na drugi napravi« (lastnik, 14. 10. 2026): datoteko ustvaris na racunalniku A, urejas na B in nato spet na A -
po Safeer Linku gre samo, kar se je spremenilo.
"""
import hashlib
import http.client
import io
import json
import os
import random
import shutil
import ssl
import tempfile
import tracemalloc
import unittest
from unittest import mock

from core import link_datoteke, link_delta, link_nadaljuj, link_pretok


def _nakljucno(n, seme=1):
    return random.Random(seme).randbytes(n)


class Razrez(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.podatki = _nakljucno(5 * 1024 * 1024)
        cls.povprecno = link_delta.izberi_povprecno(len(cls.podatki))
        cls.opis = link_delta.manifest_toka(io.BytesIO(cls.podatki).read, hitro=False, povprecno=cls.povprecno)

    def test_opis_je_pravilen(self):
        m = self.opis
        self.assertTrue(link_delta.preveri_manifest(m))
        self.assertEqual(m["velikost"], len(self.podatki))
        self.assertEqual(m["sha256"], hashlib.sha256(self.podatki).hexdigest())
        naslednji = 0
        for i, (odmik, dolzina, h) in enumerate(m["kosi"]):
            self.assertEqual(odmik, naslednji)
            self.assertLessEqual(dolzina, self.povprecno * 4)
            if i < len(m["kosi"]) - 1:
                self.assertGreaterEqual(dolzina, self.povprecno // 4)
            self.assertEqual(h, hashlib.sha256(self.podatki[odmik:odmik + dolzina]).hexdigest())
            naslednji += dolzina
        povprecje = len(self.podatki) / len(m["kosi"])
        self.assertEqual((self.povprecno, m["povprecno"], m["alg"]), (32 * 1024, 32 * 1024, "gear32-okno32-v2"))
        self.assertTrue(self.povprecno * 0.6 < povprecje < self.povprecno * 2, povprecje)

    def test_opis_datoteke_je_opis_toka(self):
        with tempfile.NamedTemporaryFile(delete=False) as d:
            d.write(self.podatki)
        self.addCleanup(os.remove, d.name)
        self.assertEqual(link_delta.manifest(d.name, hitro=False), self.opis)

    def test_vstavljanje_premakne_samo_kose_okoli_sebe(self):
        sredina = len(self.podatki) // 2
        novi = self.podatki[:sredina] + b"0123456789" + self.podatki[sredina:]
        m2 = link_delta.manifest_toka(io.BytesIO(novi).read, hitro=False, povprecno=self.povprecno)
        o = link_delta.ocena(m2, [self.opis])
        delez = o["kosov_lokalno"] / o["kosov"]
        print("\n[delta] vstavljenih 10 B v 5 MiB: kosov %d, iz prejsnje kopije %d (%.1f %%), prenesti %d B v %d zahtevah"
              % (o["kosov"], o["kosov_lokalno"], delez * 100, o["podatki"], o["zahtev"]))
        self.assertGreater(delez, 0.95)
        self.assertLess(o["podatki"], 3 * 4 * self.povprecno)
        self.assertEqual(o["zahtev"], 1)

    def test_numpy_da_iste_meje(self):
        if link_delta._np is None:
            self.skipTest("numpy ni namescen")
        self.assertEqual(link_delta.manifest_toka(io.BytesIO(self.podatki).read, hitro=True, povprecno=self.povprecno),
                         self.opis)
        # Vsa povprecja: numpy in cisti Python rezeta enako.
        podatki = self.podatki[:1024 * 1024] + bytes(100_000) + self.podatki[:50_000] * 3
        for p in (4096, 8192, 16384, 32768, 65536):
            with self.subTest(povprecno=p):
                self.assertEqual(link_delta.manifest_toka(io.BytesIO(podatki).read, hitro=True, povprecno=p),
                                 link_delta.manifest_toka(io.BytesIO(podatki).read, hitro=False, povprecno=p))

    def test_parametri_po_velikosti(self):
        z = link_delta.izberi_povprecno
        self.assertEqual([z(0), z(100), z(528 * 1024), z(1024 * 1024), z(5 * 1024 * 1024), z(10 ** 9)],
                         [4096, 4096, 4096, 8192, 32768, 65536])
        for p in (4096, 8192, 16384, 32768, 65536):
            par = link_delta.Parametri(p)
            biti = p.bit_length() - 1
            self.assertEqual((par.najmanj, par.najvec), (p // 4, p * 4))
            self.assertEqual(bin(par.maska_stroga).count("1"), biti + 2)
            self.assertEqual(bin(par.maska_blaga).count("1"), biti - 2)
            self.assertEqual(par.maska_stroga >> 31, 1)            # zgornji biti (odvisni od celega okna)
        # v1 = stalni parametri 64 KiB: enaki kot v2 s povprecjem 64 KiB
        v1 = link_delta.Parametri(65536)
        self.assertEqual((v1.maska_stroga, v1.maska_blaga), (((1 << 18) - 1) << 14, ((1 << 14) - 1) << 18))
        for slab in (3000, 6000, 131072):
            with self.assertRaises(ValueError):
                link_delta.Parametri(slab)

    def test_vsak_razrez_se_po_vstavljanju_ujame(self):
        podatki = self.podatki[:2 * 1024 * 1024]
        novi = podatki[:1_000_000] + b"x" * 10 + podatki[1_000_000:]
        for p in (4096, 16384, 65536):
            with self.subTest(povprecno=p):
                m1 = link_delta.manifest_toka(io.BytesIO(podatki).read, hitro=False, povprecno=p)
                m2 = link_delta.manifest_toka(io.BytesIO(novi).read, hitro=False, povprecno=p)
                o = link_delta.ocena(m2, [m1])
                self.assertLess(o["podatki"], 3 * 4 * p)
                povprecje = len(podatki) / len(m1["kosi"])
                self.assertTrue(p * 0.6 < povprecje < p * 2, (p, povprecje))

    def test_enolicni_podatki(self):
        # Same nicle: okno je povsod enako - meje so vedno na isti dolzini (najvec ali najmanj), nikoli pa ne zmanjka.
        m = link_delta.manifest_toka(io.BytesIO(bytes(1_000_000)).read, hitro=False)
        self.assertTrue(link_delta.preveri_manifest(m))
        self.assertEqual(link_delta.manifest_toka(io.BytesIO(b"").read)["kosi"], [])
        self.assertEqual(link_delta.manifest_toka(io.BytesIO(b"abc").read)["kosi"][0][1], 3)

    def test_omejen_pomnilnik(self):
        # 64 MiB tok, ki ga nihce ne hrani: razrez drzi v pomnilniku le nekaj blokov. Iskanje meje je tu nadomesceno
        # (cisti Python pod tracemalloc bi tekel minute); preverja se hranjenje toka, ki je enako v obeh nacinih.
        vir = random.Random(5)
        ostane = [64 * 1024 * 1024]

        def beri(n):
            n = min(n, ostane[0])
            ostane[0] -= n
            return vir.randbytes(n)
        tracemalloc.start()
        try:
            with mock.patch.object(link_delta, "_dolzina_kosa", lambda buf, s, n, hitro, par: min(n, 100_000)):
                m = link_delta.manifest_toka(beri, hitro=False)
            _, vrh = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(m["velikost"], 64 * 1024 * 1024)
        self.assertLess(vrh, 8 * 1024 * 1024, vrh)

    def test_branje_naprej_je_omejeno(self):
        # Pravi razrez: od toka nikoli ne preberemo vec kot NAJVEC + dva bloka pred koncem zadnjega kosa.
        tok = io.BytesIO(_nakljucno(4 * 1024 * 1024, 6))
        for odmik, podatki in link_delta.razrezi_tok(tok.read, hitro=False):
            self.assertLessEqual(tok.tell() - (odmik + len(podatki)), link_delta.NAJVEC + 2 * link_delta.BLOK)


class Obsegi(unittest.TestCase):
    def test_zdruzevanje(self):
        z = link_delta.zdruzi_obsege
        self.assertEqual(z([(0, 10), (10, 5), (30, 5), (35, 1)]), [(0, 15), (30, 6)])
        self.assertEqual(z([(30, 5), (0, 10), (10, 5)]), [(0, 15), (30, 5)])
        self.assertEqual(z([(0, 6), (6, 6), (12, 6)], najvec=12), [(0, 12), (12, 6)])
        self.assertEqual(z([(0, 20)], najvec=12), [(0, 20)])
        self.assertEqual(z([]), [])


class Sestava(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-delta-")
        self.addCleanup(shutil.rmtree, self.mapa, True)
        self.stara = _nakljucno(3 * 1024 * 1024, 2)
        sredina = len(self.stara) // 3
        self.nova = self.stara[:sredina] + b"spremenjeno" * 50 + self.stara[sredina + 4000:] + b"konec"
        self.pot_stare = os.path.join(self.mapa, "stara")
        with open(self.pot_stare, "wb") as d:
            d.write(self.stara)
        self.opis = link_delta.manifest_toka(io.BytesIO(self.nova).read)
        self.zahteve = []

    def _prenesi(self, odmik, dolzina):
        self.zahteve.append((odmik, dolzina))
        return self.nova[odmik:odmik + dolzina]

    def test_sestavi_iz_lokalnih_kosov(self):
        cilj = os.path.join(self.mapa, "pod", "nova")
        m = link_delta.sestavi(self.opis, [self.pot_stare], self._prenesi, cilj)
        with open(cilj, "rb") as d:
            self.assertEqual(d.read(), self.nova)
        self.assertFalse(m["polno"])
        self.assertEqual(m["podatki"] + m["iz_lokalnih"], len(self.nova))
        self.assertLess(m["podatki"], len(self.nova) // 5)
        self.assertEqual(m["zahtev"], len(self.zahteve))
        self.assertLessEqual(m["zahtev"], 3)          # sosednji manjkajoci kosi gredo v eno zahtevo
        self.assertEqual([f for f in os.listdir(os.path.dirname(cilj)) if f.endswith(".part")], [])

    def test_pokvarjen_kos_pomeni_cel_prenos(self):
        cilj = os.path.join(self.mapa, "nova")
        prvic = [True]

        def pokvarjeno(odmik, dolzina):
            p = bytearray(self._prenesi(odmik, dolzina))
            if prvic[0]:
                prvic[0] = False
                p[0] ^= 0xFF
            return bytes(p)
        m = link_delta.sestavi(self.opis, [self.pot_stare], pokvarjeno, cilj)
        self.assertTrue(m["polno"])
        self.assertEqual(m["razlog"], "kos_se_ne_ujema")
        with open(cilj, "rb") as d:
            self.assertEqual(d.read(), self.nova)

    def test_lokalni_vir_se_je_spremenil(self):
        # Opis lokalne datoteke je star (datoteka je medtem drugacna): kos se preveri in prenese z naprave.
        star_opis = link_delta.manifest(self.pot_stare)
        with open(self.pot_stare, "r+b") as d:
            d.seek(100)
            d.write(b"X" * 100)
        cilj = os.path.join(self.mapa, "nova")
        m = link_delta.sestavi(self.opis, [(self.pot_stare, star_opis)], self._prenesi, cilj)
        self.assertFalse(m["polno"])
        with open(cilj, "rb") as d:
            self.assertEqual(d.read(), self.nova)

    def test_datoteka_se_med_prenosom_spreminja(self):
        cilj = os.path.join(self.mapa, "nova")
        with open(cilj, "wb") as d:
            d.write(b"prej")
        with self.assertRaises(link_delta.NapakaDelte):
            link_delta.sestavi(self.opis, [], lambda o, d: b"\0" * d, cilj)
        with open(cilj, "rb") as d:
            self.assertEqual(d.read(), b"prej")      # cilj ostane, kot je bil
        self.assertEqual([f for f in os.listdir(self.mapa) if f.endswith(".part")], [])

    def test_opis_v1_starejse_naprave(self):
        # Starejsa naprava da opis v1 (brez "povprecno", stalno 64 KiB): lokalne kose razrezemo z istimi parametri.
        m = link_delta.manifest_toka(io.BytesIO(self.nova).read, povprecno=65536)
        del m["povprecno"]
        m["alg"] = "gear32-okno32-v1"
        self.assertTrue(link_delta.preveri_manifest(m))
        lokalni_v2 = (self.pot_stare, link_delta.manifest(self.pot_stare))      # drugo povprecje: izracuna se znova
        self.assertNotEqual(lokalni_v2[1]["povprecno"], 65536)
        cilj = os.path.join(self.mapa, "nova")
        r = link_delta.sestavi(m, [lokalni_v2], self._prenesi, cilj)
        self.assertFalse(r["polno"])
        self.assertGreater(r["iz_lokalnih"], len(self.nova) // 2)
        with open(cilj, "rb") as d:
            self.assertEqual(d.read(), self.nova)

    def test_neznan_razrez(self):
        m = dict(self.opis, alg="gear64-v9")
        self.assertFalse(link_delta.preveri_manifest(m))
        self.assertFalse(link_delta.preveri_manifest(dict(self.opis, povprecno=3000)))
        with self.assertRaises(link_delta.NapakaDelte):
            link_delta.sestavi(m, [self.pot_stare], self._prenesi, os.path.join(self.mapa, "x"))

    def test_zip_s_ploscicami_kot_pcraft(self):
        # PhotoCraft .pcraft: ZIP brez stiskanja, ploscice z imeni po vsebini, spredaj predogled, zadaj manifest.json.
        # Druga razlicica: nov predogled (50 KB), ena nova ploscica na sredini, spremenjen manifest.json.
        import zipfile
        rnd = random.Random(42)
        ploscice = [rnd.randbytes(rnd.randint(300, 10_000)) for _ in range(120)]

        # Stalen cas v glavah ZIP: writestr(ime, ...) zapise trenutni cas (DOS, 2 s) v lokalno in centralno glavo vsakega
        # vnosa. Ce je med pisanjem v1 in v2 minila meja dveh sekund (pocasen CI), so se glave nespremenjenih ploscic
        # razlikovale in kosi s 4 KiB okoli njih so bili novi (hitra-vrata (5): 53,5 %). Nespremenjena ploscica = enaki bajti.
        cas = (2026, 10, 14, 12, 0, 0)

        def zip_(pot, predogled, ploscice_, opis):
            with zipfile.ZipFile(pot, "w", zipfile.ZIP_STORED) as z:
                z.writestr(zipfile.ZipInfo("preview.png", cas), predogled)
                for p in ploscice_:
                    z.writestr(zipfile.ZipInfo("tiles/%s.zst" % hashlib.sha256(p).hexdigest(), cas), p)
                z.writestr(zipfile.ZipInfo("manifest.json", cas), opis)
        v1, v2 = os.path.join(self.mapa, "v1.pcraft"), os.path.join(self.mapa, "v2.pcraft")
        zip_(v1, rnd.randbytes(50_000), ploscice, json.dumps({"plasti": 3, "ploscice": len(ploscice)}))
        nove = ploscice[:60] + [rnd.randbytes(4000)] + ploscice[60:]
        zip_(v2, rnd.randbytes(50_000), nove, json.dumps({"plasti": 4, "ploscice": len(nove)}))
        with open(v2, "rb") as d:
            vsebina_v2 = d.read()
        m2 = link_delta.manifest(v2)                         # kot streznik: povprecje po velikosti
        cilj = os.path.join(self.mapa, "sestavljena.pcraft")
        r = link_delta.sestavi(m2, [v1], lambda o, n: vsebina_v2[o:o + n], cilj)
        with open(cilj, "rb") as d:
            self.assertEqual(d.read(), vsebina_v2)
        opis_bajtov = len(json.dumps(m2, separators=(",", ":")))
        delez = (r["podatki"] + opis_bajtov) / len(vsebina_v2)
        print("\n[delta] .pcraft-podoben ZIP %d B, povprecje %d B: podatki %d B + opis %d B = %.1f %% datoteke, %d zahtev"
              % (len(vsebina_v2), m2["povprecno"], r["podatki"], opis_bajtov, delez * 100, r["zahtev"]))
        self.assertEqual(m2["povprecno"], 4096)
        self.assertLess(delez, 0.35)
        # Za primerjavo: stalno povprecje 64 KiB (v1) prenese skoraj vse.
        m_staro = link_delta.manifest(v2, povprecno=65536)
        o = link_delta.ocena(m_staro, [link_delta.manifest(v1, povprecno=65536)])
        print("[delta] isti ZIP s stalnimi 64 KiB kosi (v1): podatki %d B = %.1f %% datoteke"
              % (o["podatki"], 100.0 * o["podatki"] / len(vsebina_v2)))

    def test_napacen_opis(self):
        slab = dict(self.opis, kosi=self.opis["kosi"][1:])
        with self.assertRaises(link_delta.NapakaDelte):
            link_delta.sestavi(slab, [], self._prenesi, os.path.join(self.mapa, "x"))
        self.assertFalse(link_delta.preveri_manifest({"v": 1, "velikost": 1, "sha256": "x", "kosi": []}))


class _Pretok(link_pretok.LokalniPretok):
    """Neposredna pot do preizkusnega streznika (odtis je znan)."""

    def __init__(self, odtis):
        super().__init__(potrdilo=lambda naslov, rok: (odtis, ""))


class Streznik(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-kosi-")
        self.addCleanup(shutil.rmtree, self.mapa, True)
        self.deljena = os.path.join(self.mapa, "Slike")
        os.makedirs(self.deljena)
        self.pot = os.path.join(self.deljena, "risba.pcraft")
        self.vsebina = _nakljucno(1024 * 1024, 3)
        with open(self.pot, "wb") as d:
            d.write(self.vsebina)
        self.d = link_datoteke.Datoteke([self.deljena], tls_mapa=os.path.join(self.mapa, "tls"))
        self.addCleanup(self.d.ustavi)
        # Naprava ima datoteke odprte - neodvisno od zapisa dovoljenj na disku, ki ga pustijo drugi preizkusi v istem
        # procesu (CI: unittest v enem procesu, 14. 10. 2026 je tu padlo 6 preizkusov z 401).
        self.d.streznik.sme = lambda naprava, zmoznost: True
        self.d.streznik.umaknjena = lambda naprava: False
        with link_datoteke._opisi_kljuc:
            link_datoteke._opisi.clear()
        self.streznik = self.d.seznam("share:0:", "racunalnik-b")["server"]
        # Naslov v domacem omrezju je odvisen od okolja preizkusa: streznik poslusa na vseh, mi gremo na 127.0.0.1.
        self.streznik["base_url"] = "https://127.0.0.1:%d" % self.d.streznik.vrata

    def _zahteva(self, pot, glave=None, metoda="GET"):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        p = http.client.HTTPSConnection("127.0.0.1", self.d.streznik.vrata, context=ctx, timeout=30)
        p.request(metoda, pot, headers=glave or {})
        o = p.getresponse()
        telo = o.read()
        p.close()
        return o.status, telo

    def test_opis_zahteva_zeton_in_pravico_datotek(self):
        z = {"X-Safeer-Token": self.streznik["token"]}
        st, telo = self._zahteva("/kosi/share:0:risba.pcraft", z)
        self.assertEqual(st, 200)
        m = json.loads(telo)
        self.assertTrue(link_delta.preveri_manifest(m))
        self.assertEqual(m["sha256"], hashlib.sha256(self.vsebina).hexdigest())
        # brez zetona, z napacnim, zeton v naslovu: nic
        self.assertEqual(self._zahteva("/kosi/share:0:risba.pcraft")[0], 401)
        self.assertEqual(self._zahteva("/kosi/share:0:risba.pcraft", {"X-Safeer-Token": "x"})[0], 401)
        self.assertEqual(self._zahteva("/kosi/share:0:risba.pcraft?t=" + self.streznik["token"])[0], 401)
        # pot ven iz deljene mape
        self.assertEqual(self._zahteva("/kosi/share:0:../../etc/passwd", z)[0], 404)
        # naprava, ki ji je uporabnik vzel datoteke (zmoznost "d"): zavrnjeno, kot pri prenosu datoteke
        self.d.streznik.sme = lambda naprava, zmoznost: False
        self.assertEqual(self._zahteva("/kosi/share:0:risba.pcraft", z)[0], 401)
        self.assertEqual(self._zahteva("/d/share:0:risba.pcraft", z)[0], 401)
        # ... razen datoteke, ki ji jo je uporabnik tega racunalnika izrecno poslal
        self.d.streznik.dovoli_izrecno("racunalnik-b", "share:0:risba.pcraft")
        self.assertEqual(self._zahteva("/kosi/share:0:risba.pcraft", z)[0], 200)

    def test_opis_prek_huba_je_ista_pot(self):
        self.assertTrue(link_datoteke.je_pot_streznika("/kosi/share:0:x"))

    def test_predpomnilnik_opisov(self):
        prvi = link_datoteke.opis_kosov(self.pot)
        self.assertIs(link_datoteke.opis_kosov(self.pot), prvi)        # isti opis iz pomnilnika
        with open(self.pot, "r+b") as d:                                  # ista velikost, nova vsebina in cas
            d.write(b"Z" * 10)
        s = os.stat(self.pot)
        os.utime(self.pot, ns=(s.st_atime_ns, s.st_mtime_ns + 5_000_000_000))
        drugi = link_datoteke.opis_kosov(self.pot)
        self.assertIsNot(drugi, prvi)
        self.assertEqual(json.loads(drugi)["sha256"], hashlib.sha256(b"Z" * 10 + self.vsebina[10:]).hexdigest())
        # najvec NAJVEC_OPISOV opisov
        for i in range(link_datoteke.NAJVEC_OPISOV + 5):
            p = os.path.join(self.deljena, "f%d" % i)
            with open(p, "wb") as d:
                d.write(b"%d" % i)
            link_datoteke.opis_kosov(p)
        self.assertLessEqual(len(link_datoteke._opisi), link_datoteke.NAJVEC_OPISOV)

    def _nadaljuj(self, moje_ime="", deljene=(), pot_imen=("Slike", "risba.pcraft"), oznaka="share:0:risba.pcraft",
                  delo=None):
        self.odprte = []
        return link_nadaljuj.nadaljuj_tukaj(
            self.streznik, "", oznaka, "n-aaaa", "Racunalnik A", list(pot_imen), moje_ime=moje_ime,
            odpri=lambda p: self.odprte.append(p) or True, pretok=_Pretok(self.streznik["fp"]),
            mapa_dela=delo or os.path.join(self.mapa, "delo"), mapa_predpomnilnika=os.path.join(self.mapa, "pp"),
            deljene=list(deljene))

    def test_nadaljuj_tukaj_prenese_samo_spremembe(self):
        izid = self._nadaljuj()
        self.assertTrue(izid["ok"], izid)
        cilj = os.path.join(self.mapa, "delo", "Racunalnik A", "Slike", "risba.pcraft")
        self.assertEqual(izid["pot"], cilj)
        self.assertEqual(self.odprte, [cilj])
        with open(cilj, "rb") as d:
            self.assertEqual(d.read(), self.vsebina)
        self.assertFalse(izid["delta"])                        # prvic ni cesa ponovno uporabiti: brez opisa
        self.assertEqual((izid["razlog"], izid["opis_bajtov"]), ("prvi_prenos", 0))
        self.assertEqual(izid["podatki"], len(self.vsebina))
        # Na A se datoteka spremeni (vstavljeno na sredini): na B gre samo sprememba.
        nova = self.vsebina[:500_000] + b"nova poteza" + self.vsebina[500_000:]
        with open(self.pot, "wb") as d:
            d.write(nova)
        izid = self._nadaljuj()
        self.assertTrue(izid["ok"], izid)
        with open(cilj, "rb") as d:
            self.assertEqual(d.read(), nova)
        self.assertLess(izid["podatki"], 300 * 1024)
        self.assertGreater(izid["iz_lokalnih"], len(nova) * 0.7)
        self.assertTrue(izid["delta"])
        self.assertEqual(izid["preneseno"], izid["podatki"] + izid["opis_bajtov"])
        self.assertFalse(izid["prejsnja_v_smeteh"])
        print("\n[delta] nadaljuj tukaj po vstavljanju: %d B od %d B po omrezju (opis %d B), %d zahtev, %.3f s"
              % (izid["preneseno"], izid["velikost"], izid["opis_bajtov"], izid["zahtev"], izid["cas_s"]))

    def test_urejena_delovna_kopija_gre_v_smeti(self):
        self.assertTrue(self._nadaljuj()["ok"])
        cilj = os.path.join(self.mapa, "delo", "Racunalnik A", "Slike", "risba.pcraft")
        with open(cilj, "ab") as d:
            d.write(b"lokalna sprememba")
        with open(self.pot, "ab") as d:
            d.write(b"sprememba na A")
        v_smeti = []
        with mock.patch("core.link_urejanje.v_smeti", side_effect=lambda p: (v_smeti.append(open(p, "rb").read()), os.remove(p))):
            izid = self._nadaljuj()
        self.assertTrue(izid["ok"], izid)
        self.assertTrue(izid["prejsnja_v_smeteh"])
        self.assertTrue(v_smeti[0].endswith(b"lokalna sprememba"))
        with open(cilj, "rb") as d:
            self.assertTrue(d.read().endswith(b"sprememba na A"))
        # Nespremenjena delovna kopija se zamenja brez Smeti.
        with open(self.pot, "ab") as d:
            d.write(b"!")
        with mock.patch("core.link_urejanje.v_smeti", side_effect=AssertionError("ne v smeti")):
            self.assertFalse(self._nadaljuj()["prejsnja_v_smeteh"])

    def test_datoteka_se_vrne_na_izvirno_mesto(self):
        # Na drugi napravi je datoteka v »Z drugih naprav/<ime tega racunalnika>/Slike/...«: gre nazaj v izvirnik.
        izvir = os.path.join(self.mapa, "moje", "Slike")
        os.makedirs(izvir)
        with open(os.path.join(izvir, "risba.pcraft"), "wb") as d:
            d.write(self.vsebina[:900_000])               # starejsa razlicica: vecina kosov je ze tu
        with mock.patch("core.link_urejanje.v_smeti", side_effect=os.remove):
            izid = self._nadaljuj(moje_ime="Racunalnik B", deljene=[izvir],
                                  pot_imen=["Prejemi", "Safeer", "Z drugih naprav", "Racunalnik B", "Slike", "risba.pcraft"])
        self.assertTrue(izid["ok"], izid)
        self.assertTrue(izid["izvirnik"])
        self.assertEqual(izid["pot"], os.path.join(izvir, "risba.pcraft"))
        self.assertLess(izid["podatki"], 400 * 1024)
        with open(izid["pot"], "rb") as d:
            self.assertEqual(d.read(), self.vsebina)

    def test_naprava_brez_opisov(self):
        # Starejsa razlicica ali Android: /kosi/ ne obstaja - datoteka pride v celoti, prav tako preverjena po dolzini.
        self.assertTrue(self._nadaljuj()["ok"])
        with open(self.pot, "ab") as d:
            d.write(b"dodano na A")
        with mock.patch.object(link_datoteke, "postrezi_kose",
                               lambda o, s, oz, g: link_datoteke._napaka_http(o, 404, "ni take poti")):
            izid = self._nadaljuj()
        self.assertTrue(izid["ok"], izid)
        self.assertFalse(izid["delta"])
        self.assertEqual(izid["razlog"], "naprava_brez_opisa")
        with open(izid["pot"], "rb") as d:
            self.assertEqual(d.read(), self.vsebina + b"dodano na A")

    def test_neznan_razrez_naprave_pomeni_cel_prenos(self):
        self.assertTrue(self._nadaljuj()["ok"])
        with open(self.pot, "ab") as d:
            d.write(b"dodano")
        prav = link_datoteke.opis_kosov
        with mock.patch.object(link_datoteke, "opis_kosov",
                               lambda pot: json.dumps(dict(json.loads(prav(pot)), alg="gear64-v9")).encode()):
            izid = self._nadaljuj()
        self.assertTrue(izid["ok"], izid)
        self.assertEqual((izid["delta"], izid["razlog"]), (False, "naprava_brez_opisa"))
        with open(izid["pot"], "rb") as d:
            self.assertEqual(d.read(), self.vsebina + b"dodano")

    def test_brez_pravice(self):
        self.d.streznik.sme = lambda naprava, zmoznost: False
        self.assertEqual(self._nadaljuj(), {"ok": False, "koda": "ni_dovoljenja"})

    def test_napacen_streznik(self):
        izid = link_nadaljuj.nadaljuj_tukaj({"base_url": "https://8.8.8.8:1", "fp": "a", "token": "b"}, "", "x", "n", "N", ["x"])
        self.assertEqual(izid, {"ok": False, "koda": "napacen_streznik"})


class Poti(unittest.TestCase):
    def test_varna_imena(self):
        self.assertEqual(link_nadaljuj.komponente(["..", "a/b", ".ssh", "", "x.pcraft"]),
                         ["_.", "a_b", "_ssh", "x.pcraft"])

    def test_izvirnik_ostane_v_deljeni_mapi(self):
        mapa = tempfile.mkdtemp(prefix="safeer-izvir-")
        self.addCleanup(shutil.rmtree, mapa, True)
        koren = os.path.join(mapa, "Slike")
        os.makedirs(koren)
        os.symlink("/", os.path.join(koren, "ven"))
        deli = link_nadaljuj.komponente(["Z drugih naprav", "Moj", "Slike", "ven", "etc", "passwd"])
        self.assertEqual(link_nadaljuj.izvirnik(deli, "Moj", [koren]), "")
        deli = link_nadaljuj.komponente(["Z drugih naprav", "Moj", "Slike", "a.txt"])
        self.assertEqual(link_nadaljuj.izvirnik(deli, "Moj", [koren]), os.path.join(koren, "a.txt"))
        self.assertEqual(link_nadaljuj.izvirnik(deli, "Tuj", [koren]), "")


if __name__ == "__main__":
    unittest.main()
