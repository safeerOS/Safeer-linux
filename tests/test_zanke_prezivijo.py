"""Dolgotrajne zanke se po izjemi obnovijo (Safeer OS tece dneve v enem procesu).

  * Link (link_hub.Povezava._zanka): izjema v _odpri ali v klicatelju ob_stanju je koncala nit ponovnega
    povezovanja - naprava se ni vec vrnila v Link do ponovnega zagona.
  * Scit (os_scit.Seznami._tek): izjema pri osvezitvi je koncala nit, _nit pa je ostal nastavljen, zato je
    zazeni() ni obnovil - seznami groznj se niso vec osvezevali.
"""
import os
import sys
import threading
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import link_hub, os_scit  # noqa: E402


class PonovnoPovezovanje(unittest.TestCase):
    def test_izjeme_ne_ustavijo_zanke(self):
        p = link_hub.Povezava.__new__(link_hub.Povezava)
        p._ustavljen, p.tece, p.odjemalec = False, False, None
        p._poslusaj = lambda: None
        stanja, poskusi = [], []

        def ob_stanju(ok):
            stanja.append(ok)
            raise RuntimeError("napaka klicatelja")
        p.ob_stanju = ob_stanju

        def odpri():
            poskusi.append(1)
            if len(poskusi) == 1:
                raise ValueError("model naprave")
            return True
        p._odpri = odpri
        izidi = iter(["", "", "zaprto"])
        p._cakaj_na_poskus = lambda _s: next(izidi)
        n = threading.Thread(target=p._zanka, daemon=True)
        n.start()
        n.join(5)
        self.assertFalse(n.is_alive())
        self.assertEqual(len(poskusi), 2)            # po izjemi v _odpri je poskusila znova
        self.assertEqual(stanja, [False, False, True, False])


class SeznamiScita(unittest.TestCase):
    def test_napaka_osvezitve_ne_konca_niti(self):
        s = os_scit.Seznami.__new__(os_scit.Seznami)
        s._stop = threading.Event()
        s.nabor = [1]
        klici = []

        def osvezi():
            klici.append(1)
            if len(klici) == 1:
                raise MemoryError("gradnja nabora")
            s._stop.set()
            return True
        s.osvezi = osvezi
        s._do_naslednje = lambda: 0.0
        n = threading.Thread(target=s._tek, daemon=True)
        s._nit = n
        with mock.patch.multiple(os_scit, OSVEZITEV=0.0, PONOVNI_POSKUS=0.0, PRVA_OSVEZITEV=0.0):
            n.start()
            n.join(5)
        self.assertEqual(len(klici), 2)


if __name__ == "__main__":
    unittest.main()
