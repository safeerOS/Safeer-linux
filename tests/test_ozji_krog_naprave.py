"""Ozji krog zaupanja (»Schengen«, core/link_dostop): samo naprave v njem Safeer OS pokaze in odpre za ogled programov,
datotek in zaslona. Lastnik, 17. 10. 2026: »Telefon, ki ni v ozjem krogu zaupanja, med napravami za ogled programov in
datotek ne smemo niti videti.«"""
import os
import re
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import safeer_os  # noqa: E402

NAPRAVE = {"ok": True, "naprave": [
    {"id": "n-jaz", "ime": "Ta", "zmoznosti": ["apps", "files"], "ta": True, "ozji": True},
    {"id": "n-tablica", "ime": "Tablica", "zmoznosti": ["remote", "files"], "platforma": "tablet", "ozji": True},
    {"id": "n-tuji", "ime": "Tuji telefon", "zmoznosti": ["remote", "files"], "platforma": "phone", "ozji": False},
    {"id": "n-star", "ime": "Brez polja", "zmoznosti": ["remote", "files"], "platforma": "phone"},
]}


def _control(klici=None):
    def f(metoda, *a):
        if klici is not None:
            klici.append((metoda,) + a)
        if metoda == "Seznam":
            return NAPRAVE
        return {"ok": True, "items": []}
    return f


class OzjiKrog(unittest.TestCase):
    def test_programi_samo_ozji_krog(self):
        with mock.patch.object(safeer_os, "_control_naprave", _control()):
            self.assertEqual([n["id"] for n in safeer_os.naprave_s_programi()], ["n-tablica"])

    def test_datoteke_samo_ozji_krog(self):
        with mock.patch.object(safeer_os, "_control_naprave", _control()):
            self.assertEqual([n["id"] for n in safeer_os.naprave_z_datotekami()], ["n-tablica"])

    def test_neposreden_klic_za_tujo_napravo_zavrnjen(self):
        klici = []
        with mock.patch.object(safeer_os, "_control_naprave", _control(klici)):
            self.assertEqual(safeer_os.programi_naprave("n-tuji")["koda"], "ni_ozji_krog")
            self.assertEqual(safeer_os.datoteke_naprave("n-tuji")["koda"], "ni_ozji_krog")
            self.assertEqual(safeer_os.upravljaj_racunalnik("n-tuji")["koda"], "ni_ozji_krog")
        # tuja naprava ne dobi nobenega ukaza (samo branje seznama)
        self.assertEqual({k[0] for k in klici}, {"Seznam"})

    def test_ozji_krog_dela(self):
        klici = []
        with mock.patch.object(safeer_os, "_control_naprave", _control(klici)):
            self.assertTrue(safeer_os.programi_naprave("n-tablica")["ok"])
        self.assertIn(("Aplikacije", "n-tablica"), klici)

    def test_vse_naprave_nosijo_ozji(self):
        with mock.patch.object(safeer_os, "_control_naprave", _control()):
            po_id = {n["id"]: n["ozji"] for n in safeer_os.vse_naprave()}
        self.assertEqual(po_id, {"n-jaz": True, "n-tablica": True, "n-tuji": False, "n-star": False})

    def test_control_seznam_nosi_ozji(self):
        with open(os.path.join(KOREN, "safeer_control.py"), encoding="utf-8") as f:
            vir = f.read()
        self.assertIn('"ozji": _v_ozjem_krogu(n.get("id", ""))', vir)

    def test_upravljanje_zaslona_v_strani_samo_ozji(self):
        with open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertRegex(js, r"var jeRacunalnik = !n\.ta && n\.ozji &&")
        self.assertTrue(re.search(r"glavni\.ozji = !!\(glavni\.ozji \|\| drugi\.ozji\)", js))


if __name__ == "__main__":
    unittest.main()
