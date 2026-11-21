"""Uradni posnetek skladbe: isti primeri kot tests/UradniPosnetekTest.kt v Safeer OS."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import uradni_posnetek as u  # noqa: E402
from core.uradni_posnetek import Zadetek  # noqa: E402

CLIP = Zadetek("clip", "Nirvana - Lithium (Official Music Video)", "Nirvana", 257)
AUDIO = Zadetek("audio", "Nirvana - Lithium (Official Audio)", "Nirvana", 257)
LIVE = Zadetek("live", "Nirvana - Lithium (Live at Reading)", "Nirvana", 260)
COVER = Zadetek("cover", "Lithium (Cover)", "Nirvana Cover Channel", 257)
DRUGA = Zadetek("drug", "Nirvana - Heart-Shaped Box (Official Music Video)", "Nirvana", 280)
DOLG = Zadetek("dolg", "Nirvana - Lithium (Official Music Video)", "Nirvana", 900)


class UradniPosnetek(unittest.TestCase):
    def test_besedilo(self):
        self.assertEqual(u.ravno("Čšž Éé!"), "csz ee")
        self.assertEqual(u.golo("Trevo (Tu) (part. X)"), "trevo")

    def test_kanal(self):
        for k in ("Nirvana", "NirvanaVEVO", "Nirvana - Topic", "Foo, Nirvana"):
            self.assertTrue(u.je_kanal_izvajalca(k, "Nirvana"), k)
        self.assertFalse(u.je_kanal_izvajalca("Nirvana Fan Club", "Nirvana"))
        self.assertFalse(u.je_kanal_izvajalca("X", ""))

    def test_izbira(self):
        self.assertEqual(u.izberi([AUDIO, CLIP], "Lithium", "Nirvana", 257), "clip")
        self.assertEqual(u.izberi([LIVE], "Lithium", "Nirvana", 257), "")
        self.assertEqual(u.izberi([COVER], "Lithium", "Nirvana", 257), "")
        self.assertEqual(u.izberi([DRUGA], "Lithium", "Nirvana", 257), "")
        self.assertEqual(u.izberi([AUDIO], "Lithium", "Nirvana", 257), "audio")
        self.assertEqual(u.izberi([DOLG, CLIP], "Lithium", "Nirvana", 257), "clip")
        self.assertEqual(u.izberi([], "Lithium", "Nirvana", 257), "")
        self.assertEqual(u.izberi([CLIP], "Lithium", "Nirvana, Neko Drug", 257), "clip")

    def test_live_v_naslovu_skladbe(self):
        z = Zadetek("z", "Nirvana - Live Forever", "Nirvana", 200)
        self.assertEqual(u.izberi([z], "Live Forever", "Nirvana", 200), "z")


if __name__ == "__main__":
    unittest.main()
