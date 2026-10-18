"""Nova razlicica tece takoj po namestitvi (core/nova_razlicica.py; lastnik 18. 10. 2026: po `apt install` je stari
Safeer OS tekel se dneve). Spremljanje datoteke razlicice, cakanje na pravi trenutek, stanje in zagon nove razlicice."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

KOREN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN))
sys.path.insert(0, str(KOREN / "tests"))

from core import nova_razlicica as nr  # noqa: E402
from core.os_predvajalnik import Predvajalnik  # noqa: E402


class LazniGLib:
    """Brez zanke: casovnike shranimo in jih sprozimo rocno."""

    def __init__(self):
        self.casovniki = {}
        self._n = 0

    def timeout_add_seconds(self, s, f):
        self._n += 1
        self.casovniki[self._n] = (s, f)
        return self._n

    def source_remove(self, n):
        self.casovniki.pop(n, None)


class Spremljanje(unittest.TestCase):
    """Pravi Gio.FileMonitor: dpkg zamenja datoteko s preimenovanjem iz .dpkg-new."""

    def setUp(self):
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib
        self.Gio, self.GLib = Gio, GLib
        self._d = tempfile.TemporaryDirectory()
        self.mapa = Path(self._d.name) / "packaging"
        self.mapa.mkdir()
        self.pot = self.mapa / "VERSION_OS"
        self.pot.write_text("0.4.85\n")
        self.javljeno = []
        self.namescanje = [False]

    def tearDown(self):
        self._d.cleanup()

    def _spremljevalec(self):
        return nr.Spremljevalec(self.Gio, self.GLib, str(self.pot), "0.4.85", self.javljeno.append, zamik_s=1,
                                namescanje=lambda: self.namescanje[0])

    def _cakaj(self, s: float):
        konec = time.monotonic() + s
        kontekst = self.GLib.MainContext.default()
        while time.monotonic() < konec:
            kontekst.iteration(False)
            time.sleep(0.02)

    def _namesti(self, razlicica: str):
        nova = self.mapa / "VERSION_OS.dpkg-new"
        nova.write_text(razlicica + "\n")
        os.rename(nova, self.pot)

    def test_dpkg_zamenja_datoteko(self):
        s = self._spremljevalec()
        try:
            self._namesti("0.4.86")
            self._cakaj(3)
            self.assertEqual(self.javljeno, ["0.4.86"])
            # Ista razlicica se ne javi dvakrat; ista kot nasa sploh ne.
            self._namesti("0.4.86")
            self._cakaj(2.5)
            self.assertEqual(self.javljeno, ["0.4.86"])
        finally:
            s.ustavi()

    def test_caka_konec_namestitve_in_ne_ob_odstranitvi(self):
        s = self._spremljevalec()
        try:
            self.namescanje[0] = True
            self._namesti("0.4.87")
            self._cakaj(2.5)
            self.assertEqual(self.javljeno, [], "med dpkg se ne javi")
            self.namescanje[0] = False
            self._cakaj(2.5)
            self.assertEqual(self.javljeno, ["0.4.87"])
            self.pot.unlink()                     # odstranitev paketa: nic
            self._cakaj(2.5)
            self.assertEqual(self.javljeno, ["0.4.87"])
        finally:
            s.ustavi()

    def test_namescanje_iz_proc(self):
        with tempfile.TemporaryDirectory() as d:
            for pid, ime in (("12", "bash"), ("15", "dpkg"), ("x", "dpkg")):
                (Path(d) / pid).mkdir()
                (Path(d) / pid / "comm").write_text(ime + "\n")
            self.assertTrue(nr.namescanje_tece(d))
            (Path(d) / "15" / "comm").write_text("python3\n")
            self.assertFalse(nr.namescanje_tece(d))


class Cakanje(unittest.TestCase):
    def _cakanje(self, zaposleno="", nedejaven=None, zaklenjeno=False, takoj=False):
        self.stanje = {"z": zaposleno, "n": nedejaven, "l": zaklenjeno}
        self.izvedeno = []
        self.obvestila = []
        self.glib = LazniGLib()
        return nr.Cakanje(self.glib, lambda: self.stanje["z"], lambda: self.stanje["n"], lambda: self.stanje["l"],
                          lambda: self.izvedeno.append(1), takoj=takoj, ob_cakanju=self.obvestila.append)

    def test_razlogi(self):
        c = self._cakanje(zaposleno="predvajanje")
        self.assertEqual(c.razlog(), "predvajanje")
        self.stanje["z"] = ""
        self.assertEqual(c.razlog(), "", "namizje ne pove nedejavnosti: takoj, ko nic ne tece")
        self.stanje["n"] = 30.0
        self.assertEqual(c.razlog(), "uporabnik")
        self.stanje["l"] = True
        self.assertEqual(c.razlog(), "", "zaklenjen zaslon")
        self.stanje["l"], self.stanje["n"] = False, float(nr.NEDEJAVEN_S)
        self.assertEqual(c.razlog(), "")
        c = self._cakanje(nedejaven=1.0, takoj=lambda: True)
        self.assertEqual(c.razlog(), "", "posodobitev iz Safeer OS ne caka na nedejavnost")
        c = self._cakanje(zaposleno="klic", takoj=True)
        self.assertEqual(c.razlog(), "klic", "klica ne prekine niti posodobitev iz Safeer OS")

    def test_pocaka_in_izvede_enkrat(self):
        c = self._cakanje(zaposleno="prenos")
        c.zacni()
        self.assertEqual(self.izvedeno, [])
        self.assertEqual(self.obvestila, ["prenos"])
        (_s, tik), = self.glib.casovniki.values()
        self.stanje["z"] = "predvajanje"
        self.assertTrue(tik())
        self.assertEqual(self.obvestila, ["prenos"], "obvestilo samo enkrat")
        self.stanje["z"] = ""
        self.assertFalse(tik())
        self.assertEqual(self.izvedeno, [1])
        self.assertFalse(tik())
        self.assertEqual(self.izvedeno, [1])

    def test_takoj_brez_cakanja_in_gumb(self):
        c = self._cakanje()
        c.zacni()
        self.assertEqual(self.izvedeno, [1])
        self.assertEqual(self.glib.casovniki, {})
        c = self._cakanje(zaposleno="predvajanje")
        c.zacni()
        c.zdaj()
        self.assertEqual(self.izvedeno, [1])
        self.assertEqual(self.glib.casovniki, {})


class Stanje(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.okolje = mock.patch.dict(os.environ, {"SAFEER_NOVA_RAZLICICA_MAPA": os.path.join(self._d.name, "m")})
        self.okolje.start()

    def tearDown(self):
        self.okolje.stop()
        self._d.cleanup()

    def test_shrani_preberi_izbrise(self):
        self.assertTrue(nr.shrani_stanje("safeer-os", {"v": "0.4.86", "splet": ["https://a.si/"]}))
        pot = Path(nr.pot_stanja("safeer-os"))
        self.assertEqual(stat.S_IMODE(pot.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(pot.parent.stat().st_mode), 0o700)
        self.assertEqual(nr.preberi_stanje("safeer-os", "0.4.86")["splet"], ["https://a.si/"])
        self.assertFalse(pot.exists())
        self.assertEqual(nr.preberi_stanje("safeer-os", "0.4.86"), {})

    def test_vsak_program_svojo_datoteko(self):
        """E2E 18. 10. 2026: vgrajeni Control je prebral (in izbrisal) stanje Safeer OS, ko sta imela isto pot."""
        nr.shrani_stanje("safeer-os", {"v": "0.4.86", "splet": ["https://a.si/"]})
        self.assertEqual(nr.preberi_stanje("safeer-control", "2.1.83"), {})
        self.assertEqual(nr.preberi_stanje("safeer-os", "0.4.86")["splet"], ["https://a.si/"])

    def test_staro_ali_druga_razlicica(self):
        nr.shrani_stanje("safeer-os", {"v": "0.4.86"})
        self.assertEqual(nr.preberi_stanje("safeer-os", "0.4.87"), {})
        nr.shrani_stanje("safeer-os", {"v": "0.4.86"})
        pot = Path(nr.pot_stanja("safeer-os"))
        d = json.loads(pot.read_text())
        d["cas"] -= nr.STANJE_VELJA_S + 1
        pot.write_text(json.dumps(d))
        self.assertEqual(nr.preberi_stanje("safeer-os", "0.4.86"), {})

    def test_zavihki_in_lokalni_medij(self):
        def splet(*uri):
            return SimpleNamespace(zavihki=[{"pogled": SimpleNamespace(get_uri=lambda u=u: u)} for u in uri])
        self.assertEqual(nr.zavihki([None, splet("https://a.si/", "file:///usr/lib/safeer-os/ui/splet.html", "about:blank"),
                                     splet("http://b.si/x?y=1", "https://a.si/")]),
                         ["https://a.si/", "http://b.si/x?y=1"])
        datoteka = Path(self._d.name) / "film v.mkv"
        datoteka.write_bytes(b"x")
        self.assertEqual(nr.lokalni_medij(datoteka.as_uri()), str(datoteka))
        self.assertEqual(nr.lokalni_medij(str(datoteka)), str(datoteka))
        self.assertEqual(nr.lokalni_medij("http://192.168.1.5:8096/Videos/1/stream?api_key=x"), "")
        self.assertEqual(nr.lokalni_medij("file:///ni/te/datoteke.mkv"), "")

    def test_velja_samo_namescen_paket(self):
        self.assertTrue(nr.velja("/usr/lib/safeer-os", {}))
        self.assertFalse(nr.velja("/usr/lib/safeer-os", {"FLATPAK_ID": "x"}))
        self.assertFalse(nr.velja("/tmp/.mount_x/usr/lib/safeer-os", {"APPIMAGE": "/a"}))
        self.assertFalse(nr.velja(str(KOREN), {}))


class Pogledi(unittest.TestCase):
    def test_zvok_in_klic_v_oknih(self):
        NONE = object()

        class WebView:
            def __init__(self, zvok=False, kamera=False):
                self._z, self._k = zvok, kamera
                self.otroci = []

            def is_playing_audio(self):
                return self._z

            def get_camera_capture_state(self):
                return "aktivno" if self._k else NONE

            def get_microphone_capture_state(self):
                return NONE

            def get_display_capture_state(self):
                return NONE

            def get_first_child(self):
                return None

            def get_next_sibling(self):
                return getattr(self, "brat", None)

        class Skatla(WebView):
            def __init__(self, *otroci):
                super().__init__()
                self.otroci = list(otroci)
                for a, b in zip(self.otroci, self.otroci[1:]):
                    a.brat = b

            def get_first_child(self):
                return self.otroci[0] if self.otroci else None

        WebKit = SimpleNamespace(WebView=type("Pravi", (), {}), MediaCaptureState=SimpleNamespace(NONE=NONE))
        # Samo pravi razred WebView steje: zamenjamo ga z nasim.
        WebKit.WebView = WebView
        Gtk = SimpleNamespace(Window=SimpleNamespace(list_toplevels=lambda: []))
        okno = Skatla(Skatla(), Skatla(Skatla(WebView())))
        self.assertEqual(nr.zaposlenost_pogledov(Gtk, WebKit, [okno]), "")
        okno = Skatla(Skatla(WebView()), Skatla(Skatla(WebView(zvok=True))))
        self.assertEqual(nr.zaposlenost_pogledov(Gtk, WebKit, [okno]), "predvajanje")
        okno = Skatla(Skatla(WebView(zvok=True)), Skatla(WebView(kamera=True)))
        self.assertEqual(nr.zaposlenost_pogledov(Gtk, WebKit, [okno]), "klic")


class Predvajanje(unittest.TestCase):
    """Obnova ustavljenega predvajanja: nalozi v premoru (brez zvoka) in skoci na shranjeni polozaj."""

    def test_v_premoru(self):
        from test_os_predvajalnik import Element
        element = Element()
        gst = SimpleNamespace(ElementFactory=SimpleNamespace(make=lambda *_: element),
                              State=SimpleNamespace(NULL="null", PLAYING="playing", PAUSED="paused"),
                              StateChangeReturn=SimpleNamespace(FAILURE="failure"),
                              Format=SimpleNamespace(TIME="time"), SECOND=1_000_000_000, CLOCK_TIME_NONE=2**64 - 1,
                              SeekFlags=SimpleNamespace(FLUSH=1, KEY_UNIT=2),
                              MessageType=SimpleNamespace(EOS="eos", ERROR="error", ASYNC_DONE="async_done"))
        p = Predvajalnik(gst)
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        film, drugi = Path(d.name) / "film.mkv", Path(d.name) / "drugi.mkv"
        film.write_bytes(b"x")
        drugi.write_bytes(b"x")
        p.dodaj(film.as_uri(), predvajaj=True, vrsta="video", naslov="Film", zacetek=95, v_premoru=True)
        self.assertEqual(p.stanje, "premor")
        self.assertNotIn("playing", element.stanja)
        self.assertEqual(element.stanja[-1], "paused")
        self.assertTrue(p.poskusi_nadaljevati())
        self.assertEqual(element.skoki[-1][2], 95 * 1_000_000_000)
        p.premor()                                  # uporabnik pritisne predvajaj
        self.assertEqual(p.stanje, "predvaja")
        p.dodaj(drugi.as_uri(), predvajaj=True)
        self.assertEqual(element.stanja[-1], "playing", "brez v_premoru kot prej")


class ZagonNoveRazlicice(unittest.TestCase):
    def test_pod_zaganjalnikom_koda_75(self):
        with mock.patch.dict(os.environ, {"SAFEER_OS_NADZOR": str(os.getppid())}):
            self.assertEqual(nr.znova("SAFEER_OS_NADZOR", "/ni/skripte.py", ["--delovna"]), nr.KODA_ZNOVA)

    def test_brez_zaganjalnika_exec_nove_kode(self):
        with tempfile.TemporaryDirectory() as d:
            nova = Path(d) / "nova.py"
            nova.write_text("import sys\nprint('NOVA', sys.argv[1:])\n")
            koda = ("import sys; sys.path.insert(0, %r)\n"
                    "from core import nova_razlicica as nr\n"
                    "nr.znova('SAFEER_OS_NADZOR', %r, ['--magnet', 'magnet:?xt=1', '--delovna', '--okno'])\n"
                    "print('STARA SE NI KONCALA')\n" % (str(KOREN), str(nova)))
            okolje = {k: v for k, v in os.environ.items() if k != "SAFEER_OS_NADZOR"}
            r = subprocess.run([sys.executable, "-c", koda], capture_output=True, text=True, env=okolje, timeout=60)
        self.assertEqual(r.stdout.strip(), "NOVA ['--delovna', '--okno']", r.stderr)

    def _zaganjalnik(self, ime_zaganjalnika, mapa_lib, skripta, program, argumenti):
        d = tempfile.mkdtemp(prefix="safeer-nova-")
        app = Path(d) / "lib" / mapa_lib
        (app / "core").mkdir(parents=True)
        (Path(d) / "bin").mkdir()
        (app / skripta).write_text(program)
        (app / "core" / "__init__.py").write_text("")
        (app / "core" / "os_stabilnost.py").write_text("def zabelezi_sesutje(*a, **k):\n    return 1\n")
        # --delovna gre pod varuha procesov (core/varuh_procesov.py), ki koda 75 obravnava enako kot zanka zaganjalnika.
        (app / "core" / "varuh_procesov.py").write_text((KOREN / "core" / "varuh_procesov.py").read_text())
        zag = Path(d) / "bin" / mapa_lib
        zag.write_text((KOREN / "packaging" / ime_zaganjalnika).read_text())
        zag.chmod(0o755)
        (Path(d) / "run").mkdir(mode=0o700)
        okolje = dict(os.environ, XDG_CACHE_HOME=str(Path(d) / "cache"), PYTHON=sys.executable,
                      SAFEER_OS_BREZ_FLATPAKA="1", XDG_RUNTIME_DIR=str(Path(d) / "run"))
        r = subprocess.run(["bash", str(zag), *argumenti], capture_output=True, text=True, timeout=120, env=okolje)
        return r, app

    PROGRAM = ("import os, sys\n"
               "if '--vrni-mint' in sys.argv[1:]:\n    raise SystemExit(0)\n"
               "p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zagoni')\n"
               "open(p, 'a').write(' '.join(sys.argv[1:]) + '|' + os.environ.get('%s', '') + '|' + str(os.getppid()) + chr(10))\n"
               "n = len(open(p).read().splitlines())\n"
               "raise SystemExit(75 if n == 1 else 0)\n")

    def test_zaganjalnik_os_zazene_novega(self):
        r, app = self._zaganjalnik("safeer-os-launcher", "safeer-os", "safeer_os.py", self.PROGRAM % "SAFEER_OS_NADZOR",
                                   ["--delovna", "--magnet", "magnet:?xt=urn:btih:1"])
        self.assertEqual(r.returncode, 0, r.stderr)
        zagoni = (app / "zagoni").read_text().splitlines()
        self.assertEqual(len(zagoni), 2)
        self.assertTrue(zagoni[0].startswith("--delovna --magnet magnet:?xt=urn:btih:1|"))
        self.assertTrue(zagoni[1].startswith("--delovna|"), zagoni[1])     # enkratni ukaz se ne ponovi
        for vrstica in zagoni:
            _arg, nadzor, stars = vrstica.split("|")
            self.assertEqual(nadzor, stars, "zaganjalnik (za --delovna varuh procesov) je stars in to pove")

    def test_zaganjalnik_os_zazene_novega_brez_varuha(self):
        """Drugi nacini (Safeer Player, okno) ostanejo v zanki zaganjalnika - koda 75 zazene nov zaganjalnik."""
        r, app = self._zaganjalnik("safeer-os-launcher", "safeer-os", "safeer_os.py", self.PROGRAM % "SAFEER_OS_NADZOR",
                                   ["--predvajalnik"])
        self.assertEqual(r.returncode, 0, r.stderr)
        zagoni = (app / "zagoni").read_text().splitlines()
        self.assertEqual([z.split("|")[0] for z in zagoni], ["--predvajalnik", "--predvajalnik"])
        for vrstica in zagoni:
            _arg, nadzor, stars = vrstica.split("|")
            self.assertEqual(nadzor, stars)

    def test_zaganjalnik_control_zazene_novega(self):
        r, app = self._zaganjalnik("safeer-control-launcher", "safeer-control", "safeer_control.py",
                                   self.PROGRAM % "SAFEER_CONTROL_NADZOR", ["--ozadje"])
        self.assertEqual(r.returncode, 0, r.stderr)
        zagoni = (app / "zagoni").read_text().splitlines()
        self.assertEqual([z.split("|")[0] for z in zagoni], ["--ozadje", "--ozadje"])


class ShraniInObnovi(unittest.TestCase):
    """Safeer OS pred koncem shrani zavihke Spleta in predvajanje; nova razlicica jih obnovi (ustavljeno ostane ustavljeno)."""

    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.okolje = mock.patch.dict(os.environ, {"SAFEER_NOVA_RAZLICICA_MAPA": os.path.join(self._d.name, "m")})
        self.okolje.start()
        import safeer_os
        self.os_ = safeer_os
        self.film = Path(self._d.name) / "film.mkv"
        self.film.write_bytes(b"x")

    def tearDown(self):
        self.okolje.stop()
        self._d.cleanup()

    def _app(self, stanje_predvajalnika):
        servis = SimpleNamespace(trenutna=SimpleNamespace(uri=self.film.as_uri(), naslov="Film", vrsta="video"),
                                 stanje=stanje_predvajalnika, podatki=lambda: {"pozicija": 754.6, "trajanje": 5400})
        zavihek = {"pogled": SimpleNamespace(get_uri=lambda: "https://www.24ur.com/")}
        # Odprta okna Safeer OS (lupina v svojem procesu: obnova tudi po sesutju) - Zapiski odprti, Nastavitve skrite.
        okna = {"zapiski": (SimpleNamespace(get_visible=lambda: True), None),
                "nastavitve": (SimpleNamespace(get_visible=lambda: False), None)}
        app = mock.Mock(_ponovni_zagon=False, _koncano=False, _nova_razlicica="0.4.86", _medijski_predvajalnik=servis,
                        _spletni=SimpleNamespace(zavihki=[zavihek]), _spletni_namizje=None, okna_razdelkov=okna,
                        okno_predvajalnik=None)
        # Pravo zbiranje stanja (skupno za novo razlicico in obnovo po sesutju pod varuhom).
        app._stanje_za_obnovo = lambda **kw: self.os_.SafeerOS._stanje_za_obnovo(app, **kw)
        return app

    def test_shrani_konca_in_obnovi_ustavljeno(self):
        app = self._app("premor")
        self.os_.SafeerOS._znova_v_novo(app)
        self.assertTrue(app._ponovni_zagon)
        app._koncaj.assert_called_once()
        app._shrani_medijski_napredek.assert_called_once()        # »Nadaljuj z ogledom« dobi zadnji polozaj
        nova = mock.Mock()
        with mock.patch.object(self.os_, "RAZLICICA", "0.4.86"):
            self.os_.SafeerOS._obnovi_po_novi_razlicici(nova)
        nova._splet.assert_called_once_with("https://www.24ur.com/", True)
        nova._odpri_okno_razdelka.assert_called_once_with("zapiski")
        args, kw = nova._predvajaj_neposredno.call_args
        self.assertEqual(args[0], self.film.as_uri())
        self.assertEqual((kw["zacetek"], kw["v_premoru"], kw["prikazi"], kw["vrsta"]), (754, True, False, "video"))

    def test_izrecen_zagon_med_predvajanjem_nadaljuje(self):
        self.os_.SafeerOS._znova_v_novo(self._app("predvaja"))
        nova = mock.Mock()
        with mock.patch.object(self.os_, "RAZLICICA", "0.4.86"):
            self.os_.SafeerOS._obnovi_po_novi_razlicici(nova)
        self.assertFalse(nova._predvajaj_neposredno.call_args.kwargs["v_premoru"])

    def test_tok_s_streznika_ni_shranjen(self):
        app = self._app("premor")
        app._medijski_predvajalnik.trenutna.uri = "http://192.168.1.5:8096/Videos/1/stream?api_key=SKRIVNO"
        self.os_.SafeerOS._znova_v_novo(app)
        vsebina = Path(nr.pot_stanja("safeer-os")).read_text()
        self.assertNotIn("SKRIVNO", vsebina)
        self.assertNotIn("predvajanje", json.loads(vsebina))


class Povezava(unittest.TestCase):
    """Safeer OS in Control: spremljanje ob zagonu, zaposlenost in zagon nove razlicice ob koncu main()."""

    def test_safeer_os(self):
        vir = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
        zagon = vir[vir.index("    def do_startup(self) -> None:"):vir.index("    def do_shutdown(self)")]
        self.assertIn("self._spremljaj_novo_razlicico()", zagon)
        self.assertIn("self._obnovi_po_novi_razlicici", zagon)
        main = vir[vir.index("\ndef main("):]
        self.assertIn('nova_razlicica.znova("SAFEER_OS_NADZOR", os.path.abspath(__file__), _ZACETNI_ARGV[1:])', main)
        # Samo pravi zahtevek: lazni SafeerOS (MagicMock) v preizkusih main() ne sme sprozit exec (prej je pytest obvisel).
        self.assertIn('if getattr(app, "_ponovni_zagon", False) is True:', main)
        zap = vir[vir.index("    def _zaposleno(self)"):vir.index("    def _znova_v_novo(self)")]
        for kos in ('"predvajanje"', "zaposlenost_pogledov", "prenosi", "posodabljanje.tece()", 'budnost.dejavno("pomoc"',
                    "c.zaposlenost()"):
            self.assertIn(kos, zap)
        self.assertIn("self._posodobil_sam = True", vir)

    def test_safeer_control(self):
        vir = (KOREN / "safeer_control.py").read_text(encoding="utf-8")
        zagon = vir[vir.index("    def do_startup(self) -> None:"):]
        zagon = zagon[:zagon.index("\n    def ", 10)]
        self.assertIn("self._spremljaj_novo_razlicico()", zagon)
        self.assertIn('nova_razlicica.znova("SAFEER_CONTROL_NADZOR"', vir[vir.index("\ndef main("):])

    def test_besedila_v_vseh_jezikih(self):
        self.assertEqual(set(nr.BESEDILA), {"sl", "en", "de", "es", "fr", "it"})
        for jezik, b in nr.BESEDILA.items():
            self.assertEqual(set(b), {"naslov", "besedilo", "zdaj"}, jezik)
        self.assertEqual(nr.besedila("sl", "Safeer OS", "0.4.86")["naslov"], "Safeer OS 0.4.86 je nameščen")

    def test_v_tovoru(self):
        for tovor in ("install_os_payload.sh", "install_control_payload.sh"):
            self.assertRegex((KOREN / "packaging" / tovor).read_text(), r"for modul in [^\n]*\bnova_razlicica\b")


if __name__ == "__main__":
    unittest.main()
