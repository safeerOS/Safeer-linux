"""Deljenje zaslona in zvok na napravo: tihe povezave v omrezju ne smejo zadrzati prave naprave (neodvisni pregled
19. 10. 2026). Prej se je vsaka povezava obdelala po vrsti z rokom ROKOVANJE_S (10 s) - dve ali tri tihe so pokrile
ves cas cakanja. Zdaj ima vsaka svojo nit in rok (core/link_vticnik.sprejmi_s_pozdravom), cez mejo se zapre najstarejsa.
Vse samo na 127.0.0.1."""
import shutil
import socket
import ssl
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from core import link_datoteke, link_vticnik, link_zaslon, link_zvok


class TihePovezave(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapa = tempfile.mkdtemp(prefix="safeer-pozdrav-vzporedno-")
        kljuc, potrdilo, _ = link_datoteke.zagotovi_potrdilo(cls.mapa)
        cls.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.ctx.load_cert_chain(potrdilo, kljuc)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.mapa, ignore_errors=True)

    def _pravi(self, port, pozdrav, izid):
        k = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        k.check_hostname = False
        k.verify_mode = ssl.CERT_NONE
        try:
            s = k.wrap_socket(socket.create_connection(("127.0.0.1", port), timeout=10))
            s.sendall(pozdrav.encode())
            izid["pravi"] = s
        except OSError as e:
            izid["napaka"] = e

    def _preveri(self, modul, sprejmi, pozdrav, tihih):
        posluh = socket.socket()
        posluh.bind(("127.0.0.1", 0))
        posluh.listen(64)
        port = posluh.getsockname()[1]
        izid, tihe = {}, []
        try:
            with mock.patch.object(modul, "ROKOVANJE_S", 10.0, create=True), \
                    mock.patch.object(modul, "CAKANJE_S", 30, create=True):
                nit = threading.Thread(target=lambda: izid.update(sprejeto=sprejmi(posluh, self.ctx)), daemon=True)
                nit.start()
                for _ in range(tihih):           # odprejo TCP in ne posljejo nicesar (ne rokovanja ne pozdrava)
                    tihe.append(socket.create_connection(("127.0.0.1", port), timeout=10))
                    time.sleep(0.02)
                time.sleep(0.3)                  # tihe so ze sprejete in v rokovanju
                zacetek = time.monotonic()
                pravi = threading.Thread(target=self._pravi, args=(port, pozdrav, izid), daemon=True)
                pravi.start()
                nit.join(8.0)
                trajalo = time.monotonic() - zacetek
        finally:
            for s in tihe:
                s.close()
            for s in (izid.get("pravi"), izid.get("sprejeto")):
                s = s[0] if isinstance(s, tuple) else s
                if s is not None:
                    s.close()
            posluh.close()
        self.assertIsNotNone(izid.get("sprejeto"), "tihe povezave so zadrzale pravo napravo")
        self.assertLess(trajalo, 4.0)

    def test_zaslon_stiri_tihe(self):
        z = link_zaslon.Zaslon(tls_mapa=self.mapa)
        z._zeton = "pravi-zeton"
        self._preveri(link_zaslon, z._sprejmi, "SAFEER-ZASLON pravi-zeton\n", 4)

    def test_zvok_stiri_tihe(self):
        z = link_zvok.ZvokNaNapravo(tls_mapa=self.mapa, ffmpeg=sys.executable)
        z._zeton = "pravi-zeton"
        self._preveri(link_zvok, z._sprejmi, "SAFEER-ZVOK pravi-zeton\n", 4)

    def test_cez_mejo_se_izrine_najstarejsa(self):
        """Vec tihih, kot je NAJVEC_HKRATNIH_POZDRAVOV: nova povezava izrine najstarejso, prava naprava pride skozi."""
        z = link_zvok.ZvokNaNapravo(tls_mapa=self.mapa, ffmpeg=sys.executable)
        z._zeton = "pravi-zeton"
        self._preveri(link_zvok, z._sprejmi, "SAFEER-ZVOK pravi-zeton\n", link_vticnik.NAJVEC_HKRATNIH_POZDRAVOV + 6)

    def test_izrinjena_se_zapre_in_niti_so_omejene(self):
        """Koncni pregled b8e39da: wrap_socket surovo vticnico odklopi pred rokovanjem, zato izrinjanje ni zaprlo
        povezave - vsaka je obdrzala nit in deskriptor do roka. Izrinjena tiha povezava mora biti pri odjemalcu zaprta
        v manj kot sekundi, zivih niti pozdrava pa nikoli vec kot NAJVEC_NITI_POZDRAVA."""
        posluh = socket.socket()
        posluh.bind(("127.0.0.1", 0))
        posluh.listen(128)
        port = posluh.getsockname()[1]
        z = link_zvok.ZvokNaNapravo(tls_mapa=self.mapa, ffmpeg=sys.executable)
        z._zeton = "pravi-zeton"
        izid, tihe, najvec_niti = {}, [], [0]
        try:
            with mock.patch.object(link_zvok, "ROKOVANJE_S", 10.0), mock.patch.object(link_zvok, "CAKANJE_S", 30):
                nit = threading.Thread(target=lambda: izid.update(sprejeto=z._sprejmi(posluh, self.ctx)), daemon=True)
                nit.start()
                for _ in range(60):
                    tihe.append(socket.create_connection(("127.0.0.1", port), timeout=10))
                    najvec_niti[0] = max(najvec_niti[0], sum(1 for t in threading.enumerate()
                                                             if t.name == "safeer-pozdrav"))
                    time.sleep(0.005)
                time.sleep(1.0)
                zaprte = 0
                for s in tihe:
                    s.settimeout(0.05)
                    try:
                        zaprte += s.recv(1) == b""
                    except socket.timeout:
                        pass
                    except OSError:
                        zaprte += 1                 # ECONNRESET: tudi zaprta
                pravi = threading.Thread(target=self._pravi, args=(port, "SAFEER-ZVOK pravi-zeton\n", izid), daemon=True)
                pravi.start()
                nit.join(8.0)
        finally:
            for s in tihe:
                s.close()
            for s in (izid.get("pravi"), izid.get("sprejeto")):
                if s is not None:
                    s.close()
            posluh.close()
        self.assertGreaterEqual(zaprte, 60 - link_vticnik.NAJVEC_HKRATNIH_POZDRAVOV, "izrinjene povezave so ostale odprte")
        self.assertLessEqual(najvec_niti[0], link_vticnik.NAJVEC_NITI_POZDRAVA)
        self.assertIsNotNone(izid.get("sprejeto"), "prava naprava pride skozi tudi po poplavi")

    def test_brez_povezave_vrne_none(self):
        """Varovalka: brez naprave se cakanje konca ob CAKANJE_S (zvok je prej tu vrgel socket.timeout)."""
        posluh = socket.socket()
        posluh.bind(("127.0.0.1", 0))
        posluh.listen(4)
        try:
            z = link_zvok.ZvokNaNapravo(tls_mapa=self.mapa, ffmpeg=sys.executable)
            z._zeton = "pravi-zeton"
            with mock.patch.object(link_zvok, "CAKANJE_S", 0.5):
                zacetek = time.monotonic()
                self.assertIsNone(z._sprejmi(posluh, self.ctx))
                self.assertLess(time.monotonic() - zacetek, 3.0)
        finally:
            posluh.close()


if __name__ == "__main__":
    unittest.main()
