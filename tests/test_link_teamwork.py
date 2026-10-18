"""Teamwork (core/link_teamwork): ista datoteka na vec napravah, za vse programe (lastnik, 14. 10. 2026)."""
import os
import random
import shutil
import tempfile
import threading
import time
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

    def _kopije(self):
        return sorted(x for x in os.listdir(self.deljena) if "(" in x)

    def test_spor_ne_dela_kopij_v_nedogled(self):
        """Pregled 14. 10.: ce prenos glavne razlicice po sporu ne uspe, ista vsebina ne gre znova (ena kopija)."""
        self._udelezi()
        self.okna_b.append({"ime": "vecer.pcraft", "program": "PhotoCraft"})
        self._tiki(2)
        self._uredi(self.izvirnik, 100, b"AAAA")
        self.a.tik()
        self.ura.t += 2
        self.a.tik()
        self.b.prenesi = lambda u: {"ok": False}
        self._uredi(self.kopija, 500_000, b"BBBB")
        for _ in range(10):
            self.ura.t += 2
            self.b.tik()
        self.assertEqual(self._kopije(), ["vecer (Prenosnik).pcraft"])

    def test_shrani_in_zapri_na_lastniku(self):
        """Program na lastniku shrani staro vsebino in se zapre v istem trenutku: razlicica z B ostane kot kopija."""
        self._udelezi()
        self.okna_a.append({"ime": "vecer.pcraft", "program": "PhotoCraft"})
        self.okna_b.append({"ime": "vecer.pcraft", "program": "PhotoCraft"})
        self._tiki(2)
        self._uredi(self.kopija, 200, b"BBBB")
        self._tiki(2)
        stara = bytearray(self.vsebina)
        stara[50:54] = b"AAAA"
        with open(self.izvirnik, "wb") as f:
            f.write(stara)
        os.utime(self.izvirnik, ns=(int(self.ura.t * 2e9),) * 2)
        self.okna_a.clear()
        for _ in range(2):
            self.ura.t += 2
            self.a.tik()
        self.assertEqual(self._kopije(), ["vecer (Prenosnik).pcraft"])
        self.assertIn("spor", [k for k, _ in self.obv_a])

    def test_shranitev_lastnika_med_sestavljanjem_popravka(self):
        """Lastnik shrani, medtem ko se popravek sestavlja: njegova shranitev ostane glavna, popravek gre v kopijo."""
        self._udelezi()
        self.okna_b.append({"ime": "vecer.pcraft", "program": "PhotoCraft"})
        self._tiki(2)
        izvirna = tw.uporabi_popravek

        def pocasna(*a, **k):
            izid = izvirna(*a, **k)
            with open(self.izvirnik, "r+b") as f:
                f.seek(10)
                f.write(b"OWNERSAVE")
            return izid
        tw.uporabi_popravek = pocasna
        try:
            self._uredi(self.kopija, 300_000, b"BBBB")
            self._tiki(3)
        finally:
            tw.uporabi_popravek = izvirna
        with open(self.izvirnik, "rb") as f:
            self.assertEqual(f.read()[10:19], b"OWNERSAVE")
        kopije = self._kopije()
        self.assertEqual(len(kopije), 1)
        with open(os.path.join(self.deljena, kopije[0]), "rb") as f:
            self.assertEqual(f.read()[300_000:300_004], b"BBBB")

    def test_udelezbe_ostanejo_po_ponovnem_zagonu(self):
        self._udelezi()
        b2 = tw.Teamwork(razresi=lambda o: "", ime_naprave=lambda i: i, obvesti=lambda k, p: None, ukaz=self._ukaz,
                         okna=lambda: [], mapa=os.path.join(self.tmp, "b-tw"), procesi=None, zdaj=self.ura)
        self.assertEqual([u.pot for u in b2._udelezbe.values()], [self.kopija])
        with open(os.path.join(self.tmp, "b-tw", "udelezbe.json")) as f:
            self.assertNotIn("token", f.read(), "zetonov ne shranjujemo")

    def test_odstranjeno_deljenje_ustavi_sejo(self):
        """Uporabnik je mapo odstranil iz deljenih: obstojeca seja ne sme vec pisati v datoteko (prej je s shranjeno
        potjo pisala naprej - preverjeno 18. 10. 2026)."""
        oznaka = "share:0:vecer.pcraft"
        self.assertTrue(self.a.prijava("B", {"id": oznaka, "odprto": True})["ok"])
        nova = bytearray(self.vsebina)
        nova[10:20] = b"PREPISANO!"
        b = os.path.join(self.tmp, "nova.pcraft")
        with open(b, "wb") as f:
            f.write(nova)
        telo = os.path.join(self.tmp, "telo")
        tw.naredi_popravek(b, link_delta.manifest(self.izvirnik), tw._sha(self.izvirnik), telo)
        self.a.razresi = lambda o: ""
        self.assertEqual(self.a.popravek("B", oznaka, telo)[0], 409)
        with open(self.izvirnik, "rb") as f:
            self.assertEqual(f.read(), self.vsebina, "datoteka ostane nespremenjena")
        self.assertEqual(self.a.prijava("B", {"id": oznaka, "odprto": True}),
                         {"ok": False, "koda": "ni_datoteke"})
        self.assertNotIn(oznaka, self.a._seje)
        # Oznaka zdaj kaze na drugo datoteko: seja stare poti ne velja, nova je za novo datoteko.
        druga = os.path.join(self.deljena, "druga.pcraft")
        with open(druga, "wb") as f:
            f.write(b"druga")
        self.a.razresi = lambda o: self.izvirnik
        self.assertTrue(self.a.prijava("B", {"id": oznaka, "odprto": True})["ok"])
        self.a.razresi = lambda o: druga
        self.assertEqual(self.a.prijava("B", {"id": oznaka, "odprto": True})["ime"], "druga.pcraft")
        self.assertEqual(self.a.popravek("B", oznaka, telo)[0], 409, "popravek stare datoteke ne pristane v drugi")
        with open(druga, "rb") as f:
            self.assertEqual(f.read(), b"druga")

    def test_udelezenec_neha_posiljati_ko_deljenja_ni(self):
        def ukaz(naprava, dejanje, p):
            d = self.a.prijava("B", p)               # kot SafeerLink.ukaz_pocakaj: napaka naprave -> ok, koda
            return {"ok": bool(d.get("ok")), "koda": str(d.get("koda") or ""), "data": d}
        self.b.ukaz = ukaz
        self.assertTrue(self._udelezi()["podprto"])
        self.okna_b.append({"ime": "[vecer] (imported) – GIMP", "program": "Gimp-2.10"})
        self._tiki(1)
        self.a.razresi = lambda o: ""
        self._uredi(self.kopija, 1000, b"X" * 50)
        self._tiki(3)
        with open(self.izvirnik, "rb") as f:
            self.assertEqual(f.read(), self.vsebina)
        self.assertLessEqual(len(self.poslano), 1, "brez ponavljanja posiljanja")

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
        self.assertEqual(tw.kratko_ime("Tablica lastnik"), "Tablica lastnik")
        self.assertEqual(os.path.basename(tw.ime_kopije("/x/a.txt", "Safeer OS (OnePlus)")), "a (OnePlus).txt")

    def test_besedila_v_vseh_jezikih(self):
        for jezik, b in tw.BESEDILA.items():
            self.assertEqual(set(b), set(tw.BESEDILA["sl"]), jezik)
            for koda in b:
                if koda != "tukaj":
                    tw.besedilo(jezik, koda, ime="a", kdo="b", kopija="c")


