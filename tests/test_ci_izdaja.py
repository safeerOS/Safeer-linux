"""tools/ci_izdaja.py (lastnik 25. 10. 2026: »Izdaja je samo to, kar preizkusim in recem, da lahko objavimo.«): oznaka v*
nicesar ne gradi; izdaja vzame nespremenjene pakete zelenega teka veje tega repozitorija in toka za ISTI commit. Brez
takega teka oznaka pade; tek drugega commita, repozitorija, toka ali dogodka se zavrne."""
import hashlib
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN / "tools"))
import ci_izdaja as ci  # noqa: E402

REPO = "lastnik/repo"
REPO_ID = "1066"
SHA = "c" * 40
DRUG_SHA = "d" * 40
TEKOCI = "999"


def tek(id_, sha=SHA, dogodek="push", repo=REPO_ID, pot=ci.DELOVNI_TOK, zakljucek="success", veja="delo-133",
        ustvarjen="2026-10-25T10:00:00Z"):
    return {"id": id_, "head_sha": sha, "event": dogodek, "head_repository": {"id": int(repo)}, "path": pot,
            "status": "completed", "conclusion": zakljucek, "head_branch": veja, "created_at": ustvarjen}


def posli(**spremembe):
    izid = []
    for posel in ci.POSLI_IZDAJE:
        imena = {"hitra-vrata": ["hitra-vrata (%d)" % i for i in range(1, 7)], "mint": ["mint (22)", "mint (22.3)"],
                 "preizkusi-webkit": ["preizkusi-webkit (1)", "preizkusi-webkit (2)"]}.get(posel, [posel])
        izid += [{"name": i, "conclusion": spremembe.get(i, "success")} for i in imena]
    izid.append({"name": "release", "conclusion": "skipped"})
    return izid


def artefakti(brez=()):
    return [{"name": a, "expired": False} for a in ci.ARTEFAKTI if a not in brez]


class LazenApi:
    def __init__(self, teki, posli_teka=None, artefakti_teka=None):
        self.teki, self.posli, self.artefakti, self.klici = teki, posli_teka or {}, artefakti_teka or {}, []

    def __call__(self, pot):
        self.klici.append(pot)
        if "/actions/workflows/linux-packages.yml/runs?head_sha=" in pot:
            sha = pot.split("head_sha=", 1)[1].split("&", 1)[0]
            return {"workflow_runs": [t for t in self.teki if t["head_sha"] == sha]}
        tek_id = int(pot.split("/runs/", 1)[1].split("/", 1)[0])
        if "/jobs?" in pot:
            return {"jobs": self.posli.get(tek_id, posli())}
        if "/artifacts?" in pot:
            return {"artifacts": self.artefakti.get(tek_id, artefakti())}
        raise AssertionError(pot)


