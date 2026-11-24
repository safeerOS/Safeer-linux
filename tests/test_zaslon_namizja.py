"""Glavni zaslon pripada racunalniku (lastnik, 24. 11. 2026 ~20:15).

»samo ko je prenos slike preko linka je lahko naprava katera predvaja glavni zaslon; v vsakem drugacnem primeru se glavni
zaslon vrne napravi kateri pripada«. Pri prenosniku je to vgrajen zaslon (eDP/LVDS/DSI): namizje Safeer OS, pult
Cinnamona in dock so tam, tudi ce je TV na HDMI primarni (prej: TV v mirovanju je imel namizje, prenosnik samo ozadje).
Pokrov zaprt ali namizni PC (vgrajenega ni): ostane dosedanji primarni. Med prenosom slike prek Linka se nic ne spremeni."""

import unittest

from core import zaslon_namizja as zn

XRANDR = (
    "Screen 0: minimum 320 x 200, current 5760 x 2160, maximum 16384 x 16384\n"
    "eDP-1 connected 1920x1080+3840+0 (normal left inverted right x axis y axis) 344mm x 193mm\n"
    "   1920x1080     60.02*+\n"
    "HDMI-1 connected primary 3840x2160+0+0 (normal left inverted right x axis y axis) 1440mm x 810mm\n"
    "   3840x2160     60.00*+\n"
    "DP-1 disconnected (normal left inverted right x axis y axis)\n"
    "DP-2 connected (normal left inverted right x axis y axis)\n"
)


def _izhodi(primarni="HDMI-1", vgrajen=True, pokrov_zaprt=False):
    seznam = []
    if vgrajen:
        seznam.append({"ime": "eDP-1", "primarni": primarni == "eDP-1", "aktiven": not pokrov_zaprt})
    seznam.append({"ime": "HDMI-1", "primarni": primarni == "HDMI-1", "aktiven": True})
    return seznam


class _Shramba(dict):
    def set(self, kljuc, vrednost):
        self[kljuc] = vrednost


class Razclenitev(unittest.TestCase):
    def test_xrandr_izhodi(self):
        izhodi = zn.razcleni_xrandr(XRANDR)
        self.assertEqual([(i["ime"], i["primarni"], i["aktiven"]) for i in izhodi],
                         [("eDP-1", False, True), ("HDMI-1", True, True), ("DP-1", False, False),
                          ("DP-2", False, False)])

    def test_vgrajen_izhod(self):
        for ime in ("eDP-1", "eDP1", "LVDS-1", "DSI-1"):
            self.assertTrue(zn.je_vgrajen(ime), ime)
        for ime in ("HDMI-1", "DP-1", "HDMI-A-0", ""):
            self.assertFalse(zn.je_vgrajen(ime), ime)

    def test_ime_izhoda_za_xrandr(self):
        self.assertTrue(zn.varno_ime("HDMI-A-0"))
        for ime in ("-primary", "", "a b", "x" * 40, None):
            self.assertFalse(zn.varno_ime(ime), ime)

    def test_nastavitev(self):
        self.assertEqual(zn.nastavitev(None), "samodejno")
        self.assertEqual(zn.nastavitev("x"), "samodejno")
        self.assertEqual(zn.nastavitev("prenosnik"), "samodejno")     # nastavitev prve razlicice: zdaj pravilo
        self.assertEqual(zn.nastavitev("glavni"), "glavni")


class Izbira(unittest.TestCase):
    def test_vgrajen_je_glavni_zaslon(self):
        self.assertEqual(zn.izberi(_izhodi(), "samodejno"), "eDP-1")

    def test_pokrov_zaprt_ostane_primarni(self):
        self.assertEqual(zn.izberi(_izhodi(pokrov_zaprt=True), "samodejno"), "HDMI-1")

    def test_namizni_racunalnik(self):
        self.assertEqual(zn.izberi(_izhodi(vgrajen=False), "samodejno"), "HDMI-1")

    def test_vedno_na_glavnem(self):
        self.assertEqual(zn.izberi(_izhodi(), "glavni"), "HDMI-1")


