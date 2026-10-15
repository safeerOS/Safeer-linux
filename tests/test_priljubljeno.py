"""Priljubljene (core/priljubljeno.py), predogled in vec datotek v Smeti (core/os_datoteke.py) ter pot skozi most.

Prej so bile priljubljene samo v localStorage delovne povrsine WebKit (namizje QML jih ni videlo) - 15. 10. 2026."""
import json
import os
import shutil
import tempfile
import threading
import unittest
from unittest import mock

from core import os_datoteke, priljubljeno


class Shramba(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mapa, True)
        self.dogodki = []
        self.s = priljubljeno.Priljubljeno(os.path.join(self.mapa, "cfg", "priljubljeno.json"), self.dogodki.append)
        self.f = os.path.join(self.mapa, "a.txt")
        with open(self.f, "w") as f:
            f.write("x")

    def test_preklopi_datoteko_in_dogodek(self):
        st = self.s.preklopi("datoteka", {"pot": self.f, "ime": "a.txt"})
        self.assertEqual([d["pot"] for d in st["datoteke"]], [self.f])
        self.assertTrue(st["datoteke"][0]["obstaja"])
        self.assertEqual(st["datoteke"][0]["vrsta"], "dokument")
        self.assertEqual(len(self.dogodki), 1)
        # Isto stanje se enkrat: brez zapisa in brez dogodka.
        self.s.preklopi("datoteka", self.f, True)
        self.assertEqual(len(self.dogodki), 1)
        st = self.s.preklopi("datoteka", self.f)
        self.assertEqual(st["datoteke"], [])
        self.assertEqual(len(self.dogodki), 2)

    def test_manjkajoca_ostane_kot_nedosegljiva(self):
        self.s.preklopi("datoteka", self.f)
        os.remove(self.f)
        d = self.s.stanje()["datoteke"]
        self.assertEqual(len(d), 1)
        self.assertFalse(d[0]["obstaja"])

    def test_atomarno_in_pokvarjen_zapis(self):
        self.s.preklopi("program", "ta:gimp.desktop")
        with open(self.s.pot, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["programi"], ["ta:gimp.desktop"])
        self.assertEqual([x for x in os.listdir(os.path.dirname(self.s.pot)) if x.endswith(".tmp")], [])
        with open(self.s.pot, "w") as f:
            f.write("{pokvarjeno")
        self.assertEqual(self.s.stanje()["programi"], [])
        with open(self.s.pot, "w") as f:
            json.dump({"datoteke": [{"pot": "relativna"}, 5, {"pot": "/a\0b"}], "programi": ["brez-dvopicja", 3],
                       "kategorije": {"ta:x": "neznana"}, "nastavitve": {"programiPogled": "x"}}, f)
        st = self.s.stanje()
        self.assertEqual((st["datoteke"], st["programi"], st["kategorije"]), ([], [], {}))
        self.assertEqual(st["nastavitve"]["programiPogled"], "mreza")

    def test_vzporedno_brez_izgube(self):
        niti = [threading.Thread(target=self.s.preklopi, args=("program", "ta:p%d.desktop" % i)) for i in range(30)]
        for n in niti:
            n.start()
        for n in niti:
            n.join()
        self.assertEqual(len(self.s.stanje()["programi"]), 30)

    def test_vrstni_red_kategorija_nastavitve(self):
        for k in ("ta:a", "ta:b", "ta:c"):
            self.s.preklopi("program", k)
        st = self.s.vrstni_red("programi", ["ta:c", "ta:a", "ta:neznan"])
        self.assertEqual(st["programi"], ["ta:c", "ta:a", "ta:b"])       # izpusceni ostane na koncu
        st = self.s.kategorija("ta:a", "mediji")
        self.assertEqual(st["kategorije"], {"ta:a": "mediji"})
        self.assertEqual(self.s.kategorija("ta:a", "neznana")["kategorije"], {"ta:a": "mediji"})
        self.assertEqual(self.s.kategorija("ta:a", "")["kategorije"], {})
        self.assertEqual(self.s.nastavi("programiRazvrsti", "nazadnje")["nastavitve"]["programiRazvrsti"], "nazadnje")
        self.assertEqual(self.s.nastavi("programiRazvrsti", "rm -rf")["nastavitve"]["programiRazvrsti"], "nazadnje")
        g = os.path.join(self.mapa, "g.txt")
        open(g, "w").close()
        self.s.preklopi("datoteka", self.f)
        self.s.preklopi("datoteka", g)
        self.assertEqual([d["pot"] for d in self.s.vrstni_red("datoteke", [g])["datoteke"]], [g, self.f])

    def test_preselitev_iz_localstorage(self):
        self.s.preklopi("program", "ta:obstojeci")
        stari = {"priljubljeneDat": [{"ime": "a.txt", "pot": self.f, "mapa": False}, {"pot": self.f}],
                 "priljubljeniPrg": ["ta:obstojeci", "tv1:com.app"], "kategorije": {"ta:gimp.desktop": "mediji"}, "pogled": "seznam"}
        st = self.s.preseli(stari)
        self.assertEqual([d["pot"] for d in st["datoteke"]], [self.f])
        self.assertEqual(st["programi"], ["ta:obstojeci", "tv1:com.app"])
        self.assertEqual(st["kategorije"], {"ta:gimp.desktop": "mediji"})
        self.assertEqual(st["nastavitve"]["programiPogled"], "seznam")
        self.assertTrue(st["preseljeno"])
        n = len(self.dogodki)
        self.s.preseli(stari)                       # drugi pogled z istim localStorage: nic novega
        self.assertEqual(len(self.dogodki), n)

    def test_sledi_premiku_in_razveljavitvi(self):
        mapa = os.path.join(self.mapa, "M")
        os.mkdir(mapa)
        v = os.path.join(mapa, "v.txt")
        open(v, "w").close()
        self.s.preklopi("datoteka", v)
        self.s.preklopi("datoteka", self.f)
        nova = os.path.join(self.mapa, "N")
        os.rename(mapa, nova)
        pari = priljubljeno.premaknjeno_po_dejanju("preimenujDatoteko", [mapa, "N"], {"ok": True, "pot": nova})
        st = self.s.premaknjeno(pari)
        self.assertEqual([d["pot"] for d in st["datoteke"]], [os.path.join(nova, "v.txt"), self.f])
        os.rename(nova, mapa)
        zapis = {"vrsta": "preimenovanje", "pari": [[mapa, nova]]}
        pari = priljubljeno.premaknjeno_po_razveljavitvi(zapis, {"ok": True, "narejeno": 1})
        self.assertEqual(pari, [[nova, mapa]])
        self.assertEqual(self.s.premaknjeno(pari)["datoteke"][0]["pot"], v)
        self.assertIsNone(priljubljeno.premaknjeno_po_dejanju("prilepiDatoteke", [[v], "/x", False], {"pari": [[v, "/x/v"]]}))


