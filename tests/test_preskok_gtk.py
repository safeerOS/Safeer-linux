"""Gumb »Preskoci uvod« v GTK predvajalniku Safeer OS (lastnik 13. 11. 2026): pravi Gtk.Button, lazni predvajalnik in
katalog. Preveri, da se gumb pokaze samo med odsekom in ob vklopljenem stikalu, da preskok skoci na konec odseka in da
gumb po 15 s izgine (OK/klik spet dela kot prej)."""
import types
import unittest
from unittest import mock

from core import preskok_odsekov as P


def _gtk():
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk
        return Gtk if Gtk.init_check() else None
    except Exception:  # noqa: BLE001
        return None


Gtk = _gtk()


@unittest.skipIf(Gtk is None, "ni GTK 4 ali zaslona (xvfb-run)")
class PreskokGtk(unittest.TestCase):
    def setUp(self):
        import safeer_os
        self.S = safeer_os.SafeerOS
        self.ukazi = []
        servis = types.SimpleNamespace(trenutna=types.SimpleNamespace(uri="https://tok.example/e2"),
                                       moznosti={"preskok_odsekov": True},
                                       podatki=lambda: {"trajanje": 2900.0})
        katalog = mock.MagicMock()
        katalog.vnos_predvajanega.return_value = {"kljuc": "tmdb:tv:1396:1:2"}
        self.l = types.SimpleNamespace(_medijski_preskok=Gtk.Button(), _medijski_predvajalnik=servis, _katalog=katalog,
                                       _mb=lambda k: k, _medijski_ukaz=lambda u, a: self.ukazi.append((u, a)))
        self.l._medijski_preskoci = lambda: self.S._medijski_preskoci(self.l)
        # Enako kot safeer_os pri gradnji okna predvajalnika (connect("clicked", ... _medijski_preskoci())).
        self.l._medijski_preskok.connect("clicked", lambda _g: self.l._medijski_preskoci())
        self.klici = []
        self.odseki = P.razcleni('{"intro":[{"start_ms":314551,"end_ms":331127}],"credits":[{"start_ms":2848149,"end_ms":null}]}')

    def _tik(self, pozicija, zdaj=100.0):
        def pridobi(url, izid):
            self.klici.append(url)
            izid(self.odseki)
            return True
        # Ura modula, ne time.monotonic (ta je skupen vsem nitim procesa).
        with mock.patch.object(P, "pridobi", pridobi), mock.patch("safeer_os.GLib.idle_add", lambda f: f()), \
                mock.patch.object(P, "ura", lambda: zdaj):
            self.S._medijski_preskok_osvezi(self.l, {"pozicija": pozicija, "trajanje": 2900.0, "zivo": False})

    def test_gumb_med_uvodom_in_preskok(self):
        self._tik(100)
        self.assertEqual(self.klici, ["https://api.theintrodb.org/v4/media?tmdb_id=1396&season=1&episode=2"])
        self.assertFalse(self.l._medijski_preskok.get_visible())
        self._tik(320)
        self.assertTrue(self.l._medijski_preskok.get_visible())
        self.assertEqual(self.l._medijski_preskok.get_label(), "preskoci_uvod")
        self.assertEqual(len(self.klici), 1, "ena poizvedba na posnetek")
        self.l._medijski_preskok.emit("clicked")
        self.assertEqual(self.ukazi, [("skok", 331.127)])
        self.assertFalse(self.l._medijski_preskok.get_visible())

    def test_odjavna_skoci_na_zadnjo_sekundo(self):
        self._tik(2860)
        self.assertEqual(self.l._medijski_preskok.get_label(), "preskoci_odjavna")
        self.l._medijski_preskok.emit("clicked")
        self.assertEqual(self.ukazi, [("skok", 2899.0)])

    def test_gumb_izgine_po_15_s(self):
        self._tik(320, zdaj=100.0)
        self.assertTrue(self.l._medijski_preskok.get_visible())
        self._tik(330, zdaj=116.0)
        self.assertFalse(self.l._medijski_preskok.get_visible())

    def test_izklopljeno_brez_poizvedbe_in_gumba(self):
        self.l._medijski_predvajalnik.moznosti = {"preskok_odsekov": False}
        self._tik(320)
        self.assertEqual(self.klici, [])
        self.assertFalse(self.l._medijski_preskok.get_visible())

    def test_v_zivo_brez_poizvedbe(self):
        def pridobi(url, izid):
            self.klici.append(url)
        with mock.patch.object(P, "pridobi", pridobi), mock.patch("safeer_os.GLib.idle_add", lambda f: f()):
            self.S._medijski_preskok_osvezi(self.l, {"pozicija": 10, "trajanje": 0, "zivo": True})
        self.assertEqual(self.klici, [])

    def test_brez_trajanja_ni_poizvedbe(self):
        """Tok v zivo dobi oznako »zivo« sele po nekaj sekundah - do takrat ga loci samo trajanje 0."""
        def pridobi(url, izid):
            self.klici.append(url)
            return True
        with mock.patch.object(P, "pridobi", pridobi), mock.patch("safeer_os.GLib.idle_add", lambda f: f()):
            self.S._medijski_preskok_osvezi(self.l, {"pozicija": 1, "trajanje": 0, "zivo": False})
        self.assertEqual(self.klici, [])

    def test_izklop_med_poizvedbo_zavrze_odgovor(self):
        cakajo = []

        def pridobi(url, izid):
            cakajo.append(izid)
            return True
        with mock.patch.object(P, "pridobi", pridobi), mock.patch("safeer_os.GLib.idle_add", lambda f: f()), \
                mock.patch.object(P, "ura", lambda: 100.0):
            self.S._medijski_preskok_osvezi(self.l, {"pozicija": 100, "trajanje": 2900.0, "zivo": False})
            self.l._medijski_predvajalnik.moznosti = {"preskok_odsekov": False}
            self.l._preskok_stanje = None                       # kot preklop v ploscici
            self.S._medijski_preskok_osvezi(self.l, {"pozicija": 101, "trajanje": 2900.0, "zivo": False})
            cakajo[0](self.odseki)                              # pozni odgovor prve poizvedbe
            self.S._medijski_preskok_osvezi(self.l, {"pozicija": 320, "trajanje": 2900.0, "zivo": False})
        self.assertFalse(self.l._medijski_preskok.get_visible())

    def test_gumb_starega_posnetka_ne_skoci_v_novega(self):
        self._tik(320)
        self.assertTrue(self.l._medijski_preskok.get_visible())
        self.l._medijski_predvajalnik.trenutna = types.SimpleNamespace(uri="https://tok.example/e3")
        self.l._medijski_preskok.emit("clicked")
        self.assertEqual(self.ukazi, [])
        self.assertFalse(self.l._medijski_preskok.get_visible())

    def test_preskocen_odsek_ne_pokaze_gumba_znova(self):
        self._tik(320)
        self.l._medijski_preskok.emit("clicked")
        self._tik(329)                                          # skok po kljucni slicici pristane malo pred koncem
        self.assertFalse(self.l._medijski_preskok.get_visible())
