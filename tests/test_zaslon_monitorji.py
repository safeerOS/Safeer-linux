"""Monitorji in okvir naprave za Zaslone (core/zaslon_monitorji; lastnik 25. 10. 2026 12:07) z laznimi monitorji, in
vrstni red naprav, ki ga izbere uporabnik (core/link_prostori.preuredi)."""
import unittest

from core import link_prostori, zaslon_monitorji as zm


class _Geom:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.width, self.height = x, y, w, h


class _Monitor:
    def __init__(self, prikljucek, opis, g, merilo=1):
        self._p, self._o, self._g, self._m = prikljucek, opis, g, merilo

    def get_connector(self):
        return self._p

    def get_description(self):
        return self._o

    def get_geometry(self):
        return self._g

    def get_scale_factor(self):
        return self._m


class _Seznam:
    def __init__(self, m):
        self.m = m

    def get_n_items(self):
        return len(self.m)

    def get_item(self, i):
        return self.m[i]


class _Zaslon:
    def __init__(self, m):
        self.m = m

    def get_monitors(self):
        return _Seznam(self.m)


class Monitorji(unittest.TestCase):
    def test_lazna_monitorja(self):
        z = _Zaslon([_Monitor("eDP-1", "Vgrajen zaslon", _Geom(0, 0, 1920, 1080)),
                     _Monitor("HDMI-1", "Philips 27", _Geom(1920, 0, 2560, 1440), 2)])
        m = zm.monitorji(z)
        self.assertEqual([(x["st"], x["oznaka"], x["ime"], x["x"], x["w"], x["merilo"]) for x in m],
                         [(1, "eDP-1", "Vgrajen zaslon", 0, 1920, 1), (2, "HDMI-1", "Philips 27", 1920, 2560, 2)])
        self.assertEqual(zm.najdi(m, "HDMI-1")["st"], 2)
        self.assertIsNone(zm.najdi(m, "DP-9"))
        self.assertIsNone(zm.najdi(m, ""))

    def test_brez_prikljucka_in_napaka(self):
        m = zm.monitorji(_Zaslon([_Monitor(None, "", _Geom(0, 0, 800, 600))]))
        self.assertEqual(m[0]["oznaka"], "monitor-1")

        class Pokvarjen:
            def get_monitors(self):
                raise RuntimeError("brez zaslona")
        self.assertEqual(zm.monitorji(Pokvarjen()), [])


class Parametri(unittest.TestCase):
    def test_star_in_nov_zapis(self):
        self.assertEqual(zm.parametri_odpiranja("1"), {"celo": True, "monitor": "", "okvir": False})
        self.assertEqual(zm.parametri_odpiranja("0")["celo"], False)
        for niz in ('{"celo": true, "monitor": "HDMI-1"}', zm.niz_odpiranja(True, "HDMI-1")):
            self.assertEqual(zm.parametri_odpiranja(niz), {"celo": True, "monitor": "HDMI-1", "okvir": False})
        self.assertEqual(zm.niz_odpiranja(True), "1", "starejsi Control razume samo 1/0")
        self.assertEqual(zm.parametri_odpiranja(zm.niz_odpiranja(False, okvir=True))["okvir"], True)
        for slabo in ("x", "[1]", '{"celo": "da", "monitor": 5}', None):
            self.assertEqual(zm.parametri_odpiranja(slabo), {"celo": False, "monitor": "", "okvir": False}, slabo)
        self.assertEqual(len(zm.parametri_odpiranja('{"monitor": "%s"}' % ("A" * 500))["monitor"]), 64)


class Okvir(unittest.TestCase):
    M = {"x": 1920, "y": 0, "w": 2560, "h": 1440}

    def test_telefon_pomanjsan_brez_raztega_na_sredini(self):
        o = zm.okvir_naprave(1080, 2340, self.M)
        self.assertAlmostEqual(o["w"] / o["h"], 1080 / 2340, places=2)
        self.assertLessEqual(o["h"], int(1440 * zm.DELEZ_OKVIRJA) + 1)
        self.assertEqual(o["x"], 1920 + (2560 - o["w"]) // 2)
        self.assertEqual(o["y"], (1440 - o["h"]) // 2)
        self.assertLess(o["merilo"], 1)

    def test_ki_gre_na_monitor_ostane_1_1(self):
        o = zm.okvir_naprave(800, 1280, {"x": 0, "y": 0, "w": 3840, "h": 2160})
        self.assertEqual((o["w"], o["h"], o["merilo"]), (800, 1280, 1.0))

    def test_tablica_lezece(self):
        o = zm.okvir_naprave(2560, 1600, {"x": 0, "y": 0, "w": 1920, "h": 1080})
        self.assertAlmostEqual(o["w"] / o["h"], 1.6, places=2)
        self.assertLessEqual(o["w"], 1920)

    def test_privzeta_velikost(self):
        self.assertEqual(zm.velikost_naprave("tablica"), (1600, 2560))
        self.assertEqual(zm.velikost_naprave("telefon", 720, 1600), (720, 1600))
        self.assertEqual(zm.velikost_naprave("tv"), zm.PRIVZETO["telefon"])
        self.assertEqual(zm.na_sredino({"x": 100, "y": 0, "w": 1000, "h": 800}, 4000, 400),
                         {"x": 100, "y": 200, "w": 1000, "h": 400})


ZNANE = [{"kljuc": "tv-9", "id": "tv-9-os", "ime": "Kuhinja", "vrsta": "tv", "nacin": "zaslon", "dodana": 1, "videna": 1},
         {"kljuc": "pc-1", "id": "pc-1-control", "ime": "Pisarna", "vrsta": "racunalnik", "nacin": "racunalnik",
          "dodana": 2, "videna": 2},
         {"kljuc": "t-1", "id": "t-1-os", "ime": "Tablica", "vrsta": "tablica", "nacin": "zaslon", "dodana": 3, "videna": 3}]


class VrstniRed(unittest.TestCase):
    def test_preuredi_in_zapomni(self):
        nove = link_prostori.preuredi(ZNANE, ["t-1", "pc-1-os", "tuj", 5])
        self.assertEqual([z["id"] for z in nove], ["t-1-os", "pc-1-control", "tv-9-os"])
        self.assertEqual([z["mesto"] for z in nove], [0, 1, 2])
        # Zapomni (osvezitev) vrstni red obdrzi; nova naprava gre na konec.
        zive = [{"id": "f-2-os", "ime": "Telefon", "zmoznosti": ["zaslon.deli"], "platforma": "phone", "ozji": True}]
        po = link_prostori.zapomni(nove, zive, 100)
        self.assertEqual([z["id"] for z in po], ["t-1-os", "pc-1-control", "tv-9-os", "f-2-os"])
        self.assertEqual(link_prostori.ocisti_znane(po), po, "mesto prezivi zapis v os.json")

    def test_pokvarjeno_mesto_se_prezre(self):
        z = [dict(ZNANE[0], mesto="1"), dict(ZNANE[1], mesto=True), dict(ZNANE[2], mesto=-3)]
        self.assertTrue(all("mesto" not in x for x in link_prostori.ocisti_znane(z)))


if __name__ == "__main__":
    unittest.main()
