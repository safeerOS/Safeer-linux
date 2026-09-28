import unittest

from core.link_sway import fiksno_platno, merilo_platna


class FiksnoPlatnoTest(unittest.TestCase):
    def test_glut_igra_brez_razreda(self):
        okno = {"shell": "xwayland", "window_properties": {"title": "Crack Attack!"},
                "geometry": {"width": 400, "height": 400}}
        self.assertEqual(fiksno_platno(okno), (400, 400))

    def test_sodobni_programi_niso_platno(self):
        self.assertIsNone(fiksno_platno({"shell": "xdg_shell", "geometry": {"width": 400, "height": 400}}))
        self.assertIsNone(fiksno_platno({"shell": "xwayland", "window_properties": {"class": "Brave-browser"},
                                         "geometry": {"width": 800, "height": 600}}))

    def test_majhna_okna_niso_platno(self):
        self.assertIsNone(fiksno_platno({"shell": "xwayland", "geometry": {"width": 120, "height": 80}}))

    def test_merilo_zapolni_brez_obrezovanja(self):
        self.assertAlmostEqual(merilo_platna(1920, 1080, 400, 400), 2.7, places=2)
        self.assertAlmostEqual(merilo_platna(1920, 1080, 640, 480), 2.25, places=2)
        self.assertEqual(merilo_platna(1920, 1080, 2560, 1440), 1.0)
        self.assertLessEqual(merilo_platna(3840, 2160, 200, 150), 6.0)


if __name__ == "__main__":
    unittest.main()


class UrejenoTest(unittest.TestCase):
    def test_povecano_okno_ni_urejeno(self):
        from core.link_sway import _ze_urejeno
        self.assertTrue(_ze_urejeno({"type": "floating_con", "rect": {"width": 400, "height": 400}}, (400, 400)))
        self.assertFalse(_ze_urejeno({"type": "floating_con", "rect": {"width": 1920, "height": 1075}}, (400, 400)))
        self.assertFalse(_ze_urejeno({"type": "con", "rect": {"width": 400, "height": 400}}, (400, 400)))
