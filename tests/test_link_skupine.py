"""Skupine programov za televizor (core/link_programi.py).

Televizor ima na racunalniku hitro sto programov; abecedni seznam je bil zato neuporaben.
Skupine so iste, kot jih uporabnik pozna iz menija svojega namizja, in nastanejo iz kategorij
XDG - ne iz imena programa in ne iz ugibanja.
"""
import os
import sys
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_programi  # noqa: E402


def zapisi(mapa, ime, vsebina):
    with open(os.path.join(mapa, ime), "w", encoding="utf-8") as d:
        d.write(vsebina)


def vnos(ime, kategorije):
    return ("[Desktop Entry]\nType=Application\nName=%s\nExec=/bin/true\nCategories=%s\n"
            % (ime, kategorije))


class Razvrscanje(unittest.TestCase):
    def test_igra_je_igra_tudi_ce_ima_se_kaj(self):
        self.assertEqual(link_programi.skupina({"Game", "AudioVideo"}), "igre")
        self.assertEqual(link_programi.skupina({"ArcadeGame"}), "igre")

    def test_vsakdanje_skupine(self):
        self.assertEqual(link_programi.skupina({"Office", "WordProcessor"}), "pisarna")
        self.assertEqual(link_programi.skupina({"Development", "IDE"}), "programiranje")
        self.assertEqual(link_programi.skupina({"Network", "WebBrowser"}), "splet")
        self.assertEqual(link_programi.skupina({"AudioVideo", "Player"}), "predstavnost")
        self.assertEqual(link_programi.skupina({"Utility", "Archiving"}), "orodja")
        self.assertEqual(link_programi.skupina({"Education"}), "ucenje")

    def test_pregledovalnik_slik_ni_pisarna(self):
        """Graphics;Viewer je pregledovalnik slik - ta sodi med predstavnost."""
        self.assertEqual(link_programi.skupina({"Graphics", "Viewer"}), "predstavnost")

    def test_brez_kategorij_posteno_drugo(self):
        self.assertEqual(link_programi.skupina(set()), link_programi.PRIVZETA_SKUPINA)
        self.assertEqual(link_programi.skupina({"Neznano"}), "drugo")


class VSeznamu(unittest.TestCase):
    def test_vsak_program_pove_svojo_skupino(self):
        with tempfile.TemporaryDirectory() as mapa:
            zapisi(mapa, "igra.desktop", vnos("Igrica", "Game;"))
            zapisi(mapa, "pisalo.desktop", vnos("Pisalo", "Office;WordProcessor;"))
            zapisi(mapa, "neznano.desktop", vnos("Neznano", ""))
            s = link_programi.Programi(vklopljeno=True, mape=[mapa]).seznam(z_ikonami=False)
        skupine = {v["name"]: v["group"] for v in s["items"]}
        self.assertEqual(skupine, {"Igrica": "igre", "Pisalo": "pisarna", "Neznano": "drugo"})


class BrezDvojnikov(unittest.TestCase):
    """Isti napis dvakrat je na televizorju uganka, ne izbira."""

    def test_isto_ime_le_enkrat(self):
        with tempfile.TemporaryDirectory() as prva, tempfile.TemporaryDirectory() as druga:
            zapisi(prva, "engrampa.desktop", vnos("Archive Manager", "Utility;Archiving;"))
            zapisi(druga, "org.gnome.FileRoller.desktop", vnos("Archive Manager", "Utility;Archiving;"))
            zapisi(druga, "mines.desktop", vnos("Mines", "Game;"))
            s = link_programi.Programi(vklopljeno=True, mape=[prva, druga]).seznam(z_ikonami=False)
        imena = sorted(v["name"] for v in s["items"])
        self.assertEqual(imena, ["Archive Manager", "Mines"])
        # Obdrzi prvo mapo po vrsti (uporabnikova pred sistemsko pred Flatpakom).
        arhiv = [v for v in s["items"] if v["name"] == "Archive Manager"][0]
        self.assertEqual(arhiv["id"], "app:engrampa.desktop")


if __name__ == "__main__":
    unittest.main(verbosity=2)
