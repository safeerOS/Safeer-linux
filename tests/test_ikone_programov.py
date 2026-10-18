"""Ikone, ki jih uporabnik ne sme zamenjati (lastnik, 17. 10. 2026).

1. Mintove posodobitve v pultu: Papirus-Dark jih rise kot scit, uporabnik jih je imel za Safeer Scit. Safeer Cinnamon
   zato namesti temo Safeer-Papirus-Dark (packaging/tema-cinnamon/ikone, tools/ikone_posodobitev.py) s krozno puscico.
2. Safeer Browser in Safeer OS sta imela isto ikono (scit z »S«): brskalnik ima svojo (globus z »S«, assets/brskalnik.svg).
"""
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("ikone_posodobitev", os.path.join(KOREN, "tools", "ikone_posodobitev.py"))
ikone_posodobitev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ikone_posodobitev)

TEMA = Path(KOREN, "packaging", "tema-cinnamon", "ikone", "Safeer-Papirus-Dark")
BROWSER_ID = "io.github.memelandfaner.SafeerBrowser"
OS_ID = "io.github.memelandfaner.SafeerOS"


def _index_theme() -> dict:
    import configparser
    p = configparser.RawConfigParser()
    p.optionxform = str
    p.read(TEMA / "index.theme", encoding="utf-8")
    return {s: dict(p[s]) for s in p.sections()}


class IkonePosodobitev(unittest.TestCase):
    def test_tema_je_iz_generatorja(self):
        """Datoteke v repozitoriju so tocno to, kar narise tools/ikone_posodobitev.py (nihce jih ne popravlja na roke)."""
        with tempfile.TemporaryDirectory() as mapa:
            zapisane = ikone_posodobitev.zapisi(mapa)
            nove = {str(Path(p).relative_to(mapa)) for p in zapisane} | {"index.theme"}
            v_repo = {str(p.relative_to(TEMA)) for p in TEMA.rglob("*") if p.is_file()}
            self.assertEqual(v_repo, nove)
            for rel in nove:
                self.assertEqual((TEMA / rel).read_text(encoding="utf-8"), Path(mapa, rel).read_text(encoding="utf-8"), rel)

    def test_index_theme(self):
        t = _index_theme()
        glava = t["Icon Theme"]
        self.assertEqual(glava["Name"], "Safeer-Papirus-Dark")
        self.assertEqual(glava["Inherits"].split(",")[0], "Papirus-Dark")    # vse ostale ikone ostanejo Papirusove
        mape = glava["Directories"].split(",")
        # Velikosti, v katerih ima Papirus-Dark mintupdate-* v pultu, in razsirljiva za ostale.
        self.assertEqual(set(mape), {"16x16/panel", "22x22/panel", "24x24/panel", "scalable/status"})
        for mapa in mape:
            self.assertIn(mapa, t)
            self.assertEqual(t[mapa]["Context"], "Status")
            for stanje in ("updates-available", "up-to-date", "checking", "error", "installing"):
                # mintUpdate 7 isce »-symbolic«, Papirus in starejsi »mintupdate-<stanje>«.
                for ime in ("mintupdate-%s.svg" % stanje, "mintupdate-%s-symbolic.svg" % stanje):
                    self.assertTrue((TEMA / mapa / ime).is_file(), mapa + "/" + ime)

    def test_ikone_brez_potez_in_brez_scita(self):
        """GTK simbolno ikono prebarva samo s »fill«: poteza bi ostala siva na temnem pultu. In nobena ni Papirusov scit."""
        papirus_scit = "C 8.8519,4.9698"
        for svg in TEMA.rglob("*.svg"):
            besedilo = svg.read_text(encoding="utf-8")
            ET.fromstring(besedilo)
            self.assertNotIn("stroke", besedilo, svg.name)
            self.assertNotIn(papirus_scit, besedilo, svg.name)
            if svg.name.endswith("-symbolic.svg") and "error" in svg.name:
                self.assertIn('class="error"', besedilo)
        self.assertIn('class="warning"', (TEMA / "22x22/panel/mintupdate-updates-available-symbolic.svg").read_text())

    def test_paket_namesti_temo(self):
        with tempfile.TemporaryDirectory() as koren:
            subprocess.run(["bash", os.path.join(KOREN, "packaging", "install_cinnamon_payload.sh"), koren],
                           check=True, capture_output=True)
            tema = Path(koren, "usr/share/icons/Safeer-Papirus-Dark")
            self.assertTrue((tema / "index.theme").is_file())
            self.assertTrue((tema / "22x22/panel/mintupdate-updates-available-symbolic.svg").is_file())
            # Brez predpomnilnika (paket ga ob odstranitvi ne bi pobrisal) in berljivo za vse.
            self.assertFalse((tema / "icon-theme.cache").exists())
            for p in tema.rglob("*"):
                self.assertEqual(p.stat().st_mode & 0o777, 0o755 if p.is_dir() else 0o644, p)

    def test_deb_vsebuje_payload_cinnamon(self):
        with open(os.path.join(KOREN, "build_os_deb.sh"), encoding="utf-8") as f:
            self.assertIn("install_cinnamon_payload.sh", f.read())


