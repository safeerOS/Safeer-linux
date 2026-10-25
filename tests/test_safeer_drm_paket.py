"""Safeer DRM v paketih (lastnik, 18. 10. 2026: Safeer DRM je del paketa in se med delovanjem ne prenasa).

packaging/safeer_drm_paket.py pripravi mapo iz pripetega ECS (zip, SHA-256); namesti_safeer_drm.sh jo da v tovor .deb,
AppImage in Flatpaka. Widevine CDM NI v paketu (odlocitev lastnika po FAQ castLabs): ECS ga ob prvi zasciteni vsebini
sam namesti z Googlovih streznikov. Preizkus z majhnim laznim paketom (brez omrezja, SAFEER_DRM_PIN) in skladnost pina
z manifesti Flatpak, delovnim tokom CI in skriptami gradnje.
"""
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
ORODJE = KOREN / "packaging" / "safeer_drm_paket.py"
PIN = json.loads((KOREN / "packaging" / "safeer-drm.json").read_text(encoding="utf-8"))


def _sha(podatki: bytes) -> str:
    return hashlib.sha256(podatki).hexdigest()


def _zip(datoteke: dict) -> bytes:
    """{ime: (vsebina, pravice)}; pravice z vrsto datoteke (npr. 0o120777 = simbolna povezava)."""
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for ime, (vsebina, pravice) in datoteke.items():
            info = zipfile.ZipInfo(ime)
            info.external_attr = (pravice if pravice > 0o7777 else 0o100000 | pravice) << 16
            z.writestr(info, vsebina)
    return b.getvalue()


PROGRAM = b"\x7fELF-safeer-drm"
ECS = {"safeer-drm": (PROGRAM, 0o4775), "chrome-sandbox": (b"\x7fELF-sandbox", 0o4755),
       "chrome_crashpad_handler": (b"\x7fELF-crashpad", 0o775), "libffmpeg.so": (b"\x7fELF-ffmpeg", 0o775),
       "LICENSE": ("Copyright (c) Electron contributors", 0o664), "LICENSES.chromium.html": ("<html>", 0o664),
       "locales/sl.pak": (b"pak", 0o664), "resources/app/main.js": ("// stara logika", 0o664),
       "resources/app/package.json": ("{}", 0o664), "version": ("44.5.1+wvcus", 0o664)}


class Lazni(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.d, ignore_errors=True))

    def _pripravi_vire(self, ecs=None, program=PROGRAM):
        zip_ = self.d / "ecs.zip"
        zip_.write_bytes(_zip(ecs or ECS))
        pin = {"safeer_drm": dict(PIN["safeer_drm"], velikost=zip_.stat().st_size, sha256=_sha(zip_.read_bytes()),
                                  program_sha256=_sha(program))}
        (self.d / "pin.json").write_text(json.dumps(pin))
        self.okolje = dict(os.environ, SAFEER_DRM_PIN=str(self.d / "pin.json"))
        return zip_

    def _orodje(self, *argumenti):
        return subprocess.run([sys.executable, str(ORODJE), *map(str, argumenti)], capture_output=True, text=True,
                              env=self.okolje, cwd=self.d)

    def _pripravi(self, cilj=None):
        return self._orodje("pripravi", cilj or self.d / "tovor" / "safeer-drm", "--zip", self.d / "ecs.zip")


