"""Ozadje pogleda WebKit: spletna stran brez svojega ozadja mora biti berljiva.

WebKit ozadje pogleda nariše pod stranjo, ki svojega ozadja ne določi. Brskalnika (vgrajeni v Safeer OS in Safeer
Browser) pogledu nastavita temno ozadje, da se ob odpiranju ne zabliska belo. Stran brez svojega ozadja (navaden
HTML, besedilna datoteka, tudi WebKitova stran »strani ni mogoče naložiti«) je bila zato temna s črnim besedilom -
neberljiva. V živo, 7. 10. 2026, preizkusni zabojnik: stran z enim odstavkom se v vgrajenem brskalniku ni videla.
Pravilo: temno samo pod našimi stranmi (začetna stran iz mape ui), pod spletom belo, kot privzame vsak brskalnik.
"""
import os
import tempfile
import unittest
from unittest import mock

from core import ozadje_strani

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class Pogled:
    """Lažni pogled: beleži nastavljene barve; atribute si zapomni kot pravi ovoj GObject."""

    def __init__(self, naslov=""):
        self.get_uri = mock.MagicMock(return_value=naslov)
        self.set_background_color = mock.MagicMock()
        self.connect = mock.MagicMock()


def barve(Gdk):
    """Zaporedje barv, ki so bile razčlenjene za nastavitev (Gdk.RGBA().parse)."""
    return [k.args[0] for k in Gdk.RGBA.return_value.parse.call_args_list]


class Barva(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="ozadje-")
        self.ui = os.path.join(self.mapa, "ui")
        os.makedirs(self.ui)
        self.addCleanup(lambda: __import__("shutil").rmtree(self.mapa, ignore_errors=True))

    def barva(self, naslov):
        return ozadje_strani.barva(naslov, self.ui, "#0a141c")

    def test_splet_je_bel(self):
        for naslov in ("http://example.org/", "https://example.org/a?b=c", "http://127.0.0.1:8765/druga.html",
                       "file:///etc/hostname", "file://" + self.mapa + "/drugje/stran.html",
                       "data:text/html,<p>a</p>", "view-source:https://example.org/", "ftp://example.org/"):
            self.assertEqual(self.barva(naslov), ozadje_strani.BELO, naslov)

    def test_nase_strani_ostanejo_temne(self):
        for naslov in ("", None, "about:blank", "file://" + self.ui + "/splet.html",
                       "file://" + self.ui + "/home.html?q=1#x", "file://" + self.ui + "/pod/mapa.html"):
            self.assertEqual(self.barva(naslov), "#0a141c", naslov)

    def test_pot_z_dvema_pikama_ne_velja_za_naso(self):
        self.assertEqual(self.barva("file://" + self.ui + "/../drugje.html"), ozadje_strani.BELO)
        self.assertEqual(self.barva("file://" + self.ui + "-ponaredek/stran.html"), ozadje_strani.BELO)

    def test_uskladi_nastavi_barvo_pogleda(self):
        Gdk, pogled = mock.MagicMock(), Pogled()
        pogled.get_uri.return_value = "https://example.org/"
        self.assertEqual(ozadje_strani.uskladi(Gdk, pogled, self.ui, "#0a141c"), ozadje_strani.BELO)
        Gdk.RGBA.return_value.parse.assert_called_once_with(ozadje_strani.BELO)
        pogled.set_background_color.assert_called_once_with(Gdk.RGBA.return_value)

    def test_uskladi_ne_podre_nalaganja(self):
        Gdk, pogled = mock.MagicMock(), mock.MagicMock()
        pogled.get_uri.side_effect = RuntimeError("pogled je ze unicen")
        self.assertEqual(ozadje_strani.uskladi(Gdk, pogled, self.ui, "#0a141c"), "")


