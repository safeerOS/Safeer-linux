"""Safeer OS mora slediti menjavi zaslona.

20. 9. 2026: Matej je zaprl pokrov prenosnika in slika je sla na televizor (3840x2160). Vrstica in
namizje sta ostala v velikosti prejsnjega zaslona (1920x1080) in na njegovem mestu - cez pol
zaslona. Velikost se je namrec brala samo enkrat, ob zagonu.

Testi berejo izvorno kodo, ker safeer_os.py ob uvozu potrebuje GTK (v testnem okolju ga ni).
"""
import os
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _vir() -> str:
    with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as d:
        return d.read()


class Zasloni(unittest.TestCase):
    def setUp(self) -> None:
        self.vir = _vir()

    def test_poslusa_obe_spremembi_zaslona(self):
        """Zamenjan zaslon in spremenjena locljivost sta dva razlicna signala; potrebujemo oba."""
        self.assertIn('"monitors-changed"', self.vir)
        self.assertIn('"size-changed"', self.vir)

    def test_spremembe_zdruzimo(self):
        """Menjava zaslona sprozi rafal dogodkov: prilagodimo se enkrat, ne pri vsakem."""
        self.assertIn("GLib.timeout_add(500, self._prilagodi_zaslonu)", self.vir)
        self.assertIn("GLib.source_remove(self._zaslon_zamik)", self.vir)

    def test_prilagodi_vrstico_in_namizje(self):
        """Prilagoditev mora premakniti IN raztegniti oboje - sicer ostane eno od njiju napacno."""
        zacetek = self.vir.index("def _prilagodi_zaslonu")
        telo = self.vir[zacetek:self.vir.index("def _rezerviraj", zacetek)]
        self.assertIn("self.vrstica.move(g.x, g.y + g.height - VISINA_VRSTICE)", telo)
        self.assertIn("self.vrstica.resize(g.width, VISINA_VRSTICE)", telo)
        self.assertIn("self.okno.move(g.x, g.y)", telo)
        self.assertIn("self.okno.resize(g.width, g.height - VISINA_VRSTICE)", telo)

    def test_rezervacija_roba_gre_znova(self):
        """_NET_WM_STRUT je izracunan iz velikosti zaslona: po menjavi mora biti postavljen znova,
        sicer programi z najvecjim oknom segajo pod vrstico (ali pustijo prazen pas)."""
        zacetek = self.vir.index("def _prilagodi_zaslonu")
        telo = self.vir[zacetek:self.vir.index("def _rezerviraj", zacetek)]
        self.assertIn("self._rezerviraj(self.vrstica, g)", telo)

    def test_prilagoditev_se_ne_ponavlja(self):
        """Vrne False: GLib.timeout_add ponavlja, dokler ne vrnemo False."""
        zacetek = self.vir.index("def _prilagodi_zaslonu")
        telo = self.vir[zacetek:self.vir.index("def _rezerviraj", zacetek)]
        self.assertIn("return False", telo)

    def test_brez_zaslona_ne_pade(self):
        """Med menjavo zaslona je lahko trenutek brez zaslona - takrat ne delamo nicesar."""
        zacetek = self.vir.index("def _prilagodi_zaslonu")
        telo = self.vir[zacetek:self.vir.index("def _rezerviraj", zacetek)]
        self.assertIn("if g is None:", telo)

    def test_poslusanje_se_vklopi_ob_vrstici(self):
        """Vrstica obstaja samo v namiznem nacinu; tam se vklopi tudi spremljanje zaslonov."""
        zacetek = self.vir.index("def _ustvari_vrstico")
        telo = self.vir[zacetek:self.vir.index("def _spremljaj_zaslone", zacetek)]
        self.assertIn("self._spremljaj_zaslone()", telo)


if __name__ == "__main__":
    unittest.main()
