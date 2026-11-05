"""L8/B9 (pregled 5. 11. 2026): barve vgrajenega Spleta iz assets/os/tokens.css (en vir, core/os_lupina.tokeni), ne
trdo kodirane v core/os_splet.py; naslovna vrstica z fokusom ima viden okvir v barvi --fokus."""
import os
import re
import unittest

from core import os_lupina, os_splet

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BarveSpleta(unittest.TestCase):
    def setUp(self):
        self.vir = open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8").read()

    def test_fokus_naslovne_vrstice(self):
        css = os_splet.css_spleta(os_lupina.tokeni())
        r, g, b, _a = os_lupina.tokeni()["fokus"]
        self.assertIn("#splet-naslov:focus-within { border-color: rgba(%d,%d,%d,1); }" % (r, g, b), css)

    def test_barve_iz_tokenov(self):
        t = dict(os_lupina.tokeni())
        t["ozadje"] = (1, 2, 3, 1.0)
        t["fokus"] = (4, 5, 6, 1.0)
        css = os_splet.css_spleta(t)
        self.assertIn("#safeer-splet { background: rgba(1,2,3,1);", css)
        self.assertIn("border-color: rgba(4,5,6,1)", css)

    def test_brez_trdih_barv_v_slogu(self):
        _css = self.vir.split("    def _css(self) -> None:", 1)[1].split("    def _gumb(", 1)[0]
        self.assertIn("css_spleta(os_lupina.tokeni())", _css)
        predloga = self.vir.split("def css_spleta(", 1)[1].split("def gostitelj_strani(", 1)[0]
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{6}\b|rgba\(\d", predloga), [])

    def test_novi_zetoni_in_privzete_barve_enake(self):
        # Brez tokens.css je videz isti kot z njim (privzete barve = barve v tokens.css).
        t = os_lupina.tokeni()
        for ime in os_splet._BARVE_SPLETA:
            self.assertIn(ime, t)
            self.assertEqual(t[ime], os_splet._BARVE_SPLETA[ime], ime)
        self.assertEqual(os_splet.css_spleta(t), os_splet.css_spleta({}))


if __name__ == "__main__":
    unittest.main()