class Pripravi(Lazni):
    def test_postavitev_pravice_in_obvestila(self):
        self._pripravi_vire()
        r = self._pripravi()
        self.assertEqual(r.returncode, 0, r.stderr)
        m = self.d / "tovor" / "safeer-drm"
        self.assertEqual((m / "safeer-drm").read_bytes(), PROGRAM)
        # Izvrsljive datoteke ostanejo izvrsljive, nikjer setuid (chrome-sandbox ni potreben); drugo samo za branje.
        self.assertEqual(stat.S_IMODE((m / "safeer-drm").stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((m / "chrome-sandbox").stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((m / "locales" / "sl.pak").stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE((m / "locales").stat().st_mode), 0o755)
        # Logika predvajalnika iz tega izvora, ne iz zip.
        self.assertEqual((m / "resources/app/main.js").read_bytes(), (KOREN / "assets/safeer_drm/main.js").read_bytes())
        self.assertEqual((m / "resources/app/package.json").read_bytes(),
                         (KOREN / "assets/safeer_drm/package.json").read_bytes())
        # Widevine CDM ni v paketu.
        self.assertFalse((m / "WidevineCdm").exists())
        self.assertEqual(list(m.rglob("libwidevinecdm.so")), [])
        obvestilo = (m / "OBVESTILO.txt").read_text(encoding="utf-8")
        for besedilo in ("castLabs", PIN["safeer_drm"]["ecs"], "LICENSES.chromium.html", "NI del tega paketa",
                         "is NOT part of this package", "Googlovih streznikov", "Google's servers"):
            self.assertIn(besedilo, obvestilo)
        self.assertNotRegex(obvestilo.lower(), r"pogodb[a-z]* (st|št)|contract no|\d{6,}")   # brez podatkov pogodbe
        r = self._orodje("preveri", m)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_ponovna_priprava_prepise_samo_svojo_mapo(self):
        self._pripravi_vire()
        self.assertEqual(self._pripravi().returncode, 0)
        self.assertEqual(self._pripravi().returncode, 0)          # oznaka .safeer-drm-tovor: nasa mapa
        tuja = self.d / "tuja"
        tuja.mkdir()
        (tuja / "dokument.txt").write_text("uporabnik")
        r = self._pripravi(tuja)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((tuja / "dokument.txt").read_text(), "uporabnik")

    def test_napacen_sha256(self):
        self._pripravi_vire()
        pin = json.loads((self.d / "pin.json").read_text())
        pin["safeer_drm"]["sha256"] = "0" * 64
        (self.d / "pin.json").write_text(json.dumps(pin))
        r = self._pripravi()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SHA-256", r.stderr)
        self.assertFalse((self.d / "tovor" / "safeer-drm").exists())

    def test_program_ni_pripeti(self):
        self._pripravi_vire(program=b"drug program")
        r = self._pripravi()
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.d / "tovor" / "safeer-drm").exists())
        self.assertEqual([x for x in (self.d / "tovor").iterdir()], [])      # brez ostankov zacasne mape

    def test_nevarne_poti_povezave_in_cdm(self):
        """Tudi Widevine CDM v zip ne sme v paket (namesti ga ECS z Googlovih streznikov)."""
        for dodatek in ({"../ven": ("x", 0o644)}, {"povezava": ("/etc/passwd", 0o120777)},
                        {"WidevineCdm/4.10.3112.0/_platform_specific/linux_x64/libwidevinecdm.so": (b"\x7fELF", 0o755)}):
            with self.subTest(dodatek=list(dodatek)):
                self._pripravi_vire(ecs=dict(ECS, **dodatek))
                r = self._pripravi()
                self.assertNotEqual(r.returncode, 0)
                self.assertFalse((self.d / "ven").exists())
                self.assertFalse((self.d / "tovor" / "safeer-drm").exists())

    def test_preveri_zazna_setuid_spremembo_in_cdm(self):
        self._pripravi_vire()
        self.assertEqual(self._pripravi().returncode, 0)
        m = self.d / "tovor" / "safeer-drm"
        (m / "chrome-sandbox").chmod(0o4755)
        (m / "WidevineCdm" / "4.10.3112.0").mkdir(parents=True)
        r = self._orodje("preveri", m)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("setuid", r.stderr)
        self.assertIn("Widevine CDM je v paketu", r.stderr)
        (m / "safeer-drm").write_bytes(b"spremenjen")
        self.assertIn("pripetega SHA-256", self._orodje("preveri", m).stderr)


class Tovor(Lazni):
    """namesti_safeer_drm.sh iz install_payload.sh / install_os_payload.sh: <tovor>/safeer-drm in share/doc."""

    def _namesti(self, skripta, lib, doc):
        self._pripravi_vire()
        self.assertEqual(self._pripravi().returncode, 0)
        predpona = self.d / "usr"
        r = subprocess.run(["bash", str(KOREN / "packaging" / skripta), str(predpona)], capture_output=True, text=True,
                           env=dict(self.okolje, SAFEER_DRM_TOVOR=str(self.d / "tovor" / "safeer-drm")))
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        m = predpona / "lib" / lib / "safeer-drm"
        self.assertTrue(os.access(m / "safeer-drm", os.X_OK))
        self.assertTrue(os.access(m / "chrome_crashpad_handler", os.X_OK))
        self.assertFalse((m / ".safeer-drm-tovor").exists())
        dokumenti = predpona / "share" / "doc" / doc / "safeer-drm"
        self.assertEqual(sorted(x.name for x in dokumenti.iterdir()), ["LICENSE.electron", "OBVESTILO.txt"])
        # Namesceni tovor (brez izvorne mape) najde Safeer DRM v paketu.
        koda = (f"import sys; sys.path.insert(0, {str(predpona / 'lib' / lib)!r}); from core import safeer_drm as d; "
                "print(d.izvrsljiva())")
        okolje = {k: v for k, v in self.okolje.items() if k not in ("PYTHONPATH", "SAFEER_DRM_MAPA")}
        izid = subprocess.run([sys.executable, "-c", koda], capture_output=True, text=True, env=okolje,
                              cwd=tempfile.gettempdir())
        self.assertEqual(izid.returncode, 0, izid.stderr[-800:])
        self.assertEqual(izid.stdout.split(), [str(m / "safeer-drm")])

    def test_brskalnik(self):
        self._namesti("install_payload.sh", "safeer-browser", "safeer-browser")

    def test_safeer_os_pravice_ostanejo_po_poenotenju(self):
        """install_os_payload.sh vsem datotekam tovora nastavi 644 - Safeer DRM mora priti za tem."""
        self._namesti("install_os_payload.sh", "safeer-os", "safeer-os")

    def test_brez_tovora_ni_safeer_drm(self):
        predpona = self.d / "usr"
        okolje = {k: v for k, v in os.environ.items() if k != "SAFEER_DRM_TOVOR"}
        r = subprocess.run(["bash", str(KOREN / "packaging" / "install_payload.sh"), str(predpona)], capture_output=True,
                           text=True, env=okolje)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        self.assertIn("SAFEER_DRM_TOVOR ni nastavljen", r.stderr)
        self.assertFalse((predpona / "lib" / "safeer-browser" / "safeer-drm").exists())


class Skladnost(unittest.TestCase):
    """Isti pin povsod: Flatpak, CI, .deb in AppImage; Widevine CDM nikjer v paketih."""

    def test_pin(self):
        self.assertEqual(sorted(k for k in PIN if not k.startswith("_")), ["safeer_drm"])     # brez pina CDM
        self.assertRegex(PIN["safeer_drm"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(PIN["safeer_drm"]["program_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(PIN["safeer_drm"]["url"].startswith("https://github.com/safeerOS/Safeer-linux/releases/download/"))
        self.assertIn("libgtk-3-0t64", PIN["safeer_drm"]["deb_odvisnosti"])
        self.assertIn("libnss3", PIN["safeer_drm"]["deb_odvisnosti"])
        besedilo = json.dumps(PIN).lower()
        for prepovedano in ("token", "secret", "password", "geslo", "api_key", ".crx", "dl.google.com"):
            self.assertNotIn(prepovedano, besedilo)

    def test_manifesta_flatpak(self):
        v = PIN["safeer_drm"]
        for ime, lib in (("io.github.memelandfaner.SafeerBrowser.yml", "install_payload.sh"),
                         ("io.github.memelandfaner.SafeerOS.yml", "install_os_payload.sh")):
            m = (KOREN / ime).read_text(encoding="utf-8")
            self.assertIn(f"        url: {v['url']}\n        sha256: {v['sha256']}\n        dest-filename: {v['datoteka']}\n",
                          m, ime)
            self.assertIn(f"      - python3 packaging/safeer_drm_paket.py pripravi build/safeer-drm --zip {v['datoteka']}\n", m)
            self.assertRegex(m, r"SAFEER_DRM_TOVOR=build/safeer-drm bash packaging/%s /app " % lib)
            self.assertIn("          - safeer-drm\n", m)                       # razvojna mapa ne gre v vir
            for odpadlo in (".crx3", "dl.google.com", "--crx", "--disable-component-update"):
                self.assertNotIn(odpadlo, m, (ime, odpadlo))
            # Dovoljenja peskovnika se zaradi Safeer DRM ne razsirijo.
            self.assertNotIn("--filesystem=xdg-data", m)

    def test_ci_vgradi_v_vse_pakete_in_preveri(self):
        wf = (KOREN / ".github" / "workflows" / "linux-packages.yml").read_text(encoding="utf-8")
        self.assertEqual(wf.count("run: python3 packaging/safeer_drm_paket.py pripravi build/safeer-drm"), 2)
        # AppImage CI od 25. 10. 2026 ne gradi (opuscen); skripti AppImage Safeer DRM se vedno vgradita (spodaj).
        self.assertNotIn("build_appimage.sh", wf)
        self.assertNotIn("build_os_appimage.sh", wf)
        for gradnja in ("bash build_deb.sh", "bash build_os_deb.sh"):
            vrstica = next(v for v in wf.splitlines() if v.rstrip().endswith(gradnja))
            self.assertIn('SAFEER_DRM_TOVOR="$PWD/build/safeer-drm"', vrstica, gradnja)
        for preverba in ("python3 packaging/safeer_drm_paket.py preveri /usr/lib/safeer-browser/safeer-drm",
                         "python3 packaging/safeer_drm_paket.py preveri /usr/lib/safeer-os/safeer-drm",
                         '"$PWD/packaging/safeer_drm_paket.py" preveri /app/lib/safeer-browser/safeer-drm',
                         '"$PWD/packaging/safeer_drm_paket.py" preveri /app/lib/safeer-os/safeer-drm'):
            self.assertIn(preverba, wf)
        # CDM ni v paketih .deb (preverba), pin CDM in porocilo o novejsem CDM sta odpadla.
        self.assertEqual(wf.count("grep -E 'WidevineCdm|libwidevinecdm'; then echo \"::error::Widevine CDM je v paketu\""), 2)
        self.assertNotIn("safeer_drm_paket.py novejsi", wf)
        self.assertNotIn("LICENSE.widevine-cdm", wf)
        self.assertNotRegex(wf, r"secrets\.[A-Z_]*(DRM|WIDEVINE|CDM)")

    def test_deb_odvisnosti_in_appimage(self):
        for ime in ("build_deb.sh", "build_os_deb.sh"):
            self.assertIn('packaging/safeer_drm_paket.py" odvisnosti-deb', (KOREN / ime).read_text(encoding="utf-8"))
        for skripta, apprun, lib in (("build_appimage.sh", "AppRun", "safeer-browser"),
                                     ("build_os_appimage.sh", "AppRun-os", "safeer-os")):
            s = (KOREN / "packaging" / skripta).read_text(encoding="utf-8")
            self.assertIn(f'mv "$APPDIR/usr/lib/{lib}/safeer-drm" "$APPDIR/opt/safeer-drm"', s)
            self.assertLess(s.index('"$APPDIR/opt/safeer-drm"'), s.index('"$LINUXDEPLOY"'))
            self.assertIn('export SAFEER_DRM_MAPA="$APPDIR/opt/safeer-drm"', (KOREN / "packaging" / apprun).read_text())

    def test_odvisnosti_deb_ukaz(self):
        r = subprocess.run([sys.executable, str(ORODJE), "odvisnosti-deb"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), ", ".join(PIN["safeer_drm"]["deb_odvisnosti"]))
        self.assertEqual(subprocess.run([sys.executable, str(ORODJE), "novejsi"], capture_output=True).returncode, 2)


class Licenca(unittest.TestCase):
    def test_metainfo_brez_lastniske_komponente(self):
        """V paketu ni lastniskega CDM (ECS je Electron/Chromium in castLabs, MIT): licenca projekta ostane Apache-2.0."""
        for ime in ("io.github.memelandfaner.SafeerBrowser.metainfo.xml", "io.github.memelandfaner.SafeerOS.metainfo.xml"):
            m = re.search(r"<project_license>([^<]+)</project_license>", (KOREN / ime).read_text(encoding="utf-8"))
            self.assertEqual(m.group(1), "Apache-2.0", ime)


if __name__ == "__main__":
    unittest.main()