class Straza(unittest.TestCase):
    """Cikel v glavnem procesu: primarni izhod RandR na vgrajen zaslon (pult Cinnamona in dock Plank mu sledita) in
    lupini pove, kje naj bo namizje; med prenosom slike prek Linka nic."""

    def setUp(self):
        self.primarni = "HDMI-1"
        self.pokrov_zaprt = False
        self.seja = False
        self.preklopi = []
        self.izbire = []
        self.shramba = _Shramba()

        def nastavi(ime):
            self.preklopi.append(ime)
            self.primarni = ime
            return True

        self.s = zn.Straza(lambda: _izhodi(self.primarni, pokrov_zaprt=self.pokrov_zaprt), lambda: self.seja, nastavi,
                           self.izbire.append, self.shramba)

    def test_hdmi_primarni_namizje_na_prenosnik(self):
        self.s.korak()
        self.assertEqual(self.preklopi, ["eDP-1"])
        self.assertEqual(self.izbire, ["eDP-1"])
        self.assertEqual(self.shramba.get("namizje_zaslon_prej"), {"glavni": "HDMI-1", "vgrajen": "eDP-1"})

    def test_pokrov_zaprt_ostane(self):
        self.pokrov_zaprt = True
        self.s.korak()
        self.assertEqual(self.preklopi, [])
        self.assertEqual(self.izbire, ["HDMI-1"])

    def test_pokrov_zaprt_x_pusti_ugasnjen_primarni(self):
        # X ugasnjenega eDP pusti kot primarnega: ne prestavljamo na HDMI in si ne zapisemo napacnega »prejsnjega«.
        self.primarni = "eDP-1"
        self.pokrov_zaprt = True
        self.s.korak()
        self.assertEqual((self.preklopi, self.izbire), ([], ["HDMI-1"]))
        self.assertIsNone(self.shramba.get("namizje_zaslon_prej"))

    def test_seja_linka_brez_spremembe_po_koncu_vgrajen(self):
        self.seja = True
        self.s.korak()
        self.assertEqual((self.preklopi, self.izbire), ([], []))
        self.seja = False
        self.s.korak()
        self.assertEqual((self.preklopi, self.izbire), (["eDP-1"], ["eDP-1"]))

    def test_vedno_na_glavnem_se_ne_vmesava(self):
        self.shramba.set("namizje_zaslon", "glavni")
        self.s.korak()
        self.assertEqual((self.preklopi, self.izbire), ([], ["HDMI-1"]))

    def test_vedno_na_glavnem_vrne_nas_preklop(self):
        self.s.korak()
        self.shramba.set("namizje_zaslon", "glavni")
        self.s.korak()
        self.assertEqual(self.preklopi, ["eDP-1", "HDMI-1"])
        self.assertEqual(self.izbire[-1], "HDMI-1")
        self.assertIsNone(self.shramba.get("namizje_zaslon_prej"))

    def test_primarni_spet_na_hdmi_se_vrne(self):
        self.s.korak()
        self.primarni = "HDMI-1"          # Muffin ob ponovnem priklopu ali uporabnik v Nastavitvah zaslona
        self.s.korak()
        self.assertEqual(self.preklopi, ["eDP-1", "eDP-1"])
        self.assertEqual(self.shramba.get("namizje_zaslon_prej"), {"glavni": "HDMI-1", "vgrajen": "eDP-1"})

    def test_primarni_ze_vgrajen(self):
        self.primarni = "eDP-1"
        self.s.korak()
        self.assertEqual((self.preklopi, self.izbire), ([], ["eDP-1"]))
        self.assertIsNone(self.shramba.get("namizje_zaslon_prej"))

    def test_neuspel_xrandr_ne_vsake_3_s(self):
        poskusi = []
        self.s.nastavi_primarni = lambda ime: poskusi.append(ime) and False
        for _ in range(11):
            self.s.korak()
        self.assertEqual(len(poskusi), 1)
        self.s.korak()
        self.assertEqual(len(poskusi), 2)

    def test_nazaj_v_mint_vrne_primarni(self):
        self.s.korak()
        self.s.vrni()
        self.assertEqual(self.preklopi, ["eDP-1", "HDMI-1"])
        self.assertIsNone(self.shramba.get("namizje_zaslon_prej"))

    def test_hdmi_odklopljen_pozabi(self):
        self.s.korak()
        self.s.beri_izhode = lambda: [i for i in _izhodi(self.primarni) if i["ime"] != "HDMI-1"]
        self.s.korak()
        self.assertIsNone(self.shramba.get("namizje_zaslon_prej"))
        self.s.vrni()
        self.assertEqual(self.preklopi, ["eDP-1"])

    def test_izbira_samo_ob_spremembi(self):
        self.s.korak()
        self.s.korak()
        self.assertEqual(self.izbire, ["eDP-1"])


