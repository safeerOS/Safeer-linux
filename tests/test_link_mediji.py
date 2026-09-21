# -*- coding: utf-8 -*-
"""Predvajalniki na locenem zaslonu (core/link_mediji.py): profil, izbira predvajalnika, stanje, ukazi."""
import unittest

from core import link_mediji
from core.link_mediji import Mpris, dogodek_v_tipko, je_potomec, je_predvajalnik, stanje_iz_lastnosti
from core.link_vnos import TIPKE


class Profil(unittest.TestCase):
    def test_profil_programa(self):
        P = link_mediji.profil_programa
        vlc = {"AudioVideo", "Player", "Recorder"}
        self.assertEqual(P(vlc, "/usr/share/applications/vlc.desktop", "/usr/bin/vlc %U"), "predvajalnik")
        # Kodi ima kategorije predvajalnika, a je narejen za daljinec: tipke, ne pas predvajalnika.
        self.assertEqual(P({"AudioVideo", "Video", "Player", "TV"}, "/usr/share/applications/kodi.desktop", "kodi"), "tv")
        self.assertEqual(P({"AudioVideo"}, "tv.plex.PlexHTPC.desktop", "/usr/bin/flatpak run tv.plex.PlexHTPC"), "tv")
        self.assertEqual(P({"Network", "WebBrowser"}, "firefox.desktop", "firefox %u"), "")
        self.assertEqual(P(None), "")

    def test_predvajalniki(self):
        self.assertTrue(je_predvajalnik({"AudioVideo", "Player", "Recorder"}))      # VLC
        self.assertTrue(je_predvajalnik({"GTK", "AudioVideo", "Video", "Player"}))  # Celluloid
        self.assertTrue(je_predvajalnik({"AudioVideo", "Audio", "Player"}))        # Rhythmbox
        self.assertTrue(je_predvajalnik({"AudioVideo", "Video", "TV"}))            # Hypnotix, Kodi

    def test_ni_predvajalnik(self):
        self.assertFalse(je_predvajalnik({"AudioVideo", "Recorder"}))               # OBS
        self.assertFalse(je_predvajalnik({"AudioVideo", "Video", "AudioVideoEditing"}))  # Kdenlive
        self.assertFalse(je_predvajalnik({"Graphics", "Viewer"}))
        self.assertFalse(je_predvajalnik({"AudioVideo", "GNOME", "GTK", "Office", "Settings", "Utility", "Video"}))
        self.assertFalse(je_predvajalnik({"Network", "WebBrowser"}))
        self.assertFalse(je_predvajalnik(set()))
        self.assertFalse(je_predvajalnik(None))


class Potomec(unittest.TestCase):
    def test_veriga(self):
        starsi = {50: 40, 40: 30, 30: 1, 60: 1}.get
        self.assertTrue(je_potomec(50, 30, lambda p: starsi(p, 0)))
        self.assertTrue(je_potomec(30, 30, lambda p: starsi(p, 0)))
        self.assertFalse(je_potomec(60, 30, lambda p: starsi(p, 0)))

    def test_zanka_ne_visi(self):
        self.assertFalse(je_potomec(5, 9, lambda p: {5: 6, 6: 5}[p]))


class Stanje(unittest.TestCase):
    def test_polno(self):
        s = stanje_iz_lastnosti({"PlaybackStatus": "Playing", "Position": 65_500_000, "CanSeek": True,
                                 "Metadata": {"xesam:title": "Pesem", "xesam:artist": ["A", "B"],
                                              "mpris:length": 200_000_000}})
        self.assertEqual(s, {"naslov": "Pesem", "izvajalec": "A, B", "dolzina": 200, "polozaj": 65,
                             "predvaja": True, "premik": True})

    def test_brez_oznak_ime_datoteke(self):
        s = stanje_iz_lastnosti({"PlaybackStatus": "Paused",
                                 "Metadata": {"xesam:url": "file:///home/u/Moj%20film.mkv"}})
        self.assertEqual(s["naslov"], "Moj film.mkv")
        self.assertFalse(s["predvaja"])
        self.assertEqual((s["dolzina"], s["polozaj"]), (0, 0))

    def test_polozaj_ne_cez_dolzino(self):
        s = stanje_iz_lastnosti({"Position": 999_000_000, "Metadata": {"mpris:length": 10_000_000}})
        self.assertEqual(s["polozaj"], 10)


