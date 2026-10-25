"""tools/ci_artefakt.py (lastnik 25. 10. 2026: nas WebKit enkrat na kljuc): artefakt drugega teka samo iz zaupanja vrednega
teka. Neodvisni pregled 25. 10. 2026: meja zaupanja je zdruzitev v main - main, oznake v* in pull_request vzamejo samo
artefakt teka main (potisk, commit v zgodovini main), veja tudi svojega, nikoli tujega (M1 »v1-zlo«, M2, M3, M8)."""
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN / "tools"))
import ci_artefakt as ca  # noqa: E402

REPO = "lastnik/repo"
REPO_ID = "1066"
SHA_MAIN = "a" * 40          # commit, ki je bil vrh refs/heads/main (zdruzitev), zdaj v zgodovini main
SHA_TUJ = "b" * 40           # commit, ki ga v main ni (veja, oznaka z imenom »main«)
SHA_GLAVA = "e" * 40         # trenutni vrh refs/heads/main
SHA_VMESNI = "f" * 40        # vmesni commit zdruzene veje: v zgodovini main, a nikoli vrh main (pregled N1 b)

GLAVNA = ca.Potrosnik("refs/heads/main", "push")
GLAVNA_ROCNO = ca.Potrosnik("refs/heads/main", "workflow_dispatch")
OZNAKA = ca.Potrosnik("refs/tags/v1.0.133", "push")
PR = ca.Potrosnik("refs/pull/7/merge", "pull_request")
PR_DELO = ca.Potrosnik("refs/pull/7/merge", "pull_request", "delo-133")     # PR iz veje delo-133 (GITHUB_HEAD_REF)
DELO = ca.Potrosnik("refs/heads/delo-133", "push")
DELO_ROCNO = ca.Potrosnik("refs/heads/delo-133", "workflow_dispatch")
ZLO = ca.Potrosnik("refs/heads/v1-zlo", "push")


def tek(id_, dogodek="push", repo=REPO_ID, veja="delo-133", sha=SHA_TUJ, pot=ca.DELOVNI_TOK):
    t = {"id": id_, "event": dogodek, "head_repository": {"id": int(repo)}, "head_branch": veja, "head_sha": sha}
    if pot is not None:
        t["path"] = pot
    return t


def glavni_api(pot):
    """Lazen API za vir »main«: vrh veje, primerjava commitov (samo s SHA veje - ime »main« je ob oznaki main dvoumno,
    pregled N1 a) in dejavnost refs/heads/main (kateri commiti so bili vrh main)."""
    if pot == "/repos/%s/git/ref/heads/main" % REPO:
        return {"ref": "refs/heads/main", "object": {"sha": SHA_GLAVA, "type": "commit"}}
    if pot.startswith("/repos/%s/compare/" % REPO):
        assert pot.endswith("...%s?per_page=1" % SHA_GLAVA), pot
        sha = pot.split("/compare/", 1)[1].split("...", 1)[0]
        return {"status": {SHA_GLAVA: "identical", SHA_MAIN: "ahead", SHA_VMESNI: "ahead"}.get(sha, "diverged")}
    if pot.startswith("/repos/%s/activity?ref=refs/heads/main" % REPO):
        return [{"after": SHA_GLAVA, "ref": "refs/heads/main", "activity_type": "push"},
                {"after": SHA_MAIN, "ref": "refs/heads/main", "activity_type": "pr_merge"},
                {"after": SHA_TUJ, "ref": "refs/heads/main", "activity_type": "branch_deletion"}]
    raise AssertionError(pot)


