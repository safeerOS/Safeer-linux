"""Dodatek Stremio na racunalniku tako enostavno kot na Androidu (lastnik, 11. 10. 2026): gumb »Install« (stremio://)
v Spletu ali v drugem brskalniku odpre okno Dodatki v Safeer Playerju, gumb Prilepi, naslov /configure ali manifesta
velja za isti dodatek. Brez omrezja in brez GTK."""
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)
from core import media_servers, os_media  # noqa: E402


def _beri(pot):
    with open(os.path.join(KOREN, pot), encoding="utf-8") as f:
        return f.read()


class NaslovDodatka(unittest.TestCase):
    def test_install_manifest_koren_configure(self):
        n = media_servers.stremio_naslov_dodatka
        self.assertEqual(n("stremio://d.primer.si/abc/manifest.json"), "https://d.primer.si/abc/manifest.json")
        self.assertEqual(n("https://d.primer.si/abc/"), "https://d.primer.si/abc/manifest.json")
        self.assertEqual(n("https://d.primer.si/abc/configure"), "https://d.primer.si/abc/manifest.json")
        self.assertEqual(n("https://d.primer.si/configure/"), "https://d.primer.si/manifest.json")
        self.assertEqual(n("http://192.168.0.10:7000/manifest.json"), "http://192.168.0.10:7000/manifest.json")

    def test_zavrne(self):
        n = media_servers.stremio_naslov_dodatka
        for slab in ("", "javascript:alert(1)", "file:///etc/passwd", "http://d.primer.si/manifest.json",
                     "https://u:g@d.primer.si/manifest.json", "https://d.primer.si/manifest.json?x=1",
                     "https://d.primer.si/a b/manifest.json", "stremio:///manifest.json"):
            self.assertEqual(n(slab), "", slab)

    def test_koren_brez_configure(self):
        self.assertEqual(media_servers._stremio_koren("https://d.primer.si/x/configure"), "https://d.primer.si/x")
        self.assertEqual(media_servers._stremio_koren("https://d.primer.si/x/manifest.json"), "https://d.primer.si/x")


class DodajanjeEnkrat(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="safeer-stremio-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.mc = os_media.MediaCenter(self.tmp, roots=[], secret_encryptor=lambda s: s, secret_decryptor=lambda s: s)
        for p in (mock.patch.object(media_servers, "stremio_preveri", lambda base: ""),
                  mock.patch.object(media_servers, "authenticate", lambda *a, **k: {}),
                  mock.patch.object(media_servers, "stremio_manifest", lambda url: {"id": "x", "name": "Preizkusni dodatek", "resources": ["stream"]})):
            p.start()
            self.addCleanup(p.stop)

    def test_isti_dodatek_iz_razlicnih_naslovov(self):
        r = self.mc.add_server("stremio", "", "stremio://d.primer.si/abc/manifest.json", "", "")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["vir"]["url"], "https://d.primer.si/abc/manifest.json")
        self.assertEqual(r["vir"]["ime"], "Preizkusni dodatek")
        for drug in ("https://d.primer.si/abc/configure", "https://d.primer.si/abc", "https://d.primer.si/abc/manifest.json"):
            r2 = self.mc.add_server("stremio", "", drug, "", "")
            self.assertFalse(r2["ok"], drug)
            self.assertTrue(r2.get("podvojen"), drug)
            self.assertIn("dodatek", r2["napaka"])


class SpletPredaGumbInstall(unittest.TestCase):
    """Splet (VdelaniSplet) povezave stremio:// ne odpre: odda jo Safeer Playerju, stran sama ne doda nicesar."""

    def _splet(self, klici):
        from core import os_splet
        s = os_splet.VdelaniSplet.__new__(os_splet.VdelaniSplet)

        class W:
            class PolicyDecisionType:
                NAVIGATION_ACTION, NEW_WINDOW_ACTION, RESPONSE = 0, 1, 2

        class G:
            @staticmethod
            def idle_add(fn):
                fn()

        s.WebKit2, s.GLib = W, G
        s.stremio_dodatek = lambda url: klici.append(url) or True
        s.nov_zavihek = lambda url: self.fail("stremio:// ne sme v nov zavihek")
        return s, W

    def _odlocitev(self, url, ignorirano):
        class Zahteva:
            def get_uri(self):
                return url

            def get_http_method(self):
                return "GET"

        class Dejanje:
            def get_request(self):
                return Zahteva()

        class Odlocitev:
            def get_navigation_action(self):
                return Dejanje()

            def ignore(self):
                ignorirano.append(True)

            def use(self):
                raise AssertionError("stremio:// se ne sme odpreti")
        return Odlocitev()

    def test_install_gre_playerju(self):
        for vrsta in (0, 1):
            klici, ign = [], []
            s, W = self._splet(klici)
            self.assertTrue(s._politika(None, self._odlocitev("stremio://d.primer.si/manifest.json", ign), vrsta))
            self.assertEqual(klici, ["stremio://d.primer.si/manifest.json"])
            self.assertEqual(ign, [True])


class Namestitev(unittest.TestCase):
    def test_vnos_x_scheme_handler(self):
        vnos = _beri("packaging/safeer-os-stremio.desktop")
        self.assertIn("MimeType=x-scheme-handler/stremio;", vnos)
        self.assertIn("Exec=safeer-os --stremio %u", vnos)
        self.assertIn("NoDisplay=true", vnos)
        self.assertIn("safeer-os-stremio.desktop", _beri("packaging/install_os_payload.sh"))
        self.assertIn("$ID.Stremio.desktop", _beri("packaging/install_os_payload.sh"))

    def test_safeer_os(self):
        s = _beri("safeer_os.py")
        for niz in ('Gio.SimpleAction.new("stremio"', '"cakajociStremio"', '"odlozisceBesedilo"', '"--stremio"',
                    "def stremio_privzeto", "stremio_dodatek=self._odpri_stremio_dodatek"):
            self.assertIn(niz, s)
        # Obstojece izbire (npr. aplikacija Stremio) ne spremenimo: privzeto nastavimo samo, ce ga ni.
        self.assertIn("if not zdaj and vnos:", s)

    def test_stran(self):
        js, html, bes = _beri("assets/os/os.js"), _beri("assets/os/index.html"), _beri("assets/os/besedila.js")
        self.assertIn('id="katPrilepi"', html)
        self.assertIn('vrsta === "stremioDodatek"', js)
        self.assertIn('klic("cakajociStremio")', js)
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            vrstica = next(v for v in bes.splitlines() if v.startswith("Object.assign(BESEDILA_OS.%s, {\"katPrilepi\"" % jezik))
            for kljuc in ("katPrilepi", "katStremioPotrdi", "katOdloziscePrazno"):
                self.assertIn('"%s"' % kljuc, vrstica)
            self.assertTrue(re.search(r"\{gostitelj\}", vrstica), jezik)


if __name__ == "__main__":
    unittest.main()
