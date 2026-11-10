"""Varnost Linka, tocka 5 (pregled TV 10. 11. 2026): streznik datotek ima mejo socasnih povezav (skupaj in na naslov),
rele mejo socasnih kanalov; krajevna vrata releja so samo na 127.0.0.1. Brez zunanjega omrezja (samo zanka)."""
import socket
import threading
import time
import unittest
from unittest import mock

from core import link_datoteke, link_rele


class LaznaPovezava:
    def __init__(self):
        self.zaprta = False

    def shutdown(self, *_a):
        pass

    def close(self):
        self.zaprta = True


def _streznik():
    s = object.__new__(link_datoteke._Streznik)
    s.obramba, s.cuvaj = None, None
    return s


class StreznikDatotek(unittest.TestCase):
    def test_meja_na_naslov_in_skupaj(self):
        s = _streznik()
        with mock.patch.object(link_datoteke, "je_krajevni_vir", return_value=True):
            prve = [LaznaPovezava() for _ in range(link_datoteke.NAJVEC_POVEZAV_NA_NASLOV)]
            self.assertTrue(all(s.verify_request(p, ("192.0.2.20", 1)) for p in prve))
            self.assertFalse(s.verify_request(LaznaPovezava(), ("192.0.2.20", 2)), "en naslov ne zasede vsega")
            drug = LaznaPovezava()
            self.assertTrue(s.verify_request(drug, ("192.0.2.21", 1)), "drug naslov se dobi mesto")
            s.shutdown_request(prve[0])
            self.assertTrue(prve[0].zaprta)
            nova = LaznaPovezava()
            self.assertTrue(s.verify_request(nova, ("192.0.2.20", 3)), "sproscena povezava vrne mesto")
            ostale = []
            n = 3
            while len(s._odprte) < link_datoteke.NAJVEC_POVEZAV:
                p = LaznaPovezava()
                self.assertTrue(s.verify_request(p, ("192.0.2.%d" % (30 + n // 10), n)))
                ostale.append(p)
                n += 1
            self.assertFalse(s.verify_request(LaznaPovezava(), ("198.51.100.99", 1)), "skupna meja")

    def test_zavrnjena_povezava_ne_sprosti_tuje(self):
        s = _streznik()
        with mock.patch.object(link_datoteke, "je_krajevni_vir", return_value=True):
            zive = [LaznaPovezava() for _ in range(link_datoteke.NAJVEC_POVEZAV_NA_NASLOV)]   # zive kot v strezniku
            for p in zive:
                s.verify_request(p, ("198.51.100.5", 1))
            zavrnjena = LaznaPovezava()
            self.assertFalse(s.verify_request(zavrnjena, ("198.51.100.5", 2)))
            s.shutdown_request(zavrnjena)                 # socketserver jo zapre: stevec ostane
            self.assertFalse(s.verify_request(LaznaPovezava(), ("198.51.100.5", 3)))


class Rele(unittest.TestCase):
    def test_meja_kanalov(self):
        mesta = threading.BoundedSemaphore(2)
        stoj = threading.Event()
        zavrnjeni = []
        self.assertTrue(link_rele._zacni_kanal(mesta, stoj.wait, lambda: zavrnjeni.append(1)))
        self.assertTrue(link_rele._zacni_kanal(mesta, stoj.wait, lambda: zavrnjeni.append(1)))
        self.assertFalse(link_rele._zacni_kanal(mesta, stoj.wait, lambda: zavrnjeni.append(1)))
        self.assertEqual(zavrnjeni, [1])
        stoj.set()
        konec = time.monotonic() + 5
        while time.monotonic() < konec and not link_rele._zacni_kanal(mesta, lambda: None, lambda: None):
            time.sleep(0.01)
        self.assertLess(time.monotonic(), konec, "koncan kanal sprosti mesto (tudi ob napaki)")

    def test_krajevni_rele_samo_zanka_in_meja(self):
        stoj = threading.Event()
        with mock.patch.object(link_rele, "NAJVEC_KANALOV", 2), \
                mock.patch.object(link_rele.LokalniRele, "_kanal", lambda self, tcp, oddaja=False: stoj.wait(5)):
            r = link_rele.LokalniRele("cilj")
            try:
                self.assertEqual(r.streznik.getsockname()[0], "127.0.0.1")
                odjemalci = [socket.create_connection(("127.0.0.1", r.vrata), timeout=5) for _ in range(3)]
                tretji = odjemalci[2]
                tretji.settimeout(5)
                self.assertEqual(tretji.recv(1), b"", "tretji kanal je zavrnjen (povezava zaprta)")
                self.assertEqual(r.zadnja_napaka, "prevec_kanalov")
            finally:
                stoj.set()
                for o in locals().get("odjemalci", []):
                    o.close()
                r.zapri()

    def test_agent_huba_uporablja_mejo(self):
        vir = open(link_rele.__file__, encoding="utf-8").read()
        self.assertIn("_zacni_kanal(self._mesta, lambda k=kanal: self._kanal(k),", vir)


if __name__ == "__main__":
    unittest.main()