class Zaupanje(unittest.TestCase):
    def vir(self, t, potrosnik):
        return ca.vir(t, REPO_ID, potrosnik, glavni_api, REPO)

    def test_v1_zlo_ni_vir_za_izdajo_main_ali_drugo_vejo(self):
        """Pregled M1 (KRITICNO): veja, katere ime se zacne z »v«, ni oznaka izdaje - njen artefakt ne gre v izdajo."""
        zlo = tek(1, veja="v1-zlo")
        for potrosnik in (OZNAKA, GLAVNA, GLAVNA_ROCNO, PR, DELO, DELO_ROCNO):
            with self.subTest(potrosnik=potrosnik):
                self.assertIsNone(self.vir(zlo, potrosnik))
        self.assertEqual(self.vir(zlo, ZLO), "veja")       # samo ista veja (ista domena zaupanja)

    def test_main_in_oznake_samo_iz_main(self):
        """Pregled M2 (VISOKO): main, oznake in pull_request nikoli ne vzamejo artefakta druge veje."""
        for veja in ("delo-133", "gtk4-deb-webkit", "v1.0.133", "nova-funkcija"):
            for potrosnik in (GLAVNA, GLAVNA_ROCNO, OZNAKA, PR):
                with self.subTest(veja=veja, potrosnik=potrosnik):
                    self.assertIsNone(self.vir(tek(1, veja=veja, sha=SHA_MAIN), potrosnik))
        glavna = tek(2, veja="main", sha=SHA_MAIN)
        for potrosnik in (GLAVNA, GLAVNA_ROCNO, OZNAKA, PR, DELO, ZLO):
            with self.subTest(potrosnik=potrosnik):
                self.assertEqual(self.vir(glavna, potrosnik), "main")    # pot navzdol: main za vse

    def test_main_samo_ob_potisku_in_iz_zgodovine_main(self):
        # Rocni zagon na main, pull_request z vejo main in tek oznake z imenom »main« (commit ni v main) niso vir.
        for t in (tek(1, "workflow_dispatch", veja="main", sha=SHA_MAIN), tek(2, "pull_request", veja="main", sha=SHA_MAIN),
                  tek(3, veja="main", sha=SHA_TUJ), tek(4, veja="main", sha="ni-sha")):
            for potrosnik in (GLAVNA, OZNAKA, DELO):
                with self.subTest(tek=t["id"], potrosnik=potrosnik):
                    self.assertIsNone(self.vir(t, potrosnik))

    def test_oznaka_main_ni_tek_main(self):
        """Ponovni pregled N1: tek oznake »main« (head_branch main, push) na commitu, ki ni bil nikoli vrh refs/heads/main
        (vmesni commit zdruzene veje ali tuj commit), ni vir; primerjava je s SHA veje, ne z imenom."""
        for sha in (SHA_VMESNI, SHA_TUJ):
            for potrosnik in (GLAVNA, OZNAKA, PR, DELO):
                with self.subTest(sha=sha[:1], potrosnik=potrosnik):
                    self.assertIsNone(self.vir(tek(1, veja="main", sha=sha), potrosnik))
        self.assertEqual(self.vir(tek(2, veja="main", sha=SHA_GLAVA), OZNAKA), "main")
        klici = []
        ca.iz_glavne(tek(3, veja="main", sha=SHA_MAIN), lambda p: (klici.append(p), glavni_api(p))[1], REPO)
        self.assertFalse([k for k in klici if "...main?" in k], klici)

    def test_dejavnost_ni_dosegljiva(self):
        """Brez dokaza, da je bil commit vrh main (API dejavnosti 403/404), vir ni zaupanja vreden - gradnja v teku."""
        import urllib.error

        def api(pot):
            if "/activity?" in pot:
                raise urllib.error.HTTPError(pot, 403, "Resource not accessible by integration", {}, None)
            return glavni_api(pot)
        opozorila = []
        self.assertFalse(ca.iz_glavne(tek(1, veja="main", sha=SHA_MAIN), api, REPO, opozorila.append))
        self.assertIn("403", opozorila[0])

    def test_veja_iz_sebe_nikoli_iz_tuje(self):
        self.assertEqual(self.vir(tek(1, veja="delo-133"), DELO), "veja")
        self.assertEqual(self.vir(tek(1, "workflow_dispatch", veja="delo-133"), DELO), "veja")
        self.assertEqual(self.vir(tek(1, veja="delo-133"), DELO_ROCNO), "veja")
        self.assertIsNone(self.vir(tek(1, veja="druga"), DELO))
        self.assertIsNone(self.vir(tek(1, "pull_request", veja="delo-133"), DELO))

    def test_pull_request_iz_veje_glave(self):
        """Ponovni pregled N2: PR vzame artefakt teka veje glave (potisk v ta repozitorij) ali main, nikoli tuje veje,
        PR teka ali forka; sam nikoli ne nalaga (nikomur ni vir) in ne osvezuje."""
        self.assertEqual(self.vir(tek(1, veja="delo-133"), PR_DELO), "veja")
        self.assertEqual(self.vir(tek(2, "workflow_dispatch", veja="delo-133"), PR_DELO), "veja")
        self.assertEqual(self.vir(tek(3, veja="main", sha=SHA_MAIN), PR_DELO), "main")
        for t in (tek(4, veja="druga"), tek(5, "pull_request", veja="delo-133"), tek(6, veja="delo-133", repo="999"),
                  tek(7, veja="v1-zlo")):
            with self.subTest(tek=t["id"]):
                self.assertIsNone(self.vir(t, PR_DELO))
        self.assertFalse(PR_DELO.nalaga)
        self.assertFalse(ca.osvezi({"vir": "veja", "ustvarjen": "2026-01-01T00:00:00Z"}, PR_DELO))
        for glava in ("", "main", "refs/heads/delo-133"):                   # brez glave ali glava main: samo main
            with self.subTest(glava=glava):
                self.assertIsNone(ca.Potrosnik("refs/pull/7/merge", "pull_request", glava).domaca_veja)
        self.assertIsNone(ca.Potrosnik("refs/tags/v1.0.133", "push", "delo-133").domaca_veja)   # glava samo pri PR

    def test_repozitorij_in_tok(self):
        """Fork (drug repozitorij), drug tok in manjkajoce polje path (pregled M8) niso vir."""
        for t in (tek(1, veja="main", sha=SHA_MAIN, repo="999"), tek(2, veja="main", sha=SHA_MAIN, pot=None),
                  tek(3, veja="main", sha=SHA_MAIN, pot=".github/workflows/govor.yml"),
                  tek(4, veja="delo-133", pot=None)):
            with self.subTest(tek=t["id"]):
                self.assertIsNone(self.vir(t, DELO))

    def test_osvezitev_samo_v_isti_domeni(self):
        """Pregled M3 (VISOKO): star artefakt drugega vira se pod tem tekom ne nalozi znova (ne »opere« se)."""
        zdaj = datetime(2026, 12, 30, tzinfo=timezone.utc)
        star = "2026-10-25T06:00:00Z"
        self.assertTrue(ca.osvezi({"vir": "main", "ustvarjen": star}, GLAVNA, zdaj))
        self.assertTrue(ca.osvezi({"vir": "veja", "ustvarjen": star}, DELO, zdaj))
        for vir, potrosnik in (("main", DELO), ("main", OZNAKA), ("main", PR), ("main", GLAVNA_ROCNO)):
            with self.subTest(vir=vir, potrosnik=potrosnik):
                self.assertFalse(ca.osvezi({"vir": vir, "ustvarjen": star}, potrosnik, zdaj))
        self.assertFalse(ca.osvezi({"vir": "main", "ustvarjen": "2026-11-25T06:00:00Z"}, GLAVNA, zdaj))
        self.assertFalse(ca.osvezi(None, GLAVNA, zdaj))

    def test_kdo_nalaga(self):
        self.assertTrue(GLAVNA.nalaga)
        self.assertTrue(DELO.nalaga)
        self.assertTrue(DELO_ROCNO.nalaga)
        for potrosnik in (GLAVNA_ROCNO, OZNAKA, PR):
            self.assertFalse(potrosnik.nalaga, potrosnik)

    def test_star(self):
        zdaj = datetime(2026, 12, 30, tzinfo=timezone.utc)
        self.assertTrue(ca.star("2026-10-25T06:00:00Z", zdaj))
        self.assertFalse(ca.star("2026-11-25T06:00:00Z", zdaj))
        self.assertFalse(ca.star("ni-cas", zdaj))


