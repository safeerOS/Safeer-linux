"""Stranska plosca Safeer Browserja (GTK4, core/stranska_plosca.py): bere katalog spletnih klepetov iz nastavitev
(core/config.py »integrations«, ista kot Sporocila v Safeer OS), storitev odpre v vgrajenem pogledu Spleta (ista seja
in zascita), znacka neprebranih iz naslova strani. Brez omrezja: zaprt posrednik."""
import os
import tempfile
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOM = tempfile.mkdtemp(prefix="safeer-plosca-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_DOM, ".config")
os.environ["XDG_CACHE_HOME"] = os.path.join(_DOM, ".cache")

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gdk, Gio, GLib, Gtk, WebKit  # noqa: E402

Gtk.init()


def _cakaj(pogoj, cas=5.0):
    kontekst = GLib.MainContext.default()
    rok = time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.005)
    return pogoj()


class Plosca(unittest.TestCase):
    def test_katalog_vklop_odpri_znacka(self):
        from core import config as _config
        os.makedirs(_config.CONFIG_DIR, exist_ok=True)
        c = _config.ConfigManager()
        for k, v in (("doh_enabled", False), ("secure_proxy_mode", "custom"), ("secure_proxy_url", "http://127.0.0.1:9"),
                     ("easylist_enabled", False)):
            c.set(k, v)
        from core.os_splet import VdelaniSplet
        from core.stranska_plosca import StranskaPlosca
        splet = VdelaniSplet(Gtk, Gdk, Gio, GLib, WebKit, KOREN, lambda: "sl", None, prvi_zavihek=False, config=c)
        p = StranskaPlosca(Gtk, Gio, splet, lambda: "sl")
        integracije = p.integracije()
        self.assertIn("whatsapp", integracije, "katalog Sporocil je v stranski plosci")
        self.assertNotIn("remote_control", integracije, "samo spletne storitve (https)")
        self.assertEqual(p.gumbi, {}, "privzeto ni vklopljena nobena storitev")
        p.vklopi("whatsapp", True)
        self.assertIn("whatsapp", p.gumbi)
        p.preklopi("whatsapp")
        a = p.aplikacije["whatsapp"]
        self.assertIn(a.pogled, splet.aplikacije, "ista seja in zascita kot zavihki")
        self.assertTrue(p.razkrij.get_reveal_child())
        a.pogled.load_html("<title>(3) WhatsApp</title>", "https://web.whatsapp.com/")
        self.assertTrue(_cakaj(lambda: "3" in (p.gumbi["whatsapp"].get_label() or "")))
        p.preklopi("whatsapp")
        self.assertFalse(p.razkrij.get_reveal_child(), "drugi klik skrije plosco, storitev tece naprej")
        self.assertIn("whatsapp", p.aplikacije)
        p.vklopi("whatsapp", False)
        self.assertNotIn("whatsapp", p.aplikacije, "izklop storitev sprosti")
        self.assertFalse(c.get("integrations")["whatsapp"]["enabled"])


if __name__ == "__main__":
    unittest.main()
