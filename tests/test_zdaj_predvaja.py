"""»Predvaja se« tudi za skladbo s seznama v vgradnem predvajalniku YouTuba (lastnik, 14. 10. 2026: med glasbo v
Medijskem centru je pripomocek na namizju kazal »Ni predvajanja«).

Namizje (delovna.js, Namizje.qml), Medijski center in sistem (MPRIS) berejo `predvajalnikStanje`; ta je doslej poznal
samo domaci predvajalnik GStreamer. Zdaj javi tudi skladbo iz kataloga, tipke pa gredo vgradnemu predvajalniku."""
import json
import os
import tempfile
import unittest
from unittest import mock

from core import os_katalog as K

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _LazniMc:
    def __init__(self, vnosi):
        self.vnosi = vnosi

    def resolve(self, ident):
        return self.vnosi.get(ident)


def _katalog(dogodki=None):
    mapa = tempfile.mkdtemp()
    k = K.Katalog(mapa, dogodek=lambda v, p: (dogodki if dogodki is not None else []).append((v, p)),
                  v_glavni=lambda delo: delo(), predvajaj=lambda *a: True, vdelano=lambda u: True,
                  youtube=lambda u, n: True, youtube_ukaz=lambda u: True)
    k._mc = _LazniMc({"seznam:a": {"id": "seznam:a", "vrsta": "glasba", "naslov": "Pesem", "izvajalec": "Pevka",
                                   "slika": "https://i.ytimg.com/vi/59o4m222aVw/hqdefault.jpg", "youtube": "59o4m222aVw"}})
    return k


class PodatkiKataloga(unittest.TestCase):
    def test_brez_skladbe_ni_podatkov(self):
        self.assertIsNone(_katalog().yt_podatki())

    def test_skladba_s_seznama(self):
        k = _katalog()
        k.izvedi("mediaPredvajaj", ["seznam:a"])
        p = k.yt_podatki()
        self.assertEqual(p, {"stanje": "predvaja", "naslov": "Pesem", "izvajalec": "Pevka",
                             "slika": "https://i.ytimg.com/vi/59o4m222aVw/hqdefault.jpg", "izvor": "YouTube", "vrsta": "medij"})
        k.yt_sporocilo(json.dumps({"stanje": 1}))
        self.assertEqual(k.yt_podatki()["stanje"], "predvaja")
        k.yt_sporocilo(json.dumps({"stanje": 2}))
        self.assertEqual(k.yt_podatki()["stanje"], "premor")
        k.yt_sporocilo(json.dumps({"stanje": 1}))
        self.assertEqual(k.yt_podatki()["stanje"], "predvaja")
        k.yt_zaprt()
        self.assertIsNone(k.yt_podatki())

    def test_konec_in_napaka_koncata_predvajanje(self):
        k = _katalog()
        k.izvedi("mediaPredvajaj", ["seznam:a"])
        k.yt_sporocilo(json.dumps({"stanje": 1}))
        k.yt_sporocilo(json.dumps({"stanje": 0}))
        self.assertIsNone(k.yt_podatki())
        k.izvedi("mediaPredvajaj", ["seznam:a"])
        k.yt_sporocilo(json.dumps({"napaka": True, "koda": "x"}))
        self.assertIsNone(k.yt_podatki())


class _Lupina(unittest.TestCase):
    """Metode SafeerOS na laznem objektu (brez okna in GStreamerja)."""

    def setUp(self):
        import safeer_os
        S = safeer_os.SafeerOS

        class Lazna:
            _yt_predvajanje = S._yt_predvajanje
            _medijski_podatki = S._medijski_podatki
            _yt_ukaz = S._yt_ukaz
            _medijski_ukaz = S._medijski_ukaz
            _mpris_podatki = S._mpris_podatki
            _yt_spremenjeno = S._yt_spremenjeno
        self.l = Lazna()
        self.dogodki = []
        self.l._dogodek = lambda v, p=None, pogled=None: self.dogodki.append((v, p))
        self.l._katalog_youtube_ukaz = mock.MagicMock(return_value=True)
        self.l._mpris_osvezi = mock.MagicMock()
        # Vgrajeni predvajalnik je plast v oknu Medijskega centra (core/os_medijska_plast.py), ne svoje okno.
        self.l._medijska_plast = mock.MagicMock()
        self.l._pokazi_medijsko_plast = mock.MagicMock(return_value=True)
        self.l._medijski_predvajalnik = None
        self.l._katalog = _katalog()

    def _igra_yt(self, stanje=1):
        self.l._katalog.izvedi("mediaPredvajaj", ["seznam:a"])
        self.l._katalog.yt_sporocilo(json.dumps({"stanje": 1}))
        if stanje != 1:
            self.l._katalog.yt_sporocilo(json.dumps({"stanje": stanje}))


