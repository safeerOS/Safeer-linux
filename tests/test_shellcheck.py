"""Skripte lupine brez opozoril shellcheck (raven warning). Tedenski pregled 4. 11. 2026 je nasel 9 opozoril (SC2148,
SC2155, SC2164, SC2034); preizkus jih drzi na nic. V CI je shellcheck namescen (hitra-vrata), zato se tam ne preskoci."""
import glob
import os
import shutil
import subprocess
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def skripte():
    izid = subprocess.run(["git", "-c", "safe.directory=" + KOREN, "-C", KOREN, "ls-files", "-z", "*.sh"],
                          capture_output=True, text=True, timeout=30, check=True).stdout.split("\0")
    dodatne = glob.glob(os.path.join(KOREN, "packaging", "*launcher")) + glob.glob(os.path.join(KOREN, "packaging", "AppRun*"))
    return sorted({os.path.join(KOREN, d) for d in izid if d} | set(dodatne))


def shellcheck(datoteke):
    return subprocess.run(["shellcheck", "-S", "warning", "-f", "gcc"] + list(datoteke), capture_output=True, text=True,
                          timeout=300, cwd=KOREN)


class Shellcheck(unittest.TestCase):
    def setUp(self):
        if not shutil.which("shellcheck"):
            if os.environ.get("GITHUB_ACTIONS") == "true":
                self.fail("v CI mora biti shellcheck namescen (linux-packages.yml, hitra-vrata)")
            self.skipTest("shellcheck ni namescen")

    def _brez_opozoril(self, izid):
        self.assertEqual(izid.stdout.replace(KOREN + "/", ""), "")
        # Napaka orodja (datoteka manjka, ni berljiva) gre na stderr, stdout ostane prazen: brez tega bi preizkus
        # uspel, ne da bi karkoli preveril (CodeRabbit, 4. 11. 2026).
        self.assertEqual(izid.returncode, 0, izid.stderr)

    def test_brez_opozoril(self):
        self._brez_opozoril(shellcheck(skripte()))

    def test_napaka_orodja_ni_uspeh(self):
        izid = shellcheck([os.path.join(KOREN, "packaging", "ne-obstaja-%d.sh" % os.getpid())])
        with self.assertRaises(AssertionError):
            self._brez_opozoril(izid)


if __name__ == "__main__":
    unittest.main()