class Predogled(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mapa, True)
        os.environ["XDG_CACHE_HOME"] = os.path.join(self.mapa, "cache")
        self.addCleanup(os.environ.pop, "XDG_CACHE_HOME", None)

    def _pot(self, ime, vsebina):
        p = os.path.join(self.mapa, ime)
        with open(p, "wb") as f:
            f.write(vsebina)
        return p

    def test_besedilo_omejeno(self):
        p = self._pot("velika.log", ("vrstica čšž\n" * 40000).encode("utf-8"))
        self.assertGreater(os.path.getsize(p), os_datoteke.MEJA_BESEDILA)
        resnicni_open = open
        prebrano = []

        def opazuj(pot, nacin="r", *a, **k):
            f = resnicni_open(pot, nacin, *a, **k)
            if pot == p:
                izvirni = f.read
                f.read = lambda n=-1: prebrano.append(n) or izvirni(n)
            return f
        with mock.patch("builtins.open", opazuj):
            r = os_datoteke.predogled(p)
        self.assertEqual(r["nacin"], "besedilo")
        self.assertTrue(r["odrezano"])
        self.assertLessEqual(len(r["besedilo"].encode("utf-8")), os_datoteke.MEJA_BESEDILA + 4)
        self.assertEqual(prebrano, [os_datoteke.MEJA_BESEDILA + 1])          # nikoli cela datoteka
        self.assertIn("čšž", r["besedilo"])

    def test_binarno_in_posebne(self):
        r = os_datoteke.predogled(self._pot("program.bin", b"\x7fELF\0\0\x01" * 100))
        self.assertEqual(r["nacin"], "podatki")                  # application/octet-stream: brez branja
        r = os_datoteke.predogled(self._pot("brez_koncnice", b"\x7fELF\0\0\x01" * 100))
        self.assertEqual(r["nacin"], "podatki")
        self.assertTrue(r["binarno"])
        r = os_datoteke.predogled(self._pot("koda.py", b"print('ok')\n"))
        self.assertEqual((r["nacin"], r["besedilo"], r["odrezano"]), ("besedilo", "print('ok')\n", False))
        self.assertEqual(os_datoteke.predogled(self.mapa)["napaka"], "mapa")
        self.assertEqual(os_datoteke.predogled(os.path.join(self.mapa, "ni"))["napaka"], "ni_datoteke")
        cev = os.path.join(self.mapa, "cev")
        os.mkfifo(cev)
        self.assertEqual(os_datoteke.predogled(cev)["napaka"], "ni_navadna")      # branje cevi bi obviselo

    def test_slika_medij_pdf(self):
        self.assertEqual(os_datoteke.predogled(self._pot("s.png", b"\x89PNG"))["nacin"], "slika")
        self.assertEqual(os_datoteke.predogled(self._pot("p.mp3", b"ID3"))["nacin"], "medij")
        with mock.patch.object(os_datoteke, "MEJA_SLIKE", 2):
            r = os_datoteke.predogled(self._pot("v.jpg", b"0123"))
        self.assertEqual((r["nacin"], r["prevelika"]), ("podatki", True))
        pdf = self._pot("d.pdf", b"%PDF-1.4 ni pravi")
        with mock.patch.dict("sys.modules", {"cairo": None}):
            r = os_datoteke.predogled(pdf, najdi=lambda _ime: None)
        self.assertEqual((r["nacin"], r["brezOrodja"]), ("podatki", True))

    @unittest.skipUnless(shutil.which("pdftoppm"), "brez pdftoppm")
    def test_pdf_prva_stran(self):
        pdf = os.path.join(self.mapa, "d.pdf")
        # Najmanjsi veljaven PDF z eno prazno stranjo.
        deli = [b"%PDF-1.4\n", b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n",
                b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n",
                b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 300]>>endobj\n"]
        odmiki, telo = [], b""
        for d in deli:
            odmiki.append(len(telo))
            telo += d
        xref = len(telo)
        telo += b"xref\n0 4\n0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % o for o in odmiki[1:])
        telo += b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % xref
        with open(pdf, "wb") as f:
            f.write(telo)
        r = os_datoteke.predogled(pdf)
        self.assertEqual(r["nacin"], "pdf")
        self.assertTrue(os.path.isfile(r["slika"]))
        self.assertEqual(os_datoteke.predogled(pdf)["slika"], r["slika"])       # iz predpomnilnika


