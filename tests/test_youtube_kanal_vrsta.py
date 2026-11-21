"""Vrsta videa kanala: isti primeri kot tests/YoutubeKanalVrstaTest.kt v Safeer OS."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import youtube_kanal_vrsta as k  # noqa: E402
from core.youtube_kanal_vrsta import GLASBA, KRATKI, OSTALO  # noqa: E402


class VrstaKanala(unittest.TestCase):
    def test_trajanje(self):
        self.assertEqual(k.trajanje("3:51"), 231)
        self.assertEqual(k.trajanje("1:02:03"), 3723)
        for slabo in ("3:5", "a:bc", "", None, "1:75"):
            self.assertIsNone(k.trajanje(slabo), slabo)

    def test_glasba(self):
        self.assertEqual(k.vrsta("Rick Astley - Dance (Live at The O2, London, April 2026)", "Rick Astley", 231), GLASBA)
        self.assertEqual(k.vrsta("Nirvana - Lithium", "Nirvana", 257), GLASBA)
        self.assertEqual(k.vrsta("Lithium", "Nirvana - Topic", 257), GLASBA)
        self.assertEqual(k.vrsta("Song (Official Audio)", "X", None), GLASBA)
        self.assertEqual(k.vrsta("Nirvana - Lithium", "Nirvana", None), OSTALO)

    def test_ostalo(self):
        self.assertEqual(k.vrsta("Podcast #12 - Glasba in zivljenje", "Ana", 3000), OSTALO)
        self.assertEqual(k.vrsta("Rick Astley - '50' Track By Track (10 Years Later)", "Rick Astley", 1200), OSTALO)
        self.assertEqual(k.vrsta("Best of 2026 - mix (Official Audio)", "X", 3600), OSTALO)
        self.assertEqual(k.vrsta("Moj dan - vlog", "Ana", 600), OSTALO)
        self.assertEqual(k.vrsta("Kako popravim kolo", "Marko", 480), OSTALO)
        self.assertEqual(k.vrsta("Rick Astley - The Never Book Tour Dublin 2024", "Rick Astley", 412), OSTALO)
        self.assertEqual(k.vrsta("Rick Astley - What's in your fridge?", "Rick Astley", 66), OSTALO)
        self.assertEqual(k.vrsta("A - B", "X", 99), OSTALO)
        self.assertEqual(k.vrsta("A - B", "X", 100), GLASBA)

    def test_kratki(self):
        self.assertEqual(k.vrsta("Nirvana - Lithium", "Nirvana", None, je_shorts=True), KRATKI)
        self.assertEqual(k.vrsta("Dance (Official Video)", "X", 45), KRATKI)
        self.assertEqual(k.vrsta("Fun #Shorts", "X", None), KRATKI)
        self.assertEqual(k.vrsta("A - B (Official Video)", "X", 61), GLASBA)


if __name__ == "__main__":
    unittest.main()
