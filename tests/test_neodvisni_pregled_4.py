"""Popravki po tretjem neodvisnem pregledu izdaje 1.0.128 (19. 10. 2026) in okolje procesa med tekom.

- safeer-cinnamon: dock najde tudi programe Flatpak, namescene samo za uporabnika (~/.local/share/flatpak/exports);
  pgrep/pkill Planka in delovne povrsine samo za procese tega uporabnika.
- Prazen XDG_CONFIG_HOME / XDG_CACHE_HOME / XDG_DATA_HOME / XDG_RUNTIME_DIR velja kot nenastavljen (specifikacija XDG):
  prej je dal relativno pot - nastavitve bi sle v trenutno mapo.
- Okolja procesa ne spreminjamo, ko v njem ze tecejo niti (setenv med getenv druge niti je v glibc nedefiniran):
  vgradnja Controla v Safeer OS (zastavica v core/en_proces), ponovni zagon Controla (execve z lastnim okoljem).
Vsak preizkus brez svojega popravka pade.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKRIPTA = os.path.join(KOREN, "packaging", "tema-cinnamon", "safeer-cinnamon")
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)


class DockFlatpakUporabnika(unittest.TestCase):
    def _najdi(self, dom: str, koren: str, ime: str) -> subprocess.CompletedProcess:
        with open(SKRIPTA, encoding="utf-8") as f:
            funkcija = re.search(r"^najdi_program\(\) \{.*?^\}", f.read(), re.S | re.M).group(0)
        okolje = {k: v for k, v in os.environ.items() if k != "XDG_DATA_HOME"}
        okolje.update(HOME=dom, KOREN=koren)
        return subprocess.run(["bash", "-c", funkcija + '\nnajdi_program "$1"', "bash", ime], env=okolje,
                              capture_output=True, text=True, timeout=10)

    def test_program_flatpak_uporabnika(self):
        tmp = tempfile.mkdtemp()
        try:
            mapa = os.path.join(tmp, "dom", ".local", "share", "flatpak", "exports", "share", "applications")
            os.makedirs(mapa)
            pot = os.path.join(mapa, "org.gimp.GIMP.desktop")
            open(pot, "w").close()
            izid = self._najdi(os.path.join(tmp, "dom"), os.path.join(tmp, "koren"), "org.gimp.GIMP")
            self.assertEqual((izid.returncode, izid.stdout.strip()), (0, pot), izid.stderr)
            self.assertEqual(self._najdi(os.path.join(tmp, "dom"), os.path.join(tmp, "koren"), "ni.Ga").returncode, 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_procesi_samo_tega_uporabnika(self):
        """Ob vec prijavljenih uporabnikih se tuj Plank ne steje za nasega in se ga ne poskusa ustaviti."""
        with open(SKRIPTA, encoding="utf-8") as f:
            vrstice = [v.strip() for v in f if re.search(r"\b(pgrep|pkill)\b", v) and not v.lstrip().startswith("#")]
        self.assertTrue(vrstice)
        for v in vrstice:
            self.assertIn('-u "$(id -u)"', v, v)


class PraznaSpremenljivkaXdg(unittest.TestCase):
    def test_prazna_je_kot_nenastavljena(self):
        from core import os_jbl, predvajalnik_moznosti, zvok_na_zvocnik
        prazno = {"XDG_CONFIG_HOME": "", "XDG_CACHE_HOME": "", "XDG_DATA_HOME": ""}
        with mock.patch.dict(os.environ, prazno):
            for pot in (os_jbl.mapa(), predvajalnik_moznosti._pot(), zvok_na_zvocnik._pot_zakasnitev()):
                self.assertTrue(os.path.isabs(pot), pot)
                self.assertTrue(pot.startswith(os.path.expanduser("~/.config")), pot)

    def test_nikjer_oblika_s_privzeto_vrednostjo(self):
        """os.environ.get("XDG_..._HOME", privzeto) vrne "" za prazno spremenljivko; prav je `get(...) or privzeto`."""
        vzorec = re.compile(r"""(environ\.get|getenv)\(\s*['"]XDG_\w+_(HOME|DIR)['"]\s*,""")
        najdeno = []
        poti = [os.path.join(KOREN, ime) for ime in os.listdir(KOREN) if ime.endswith(".py")]
        for koren, _mape, datoteke in os.walk(os.path.join(KOREN, "core")):
            poti += [os.path.join(koren, d) for d in datoteke if d.endswith(".py")]
        for pot in poti:
            with open(pot, encoding="utf-8") as f:
                for st, vrstica in enumerate(f, 1):
                    if vzorec.search(vrstica):
                        najdeno.append("%s:%d" % (os.path.relpath(pot, KOREN), st))
        self.assertEqual(najdeno, [])


class OkoljeProcesaMedTekom(unittest.TestCase):
    def test_vgradnja_controla_brez_okoljske_spremenljivke(self):
        from core import en_proces
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            izvor = f.read()
        self.assertNotIn('os.environ["SAFEER_CONTROL_VGRAJEN"]', izvor)
        self.assertIn("en_proces.vgradi_control()", izvor)
        with mock.patch.object(en_proces, "_control_bo_vgrajen", False):
            self.assertFalse(en_proces.control_bo_vgrajen())
            en_proces.vgradi_control()
            self.assertTrue(en_proces.control_bo_vgrajen())

    def test_ponovni_zagon_controla_ne_spremeni_okolja(self):
        import safeer_control
        lazna = mock.MagicMock()
        prej = dict(os.environ)
        with mock.patch.object(safeer_control, "VGRAJEN", False), \
                mock.patch.object(safeer_control.os, "execve") as execve, \
                mock.patch.object(safeer_control.os, "execv") as execv:
            safeer_control.SafeerControl._znova_zazeni(lazna)
        self.assertEqual(dict(os.environ), prej)
        execv.assert_not_called()
        program, argv, okolje = execve.call_args[0]
        self.assertEqual(okolje.get("SAFEER_CONTROL_ODPRI"), "1")
        self.assertIn("--ozadje", argv)


if __name__ == "__main__":
    unittest.main()
