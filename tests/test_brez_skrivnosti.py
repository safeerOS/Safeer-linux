"""V repozitoriju ni zasebnih kljucev, zetonov in osebnih podatkov lastnika (pravilo iz AGENTS.md)."""
import hashlib
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

    def test_brez_osebnih_podatkov_lastnika(self):
        """Ime in e-naslovi lastnika ne smejo v repozitorij (AGENTS.md: v besedilu »lastnik«). Preizkus hrani le
        zgoscene vrednosti (z dodatkom), da sam ne vsebuje podatkov, ki jih isce. Nov podatek dodaj v ZASEBNO kot
        hashlib.sha256(("safeer-zasebnost:" + beseda.lower()).encode()).hexdigest()."""
        try:
            datoteke = subprocess.run(["git", "-C", str(KOREN), "ls-files"], capture_output=True, text=True,
                                      check=True, timeout=30).stdout.split("\n")
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git ni na voljo")
        besede = re.compile(r"[^\W\d_]+")
        # Zacetek samo na meji besede: brez tega je iskanje po dolgih vrsticah brez @ kvadratno (minute).
        naslovi = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
        znane: dict = {}

        def zasebno(beseda: str) -> bool:
            if beseda not in znane:
                znane[beseda] = hashlib.sha256(("safeer-zasebnost:" + beseda).encode()).hexdigest() in ZASEBNO
            return znane[beseda]
        najdeno = []
        for ime in filter(None, datoteke):
            pot = KOREN / ime
            try:
                if pot.stat().st_size > 2_000_000:
                    continue
                besedilo = pot.read_text("utf-8", errors="ignore").lower()
            except OSError:
                continue
            kandidati = set(besede.findall(besedilo)) | set(naslovi.findall(besedilo))
            if any(zasebno(b) for b in kandidati):
                najdeno.append(ime)
        self.assertEqual(najdeno, [], "osebni podatek lastnika - zamenjaj z »lastnik«")


#: Zgoscene vrednosti osebnih podatkov lastnika (imena in e-naslovi, male crke) - glej preizkus zgoraj.
ZASEBNO = {
    "ce51747ed13c39501b20799fa40676dd8b01138ba3a29e8e3271fd0157124d27",
    "08f09f3301a6363d74b3f2c74fe5d57ee66cd93f176a42768110c889cdd4ff46",
    "4ac09f9ae7b2184bd229fbd61657e25bc63520fa4598023a1384338e0a0b3759",
    "c478dec6dfae0be58cf5c90d3d025214afef1d4ec52deb6d04c48f92c000d934",
    "5f567bb564e3ad4e275f0a42eaa111ef32150b9bb45216e2654be439b5dc2df1",
    "19f91db34357afcf94980821b7090a09b5f039a224a1a1918362e13bcfd75500",
}


if __name__ == "__main__":
    unittest.main()
