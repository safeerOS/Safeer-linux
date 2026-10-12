"""Vmesne izboljsave 12. 10. 2026: dvojni Esc zapre Splet, Browser obnovi prevelik omrezni proces med mirovanjem,
Splet ob zaklepu zaslona sprosti pomnilnik."""
import ast
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KOREN = Path(__file__).resolve().parents[1]


def _funkcija(datoteka, ime):
    drevo = ast.parse((KOREN / datoteka).read_text(encoding="utf-8"))
    vozel = next(n for n in drevo.body if isinstance(n, ast.FunctionDef) and n.name == ime)
    prostor = {}
    exec(compile(ast.Module(body=[vozel], type_ignores=[]), datoteka, "exec"), prostor)
    return prostor[ime]


class DvojniEsc(unittest.TestCase):
    def setUp(self):
        self.f = _funkcija("safeer_os.py", "dvojni_esc")

    def test_hitro_zaporedje(self):
        self.assertTrue(self.f(1000, 1400))
        self.assertTrue(self.f(1000, 1600))

    def test_prepocasi_ali_prvi(self):
        self.assertFalse(self.f(1000, 1601))
        self.assertFalse(self.f(None, 1000))
        self.assertFalse(self.f(1000, 0))
        self.assertFalse(self.f(2000, 1000))

    def test_vgrajeno_v_tipko_spleta(self):
        besedilo = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
        zacetek = besedilo.index("def _tipka_splet_na_namizju")
        telo = besedilo[zacetek:besedilo.index("\n    def ", zacetek + 10)]
        self.assertLess(telo.index("dvojni_esc"), telo.index("propagate_key_event"))


class RecikliranjeOmreznega(unittest.TestCase):
    def setUp(self):
        from core.pomnilnik import recikliraj_omrezni
        self.f = recikliraj_omrezni
        self.osnova = dict(okno_aktivno=False, neaktivno_s=301, prenosi=False, nalaganje=False, zvok=False,
                           pss_mb=350, meja_mb=300)

    def test_mirovanje_nad_mejo(self):
        self.assertTrue(self.f(**self.osnova))

    def test_nikoli_med_uporabo(self):
        for kljuc, vrednost in (("okno_aktivno", True), ("prenosi", True), ("nalaganje", True), ("zvok", True),
                                ("neaktivno_s", 299), ("pss_mb", 299), ("meja_mb", 0)):
            with self.subTest(kljuc):
                self.assertFalse(self.f(**dict(self.osnova, **{kljuc: vrednost})))

    def test_browser_klice_odlocitev(self):
        besedilo = (KOREN / "safeer_mint.py").read_text(encoding="utf-8")
        self.assertIn("self._recikliraj_omrezni_proces(zdaj)", besedilo)
        self.assertIn("recikliraj_omrezni(", besedilo)


class OmrezniProcesShrambe(unittest.TestCase):
    def test_pss_tega_procesa(self):
        from core import os_splet
        self.assertGreater(os_splet.pss_mb(os.getpid()), 1)
        self.assertEqual(os_splet.pss_mb(2 ** 22 + 7), 0.0)

    def test_izbere_po_piskotkih(self):
        from core import os_splet
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "cookies.sqlite")
            odprte = {1: {"/x"}, 2: {os.path.realpath(p)}}
            with mock.patch.object(os_splet, "omrezni_procesi", return_value={1, 2}), \
                    mock.patch.object(os_splet, "odprte_datoteke", side_effect=lambda pid: odprte[pid]):
                self.assertEqual(os_splet.omrezni_procesi_shrambe(p), [2])


