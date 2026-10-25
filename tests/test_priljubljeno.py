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
        self.assertEqual(st["datoteke"][0]["vrsta"], "dokument")
        self.assertEqual(len(self.dogodki), 1)
        # Isto stanje se enkrat: brez zapisa in brez dogodka.
        self.s.preklopi("datoteka", self.f, True)
        self.assertEqual(len(self.dogodki), 1)
        st = self.s.preklopi("datoteka", self.f)
        self.assertEqual(st["datoteke"], [])
        self.assertEqual(len(self.dogodki), 2)

    def test_v_smeteh_skrita_ob_obnovi_na_istem_mestu(self):
        """Lastnik, 15. 10. 2026: v Smeti gre tudi priljubljena; ni je nikjer; obnovljena se vrne na svoje mesto."""
        g, h = os.path.join(self.mapa, "g.txt"), os.path.join(self.mapa, "h.txt")
        for p in (g, h):
            open(p, "w").close()
        for p in (g, self.f, h):
            self.s.preklopi("datoteka", p)
        self.s.osvezi()
        n = len(self.dogodki)
        smeti = os.path.join(self.mapa, "Smeti")
        os.mkdir(smeti)
        os.rename(self.f, os.path.join(smeti, "a.txt"))                 # »V Smeti«
        st = self.s.osvezi()
        self.assertEqual([d["pot"] for d in st["datoteke"]], [g, h])
        self.assertNotIn("obstaja", st["datoteke"][0])
        self.assertEqual(len(self.dogodki), n + 1)                       # namizji dobita dogodek
        self.s.osvezi()
        self.assertEqual(len(self.dogodki), n + 1)                       # brez spremembe brez dogodka
        # Vrstni red, ki ga uporabnik medtem spremeni, skrite ne premakne.
        self.s.vrstni_red("datoteke", [h, g])
        os.rename(os.path.join(smeti, "a.txt"), self.f)                 # Obnovi / Razveljavi
        st = self.s.osvezi()
        self.assertEqual([d["pot"] for d in st["datoteke"]], [h, self.f, g])
        self.assertEqual(len(self.dogodki), n + 3)

    def test_izpraznjene_smeti_in_30_dni(self):
        g = os.path.join(self.mapa, "usb", "film.mkv")
        os.makedirs(os.path.dirname(g))
        open(g, "w").close()
        self.s.preklopi("datoteka", self.f)
        self.s.preklopi("datoteka", g)
        os.remove(self.f)                                                # izpraznjene Smeti: trajno izbrisano
        shutil.rmtree(os.path.dirname(g))                               # odklopljen USB
        self.s.odstrani_poti([self.f])
        with open(self.s.pot, encoding="utf-8") as f:
            self.assertEqual([d["pot"] for d in json.load(f)["datoteke"]], [g])
        # USB: dokler ga ni manj kot 30 dni, zapis ostane (skrit); po tem se pozabi - razen ce je v Smeteh.
        zdaj = [10 ** 9]
        self.s.cas = lambda: zdaj[0]
        self.s.v_smeteh = lambda: [os.path.dirname(g)]
        with open(self.s.pot, encoding="utf-8") as f:
            videno = json.load(f)["datoteke"][0]["videno"]
        zdaj[0] = videno + priljubljeno.POZABI_PO - 10
        self.assertEqual(self.s.stanje()["datoteke"], [])
        with open(self.s.pot, encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["datoteke"]), 1)
        zdaj[0] = videno + priljubljeno.POZABI_PO + 10
        self.s.stanje()
        with open(self.s.pot, encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["datoteke"]), 1)           # mapa je v Smeteh: ostane
        self.s.v_smeteh = lambda: []
        self.s.stanje()
        with open(self.s.pot, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["datoteke"], [])

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
        self.assertEqual(st["programi"], ["ta:c", "ta:b", "ta:a"])       # izpusceni (skriti) ostane na svojem mestu
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
        self.assertEqual([d["pot"] for d in self.s.vrstni_red("datoteke", [g, self.f])["datoteke"]], [g, self.f])

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


