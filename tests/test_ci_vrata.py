"""CI Safeer-linux (lastnik 25. 10. 2026: »za veliko gradnje je relativno malo uspehov«): hitra vrata pred vsako gradnjo,
preizkusi z WebKitom samo z nasim WebKitom, en tek na vejo, WebKit enkrat na kljuc (artefakt za vse veje).

Suha preverba grafa poslov (needs) in nastavitev, brez potiska: napaka v delovnem toku se pokaze v hitrih vratih."""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - hitra vrata ga namestijo (python3-yaml)
    yaml = None

KOREN = Path(__file__).resolve().parents[1]
DELOVNI_TOK = KOREN / ".github" / "workflows" / "linux-packages.yml"
sys.path.insert(0, str(KOREN / "tests"))
import razvrstitev_webkit as rw  # noqa: E402
sys.path.insert(0, str(KOREN / "tools"))
import ci_izdaja  # noqa: E402

#: Posli, ki trajajo minute do ur ali gradijo pakete: vsi cakajo na hitra vrata (neposredno ali posredno).
DRAGI = ("webkit-kljuc", "webkit-deb-profil", "webkit-deb", "brskalnik", "safeer-os", "qt-xcb", "mint", "debian",
         "webkit-pgo-profil", "webkit-pgo-ucenje", "flatpak", "flatpak-brskalnik", "preizkusi-webkit", "paketi-izdaje")
#: Posla izdaje ob oznaki v*: brez needs in brez gradnje (paketi iz zelenega teka istega commita, tools/ci_izdaja.py).
IZDAJA = ("release", "beta-izdaja")
#: Gostitelji GitHub (enkratni VM): vsebnik --privileged nikoli na lastnem tekacu (pregled M10, N8 a: brez izrazov).
GOSTITELJI_GITHUB = frozenset({"ubuntu-24.04", "ubuntu-22.04", "ubuntu-latest", "ubuntu-24.04-arm"})


def gostitelj_github(runs_on) -> bool:
    return isinstance(runs_on, str) and runs_on in GOSTITELJI_GITHUB


#: Spletni pogon ne sme v hitra vrata ne kot sistemski v posel preizkusi-webkit.
SISTEMSKI_WEBKIT = re.compile(r"\b(gir1\.2-webkit-6\.0|gir1\.2-soup-3\.0|gir1\.2-javascriptcoregtk|libwebkitgtk-6\.0-4)\b")


