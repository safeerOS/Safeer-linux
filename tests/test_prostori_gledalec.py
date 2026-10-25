"""Gledalec prostora (core/prostori_gledalec.py): drzan Esc zapusti cel zaslon, kratek gre napravi; spuscene datoteke;
besedila vrstice v vseh 6 jezikih vmesnika."""
import unittest

from core import prostori_gledalec as pg


class DrzanEsc(unittest.TestCase):
    def test_kratek_gre_napravi(self):
        t = pg.DrzanaTipka(0.8)
        t.pritisk(10.0)
        t.pritisk(10.1)                     # samodejno ponavljanje
        self.assertFalse(t.poteklo(10.3))
        self.assertEqual(t.spust(10.4), "kratko")
        self.assertFalse(t.drzana)

    def test_drzan_zapusti_enkrat(self):
        t = pg.DrzanaTipka(0.8)
        t.pritisk(10.0)
        t.pritisk(10.5)
        self.assertTrue(t.poteklo(10.85))
        self.assertFalse(t.poteklo(11.0), "izhod samo enkrat")
        self.assertEqual(t.spust(11.2), "nic", "spust po izhodu ne gre napravi")

    def test_dolg_brez_casovnika(self):
        t = pg.DrzanaTipka(0.8)
        t.pritisk(1.0)
        self.assertEqual(t.spust(2.0), "izhod")

    def test_spust_brez_pritiska(self):
        # Esc, pritisnjen pred odprtjem gledalca (npr. v preklopniku), se tu ne steje.
        self.assertEqual(pg.DrzanaTipka().spust(5.0), "")


class Datoteke(unittest.TestCase):
    def test_poti(self):
        self.assertEqual(pg.poti_spuscenih(["/a", "/a", "rel", None, "/b\x00c", "/c"]), ["/a", "/c"])
        self.assertEqual(len(pg.poti_spuscenih(["/%d" % i for i in range(50)])), pg.NAJVEC_DATOTEK)


class Besedila(unittest.TestCase):
    def test_vsi_jeziki_vsi_kljuci(self):
        kljuci = set(pg.BESEDILA["sl"])
        self.assertEqual(set(pg.BESEDILA), {"sl", "en", "de", "es", "fr", "it"})
        for jezik, b in pg.BESEDILA.items():
            self.assertEqual(set(b), kljuci, jezik)
            self.assertTrue(all(v.strip() for v in b.values()), jezik)

    def test_nadomescanje_in_rezerva(self):
        self.assertEqual(pg.besedilo("sl", "posiljam", n=3), "Pošiljam datoteke (3) …")
        self.assertEqual(pg.besedilo("xx", "zapri"), "Close")
        self.assertEqual(pg.besedilo(None, "zapri"), "Close")
        self.assertEqual(pg.besedilo("de_AT", "zapri"), "Schließen")


if __name__ == "__main__":
    unittest.main()
