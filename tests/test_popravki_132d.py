"""Popravki srednjih najdb neodvisnega pregleda izdaje 1.0.132 (S1-S4, N1, N2; 21. 10. 2026).

S1 --exclude-libs samo za libxml2/libxslt/libexslt, N1 preverba praznih ldflags iz modula, S2 vse knjiznice WebKita,
JSC in libsoup pod naso predpono, S3 realpath, N2 SAFEER_WEBKIT_PREDPONA samo za izvorno kodo, S4 brisanje seznama
gostiteljev brez https za vse Splete procesa. Okolje procesa se ne spreminja (AGENTS.md): kar ga rabi, tece v podprocesu."""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import https_nadgradnja as H  # noqa: E402
from core import zasebni_webkit as zw  # noqa: E402


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


def maps(*poti):
    return "".join("7f0000000000-7f0000001000 r-xp 00000000 08:01 %d %s\n" % (i, p) for i, p in enumerate(poti))


class TestS1N1Povezovanje(unittest.TestCase):
    def test_exclude_libs_samo_za_tri_arhive(self):
        for pot, vsebina in (("packaging/webkit-deb/zgradi.sh", beri("packaging", "webkit-deb", "zgradi.sh")),
                             (".github/workflows/linux-packages.yml", beri(".github", "workflows", "linux-packages.yml")),
                             ("packaging/webkit/webkitgtk6-safeer.yml", beri("packaging", "webkit", "webkitgtk6-safeer.yml")),
                             ("packaging/webkit-deb/modul.py", beri("packaging", "webkit-deb", "modul.py"))):
            with self.subTest(pot=pot):
                self.assertNotIn("exclude-libs,ALL", vsebina)
        self.assertIn('export LDFLAGS="$WK_LDFLAGS -Wl,--exclude-libs,libxml2.a:libxslt.a:libexslt.a"',
                      beri("packaging", "webkit-deb", "zgradi.sh"))

    def _tek(self, ldflags):
        """Vrstice zgradi.sh od WK_LDFLAGS do export LDFLAGS, s polje() iz modula WebKita (ldflags)."""
        s = beri("packaging", "webkit-deb", "zgradi.sh")
        a = s.index('WK_LDFLAGS="$(polje ldflags')
        b = s.index("\n", s.index("export LDFLAGS=", a))
        skripta = ("set -e\npolje() { printf '%s' \"$LDF\"; }\nWK_JSON=x\n" + s[a:b] + '\necho "LDFLAGS=$LDFLAGS"\n')
        return subprocess.run(["bash", "-c", skripta], capture_output=True, text=True, timeout=30,
                              env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LDF": ldflags})

    def test_prazni_ldflags_iz_modula_ustavijo_gradnjo(self):
        r = self._tek("")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("nima ldflags", r.stderr)

    def test_ldflags_iz_modula_in_tri_arhivi(self):
        r = self._tek("-Wl,-z,relro,-z,now")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("LDFLAGS=-Wl,-z,relro,-z,now -Wl,--exclude-libs,libxml2.a:libxslt.a:libexslt.a", r.stdout)


class TestS2S3NasWebkit(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.pred = os.path.join(self.d, "safeer-webkit")
        os.makedirs(os.path.join(self.pred, "lib"))
        for ime in ("libwebkitgtk-6.0.so.4", "libjavascriptcoregtk-6.0.so.1", "libsoup-3.0.so.0"):
            open(os.path.join(self.pred, "lib", ime), "w").close()
        self.nase = [os.path.join(self.pred, "lib", ime) for ime in
                     ("libwebkitgtk-6.0.so.4", "libjavascriptcoregtk-6.0.so.1", "libsoup-3.0.so.0")]

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def _preveri(self, vsebina, predpona=None):
        with mock.patch.object(zw, "_koren_nasega", lambda p=None: p):     # brez FLATPAK_ID/APPDIR iz okolja
            return zw.preveri_nas_webkit(WebKit=None, uveljavi=False, maps_vsebina=vsebina,
                                         predpona=self.pred if predpona is None else predpona)

    def test_vse_nase(self):
        je_nas, pot, _r = self._preveri(maps(*self.nase))
        self.assertTrue(je_nas)
        self.assertEqual(pot, self.nase[0])

    def test_mesano_nalaganje_webkit(self):
        """Prej: prva pot po abecedi (»/tmp…/safeer-webkit« pred »/usr/lib/x86_64…«) je dala »nas«."""
        je_nas, pot, _r = self._preveri(maps(*self.nase, "/usr/lib/x86_64-linux-gnu/libwebkitgtk-6.0.so.4.3.5"))
        self.assertFalse(je_nas)
        self.assertEqual(pot, "/usr/lib/x86_64-linux-gnu/libwebkitgtk-6.0.so.4.3.5")

    def test_sistemski_libsoup_ali_jsc(self):
        for tuja in ("/usr/lib/x86_64-linux-gnu/libsoup-3.0.so.0.4.4",
                     "/usr/lib/x86_64-linux-gnu/libjavascriptcoregtk-6.0.so.1.3.5"):
            with self.subTest(tuja=tuja):
                je_nas, pot, _r = self._preveri(maps(self.nase[0], tuja))
                self.assertFalse(je_nas)
                self.assertEqual(pot, tuja)

    def test_predpona_je_simbolna_povezava(self):
        """maps kaze razreseno pot; predpona iz nastavi() je lahko povezava (prej lazni izhod namescenega programa)."""
        povezava = os.path.join(self.d, "lib64-safeer-webkit")
        os.symlink(self.pred, povezava)
        je_nas, _pot, _r = self._preveri(maps(*self.nase), predpona=povezava)
        self.assertTrue(je_nas)

    def test_brez_webkita_ni_nas(self):
        je_nas, pot, _r = self._preveri(maps(self.nase[2]))
        self.assertFalse(je_nas)
        self.assertIsNone(pot)

    def test_izbrisana_datoteka_in_drugi_vnosi(self):
        n = zw.nalozene_knjiznice(maps(self.nase[0] + " (deleted)", "/usr/lib/libsoupx.so", "[heap]") + "7f00 r-xp 0 0 0\n")
        self.assertEqual(n, {"libwebkitgtk-6.0": {self.nase[0]}})

    def test_n2_predpona_iz_okolja_samo_za_izvorno_kodo(self):
        koda = ("import sys; sys.path.insert(0, sys.argv[1]); from core import zasebni_webkit as zw\n"
                "zw._namescen = lambda: sys.argv[2] == '1'\n"
                "print(zw.nastavi('/nikjer'), zw.poisci_nas_webkit(None))\n")
        os.makedirs(os.path.join(self.pred, "lib", "girepository-1.0"))
        open(os.path.join(self.pred, zw.TYPELIB), "w").close()
        okolje = {k: v for k, v in os.environ.items() if k not in ("FLATPAK_ID", "APPIMAGE", "APPDIR",
                                                                    "SAFEER_SISTEMSKI_WEBKIT")}
        okolje["SAFEER_WEBKIT_PREDPONA"] = self.pred
        for namescen in ("1", "0"):
            with self.subTest(namescen=namescen):
                r = subprocess.run([sys.executable, "-c", koda, KOREN, namescen], capture_output=True, text=True,
                                   timeout=30, env=okolje)
                self.assertEqual(r.returncode, 0, r.stderr)
                prvi, drugi = r.stdout.split()
                if namescen == "1":
                    self.assertNotIn(self.pred, (prvi, drugi))      # namesceni program: okolje ne doloca WebKita
                else:
                    self.assertEqual((prvi, drugi), (self.pred, self.pred))


class TestS4SejaHttps(unittest.TestCase):
    def test_en_primerek_na_mapo(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = H.seja_za(d), H.seja_za(os.path.join(d, "."))
            self.assertIs(a, b)
            a.povratek("primer.si")
            b.pocisti()
            self.assertFalse(a.je_brez_https("primer.si"))
            H._SEJE.pop(os.path.realpath(d), None)

    def test_brisanje_v_drugem_procesu(self):
        """Drug proces (ista mapa) je izbrisal datoteko: seznam v pomnilniku tega procesa ne sme ostati."""
        with tempfile.TemporaryDirectory() as d:
            s = H.Seja(d)
            s.povratek("primer.si")
            self.assertTrue(s.je_brez_https("primer.si"))
            os.remove(os.path.join(d, H.DATOTEKA_POVRATKOV))
            self.assertFalse(s.je_brez_https("primer.si"))
            self.assertEqual(s.nadgradnja("http://primer.si/", "GET"), "https://primer.si/")

    def test_splet_uporablja_skupno_sejo(self):
        s = beri("core", "os_splet.py")
        self.assertIn("https_nadgradnja.seja_za(mapa)", s)
        self.assertIn("https_nadgradnja.seja_za(self.config.config_dir).pocisti()", s)
        self.assertNotIn("https_nadgradnja.Seja(", s)

    def test_seja_brez_mape_ostane_v_pomnilniku(self):
        s = H.seja_za(None)
        s.povratek("primer.si")
        self.assertTrue(s.je_brez_https("primer.si"))


if __name__ == "__main__":
    unittest.main()
