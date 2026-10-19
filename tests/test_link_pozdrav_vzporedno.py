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

    def test_izrinjanje_ne_zapre_tuje_stevilke(self):
        """Pregled 72d1d79: glavna nit je izrinjeno vticnico zaprla (close) - stevilka deskriptorja se je sprostila in
        nit pozdrava bi jo lahko zaprla, ko jo je jedro ze dalo drugi povezavi istega procesa. Glavna nit sme izrinjeno
        samo zbuditi (shutdown); zapre jo nit, ki jo ima - odjemalec izrinjene povezave dobi konec.
        sprejmi_s_pozdravom klicemo neposredno z najvec_hkrati=2 (privzeti argument se veze ob definiciji, pregled
        92e0d6a), 5 tihih povezav -> 3 izrinjenja."""
        posluh = socket.socket()
        posluh.bind(("127.0.0.1", 0))
        posluh.listen(64)
        port = posluh.getsockname()[1]
        tihe, zbujene, zaprte_glavna = [], [], []
        pravi_zbudi = getattr(link_vticnik, "_zbudi_tiho", lambda s: None)
        pravi_zapri = link_vticnik._zapri_tiho

        def zbudi(s):
            if s is not None:
                zbujene.append(threading.current_thread().name)
            pravi_zbudi(s)

        def zapri(s):
            if s is not None and threading.current_thread().name == "preizkus-sprejem":
                zaprte_glavna.append(s)
            pravi_zapri(s)

        izid = {}
        try:
            with mock.patch.object(link_vticnik, "_zbudi_tiho", side_effect=zbudi, create=True), \
                    mock.patch.object(link_vticnik, "_zapri_tiho", side_effect=zapri):
                nit = threading.Thread(target=lambda: izid.update(sprejeto=link_vticnik.sprejmi_s_pozdravom(
                    posluh, self.ctx, lambda _v: False, link_zvok.ZvokNaNapravo._preberi_vrstico,
                    time.monotonic() + 2.0, 10.0, najvec_hkrati=2)), name="preizkus-sprejem", daemon=True)
                nit.start()
                for _ in range(5):
                    tihe.append(socket.create_connection(("127.0.0.1", port), timeout=10))
                    time.sleep(0.1)
                time.sleep(0.5)
                konec_pri_odjemalcu = 0
                for s in tihe[:3]:                  # najstarejse tri so izrinjene
                    s.settimeout(1.0)
                    try:
                        konec_pri_odjemalcu += s.recv(1) == b""
                    except socket.timeout:
                        pass
                    except OSError:
                        konec_pri_odjemalcu += 1
                nit.join(20)
        finally:
            for s in tihe:
                s.close()
            posluh.close()
        self.assertEqual(len(zbujene), 3, "vsaka izrinjena povezava se zbudi enkrat")
        self.assertTrue(all(ime == "preizkus-sprejem" for ime in zbujene))
        self.assertEqual(zaprte_glavna, [], "glavna nit izrinjene vticnice ne zapre (close)")
        self.assertEqual(konec_pri_odjemalcu, 3, "nit pozdrava izrinjeno povezavo zapre sama")

    def test_meja_niti_zapre_novo_povezavo_brez_niti(self):
        """Ko je zivih niti pozdrava NAJVEC_NITI_POZDRAVA, nova povezava ne dobi niti (zapre se takoj)."""
        posluh = socket.socket()
        posluh.bind(("127.0.0.1", 0))
        posluh.listen(64)
        port = posluh.getsockname()[1]
        z = link_zvok.ZvokNaNapravo(tls_mapa=self.mapa, ffmpeg=sys.executable)
        z._zeton = "pravi-zeton"
        izid, tihe = {}, []
        try:
            # NAJVEC_NITI_POZDRAVA se bere ob izvajanju; meja hkratnih ostane privzetih 8 (vec od 5 povezav).
            with mock.patch.object(link_vticnik, "NAJVEC_NITI_POZDRAVA", 2), \
                    mock.patch.object(link_zvok, "ROKOVANJE_S", 10.0), mock.patch.object(link_zvok, "CAKANJE_S", 3):
                nit = threading.Thread(target=lambda: izid.update(sprejeto=z._sprejmi(posluh, self.ctx)), daemon=True)
                nit.start()
                for _ in range(5):
                    tihe.append(socket.create_connection(("127.0.0.1", port), timeout=10))
                    time.sleep(0.05)
                time.sleep(0.5)
                niti = sum(1 for t in threading.enumerate() if t.name == "safeer-pozdrav")
                zaprte = 0
                for s in tihe:
                    s.settimeout(0.2)
                    try:
                        zaprte += s.recv(1) == b""
                    except socket.timeout:
                        pass
                    except OSError:
                        zaprte += 1
                nit.join(20)
        finally:
            for s in tihe:
                s.close()
            posluh.close()
        self.assertLessEqual(niti, 2)
        self.assertGreaterEqual(zaprte, 3, "povezave cez mejo niti so zaprte takoj")

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
