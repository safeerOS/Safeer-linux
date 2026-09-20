"""Stabilnost Safeer OS: sled ob sesutju, varni nacin, varna raba libwnck, nadzor zaganjalnika.

Ozadje: 20. 9. 2026 se je Safeer OS sesul (SIGSEGV v libglib med g_object_unref), ker je
`Wnck.Screen.force_update()` tekel ob vsakem branju seznama oken in so objekti oken pri tem
umirali pod nogami. Ob sesutju ni bilo ne sledi ne okrevanja. Ti testi cuvajo oboje.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import os_okna, os_stabilnost  # noqa: E402


class Sled(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-stabilnost-")
        self.okolje = mock.patch.dict(os.environ, {"XDG_CACHE_HOME": self.mapa})
        self.okolje.start()

    def tearDown(self):
        self.okolje.stop()

    def test_sled_ob_sesutju_se_zapise(self):
        """Ob SIGSEGV mora v dnevniku ostati sled Pythona - sicer ne vemo, kaj je teklo."""
        koda = (
            "import os, sys; sys.path.insert(0, %r);\n"
            "from core import os_stabilnost;\n"
            "os_stabilnost.vkljuci('safeer-os');\n"
            "import ctypes; ctypes.string_at(1)\n" % KOREN
        )
        r = subprocess.run([sys.executable, "-c", koda], capture_output=True, text=True,
                           env=dict(os.environ, XDG_CACHE_HOME=self.mapa), timeout=60)
        self.assertLess(r.returncode, 0, "proces se ni sesul, test nima smisla")
        pot = os.path.join(self.mapa, "safeer-os", "sled.log")
        self.assertTrue(os.path.isfile(pot), "sledi ni")
        vsebina = open(pot, encoding="utf-8", errors="replace").read()
        self.assertIn("Fatal Python error", vsebina)
        self.assertIn("string_at", vsebina, "v sledi ni vrstice, ki je padla")

    def test_neujeta_izjema_v_dnevniku(self):
        koda = ("import sys; sys.path.insert(0, %r);\n"
                "from core import os_stabilnost; os_stabilnost.vkljuci('safeer-os');\n"
                "raise RuntimeError('preizkus')\n" % KOREN)
        subprocess.run([sys.executable, "-c", koda], capture_output=True, text=True,
                       env=dict(os.environ, XDG_CACHE_HOME=self.mapa), timeout=60)
        dnevnik = open(os.path.join(self.mapa, "safeer-os", "dnevnik.log"), encoding="utf-8").read()
        self.assertIn("neujeta izjema", dnevnik)
        self.assertIn("RuntimeError: preizkus", dnevnik)

    def test_varni_nacin_po_ponovljenih_sesutjih(self):
        self.assertFalse(os_stabilnost.naj_bo_varni_nacin("safeer-os", cas=1000.0))
        os_stabilnost.zabelezi_sesutje("safeer-os", 139, cas=1000.0)
        self.assertFalse(os_stabilnost.naj_bo_varni_nacin("safeer-os", cas=1001.0))
        os_stabilnost.zabelezi_sesutje("safeer-os", 139, cas=1002.0)
        self.assertTrue(os_stabilnost.naj_bo_varni_nacin("safeer-os", cas=1003.0))
        # Staro sesutje se ne steje vec.
        self.assertFalse(os_stabilnost.naj_bo_varni_nacin("safeer-os", cas=1003.0 + os_stabilnost.OKNO_SESUTIJ_S))
        # Ko program dolgo tece, zgodovino pozabimo.
        os_stabilnost.pozabi_sesutja("safeer-os")
        self.assertFalse(os_stabilnost.naj_bo_varni_nacin("safeer-os", cas=1003.0))

    def test_dnevnik_se_ne_razraste(self):
        pot = os.path.join(self.mapa, "safeer-os")
        os.makedirs(pot, exist_ok=True)
        with open(os.path.join(pot, "dnevnik.log"), "w", encoding="utf-8") as d:
            d.write("x" * (os_stabilnost.NAJVECJI_DNEVNIK * 2))
        os_stabilnost.zapisi("safeer-os", "nova vrstica")
        self.assertLess(os.path.getsize(os.path.join(pot, "dnevnik.log")), os_stabilnost.NAJVECJI_DNEVNIK)


class Okna(unittest.TestCase):
    """Seznam oken ne sme biti nikoli razlog za sesutje."""

    def test_brez_wnck_vrne_prazno(self):
        with mock.patch.dict(os.environ, {os_okna.IZKLOP: "1"}):
            self.assertEqual(os_okna.seznam(), [])
            self.assertFalse(os_okna.dejanje(123, "zapri"))
            self.assertEqual(os_okna.pomanjsaj_vse(), 0)
            self.assertFalse(os_okna.na_voljo())
            self.assertFalse(os_okna.spremljaj(lambda: None))

    def test_iz_druge_niti_ne_gre_v_libwnck(self):
        """libwnck je samo za glavno nit; klic iz niti mora vrniti prazno, ne pa tvegati sesutje."""
        import threading
        izid = {}

        def v_niti():
            izid["seznam"] = os_okna.seznam()
            izid["dejanje"] = os_okna.dejanje(1, "aktiviraj")

        n = threading.Thread(target=v_niti)
        n.start()
        n.join(10)
        self.assertEqual(izid.get("seznam"), [])
        self.assertIs(izid.get("dejanje"), False)

    def test_force_update_samo_enkrat(self):
        """Ponovljeni force_update je bil vzrok sesutja 20. 9. 2026."""
        with open(os.path.join(KOREN, "core", "os_okna.py"), encoding="utf-8") as d:
            vir = d.read()
        klici = [l.strip() for l in vir.splitlines()
                 if "force_update()" in l and not l.strip().startswith("#") and "_zaslon.force_update()" in l]
        self.assertEqual(len(klici), 1, "force_update sme biti poklican samo na enem mestu: %s" % klici)
        self.assertIn("_osvezen", vir, "force_update mora biti zasciten z zastavico")
        # In v glavnem programu ga ne sme biti vec.
        glavni = open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8").read()
        self.assertNotIn("force_update", glavni)
        self.assertNotIn("Wnck", glavni, "libwnck se uporablja samo prek core/os_okna.py")

    def test_ikone_oken_se_pocistijo(self):
        mapa = tempfile.mkdtemp(prefix="safeer-ikone-")
        for xid in range(300):
            open(os.path.join(mapa, "okno-%d.png" % xid), "wb").close()
        os_okna._pocisti_ikone(mapa, {1, 2, 3}, najvec=200)
        ostane = sorted(int(i[5:-4]) for i in os.listdir(mapa))
        self.assertEqual(ostane, [1, 2, 3])


class Zaganjalnik(unittest.TestCase):
    """Zaganjalnik mora Safeer OS po sesutju znova zagnati - a ne v neskoncnost."""

    POT = os.path.join(KOREN, "packaging", "safeer-os-launcher")

    def _zazeni(self, vsebina_programa: str, argumenti=(), okolje=None):
        mapa = tempfile.mkdtemp(prefix="safeer-zagon-")
        app = os.path.join(mapa, "lib", "safeer-os")
        os.makedirs(os.path.join(app, "core"), exist_ok=True)
        os.makedirs(os.path.join(mapa, "bin"), exist_ok=True)
        with open(os.path.join(app, "safeer_os.py"), "w", encoding="utf-8") as d:
            d.write(vsebina_programa)
        with open(os.path.join(app, "core", "__init__.py"), "w", encoding="utf-8") as d:
            d.write("")
        with open(os.path.join(app, "core", "os_stabilnost.py"), "w", encoding="utf-8") as d:
            d.write("def zabelezi_sesutje(*a, **k):\n    return 1\n")
        zaganjalnik = os.path.join(mapa, "bin", "safeer-os")
        with open(self.POT, encoding="utf-8") as d:
            vsebina = d.read()
        with open(zaganjalnik, "w", encoding="utf-8") as d:
            d.write(vsebina)
        os.chmod(zaganjalnik, 0o755)
        o = dict(os.environ, XDG_CACHE_HOME=os.path.join(mapa, "cache"), PYTHON=sys.executable)
        o.update(okolje or {})
        return subprocess.run(["bash", zaganjalnik, *argumenti], capture_output=True, text=True, timeout=120, env=o), mapa

    def test_normalen_izhod_se_ne_ponovi(self):
        program = ("import os\n"
                   "open(os.path.join(os.path.dirname(__file__), 'stevec'), 'a').write('x')\n")
        r, mapa = self._zazeni(program)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(open(os.path.join(mapa, "lib", "safeer-os", "stevec")).read()), 1)

    def test_navadna_napaka_se_ne_ponovi(self):
        r, mapa = self._zazeni("import sys\nsys.exit(3)\n")
        self.assertEqual(r.returncode, 3)

    def test_sesutje_se_ponovi_in_nato_odneha(self):
        """Signal (sesutje) pomeni ponoven zagon, a najvec petkrat."""
        program = ("import os, signal\n"
                   "p = os.path.join(os.path.dirname(__file__), 'stevec')\n"
                   "open(p, 'a').write('x')\n"
                   "os.kill(os.getpid(), signal.SIGSEGV)\n")
        r, mapa = self._zazeni(program)
        zagonov = len(open(os.path.join(mapa, "lib", "safeer-os", "stevec")).read())
        self.assertEqual(zagonov, 5, "zaganjalnik mora poskusiti petkrat, potem odnehati")
        self.assertGreater(r.returncode, 128)
        dnevnik = open(os.path.join(mapa, "cache", "safeer-os", "dnevnik.log"), encoding="utf-8").read()
        self.assertIn("signala 11", dnevnik)
        self.assertIn("odneham", dnevnik)

    def test_version_ne_gre_skozi_nadzor(self):
        r, _ = self._zazeni("print('Safeer OS 0.4.2')\n", argumenti=["--version"])
        self.assertIn("Safeer OS", r.stdout)


if __name__ == "__main__":
    unittest.main()
