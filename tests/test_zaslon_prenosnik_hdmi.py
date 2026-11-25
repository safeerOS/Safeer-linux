"""Prenosnik lastnika 25. 11. 2026 ~04:05: HDMI-1 je »connected« in primaren na 0,0, a ne daje slike (od 16. 11.);
eDP-1 je desno (+1920). Namizje, pult in dock so bili na nevidnem HDMI, na prenosniku samo ozadje.

Preizkus gre skozi pravi izpis `xrandr --current` (razcleni_xrandr) in Strazo, ne samo skozi slovarje."""

import unittest

from core import zaslon_namizja as zn


def _xrandr(primarni: str, hdmi_vklopljen: bool = True, edp_x: int = 1920) -> str:
    """Izpis xrandr kot na prenosniku (Extensa 215-54, Cinnamon 6.6.9); HDMI brez slike je vseeno »connected«."""
    p = lambda ime: " primary" if primarni == ime else ""   # noqa: E731
    hdmi = (f"HDMI-1 connected{p('HDMI-1')} 1920x1080+0+0 (normal left inverted right x axis y axis) 1600mm x 900mm\n"
            "   1920x1080     60.00*+  50.00    59.94\n") if hdmi_vklopljen else \
        "HDMI-1 connected (normal left inverted right x axis y axis)\n   1920x1080     60.00 +\n"
    sirina = 1920 + (1920 if hdmi_vklopljen else 0)
    return (f"Screen 0: minimum 320 x 200, current {sirina} x 1080, maximum 16384 x 16384\n"
            f"eDP-1 connected{p('eDP-1')} 1920x1080+{edp_x if hdmi_vklopljen else 0}+0 "
            "(normal left inverted right x axis y axis) 344mm x 193mm\n"
            "   1920x1080     60.00*+  59.97\n" + hdmi)


class _Shramba(dict):
    def set(self, kljuc, vrednost):
        self[kljuc] = vrednost


class PrenosnikHdmiBrezSlike(unittest.TestCase):
    def setUp(self):
        self.stanje = {"primarni": "HDMI-1", "hdmi": True}
        self.preklopi, self.izbire, self.shramba = [], [], _Shramba()

        def beri():
            return zn.razcleni_xrandr(_xrandr(self.stanje["primarni"], self.stanje["hdmi"]))

        def nastavi(ime):
            self.preklopi.append(ime)
            self.stanje["primarni"] = ime
            return True

        self.s = zn.Straza(beri, lambda: False, nastavi, self.izbire.append, self.shramba)

    def test_razclenitev_pravega_izpisa(self):
        izhodi = zn.razcleni_xrandr(_xrandr("HDMI-1"))
        self.assertEqual(izhodi, [{"ime": "eDP-1", "primarni": False, "aktiven": True},
                                  {"ime": "HDMI-1", "primarni": True, "aktiven": True}])

    def test_hdmi_primaren_brez_slike_namizje_na_edp(self):
        self.assertEqual(self.s.korak(), "eDP-1")
        self.assertEqual(self.preklopi, ["eDP-1"])
        self.assertEqual(self.izbire, ["eDP-1"])

    def test_muffin_vrne_hdmi_za_primarnega_straza_popravi(self):
        """Ob ponovnem priklopu Muffin uporabi monitors.xml (HDMI primaren): naslednji cikel (<= 3 s) spet eDP."""
        self.s.korak()
        self.stanje["primarni"] = "HDMI-1"
        self.assertEqual(self.s.korak(), "eDP-1")
        self.assertEqual(self.preklopi, ["eDP-1", "eDP-1"])

    def test_xrandr_auto_po_rocnem_izklopu_ostane_edp(self):
        """Merilo naloge: po `xrandr --auto` (HDMI spet vklopljen, eDP primaren) se nic ne premakne."""
        self.stanje.update(primarni="eDP-1", hdmi=False)
        self.assertEqual(self.s.korak(), "eDP-1")
        self.stanje["hdmi"] = True
        self.assertEqual(self.s.korak(), "eDP-1")
        self.assertEqual(self.preklopi, [])
        self.assertEqual(self.izbire, ["eDP-1"])


if __name__ == "__main__":
    unittest.main()
