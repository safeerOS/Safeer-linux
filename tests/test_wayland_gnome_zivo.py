"""Zivi preizkus Safeer OS na brezglavem GNOME 46 (mutter, Wayland - kot Ubuntu 24.04), nastavitve v zacasnem dconf.

- Privzeti zagon odpre aplikacijo QML v oknu (namizja pod okni na Waylandu ni), ne prazne/crne povrsine.
- Dostopnost GNOME (vecje besedilo 125 %, visok kontrast, brez animacij) pride v namizje QML.
- Dock = priljubljeni GNOME (Ubuntu Dock): dodaj, razvrsti, odstrani.
- Ozadje: izbira v Safeer OS nastavi ozadje GNOME (svetli in temni slog), branje ga vrne.
Brez mutterja se preskoci. Izmerjeno 18. 10. 2026 (vsebnik Ubuntu 24.04, mutter 46.2)."""

import json
import os
import sys
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOREN, "tests"))

import wayland_okolje  # noqa: E402

NASTAVITVE = r'''
import json, os, sys
sys.path.insert(0, os.getcwd())
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
Gtk.init()
from core import os_dock, os_lupina, os_sistem
izid = {"dostopnost": os_lupina.dostopnost_sistema(), "dock": os_dock.vrsta_docka()}
nastavitve = "/usr/share/applications/org.gnome.Settings.desktop"
izid["dodaj"] = os_dock.dodaj(nastavitve)
izid["po_dodaj"] = [e["id"] for e in os_dock.elementi()]
izid["razvrsti"] = os_dock.razvrsti(["org.gnome.Settings.desktop"])
izid["po_razvrsti"] = os_dock.elementi()[0]["id"] if os_dock.elementi() else ""
izid["odstrani"] = os_dock.odstrani("org.gnome.Settings.desktop")
izid["po_odstrani"] = [e["id"] for e in os_dock.elementi()]
slika = sys.argv[1]
izid["ozadje_nastavi"] = os_lupina.nastavi_ozadje_sistema(slika)
izid["ozadje"] = os_sistem.ozadje_namizja()
print("IZID " + json.dumps(izid), flush=True)
'''


def _pika(pot, x, y):
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    pb = GdkPixbuf.Pixbuf.new_from_file(pot)
    p = pb.get_pixels()
    i = y * pb.get_rowstride() + x * pb.get_n_channels()
    return tuple(p[i:i + 3])


@unittest.skipUnless(wayland_okolje.gnome_na_voljo() and os.path.exists("/usr/share/applications/org.gnome.Settings.desktop"),
                     "brez mutterja ali Nastavitev GNOME")
class SafeerOsGnome(unittest.TestCase):
    def test_nastavitve_gnome(self):
        with wayland_okolje.Mutter() as m:
            m.gsettings("set", "org.gnome.desktop.interface", "text-scaling-factor", "1.25")
            m.gsettings("set", "org.gnome.desktop.a11y.interface", "high-contrast", "true")
            m.gsettings("set", "org.gnome.desktop.interface", "enable-animations", "false")
            m.gsettings("set", "org.gnome.shell", "favorite-apps", "['org.gnome.Nautilus.desktop']")
            slika = os.path.join(m.mapa, "ozadje.png")
            m.posnetek(slika)
            p = m.zazeni([sys.executable, "-c", NASTAVITVE, slika])
            p.wait(60)
            vrstica = next((v for v in m.dnevnik(0).splitlines() if v.startswith("IZID ")), "")
            self.assertTrue(vrstica, m.dnevnik(0)[-2000:])
            izid = json.loads(vrstica[5:])
            print(izid)
            self.assertEqual(izid["dostopnost"], {"tekstOdstotek": 125, "kontrast": True, "gibanje": False})
            self.assertEqual(izid["dock"], "gnome")
            self.assertTrue(izid["dodaj"]["ok"])
            self.assertIn("org.gnome.Settings.desktop", izid["po_dodaj"])
            self.assertEqual(izid["po_razvrsti"], "org.gnome.Settings.desktop")
            self.assertNotIn("org.gnome.Settings.desktop", izid["po_odstrani"])
            self.assertTrue(izid["ozadje_nastavi"])
            self.assertEqual(izid["ozadje"], slika)
            self.assertIn("ozadje.png", m.gsettings("get", "org.gnome.desktop.background", "picture-uri-dark"))

    def test_privzeti_zagon_je_okno(self):
        with wayland_okolje.Mutter() as m:
            m.zazeni([sys.executable, "safeer_os.py"])
            pot = os.path.join(m.mapa, "os.png")
            sredina = vogal = None
            konec = time.monotonic() + 40
            while time.monotonic() < konec:
                time.sleep(3)
                if m.posnetek(pot):
                    sredina, vogal = _pika(pot, 960, 540), _pika(pot, 5, 5)
                    # Okno Safeer OS (temne plosce iz tokens.css) na sredini, ozadje GNOME v kotu: okno ni cez ves zaslon.
                    if sredina != vogal and max(sredina) < 80:
                        break
            self.assertNotEqual(sredina, vogal, "okno ne pokrije vsega zaslona (ni celozaslonskega namizja)")
            self.assertLess(max(sredina), 80, "na sredini je temno namizje QML (paleta tokens.css)")
            self.assertIn("Safeer Control tece v procesu Safeer OS", m.dnevnik(0))


if __name__ == "__main__":
    unittest.main()
