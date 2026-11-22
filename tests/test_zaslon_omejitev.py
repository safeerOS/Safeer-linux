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
        with mock.patch.object(Z, "VKLOP_V_PREIZKUSIH", True), \
                mock.patch.object(Z.subprocess, "run", return_value=mock.Mock(returncode=0)) as tek:
            u = self._ukaz()
            self._ukaz()
        self.assertEqual(u[u.index("-rc_mode") + 1], "QVBR")
        self.assertIn("-maxrate", u)
        self.assertEqual(tek.call_count, 1)                     # preizkus enkrat, izid si zapomnimo

    def test_star_gonilnik_ostane_cqp(self):
        with mock.patch.object(Z, "VKLOP_V_PREIZKUSIH", True), \
                mock.patch.object(Z.subprocess, "run", return_value=mock.Mock(returncode=1)):
            u = self._ukaz()
        self.assertEqual(u[u.index("-rc_mode") + 1], "CQP")
        self.assertNotIn("-maxrate", u)

    def test_izklop(self):
        with mock.patch.object(Z, "VKLOP_V_PREIZKUSIH", False), \
                mock.patch.object(Z.subprocess, "run", return_value=mock.Mock(returncode=0)) as tek:
            u = self._ukaz()
        self.assertEqual(u[u.index("-rc_mode") + 1], "CQP")
        self.assertEqual(tek.call_count, 0)


class PreizkusiGonilnikaBrezZbiranjaIzhoda(unittest.TestCase):
    """21. 11. 2026: preizkus gonilnika z `capture_output=True` je z laznim ffmpeg (pise tok brez konca) porabil 18 GB in
    sprozil OOM celega racunalnika. Preizkusa, ki stejeta samo izhodno kodo, izhoda ne smeta zbirati."""

    def test_brez_capture_output(self):
        import inspect
        for fn in (Z.omejitev_mozna, Z.gpu_lestvica_mozna):
            vir = inspect.getsource(fn)
            self.assertNotIn("capture_output=", vir, fn.__name__)        # v komentarju je beseda dovoljena
            self.assertIn("stdout=subprocess.DEVNULL", vir, fn.__name__)
            self.assertIn("timeout=", vir, fn.__name__)


class OmejitevOdpoved(unittest.TestCase):
    """Slepi pregled 22. 11. 2026, najdba 4: preizkus meje mora uporabiti profil in obliko seje; odpoved zajema z mejo
    vzame mejo, ne HEVC."""
    def setUp(self):
        Z._OMEJITEV.clear()
        self._hevc = dict(Z._HEVC)

    def tearDown(self):
        Z._OMEJITEV.clear()
        Z._HEVC.clear()
        Z._HEVC.update(self._hevc)

    def test_preizkus_s_profilom_in_obliko_seje(self):
        with mock.patch.object(Z, "VKLOP_V_PREIZKUSIH", True), \
                mock.patch.object(Z.subprocess, "run", return_value=mock.Mock(returncode=0)) as tek:
            Z.omejitev_mozna("ffmpeg", "/dev/dri/renderD128", "hevc_vaapi", "rext", "vuyx")
        argv = tek.call_args[0][0]
        self.assertEqual(argv[argv.index("-profile:v") + 1], "rext")
        self.assertIn("format=vuyx,hwupload", argv)

    def test_razlicen_profil_nov_preizkus(self):
        with mock.patch.object(Z, "VKLOP_V_PREIZKUSIH", True), \
                mock.patch.object(Z.subprocess, "run", side_effect=[mock.Mock(returncode=0), mock.Mock(returncode=1)]):
            self.assertTrue(Z.omejitev_mozna("ffmpeg", "v", "hevc_vaapi", "main", "nv12"))
            self.assertFalse(Z.omejitev_mozna("ffmpeg", "v", "hevc_vaapi", "rext", "vuyx"))

    def test_odpoved_zajema_z_mejo_vzame_mejo_ne_hevc(self):
        slika = mock.Mock()
        slika.wait.return_value = 1
        Z._HEVC.pop(Z._HEVC_ODPOVED, None)
        kriva = Z.Zaslon._preveri_omejitev(slika, ["ffmpeg", "-rc_mode", "QVBR"], [0, 0])
        self.assertTrue(kriva)
        self.assertTrue(Z._OMEJITEV.get(Z._OMEJITEV_ODPOVED))
        self.assertFalse(Z._HEVC.get(Z._HEVC_ODPOVED))
        with mock.patch.object(Z, "VKLOP_V_PREIZKUSIH", True), \
                mock.patch.object(Z.subprocess, "run", return_value=mock.Mock(returncode=0)) as tek:
            self.assertFalse(Z.omejitev_mozna("ffmpeg", "v", "h264_vaapi", "high"))
        self.assertEqual(tek.call_count, 0)

    def test_zajem_brez_meje_ni_krivda_meje(self):
        slika = mock.Mock()
        slika.wait.return_value = 1
        self.assertFalse(Z.Zaslon._preveri_omejitev(slika, ["ffmpeg", "-rc_mode", "CQP"], [0, 0]))


if __name__ == "__main__":
    unittest.main()
