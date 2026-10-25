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
            # Skupni slovar namizja (QML in delovna povrsina): vseh 6 jezikov.
            self.assertEqual(len(re.findall(r"\b" + kljuc + ":", open(os.path.join(KOREN, "assets", "os", "besedila-namizja.js"),
                                                                     encoding="utf-8").read())), 6, kljuc)

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


STREZNIK = {"base_url": "https://192.168.0.20:8443", "fp": "ab" * 32, "token": "z"}


class SliciceInDeli(unittest.TestCase):
    """Lastnik 25. 10. 2026: slicice in vse datoteke povezanih naprav (Android link-datoteke: /thumb, next_offset)."""

    def setUp(self):
        p = mock.patch.object(safeer_os, "_STREZNIKI_NAPRAV", {})
        p.start()
        self.addCleanup(p.stop)

    def test_del_mape_in_streznik_iz_lastnega_odgovora(self):
        klici = []

        def control(metoda, *a):
            klici.append((metoda,) + a)
            return {"ok": True, "items": [], "server": STREZNIK, "next_offset": 1000}
        with mock.patch.object(safeer_os, "_v_ozjem_krogu", return_value=True), \
                mock.patch.object(safeer_os, "_control_naprave", control):
            safeer_os.datoteke_naprave("n-tel", "media:camera")
            safeer_os.datoteke_naprave("n-tel", "media:camera", 500)
        self.assertEqual(klici, [("Datoteke", "n-tel", "media:camera"),
                                 ("DatotekeDel", "n-tel", "media:camera", '{"offset": 500}')])
        slicice = mock.Mock()
        slicice.dobi.return_value = {"media:image:1": "/tmp/x.jpg"}
        with mock.patch.object(safeer_os, "_v_ozjem_krogu", return_value=True), \
                mock.patch.object(safeer_os, "_SLICICE_NAPRAV", slicice):
            r = safeer_os.slicice_naprave("n-tel", [{"id": "media:image:1", "modified": 5, "size": 9, "server": "tuj"}])
        self.assertEqual(r, {"media:image:1": "file:///tmp/x.jpg"})
        naprava, streznik, vnosi = slicice.dobi.call_args[0]
        self.assertEqual((naprava, streznik), ("n-tel", STREZNIK), "streznik iz odgovora naprave, ne iz strani")
        self.assertEqual(vnosi, [{"id": "media:image:1", "modified": 5, "size": 9}])

    def test_brez_ozjega_kroga_ali_seznama_nic(self):
        safeer_os._STREZNIKI_NAPRAV["n-tel"] = STREZNIK
        slicice = mock.Mock()
        with mock.patch.object(safeer_os, "_v_ozjem_krogu", return_value=False), \
                mock.patch.object(safeer_os, "_SLICICE_NAPRAV", slicice):
            self.assertEqual(safeer_os.slicice_naprave("n-tel", [{"id": "media:image:1"}]), {})
            self.assertEqual(safeer_os.datoteke_naprave("n-tel", "", 500)["koda"], "ni_ozji_krog")
        with mock.patch.object(safeer_os, "_v_ozjem_krogu", return_value=True), \
                mock.patch.object(safeer_os, "_SLICICE_NAPRAV", slicice):
            self.assertEqual(safeer_os.slicice_naprave("n-druga", [{"id": "media:image:1"}]), {}, "naprava brez seznama")
            self.assertEqual(safeer_os.slicice_naprave("n-tel", "ni seznam"), {})
        slicice.dobi.assert_not_called()

    def test_qml_slicice_in_nalozi_vec(self):
        with open(os.path.join(KOREN, "assets", "os", "qml", "Datoteke.qml"), encoding="utf-8") as f:
            qml = f.read()
        self.assertIn('koren.klic("sliciceNaprave"', qml)
        self.assertIn('koren.klic("datotekeNaprave", [naprava, vir.pot, odmik]', qml)
        with open(os.path.join(KOREN, "assets", "os", "besedila-namizja.js"), encoding="utf-8") as f:
            besedila = f.read()
        for kljuc in ("naloziVec", "naloziVecOd", "napravaDeliIzbrane"):
            self.assertEqual(len(re.findall(r"\b" + kljuc + ":", besedila)), 6, kljuc)


class ProsnjaZaDostop(unittest.TestCase):
    """Android link-datoteke: files.request_access brez parametrov; razlog notifications / off."""

    def test_prosnja_samo_ozjemu_krogu_in_razlog(self):
        klici = []

        def control(metoda, *a):
            klici.append((metoda,) + a)
            return {"ok": True, "data": {"shown": False, "reason": "notifications", "x": "<b>"}}
        with mock.patch.object(safeer_os, "_v_ozjem_krogu", return_value=True), \
                mock.patch.object(safeer_os, "_control_naprave", control):
            r = safeer_os.prosi_dostop_naprave("n-tel")
        self.assertEqual(r, {"ok": True, "shown": False, "reason": "notifications"})
        self.assertEqual(klici, [("Ukaz", "n-tel", "files.request_access", "{}")])
        with mock.patch.object(safeer_os, "_v_ozjem_krogu", return_value=True), \
                mock.patch.object(safeer_os, "_control_naprave", lambda *a: {"ok": True, "data": {"reason": "tuje"}}):
            self.assertEqual(safeer_os.prosi_dostop_naprave("n-tel")["reason"], "", "neznan razlog se ne prenese")
        with mock.patch.object(safeer_os, "_v_ozjem_krogu", return_value=False), \
                mock.patch.object(safeer_os, "_control_naprave") as c:
            self.assertEqual(safeer_os.prosi_dostop_naprave("n-tel")["koda"], "ni_ozji_krog")
        c.assert_not_called()
        with open(os.path.join(KOREN, "assets", "os", "besedila-namizja.js"), encoding="utf-8") as f:
            besedila = f.read()
        for kljuc in ("prosiZaDostop", "prosnjaPrikazana", "prosnjaObvestila", "prosnjaIzklopljeno"):
            self.assertEqual(len(re.findall(r"\b" + kljuc + ":", besedila)), 6, kljuc)


class ControlDelSeznama(unittest.TestCase):
    def test_parametri_samo_znani_in_omejeni(self):
        import safeer_control
        f = safeer_control.link_daljinec_del_seznama
        self.assertEqual(f('{"offset": 500, "limit": 9999, "from": 1, "x": 2}'), {"offset": 500, "from": 1})
        self.assertEqual(f('{"offset": -1, "limit": true}'), {})
        self.assertEqual(f("ni json"), {})
        self.assertEqual(f("[1]"), {})
        self.assertEqual(safeer_control._celo_stevilo("12"), 12)
        self.assertEqual(safeer_control._celo_stevilo(True), 0)


if __name__ == "__main__":
    unittest.main()
