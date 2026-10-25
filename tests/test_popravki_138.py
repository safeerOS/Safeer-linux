"""Izdaja 1.0.132 brez AppImage (lastnik, 21. 10. 2026): AppImage 1.0.131 je nosil Ubuntujev WebKitGTK 2.52.6 in libsoup
3.4.4, ne nasega WebKita. CI ga ne gradi in ne prilozi; AppImage brez nasega gradbenega odtisa se ne zazene; uporabnik
AppImage dobi jasno sporocilo in stran s prenosi, ne polovicne posodobitve. Okolje procesa se ne spreminja (AGENTS.md)."""
import copy
import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)
sys.path.insert(0, os.path.join(KOREN, "tools"))

from core import os_posodobitve as op  # noqa: E402
from core import zasebni_webkit as zw  # noqa: E402


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class TestCiBrezAppImage(unittest.TestCase):
    def setUp(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("brez python3-yaml")
        self.wf = yaml.safe_load(beri(".github", "workflows", "linux-packages.yml"))

    def test_appimage_koraki_odstranjeni(self):
        """Od 25. 10. 2026 CI AppImage sploh ne gradi (prej koraki z if: env.SAFEER_APPIMAGE == '1' - in v oktobru 12
        padcev posla z AppImage). Skripte gradnje ostanejo v packaging/ za ponovni vklop z nasim WebKitom."""
        self.assertNotIn("SAFEER_APPIMAGE", self.wf.get("env") or {})
        koraki = [k for posel in self.wf["jobs"].values() for k in posel.get("steps", [])
                  if any(x in (k.get("run") or "") for x in ("build_appimage", "build_os_appimage", "fetch_linuxdeploy",
                                                              "test_appimage", "appimage-extract"))]
        self.assertEqual(koraki, [])
        for ime, posel in self.wf["jobs"].items():
            for k in posel.get("steps", []):
                self.assertNotIn(".AppImage", str((k.get("with") or {}).get("path", "")), ime)
        self.assertTrue(os.path.isfile(os.path.join(KOREN, "packaging", "build_os_appimage.sh")))

    def test_izdaja_brez_appimage(self):
        koraki = [k for posel in self.wf["jobs"].values() for k in posel.get("steps", [])
                  if "sha256sum -- * > SHA256SUMS" in (k.get("run") or "")]
        # Od 25. 10. 2026 seznam paketov izdaje zapise posel paketi-izdaje v teku veje; izdaja (stabilna in beta) ob oznaki
        # vzame natanko te datoteke (tools/ci_izdaja.py preveri: AppImage ali datoteka zunaj seznama = napaka).
        self.assertEqual(koraki, [k for k in self.wf["jobs"]["paketi-izdaje"]["steps"] if k in koraki])
        self.assertEqual(len(koraki), 1)
        for izdaja in ("release", "beta-izdaja"):
            self.assertIn("python3 tools/ci_izdaja.py preveri artifacts artifacts/paketi-izdaje release",
                          [k.get("run") for k in self.wf["jobs"][izdaja]["steps"]])
        for k in koraki:
            # AppImage med artefakti ustavi izdajo, preden se karkoli premakne v izdajo; v izdajo gredo samo .deb in .flatpak.
            self.assertIn("if find artifacts -type f -name '*.AppImage' | grep .; then", k["run"])
            self.assertLess(k["run"].index("-name '*.AppImage' | grep ."), k["run"].index("-exec mv -t release"))
            self.assertIn("\\( -name '*.deb' -o -name '*.flatpak' \\)", k["run"])

    def test_readme_ne_ponuja_appimage(self):
        for ime in ("README.md", "README.sl.md"):
            with self.subTest(ime=ime):
                s = beri(ime)
                self.assertNotIn("chmod +x Safeer-Browser-", s)
                self.assertNotIn("AppImage_%7C", s)


class TestBetaSeznamBrezAppImage(unittest.TestCase):
    def test_seznam_brez_appimage(self):
        try:
            import beta_seznam
        except ImportError as e:
            self.skipTest("beta_seznam: %s" % e)
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa, True)
        vrstice = []
        for i, ime in enumerate(("safeer-os_0.4.90-beta.1_amd64.deb", "safeer-os-app_0.4.90-beta.1_amd64.deb",
                                 "Safeer-OS-0.4.90-beta.1-x86_64.flatpak", "safeer-browser_1.0.132-beta.1_amd64.deb",
                                 "Safeer-Browser-1.0.132-beta.1-x86_64.flatpak")):
            v = os.urandom(100 + i)
            with open(os.path.join(mapa, ime), "wb") as f:
                f.write(v)
            vrstice.append("%s  %s\n" % (hashlib.sha256(v).hexdigest(), ime))
        with open(os.path.join(mapa, "SHA256SUMS"), "w") as f:
            f.writelines(vrstice)
        s = beta_seznam.zgradi_seznam("v1.0.132-beta.1", mapa, datetime(2026, 10, 21, tzinfo=timezone.utc))
        for kljuc in ("safeer-os", "safeer-browser"):
            self.assertNotIn("appimage", s["linux"][kljuc])
            self.assertIn("flatpak", s["linux"][kljuc])
        # AppImage v SHA256SUMS izdaje, datoteke pa ni: napaka (ne tih izpust)
        with open(os.path.join(mapa, "SHA256SUMS"), "a") as f:
            f.write("%s  Safeer-OS-0.4.90-beta.1-x86_64.AppImage\n" % ("0" * 64))
        with self.assertRaises(beta_seznam.Napaka):
            beta_seznam.zgradi_seznam("v1.0.132-beta.1", mapa, datetime(2026, 10, 21, tzinfo=timezone.utc))


