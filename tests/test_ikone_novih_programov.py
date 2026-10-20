"""Ikona programa, namescenega med delovanjem Safeer OS (testni PC 20. 10. 2026: Claude je imel v Programih prazno
ikono). GTK4 tema ikon novih ikon sama ne opazi (izmerjeno: has_icon ostane False tudi po 6 s); core/gostitelj
.osvezi_temo_ikon jo prisili v ponovno branje, NadzorProgramov to naredi pred vsakim obvestilom o spremembi programov.
Pravi GTK4 v podprocesu z lastnim XDG_DATA_HOME (preizkus ne spremeni racunalnika)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKRIPT = r'''
import os, sys
sys.path.insert(0, sys.argv[1])
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, GdkPixbuf
Gtk.init()
from core import gostitelj
mapa = os.path.join(os.environ["XDG_DATA_HOME"], "icons", "hicolor", "48x48", "apps")
os.makedirs(mapa, exist_ok=True)
tema = gostitelj.tema_ikon(Gtk)
ime = "safeer-preizkus-nova-ikona"
pred = tema.has_icon(ime)
GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 48, 48).savev(os.path.join(mapa, ime + ".png"), "png", [], [])
brez = tema.has_icon(ime)
osvezeno = gostitelj.osvezi_temo_ikon()
print(pred, brez, osvezeno, tema.has_icon(ime), bool(gostitelj.ikona_iz_teme(ime, 48)))
'''


class IkoneNovihProgramov(unittest.TestCase):
    def test_tema_po_osvezitvi_najde_novo_ikono(self):
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            self.skipTest("brez zaslona (xvfb-run)")
        tmp = tempfile.mkdtemp()
        try:
            okolje = dict(os.environ, XDG_DATA_HOME=os.path.join(tmp, "data"))
            r = subprocess.run([sys.executable, "-c", SKRIPT, KOREN], env=okolje, capture_output=True, text=True, timeout=60)
            if r.returncode != 0 and "Namespace Gtk not available" in r.stderr:
                self.skipTest("brez GTK4")
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            pred, brez, osvezeno, po, pot = r.stdout.split()
            self.assertEqual((pred, brez), ("False", "False"), "GTK4 brez osvezitve nove ikone ne vidi (zato popravek)")
            self.assertEqual((osvezeno, po, pot), ("True", "True", "True"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_nadzor_programov_osvezi_temo_pred_obvestilom(self):
        sys.path.insert(0, KOREN)
        from core import gostitelj, os_programi
        vrstni_red = []
        nadzor = os_programi.NadzorProgramov([], lambda: vrstni_red.append("programi"))
        with mock.patch.object(gostitelj, "osvezi_temo_ikon", side_effect=lambda: vrstni_red.append("ikone")):
            nadzor._poslji()
        self.assertEqual(vrstni_red, ["ikone", "programi"])


if __name__ == "__main__":
    unittest.main()
