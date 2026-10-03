"""Iskanje datotek z indeksom (core/os_iskalnik.py).

Prej je vsaka črka znova hodila po disku (največ 1,5 s, do 60 zadetkov, po širini): globoke datoteke niso bile najdene.
Indeks najde po vsej globini, brez šumnikov, z več besedami in razvrsti po ujemanju.
"""
import os
import shutil
import sys
import tempfile
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)
from core import os_datoteke  # noqa: E402
from core import os_iskalnik as I  # noqa: E402


class Osnova(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="safeer-isk-")
        self.dom = os.path.join(self.tmp, "dom")
        os.makedirs(self.dom)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pisi(self, *deli, starost_dni=0):
        pot = os.path.join(self.dom, *deli)
        os.makedirs(os.path.dirname(pot), exist_ok=True)
        with open(pot, "w", encoding="utf-8") as f:
            f.write("x")
        if starost_dni:
            kdaj = time.time() - starost_dni * 86400
            os.utime(pot, (kdaj, kdaj))
        return pot

    def indeks(self, **k):
        idx = I.Indeks(self.dom, **k)
        idx.zgradi()
        return idx

    def poti(self, idx, niz, meja=60):
        return [os.path.relpath(z[0], self.dom) for z in idx.isci(niz, meja)]


class TestIndeks(Osnova):
    def test_kljuc_brez_sumnikov(self):
        self.assertEqual(I.kljuc("ČŠŽ đ Ł é ß Ö"), "csz d l e ss o")
        self.assertEqual(I.kljuc("Navadno Ime.TXT"), "navadno ime.txt")

    def test_najde_po_vsej_globini_in_brez_sumnikov(self):
        self.pisi("Dokumenti", "a", "b", "c", "d", "Letno poročilo 2024.odt")
        self.pisi("Čopič.png")
        idx = self.indeks()
        globoka = os.path.join("Dokumenti", "a", "b", "c", "d", "Letno poročilo 2024.odt")
        self.assertEqual(self.poti(idx, "porocilo"), [globoka])
        self.assertEqual(self.poti(idx, "POROČILO"), [globoka])
        self.assertEqual(self.poti(idx, "copic"), ["Čopič.png"])
        self.assertEqual(self.poti(idx, "ni-takega-imena"), [])

    def test_vec_besed_v_poljubnem_vrstnem_redu(self):
        for ime in ("Račun Telekom 2024-03.pdf", "Račun Elektro 2024-03.pdf", "Račun Telekom 2023-11.pdf"):
            self.pisi("Računi", ime)
        idx = self.indeks()
        self.assertEqual(self.poti(idx, "racun telekom 2024"), [os.path.join("Računi", "Račun Telekom 2024-03.pdf")])
        self.assertEqual(self.poti(idx, "2024 telekom"), [os.path.join("Računi", "Račun Telekom 2024-03.pdf")])
        self.assertEqual(len(self.poti(idx, "racun")), 4)                        # tri datoteke in mapa Računi
        self.assertEqual(self.poti(idx, "telekom elektro"), [])

    def test_razvrstitev_po_ujemanju(self):
        self.pisi("globoko", "x", "plan.txt")       # celo ime (brez končnice), čeprav globlje
        self.pisi("planiranje.txt")                 # začetek imena
        self.pisi("moj-plan.txt")                   # začetek besede v imenu
        self.pisi("eksplanacija.txt")               # sredina besede
        idx = self.indeks()
        self.assertEqual(self.poti(idx, "plan"),
                         [os.path.join("globoko", "x", "plan.txt"), "planiranje.txt", "moj-plan.txt", "eksplanacija.txt"])

    def test_preskoci_skrite_mape_kodo_in_povezave(self):
        self.pisi(".skrito", "tajni-plan.txt")
        self.pisi("node_modules", "paket", "plan.js")
        self.pisi("projekt", "plan.md")
        self.pisi("z\nnovo-vrstico-plan.txt")
        os.symlink(os.path.join(self.dom, "projekt"), os.path.join(self.dom, "bliznjica"))
        idx = self.indeks()
        self.assertEqual(self.poti(idx, "plan"), [os.path.join("projekt", "plan.md")])
        self.assertEqual(self.poti(idx, "node_modules"), ["node_modules"])       # mapa je vidna, njena vsebina ne
        self.assertEqual(self.poti(idx, "bliznjica"), ["bliznjica"])             # povezavi ne sledimo (brez podvojenih)

    def test_meja_vnosov_pusti_plitve(self):
        for mapa in ("a", "b", "c"):
            self.pisi(mapa, "notri-" + mapa + ".txt")
        self.pisi("zgoraj.txt")
        idx = self.indeks(najvec=3)
        self.assertTrue(idx.nepopoln)
        self.assertEqual(self.poti(idx, "zgoraj"), ["zgoraj.txt"])
        self.assertEqual(self.poti(idx, "notri"), [])
        cel = self.indeks()
        self.assertFalse(cel.nepopoln)
        self.assertEqual(len(self.poti(cel, "notri")), 3)

    def test_strnjen_zapis(self):
        for i in range(500):
            self.pisi("m%02d" % (i % 20), "datoteka-%04d.txt" % i)
        idx = self.indeks()
        kljuci, _zk, imena = idx._podatki[0], idx._podatki[1], idx._podatki[2]
        self.assertEqual(idx.vnosov, 520)
        self.assertLess(len(kljuci) + len(imena), 520 * 2 * 20, "imena so v dveh nizih bajtov, ne v predmetih")
        self.assertEqual(self.poti(idx, "datoteka-0499"), [os.path.join("m19", "datoteka-0499.txt")])


