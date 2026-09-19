"""Krajevna imena naprav v Safeer Linku (Linux): shranijo se v nastavitve, prazno ime vzdevek odstrani,
stran jih dobi v stanju (__safeerLink.vzdevki), most JS ima vzdevki/shraniVzdevek."""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import safeer_link  # noqa: E402


class LazniConfig:
    def __init__(self):
        self.d = {}

    def get(self, k, privzeto=None):
        return self.d.get(k, privzeto)

    def set(self, k, v):
        self.d[k] = v
        return True


class Vzdevki(unittest.TestCase):
    def test_shramba(self):
        o = safeer_link.SafeerLink.__new__(safeer_link.SafeerLink)
        o.config = LazniConfig()
        self.assertEqual(o._vzdevki(), {})
        o._shrani_vzdevek("tv-philips", "  Dnevna soba ")
        self.assertEqual(o._vzdevki(), {"tv-philips": "Dnevna soba"})
        o._shrani_vzdevek("tv-philips", "")
        self.assertEqual(o._vzdevki(), {})
        o._shrani_vzdevek("", "x")
        self.assertEqual(o._vzdevki(), {})
        o._shrani_vzdevek("p", "a" * 100)
        self.assertEqual(len(o._vzdevki()["p"]), 64)

    def test_most(self):
        self.assertIn("vzdevki: function ()", safeer_link.MOST_JS)
        self.assertIn('poslji("shraniVzdevek"', safeer_link.MOST_JS)


if __name__ == "__main__":
    unittest.main()
