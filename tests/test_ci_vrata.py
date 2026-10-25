"""CI Safeer-linux (lastnik 25. 10. 2026: »za veliko gradnje je relativno malo uspehov«): hitra vrata pred vsako gradnjo,
preizkusi z WebKitom samo z nasim WebKitom, en tek na vejo, WebKit enkrat na kljuc (artefakt za vse veje).

Suha preverba grafa poslov (needs) in nastavitev, brez potiska: napaka v delovnem toku se pokaze v hitrih vratih."""
import re
import sys
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

#: Posli, ki trajajo minute do ur ali gradijo pakete: vsi cakajo na hitra vrata (neposredno ali posredno).
DRAGI = ("webkit-kljuc", "webkit-deb-profil", "webkit-deb", "brskalnik", "safeer-os", "qt-xcb", "mint", "debian",
         "webkit-pgo-profil", "webkit-pgo-ucenje", "flatpak", "flatpak-brskalnik", "preizkusi-webkit", "release",
         "beta-izdaja")
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
        for izdaja in ("release", "beta-izdaja"):
            self.assertLessEqual({"hitra-vrata", "preizkusi-webkit", "mint", "flatpak", "flatpak-brskalnik"},
                                 set(self._potrebe(izdaja)))

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
        self.assertEqual(c["cancel-in-progress"], "${{ !startsWith(github.ref, 'refs/tags/') }}")
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
