"""Prostori (Safeer Link Spaces, MVP) - cista pravila core/link_prostori.py: kdo je prostor, sorodniki, stalen vrstni red,
naprave brez povezave, odvzet ozji krog, varno odpiranje (samo prostor s seznama)."""
import unittest

from core import link_prostori as lp


def naprava(id_, ime="", zm=(), platforma="", vrsta="", ta=False, ozji=True):
    return {"id": id_, "ime": ime or id_, "zmoznosti": list(zm), "platforma": platforma, "vrsta": vrsta,
            "ta": ta, "ozji": ozji}


PC = naprava("pc-1-control", "Pisarna", ["desktop", "apps", "remote"], "windows", "control")
TABLICA = naprava("t-1-os", "Tablica", ["zaslon.deli", "remote", "apps"], "tablet")
TV = naprava("tv-1", "Dnevna soba", ["screen", "media"], "tv")
TV_OS = naprava("tv-1-os", "Dnevna soba", ["zaslon.deli", "remote", "apps"], "tv")
TA = naprava("jaz-control", "Ta", ["desktop"], "linux", ta=True)


class KdoJeProstor(unittest.TestCase):
    def test_racunalnik_in_android(self):
        z = lp.zive_s_prostorom([PC, TABLICA, TA])
        self.assertEqual(set(z), {"pc-1", "t-1"})
        self.assertEqual(z["pc-1"]["nacin"], lp.NACIN_RACUNALNIK)
        self.assertEqual(z["pc-1"]["vrsta"], "racunalnik")
        self.assertEqual(z["t-1"]["nacin"], lp.NACIN_ZASLON)
        self.assertEqual(z["t-1"]["vrsta"], "tablica")

    def test_brez_zaslona_ni_prostor(self):
        self.assertEqual(lp.zive_s_prostorom([TV]), {})

    def test_izven_ozjega_kroga_ni_prostor(self):
        self.assertEqual(lp.zive_s_prostorom([dict(PC, ozji=False)]), {})

    def test_ta_racunalnik_in_sorodniki_niso_prostor(self):
        self.assertEqual(lp.zive_s_prostorom([TA, naprava("jaz", "Ta", ["url"], "linux")]), {})

    def test_sorodniki_en_prostor_ukaz_vnosu_z_zaslonom(self):
        z = lp.zive_s_prostorom([TV, TV_OS])
        self.assertEqual(list(z), ["tv-1"])
        self.assertEqual(z["tv-1"]["id"], "tv-1-os", "ukaz gre vnosu, ki zaslon deli")
        self.assertEqual(z["tv-1"]["vrsta"], "tv")
        self.assertTrue(z["tv-1"]["aplikacije"])

    def test_namizje_pred_deljenjem(self):
        a = naprava("x", "X", ["zaslon.deli", "a", "b", "c"], "tablet")
        b = naprava("x-control", "X", ["desktop"], "linux")
        self.assertEqual(lp.zive_s_prostorom([a, b])["x"]["id"], "x-control")

    def test_pokvarjeni_vnosi(self):
        self.assertEqual(lp.zive_s_prostorom([None, "x", {"id": ""}, {"id": "y", "zmoznosti": "desktop"}]), {})

    def test_vrsta(self):
        self.assertEqual(lp.vrsta(naprava("a", platforma="phone")), "telefon")
        self.assertEqual(lp.vrsta(naprava("a", platforma="tv")), "tv")
        self.assertEqual(lp.vrsta(naprava("a", platforma="linux")), "racunalnik")
        self.assertEqual(lp.vrsta(naprava("a")), "naprava")


