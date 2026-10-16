#!/usr/bin/env python3
"""Namestitev iz izvorne kode (install.sh, safeer-mint.sh) in debian/ sta GTK4 kot paketi .deb, Flatpak in AppImage.

Odlocitev lastnika 16. 10. 2026: GTK4 (WebKitGTK 6.0) je privzet povsod; GTK3 (safeer_mint.py) samo z
SAFEER_BRSKALNIK_GTK3=1 do umika. Vir resnice za pakete je Depends v build_deb.sh (prej je install.sh preveril
pakete GTK3, debian/control pa zahteval GTK3, ceprav so vsi paketi ze GTK4)."""

import os
import re
import shutil
import subprocess
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ID = "io.github.memelandfaner.SafeerBrowser"


def _beri(ime: str) -> str:
    with open(os.path.join(KOREN, ime), encoding="utf-8") as f:
        return f.read()


def _paketi(besedilo: str) -> set:
    return {re.sub(r"\s*\(.*?\)", "", p).strip() for p in besedilo.split(",") if p.strip()} - {"python3"}


def _depends_build_deb(gtk3: bool) -> set:
    vzorec = (r'SAFEER_BRSKALNIK_GTK3:-0}" = 1 ]; then\s+ODVISNOSTI="([^"]+)"' if gtk3
              else r'else\s+ODVISNOSTI="([^"]+)"')
    najdeno = re.search(vzorec, _beri("build_deb.sh"))
    assert najdeno, "build_deb.sh nima seznama ODVISNOSTI"
    return _paketi(najdeno.group(1))


def _paketi_install(gtk3: bool) -> set:
    namestitev = _beri("install.sh")
    vzorec = (r'SAFEER_BRSKALNIK_GTK3:-0}" = 1 ]; then\s+PAKETI="([^"]+)"' if gtk3
              else r'else\n(?:\s+echo[^\n]*\n)?\s+PAKETI="([^"]+)"')
    najdeno = re.search(vzorec, namestitev)
    assert najdeno, "install.sh nima seznama PAKETI"
    return set(najdeno.group(1).split())


class PreizkusOdvisnostiNamestitve(unittest.TestCase):
    def test_install_sh_preveri_odvisnosti_paketa_gtk4(self):
        preverjeni = _paketi_install(gtk3=False)
        self.assertLessEqual(_depends_build_deb(gtk3=False), preverjeni)
        self.assertIn("gir1.2-webkit-6.0", preverjeni)
        self.assertIn("gir1.2-gtk-4.0", preverjeni)
        self.assertNotIn("gir1.2-gtk-3.0", preverjeni)
        self.assertIn("Linux Mint 22 / Ubuntu 24.04", _beri("install.sh"))

    def test_install_sh_gtk3_le_na_izrecno_izbiro(self):
        self.assertLessEqual(_depends_build_deb(gtk3=True), _paketi_install(gtk3=True))

    def test_debian_control_je_gtk4(self):
        control = _beri("debian/control")
        # Dva odstavka: izvorni (Build-Depends) in paket safeer-browser (Depends) - preverjamo Depends paketa.
        self.assertRegex(control, r"(?m)^Source: safeer-browser$")
        self.assertRegex(control, r"(?m)^Build-Depends: debhelper-compat")
        paket = control.split("\nPackage: safeer-browser\n", 1)[1]
        zahteve = re.split(r"(?m)^Depends:", paket, 1)[1].split("Recommends:", 1)[0]
        zahteve = re.sub(r"\$\{[^}]+\}", "", zahteve)
        self.assertEqual(_paketi(zahteve), _depends_build_deb(gtk3=False))
        for star in ("gir1.2-gtk-3.0", "gir1.2-webkit2-4.1", "libwebkit2gtk-4.1"):
            self.assertNotIn(star, zahteve)
        self.assertIn("GTK4", control)
        self.assertNotIn("GTK3", control)
        # debian/rules mora namestiti isti (GTK4) tovor, sicer bi Depends GTK4 veljal za kodo GTK3.
        self.assertIn("packaging/install_payload.sh", _beri("debian/rules"))
        self.assertNotIn("safeer_mint.py", _beri("debian/rules"))

    def test_prenosni_arhiv_ima_vstop_gtk4(self):
        gradnja = _beri("build_deb.sh")
        ukaz = re.search(r'tar -czf "\$DIR/\$TAR_PACKAGE".*?-C "\$DIR" \\\n(.*?)\nTAR_DATOTEKE', gradnja, re.S)
        self.assertIsNotNone(ukaz)
        datoteke = ukaz.group(1).replace("\\\n", " ").split()
        for ime in ("safeer_brskalnik.py", "safeer-mint.sh", "install.sh", "packaging/safeer-browser.desktop",
                    "packaging/VERSION"):
            self.assertIn(ime, datoteke)
        for ime in datoteke:
            self.assertTrue(os.path.exists(os.path.join(KOREN, ime)), ime)
        # Arhiv ni vec samo za GTK3.
        pred = gradnja.split('tar -czf "$DIR/$TAR_PACKAGE"')[0].rsplit("# 9.", 1)[1]
        self.assertNotIn('if [ "${SAFEER_BRSKALNIK_GTK3', pred)