class Najdi(unittest.TestCase):
    def _api(self, artefakti, teki, klici=None):
        def api(pot):
            if klici is not None:
                klici.append(pot)
            if "/actions/artifacts?" in pot:
                stran = int(pot.rsplit("page=", 1)[1])
                return {"artifacts": artefakti[(stran - 1) * 100:stran * 100]}
            if "/actions/runs/" in pot:
                return teki[int(pot.rsplit("/", 1)[1])]
            return glavni_api(pot)
        return api

    def test_najnovejsi_zaupanja_vreden(self):
        def a(t, cas, potekel=False):
            return {"name": "safeer-webkit-tar-k", "expired": potekel, "created_at": cas, "workflow_run": {"id": t}}
        artefakti = [a(30, "2026-10-25T06:00:00Z"), a(40, "2026-10-26T06:00:00Z", True), a(20, "2026-10-24T06:00:00Z"),
                     a(10, "2026-10-20T06:00:00Z"), a(50, "2026-10-25T08:00:00Z")]
        teki = {30: tek(30, "pull_request", veja="main", sha=SHA_MAIN), 20: tek(20, veja="main", sha=SHA_MAIN),
                10: tek(10, veja="main", sha=SHA_MAIN), 50: tek(50, veja="v1-zlo")}
        klici, opozorila = [], []
        izid = ca.najdi("safeer-webkit-tar-k", REPO, REPO_ID, OZNAKA, self._api(artefakti, teki, klici), "",
                        opozorila.append)
        self.assertEqual(izid, {"run_id": "20", "ustvarjen": "2026-10-24T06:00:00Z", "vir": "main", "veja": "main",
                                "sha": SHA_MAIN})
        self.assertIn("name=safeer-webkit-tar-k", klici[0])
        self.assertEqual(len(opozorila), 2)                       # v1-zlo (najnovejsi) in pull_request
        self.assertIn("iz teka 50 ", opozorila[0])
        self.assertIn("iz teka 30 ", opozorila[1])
        self.assertIsNone(ca.najdi("x", REPO, REPO_ID, OZNAKA, lambda p: {"artifacts": []}))

    def test_kandidat_tuje_veje_brez_klica(self):
        """Pregled N5: artefakt, katerega tek po podatkih artefakta ni iz main, te veje ali tega repozitorija, se zavrze
        brez klica API teka (odlocitev o viru pa je vedno iz podatkov teka)."""
        artefakti = [{"name": "k", "expired": False, "created_at": "2026-10-2%dT00:00:00Z" % i,
                      "workflow_run": {"id": i, "head_branch": veja, "head_repository_id": int(repo)}}
                     for i, veja, repo in ((3, "tuja", REPO_ID), (2, "main", "77"), (1, "delo-133", REPO_ID))]
        klici = []
        izid = ca.najdi("k", REPO, REPO_ID, DELO, self._api(artefakti, {1: tek(1, veja="delo-133")}, klici))
        self.assertEqual(izid["run_id"], "1")
        self.assertEqual([k for k in klici if "/actions/runs/" in k], ["/repos/%s/actions/runs/1" % REPO])

    def test_strani(self):
        """Pregled M9: vec kot 100 artefaktov z istim imenom - prebere vse strani in vzame najnovejsega."""
        artefakti = [{"name": "k", "expired": False, "created_at": "2026-10-01T00:%02d:00Z" % (i % 60),
                      "workflow_run": {"id": 1000 + i}} for i in range(100)]
        artefakti.append({"name": "k", "expired": False, "created_at": "2026-10-25T00:00:00Z", "workflow_run": {"id": 7}})
        teki = {i: tek(i, veja="main", sha=SHA_TUJ) for i in range(1000, 1100)}
        teki[7] = tek(7, veja="main", sha=SHA_MAIN)
        self.assertEqual(ca.najdi("k", REPO, REPO_ID, GLAVNA, self._api(artefakti, teki))["run_id"], "7")

    def test_izrecen_tek(self):
        artefakti = [{"name": "k", "expired": False, "created_at": "2026-10-2%dT00:00:00Z" % i, "workflow_run": {"id": i}}
                     for i in (1, 2)]
        teki = {1: tek(1, veja="main", sha=SHA_MAIN), 2: tek(2, veja="v1-zlo")}
        api = self._api(artefakti, teki)
        self.assertEqual(ca.najdi("k", REPO, REPO_ID, DELO, api, "1")["run_id"], "1")
        self.assertIsNone(ca.najdi("k", REPO, REPO_ID, OZNAKA, api, "2"))
        with self.assertRaises(ValueError):
            ca.najdi("k", REPO, REPO_ID, DELO, api, "1; ls")

    def test_neveljavno_ime(self):
        for ime in ("", "a/b", "a b", "a&per_page=1"):
            with self.assertRaises(ValueError):
                ca.najdi(ime, REPO, REPO_ID, DELO, lambda p: {})


