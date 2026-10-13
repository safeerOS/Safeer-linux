"""DoH posrednik govori tudi SOCKS5 (13. 10. 2026).

libsoup prek posrednika http HTTP/2 izklopi, prek SOCKS5 pa ne (od 3.6). github.com je bil zato hladno 1171 ms
namesto 600 ms. Ti testi preverijo, da SOCKS5 velja ista pravila kot HTTP CONNECT (vrata, DoH, samo javni naslovi)
in da ostane HTTP CONNECT na istih vratih nespremenjen."""
import os
import socket
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.doh_proxy as doh_proxy  # noqa: E402
from core.doh_proxy import LocalDoHProxy  # noqa: E402


class Razresevalnik:
    provider = "preizkus"

    def __init__(self, imena):
        self.imena = imena
        self.vprasana = []
        self.pozabljena = []

    def resolve(self, hostname, timeout=3.5):
        self.vprasana.append(hostname)
        return self.imena.get(hostname)

    def pozabi(self, hostname):
        self.pozabljena.append(hostname)


class Odmev:
    """Streznik na 127.0.0.1, ki vrne, kar dobi."""

    def __init__(self):
        self.s = socket.socket()
        self.s.bind(("127.0.0.1", 0))
        self.s.listen(8)
        self.vrata = self.s.getsockname()[1]
        threading.Thread(target=self._tek, daemon=True).start()

    def _tek(self):
        while True:
            try:
                c, _ = self.s.accept()
            except OSError:
                return
            threading.Thread(target=self._en, args=(c,), daemon=True).start()

    @staticmethod
    def _en(c):
        with c:
            while True:
                d = c.recv(4096)
                if not d:
                    return
                c.sendall(d)

    def zapri(self):
        self.s.close()


def _beri(s, n):
    d = b""
    while len(d) < n:
        k = s.recv(n - len(d))
        if not k:
            break
        d += k
    return d


