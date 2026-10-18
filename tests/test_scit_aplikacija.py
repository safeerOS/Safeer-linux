"""Safeer Scit kot svoj program (lastnik, 18. 10. 2026): svoj vnos v meniju in okno (razdelek »scit«) z vsemi
nastavitvami in statistiko. Nastavitve so EN blok (#blokScit), ki ga uporabljajo Nastavitve, vodnik in okno Scita -
blok se premakne, ne podvoji; spremembe gredo vsem oknom (dogodek »scit«). Streznik naprej ima en vir (Scit)."""
import json
import os
import sys
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class Program(unittest.TestCase):
    def test_vnos_v_meniju_in_okno(self):
        import safeer_os
        self.assertIn("scit", safeer_os.OKNA_V_PULTU)
        self.assertIn("scit", safeer_os.RAZDELKI_V_SVOJEM_OKNU)
        self.assertEqual(safeer_os.razred_in_ikona("scit")[0], "safeer-os.scit")
        for jezik, ime in (("sl", "Safeer Ščit"), ("en", "Safeer Shield"), ("de", "Safeer Schild")):
            self.assertEqual(safeer_os._NASLOVI_RAZDELKOV[jezik]["scit"], ime)
        vnos = _beri("packaging", "safeer-os-scit.desktop")
        self.assertIn("Exec=safeer-os --razdelek scit", vnos)
        self.assertIn("StartupWMClass=safeer-os.scit", vnos)
        self.assertNotIn("NoDisplay=true", vnos)                  # svoj program: v meniju viden
        for jezik in ("sl", "de", "es", "fr", "it"):
            self.assertIn("Name[%s]=" % jezik, vnos)
            self.assertIn("Comment[%s]=" % jezik, vnos)

    def test_na_delovni_povrsini_svoje_okno(self):
        import safeer_os
        klici = []

        class Os:
            okno, okno_delovna = None, object()

            def _odpri_okno_razdelka(self, ime, cilj=""):
                klici.append((ime, cilj))
                return True
        with mock.patch.object(safeer_os.GLib, "timeout_add", lambda *a, **k: 0):
            safeer_os.SafeerOS._odpri_razdelek(Os(), "scit")
        self.assertEqual(klici, [("scit", "scit")])

    def test_pult_odpre_okno_scita(self):
        vir = _beri("safeer_os.py")
        telo = vir[vir.index("    def _zacni_scit_pult(self)"):vir.index("    def _osvezi_scit_pult(")]
        self.assertIn('self._odpri_razdelek("scit")', telo)

    def test_spremembe_gredo_vsem_oknom(self):
        """Vsak klic, ki Scit spremeni, gre skozi _po_scitu (pult + dogodek »scit« vsem stranem)."""
        vir = _beri("safeer_os.py")
        for metoda in ("scitVklop", "scitDovoli", "scitNaprej", "scitTwitch", "scitPremor"):
            vrstica = vir[vir.index('"%s": lambda: ' % metoda):]
            self.assertTrue(vrstica.split("\n", 1)[0].startswith('"%s": lambda: self._po_scitu(' % metoda), metoda)
        import safeer_os
        dogodki = []
        jaz = mock.MagicMock()
        jaz._dogodek = lambda v, p: dogodki.append((v, p))
        with mock.patch.object(safeer_os.GLib, "idle_add", lambda fn, *a: fn(*a)):
            safeer_os.SafeerOS._po_scitu(jaz, {"vklop": True})
        self.assertEqual(dogodki, [("scit", {"vklop": True})])


class EnVirNaprej(unittest.TestCase):
    """Splet (nastavitve DNS) in Scit (okno Safeer Scit) imata en streznik naprej - prej vsak svojega."""

    def test_splet_bere_in_pise_scit(self):
        from core import doh_proxy, os_scit
        import tempfile

        class Shramba(dict):
            def set(self, k, v):
                self[k] = v

        class Config(dict):
            def set(self, k, v):
                self[k] = v
        with tempfile.TemporaryDirectory() as m, mock.patch.object(os_scit, "izprazni_predpomnilnik"), \
                mock.patch.object(os_scit, "pravilo_namesceno", return_value=False), \
                mock.patch.object(os_scit, "razlog_nemoznosti", return_value="ni_resolved"):
            scit = os_scit.Scit(Shramba(scit_naprej="quad9"), mapa=m)
            config = Config(scit_naprej="google")
            with mock.patch.object(doh_proxy, "_vir_naprej", None):
                self.assertEqual(doh_proxy.naprej_iz(config), ("google", ""))       # samostojni Safeer Browser
                doh_proxy.nastavi_vir_naprej(scit)
                self.assertEqual(doh_proxy.naprej_iz(config), ("quad9", ""))         # v Safeer OS: Scit
                self.assertEqual(doh_proxy.shrani_naprej(config, "adguard"), "")
                self.assertEqual((scit.naprej()[0], config["scit_naprej"]), ("adguard", "google"))
                self.assertEqual(doh_proxy.shrani_naprej(config, "custom", "127.0.0.53"), "naprej_zanka")
                self.assertEqual(scit.naprej()[0], "adguard")
                # Skupni razresevalnik Spleta dobi spremembo iz Scita takoj.
                r = doh_proxy.DoHResolver("scit", naprej="cloudflare")
                with mock.patch.object(doh_proxy, "_global_resolver", r):
                    scit.nastavi_naprej("opendns")
                    self.assertEqual(r.naprej, "opendns")
                    kwargs = {}
                    with mock.patch.object(doh_proxy, "get_doh_proxy", lambda **k: kwargs.update(k)):
                        doh_proxy.doh_iz_nastavitev(Config(doh_provider="scit", scit_naprej="google"))
                    self.assertEqual(kwargs["naprej"], "opendns")

    def test_dialog_spleta_uporablja_en_vir(self):
        vir = _beri("core", "os_splet.py")
        self.assertNotIn('self.config.set("scit_naprej"', vir)
        self.assertIn("shrani_naprej(self.config, n,", vir)
        self.assertIn("naprej_iz(self.config)", vir)


