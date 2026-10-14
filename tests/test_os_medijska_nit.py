"""GTK in GStreamer morata ostati na glavni niti mostu."""

import ast
import unittest
from pathlib import Path


class MostMedijevTests(unittest.TestCase):
    def test_ukazi_z_okni_in_predvajalnikom_so_na_glavni_niti(self):
        izvor = ast.parse((Path(__file__).resolve().parents[1] / "safeer_os.py").read_text())
        razred = next(n for n in izvor.body if isinstance(n, ast.ClassDef) and n.name == "SafeerOS")
        # Klic mostu obdela _obdelaj_klic (stran WebKit in lupina QML).
        metoda = next(n for n in razred.body if isinstance(n, ast.FunctionDef) and n.name == "_obdelaj_klic")
        slovarji = {}
        for vnos in ast.walk(metoda):
            if isinstance(vnos, ast.Assign) and len(vnos.targets) == 1 and isinstance(vnos.targets[0], ast.Name):
                if vnos.targets[0].id in ("glavna", "ozadje", "asinhrono") and isinstance(vnos.value, ast.Dict):
                    slovarji[vnos.targets[0].id] = {k.value for k in vnos.value.keys if isinstance(k, ast.Constant)}
        zahtevani = {"splet", "medij", "lokalniMediji", "medijskaMapa", "medijskiTok",
                    "dodajMedijskiTok", "odpriMedijskiTok", "odpriLokalniMedij",
                    "predvajalnikStanje", "predvajalnikUkaz"}
        # GTK4: sistemska okna (izbira datotek, tok) so asinhrona, a prav tako na glavni niti (odgovor pride pozneje).
        self.assertTrue(zahtevani <= slovarji["glavna"] | slovarji["asinhrono"])
        self.assertTrue({"lokalniMediji", "medijskaMapa", "medijskiTok"} <= slovarji["asinhrono"])
        self.assertFalse(zahtevani & slovarji["ozadje"])
        self.assertTrue({"knjiznicaMedijev", "tokoviMedijev"} <= slovarji["ozadje"])


if __name__ == "__main__":
    unittest.main()
