"""V repozitoriju ni zasebnih kljucev, zetonov in osebnih podatkov lastnika (pravilo iz AGENTS.md)."""
import hashlib
import os
import re
import subprocess
import unittest
from pathlib import Path

try:
    import pwd
except ImportError:     # Windows
    pwd = None

KOREN = Path(__file__).resolve().parents[1]
VZORCI = {
    "zasebni kljuc": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "GitHub zeton": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}"),
    "Google API kljuc": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "AWS kljuc": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Slack zeton": re.compile(r"\bxox[abpr]-[0-9A-Za-z-]{10,}"),
}
PRESKOCI = {"tests/test_brez_skrivnosti.py"}
# Ozke izjeme: datoteka -> razlog. Velja samo za vzorec zasebnega kljuca in samo, ce za glavo ni pravega telesa
# kljuca (PRAVI_KLJUC); pravi kljuc v isti datoteki preizkus se vedno ujame (tedenski pregled 4. 11. 2026).
IZJEME_KLJUC = {
    "tests/test_domaca_mapa_pregled6.py": "lazna glava kljuca v zacasni datoteki - preizkus, da pregled domace mape "
                                          "najde datoteko s kljucem",
    "tests/test_pregled11_ozji_krog.py": "lazna glava kljuca v .crt - preizkus, da Link taksne datoteke ne deli",
}
# Glava, za katero (tudi prek ubezne sekvence \\n v nizu) sledi vsaj 40 znakov base64: tako je videti pravi kljuc.
PRAVI_KLJUC = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----(?:\s|\\n)+[A-Za-z0-9+/=]{40,}")


def _sledene_datoteke(test: unittest.TestCase) -> list:
    """Sledene datoteke repozitorija. Preizkus se NE preskoci, ce git ne dela (prej »git ni na voljo« v CI):
    pod pytest je HOME zacasna mapa (korenski conftest.py), zato globalni safe.directory iz actions/checkout ne
    velja in git v vsebniku (root, delovna mapa drugega uporabnika) zavrne repozitorij. Zato ga podamo z -c."""
    izid = subprocess.run(["git", "-c", "safe.directory=" + str(KOREN), "-C", str(KOREN), "ls-files", "-z"],
                          capture_output=True, text=True, timeout=60)
    test.assertEqual(izid.returncode, 0, "git ls-files ni uspel: " + izid.stderr.strip())
    return [d for d in izid.stdout.split("\0") if d]


class BrezSkrivnosti(unittest.TestCase):
    def test_sledene_datoteke(self):
        # Vzorci kljucev ne potrebujejo seznama zasebnih vrednosti: tecejo vedno, tudi v CI (prej je pogoj
        # »if not ZASEBNO« ta preizkus v CI vedno preskocil, tedenski pregled 4. 11. 2026).
        najdeno = []
        for ime in _sledene_datoteke(self):
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
                if not vzorec.search(besedilo):
                    continue
                if opis == "zasebni kljuc" and ime in IZJEME_KLJUC and not PRAVI_KLJUC.search(besedilo):
                    continue
                najdeno.append(f"{ime}: {opis}")
        self.assertEqual(najdeno, [])

    def test_brez_osebnih_podatkov_lastnika(self):
        """Ime in e-naslovi lastnika ne smejo v repozitorij (AGENTS.md: v besedilu »lastnik«). Preizkus hrani le
        zgoscene vrednosti (z dodatkom), da sam ne vsebuje podatkov, ki jih isce. Nov podatek dodaj v lokalni seznam (glej _zasebno_sha256) kot
        hashlib.sha256(("safeer-zasebnost:" + beseda.lower()).encode()).hexdigest()."""
        if not ZASEBNO:
            # Brez seznama bi preizkus tiho uspel; preskok se izpise (-rs), CI doda se opozorilo (linux-packages.yml).
            self.skipTest("ni seznama zasebnih vrednosti (skrivnost CI SAFEER_ZASEBNO_SHA256 ali lokalna datoteka "
                          "safeer-razvoj/zasebno-sha256 v mapi nastavitev uporabnika)")
        datoteke = _sledene_datoteke(self)
        besede = re.compile(r"[^\W\d_]+")
        # Zacetek samo na meji besede: brez tega je iskanje po dolgih vrsticah brez @ kvadratno (minute).
        naslovi = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
        znane: dict = {}

        def zasebno(beseda: str) -> bool:
            if beseda not in znane:
                znane[beseda] = hashlib.sha256(("safeer-zasebnost:" + beseda).encode()).hexdigest() in ZASEBNO
            return znane[beseda]
        najdeno = []
        for ime in datoteke:
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


class IzjemaKljuca(unittest.TestCase):
    def test_izjema_ne_skrije_pravega_kljuca(self):
        """Izjema velja samo za lazne glave: pravi kljuc PEM (tudi zapisan z \\n v nizu) PRAVI_KLJUC ujame."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        self.assertTrue(PRAVI_KLJUC.search(pem))
        self.assertTrue(PRAVI_KLJUC.search(repr(pem)))
        for lazno in ("-----BEGIN OPENSSH PRIVATE KEY-----\\nb3Blbn\\n", "-----BEGIN PRIVATE KEY-----\\nMII\\n-----END"):
            self.assertIsNone(PRAVI_KLJUC.search(lazno))


def _zasebno_sha256() -> set:
    """Zgoscene vrednosti osebnih podatkov lastnika NISO v repozitoriju (z javnim dodatkom bi se ime ali e-naslov dalo
    potrditi z ugibanjem). Vir: spremenljivka SAFEER_ZASEBNO_SHA256 (vejice; v CI skrivnost repozitorija) ali lokalna
    datoteka $XDG_CONFIG_HOME/safeer-razvoj/zasebno-sha256 (ena vrednost na vrstico)."""
    vrednosti = os.environ.get("SAFEER_ZASEBNO_SHA256", "").replace(",", "\n").split()
    # Pod pytest sta HOME in XDG_CONFIG_HOME zacasni mapi (korenski conftest.py), zato je bil lokalni seznam
    # nedosegljiv in preizkus se je preskocil tudi na razvojnem racunalniku (4. 11. 2026). Pravo domaco mapo vzamemo
    # iz passwd (samo branje).
    mape = [os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")]
    try:
        if pwd is not None:
            mape.append(os.path.join(pwd.getpwuid(os.getuid()).pw_dir, ".config"))
    except (KeyError, OSError):
        pass
    for mapa in dict.fromkeys(mape):
        try:
            vrednosti += (Path(mapa) / "safeer-razvoj" / "zasebno-sha256").read_text("utf-8").split()
        except OSError:
            pass
    return {v.strip().lower() for v in vrednosti if re.fullmatch(r"[0-9a-fA-F]{64}", v.strip())}


ZASEBNO = _zasebno_sha256()


if __name__ == "__main__":
    unittest.main()
