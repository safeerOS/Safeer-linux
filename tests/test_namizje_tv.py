"""Namizje za ogled od dalec (lastnik, 11. 10. 2026): iskanje v predvajalniku na namizju, velikost besedila do 200 %,
kategorije programov v eni vrstici in iskanje programov ob izbiri naprave. Brez GTK."""
import os
import unittest
from besedila_namizja import besedila, stevilo  # noqa: E402 - skupni slovar namizja

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(pot):
    with open(os.path.join(KOREN, pot), encoding="utf-8") as f:
        return f.read()


class NamizjeTv(unittest.TestCase):
    def test_iskanje_v_predvajalniku(self):
        html, js = _beri("assets/os/delovna.html"), _beri("assets/os/delovna.js")
        mediji = html.split('id="ploscaMediji"', 1)[1].split("</section>", 1)[0]
        self.assertIn('id="medijIskanjePolje"', mediji)
        self.assertIn('id="medijZadetki"', mediji)
        self.assertIn('klic("mediaKatalog", [q, "vse"', js)
        self.assertIn("poveziMedijIskanje();", js)
        self.assertIn("odpriIzKataloga(z.k)", js)

    def test_velikost_besedila_do_200(self):
        html, py, sc = _beri("assets/os/delovna.html"), _beri("safeer_os.py"), _beri("packaging/tema-cinnamon/safeer-cinnamon")
        self.assertIn('<option value="200"', html)
        self.assertIn("int(vklop) in (100, 125, 150, 160, 175, 200)", py)
        self.assertIn('stanje["tekstOdstotek"]', py)
        self.assertIn("200) tekst 2.0 ;; 175) tekst 1.75 ;;", sc)

    def test_programi_ena_vrstica(self):
        html, css = _beri("assets/os/delovna.html"), _beri("assets/os/delovna.css")
        glava = html.split('id="ploscaProgrami"', 1)[1].split('class="prg-orodja"', 1)[0]
        self.assertIn('id="prgFilter"', glava)          # iskanje ob izbiri naprave
        self.assertLess(glava.index('id="prgFilter"'), glava.index('id="prgNaprava"'))
        self.assertIn("flex-wrap: nowrap; overflow-x: auto", css)


if __name__ == "__main__":
    unittest.main()


class ProgramiTegaRacunalnika(unittest.TestCase):
    def test_privzeto_ta_racunalnik(self):
        js = _beri("assets/os/delovna.js")
        self.assertIn('return v == null ? "ta" : v;', js)
        self.assertIn('localStorage.setItem("safeer_prg_naprava", this.value)', js)
        self.assertIn('var nedosegljive = $("prgNaprava").value !== "ta" ? P.nedosegljive : [];', js)
        # Nedosegljive naprave: ena kratka vrstica s stevilom, ne nastevanje imen.
        self.assertNotIn('P.nedosegljive.forEach', js)
        self.assertIn('"{n} naprave niso dosegljive"', besedila())

    def test_oblika_ob_istem_imenu(self):
        import sys
        sys.path.insert(0, KOREN)
        from core import os_programi
        self.assertEqual(os_programi.oblika_namestitve("/home/u/.local/share/flatpak/exports/share/applications/a.desktop"), "Flatpak")
        self.assertEqual(os_programi.oblika_namestitve("/var/lib/snapd/desktop/applications/a.desktop"), "Snap")
        self.assertEqual(os_programi.oblika_namestitve("/usr/share/applications/a.desktop"), "")
