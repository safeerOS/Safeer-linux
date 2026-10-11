"""Iskanje z glasom v lupi namizja (lastnik, 11. 10. 2026): core/os_govor.py snema, zazna konec govora in prepozna
govor na tem racunalniku. Tu brez mikrofona in brez pravega modela: snemalnik in whisper-cli sta lazna."""
import hashlib
import http.server
import math
import os
import shutil
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import os_govor  # noqa: E402


def pcm(odseki):
    """[(sekunde, amplituda)] -> s16le 16 kHz (ton 300 Hz)."""
    izhod = bytearray()
    n = 0
    for sekunde, amp in odseki:
        for _ in range(int(sekunde * os_govor.VZORCI)):
            izhod += struct.pack("<h", int(amp * math.sin(2 * math.pi * 300 * n / os_govor.VZORCI)))
            n += 1
    return bytes(izhod)


def zaznaj(podatki):
    z = os_govor.ZaznavaGovora()
    korak = os_govor.KOS * 2
    for i in range(0, len(podatki), korak):
        izid = z.kos(os_govor._rms(podatki[i:i + korak]))
        if izid:
            return izid, round(i / 2 / os_govor.VZORCI, 2), z.govor
    return None, None, z.govor


class TestCiscenje(unittest.TestCase):
    def test_ocisti(self):
        self.assertEqual(os_govor.ocisti(" Odpri nastavitve zaslona."), "nastavitve zaslona")
        self.assertEqual(os_govor.ocisti("Predvajaj Jungle Book!"), "Jungle Book")
        self.assertEqual(os_govor.ocisti("Poišči datoteko navodila"), "datoteko navodila")
        self.assertEqual(os_govor.ocisti("open firefox", "en"), "firefox")
        self.assertEqual(os_govor.ocisti("Search for cats", "en"), "cats", "daljsi ukaz pred krajsim")
        self.assertEqual(os_govor.ocisti("Abre el archivo.", "es"), "archivo")
        self.assertEqual(os_govor.ocisti("Öffne die Einstellungen", "de"), "Einstellungen")
        self.assertEqual(os_govor.ocisti("Reproduz o filme", "pt"), "filme")
        self.assertEqual(os_govor.ocisti("Play the Jungle Book", "en"), "Jungle Book")
        self.assertEqual(os_govor.ocisti("[BLANK_AUDIO]"), "")
        self.assertEqual(os_govor.ocisti("(glasba) Zvok"), "Zvok")
        self.assertEqual(os_govor.ocisti("Odpri."), "", "samo ukaz: nic za iskati")
        self.assertEqual(os_govor.ocisti("Odprtje računa"), "Odprtje računa", "beseda, ki se z ukazom samo zacne, ostane")


class TestZaznava(unittest.TestCase):
    def test_govor_in_tisina_po_njem(self):
        izid, cas, govor = zaznaj(pcm([(0.4, 60), (1.5, 6000), (2.0, 60)]))
        self.assertEqual(izid, "konec")
        self.assertTrue(govor)
        self.assertAlmostEqual(cas, 0.4 + 1.5 + os_govor.TISINA_PO_GOVORU, delta=0.1)

    def test_nihce_ne_govori(self):
        izid, cas, govor = zaznaj(pcm([(6.0, 80)]))
        self.assertEqual((izid, govor), ("tisina", False))
        self.assertAlmostEqual(cas, os_govor.ZACETNA_TISINA, delta=0.05)

    def test_hrupno_ozadje(self):
        # Ozadje 1500 (ventilator): govor mora biti vsaj 3x glasnejsi; 2500 ni govor.
        self.assertEqual(zaznaj(pcm([(0.4, 1500), (1.0, 2500), (5.0, 1500)]))[0], "tisina")
        self.assertEqual(zaznaj(pcm([(0.4, 1500), (1.0, 9000), (2.0, 1500)]))[0], "konec")

    def test_mikrofon_se_odpira_z_niclami(self):
        # Prvi kosi so nicle (mikrofon se odpira), potem hrup ~690 (izmerjeno na prenosniku): to ni govor.
        self.assertEqual(zaznaj(pcm([(0.15, 0), (6.0, 690)]))[0], "tisina")
        self.assertEqual(zaznaj(pcm([(0.15, 0), (0.5, 690), (1.0, 5000), (2.0, 690)]))[0], "konec")

    def test_najdlje(self):
        izid, cas, _ = zaznaj(pcm([(0.4, 60), (10.0, 6000)]))
        self.assertEqual(izid, "konec")
        self.assertAlmostEqual(cas, os_govor.NAJDALJE, delta=0.05)


