"""Zajem, ki takoj pade (core/link_zaslon.py): vzrok v dnevnik in meja ponovitev.

Izmerjeno 10. 11. 2026 na testnem PC: ffmpeg (x11grab, napacna velikost zaslona) je koncal v 0,1 s z izhodom 234,
gledalec je sejo zahteval znova vsakih ~1,4 s (18+ sej), vzroka ni bilo v dnevniku (stderr v DEVNULL).
Sejo znova zahteva GLEDALEC (screen.start -> Zaslon.zacni), streznik sam nikoli - zato je meja v zacni().

Preizkus ne spreminja os.environ: modul link_zaslon dobi svoj pogled na okolje (_Os), lazni ffmpeg je skripta v
mktemp -d, ki jo preizkus na koncu pobrise.
"""
import os
import shutil
import stat
import sys
import tempfile
import threading
import unittest
from unittest import mock

from core import link_datoteke, link_daljinec, link_zaslon
from tests.test_zaslon_seja import _Televizor

#: Lazni ffmpeg: zabelezi zagon, izpise dolgo napako na stderr in konca z 234 (kot x11grab izven zaslona).
LAZNI_FFMPEG = '''#!{python}
import sys
with open({zagoni!r}, "a") as d:
    d.write("zagon\\n")
sys.stderr.write("a" * 3000 + "\\n")
sys.stderr.write("[x11grab] Capture area 1920x1080 at position 0.0 outside the screen size 1440x900\\n")
sys.stderr.write("KONEC-IZPISA\\n")
sys.stderr.flush()
sys.exit(234)
'''


class Rep(unittest.TestCase):
    def test_hrani_samo_konec(self):
        rep = link_zaslon.RepIzpisa(2000)
        for _ in range(500):
            rep.dodaj(b"x" * 1000)                  # 500 kB izpisa
        rep.dodaj("čšž KONEC".encode("utf-8"))
        self.assertLessEqual(rep.bajtov(), 8000, "pomnilnik je omejen")
        besedilo = rep.besedilo()
        self.assertLessEqual(len(besedilo), 2000)
        self.assertTrue(besedilo.endswith("čšž KONEC"))

    def test_bralna_nit_prebere_do_konca(self):
        r, w = os.pipe()
        rep = link_zaslon.RepIzpisa(50)
        nit = threading.Thread(target=link_zaslon.beri_izpis, args=(os.fdopen(r, "rb", buffering=0), rep))
        nit.start()
        with os.fdopen(w, "wb") as pisi:
            pisi.write(b"y" * 100000 + b"zadnja vrstica")
        nit.join(5)
        self.assertFalse(nit.is_alive())
        self.assertTrue(rep.besedilo().endswith("zadnja vrstica"))


class Odpovedi(unittest.TestCase):
    """Cista logika meje (brez procesov)."""

    def test_tri_zaporedne_ustavijo(self):
        o = link_zaslon.OdpovediZajema()
        self.assertIsNone(o.zacetek("tv", 0.0))
        self.assertIsNone(o.konec("tv", 0.1, False, 234, 0.1))
        self.assertIsNone(o.konec("tv", 0.1, False, 234, 1.5))
        self.assertEqual(o.konec("tv", 0.1, False, 234, 3.0), "izhod_234")
        self.assertEqual(o.zacetek("tv", 4.4), "izhod_234")
        self.assertEqual(o.stanje("tv"), {"razlog": "izhod_234", "zaporednih": 3})
        self.assertIsNone(o.zacetek("druga", 4.4), "druga naprava ni ustavljena")

    def test_slika_ponastavi(self):
        o = link_zaslon.OdpovediZajema()
        o.konec("tv", 0.1, False, 234, 0.0)
        o.konec("tv", 0.1, False, 234, 1.0)
        self.assertIsNone(o.konec("tv", 0.5, True, 0, 2.0))
        self.assertIsNone(o.konec("tv", 0.1, False, 234, 3.0))
        self.assertIsNone(o.konec("tv", 0.1, False, 234, 4.0), "po sliki se steje od zacetka")

    def test_ustavili_mi_in_pocasen_konec(self):
        o = link_zaslon.OdpovediZajema()
        o.konec("tv", 0.1, False, 234, 0.0)
        o.konec("tv", 0.1, False, 234, 1.0)
        self.assertIsNone(o.konec("tv", 0.1, False, -15, 1.5), "zajem, ki smo ga ustavili mi, ni odpoved")
        self.assertIsNone(o.konec("tv", 0.1, False, None, 1.6))
        self.assertEqual(o.konec("tv", 0.1, False, 1, 2.0), "izhod_1")
        o2 = link_zaslon.OdpovediZajema()
        o2.konec("tv", 0.1, False, 234, 0.0)
        o2.konec("tv", 0.1, False, 234, 1.0)
        self.assertIsNone(o2.konec("tv", 5.0, False, 1, 7.0), "dolga seja prekine niz")
        self.assertIsNone(o2.konec("tv", 0.1, False, 234, 8.0))

    def test_premor_30_s(self):
        o = link_zaslon.OdpovediZajema()
        for t in (0.0, 1.0, 2.0):
            o.konec("tv", 0.1, False, 234, t)
        # Samodejno ponavljanje gledalca (~1,4 s) okno podaljsuje: ostane ustavljeno.
        t = 2.0
        for _ in range(40):
            t += 1.4
            self.assertEqual(o.zacetek("tv", t), "izhod_234")
        # Rocni nov zagon po 30 s mirovanja: steje znova.
        self.assertIsNone(o.zacetek("tv", t + 30.0))
        self.assertIsNone(o.stanje("tv"))