class Socks5(unittest.TestCase):

    def setUp(self):
        self.odmev = Odmev()
        self.res = Razresevalnik({"primer.test": "127.0.0.1"})
        self.posrednik = LocalDoHProxy(self.res, dovoli_lokalno=True)
        # Povratni naslov je vedno zavrnjen; za preizkusni odmev ga dovolimo samo, ko je lokalno vklopljeno.
        pravi = doh_proxy.je_dovoljen_cilj
        cilj = mock.patch.object(doh_proxy, "je_dovoljen_cilj",
                                 lambda n, lok=False: (lok and n == "127.0.0.1") or pravi(n, lok))
        cilj.start()
        self.addCleanup(cilj.stop)
        self.posrednik.start()

    def tearDown(self):
        self.posrednik.stop()
        self.odmev.zapri()

    def _pozdrav(self, metode=b"\x00"):
        s = socket.create_connection(("127.0.0.1", self.posrednik.actual_port), timeout=5)
        s.sendall(b"\x05" + bytes([len(metode)]) + metode)
        return s, _beri(s, 2)

    def _zahteva(self, ime, vrata):
        s, pozdrav = self._pozdrav()
        self.assertEqual(pozdrav, b"\x05\x00")
        s.sendall(b"\x05\x01\x00\x03" + bytes([len(ime)]) + ime + vrata.to_bytes(2, "big"))
        return s, _beri(s, 10)

    def test_ime_gre_prek_doh_in_tunel_dela(self):
        s, odg = self._zahteva(b"primer.test", self.odmev.vrata)
        with s:
            self.assertEqual(odg[:2], b"\x05\x00")
            s.sendall(b"zdravo")
            self.assertEqual(_beri(s, 6), b"zdravo")
        self.assertEqual(self.res.vprasana, ["primer.test"])

    def test_prepovedana_vrata_koda_2(self):
        s, odg = self._zahteva(b"primer.test", 22)
        s.close()
        self.assertEqual(odg[:2], b"\x05\x02")
        self.assertEqual(self.res.vprasana, [])

    def test_ime_brez_naslova_koda_4(self):
        s, odg = self._zahteva(b"ni.test", 443)
        s.close()
        self.assertEqual(odg[:2], b"\x05\x04")

    def test_lokalni_cilj_brez_dovoljenja_koda_2(self):
        self.posrednik.dovoli_lokalno = False
        s, odg = self._zahteva(b"primer.test", self.odmev.vrata)
        s.close()
        self.assertEqual(odg[:2], b"\x05\x02")

    def test_naslov_ipv4_brez_doh_a_s_preverjanjem(self):
        self.posrednik.dovoli_lokalno = False
        s, pozdrav = self._pozdrav()
        s.sendall(b"\x05\x01\x00\x01" + socket.inet_aton("169.254.169.254") + (80).to_bytes(2, "big"))
        odg = _beri(s, 10)
        s.close()
        self.assertEqual(odg[:2], b"\x05\x02")
        self.assertEqual(self.res.vprasana, [])

    def test_samo_prijava_zavrnjena(self):
        s, pozdrav = self._pozdrav(b"\x02")
        s.close()
        self.assertEqual(pozdrav, b"\x05\xff")

    def test_bind_ni_podprt(self):
        s, _ = self._pozdrav()
        s.sendall(b"\x05\x02\x00\x03\x0bprimer.test\x01\xbb")
        odg = _beri(s, 10)
        s.close()
        self.assertEqual(odg[:2], b"\x05\x07")

    def test_neuspela_povezava_koda_5_in_ponovno_razresevanje(self):
        prosta = socket.socket()
        prosta.bind(("127.0.0.1", 0))
        vrata = prosta.getsockname()[1]
        prosta.close()
        s, odg = self._zahteva(b"primer.test", vrata)
        s.close()
        self.assertEqual(odg[:2], b"\x05\x05")
        self.assertEqual(self.res.pozabljena, ["primer.test"])

    def test_http_connect_na_istih_vratih_ostane(self):
        s = socket.create_connection(("127.0.0.1", self.posrednik.actual_port), timeout=5)
        with s:
            s.sendall(b"CONNECT primer.test:%d HTTP/1.1\r\nHost: primer.test\r\n\r\n" % self.odmev.vrata)
            glava = b""
            while b"\r\n\r\n" not in glava:
                k = s.recv(1)
                if not k:
                    break
                glava += k
            self.assertTrue(glava.startswith(b"HTTP/1.1 200"))
            s.sendall(b"abc")
            self.assertEqual(_beri(s, 3), b"abc")

    def test_reza_se_sprosti(self):
        for _ in range(3):
            s, odg = self._zahteva(b"ni.test", 443)
            s.close()
        # vse reze nazaj: BoundedSemaphore bi ob prevec release vrgel napako, ob premalo pa acquire ne bi uspel
        import time
        time.sleep(0.2)
        zasedene = 0
        while self.posrednik._slots.acquire(blocking=False):
            zasedene += 1
        self.assertEqual(zasedene, doh_proxy.NAJVEC_POVEZAV)


class Nastavitve(unittest.TestCase):

    class Nastavitev:
        def __init__(self, privzeto, izjeme):
            self.privzeto = privzeto
            self.izjeme = izjeme
            self.sheme = {}

        def add_proxy_for_scheme(self, shema, naslov):
            self.sheme[shema] = naslov

    class WebKit:
        pass

    def setUp(self):
        self.WebKit.NetworkProxySettings = mock.Mock(new=lambda p, i: Nastavitve.Nastavitev(p, i))

    def _soup(self, maj, mn):
        return mock.patch.multiple(doh_proxy.Soup, get_major_version=mock.Mock(return_value=maj),
                                   get_minor_version=mock.Mock(return_value=mn))

    def test_libsoup_36_https_prek_socks5(self):
        with self._soup(3, 6):
            p = doh_proxy.nastavitve_posrednika(self.WebKit, 4321, ["localhost"])
        self.assertEqual(p.privzeto, "http://127.0.0.1:4321")
        self.assertEqual(p.sheme, {"https": "socks5://127.0.0.1:4321"})
        self.assertEqual(p.izjeme, ["localhost"])

    def test_libsoup_34_ostane_http_connect(self):
        with self._soup(3, 4):
            p = doh_proxy.nastavitve_posrednika(self.WebKit, 4321, [])
        self.assertEqual(p.privzeto, "http://127.0.0.1:4321")
        self.assertEqual(p.sheme, {})


if __name__ == "__main__":
    unittest.main()
