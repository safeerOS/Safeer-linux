"""Nacin za kavc v Medijskem centru (lastnik, 11. 10. 2026): daljinec, telefon, igralni plosek - in vedno tudi miska.
Safeer Player se odpre cez cel zaslon. Brez GTK; logiko v brskalniku preverja tools (Playwright) rocno."""
import os
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(pot):
    with open(os.path.join(KOREN, pot), encoding="utf-8") as f:
        return f.read()


class Kavc(unittest.TestCase):
    def test_stran_nalozi_kavc(self):
        html = _beri("assets/os/index.html")
        self.assertIn('<script src="kavc.js"></script>', html)
        self.assertIn('id="medijiKavc"', html)
        self.assertLess(html.index('src="os.js"'), html.index('src="kavc.js"'))

    def test_tipke_miska_plosek(self):
        js = _beri("assets/os/kavc.js")
        for niz in ('ArrowLeft: "levo"', '"BrowserBack"', '"Backspace"', "gamepadconnected", "getGamepads",
                    '"mousemove"', '"kavc-miska"', '"kavc-tipke"', 'klic("kavcCelZaslon"'):
            self.assertIn(niz, js)
        self.assertTrue(all(ord(c) < 128 for c in js), "kavc.js: samo ASCII (kot ostale skripte strani)")

    def test_cel_zaslon_in_besedila(self):
        py = _beri("safeer_os.py")
        self.assertIn('"kavcCelZaslon": lambda: self._kavc_cel_zaslon(pogled', py)
        self.assertIn("okno.fullscreen()", py)
        telo = py.split("def _ustvari_predvajalnik", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("okno.maximize()", telo)
        self.assertNotIn("if iskanje and not self.posnetek", telo)      # vedno cez cel zaslon, ne samo ob iskanju
        bes = _beri("assets/os/besedila.js")
        for j in ("sl", "en", "de", "es", "fr", "it"):
            self.assertIn('BESEDILA_OS.%s, {"kavcVklop"' % j, bes)
        # Lastnik 15. 10. 2026: »Celozaslonski nacin« s standardno ikono; povecava je stran potisnila cez rob zaslona.
        self.assertNotIn("html.kavc body { zoom", _beri("assets/os/os.css"))
        self.assertIn('BESEDILA_OS.sl, {"kavcVklop": "Celozaslonski način"', bes)
        self.assertIn('id="medijiKavc" type="button" aria-pressed="false"><svg data-ikona="celZaslon">', _beri("assets/os/index.html"))
        kavc = _beri("assets/os/kavc.js")
        self.assertIn('ime = vklop ? "celZaslonIzhod" : "celZaslon"', kavc)
        self.assertIn('if (e.key !== "F11"', kavc)
        self.assertIn("window.SafeerIkone = IK;", _beri("assets/os/os.js"))


if __name__ == "__main__":
    unittest.main()