class TestIskanje(Osnova):
    def setUp(self):
        super().setUp()
        self.prej = I._indeks
        I._indeks = I.Indeks(self.dom)

    def tearDown(self):
        I._indeks = self.prej
        super().tearDown()

    def test_prvo_iskanje_pocaka_na_indeks(self):
        # Stran po tipkanju pošlje ENO poizvedbo: že ta mora dobiti odgovor iz indeksa (majhna mapa je prehojena takoj).
        pot = self.pisi("a", "b", "Načrt.txt")
        self.assertFalse(I.indeks().pripravljen())
        zadetki = I.isci("nacrt")
        self.assertEqual([e["pot"] for e in zadetki], [pot])
        self.assertTrue(I.indeks().pripravljen())
        self.assertEqual(set(zadetki[0]), set(os_datoteke.isci("nacrt", self.dom)[0]), "enaka oblika kot hoja po disku")

    def test_pocasna_gradnja_ne_zadrzi_iskanja(self):
        pot = self.pisi("Načrt 2024.txt")
        idx = I.indeks()
        prava = idx.zgradi
        idx.zgradi = lambda: (time.sleep(0.6), prava())[1]
        rok, I.CAKAJ_PRVI_INDEKS_S = I.CAKAJ_PRVI_INDEKS_S, 0.1
        try:
            zacetek = time.monotonic()
            # Velika mapa, hladen disk: odgovori hoja po disku - z istimi pravili (brez šumnikov, več besed).
            self.assertEqual([e["pot"] for e in I.isci("2024 nacrt")], [pot])
            self.assertLess(time.monotonic() - zacetek, 0.5)
            self.assertFalse(idx.pripravljen())
            self.assertTrue(idx.pocakaj(3))
            self.assertEqual([e["pot"] for e in I.isci("2024 nacrt")], [pot])
        finally:
            I.CAKAJ_PRVI_INDEKS_S = rok

    def test_izbrisana_izpade_nova_pride_po_obnovi(self):
        stara = self.pisi("stara.txt")
        I.indeks().zgradi()
        os.remove(stara)
        self.pisi("nova stara.txt")
        self.assertEqual(I.isci("stara"), [])                 # izbrisane ni več, nove indeks še ne pozna
        self.assertFalse(I.indeks().star())
        I.zastarel()                                          # Safeer je sam nekaj spremenil
        self.assertFalse(I.indeks().star(), "takoj po gradnji ne gradimo znova")
        I.indeks().zgrajen -= I.NAJMANJ_MED_GRADNJAMA_S + 1
        self.assertTrue(I.indeks().star())
        I.indeks().zgradi()
        self.assertEqual([e["ime"] for e in I.isci("stara")], ["nova stara.txt"])
        I.indeks().zgrajen -= I.STAROST_S + 1                 # star indeks se obnovi tudi brez znane spremembe
        self.assertTrue(I.indeks().star())

    def test_nedavno_spremenjena_je_prej(self):
        self.pisi("zapisnik a.txt", starost_dni=400)          # krajše ime bi bilo sicer prvo
        self.pisi("zapisnik bbbbbb.txt")
        I.indeks().zgradi()
        self.assertEqual([e["ime"] for e in I.isci("zapisnik")], ["zapisnik bbbbbb.txt", "zapisnik a.txt"])
        # Svežina ne preglasi vrste ujemanja: začetek imena ostane pred sredino besede.
        self.pisi("zapis.txt", starost_dni=400)
        self.pisi("prezapis.txt")
        I.indeks().zgradi()
        self.assertEqual([e["ime"] for e in I.isci("zapis")][0], "zapis.txt")

    def test_kratka_poizvedba_in_meja(self):
        for i in range(80):
            self.pisi("slika%03d.jpg" % i)
        I.indeks().zgradi()
        self.assertEqual(I.isci("s"), [])
        self.assertEqual(len(I.isci("slika")), os_datoteke.NAJVEC_ZADETKOV)
        self.assertEqual(len(I.isci("slika", 200)), 80)

    def test_nepopoln_indeks_dopolni_hoja_po_disku(self):
        for mapa in ("a", "b", "c"):
            self.pisi(mapa, "notri-" + mapa + ".txt")
        I._indeks = I.Indeks(self.dom, najvec=3)
        I.indeks().zgradi()
        self.assertEqual(len(I.isci("notri")), 3)


