"""Namizje na zaslonu, ki ga uporabnik vidi (lastnik, 24. 11. 2026).

Prenosnik + TV na HDMI (primarni). TV v mirovanju: X11 tega ne vidi (HDMI ostane »connected«, DPMS On, CEC ni), zato je
bilo namizje QML (pult, dock, okna) na ugasnjenem TV, prenosnik je kazal samo ozadje. Vir stanja je TV sam (Safeer Link,
host.info -> zaslon.prizgan); ujemanje izhoda s TV po znamki iz EDID (PNP »PHL«, ime »Philips FTV«)."""

import unittest

from core import zaslon_namizja as zn


def _edid(pnp: str, ime: str) -> bytes:
    """Najmanjsi EDID 1.3: glava, proizvajalec (3 crke po 5 bitov) in opisnik imena monitorja (0xFC)."""
    e = bytearray(128)
    e[0:8] = b"\x00\xff\xff\xff\xff\xff\xff\x00"
    v = ((ord(pnp[0]) - 64) << 10) | ((ord(pnp[1]) - 64) << 5) | (ord(pnp[2]) - 64)
    e[8], e[9] = v >> 8, v & 0xFF
    e[54:59] = b"\x00\x00\x00\xfc\x00"
    e[59:72] = (ime.encode("ascii") + b"\n").ljust(13, b" ")
    for z in (72, 90, 108):
        e[z:z + 5] = b"\x00\x00\x00\x10\x00"         # prazni opisniki
    return bytes(e)


def _hex(b: bytes) -> str:
    return "".join("\t\t" + b[i:i + 16].hex() + "\n" for i in range(0, len(b), 16))


XRANDR = (
    "Screen 0: minimum 320 x 200, current 5760 x 2160, maximum 16384 x 16384\n"
    "eDP-1 connected 1920x1080+3840+0 (normal left inverted right x axis y axis) 344mm x 193mm\n"
    "\t_MUFFIN_PRESENTATION_OUTPUT: 0 \n"
    "\tEDID: \n" + _hex(_edid("BOE", "NT156FHM-N61")) +
    "\tvrr_capable: 0 \n\t\trange: (0, 1)\n"
    "   1920x1080     60.02*+\n"
    "HDMI-1 connected primary 3840x2160+0+0 (normal left inverted right x axis y axis) 1440mm x 810mm\n"
    "\tEDID: \n" + _hex(_edid("PHL", "Philips FTV") + bytes(128)) +
    "\tmax bpc: 12 \n"
    "   3840x2160     60.00*+\n"
    "DP-1 disconnected (normal left inverted right x axis y axis)\n"
)


def _izhodi(primarni="HDMI-1", tv=("PHL", "Philips FTV"), vgrajen=True):
    seznam = []
    if vgrajen:
        seznam.append({"ime": "eDP-1", "primarni": primarni == "eDP-1", "aktiven": True,
                       "pnp": "BOE", "model": "NT156FHM-N61"})
    seznam.append({"ime": "HDMI-1", "primarni": primarni == "HDMI-1", "aktiven": True, "pnp": tv[0], "model": tv[1]})
    return seznam


class _Shramba(dict):
    def set(self, kljuc, vrednost):
        self[kljuc] = vrednost


PHILIPS_UGASNJEN = [{"id": "tv1", "znamka": "Philips", "prizgan": False}]
PHILIPS_PRIZGAN = [{"id": "tv1", "znamka": "Philips", "prizgan": True}]


