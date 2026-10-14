"""Safeer Browser za Linux na GTK4 (Splet v svojem oknu) - lastnik 14. 10. 2026: najnovejsa tehnologija tudi tu."""
import os
import tempfile
import unittest

import safeer_brskalnik as b


class Naslovi(unittest.TestCase):
    def test_argumenti(self):
        with tempfile.NamedTemporaryFile(suffix=".html") as f:
            n = b.naslovi_iz_argumentov(["--x", "https://a.si/", "about:blank", f.name, "ni-datoteka"])
        self.assertEqual(n[:2], ["https://a.si/", "about:blank"])
        self.assertTrue(n[2].startswith("file://"))
        self.assertEqual(len(n), 3)


class Seja(unittest.TestCase):
    def test_shrani_in_nalozi(self):
        class C(dict):
            def set(self, k, v):
                self[k] = v
        c = C()
        b.shrani_sejo(c, ["https://a.si/", "file:///x/splet.html", "http://b.si/", ""])
        self.assertEqual(b.nalozi_sejo(c), ["https://a.si/", "http://b.si/"])


class Okno(unittest.TestCase):
    def test_splet_v_oknu_z_drm_in_temnim(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["XDG_CONFIG_HOME"] = d
            app = b.SafeerBrskalnik()
            app.register(None)
            app._ustvari()
            s = app.splet
            self.assertIs(app.okno.get_child(), s.gradnik)
            self.assertFalse(s.povezava.get_visible())        # brez oznake Safeer Linka
            self.assertTrue(hasattr(s, "_drm_vdelaj"))         # Safeer DRM (Widevine) v zavihku
            self.assertTrue(hasattr(s, "_temno_namesti"))      # Dark Reader
            app.okno.destroy()


def test_zaprtje_okna_konca_drm():
    """Preizkus 14. 10.: po zaprtju okna je safeer-drm na gostitelju ostal (flatpak-spawn) in drzal Flatpak."""
    besedilo = open(os.path.join(b.KOREN, "safeer_brskalnik.py"), encoding="utf-8").read()
    telo = besedilo.split("def _ob_zaprtju", 1)[1].split("def do_activate", 1)[0]
    assert "koncaj_drm()" in telo
    splet = open(os.path.join(b.KOREN, "core", "os_splet.py"), encoding="utf-8").read()
    telo = splet.split("def koncaj_drm", 1)[1].split("def _drm_konec", 1)[0]
    assert "self.zavihki" in telo and "_drm_konec(z)" in telo