class PregledShrambe(unittest.TestCase):
    """Popravki neodvisnega pregleda (15. 10. 2026) - vsak preizkus je padel pred popravkom."""

    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mapa, True)
        self.dogodki = []
        self.s = priljubljeno.Priljubljeno(os.path.join(self.mapa, "cfg", "priljubljeno.json"), self.dogodki.append)

    def _zapis(self, podatki):
        os.makedirs(os.path.dirname(self.s.pot), exist_ok=True)
        with open(self.s.pot, "w", encoding="utf-8") as f:
            json.dump(podatki, f)

    def _datoteke_v_zapisu(self):
        with open(self.s.pot, encoding="utf-8") as f:
            return [d["pot"] for d in json.load(f)["datoteke"]]

    def test_zapis_brez_casa_ni_pozabljen_zaradi_drugega(self):
        """Ena stara skrita s casom in ena brez casa (prejsnja razlicica): brez casa mora dobiti 30 dni, ne izginiti."""
        stara, brez = os.path.join(self.mapa, "stara.txt"), os.path.join(self.mapa, "brez.txt")
        self._zapis({"datoteke": [{"pot": stara, "videno": 1000.0}, {"pot": brez}]})
        self.s.cas = lambda: 1000.0 + priljubljeno.POZABI_PO + 5
        self.s.v_smeteh = lambda: []
        self.s.stanje()
        self.assertEqual(self._datoteke_v_zapisu(), [brez])

    def test_pokvarjen_zapis_ostane_kot_kopija(self):
        self._zapis({"programi": ["ta:gimp.desktop"]})
        with open(self.s.pot, "a", encoding="utf-8") as f:
            f.write("}}")
        st = self.s.preklopi("program", "ta:x")                  # pisanje po pokvarjenem: prej je izvirnik izgubljen
        self.assertEqual(st["programi"], ["ta:x"])
        with open(self.s.pot + ".pokvarjeno", encoding="utf-8") as f:
            self.assertIn("ta:gimp.desktop", f.read())

    def test_osvezi_ne_zaklene_samega_sebe(self):
        """osvezi drzi zaklep datoteke in klice stanje: drugi flock v istem procesu bi cakal za vedno."""
        t = threading.Thread(target=self.s.osvezi, daemon=True)
        t.start()
        t.join(5)
        self.assertFalse(t.is_alive(), "osvezi je obvisel")
        self.assertEqual(len(self.dogodki), 1)

    def test_vec_datotek_ena_sprememba_in_rod(self):
        poti = []
        for ime in ("a", "b", "c"):
            poti.append(os.path.join(self.mapa, ime))
            open(poti[-1], "w").close()
        self.s.preklopi("datoteka", poti[0])
        rod = self.s.stanje()["rod"]
        n = len(self.dogodki)
        st = self.s.preklopi("datoteke", [{"pot": p, "ime": os.path.basename(p)} for p in poti])
        self.assertEqual([d["pot"] for d in st["datoteke"]], poti)          # brez podvojene »a«
        self.assertEqual(len(self.dogodki), n + 1)                          # en dogodek za vse
        self.assertGreater(st["rod"], rod)
        st = self.s.preklopi("datoteke", poti)                              # vse so: odstrani vse
        self.assertEqual(st["datoteke"], [])
        self.assertEqual(self.s.preklopi("datoteke", "ni seznam")["datoteke"], [])

    def test_meje_dolzine_in_stevila(self):
        self.assertEqual(self.s.preklopi("datoteka", "/" + "a" * 5000)["datoteke"], [])
        with mock.patch.object(priljubljeno, "NAJVEC_KATEGORIJ", 3):
            for i in range(5):
                self.s.kategorija("ta:p%d" % i, "igre")
            self.assertEqual(list(self.s.stanje()["kategorije"]), ["ta:p2", "ta:p3", "ta:p4"])

    def test_zapis_samo_za_uporabnika(self):
        self.s.preklopi("program", "ta:x")
        self.assertEqual(os.stat(self.s.pot).st_mode & 0o777, 0o600)

    def test_dogodki_po_vrsti_sprememb(self):
        """Dogodek gre pod zaklepom: zadnji dogodek je vedno koncno stanje (prej sta se dve niti lahko prehiteli)."""
        niti = [threading.Thread(target=self.s.preklopi, args=("program", "ta:p%d" % i)) for i in range(20)]
        for n in niti:
            n.start()
        for n in niti:
            n.join()
        self.assertEqual(len(self.dogodki[-1]["programi"]), 20)
        rodovi = [d["rod"] for d in self.dogodki]
        self.assertEqual(rodovi, sorted(rodovi))


