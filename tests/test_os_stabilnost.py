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
            # Zaganjalnik ob vsakem nekoncnem izhodu poklice `--vrni-mint`; vzorcni program to zabelezi
            # in koncna, da ne vpliva na stetje zagonov.
            d.write("import os, sys\n"
                    "if '--vrni-mint' in sys.argv[1:]:\n"
                    "    open(os.path.join(os.path.dirname(__file__), 'vrni-mint'), 'a').write('x')\n"
                    "    raise SystemExit(0)\n")
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

    def _vrnitev_mint(self, mapa) -> int:
        pot = os.path.join(mapa, "lib", "safeer-os", "vrni-mint")
        return len(open(pot).read()) if os.path.exists(pot) else 0

    def test_normalen_izhod_se_ne_ponovi(self):
        program = ("import os\n"
                   "open(os.path.join(os.path.dirname(__file__), 'stevec'), 'a').write('x')\n")
        r, mapa = self._zazeni(program)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(open(os.path.join(mapa, "lib", "safeer-os", "stevec")).read()), 1)
        # Ob normalnem koncu je Safeer OS pult vrnil sam; zaganjalnik ga ne sme klicati se enkrat.
        self.assertEqual(self._vrnitev_mint(mapa), 0)

    def test_napaka_vrne_mintov_pult(self):
        """Tudi navadna napaka (ne sesutje) ne sme pustiti namizja brez Mintovega pulta."""
        r, mapa = self._zazeni("import sys\nsys.exit(3)\n")
        self.assertEqual(r.returncode, 3)
        self.assertEqual(self._vrnitev_mint(mapa), 1)

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
        # Po vsakem sesutju in se enkrat, ko zaganjalnik odneha: Mint mora ostati uporaben.
        self.assertEqual(self._vrnitev_mint(mapa), 6, "pult se mora vrniti po vsakem sesutju in ob odnehanju")

    def test_version_ne_gre_skozi_nadzor(self):
        r, _ = self._zazeni("print('Safeer OS 0.4.2')\n", argumenti=["--version"])
        self.assertIn("Safeer OS", r.stdout)


class MintovPult(unittest.TestCase):
    """Mint pod masko mora ostati varnostna mreza: pult se vrne tudi, kadar Safeer OS ne konca lepo."""

    def setUp(self):
        import safeer_os
        self.os_modul = safeer_os
        self.nastavljeno = {}
        self.brano = {"panels-autohide": "['1:false']", "panels-show-delay": "['1:0']",
                      "panels-enabled": "['1:0:bottom']"}

        def lazni_gsettings(*a):
            if a[0] == "get":
                return self.brano.get(a[2])
            if a[0] == "set":
                self.nastavljeno[a[2]] = a[3]
                self.brano[a[2]] = a[3]
                return ""
            return None

        self.zaplata = mock.patch.object(safeer_os, "_gsettings", lazni_gsettings)
        self.zaplata.start()

    def tearDown(self):
        self.zaplata.stop()

    class Shramba:
        def __init__(self):
            self.d = {}

        def get(self, k, privzeto=None):
            return self.d.get(k, privzeto)

        def set(self, k, v):
            self.d[k] = v

    def test_skrij_shrani_prvotne_vrednosti(self):
        s = self.Shramba()
        self.os_modul.skrij_mintov_pult(s)
        self.assertEqual(s.get("mintov_pult"),
                         {"panels-autohide": "['1:false']", "panels-show-delay": "['1:0']"})
        self.assertEqual(self.nastavljeno["panels-show-delay"], "['1:86400000']")

    def test_popravi_po_sesutju_vrne_pult(self):
        """Prejsnji zagon je pustil pult skrit: naslednji zagon (ali --vrni-mint) ga vrne."""
        s = self.Shramba()
        self.os_modul.skrij_mintov_pult(s)
        self.assertTrue(self.os_modul.pult_je_skrit(s))
        self.assertTrue(self.os_modul.popravi_po_sesutju(s))
        self.assertEqual(self.brano["panels-autohide"], "['1:false']")
        self.assertEqual(self.brano["panels-show-delay"], "['1:0']")
        self.assertFalse(self.os_modul.pult_je_skrit(s))

    def test_popravi_je_idempotenten(self):
        """Veckraten klic (zaganjalnik + zagon) ne sme nicesar pokvariti."""
        s = self.Shramba()
        self.os_modul.skrij_mintov_pult(s)
        self.os_modul.popravi_po_sesutju(s)
        self.brano["panels-show-delay"] = "['1:250']"      # uporabnik je medtem sam nekaj nastavil
        self.assertFalse(self.os_modul.popravi_po_sesutju(s))
        self.assertEqual(self.brano["panels-show-delay"], "['1:250']")

    def test_brez_pulta_ni_kaj_skriti(self):
        s = self.Shramba()
        self.brano["panels-enabled"] = "@as []"
        self.os_modul.skrij_mintov_pult(s)
        self.assertIsNone(s.get("mintov_pult"))
        self.assertEqual(self.nastavljeno, {})