class TestVgradnja(unittest.TestCase):
    """safeer_os.py ob uvozu potrebuje GTK, zato beremo izvorno kodo."""

    def beri(self, *pot):
        with open(os.path.join(KOREN, *pot), encoding="utf-8") as f:
            return f.read()

    def test_most_isce_v_indeksu(self):
        vir = self.beri("safeer_os.py")
        self.assertIn('"isciDatoteke": lambda: os_iskalnik.isci(', vir)
        self.assertNotIn('"isciDatoteke": lambda: os_datoteke.isci(', vir, "hoja po disku ob vsaki črki")
        self.assertIn("min(300, max(1, int(a[1])))", vir, "stran ne sme zahtevati neomejeno zadetkov")

    def test_safeerjeve_spremembe_oznacijo_indeks_za_starega(self):
        vir = self.beri("safeer_os.py")
        for metoda in ("novaMapa", "novaDatoteka", "preimenujDatoteko", "vSmeti", "prilepiDatoteke", "obnoviIzSmeti",
                       "razveljaviDatoteke"):
            self.assertIn('"%s"' % metoda, vir[vir.index("    SPREMINJAJO_DATOTEKE = frozenset("):][:400], metoda)
        self.assertIn("if metoda in self.SPREMINJAJO_DATOTEKE:\n                        os_iskalnik.zastarel()", vir)

    def test_indeks_se_zgradi_kmalu_po_zagonu(self):
        vir = self.beri("safeer_os.py")
        self.assertIn("GLib.timeout_add_seconds(12, lambda: (os_iskalnik.indeks().zgradi_v_ozadju(), False)[1])", vir)

    def test_modul_je_v_tovoru_in_razdelek_dobi_vec_zadetkov(self):
        self.assertIn(" os_iskalnik ", self.beri("packaging", "install_os_payload.sh"))
        self.assertIn('klic("isciDatoteke", [S.datotekeIskanje, 200])', self.beri("assets", "os", "os.js"))


if __name__ == "__main__":
    unittest.main()