class Zgodaj(unittest.TestCase):
    """Belo mora biti nastavljeno, PREDEN dokument spletne strani nastane, in pozneje ne znova.

    Izmerjeno 7. 10. 2026 (WebKitGTK 2.52.6, preizkusni zabojnik): stran z `color-scheme: dark` brez svojega ozadja dobi od
    WebKita temno osnovo in belo besedilo - razen če ji belo ozadje pogleda nastavimo, ko dokument že obstaja (ob
    LoadEvent.COMMITTED): takrat je bila bela z belim besedilom. Belo, nastavljeno ob odločanju o navigaciji ali ob
    LoadEvent.STARTED, WebKit ob temni shemi sam zamenja.
    """
    UI = "/opt/safeer/ui"
    TEMNA = "#0a141c"

    def _prikljucen(self, naslov=""):
        Gdk, WebKit2, pogled = mock.MagicMock(), mock.MagicMock(), Pogled(naslov)
        ozadje_strani.prikljuci(Gdk, WebKit2, pogled, self.UI, self.TEMNA)
        poslusalci = {k.args[0]: k.args[1] for k in pogled.connect.call_args_list}
        return Gdk, WebKit2, pogled, poslusalci

    def test_ob_nastanku_temno(self):
        Gdk, _W, pogled, poslusalci = self._prikljucen()
        self.assertEqual(barve(Gdk), [self.TEMNA])                 # brez belega bliska pod našo začetno stranjo
        self.assertEqual(set(poslusalci), {"decide-policy", "load-changed"})

    def test_splet_belo_ze_ob_odlocanju_in_samo_enkrat(self):
        Gdk, W, pogled, poslusalci = self._prikljucen("file://" + self.UI + "/home.html")
        odlocitev = mock.MagicMock()
        odlocitev.get_navigation_action.return_value.get_request.return_value.get_uri.return_value = "https://example.org/"
        self.assertFalse(poslusalci["decide-policy"](pogled, odlocitev, W.PolicyDecisionType.NAVIGATION_ACTION),
                         "odločitve ne sprejme - drugi poslušalci pridejo na vrsto")
        self.assertEqual(barve(Gdk), [self.TEMNA, ozadje_strani.BELO])
        odlocitev.use.assert_not_called()
        odlocitev.ignore.assert_not_called()
        # Nalaganje iste strani: STARTED in COMMITTED barve NE nastavita znova (to je povozilo temno osnovo strani).
        pogled.get_uri.return_value = "https://example.org/"
        poslusalci["load-changed"](pogled, W.LoadEvent.STARTED)
        poslusalci["load-changed"](pogled, W.LoadEvent.COMMITTED)
        poslusalci["load-changed"](pogled, W.LoadEvent.FINISHED)
        self.assertEqual(barve(Gdk), [self.TEMNA, ozadje_strani.BELO])
        self.assertEqual(pogled.set_background_color.call_count, 2)
        # Naslednja spletna stran: nič.
        odlocitev.get_navigation_action.return_value.get_request.return_value.get_uri.return_value = "https://drugje.example/"
        poslusalci["decide-policy"](pogled, odlocitev, W.PolicyDecisionType.NAVIGATION_ACTION)
        pogled.get_uri.return_value = "https://drugje.example/"
        poslusalci["load-changed"](pogled, W.LoadEvent.STARTED)
        poslusalci["load-changed"](pogled, W.LoadEvent.COMMITTED)
        self.assertEqual(pogled.set_background_color.call_count, 2)

    def test_brez_odlocanja_poskrbi_zacetek_nalaganja(self):
        # Nalaganje, ki ne gre skozi našega poslušalca odločanja: belo ob STARTED (še vedno pred dokumentom).
        Gdk, W, pogled, poslusalci = self._prikljucen("https://example.org/")
        poslusalci["load-changed"](pogled, W.LoadEvent.STARTED)
        self.assertEqual(barve(Gdk), [self.TEMNA, ozadje_strani.BELO])
        poslusalci["load-changed"](pogled, W.LoadEvent.COMMITTED)
        self.assertEqual(pogled.set_background_color.call_count, 2)

    def test_nasa_stran_temno_sele_ko_je_prikazana(self):
        Gdk, W, pogled, poslusalci = self._prikljucen("https://example.org/")
        poslusalci["load-changed"](pogled, W.LoadEvent.STARTED)                     # na spletu: belo
        odlocitev = mock.MagicMock()
        odlocitev.get_navigation_action.return_value.get_request.return_value.get_uri.return_value = "file://" + self.UI + "/home.html"
        poslusalci["decide-policy"](pogled, odlocitev, W.PolicyDecisionType.NAVIGATION_ACTION)
        pogled.get_uri.return_value = "file://" + self.UI + "/home.html"
        poslusalci["load-changed"](pogled, W.LoadEvent.STARTED)
        # Navigacija se lahko še prekliče: spletna stran brez ozadja, ki je še na zaslonu, ne sme potemneti.
        self.assertEqual(barve(Gdk), [self.TEMNA, ozadje_strani.BELO])
        poslusalci["load-changed"](pogled, W.LoadEvent.COMMITTED)
        self.assertEqual(barve(Gdk), [self.TEMNA, ozadje_strani.BELO, self.TEMNA])

    def test_druge_odlocitve_in_napake_ne_motijo(self):
        Gdk, W, pogled, poslusalci = self._prikljucen("file://" + self.UI + "/home.html")
        odlocitev = mock.MagicMock()
        odlocitev.get_navigation_action.return_value.get_request.return_value.get_uri.return_value = "https://example.org/"
        self.assertFalse(poslusalci["decide-policy"](pogled, odlocitev, W.PolicyDecisionType.RESPONSE))
        self.assertFalse(poslusalci["decide-policy"](pogled, odlocitev, W.PolicyDecisionType.NEW_WINDOW_ACTION))
        self.assertEqual(barve(Gdk), [self.TEMNA])
        odlocitev.get_navigation_action.side_effect = RuntimeError("ni dejanja")
        self.assertFalse(poslusalci["decide-policy"](pogled, odlocitev, W.PolicyDecisionType.NAVIGATION_ACTION))
        pogled.get_uri.side_effect = RuntimeError("pogled je že uničen")
        poslusalci["load-changed"](pogled, W.LoadEvent.STARTED)
        poslusalci["load-changed"](pogled, W.LoadEvent.COMMITTED)
        self.assertEqual(barve(Gdk), [self.TEMNA])

    def test_zasilna_pot_ob_prikazu(self):
        # Če zgodnja nastavitev ni tekla (pogled brez priklopa), COMMITTED še vedno poskrbi za navadno stran brez ozadja.
        Gdk, pogled = mock.MagicMock(), Pogled("https://example.org/")
        self.assertEqual(ozadje_strani.uskladi(Gdk, pogled, self.UI, self.TEMNA), ozadje_strani.BELO)
        self.assertEqual(ozadje_strani.uskladi(Gdk, pogled, self.UI, self.TEMNA), ozadje_strani.BELO)
        self.assertEqual(pogled.set_background_color.call_count, 1)


