# -*- coding: utf-8 -*-
"""Loceni zaslon v obliki zaslona naprave, ki gleda (`view` v `screen.start`): velikost, merilo, dogovor.

Brez swaya in brez zajema: lazni drugi zaslon si zapomni, kaj bi nastavil."""
import os
import sys
import types
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec, link_sway, link_zaslon  # noqa: E402


class LazniDrugi:
    def __init__(self):
        self.velikosti = []
        self.merila = []
        self.vnos = types.SimpleNamespace(mozno=True, porocaj_kazalec=False, sprosti_vse=lambda: None,
                                          zapri=lambda: None)
        self.zadnja_skupina = ""
        self.zadnji_profil = ""

    def tece(self):
        return True

    def okna(self):
        return 1

    def velikost(self, s, v):
        self.velikosti.append((s, v))

    def osnovno_merilo(self, m):
        self.merila.append(m)

    def zvok_vir(self):
        return None

    def okolje(self):
        return dict(os.environ)

    def ukaz_zajema(self, fps, qp, bitrate):
        return ["/bin/true"]


class Velikost(unittest.TestCase):
    PRIVZETO = (1920, 1080)

    def test_brez_podatka_velja_privzeto(self):
        for pogled in (None, {}, "2340x1080", {"w": "x", "h": 1080}, {"w": 0, "h": 0}, {"w": None, "h": None}):
            self.assertEqual(link_zaslon.velikost_za_gledalca(pogled, self.PRIVZETO), self.PRIVZETO, pogled)

    def test_zaslon_naprave(self):
        v = link_zaslon.velikost_za_gledalca
        self.assertEqual(v({"w": 2340, "h": 1080}, self.PRIVZETO), (2340, 1080))     # telefon, lezece
        self.assertEqual(v({"w": 1920, "h": 1200}, self.PRIVZETO), (1920, 1200))     # tablica 16:10
        self.assertEqual(v({"w": 1280, "h": 576}, self.PRIVZETO), (1280, 576))
        self.assertEqual(v({"w": 1080, "h": 2340}, self.PRIVZETO), (1080, 2340))     # pokoncno ostane pokoncno
        self.assertEqual(v({"w": 2241, "h": 1079}, self.PRIVZETO), (2240, 1078))     # sodi stranici
        self.assertEqual(v({"w": 2340.0, "h": "1080"}, self.PRIVZETO), (2340, 1080))

    def test_zunaj_meja_velja_privzeto(self):
        v = link_zaslon.velikost_za_gledalca
        for pogled in ({"w": 480, "h": 320}, {"w": 639, "h": 400}, {"w": 4096, "h": 2160}, {"w": 3840, "h": 2400},
                       {"w": -2340, "h": 1080}, {"w": 10 ** 9, "h": 10 ** 9}):
            self.assertEqual(v(pogled, self.PRIVZETO), self.PRIVZETO, pogled)
        self.assertEqual(v({"w": 3840, "h": 2160}, self.PRIVZETO), (3840, 2160))
        self.assertEqual(v({"w": 640, "h": 360}, self.PRIVZETO), (640, 360))


class Merilo(unittest.TestCase):
    def test_gost_telefon_dobi_vecje_gumbe(self):
        m = link_zaslon.merilo_za_gledalca
        self.assertEqual(m({"density": 3.0, "kind": "phone"}, (2340, 1080)), 2.0)
        self.assertEqual(m({"density": 2.625, "kind": "phone"}, (2400, 1080)), 1.75)
        # Programom mora ostati vsaj 540 navideznih tock po krajsi stranici.
        self.assertEqual(m({"density": 4.0, "kind": "phone"}, (3120, 1440)), 2.5)
        self.assertEqual(m({"density": 3.0, "kind": "phone"}, (1600, 720)), 1.25)
        self.assertEqual(m({"density": 2.0, "kind": "phone"}, (1280, 576)), 1.0)

    def test_tablica_televizor_in_stare_naprave(self):
        m = link_zaslon.merilo_za_gledalca
        self.assertEqual(m({"density": 1.5, "kind": "tablet"}, (1920, 1200)), 1.0)
        self.assertEqual(m({"density": 2.0, "kind": "tv"}, (1920, 1080)), 1.0)
        self.assertEqual(m({"density": 2.0, "kind": "TV "}, (1920, 1080)), 1.0)
        self.assertEqual(m(None, (1920, 1080)), 1.0)
        self.assertEqual(m({}, (1920, 1080)), 1.0)
        self.assertEqual(m({"density": "x"}, (1920, 1080)), 1.0)
        self.assertEqual(m({"density": float("nan")}, (2340, 1080)), 1.0)
        self.assertEqual(m({"density": float("inf")}, (2340, 1080)), 1.0)

    def test_izrecno_merilo_naprave(self):
        m = link_zaslon.merilo_za_gledalca
        self.assertEqual(m({"density": 3.0, "scale": 1.5}, (2340, 1080)), 1.5)
        self.assertEqual(m({"density": 3.0, "scale": 1.6}, (2340, 1080)), 1.5)     # na cetrtine navzdol
        self.assertEqual(m({"density": 3.0, "scale": 9}, (2340, 1080)), 3.0)
        self.assertEqual(m({"density": 3.0, "scale": 0.4, "kind": "tv"}, (1920, 1080)), 1.0)
        self.assertEqual(m({"density": 3.0, "scale": 2, "kind": "tv"}, (1920, 1080)), 2.0)   # uporabnik je izbral