class ZivoOkno(unittest.TestCase):
    """Okno Safeer Scit (index.html?razdelek=scit) v pravem WebKitGTK 6.0 z laznim mostom."""

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            raise unittest.SkipTest("ni zaslona (xvfb-run)")
        try:
            import gi
            gi.require_version("WebKit", "6.0")
            gi.require_version("Gtk", "4.0")
            from gi.repository import GLib, Gtk, WebKit
        except (ImportError, ValueError) as e:
            raise unittest.SkipTest("ni WebKitGTK 6.0: %s" % e)
        cls.GLib, cls.Gtk, cls.WebKit = GLib, Gtk, WebKit
        Gtk.init()

    STANJE = {"vklop": True, "tece": True, "mozno": True, "razlog": "", "napaka": "", "blokiranih": 5, "poizvedb": 50,
              "domen": 120000, "posodobljeno": 1760781600, "pravil": 208337, "rezerv": 3, "nesifrirano": True,
              "zadnje": [], "izjeme": [], "premor": 0, "naprej": "cloudflare", "naprejPoMeri": "", "twitchOglasi": True}

    def _js(self, pogled, koda):
        GLib = self.GLib
        zanka = GLib.MainLoop()
        izid = {}

        def konec(p, r, *_):
            try:
                izid["v"] = p.evaluate_javascript_finish(r).to_string()
            except Exception as e:  # noqa: BLE001
                izid["v"] = "napaka: %s" % e
            zanka.quit()
        pogled.evaluate_javascript(koda, -1, None, None, None, konec)
        GLib.timeout_add_seconds(10, zanka.quit)
        zanka.run()
        return izid.get("v")

    def test_okno_scita(self):
        WebKit, GLib = self.WebKit, self.GLib
        odgovori = {"zacetek": {"jezik": "sl", "ime": "", "racunalnik": "", "sistem": ""}, "scit": self.STANJE,
                    "scitStatistika": {"scit": self.STANJE, "splet": {"oglasi": 7, "groznje": 1},
                                       "pravila": {"verzija": 202610181200, "vir": "podpisana", "pravil": 171}},
                    "mediaSpScit": {"scit": True}}
        most = ("window.__klici = []; var O = %s; window.SafeerOS = { klic: function (m, a) { window.__klici.push(m);"
                " return m in O ? Promise.resolve(JSON.parse(JSON.stringify(O[m]))) : Promise.reject('ni'); } };"
                % json.dumps(odgovori))
        ucm = WebKit.UserContentManager()
        ucm.add_script(WebKit.UserScript(most, WebKit.UserContentInjectedFrames.TOP_FRAME,
                                         WebKit.UserScriptInjectionTime.START, None, None))
        pogled = WebKit.WebView(user_content_manager=ucm)
        pogled.get_settings().set_property("allow-file-access-from-file-urls", True)
        okno = self.Gtk.Window()
        okno.set_child(pogled)
        okno.set_default_size(1100, 800)
        okno.present()
        zanka = GLib.MainLoop()
        pogled.connect("load-changed", lambda _p, d: d == WebKit.LoadEvent.FINISHED and GLib.timeout_add(2500, zanka.quit))
        pogled.load_uri("file://" + os.path.join(KOREN, "assets", "os", "index.html") + "?razdelek=scit&jezik=sl")
        GLib.timeout_add_seconds(30, zanka.quit)
        zanka.run()
        try:
            st = json.loads(self._js(pogled, """JSON.stringify({
                naslov: document.title,
                vMestu: document.getElementById('scitMesto').contains(document.getElementById('blokScit')),
                blokov: document.querySelectorAll('#blokScit').length,
                viden: document.getElementById('r-scit').classList.contains('viden'),
                statistika: document.getElementById('scitStatistika').innerText,
                nesifrirano: (document.querySelector('#blokScit .scit-nesifrirano') || {}).textContent || '',
                stikalo: (document.querySelector('#blokScit button.stikalo') || {}).tagName || '',
                klici: window.__klici})"""))
            self.assertEqual(st["naslov"], "Safeer Ščit")
            self.assertTrue(st["viden"])
            self.assertTrue(st["vMestu"])
            self.assertEqual(st["blokov"], 1)                         # en blok nastavitev, ne kopija
            self.assertIn("scitStatistika", st["klici"])
            for del_ in ("5 blokiranih od 50", "8 blokiranih", "171 pravil", "podpisan seznam s safeer.si", "208337"):
                self.assertIn(del_, st["statistika"])
            self.assertIn("nešifrirano", st["nesifrirano"])         # mirna vrstica, ne okno
            self.assertEqual(st["stikalo"], "BUTTON")                 # tipkovnica: pravi gumb
            # Sprememba drugje (dogodek »scit«): okno pokaze isto stanje takoj.
            novo = dict(self.STANJE, nesifrirano=False)
            self._js(pogled, "window.safeerOsDogodek('scit', %s); 'ok'" % json.dumps(novo))
            self.assertEqual(self._js(pogled, "String(!!document.querySelector('#blokScit .scit-nesifrirano'))"), "false")
        finally:
            okno.destroy()


if __name__ == "__main__":
    unittest.main()
