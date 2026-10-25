"""Varovalo programov (tests/varovalo_programov.py): preizkus ne zazene pravega pkexec/sudo ne namescenega Safeerja.

25. 10. 2026 14:25: test_sistemski_programi.OvojiFlatpak je prek ovoja Flatpak zagnal pravi /usr/bin/safeer-cinnamon
--od-vklopa -> pkexec (okno za skrbnisko geslo na lastnikovem zaslonu). Preizkusi tu preverijo obe plasti varovala na
lastnem primerku (namescenega v conftest.py ne sprozijo).
"""
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import varovalo_programov as vp  # noqa: E402


class Ukazi(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mapa, True)
        self.v = vp.Varovalo(dovoljeno=self.mapa, dnevnik=os.devnull)

    def test_pravi_programi_za_skrbniske_pravice(self):
        for ukaz in (["pkexec", "/usr/lib/x/od-vklopa", "vklopi"], ["/usr/bin/pkexec", "true"], ["sudo", "-n", "true"],
                     ["env", "LC_ALL=C", "sudo", "ls"], ["timeout", "5", "doas", "ls"], ["nice", "-n", "5", "su", "-c", "x"]):
            self.assertIsNotNone(self.v.razlog_ukaza(ukaz), ukaz)

    def test_namesceni_safeer(self):
        for ukaz in (["/usr/bin/safeer-cinnamon", "--od-vklopa"], ["/usr/lib/safeer-os/safeer_os.py"],
                     ["bash", "/usr/bin/safeer-cinnamon", "--od-vklopa"], ["python3", "/usr/lib/safeer-control/x.py"],
                     ["flatpak", "run", "io.github.memelandfaner.SafeerOS"],
                     ["/var/lib/flatpak/exports/bin/io.github.memelandfaner.SafeerBrowser"]):
            self.assertIsNotNone(self.v.razlog_ukaza(ukaz), ukaz)

    def test_lupina(self):
        skripta = ('for d in /usr/local/sbin /usr/bin; do [ -x "$d/$0" ] && exec "$d/$0" "$@"; done; '
                   'exec /usr/bin/safeer-cinnamon --od-vklopa')
        self.assertIsNotNone(self.v.razlog_ukaza(["/bin/sh", "-c", skripta, "safeer-cinnamon"]))
        self.assertIsNotNone(self.v.razlog_lupine("ls && pkexec /usr/lib/x"))
        self.assertIsNotNone(self.v.razlog_lupine("echo $(sudo cat /etc/shadow)"))
        self.assertIsNone(self.v.razlog_lupine("command -v ls >/dev/null; echo 'pkexec je samo besedilo'"))

    def test_spletni_motor_dovoljen_drugo_pod_safeer_ne(self):
        """Pomozni procesi nasega WebKita (preizkusi tecejo samo z njim): dovoljeni; vse drugo ostane prepovedano."""
        for pot in ("/usr/lib/safeer-webkit/libexec/webkitgtk-6.0/WebKitWebProcess",
                    "/usr/lib/safeer-webkit/libexec/webkitgtk-6.0/WebKitNetworkProcess",
                    "/usr/lib/safeer-browser/webkit-vgrajen/libexec/webkitgtk-6.0/WebKitWebProcess",
                    "/usr/lib/safeer-os/webkit-vgrajen/libexec/webkitgtk-6.0/WebKitGPUProcess"):
            self.assertIsNone(self.v.prepovedana_pot(pot), pot)
            self.assertIsNone(self.v.razlog_ukaza([pot, "7", "8"]), pot)
        for pot in ("/usr/lib/safeer-webkit/libexec/webkitgtk-6.0/jsc",
                    "/usr/lib/safeer-webkit/libexec/webkitgtk-6.0/safeer-cinnamon",
                    "/usr/lib/safeer-webkit/libexec/WebKitWebProcess",
                    "/usr/lib/safeer-os/libexec/webkitgtk-6.0/WebKitWebProcess",
                    "/usr/lib/safeer-webkit/libexec/webkitgtk-6.0/../../../safeer-os/safeer_os.py",
                    "/usr/lib/safeer-os/safeer_os.py", "/usr/bin/safeer-cinnamon", "/usr/bin/pkexec"):
            self.assertIsNotNone(self.v.prepovedana_pot(pot), pot)

    def test_lazni_v_zacasni_mapi_in_navadni_programi(self):
        lazni = os.path.join(self.mapa, "pkexec")
        with open(lazni, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho LAZNI\n")
        os.chmod(lazni, 0o755)
        self.assertIsNone(self.v.razlog_ukaza([lazni, "x"]))
        self.assertIsNone(self.v.razlog_ukaza(["pkexec", "x"], path=self.mapa + os.pathsep + "/usr/bin"),
                          "lazni pkexec na zacetku PATH")
        self.assertIsNotNone(self.v.razlog_ukaza(["pkexec", "x"], path="/usr/bin"), "pravi pkexec po PATH")
        for ukaz in (["ls", "-d", "/"], ["bash", os.path.join(self.mapa, "s.sh")], [sys.executable, "-c", "pass"]):
            self.assertIsNone(self.v.razlog_ukaza(ukaz), ukaz)
        povezava = os.path.join(self.mapa, "ls")
        os.symlink("/usr/bin/pkexec", povezava)
        self.assertIsNotNone(self.v.razlog_ukaza([povezava]), "povezava iz zacasne mape na pravi pkexec")

    def test_podproces_se_ne_zazene(self):
        """Namescen primerek: podproces s prepovedanim programom dobi izjemo, preden se karkoli zazene. Pod varovalom
        je lazen zagon (nikoli pravi - tudi ce varovalo ne bi delovalo, se ne zazene nic)."""
        zagnano = []

        def lazni_init(self_, args, *a, **kw):
            zagnano.append(args)
            raise OSError("preizkus: zagon ni dovoljen")
        v = vp.Varovalo(dovoljeno=self.mapa, dnevnik=os.devnull, koren=-1)     # brez niti potomcev
        with mock.patch.object(subprocess.Popen, "__init__", lazni_init), \
                mock.patch.object(os, "system", lambda u: zagnano.append(u) or 0):
            v.namesti()
            try:
                with self.assertRaises(vp.KrsitevPrograma):
                    subprocess.run(["sudo", "-n", "true"], capture_output=True, timeout=5)
                with self.assertRaises(vp.KrsitevPrograma):
                    subprocess.run("pkexec true", shell=True, capture_output=True, timeout=5)
                with self.assertRaises(vp.KrsitevPrograma):
                    os.system("/usr/bin/safeer-cinnamon --od-vklopa")
                self.assertEqual((len(v.krsitve), zagnano), (3, []), "nic ni prislo do zagona")
                with self.assertRaises(OSError):
                    subprocess.run(["true"], timeout=5)
                self.assertEqual(zagnano, [["true"]], "navaden program gre naprej do zagona")
            finally:
                v.odstrani()


@pytest.mark.skipif(not os.path.isdir("/proc/self/task"), reason="potomci samo prek /proc (Linux)")
class Potomci(unittest.TestCase):
    def test_potomca_s_prepovedanim_programom_ubije_takoj(self):
        """Program, ki ga zazene skripta mimo Pythona: nit ga najde med potomci in ubije (SIGKILL)."""
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa, True)
        lazni_sistem = os.path.join(mapa, "usr-bin")
        os.mkdir(lazni_sistem)
        program = os.path.join(lazni_sistem, "safeer-cinnamon")
        with open(program, "w", encoding="utf-8") as f:
            # Lupina caka v vgrajenem read (brez otroka): prej je `sleep 30` po SIGKILL lupine 30 s ostal kot sirota.
            f.write("#!/bin/sh\nread vrstica\n")
        os.chmod(program, 0o755)
        # Ta primerek: zacasna mapa teka NI dovoljena, »sistemska mapa« je lazni_sistem.
        v = vp.Varovalo(dovoljeno=os.path.join(mapa, "drugje"), dnevnik=os.devnull)
        with mock.patch.object(vp, "PREDPONE", (os.path.join(lazni_sistem, "safeer"),)):
            v.namesti()
            try:
                # Mimo Pythona: lupina zazene skripto (exec), Python vidi samo /bin/sh -c.
                p = subprocess.Popen(["/bin/sh", "-c", 'exec "$0" --od-vklopa', program], stdin=subprocess.PIPE)
                try:
                    zacetek = time.monotonic()
                    koda = p.wait(timeout=10)
                    self.assertLess(time.monotonic() - zacetek, 2.0)
                finally:
                    if p.poll() is None:
                        p.kill()
                        p.wait()
                    p.stdin.close()
            finally:
                v.odstrani()
        self.assertEqual(koda, -signal.SIGKILL)
        self.assertTrue(any("potomec" in k and "safeer-cinnamon" in k for k in v.krsitve), v.krsitve)

    def test_spletni_motor_prezivi_safeer_in_pkexec_ne(self):
        """Pravi procesi (kopije programa sleep) v laznem korenu sistema: WebKitWebProcess nasega WebKita nit pusti,
        safeer-cinnamon in pkexec ubije. 25. 10. 2026 15:12 je varovalo ubijalo WebKitWebProcess nasega WebKita."""
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa, True)
        koren = os.path.join(mapa, "koren")
        motor = os.path.join(koren, "usr/lib/safeer-webkit/libexec/webkitgtk-6.0")
        bin_ = os.path.join(koren, "usr/bin")
        os.makedirs(motor)
        os.makedirs(bin_)
        spanje = shutil.which("sleep")
        programi = {}
        for ime, pot in (("splet", os.path.join(motor, "WebKitWebProcess")),
                         ("safeer", os.path.join(bin_, "safeer-cinnamon")), ("pkexec", os.path.join(bin_, "pkexec"))):
            shutil.copy2(spanje, pot)
            programi[ime] = pot
        # Ta primerek: zacasna mapa teka NI dovoljena, »sistem« je lazni koren.
        v = vp.Varovalo(dovoljeno=os.path.join(mapa, "drugje"), dnevnik=os.devnull)
        procesi = {}
        with mock.patch.object(vp, "PREDPONE", (os.path.join(bin_, "safeer"), os.path.join(koren, "usr/lib/safeer"))), \
                mock.patch.object(vp, "SPLETNI_MOTOR_MAPE", (motor,), create=True):
            v.namesti()
            try:
                for ime, pot in programi.items():
                    # Mimo Pythona (kot WebKit prek GLib): lupina zazene program, Python vidi samo /bin/sh -c.
                    procesi[ime] = subprocess.Popen(["/bin/sh", "-c", 'exec "$0" 30', pot])
                konec = time.monotonic() + 3.0
                while time.monotonic() < konec and (procesi["safeer"].poll() is None or procesi["pkexec"].poll() is None):
                    time.sleep(0.05)
                time.sleep(10 * vp.PREGLED_S)      # se deset pregledov za spletni motor
                splet_zivi = procesi["splet"].poll() is None
            finally:
                v.odstrani()
                for p in procesi.values():
                    if p.poll() is None:
                        p.kill()
                    p.wait()
        self.assertTrue(splet_zivi, "WebKitWebProcess nasega WebKita je ubit: %s" % v.krsitve)
        self.assertEqual(procesi["safeer"].returncode, -signal.SIGKILL, v.krsitve)
        self.assertEqual(procesi["pkexec"].returncode, -signal.SIGKILL, v.krsitve)
        self.assertFalse(any("WebKitWebProcess" in k for k in v.krsitve), v.krsitve)

    def test_program_s_setuid_po_imenu(self):
        """pkexec/sudo imata setuid: exe ni berljiv, odloci ime v cmdline."""
        v = vp.Varovalo(dovoljeno=tempfile.gettempdir(), dnevnik=os.devnull)
        p = subprocess.Popen(["sleep", "30"])
        try:
            with mock.patch.object(vp.os, "readlink", side_effect=PermissionError(13, "setuid")), \
                    mock.patch("builtins.open", mock.mock_open(read_data=b"pkexec\0/usr/lib/x/od-vklopa\0vklopi\0")):
                self.assertIsNotNone(v.razlog_procesa(p.pid))
            self.assertIsNone(v.razlog_procesa(p.pid), "pravi sleep ni prepovedan")
        finally:
            p.kill()
            p.wait()


if __name__ == "__main__":
    unittest.main()
