"""S8 (pregled 5. 11. 2026): strezniki usmerjevalnika vzporedno s skupnim rokom (ROK_USMERJEVALNIK), prvi odgovor
zmaga; ce ne odgovori nobeden, SERVFAIL v roku, ne molk. Lazni strezniki na 127.0.0.1 in 127.0.0.2 (vrata 53 so
preslikana z getaddrinfo); vse vticnice in niti preizkus zapre sam."""
import os
import socket
import struct
import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_scit  # noqa: E402


def vprasanje(ime, id_=0x4242):
    q = b"".join(bytes([len(d)]) + d.encode() for d in ime.split(".")) + b"\x00"
    return struct.pack("!HHHHHH", id_, 0x0100, 1, 0, 0, 0) + q + struct.pack("!HH", 1, 1)


class Streznik:
    """Lazen DNS na naslovu; molci=True: prejme in ne odgovori."""

    def __init__(self, naslov, molci):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind((naslov, 0))
        self.s.settimeout(0.1)
        self.vrata = self.s.getsockname()[1]
        self.molci = molci
        self.prejeto = 0
        self._tece = True
        self.nit = threading.Thread(target=self._tek, daemon=True)
        self.nit.start()

    def _tek(self):
        while self._tece:
            try:
                p, od = self.s.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            self.prejeto += 1
            if not self.molci:
                self.s.sendto(p[:2] + b"\x81\x80" + p[4:], od)

    def zapri(self):
        self._tece = False
        self.nit.join(2)
        self.s.close()


class Usmerjevalnik(unittest.TestCase):
    def _strezniki(self, *molcijo):
        strezniki, vrata = [], {}
        for i, molci in enumerate(molcijo):
            naslov = "127.0.0.%d" % (i + 1)
            st = Streznik(naslov, molci)
            self.addCleanup(st.zapri)
            strezniki.append(st)
            vrata[naslov] = st.vrata
        izvirni = socket.getaddrinfo

        def getaddrinfo(g, v, *a, **k):
            return izvirni(g, vrata.get(g, v) if v == 53 else v, *a, **k)
        zamenjava = mock.patch.object(socket, "getaddrinfo", getaddrinfo)
        zamenjava.start()
        self.addCleanup(zamenjava.stop)
        r = os_scit.Razresevalnik(lambda ime: None, lambda: list(vrata))
        return r, strezniki

    def test_vsi_molcijo_servfail_v_roku(self):
        r, strezniki = self._strezniki(True, True)
        p = vprasanje("safeer.si")
        t0 = time.monotonic()
        o = r._vprasaj_usmerjevalnik(p, False)
        trajalo = time.monotonic() - t0
        self.assertIsNotNone(o, "molk: odjemalec bi cakal svoj rok in sel mimo Scita")
        self.assertEqual(o[:4], p[:2] + b"\x81\x82")           # SERVFAIL z istim id
        self.assertLess(trajalo, 0.5)
        self.assertEqual([s.prejeto for s in strezniki], [1, 1])   # vprasana sta bila oba (hkrati)

    def test_mrtev_in_ziv_odgovori_ziv_brez_zamika(self):
        r, strezniki = self._strezniki(True, False)          # prvi molci, drugi odgovori
        p = vprasanje("safeer.si", id_=0x0707)
        t0 = time.monotonic()
        o = r._vprasaj_usmerjevalnik(p, False)
        self.assertLess(time.monotonic() - t0, 0.3)
        self.assertEqual(o[:4], b"\x07\x07\x81\x80")

    def test_zaprta_vrata_ne_zadrzijo(self):
        # Streznik brez programa na vratih (ICMP »vrata zaprta«) in ziv streznik: odgovor zivega.
        r, strezniki = self._strezniki(False)
        prazna = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        prazna.bind(("127.0.0.2", 0))
        mrtva = prazna.getsockname()[1]
        prazna.close()
        izvirni = socket.getaddrinfo
        with mock.patch.object(socket, "getaddrinfo",
                               lambda g, v, *a, **k: izvirni(g, mrtva if g == "127.0.0.2" and v == 53 else v, *a, **k)):
            r.upstream = lambda: ["127.0.0.2", "127.0.0.1"]
            o = r._vprasaj_usmerjevalnik(vprasanje("safeer.si", id_=0x0909), False)
        self.assertEqual(o[:4], b"\x09\x09\x81\x80")

    def test_tcp_brez_streznikov_servfail(self):
        r = os_scit.Razresevalnik(lambda ime: None, lambda: ["127.0.0.1"])
        p = vprasanje("safeer.si", id_=0x0303)
        with mock.patch.object(os_scit, "CAS_UPSTREAM", 0.3), \
                mock.patch.object(socket, "create_connection", side_effect=ConnectionRefusedError()):
            o = r._vprasaj_usmerjevalnik(p, True)
        self.assertEqual(o[:4], b"\x03\x03\x81\x82")

    def test_tcp_pocasno_telo_ne_podaljsa_skupnega_roka(self):
        # CodeRabbit 5. 11. 2026: streznik poslje glavo dolzine in telo po en bajt na 0,1 s. Prej je vsak recv dobil
        # poln ostanek roka znova, zato je poizvedba trajala, dokler streznik ni poslal vsega (~4 s namesto 0,5 s).
        p = vprasanje("safeer.si", id_=0x0505)
        odgovor = p[:2] + b"\x81\x80" + p[4:] + b"\x00" * 20
        posluh = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        posluh.bind(("127.0.0.1", 0))
        posluh.listen(1)
        posluh.settimeout(2)
        vrata = posluh.getsockname()[1]
        konec_streznika = threading.Event()

        def tek():
            try:
                k, _ = posluh.accept()
            except OSError:
                return
            with k:
                try:
                    k.settimeout(1)
                    k.recv(4096)
                    k.sendall(struct.pack("!H", len(odgovor)))
                    for b in odgovor:
                        if konec_streznika.wait(0.1):
                            return
                        k.sendall(bytes([b]))
                except OSError:
                    return
        nit = threading.Thread(target=tek, daemon=True)
        nit.start()

        def koncaj():
            konec_streznika.set()
            nit.join(3)
            posluh.close()
        self.addCleanup(koncaj)
        izvirni = socket.create_connection
        r = os_scit.Razresevalnik(lambda ime: None, lambda: ["127.0.0.1"])
        with mock.patch.object(os_scit, "CAS_UPSTREAM", 0.5), \
                mock.patch.object(socket, "create_connection",
                                  lambda naslov, timeout=None: izvirni((naslov[0], vrata), timeout=timeout)):
            t0 = time.monotonic()
            o = r._vprasaj_usmerjevalnik(p, True)
            trajalo = time.monotonic() - t0
        self.assertLess(trajalo, 0.9)
        self.assertEqual(o[:4], b"\x05\x05\x81\x82")        # SERVFAIL v roku


if __name__ == "__main__":
    unittest.main()