class TestAppImageOdtis(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.usr = os.path.join(self.d, "usr")
        os.makedirs(os.path.join(self.usr, "lib"))
        self.lib = [os.path.join(self.usr, "lib", i) for i in
                    ("libwebkitgtk-6.0.so.4", "libjavascriptcoregtk-6.0.so.1", "libsoup-3.0.so.0")]
        for p in self.lib:
            open(p, "w").close()
        self.maps = "".join("7f00-7f01 r-xp 0 08:01 1 %s\n" % p for p in self.lib)

    def _preveri(self, appimage):
        with mock.patch.object(zw, "_koren_nasega", lambda p=None: self.d), \
                mock.patch.object(zw, "_je_appimage", return_value=appimage):
            return zw.preveri_nas_webkit(WebKit=None, uveljavi=False, maps_vsebina=self.maps)[0]

    def test_appimage_brez_odtisa_ni_nas(self):
        """1.0.131: Ubuntujev WebKit pod $APPDIR je bil »nas«."""
        self.assertFalse(self._preveri(appimage=True))

    def test_appimage_z_odtisom_je_nas(self):
        os.makedirs(os.path.join(self.usr, "share", "webkitgtk-safeer"))
        with open(os.path.join(self.usr, zw.ODTIS), "w") as f:
            f.write("0123456789abcdef\n")
        self.assertTrue(self._preveri(appimage=True))

    def test_flatpak_in_deb_brez_odtisa_ostaneta(self):
        self.assertTrue(self._preveri(appimage=False))

    def test_je_appimage_po_okolju(self):
        with mock.patch.object(zw.os, "environ", {"APPDIR": "/tmp/.mount_x"}):
            self.assertTrue(zw._je_appimage())
        with mock.patch.object(zw.os, "environ", {"APPDIR": "/tmp/.mount_x", "FLATPAK_ID": "x"}):
            self.assertFalse(zw._je_appimage())
        with mock.patch.object(zw.os, "environ", {}):
            self.assertFalse(zw._je_appimage())


MANIFEST = {"linux": {"safeer-os": {"razlicica": "0.4.90",
                                    "deb": {"url": "https://github.com/x/safeer-os_0.4.90_amd64.deb", "sha256": "a" * 64, "velikost": 1},
                                    "flatpak": {"url": "https://github.com/x/Safeer-OS-0.4.90-x86_64.flatpak", "sha256": "c" * 64, "velikost": 1}}},
            "stran": "https://safeer.si/prenosi/"}


class TestPosodobitevAppImage(unittest.TestCase):
    def test_brez_vnosa_appimage_samo_stran(self):
        i = op.preveri("linux", {"safeer-os": "0.4.89"}, MANIFEST, nacin="appimage")
        self.assertEqual(len(i["nove"]), 1)
        self.assertIsNone(i["nove"][0]["datoteka"])
        self.assertTrue(i["rocno"])
        self.assertEqual(i["stran"], "https://safeer.si/prenosi/")

    def test_z_vnosom_ni_rocno(self):
        m = copy.deepcopy(MANIFEST)
        m["linux"]["safeer-os"]["appimage"] = {"url": "https://github.com/x/Safeer-OS-0.4.90-x86_64.AppImage",
                                               "sha256": "d" * 64, "velikost": 1}
        i = op.preveri("linux", {"safeer-os": "0.4.89"}, m, nacin="appimage")
        self.assertFalse(i["rocno"])
        self.assertIsNotNone(i["nove"][0]["datoteka"])
        self.assertFalse(op.preveri("linux", {"safeer-os": "0.4.89"}, MANIFEST, nacin="deb")["rocno"])
        self.assertFalse(op.preveri("linux", {"safeer-os": "0.4.90"}, MANIFEST, nacin="appimage")["rocno"])

    def test_vmesnik_in_zaledje(self):
        js = beri("assets", "os", "os.js")
        self.assertIn('st.rocno ? t(st.nacin === "appimage" ? "posodobitevAppImagePod" : "posodobitevRocnoPod")', js)
        self.assertIn('if (st.rocno || (st.nacin !== "deb"', js)
        self.assertIn('{"ok": False, "koda": "rocno", "stran": st["stran"]} if st["nove"]', beri("safeer_os.py"))
        b = beri("assets", "os", "besedila.js")
        self.assertEqual(b.count("posodobitevAppImagePod:"), 6)
        self.assertIn("na voljo kot Flatpak ali .deb", b)
        self.assertIn("available as a Flatpak or .deb", b)


if __name__ == "__main__":
    unittest.main()