class Razclenitev(unittest.TestCase):
    def test_edid_pnp_in_ime(self):
        self.assertEqual(zn.edid_podatki(_edid("PHL", "Philips FTV")), {"pnp": "PHL", "model": "Philips FTV"})

    def test_edid_pokvarjen(self):
        self.assertEqual(zn.edid_podatki(b"\x00\x01"), {"pnp": "", "model": ""})

    def test_xrandr_izhodi(self):
        izhodi = zn.razcleni_xrandr(XRANDR)
        self.assertEqual([i["ime"] for i in izhodi], ["eDP-1", "HDMI-1", "DP-1"])
        edp, hdmi, dp = izhodi
        self.assertFalse(edp["primarni"])
        self.assertTrue(hdmi["primarni"])
        self.assertEqual((hdmi["pnp"], hdmi["model"]), ("PHL", "Philips FTV"))
        self.assertTrue(edp["aktiven"] and hdmi["aktiven"])
        self.assertFalse(dp["aktiven"])

    def test_vgrajen_izhod(self):
        for ime in ("eDP-1", "eDP1", "LVDS-1", "DSI-1"):
            self.assertTrue(zn.je_vgrajen(ime), ime)
        for ime in ("HDMI-1", "DP-1", "HDMI-A-0", ""):
            self.assertFalse(zn.je_vgrajen(ime), ime)

    def test_znamka_iz_pnp_ali_imena(self):
        self.assertEqual(zn.znamka_izhoda({"pnp": "PHL", "model": ""}), "philips")
        self.assertEqual(zn.znamka_izhoda({"pnp": "SEC", "model": ""}), "samsung")
        self.assertEqual(zn.znamka_izhoda({"pnp": "GSM", "model": "LG TV"}), "lg")
        self.assertEqual(zn.znamka_izhoda({"pnp": "XYZ", "model": "SONY TV"}), "sony")
        self.assertEqual(zn.znamka_izhoda({"pnp": "XYZ", "model": "Monitor"}), "")


class Izbira(unittest.TestCase):
    def test_tv_ugasnjen_prenosnik(self):
        self.assertEqual(zn.izberi(_izhodi(), PHILIPS_UGASNJEN, "samodejno"), "eDP-1")

    def test_tv_prizgan_ostane_primarni(self):
        self.assertEqual(zn.izberi(_izhodi(), PHILIPS_PRIZGAN, "samodejno"), "HDMI-1")

    def test_neznano_ostane_primarni(self):
        # Starejsi TV brez polja zaslon (prizgan None), TV ne odgovori ali TV v Linku ni.
        self.assertEqual(zn.izberi(_izhodi(), [{"id": "tv1", "znamka": "Philips", "prizgan": None}], "samodejno"),
                         "HDMI-1")
        self.assertEqual(zn.izberi(_izhodi(), [], "samodejno"), "HDMI-1")

    def test_druga_znamka_ni_nas_tv(self):
        samsung = [{"id": "tv2", "znamka": "Samsung", "prizgan": False}]
        self.assertEqual(zn.izberi(_izhodi(), samsung, "samodejno"), "HDMI-1")

    def test_dva_tv_iste_znamke_ni_zanesljivo(self):
        dva = PHILIPS_UGASNJEN + [{"id": "tv2", "znamka": "Philips", "prizgan": False}]
        self.assertEqual(zn.izberi(_izhodi(), dva, "samodejno"), "HDMI-1")

    def test_pokrov_zaprt(self):
        self.assertEqual(zn.izberi(_izhodi(vgrajen=False), PHILIPS_UGASNJEN, "samodejno"), "HDMI-1")

    def test_nastavitev_prenosnik_in_glavni(self):
        self.assertEqual(zn.izberi(_izhodi(), PHILIPS_PRIZGAN, "prenosnik"), "eDP-1")
        self.assertEqual(zn.izberi(_izhodi(), PHILIPS_UGASNJEN, "glavni"), "HDMI-1")
        self.assertEqual(zn.izberi(_izhodi(vgrajen=False), [], "prenosnik"), "HDMI-1")

    def test_neznana_nastavitev_je_samodejno(self):
        self.assertEqual(zn.nastavitev("x"), "samodejno")
        self.assertEqual(zn.nastavitev(None), "samodejno")
        self.assertEqual(zn.nastavitev("prenosnik"), "prenosnik")

    def test_preverjanje_samo_ko_je_primarni_zunanji_tv(self):
        self.assertTrue(zn.potrebno_preverjanje(_izhodi(), "HDMI-1"))
        self.assertFalse(zn.potrebno_preverjanje(_izhodi(primarni="eDP-1"), "eDP-1"))
        self.assertFalse(zn.potrebno_preverjanje(_izhodi(vgrajen=False), "HDMI-1"))
        self.assertFalse(zn.potrebno_preverjanje(_izhodi(tv=("DEL", "DELL U2720Q")), "HDMI-1"))


