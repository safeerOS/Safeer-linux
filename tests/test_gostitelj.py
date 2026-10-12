"""Safeer OS v Flatpaku: poti racunalnika (/run/host) in zagon programov na racunalniku."""
import os
import unittest
from pathlib import Path
from unittest import mock

from core import gostitelj as G

KOREN = Path(__file__).resolve().parents[1]


class Poti(unittest.TestCase):
    def test_na_gostitelju(self):
        self.assertEqual(G.na_gostitelju("/run/host/usr/share/applications/firefox.desktop"),
                         "/usr/share/applications/firefox.desktop")
        self.assertEqual(G.na_gostitelju("/home/x/.local/share/applications/a.desktop"), "/home/x/.local/share/applications/a.desktop")
        self.assertEqual(G.na_gostitelju("/run/hostile/x"), "/run/hostile/x")

    def test_zunaj_flatpaka_brez_ucinka(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FLATPAK_ID", None)
            self.assertEqual(G.mape_gostitelja("applications"), [])
            self.assertFalse(G.zazeni_vnos("/usr/share/applications/x.desktop"))

    def test_v_flatpaku_mape_in_zagon(self):
        with mock.patch.object(G, "v_flatpaku", return_value=True), \
             mock.patch.object(G.shutil, "which", return_value="/usr/bin/flatpak-spawn"), \
             mock.patch.object(G.subprocess, "Popen") as popen:
            self.assertIn("/run/host/usr/share/applications", G.mape_gostitelja("applications"))
            self.assertTrue(G.zazeni_vnos("/run/host/usr/share/applications/firefox.desktop", ["/run/host/usr/x.txt"]))
            ukaz = popen.call_args[0][0]
            self.assertEqual(ukaz[:2], ["flatpak-spawn", "--host"])
            self.assertEqual(ukaz[-3:], ["launch", "/usr/share/applications/firefox.desktop", "/usr/x.txt"])


class Povezano(unittest.TestCase):
    def test_manifest_dovoljenja(self):
        s = (KOREN / "io.github.memelandfaner.SafeerOS.yml").read_text(encoding="utf-8")
        self.assertIn("--filesystem=host-os:ro", s)

    def test_zagon_v_safeer_os(self):
        s = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
        i = s.index("def _zazeni_vnos_z")
        self.assertIn("gostitelj.zazeni_vnos(pot, datoteke)", s[i:i + 900])


if __name__ == "__main__":
    unittest.main()
