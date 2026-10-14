"""Ob prijavi samozagon locenega Controla ne sme odpreti okna vgrajenega Controla (namizje najprej, 14. 10. 2026)."""
import os
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def vir():
    with open(os.path.join(KOREN, "safeer_control.py"), encoding="utf-8") as f:
        return f.read()


class ZagonBrezOkna(unittest.TestCase):
    def test_vgrajen_ob_zagonu_ne_pokaze_okna(self):
        import safeer_control as sc
        app = mock.MagicMock()
        app.ozadje, app._prva_aktivacija = True, False
        app._ZAGNAN_OB = sc.time.time()
        app.ZAGON_BREZ_OKNA_S = 60
        with mock.patch.object(sc, "VGRAJEN", True):
            sc.SafeerControl.do_activate(app)
        app.pokazi_okno.assert_not_called()

    def test_vgrajen_pozneje_pokaze_okno(self):
        import safeer_control as sc
        app = mock.MagicMock()
        app.ozadje, app._prva_aktivacija = True, False
        app._ZAGNAN_OB = sc.time.time() - 120
        app.ZAGON_BREZ_OKNA_S = 60
        app._koda_posodobljena.return_value = False
        with mock.patch.object(sc, "VGRAJEN", True):
            sc.SafeerControl.do_activate(app)
        app.pokazi_okno.assert_called_once()

    def test_samozagon_s_zasedenim_imenom_konca_tiho(self):
        s = vir()
        self.assertIn("if ozadje and _ime_zasedeno():", s)
        self.assertLess(s.index("if ozadje and _ime_zasedeno():"), s.index("app = SafeerControl(ozadje=ozadje)"))


if __name__ == "__main__":
    unittest.main()
