"""Posiljanje datotek s tega racunalnika na napravo (core/link_posiljanje.py) in koda napake sredisca brez teh poti."""
import os
import tempfile
import threading
import time
import unittest

from core import link_deljenje, link_posiljanje


class PosiljanjeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.klici = []
        self.izid = (True, {})
        self.cakaj = None
        self.p = link_posiljanje.Posiljanje(self._poslji, lambda i: {"tv1": "Televizor"}.get(i, ""))

    def _poslji(self, naprava, pot, napredek):
        self.klici.append((naprava, os.path.basename(pot)))
        napredek(50)
        if self.cakaj is not None:
            self.cakaj.wait(5)
        napredek(100)
        return self.izid

    def _datoteka(self, ime, velikost=10):
        pot = os.path.join(self.tmp.name, ime)
        with open(pot, "wb") as f:
            f.write(b"x" * velikost)
        return pot

    def _do_konca(self, id_):
        for _ in range(200):
            s = self.p.stanje(id_)
            if s["stanje"] != "posiljam":
                return s
            time.sleep(0.01)
        self.fail("posiljanje se ni koncalo")

    def test_vec_datotek_po_vrsti_z_napredkom(self):
        self.cakaj = threading.Event()
        a, b = self._datoteka("a.txt", 100), self._datoteka("b.txt", 300)
        r = self.p.zacni("tv1", [a, b, a])
        self.assertTrue(r["ok"])
        self.assertEqual((r["naprava"], r["datotek"], r["stanje"]), ("Televizor", 2, "posiljam"), "ista pot samo enkrat")
        for _ in range(200):
            if self.klici:
                break
            time.sleep(0.01)
        s = self.p.stanje(r["id"])
        self.assertEqual((s["ime"], s["poslanih"], s["odstotek"]), ("a.txt", 0, 12), "polovica prve od 400 bajtov")
        self.cakaj.set()
        s = self._do_konca(r["id"])
        self.assertEqual((s["stanje"], s["poslanih"], s["odstotek"], s["koda"]), ("poslano", 2, 100, ""))
        self.assertEqual(self.klici, [("tv1", "a.txt"), ("tv1", "b.txt")])

    def test_napaka_ustavi_vrsto_in_pove_razlog(self):
        self.izid = (False, {"sporocilo": "Ciljna naprava ni povezana.", "koda": "naprava_ni_povezana", "zasedenaOd": ""})
        r = self.p.zacni("tv1", [self._datoteka("a.txt"), self._datoteka("b.txt")])
        s = self._do_konca(r["id"])
        self.assertEqual((s["stanje"], s["koda"], s["poslanih"], s["ime"]), ("napaka", "naprava_ni_povezana", 0, "a.txt"))
        self.assertEqual(len(self.klici), 1, "po napaki naslednjih ne posilja")

    def test_izjema_pri_oddaji_ne_podre_niti(self):
        def pade(_n, _p, _napredek):
            raise OSError("omrezje")
        p = link_posiljanje.Posiljanje(pade)
        r = p.zacni("tv1", [self._datoteka("a.txt")])
        for _ in range(200):
            s = p.stanje(r["id"])
            if s["stanje"] != "posiljam":
                break
            time.sleep(0.01)
        self.assertEqual((s["stanje"], s["koda"]), ("napaka", "posiljanje_ni_uspelo"))
        self.assertEqual(s["naprava"], "tv1", "brez imena ostane id")

    def test_mape_se_ne_posiljajo(self):
        mapa = os.path.join(self.tmp.name, "Mapa")
        os.mkdir(mapa)
        self.assertEqual(self.p.zacni("tv1", [mapa]), {"ok": False, "koda": "samo_mape", "mape": 1})
        r = self.p.zacni("tv1", [mapa, self._datoteka("a.txt")])
        self.assertEqual((r["ok"], r["datotek"], r["mape"]), (True, 1, 1))
        self._do_konca(r["id"])

    def test_zavrnitve(self):
        self.assertEqual(self.p.zacni("", [self._datoteka("a.txt")])["koda"], "ni_naprave")
        self.assertEqual(self.p.zacni("tv1", [])["koda"], "ni_datoteke")
        self.assertEqual(self.p.zacni("tv1", [os.path.join(self.tmp.name, "ni-je.txt")])["koda"], "ni_datoteke")
        self.assertEqual(self.p.zacni("tv1", "ni seznam")["koda"], "ni_datoteke")
        self.assertEqual(self.p.stanje("neznan"), {"ok": False, "koda": "ni_posiljke"})
        prevec = [self._datoteka("d%d.txt" % i, 1) for i in range(link_posiljanje.NAJVEC_DATOTEK + 1)]
        self.assertEqual(self.p.zacni("tv1", prevec)["koda"], "prevec_datotek")
        self.assertEqual(self.klici, [])

    def test_prevelika_datoteka(self):
        pot = self._datoteka("velika.bin", 20)
        stara = link_posiljanje.NAJVECJA_DATOTEKA
        link_posiljanje.NAJVECJA_DATOTEKA = 10
        try:
            self.assertEqual(self.p.zacni("tv1", [pot])["koda"], "prevelika")
        finally:
            link_posiljanje.NAJVECJA_DATOTEKA = stara

    def test_koncana_posiljanja_ne_rastejo_brez_meje(self):
        pot = self._datoteka("a.txt")
        idji = []
        for _ in range(link_posiljanje.NAJVEC_KONCANIH + 8):
            r = self.p.zacni("tv1", [pot])
            idji.append(r["id"])
            self._do_konca(r["id"])
        self.assertLessEqual(len(self.p._posiljke), link_posiljanje.NAJVEC_KONCANIH)
        self.assertTrue(self.p.stanje(idji[-1])["ok"], "zadnje stanje je se na voljo")
        self.assertFalse(self.p.stanje(idji[0])["ok"])


class NapakaSredisca(unittest.TestCase):
    def test_sredisce_brez_poti_dobi_svojo_kodo(self):
        # Racunalnik kot sredisce pred 2.1.45: PUT /cast/file -> 501, POST /cast/share/text -> 404 »ni_poti«.
        for koda, odgovor in ((501, {}), (405, {}), (404, {}), (404, {"error": "Ni te poti.", "error_code": "ni_poti"})):
            self.assertEqual(link_deljenje.napaka_huba(koda, odgovor)["koda"], "sredisce_ne_zna", (koda, odgovor))

    def test_druge_napake_ostanejo(self):
        n = link_deljenje.napaka_huba(404, {"napaka": "ciljna naprava ni povezana", "koda": "naprava_ni_povezana"})
        self.assertEqual((n["koda"], n["sporocilo"]), ("naprava_ni_povezana", "ciljna naprava ni povezana"))
        n = link_deljenje.napaka_huba(409, {"napaka": "zasedena", "koda": "naprava_zasedena", "busy_by": "Tablica"})
        self.assertEqual((n["koda"], n["zasedenaOd"]), ("naprava_zasedena", "Tablica"))
        self.assertEqual(link_deljenje.napaka_huba(401, {"error": "Naprava ni seznanjena.", "error_code": "naprava_ni_seznanjena"})["koda"],
                         "naprava_ni_seznanjena")
        self.assertEqual(link_deljenje.napaka_huba(500, {})["sporocilo"], "Hub je odgovoril 500")


if __name__ == "__main__":
    unittest.main()
