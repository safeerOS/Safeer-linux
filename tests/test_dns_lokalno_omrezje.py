"""Stikalo »DNS v lokalnem omrezju« (doh_lokalno_omrezje, prej v GTK3 brskalniku) v nastavitvah Spleta - isto okno v
Safeer OS in GTK4 Safeer Browserju (core/os_splet.VdelaniSplet._nastavitve, pravo okno pod Xvfb).

Pomen (core/doh_proxy.je_dovoljen_cilj): ime, ki ga DNS prevede v naslov domacega omrezja (Pi-hole, usmerjevalnik, NAS),
se odpre; povratni in metapodatkovni naslovi ostanejo zavrnjeni. Privzeto izklopljeno (DNS rebinding)."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import Gdk, Gio, GLib, Gtk, WebKit
except (ImportError, ValueError):
    Gtk = WebKit = None

from core import doh_proxy
from core.i18n import TRANSLATIONS

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _otroci(g):
    o = g.get_first_child()
    while o is not None:
        yield o
        yield from _otroci(o)
        o = o.get_next_sibling()


def _id_ji(combo):
    model = combo.get_model()
    return [model[i][1] for i in range(len(model))]


class Pomen(unittest.TestCase):
    def test_privzeto_izklopljeno_in_v_vseh_jezikih(self):
        from core.config import DEFAULT_SETTINGS
        self.assertIs(DEFAULT_SETTINGS["doh_lokalno_omrezje"], False)
        for j in ("sl", "en", "de", "es", "fr", "it"):
            self.assertTrue(TRANSLATIONS[j].get("doh_lokalno_lbl"), j)

    def test_posrednik_dovoli_domace_naslove_samo_s_stikalom(self):
        self.assertFalse(doh_proxy.je_dovoljen_cilj("192.168.1.2"))
        self.assertTrue(doh_proxy.je_dovoljen_cilj("192.168.1.2", dovoli_lokalno=True))
        for naslov in ("127.0.0.1", "169.254.169.254", "::1"):     # povratni in metapodatki: nikoli
            self.assertFalse(doh_proxy.je_dovoljen_cilj(naslov, dovoli_lokalno=True), naslov)

    def test_brskalnik_uporabi_iste_nastavitve(self):
        with open(os.path.join(KOREN, "safeer_brskalnik.py"), encoding="utf-8") as f:
            self.assertIn("VdelaniSplet(Gtk, Gdk, Gio, GLib, WebKit2", f.read())


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(WebKit, "potrebuje WebKitGTK 6.0")
class StikaloVNastavitvah(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Gtk.init()
        from core import config as _config
        from core.os_splet import VdelaniSplet
        cls.mapa = tempfile.mkdtemp(prefix="safeer-dns-lokalno-")
        cls.datoteka = os.path.join(cls.mapa, "settings.json")
        Path(cls.datoteka).write_text(json.dumps({"doh_provider": "scit", "doh_enabled": True, "easylist_enabled": False,
                                                  "first_run_completed": True}))
        with mock.patch.object(_config, "CONFIG_DIR", cls.mapa), mock.patch.object(_config, "CONFIG_FILE", cls.datoteka):
            cls.c = _config.ConfigManager()
        with mock.patch.object(doh_proxy, "get_doh_proxy", return_value=None), \
                mock.patch("core.threat_intel.skupna", side_effect=RuntimeError("brez vira groženj v preizkusu")):
            cls.splet = VdelaniSplet(Gtk, Gdk, Gio, GLib, WebKit, KOREN, lambda: "sl", None, prvi_zavihek=False,
                                     config=cls.c)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.mapa, ignore_errors=True)

    def _odpri(self):
        ujeto = {}
        izvirni = self.splet._dialog

        def dialog(*a, **k):
            d, o = izvirni(*a, **k)
            ujeto["d"] = d
            return d, o
        with mock.patch.object(self.splet, "_dialog", dialog):
            self.splet._nastavitve()
        d = ujeto["d"]
        self.addCleanup(d.destroy)
        napis = TRANSLATIONS["sl"]["doh_lokalno_lbl"]
        stikalo = next(g for g in _otroci(d) if isinstance(g, Gtk.CheckButton) and g.get_label() == napis)
        doh = next(c for c in _otroci(d) if isinstance(c, Gtk.ComboBoxText) and "opendns" in _id_ji(c))
        return d, stikalo, doh

    def test_stikalo_se_shrani_in_pride_do_posrednika(self):
        d, stikalo, doh = self._odpri()
        self.assertFalse(stikalo.get_active())                     # privzeto izklopljeno
        self.assertTrue(stikalo.get_visible())
        doh.set_active_id("disabled")
        self.assertFalse(stikalo.get_visible())                    # brez sifriranega DNS ni posrednika, ki bi preverjal
        doh.set_active_id("scit")
        self.assertTrue(stikalo.get_visible())
        stikalo.set_active(True)
        klici = []
        with mock.patch.object(doh_proxy, "get_doh_proxy", side_effect=lambda **k: klici.append(k)):
            d.odgovor(Gtk.ResponseType.OK)
        self.assertIs(json.loads(Path(self.datoteka).read_text())["doh_lokalno_omrezje"], True)
        self.assertTrue(klici and klici[-1]["lokalno"] is True, klici)   # takoj velja (ze tekoci posrednik)
        d2, stikalo2, _doh = self._odpri()
        self.assertTrue(stikalo2.get_active())                     # okno pokaze shranjeno
        stikalo2.set_active(False)
        with mock.patch.object(doh_proxy, "get_doh_proxy", side_effect=lambda **k: klici.append(k)):
            d2.odgovor(Gtk.ResponseType.OK)
        self.assertIs(json.loads(Path(self.datoteka).read_text())["doh_lokalno_omrezje"], False)
        self.assertIs(klici[-1]["lokalno"], False)


if __name__ == "__main__":
    unittest.main()
