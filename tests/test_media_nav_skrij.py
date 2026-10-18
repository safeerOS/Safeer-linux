"""Leva navigacija Medijskega centra se skrci na ikone in razsiri nazaj (lastnik, 14. 10. 2026). Lastnik 18. 10. 2026:
samo ena moznost - gumb Skrci; »Skrij meni« in rocaj sta odstranjena (brez podvajanja)."""
import os
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class NavigacijaMedijev(unittest.TestCase):
    def setUp(self):
        self.html = _beri("assets", "os", "index.html")
        self.js = _beri("assets", "os", "os.js")
        self.css = _beri("assets", "os", "os.css")

    def test_samo_gumb_skrci(self):
        telo = self.html.split('<div class="media-telo">', 1)[1].split('<div class="media-vsebina">', 1)[0]
        self.assertIn('id="mediaNavSkrci" type="button" aria-controls="mediaNav" aria-expanded="true"', telo)
        for odstranjeno in ("mediaNavSkrij", "mediaNavRocaj"):
            self.assertNotIn(odstranjeno, self.html + self.js + self.css)
        self.assertNotIn("nav-skrita", self.js + self.css)

    def test_tipke_ne_trcijo_s_stransko_vrstico(self):
        # Glavno okno: Ctrl+B je stranska vrstica (brez Shift), Medijski center Ctrl+Shift+B; Safeer Player tudi Ctrl+B.
        self.assertIn("if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (e.key === \"b\" || e.key === \"B\"))", self.js)
        self.assertIn("if (!(e.shiftKey || PREDVAJALNIK)) return;", self.js)
        self.assertIn('function navTipka() { return PREDVAJALNIK ? "Ctrl+B" : "Ctrl+Shift+B"; }', self.js)
        self.assertIn("navNastavi(!navSkrcena());", self.js)

    def test_zapomni_po_vrsti_okna_in_varno(self):
        self.assertIn('var NAV_KLJUC = "safeer_media_nav_" + (PREDVAJALNIK ? "player" : "glavno");', self.js)
        self.assertIn("try { localStorage.setItem(NAV_KLJUC, skrcena ? \"skrcena\" : \"\"); } catch (e) {}", self.js)
        self.assertIn("try { var shranjeno = localStorage.getItem(NAV_KLJUC);", self.js)

    def test_skrcena_ohrani_imena(self):
        # Samo ikone: ime v aria-label in namigu zavihkov, prostor dobi vsebina (virov v levem stolpcu ni vec).
        self.assertIn('if (cilj[1] === "media-nav-kategorija") { b.setAttribute("aria-label", t("media_" + k[0]));', self.js)
        self.assertIn("#r-media.nav-skrcena .media-telo { grid-template-columns: 64px minmax(0, 1fr); gap: 20px; }", self.css)


    def test_prej_skrita_postane_skrcena(self):
        self.assertIn('if (shranjeno === "skrcena" || shranjeno === "skrita") navNastavi(true);', self.js)

    def test_besedila(self):
        bes = _beri("assets", "os", "besedila.js")
        for kljuc in ("mediaNavSkrci", "mediaNavRazsiri"):
            self.assertEqual(bes.count('"%s":' % kljuc), 6, kljuc)
        for j in ("sl", "en", "de", "es", "fr", "it"):
            self.assertIn('Object.assign(BESEDILA_OS.%s, {"mediaNavSkrci"' % j, bes)


if __name__ == "__main__":
    unittest.main()
