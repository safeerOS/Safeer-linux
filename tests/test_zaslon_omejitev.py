"""Zivi zaslon: zgornja meja hitrosti (21. 11. 2026). Izmerjeno: CQP na sliki s sumom 551-757 Mbit/s, kabel zmore 100."""
import os
import unittest
from unittest import mock

from core import link_zaslon as Z


class Omejitev(unittest.TestCase):
    def setUp(self):
        Z._OMEJITEV.clear()

    def tearDown(self):
        Z._OMEJITEV.clear()

    def test_nacin_hitrosti(self):
        self.assertEqual(Z.nacin_hitrosti(16, False), ["-rc_mode", "CQP", "-qp", "16"])
        u = Z.nacin_hitrosti(16, True)
        self.assertEqual(u[:4], ["-rc_mode", "QVBR", "-global_quality", "16"])
        self.assertEqual(u[u.index("-maxrate") + 1], "%dM" % Z.NAJVEC_MBIT)
        self.assertLessEqual(Z.NAJVEC_MBIT, 75)                 # 100 Mbit/s kabel: prostor za protokol in nihanja
        self.assertLess(Z.CILJ_MBIT, Z.NAJVEC_MBIT)

    def _ukaz(self):
        return Z.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 60, "24M", "/dev/dri/renderD128", "ffmpeg", qp=16)

    def test_gonilnik_z_mejo(self):
        with mock.patch.dict(os.environ, {"SAFEER_ZASLON_OMEJITEV": "1"}), \
                mock.patch.object(Z.subprocess, "run", return_value=mock.Mock(returncode=0)) as tek:
            u = self._ukaz()
            self._ukaz()
        self.assertEqual(u[u.index("-rc_mode") + 1], "QVBR")
        self.assertIn("-maxrate", u)
        self.assertEqual(tek.call_count, 1)                     # preizkus enkrat, izid si zapomnimo

    def test_star_gonilnik_ostane_cqp(self):
        with mock.patch.dict(os.environ, {"SAFEER_ZASLON_OMEJITEV": "1"}), \
                mock.patch.object(Z.subprocess, "run", return_value=mock.Mock(returncode=1)):
            u = self._ukaz()
        self.assertEqual(u[u.index("-rc_mode") + 1], "CQP")
        self.assertNotIn("-maxrate", u)

    def test_izklop(self):
        with mock.patch.dict(os.environ, {"SAFEER_ZASLON_OMEJITEV": "0"}), \
                mock.patch.object(Z.subprocess, "run", return_value=mock.Mock(returncode=0)) as tek:
            u = self._ukaz()
        self.assertEqual(u[u.index("-rc_mode") + 1], "CQP")
        self.assertEqual(tek.call_count, 0)


if __name__ == "__main__":
    unittest.main()
