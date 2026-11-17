"""Zaslon X11 se med sejo spremeni (pokrov prenosnika zaprt, monitor odklopljen): seja ne sme posiljati napacnega izreza.

Izmerjeno 17. 11. 2026: ob zacetku seje je ffmpeg dobil `-video_size 1920x1080 -i :0`; po zaprtju pokrova je X ostal
samo s HDMI-1 (2560x1440), zajem pa je se vedno jemal 1920x1080 od zgoraj levo - televizor je kazal povecan izrez, vnos
pa bi zadel napacne tocke. Straza seje zato primerja zajeto geometrijo z zacetno in sejo konca z `zaslon_spremenjen`.
"""
import inspect
import threading
import unittest
from unittest import mock

from core import link_zaslon

ZACETNA = (":0", (1920, 1080), (0, 0))
NOVA = ((2560, 1440), (0, 0))
ENAKA = ((1920, 1080), (0, 0))


def _zaslon(seja=4):
    z = link_zaslon.Zaslon(vklopljeno=True)
    z._seja_st = seja
    z.ustavi = mock.Mock()
    return z


def _zazeni(z, meritve, seja=4):
    """Straza tece z zaporedjem meritev; po zadnji meritvi sejo ustavimo (konec seje)."""
    konec = threading.Event()
    zaporedje = list(meritve)

    def meritev(display):
        if not zaporedje:
            konec.set()
            return ENAKA
        return zaporedje.pop(0)

    with mock.patch.object(link_zaslon, "GEOMETRIJA_PREVERI_S", 0.01), \
            mock.patch.object(link_zaslon, "_geometrija_zajema", side_effect=meritev), \
            mock.patch("builtins.print"):
        nit = threading.Thread(target=z._strazi_geometrijo, args=(seja, konec, ZACETNA), daemon=True)
        nit.start()
        nit.join(3.0)
    konec.set()
    return nit


class StrazaGeometrije(unittest.TestCase):
    def test_trajna_sprememba_konca_sejo_z_razlogom(self):
        z = _zaslon()
        nit = _zazeni(z, [NOVA, NOVA, NOVA])
        self.assertFalse(nit.is_alive())
        z.ustavi.assert_called_once_with(seja=4, obvestilo={"konec": "zaslon_spremenjen"})

    def test_enkraten_preskok_ne_konca_seje(self):
        z = _zaslon()
        _zazeni(z, [NOVA, ENAKA, ENAKA, NOVA, ENAKA])
        z.ustavi.assert_not_called()

    def test_nespremenjen_zaslon_ne_konca_seje(self):
        z = _zaslon()
        _zazeni(z, [ENAKA] * 6)
        z.ustavi.assert_not_called()

    def test_zaslona_ni_mogoce_izmeriti_ne_sklepamo(self):
        z = _zaslon()
        _zazeni(z, [None] * 6)
        z.ustavi.assert_not_called()

    def test_sprememba_odmika_je_sprememba(self):
        z = _zaslon()
        _zazeni(z, [((1920, 1080), (2560, 0))] * 3)
        z.ustavi.assert_called_once()

    def test_druga_seja_ni_nasa(self):
        z = _zaslon(seja=9)
        _zazeni(z, [NOVA, NOVA, NOVA], seja=4)
        z.ustavi.assert_not_called()


class GeometrijaZajema(unittest.TestCase):
    def test_vec_monitorjev_primarni(self):
        monitor = {"sirina": 2560, "visina": 1440, "x": 0, "y": 0}
        with mock.patch.object(link_zaslon, "_deljeni_monitor", return_value=monitor):
            self.assertEqual(link_zaslon._geometrija_zajema(":0"), ((2560, 1440), (0, 0)))

    def test_en_monitor_ves_zaslon(self):
        with mock.patch.object(link_zaslon, "_deljeni_monitor", return_value=None), \
                mock.patch.object(link_zaslon, "_zaslon_geometrija", return_value=(2560, 1440)):
            self.assertEqual(link_zaslon._geometrija_zajema(":0"), ((2560, 1440), (0, 0)))

    def test_brez_meritve_none(self):
        with mock.patch.object(link_zaslon, "_deljeni_monitor", return_value=None), \
                mock.patch.object(link_zaslon, "_zaslon_geometrija", return_value=None):
            self.assertIsNone(link_zaslon._geometrija_zajema(":0"))

    def test_napaka_x_none(self):
        with mock.patch.object(link_zaslon, "_deljeni_monitor", side_effect=OSError("X")):
            self.assertIsNone(link_zaslon._geometrija_zajema(":0"))


class Napeljava(unittest.TestCase):
    """Straza mora biti res priklopljena v sejo X11 (brez tega bi bili zgornji preizkusi brez ucinka)."""

    def test_seja_zazene_strazo_in_zapomni_zacetno_geometrijo(self):
        vir = inspect.getsource(link_zaslon.Zaslon)
        self.assertIn("self._geometrija_x11 = (display, (int(izvor[0]), int(izvor[1])), "
                      "(int(odmik[0]), int(odmik[1])))", vir)
        self.assertIn("target=self._strazi_geometrijo", vir)
        self.assertIn('getattr(self, "_geometrija_x11", None) is not None', vir)


if __name__ == "__main__":
    unittest.main()
