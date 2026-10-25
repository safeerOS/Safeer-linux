"""Nasi podprocesi v svoji skupini (core/otroci.py, nacrt stabilnosti P1, naloga 41).

Pred popravkom je ob roku ali ustavitvi signal dobil samo glavni proces: vnuk (soffice.bin za oosplash, upodabljalnik
Electrona, swaybg za sway) je ostal. Okolje procesa preizkusov se ne spreminja (AGENTS.md): podprocesi dobijo env=.

Varovalo signalov (tests/varovalo_signalov.py, conftest): signal sme samo potomcem procesa preizkusov. Vnuk osiroti, ko se
sh konca, zato ga preizkus razglasi za svojega (lastni), dokler se tece; pospravljanje ubije samo isti proces (cas
zagona), nikoli PID, ki ga je sistem ze pobral (25. 10. 2026: tek je padal na kill(9) koncanih procesov).
"""
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)
sys.path.insert(0, os.path.join(KOREN, "tests"))

from core import os_pretvorba_datotek, otroci  # noqa: E402
from varovalo_signalov import cas_zagona, lastni  # noqa: E402


def zivi(pid: int) -> bool:
    """Proces tece (zombi, ki ga init v vsebniku morda ne pobere, ne steje)."""
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def pocakaj_datoteko(pot: str, rok: float = 5.0) -> int:
    konec = time.monotonic() + rok
    while time.monotonic() < konec:
        try:
            with open(pot) as f:
                vsebina = f.read().strip()
            if vsebina:
                return int(vsebina)
        except OSError:
            pass
        time.sleep(0.02)
    raise AssertionError("ni datoteke " + pot)


def zabelezi(pid: int):
    """(pid, cas zagona) procesa, ki ga je zagnal preizkus (sh ali sleep), ali None, ce ga ni vec."""
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            program = os.path.basename(f.read().split(b"\0", 1)[0]).decode("utf-8", "replace")
    except OSError:
        return None
    if program not in ("sh", "sleep"):
        return None
    cas = lastni(pid)
    return None if cas is None else (pid, cas)


def ubij_ce_isti(zapis) -> None:
    """SIGKILL samo istemu procesu (enak cas zagona): PID koncanega procesa je lahko ze tuj."""
    if zapis is not None and cas_zagona(zapis[0]) == zapis[1]:
        try:
            os.kill(zapis[0], signal.SIGKILL)
        except OSError:
            pass


def pocakaj_konec(pid: int, rok: float = 5.0) -> bool:
    konec = time.monotonic() + rok
    while time.monotonic() < konec:
        if not zivi(pid):
            return True
        time.sleep(0.02)
    return False


