"""Usklajenost slike in zvoka, ko gre zvok na zvocnik v omrezju (lastnik, 17. 10. 2026: »Vse, kar se predvaja v nasem
predvajalniku, lahko predvajamo na zvocniku ... poskrbi za usklajenost video in zvocnega toka«).

* core/zvok_na_zvocnik.py oceni zakasnitev zvocnika (GetPositionInfo glede na prvi bajt toka) in jo zapomni za vsak
  zvocnik posebej; rocna nastavitev (drsnik) ima prednost; ob koncu seje je zakasnitev 0;
* core/os_predvajalnik.py zamakne sliko (playbin av-offset > 0), skupaj z uporabnikovim zamikom zvoka;
* okno predvajalnika videa (GTK, safeer_os.py) ima gumb »Predvajaj na …« z istim seznamom (os_zvok.moznosti_izhoda).
Brez pravega zvocnika in GStreamerja: lazni DLNA, lazni pactl, lazni playbin."""
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

from core import os_zvok
from core import zvok_na_zvocnik as zz
from test_predvajalnik_moznosti import _predvajalnik
from test_zvok_na_zvocnik import LazniPactl, LazniZvocnik

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JEZIKI = ("sl", "en", "de", "es", "fr", "it")


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class Ocena(unittest.TestCase):
    def test_iz_prehodov_relative_time(self):
        # Prava zakasnitev 1,6 s: RelTime = floor(t - 1,6); meritve vsakih 0,25 s od t = 10 s naprej.
        meritve = [(10 + i * 0.25, int(10 + i * 0.25 - 1.6)) for i in range(40)]
        self.assertTrue(abs(zz.ocena_zakasnitve(meritve) - 1600) <= 150, zz.ocena_zakasnitve(meritve))

    def test_brez_prehoda_ali_nesmiselno(self):
        self.assertIsNone(zz.ocena_zakasnitve([]))
        self.assertIsNone(zz.ocena_zakasnitve([(1.0, 0), (1.25, 0), (1.5, 0)]))   # zvocnik RelTime ne javlja (0)
        self.assertIsNone(zz.ocena_zakasnitve([(1.0, 5), (1.25, 6)]))              # RelTime pred tokom: nemogoce

    def test_omejitev(self):
        self.assertEqual(zz.omeji_zakasnitev(1873), 1850)
        self.assertEqual(zz.omeji_zakasnitev(-40), 0)
        self.assertEqual(zz.omeji_zakasnitev(99_999), zz.MEJA_ZAKASNITVE_MS)
        self.assertEqual(zz.omeji_zakasnitev("x"), zz.PRIVZETA_ZAKASNITEV_MS)


