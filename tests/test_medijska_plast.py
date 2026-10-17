"""Vgrajeni spletni predvajalnik (YouTube s seznama, vdelana stran) v oknu Medijskega centra, ne v locenem oknu
(lastnik, 17. 10. 2026). Lazni Gtk brez prikaza: core/os_medijska_plast.py in metode safeer_os (izvlecene iz vira -
safeer_os je GTK 4 in ga ta skupina preizkusov ne sme uvoziti)."""
import ast
import os
import types
import unittest
from unittest import mock

from core import os_katalog, os_lupina, os_medijska_plast, os_media_besedila

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YT = os_katalog.PREDPONA_VGRADNJE


class _Gradnik:
    def __init__(self, *a, **kw):
        self.vidno, self.otroci, self.signali, self.lastnosti = True, [], {}, dict(kw)

    def set_visible(self, v):
        self.vidno = bool(v)

    def get_visible(self):
        return self.vidno

    def connect(self, ime, fn):
        self.signali[ime] = fn

    def append(self, otrok):
        self.otroci.append(otrok)

    def __getattr__(self, ime):          # set_hexpand, add_css_class, set_tooltip_text ... - brez ucinka
        if ime.startswith(("set_", "add_", "grab_")):
            return lambda *a, **kw: self.lastnosti.__setitem__(ime, a)
        raise AttributeError(ime)


class _Prekrivanje(_Gradnik):
    def add_overlay(self, g):
        self.otroci.append(g)

    def remove_overlay(self, g):
        self.otroci.remove(g)


class _Okno(_Gradnik):
    cel = False

    def fullscreen(self):
        self.cel = True

    def unfullscreen(self):
        self.cel = False

    def maximize(self):
        pass


def _novo_okno(*_a, **_kw):
    raise AssertionError("vgrajeni predvajalnik ne sme odpreti novega okna Gtk")


LAZNI_GTK = types.SimpleNamespace(
    Orientation=types.SimpleNamespace(VERTICAL=1, HORIZONTAL=0), Box=_Gradnik, Button=_Gradnik, Label=_Gradnik,
    Overlay=_Prekrivanje, ApplicationWindow=_novo_okno, Window=_novo_okno)


def _plast(nazaj=None):
    pogled = _Gradnik()
    return os_medijska_plast.MedijskaPlast(LAZNI_GTK, pogled, lambda k: os_media_besedila.besedilo(k, "sl"),
                                           nazaj or (lambda: None)), pogled


class Plast(unittest.TestCase):

    def test_pas_in_pogled_v_prekrivanju_okna(self):
        plast, pogled = _plast()
        okno, prek = _Okno(), _Prekrivanje()
        self.assertFalse(plast.je_vidna())
        plast.postavi(okno, prek)
        plast.pokazi("Skladba")
        self.assertEqual(prek.otroci, [plast.koren])
        self.assertEqual(plast.koren.otroci, [plast.pas, pogled])
        self.assertTrue(plast.je_vidna())
        self.assertEqual(plast.naslov.lastnosti["set_label"], ("Skladba",))
        self.assertIn("Medijski center", plast.nazaj.lastnosti["label"])

    def test_drugo_okno_plast_premakne(self):
        plast, _ = _plast()
        a, b = _Prekrivanje(), _Prekrivanje()
        plast.postavi(_Okno(), a)
        plast.postavi(_Okno(), b)
        self.assertEqual((a.otroci, b.otroci), ([], [plast.koren]))

    def test_nazaj_skrije_ne_ustavi(self):
        klici = []
        plast, _ = _plast(lambda: klici.append("nazaj"))
        plast.postavi(_Okno(), _Prekrivanje())
        plast.pokazi()
        plast.nazaj.signali["clicked"]()
        self.assertFalse(plast.je_vidna())
        self.assertEqual(klici, ["nazaj"])

    def test_esc_zapre_cel_zaslon_in_ne_ustavi(self):
        klici = []
        plast, _ = _plast(lambda: klici.append("nazaj"))
        okno = _Okno()
        plast.postavi(okno, _Prekrivanje())
        plast.pokazi()
        self.assertTrue(plast.tipka("F11"))
        self.assertTrue(okno.cel)
        self.assertFalse(plast.pas.vidno)              # cel zaslon: samo video
        self.assertTrue(plast.tipka("Escape"))
        self.assertFalse(okno.cel)
        self.assertTrue(plast.je_vidna())              # predvajalnik ostane
        self.assertEqual(klici, [])
        self.assertTrue(plast.tipka("Escape"))          # drugi Esc: nazaj v katalog (plast skrita, zvok igra)
        self.assertEqual(klici, ["nazaj"])
        self.assertFalse(plast.tipka("Escape"))         # skrita plast tipk ne jemlje strani

    def test_css_iz_tokenov(self):
        css = os_medijska_plast.css_pasu(os_lupina.tokeni())
        self.assertIn(".safeer-medijski-pas", css)
        self.assertEqual(os_medijska_plast.css_pasu({}), "")

    def test_prevodi(self):
        for j in ("sl", "en", "de", "es", "fr", "it"):
            for k in ("nazaj_medijski_center", "nazaj_medijski_center_namig", "celozaslonsko_f11"):
                self.assertIn(k, os_media_besedila.BESEDILA[j], (j, k))