class PreizkusNamestitveVLaznemDomu(unittest.TestCase):
    """install.sh, safeer-mint.sh in uninstall.sh v lazni domaci mapi; dpkg in orodja namizja so nadomestki,
    vstopa sta skripti, ki izpiseta svoje ime (nic se ne namesti ali zazene na pravem racunalniku)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="safeer-install-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.izvor = os.path.join(self.tmp, "izvor")
        os.makedirs(os.path.join(self.izvor, "packaging"))
        os.makedirs(os.path.join(self.izvor, "assets"))
        for ime in ("install.sh", "uninstall.sh", "safeer-mint.sh", "safeer-browser.desktop",
                    "packaging/safeer-browser.desktop", "assets/icon.png"):
            shutil.copy(os.path.join(KOREN, ime), os.path.join(self.izvor, ime))
        for ime in ("safeer_brskalnik.py", "safeer_mint.py"):
            with open(os.path.join(self.izvor, ime), "w") as f:
                f.write(f"import sys\nprint({ime!r}, *sys.argv[1:])\n")
        self.dom = os.path.join(self.tmp, "dom")
        os.makedirs(os.path.join(self.dom, "Desktop"))
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        for ime, telo in {"dpkg": "exit 0", "apt-cache": "exit 0", "gio": "exit 0", "pkill": "exit 1",
                          "flatpak": "exit 1", "update-desktop-database": "exit 0",
                          "gtk-update-icon-cache": "exit 0"}.items():
            pot = os.path.join(self.bin, ime)
            with open(pot, "w") as f:
                f.write("#!/bin/sh\n" + telo + "\n")
            os.chmod(pot, 0o755)

    def _okolje(self, **dodatno):
        return {"HOME": self.dom, "PATH": self.bin + ":/usr/bin:/bin", **dodatno}

    def _pozeni(self, skripta, *argumenti, **okolje):
        return subprocess.run(["bash", os.path.join(self.izvor, skripta), *argumenti], env=self._okolje(**okolje),
                              check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)

    def test_namesti_zazene_gtk4_in_odstrani(self):
        self._pozeni("install.sh")
        zaganjalnik = os.path.join(self.dom, ".local/bin/safeer-browser")
        vnos = os.path.join(self.dom, ".local/share/applications/safeer-browser.desktop")
        with open(vnos, encoding="utf-8") as f:
            besedilo = f.read()
        self.assertIn(f"Exec={zaganjalnik} %U", besedilo)
        self.assertIn(f"StartupWMClass={APP_ID}", besedilo)
        self.assertTrue(os.path.exists(os.path.join(self.dom, "Desktop/safeer-browser.desktop")))
        izhod = subprocess.run([zaganjalnik, "https://example.com"], env=self._okolje(), capture_output=True,
                               text=True, check=True, timeout=30).stdout.split()
        self.assertEqual(izhod, ["safeer_brskalnik.py", "https://example.com"])
        izhod = subprocess.run([zaganjalnik], env=self._okolje(SAFEER_BRSKALNIK_GTK3="1"), capture_output=True,
                               text=True, check=True, timeout=30).stdout.split()
        self.assertEqual(izhod, ["safeer_mint.py"])

        self._pozeni("uninstall.sh")
        for pot in (zaganjalnik, os.path.join(self.dom, ".local/bin/safeer"), vnos,
                    os.path.join(self.dom, "Desktop/safeer-browser.desktop"),
                    os.path.join(self.dom, ".local/share/pixmaps/safeer-browser.png"),
                    os.path.join(self.dom, ".local/share/icons/hicolor/256x256/apps/safeer-browser.png")):
            self.assertFalse(os.path.lexists(pot), pot)

    def test_gtk3_vnos_na_izrecno_izbiro(self):
        self._pozeni("install.sh", SAFEER_BRSKALNIK_GTK3="1")
        with open(os.path.join(self.dom, ".local/share/applications/safeer-browser.desktop"), encoding="utf-8") as f:
            self.assertIn("StartupWMClass=safeer-browser\n", f.read())


if __name__ == "__main__":
    unittest.main()