class _Os:
    """Pogled modula link_zaslon na okolje: os brez spremembe os.environ procesa."""

    def __init__(self, okolje: dict) -> None:
        self.environ = okolje

    def __getattr__(self, ime):
        return getattr(os, ime)


class SejaZajemPade(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-zajem-pade-")
        self.addCleanup(shutil.rmtree, self.mapa, True)
        try:
            link_datoteke.zagotovi_potrdilo(os.path.join(self.mapa, "tls"))
        except Exception as e:  # noqa: BLE001 - brez orodja za potrdilo preizkusa ni mogoce izvesti
            self.skipTest("potrdila ni mogoce ustvariti: %s" % e)
        self.zagoni = os.path.join(self.mapa, "zagoni")
        self.ffmpeg = os.path.join(self.mapa, "lazni-ffmpeg")
        with open(self.ffmpeg, "w", encoding="utf-8") as d:
            d.write(LAZNI_FFMPEG.format(python=sys.executable, zagoni=self.zagoni))
        os.chmod(self.ffmpeg, os.stat(self.ffmpeg).st_mode | stat.S_IXUSR)
        okolje = dict(os.environ, DISPLAY=":0", SAFEER_ZASLON_GPU="0", SAFEER_ZASLON_RTT="0",
                      SAFEER_ZASLON_MERITVE=os.path.join(self.mapa, "meritve.jsonl"))
        self.izpis = []
        for p in (mock.patch.object(link_zaslon, "os", _Os(okolje)),
                  mock.patch("core.seja_prikaza.je_wayland", return_value=False),
                  mock.patch.object(link_zaslon, "_deljeni_monitor", return_value=None),
                  mock.patch.object(link_zaslon, "_izvor_zaslona", return_value=(1440, 900)),
                  mock.patch.object(link_zaslon, "privzeti_monitor", return_value=None),
                  mock.patch.object(link_zaslon, "vaapi_naprava", return_value=None),
                  mock.patch.object(link_zaslon, "hevc_mozen", return_value=False),
                  mock.patch.object(link_zaslon, "gpu_lestvica_mozna", return_value=False),
                  mock.patch("builtins.print", side_effect=lambda *a, **k: self.izpis.append(" ".join(map(str, a))))):
            p.start()
            self.addCleanup(p.stop)
        self.z = link_zaslon.Zaslon(tls_mapa=os.path.join(self.mapa, "tls"), vklopljeno=True, ffmpeg=self.ffmpeg)
        self.z.dostop = lambda naprava: True
        self.televizorji = []

    def tearDown(self):
        for t in self.televizorji:
            t.zapri()
        self.z.ustavi(pocakaj_s=5.0)
        for n in threading.enumerate():
            if n.name in ("safeer-zaslon", "safeer-zaslon-izpis"):
                n.join(5.0)

    def _seja(self) -> _Televizor:
        tv = _Televizor(self.z.zacni("tv-test"))
        self.televizorji.append(tv)
        self.assertTrue(tv.koncan.wait(15), "seja se ni koncala")
        return tv

    def _zagonov(self) -> int:
        try:
            with open(self.zagoni, encoding="utf-8") as d:
                return len(d.readlines())
        except FileNotFoundError:
            return 0

    def test_vzrok_v_dnevniku_in_meja(self):
        prva = self._seja()
        druga = self._seja()
        for tv in (prva, druga):
            self.assertFalse([o for o in tv.obvestila if o.get("konec") == "zajem"], "pred mejo gledalec konca ne dobi")
        vrstice = [v for v in self.izpis if "ffmpeg:" in v and "brez slike" in v]
        self.assertEqual(len(vrstice), 2, self.izpis)
        self.assertIn("koda 234", vrstice[0])
        self.assertIn("outside the screen size 1440x900", vrstice[0])
        self.assertTrue(vrstice[0].rstrip().endswith("KONEC-IZPISA"))
        self.assertLessEqual(len(vrstice[0].split("ffmpeg: ", 1)[1]), link_zaslon.ZAJEM_REP_ZNAKOV)

        tretja = self._seja()
        self.assertIn({"konec": "zajem", "razlog": "izhod_234"}, tretja.obvestila)
        self.assertEqual(self.z.stanje().get("zajem"), {"razlog": "izhod_234", "zaporednih": 3, "pada": True})
        self.assertEqual(self._zagonov(), 3)

        # Gledalec ponovi screen.start: streznik nove seje ne zacne, ffmpeg se ne zazene.
        with self.assertRaises(link_zaslon.ZajemPada) as napaka:
            self.z.zacni("tv-test")
        self.assertEqual(napaka.exception.razlog, "izhod_234")
        self.assertEqual(self._zagonov(), 3)
        self.assertFalse(self.z.stanje()["tece"])


class OdgovorDaljinca(unittest.TestCase):
    """screen.start po meji: koda in razlog za gledalca (link_daljinec)."""

    def test_zajem_pada(self):
        izidi = []

        class _Zaslon:
            drugi = None

            def na_voljo(self):
                return {"dovoljeno": True, "ffmpeg": True, "mozno": True}

            def zacni(self, *a, **k):
                raise link_zaslon.ZajemPada("izhod_234")

        link_daljinec.izvedi_control("screen.start", {}, lambda _u: None, izidi.append, posiljatelj="tv-test",
                                     zaslon=_Zaslon())
        self.assertTrue(izidi)
        self.assertEqual(izidi[-1]["code"], "zajem_pada")
        self.assertEqual(izidi[-1]["data"], {"konec": "zajem", "razlog": "izhod_234"})


if __name__ == "__main__":
    unittest.main()