def _metode(*imena):
    """Metode razreda SafeerOS iz vira (brez uvoza GTK 4)."""
    with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
        vir = f.read()
    drevo = ast.parse(vir)
    razred = next(n for n in drevo.body if isinstance(n, ast.ClassDef) and n.name == "SafeerOS")
    izid = {}
    for n in razred.body:
        if isinstance(n, ast.FunctionDef) and n.name in imena:
            izid[n.name] = n
    assert set(izid) == set(imena), set(imena) - set(izid)
    return izid


class YoutubeVIstemOknu(unittest.TestCase):
    """_katalog_youtube in _pokazi_medijsko_plast z laznim Gtk: brez novega okna, plast v oknu Safeer Playerja."""

    def setUp(self):
        imena = ("_katalog_youtube", "_pokazi_medijsko_plast", "_medijsko_okno_cilj", "_plast_tipka",
                 "_medijska_plast_nazaj", "_yt_ukaz")
        self.gdk = mock.MagicMock()
        self.gdk.keyval_name = lambda k: k
        imenski = {"os_katalog": os_katalog, "WebKit2": mock.MagicMock(), "GLib": mock.MagicMock(), "Gtk": LAZNI_GTK,
                   "Gdk": self.gdk, "json": __import__("json"), "Optional": __import__("typing").Optional,
                   "_v_ospredje": mock.MagicMock()}
        modul = ast.Module(body=list(_metode(*imena).values()), type_ignores=[])
        exec(compile(modul, "safeer_os.py", "exec"), imenski)       # noqa: S102 - lastna koda iz repozitorija
        self.v_ospredje = imenski["_v_ospredje"]
        L = type("Lazna", (), {i: imenski[i] for i in imena})
        self.l = L()
        l = self.l
        l.namizje = False
        l.okno, l.pogled = _Okno(), _Gradnik()
        l.okno_predvajalnik, l.pogled_predvajalnik = None, None
        l._prekrivanja = {id(l.pogled): _Prekrivanje()}
        l._katalog_pogled = None
        l._medijski_pogled = mock.MagicMock()
        l._medijska_plast, _ = _plast(lambda: l._medijska_plast_nazaj())      # kot v _ustvari_medijski_pogled
        l._medijski_rod = 0
        l._ustvari_medijski_pogled = lambda: True
        l._ustavi_neposredni_medij = mock.MagicMock()
        l._yt_prijava_v_medijski_pogled = mock.MagicMock()
        l._yt_spremenjeno = mock.MagicMock()
        l._pocisti_medijski_pogled = mock.MagicMock()
        l._katalog_youtube_ukaz = mock.MagicMock()
        l._dogodek = mock.MagicMock()
        l._mb = lambda k: os_media_besedila.besedilo(k, "sl")

        def odpri_predvajalnik(iskanje=""):
            l.okno_predvajalnik, l.pogled_predvajalnik = _Okno(), _Gradnik()
            l._prekrivanja[id(l.pogled_predvajalnik)] = _Prekrivanje()
            return True
        l._odpri_predvajalnik = mock.MagicMock(side_effect=odpri_predvajalnik)

    def test_prva_skladba_odpre_safeer_player_in_plast_v_njem(self):
        l = self.l
        self.assertTrue(l._katalog_youtube(YT + "dQw4w9WgXcQ", "Pesem"))
        l._odpri_predvajalnik.assert_called_once()
        self.assertIs(l._medijska_plast.okno, l.okno_predvajalnik)
        self.assertEqual(l._prekrivanja[id(l.pogled_predvajalnik)].otroci, [l._medijska_plast.koren])
        self.assertTrue(l._medijska_plast.je_vidna())
        self.v_ospredje.assert_called_with(l.okno_predvajalnik)

    def test_iz_glavnega_okna_ostane_v_glavnem(self):
        l = self.l
        l._katalog_pogled = l.pogled
        l._katalog_youtube(YT + "dQw4w9WgXcQ", "Pesem")
        l._odpri_predvajalnik.assert_not_called()
        self.assertIs(l._medijska_plast.okno, l.okno)

    def test_namizni_nacin_glavnega_okna_ne_uporabi(self):
        l = self.l
        l.namizje, l._katalog_pogled = True, l.pogled          # glavno okno je ozadje namizja
        l._katalog_youtube(YT + "dQw4w9WgXcQ", "Pesem")
        self.assertIs(l._medijska_plast.okno, l.okno_predvajalnik)

    def test_nazaj_glasba_igra_naprej_mini_predvajalnik_jo_vrne(self):
        l = self.l
        l._katalog_youtube(YT + "dQw4w9WgXcQ", "Pesem")
        l._medijski_skladba = True
        l._medijska_plast.nazaj_v_center()
        self.assertFalse(l._medijska_plast.je_vidna())
        l._pocisti_medijski_pogled.assert_not_called()           # zvok ne utihne
        l._yt_spremenjeno.assert_called()                         # mini predvajalnik pokaze skladbo
        # naslednja skladba plasti ne vrine pred katalog
        l._katalog_youtube(YT + "9bZkp7q19f0", "Druga")
        self.assertFalse(l._medijska_plast.je_vidna())
        # klik na mini predvajalnik (predvajalnikUkaz »odpri«) video spet pokaze
        self.assertTrue(l._yt_ukaz("odpri", {"stanje": "predvaja"}))
        self.assertTrue(l._medijska_plast.je_vidna())

    def test_nazaj_iz_vdelane_strani_ustavi(self):
        l = self.l
        l._medijski_skladba = False
        l._medijska_plast.postavi(l.okno, l._prekrivanja[id(l.pogled)])
        l._medijska_plast.nazaj_v_center()
        l._pocisti_medijski_pogled.assert_called_once()

    def test_tipke_samo_v_oknu_plasti(self):
        l = self.l
        l._katalog_pogled = l.pogled
        l._katalog_youtube(YT + "dQw4w9WgXcQ", "Pesem")
        dogodek = types.SimpleNamespace(keyval="Escape")
        self.assertFalse(l._plast_tipka(_Okno(), dogodek))
        self.assertTrue(l._plast_tipka(l.okno, dogodek))

    def test_v_viru_ni_okna_za_pogled(self):
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            vir = f.read()
        pogled = vir[vir.index("def _ustvari_medijski_pogled"):vir.index("def _katalog_youtube(")]
        self.assertNotIn("Gtk.ApplicationWindow(", pogled)
        self.assertNotIn("Gtk.Window(", pogled)
        self.assertIn("os_medijska_plast.MedijskaPlast(Gtk, pogled", pogled)
        self.assertNotIn("_medijski_okno", vir)
        # Piskotki YouTuba, skript skladbe in Scit (decide-policy) ostanejo na pogledu.
        self.assertIn("self._yt_prijava_v_medijski_pogled()", vir[vir.index("def _katalog_youtube("):])
        self.assertIn("os_katalog.SKRIPT_SKLADBE", pogled)
        self.assertIn('pogled.connect("decide-policy", self._medijski_odlocitev)', pogled)


if __name__ == "__main__":
    unittest.main()