class Najdi(unittest.TestCase):
    def test_zelen_tek_istega_commita(self):
        api = LazenApi([tek(10)])
        izid = ci.najdi(REPO, REPO_ID, SHA, TEKOCI, api)
        self.assertEqual(izid, {"run_id": "10", "veja": "delo-133", "dogodek": "push", "ustvarjen": "2026-10-25T10:00:00Z"})
        self.assertIn("head_sha=%s" % SHA, api.klici[0])

    def test_oznaka_brez_zelenega_teka_pade(self):
        with self.assertRaises(ci.NapakaIzdaje) as e:
            ci.najdi(REPO, REPO_ID, SHA, TEKOCI, LazenApi([]))
        self.assertIn("oznaka nicesar ne gradi", str(e.exception))

    def test_zavrne_tuje_teke(self):
        """Drug commit, drug repozitorij (fork), drug tok, pull_request, rdec ali nedokoncan tek in ta tek sam."""
        api = LazenApi([tek(1, sha=DRUG_SHA)])
        self.assertRaises(ci.NapakaIzdaje, ci.najdi, REPO, REPO_ID, SHA, TEKOCI, api)
        primeri = {"drug repozitorij": tek(2, repo="77"), "drug tok": tek(3, pot=".github/workflows/govor.yml"),
                   "dogodek pull_request": tek(4, dogodek="pull_request"), "ni zelen": tek(5, zakljucek="failure"),
                   "ta tek": tek(int(TEKOCI)), "drug commit": tek(6, sha=DRUG_SHA)}
        for razlog, t in primeri.items():
            with self.subTest(razlog=razlog):
                self.assertIn(razlog, ci.razlog_teka(t, REPO_ID, SHA, TEKOCI))
                with self.assertRaises(ci.NapakaIzdaje) as e:
                    ci.najdi(REPO, REPO_ID, SHA, TEKOCI, LazenApi([t]))
                self.assertIn("oznaka nicesar ne gradi", str(e.exception))

    def test_posli_izdaje_in_artefakti(self):
        """Vsak posel izdaje (tudi mint, preizkusi-webkit) uspesen, ne preskocen; brez artefakta paketi-izdaje (rocni zagon
        z vhodi gradnje) tek ni vir."""
        for opis, p, a in (("mint padel", posli(**{"mint (22.3)": "failure"}), artefakti()),
                           ("preizkusi-webkit preskocen", posli(**{"preizkusi-webkit (2)": "skipped"}), artefakti()),
                           ("brez paketi-izdaje", posli(), artefakti(brez=("paketi-izdaje",))),
                           ("brez flatpak", posli(), artefakti(brez=("flatpak",)))):
            with self.subTest(opis=opis):
                with self.assertRaises(ci.NapakaIzdaje):
                    ci.najdi(REPO, REPO_ID, SHA, TEKOCI, LazenApi([tek(10)], {10: p}, {10: a}))
        brez_mint = [x for x in posli() if not x["name"].startswith("mint")]
        self.assertIn("mint", ci.zakaj_ne(tek(10), REPO_ID, SHA, TEKOCI, brez_mint, artefakti()))

    def test_rocni_zagon_brez_vhodov_gradnje(self):
        api = LazenApi([tek(11, dogodek="workflow_dispatch", ustvarjen="2026-10-25T12:00:00Z"),
                        tek(12, dogodek="workflow_dispatch", ustvarjen="2026-10-25T13:00:00Z")],
                       artefakti_teka={12: artefakti(brez=("paketi-izdaje",))})
        izid = ci.najdi(REPO, REPO_ID, SHA, TEKOCI, api)
        self.assertEqual((izid["run_id"], izid["dogodek"]), ("11", "workflow_dispatch"))   # 12: vhodi gradnje

    def test_vec_zelenih_tekov_pade_izbira_z_vhodom(self):
        """Kot v1.0.128 (3a65bfd: zelena teka main in gtk4-deb-webkit, tek oznake): paketi tekov niso enaki, CI ne ve,
        katere je lastnik preizkusil - ne vzame najnovejsega, ampak pade; izbira z vhodom izdaja_tek."""
        teki = [tek(39343310756, veja="gtk4-deb-webkit", ustvarjen="2026-10-19T23:43:26Z"),
                tek(39364950738, veja="main", ustvarjen="2026-10-20T03:33:48Z"),
                tek(39364325318, veja="v1.0.128", zakljucek="cancelled", ustvarjen="2026-10-20T03:26:46Z")]
        with self.assertRaises(ci.NapakaIzdaje) as e:
            ci.najdi(REPO, REPO_ID, SHA, TEKOCI, LazenApi(teki), oznaka="v1.0.128")
        sporocilo = str(e.exception)
        for del_ in ("39343310756: veja gtk4-deb-webkit", "39364950738: veja main",
                     "gh workflow run linux-packages.yml --ref v1.0.128 -f izdaja_tek=<id>"):
            self.assertIn(del_, sporocilo)
        izid = ci.najdi(REPO, REPO_ID, SHA, TEKOCI, LazenApi(teki), izbran_tek="39343310756")
        self.assertEqual((izid["run_id"], izid["veja"]), ("39343310756", "gtk4-deb-webkit"))
        # Izbrani tek mora prestati iste preverbe: preklican tek oznake, tek drugega commita, tek z vhodi gradnje, ne-stevilo.
        drugi = tek(5, sha=DRUG_SHA)
        api = LazenApi(teki + [drugi, tek(12, dogodek="workflow_dispatch")], artefakti_teka={12: artefakti(brez=("paketi-izdaje",))})
        for izbran in ("39364325318", "5", "12", "abc", "1 OR 1"):
            with self.subTest(izbran=izbran):
                self.assertRaises(ci.NapakaIzdaje, ci.najdi, REPO, REPO_ID, SHA, TEKOCI, api, izbran)

    def test_sha_oznake(self):
        with self.assertRaises(ci.NapakaIzdaje):
            ci.najdi(REPO, REPO_ID, "v1.0.133", TEKOCI, LazenApi([]))


