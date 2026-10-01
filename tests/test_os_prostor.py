"""Datoteke: prostor na disku in najvecje datoteke za skupni prostor (core/os_datoteke.py)."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import os_datoteke as o  # noqa: E402


class Prostor(unittest.TestCase):
    def setUp(self):
        self.dom = tempfile.mkdtemp(prefix="safeer-prostor-")
        os.makedirs(os.path.join(self.dom, "Videi"))
        os.makedirs(os.path.join(self.dom, ".skrito"))
        os.makedirs(os.path.join(self.dom, "node_modules"))
        for pot, mb in (("Videi/film.mkv", 300), ("velik.zip", 150), ("majhen.txt", 1),
                        (".skrito/skrit.bin", 400), ("node_modules/x.bin", 500)):
            with open(os.path.join(self.dom, pot), "wb") as d:
                d.truncate(mb * 1024 * 1024)   # redka datoteka: hitro, brez porabe diska

    def tearDown(self):
        shutil.rmtree(self.dom, ignore_errors=True)

    def test_najvecje(self):
        self.assertEqual([e["ime"] for e in o.najvecje(self.dom)], ["film.mkv", "velik.zip"])  # >=100 MB, brez skritih in kode

    def test_prostor(self):
        p = o.prostor(self.dom)
        self.assertGreater(p["skupaj"], 0)
        self.assertIn(p["malo"], (True, False))
        self.assertEqual(o.prostor("/ne/obstaja")["prosto"], -1)


if __name__ == "__main__":
    unittest.main()