class Zapis(unittest.TestCase):
    def test_stalen_vrstni_red(self):
        z1 = lp.zapomni([], [TABLICA], 100)
        z2 = lp.zapomni(z1, [PC, TABLICA], 200)
        self.assertEqual([z["kljuc"] for z in z2], ["t-1", "pc-1"], "nova naprava gre na konec")
        # Tablica odide in pride nazaj: mesto ostane.
        z3 = lp.zapomni(z2, [PC], 300)
        z4 = lp.zapomni(z3, [PC, TABLICA], 400)
        self.assertEqual([z["kljuc"] for z in z4], ["t-1", "pc-1"])
        self.assertEqual(z4[0]["dodana"], 100)
        self.assertEqual(z4[0]["videna"], 400)

    def test_brez_povezave_ostane(self):
        z = lp.zapomni(lp.zapomni([], [PC, TABLICA], 100), [PC], 200)
        p = lp.prostori(z, [PC])
        self.assertEqual([(x["id"], x["povezana"]) for x in p], [("pc-1-control", True), ("t-1-os", False)])
        self.assertEqual(p[1]["videna"], 100)
        self.assertFalse(p[1]["aplikacije"], "naprava brez povezave nima programov")

    def test_odvzet_ozji_krog_izpade(self):
        z = lp.zapomni([], [PC, TABLICA], 100)
        z = lp.zapomni(z, [PC, dict(TABLICA, ozji=False)], 200)
        self.assertEqual([x["kljuc"] for x in z], ["pc-1"])

    def test_izklopljeno_deljenje_izpade(self):
        z = lp.zapomni([], [TABLICA], 100)
        z = lp.zapomni(z, [dict(TABLICA, zmoznosti=["remote"])], 200)
        self.assertEqual(z, [])

    def test_ime_se_posodobi(self):
        z = lp.zapomni([], [PC], 100)
        z = lp.zapomni(z, [dict(PC, ime="Delo")], 200)
        self.assertEqual(lp.prostori(z, [])[0]["ime"], "Delo")

    def test_najvec_znanih_najprej_izpadejo_nevidene(self):
        zive = [naprava("n%d" % i, "N%d" % i, ["zaslon.deli"], "phone") for i in range(lp.NAJVEC_ZNANIH)]
        z = lp.zapomni([], zive[:1], 1)                       # n0 viden najdlje nazaj
        z = lp.zapomni(z, zive[1:], 2)
        self.assertEqual(len(z), lp.NAJVEC_ZNANIH)
        z = lp.zapomni(z, [naprava("nova", "Nova", ["desktop"], "linux")] + zive[1:], 3)
        kljuci = [x["kljuc"] for x in z]
        self.assertEqual(len(z), lp.NAJVEC_ZNANIH)
        self.assertNotIn("n0", kljuci)
        self.assertEqual(kljuci[-1], "nova")

    def test_povezane_ne_izpadejo_tudi_nad_mejo(self):
        zive = [naprava("n%d" % i, "N%d" % i, ["zaslon.deli"], "phone") for i in range(lp.NAJVEC_ZNANIH + 3)]
        self.assertEqual(len(lp.zapomni([], zive, 5)), lp.NAJVEC_ZNANIH + 3)

    def test_pokvarjen_zapis(self):
        surovo = [None, 5, {"kljuc": ""}, {"kljuc": "a", "vrsta": "<script>", "nacin": "x", "dodana": "zz",
                                            "ime": "A" * 500}, {"kljuc": "a"}]
        c = lp.ocisti_znane(surovo)
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0]["vrsta"], "naprava")
        self.assertEqual(c[0]["nacin"], lp.NACIN_ZASLON)
        self.assertEqual(c[0]["dodana"], 0)
        self.assertLessEqual(len(c[0]["ime"]), 80)
        self.assertEqual(lp.ocisti_znane("ni seznam"), [])


class Odpiranje(unittest.TestCase):
    def test_samo_prostor_s_seznama(self):
        zive = [PC, TABLICA, TV, TV_OS, TA]
        self.assertEqual(lp.za_odpiranje(zive, "pc-1-control")["nacin"], lp.NACIN_RACUNALNIK)
        self.assertEqual(lp.za_odpiranje(zive, "tv-1")["id"], "tv-1-os", "tudi id sorodnika najde prostor")
        self.assertIsNone(lp.za_odpiranje(zive, "jaz-control"), "ta racunalnik ni prostor")
        self.assertIsNone(lp.za_odpiranje(zive, "neznana"))
        self.assertIsNone(lp.za_odpiranje(zive, ""))
        self.assertIsNone(lp.za_odpiranje([dict(PC, ozji=False)], "pc-1-control"))

    def test_cel_zaslon_kot_android(self):
        self.assertEqual(lp.CEL_ZASLON, "safeer.cel.zaslon")      # Android link/Daljinec.CEL_ZASLON
        self.assertEqual(lp.ZMOZNOST_DELI_ZASLON, "zaslon.deli")  # Android link/Daljinec.ZMOZNOST_DELI_ZASLON


if __name__ == "__main__":
    unittest.main()