class _Zaslon:
    def __init__(self, ime):
        self._ime = ime

    def name(self):
        return self._ime


class Lupina(unittest.TestCase):
    """Namizje QML je v procesu lupine: izbiro dobi kot ukaz »zaslon« (tudi ob vsaki novi povezavi)."""

    def test_qscreen_po_imenu(self):
        from core import os_lupina
        edp, hdmi = _Zaslon("eDP-1"), _Zaslon("HDMI-1")
        self.assertIs(os_lupina.zaslon_po_imenu([hdmi, edp], "eDP-1", hdmi), edp)
        self.assertIs(os_lupina.zaslon_po_imenu([hdmi, edp], "", hdmi), hdmi)
        self.assertIs(os_lupina.zaslon_po_imenu([hdmi], "eDP-1", hdmi), hdmi)      # izhoda ni vec: primarni

    def test_isti_zaslon_brez_ponovnega_docka(self):
        from unittest import mock
        from core import os_lupina
        edp, hdmi = _Zaslon("eDP-1"), _Zaslon("HDMI-1")
        namizje = os_lupina.Namizje.__new__(os_lupina.Namizje)
        namizje.v_oknu = False
        klici = []
        namizje._zaslon_spremenjen = lambda: klici.append(os_lupina._IZHOD_NAMIZJA)
        with mock.patch.object(os_lupina, "_IZHOD_NAMIZJA", ""), \
                mock.patch.object(os_lupina, "zaslon_namizja",
                                  side_effect=lambda: edp if os_lupina._IZHOD_NAMIZJA == "eDP-1" else hdmi):
            namizje.nastavi_zaslon("HDMI-1")        # primarni kot doslej: dock ostane
            namizje.nastavi_zaslon("eDP-1")         # vgrajen: namizje in dock na prenosnik
            namizje.nastavi_zaslon("eDP-1")
        self.assertEqual(klici, ["eDP-1"])

    def test_streznik_poslje_ukaz_zaslon(self):
        from core import lupina_most, lupina_streznik
        lupina = lupina_streznik.OddaljenaLupina.__new__(lupina_streznik.OddaljenaLupina)
        poslano = []
        lupina.poslji = poslano.append
        lupina.nastavi_zaslon("eDP-1")
        okvirji = lupina_most.Dekoder().dodaj(poslano[0])
        self.assertEqual(lupina_most.razcleni(*okvirji[0]), ("U", {"u": "zaslon", "ime": "eDP-1"}))

    def test_lupina_izvede_ukaz_zaslon(self):
        from core import lupina_proces
        klici = []

        class _L:
            most = None

            def nastavi_zaslon(self, ime):
                klici.append(ime)

        odjemalec = lupina_proces.Odjemalec.__new__(lupina_proces.Odjemalec)
        odjemalec.lupina = _L()
        odjemalec._okvir("U", {"u": "zaslon", "ime": "eDP-1"})
        odjemalec._okvir("U", {"u": "zaslon", "ime": 5})               # napacna oblika: nic
        self.assertEqual(klici, ["eDP-1"])


if __name__ == "__main__":
    unittest.main()
