"""Safeer Player (film v oknu GTK4): cel zaslon res cez ves zaslon in samo video.

Lastnik, 17. 11. 2026: »v Medijskem centru na Linuxu ne morem dati filma na pavzo in res cez celi zaslon«.
Izmerjeno na prenosniku (Cinnamon/Muffin): okno predvajalnika je prehodno (set_transient_for) in ima tip
_NET_WM_WINDOW_TYPE_DIALOG; po kliku »Cel zaslon« je ostalo brez _NET_WM_STATE_FULLSCREEN. Po umiku starsa je stanje
FULLSCREEN in tip NORMAL, po izhodu se stars vrne. Gumbi in drsnik se v celem zaslonu skrijejo (ob premiku miske za 3 s
pokazejo). Metode se klicejo nevezane na lazni self, zato ne potrebujejo zaslona."""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

import safeer_os  # noqa: E402

SO = safeer_os.SafeerOS


class LaznoOkno:
    def __init__(self, stars=None):
        self.stars, self.cel, self.zapis = stars, False, []

    def get_transient_for(self):
        return self.stars

    def set_transient_for(self, stars):
        self.zapis.append(("stars", stars))
        self.stars = stars

    def fullscreen(self):
        self.zapis.append(("fullscreen", self.stars))
        self.cel = True

    def unfullscreen(self):
        self.zapis.append(("unfullscreen", self.stars))
        self.cel = False

    def is_fullscreen(self):
        return self.cel


class StarsOdMaknjenPredCelimZaslonom(unittest.TestCase):
    def test_stars_se_umakne_pred_celim_zaslonom_in_vrne_po_izhodu(self):
        stars = object()
        okno = LaznoOkno(stars)
        SO._nastavi_cel_zaslon_okna(okno, True)
        self.assertEqual(okno.zapis, [("stars", None), ("fullscreen", None)],
                         "fullscreen() mora biti klican, ko okno ze nima starsa (tip DIALOG Muffin ne razsiri)")
        SO._nastavi_cel_zaslon_okna(okno, False)
        self.assertIs(okno.stars, stars)
        self.assertEqual(okno.zapis[2][0], "unfullscreen")
        self.assertEqual(okno.zapis[-1], ("stars", stars))

    def test_okno_brez_starsa_gre_v_cel_zaslon_in_nazaj(self):
        okno = LaznoOkno(None)
        SO._nastavi_cel_zaslon_okna(okno, True)
        SO._nastavi_cel_zaslon_okna(okno, False)
        self.assertEqual([z[0] for z in okno.zapis], ["fullscreen", "unfullscreen"])
        self.assertIsNone(okno.stars)

    def test_preklop_cel_zaslon_gumb_f11_dvojni_klik(self):
        stars = object()
        okno = LaznoOkno(stars)
        sam = SimpleNamespace(_nastavi_cel_zaslon_okna=SO._nastavi_cel_zaslon_okna)
        self.assertTrue(SO._medijski_cel_zaslon(sam, okno))
        self.assertTrue(okno.cel)
        self.assertIsNone(okno.stars)
        self.assertTrue(SO._medijski_cel_zaslon(sam, okno))
        self.assertFalse(okno.cel)
        self.assertIs(okno.stars, stars)


class LazenGradnik:
    def __init__(self):
        self.vidno, self.robovi = True, {}

    def set_visible(self, v):
        self.vidno = v

    def __getattr__(self, ime):
        if ime.startswith("set_margin_"):
            return lambda v: self.robovi.__setitem__(ime[11:], v)
        raise AttributeError(ime)


class UpravljanjeVCelemZaslonu(unittest.TestCase):
    def setUp(self):
        self.gradniki = [LazenGradnik() for _ in range(4)]
        self.postavitev = LazenGradnik()
        self.sam = SimpleNamespace(_medijski_upravljanje=self.gradniki, _medijski_postavitev=self.postavitev,
                                   _medijski_cel_casovnik=0, _medijski_zadnja_miska=(0.0, 0.0))

    def test_cel_zaslon_skrije_upravljanje_in_robove(self):
        SO._medijski_upravljanje_cel_zaslon(self.sam, _cel())
        self.assertTrue(all(not g.vidno for g in self.gradniki))
        self.assertEqual(set(self.postavitev.robovi.values()), {0})

    def test_izhod_iz_celega_zaslona_vrne_upravljanje_in_robove(self):
        SO._medijski_upravljanje_cel_zaslon(self.sam, _cel())
        SO._medijski_upravljanje_cel_zaslon(self.sam, _okno_ni_cel())
        self.assertTrue(all(g.vidno for g in self.gradniki))
        self.assertEqual(set(self.postavitev.robovi.values()), {16})

    def test_pokazi_za_hip_samo_v_celem_zaslonu_in_skrije_po_3_s(self):
        casovnik = {}
        sam = self.sam
        sam._medijski_upravljanje_cel_zaslon = lambda okno, pokazi=None: SO._medijski_upravljanje_cel_zaslon(sam, okno, pokazi)
        with mock.patch.object(safeer_os.GLib, "timeout_add_seconds",
                               side_effect=lambda s, f: casovnik.update(s=s, f=f) or 7), \
                mock.patch.object(safeer_os.GLib, "source_remove"):
            SO._medijski_pokazi_upravljanje_za_hip(sam, _okno_ni_cel())
            self.assertEqual(casovnik, {}, "zunaj celega zaslona casovnik ne tece")
            cel = _cel()
            SO._medijski_pokazi_upravljanje_za_hip(sam, cel)
            self.assertTrue(all(g.vidno for g in self.gradniki))
            self.assertEqual(casovnik["s"], 3)
            casovnik["f"]()                              # po 3 s
            self.assertTrue(all(not g.vidno for g in self.gradniki))

    def test_gib_pod_mirujoco_misko_ne_pokaze_upravljanja(self):
        """GTK4 ob spremembi gradnikov pod mirujoco misko sam poslje »motion«: skrito upravljanje ostane skrito."""
        klici = []
        sam = SimpleNamespace(_medijski_zadnja_miska=(100.0, 100.0),
                              _medijski_pokazi_upravljanje_za_hip=lambda okno: klici.append(okno))
        SO._medijski_miska_se_je_premaknila(sam, "o", 100.0, 101.0)
        self.assertEqual(klici, [])
        SO._medijski_miska_se_je_premaknila(sam, "o", 140.0, 160.0)
        self.assertEqual(klici, ["o"])


def _cel():
    o = LaznoOkno(None)
    o.cel = True
    return o


def _okno_ni_cel():
    return LaznoOkno(None)


if __name__ == "__main__":
    unittest.main()