class Seja(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("DISPLAY", ":0")
        self.z = link_zaslon.Zaslon(vklopljeno=True, ffmpeg="/bin/true")
        self.z.drugi = LazniDrugi()

    def tearDown(self):
        self.z.ustavi()

    def test_loceni_zaslon_dobi_obliko_naprave(self):
        seja = self.z.zacni("fon", "najvisja", "apps",
                            pogled={"w": 2340, "h": 1080, "density": 3.0, "kind": "phone", "touch": True})
        self.assertEqual((seja["width"], seja["height"]), (2340, 1080))
        self.assertEqual(seja["screen"], "apps")
        self.assertEqual(seja["scale"], 2.0)
        self.assertEqual(seja["fps"], 60)                       # kakovost ostane, spremeni se samo oblika
        self.assertEqual(self.z.drugi.velikosti[-1], (2340, 1080))
        self.assertEqual(self.z.drugi.merila[-1], 2.0)

    def test_starejsa_naprava_dobi_velikost_iz_kakovosti(self):
        seja = self.z.zacni("tv", "najvisja", "apps")
        self.assertEqual((seja["width"], seja["height"]), (1920, 1080))
        self.assertEqual(seja["scale"], 1.0)
        self.assertEqual(self.z.drugi.velikosti[-1], (1920, 1080))
        self.assertEqual(self.z.drugi.merila[-1], 1.0)
        seja = self.z.zacni("tv", "nizka", "apps")
        self.assertEqual((seja["width"], seja["height"]), (1280, 720))

    def test_televizor_po_telefonu_dobi_svoj_zaslon_nazaj(self):
        self.z.zacni("fon", "najvisja", "apps", pogled={"w": 2340, "h": 1080, "density": 3.0, "kind": "phone"})
        seja = self.z.zacni("tv", "najvisja", "apps", pogled={"w": 1920, "h": 1080, "density": 2.0, "kind": "tv"})
        self.assertEqual((seja["width"], seja["height"], seja["scale"]), (1920, 1080, 1.0))
        self.assertEqual(self.z.drugi.velikosti[-1], (1920, 1080))
        self.assertEqual(self.z.drugi.merila[-1], 1.0)

    def test_pravi_zaslon_se_po_napravi_ne_ravna(self):
        # Cilj `desktop`: zajem pravega zaslona; povrsina naprave ne spremeni nicesar na racunalniku.
        seja = self.z.zacni("fon", "najvisja", "desktop",
                            pogled={"w": 2340, "h": 1080, "density": 3.0, "kind": "phone"})
        self.assertEqual(seja["screen"], "desktop")
        self.assertEqual(seja["scale"], 1.0)
        self.assertEqual(self.z.drugi.velikosti, [])
        self.assertEqual(self.z.drugi.merila, [])
        self.assertLessEqual(seja["width"], 1920)
        self.assertLessEqual(seja["height"], 1080)

    def test_naprava_med_sejo_izbere_vecjo_vsebino(self):
        poslano = []
        odjemalec = types.SimpleNamespace(sendall=poslano.append)
        self.z.zacni("fon", "najvisja", "apps", pogled={"w": 2340, "h": 1080, "density": 3.0, "kind": "phone"})
        self.assertEqual(self.z.drugi.merila[-1], 2.0)
        self.z._nastavi_merilo(odjemalec, {"vrsta": "merilo", "merilo": 2.5})
        self.assertEqual(self.z.drugi.merila[-1], 2.5)
        self.assertIn(b'"merilo": 2.5', poslano[-1])
        self.assertEqual(poslano[-1][0], link_zaslon.OKVIR_OBVESTILO)
        self.z._nastavi_merilo(odjemalec, {"vrsta": "merilo", "merilo": 1.3})          # na cetrtine navzdol
        self.assertEqual(self.z.drugi.merila[-1], 1.25)
        self.z._nastavi_merilo(odjemalec, {"vrsta": "merilo", "merilo": 99})           # najvec 3
        self.assertEqual(self.z.drugi.merila[-1], 3.0)
        stevilo = len(self.z.drugi.merila)
        for slabo in (None, "x", 0, -2, float("nan"), float("inf")):
            self.z._nastavi_merilo(odjemalec, {"vrsta": "merilo", "merilo": slabo})
        self.assertEqual(len(self.z.drugi.merila), stevilo)                              # nesmisel ne spremeni nicesar

    def test_merilo_pravega_zaslona_se_ne_spreminja(self):
        poslano = []
        odjemalec = types.SimpleNamespace(sendall=poslano.append)
        self.z.zacni("fon", "najvisja", "desktop", pogled={"w": 2340, "h": 1080, "density": 3.0, "kind": "phone"})
        self.z._nastavi_merilo(odjemalec, {"vrsta": "merilo", "merilo": 2.0})
        self.assertEqual(self.z.drugi.merila, [])
        self.assertEqual(poslano, [])

    def test_ukaz_screen_start_preda_povrsino(self):
        klici = []

        class Zaslon:
            drugi = None

            def na_voljo(self):
                return {"dovoljeno": True, "mozno": True}

            def zacni(self, posiljatelj, kakovost, cilj, **dodatno):
                klici.append((posiljatelj, kakovost, cilj, dodatno))
                return {"port": 1, "fp": "a" * 64, "token": "t"}

        izidi = []
        pogled = {"w": 2340, "h": 1080, "density": 3.0, "kind": "phone"}
        link_daljinec.izvedi_control("screen.start", {"quality": "najvisja", "screen": "apps", "view": pogled},
                                     lambda u: None, izidi.append, zaslon=Zaslon(), posiljatelj="fon")
        link_daljinec.izvedi_control("screen.start", {"quality": "najvisja", "screen": "apps", "relay": True},
                                     lambda u: None, izidi.append, zaslon=Zaslon(), posiljatelj="fon")
        link_daljinec.izvedi_control("screen.start", {"quality": "najvisja", "screen": "apps", "view": "2340x1080"},
                                     lambda u: None, izidi.append, zaslon=Zaslon(), posiljatelj="fon")
        self.assertTrue(all(i.get("ok") for i in izidi), izidi)
        self.assertEqual(klici[0][3], {"pogled": pogled})
        self.assertEqual(klici[1][3], {"prek_huba": True})
        self.assertEqual(klici[2][3], {})                        # neveljaven `view` se ne preda


class DrugiZaslonMerilo(unittest.TestCase):
    def test_osnovno_merilo_velja_za_navadne_programe(self):
        d = link_sway.DrugiZaslon(mapa="/nonexistent/safeer-test")
        ukazi = []
        d.tece = lambda: True
        d._msg = lambda argumenti, vrsta=None: ukazi.append(list(argumenti)) or ""
        d._spredaj = lambda: None
        d.okna = lambda: 0
        d.osnovno_merilo(2.0)
        self.assertEqual(ukazi[-1], ["output", link_sway.IZHOD, "scale", "2.000000"])
        d.osnovno_merilo(2.0)                                    # isto merilo: brez novega ukaza
        self.assertEqual(len(ukazi), 1)
        d.osnovno_merilo(1.0)
        self.assertEqual(ukazi[-1], ["output", link_sway.IZHOD, "scale", "1.000000"])
        d.osnovno_merilo(9)
        self.assertEqual(ukazi[-1], ["output", link_sway.IZHOD, "scale", "3.000000"])
        d.osnovno_merilo("x")
        self.assertEqual(ukazi[-1], ["output", link_sway.IZHOD, "scale", "1.000000"])


if __name__ == "__main__":
    unittest.main()
