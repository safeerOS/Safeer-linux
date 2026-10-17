#!/usr/bin/env python3
"""DoH v dolgotrajnem procesu (Safeer OS tece dneve): predpomnilnik ne raste za vedno, zanka sprejemanja pa ob
trajni napaki ne vrti procesorja in ne izgublja mest za povezave."""

import errno
import os
import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.doh_proxy as doh_proxy  # noqa: E402
from core.doh_proxy import DoHResolver, LocalDoHProxy  # noqa: E402


class PredpomnilnikSePocisti(unittest.TestCase):
    def test_pretecena_imena_izginejo(self):
        r = DoHResolver("cloudflare")
        zdaj = time.time()
        with r._lock:
            for i in range(500):
                r._cache["star%d.example" % i] = ("1.2.3.4", zdaj - r.STARO_S - 10)
                r._cache["neg%d.example" % i] = (None, zdaj - 1)
            r._cache["svez.example"] = ("5.6.7.8", zdaj + 300)
            r._cache["star-a-se-uporaben.example"] = ("5.6.7.9", zdaj - 10)
            r._pocisceno = zdaj - r.POCISTI_S - 1
        with mock.patch.object(r, "_query_doh", return_value=("9.9.9.9", 60)):
            self.assertEqual(r.resolve("novo.example"), "9.9.9.9")
        self.assertEqual(set(r._cache), {"svez.example", "star-a-se-uporaben.example", "novo.example"})


class _StrezniskiVtic:
    def __init__(self, posrednik, napaka):
        self.posrednik, self.napaka, self.klicev = posrednik, napaka, 0

    def accept(self):
        self.klicev += 1
        if self.klicev > 200:
            self.posrednik.is_running = False
        return self.napaka()


class ZankaSprejemanja(unittest.TestCase):
    def _zazeni(self, posrednik, cas=0.6, nit=None):
        posrednik.is_running = True
        n = nit or threading.Thread(target=posrednik._accept_loop, daemon=True)
        n.start()
        time.sleep(cas)
        posrednik.is_running = False
        n.join(2)

    def test_trajna_napaka_ne_vrti_zanke(self):
        posrednik = LocalDoHProxy(DoHResolver("cloudflare"))

        def emfile():
            raise OSError(errno.EMFILE, "Too many open files")
        vtic = _StrezniskiVtic(posrednik, emfile)
        posrednik._server_sock = vtic
        self._zazeni(posrednik)
        self.assertLess(vtic.klicev, 20)

    def test_neuspela_nit_vrne_mesto_in_zapre_povezavo(self):
        posrednik = LocalDoHProxy(DoHResolver("cloudflare"))
        zaprte = []

        class Odjemalec:
            def setsockopt(self, *a):
                pass

            def close(self):
                zaprte.append(self)

        posrednik._server_sock = _StrezniskiVtic(posrednik, lambda: (Odjemalec(), ("127.0.0.1", 1)))

        class NeZazene:
            def __init__(self, *a, **k):
                pass

            def start(self):
                raise RuntimeError("can't start new thread")
        nit = threading.Thread(target=posrednik._accept_loop, daemon=True)   # pred zamenjavo razreda Thread
        with mock.patch.object(doh_proxy.threading, "Thread", NeZazene):
            self._zazeni(posrednik, nit=nit)
        self.assertTrue(zaprte)
        self.assertEqual(posrednik._sockets, set())
        # Vsa mesta so spet prosta.
        for _ in range(doh_proxy.NAJVEC_POVEZAV):
            self.assertTrue(posrednik._slots.acquire(blocking=False))


if __name__ == "__main__":
    unittest.main()