class Straza(unittest.TestCase):
    """Cikel v glavnem procesu: prebere izhode in TV, po potrebi prestavi primarni izhod RandR (pult Cinnamona in dock
    Plank sledita primarnemu) in pove lupini, kje naj bo namizje."""

    def setUp(self):
        self.primarni = "HDMI-1"
        self.tv = list(PHILIPS_PRIZGAN)
        self.klici_tv = 0
        self.preklopi = []
        self.izbire = []
        self.shramba = _Shramba()

        def beri_tv():
            self.klici_tv += 1
            return self.tv

        def nastavi(ime):
            self.preklopi.append(ime)
            self.primarni = ime
            return True

        self.s = zn.Straza(lambda: _izhodi(self.primarni), beri_tv, nastavi,
                           lambda ime, speci: self.izbire.append((ime, tuple(speci))), self.shramba)

    def test_ugasnem_tv_in_ga_prizgem(self):
        self.s.korak()
        self.assertEqual(self.preklopi, [])
        self.assertEqual(self.izbire[-1], ("HDMI-1", ()))
        self.tv = list(PHILIPS_UGASNJEN)
        self.s.korak()
        self.assertEqual(self.preklopi, ["eDP-1"])
        self.assertEqual(self.izbire[-1], ("eDP-1", ("HDMI-1",)))
        self.assertEqual(self.shramba["namizje_zaslon_prej"], {"glavni": "HDMI-1", "vgrajen": "eDP-1"})
        self.tv = list(PHILIPS_PRIZGAN)
        self.s.korak()
        self.assertEqual(self.preklopi, ["eDP-1", "HDMI-1"])
        self.assertEqual(self.izbire[-1], ("HDMI-1", ()))
        self.assertIsNone(self.shramba.get("namizje_zaslon_prej"))

    def test_tv_v_mirovanju_izgine_iz_omrezja_namizje_ostane(self):
        self.tv = list(PHILIPS_UGASNJEN)
        self.s.korak()
        self.tv = []                    # TV po nekaj minutah mirovanja ne odgovarja vec
        self.s.korak()
        self.assertEqual(self.preklopi, ["eDP-1"])
        self.assertEqual(self.izbire[-1][0], "eDP-1")

    def test_uporabnik_sam_zamenja_primarni(self):
        self.tv = list(PHILIPS_UGASNJEN)
        self.s.korak()
        self.primarni = "HDMI-1"        # uporabnik v Nastavitvah zaslona izbere TV za glavnega
        self.tv = list(PHILIPS_PRIZGAN)
        self.s.korak()
        self.assertEqual(self.preklopi, ["eDP-1"])        # ne vracamo in ne bijemo se z uporabnikom
        self.assertIsNone(self.shramba.get("namizje_zaslon_prej"))

    def test_primarni_nazaj_na_tv_ki_spi(self):
        # Primarni se vrne na TV (uporabnik ali muffin), TV pa se vedno spi ali ne odgovarja: zadrzanje ostane.
        for tv in (list(PHILIPS_UGASNJEN), []):
            self.setUp()
            self.tv = list(PHILIPS_UGASNJEN)
            self.s.korak()
            self.primarni = "HDMI-1"
            self.tv = tv
            self.s.korak()
            self.assertEqual(self.preklopi, ["eDP-1", "eDP-1"])
            self.assertEqual(self.shramba.get("namizje_zaslon_prej"), {"glavni": "HDMI-1", "vgrajen": "eDP-1"})
            self.assertEqual(self.izbire[-1], ("eDP-1", ("HDMI-1",)))

    def test_tv_odklopljen_pozabi(self):
        self.tv = list(PHILIPS_UGASNJEN)
        self.s.korak()
        self.s.beri_izhode = lambda: [i for i in _izhodi(self.primarni) if i["ime"] != "HDMI-1"]
        self.s.korak()
        self.assertIsNone(self.shramba.get("namizje_zaslon_prej"))
        self.assertEqual(self.izbire[-1], ("eDP-1", ()))

    def test_brez_tv_izhoda_ne_sprasuje_naprav(self):
        self.primarni = "eDP-1"
        self.s.korak()
        self.assertEqual(self.klici_tv, 0)

    def test_nastavitev_glavni_vrne_preklop(self):
        self.tv = list(PHILIPS_UGASNJEN)
        self.s.korak()
        self.shramba.set("namizje_zaslon", "glavni")
        self.s.korak()
        self.assertEqual(self.preklopi, ["eDP-1", "HDMI-1"])
        self.assertEqual(self.izbire[-1], ("HDMI-1", ()))

    def test_nastavitev_prenosnik_ne_menja_primarnega(self):
        self.shramba.set("namizje_zaslon", "prenosnik")
        self.s.korak()
        self.assertEqual(self.preklopi, [])
        self.assertEqual(self.izbire[-1], ("eDP-1", ()))

    def test_izbira_samo_ob_spremembi(self):
        self.s.korak()
        self.s.korak()
        self.assertEqual(len(self.izbire), 1)


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
        with mock.patch.object(os_lupina, "_IZHOD_NAMIZJA", ""), mock.patch.object(os_lupina, "_SPECI", frozenset()), \
                mock.patch.object(os_lupina, "zaslon_namizja",
                                  side_effect=lambda: edp if os_lupina._IZHOD_NAMIZJA == "eDP-1" else hdmi):
            namizje.nastavi_zaslon("HDMI-1", [])            # primarni kot doslej: dock ostane
            namizje.nastavi_zaslon("eDP-1", ["HDMI-1"])     # TV spi: namizje in dock na prenosnik
            namizje.nastavi_zaslon("eDP-1", ["HDMI-1"])
        self.assertEqual(klici, ["eDP-1"])

    def test_streznik_poslje_ukaz_zaslon(self):
        from core import lupina_most, lupina_streznik
        lupina = lupina_streznik.OddaljenaLupina.__new__(lupina_streznik.OddaljenaLupina)
        poslano = []
        lupina.poslji = poslano.append
        lupina.nastavi_zaslon("eDP-1", ["HDMI-1"])
        okvirji = lupina_most.Dekoder().dodaj(poslano[0])
        self.assertEqual(lupina_most.razcleni(*okvirji[0]), ("U", {"u": "zaslon", "ime": "eDP-1", "speci": ["HDMI-1"]}))

    def test_lupina_izvede_ukaz_zaslon(self):
        from core import lupina_proces
        klici = []

        class _L:
            most = None

            def nastavi_zaslon(self, ime, speci):
                klici.append((ime, speci))

        odjemalec = lupina_proces.Odjemalec.__new__(lupina_proces.Odjemalec)
        odjemalec.lupina = _L()
        odjemalec._okvir("U", {"u": "zaslon", "ime": "eDP-1", "speci": ["HDMI-1"]})
        odjemalec._okvir("U", {"u": "zaslon", "ime": "eDP-1", "speci": "HDMI-1"})       # napacna oblika: nic
        self.assertEqual(klici, [("eDP-1", ["HDMI-1"])])


if __name__ == "__main__":
    unittest.main()
