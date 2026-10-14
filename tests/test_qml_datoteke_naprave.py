"""Lupina QML na Linuxu: datoteke z druge naprave (prenesiDatotekoNaprave, odpriDatotekoTukaj) - 14. 10. 2026.

Datoteke.qml (ista kot na Windows) je klicala metodi, ki ju Linux ni imel; datoteka z naprave se je odprla z napako."""
import os
import re
import unittest
from unittest import mock

import safeer_os

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DatotekeNaprave(unittest.TestCase):
    def test_metodi_sta_v_mostu(self):
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            vir = f.read()
        for metoda in ("prenesiDatotekoNaprave", "odpriDatotekoTukaj"):
            self.assertIn('"%s":' % metoda, vir)
        with open(os.path.join(KOREN, "assets", "os", "qml", "Datoteke.qml"), encoding="utf-8") as f:
            qml = f.read()
        self.assertIn('"prenesiDatotekoNaprave", [naprava, e.id, e.ime, streznik, mape]', qml)
        for kljuc in ("odprtoV", "odprtoNaNapravi", "teamworkTudi"):
            self.assertEqual(len(re.findall(kljuc + ":", open(os.path.join(KOREN, "assets", "os", "qml", "Namizje.qml"),
                                                                encoding="utf-8").read())), 2, kljuc)   # sl in en

    def test_prenos_gre_prek_nadaljuj_tukaj(self):
        klici = []
        naprave = {"naprave": [{"id": "n-1", "ime": "Prenosnik"}]}
        with mock.patch.object(safeer_os, "_control_naprave", lambda m, *a: naprave if m == "Seznam" else {}), \
                mock.patch.object(safeer_os, "nadaljuj_tukaj", lambda *a: klici.append(a) or {"ok": True}):
            r = safeer_os.prenesi_datoteko_naprave("n-1", "share:0:a/b.txt", "b.txt", {"base_url": "x"}, ["Mapa", "", "Pod"])
        self.assertTrue(r["ok"])
        streznik, kljuc, oznaka, naprava, ime, pot_imen, _z = klici[0]
        self.assertEqual((oznaka, naprava, ime, pot_imen), ("share:0:a/b.txt", "n-1", "Prenosnik", ["Mapa", "Pod", "b.txt"]))

    def test_odpri_na_napravi_brez_locenega_zaslona(self):
        ukazi = []

        def control(metoda, *a):
            ukazi.append((metoda,) + a)
            if a[1:2] == ("files.open_locen",):
                return {"ok": False, "koda": "ni_locenega_zaslona"}
            return {"ok": True}
        with mock.patch.object(safeer_os, "_control_naprave", control), \
                mock.patch.object(safeer_os, "upravljaj_racunalnik", lambda i: {"ok": True, "naprava": i}):
            r = safeer_os.odpri_na_napravi_tukaj("n-1", "share:0:x.odt")
        self.assertEqual(r, {"ok": True, "naprava": "n-1"})
        self.assertEqual([u[2] for u in ukazi], ["files.open_locen", "files.open"])


if __name__ == "__main__":
    unittest.main()
