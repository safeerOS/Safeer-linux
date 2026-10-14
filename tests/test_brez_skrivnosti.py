"""V repozitoriju ni zasebnih kljucev in zetonov (pravilo iz AGENTS.md)."""
import re
import subprocess
import unittest
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
VZORCI = {
    "zasebni kljuc": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "GitHub zeton": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}"),
    "Google API kljuc": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "AWS kljuc": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Slack zeton": re.compile(r"\bxox[abpr]-[0-9A-Za-z-]{10,}"),
}
PRESKOCI = {"tests/test_brez_skrivnosti.py"}


class BrezSkrivnosti(unittest.TestCase):
    def test_sledene_datoteke(self):
        try:
            datoteke = subprocess.run(["git", "-C", str(KOREN), "ls-files"], capture_output=True, text=True,
                                      check=True, timeout=30).stdout.split("\n")
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git ni na voljo")
        najdeno = []
        for ime in filter(None, datoteke):
            if ime in PRESKOCI:
                continue
            pot = KOREN / ime
            try:
                if pot.stat().st_size > 2_000_000:
                    continue
                besedilo = pot.read_text("utf-8", errors="ignore")
            except OSError:
                continue
            for opis, vzorec in VZORCI.items():
                if vzorec.search(besedilo):
                    najdeno.append(f"{ime}: {opis}")
        self.assertEqual(najdeno, [])


if __name__ == "__main__":
    unittest.main()
