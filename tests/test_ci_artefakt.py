"""tools/ci_artefakt.py (lastnik 25. 10. 2026: nas WebKit enkrat na kljuc): gradnja iz artefakta drugega teka samo, ce je
tek zaupanja vreden - ta repozitorij, push/workflow_dispatch istega toka, pri oznaki izdaje veja izdaje ali isti commit."""
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN / "tools"))
import ci_artefakt as ca  # noqa: E402

REPO_ID = "1066"


def tek(id_, dogodek="push", repo=REPO_ID, veja="delo-133", sha="a" * 40, pot=ca.DELOVNI_TOK):
    return {"id": id_, "event": dogodek, "head_repository": {"id": int(repo)}, "head_branch": veja, "head_sha": sha,
            "path": pot}


class Zaupanje(unittest.TestCase):
    def test_pravila(self):
        self.assertTrue(ca.zaupanja_vreden(tek(1), REPO_ID, False, ""))
        self.assertTrue(ca.zaupanja_vreden(tek(1, "workflow_dispatch"), REPO_ID, False, ""))
        self.assertFalse(ca.zaupanja_vreden(tek(1, "pull_request"), REPO_ID, False, ""))
        self.assertFalse(ca.zaupanja_vreden(tek(1, repo="999"), REPO_ID, False, ""))        # fork
        self.assertFalse(ca.zaupanja_vreden(tek(1, pot=".github/workflows/govor.yml"), REPO_ID, False, ""))
        # Oznaka izdaje: samo veje izdaje, oznake ali isti commit.
        self.assertFalse(ca.zaupanja_vreden(tek(1), REPO_ID, True, "b" * 40))
        self.assertTrue(ca.zaupanja_vreden(tek(1), REPO_ID, True, "a" * 40))
        for veja in ("main", "gtk4-deb-webkit", "v1.0.133"):
            self.assertTrue(ca.zaupanja_vreden(tek(1, veja=veja), REPO_ID, True, "b" * 40), veja)

    def test_najdi_najnovejsi_zaupanja_vreden(self):
        artefakti = {"artifacts": [
            {"name": "safeer-webkit-tar-k", "expired": False, "created_at": "2026-10-25T06:00:00Z",
             "workflow_run": {"id": 30}},                                                       # pull_request: ne
            {"name": "safeer-webkit-tar-k", "expired": True, "created_at": "2026-10-26T06:00:00Z",
             "workflow_run": {"id": 40}},                                                       # potekel: ne
            {"name": "safeer-webkit-tar-k", "expired": False, "created_at": "2026-10-24T06:00:00Z",
             "workflow_run": {"id": 20}},
            {"name": "safeer-webkit-tar-k", "expired": False, "created_at": "2026-10-20T06:00:00Z",
             "workflow_run": {"id": 10}},
        ]}
        teki = {30: tek(30, "pull_request"), 20: tek(20), 10: tek(10)}
        klici, opozorila = [], []

        def api(pot):
            klici.append(pot)
            if "/artifacts?" in pot:
                return artefakti
            return teki[int(pot.rsplit("/", 1)[1])]
        izid = ca.najdi("safeer-webkit-tar-k", "safeerOS/Safeer-linux", REPO_ID, False, "", api, opozorila.append)
        self.assertEqual(izid, {"run_id": "20", "ustvarjen": "2026-10-24T06:00:00Z"})
        self.assertIn("name=safeer-webkit-tar-k", klici[0])
        self.assertEqual(len(opozorila), 1)
        self.assertIsNone(ca.najdi("x", "r/r", REPO_ID, False, "", lambda p: {"artifacts": []}))

    def test_neveljavno_ime(self):
        for ime in ("", "a/b", "a b", "a&per_page=1"):
            with self.assertRaises(ValueError):
                ca.najdi(ime, "r/r", REPO_ID, False, "", lambda p: {})

    def test_osvezitev_po_60_dneh(self):
        zdaj = datetime(2026, 12, 30, tzinfo=timezone.utc)
        self.assertTrue(ca.star("2026-10-25T06:00:00Z", zdaj))
        self.assertFalse(ca.star("2026-11-25T06:00:00Z", zdaj))
        self.assertFalse(ca.star("ni-cas", zdaj))

    def test_izhod_koraka(self):
        """Brez zetona v okolju tega procesa: podproces z env= (AGENTS.md), lazni API prek pythonovega -c."""
        with tempfile.TemporaryDirectory() as d:
            izhod = Path(d) / "izhod"
            koda = ("import sys, json; sys.path.insert(0, %r); import ci_artefakt as ca; "
                    "ca._api = lambda z: (lambda p: {'artifacts': []}); sys.exit(ca.main(['najdi', 'flatpak-builder-os-ab']))"
                    % str(KOREN / "tools"))
            okolje = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GITHUB_REPOSITORY": "safeerOS/Safeer-linux",
                      "GITHUB_REPOSITORY_ID": REPO_ID, "GH_TOKEN": "x", "GITHUB_OUTPUT": str(izhod), "IZDAJA": "false"}
            r = subprocess.run([sys.executable, "-I", "-c", koda], capture_output=True, text=True, env=okolje, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(izhod.read_text().splitlines(),
                             ["ime=flatpak-builder-os-ab", "run_id=", "ustvarjen=", "osvezi=false"])
            self.assertIn("gradnja v tem teku", r.stdout)


if __name__ == "__main__":
    unittest.main()