class StanjeZaNamizje(_Lupina):
    def test_nic_ne_igra(self):
        self.assertEqual(self.l._medijski_podatki()["stanje"], "ustavljeno")
        self.l._katalog = None
        self.assertEqual(self.l._medijski_podatki()["stanje"], "ustavljeno")

    def test_skladba_youtube_v_obliki_domacega_predvajalnika(self):
        self._igra_yt()
        p = self.l._medijski_podatki()
        for kljuc in ("stanje", "naslov", "vrsta", "indeks", "zacetniIndeks", "skupaj", "vrstaSeznam", "pozicija",
                      "trajanje", "napaka"):
            self.assertIn(kljuc, p)
        self.assertEqual((p["stanje"], p["naslov"], p["izvor"], p["izvajalec"]), ("predvaja", "Pesem", "YouTube", "Pevka"))
        self.assertEqual(p["trajanje"], 0)          # drsnik polozaja se skrije (vgradni predvajalnik ga ne javlja)
        self.assertTrue(p["vrstaStrani"])           # naslednja/prejsnja ostaneta na voljo
        self._igra_yt(2)
        self.assertEqual(self.l._medijski_podatki()["stanje"], "premor")

    def test_domaci_predvajalnik_ima_prednost(self):
        self._igra_yt()
        servis = mock.MagicMock(stanje="predvaja")
        servis.podatki.return_value = {"stanje": "predvaja", "naslov": "Radio"}
        self.l._medijski_predvajalnik = servis
        self.assertEqual(self.l._medijski_podatki()["naslov"], "Radio")
        servis.stanje = "ustavljeno"
        self.assertEqual(self.l._medijski_podatki()["naslov"], "Pesem")

    def test_skladba_kataloga_v_domacem_predvajalniku(self):
        # Naslednjo vodi stran (vrstaStrani), izvajalec in naslovnica pridejo iz kataloga - za pripomocke in MPRIS.
        servis = mock.MagicMock(stanje="predvaja", vrsta=[1])
        servis.trenutna.uri = "https://radio.test/a.mp3"
        servis.podatki.return_value = {"stanje": "predvaja", "naslov": "A", "vrsta": "medij"}
        self.l._medijski_predvajalnik = servis
        self.l._katalog._predvajano["https://radio.test/a.mp3"] = {"zvok": True, "izvajalec": "Pevka", "slika": "https://x.test/a.jpg"}
        p = self.l._medijski_podatki()
        self.assertEqual((p["vrstaStrani"], p["izvajalec"], p["slika"]), (True, "Pevka", "https://x.test/a.jpg"))
        self.assertTrue(self.l._mpris_podatki()["vrstaStrani"])
        servis.trenutna.uri = "file:///glasba/b.mp3"          # krajevna datoteka: vrsto vodi predvajalnik
        p = self.l._mpris_podatki()
        self.assertEqual((p["vrstaStrani"], p["izvajalec"], p["slika"]), (False, "", ""))

    def test_mpris_dobi_izvajalca_in_sliko(self):
        self._igra_yt()
        p = self.l._mpris_podatki()
        self.assertEqual((p["izvajalec"], p["slika"][:8], p["vrstaStrani"]), ("Pevka", "https://", True))
        from core import os_mpris
        last = os_mpris.lastnosti(p)
        self.assertEqual(last["PlaybackStatus"], "Playing")
        self.assertTrue(last["CanGoNext"] and last["CanGoPrevious"])
        self.assertFalse(last["CanSeek"])

    def test_sprememba_gre_stranem_in_sistemu(self):
        self._igra_yt()
        self.l._yt_spremenjeno()
        self.assertEqual(self.dogodki[-1][0], "predvajalnik")
        self.assertEqual(self.dogodki[-1][1]["naslov"], "Pesem")
        self.l._mpris_osvezi.assert_called_once()


class TipkeZaSkladbo(_Lupina):
    def test_premor_in_nadaljevanje(self):
        self._igra_yt(1)
        self.assertTrue(self.l._medijski_ukaz("premor"))
        self.l._katalog_youtube_ukaz.assert_called_with("pauseVideo")
        self._igra_yt(2)
        self.l._medijski_ukaz("premor")
        self.l._katalog_youtube_ukaz.assert_called_with("playVideo")

    def test_naslednja_in_prejsnja_vodi_stran(self):
        self._igra_yt()
        self.assertTrue(self.l._medijski_ukaz("naslednja"))
        self.assertTrue(self.l._medijski_ukaz("prejsnja"))
        self.assertEqual(self.dogodki, [("mediaVrstaUkaz", 1), ("mediaVrstaUkaz", -1)])

    def test_ustavi_zapre_pogled_in_odpri_ga_pokaze(self):
        self._igra_yt()
        self.assertTrue(self.l._medijski_ukaz("ustavi"))
        self.l._katalog_youtube_ukaz.assert_called_with("zapri")
        self.assertTrue(self.l._medijski_ukaz("odpri"))
        self.l._pokazi_medijsko_plast.assert_called_once()
        self.assertFalse(self.l._medijski_ukaz("skok", 30.0))

    def test_brez_skladbe_ostane_domaci_predvajalnik(self):
        self.assertFalse(self.l._medijski_ukaz("premor"))          # nic ne igra
        self.l._katalog_youtube_ukaz.assert_not_called()
        self._igra_yt()
        servis = mock.MagicMock(stanje="premor", vrsta=[], trenutna=None)
        self.l._medijski_predvajalnik = servis
        self.l._shrani_medijski_napredek = mock.MagicMock()
        self.assertTrue(self.l._medijski_ukaz("premor"))
        servis.premor.assert_called_once()
        self.l._katalog_youtube_ukaz.assert_not_called()


class Povezave(unittest.TestCase):
    """Stanje se spremeni v gostitelju: vsaka sprememba skladbe sprozi osvezitev (staticno, brez WebKita)."""

    def test_klici_ob_spremembah(self):
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            koda = f.read()
        self.assertIn("self._katalog.yt_sporocilo(rezultat.to_string())\n            self._yt_spremenjeno()", koda)
        self.assertIn("self._katalog.yt_zaprt()\n                self._yt_spremenjeno()", koda)
        self.assertIn("GLib.idle_add(lambda: self._yt_spremenjeno() and False)", koda)


if __name__ == "__main__":
    unittest.main()
