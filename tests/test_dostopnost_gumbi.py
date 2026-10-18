"""Dostopnost: vsak gumb ima ime za bralnik zaslona (GTK4 in QML). Pregled 18. 10. 2026 je nasel tri gumbe »Zapri«
samo z ikono v Spletu (core/os_splet.py) in zvezdico priljubljenih v Programih brez imena; ta preizkus prepreci nove."""

import pathlib
import re
import unittest

KOREN = pathlib.Path(__file__).resolve().parents[1]


class GumbiGtk(unittest.TestCase):
    def test_gumbi_z_ikono_imajo_ime(self):
        datoteke = [KOREN / p for p in ("safeer_os.py", "safeer_control.py", "safeer_brskalnik.py")] + \
            sorted((KOREN / "core").glob("*.py"))
        brez = []
        for f in datoteke:
            v = f.read_text(encoding="utf-8").splitlines()
            for i, vrstica in enumerate(v):
                m = re.search(r"(\w+)\s*=\s*Gtk\.(?:Button|ToggleButton|MenuButton)\.new_from_icon_name\(", vrstica) or \
                    re.search(r"(\w+)\s*=\s*Gtk\.(?:Button|ToggleButton|MenuButton)\(icon_name=", vrstica)
                if not m:
                    continue
                okolica = "\n".join(v[i:i + 12])
                if "tooltip_text" not in vrstica and not re.search(
                        re.escape(m.group(1)) + r"\.(set_tooltip_text|update_property|set_tooltip_markup)", okolica):
                    brez.append("%s:%d" % (f.name, i + 1))
        self.assertEqual(brez, [])


class KlikiQml(unittest.TestCase):
    def test_kliki_imajo_dostopno_ime(self):
        """MouseArea s klikom je v elementu z Accessible.* ali activeFocusOnTab (Gumb, GumbIkona ...). Izjema: temno
        ozadje okna (klik zapre okno; tipkovnica: Escape)."""
        brez = []
        for f in sorted((KOREN / "assets" / "os" / "qml").glob("*.qml")):
            v = f.read_text(encoding="utf-8").splitlines()
            for i, vrstica in enumerate(v):
                if "MouseArea" not in vrstica or not ("onClicked" in vrstica or (i + 1 < len(v) and "onClicked" in v[i + 1])):
                    continue
                if "zapri()" in vrstica and "anchors.fill: parent" in vrstica:
                    continue
                zamik = len(vrstica) - len(vrstica.lstrip())
                blok, j = [], i - 1
                while j >= 0 and j > i - 40:
                    blok.append(v[j])
                    if v[j].rstrip().endswith("{") and len(v[j]) - len(v[j].lstrip()) < zamik:
                        break
                    j -= 1
                besedilo = "\n".join(blok)
                if "Accessible" not in besedilo and "activeFocusOnTab" not in besedilo:
                    brez.append("%s:%d" % (f.name, i + 1))
        self.assertEqual(brez, [])


if __name__ == "__main__":
    unittest.main()
