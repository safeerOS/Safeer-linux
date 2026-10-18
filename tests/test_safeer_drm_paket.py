"""Safeer DRM v paketih (lastnik, 18. 10. 2026: DRM je del paketa, med delovanjem se nic ne prenese).

packaging/safeer_drm_paket.py pripravi mapo iz pripetega ECS (zip) in pripetega Widevine CDM (CRX3), oba preverjena s
SHA-256; namesti_safeer_drm.sh jo da v tovor .deb, AppImage in Flatpaka. Preizkus z majhnim laznim paketom (brez omrezja,
SAFEER_DRM_PIN) in skladnost pina z manifesti Flatpak, delovnim tokom CI in skriptami gradnje.
"""
import hashlib
import io
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
ORODJE = KOREN / "packaging" / "safeer_drm_paket.py"
PIN = json.loads((KOREN / "packaging" / "safeer-drm.json").read_text(encoding="utf-8"))
CDM = "4.10.3112.0"


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


def _crx(manifest_verzija: str = CDM, knjiznica: bytes = b"\x7fELF-cdm") -> bytes:
    vsebina = _zip({"manifest.json": (json.dumps({"name": "WidevineCdm", "version": manifest_verzija}), 0o644),
                    "LICENSE": ("Google LLC ... separate license agreement with Google.", 0o644),
                    "_platform_specific/linux_x64/libwidevinecdm.so": (knjiznica, 0o755),
                    "_metadata/verified_contents.json": ("{}", 0o644)})
    glava = b"\x08\x01"                                    # glava CRX3 (protobuf), za razpakiranje nepomembna
    return b"Cr24" + struct.pack("<II", 3, len(glava)) + glava + vsebina


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

    def _pripravi_vire(self, ecs=None, crx=None, program=PROGRAM, knjiznica=b"\x7fELF-cdm"):
        zip_ = self.d / "ecs.zip"
        zip_.write_bytes(_zip(ecs or ECS))
        crx3 = self.d / "cdm.crx3"
        crx3.write_bytes(crx if crx is not None else _crx())
        pin = {"safeer_drm": dict(PIN["safeer_drm"], velikost=zip_.stat().st_size, sha256=_sha(zip_.read_bytes()),
                                  program_sha256=_sha(program)),
               "widevine": dict(PIN["widevine"], verzija=CDM, velikost=crx3.stat().st_size, sha256=_sha(crx3.read_bytes()),
                                knjiznica_sha256=_sha(knjiznica))}
        (self.d / "pin.json").write_text(json.dumps(pin))
        self.okolje = dict(os.environ, SAFEER_DRM_PIN=str(self.d / "pin.json"))
        return zip_, crx3

    def _orodje(self, *argumenti):
        return subprocess.run([sys.executable, str(ORODJE), *map(str, argumenti)], capture_output=True, text=True,
                              env=self.okolje, cwd=self.d)

    def _pripravi(self, cilj=None):
        zip_, crx3 = self.d / "ecs.zip", self.d / "cdm.crx3"
        return self._orodje("pripravi", cilj or self.d / "tovor" / "safeer-drm", "--zip", zip_, "--crx", crx3)


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
        cdm = m / "WidevineCdm" / CDM
        self.assertEqual(sorted(str(x.relative_to(cdm)) for x in cdm.rglob("*") if x.is_file()),
                         ["LICENSE", "_platform_specific/linux_x64/libwidevinecdm.so", "manifest.json"])
        self.assertEqual(stat.S_IMODE((cdm / "_platform_specific/linux_x64/libwidevinecdm.so").stat().st_mode), 0o755)
        obvestilo = (m / "OBVESTILO.txt").read_text(encoding="utf-8")
        for besedilo in ("castLabs", "Widevine", "Google LLC", CDM, PIN["safeer_drm"]["ecs"], "LICENSES.chromium.html",
                         f"WidevineCdm/{CDM}/LICENSE"):
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

    def test_napacen_sha256_ali_velikost(self):
        self._pripravi_vire()
        pin = json.loads((self.d / "pin.json").read_text())
        pin["widevine"]["sha256"] = "0" * 64
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

    def test_nevarne_poti_in_povezave(self):
        for dodatek in ({"../ven": ("x", 0o644)}, {"povezava": ("/etc/passwd", 0o120777)}):
            with self.subTest(dodatek=list(dodatek)):
                self._pripravi_vire(ecs=dict(ECS, **dodatek))
                r = self._pripravi()
                self.assertNotEqual(r.returncode, 0)
                self.assertFalse((self.d / "ven").exists())
                self.assertFalse((self.d / "tovor" / "safeer-drm").exists())

    def test_cdm_druge_verzije_ali_ni_crx3(self):
        for crx in (_crx("4.10.9999.0"), _zip({"manifest.json": ("{}", 0o644)})):
            with self.subTest():
                self._pripravi_vire(crx=crx)
                self.assertNotEqual(self._pripravi().returncode, 0)

    def test_preveri_zazna_spremembo_in_setuid(self):
        self._pripravi_vire()
        self.assertEqual(self._pripravi().returncode, 0)
        m = self.d / "tovor" / "safeer-drm"
        knjiznica = m / "WidevineCdm" / CDM / "_platform_specific/linux_x64/libwidevinecdm.so"
        knjiznica.write_bytes(b"spremenjena")
        (m / "chrome-sandbox").chmod(0o4755)
        r = self._orodje("preveri", m)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("libwidevinecdm.so", r.stderr)
        self.assertIn("setuid", r.stderr)


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
        for ime in ("OBVESTILO.txt", "LICENSE.electron", "LICENSE.widevine-cdm"):
            self.assertTrue((predpona / "share" / "doc" / doc / "safeer-drm" / ime).is_file(), ime)
        # Namesceni tovor (brez izvorne mape) najde Safeer DRM v paketu.
        koda = (f"import sys; sys.path.insert(0, {str(predpona / 'lib' / lib)!r}); from core import safeer_drm as d; "
                "print(d.izvrsljiva()); print(d.mapa_cdm())")
        okolje = {k: v for k, v in self.okolje.items() if k not in ("PYTHONPATH", "SAFEER_DRM_MAPA")}
        izid = subprocess.run([sys.executable, "-c", koda], capture_output=True, text=True, env=okolje,
                              cwd=tempfile.gettempdir())
        self.assertEqual(izid.returncode, 0, izid.stderr[-800:])
        self.assertEqual(izid.stdout.split(), [str(m / "safeer-drm"), str(m / "WidevineCdm" / CDM)])

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
    """Isti pin povsod: Flatpak, CI, .deb in AppImage."""

    def test_pin(self):
        for kljuc in ("safeer_drm", "widevine"):
            self.assertRegex(PIN[kljuc]["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(PIN[kljuc]["url"].startswith("https://"))
        self.assertTrue(PIN["widevine"]["url"].startswith("https://dl.google.com/release2/chrome_component/"))
        self.assertIn(PIN["widevine"]["verzija"], PIN["widevine"]["url"])
        self.assertRegex(PIN["widevine"]["knjiznica_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(PIN["safeer_drm"]["program_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("libgtk-3-0t64", PIN["safeer_drm"]["deb_odvisnosti"])
        self.assertIn("libnss3", PIN["safeer_drm"]["deb_odvisnosti"])
        # Brez skrivnosti: CDM je z javnega Googlovega streznika komponent (brez gesel in zetonov).
        besedilo = json.dumps(PIN).lower()
        for prepovedano in ("token", "secret", "password", "geslo", "api_key"):
            self.assertNotIn(prepovedano, besedilo)

    def test_manifesta_flatpak(self):
        for ime, lib in (("io.github.memelandfaner.SafeerBrowser.yml", "install_payload.sh"),
                         ("io.github.memelandfaner.SafeerOS.yml", "install_os_payload.sh")):
            m = (KOREN / ime).read_text(encoding="utf-8")
            for kljuc in ("safeer_drm", "widevine"):
                v = PIN[kljuc]
                self.assertIn(f"        url: {v['url']}\n        sha256: {v['sha256']}\n        dest-filename: {v['datoteka']}\n",
                              m, (ime, kljuc))
            self.assertIn(f"python3 packaging/safeer_drm_paket.py pripravi build/safeer-drm --zip {PIN['safeer_drm']['datoteka']}"
                          f" --crx {PIN['widevine']['datoteka']}", m)
            self.assertRegex(m, r"SAFEER_DRM_TOVOR=build/safeer-drm bash packaging/%s /app " % lib)
            self.assertIn("          - safeer-drm\n", m)                       # razvojna mapa ne gre v vir
            # Dovoljenja peskovnika se zaradi Safeer DRM ne razsirijo.
            self.assertNotIn("--filesystem=xdg-data", m)

    def test_ci_vgradi_v_vse_pakete_in_preveri(self):
        wf = (KOREN / ".github" / "workflows" / "linux-packages.yml").read_text(encoding="utf-8")
        self.assertEqual(wf.count("run: python3 packaging/safeer_drm_paket.py pripravi build/safeer-drm"), 2)
        for gradnja in ("bash build_deb.sh", "bash build_os_deb.sh", "bash packaging/build_appimage.sh",
                        "bash packaging/build_os_appimage.sh"):
            vrstica = next(v for v in wf.splitlines() if v.rstrip().endswith(gradnja))
            self.assertIn('SAFEER_DRM_TOVOR="$PWD/build/safeer-drm"', vrstica, gradnja)
        for preverba in ("python3 packaging/safeer_drm_paket.py preveri /usr/lib/safeer-browser/safeer-drm",
                         "python3 packaging/safeer_drm_paket.py preveri /usr/lib/safeer-os/safeer-drm",
                         '"$PWD/packaging/safeer_drm_paket.py" preveri /app/lib/safeer-browser/safeer-drm',
                         '"$PWD/packaging/safeer_drm_paket.py" preveri /app/lib/safeer-os/safeer-drm',
                         "python3 packaging/safeer_drm_paket.py preveri build/os-appimage-x/squashfs-root/opt/safeer-drm"):
            self.assertIn(preverba, wf)
        self.assertIn("safeer_drm_paket.py novejsi", wf)
        # CDM je z javnega Googlovega streznika: brez skrivnosti posrednika v CI.
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

    def test_novejsi_samo_porocilo(self):
        sys.path.insert(0, str(KOREN / "packaging"))
        try:
            import safeer_drm_paket as orodje
        finally:
            sys.path.remove(str(KOREN / "packaging"))
        zahteve = []

        class Odziv(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

        def odpri(zahteva, timeout):
            zahteve.append(json.loads(zahteva.data))
            telo = {"response": {"app": [{"updatecheck": {"status": "ok", "manifest": {"version": "4.10.3200.0"}}}]}}
            return Odziv((")]}'\n" + json.dumps(telo)).encode())
        izid = orodje.novejsi(odpri)
        self.assertEqual(izid, {"pripeta": PIN["widevine"]["verzija"], "ponujena": "4.10.3200.0", "novejsa": True})
        self.assertEqual(zahteve[0]["request"]["app"][0]["appid"], PIN["widevine"]["id_komponente"])
        self.assertEqual(zahteve[0]["request"]["prodversion"], PIN["safeer_drm"]["chromium"])


class Licenca(unittest.TestCase):
    def test_metainfo_navaja_lastnisko_komponento(self):
        """Paketa nosita lastniski Widevine CDM: AppStream to pove (LicenseRef-proprietary), poleg Apache-2.0."""
        for ime in ("io.github.memelandfaner.SafeerBrowser.metainfo.xml", "io.github.memelandfaner.SafeerOS.metainfo.xml"):
            m = re.search(r"<project_license>([^<]+)</project_license>", (KOREN / ime).read_text(encoding="utf-8"))
            self.assertEqual(m.group(1), "Apache-2.0 AND LicenseRef-proprietary", ime)


if __name__ == "__main__":
    unittest.main()