class IkonaBrskalnika(unittest.TestCase):
    @staticmethod
    def _namesti(skripta, prefix, *id_):
        subprocess.run(["bash", os.path.join(KOREN, "packaging", skripta), str(prefix), *id_], check=True,
                       capture_output=True)

    def test_svg_je_drug_znak(self):
        brskalnik = Path(KOREN, "assets", "brskalnik.svg").read_text(encoding="utf-8")
        ET.fromstring(brskalnik)
        znak = Path(KOREN, "assets", "os", "znak.svg").read_text(encoding="utf-8")
        scit = "M64 20 98 33v28c0 22-14 38-34 47C44 99 30 83 30 61V33Z"
        self.assertIn(scit, znak)
        self.assertNotIn(scit, brskalnik)          # globus, ne scit
        self.assertIn("<circle", brskalnik)
        self.assertNotIn("c2pa", brskalnik)

    def test_deb_razlicni_ikoni(self):
        """Paketa safeer-browser in safeer-os: v vsaki velikosti druga slika, oba imata SVG."""
        with tempfile.TemporaryDirectory() as mapa:
            b, o = Path(mapa, "b/usr"), Path(mapa, "o/usr")
            self._namesti("install_payload.sh", b)
            self._namesti("install_os_payload.sh", o)
            ikone_b = {p.parent.parent.name: p for p in (b / "share/icons/hicolor").glob("*/apps/safeer-browser.*")}
            ikone_o = {p.parent.parent.name: p for p in (o / "share/icons/hicolor").glob("*/apps/safeer-os.*")}
            self.assertIn("scalable", ikone_b)
            self.assertIn("scalable", ikone_o)
            self.assertGreaterEqual(len(ikone_b), 9)
            self.assertEqual(set(ikone_b), set(ikone_o))
            for velikost, pot in ikone_b.items():
                self.assertNotEqual(pot.read_bytes(), ikone_o[velikost].read_bytes(), velikost)
            self.assertNotEqual((b / "share/pixmaps/safeer-browser.png").read_bytes(),
                                (o / "share/pixmaps/safeer-os.png").read_bytes())
            # AppImage brskalnika vzame to datoteko (packaging/build_appimage.sh --icon-file).
            self.assertTrue((b / "share/icons/hicolor/256x256/apps/safeer-browser.png").is_file())
            # Brskalnik ne nosi nobene PNG Safeer OS (git mv: PNG scita so zdaj packaging/icons/os).
            os_png = {p.read_bytes() for p in Path(KOREN, "packaging/icons/os/hicolor").glob("*/apps/safeer-os.png")}
            for p in (b / "share/icons").rglob("*.png"):
                self.assertNotIn(p.read_bytes(), os_png, p)

    def test_flatpak_ikone_z_id(self):
        """Flatpak izvozi samo ikone, ki se zacnejo z ID-jem programa: obe velikosti in SVG brskalnika."""
        with tempfile.TemporaryDirectory() as mapa:
            prefix = Path(mapa, "usr")
            self._namesti("install_payload.sh", prefix, BROWSER_ID)
            ikone = list((prefix / "share/icons").rglob("*.*"))
            self.assertTrue(ikone)
            for p in ikone:
                self.assertTrue(p.name.startswith(BROWSER_ID), p.name)
            self.assertTrue((prefix / "share/icons/hicolor/scalable/apps" / (BROWSER_ID + ".svg")).is_file())
            with open(prefix / "share/applications" / (BROWSER_ID + ".desktop"), encoding="utf-8") as f:
                self.assertIn("Icon=%s\n" % BROWSER_ID, f.read())

    def test_vnosi_in_metainfo(self):
        for vnos, ikona in (("packaging/safeer-browser.desktop", "safeer-browser"),
                            ("packaging/safeer-os.desktop", "safeer-os")):
            with open(os.path.join(KOREN, vnos), encoding="utf-8") as f:
                self.assertIn("Icon=%s\n" % ikona, f.read(), vnos)
        # Metainfo se na ikono sklicuje prek vnosa (launchable), ne s svojo potjo do slike.
        for meta in ("io.github.memelandfaner.SafeerBrowser.metainfo.xml", "io.github.memelandfaner.SafeerOS.metainfo.xml"):
            with open(os.path.join(KOREN, meta), encoding="utf-8") as f:
                self.assertNotIn("<icon", f.read(), meta)


if __name__ == "__main__":
    unittest.main()