class Predogled(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mapa, True)
        # Vrednost samo zamenjamo in vrnemo; brisanje spremenljivke v procesu z nitmi (unsetenv) ni dovoljeno (AGENTS.md).
        prej = os.environ.get("XDG_CACHE_HOME")      # pod pytest vedno nastavljena (korenski conftest.py)
        self.addCleanup(lambda: os.environ.pop("XDG_CACHE_HOME", None) if prej is None
                        else os.environ.__setitem__("XDG_CACHE_HOME", prej))
        os.environ["XDG_CACHE_HOME"] = os.path.join(self.mapa, "cache")

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

    def test_cev_namesto_datoteke_ne_obvisi(self):
        """Datoteka, zamenjana s cevjo med preverjanjem in branjem: branje ne caka na pisca (nit mostu bi obvisela)."""
        cev = os.path.join(self.mapa, "zamenjana.txt")
        os.mkfifo(cev)
        izid = []
        t = threading.Thread(target=lambda: izid.append(self._beri_varno(cev)), daemon=True)
        t.start()
        t.join(5)
        self.assertFalse(t.is_alive(), "branje cevi je obviselo")
        self.assertEqual(izid, ["ni_navadna"])
        # Ce stat pokaze navadno datoteko, odpre pa se cev: predogled vrne napako, ne obvisi.
        resnicni = os.stat
        with mock.patch.object(os_datoteke.os, "stat", lambda p, *a, **k: resnicni(__file__) if p == cev else resnicni(p, *a, **k)):
            r = os_datoteke.predogled(cev)
        self.assertEqual((r["ok"], r["napaka"]), (False, "ni_navadna"))

    @staticmethod
    def _beri_varno(pot):
        try:
            os_datoteke._besedilo_z_zacetka(pot)
            return "prebrano"
        except OSError as e:
            return str(e)

    def test_pdf_pokvarjen_izhod_ni_v_predpomnilniku(self):
        """pdftoppm, ki pade ali ga prekine casovna meja, ne pusti pokvarjene slike, ki bi jo predogled nato vedno kazal.
        PDF se nikoli ne razclenjuje v procesu Safeer OS (Poppler GI) - en pokvarjen PDF bi podrl namizje."""
        orodja = os.path.join(self.mapa, "bin")
        os.mkdir(orodja)
        orodje = os.path.join(orodja, "pdftoppm")
        with open(orodje, "w") as f:
            f.write('#!/bin/sh\nfor a; do z="$a"; done\nprintf "\\211PNG polovica" > "$z.png"\nexit 1\n')
        os.chmod(orodje, 0o755)
        pdf = self._pot("d.pdf", b"%PDF-1.4 pokvarjen")
        r = os_datoteke.predogled(pdf, najdi=lambda ime: orodje if ime == "pdftoppm" else None)
        self.assertEqual((r["nacin"], r.get("brezOrodja")), ("podatki", True))
        mapa = os_datoteke._mapa_predogledov()
        self.assertEqual(os.listdir(mapa), [])
        self.assertEqual(os.stat(mapa).st_mode & 0o777, 0o700)
        with mock.patch.dict("sys.modules", {"gi": None}):          # brez orodja: Popplerja v procesu ne poskusi
            self.assertEqual(os_datoteke.predogled(pdf, najdi=lambda _i: None)["brezOrodja"], True)

    def test_predpomnilnik_predogledov_omejen(self):
        mapa = os_datoteke._mapa_predogledov()
        os.makedirs(mapa)
        for i in range(8):
            p = os.path.join(mapa, "%02d.png" % i)
            open(p, "w").close()
            os.utime(p, (1000 + i, 1000 + i))
        os_datoteke._pospravi_predoglede(mapa, 5)
        self.assertEqual(sorted(os.listdir(mapa)), ["%02d.png" % i for i in range(3, 8)])

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
        r = os_datoteke.v_smeti_vec(["/x%d" % i for i in range(os_datoteke.NAJVEC_NAENKRAT + 1)])
        self.assertEqual((r["napaka"], r["najvec"]), ("prevec", os_datoteke.NAJVEC_NAENKRAT))   # namizje pove mejo
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