class VecVSmeti(unittest.TestCase):
    def test_idji_za_eno_razveljavitev(self):
        izidi = {"/a": {"ok": True, "id": "a.1"}, "/b": {"ok": True, "id": "b"}, "/c": {"ok": False, "napaka": "ni_dovoljenja"}}
        with mock.patch.object(os_datoteke, "v_smeti", side_effect=lambda p: izidi[p]):
            r = os_datoteke.v_smeti_vec(["/a", "/b", "/c", "/a"])
        self.assertEqual(r["idji"], ["a.1", "b"])
        self.assertEqual(r["narejeno"], ["/a", "/b"])
        self.assertEqual(r["napake"], [{"pot": "/c", "napaka": "ni_dovoljenja"}])
        self.assertFalse(r["ok"])
        self.assertEqual(os_datoteke.v_smeti_vec([])["napaka"], "ni_datoteke")
        # En zapis razveljavi obnovi vse.
        with mock.patch.object(os_datoteke, "obnovi_iz_smeti", return_value={"ok": True}) as obnovi:
            r = os_datoteke.razveljavi({"vrsta": "smeti", "idji": ["a.1", "b"]})
        self.assertEqual(r["narejeno"], 2)
        self.assertEqual([c.args[0] for c in obnovi.call_args_list], ["a.1", "b"])

    def test_razveljavi_vec_premikov(self):
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa, True)
        cilj = os.path.join(mapa, "cilj")
        os.mkdir(cilj)
        poti = []
        for ime in ("a", "b", "c"):
            poti.append(os.path.join(mapa, ime))
            open(poti[-1], "w").close()
        r = os_datoteke.prilepi(poti, cilj, True)
        self.assertEqual(len(r["pari"]), 3)
        r2 = os_datoteke.razveljavi({"vrsta": "premik", "pari": r["pari"]})
        self.assertEqual(r2["narejeno"], 3)
        self.assertTrue(all(os.path.exists(p) for p in poti))