class ZaklepSpleta(unittest.TestCase):
    def _splet(self, mapa, nalaga=False):
        from core import os_splet
        s = os_splet.VdelaniSplet.__new__(os_splet.VdelaniSplet)
        pogled = mock.Mock()
        pogled.is_loading.return_value = nalaga
        s.zavihki, s.aktivni = [{"pogled": pogled}], pogled

        class Config:
            config_dir = mapa
        s.config = Config()
        return s, os_splet

    def test_velik_proces_obnovi_zavihki_ostanejo(self):
        with tempfile.TemporaryDirectory() as d:
            s, os_splet = self._splet(d)
            with mock.patch.object(os_splet.VdelaniSplet, "sprazni_predpomnilnik") as sp, \
                    mock.patch.object(os_splet, "omrezni_procesi_shrambe", return_value=[7]), \
                    mock.patch.object(os_splet, "pss_mb", return_value=400), \
                    mock.patch.object(os_splet.os, "kill") as kill:
                self.assertTrue(s.ob_zaklepu())
            sp.assert_called_once()
            kill.assert_called_once_with(7, 15)
            self.assertEqual(len(s.zavihki), 1)

    def test_majhen_ali_med_nalaganjem_ne(self):
        for nalaga, velikost in ((False, 100), (True, 900)):
            with tempfile.TemporaryDirectory() as d:
                s, os_splet = self._splet(d, nalaga)
                with mock.patch.object(os_splet.VdelaniSplet, "sprazni_predpomnilnik"), \
                        mock.patch.object(os_splet, "omrezni_procesi_shrambe", return_value=[7]), \
                        mock.patch.object(os_splet, "pss_mb", return_value=velikost), \
                        mock.patch.object(os_splet.os, "kill") as kill:
                    self.assertFalse(s.ob_zaklepu())
                kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class SpletVPrivzetemBrskalniku(unittest.TestCase):
    """Uporabnik, ki mu je ljubsi drug brskalnik: iskanje po spletu iz polja na namizju odpre privzeti brskalnik."""

    def setUp(self):
        self.js = (KOREN / "assets/os/delovna.js").read_text(encoding="utf-8")

    def test_stikalo_v_nastavitvah(self):
        html = (KOREN / "assets/os/delovna.html").read_text(encoding="utf-8")
        self.assertIn('id="stikaloBrskalnik"', html)
        self.assertIn("spletVBrskalniku: false", self.js)
        self.assertEqual(self.js.count("spletVBrskalniku:"), 3)      # sl, en, privzeto

    def test_iskanje_najprej_preveri_stikalo(self):
        zacetek = self.js.index("function odpriSplet(q)")
        telo = self.js[zacetek:self.js.index("\n  }\n", zacetek)]
        self.assertLess(telo.index("N.spletVBrskalniku"), telo.index('klic("spletNaNamizju"'))
        self.assertIn('klic("odpriVBrskalniku", [q])', telo)

    def test_ime_privzetega_brskalnika(self):
        f = _funkcija("safeer_os.py", "privzeti_brskalnik")

        class App:
            def get_display_name(self):
                return "Opera"

        class AppInfo:
            ime = App()

            @classmethod
            def get_default_for_uri_scheme(cls, shema):
                return cls.ime if shema == "https" else None

        f.__globals__["Gio"] = type("Gio", (), {"AppInfo": AppInfo})
        self.assertEqual(f(), "Opera")
        AppInfo.ime = None
        self.assertEqual(f(), "")


class SistemskeNastavitve(unittest.TestCase):
    """Uporabnik ima vedno proste roke: vse nastavitve namizja so dosegljive iz nastavitev delovne povrsine."""

    def test_gumbi_in_besedila(self):
        html = (KOREN / "assets/os/delovna.html").read_text(encoding="utf-8")
        js = (KOREN / "assets/os/delovna.js").read_text(encoding="utf-8")
        for modul in ("themes", "backgrounds", "fonts", "display", "windows", "panel", "nightlight", ""):
            self.assertIn('data-modul="%s"' % modul, html)
        for kljuc in ("modulTeme", "modulVse", "sistemNaslov"):
            self.assertEqual(js.count(kljuc + ":"), 2)       # sl, en
        self.assertIn('klic("sistemskeNastavitve"', js)

    def test_samo_znani_moduli(self):
        f = _funkcija("safeer_os.py", "sistemske_nastavitve")
        zagnano = []

        class Sp:
            DEVNULL = None

            @staticmethod
            def Popen(ukaz, **_k):
                zagnano.append(ukaz)

        f.__globals__.update(subprocess=Sp, MODULI_NASTAVITEV=("", "themes"))
        with mock.patch("shutil.which", lambda u: "/usr/bin/" + u if u == "cinnamon-settings" else None):
            self.assertTrue(f("themes"))
            self.assertTrue(f(""))
            self.assertFalse(f("; rm -rf /"))
        self.assertEqual(zagnano, [["cinnamon-settings", "themes"], ["cinnamon-settings"]])


