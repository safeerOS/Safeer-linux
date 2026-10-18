"""HiDPI na Waylandu (brezglavi sway): delno merilo 1,5 in celo 2 - GTK4 in lupina QML risata v pravem merilu, okno
Safeer OS ne gre cez rob logicnega zaslona.

Izmerjeno 18. 10. 2026 (sway 1.9, Qt 6.11, GTK 4.14): merilo 1,5 -> GTK4 povrsina 1,5, QML okno devicePixelRatio 1,5
(os_lupina.pripravi: platforma wayland, PassThrough); z Round bi bilo 2,0 in sestavljalnik bi sliko pomanjsal."""

import os
import sys
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOREN, "tests"))

import wayland_okolje  # noqa: E402

GTK = r'''
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
def akt(a):
    w = Gtk.ApplicationWindow(application=a, title="merilo")
    w.set_child(Gtk.Label(label="Safeer"))
    w.present()
    def izpis():
        print("GTK", w.get_surface().get_scale(), flush=True)
        a.quit()
        return False
    GLib.timeout_add(1500, izpis)
a = Gtk.Application(application_id="org.safeer.Merilo")
a.connect("activate", akt)
a.run([])
'''

QML = r'''
import os, sys
sys.path.insert(0, os.getcwd())
from core import os_lupina
assert os_lupina.pripravi(["preizkus"])
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
v = QQuickView()
v.resize(400, 300)
v.show()
def izpis():
    print("QT", QGuiApplication.platformName(), v.devicePixelRatio(), flush=True)
    QGuiApplication.quit()
QTimer.singleShot(1500, izpis)
QGuiApplication.instance().exec()
'''


@unittest.skipUnless(wayland_okolje.na_voljo(), "brez sway")
class Merilo(unittest.TestCase):
    def test_delno_merilo_gtk_in_qml(self):
        with wayland_okolje.Sway(merilo=1.5) as s:
            s.zazeni([sys.executable, "-c", GTK]).wait(30)
            s.zazeni([sys.executable, "-c", QML]).wait(30)
            gtk, qml = s.dnevnik(0), s.dnevnik(1)
        self.assertIn("GTK 1.5", gtk, gtk[-800:])
        self.assertIn("QT wayland 1.5", qml, qml[-800:])

    def test_okno_ne_gre_cez_logicni_zaslon(self):
        """Merilo 2 (1920x1080 = 960x540 logicno): okno Safeer OS nativno (xdg_shell) in znotraj zaslona. sway okna
        razporedi sam; da minimum okna (960x620) na majhnem logicnem zaslonu ne potisne okna cez rob na GNOME, preverja
        tests/test_qml_aplikacija_v_oknu.py (os_lupina.najmanjsa_velikost)."""
        with wayland_okolje.Sway(merilo=2.0) as s:
            s.zazeni([sys.executable, "safeer_os.py", "--okno"])
            okno = s.pocakaj_okno("io.github.memelandfaner.SafeerOS", 60)
            time.sleep(2)
            izhod = s.izhodi()[0]["rect"]
        self.assertIsNotNone(okno)
        self.assertEqual(okno["shell"], "xdg_shell", "lupina QML tece nativno na Waylandu, ne prek XWaylanda")
        self.assertLessEqual(okno["rect"]["y"] + okno["rect"]["height"], izhod["height"])


if __name__ == "__main__":
    unittest.main()