@unittest.skipUnless(os.name == "posix" and os.path.isdir("/proc"), "samo Linux")
class Skupina(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="otroci-")
        self.vnuk = os.path.join(self.d, "vnuk")
        self.pidi = []

    def tearDown(self):
        for zapis in self.pidi:        # pospravi tudi, ce preizkus pade
            ubij_ce_isti(zapis)
        for ime in os.listdir(self.d):
            os.unlink(os.path.join(self.d, ime))
        os.rmdir(self.d)

    def _zabelezi(self, *pidi: int) -> None:
        self.pidi += [zabelezi(pid) for pid in pidi]

    def _ukaz_z_vnukom(self, cakaj: bool = True) -> list:
        # sh zazene vnuka (sleep) v isti skupini in ga caka - kot oosplash soffice.bin.
        return ["sh", "-c", 'sleep 60 & echo $! > "$1"; %s' % ("wait" if cakaj else "exit 0"), "sh", self.vnuk]

    def test_ustavitev_konca_otroka_in_vnuka(self):
        p = otroci.zazeni(self._ukaz_z_vnukom(), stdin=subprocess.DEVNULL)
        vnuk = pocakaj_datoteko(self.vnuk)
        self._zabelezi(p.pid, vnuk)
        self.assertTrue(zivi(vnuk))
        otroci.ustavi(p, rok=2)
        self.assertIsNotNone(p.returncode)
        self.assertTrue(pocakaj_konec(vnuk), "vnuk je ostal")

    def test_rok_konca_celo_skupino(self):
        p = otroci.zazeni(self._ukaz_z_vnukom(), stdin=subprocess.DEVNULL)
        vnuk = pocakaj_datoteko(self.vnuk)
        self._zabelezi(p.pid, vnuk)
        with self.assertRaises(subprocess.TimeoutExpired):
            otroci.pocakaj(p, rok=0.3, rok_konca=2)
        self.assertTrue(pocakaj_konec(vnuk))

    def test_vnuk_po_koncu_glavnega_ne_ostane(self):
        p = otroci.zazeni(self._ukaz_z_vnukom(cakaj=False), stdin=subprocess.DEVNULL)
        # sh zapise vnuka in se konca: vnuk osiroti (ni vec potomec), core/otroci pa mora pospraviti tudi njega.
        vnuk = pocakaj_datoteko(self.vnuk)
        self._zabelezi(vnuk)
        self.assertEqual(otroci.pocakaj(p, rok=10, rok_konca=2), 0)
        self.assertTrue(pocakaj_konec(vnuk))

    def test_sigkill_ce_skupina_ne_uboga(self):
        ukaz = ["sh", "-c", 'trap "" TERM; sleep 60 & echo $! > "$1"; while :; do sleep 0.1; done', "sh", self.vnuk]
        p = otroci.zazeni(ukaz, stdin=subprocess.DEVNULL)
        vnuk = pocakaj_datoteko(self.vnuk)
        self._zabelezi(p.pid, vnuk)
        zacetek = time.monotonic()
        otroci.ustavi(p, rok=0.5)
        self.assertLess(time.monotonic() - zacetek, 5)
        self.assertEqual(p.returncode, -9)
        self.assertTrue(pocakaj_konec(vnuk))

    def test_pretvorba_datotek_ob_roku(self):
        """os_pretvorba_datotek._zazeni_s_koncem (soffice): pred popravkom je SIGTERM dobil samo glavni proces."""
        with self.assertRaises(subprocess.TimeoutExpired):
            os_pretvorba_datotek._zazeni_s_koncem(self._ukaz_z_vnukom(), 0.5)
        vnuk = pocakaj_datoteko(self.vnuk)
        self._zabelezi(vnuk)
        self.assertTrue(pocakaj_konec(vnuk), "soffice.bin (vnuk) je ostal po roku")

    def test_otrok_brez_svoje_skupine_samo_on(self):
        """Nikoli killpg na skupino Safeer OS: otrok brez start_new_session dobi signal sam."""
        p = subprocess.Popen(["sleep", "60"])
        self._zabelezi(p.pid)
        self.assertIsNone(otroci._skupina(p))
        otroci.ustavi(p, rok=2)
        self.assertEqual(p.returncode, -15)

    def test_nadomestni_objekt(self):
        class Lazni:
            pid = None
            returncode = None
            klici = []

            def poll(self):
                return self.returncode

            def terminate(self):
                self.klici.append("terminate")
                self.returncode = -15

            def wait(self, timeout=None):
                return self.returncode

            def kill(self):
                self.klici.append("kill")

        lazni = Lazni()
        self.assertEqual(otroci.ustavi(lazni), -15)
        self.assertEqual(lazni.klici, ["terminate"])


