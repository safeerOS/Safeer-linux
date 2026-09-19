"""Vnos s televizorja na racunalnik (core/link_vnos.py): samo dovoljeno in nic skozi lupino."""
import os
import sys
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_vnos  # noqa: E402


class Lazni(link_vnos.Vnos):
    """Namesto xdotool si ukaze samo zapomni."""

    def __init__(self):
        super().__init__(xdotool="/usr/bin/xdotool")
        self.ukazi = []

    def _pozeni(self, argumenti):
        self.ukazi.append(list(argumenti))
        self.stevec += 1
        return True


class Dovoljeno(unittest.TestCase):
    def setUp(self):
        self.v = Lazni()

    def test_tipke_s_seznama(self):
        self.assertTrue(self.v.izvedi({"vrsta": "tipka", "tipka": "gor"}))
        self.assertEqual(self.v.ukazi[-1], ["key", "--clearmodifiers", "Up"])
        self.assertTrue(self.v.izvedi({"vrsta": "tipka", "tipka": "OK"}))
        self.assertEqual(self.v.ukazi[-1][-1], "Return")

    def test_bliznjice_za_delo_z_dokumentom(self):
        """Pisanje na televizorju brez shranjevanja ni pisanje; bliznjice so na seznamu."""
        self.assertTrue(self.v.izvedi({"vrsta": "tipka", "tipka": "shrani"}))
        self.assertEqual(self.v.ukazi[-1], ["key", "--clearmodifiers", "ctrl+s"])
        self.assertTrue(self.v.izvedi({"vrsta": "tipka", "tipka": "Shrani_Kot"}))
        self.assertEqual(self.v.ukazi[-1][-1], "ctrl+shift+s")
        for oznaka, pricakovano in (("izberi_vse", "ctrl+a"), ("ponovi", "ctrl+y"),
                                    ("krepko", "ctrl+b"), ("lezece", "ctrl+i"),
                                    ("podcrtano", "ctrl+u"), ("natisni", "ctrl+p")):
            self.assertTrue(self.v.izvedi({"vrsta": "tipka", "tipka": oznaka}), oznaka)
            self.assertEqual(self.v.ukazi[-1][-1], pricakovano, oznaka)

    def test_besedilo_s_sumniki(self):
        """Tipkovnica na televizorju poslje tudi c, s, z - gredo skozi kot navadno besedilo."""
        self.assertTrue(self.v.izvedi({"vrsta": "besedilo", "besedilo": "čšž ČŠŽ"}))
        self.assertEqual(self.v.ukazi[-1][-1], "čšž ČŠŽ")
        self.assertEqual(self.v.ukazi[-1][-2], "--")

    def test_neznana_tipka_ne_gre_skozi(self):
        self.assertFalse(self.v.izvedi({"vrsta": "tipka", "tipka": "rm -rf"}))
        self.assertFalse(self.v.izvedi({"vrsta": "tipka", "tipka": "ctrl+alt+F2"}))
        self.assertEqual(self.v.ukazi, [])

    def test_neznana_vrsta_ne_gre_skozi(self):
        self.assertFalse(self.v.izvedi({"vrsta": "ukaz", "ukaz": "reboot"}))
        self.assertFalse(self.v.izvedi({}))
        self.assertFalse(self.v.izvedi({"vrsta": "tipka"}))
        self.assertEqual(self.v.ukazi, [])

    def test_besedilo_gre_za_dvojni_pomisljaj(self):
        self.assertTrue(self.v.izvedi({"vrsta": "besedilo", "besedilo": "safeer.si -rf; reboot"}))
        u = self.v.ukazi[-1]
        self.assertEqual(u[0], "type")
        self.assertIn("--", u)
        self.assertEqual(u[-1], "safeer.si -rf; reboot")     # kot en sam argument, ne skozi lupino

    def test_besedilo_brez_krmilnih_znakov_in_omejeno(self):
        self.assertFalse(self.v.izvedi({"vrsta": "besedilo", "besedilo": "a\nb"}))
        self.assertTrue(self.v.izvedi({"vrsta": "besedilo", "besedilo": "x" * 500}))
        self.assertEqual(len(self.v.ukazi[-1][-1]), link_vnos.NAJVEC_BESEDILA)

    def test_premik_je_omejen(self):
        self.assertTrue(self.v.izvedi({"vrsta": "premik", "dx": 5000, "dy": -5000}))
        self.assertEqual(self.v.ukazi[-1][-2:], [str(link_vnos.NAJVEC_PREMIK), str(-link_vnos.NAJVEC_PREMIK)])
        self.assertFalse(self.v.izvedi({"vrsta": "premik", "dx": "veliko", "dy": 0}))
        self.assertFalse(self.v.izvedi({"vrsta": "premik", "dx": 0, "dy": 0}))

    def test_kliki_in_kolesce(self):
        self.assertTrue(self.v.izvedi({"vrsta": "klik", "gumb": "desni"}))
        self.assertEqual(self.v.ukazi[-1][-1], "3")
        self.assertTrue(self.v.izvedi({"vrsta": "klik", "gumb": "levi", "dvojni": True}))
        self.assertIn("--repeat", self.v.ukazi[-1])
        self.assertFalse(self.v.izvedi({"vrsta": "klik", "gumb": "cetrti"}))
        self.assertTrue(self.v.izvedi({"vrsta": "kolesce", "smer": "dol", "koliko": 99}))
        self.assertEqual(self.v.ukazi[-1][2], "10")          # navzgor omejeno
        self.assertFalse(self.v.izvedi({"vrsta": "kolesce", "smer": "vstran"}))

    def test_brez_xdotool_ne_naredi_nicesar(self):
        v = link_vnos.Vnos(xdotool="")
        self.assertFalse(v.mozno)
        self.assertFalse(v.izvedi({"vrsta": "tipka", "tipka": "gor"}))


