"""Obvestila uskladitve kljucev v jeziku uporabnika (CodeRabbit 9. 11. 2026): SafeerLink._jezik je metoda; prej je
str(metode) dal »<b« in Slovenec je vedno dobil angleska besedila."""

import types
import unittest

import safeer_control


def _control(link):
    return types.SimpleNamespace(link=link)


class _Link:
    def __init__(self, jezik):
        self.jezik = jezik

    def _jezik(self):
        if isinstance(self.jezik, Exception):
            raise self.jezik
        return self.jezik


class BesediloKljucev(unittest.TestCase):
    def test_slovensko(self):
        b = safeer_control.SafeerControl._besedilo_kljucev
        self.assertEqual(b(_control(_Link("sl")), "sprejmi"), "Sprejmi")
        self.assertEqual(b(_control(_Link("sl")), "razveljavi"), "Razveljavi")

    def test_drug_jezik_in_napaka_anglesko(self):
        b = safeer_control.SafeerControl._besedilo_kljucev
        self.assertEqual(b(_control(_Link("de")), "sprejmi"), "Accept")
        self.assertEqual(b(_control(_Link(RuntimeError("brez nastavitev"))), "vredu"), "OK")


if __name__ == "__main__":
    unittest.main()
