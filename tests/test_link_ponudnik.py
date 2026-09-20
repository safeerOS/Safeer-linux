"""Korak 6: racunalnik kot ponudnik aplikacij v Safeer Linku (Protocol v1).

Programi racunalnika gredo v prijavo kot katalog `apps` samo, ce jih je uporabnik dovolil;
katalog je brez ikon in v mejah huba (200 vnosov, 32 KiB).
"""
import json
import os
import tempfile
import unittest

from core import link_hub, link_programi


def _vnos(mapa, ime, naslov):
    with open(os.path.join(mapa, ime), "w", encoding="utf-8") as d:
        d.write(f"[Desktop Entry]\nType=Application\nName={naslov}\nExec=true\nIcon=x\nCategories=Utility;\n")


class Katalog(unittest.TestCase):
    def test_brez_dovoljenja_prazen(self):
        with tempfile.TemporaryDirectory() as m:
            _vnos(m, "a.desktop", "Aplikacija")
            self.assertEqual(link_programi.Programi(False, mape=[m]).katalog_v1(), {})

    def test_z_dovoljenjem_imena_brez_ikon(self):
        with tempfile.TemporaryDirectory() as m:
            _vnos(m, "gimp.desktop", "GIMP")
            _vnos(m, "vlc.desktop", "VLC")
            k = link_programi.Programi(True, mape=[m]).katalog_v1()
            self.assertEqual(k.get("app:gimp.desktop"), {"name": "GIMP", "kind": "linux"})
            self.assertIn("app:vlc.desktop", k)
            self.assertLess(len(json.dumps(k)), 32 * 1024)

    def test_meje_huba(self):
        with tempfile.TemporaryDirectory() as m:
            for i in range(260):
                _vnos(m, f"p{i:03d}.desktop", f"Program {i}")
            k = link_programi.Programi(True, mape=[m]).katalog_v1()
            self.assertLessEqual(len(k), link_programi.NAJVEC)
            self.assertLess(len(json.dumps(k)), 32 * 1024)


class Prijava(unittest.TestCase):
    def test_povezava_ima_katalog_in_objavo(self):
        p = link_hub.Povezava("wss://x/cast/ws", "", "n-0123456789abcdef-control", "Control",
                              katalog=lambda: {"app:a.desktop": {"name": "A", "kind": "linux"}})
        self.assertEqual(p.katalog()["app:a.desktop"]["name"], "A")
        self.assertFalse(p.objavi_katalog({}), "brez odprte povezave se nic ne poslje")


if __name__ == "__main__":
    unittest.main()