class Drzanje(unittest.TestCase):
    """Igra in dolgo drsenje potrebujeta pritisk in spust, ne kratkega piska."""

    def setUp(self):
        self.v = Lazni()

    def test_pritisk_in_spust(self):
        self.assertTrue(self.v.izvedi({"vrsta": "tipka_dol", "tipka": "gor"}))
        self.assertEqual(self.v.ukazi[-1], ["keydown", "--clearmodifiers", "Up"])
        self.assertEqual(self.v.drzane(), ["Up"])
        self.assertTrue(self.v.izvedi({"vrsta": "tipka_gor", "tipka": "gor"}))
        self.assertEqual(self.v.ukazi[-1], ["keyup", "--clearmodifiers", "Up"])
        self.assertEqual(self.v.drzane(), [])

    def test_ponovljeno_javljanje_ne_pritisne_dvakrat(self):
        """Televizor drzanje ponavlja, da se ve, da je zivo; tipka se sme pritisniti le enkrat."""
        for _ in range(4):
            self.assertTrue(self.v.izvedi({"vrsta": "tipka_dol", "tipka": "levo"}))
        self.assertEqual([u for u in self.v.ukazi if u[0] == "keydown"],
                         [["keydown", "--clearmodifiers", "Left"]])

    def test_bliznjica_se_ne_drzi(self):
        """ctrl+s ni tipka, ki bi jo kdo drzal - drzana krmilka bi ob prekinitvi ostala pritisnjena."""
        self.assertFalse(self.v.izvedi({"vrsta": "tipka_dol", "tipka": "shrani"}))
        self.assertEqual(self.v.drzane(), [])
        self.assertEqual(self.v.ukazi, [])

    def test_neznana_tipka_se_ne_drzi(self):
        self.assertFalse(self.v.izvedi({"vrsta": "tipka_dol", "tipka": "rm -rf"}))
        self.assertEqual(self.v.ukazi, [])

    def test_pozabljena_tipka_se_spusti_sama(self):
        """Ce povezava pade sredi drzanja, tipka ne sme ostati pritisnjena."""
        import time

        self.assertTrue(self.v.izvedi({"vrsta": "tipka_dol", "tipka": "desno"}))
        self.v.sprosti_pozabljene(time.monotonic() + link_vnos.NAJVEC_DRZANJA_S + 1)
        self.assertEqual(self.v.ukazi[-1], ["keyup", "--clearmodifiers", "Right"])
        self.assertEqual(self.v.drzane(), [])

    def test_konec_seje_spusti_vse(self):
        for tipka in ("gor", "levo", "presledek"):
            self.assertTrue(self.v.izvedi({"vrsta": "tipka_dol", "tipka": tipka}))
        self.assertEqual(len(self.v.drzane()), 3)
        self.v.sprosti_vse()
        self.assertEqual(self.v.drzane(), [])
        self.assertEqual(len([u for u in self.v.ukazi if u[0] == "keyup"]), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
