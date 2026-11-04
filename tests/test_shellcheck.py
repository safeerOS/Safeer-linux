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


class Shellcheck(unittest.TestCase):
    def test_brez_opozoril(self):
        if not shutil.which("shellcheck"):
            if os.environ.get("GITHUB_ACTIONS") == "true":
                self.fail("v CI mora biti shellcheck namescen (linux-packages.yml, hitra-vrata)")
            self.skipTest("shellcheck ni namescen")
        izid = subprocess.run(["shellcheck", "-S", "warning", "-f", "gcc"] + skripte(), capture_output=True, text=True,
                              timeout=300, cwd=KOREN)
        self.assertEqual(izid.stdout.replace(KOREN + "/", ""), "")


if __name__ == "__main__":
    unittest.main()