@unittest.skipUnless(os.name == "posix" and os.path.isdir("/proc"), "samo Linux")
class Izhod(unittest.TestCase):
    def _skript(self, d: str, telo: str) -> str:
        pot = os.path.join(d, "s.py")
        with open(pot, "w") as f:
            f.write(textwrap.dedent("""
                import os, subprocess, sys
                sys.path.insert(0, %r)
                from core import otroci
                d = sys.argv[1]
            """ % KOREN) + textwrap.dedent(telo))
        return pot

    def _pozeni(self, d: str, telo: str) -> None:
        okolje = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
        subprocess.run([sys.executable, self._skript(d, telo), d], check=True, timeout=30, env=okolje)

    def test_dolgoziv_pospravljen_ob_izhodu_uporabniski_ne(self):
        with tempfile.TemporaryDirectory(prefix="otroci-izhod-") as d:
            self._pozeni(d, """
                v = os.path.join(d, "vnuk")
                p = otroci.zazeni(["sh", "-c", 'sleep 60 & echo $! > "$1"; wait', "sh", v], dolgoziv=True)
                # Uporabniski program (kot core/os_programi.py): svoja seja, NE prek otroci - mora preziveti.
                u = subprocess.Popen(["sleep", "60"], start_new_session=True)
                open(os.path.join(d, "pidi"), "w").write("%d %d" % (p.pid, u.pid))
                import time
                while not os.path.exists(v) or not open(v).read().strip():
                    time.sleep(0.02)
                sys.exit(0)      # atexit -> otroci.pospravi_vse
            """)
            with open(os.path.join(d, "pidi")) as f:
                otrok, uporabniski = (int(x) for x in f.read().split())
            vnuk = pocakaj_datoteko(os.path.join(d, "vnuk"))
            # Vsi trije so osiroteli (s.py se je koncal): pospravljanje samo istih procesov, ce se tecejo.
            zapisi = [zabelezi(pid) for pid in (otrok, vnuk, uporabniski)]
            try:
                self.assertTrue(pocakaj_konec(otrok), "dolgoziv otrok je ostal po izhodu")
                self.assertTrue(pocakaj_konec(vnuk), "vnuk dolgozivega otroka je ostal po izhodu")
                self.assertTrue(zivi(uporabniski), "uporabniski program je bil pospravljen")
            finally:
                for zapis in zapisi:
                    ubij_ce_isti(zapis)

    def test_pospravi_vse(self):
        p = otroci.zazeni(["sleep", "60"], dolgoziv=True)
        try:
            self.assertIn(p, otroci.dolgozivi())
            self.assertGreaterEqual(otroci.pospravi_vse(rok=2), 1)
            self.assertEqual(p.returncode, -15)
            self.assertNotIn(p, otroci.dolgozivi())
        finally:
            if p.poll() is None:
                p.kill()


class Vezava(unittest.TestCase):
    """Nasi dolgozivi otroci gredo prek core/otroci; uporabniski programi ne (morajo preziveti Safeer OS)."""

    def beri(self, pot):
        with open(os.path.join(KOREN, pot), encoding="utf-8") as f:
            return f.read()

    def test_nasi_otroci(self):
        for pot, zagon, ustavi in (
                ("core/safeer_drm.py", "self.proces = otroci.zazeni(args,", "otroci.ustavi(self.proces)"),
                ("core/spotify_racun.py", "return otroci.zazeni(args,", "otroci.ustavi(p, rok=5)"),
                ("core/link_sway.py", 'self._sway = otroci.zazeni(["sway", "-c", konf],', "otroci.ustavi(sway, rok=5)"),
                ("core/link_sprotno.py", "t.proces = otroci.zazeni(self.ukaz(", "otroci.ustavi(pr)"),
                ("core/link_pretvorba.py", "p = otroci.zazeni(ukaz,", "otroci.pocakaj(p)"),
                ("core/os_pretvorba_datotek.py", "p = otroci.zazeni(u,", "otroci.pocakaj(p, rok=cas, rok_konca=10)")):
            s = self.beri(pot)
            with self.subTest(pot=pot):
                self.assertIn(zagon, s)
                self.assertIn(ustavi, s)
                self.assertIn("dolgoziv=True", s)

    def test_execv_pospravi(self):
        s = self.beri("core/nova_razlicica.py")
        self.assertLess(s.index("otroci.pospravi_vse()"), s.index("os.execv("))

    def test_uporabniski_programi_ostanejo(self):
        for pot in ("core/os_programi.py", "core/os_odpri_z.py", "core/namizni_programi.py"):
            with self.subTest(pot=pot):
                self.assertNotIn("otroci", self.beri(pot))

    def test_tovor(self):
        self.assertIn(" otroci ", self.beri("packaging/install_os_payload.sh"))
        self.assertIn(" otroci ", self.beri("packaging/install_control_payload.sh"))


if __name__ == "__main__":
    unittest.main()
