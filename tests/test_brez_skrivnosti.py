"""V repozitoriju ni zasebnih kljucev, zetonov in osebnih podatkov lastnika (pravilo iz AGENTS.md)."""
import hashlib
import os
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
        if not ZASEBNO:
            self.skipTest("ni seznama zasebnih vrednosti (SAFEER_ZASEBNO_SHA256 ali ~/.config/safeer-razvoj/zasebno-sha256)")
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
        zgoscene vrednosti (z dodatkom), da sam ne vsebuje podatkov, ki jih isce. Nov podatek dodaj v lokalni seznam (glej _zasebno_sha256) kot
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


def _zasebno_sha256() -> set:
    """Zgoscene vrednosti osebnih podatkov lastnika NISO v repozitoriju (z javnim dodatkom bi se ime ali e-naslov dalo
    potrditi z ugibanjem). Vir: spremenljivka SAFEER_ZASEBNO_SHA256 (vejice; v CI skrivnost repozitorija) ali lokalna
    datoteka $XDG_CONFIG_HOME/safeer-razvoj/zasebno-sha256 (ena vrednost na vrstico)."""
    vrednosti = os.environ.get("SAFEER_ZASEBNO_SHA256", "").replace(",", "\n").split()
    datoteka = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "safeer-razvoj" / "zasebno-sha256"
    try:
        vrednosti += datoteka.read_text("utf-8").split()
    except OSError:
        pass
    return {v.strip().lower() for v in vrednosti if re.fullmatch(r"[0-9a-fA-F]{64}", v.strip())}


ZASEBNO = _zasebno_sha256()


if __name__ == "__main__":
    unittest.main()