if __name__ == "__main__":
    unittest.main()


class StreznikPopravkov(unittest.TestCase):
    """POST /popravek/<id> na pravem strezniku datotek: zeton, pravica, prijava v sejo, zapis."""

    def setUp(self):
        import ssl
        import http.client
        from core import link_datoteke
        self.ssl, self.http = ssl, http.client
        self.tmp = tempfile.mkdtemp()
        self.deljena = os.path.join(self.tmp, "Slike")
        os.makedirs(self.deljena)
        self.pot = os.path.join(self.deljena, "a.bin")
        self.vsebina = _podatki(200_000, 7)
        with open(self.pot, "wb") as f:
            f.write(self.vsebina)
        self.d = link_datoteke.Datoteke([self.deljena], tls_mapa=os.path.join(self.tmp, "tls"))
        self.d.streznik.sme = lambda naprava, zmoznost: True
        self.d.streznik.umaknjena = lambda naprava: False
        # Preizkus ne sme biti odvisen od prostega prostora na disku gostitelja (507 ni prostora).
        rezerva = link_datoteke.REZERVA_DISKA
        link_datoteke.REZERVA_DISKA = 0
        self.addCleanup(setattr, link_datoteke, "REZERVA_DISKA", rezerva)
        self.tw = tw.Teamwork(razresi=self.d.pot, ime_naprave=lambda i: i, obvesti=lambda k, p: None, ukaz=None,
                              okna=lambda: [], mapa=os.path.join(self.tmp, "tw"), procesi=None)
        self.d.teamwork = self.d.streznik.teamwork = self.tw
        self.streznik = self.d.streznik_za("naprava-b")

    def tearDown(self):
        self.d.ustavi()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _poslji(self, telo, zeton):
        ctx = self.ssl.SSLContext(self.ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = self.ssl.CERT_NONE
        p = self.http.HTTPSConnection("127.0.0.1", self.d.streznik.vrata, context=ctx, timeout=30)
        glave = {"Content-Length": str(len(telo))}
        if zeton:
            glave["X-Safeer-Token"] = zeton
        p.request("POST", "/popravek/share:0:a.bin", body=telo, headers=glave)
        o = p.getresponse()
        odgovor = o.read()
        p.close()
        return o.status, odgovor

    def test_popravek_prek_streznika(self):
        nova = bytearray(self.vsebina)
        nova[1000:1004] = b"NOVO"
        b = os.path.join(self.tmp, "b.bin")
        with open(b, "wb") as f:
            f.write(nova)
        telo_pot = os.path.join(self.tmp, "telo")
        osnova = tw._sha(self.pot)
        tw.naredi_popravek(b, link_delta.manifest(self.pot), osnova, telo_pot)
        with open(telo_pot, "rb") as f:
            telo = f.read()
        self.assertEqual(self._poslji(telo, "")[0], 401)
        self.assertEqual(self._poslji(telo, "napacen")[0], 401)
        # Naprava, ki ni prijavljena v sejo datoteke, je ne more spremeniti.
        self.assertEqual(self._poslji(telo, self.streznik["token"])[0], 409)
        self.tw.prijava("naprava-b", {"id": "share:0:a.bin", "odprto": True})
        status, _ = self._poslji(telo, self.streznik["token"])
        self.assertEqual(status, 200)
        with open(self.pot, "rb") as f:
            self.assertEqual(f.read(), bytes(nova))
        # Naprava brez pravice do datotek: zavrnjeno.
        self.d.streznik.sme = lambda naprava, zmoznost: False
        self.assertEqual(self._poslji(telo, self.streznik["token"])[0], 401)

    def _napol(self, zapri, vrata, pot):
        """Naprava zacne oddajo popravka in utihne (izgubljeno omrezje) ali sredi oddaje odide."""
        import socket
        ctx = self.ssl.SSLContext(self.ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = self.ssl.CERT_NONE
        v = ctx.wrap_socket(socket.create_connection(("127.0.0.1", vrata), timeout=10))
        v.sendall(("POST %s HTTP/1.1\r\nHost: x\r\nContent-Length: 100000\r\n"
                   "X-Safeer-Token: %s\r\n\r\n" % (pot, self.streznik["token"])).encode() + b"z" * 5000)
        if zapri:
            v.close()
            return None
        return v

    def _pocakaj(self, pogoj, rok=8.0):
        konec = time.monotonic() + rok
        while time.monotonic() < konec:
            if pogoj():
                return True
            time.sleep(0.05)
        return pogoj()

    def test_prekinjena_oddaja_ne_drzi_niti_mest_in_datotek(self):
        self._prekinjena(self.d.streznik.vrata, "/popravek/share:0:a.bin")

    def test_prekinjena_oddaja_prek_huba(self):
        """Prek Huba (Global Link) povezava po glavah nima roka (rok_po_rokovanju=None): tu je bila nit za vedno."""
        from unittest import mock
        from core import link_hub_streznik
        hub = link_hub_streznik.HubStreznik(tls_mapa=os.path.join(self.tmp, "tls"))
        hub._ze_gosti_lokalno = staticmethod(lambda: False)
        hub.datoteke = self.d.streznik
        with mock.patch.object(link_hub_streznik, "PRIVZETA_VRATA", 0):
            self.assertTrue(hub.zazeni())
        self.addCleanup(hub.ustavi)
        self._prekinjena(hub.vrata, "/cast/popravek/share:0:a.bin")

    def _prekinjena(self, vrata, pot):
        """Prej brez roka branja (prek Huba): utihnjena naprava je za vedno drzala nit, eno od dveh mest za popravke
        in zacasno datoteko; po dveh takih so vsi popravki dobili 503."""
        from core import link_datoteke
        prej_rok = link_datoteke.ROK_BRANJA_POPRAVKA_S
        link_datoteke.ROK_BRANJA_POPRAVKA_S = 0.5
        zacasno = self.tw._mapa_zacasnih()
        try:
            time.sleep(0.2)
            niti_prej = threading.active_count()
            fd_prej = len(os.listdir("/proc/self/fd")) if os.path.isdir("/proc/self/fd") else None
            tihi = [self._napol(False, vrata, pot) for _ in range(3)]
            self._napol(True, vrata, pot)
            self.assertTrue(self._pocakaj(lambda: any(i.startswith(".popravek-") for i in os.listdir(zacasno)), 3.0),
                            "oddaja se je zacela (zacasna datoteka)")
            self.assertTrue(self._pocakaj(lambda: threading.active_count() <= niti_prej),
                            "niti obravnave so ostale: %d > %d" % (threading.active_count(), niti_prej))
            self.assertEqual([i for i in os.listdir(zacasno) if i.startswith(".popravek-")], [])
            for v in tihi:
                v.close()
            if fd_prej is not None:
                self.assertTrue(self._pocakaj(lambda: len(os.listdir("/proc/self/fd")) <= fd_prej),
                                "deskriptorji: %d > %d" % (len(os.listdir("/proc/self/fd")), fd_prej))
        finally:
            link_datoteke.ROK_BRANJA_POPRAVKA_S = prej_rok
        # Obe mesti za popravke sta prosti: pravi popravek gre skozi (ne 503).
        nova = bytearray(self.vsebina)
        nova[0:4] = b"ZIVO"
        b = os.path.join(self.tmp, "b.bin")
        with open(b, "wb") as f:
            f.write(nova)
        telo_pot = os.path.join(self.tmp, "telo")
        tw.naredi_popravek(b, link_delta.manifest(self.pot), tw._sha(self.pot), telo_pot)
        with open(telo_pot, "rb") as f:
            telo = f.read()
        self.tw.prijava("naprava-b", {"id": "share:0:a.bin", "odprto": True})
        self.assertEqual(self._poslji(telo, self.streznik["token"])[0], 200)


class GlavnaNit(unittest.TestCase):
    """files.session prihaja na glavni niti (core/safeer_link -> link_daljinec.izvedi_control). Prej je prijava tam
    cakala na glavno nit samo (seznam oken) - 3 s zamrznitve ob vsakem javljanju udelezenca (vsakih 5 s)."""

    def _glib(self):
        try:
            from gi.repository import GLib
        except Exception as e:  # noqa: BLE001 - okolje brez gi
            self.skipTest("gi ni na voljo: %s" % e)
        return GLib

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pot = os.path.join(self.tmp, "a.txt")
        with open(self.pot, "w") as f:
            f.write("x" * 1000)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _tw(self, okna):
        return tw.Teamwork(razresi=lambda o: self.pot if o == "id1" else "", ime_naprave=lambda i: i,
                           obvesti=lambda *a: None, ukaz=None, okna=okna, mapa=os.path.join(self.tmp, "tw"),
                           procesi=None)

    def test_prijava_na_glavni_niti_ne_caka(self):
        GLib = self._glib()
        zanka = GLib.MainLoop()
        izid = {}
        t = self._tw(lambda: tw.na_glavni_niti(lambda: [{"ime": "a.txt - urejevalnik", "program": "Gedit"}], 3.0))

        def na_glavni():
            for i in range(2):
                zacetek = time.monotonic()
                izid[i] = (t.prijava("n-1", {"id": "id1", "odprto": True}), time.monotonic() - zacetek)
            zanka.quit()
            return False
        GLib.idle_add(na_glavni)
        GLib.timeout_add_seconds(20, zanka.quit)
        zanka.run()
        for i in (0, 1):
            stanje, cas = izid[i]
            self.assertTrue(stanje["ok"])
            self.assertLess(cas, 1.0, "prijava je cakala na glavno nit (%.2f s)" % cas)
        self.assertEqual(stanje["drugi"], ["@tukaj"], "seznam oken je prebran (datoteka odprta tudi tukaj)")

    def test_iz_niti_prek_glavne_zanke(self):
        GLib = self._glib()
        zanka = GLib.MainLoop()
        izid = {}

        def v_niti():
            izid["nit"] = tw.na_glavni_niti(lambda: threading.current_thread() is threading.main_thread(), 3.0)
            GLib.idle_add(zanka.quit)
        threading.Thread(target=v_niti, daemon=True).start()
        GLib.timeout_add_seconds(20, zanka.quit)
        zanka.run()
        self.assertIs(izid.get("nit"), True, "delo je teklo na glavni niti")
        # Glavna zanka ne tece (zasedena): po roku None, stanje odprtosti ostane.
        izid.clear()
        nit = threading.Thread(target=lambda: izid.setdefault("x", tw.na_glavni_niti(lambda: [], 0.2)), daemon=True)
        nit.start()
        nit.join(5)
        self.assertIn("x", izid)
        self.assertIsNone(izid["x"])
        GLib.MainContext.default().iteration(False)   # pocisti cakajoce delo

    def test_files_session_v_niti(self):
        """izvedi_control (glavna nit) se vrne takoj; odgovor pride prek koncaj iz niti."""
        from core import link_daljinec

        class Tw:
            def prijava(self, posiljatelj, p):
                time.sleep(0.5)                      # npr. prva prijava velike datoteke
                return {"ok": True, "sha256": "x", "niti": threading.current_thread().name}

        class Datoteke:
            teamwork = Tw()

            def streznik_za(self, posiljatelj, hub_url):
                return {"base_url": "https://x"}
        odgovori = []
        prispel = threading.Event()
        zacetek = time.monotonic()
        link_daljinec.izvedi_control("files.session", {"id": "id1", "odprto": True}, lambda u: None,
                                     lambda r: (odgovori.append(r), prispel.set()), datoteke=Datoteke(),
                                     posiljatelj="n-1")
        self.assertLess(time.monotonic() - zacetek, 0.2, "glavna nit ne caka na prijavo")
        self.assertTrue(prispel.wait(5))
        r = odgovori[0]
        self.assertTrue(r["ok"])
        self.assertEqual(r["data"]["streznik"], {"base_url": "https://x"})
        self.assertEqual(r["data"]["niti"], "safeer-teamwork-prijava")

    def test_hkratni_prvi_prijavi_bereta_datoteko_enkrat(self):
        t = self._tw(lambda: [])
        branja = []
        izvirna = tw._sha

        def sha(pot):
            branja.append(pot)
            time.sleep(0.3)
            return izvirna(pot)
        tw._sha = sha
        try:
            niti = [threading.Thread(target=t.prijava, args=("n-%d" % i, {"id": "id1"})) for i in range(3)]
            for n in niti:
                n.start()
            for n in niti:
                n.join(10)
        finally:
            tw._sha = izvirna
        self.assertEqual(len(branja), 1)
        self.assertEqual(set(t._seje["id1"].udelezenci), {"n-0", "n-1", "n-2"})
        self.assertEqual(t._ustvarjanje, {})
