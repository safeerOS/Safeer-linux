"""link_zaslon._koncaj: signal nikoli na ze pobran PID (CI 40360017279, 40471446443 - varovalo signalov »kill(15) (?)«).

Tekma iz CPython (bpo-38630): nit A drzi Popen._waitpid_lock in proces pobere; poll() v niti B zaklepa ne dobi, vrne
None, send_signal pa vseeno poklice os.kill na sproscen PID. Preizkus tekmo ponovi deterministicno."""
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock

from core import link_zaslon


class KoncajTekma(unittest.TestCase):
    def test_signal_ne_gre_na_pid_ki_ga_pobira_druga_nit(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        time.sleep(0.3)                                   # proces je koncal (zombi), Popen ga se ni pobral
        pobira = threading.Event()

        def nit_a():                                      # kot strazar/_koda_odpovedi: pobere pod zaklepom
            with p._waitpid_lock:
                pobira.set()
                import os
                _pid, status = os.waitpid(p.pid, 0)       # PID je sproscen
                time.sleep(0.4)                           # okno tekme: returncode se ni nastavljen
                p.returncode = os.waitstatus_to_exitcode(status)

        t = threading.Thread(target=nit_a)
        t.start()
        pobira.wait(2)
        klici = []
        with mock.patch("os.kill", side_effect=lambda pid, sig: klici.append((pid, sig))):
            link_zaslon._koncaj(p)
        t.join(5)
        self.assertEqual(klici, [], "signal je sel na pobran (morda tuj) PID")
        self.assertEqual(p.returncode, 0)

    def test_tekoc_proces_se_vedno_ustavi(self):
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            link_zaslon._koncaj(p)
            self.assertIsNotNone(p.returncode)
            self.assertLess(p.returncode, 0)              # ustavljen s signalom (SIGTERM)
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()


if __name__ == "__main__":
    unittest.main()
