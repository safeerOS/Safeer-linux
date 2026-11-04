"""Safeer Player (samostojni Predvajalnik / Medijski center) in namizje Safeer OS berejo ISTE kljuce (lastnik 4. 11. 2026:
»ce ga vnesem v namiznem okolju Safeer OS, velja tudi za predvajalnik«). Player ni drug program: meni in ukaz zazeneta
`safeer-os --predvajalnik` (isti proces, ce Safeer OS tece; sicer isti program z istimi mapami), Katalog je v programu en
sam z mapo os_programi.MAPA_NASTAVITEV/media, kljuci so v isti zbirki (ena shema). Preizkus pazi, da se to ne razide."""
import os
import re
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class PredvajalnikIstaShramba(unittest.TestCase):
    def test_player_je_isti_program(self):
        self.assertRegex(beri("packaging", "safeer-player.desktop"), r"(?m)^Exec=safeer-os --predvajalnik$")
        self.assertIn('exec /usr/bin/safeer-os --predvajalnik "$@"', beri("packaging", "safeer-player-launcher"))

    def test_en_katalog_z_mapo_nastavitev(self):
        s = beri("safeer_os.py")
        self.assertEqual(len(re.findall(r"\bos_katalog\.Katalog\(", s)), 1)
        self.assertIn('os_katalog.Katalog(\n                os.path.join(os_programi.MAPA_NASTAVITEV, "media")', s)
        # Usklajevanje kljucev (Safeer Control) vzame isti Medijski center ali isto mapo.
        c = beri("safeer_control.py")
        self.assertIn('mapa = os.path.join(os_programi.MAPA_NASTAVITEV, "media")', c)
        self.assertIn("return kat.mc", c)

    def test_ena_zbirka_skrivnosti(self):
        k = beri("core", "os_katalog.py")
        self.assertEqual(len(re.findall(r"(?m)^SHEMA_SKRIVNOSTI = ", k)), 1)
        self.assertEqual(len(re.findall(r"Secret\.Schema\.new\(", k)), 1)
        self.assertEqual(len(re.findall(r"(?m)^STORITEV = ", beri("core", "sporocila", "skrivnosti.py"))), 1)
        # Nacin predvajalnika ne izbere druge mape nastavitev.
        s = beri("safeer_os.py")
        self.assertNotRegex(s, r"MAPA_NASTAVITEV\s*=")


if __name__ == "__main__":
    unittest.main()
