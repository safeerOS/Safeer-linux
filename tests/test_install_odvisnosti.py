#!/usr/bin/env python3
"""Namestitev iz izvorne kode (install.sh, safeer-mint.sh) in debian/ sta GTK4 kot paketi .deb, Flatpak in AppImage.

Odlocitev lastnika 16. 10. 2026: GTK4 (WebKitGTK 6.0) je privzet povsod; GTK3 je umaknjen 18. 10. 2026. Vir resnice za pakete je Depends v build_deb.sh (prej je install.sh preveril
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


def _depends_build_deb() -> set:
    najdeno = re.search(r'else\s+ODVISNOSTI="([^"]+)"', _beri("build_deb.sh"))
    assert najdeno, "build_deb.sh nima seznama ODVISNOSTI"
    return _paketi(najdeno.group(1))


def _paketi_install() -> set:
    najdeno = re.search(r'(?m)^PAKETI="([^"]+)"', _beri("install.sh"))
    assert najdeno, "install.sh nima seznama PAKETI"
    return set(najdeno.group(1).split())


class PreizkusOdvisnostiNamestitve(unittest.TestCase):
    def test_install_sh_preveri_odvisnosti_paketa_gtk4(self):
        preverjeni = _paketi_install()
        self.assertLessEqual(_depends_build_deb(), preverjeni)
        self.assertIn("gir1.2-webkit-6.0", preverjeni)
        self.assertIn("gir1.2-gtk-4.0", preverjeni)
        self.assertNotIn("gir1.2-gtk-3.0", preverjeni)
        self.assertIn("Linux Mint 22 / Ubuntu 24.04", _beri("install.sh"))

    def test_gtk3_ni_vec(self):
        for ime in ("install.sh", "build_deb.sh", "safeer-mint.sh", "packaging/install_payload.sh"):
            self.assertNotIn("SAFEER_BRSKALNIK_GTK3", _beri(ime), ime)
        self.assertFalse(os.path.exists(os.path.join(KOREN, "safeer_mint.py")))

    def test_debian_control_je_gtk4(self):
        control = _beri("debian/control")
        # Dva odstavka: izvorni (Build-Depends) in paket safeer-browser (Depends) - preverjamo Depends paketa.
        self.assertRegex(control, r"(?m)^Source: safeer-browser$")
        self.assertRegex(control, r"(?m)^Build-Depends: debhelper-compat")
        paket = control.split("\nPackage: safeer-browser\n", 1)[1]
        zahteve = re.split(r"(?m)^Depends:", paket, 1)[1].split("Recommends:", 1)[0]
        zahteve = re.sub(r"\$\{[^}]+\}", "", zahteve)
        self.assertEqual(_paketi(zahteve), _depends_build_deb())
        for star in ("gir1.2-gtk-3.0", "gir1.2-webkit2-4.1", "libwebkit2gtk-4.1"):
            self.assertNotIn(star, zahteve)
        self.assertIn("GTK4", control)
        self.assertNotIn("GTK3", control)
        # debian/rules mora namestiti isti (GTK4) tovor.
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


class PreizkusNamestitveVLaznemDomu(unittest.TestCase):
    """install.sh, safeer-mint.sh in uninstall.sh v lazni domaci mapi; dpkg in orodja namizja so nadomestki,
    vstopa sta skripti, ki izpiseta svoje ime (nic se ne namesti ali zazene na pravem racunalniku)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="safeer-install-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.izvor = os.path.join(self.tmp, "izvor")
        os.makedirs(os.path.join(self.izvor, "packaging"))
        os.makedirs(os.path.join(self.izvor, "assets"))
        for ime in ("install.sh", "uninstall.sh", "safeer-mint.sh",
                    "packaging/safeer-browser.desktop", "assets/brskalnik.svg"):
            shutil.copy(os.path.join(KOREN, ime), os.path.join(self.izvor, ime))
        shutil.copytree(os.path.join(KOREN, "packaging", "icons", "hicolor"),
                        os.path.join(self.izvor, "packaging", "icons", "hicolor"))
        with open(os.path.join(self.izvor, "safeer_brskalnik.py"), "w") as f:
            f.write("import sys\nprint('safeer_brskalnik.py', *sys.argv[1:])\n")
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
        # Svoja ikona brskalnika (globus), ne scit Safeer OS (assets/icon.png) - lastnik, 17. 10. 2026.
        ikona = os.path.join(self.dom, ".local/share/icons/hicolor/256x256/apps/safeer-browser.png")
        with open(ikona, "rb") as f, open(os.path.join(KOREN, "assets", "icon.png"), "rb") as g:
            self.assertNotEqual(f.read(), g.read())
        self.assertTrue(os.path.isfile(os.path.join(self.dom, ".local/share/icons/hicolor/scalable/apps/safeer-browser.svg")))
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

        self._pozeni("uninstall.sh")
        for pot in (zaganjalnik, os.path.join(self.dom, ".local/bin/safeer"), vnos,
                    os.path.join(self.dom, "Desktop/safeer-browser.desktop"),
                    os.path.join(self.dom, ".local/share/pixmaps/safeer-browser.png"),
                    os.path.join(self.dom, ".local/share/icons/hicolor/256x256/apps/safeer-browser.png"),
                    os.path.join(self.dom, ".local/share/icons/hicolor/scalable/apps/safeer-browser.svg")):
            self.assertFalse(os.path.lexists(pot), pot)


if __name__ == "__main__":
    unittest.main()