class Most(unittest.TestCase):
    """Klici iz namizja gredo skozi SafeerOS._obdelaj_klic do shrambe; preimenovanje premakne priljubljeno."""

    def test_pot_skozi_safeer_os(self):
        import safeer_os as so
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa, True)
        shramba = priljubljeno.Priljubljeno(os.path.join(mapa, "p.json"))
        dogodki = []
        odgovori = {}
        gotovo = threading.Event()

        class Pogled:
            def qml_odgovor(self, i, ok, podatki):
                odgovori[i] = (ok, podatki)
                gotovo.set()

        jaz = mock.MagicMock()
        jaz._katalog_most.return_value.pozna.return_value = False
        jaz.SPREMINJAJO_DATOTEKE = so.SafeerOS.SPREMINJAJO_DATOTEKE
        jaz._odgovori = lambda p, i, ok, d: so.SafeerOS._odgovori(jaz, p, i, ok, d)
        jaz._priljubljeno = lambda: shramba
        jaz._priljubljene_sledijo = lambda m, a, izid: so.SafeerOS._priljubljene_sledijo(jaz, m, a, izid)
        shramba.ob_spremembi = dogodki.append

        def klic(metoda, a):
            gotovo.clear()
            so.SafeerOS._obdelaj_klic(jaz, Pogled(), 1, metoda, a)
            self.assertTrue(gotovo.wait(5), metoda)
            return odgovori[1]
        f = os.path.join(mapa, "a.txt")
        open(f, "w").close()
        ok, st = klic("priljubljenoPreklopi", ["datoteka", {"pot": f, "ime": "a.txt", "mapa": False}])
        self.assertTrue(ok)
        self.assertEqual(st["datoteke"][0]["pot"], f)
        self.assertEqual(len(dogodki), 1)
        with mock.patch.object(so, "os_iskalnik", mock.MagicMock()):
            ok, r = klic("preimenujDatoteko", [f, "b.txt"])
        self.assertTrue(r["ok"])
        self.assertEqual(shramba.stanje()["datoteke"][0]["pot"], os.path.join(mapa, "b.txt"))
        self.assertEqual(klic("priljubljenoSeznam", [])[1]["datoteke"][0]["ime"], "b.txt")
        klic("priljubljenoVrstniRed", ["programi", ["ta:x"]])
        klic("priljubljenoKategorija", ["ta:x", "igre"])
        self.assertEqual(shramba.stanje()["kategorije"], {"ta:x": "igre"})
        ok, r = klic("predogledDatoteke", [os.path.join(mapa, "b.txt")])
        self.assertEqual(r["nacin"], "besedilo")


if __name__ == "__main__":
    unittest.main()
