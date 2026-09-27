import unittest

from core.tab_lifecycle import (dejanje_zavihka, je_pomnilniski_pritisk,
                                izberi_za_sprostitev, najstarejsi_neaktivni)


class TabLifecycleTests(unittest.TestCase):
    def dejanje(self, starost, **kwargs):
        argumenti = dict(neaktiven_od=100 - starost, zdaj=100, aktiven=False, zvok=False,
                         zasciten=False, zamrznjen=False, zamrzni_po=60, zavrzi_po=600)
        argumenti.update(kwargs)
        return dejanje_zavihka(**argumenti)

    def test_meji_60_in_600(self):
        self.assertEqual(self.dejanje(59), "")
        self.assertEqual(self.dejanje(60), "zamrzni")
        self.assertEqual(self.dejanje(599), "zamrzni")
        self.assertEqual(self.dejanje(600), "zavrzi")

    def test_aktiven_in_zvok_sta_izjema(self):
        self.assertEqual(self.dejanje(700, aktiven=True), "")
        self.assertEqual(self.dejanje(700, zvok=True), "")
        self.assertEqual(self.dejanje(700, zasciten=True), "")
        self.assertEqual(self.dejanje(70, aktiven=True, zamrznjen=True), "obnovi")

    def test_nicelna_meja_izklopi_posamezen_korak(self):
        self.assertEqual(self.dejanje(70, zamrzni_po=0), "")
        self.assertEqual(self.dejanje(700, zavrzi_po=0), "zamrzni")

    def test_pomnilniski_pritisk_in_vrstni_red(self):
        self.assertTrue(je_pomnilniski_pritisk("MemTotal: 1000 kB\nMemAvailable: 99 kB\n"))
        self.assertFalse(je_pomnilniski_pritisk("MemTotal: 1000 kB\nMemAvailable: 100 kB\n"))
        tabs = [
            {"id": "nov", "inactive_since": 20},
            {"id": "zvok", "inactive_since": 1, "audio": True},
            {"id": "star", "inactive_since": 10},
            {"id": "aktiven", "inactive_since": 0, "active": True},
        ]
        self.assertEqual([t["id"] for t in najstarejsi_neaktivni(tabs)], ["star", "nov"])

    def test_pritisk_izbere_najstarejse_do_primanjkljaja(self):
        tabs = [
            {"id": "nov", "inactive_since": 20, "rss_mb": 300},
            {"id": "star", "inactive_since": 10, "rss_mb": 200},
            {"id": "zvok", "inactive_since": 1, "rss_mb": 900, "audio": True},
        ]
        self.assertEqual([t["id"] for t in izberi_za_sprostitev(tabs, 350 * 1024)],
                         ["star", "nov"])


if __name__ == "__main__":
    unittest.main()
