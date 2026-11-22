"""Navigation API v Spletu (lastnik 22. 11. 2026: »ce koristi, ga privzeto vkljucimo in vklopimo«)."""
import unittest

from core import scit_pravila


class NavigationApi(unittest.TestCase):
    def test_izrecno_vklopljena(self):
        self.assertIn(("NavigationAPI", True), scit_pravila.FUNKCIJE_SPLETA)
        self.assertNotIn(("NavigationAPI", False), scit_pravila.FUNKCIJE_ZASEBNOSTI)

    def test_nastavi_funkcije_jo_vklopi(self):
        class F:
            def __init__(self, i):
                self.i = i

            def get_identifier(self):
                return self.i

        class Seznam:
            def __init__(self, imena):
                self.f = [F(i) for i in imena]

            def get_length(self):
                return len(self.f)

            def get(self, i):
                return self.f[i]

        class W:
            class Settings:
                @staticmethod
                def get_all_features():
                    return Seznam(["NavigationAPI", "SpatialNavigation"])

        vklopljene = {}

        class Nastavitve:
            def set_feature_enabled(self, f, v):
                vklopljene[f.get_identifier()] = v

        self.assertEqual(scit_pravila.funkcije_spleta(W, Nastavitve()), ["NavigationAPI"])
        self.assertEqual(vklopljene, {"NavigationAPI": True})


if __name__ == "__main__":
    unittest.main()
