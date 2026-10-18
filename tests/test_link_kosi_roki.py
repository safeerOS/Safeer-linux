"""Opis kosov (`/kosi/<id>`, prek Huba `/cast/kosi/<id>`) ima roke kot sprejem popravka (pregled 18. 10. 2026).

Prej: cakanje na mesto za racunanje brez roka (dve pocasni datoteki sta za vedno ustavili vse naslednje zahteve),
racunanje brez roka (tudi ko odjemalec ni vec cakal) in pisanje odgovora prek Huba brez roka.
"""
import io
import os
import shutil
import tempfile
import threading
import unittest
from unittest import mock

from core import link_datoteke as ld


class _Povezava:
    def __init__(self):
        self.roki = []

    def settimeout(self, s):
        self.roki.append(s)


class _Obravnava:
    def __init__(self):
        self.headers = {"X-Safeer-Token": "z"}
        self.connection = _Povezava()
        self.wfile = io.BytesIO()
        self.kode = []
        self.command = "GET"
        self.close_connection = False

    def send_response(self, koda):
        self.kode.append(koda)

    def send_header(self, *_a):
        pass

    def end_headers(self):
        pass


class _Mape:
    def __init__(self, pot):
        self.pot = pot

    def razresi(self, _oznaka):
        return ("share:0", self.pot)


class _Streznik:
    def __init__(self, pot):
        self.mape = _Mape(pot)

    def zeton_velja(self, *_a, **_k):
        return True


class RokiOpisa(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-kosi-")
        self.pot = os.path.join(self.mapa, "a.bin")
        with open(self.pot, "wb") as d:
            d.write(os.urandom(200_000))
        ld._opisi.clear()

    def tearDown(self):
        ld._opisi.clear()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_brez_mesta_po_roku_zasedeno(self):
        ob = _Obravnava()
        for _ in range(2):                         # obe mesti zasedeta pocasni datoteki
            self.assertTrue(ld._OPISI_HKRATI.acquire(timeout=1))
        try:
            with mock.patch.object(ld, "CAKAJ_NA_OPIS_S", 0.2):
                nit = threading.Thread(target=ld.postrezi_kose, args=(ob, _Streznik(self.pot), "share:0:a.bin", False),
                                       daemon=True)
                nit.start()
                nit.join(5)
            self.assertFalse(nit.is_alive(), "zahteva ne sme cakati na mesto brez roka")
            self.assertEqual(ob.kode, [503])
        finally:
            for _ in range(2):
                ld._OPISI_HKRATI.release()

    def test_racunanje_po_roku_se_ustavi(self):
        ob = _Obravnava()
        with mock.patch.object(ld, "ROK_RACUNANJA_OPISA_S", -1.0):
            ld.postrezi_kose(ob, _Streznik(self.pot), "share:0:a.bin", False)
        self.assertEqual(ob.kode, [503])
        # mesto se je sprostilo
        self.assertTrue(ld._OPISI_HKRATI.acquire(timeout=0.1))
        ld._OPISI_HKRATI.release()

    def test_pisanje_odgovora_z_rokom(self):
        ob = _Obravnava()
        ld.postrezi_kose(ob, _Streznik(self.pot), "share:0:a.bin", False)
        self.assertEqual(ob.kode, [200])
        self.assertIn(ld.ROK_PISANJA_OPISA_S, ob.connection.roki)
        self.assertGreater(len(ob.wfile.getvalue()), 0)


if __name__ == "__main__":
    unittest.main()