class Preveri(unittest.TestCase):
    PAKETI = {"brskalnik/safeer-browser_1.0_amd64.deb": b"brskalnik", "safeer-os/safeer-os_1.0_amd64.deb": b"os",
              "safeer-os/safeer-os-app_1.0_amd64.deb": b"app", "flatpak/Safeer-OS-1.0-x86_64.flatpak": b"fos",
              "flatpak-brskalnik/Safeer-Browser-1.0-x86_64.flatpak": b"fbr"}

    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.mapa = Path(self._d.name) / "artifacts"
        for ime, vsebina in self.PAKETI.items():
            (self.mapa / ime).parent.mkdir(parents=True, exist_ok=True)
            (self.mapa / ime).write_bytes(vsebina)
        self.pi = self.mapa / "paketi-izdaje"
        self.pi.mkdir()
        self.seznam = "".join("%s  %s\n" % (hashlib.sha256(v).hexdigest(), Path(i).name)
                              for i, v in sorted(self.PAKETI.items(), key=lambda x: Path(x[0]).name))
        (self.pi / "SHA256SUMS").write_text(self.seznam)
        self.vhodi({"dogodek": "push", "pgo": "", "pgo_profraw_run": ""})
        self.cilj = Path(self._d.name) / "release"

    def tearDown(self):
        self._d.cleanup()

    def vhodi(self, v):
        (self.pi / "vhodi.json").write_text(json.dumps(v))

    def test_nespremenjeni_paketi(self):
        (self.mapa / "safeer-os" / "safeer-webkit_2.54_amd64.deb").write_bytes(b"wk")        # ni paket izdaje
        seznam = ci.preveri(self.mapa, self.pi, self.cilj)
        self.assertEqual(len(seznam), 5)
        self.assertEqual(sorted(p.name for p in self.cilj.iterdir()), sorted([Path(i).name for i in self.PAKETI] + ["SHA256SUMS"]))
        self.assertEqual((self.cilj / "SHA256SUMS").read_text(), self.seznam)
        self.assertEqual((self.cilj / "safeer-os_1.0_amd64.deb").read_bytes(), b"os")

    def test_spremenjen_odvec_ali_manjkajoc_paket(self):
        for opis, dejanje in (("spremenjen", lambda: (self.mapa / "flatpak" / "Safeer-OS-1.0-x86_64.flatpak").write_bytes(b"x")),
                              ("odvec", lambda: (self.mapa / "brskalnik" / "safeer-browser_2.0_amd64.deb").write_bytes(b"y")),
                              ("manjka", lambda: (self.mapa / "safeer-os" / "safeer-os-app_1.0_amd64.deb").unlink()),
                              ("AppImage", lambda: (self.mapa / "safeer-os" / "Safeer-OS-1.0-x86_64.AppImage").write_bytes(b"z"))):
            with self.subTest(opis=opis):
                self.tearDown()
                self.setUp()
                dejanje()
                with self.assertRaises(ci.NapakaIzdaje):
                    ci.preveri(self.mapa, self.pi, self.cilj)
                self.assertFalse((self.cilj / "SHA256SUMS").exists())

    def test_neveljaven_seznam_in_vhodi(self):
        for vrstica in ("%s  ../safeer-os_1.0_amd64.deb\n" % ("0" * 64), "%s  safeer-webkit_1_amd64.deb\n" % ("0" * 64),
                        "abc  safeer-os_1.0_amd64.deb\n", ""):
            with self.subTest(vrstica=vrstica):
                (self.pi / "SHA256SUMS").write_text(vrstica)
                self.assertRaises(ci.NapakaIzdaje, ci.preveri, self.mapa, self.pi, self.cilj)
        (self.pi / "SHA256SUMS").write_text(self.seznam)
        for vhodi in ({"dogodek": "workflow_dispatch", "pgo": "true", "pgo_profraw_run": ""},
                      {"dogodek": "workflow_dispatch", "pgo": "false", "pgo_profraw_run": "123"},
                      {"dogodek": "pull_request", "pgo": "", "pgo_profraw_run": ""}):
            with self.subTest(vhodi=vhodi):
                self.vhodi(vhodi)
                self.assertRaises(ci.NapakaIzdaje, ci.preveri, self.mapa, self.pi, self.cilj)
        self.vhodi({"dogodek": "workflow_dispatch", "pgo": "false", "pgo_profraw_run": ""})
        self.assertEqual(len(ci.preveri(self.mapa, self.pi, self.cilj)), 5)


