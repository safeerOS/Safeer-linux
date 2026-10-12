"""Dve namizji hkrati ne (12. 10. 2026): med delovno povrsino Safeer OS Nemovo namizje ne tece."""
import os
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DveNamizji(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(KOREN, "packaging", "tema-cinnamon", "safeer-cinnamon"), encoding="utf-8") as f:
            self.s = f.read()

    def _telo(self, ime):
        return self.s.split("\n" + ime + "() {", 1)[1].split("\n}\n", 1)[0]

    def test_delovna_ugasne_nemovo_namizje(self):
        self.assertIn("nemo_namizje_izklopi", self._telo("delovna"))
        izklop = self._telo("nemo_namizje_izklopi")
        self.assertIn('pisi "$NEMO_IKONE" false', izklop)
        self.assertIn("pkill -TERM -x -u", izklop)            # samo nemo-desktop tega uporabnika, natancno ime
        self.assertLess(izklop.index('[ -n "$KOREN" ] && return 0'), izklop.index("pkill"))   # preizkusi ne ubijajo

    def test_izklop_vrne_prejsnje(self):
        self.assertIn("nemo_namizje_vrni", self._telo("delovna_izklopi"))
        vrni = self._telo("nemo_namizje_vrni")
        self.assertIn("nemo-ikone-prej", vrni)
        self.assertIn("setsid nemo-desktop", vrni)

    def test_ob_prijavi(self):
        seja = self.s.split("--seja)", 1)[1].split(";;", 1)[0]
        self.assertLess(seja.index("nemo_namizje_izklopi"), seja.index("exec safeer-os --delovna"))


if __name__ == "__main__":
    unittest.main()
