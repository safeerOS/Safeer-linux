"""Nastavitve DNS v Spletu in GTK4 Safeer Browserju (core/os_splet.py, pravo okno pod xvfb): Safeer Scit na vrhu, pet
ponudnikov, po meri, izklopljeno; streznik naprej za Scit; napacen naslov po meri okna ne zapre in nic ne shrani."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gdk, Gio, GLib, Gtk, WebKit  # noqa: E402

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Gtk.init()

from core import config as _config  # noqa: E402
from core import doh_proxy  # noqa: E402
from core.os_splet import VdelaniSplet  # noqa: E402


def _otroci(g):
    o = g.get_first_child()
    while o is not None:
        yield o
        yield from _otroci(o)
        o = o.get_next_sibling()


def _id_ji(combo):
    model = combo.get_model()
    return [model[i][1] for i in range(len(model))]


class NastavitveDNS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapa = tempfile.mkdtemp(prefix="safeer-dns-")
        cls.datoteka = os.path.join(cls.mapa, "settings.json")
        Path(cls.datoteka).write_text(json.dumps({"doh_provider": "disabled", "doh_enabled": False,
                                                  "first_run_completed": True}))
        with mock.patch.object(_config, "CONFIG_DIR", cls.mapa), mock.patch.object(_config, "CONFIG_FILE", cls.datoteka):
            cls.c = _config.ConfigManager()
        cls.splet = VdelaniSplet(Gtk, Gdk, Gio, GLib, WebKit, KOREN, lambda: "sl", None, prvi_zavihek=False, config=cls.c)

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
        combi = [g for g in _otroci(d) if isinstance(g, Gtk.ComboBoxText)]
        doh = next(c for c in combi if "opendns" in _id_ji(c) and "scit" in _id_ji(c))
        naprej = next(c for c in combi if "router" in _id_ji(c))
        vnosi = [g for g in _otroci(d) if isinstance(g, Gtk.Entry) and "192.168.1.2" in (g.get_placeholder_text() or "")]
        return d, doh, naprej, vnosi

    def _shrani(self, d):
        with mock.patch.object(doh_proxy, "get_doh_proxy", return_value=None):
            d.odgovor(Gtk.ResponseType.OK)

    def test_izbire_in_vrstni_red(self):
        d, doh, naprej, vnosi = self._odpri()
        self.assertEqual(_id_ji(doh), list(doh_proxy.IZBIRE_DNS))
        self.assertEqual(_id_ji(naprej), list(doh_proxy.IZBIRE_NAPREJ))
        self.assertEqual(doh.get_active_id(), "disabled")
        self.assertFalse(naprej.get_visible())
        doh.set_active_id("scit")
        self.assertTrue(naprej.get_visible())
        self.assertEqual(naprej.get_active_id(), "cloudflare")
        besedila = " ".join(g.get_text() for g in _otroci(d) if isinstance(g, Gtk.Label))
        self.assertIn("Cloudflare", besedila)       # pove, kdo vidi imena
        self.assertEqual(len(vnosi), 2)

    def test_napacen_naslov_ne_zapre_okna_pravilen_ip_se_shrani(self):
        d, doh, naprej, vnosi = self._odpri()
        doh.set_active_id("custom")
        vnosi[0].set_text("http://dns.example/dns-query")
        self._shrani(d)
        self.assertTrue(d.get_visible())
        self.assertEqual(json.loads(Path(self.datoteka).read_text())["doh_provider"], "disabled")
        besedila = [g.get_text() for g in _otroci(d) if isinstance(g, Gtk.Label)]
        self.assertTrue(any("https://" in b for b in besedila))
        vnosi[0].set_text("192.168.0.135")
        self._shrani(d)
        shranjeno = json.loads(Path(self.datoteka).read_text())
        self.assertEqual((shranjeno["doh_provider"], shranjeno["custom_doh_url"]), ("custom", "192.168.0.135"))
        self.assertTrue(shranjeno["doh_enabled"])
        self.assertTrue(shranjeno["dns_izbira_uporabnika"])

    def test_scit_z_usmerjevalnikom(self):
        d, doh, naprej, vnosi = self._odpri()
        doh.set_active_id("scit")
        naprej.set_active_id("router")
        self._shrani(d)
        shranjeno = json.loads(Path(self.datoteka).read_text())
        self.assertEqual((shranjeno["doh_provider"], shranjeno["scit_naprej"]), ("scit", "router"))


if __name__ == "__main__":
    unittest.main()
