"""Navidezni igralni plosek racunalnika (core/link_plosek.py).

Preizkusi tecejo tudi brez /dev/uinput: kar gre v jedro, zamenjamo z zapisnikom. Pomembno je,
da z omrezja pride samo tisto, kar je na seznamu dovoljenega, in da konec seje ne pusti
pritisnjenega gumba.
"""
import os
import struct
import sys
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_plosek  # noqa: E402


class Lazni(link_plosek.Plosek):
    """Namesto jedra si dogodke samo zapomni."""

    def __init__(self):
        super().__init__()
        self.dogodki = []
        self._fd = -1          # kot da je naprava odprta

    def mozno(self):
        return True

    def _poslji(self, vrsta, koda, vrednost):
        self.dogodki.append((vrsta, koda, vrednost))
        return True


def brez_sinhronizacije(dogodki):
    return [d for d in dogodki if d[0] != link_plosek.EV_SYN]


class Gumbi(unittest.TestCase):
    def setUp(self):
        self.p = Lazni()
        self.p.dogodki = []

    def test_pritisk_in_spust(self):
        self.assertTrue(self.p.gumb("a", True))
        self.assertIn((link_plosek.EV_KEY, link_plosek.GUMBI["a"], 1), self.p.dogodki)
        self.assertTrue(self.p.gumb("a", False))
        self.assertIn((link_plosek.EV_KEY, link_plosek.GUMBI["a"], 0), self.p.dogodki)

    def test_vsak_gumb_ima_svojo_kodo(self):
        self.assertEqual(len(set(link_plosek.GUMBI.values())), len(link_plosek.GUMBI))
        self.assertEqual(len(set(k for k, _s, _z in link_plosek.OSI.values())), len(link_plosek.OSI))

    def test_neznan_gumb_ne_gre_skozi(self):
        self.assertFalse(self.p.gumb("rm -rf", True))
        self.assertFalse(self.p.gumb("", True))
        self.assertEqual(self.p.dogodki, [])

    def test_konec_seje_spusti_vse(self):
        for g in ("a", "l1", "zacni"):
            self.p.gumb(g, True)
        self.p.dogodki = []
        self.p.sprosti_vse()
        spusceni = {koda for vrsta, koda, vrednost in self.p.dogodki
                    if vrsta == link_plosek.EV_KEY and vrednost == 0}
        self.assertEqual(spusceni, {link_plosek.GUMBI[g] for g in ("a", "l1", "zacni")})


class Osi(unittest.TestCase):
    def setUp(self):
        self.p = Lazni()
        self.p.dogodki = []

    def test_palica_gre_od_minus_ena_do_ena(self):
        koda, _spodaj, zgoraj = link_plosek.OSI["leva_x"]
        self.assertTrue(self.p.os("leva_x", 1.0))
        self.assertEqual(brez_sinhronizacije(self.p.dogodki)[-1], (link_plosek.EV_ABS, koda, zgoraj))
        self.assertTrue(self.p.os("leva_x", -1.0))
        self.assertEqual(brez_sinhronizacije(self.p.dogodki)[-1], (link_plosek.EV_ABS, koda, -zgoraj))

    def test_odklon_je_omejen_navzgor_in_navzdol(self):
        koda, _spodaj, zgoraj = link_plosek.OSI["leva_y"]
        self.assertTrue(self.p.os("leva_y", 9.0))
        self.assertEqual(brez_sinhronizacije(self.p.dogodki)[-1], (link_plosek.EV_ABS, koda, zgoraj))

    def test_sprozilec_ne_gre_pod_nic(self):
        koda, spodaj, _zgoraj = link_plosek.OSI["sprozilec_l"]
        self.assertEqual(spodaj, 0)
        self.assertTrue(self.p.os("sprozilec_l", -0.8))
        self.assertEqual(brez_sinhronizacije(self.p.dogodki)[-1], (link_plosek.EV_ABS, koda, 0))

    def test_neznana_os_in_nestevilo_ne_gresta_skozi(self):
        self.assertFalse(self.p.os("sistem", 1.0))
        self.assertFalse(self.p.os("leva_x", "veliko"))
        self.assertFalse(self.p.os("leva_x", float("nan")))
        self.assertEqual(self.p.dogodki, [])


class Opis(unittest.TestCase):
    def test_struktura_za_jedro_je_prave_velikosti(self):
        """uinput_user_dev: ime 80 + input_id 8 + ff_effects_max 4 + 4x64 celih stevil."""
        opis = struct.pack("@80sHHHHI" + "i" * (4 * link_plosek.ABS_CNT),
                           b"x", 3, 1, 1, 1, 0, *([0] * (4 * link_plosek.ABS_CNT)))
        self.assertEqual(len(opis), 80 + 8 + 4 + 4 * link_plosek.ABS_CNT * 4)

    def test_brez_dostopa_ne_obljublja_nicesar(self):
        p = link_plosek.Plosek(pot="/ni/te/naprave")
        self.assertFalse(p.mozno())
        self.assertFalse(p.odpri())
        self.assertFalse(p.gumb("a", True))
        self.assertFalse(p.odprt)
        self.assertTrue(p.napaka)


if __name__ == "__main__":
    unittest.main(verbosity=2)