class ZaganjalnikControl(unittest.TestCase):
    """Safeer Control tece ves dan v ozadju; ce pade, naprave tiho izgubijo racunalnik."""

    POT = os.path.join(KOREN, "packaging", "safeer-control-launcher")

    def _zazeni(self, program, argumenti=()):
        mapa = tempfile.mkdtemp(prefix="safeer-control-zagon-")
        app = os.path.join(mapa, "lib", "safeer-control")
        os.makedirs(os.path.join(app, "core"), exist_ok=True)
        os.makedirs(os.path.join(mapa, "bin"), exist_ok=True)
        with open(os.path.join(app, "safeer_control.py"), "w", encoding="utf-8") as d:
            d.write(program)
        with open(os.path.join(app, "core", "__init__.py"), "w", encoding="utf-8") as d:
            d.write("")
        with open(os.path.join(app, "core", "os_stabilnost.py"), "w", encoding="utf-8") as d:
            d.write("def zabelezi_sesutje(*a, **k):\n    return 1\n")
        pot = os.path.join(mapa, "bin", "safeer-control")
        with open(self.POT, encoding="utf-8") as d:
            vsebina = d.read()
        with open(pot, "w", encoding="utf-8") as d:
            d.write(vsebina)
        os.chmod(pot, 0o755)
        o = dict(os.environ, XDG_CACHE_HOME=os.path.join(mapa, "cache"), PYTHON=sys.executable)
        return subprocess.run(["bash", pot, *argumenti], capture_output=True, text=True, timeout=120, env=o), mapa

    def test_normalen_izhod_se_ne_ponovi(self):
        r, mapa = self._zazeni("import os\nopen(os.path.join(os.path.dirname(__file__), 'stevec'), 'a').write('x')\n")
        self.assertEqual(r.returncode, 0)
        with open(os.path.join(mapa, "lib", "safeer-control", "stevec")) as f:
            self.assertEqual(len(f.read()), 1)

    def test_sesutje_se_ponovi_in_nato_odneha(self):
        program = ("import os, signal\n"
                   "open(os.path.join(os.path.dirname(__file__), 'stevec'), 'a').write('x')\n"
                   "os.kill(os.getpid(), signal.SIGSEGV)\n")
        r, mapa = self._zazeni(program)
        with open(os.path.join(mapa, "lib", "safeer-control", "stevec")) as f:
            self.assertEqual(len(f.read()), 5, "zaganjalnik mora poskusiti petkrat, potem odnehati")
        self.assertGreater(r.returncode, 128)
        with open(os.path.join(mapa, "cache", "safeer-control", "dnevnik.log"), encoding="utf-8") as f:
            dnevnik = f.read()
        self.assertIn("signala 11", dnevnik)
        self.assertIn("odneham", dnevnik)


if __name__ == "__main__":
    unittest.main()