def yaml_vhodi():
    import yaml
    tok = yaml.safe_load((KOREN / ".github/workflows/linux-packages.yml").read_text(encoding="utf-8"))
    return tok[True]["workflow_dispatch"]["inputs"]            # PyYAML prebere kljuc »on« kot True


class _Streznik(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - ime iz http.server
        try:
            telo = json.dumps(self.server.api(self.path)).encode()
        except Exception:  # noqa: BLE001 - lazen API: vsaka napaka je odgovor 500
            self.send_error(500)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(telo)))
        self.end_headers()
        self.wfile.write(telo)

    def log_message(self, *a):
        pass


class KorakIzdaje(unittest.TestCase):
    """Pravi korak posla release in beta-izdaja (bash) proti laznemu API na 127.0.0.1; okolje podprocesa z env=."""

    def setUp(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("python3-yaml ni namescen")
        self.posli = yaml.safe_load((KOREN / ".github/workflows/linux-packages.yml").read_text(encoding="utf-8"))["jobs"]
        self.streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Streznik)
        self.nit = threading.Thread(target=self.streznik.serve_forever, daemon=True)
        self.nit.start()
        self._d = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.streznik.shutdown()
        self.streznik.server_close()
        self.nit.join(10)
        self._d.cleanup()

    def _pozeni(self, posel, izbran=""):
        korak = next(k for k in self.posli[posel]["steps"] if k.get("name") == "Green run of the same commit (the tag builds nothing)")
        izhod = Path(self._d.name) / ("izhod-%s" % posel)
        izhod.write_text("")
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GITHUB_API_URL": "http://127.0.0.1:%d" % self.streznik.server_port,
               "GITHUB_REPOSITORY": REPO, "GITHUB_REPOSITORY_ID": REPO_ID, "GITHUB_SHA": SHA, "GITHUB_RUN_ID": TEKOCI,
               "GITHUB_OUTPUT": str(izhod), "GH_TOKEN": "x", "GITHUB_REF_NAME": "v1.0.133", "IZDAJA_TEK": izbran}
        env.update({k: "x" for k in (korak.get("env") or {}) if k not in env})
        r = subprocess.run(["bash", "-e", "-c", korak["run"]], cwd=str(KOREN), env=env, capture_output=True, text=True, timeout=60)
        return r.returncode, dict(v.split("=", 1) for v in izhod.read_text().splitlines() if "=" in v), r.stdout + r.stderr

    def test_oznaka_brez_teka_pade_s_tekom_vzame_njegove_pakete(self):
        for posel in ("release", "beta-izdaja"):
            with self.subTest(posel=posel):
                self.streznik.api = LazenApi([tek(5, sha=DRUG_SHA), tek(6, repo="77"), tek(7, pot=".github/workflows/x.yml")])
                k, izhod, izpis = self._pozeni(posel)
                self.assertEqual(k, 1, izpis)
                self.assertIn("::error::", izpis)
                self.assertIn("oznaka nicesar ne gradi", izpis)
                self.assertNotIn("run_id", izhod)
                self.streznik.api = LazenApi([tek(8), tek(5, sha=DRUG_SHA)])
                k, izhod, izpis = self._pozeni(posel)
                self.assertEqual((k, izhod.get("run_id")), (0, "8"), izpis)
                # Dva zelena teka istega commita: pade s seznamom; rocni zagon na oznaki z izdaja_tek izbere enega.
                self.streznik.api = LazenApi([tek(8), tek(9, veja="main")])
                k, izhod, izpis = self._pozeni(posel)
                self.assertEqual((k, izhod.get("run_id")), (1, None), izpis)
                self.assertIn("--ref v1.0.133 -f izdaja_tek=<id>", izpis)
                k, izhod, izpis = self._pozeni(posel, izbran="9")
                self.assertEqual((k, izhod.get("run_id"), izhod.get("veja")), (0, "9", "main"), izpis)
                self.assertEqual(self._korak_env(posel)["IZDAJA_TEK"], "${{ inputs.izdaja_tek }}")

    def _korak_env(self, posel):
        return next(k for k in self.posli[posel]["steps"]
                    if k.get("name") == "Green run of the same commit (the tag builds nothing)").get("env") or {}

    def test_seznam_paketov_samo_iz_potiska_ali_rocnega_zagona(self):
        """Artefakt paketi-izdaje nalozi samo potisk ali rocni zagon s privzetima vhodoma gradnje (ne pull_request)."""
        korak = next(k for k in self.posli["paketi-izdaje"]["steps"] if "upload-artifact" in str(k.get("uses")))
        self.assertEqual(korak["if"], "github.event_name == 'push' || (github.event_name == 'workflow_dispatch' && "
                                      "!inputs.pgo && inputs.pgo_profraw_run == '')")
        self.assertEqual(korak["with"]["name"], "paketi-izdaje")
        vhod = yaml_vhodi()["izdaja_tek"]
        self.assertEqual((vhod["type"], vhod["default"]), ("string", ""))

    def test_prenos_samo_iz_najdenega_teka(self):
        for posel in ("release", "beta-izdaja"):
            koraki = self.posli[posel]["steps"]
            prenosi = [k for k in koraki if "download-artifact" in str(k.get("uses"))]
            self.assertEqual(sorted(k["with"]["name"] for k in prenosi), sorted(ci.ARTEFAKTI))
            for k in prenosi:
                self.assertEqual(k["with"]["run-id"], "${{ steps.tek.outputs.run_id }}")
            imena = [k.get("name") for k in koraki]
            self.assertLess(imena.index("Green run of the same commit (the tag builds nothing)"),
                            imena.index("Packages are exactly those of that run (SHA-256 of every file)"))
            preveri = next(k for k in koraki if k.get("name") == "Packages are exactly those of that run (SHA-256 of every file)")
            self.assertEqual(preveri["run"], "python3 tools/ci_izdaja.py preveri artifacts artifacts/paketi-izdaje release")
            self.assertEqual(self.posli[posel]["permissions"], {"contents": "write", "actions": "read"})
            self.assertNotIn("needs", self.posli[posel])


if __name__ == "__main__":
    unittest.main()
