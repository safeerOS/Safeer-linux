"""Leva navigacija Medijskega centra se skrci na ikone ali povsem skrije in se zlahka spet pokaze (lastnik, 14. 10. 2026),
kot stranska vrstica Safeer OS. Izris preverjen z WebKitGTK 6.0 pod xvfb pri 1440 px (razsirjena, skrcena, skrita z
rocajem; Ctrl+B v Safeer Playerju jo pokaze in izbor gre na izbran zavihek)."""
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

    def test_gumbi_in_rocaj(self):
        telo = self.html.split('<div class="media-telo">', 1)[1].split('<div class="media-vsebina">', 1)[0]
        self.assertIn('id="mediaNavRocaj" type="button" aria-controls="mediaNav"', telo)
        self.assertLess(telo.index('id="mediaNavRocaj"'), telo.index('<nav class="media-nav"'))   # prvi stolpec mreze
        self.assertIn('id="mediaNavSkrci" type="button" aria-controls="mediaNav" aria-expanded="true"', telo)
        self.assertIn('id="mediaNavSkrij" type="button" aria-controls="mediaNav"', telo)

    def test_tipke_ne_trcijo_s_stransko_vrstico(self):
        # Glavno okno: Ctrl+B je stranska vrstica (brez Shift), Medijski center Ctrl+Shift+B; Safeer Player tudi Ctrl+B.
        self.assertIn("if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (e.key === \"b\" || e.key === \"B\"))", self.js)
        self.assertIn("if (!(e.shiftKey || PREDVAJALNIK)) return;", self.js)
        self.assertIn('function navTipka() { return PREDVAJALNIK ? "Ctrl+B" : "Ctrl+Shift+B"; }', self.js)
        self.assertIn('if (navStanje() === "skrita") navNastavi("", true);', self.js)

    def test_zapomni_po_vrsti_okna_in_varno(self):
        self.assertIn('var NAV_KLJUC = "safeer_media_nav_" + (PREDVAJALNIK ? "player" : "glavno");', self.js)
        self.assertIn("try { localStorage.setItem(NAV_KLJUC, stanje); } catch (e) {}", self.js)
        self.assertIn("try { var shranjeno = localStorage.getItem(NAV_KLJUC);", self.js)

    def test_skrcena_ohrani_imena(self):
        # Samo ikone: ime v aria-label in namigu (zavihki in viri), prostor dobi vsebina.
        self.assertIn('if (cilj[1] === "media-nav-kategorija") { b.setAttribute("aria-label", t("media_" + k[0]));', self.js)
        self.assertIn('b.setAttribute("aria-label", v.ime + ", " + v.pod);', self.js)
        self.assertIn("#r-media.nav-skrcena .media-telo { grid-template-columns: 64px minmax(0, 1fr); gap: 20px; }", self.css)
        self.assertIn("#r-media.nav-skrita .media-telo { grid-template-columns: 16px minmax(0, 1fr); gap: 12px; }", self.css)
        self.assertIn("#r-media.nav-skrita .media-nav { display: none; }", self.css)
        # Rocaj je viden samo, ko je navigacija skrita in je Medijski center dovolj sirok za levo navigacijo.
        self.assertIn(".media-nav-rocaj { display: none; }", self.css)

    def test_fokus_po_skritju_in_prikazu(self):
        self.assertIn('if (stanje === "skrita") { var rocaj = $("mediaNavRocaj"); if (rocaj) rocaj.focus(); }', self.js)
        self.assertIn('document.querySelector(".media-nav-kategorija.izbrana")', self.js)

    def test_besedila(self):
        bes = _beri("assets", "os", "besedila.js")
        for kljuc in ("mediaNavSkrci", "mediaNavRazsiri", "mediaNavSkrij", "mediaNavPokazi"):
            self.assertEqual(bes.count('"%s":' % kljuc), 6, kljuc)
        for j in ("sl", "en", "de", "es", "fr", "it"):
            self.assertIn('Object.assign(BESEDILA_OS.%s, {"mediaNavSkrci"' % j, bes)


if __name__ == "__main__":
    unittest.main()
