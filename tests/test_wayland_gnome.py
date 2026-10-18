"""Safeer OS na GNOME (Ubuntu 24.04): dock = priljubljeni GNOME, plosce Nastavitev, ozadje, stikala, ki jih ni.

Brez zaslona (gsettings je lazen); zivo isto preverja tests/test_wayland_gnome_zivo.py."""

import os
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

KOREN = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN))

from core import os_dock, os_sistem  # noqa: E402

GNOME = {"XDG_CURRENT_DESKTOP": "ubuntu:GNOME", "XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"}
KDE_WAYLAND = {"XDG_CURRENT_DESKTOP": "KDE", "XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"}


class LazenGsettings:
    def __init__(self, priljubljeni):
        self.priljubljeni = list(priljubljeni)
        self.klici = []

    def __call__(self, argv, **_kw):
        self.klici.append(argv)
        if argv[:2] == ["gsettings", "get"] and argv[2:4] == ["org.gnome.shell", "favorite-apps"]:
            return subprocess.CompletedProcess(argv, 0, os_dock.zapisi_seznam(self.priljubljeni) + "\n", "")
        if argv[:2] == ["gsettings", "set"] and argv[2:4] == ["org.gnome.shell", "favorite-apps"]:
            self.priljubljeni = os_dock.razcleni_seznam(argv[4])
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 1, "", "ni")


class DockGnome(unittest.TestCase):
    def test_priljubljeni_so_dock(self):
        g = LazenGsettings(["a.desktop", "b.desktop"])
        with mock.patch.dict(os.environ, GNOME), mock.patch.object(os_dock.subprocess, "run", g), \
                mock.patch.object(os_dock, "_pot_po_id", lambda i: "/usr/share/applications/" + i), \
                mock.patch.object(os_dock.os.path, "isfile", lambda p: True):
            self.assertEqual(os_dock.vrsta_docka(), "gnome")
            self.assertTrue(os_dock.je_namescen())
            self.assertEqual([e["id"] for e in os_dock.elementi()], ["a.desktop", "b.desktop"])
            self.assertEqual(os_dock.dodaj("/usr/share/applications/c.desktop"), {"ok": True})
            self.assertEqual(g.priljubljeni, ["a.desktop", "b.desktop", "c.desktop"])
            self.assertEqual(os_dock.dodaj("/usr/share/applications/c.desktop"), {"ok": True, "ze": True})
            self.assertEqual(os_dock.razvrsti(["c.desktop", "x.desktop"]), {"ok": True})
            self.assertEqual(g.priljubljeni, ["c.desktop", "a.desktop", "b.desktop"])
            self.assertEqual(os_dock.odstrani("a.desktop"), {"ok": True})
            self.assertEqual(g.priljubljeni, ["c.desktop", "b.desktop"])
            self.assertEqual(os_dock.rob_docka(), ("", 0))      # Ubuntu Dock rezervira prostor sam
            self.assertFalse(any("plank" in " ".join(k) for k in g.klici), "na GNOME se Plank ne zaganja")

    def test_brez_docka_na_waylandu_brez_gnome(self):
        """KDE/sway na Waylandu: Plank (X11) ni dock - vmesnik »Prilagodi dock« skrije."""
        with mock.patch.dict(os.environ, KDE_WAYLAND), mock.patch.object(os_dock, "_plank_namescen", lambda: True):
            self.assertEqual(os_dock.vrsta_docka(), "")
            self.assertFalse(os_dock.je_namescen())

    def test_vmesnik_skrije_kar_ni(self):
        so = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
        self.assertIn('"plank": bool(vrsta), "vecNastavitev": vrsta == "plank"', so)
        ud = (KOREN / "assets" / "os" / "qml" / "UrediDock.qml").read_text(encoding="utf-8")
        self.assertIn("visible: okno.plank && okno.vecNastavitev && !okno.izbiram", ud)
        lupina = (KOREN / "core" / "os_lupina.py").read_text(encoding="utf-8")
        self.assertIn('"dock": os_dock.je_namescen()', lupina)
        js = (KOREN / "assets" / "os" / "os.js").read_text(encoding="utf-8")
        self.assertIn("S.zacetek.safeerCinnamon || S.zacetek.wayland", js)
        self.assertIn('"wayland": seja_prikaza.je_wayland()', so)