class LazniApi(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - ime iz http.server
        odgovor = self.server.podatki.get(self.path)
        if odgovor is None:
            self.send_error(500 if self.server.podatki.get("napaka") else 404)
            return
        telo = json.dumps(odgovor).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(telo)))
        self.end_headers()
        self.wfile.write(telo)

    def log_message(self, *a):
        pass


class KorakVToku(unittest.TestCase):
    """Pravi koraki iz .github/workflows/linux-packages.yml (bash) proti laznemu API na 127.0.0.1; okolje podprocesa z
    env= (AGENTS.md), brez zetona in posrednika tega procesa."""

    def setUp(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("python3-yaml ni namescen")
        self.posli = yaml.safe_load((KOREN / ".github/workflows/linux-packages.yml").read_text(encoding="utf-8"))["jobs"]
        self.streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), LazniApi)
        self.streznik.podatki = {}
        self.nit = threading.Thread(target=self.streznik.serve_forever, daemon=True)
        self.nit.start()
        self._d = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.streznik.shutdown()
        self.streznik.server_close()
        self.nit.join(10)
        self._d.cleanup()

    def _korak(self, posel, ime):
        return next(k for k in self.posli[posel]["steps"] if k.get("name") == ime)

    def _pozeni(self, korak, ref, dogodek, okolje=None):
        izhod = Path(self._d.name) / ("izhod-%d" % len(os.listdir(self._d.name)))
        izhod.write_text("")
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GITHUB_API_URL": "http://127.0.0.1:%d" % self.streznik.server_port,
               "GITHUB_REPOSITORY": REPO, "GITHUB_REPOSITORY_ID": REPO_ID, "GITHUB_REF": ref, "GITHUB_EVENT_NAME": dogodek,
               "GITHUB_OUTPUT": str(izhod), "GH_TOKEN": "x"}
        env.update(okolje or {})
        ukaz = korak["run"].replace("${{ steps.kljuc.outputs.webkit }}", "K").replace("${{ steps.kljuc.outputs.profil }}", "P")
        self.assertNotIn("${{", ukaz)
        r = subprocess.run(["bash", "-e", "-c", ukaz], cwd=str(KOREN), env=env, capture_output=True, text=True, timeout=60)
        return r.returncode, dict(v.split("=", 1) for v in izhod.read_text().splitlines() if "=" in v), r.stdout + r.stderr

    def _artefakti(self, ime, teki):
        pot = "/repos/%s/actions/artifacts?name=%s&per_page=100&page=1" % (REPO, ime)
        self.streznik.podatki[pot] = {"artifacts": [
            {"name": ime, "expired": False, "created_at": "2026-10-2%dT00:00:00Z" % (i % 10), "workflow_run": {"id": t["id"]}}
            for i, t in enumerate(teki)]}
        for t in teki:
            self.streznik.podatki["/repos/%s/actions/runs/%d" % (REPO, t["id"])] = t
        for sha in (SHA_MAIN, SHA_TUJ, SHA_VMESNI, SHA_GLAVA):
            pot_p = "/repos/%s/compare/%s...%s?per_page=1" % (REPO, sha, SHA_GLAVA)
            self.streznik.podatki[pot_p] = glavni_api(pot_p)
        for pot_g in ("/repos/%s/git/ref/heads/main" % REPO,
                      "/repos/%s/activity?ref=refs/heads/main&per_page=100&time_period=quarter" % REPO):
            self.streznik.podatki[pot_g] = glavni_api(pot_g)

    def test_webkit_kljuc_izdaja_ne_vzame_veje_v1_zlo(self):
        korak = self._korak("webkit-kljuc", "Finished WebKitGTK with this key (artifact of main or of this branch)")
        self._artefakti("safeer-webkit-tar-K", [tek(5, veja="main", sha=SHA_MAIN), tek(6, veja="v1-zlo")])
        k, izhod, izpis = self._pozeni(korak, "refs/tags/v1.0.133", "push")
        self.assertEqual((k, izhod["run_id"], izhod["vir"], izhod["nalozi"]), (0, "5", "main", "false"), izpis)
        self.assertIn("iz teka 6 ni iz zaupanja vrednega teka", izpis)
        self._artefakti("safeer-webkit-tar-K", [tek(6, veja="v1-zlo")])
        for ref, dogodek, nalozi in (("refs/tags/v1.0.133", "push", "false"), ("refs/heads/main", "push", "true"),
                                     ("refs/heads/delo-133", "push", "true"), ("refs/pull/7/merge", "pull_request", "false")):
            with self.subTest(ref=ref):
                k, izhod, izpis = self._pozeni(korak, ref, dogodek)
                self.assertEqual((k, izhod["run_id"], izhod["nalozi"]), (0, "", nalozi), izpis)
                self.assertIn("gradnja v tem teku", izpis)
        k, izhod, izpis = self._pozeni(korak, "refs/heads/v1-zlo", "push")
        self.assertEqual((k, izhod["run_id"], izhod["vir"]), (0, "6", "veja"), izpis)
        # Pregled N2: pull_request iz veje v1-zlo (GITHUB_HEAD_REF postavi GitHub) vzame artefakt te veje, ne nalaga.
        k, izhod, izpis = self._pozeni(korak, "refs/pull/7/merge", "pull_request", {"GITHUB_HEAD_REF": "v1-zlo"})
        self.assertEqual((k, izhod["run_id"], izhod["vir"], izhod["nalozi"]), (0, "6", "veja", "false"), izpis)
        k, izhod, izpis = self._pozeni(korak, "refs/pull/7/merge", "pull_request", {"GITHUB_HEAD_REF": "druga"})
        self.assertEqual((k, izhod["run_id"]), (0, ""), izpis)

    def test_profil_pgo_flatpaka(self):
        """Posel webkit-pgo-profil (prej lastna skripta s pravilom »veja v* in vse veje«): ista pravila; izrecno izbran
        nezaupanja vreden tek in napaka API korak ustavita (ne tih ucni tek)."""
        korak = self._korak("webkit-pgo-profil", "Profile with this key (artifact of an earlier trusted run)")
        self.assertIn('python3 tools/ci_artefakt.py najdi "webkit-pgo-profraw-$KLJUC" --tek "$TEK"', korak["run"])
        self._artefakti("webkit-pgo-profraw-K", [tek(1, veja="main", sha=SHA_MAIN), tek(2, veja="nova-funkcija"),
                                                  tek(3, "pull_request", repo="999", veja="main", sha=SHA_MAIN),
                                                  tek(4, veja="v1-zlo")])
        primeri = [  # (ref, dogodek, izbran tek, koda, run_id)
            ("refs/heads/nova-funkcija", "push", "", 0, "2"),       # svoja veja (najnovejsi zaupanja vreden)
            ("refs/heads/druga", "push", "", 0, "1"),               # druga veja: samo main
            ("refs/tags/v1.0.133", "push", "", 0, "1"),             # izdaja: samo main, nikoli v1-zlo
            ("refs/heads/main", "push", "", 0, "1"),
            ("refs/heads/druga", "workflow_dispatch", "3", 1, None),  # izrecno izbran tek iz forka: napaka
            ("refs/tags/v1.0.133", "push", "4", 1, None),           # izrecno izbrana veja v1-zlo pri izdaji: napaka
            ("refs/heads/druga", "workflow_dispatch", "1", 0, "1"),
        ]
        for ref, dogodek, izbran, koda, run_id in primeri:
            with self.subTest(ref=ref, tek=izbran):
                k, izhod, izpis = self._pozeni(korak, ref, dogodek, {"KLJUC": "K", "NOV": "", "TEK": izbran})
                self.assertEqual(k, koda, izpis)
                self.assertEqual(izhod.get("run_id") or None, run_id, izpis)
        k, izhod, izpis = self._pozeni(korak, "refs/heads/main", "push", {"KLJUC": "K", "NOV": "true", "TEK": ""})
        self.assertEqual((k, izhod.get("run_id")), (0, None), izpis)          # rocno: nov ucni tek
        self.streznik.podatki = {"napaka": True}                                # API vrne 500: korak pade
        k, izhod, izpis = self._pozeni(korak, "refs/tags/v1.0.133", "push", {"KLJUC": "K", "NOV": "", "TEK": ""})
        self.assertNotEqual(k, 0, izpis)
        self.assertIn("::error::", izpis)


if __name__ == "__main__":
    unittest.main()
