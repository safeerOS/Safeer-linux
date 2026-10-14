"""Teamwork (core/link_teamwork): ista datoteka na vec napravah, za vse programe (lastnik, 14. 10. 2026)."""
import os
import random
import shutil
import tempfile
import unittest

from core import link_delta, link_teamwork as tw


def _podatki(n, seme):
    r = random.Random(seme)
    return bytes(r.getrandbits(8) for _ in range(n))


class Ura:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Par(unittest.TestCase):
    """Lastnik A (datoteka v deljeni mapi) in udelezenec B (delovna kopija), povezana brez omrezja."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ura = Ura()
        self.deljena = os.path.join(self.tmp, "a", "Slike")
        os.makedirs(self.deljena)
        self.izvirnik = os.path.join(self.deljena, "vecer.pcraft")
        self.vsebina = _podatki(600_000, 1)
        with open(self.izvirnik, "wb") as f:
            f.write(self.vsebina)
        self.kopija = os.path.join(self.tmp, "b", "Z drugih naprav", "A", "Slike", "vecer.pcraft")
        os.makedirs(os.path.dirname(self.kopija))
        shutil.copyfile(self.izvirnik, self.kopija)
        self.okna_a, self.okna_b = [], []
        self.obv_a, self.obv_b = [], []
        self.poslano = []
        self.a = tw.Teamwork(
            razresi=lambda o: self.izvirnik if o == "share:0:vecer.pcraft" else "",
            ime_naprave=lambda i: {"B": "Prenosnik"}.get(i, i),
            obvesti=lambda k, p: self.obv_a.append((k, p)), ukaz=None, okna=lambda: self.okna_a,
            mapa=os.path.join(self.tmp, "a-tw"), procesi=None, zdaj=self.ura)
        self.b = tw.Teamwork(
            razresi=lambda o: "", ime_naprave=lambda i: i, obvesti=lambda k, p: self.obv_b.append((k, p)),
            ukaz=self._ukaz, okna=lambda: self.okna_b, prenesi=self._prenesi, poslji=self._poslji,
            opis_lastnika=lambda u: link_delta.manifest(self.izvirnik), mapa=os.path.join(self.tmp, "b-tw"),
            procesi=None, zdaj=self.ura)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # B -> A brez omrezja
    def _ukaz(self, naprava, dejanje, p):
        self.assertEqual((naprava, dejanje), ("A", "files.session"))
        return {"ok": True, "data": self.a.prijava("B", p)}

    def _poslji(self, u, telo, dolzina):
        self.poslano.append(dolzina)
        return self.a.popravek("B", u.oznaka, telo)

    def _prenesi(self, u):
        shutil.copyfile(self.izvirnik, u.pot)
        return {"ok": True}

    def _udelezi(self):
        return self.b.udelezi({"naprava": "A", "ime_naprave": "Testni PC", "oznaka": "share:0:vecer.pcraft",
                               "pot_imen": ["Slike", "vecer.pcraft"], "pot": self.kopija})

    def _tiki(self, n=3, korak=2.0):
        for _ in range(n):
            self.ura.t += korak
            self.b.tik()
            self.a.tik()

    def _uredi(self, pot, odmik, nov):
        with open(pot, "r+b") as f:
            f.seek(odmik)
            f.write(nov)
        os.utime(pot, ns=(int(self.ura.t * 1e9), int(self.ura.t * 1e9)))

    def test_shranitev_na_b_pride_k_lastniku_samo_sprememba(self):
        self.assertTrue(self._udelezi()["podprto"])
        self.okna_b.append({"ime": "[vecer] (imported) – GIMP", "program": "Gimp-2.10"})
        self._tiki(1)
        self._uredi(self.kopija, 300_000, b"Teamwork!" * 100)
        self._tiki(3)
        with open(self.izvirnik, "rb") as f, open(self.kopija, "rb") as g:
            self.assertEqual(f.read(), g.read())
        self.assertEqual(len(self.poslano), 1)
        self.assertLess(self.poslano[0], 300_000, "poslani so samo spremenjeni kosi")
        self.assertEqual(self.a._seje["share:0:vecer.pcraft"].verzija, 2)
        self.assertEqual(self.obv_b, [], "ena sama naprava ureja: Teamwork ni vklopljen")

    def test_teamwork_ko_urejata_oba(self):
        self._udelezi()
        self.okna_b.append({"ime": "vecer.pcraft - PhotoCraft", "program": "PhotoCraft"})
        self._tiki(1)
        self.okna_a.append({"ime": "vecer.pcraft - PhotoCraft", "program": "PhotoCraft"})
        self._tiki(4)
        self.assertIn(("zacetek", {"ime": "vecer.pcraft", "kdo": "Prenosnik"}), self.obv_a)
        self.assertIn(("zacetek", {"ime": "vecer.pcraft", "kdo": "Testni PC"}), self.obv_b)
        self.okna_b.clear()
        self._tiki(4)
        self.assertIn("konec", [k for k, _ in self.obv_a])

    def test_shranitev_lastnika_pride_do_b(self):
        self._udelezi()
        self.okna_b.append({"ime": "vecer.pcraft", "program": "PhotoCraft"})
        self._tiki(1)
        self._uredi(self.izvirnik, 10, b"lastnik")
        self._tiki(5)
        with open(self.izvirnik, "rb") as f, open(self.kopija, "rb") as g:
            self.assertEqual(f.read(), g.read())
        self.assertIn("nova", [k for k, _ in self.obv_b])

    def test_spor_obe_razlicici_ostaneta(self):
        self._udelezi()
        self.okna_b.append({"ime": "vecer.pcraft", "program": "PhotoCraft"})
        self.okna_a.append({"ime": "vecer.pcraft", "program": "PhotoCraft"})
        self._tiki(2)
        # Oba urejata isto razlicico; najprej shrani A, nato B (B ne ve za A).
        self._uredi(self.izvirnik, 100, b"AAAA")
        self.a.tik()
        self.ura.t += 2
        self.a.tik()
        self._uredi(self.kopija, 500_000, b"BBBB")
        self.ura.t += 2
        self.b.tik()
        self.ura.t += 2
        self.b.tik()
        with open(self.izvirnik, "rb") as f:
            glavna = f.read()
        self.assertEqual(glavna[100:104], b"AAAA")
        self.assertNotEqual(glavna[500_000:500_004], b"BBBB")
        kopija = os.path.join(self.deljena, "vecer (Prenosnik).pcraft")
        with open(kopija, "rb") as f:
            k = f.read()
        self.assertEqual(k[500_000:500_004], b"BBBB")
        self.assertIn("spor", [k for k, _ in self.obv_b])
        self.assertIn("spor_drugi", [k for k, _ in self.obv_a])

    def test_program_lastnika_prepise_razlicico_z_b(self):
        """A ima odprto staro razlicico, B shrani (gre na glavno), A nato shrani svojo: razlicica B ostane kot kopija."""
        self._udelezi()
        self.okna_a.append({"ime": "vecer.pcraft", "program": "PhotoCraft"})
        self.okna_b.append({"ime": "vecer.pcraft", "program": "PhotoCraft"})
        self._tiki(2)
        self._uredi(self.kopija, 200, b"BBBB")
        self._tiki(2)
        with open(self.izvirnik, "rb") as f:
            self.assertEqual(f.read()[200:204], b"BBBB")
        # Program na A ima se staro vsebino in jo shrani.
        stara = bytearray(self.vsebina)
        stara[50:54] = b"AAAA"
        with open(self.izvirnik, "wb") as f:
            f.write(stara)
        os.utime(self.izvirnik, ns=(int(self.ura.t * 2e9), int(self.ura.t * 2e9)))
        self.ura.t += 2
        self.a.tik()
        self.ura.t += 2
        self.a.tik()
        with open(os.path.join(self.deljena, "vecer (Prenosnik).pcraft"), "rb") as f:
            self.assertEqual(f.read()[200:204], b"BBBB")
        self.assertIn("spor", [k for k, _ in self.obv_a])
        # Tudi B izve, da je njegova razlicica ohranjena kot kopija (ob naslednjem javljanju).
        self._tiki(4)
        self.assertIn(("spor", {"ime": "vecer.pcraft", "kdo": "Testni PC", "kopija": "vecer (Prenosnik).pcraft"}),
                      self.obv_b)
        self.assertNotIn("nova", [k for k, _ in self.obv_b], "ob sporu eno obvestilo, ne dve")

    def test_udelezbe_ostanejo_po_ponovnem_zagonu(self):
        self._udelezi()
        b2 = tw.Teamwork(razresi=lambda o: "", ime_naprave=lambda i: i, obvesti=lambda k, p: None, ukaz=self._ukaz,
                         okna=lambda: [], mapa=os.path.join(self.tmp, "b-tw"), procesi=None, zdaj=self.ura)
        self.assertEqual([u.pot for u in b2._udelezbe.values()], [self.kopija])
        with open(os.path.join(self.tmp, "b-tw", "udelezbe.json")) as f:
            self.assertNotIn("token", f.read(), "zetonov ne shranjujemo")

    def test_naprava_brez_teamworka(self):
        self.b.ukaz = lambda n, d, p: {"ok": False, "koda": "ni_dovoljeno"}
        self.assertFalse(self._udelezi()["podprto"])


class Popravek(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _dat(self, ime, vsebina):
        p = os.path.join(self.tmp, ime)
        with open(p, "wb") as f:
            f.write(vsebina)
        return p

    def test_samo_manjkajoci_kosi_in_sestava(self):
        stara = _podatki(1_000_000, 2)
        nova = stara[:400_000] + b"novo" * 1000 + stara[400_000:]
        a, b = self._dat("a", stara), self._dat("b", nova)
        info = tw.naredi_popravek(b, link_delta.manifest(a), "x", os.path.join(self.tmp, "p"))
        self.assertLess(info["podatki"], 200_000)
        _, m = tw.uporabi_popravek(os.path.join(self.tmp, "p"), [a], os.path.join(self.tmp, "c"))
        with open(os.path.join(self.tmp, "c"), "rb") as f:
            self.assertEqual(f.read(), nova)
        self.assertEqual(m["podatki"], info["podatki"])

    def test_pokvarjen_popravek_zavrnjen(self):
        stara = _podatki(300_000, 3)
        nova = stara[:1000] + b"x" + stara[1001:]
        a, b = self._dat("a", stara), self._dat("b", nova)
        p = os.path.join(self.tmp, "p")
        tw.naredi_popravek(b, link_delta.manifest(a), "x", p)
        with open(p, "r+b") as f:
            f.seek(-5, 2)
            f.write(b"ZZZZZ")
        with self.assertRaises(link_delta.NapakaDelte):
            tw.uporabi_popravek(p, [a], os.path.join(self.tmp, "c"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "c")))

    def test_lastnik_nima_kosov(self):
        """Opis je bil star (lastnik je medtem shranil): kos manjka -> ponovi, nic se ne zapise."""
        stara = _podatki(300_000, 4)
        nova = stara[:100] + b"y" + stara[101:]
        a, b = self._dat("a", stara), self._dat("b", nova)
        p = os.path.join(self.tmp, "p")
        tw.naredi_popravek(b, link_delta.manifest(a), "x", p)
        drugacna = self._dat("d", _podatki(300_000, 5))
        with self.assertRaises(link_delta.NapakaDelte):
            tw.uporabi_popravek(p, [drugacna], os.path.join(self.tmp, "c"))

    def test_cela_datoteka_z_androida(self):
        """Naprava brez razreza po vsebini poslje celo datoteko z vrednostjo sha256; napacna vrednost je zavrnjena."""
        import hashlib
        import json
        import struct
        vsebina = _podatki(70_000, 6)
        for sha, ok in ((hashlib.sha256(vsebina).hexdigest(), True), ("0" * 64, False)):
            glava = json.dumps({"celota": True, "velikost": len(vsebina), "sha256": sha, "osnova": "x"}).encode()
            p = self._dat("p", tw.MAGIJA + struct.pack(">I", len(glava)) + glava + vsebina)
            c = os.path.join(self.tmp, "c")
            if ok:
                g, m = tw.uporabi_popravek(p, [], c)
                with open(c, "rb") as f:
                    self.assertEqual(f.read(), vsebina)
                self.assertEqual(g["opis"]["sha256"], sha)
            else:
                with self.assertRaises(link_delta.NapakaDelte):
                    tw.uporabi_popravek(p, [], c)

    def test_glava_ne_sme_kazati_izven(self):
        p = self._dat("p", tw.MAGIJA + b"\xff\xff\xff\xff")
        with self.assertRaises(link_delta.NapakaDelte):
            tw.preberi_glavo(p)


class Zaznava(unittest.TestCase):
    def test_naslov_okna(self):
        pot = "/x/Slike/vecer-v-gorah.pcraft"
        self.assertEqual(tw.program_okna(pot, [{"ime": "[vecer-v-gorah] (imported)-1.0 – GIMP", "program": "Gimp"}]), "Gimp")
        self.assertEqual(tw.program_okna(pot, [{"ime": "vecer-v-gorah.pcraft — PhotoCraft", "program": "PhotoCraft"}]),
                         "PhotoCraft")
        self.assertIsNone(tw.program_okna(pot, [{"ime": "vecer-v-gorahx.png", "program": "Eog"}]))
        self.assertIsNone(tw.program_okna(pot, [{"ime": "vecer-v-gorah.pcraft", "program": "Nemo"}]),
                          "upravitelj datotek ne ureja")

    def test_zaklep_libreoffice(self):
        tmp = tempfile.mkdtemp()
        try:
            pot = os.path.join(tmp, "porocilo.odt")
            open(pot, "w").close()
            self.assertIsNone(tw.je_odprta(pot, []))
            open(os.path.join(tmp, ".~lock.porocilo.odt#"), "w").close()
            self.assertEqual(tw.je_odprta(pot, []), "libreoffice")
        finally:
            shutil.rmtree(tmp)

    def test_izbira_programa(self):
        def programi(seznam):
            return lambda pot: {"ok": True, "programi": seznam}
        gimp = {"id": "org.gimp.GIMP.desktop", "ime": "GIMP", "privzet": False}
        pc = {"id": "ai.storyteller.photocraft.desktop", "ime": "PhotoCraft", "privzet": True}
        self.assertEqual(tw.izberi_program("x.pcraft", "PhotoCraft", programi([gimp, pc]))["nacin"], "isti")
        r = tw.izberi_program("x.png", "PhotoCraft", programi([gimp]))
        self.assertEqual((r["nacin"], r["program"]), ("podprt", "org.gimp.GIMP.desktop"))
        self.assertEqual(tw.izberi_program("x.pcraft", "PhotoCraft", programi([]))["nacin"], "pretok")
        self.assertEqual(tw.izberi_program("x.png", "Gimp-2.10", programi([pc, gimp]))["program"], "org.gimp.GIMP.desktop")

    def test_ime_kopije(self):
        tmp = tempfile.mkdtemp()
        try:
            pot = os.path.join(tmp, "a.txt")
            self.assertEqual(os.path.basename(tw.ime_kopije(pot, "Prenosnik")), "a (Prenosnik).txt")
            open(os.path.join(tmp, "a (Prenosnik).txt"), "w").close()
            self.assertEqual(os.path.basename(tw.ime_kopije(pot, "Prenosnik")), "a (Prenosnik 2).txt")
            self.assertEqual(os.path.basename(tw.ime_kopije(pot, "../x")), "a (..x).txt")
        finally:
            shutil.rmtree(tmp)

    def test_kratko_ime(self):
        self.assertEqual(tw.kratko_ime("Safeer OS (OnePlus)"), "OnePlus")
        self.assertEqual(tw.kratko_ime("Safeer Control (racunalnik-1)"), "racunalnik-1")
        self.assertEqual(tw.kratko_ime("Tablica Matej"), "Tablica Matej")
        self.assertEqual(os.path.basename(tw.ime_kopije("/x/a.txt", "Safeer OS (OnePlus)")), "a (OnePlus).txt")

    def test_besedila_v_vseh_jezikih(self):
        for jezik, b in tw.BESEDILA.items():
            self.assertEqual(set(b), set(tw.BESEDILA["sl"]), jezik)
            for koda in b:
                if koda != "tukaj":
                    tw.besedilo(jezik, koda, ime="a", kdo="b", kopija="c")


if __name__ == "__main__":
    unittest.main()
