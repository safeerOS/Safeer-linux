"""Glavni zaslon (24. 11. 2026): seja prenosa slike prek Linka v Safeer OS (safeer_os._seja_zaslona_linka). Loceno od
cistih pravil (tests/test_zaslon_namizja.py), ker uvoz safeer_os rabi nas WebKit (tools/pozeni-preizkuse.sh)."""

import unittest
from unittest import mock


class _Zaslon:
    def __init__(self, tece):
        self._tece = tece

    def stanje(self):
        return {"tece": self._tece, "povezan": False}


class _Deljenje:
    def __init__(self, tece):
        self.tece = tece


class _Link:
    def __init__(self, deljenje):
        self.deljenje_zaslona = deljenje


class _Control:
    def __init__(self, zaslon=None, link=None):
        self.zaslon = zaslon
        self.link = link


class SejaLinka(unittest.TestCase):
    """Med prenosom slike prek Linka (druga naprava gleda ta zaslon ali racunalnik posilja zaslon) Straza primarnega
    izhoda ne spreminja; brez seje velja pravilo (vgrajen zaslon)."""

    def _seja(self, control):
        import safeer_os
        with mock.patch.object(safeer_os.en_proces, "control_app", return_value=control):
            return safeer_os._seja_zaslona_linka()

    def test_brez_seje(self):
        self.assertFalse(self._seja(_Control(_Zaslon(False), _Link(None))))
        self.assertFalse(self._seja(_Control(_Zaslon(False), _Link(_Deljenje(False)))))

    def test_druga_naprava_gleda_ta_zaslon(self):
        self.assertTrue(self._seja(_Control(_Zaslon(True), _Link(None))))

    def test_racunalnik_posilja_zaslon(self):
        self.assertTrue(self._seja(_Control(_Zaslon(False), _Link(_Deljenje(True)))))

    def test_pravi_zaslon_v_mirovanju_ni_seja(self):
        # Control ustvari Zaslon »pripravljen« (vklopljeno): to se ni prenos slike - sicer Straza nikoli ne bi delovala.
        from core import link_zaslon
        self.assertFalse(self._seja(_Control(link_zaslon.Zaslon(vklopljeno=True), _Link(None))))

    def test_control_ni_v_tem_procesu(self):
        import safeer_os
        for tece, pricakovano in ((False, False), (True, True)):    # locen Control: seje ne vidimo -> brez sprememb
            with mock.patch.object(safeer_os, "_control_na_vodilu", return_value=tece), \
                    mock.patch.object(safeer_os.Gio, "bus_get_sync", return_value=None):
                self.assertEqual(self._seja(None), pricakovano)

    def test_napaka_pomeni_brez_spremembe(self):
        class _Pokvarjen:
            def stanje(self):
                raise RuntimeError("x")
        self.assertTrue(self._seja(_Control(_Pokvarjen(), None)))


if __name__ == "__main__":
    unittest.main()
