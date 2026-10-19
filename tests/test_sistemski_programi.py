"""Programi, ki lahko sami vprasajo za skrbnisko geslo, samo iz sistemskih map - ne po uporabnikovem PATH.

Koncni neodvisni pregled, 19. 10. 2026 (isti razred kot core/root_ukaz.py): Ubuntu 24.04 / Mint 22 da ~/.local/bin pred
/usr/bin. Program, ki tece kot uporabnik, tja podtakne »safeer-cinnamon«, »synaptic-pkexec«, »mintupdate« ...; ob
kliku v Safeer OS uporabnik okno za geslo pricakuje, podtaknjeni program pa poklice pravi pkexec s svojim programom in
dobi root. Preizkusi podtaknejo programe v PATH in preverijo, da se noben ne zazene. Vsak brez popravka pade.
"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import root_ukaz  # noqa: E402

PODTAKNJENI = ("safeer-cinnamon", "synaptic-pkexec", "mintupdate", "mintinstall", "cinnamon-settings",
               "gnome-control-center", "systemctl", "pkexec", "ls", "nmcli", "udisksctl")


class _Podtaknjeno(unittest.TestCase):
    """Mapa s podtaknjenimi programi na zacetku PATH (kot ~/.local/bin)."""

    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        for ime in PODTAKNJENI:
            pot = os.path.join(self.mapa, ime)
            with open(pot, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\necho PODTAKNJEN\n")
            os.chmod(pot, os.stat(pot).st_mode | stat.S_IXUSR)
        self.path = mock.patch.dict(os.environ, {"PATH": self.mapa + os.pathsep + os.environ.get("PATH", "")})
        self.path.start()

    def tearDown(self):
        self.path.stop()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def podtaknjen(self, ukaz) -> bool:
        """Ali bi ukaz zagnal podtaknjen program (sam ali kot program za pkexec)."""
        for i, del_ in enumerate(ukaz[:2]):
            pot = del_ if os.path.isabs(del_) else (shutil.which(del_) if i == 0 else None)
            if pot and os.path.dirname(os.path.realpath(pot)) == os.path.realpath(self.mapa):
                return True
        return False


class SistemskiProgram(_Podtaknjeno):
    def test_ne_po_path(self):
        self.assertTrue(shutil.which("ls").startswith(self.mapa), "preizkus: podtaknjen ls je prvi v PATH")
        pot = root_ukaz.sistemski_program("ls")
        self.assertIn(os.path.dirname(pot), root_ukaz.SISTEMSKE_MAPE)
        self.assertIsNone(root_ukaz.sistemski_program("safeer-cinnamon-ni-ga"))
        self.assertIsNone(root_ukaz.sistemski_program("../bin/ls"))
        self.assertEqual(root_ukaz.sistemski_ukaz(["ls", "-d", "/"])[1:], ["-d", "/"])
        self.assertIsNone(root_ukaz.sistemski_ukaz([os.path.join(self.mapa, "nic")]))

    def test_sistemske_mape_pise_samo_root(self):
        for mapa in root_ukaz.SISTEMSKE_MAPE:
            self.assertTrue(mapa.startswith(("/usr/", "/bin", "/sbin", "/snap/")), mapa)
            if os.path.isdir(mapa):
                s = os.stat(mapa)
                self.assertEqual(s.st_uid, 0, mapa)
                self.assertFalse(s.st_mode & (stat.S_IWGRP | stat.S_IWOTH), mapa)


class NastavitveInOrodja(_Podtaknjeno):
    def _zagnano(self, klic):
        from core import os_sistem
        zagnano = []
        with mock.patch.object(os_sistem.subprocess, "Popen", lambda u, **k: zagnano.append(list(u))), \
                mock.patch.object(root_ukaz, "na_voljo", lambda: True):
            klic(os_sistem)
        return zagnano

    def test_os_sistem(self):
        zagnano = self._zagnano(lambda s: [s.odpri_nastavitve(m) for m in ("paketi", "posodobitve", "themes", "user")]
                                + [s.napajanje("spanje")])
        self.assertEqual([u for u in zagnano if self.podtaknjen(u)], [], zagnano)
        # Synaptic: pkexec in program z absolutno potjo, brez ovoja synaptic-pkexec (ta klice pkexec po PATH).
        self.assertEqual(root_ukaz.ukaz(root_ukaz.SYNAPTIC), [root_ukaz.PKEXEC, "/usr/sbin/synaptic"])
        from core import os_sistem
        self.assertEqual(os_sistem.ORODJA["paketi"], [["pkexec", root_ukaz.SYNAPTIC]])

    def test_sistemske_nastavitve_safeer_os(self):
        import safeer_os
        zagnano = []
        with mock.patch.object(safeer_os.subprocess, "Popen", lambda u, **k: zagnano.append(list(u))):
            safeer_os.sistemske_nastavitve("themes")
        self.assertEqual([u for u in zagnano if self.podtaknjen(u)], [], zagnano)

    def test_safeer_cinnamon_od_vklopa(self):
        import safeer_os
        ukaz = safeer_os._ukaz_safeer_cinnamon()
        self.assertFalse(ukaz and self.podtaknjen(ukaz), ukaz)
        pomocnik = os.path.join(self.mapa, "pomocnik")
        with open(pomocnik, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n")
        os.chmod(pomocnik, 0o755)
        zagnano = []
        with mock.patch.object(safeer_os, "OD_VKLOPA_POMOCNIK", pomocnik), \
                mock.patch.object(safeer_os.subprocess, "run",
                                  lambda u, **k: zagnano.append(list(u)) or subprocess.CompletedProcess(u, 0)):
            safeer_os.od_vklopa(True)
        self.assertEqual([u for u in zagnano if self.podtaknjen(u)], [], zagnano)

    def test_omrezje_in_nosilci(self):
        """nmcli (povezave sistema) in udisksctl (odklop) lahko prek polkita vprasata za geslo."""
        from core import os_datoteke, os_omrezje, os_sistem
        zagnano = []

        def run(u, **_k):
            zagnano.append(list(u))
            return subprocess.CompletedProcess(u, 0, "", "")
        with mock.patch.object(subprocess, "run", run):
            os_omrezje._nmcli(["connection", "delete", "id", "x"])
            os_sistem._zazeni(["nmcli", "radio", "wifi", "off"])
            with mock.patch.object(os_datoteke, "nosilci",
                                   lambda: [{"pot": "/media/usb", "naprava": "/dev/sdz1", "odstranljiv": True}]):
                os_datoteke.izvrzi("/media/usb")
        self.assertEqual([u for u in zagnano if self.podtaknjen(u)], [], zagnano)

    def test_trgovina_programov(self):
        from core import os_ponudniki_programov as P
        zagnano = []
        for ponudnik in ("mintinstall", "gnome-software", "gearlever"):
            P.odpri(ponudnik, lambda u, **k: zagnano.append(list(u)))
        self.assertEqual([u for u in zagnano if self.podtaknjen(u)], [], zagnano)


class OvojiFlatpak(_Podtaknjeno):
    def test_orodje_gostitelja_samo_iz_sistemskih_map(self):
        """Ovoj v /app/host-bin (flatpak-spawn --host) orodje poisce samo v sistemskih mapah gostitelja."""
        ovoji = os.path.join(self.mapa, "host-bin")
        subprocess.run(["bash", os.path.join(KOREN, "packaging", "flatpak_host_wrappers.sh"), ovoji], check=True,
                       capture_output=True, timeout=30)
        # Lazni flatpak-spawn: izpusti --host in --env=, ostalo zazene s PATH klicatelja (s podtaknjenimi programi).
        lazni = os.path.join(self.mapa, "flatpak-spawn")
        with open(lazni, "w", encoding="utf-8") as f:
            f.write('#!/bin/sh\nwhile [ $# -gt 0 ]; do case "$1" in --host|--env=*) shift ;; *) break ;; esac; done\n'
                    'exec "$@"\n')
        os.chmod(lazni, 0o755)
        shutil.copy(os.path.join(ovoji, "safeer-cinnamon"), os.path.join(ovoji, "ls"))
        r = subprocess.run([os.path.join(ovoji, "ls"), "-d", "/"], capture_output=True, text=True, timeout=10)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "/"), r.stderr)
        r = subprocess.run([os.path.join(ovoji, "safeer-cinnamon"), "--od-vklopa"], capture_output=True, text=True,
                           timeout=10)
        self.assertNotIn("PODTAKNJEN", r.stdout)
        if not os.path.exists("/usr/bin/safeer-cinnamon"):
            self.assertEqual(r.returncode, 127, "orodja ni na gostitelju: koda kot manjkajoc ukaz")
        with open(os.path.join(ovoji, "pkexec"), encoding="utf-8") as f:
            self.assertIn('/usr/bin/pkexec "$@"', f.read())


if __name__ == "__main__":
    unittest.main()
