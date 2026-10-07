"""Splet v Safeer OS: če se WebKitov peskovnik ne more zagnati, lupina ne sme pasti.

WebKitGTK ob prvem pogledu s peskovnikom zažene bubblewrap. Kjer jedro ne dovoli uporabniških imenskih prostorov
(zabojniki, nekatera utrjena jedra), WebKit ubije CEL proces (»Failed to fully launch dbus-proxy«). V živo, 7. 10. 2026,
preizkusni zabojnik: klik na Splet je podrl Safeer OS. Zato Safeer OS prej v ločenem procesu preveri, ali se
peskovnik da zagnati; če se ne, brskalnika ne ustvari in uporabniku pove, zakaj.
"""
import os
import subprocess
import types
import unittest
from unittest import mock

from core import os_splet

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class PeskovnikDela(unittest.TestCase):
    def _preveri(self, flatpak=False, bwrap="/usr/bin/bwrap", posrednik="/usr/bin/xdg-dbus-proxy", koda=0, izjema=None,
                 okolje=None):
        klici = []

        def zazeni(ukaz, **moznosti):
            klici.append((list(ukaz), moznosti))
            if izjema is not None:
                raise izjema
            return types.SimpleNamespace(returncode=koda)

        izid = os_splet.peskovnik_dela(
            zazeni=zazeni,
            kje=lambda ime: {"bwrap": bwrap, "xdg-dbus-proxy": posrednik}.get(ime),
            obstaja=lambda pot: flatpak and pot == "/.flatpak-info",
            okolje=okolje or {})
        return izid, klici

    def test_dela(self):
        izid, klici = self._preveri()
        self.assertTrue(izid)
        self.assertEqual(len(klici), 1)
        ukaz, moznosti = klici[0]
        self.assertEqual(ukaz[0], "/usr/bin/bwrap")
        self.assertIn("--unshare-all", ukaz)            # prav ustvarjanje imenskih prostorov je tisto, kar odpove
        self.assertLessEqual(moznosti.get("timeout", 999), 10)

    def test_ne_dela(self):
        self.assertFalse(self._preveri(koda=1)[0])                                   # »No permissions to create new namespace«
        self.assertFalse(self._preveri(izjema=subprocess.TimeoutExpired("bwrap", 8))[0])
        self.assertFalse(self._preveri(izjema=OSError("ni dovoljeno"))[0])
        izid, klici = self._preveri(bwrap=None)
        self.assertFalse(izid)
        self.assertEqual(klici, [])
        self.assertFalse(self._preveri(posrednik=None)[0])

    def test_flatpak_in_izklopljen_peskovnik_ne_preverjata(self):
        # V Flatpaku WebKit uporabi flatpak-spawn; z WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1 peskovnika sploh ne zazene.
        for moznosti in ({"flatpak": True, "bwrap": None}, {"okolje": {"WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS": "1"}, "bwrap": None}):
            izid, klici = self._preveri(**moznosti)
            self.assertTrue(izid, moznosti)
            self.assertEqual(klici, [])


class Lupina(unittest.TestCase):
    def setUp(self):
        import safeer_os
        self.os_ = safeer_os

    def _lazna(self):
        lazna = mock.MagicMock()
        lazna._spletni = None
        lazna._peskovnik_dela = None
        lazna._peskovnik_na_voljo = lambda: self.os_.SafeerOS._peskovnik_na_voljo(lazna)
        lazna._ustvari_spletni = lambda: self.os_.SafeerOS._ustvari_spletni(lazna)
        lazna._pokazi_spletni_nacin = lambda: self.os_.SafeerOS._pokazi_spletni_nacin(lazna)
        return lazna

    def test_brez_peskovnika_ni_brskalnika_in_ni_padca(self):
        lazna = self._lazna()
        with mock.patch.object(os_splet, "peskovnik_dela", return_value=False) as preverba, \
                mock.patch.object(os_splet, "VdelaniSplet") as brskalnik:
            self.assertFalse(self.os_.SafeerOS._splet(lazna, "https://example.org/"))
            self.assertFalse(self.os_.SafeerOS._razdelek(lazna, "splet"))
            self.assertFalse(self.os_.SafeerOS._splet(lazna, ""))
        brskalnik.assert_not_called()
        self.assertIsNone(lazna._spletni)
        self.assertEqual(preverba.call_count, 1, "preverba tece enkrat na zagon")
        lazna._dogodek.assert_called_with("spletBrezPeskovnika", True)      # uporabnik izve, zakaj
        lazna.pogled.evaluate_javascript.assert_not_called()                 # lupina ostane v svojem razdelku

    def test_s_peskovnikom_se_brskalnik_ustvari(self):
        lazna = self._lazna()
        with mock.patch.object(os_splet, "peskovnik_dela", return_value=True), \
                mock.patch.object(os_splet, "VdelaniSplet") as brskalnik:
            self.assertTrue(self.os_.SafeerOS._ustvari_spletni(lazna))
            self.assertTrue(self.os_.SafeerOS._ustvari_spletni(lazna))       # drugic: ze obstaja
        brskalnik.assert_called_once()
        self.assertIs(lazna._spletni, brskalnik.return_value)
        lazna._dogodek.assert_not_called()

    def test_po_prvem_prikazu_izris(self):
        # V zivo (zabojnik, 7. 10. 2026): ob prvem odpiranju brskalnika iz drugega razdelka je del orodne vrstice ostal
        # neizrisan (ostanki lupine) do spremembe velikosti okna. Po prikazu zato izrecno izrisemo okno.
        s = beri("safeer_os.py")
        prikaz = s[s.index("    def _pokazi_spletni_nacin(self)"):s.index("    def _izrisi_okno(self)")]
        self.assertIn("GLib.timeout_add(60, self._izrisi_okno)", prikaz)
        lazna = mock.MagicMock()
        self.assertFalse(self.os_.SafeerOS._izrisi_okno(lazna))      # casovnik se ne ponavlja
        lazna.okno.queue_draw.assert_called_once()

    def test_stran_pove_zakaj(self):
        self.assertIn('if (vrsta === "spletBrezPeskovnika") obvesti(t("spletBrezPeskovnika"));', beri("assets", "os", "os.js"))
        besedila = beri("assets", "os", "besedila.js")
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            self.assertRegex(besedila, r'Object\.assign\(BESEDILA_OS\.%s, \{[^\n]*"spletBrezPeskovnika": "[^"]{20,}"' % jezik, jezik)


