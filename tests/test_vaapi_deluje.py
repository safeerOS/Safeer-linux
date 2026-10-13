"""Zajem zaslona: naprava /dev/dri, na kateri strojno kodiranje ne dela, ne sme podreti zajema (x264)."""
import unittest
from unittest import mock

from core import link_zaslon as Z


class VaapiDeluje(unittest.TestCase):
    def setUp(self):
        Z._VAAPI_DELUJE.clear()

    def tearDown(self):
        Z._VAAPI_DELUJE.clear()

    def test_ne_dela_x264(self):
        zazeni = mock.Mock(return_value=mock.Mock(returncode=1))
        self.assertFalse(Z.vaapi_deluje("/dev/dri/renderD128", "/usr/bin/ffmpeg", zazeni))
        self.assertFalse(Z.vaapi_deluje("/dev/dri/renderD128", "/usr/bin/ffmpeg", zazeni))
        self.assertEqual(zazeni.call_count, 1)   # samo enkrat na zagon

    def test_dela(self):
        zazeni = mock.Mock(return_value=mock.Mock(returncode=0))
        self.assertTrue(Z.vaapi_deluje("/dev/dri/renderD128", "/usr/bin/ffmpeg", zazeni))
        ukaz = zazeni.call_args[0][0]
        self.assertIn("h264_vaapi", ukaz)
        self.assertIn("/dev/dri/renderD128", ukaz)

    def test_naprava_none_ce_ne_dela(self):
        with mock.patch.object(Z.os.path, "exists", return_value=True), \
             mock.patch.object(Z, "vaapi_deluje", return_value=False):
            self.assertIsNone(Z.vaapi_naprava("/usr/bin/ffmpeg"))


if __name__ == "__main__":
    unittest.main()
