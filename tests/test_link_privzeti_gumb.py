"""Okna Safeer Linka z gumbi: fokus ima varna izbira (pregled 18. 10. 2026, daljinec na televizorju).

Gtk.AlertDialog brez privzetega gumba da fokus PRVEMU gumbu (izmerjeno v Xvfb, GTK 4.14): v sporocilu s povezavo
(»Kopiraj«, »Odpri«, »V redu«) je en pritisk na V redu kopiral ali odprl povezavo. Zdaj ima fokus gumb, ki velja ob
Esc (varna izbira), razen ce klicatelj izrecno izbere drugega.
"""
import os
import unittest

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk
except (ImportError, ValueError):
    Gtk = None


def _fokus(gumbi, **kw):
    from core import safeer_link
    Gtk.init()
    pred = set(Gtk.Window.list_toplevels())
    safeer_link._vprasaj(None, "Naslov", "Besedilo", gumbi, **kw)
    ctx = GLib.MainContext.default()
    okno = None
    for _ in range(500):
        ctx.iteration(False)
        nova = [w for w in Gtk.Window.list_toplevels() if w not in pred]
        if nova and nova[0].get_focus() is not None:
            okno = nova[0]
            break
    if okno is None:
        return None
    gumb = okno.get_focus()
    oznaka = gumb.get_label() if hasattr(gumb, "get_label") else None
    okno.destroy()
    return oznaka


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(Gtk, "potrebuje GTK 4")
class PrivzetiGumb(unittest.TestCase):
    def test_sporocilo_s_povezavo(self):
        # Sporocilo z druge naprave (core/safeer_link._pokazi_besedilo): »Odpri« bi odprl tujo povezavo.
        self.assertEqual(_fokus(["Kopiraj", "Odpri", "V redu"]), "V redu")

    def test_namestitev_locenega_zaslona(self):
        # safeer_control.namesti_locen_zaslon: preklic je prvi gumb - fokus nanj, ne na »Namesti«.
        self.assertEqual(_fokus(["Prekliči", "Namesti"], preklic=0), "Prekliči")

    def test_izrecno_izbran(self):
        self.assertEqual(_fokus(["Ne", "Da"], preklic=0, privzeto=1), "Da")


if __name__ == "__main__":
    unittest.main()
