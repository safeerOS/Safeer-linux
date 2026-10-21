"""Profil naprave (core/profil_naprave.py): Splet in Safeer Browser po zmogljivosti naprave (lastnik 21. 10. 2026).

Varcni profil (TV-podobne naprave, < 7 GiB MemTotal) mora imeti DANASNJE meje (brez regresije); polni vec."""
import os
import sys
import tempfile
import types
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import pomnilnik, profil_naprave as P  # noqa: E402


def _meminfo(gib: float) -> str:
    return "MemTotal:       %d kB\nMemFree:         123456 kB\nMemAvailable:    234567 kB\n" % int(gib * 1024 * 1024)


def _profil(gib: float, jedra: int = 4) -> "P.Profil":
    return P.iz_podatkov(P.ram_iz_meminfo(_meminfo(gib)), jedra)


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class TestProfil(unittest.TestCase):
    def test_profil_iz_meminfo(self):
        for gib, ime in ((2, "varcni"), (2.8, "varcni"), (4, "varcni"), (6, "varcni"), (7.44, "polni"), (8, "polni"),
                         (11.6, "polni"), (16, "polni")):
            with self.subTest(gib=gib):
                self.assertEqual(_profil(gib).ime, ime)

    def test_varcni_ima_danasnje_meje(self):
        """Brez regresije na TV-podobnih napravah: iste meje kot pred profilom (core/pomnilnik)."""
        for gib in (2, 2.8, 3.8, 4, 6):
            p = _profil(gib)
            with self.subTest(gib=gib):
                self.assertEqual(p.meja_strani_mb, pomnilnik.meja_strani_mb(p.ram_mb))
                self.assertEqual(p.meja_sprostitve_mb, pomnilnik.meja_sprostitve_mb(p.ram_mb))
                self.assertIsNone(p.niti_slikanja_cpu)          # privzeto WebKita, kot danes

    def test_polni_ima_vec(self):
        for gib in (8, 16):
            p = _profil(gib, jedra=8)
            with self.subTest(gib=gib):
                self.assertEqual(p.meja_strani_mb, pomnilnik.meja_strani_mb(p.ram_mb))
                self.assertGreater(p.meja_sprostitve_mb, pomnilnik.meja_sprostitve_mb(p.ram_mb))
                self.assertEqual(p.niti_slikanja_cpu, 7)
                self.assertIsNone(p.meja_procesov)
        self.assertIsNone(_profil(16, jedra=2).niti_slikanja_cpu)     # dve jedri: privzeto WebKita
        self.assertEqual(_profil(16, jedra=32).niti_slikanja_cpu, 8)  # WebKit dovoli najvec 8

    def test_model_predpomnilnika(self):
        """Varcni brez predpomnilnika procesov (samo WEB_BROWSER ga vklopi - WebProcessCache::updateCapacity)."""
        self.assertEqual(_profil(2.8).model_predpomnilnika, "DOCUMENT_BROWSER")
        self.assertEqual(_profil(16).model_predpomnilnika, "WEB_BROWSER")
        klici = []
        W = types.SimpleNamespace(CacheModel=types.SimpleNamespace(DOCUMENT_BROWSER="db", WEB_BROWSER="wb"),
                                  WebContext=types.SimpleNamespace(get_default=lambda: types.SimpleNamespace(
                                      set_cache_model=klici.append)))
        self.assertTrue(P.nastavi_model(W, profil=_profil(2.8)))
        self.assertTrue(P.nastavi_model(W, profil=_profil(16)))
        self.assertEqual(klici, ["db", "wb"])

    def test_trenutni_bere_meminfo(self):
        with tempfile.NamedTemporaryFile("w", suffix=".meminfo", delete=False) as d:
            d.write(_meminfo(3.5))
        try:
            P._trenutni = None
            self.assertEqual(P.trenutni(d.name).ime, "varcni")
        finally:
            P._trenutni = None
            os.unlink(d.name)

    def test_okolje_niti_slikanja(self):
        okolje = {}
        self.assertEqual(P.okolje_pred_nitmi(okolje, _profil(16, jedra=4)), {"WEBKIT_SKIA_CPU_PAINTING_THREADS": "3"})
        self.assertEqual(okolje["WEBKIT_SKIA_CPU_PAINTING_THREADS"], "3")
        uporabnik = {"WEBKIT_SKIA_CPU_PAINTING_THREADS": "1"}
        self.assertEqual(P.okolje_pred_nitmi(uporabnik, _profil(16, jedra=8)), {})      # uporabnikovo ostane
        self.assertEqual(uporabnik["WEBKIT_SKIA_CPU_PAINTING_THREADS"], "1")
        varcno = {}
        self.assertEqual(P.okolje_pred_nitmi(varcno, _profil(2.8)), {})
        self.assertEqual(varcno, {})