class ZakasnitevZvocnika(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(zz, "ukaz_toka", lambda vir, ffmpeg="": [sys.executable, "-c",
                              "import sys; sys.stdout.buffer.write(b'ID3' + b'x' * 5000)"])
        p.start()
        self.addCleanup(p.stop)
        m = mock.patch.object(zz.shutil, "which", lambda x: "/usr/bin/" + x)
        m.start()
        self.addCleanup(m.stop)
        self.mapa = tempfile.mkdtemp()
        self.pot = os.path.join(self.mapa, "zvocniki.json")
        self.jbl = LazniZvocnik()
        self.z = zz.Zvocniki(najdi=lambda cas: [self.jbl], pactl=LazniPactl(), ffmpeg=sys.executable,
                             lan_naslov=lambda ip: "127.0.0.1", pot_zakasnitev=self.pot)
        self.z.osvezi(pocakaj=True)
        self.klici = []
        self.z.ob_zakasnitvi = self.klici.append
        self.addCleanup(self.z.ustavi)

    def test_privzeto_shranjeno_in_nazaj_na_nic(self):
        with mock.patch.object(zz, "ZACETNI_ZAMIK_S", 60.0):
            self.assertTrue(self.z.zacni("dlna:uuid:jbl")["ok"])
        self.assertEqual(self.klici, [zz.PRIVZETA_ZAKASNITEV_MS])
        self.assertEqual(self.z.opis()["zakasnitev"], zz.PRIVZETA_ZAKASNITEV_MS)
        self.assertEqual(self.z.nastavi_zakasnitev("dlna:uuid:jbl", 1234), 1250)       # drsnik: korak 50 ms
        self.assertEqual(self.klici[-1], 1250)
        self.assertEqual(json.load(open(self.pot))["dlna:uuid:jbl"], {"ms": 1250, "rocno": True})
        self.z.ustavi()
        self.assertEqual(self.klici[-1], 0)                     # zvok spet tu: slika brez zamika
        self.assertEqual(self.z.opis()["zakasnitev"], 0)
        self.assertEqual(self.z.zakasnitev("dlna:uuid:jbl"), 1250)   # zapomnjeno za ta zvocnik
        self.assertEqual(self.z.zakasnitev("dlna:drug"), zz.PRIVZETA_ZAKASNITEV_MS)

    def _meri(self):
        ura = [100.0]
        self.z._tok.prvi_bajt = 100.0
        self.jbl.polozaj = lambda: {"TrackURI": "", "RelTimeSeconds": max(0, int(ura[0] - 100.0 - 1.4))}
        self.z.cakaj = lambda s: ura.__setitem__(0, ura[0] + s)
        with mock.patch.object(zz.time, "monotonic", lambda: ura[0]):
            self.z._izmeri(self.z._seja)

    def test_meritev_shrani_in_zamakne(self):
        with mock.patch.object(zz, "ZACETNI_ZAMIK_S", 60.0):
            self.z.zacni("dlna:uuid:jbl")
        self._meri()
        self.assertTrue(abs(self.klici[-1] - 1400) <= 150, self.klici)
        self.assertFalse(json.load(open(self.pot))["dlna:uuid:jbl"]["rocno"])

    def test_rocna_nastavitev_ima_prednost(self):
        with mock.patch.object(zz, "ZACETNI_ZAMIK_S", 60.0):
            self.z.zacni("dlna:uuid:jbl")
        self.z.nastavi_zakasnitev("dlna:uuid:jbl", 3000)
        self._meri()
        self.assertEqual(self.klici[-1], 3000)
        self.assertEqual(self.z.zakasnitev(), 3000)

    def test_moznosti_kazejo_zakasnitev_aktivnega(self):
        z = {"izhodi": [], "link": {"zvocniki": [{"id": "dlna:1", "ime": "JBL"}, {"id": "dlna:2", "ime": "Kodi"}],
                                    "zvocnik": {"naprava": "dlna:1", "stanje": "tece", "zakasnitev": 1500}}}
        m = os_zvok.moznosti_izhoda(z)
        self.assertEqual([(x["vrsta"], x["aktiven"], x.get("zakasnitev")) for x in m],
                         [("racunalnik", False, None), ("zvocnik", True, 1500), ("zvocnik", False, None)])


class SlikaPocakaZvocnik(unittest.TestCase):
    def test_av_offset_nastavi_in_ponastavi(self):
        p, e = _predvajalnik()
        p.dodaj("https://example.test/a.mkv", vrsta="video")
        p.nastavi_zakasnitev_izhoda(2000)
        self.assertEqual(e.lastnosti["av-offset"], 2_000_000_000)           # slika 2 s kasneje
        p.premakni_zamik("zvok", 100)                                       # uporabnikov zamik se pristeje
        self.assertEqual(e.lastnosti["av-offset"], 1_900_000_000)
        p.dodaj("https://example.test/b.mkv", predvajaj=True, vrsta="video")
        self.assertEqual(e.lastnosti["av-offset"], 2_000_000_000)           # nov posnetek: zvocnik ostane
        p.nastavi_zakasnitev_izhoda(0)
        self.assertEqual(e.lastnosti["av-offset"], 0)


class OknoPredvajalnika(unittest.TestCase):
    """safeer_os.py je GTK 4 (tu ga ne nalozimo): preverimo vezavo v izvorni kodi."""

    def setUp(self):
        self.s = _beri("safeer_os.py")

    def test_gumb_predvajaj_na_v_oknu_videa(self):
        okno = self.s[self.s.index("    def _ustvari_okno_videa"):self.s.index("    def _medijski_miska_drsnika")]
        self.assertIn('self._medijski_izhod = Gtk.Button(label="🔈 " + self._mb("predvajaj_na"))', okno)
        self.assertIn("self._medijski_izhod.connect(\"clicked\", self._medijski_meni_izhoda)", okno)
        plosca = self.s[self.s.index("    def _medijska_plosca_izhoda"):self.s.index("    def _medijski_zamik_zvocnika")]
        self.assertIn("os_zvok.moznosti_izhoda(z)", plosca)                 # isti seznam kot v izhod.js
        self.assertIn("zvok_izberi_izhod(m, soglasje)", plosca)
        meni = self.s[self.s.index("    def _medijski_meni_izhoda"):self.s.index("    def _medijska_plosca_izhoda")]
        self.assertIn("threading.Thread(", meni)                             # pactl/Link v ozadju

    def test_zakasnitev_povezana_s_predvajalnikom(self):
        self.assertIn("self._povezi_zakasnitev_zvocnika()", self.s)
        self.assertIn('stanje["moznosti"] = os_zvok.moznosti_izhoda(stanje)', self.s)
        self.assertIn('"zvokZakasnitevZvocnika": lambda: zvocniki().nastavi_zakasnitev(', self.s)

    def test_besedila_gtk(self):
        from core import os_media_besedila as b
        for j in JEZIKI:
            for k in ("predvajaj_na", "ta_racunalnik", "zvocnik_omrezje", "povezujem", "isci_zvocnike",
                      "zamik_splet", "zvok_zaseden"):
                self.assertTrue(b.BESEDILA[j].get(k), (j, k))
        self.assertNotEqual(b.besedilo("predvajaj_na", "de"), b.besedilo("predvajaj_na", "en"))

    def test_drsnik_v_mini_predvajalniku(self):
        js = _beri("assets", "os", "os.js")
        self.assertIn('if (m.vrsta === "zvocnik" && m.aktiven) c.appendChild(zamikZvocnika(m));', js)
        self.assertTrue(re.search(r'd\.step = "50"', js))


if __name__ == "__main__":
    unittest.main()
