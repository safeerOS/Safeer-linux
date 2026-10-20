"""Vrata izdaje (tools/preveri_pregled.py, 20. 10. 2026): oznaka izdaje samo z zapisom neodvisnega pregleda drugega
ponudnika, brez odprtih kriticnih/visokih najdb in brez sprememb kode po pregledu. Pravi git v zacasnem repozitoriju."""
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]


def _modul():
    spec = importlib.util.spec_from_file_location("preveri_pregled", KOREN / "tools" / "preveri_pregled.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


GLAVA = ("Izdaja: v1.0.129\nCommit: {c}\nPregledovalec: Gemini prek Pi\nPonudnik: {ponudnik}\n"
         "Odprte kriticne in visoke: {odprte}\n\nPovzetek.\n")


class VrataIzdaje(unittest.TestCase):
    def setUp(self):
        if not shutil.which("git"):
            self.skipTest("ni gita")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.m = _modul()
        self.m.KOREN = self.tmp
        okolje = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                      GIT_COMMITTER_EMAIL="t@t")
        self.okolje = okolje
        self._git("init", "-q")
        self._pisi("core/a.py", "x = 1\n")
        self._pisi("packaging/VERSION", "1.0.128\n")
        self.pregledan = self._commit("koda")

    def _git(self, *a):
        return subprocess.run(["git", "-C", str(self.tmp), *a], check=True, capture_output=True, text=True,
                              env=self.okolje).stdout.strip()

    def _pisi(self, pot, besedilo):
        p = self.tmp / pot
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(besedilo, encoding="utf-8")

    def _commit(self, sporocilo):
        self._git("add", "-A")
        self._git("commit", "-q", "-m", sporocilo)
        return self._git("rev-parse", "HEAD")

    def _zapis(self, ponudnik="google", odprte="0", c=None):
        self._pisi("docs/pregledi/v1.0.129.md", GLAVA.format(c=(c or self.pregledan)[:12], ponudnik=ponudnik, odprte=odprte))
        self._pisi("packaging/VERSION", "1.0.129\n")
        return self._commit("izdaja")

    def test_veljaven_pregled_sme_naprej(self):
        izdaja = self._zapis()
        self.assertEqual(self.m.napake("v1.0.129", izdaja), [])
        self.assertEqual(self.m.main(["v1.0.129", izdaja]), 0)

    def test_brez_zapisa_ni_izdaje(self):
        self.assertIn("ni zapisa neodvisnega pregleda", " ".join(self.m.napake("v1.0.129", self.pregledan)))

    def test_isti_ponudnik_kot_avtor_ni_neodvisen(self):
        izdaja = self._zapis(ponudnik="Anthropic")
        self.assertIn("ni neodvisen", " ".join(self.m.napake("v1.0.129", izdaja)))

    def test_ponudnik_avtorja_tudi_v_daljsem_imenu(self):
        """Kimi pregled 20. 10. 2026: »Claude prek Anthropic« ali »Anthropic/Claude« je prej sel skozi (samo celoten niz)."""
        for ponudnik in ("Claude prek Anthropic", "Anthropic/Claude", "claude-opus", "ANTHROPIC API"):
            izdaja = self._zapis(ponudnik=ponudnik)
            self.assertIn("ni neodvisen", " ".join(self.m.napake("v1.0.129", izdaja)), ponudnik)

    def test_odprte_kriticne_ustavijo(self):
        izdaja = self._zapis(odprte="1")
        self.assertIn("mora biti 0", " ".join(self.m.napake("v1.0.129", izdaja)))

    def test_sprememba_kode_po_pregledu_zahteva_nov_pregled(self):
        self._zapis()
        self._pisi("core/a.py", "x = 2\n")
        izdaja = self._commit("po pregledu")
        self.assertIn("core/a.py", " ".join(self.m.napake("v1.0.129", izdaja)))

    def test_zapis_za_drugo_oznako_in_napacna_oblika(self):
        izdaja = self._zapis()
        self.assertTrue(self.m.napake("v1.0.130", izdaja))
        self.assertIn("ni oblike", " ".join(self.m.napake("1.0.129", izdaja)))

    def test_pregledan_commit_ni_prednik(self):
        izdaja = self._zapis(c="0" * 12)
        self.assertIn("ni prednik", " ".join(self.m.napake("v1.0.129", izdaja)))


class VrataVPotiskuInCi(unittest.TestCase):
    def test_pre_push_preveri_oznako_pred_preskokom_testov(self):
        s = (KOREN / "tools" / "pre_push_testi.sh").read_text(encoding="utf-8")
        self.assertIn('tools/preveri_pregled.py" "$ime" "$c"', s)
        self.assertLess(s.index("preveri_pregled.py"), s.index("SAFEER_PRESKOCI_TESTE:-"))
        subprocess.run(["bash", "-n", str(KOREN / "tools" / "pre_push_testi.sh")], check=True)

    def test_ci_izdaja_in_beta_zahtevata_pregled(self):
        potek = (KOREN / ".github" / "workflows" / "linux-packages.yml").read_text(encoding="utf-8")
        for posel, naslednji in (("release", "beta-izdaja"), ("beta-izdaja", None)):
            del_ = potek.split("\n  %s:\n" % posel, 1)[1]
            if naslednji:
                del_ = del_.split("\n  %s:\n" % naslednji, 1)[0]
            self.assertIn('run: python3 tools/preveri_pregled.py "$TAG" "$SHA"', del_, posel)
            self.assertIn("fetch-depth: 0", del_, posel)
            self.assertLess(del_.index("preveri_pregled.py"), del_.index("actions/download-artifact"), posel)


if __name__ == "__main__":
    unittest.main()
