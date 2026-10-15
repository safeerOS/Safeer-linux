"""Smeti in zaganjalniki v Flatpaku so na RACUNALNIKU, ne v peskovniku (testni PC 15. 10. 2026: Safeer OS v Flatpaku
je kazal »Smeti so prazne« in Razveljavi ni nasel datoteke, ki jo je gio trash odlozil v ~/.local/share/Trash)."""
import os
import unittest
from unittest import mock

from core import gostitelj, os_datoteke


class SmetiGostitelja(unittest.TestCase):
    def test_v_flatpaku_gostiteljeva_mapa(self):
        okolje = {"XDG_DATA_HOME": "/home/u/.var/app/x/data", "HOST_XDG_DATA_HOME": "", "FLATPAK_ID": "x"}
        with mock.patch.dict(os.environ, okolje), mock.patch.object(gostitelj, "v_flatpaku", return_value=True):
            self.assertEqual(gostitelj.podatki_gostitelja(), os.path.expanduser("~/.local/share"))
            self.assertEqual(os_datoteke._mapa_smeti(), os.path.join(os.path.expanduser("~/.local/share"), "Trash"))
        with mock.patch.dict(os.environ, dict(okolje, HOST_XDG_DATA_HOME="/home/u/podatki")), \
                mock.patch.object(gostitelj, "v_flatpaku", return_value=True):
            self.assertEqual(os_datoteke._mapa_smeti(), "/home/u/podatki/Trash")

    def test_zunaj_flatpaka_xdg(self):
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg"}), \
                mock.patch.object(gostitelj, "v_flatpaku", return_value=False):
            self.assertEqual(os_datoteke._mapa_smeti(), "/tmp/xdg/Trash")


if __name__ == "__main__":
    unittest.main()