class PreselitevDelovnePovrsine(unittest.TestCase):
    """delovna.js: stare priljubljene iz localStorage gredo enkrat v Safeer OS, nato localStorage ni vec vir."""

    @unittest.skipUnless(shutil.which("node"), "node ni namescen")
    def test_enkrat_v_safeer_os(self):
        import subprocess
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "assets", "os", "delovna.js"), encoding="utf-8") as f:
            js = f.read()
        blok = js[js.index("  var PR = {"):js.index("  // Vecje besedilo in manj prosojnosti")]
        koda = """
var assert = require("assert");
var N = { priljubljeneDat: [{ pot: "/d/a.txt", ime: "a.txt" }], priljubljeniPrg: ["ta:gimp.desktop"], kategorije: { "ta:x": "igre" }, pogled: "seznam" };
var D = { vir: null }, shranjeno = 0, klici = [], izrisano = 0;
function shrani() { shranjeno++; }
function izrisiPrograme() { izrisano++; }
function odpriVir() {}
var stanje = { datoteke: [], programi: [], kategorije: {}, nastavitve: { programiPogled: "mreza" }, preseljeno: false };
function klic(m, a) {
  klici.push([m, a]);
  if (m === "priljubljenoPreseli") stanje = { datoteke: [{ pot: "/d/a.txt", obstaja: true }], programi: ["ta:gimp.desktop"],
                                              kategorije: { "ta:x": "igre" }, nastavitve: { programiPogled: "seznam" }, preseljeno: true };
  return Promise.resolve(stanje);
}
""" + blok + """
naloziPriljubljene().then(function () {
  assert.deepStrictEqual(klici.map(function (k) { return k[0]; }), ["priljubljenoSeznam", "priljubljenoPreseli"]);
  assert.deepStrictEqual(klici[1][1][0].priljubljeniPrg, ["ta:gimp.desktop"]);
  assert.strictEqual(klici[1][1][0].pogled, "seznam");
  assert.deepStrictEqual([N.priljubljeneDat, N.priljubljeniPrg, N.kategorije], [[], [], {}]);   // localStorage ni vec vir
  assert.ok(shranjeno > 0 && izrisano > 0);
  assert.strictEqual(PR.programi[0], "ta:gimp.desktop");
  assert.strictEqual(N.pogled, "seznam");
  klici = [];
  return naloziPriljubljene();
}).then(function () {
  assert.deepStrictEqual(klici.map(function (k) { return k[0]; }), ["priljubljenoSeznam"]);    // drugic: brez prenosa
}).catch(function (e) { console.error(e); process.exit(1); });
"""
        subprocess.run(["node", "-e", koda], check=True)


