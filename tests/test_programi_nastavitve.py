"""Orodja za nastavitve sistema v iskalni lupi namizja (lastnik, 11. 10. 2026): vnos .desktop dobi oznako
»nastavitev« ter kljucne besede v jeziku uporabnika, anglesko in slovenske sopomenke."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import os_programi  # noqa: E402

VNOS = """[Desktop Entry]
Type=Application
Name=Power Management
Name[sl]=Upravljanje porabe energije
GenericName=Power
Keywords=power;battery;suspend;
Keywords[sl]=energija;
Exec=true
Categories=Settings;DesktopSettings;
"""


class TestNastavitve(unittest.TestCase):
    def _preberi(self, ime, vsebina):
        with tempfile.TemporaryDirectory() as mapa:
            pot = os.path.join(mapa, ime)
            with open(pot, "w", encoding="utf-8") as f:
                f.write(vsebina)
            with mock.patch.dict(os.environ, {"LANGUAGE": "sl", "LANG": "sl_SI.UTF-8", "LC_ALL": ""}):
                return os_programi.preberi_vnos(pot, namizja=["X-Cinnamon"])

    def test_nastavitev_in_kljucne(self):
        v = self._preberi("cinnamon-settings-power.desktop", VNOS)
        self.assertTrue(v["nastavitev"])
        self.assertEqual(v["ime"], "Upravljanje porabe energije")
        for beseda in ("energija", "power", "battery", "Power Management", "baterija", "napajanje", "nastavitve", "settings"):
            self.assertIn(beseda, v["kljucne"])
        self.assertEqual(len(v["kljucne"]), len({k.lower() for k in v["kljucne"]}), "brez ponovitev")

    def test_navaden_program_ni_nastavitev(self):
        v = self._preberi("urejevalnik.desktop", VNOS.replace("Categories=Settings;DesktopSettings;", "Categories=Utility;"))
        self.assertFalse(v["nastavitev"])
        self.assertNotIn("napajanje", v["kljucne"])


if __name__ == "__main__":
    unittest.main()