class TestJezik(unittest.TestCase):
    def test_jezik_seje(self):
        for okolje, privzeti, pricakovano in (({"LANGUAGE": "pt_PT:en", "LANG": "pt_PT.UTF-8"}, "en", "pt"),
                                              ({"LANGUAGE": "", "LC_ALL": "", "LC_MESSAGES": "", "LANG": "de_DE.UTF-8"}, "en", "de"),
                                              ({"LANGUAGE": "", "LC_ALL": "", "LC_MESSAGES": "", "LANG": "C.UTF-8"}, "sl", "sl")):
            with mock.patch.dict(os.environ, okolje):
                self.assertEqual(os_govor.jezik_govora(privzeti), pricakovano)

    def test_namig_za_vsak_jezik(self):
        for j in ("sl", "en", "de", "es", "pt"):
            self.assertIn(j, os_govor.NAMIGI)
            self.assertIn(j, os_govor.UKAZI)


class TestRaven(unittest.TestCase):
    def test_raven(self):
        self.assertEqual(os_govor.raven(0), 0.0)
        self.assertLess(os_govor.raven(600), 0.3)
        self.assertGreater(os_govor.raven(10000), 0.95)
        self.assertEqual(os_govor.raven(10 ** 6), 1.0)


class TestNamestitev(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.g = os_govor.Govor(self.mapa)
        self.okolje = mock.patch.dict(os.environ, {"SAFEER_GOVOR_PROGRAM": ""})
        self.okolje.start()

    def tearDown(self):
        self.okolje.stop()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_brez_programa_ni_podprto(self):
        with mock.patch.dict(os_govor.PROGRAMI, {"x86_64-v3": {"ime": "x", "sha256": "", "velikost": 0},
                                                 "x86_64": {"ime": "x", "sha256": "", "velikost": 0}}), \
                mock.patch("shutil.which", return_value=None), mock.patch.object(os_govor.Govor, "snemalnik", return_value=["x"]):
            self.assertEqual(self.g.stanje()["podprto"], False)
            self.assertFalse(self.g.namesti(lambda *_: None))

    def test_prenos_s_preverjanjem(self):
        vsebina = b"model" * 1000
        streznik_mapa = tempfile.mkdtemp()
        with open(os.path.join(streznik_mapa, "m.bin"), "wb") as f:
            f.write(vsebina)

        class Tih(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=streznik_mapa, **k)

            def log_message(self, *a):
                pass
        s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Tih)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        url = "http://127.0.0.1:%d/m.bin" % s.server_address[1]
        program = os.path.join(self.mapa, "whisper-cli")
        with open(program, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(program, 0o755)
        try:
            for sha, pricakovano in (("0" * 64, "napaka"), (hashlib.sha256(vsebina).hexdigest(), "namesceno")):
                dogodki = []
                koncano = threading.Event()

                def dogodek(vrsta, podatki, dogodki=dogodki, koncano=koncano):
                    dogodki.append((vrsta, podatki))
                    if vrsta in ("namesceno", "napaka"):
                        koncano.set()
                model = dict(os_govor.MODEL, url=url, sha256=sha, velikost=len(vsebina))
                with mock.patch.object(os_govor, "MODEL", model), mock.patch.object(os_govor.Govor, "snemalnik", return_value=["x"]):
                    self.assertEqual(self.g.stanje()["prenos"], len(vsebina))
                    self.assertTrue(self.g.namesti(dogodek))
                    self.assertTrue(koncano.wait(10))
                    self.assertEqual(dogodki[-1][0], pricakovano)
                    self.assertFalse(os.path.exists(self.g.pot_modela() + ".part"), "brez ostankov prenosa")
                    if pricakovano == "napaka":
                        self.assertFalse(os.path.exists(self.g.pot_modela()), "napacna datoteka se zavrze")
                    else:
                        self.assertTrue(self.g.stanje()["namesceno"])
                        self.assertIn(("namescam", {"odstotek": 99}), dogodki)
        finally:
            s.shutdown()
            shutil.rmtree(streznik_mapa, ignore_errors=True)


class TestPoslusanje(unittest.TestCase):
    """Celotna pot: lazni snemalnik da govor in tisino, lazni whisper-cli izpise besedilo in svoje argumente."""

    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        with open(os.path.join(self.mapa, os_govor.MODEL["ime"]), "wb") as f:
            f.write(b"m")
        self.posnetek = os.path.join(self.mapa, "posnetek.raw")
        self.argumenti = os.path.join(self.mapa, "argumenti.txt")
        program = os.path.join(self.mapa, "whisper-cli")
        with open(program, "w") as f:
            f.write('#!/bin/sh\necho "$@" > %s\necho " Odpri nastavitve zaslona."\n' % self.argumenti)
        os.chmod(program, 0o755)
        self.g = os_govor.Govor(self.mapa)

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def poslusaj(self, odseki, ustavi_po=None, preklici_po=None):
        with open(self.posnetek, "wb") as f:
            f.write(pcm(odseki))
        dogodki = []
        koncano = threading.Event()

        def dogodek(vrsta, podatki):
            dogodki.append((vrsta, podatki))
            if vrsta in ("besedilo", "tisina", "napaka", "preklicano"):
                koncano.set()
        # Snemalnik v realnem casu (kot mikrofon): 30 ms kosi z zamikom.
        snemalnik = [sys.executable, "-c", "import sys,time\nd=open(%r,'rb').read()\nfor i in range(0,len(d),960):\n"
                     " sys.stdout.buffer.write(d[i:i+960]); sys.stdout.flush(); time.sleep(0.003)\ntime.sleep(30)" % self.posnetek]
        with mock.patch.object(os_govor.Govor, "snemalnik", return_value=snemalnik):
            self.assertTrue(self.g.poslusaj("sl", dogodek))
            self.assertFalse(self.g.poslusaj("sl", dogodek), "ena seja naenkrat")
            if ustavi_po is not None:
                time.sleep(ustavi_po); self.g.ustavi()
            if preklici_po is not None:
                time.sleep(preklici_po); self.g.preklici()
            self.assertTrue(koncano.wait(20))
        for _ in range(50):
            if not self.g.stanje()["poslusam"]:
                break
            time.sleep(0.05)
        return dogodki

    def test_govor_v_besedilo(self):
        dogodki = self.poslusaj([(0.4, 60), (1.2, 6000), (1.5, 60)])
        self.assertEqual([d[0] for d in dogodki if d[0] not in ("raven", "delno")], ["poslusam", "prepoznavam", "besedilo"])
        ravni = [d[1]["r"] for d in dogodki if d[0] == "raven"]
        self.assertTrue(ravni and max(ravni) > 0.6 and min(ravni) < 0.1, "valovi: govor visoko, tisina nizko")
        self.assertEqual(dogodki[-1][1]["besedilo"], "nastavitve zaslona")
        with open(self.argumenti) as f:
            arg = f.read().split()
        self.assertEqual(arg[arg.index("-l") + 1], "sl")
        self.assertEqual(arg[arg.index("-ac") + 1], "512")
        wav = arg[arg.index("-f") + 1]
        self.assertFalse(os.path.exists(wav), "posnetek se po prepoznavi izbrise")
        self.assertFalse(self.g.stanje()["poslusam"])

    def test_tisina_brez_prepoznave(self):
        dogodki = self.poslusaj([(6.0, 60)])
        self.assertEqual([d[0] for d in dogodki if d[0] != "raven"], ["poslusam", "tisina"])
        self.assertFalse(os.path.exists(self.argumenti), "whisper-cli se v tisini ne pozene")

    def test_preklic(self):
        dogodki = self.poslusaj([(0.4, 60), (6.0, 6000)], preklici_po=0.3)
        self.assertEqual(dogodki[-1][0], "preklicano")
        self.assertNotIn("besedilo", [d[0] for d in dogodki])


if __name__ == "__main__":
    unittest.main()
