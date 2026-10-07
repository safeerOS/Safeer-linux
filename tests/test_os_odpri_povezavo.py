"""Safeer OS: »Odpri povezavo« iz sporočila in klici v vgrajeni brskalnik.

Tretji neodvisni pregled pred izdajo (7. 10. 2026):
  - povezava z veliko začetnico v shemi (»Https://…«, tako pišejo telefonske tipkovnice) se je v meniju ponudila, klik pa
    ni naredil nič: stran je shemo preverjala brez razlike med velikimi in malimi črkami, gostitelj z razliko;
  - povezava iz sporočila se je odprla v TRENUTNEM zavihku vgrajenega brskalnika in zamenjala stran, ki jo je imel
    uporabnik tam odprto.
Kateri naslovi se v meniju sploh ponudijo (zavajajoči ne), preverja tests/test_os_kopiranje.py.
"""
import os
import types
import unittest
from unittest import mock

from core import os_splet

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class Lupina(unittest.TestCase):
    def setUp(self):
        import safeer_os
        self.os_ = safeer_os

    def _lazna(self):
        lazna = mock.MagicMock()
        lazna._pokazi_spletni_nacin.return_value = True
        lazna._spletni.odpri.return_value = True
        lazna._spletni.odpri_povezavo.return_value = True
        return lazna

    def test_velikost_crk_v_shemi_ni_pomembna(self):
        for naslov in ("Https://example.org/a", "HTTP://EXAMPLE.ORG", "https://example.org/"):
            lazna = self._lazna()
            self.assertTrue(self.os_.SafeerOS._splet(lazna, naslov), naslov)
            lazna._spletni.odpri.assert_called_once_with(naslov)

    def test_naslov_ki_se_ne_bo_odprl_ne_zozi_lupine(self):
        # Prej: lupina se je zožila v način Splet, šele nato je brskalnik naslov zavrnil.
        for naslov in ("javascript:alert(1)", "file:///etc/passwd", "ftp://example.org/", "https://", "http:///pot",
                       "example.org", "safeer://home"):
            lazna = self._lazna()
            self.assertFalse(self.os_.SafeerOS._splet(lazna, naslov), naslov)
            lazna._pokazi_spletni_nacin.assert_not_called()
            lazna._spletni.odpri.assert_not_called()
            lazna._spletni.odpri_povezavo.assert_not_called()

    def test_prazen_naslov_samo_pokaze_brskalnik(self):
        lazna = self._lazna()
        self.assertTrue(self.os_.SafeerOS._splet(lazna, ""))
        lazna._pokazi_spletni_nacin.assert_called_once_with()
        lazna._spletni.odpri.assert_not_called()

    def test_povezava_iz_sporocila_gre_v_nov_zavihek(self):
        lazna = self._lazna()
        self.assertTrue(self.os_.SafeerOS._splet(lazna, "https://example.org/", True))
        lazna._spletni.odpri_povezavo.assert_called_once_with("https://example.org/")
        lazna._spletni.odpri.assert_not_called()
        lazna = self._lazna()
        self.assertTrue(self.os_.SafeerOS._splet(lazna, "https://example.org/"))        # drugi klici: kot doslej
        lazna._spletni.odpri.assert_called_once_with("https://example.org/")
        lazna._spletni.odpri_povezavo.assert_not_called()

    def test_most_posreduje_nov_zavihek(self):
        self.assertIn('"splet": lambda: self._splet(str(a[0]) if a else "", len(a) > 1 and a[1] is True),',
                      beri("safeer_os.py"))


class Brskalnik(unittest.TestCase):
    """VdelaniSplet.odpri_povezavo: stran, ki jo ima uporabnik odprto, ostane."""

    def _brskalnik(self, uri, ima_zavihek=True):
        pogled = mock.Mock()
        pogled.get_uri.return_value = uri
        brskalnik = types.SimpleNamespace(koren=KOREN, trenutni=lambda: pogled if ima_zavihek else None,
                                          nov_zavihek=mock.Mock())
        return brskalnik, pogled

    def test_v_zavihku_z_zacetno_stranjo_se_odpre_tam(self):
        for uri in (None, "", "about:blank", "file://" + os.path.join(KOREN, "ui", "splet.html")):
            brskalnik, pogled = self._brskalnik(uri)
            self.assertTrue(os_splet.VdelaniSplet.odpri_povezavo(brskalnik, "https://example.org/x"), uri)
            pogled.load_uri.assert_called_once_with("https://example.org/x")
            brskalnik.nov_zavihek.assert_not_called()

    def test_odprta_stran_ostane(self):
        for uri in ("https://banka.example/obrazec", "http://192.0.2.1/", "file:///tmp/dokument.html"):
            brskalnik, pogled = self._brskalnik(uri)
            self.assertTrue(os_splet.VdelaniSplet.odpri_povezavo(brskalnik, "https://example.org/x"), uri)
            pogled.load_uri.assert_not_called()
            brskalnik.nov_zavihek.assert_called_once_with("https://example.org/x")

    def test_brez_zavihka_odpre_novega(self):
        brskalnik, pogled = self._brskalnik("", ima_zavihek=False)
        self.assertTrue(os_splet.VdelaniSplet.odpri_povezavo(brskalnik, "https://example.org/x"))
        brskalnik.nov_zavihek.assert_called_once_with("https://example.org/x")

    def test_neveljaven_naslov(self):
        for naslov in ("javascript:alert(1)", "file:///etc/passwd", "https://", ""):
            brskalnik, pogled = self._brskalnik("https://banka.example/")
            self.assertFalse(os_splet.VdelaniSplet.odpri_povezavo(brskalnik, naslov), naslov)
            pogled.load_uri.assert_not_called()
            brskalnik.nov_zavihek.assert_not_called()


if __name__ == "__main__":
    unittest.main()
