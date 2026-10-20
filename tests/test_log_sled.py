"""Safeer Browser: sled sesutja (faulthandler) in neujete izjeme v dnevniku (core/log.py, revizija 20. 10. 2026).

Prej je imel sled samo Safeer OS (os_stabilnost), Control in lupina; sesutje brskalnika v WebKitu je bilo brez sledi.
"""
import os
import signal
import subprocess
import sys
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pozeni(koda: str, mapa: str) -> subprocess.CompletedProcess:
    uvod = "import sys; sys.path.insert(0, %r); from core import log; log.install(%r, 'preizkus'); " % (KOREN, mapa)
    return subprocess.run([sys.executable, "-c", uvod + koda], capture_output=True, text=True, timeout=60)


class SledBrskalnika(unittest.TestCase):
    def test_neujeta_izjema_v_niti_je_v_dnevniku(self):
        mapa = tempfile.mkdtemp()
        pozeni("import threading; n = threading.Thread(target=lambda: 1 / 0, name='preizkusna'); n.start(); n.join()",
               mapa)
        with open(os.path.join(mapa, "safeer.log"), encoding="utf-8") as f:
            dnevnik = f.read()
        self.assertIn("Neujeta izjema v niti preizkusna", dnevnik)
        self.assertIn("ZeroDivisionError", dnevnik)

    @unittest.skipUnless(hasattr(signal, "SIGSEGV"), "POSIX")
    def test_sesutje_pusti_sled_vseh_niti(self):
        mapa = tempfile.mkdtemp()
        izid = pozeni("import faulthandler; faulthandler._sigsegv()", mapa)
        self.assertEqual(izid.returncode, -signal.SIGSEGV)
        pot = os.path.join(mapa, "sled.log")
        with open(pot, encoding="utf-8") as f:
            self.assertIn("Fatal Python error: Segmentation fault", f.read())
        self.assertEqual(os.stat(pot).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