class Tipke(unittest.TestCase):
    def test_nadomestne_tipke_obstajajo(self):
        for tipka in link_mediji.TIPKE_NAMESTO.values():
            self.assertIn(tipka, TIPKE)

    def test_premik_v_tipko(self):
        self.assertEqual(dogodek_v_tipko({"ukaz": "premik", "s": 10}), {"vrsta": "tipka", "tipka": "desno"})
        self.assertEqual(dogodek_v_tipko({"ukaz": "premik", "s": -10}), {"vrsta": "tipka", "tipka": "levo"})
        self.assertIsNone(dogodek_v_tipko({"ukaz": "premik", "s": "x"}))
        self.assertEqual(dogodek_v_tipko({"ukaz": "predvajaj_pavza"}), {"vrsta": "tipka", "tipka": "presledek"})
        self.assertIsNone(dogodek_v_tipko({"ukaz": "rm -rf"}))


class LazniMpris(Mpris):
    """Brez D-Bus: dva predvajalnika, eden na locenem zaslonu (pid 50), drugi na namizju (pid 60)."""

    def __init__(self, koren=30):
        super().__init__(lambda: koren)
        self.klici = []

    def _imena(self):
        return ["org.mpris.MediaPlayer2.rhythmbox", "org.mpris.MediaPlayer2.vlc"]

    def _pid(self, ime):
        return 60 if ime.endswith("rhythmbox") else 50

    def _klic(self, ime, pot, vmesnik, metoda, argumenti=None, odgovor=""):
        self.klici.append((ime, metoda))
        return None


class IzbiraPredvajalnika(unittest.TestCase):
    def setUp(self):
        self._stars, self._okolje = link_mediji.stars, link_mediji.okolje
        link_mediji.stars = lambda p: {50: 40, 40: 30, 60: 1}.get(p, 0)
        link_mediji.okolje = lambda p: {}

    def tearDown(self):
        link_mediji.stars, link_mediji.okolje = self._stars, self._okolje

    def test_po_waylandu_tudi_brez_prednika(self):
        """Sway programe zazene z dvojnim razcepom: prepoznamo jih po WAYLAND_DISPLAY."""
        link_mediji.stars = lambda p: 1
        link_mediji.okolje = lambda p: {"WAYLAND_DISPLAY": "wayland-9" if p == 50 else "wayland-0"}
        m = LazniMpris()
        m._wayland = lambda: "wayland-9"
        self.assertEqual(m.predvajalnik(), "org.mpris.MediaPlayer2.vlc")
        m._wayland = lambda: "wayland-7"
        self.assertIsNone(m.predvajalnik())

    def test_samo_predvajalnik_locenega_zaslona(self):
        m = LazniMpris()
        self.assertEqual(m.predvajalnik(), "org.mpris.MediaPlayer2.vlc")
        self.assertTrue(m.ukaz("predvajaj_pavza"))
        self.assertEqual(m.klici[-1], ("org.mpris.MediaPlayer2.vlc", "PlayPause"))

    def test_brez_locenega_zaslona_nic(self):
        m = LazniMpris(koren=0)
        self.assertIsNone(m.predvajalnik())
        self.assertFalse(m.ukaz("predvajaj_pavza"))

    def test_neznan_ukaz_zavrnjen(self):
        m = LazniMpris()
        self.assertFalse(m.ukaz("Quit"))
        self.assertEqual(m.klici, [])


if __name__ == "__main__":
    unittest.main()