class MeniDelovnePovrsine(unittest.TestCase):
    """delovna.js: »Poslji na napravo« in »Pretvori za televizor« samo, ko delujeta (predpomnjeno, osvezeno ob odprtju
    menija in spremembi Linka) - lastnik, 15. 10. 2026: nic nedelujocega."""

    @unittest.skipUnless(shutil.which("node"), "node ni namescen")
    def test_vnosi_samo_ko_delujejo(self):
        import subprocess
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "assets", "os", "delovna.js"), encoding="utf-8") as f:
            js = f.read()

        def funkcija(ime):
            z = js.index("  function %s(" % ime)
            return js[z:js.index("\n  }\n", z) + 4]
        koda = """
var assert = require("assert");
var most = true, odgovori = {}, klici = [], meni = null, prerisano = 0;
var D = { sprejmejo: [], tvMozna: false, shrambaMozna: false, vir: { vrsta: "lokalno" }, izbrani: {} }, O = { poti: [] };
function t(k) { return k; }
function klic(m) { klici.push(m); return m in odgovori ? Promise.resolve(odgovori[m]) : Promise.reject(new Error(m)); }
function pokaziMeni(m) { meni = m.map(function (x) { return x[0]; }); }
function zgradiStranDatotek() { prerisano++; }
function jePriljubljena() { return false; }
function pretvorljiva() { return false; }
function postavkeNovo() {}
var lok = [];
function izbraniVnosi() { return lok; }
function izbraniLokalni() { return lok; }
function steviloElementov(n) { return String(n); }
var ciljiRod = 0, NAJVEC_V_MENIJU = 3;
function posljiNaNapravo() {}
function izberiNapravoInPoslji() {}
""" + funkcija("osveziCilje") + funkcija("meniDatoteke") + funkcija("meniVec") + funkcija("postavkePosiljanja") + """
var video = { pot: "/d/film.mkv", ime: "film.mkv", vrsta: "video", mapa: false };
var mapa = { pot: "/d/M", ime: "M", mapa: true };
function pocakaj() { return new Promise(function (r) { setTimeout(r, 10); }); }
meniDatoteke(video, 0, 0);
assert.ok(meni.indexOf("posljiNa") < 0 && meni.indexOf("pretvori") < 0 && meni.indexOf("shraniNaNapravo") < 0, meni.join());
meniDatoteke(mapa, 0, 0);
assert.ok(meni.indexOf("pretvoriMapo") < 0 && meni.indexOf("posljiNa") < 0);
// Odprtje menija osvezi predpomnilnik: naprava je zdaj povezana in pretvorba dela.
odgovori.napraveZaPosiljanje = [{ id: "tv1", ime: "TV" }];
odgovori.pretvorbaZaTvMozna = { ok: true, shramba: true };
klici = [];
osveziCilje();
pocakaj().then(function () {
  assert.deepStrictEqual(klici, ["napraveZaPosiljanje", "pretvorbaZaTvMozna"]);
  assert.strictEqual(prerisano, 1);                         // nov cilj spusta: stran datotek se prerise
  meniDatoteke(video, 0, 0);
  // Ena naprava: neposredno »Poslji na …« (en klik), brez izbire.
  assert.ok(meni.indexOf("posljiNa") >= 0 && meni.indexOf("posljiNaNapravo") < 0 && meni.indexOf("pretvori") >= 0 && meni.indexOf("shraniNaNapravo") >= 0, meni.join());
  meniDatoteke(mapa, 0, 0);
  assert.ok(meni.indexOf("pretvoriMapo") >= 0 && meni.indexOf("posljiNa") >= 0, "mapa gre na napravo cela");
  lok = [video, { pot: "/d/b.txt", ime: "b.txt" }, mapa];
  meniVec(0, 0);
  assert.ok(meni.indexOf("posljiNa") >= 0);
  // Vec kot tri naprave: prve tri neposredno, ostale v izbiri.
  D.sprejmejo = [1, 2, 3, 4].map(function (i) { return { id: "n" + i, ime: "N" + i }; });
  meniVec(0, 0);
  assert.strictEqual(meni.filter(function (x) { return x === "posljiNa"; }).length, 3);
  assert.ok(meni.indexOf("posljiNaNapravo") >= 0);
  // Naprava odklopljena, Control ne odgovori: vnosa izgineta ob naslednjem odprtju.
  odgovori.napraveZaPosiljanje = [];
  delete odgovori.pretvorbaZaTvMozna;
  meniVec(0, 0);
  return pocakaj();
}).then(function () {
  meniVec(0, 0);
  assert.ok(meni.indexOf("posljiNa") < 0 && meni.indexOf("posljiNaNapravo") < 0);
  meniDatoteke(video, 0, 0);
  assert.ok(meni.indexOf("posljiNa") < 0 && meni.indexOf("pretvori") < 0 && meni.indexOf("shraniNaNapravo") < 0, meni.join());
}).catch(function (e) { console.error(e); process.exit(1); });
"""
        subprocess.run(["node", "-e", koda], check=True)


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
        # V Smeti (pravi os_datoteke z Smetmi v zacasni mapi) -> skrita + dogodek; Razveljavi -> spet na istem mestu.
        b, c = os.path.join(mapa, "b.txt"), os.path.join(mapa, "c.txt")
        open(c, "w").close()
        klic("priljubljenoPreklopi", ["datoteka", c])
        smeti = os.path.join(mapa, "Smeti")
        os.makedirs(os.path.join(smeti, "files"))
        os.makedirs(os.path.join(smeti, "info"))

        def v_smeti(pot):
            ime = os.path.basename(pot)
            os.rename(pot, os.path.join(smeti, "files", ime))
            with open(os.path.join(smeti, "info", ime + ".trashinfo"), "w") as f:
                f.write("[Trash Info]\nPath=%s\nDeletionDate=2026-10-15T10:00:00\n" % pot)
        with mock.patch.object(so, "os_iskalnik", mock.MagicMock()), \
                mock.patch("core.link_urejanje.v_smeti", v_smeti), \
                mock.patch.object(os_datoteke, "_mapa_smeti", lambda: smeti):
            n = len(dogodki)
            ok, r = klic("vSmetiVec", [[b]])
            self.assertEqual(r["idji"], ["b.txt"])
            self.assertEqual([d["pot"] for d in dogodki[-1]["datoteke"]], [c])
            self.assertEqual(len(dogodki), n + 1)
            ok, r = klic("razveljaviDatoteke", [{"vrsta": "smeti", "idji": r["idji"]}])
            self.assertEqual(r["narejeno"], 1)
            self.assertEqual([d["pot"] for d in dogodki[-1]["datoteke"]], [b, c])
            # Spet v Smeti in Smeti izpraznjene (potrditev v sistemskem oknu): zapis za b izbrisan, c ostane.
            klic("vSmeti", [b])
            self.assertEqual([d["pot"] for d in dogodki[-1]["datoteke"]], [c])
            gotovo.clear()
            so.SafeerOS._obdelaj_klic(jaz, Pogled(), 1, "izprazniSmeti", [])
            odlocitev = jaz._potrdi_izpraznitev_smeti.call_args[0][0]
            odlocitev(True)
            self.assertTrue(gotovo.wait(5))
        with open(shramba.pot, encoding="utf-8") as f:
            self.assertEqual([d["pot"] for d in json.load(f)["datoteke"]], [c])

    def test_delno_izpraznjene_smeti(self):
        """Ce praznjenje Smeti ne izbrise vsega, ostane zapis za tisto, kar je se v Smeteh (obnova ga vrne)."""
        import safeer_os as so
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa, True)
        shramba = priljubljeno.Priljubljeno(os.path.join(mapa, "p.json"))
        b, c = os.path.join(mapa, "b.txt"), os.path.join(mapa, "c.txt")
        shramba.preklopi("datoteke", [b, c], True)
        v_smeteh = [{"izvirna": b}, {"izvirna": c}]
        gotovo = threading.Event()

        class Pogled:
            def qml_odgovor(self, *_a):
                gotovo.set()

        def izprazni():
            del v_smeteh[0]                       # c se ni dalo izbrisati
            return {"ok": False, "izbrisano": 1}
        jaz = mock.MagicMock()
        jaz._katalog_most.return_value.pozna.return_value = False
        jaz._odgovori = lambda p, i, ok, d: so.SafeerOS._odgovori(jaz, p, i, ok, d)
        jaz._priljubljeno = lambda: shramba
        with mock.patch.object(os_datoteke, "smeti", lambda: {"elementi": list(v_smeteh)}), \
                mock.patch.object(os_datoteke, "izprazni_smeti", izprazni):
            so.SafeerOS._obdelaj_klic(jaz, Pogled(), 1, "izprazniSmeti", [])
            jaz._potrdi_izpraznitev_smeti.call_args[0][0](True)
            self.assertTrue(gotovo.wait(5))
        with open(shramba.pot, encoding="utf-8") as f:
            self.assertEqual([d["pot"] for d in json.load(f)["datoteke"]], [c])

    def test_pretvorba_za_tv_mozna(self):
        """»Pretvori za televizor« samo, ko dela: Control tece in (ffmpeg ali naprava, ki pretvorbo zna)."""
        import safeer_os as so
        naprave = {"ok": True, "naprave": [{"id": "pc", "ta": True, "zmoznosti": ["files"], "platforma": "linux"},
                                           {"id": "pc2", "zmoznosti": ["files"], "platforma": "windows"}]}
        with mock.patch.object(so, "_control_naprave", return_value=naprave):
            self.assertFalse(so.pretvorba_za_tv_mozna(najdi=lambda _i: None)["ok"])          # samo namizne naprave
            r = so.pretvorba_za_tv_mozna(najdi=lambda _i: "/usr/bin/ffmpeg")
            self.assertEqual((r["ok"], r["shramba"]), (True, False))     # ffmpeg pretvori tu, shraniti pa nima kam
        naprave["naprave"].append({"id": "tv", "zmoznosti": ["files"], "platforma": "android"})
        with mock.patch.object(so, "_control_naprave", return_value=naprave):
            r = so.pretvorba_za_tv_mozna(najdi=lambda _i: None)
        self.assertEqual((r["ok"], r["naprave"], r["shramba"]), (True, 1, True))
        with mock.patch.object(so, "_control_naprave", return_value={"ok": False, "koda": "ni_controla"}):
            self.assertFalse(so.pretvorba_za_tv_mozna(najdi=lambda _i: "/usr/bin/ffmpeg")["ok"])   # brez Controla nic

    def test_osvezitev_ob_spremembah_zdruzena(self):
        """1000 sprememb v spremljani mapi: ena osvezitev priljubljenih, ne 1000 niti."""
        import safeer_os as so
        jaz = mock.MagicMock()
        jaz._prilj_caka = False
        casovniki = []
        with mock.patch.object(so.GLib, "timeout_add", lambda ms, f: casovniki.append(f)):
            for _ in range(1000):
                so.SafeerOS._priljubljene_osvezi_v_ozadju(jaz)
            self.assertEqual(len(casovniki), 1)
            with mock.patch.object(so.threading, "Thread") as nit:
                casovniki[0]()
                nit.call_args[1]["target"]()
            jaz._priljubljeno.return_value.osvezi.assert_called_once()
            so.SafeerOS._priljubljene_osvezi_v_ozadju(jaz)                  # po osvezitvi spet sprejme
            self.assertEqual(len(casovniki), 2)


if __name__ == "__main__":
    unittest.main()
