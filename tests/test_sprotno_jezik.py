"""Sprotna pretvorba izbere zvocno sled v zelenem jeziku (core/link_sprotno.py; Android Pretok.kt)."""
import unittest
from unittest import mock

from core import link_sprotno


def _razred():
    return next(c for c in vars(link_sprotno).values()
                if isinstance(c, type) and hasattr(c, "ukaz") and hasattr(c, "zvocna_sled"))


class JezikZvoka(unittest.TestCase):
    def test_izberi_sled(self):
        self.assertEqual(link_sprotno.izberi_sled(["por", "eng"], ["en"]), 1)
        self.assertEqual(link_sprotno.izberi_sled(["por", "en"], ["en"]), 1)
        self.assertEqual(link_sprotno.izberi_sled(["eng", "slv"], ["sl", "en"]), 1)
        self.assertEqual(link_sprotno.izberi_sled(["ger", "eng"], ["de"]), 0)
        self.assertEqual(link_sprotno.izberi_sled(["deu", "eng"], ["de"]), 0)
        self.assertEqual(link_sprotno.izberi_sled(["", "por"], ["en"]), 0, "brez zadetka prva sled")
        self.assertEqual(link_sprotno.izberi_sled([], ["en"]), 0)

    def test_jeziki_zahteve(self):
        self.assertEqual(link_sprotno.jeziki_zahteve(["EN", "sl", "en", "x", "de"]), ["en", "sl"], "najvec 4 vnosi zahteve")
        self.assertEqual(link_sprotno.jeziki_zahteve("en"), [])
        self.assertEqual(link_sprotno.jeziki_zahteve(None), [])

    def test_ukaz_in_izbira_sledi(self):
        cls = _razred()
        o = cls.__new__(cls)
        with mock.patch.object(cls, "ffmpeg", lambda self: "ffmpeg"), \
                mock.patch.object(cls, "programski_kodirnik", lambda self: "libx264"):
            self.assertIn("0:a:1?", o.ukaz("vhod", "izhod", 0, 0, 1080, None, zvocna_sled=1))
            self.assertIn("0:a:0?", o.ukaz("vhod", "izhod", 0, 0, 1080, None))
        with mock.patch.object(cls, "ffprobe", lambda self: "ffprobe"), \
                mock.patch.object(link_sprotno.subprocess, "run", return_value=mock.Mock(stdout="por\neng\n")):
            self.assertEqual(o.zvocna_sled("http://x", ["en"]), 1)
            self.assertEqual(o.zvocna_sled("http://x", []), 0)


if __name__ == "__main__":
    unittest.main()