class Vgradnja(unittest.TestCase):
    def test_vgrajeni_brskalnik(self):
        s = beri("core", "os_splet.py")
        self.assertIn('ozadje_strani.prikljuci(self.Gdk, W, pogled, os.path.join(self.koren, "ui"), TEMNO_OZADJE)', s)
        # Naš poslušalec odločanja mora biti priklopljen pred poslušalcem brskalnika (ta odločitve sprejema).
        self.assertLess(s.index("ozadje_strani.prikljuci("), s.index('pogled.connect("decide-policy", self._politika)'))
        self.assertNotIn("ozadje_strani.uskladi(", s)

    def test_safeer_browser(self):
        s = beri("safeer_mint.py")
        self.assertIn('ozadje_strani.prikljuci(Gdk, WebKit2, webview, os.path.join(BASE_DIR, "ui"), TEMNO_OZADJE)', s)
        self.assertNotIn("ozadje_strani.uskladi(", s)
        # setup_webview_settings teče pred priklopom on_decide_policy (zavihki in stranska vrstica).
        nastavitev = s.index("        self.setup_webview_settings(wv)")
        self.assertLess(nastavitev, s.index('wv.connect("decide-policy", self.on_decide_policy)'))
        self.assertLess(s.index("self.setup_webview_settings(self.sidebar_webview)"),
                        s.index('self.sidebar_webview.connect("decide-policy", self.on_decide_policy)'))


if __name__ == "__main__":
    unittest.main()
