"""_poslji_signal: signal samo procesu, ki ga Popen se ni pobral (tekma z bralcem, bpo-38630)."""
import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core import link_zaslon  # noqa: E402


class PosljiSignal(unittest.TestCase):
    def test_zivi_proces_dobi_signal(self):
        p = subprocess.Popen(["sleep", "30"])
        try:
            link_zaslon._poslji_signal(p)
            self.assertEqual(p.wait(timeout=5), -15)
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()

    def test_pobran_proces_ne_dobi_signala(self):
        p = subprocess.Popen(["true"])
        p.wait()
        with mock.patch.object(link_zaslon.os, "kill", side_effect=AssertionError("signal na sproscen PID")):
            link_zaslon._poslji_signal(p)
            link_zaslon._poslji_signal(p, True)


if __name__ == "__main__":
    unittest.main()