class ZaprtiZavihkiSeSprostijo(unittest.TestCase):
    """12. 10. 2026: rokovalnik sporocil je z mocno referenco na pogled naredil krog C-Python, ki ga zbiralnik ne vidi;
    vsak zaprt zavihek Spleta je ostal ziv (+2,2 MiB). Rokovalniki morajo pogled drzati sibko."""

    def test_brez_mocne_reference_na_pogled(self):
        import re
        for datoteka, vzorec in (("core/os_splet.py", r"lambda _u, r: self\._sporocilo\(pogled"),
                                 ("core/drm.py", r"def ob_sporocilu\(_u, _r\):\n        url = pogled"),
                                 ("safeer_mint.py", r"posiljatelj=wv"),
                                 ("safeer_os.py", r"lambda _u, r: self\._na_sporocilo\(pogled")):
            with self.subTest(datoteka):
                self.assertIsNone(re.search(vzorec, (KOREN / datoteka).read_text(encoding="utf-8")))


class BliznjiceSpleta(unittest.TestCase):
    """Splet: iste bliznjice kot v obicajnih brskalnikih (uporabnik opazi cim manj sprememb)."""

    def test_preslikava(self):
        from core.os_splet import blizjica as b
        pricakovano = {
            ("t", 1, 0, 0): "nov", ("T", 1, 1, 0): "obnovi-zaprt", ("w", 1, 0, 0): "zapri",
            ("Tab", 1, 0, 0): "naslednji", ("ISO_Left_Tab", 1, 1, 0): "prejsnji", ("Page_Down", 1, 0, 0): "naslednji",
            ("l", 1, 0, 0): "naslov", ("F6", 0, 0, 0): "naslov", ("d", 0, 0, 1): "naslov",
            ("r", 1, 0, 0): "osvezi", ("F5", 0, 0, 0): "osvezi", ("r", 1, 1, 0): "osvezi-brez",
            ("f", 1, 0, 0): "najdi", ("d", 1, 0, 0): "zaznamek", ("plus", 1, 0, 0): "povecaj",
            ("minus", 1, 0, 0): "pomanjsaj", ("0", 1, 0, 0): "povecava-0", ("3", 1, 0, 0): "zavihek-3",
            ("9", 1, 0, 0): "zavihek-zadnji", ("Left", 0, 0, 1): "nazaj", ("Right", 0, 0, 1): "naprej",
        }
        for (t, c, s, a), d in pricakovano.items():
            with self.subTest(t=t, c=c, s=s, a=a):
                self.assertEqual(b(t, bool(c), bool(s), bool(a)), d)

    def test_obicajne_tipke_ostanejo_strani(self):
        from core.os_splet import blizjica as b
        for t in ("a", "Escape", "Return", "space", "Left", "BackSpace"):
            self.assertIsNone(b(t))
        self.assertIsNone(b("c", True))      # Ctrl+C kopira na strani
        self.assertIsNone(b("v", True))

    def _splet(self, uri_tren="https://a.si/"):
        from core import os_splet
        s = os_splet.VdelaniSplet.__new__(os_splet.VdelaniSplet)
        pogledi = [mock.Mock(), mock.Mock(), mock.Mock()]
        for i, p in enumerate(pogledi):
            p.get_uri.return_value = "https://s%d.si/" % i
        s.zavihki = [{"pogled": p} for p in pogledi]
        s.aktivni = pogledi[0]
        s.izberi = lambda p: setattr(s, "aktivni", p)
        s.trenutni = lambda: s.aktivni
        s.nov_zavihek = mock.Mock()
        return s, pogledi

    def test_preklapljanje_in_obnova_zaprtega(self):
        s, p = self._splet()
        s.izvedi("naslednji"); self.assertIs(s.aktivni, p[1])
        s.izvedi("prejsnji"); s.izvedi("prejsnji"); self.assertIs(s.aktivni, p[2])
        s.izvedi("zavihek-1"); self.assertIs(s.aktivni, p[0])
        s.izvedi("zavihek-zadnji"); self.assertIs(s.aktivni, p[2])
        s._zapomni_zaprt(p[1])
        s.izvedi("obnovi-zaprt")
        s.nov_zavihek.assert_called_once_with("https://s1.si/")


