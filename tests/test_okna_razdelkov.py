"""Delovna povrsina ne odpira vec stare lupine Safeer OS (lastnik, 12. 10. 2026): razdelki imajo svoje mesto na
namizju - Zapiski, Sporocila in Nastavitve svoje okno, Naprave Safeer Control, Splet plosco Spleta na namizju."""
import os
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Os:
    def __init__(self, delovna=True):
        self.okno = None
        self.okno_delovna = object() if delovna else None
        self.klici = []

    def _odpri_okno_razdelka(self, ime, cilj=""):
        self.klici.append(("okno", ime, cilj)); return True

    def _prijava(self):
        self.klici.append(("control",)); return True

    def _splet_na_namizju(self, niz, vrh=0, domov=False):
        self.klici.append(("splet", niz, domov)); return True

    def _odpri_predvajalnik(self, iskanje=""):
        self.klici.append(("player", iskanje)); return True

    def _ustvari_okno(self):
        self.klici.append(("lupina",))

    def _domov(self, razdelek=""):
        self.klici.append(("domov", razdelek)); return True


class OknaRazdelkov(unittest.TestCase):
    def setUp(self):
        import safeer_os
        self.so = safeer_os

    def _odpri(self, razdelek, delovna=True):
        o = _Os(delovna)
        with mock.patch.object(self.so.GLib, "timeout_add", lambda *a, **k: 0):
            self.so.SafeerOS._odpri_razdelek(o, razdelek)
        return o.klici

    def test_na_delovni_povrsini_ni_stare_lupine(self):
        self.assertEqual(self._odpri("zapiski"), [("okno", "zapiski", "zapiski")])
        self.assertEqual(self._odpri("zapisek:abc"), [("okno", "zapiski", "zapisek:abc")])
        self.assertEqual(self._odpri("sporocila"), [("okno", "sporocila", "sporocila")])
        self.assertEqual(self._odpri("nastavitve#blokScit"), [("okno", "nastavitve", "nastavitve#blokScit")])
        self.assertEqual(self._odpri("naprave"), [("control",)])
        self.assertEqual(self._odpri("splet"), [("splet", "", True)])
        self.assertEqual(self._odpri("media"), [("player", "")])
        for r in ("zapiski", "sporocila", "nastavitve", "naprave", "splet", "media", "domov"):
            self.assertNotIn(("lupina",), self._odpri(r), r)

    def test_brez_delovne_povrsine_ostane_lupina(self):
        # GNOME, Xfce ... (brez Safeer Cinnamon): Safeer OS v oknu je edini vmesnik.
        self.assertEqual(self._odpri("zapiski", delovna=False)[0], ("lupina",))

    def test_meni_na_cinnamonu_ne_ponuja_lupine(self):
        vnos = open(os.path.join(KOREN, "packaging", "safeer-os.desktop"), encoding="utf-8").read()
        self.assertRegex(vnos, r"(?m)^NotShowIn=X-Cinnamon;$")

    def test_stran_pozna_okno_razdelka(self):
        js = open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8").read()
        css = open(os.path.join(KOREN, "assets", "os", "os.css"), encoding="utf-8").read()
        self.assertIn("razdelek=(zapiski|sporocila|nastavitve|scit)", js)
        self.assertIn("if (EN_RAZDELEK) return;", js, "okna razdelkov ne smejo slediti »pojdi« glavnega okna")
        self.assertIn("body.en-razdelek .razdelek:not(.viden)", css)
        self.assertEqual(set(self.so.RAZDELKI_V_SVOJEM_OKNU), {"zapiski", "sporocila", "nastavitve", "scit"})


if __name__ == "__main__":
    unittest.main()


class PloscaSporocil(unittest.TestCase):
    """Sporocila na namizju (lastnik, 12. 10. 2026): kuverta z neprebranimi v pultu, plosca s pogovori."""

    def setUp(self):
        import safeer_os
        self.so = safeer_os

    def test_ikona_kuverte_s_stevilom(self):
        import tempfile
        with tempfile.TemporaryDirectory() as mapa:
            poti = [self.so.ikona_kuverte(n, mapa) for n in (0, 3, 12, 3)]
            self.assertEqual([os.path.basename(p) for p in poti], ["kuverta-0.png", "kuverta-3.png", "kuverta-9p.png", "kuverta-3.png"])
            for p in poti:
                with open(p, "rb") as d:
                    self.assertEqual(d.read(8), b"\x89PNG\r\n\x1a\n")

    def test_pogovor_iz_plosce_odpre_okno_sporocil(self):
        o = _Os()
        with mock.patch.object(self.so.GLib, "timeout_add", lambda *a, **k: 0):
            self.so.SafeerOS._odpri_razdelek(o, "pogovor:l:n-123")
            self.so.SafeerOS._odpri_razdelek(o, "sporocila:novo")
        self.assertEqual(o.klici, [("okno", "sporocila", "pogovor:l:n-123"), ("okno", "sporocila", "sporocila:novo")])

    def test_plosca_je_v_paketu_in_klice_obstojece_metode(self):
        js = open(os.path.join(KOREN, "assets", "os", "sporocila-plosca.js"), encoding="utf-8").read()
        self.assertTrue(os.path.isfile(os.path.join(KOREN, "assets", "os", "sporocila-plosca.html")))
        vir = open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8").read()
        for metoda in ("sporocilaSeznam", "odpriRazdelek", "skrijPloscoSporocil"):
            self.assertIn('klic("%s"' % metoda, js)
            self.assertIn('"%s":' % metoda, vir)
        os_js = open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8").read()
        self.assertIn('kam.indexOf("pogovor:") === 0', os_js)
        self.assertIn('kam === "sporocila:novo"', os_js)