class TestDeljenjeProcesa(unittest.TestCase):
    def test_registrirana_domena(self):
        for g, d in (("www.rtvslo.si", "rtvslo.si"), ("a.b.example.co.uk", "example.co.uk"), ("rtvslo.si", "rtvslo.si"),
                     ("192.168.0.1", "192.168.0.1"), ("nas", "nas"), ("user.github.io", "user.github.io")):
            with self.subTest(g=g):
                self.assertEqual(P.registrirana_domena(g), d)

    def test_deli_samo_varcni_nad_mejo_ista_domena(self):
        v = _profil(2.8)
        meja = v.meja_procesov
        self.assertGreaterEqual(meja, 3)
        zavihki = [("A", "www.rtvslo.si", True), ("B", "en.wikipedia.org", True)]
        self.assertEqual(P.deli_proces(v, meja, "sport.rtvslo.si", zavihki), "A")
        self.assertIsNone(P.deli_proces(v, meja - 1, "sport.rtvslo.si", zavihki))        # pod mejo: svoj proces
        self.assertIsNone(P.deli_proces(v, meja, "github.com", zavihki))                 # druga domena
        self.assertIsNone(P.deli_proces(_profil(16), 99, "sport.rtvslo.si", zavihki))    # polni: nikoli
        self.assertIsNone(P.deli_proces(v, meja, "sport.rtvslo.si", [("A", "www.rtvslo.si", False)]))  # ne sme

    def test_obcutljive_strani_nikoli(self):
        v = _profil(2.8)
        meja = v.meja_procesov
        zavihki = [("A", "www.nlb.si", True), ("G", "www.google.com", True), ("M", "mail.google.com", True)]
        self.assertIsNone(P.deli_proces(v, meja, "klik.nlb.si", zavihki, banke=("nlb.si",)))
        self.assertIsNone(P.deli_proces(v, meja, "mail.google.com", zavihki))
        self.assertIsNone(P.deli_proces(v, meja, "accounts.google.com", zavihki))
        self.assertEqual(P.deli_proces(v, meja, "news.google.com", zavihki), "G")       # ne z mail.google.com


class TestVezava(unittest.TestCase):
    """Splet, Safeer OS in Safeer Browser profil res uporabljajo (preizkusi v kodi)."""

    def test_splet(self):
        s = beri("core", "os_splet.py")
        kontekst = s[s.index("    def _ustvari_kontekst"):s.index("    def _ustvari_kontekst") + 4000]
        self.assertLess(kontekst.index("profil_naprave.nastavi_model("), kontekst.index("pomnilnik.kontekst("))
        self.assertIn("self.profil.meja_sprostitve_mb, ubij_mb=self.profil.meja_strani_mb", kontekst)
        self.assertNotIn("CacheModel.WEB_BROWSER", s)               # model doloca samo profil
        self.assertIn("deli_z = self._deli_proces_z(naslov) if povezan is None else None", s)
        # GPU proces za DOM samo na polnem profilu IN z zastavico (A/B meritev pred privzetim vklopom)
        gpu = s.index('("UseGPUProcessForDOMRendering", True)')
        self.assertIn('self.profil.polni and self.config.get("splet_gpu_dom", False)', s[gpu - 400:gpu])
        sprosti = s[s.index("    def sprosti_zavihke"):s.index("    def ob_zaklepu")]
        self.assertIn("terminate_web_process()", sprosti)            # zaprt Splet ne pusti procesov v predpomnilniku
        self.assertLess(sprosti.index("oznaci_zaprt("), sprosti.index("terminate_web_process()"))

    def test_safeer_os_in_brskalnik(self):
        for datoteka, prvi_pogled in (("safeer_os.py", "WebKit2.WebView("), ("safeer_brskalnik.py", "VdelaniSplet(Gtk")):
            s = beri(datoteka)
            with self.subTest(datoteka=datoteka):
                self.assertLess(s.index("profil_naprave.okolje_pred_nitmi()"), s.index("import gi  # noqa: E402"))
                self.assertIn('if __name__ == "__main__":\n    profil_naprave.okolje_pred_nitmi()', s)
                self.assertLess(s.index("profil_naprave.nastavi_model(WebKit2)"), s.index(prvi_pogled))
        self.assertNotIn("CacheModel.DOCUMENT_VIEWER", beri("safeer_os.py"))   # globalni model ne preglasi Spleta

    def test_tovor(self):
        self.assertIn(" profil_naprave ", beri("packaging", "install_os_payload.sh"))


if __name__ == "__main__":
    unittest.main()
