"""Pot nazaj na Cinnamon in zastavica vodnika ob prvem zagonu v safeer_os (lastnik, 17. 10. 2026).

safeer_os tece v locenem procesu z laznim okoljem iz test_delovna (gsettings, dconf, plank ... v zacasnem HOME) in z
nedosegljivim vodilom D-Bus: nic se ne dotakne nastavitev tega racunalnika in ukaz ne more doseci Safeer OS, ki morda
tece. Skupina gtk4 (podproces uvozi safeer_os)."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Tudi ce pytest tece iz druge mape: core/ (koren) in test_delovna (ta mapa) morata biti na poti.
for _pot in (KOREN, os.path.dirname(os.path.abspath(__file__))):
    if _pot not in sys.path:
        sys.path.insert(0, _pot)

import test_delovna  # noqa: E402 - isto lazno okolje za safeer-cinnamon
TEMA = test_delovna.TEMA
# Razred TestCase iz test_delovna ne sme biti ime v tem modulu: pytest bi pobral in pognal njegove preizkuse se enkrat.
_vrednost = test_delovna.TestTemaCinnamon._vrednost
APPLETI = test_delovna.TestTemaCinnamon.APPLETI


def _okolje(tmp: str) -> dict:
    return test_delovna.TestTemaCinnamon._okolje(test_delovna.TestTemaCinnamon(), tmp)


def _gtk4_na_voljo() -> bool:
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); import safeer_os" % KOREN],
                       capture_output=True, env=dict(os.environ, DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent"))
    return r.returncode == 0


@unittest.skipUnless(_gtk4_na_voljo(), "safeer_os potrebuje GTK 4 in WebKitGTK 6.0")
class NazajNaCinnamon(unittest.TestCase):
    """safeer_os v locenem procesu, v laznem okolju (HOME, PATH z laznimi orodji, brez vodila D-Bus)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.o = _okolje(self.tmp.name)
        env = self.o["env"]
        # Prazni XDG_* bi safeer_os vzel dobesedno (relativne poti): brez njih velja HOME.
        for k in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "DISPLAY", "WAYLAND_DISPLAY", "FLATPAK_ID"):
            env.pop(k, None)
        env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + os.path.join(self.tmp.name, "ni-vodila")
        self.dnevnik = os.path.join(self.tmp.name, "safeer-cinnamon.log")
        ovoj = os.path.join(self.tmp.name, "bin", "safeer-cinnamon")
        with open(ovoj, "w") as f:
            f.write('#!/bin/sh\necho "$@" >> "%s"\nexec bash "%s" "$@"\n' % (self.dnevnik, os.path.join(TEMA, "safeer-cinnamon")))
        os.chmod(ovoj, os.stat(ovoj).st_mode | stat.S_IEXEC)
        self.shramba = os.path.join(self.o["dom"], ".config", "safeer-os", "os.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _python(self, koda: str) -> str:
        # safeer-cinnamon Safeer OS isce samo v sistemskih mapah (core/root_ukaz.sistemski_program, ne po PATH): lazno
        # orodje preizkusa dodamo na zacetek teh map v podprocesu, ne v okolje.
        priprava = ("import sys; sys.path.insert(0, %r)\nfrom core import root_ukaz\n"
                    "root_ukaz.SISTEMSKE_MAPE = (%r,) + root_ukaz.SISTEMSKE_MAPE\n" % (KOREN, os.path.join(self.tmp.name, "bin")))
        r = subprocess.run([sys.executable, "-c", priprava + koda],
                           env=self.o["env"], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        return r.stdout

    def _ukaz(self, *argumenti) -> str:
        return subprocess.run(["bash", os.path.join(TEMA, "safeer-cinnamon"), *argumenti], env=self.o["env"],
                              check=True, capture_output=True, text=True).stdout

    def _os_json(self) -> dict:
        with open(self.shramba, encoding="utf-8") as f:
            return json.load(f)

    def _zapisi_os_json(self, podatki: dict) -> None:
        os.makedirs(os.path.dirname(self.shramba), exist_ok=True)
        with open(self.shramba, "w", encoding="utf-8") as f:
            json.dump(podatki, f)

    # ------------------------------------------------------------------ vodnik: samo enkrat in samo novim
    VODNIK = ("import safeer_os\nfrom core import os_programi\n"
              "print(safeer_os.oznaci_vodnik(os_programi.Shramba()))\n")

    def test_vodnik_nova_namestitev_dokler_ni_koncan(self):
        self.assertEqual(self._python(self.VODNIK).strip(), "True")
        self.assertEqual(self._python(self.VODNIK).strip(), "True")     # ni bil koncan (sesutje, zaprto okno)
        self.assertEqual(self._os_json()["vodnik"], "caka")
        p = self._os_json()
        p["vodnik"] = "koncan"                                          # _vodnik_koncaj
        self._zapisi_os_json(p)
        self.assertEqual(self._python(self.VODNIK).strip(), "False")

    def test_obstojeci_uporabnik_ga_ne_dobi(self):
        self._zapisi_os_json({"samozagon_izbral": False, "uporaba": {"firefox.desktop": 3}})
        self.assertEqual(self._python(self.VODNIK).strip(), "False")
        self.assertEqual(self._os_json()["vodnik"], "ni_potreben")
        self.assertEqual(self._python(self.VODNIK).strip(), "False")

    # ------------------------------------------------------------------ safeer-os --nazaj-na-cinnamon
    def test_ukaz_vrne_cinnamon_in_izklopi_samozagon(self):
        self._ukaz("--profil", "delovna")
        self.assertEqual(_vrednost(self.o, "org.cinnamon.theme", "name"), "'Safeer-Cinnamon'")
        # Safeer OS je skril Mintov pult (prvotne vrednosti v os.json, kot skrij_mintov_pult).
        self._zapisi_os_json({"samozagon": True, "samozagon_izbral": True,
                              "mintov_pult": {"panels-autohide": "['1:false']", "panels-show-delay": "['1:0']"}})
        # Kot `safeer_os.py --nazaj-na-cinnamon`, a z laznim safeer-cinnamon med sistemskimi mapami (_python).
        izpis = self._python("import runpy\nsys.argv = [%r, '--nazaj-na-cinnamon']\nrunpy.run_path(%r, run_name='__main__')"
                             % (os.path.join(KOREN, "safeer_os.py"), os.path.join(KOREN, "safeer_os.py")))
        self.assertIn("Cinnamon", izpis)
        # safeer-cinnamon --izklopi: tema, pult in dock iz shranjenega stanja pred Safeer Cinnamon.
        self.assertFalse(os.path.exists(os.path.join(self.o["mapa"], "vklopljeno")))
        self.assertEqual(_vrednost(self.o, "org.cinnamon.theme", "name"), "'Mint-Y-Dark-Aqua'")
        self.assertEqual(_vrednost(self.o, "org.cinnamon", "panels-enabled"), "['1:0:bottom']")
        self.assertEqual(_vrednost(self.o, "org.cinnamon", "enabled-applets"), APPLETI)
        self.assertEqual(os.listdir(self.o["launcherji"]), ["star.dockitem"])
        # Mintov pult (Safeer OS) je vrnjen.
        self.assertEqual(_vrednost(self.o, "org.cinnamon", "panels-autohide"), "['1:false']")
        # Brez zagona ob prijavi: seja safeer-cinnamon odstranjena, vnos Safeer OS ostane, a izklopljen.
        self.assertEqual(sorted(os.listdir(self.o["avto"])), ["safeer-os.desktop", "safeer-tema.desktop"])
        with open(os.path.join(self.o["avto"], "safeer-os.desktop")) as f:
            self.assertIn("X-GNOME-Autostart-enabled=false", f.read())
        p = self._os_json()
        self.assertIs(p["samozagon"], False)
        self.assertIsNone(p.get("mintov_pult"))
        self.assertEqual(p["nazaj_na_cinnamon"], {"profil": "delovna"})
        with open(self.dnevnik) as f:
            self.assertIn("--izklopi", f.read())

    def test_ukaz_brez_safeer_cinnamon(self):
        """Samo Safeer OS (brez videza Safeer Cinnamon): izklop zagona ob prijavi, safeer-cinnamon se ne poklice."""
        self._zapisi_os_json({"samozagon": True, "samozagon_izbral": True})
        r = subprocess.run([sys.executable, os.path.join(KOREN, "safeer_os.py"), "--back-to-cinnamon"],
                           env=self.o["env"], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        with open(os.path.join(self.o["avto"], "safeer-os.desktop")) as f:
            self.assertIn("X-GNOME-Autostart-enabled=false", f.read())
        self.assertEqual(self._os_json()["nazaj_na_cinnamon"], {"profil": ""})
        self.assertFalse(os.path.exists(self.dnevnik))

    # ------------------------------------------------------------------ Safeer OS iz menija: vrnitev
    def test_vrnitev_da_obnovi_samozagon_in_postavitev(self):
        self._zapisi_os_json({"nazaj_na_cinnamon": {"profil": "dock"}, "samozagon": False, "samozagon_izbral": True})
        self._python("import safeer_os\nfrom core import os_programi\n"
                     "assert safeer_os.vrni_safeer_os(os_programi.Shramba(), True)\n")
        p = self._os_json()
        self.assertIsNone(p.get("nazaj_na_cinnamon"))
        self.assertIs(p["samozagon"], True)
        with open(os.path.join(self.o["avto"], "safeer-os.desktop")) as f:
            self.assertIn("X-GNOME-Autostart-enabled=true", f.read())
        # safeer-cinnamon tece loceno (Popen): pocakamo na njegov zadnji korak (miska_enkrat), da za sabo ne pusti procesa.
        konec = time.time() + 30
        while time.time() < konec and not os.path.exists(os.path.join(self.o["mapa"], "miska-ponujena")):
            time.sleep(0.2)
        self.assertTrue(os.path.exists(os.path.join(self.o["mapa"], "vklopljeno")))
        with open(self.dnevnik) as f:
            self.assertIn("--profil dock", f.read())

    def test_vrnitev_ne_samo_pozabi_vprasanje(self):
        self._zapisi_os_json({"nazaj_na_cinnamon": {"profil": "dock"}, "samozagon": False, "samozagon_izbral": True})
        self._python("import safeer_os\nfrom core import os_programi\n"
                     "assert not safeer_os.vrni_safeer_os(os_programi.Shramba(), False)\n")
        p = self._os_json()
        self.assertIsNone(p.get("nazaj_na_cinnamon"))
        self.assertIs(p["samozagon"], False)
        self.assertFalse(os.path.exists(self.dnevnik))


if __name__ == "__main__":
    unittest.main()