class MedijskiPogled(unittest.TestCase):
    """Tudi lahki medijski pogled (vdelana stran, vgradni predvajalnik skladbe s seznama) je WebKit s peskovnikom. Brez
    preverbe bi Safeer OS na sistemu brez peskovnika padel ob predvajanju, čeprav uporabnik Spleta nikoli ne odpre
    (drugi neodvisni pregled, 7. 10. 2026)."""

    def setUp(self):
        import safeer_os
        self.os_ = safeer_os

    def _lazna(self):
        lazna = mock.MagicMock()
        lazna._medijski_pogled = None
        lazna._spletni = None
        lazna._peskovnik_dela = None
        lazna._peskovnik_na_voljo = lambda: self.os_.SafeerOS._peskovnik_na_voljo(lazna)
        lazna._ustvari_medijski_pogled = lambda: self.os_.SafeerOS._ustvari_medijski_pogled(lazna)
        lazna._ustvari_spletni = lambda: self.os_.SafeerOS._ustvari_spletni(lazna)
        return lazna

    def test_brez_peskovnika_ni_pogleda_in_ni_padca(self):
        lazna = self._lazna()
        with mock.patch.object(os_splet, "peskovnik_dela", return_value=False) as preverba, \
                mock.patch.object(self.os_, "WebKit2") as webkit, mock.patch.object(self.os_, "Gtk"), \
                mock.patch.object(self.os_.os_katalog, "je_naslov_vgradnje", return_value=True):
            self.assertFalse(self.os_.SafeerOS._odpri_lahki_medijski_pogled(lazna, "https://example.org/video"))
            self.assertFalse(self.os_.SafeerOS._katalog_youtube(lazna, "https://example.org/embed/x", "Skladba"))
        webkit.WebView.assert_not_called()
        webkit.WebContext.new_ephemeral.assert_not_called()
        self.assertIsNone(lazna._medijski_pogled)
        self.assertEqual(preverba.call_count, 1, "preverba tece enkrat na zagon")
        lazna._dogodek.assert_called_with("medijBrezPeskovnika", True)      # uporabnik izve, zakaj
        lazna._ustavi_neposredni_medij.assert_not_called()                  # kar ze igra, igra naprej

    def test_preverba_je_skupna_s_spletom(self):
        lazna = self._lazna()
        with mock.patch.object(os_splet, "peskovnik_dela", return_value=False) as preverba, \
                mock.patch.object(os_splet, "VdelaniSplet") as brskalnik, mock.patch.object(self.os_, "WebKit2") as webkit, \
                mock.patch.object(self.os_, "Gtk"):
            self.assertFalse(self.os_.SafeerOS._ustvari_spletni(lazna))
            self.assertFalse(self.os_.SafeerOS._ustvari_medijski_pogled(lazna))
        self.assertEqual(preverba.call_count, 1)
        brskalnik.assert_not_called()
        webkit.WebView.assert_not_called()

    def test_s_peskovnikom_se_pogled_ustvari(self):
        lazna = self._lazna()
        with mock.patch.object(os_splet, "peskovnik_dela", return_value=True), \
                mock.patch.object(self.os_, "WebKit2") as webkit, mock.patch.object(self.os_, "Gtk"):
            self.assertTrue(self.os_.SafeerOS._ustvari_medijski_pogled(lazna))
            self.assertTrue(self.os_.SafeerOS._ustvari_medijski_pogled(lazna))      # drugic: ze obstaja
        webkit.WebView.assert_called_once()
        self.assertIs(lazna._medijski_pogled, webkit.WebView.return_value)
        lazna._dogodek.assert_not_called()

    def test_stran_pove_zakaj(self):
        self.assertIn('if (vrsta === "medijBrezPeskovnika") obvesti(t("medijBrezPeskovnika"));', beri("assets", "os", "os.js"))
        besedila = beri("assets", "os", "besedila.js")
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            self.assertRegex(besedila, r'Object\.assign\(BESEDILA_OS\.%s, \{[^\n]*"medijBrezPeskovnika": "[^"]{20,}"' % jezik, jezik)


if __name__ == "__main__":
    unittest.main()
