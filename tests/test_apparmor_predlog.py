"""Predlog profilov AppArmor (tedenski pregled 4. 11. 2026, V7): userns samo za bwrap, ne za vse otroke zaganjalnika.
Predlog je v tools/apparmor_predlog/ in NI v paketu, dokler ga ne preizkusimo na Ubuntu 24.04 ali Mintu z
kernel.apparmor_restrict_unprivileged_userns=1. Tu samo zgradba in prevod (apparmor_parser brez nalaganja v jedro)."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
PREDLOG = KOREN / "tools" / "apparmor_predlog"
PROFILI = {"safeer-os": "/usr/bin/safeer-os", "safeer-control": "/usr/bin/safeer-control",
           "safeer-browser": "/usr/bin/safeer"}


def _parser():
    return os.environ.get("SAFEER_APPARMOR_PARSER") or shutil.which("apparmor_parser")


class Zgradba(unittest.TestCase):
    def test_userns_samo_v_podprofilu_bwrap(self):
        for ime, pot in PROFILI.items():
            with self.subTest(ime=ime):
                besedilo = (PREDLOG / ime).read_text(encoding="utf-8")
                self.assertRegex(besedilo, r"(?m)^profile %s %s flags=\(default_allow\) \{$" % (re.escape(ime),
                                                                                               re.escape(pot)))
                glavni, _, ostalo = besedilo.partition("  profile bwrap flags=(default_allow) {\n")
                self.assertTrue(ostalo, "podprofil bwrap")
                podprofil = ostalo.split("\n  }\n", 1)[0]
                self.assertIn("  deny userns,\n", glavni)
                self.assertNotRegex(glavni, r"(?m)^\s*(allow\s+)?userns,$", "glavni profil userns ne dovoli")
                self.assertIn("  /usr/bin/bwrap Cx -> bwrap,\n", glavni)
                self.assertEqual(podprofil.strip(), "userns,")
                self.assertIn("include if exists <local/%s>" % ime, besedilo)
                # Vgrajen WebKit klice sistemski bwrap (packaging/webkit-deb/zgradi.sh: -DBWRAP_EXECUTABLE).
        self.assertIn("-DBWRAP_EXECUTABLE=/usr/bin/bwrap", (KOREN / "packaging/webkit-deb/zgradi.sh").read_text())

    def test_predlog_ni_v_paketu(self):
        """Delujoci profil ostane, dokler predloga ne preizkusimo (namesti.sh bere samo packaging/apparmor)."""
        namesti = (KOREN / "packaging" / "apparmor" / "namesti.sh").read_text(encoding="utf-8")
        self.assertNotIn("apparmor_predlog", namesti)
        for ime in PROFILI:
            self.assertIn("flags=(unconfined)", (KOREN / "packaging" / "apparmor" / ime).read_text(encoding="ascii"))


@unittest.skipUnless(_parser(), "ni apparmor_parser")
class Prevod(unittest.TestCase):
    def _prevedi(self, pot):
        dodatno = os.environ.get("SAFEER_APPARMOR_ARGUMENTI", "").split()
        return subprocess.run([_parser(), *dodatno, "-Q", "-K", "-T", "-S", str(pot)], capture_output=True, timeout=60)

    def test_predlog_se_prevede(self):
        for ime in PROFILI:
            with self.subTest(ime=ime):
                r = self._prevedi(PREDLOG / ime)
                self.assertEqual(r.returncode, 0, r.stderr.decode(errors="replace"))
                self.assertGreater(len(r.stdout), 500)

    def test_prevajalnik_zazna_spor_pravil_x(self):
        """Dokaz, da prevod preveri tudi spor prehodov: natancno pravilo za bwrap mora prevladati nad /** pix."""
        with tempfile.TemporaryDirectory() as d:
            pot = Path(d, "spor")
            pot.write_text("abi <abi/4.0>,\ninclude <tunables/global>\nprofile spor /usr/bin/spor flags=(default_allow) "
                           "{\n  /usr/bin/bwrap Cx -> bwrap,\n  /usr/bin/bwrap px,\n  profile bwrap { }\n}\n")
            self.assertNotEqual(self._prevedi(pot).returncode, 0)


if __name__ == "__main__":
    unittest.main()