class NastavitveGnome(unittest.TestCase):
    def test_plosce_gnome_46(self):
        """Plosce iz gnome-<plosca>-panel.desktop (Ubuntu 24.04); vsak modul ima plosco ali odpre prvo stran."""
        sys.path.insert(0, str(KOREN))
        vir = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
        self.assertIn('"accessibility": "universal-access"', vir)
        self.assertIn('"backgrounds": "background"', vir)
        self.assertIn('elif which("gnome-control-center"):', vir)
        self.assertIn('"nastavitveOzadja": lambda: sistemske_nastavitve("backgrounds")', vir)
        ovoji = (KOREN / "packaging" / "flatpak_host_wrappers.sh").read_text(encoding="utf-8")
        self.assertIn("gnome-control-center", ovoji)
        mapa = pathlib.Path("/usr/share/applications")
        if (mapa / "gnome-background-panel.desktop").exists():
            import re
            plosce = set(re.findall(r'": "([a-z-]+)"', vir[vir.index("PLOSCE_GNOME = {"):vir.index("def sistemske_nastavitve")]))
            for p in plosce:
                self.assertTrue((mapa / ("gnome-%s-panel.desktop" % p)).exists(), p)

    def test_ozadje_gnome_temni_slog(self):
        odgovori = {
            ("org.cinnamon.desktop.background", "picture-uri"): None,
            ("org.gnome.desktop.interface", "color-scheme"): "'prefer-dark'",
            ("org.gnome.desktop.background", "picture-uri-dark"): "'file:///usr/share/backgrounds/temno.png'",
        }
        with mock.patch.object(os_sistem, "_zazeni", lambda u, *a, **k: odgovori.get(tuple(u[2:4]))), \
                mock.patch.object(os_sistem.os.path, "isfile", lambda p: p == "/usr/share/backgrounds/temno.png"):
            self.assertEqual(os_sistem.ozadje_namizja(), "/usr/share/backgrounds/temno.png")

    def test_nastavi_ozadje_gnome_oba_sloga(self):
        from core import os_lupina
        klici = []
        with mock.patch.dict(os.environ, GNOME), \
                mock.patch("core.gostitelj.v_flatpaku", lambda: True), \
                mock.patch.object(os_lupina.os.path, "exists", lambda p: True):
            self.assertTrue(os_lupina.nastavi_ozadje_sistema("/slika.png", zazeni=lambda a: klici.append(a) or True))
        self.assertEqual([k[2:4] for k in klici], [["org.gnome.desktop.background", "picture-uri"],
                                                   ["org.gnome.desktop.background", "picture-uri-dark"]])


if __name__ == "__main__":
    unittest.main()


class PonudbaNaWaylandu(unittest.TestCase):
    def test_ponudba_kot_obvestilo_z_gumboma(self):
        """»Poslji na napravo« na Waylandu: obvestilo namizja s Sprejmi/Zavrni namesto okna v kotu (okna na Waylandu ni
        mogoce postaviti v kot ne ga drzati nad drugimi)."""
        vir = (KOREN / "safeer_control.py").read_text(encoding="utf-8")
        i = vir.index("def _pokazi_ponudbo")
        telo = vir[i:vir.index("def _umakni_pasico")]
        self.assertIn("if seja_prikaza.je_wayland():", telo)
        self.assertIn('("sprejmi", besedilo(jezik, "sprejmi"), self.predaja_sprejmi)', telo)
        self.assertIn('("zavrni", besedilo(jezik, "zavrni"), self.predaja_zavrni)', telo)
        self.assertLess(telo.index("je_wayland"), telo.index("Gtk.Window("))