class DelovniTok(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if yaml is None:
            raise unittest.SkipTest("python3-yaml ni namescen")
        cls.wf = yaml.safe_load(DELOVNI_TOK.read_text(encoding="utf-8"))
        cls.posli = cls.wf["jobs"]

    def _potrebe(self, posel):
        n = self.posli[posel].get("needs", [])
        return [n] if isinstance(n, str) else list(n)

    def _predhodniki(self, posel, videni=None):
        videni = set() if videni is None else videni
        for n in self._potrebe(posel):
            self.assertIn(n, self.posli, "%s: needs %s ne obstaja" % (posel, n))
            if n not in videni:
                videni.add(n)
                self._predhodniki(n, videni)
        return videni

    def _ukazi(self, posel):
        return "\n".join(k.get("run") or "" for k in self.posli[posel]["steps"])

    def test_graf_brez_ciklov_in_dragi_posli_za_vrati(self):
        for posel in self.posli:
            self.assertNotIn(posel, self._predhodniki(posel), "cikel v needs: %s" % posel)
        for posel in DRAGI:
            with self.subTest(posel=posel):
                self.assertLessEqual({"hitra-vrata", "ruff-nova-koda"}, self._predhodniki(posel))
        for posel in ("hitra-vrata", "ruff-nova-koda"):
            self.assertEqual(self._potrebe(posel), [], posel)
        # Izdaja ne caka na posle istega teka (ob oznaki se nic ne gradi), zahteva pa, da so v izvornem teku istega
        # commita uspesni vsi posli, na katere je prej cakala (tools/ci_izdaja.py POSLI_IZDAJE).
        for izdaja in IZDAJA:
            self.assertEqual(self._potrebe(izdaja), [], izdaja)
        self.assertLessEqual({"hitra-vrata", "preizkusi-webkit", "brskalnik", "safeer-os", "qt-xcb", "flatpak",
                              "flatpak-brskalnik", "scit-lab", "mint", "debian", "paketi-izdaje"}, set(ci_izdaja.POSLI_IZDAJE))
        self.assertLessEqual(set(ci_izdaja.POSLI_IZDAJE), set(self.posli))

    def test_oznaka_nicesar_ne_gradi(self):
        """Lastnik 25. 10. 2026 (»Izdaja je samo to, kar preizkusim«): ob oznaki v* se preskoci vsak posel razen release in
        beta-izdaja. Korenski posli imajo pogoj »ne oznaka«; ostali brez statusne funkcije (privzeti success()) ali s
        pogojem needs.<x>.result == 'success' na najvisji ravni se preskocijo, ker je kateri od njihovih needs preskocen."""
        ne_oznaka = "${{ !startsWith(github.ref, 'refs/tags/') }}"

        def deli(pogoj):
            p = pogoj.strip()
            if p.startswith("${{") and p.endswith("}}"):
                p = p[3:-2].strip()
            izid, globina, zacetek = [], 0, 0
            for i, z in enumerate(p):
                globina += (z == "(") - (z == ")")
                if globina == 0 and p.startswith("&&", i):
                    izid.append(p[zacetek:i].strip())
                    zacetek = i + 2
            return izid + [p[zacetek:].strip()]

        preskocen = {}
        for _ in range(len(self.posli)):
            for ime, posel in self.posli.items():
                if ime in IZDAJA or ime in preskocen:
                    continue
                potrebe, pogoj = self._potrebe(ime), str(posel.get("if") or "")
                if not potrebe:
                    self.assertEqual(pogoj, ne_oznaka, ime)
                    preskocen[ime] = True
                elif all(p in preskocen for p in potrebe):
                    statusna = any(f in pogoj for f in ("always()", "cancelled()", "failure()", "success()"))
                    if not statusna or any(d == "needs.%s.result == 'success'" % p for d in deli(pogoj) for p in potrebe):
                        preskocen[ime] = True
        self.assertEqual(set(preskocen), set(self.posli) - set(IZDAJA))
        for izdaja in IZDAJA:
            self.assertTrue(str(self.posli[izdaja]["if"]).startswith("startsWith(github.ref, 'refs/tags/v')"), izdaja)
            self.assertIn("python3 tools/ci_izdaja.py najdi", self._ukazi(izdaja))

    def test_preskok_vrat_preskoci_gradnje(self):
        """Posel z `if: !cancelled() ...` bi tekel tudi, ce hitra vrata padejo: pogoj mora zahtevati uspeh korena verige."""
        for posel, koren in (("webkit-deb", "needs.webkit-kljuc.result == 'success'"),
                             ("flatpak", "needs.webkit-pgo-profil.result == 'success'"),
                             ("flatpak-brskalnik", "needs.webkit-pgo-profil.result == 'success'")):
            pogoj = str(self.posli[posel].get("if", ""))
            self.assertIn("!cancelled()", pogoj)
            self.assertIn(koren, pogoj, posel)
        for posel in DRAGI:
            pogoj = str(self.posli[posel].get("if", ""))
            if "always()" in pogoj or ("!cancelled()" in pogoj and "result == 'success'" not in pogoj):
                self.fail("%s tece tudi po padcu hitrih vrat: %s" % (posel, pogoj))

    def test_hitra_vrata(self):
        v = self.posli["hitra-vrata"]
        deli = v["strategy"]["matrix"]["del"]
        self.assertFalse(v["strategy"].get("fail-fast", True))      # vse napake v enem teku, ne samo prvi del
        self.assertEqual(deli, list(range(1, len(deli) + 1)))
        ukazi = self._ukazi("hitra-vrata")
        self.assertIn("-p razvrstitev_webkit --safeer-webkit=brez --safeer-del=${{ matrix.del }}/%d " % len(deli), ukazi)
        self.assertIn("--continue-on-collection-errors", ukazi)
        self.assertNotRegex(ukazi.split("--safeer-webkit", 1)[0], SISTEMSKI_WEBKIT)
        self.assertNotRegex(ukazi, SISTEMSKI_WEBKIT)
        self.assertIn("python3-yaml", ukazi)                          # preizkusi delovnega toka tecejo, ne preskocijo
        self.assertIn("::error::v hitrih vratih je WebKitGTK ali libsoup GI", ukazi)
        self.assertLessEqual(v.get("timeout-minutes", 360), 30)
        ruff = self._ukazi("ruff-nova-koda")
        self.assertIn("python3 tools/ruff_nove_vrstice.py", ruff)
        self.assertIn("python3 packaging/check_version.py", ruff)

    def test_najprej_padli_in_ponovni_tek_dela(self):
        """Lastnik 25. 10. 2026: »nadaljuj od tam, kjer je preizkus padel«. Vsak del je svoj posel (matrika: »Re-run failed
        jobs« znova pozene samo padli del); padli preizkusi prejsnjega teka iste veje tecejo najprej in sami."""
        for posel, nacin in (("hitra-vrata", "brez"), ("preizkusi-webkit", "samo")):
            with self.subTest(posel=posel):
                p = self.posli[posel]
                deli = len(p["strategy"]["matrix"]["del"])
                self.assertGreaterEqual(deli, 2)
                self.assertFalse(p["strategy"]["fail-fast"])
                koraki = [k.get("name", "") for k in p["steps"]]
                i_obnovi = koraki.index("Failed tests of the previous run of this branch (this part)")
                i_najprej = next(i for i, k in enumerate(koraki) if k.startswith("Previously failed tests first"))
                i_vsi = next(i for i, k in enumerate(koraki) if k.startswith("Unit tests"))
                i_shrani = koraki.index("Failed tests for the next run of this branch (this part)")
                self.assertLess(i_obnovi, i_najprej)
                self.assertLess(i_najprej, i_vsi)
                self.assertLess(i_vsi, i_shrani)
                obnovi, shrani = p["steps"][i_obnovi], p["steps"][i_shrani]
                self.assertEqual(obnovi["with"]["path"], shrani["with"]["path"])       # sicer predpomnilnik ne ujame
                self.assertEqual(obnovi["with"]["key"], shrani["with"]["key"])
                self.assertIn("${{ github.ref_name }}", obnovi["with"]["key"])         # iste veje, ne main
                self.assertIn("${{ matrix.del }}", obnovi["with"]["key"])
                self.assertIn("${{ github.run_attempt }}", obnovi["with"]["key"])      # tudi »Re-run failed jobs«
                self.assertTrue(obnovi["with"]["restore-keys"].strip().endswith("-${{ matrix.del }}-"))
                self.assertTrue(shrani["if"].startswith("always()"))
                najprej = p["steps"][i_najprej]["run"]
                self.assertIn("--safeer-najprej-padli", najprej)
                self.assertIn("--safeer-webkit=%s --safeer-del=${{ matrix.del }}/%d" % (nacin, deli), najprej)
                vsi = p["steps"][i_vsi]["run"]
                self.assertIn("--safeer-padli=build/padli.json", vsi)
                self.assertNotIn("--safeer-najprej-padli", vsi)
                self.assertIn("--safeer-del=${{ matrix.del }}/%d" % deli, vsi)
                self.assertIn("-p no:cacheprovider", vsi)                              # pytest cache ostane izklopljen

    def test_orodja_zivih_preizkusov(self):
        """Hitra vrata in preizkusi-webkit imata isti nabor odvisnosti (razen paketa safeer-webkit); x11-utils (xwininfo)
        potrebuje zivi preizkus test_lupina_locena::Zivo - brez njega se preskoci z razlogom »... WebKitGTK« in posel
        preizkusi-webkit pade (izmerjeno 25. 10. 2026 v vsebniku ubuntu:24.04 z nasim WebKitom)."""
        def apt(posel):
            vrstica = next(v for v in self._ukazi(posel).splitlines() if "apt-get install -y -q ca-certificates" in v)
            return set(vrstica.split()[4:])
        self.assertEqual(apt("hitra-vrata"), apt("preizkusi-webkit"))
        self.assertIn("x11-utils", apt("preizkusi-webkit"))
        vir = (KOREN / "tests" / "test_lupina_locena.py").read_text(encoding="utf-8")
        self.assertIn('shutil.which("xwininfo")', vir)

    def test_preizkusi_z_nasim_webkitom(self):
        p = self.posli["preizkusi-webkit"]
        self.assertIn("webkit-deb", self._potrebe("preizkusi-webkit"))
        ukazi = self._ukazi("preizkusi-webkit")
        self.assertNotRegex(ukazi, SISTEMSKI_WEBKIT)
        self.assertIn("apt-get install -y -q --no-install-recommends ./build/safeer-webkit/safeer-webkit_*_amd64.deb", ukazi)
        self.assertIn('GI_TYPELIB_PATH="$W/girepository-1.0"', ukazi)
        self.assertIn("W=/usr/lib/safeer-webkit/lib", ukazi)
        self.assertIn("-p razvrstitev_webkit --safeer-webkit=samo", ukazi)
        self.assertIn("--safeer-del=${{ matrix.del }}/%d" % len(p["strategy"]["matrix"]["del"]), ukazi)
        self.assertNotIn("LD_LIBRARY_PATH", ukazi)                    # kot core/zasebni_webkit.nastavi()
        self.assertEqual(p["container"]["image"], "ubuntu:24.04")
        prenos = [k for k in p["steps"] if "download-artifact" in str(k.get("uses"))]
        self.assertEqual([k["with"]["name"] for k in prenos], ["safeer-webkit"])

    def test_vsak_pytest_z_razvrstitvijo(self):
        """Noben posel ne pozene vseh preizkusov z enim WebKitom (prej safeer-os: sistemski WebKitGTK); vsak pytest v CI
        izbere nacin, hitra vrata in preizkusi-webkit pa skupaj pokrijejo vse datoteke (test_razvrstitev_webkit)."""
        nacini = []
        for posel in self.posli:
            for vrstica in self._ukazi(posel).replace("\\\n", " ").splitlines():
                if "-m pytest" in vrstica:
                    m = re.search(r"--safeer-webkit=(brez|samo)", vrstica)
                    self.assertIsNotNone(m, "%s: pytest brez --safeer-webkit: %s" % (posel, vrstica.strip()))
                    nacini.append((posel, m.group(1)))
        self.assertEqual(sorted(set(nacini)), [("hitra-vrata", "brez"), ("preizkusi-webkit", "samo")])
        self.assertEqual(len(nacini), 4)                                  # vsak posel: najprej padli + cel del
        self.assertNotIn("Unit tests", " ".join(k.get("name", "") for k in self.posli["safeer-os"]["steps"]))

    def test_en_tek_na_vejo(self):
        c = self.wf["concurrency"]
        self.assertIn("github.ref", c["group"])
        self.assertIn("github.event.pull_request.number", c["group"])
        # Oznake se ne preklicejo; main tudi ne (ponovni pregled N2: tek main nalozi WebKit za vse veje).
        self.assertEqual(c["cancel-in-progress"], "${{ !startsWith(github.ref, 'refs/tags/') && github.ref != 'refs/heads/main' }}")
        for izdaja in ("release", "beta-izdaja"):
            self.assertEqual(self.posli[izdaja]["concurrency"]["cancel-in-progress"], False)

    def test_webkit_enkrat_na_kljuc(self):
        """Gotov WebKit, profil PGO in predpomnilnik flatpak-builderja: artefakt s kljucem (90 dni) iz zaupanja vrednega
        teka; preverba SHA-256 pred uporabo; utrjenost in zapis gradnje vedno na koncnem paketu."""
        k = self._ukazi("webkit-kljuc")
        self.assertIn('python3 tools/ci_artefakt.py najdi "safeer-webkit-tar-', k)
        self.assertIn('python3 tools/ci_artefakt.py najdi "webkit-deb-profraw-', k)
        self.assertEqual(self.posli["webkit-kljuc"]["permissions"], {"contents": "read", "actions": "read"})
        self.assertEqual(self.posli["webkit-deb-profil"]["if"], "needs.webkit-kljuc.outputs.webkit_run == ''")
        wk = self._ukazi("webkit-deb")
        self.assertLess(wk.index("sha256sum -c safeer-webkit.tar.zst.sha256"), wk.index("zstd -q -t build/safeer-webkit.tar.zst"))
        for preverba in ("bash tools/preveri_utrjenost.sh", "grep -q '^USE_PGO_PROFILE:BOOL=ON$' gradnja.txt",
                         "grep -q '^bolt: da (llvm-bolt 22\\.' gradnja.txt"):
            self.assertIn(preverba, wk)
        for posel, ime in (("webkit-deb", "safeer-webkit-tar-${{ needs.webkit-kljuc.outputs.webkit }}"),
                           ("webkit-deb-profil", "webkit-deb-profraw-${{ needs.webkit-kljuc.outputs.profil }}"),
                           ("flatpak", "${{ steps.fb.outputs.ime }}"), ("flatpak-brskalnik", "${{ steps.fb.outputs.ime }}")):
            with self.subTest(posel=posel):
                nalozi = [x for x in self.posli[posel]["steps"] if "upload-artifact" in str(x.get("uses"))
                          and x["with"]["name"] == ime]
                self.assertEqual(len(nalozi), 1)
                self.assertEqual(nalozi[0]["with"]["retention-days"], 90)
                self.assertNotIn("always()", str(nalozi[0].get("if", "")))   # samo po uspesni gradnji
        for posel, kratko in (("flatpak", "os"), ("flatpak-brskalnik", "brskalnik")):
            ukazi = self._ukazi(posel)
            self.assertIn('python3 tools/ci_artefakt.py najdi "flatpak-builder-%s-' % kratko, ukazi)
            self.assertLess(ukazi.index("sha256sum -c flatpak-builder.tar.zst.sha256"),
                            ukazi.index("tar -I zstd -xf build/fb-artefakt/flatpak-builder.tar.zst"))
            shrani = next(x for x in self.posli[posel]["steps"] if x.get("name") == "Save flatpak-builder cache (WebKitGTK with PGO)")
            self.assertIn("steps.fb.outputs.run_id == ''", shrani["if"])     # artefakt ne gre se v predpomnilnik veje
            # Pregleda M13 in N6: samo po uspesni gradnji (privzeti success()); !cancelled() bi shranil delni predpomnilnik
            # pod koncnim kljucem tudi ob padcu gradnje, always() se ob preklicu.
            for funkcija in ("always()", "cancelled()", "failure()"):
                self.assertNotIn(funkcija, shrani["if"])
        ucenje = self.posli["webkit-pgo-ucenje"]["steps"]
        imena = [k.get("name") for k in ucenje]
        shrani = ucenje[imena.index("Save flatpak-builder cache (instrumented WebKitGTK)")]
        self.assertEqual(imena.index("Save flatpak-builder cache (instrumented WebKitGTK)"),
                         imena.index("Instrumented WebKitGTK (Safeer Browser Flatpak)") + 1)   # pred ucnim tekom
        for funkcija in ("always()", "cancelled()", "failure()"):
            self.assertNotIn(funkcija, shrani["if"])

    def test_stanje_pred_bolt_samo_popolno(self):
        """Ponovni pregled N6: stanje pred BOLT se shrani tudi ob padcu BOLT (always(), namen koraka), ker arhiv nastane
        atomarno: bolt.sh pise v .del, preveri z zstd -t in sele nato preimenuje; hashFiles je prazen, dokler arhiva ni."""
        korak = next(k for k in self.posli["webkit-deb"]["steps"]
                     if k.get("name") == "Save the pre-BOLT state of our WebKitGTK (also when BOLT failed)")
        self.assertIn("hashFiles('build/webkit-predbolt.tar.zst') != ''", korak["if"])
        bolt = (KOREN / "packaging" / "webkit-deb" / "bolt.sh").read_text(encoding="utf-8")
        self.assertIn('-cf "$ARHIV.del"', bolt)
        self.assertIn('zstd -q -t "$ARHIV.del" && mv "$ARHIV.del" "$ARHIV"', bolt)

    def test_meja_zaupanja_artefaktov(self):
        """Neodvisni pregled 25. 10. 2026 (M1-M4): vir artefakta odloci samo tools/ci_artefakt.py iz GITHUB_REF (ne vec
        IZDAJA in veja v*); artefakt za druge teke nalozi samo tek, ki je komu vir (izhod nalozi); profil .deb s SHA-256."""
        klici = [(posel, k) for posel, p in self.posli.items() for k in p.get("steps", [])
                 if "tools/ci_artefakt.py" in (k.get("run") or "")]
        self.assertEqual(sorted({posel for posel, _ in klici}),
                         ["flatpak", "flatpak-brskalnik", "webkit-kljuc", "webkit-pgo-profil"])
        for posel, k in klici:
            with self.subTest(posel=posel, korak=k.get("name")):
                self.assertNotIn("IZDAJA", k.get("env") or {})
                self.assertEqual((k.get("env") or {}).get("GH_TOKEN"), "${{ github.token }}")
                self.assertEqual(self.posli[posel]["permissions"], {"contents": "read", "actions": "read"})
        besedilo = DELOVNI_TOK.read_text(encoding="utf-8")
        self.assertNotIn("gtk4-deb-webkit|v*)", besedilo)                  # stara lastna skripta profila PGO
        self.assertEqual(self.posli["webkit-kljuc"]["outputs"]["webkit_nalozi"], "${{ steps.webkit.outputs.nalozi }}")
        for posel, ime, pogoj in (
                ("webkit-deb", "Our WebKitGTK for later runs (artifact with the key, 90 days)",
                 "needs.webkit-kljuc.outputs.webkit_nalozi == 'true'"),
                ("flatpak", "flatpak-builder cache for later runs (artifact with the key, 90 days)", "steps.fb.outputs.nalozi == 'true'"),
                ("flatpak-brskalnik", "flatpak-builder cache for later runs (artifact with the key, 90 days)",
                 "steps.fb.outputs.nalozi == 'true'")):
            with self.subTest(posel=posel):
                self.assertEqual(next(k for k in self.posli[posel]["steps"] if k.get("name") == ime)["if"], pogoj)
        # Profil PGO .deb: vsote v artefaktu, preverba pred uporabo (iz drugega teka in iz tega teka).
        profil = self._ukazi("webkit-deb-profil")
        self.assertIn("sha256sum -- *.profraw > SHA256SUMS", profil)
        self.assertLess(profil.index("sha256sum -c --strict SHA256SUMS"), profil.index("sha256sum -- *.profraw > SHA256SUMS"))
        self.assertIn("sha256sum -c --strict SHA256SUMS", self._ukazi("webkit-deb"))
        nalozi = next(k for k in self.posli["webkit-deb-profil"]["steps"] if "upload-artifact" in str(k.get("uses")))
        self.assertIn("build/pgo/profraw/SHA256SUMS", nalozi["with"]["path"])

    def test_preverba_profila_deb(self):
        """Ponovni pregled N4 (b): profil PGO .deb iz drugega teka (ali tega) gre v gradnjo samo, ce je mnozica *.profraw
        natanko tista iz SHA256SUMS in se vsaka vsota ujema; dodaten ali spremenjen profil ali manjkajoc seznam ustavi posel.
        Korak pozenemo v bashu, kot ga pozene GitHub (shell: bash)."""
        for posel in ("webkit-deb-profil", "webkit-deb"):
            korak = next(k for k in self.posli[posel]["steps"] if k.get("name") == "The PGO profile is the one that was uploaded (SHA-256)")
            self.assertEqual(korak.get("shell"), "bash", posel)
            for primer, koda in (("dobro", 0), ("dodaten", 1), ("spremenjen", 1), ("brez seznama", 1), ("manjka", 1)):
                with self.subTest(posel=posel, primer=primer), tempfile.TemporaryDirectory() as d:
                    mapa = Path(d) / "build" / "pgo" / "profraw"
                    mapa.mkdir(parents=True)
                    for ime in ("1-a.profraw", "2-b.profraw"):
                        (mapa / ime).write_bytes(ime.encode() * 100)
                    subprocess.run("sha256sum -- *.profraw > SHA256SUMS", shell=True, cwd=str(mapa), check=True)
                    if primer == "dodaten":
                        (mapa / "3-podtaknjen.profraw").write_bytes(b"x")
                    elif primer == "spremenjen":
                        (mapa / "1-a.profraw").write_bytes(b"y")
                    elif primer == "brez seznama":
                        (mapa / "SHA256SUMS").unlink()
                    elif primer == "manjka":
                        (mapa / "2-b.profraw").unlink()
                    r = subprocess.run(["bash", "-e", "-c", korak["run"]], cwd=d, capture_output=True, text=True, timeout=30)
                    self.assertEqual(r.returncode != 0, bool(koda), r.stdout + r.stderr)

    def test_pripete_akcije_in_gostitelji_github(self):
        """Pregled M7: akcije na polnem SHA commita (Dependabot github-actions jih posodablja); M10: samo gostitelji GitHub
        (vsebnik --privileged tece v enkratnem VM, nikoli na lastnem tekacu)."""
        besedilo = DELOVNI_TOK.read_text(encoding="utf-8")
        uporabe = re.findall(r"uses: (\S+)(.*)", besedilo)
        self.assertGreater(len(uporabe), 50)
        for akcija, komentar in uporabe:
            with self.subTest(akcija=akcija):
                self.assertRegex(akcija, r"^actions/[a-z-]+(/[a-z]+)?@[0-9a-f]{40}$")
                self.assertRegex(komentar, r"^ # v\d+\.\d+\.\d+$")
        self.assertIn("package-ecosystem: github-actions", (KOREN / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
        for ime, posel in self.posli.items():
            with self.subTest(posel=ime):
                self.assertTrue(gostitelj_github(posel.get("runs-on")), posel.get("runs-on"))
        # Ponovni pregled N8 (a): izraz v runs-on (npr. ${{ matrix.os }}) bi se lahko razresil v self-hosted - ni dovoljen.
        for runs_on in ("self-hosted", "${{ matrix.os }}", "${{ 'ubuntu-24.04' }}", ["self-hosted", "linux"], "ubuntu-latest-zlo"):
            with self.subTest(runs_on=runs_on):
                self.assertFalse(gostitelj_github(runs_on))

    def test_brez_appimage(self):
        besedilo = DELOVNI_TOK.read_text(encoding="utf-8")
        self.assertNotIn("SAFEER_APPIMAGE", besedilo)
        self.assertNotIn("linuxdeploy", besedilo)

    def test_razdelitev_v_toku_enaka_kot_v_vticniku(self):
        """Stevilo delov v matriki je stevilo, s katerim vticnik razdeli datoteke (sicer bi kaksen del manjkal)."""
        r, stevila = rw.razvrsti(KOREN)
        for posel, webkit in (("hitra-vrata", False), ("preizkusi-webkit", True)):
            with self.subTest(posel=posel):
                deli = len(self.posli[posel]["strategy"]["matrix"]["del"])
                izbrane = [f for f, x in r.items() if bool(x) == webkit]
                razdelitev = rw.razdeli(izbrane, deli, stevila, rw.trajanja(KOREN))
                self.assertEqual(set(razdelitev.values()), set(range(1, deli + 1)))
                ocene = rw.ocena_delov(razdelitev, stevila, rw.trajanja(KOREN))
                # Ocena: noben del ni vec kot 20 % nad povprecjem (enakomerna razdelitev po izmerjenih trajanjih).
                self.assertLess(max(ocene.values()), 1.2 * sum(ocene.values()) / deli, ocene)


if __name__ == "__main__":
    unittest.main()