class ZacasniFiltri(unittest.TestCase):
    def test_odstrani_samo_stare_zacasne(self):
        import time
        from core.filter_lists import pocisti_zacasne_filtre
        with tempfile.TemporaryDirectory() as d:
            for ime in ("ContentRuleList-abc123", "ContentRuleList-XYZ789", "ContentRuleList-safeer-easylist",
                        "compiled.sha256"):
                Path(d, ime).write_text("x")
            star = time.time() - 7200
            for ime in ("ContentRuleList-abc123", "ContentRuleList-safeer-easylist", "compiled.sha256"):
                os.utime(os.path.join(d, ime), (star, star))
            self.assertEqual(pocisti_zacasne_filtre(d), 1)
            self.assertEqual(sorted(os.listdir(d)), ["ContentRuleList-XYZ789", "ContentRuleList-safeer-easylist",
                                                     "compiled.sha256"])


class UvozZavihkov(unittest.TestCase):
    """Seja Chromium (SNSS): trenutna stran vsakega odprtega zavihka; zaprti zavihki izpusceni."""

    @staticmethod
    def _ukaz(st, vsebina):
        import struct
        return struct.pack("<HB", len(vsebina) + 1, st) + vsebina

    @staticmethod
    def _nav(tab, indeks, url):
        import struct
        b = url.encode()
        telo = struct.pack("<iii", tab, indeks, len(b)) + b + b"\0" * ((4 - len(b) % 4) % 4)
        return struct.pack("<I", len(telo)) + telo

    def test_seja(self):
        import struct
        from core.uvoz_zavihkov import preberi_sejo
        p = b"SNSS" + struct.pack("<i", 3)
        p += self._ukaz(6, self._nav(1, 0, "https://a.si/"))
        p += self._ukaz(6, self._nav(1, 1, "https://a.si/druga"))
        p += self._ukaz(7, struct.pack("<ii", 1, 1))
        p += self._ukaz(6, self._nav(2, 0, "https://b.si/"))
        p += self._ukaz(6, self._nav(3, 0, "https://zaprt.si/"))
        p += self._ukaz(16, struct.pack("<iq", 3, 0))
        p += self._ukaz(6, self._nav(4, 0, "chrome://newtab/"))
        self.assertEqual(preberi_sejo(p), ["https://a.si/druga", "https://b.si/"])
        self.assertEqual(preberi_sejo(b"nesmisel"), [])

    def test_najde_opero(self):
        from core.uvoz_zavihkov import najdi_seje
        with tempfile.TemporaryDirectory() as d:
            mapa = Path(d, ".config/opera/Sessions"); mapa.mkdir(parents=True)
            (mapa / "Session_1").write_bytes(b"SNSS")
            self.assertEqual(list(najdi_seje(d)), ["Opera"])


class Zgodovina(unittest.TestCase):
    def test_dodaj_isci(self):
        from core import zgodovina
        with tempfile.TemporaryDirectory() as d:
            pot = os.path.join(d, "history.json")
            self.assertTrue(zgodovina.dodaj(pot, "https://a.si/", "Prva"))
            self.assertTrue(zgodovina.dodaj(pot, "https://a.si/", "Prva 2"))
            self.assertTrue(zgodovina.dodaj(pot, "https://b.si/", "Druga"))
            self.assertFalse(zgodovina.dodaj(pot, "file:///etc/passwd"))
            z = zgodovina.nalozi(pot)
            self.assertEqual([x["url"] for x in z], ["https://b.si/", "https://a.si/"])
            self.assertEqual(z[1]["title"], "Prva 2")
            self.assertEqual([x["url"] for x in zgodovina.isci(z, "druga")], ["https://b.si/"])

    def test_bliznjici(self):
        from core.os_splet import blizjica, besedila
        self.assertEqual(blizjica("h", True), "zgodovina")
        self.assertEqual(blizjica("O", True, True), "zaznamki")
        for j in ("sl", "en", "de", "es", "fr", "it"):
            for k in ("zaznamki", "zgodovina", "uvozi", "uvoz_zavihki", "zapri", "prazno"):
                self.assertIn(k, besedila(j))
