#!/usr/bin/env python3
"""uninstall.sh brise prave mape brskalnika iz izvorne kode in nic drugega.

Pregled 16. 10. 2026: CACHE_DIR je kazal na ~/.cache/safeer_mint.py, WebKit pa od GLib.set_prgname("safeer-browser")
pise v ~/.cache/safeer-browser; brez --purge mora profil (nastavitve, zaznamki) ostati, kot skripta obljublja.
Skripta tece v lazni domaci mapi; pkill, dpkg in flatpak so nadomestki (nic se ne ustavi na pravem racunalniku)."""

import os
import shutil
import subprocess
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAPE = {
    "profil": ".config/safeer-mint/settings.json",
    "profil_predpomnilnik": ".config/safeer-mint/web-data/cache/x",
    "profil_strani": ".config/safeer-mint/web-data/localstorage/x",
    "webkit_predpomnilnik": ".cache/safeer-browser/WebKitCache/x",
    "star_predpomnilnik": ".cache/safeer_mint.py/x",
    "webkit_podatki": ".local/share/safeer-browser/storage/x",
    "stari_podatki": ".local/share/safeer_mint.py/localstorage/x",
    "seznami": ".local/share/safeer-mint/threat-intel/x",
    "safeer_os": ".config/safeer-os/x",
    "safeer_os_podatki": ".local/share/safeer-os/x",
    "safeer_os_predpomnilnik": ".cache/safeer-os/x",
    "tuje": ".cache/drugo/x",
}


class PreizkusOdstranitve(unittest.TestCase):
    def setUp(self):
        self.dom = tempfile.mkdtemp(prefix="safeer-uninstall-")
        self.addCleanup(shutil.rmtree, self.dom, True)
        for pot in MAPE.values():
            os.makedirs(os.path.dirname(os.path.join(self.dom, pot)), exist_ok=True)
            with open(os.path.join(self.dom, pot), "w") as f:
                f.write("x")
        self.bin = os.path.join(self.dom, "bin")
        os.makedirs(self.bin)
        self.namesceni = os.path.join(self.dom, "namesceni")
        open(self.namesceni, "w").close()
        nadomestki = {
            "pkill": "exit 1",
            "dpkg": f'[ "$1" = -s ] && grep -qx "$2" "{self.namesceni}"',
            "flatpak": "exit 1",
            "update-desktop-database": "exit 0",
            "gtk-update-icon-cache": "exit 0",
        }
        for ime, telo in nadomestki.items():
            pot = os.path.join(self.bin, ime)
            with open(pot, "w") as f:
                f.write("#!/bin/sh\n" + telo + "\n")
            os.chmod(pot, 0o755)

    def _pozeni(self, *argumenti):
        okolje = {"HOME": self.dom, "PATH": self.bin + ":/usr/bin:/bin"}
        subprocess.run(["bash", os.path.join(KOREN, "uninstall.sh"), *argumenti], env=okolje, check=True,
                       stdout=subprocess.DEVNULL, timeout=30)
        return {k for k, p in MAPE.items() if os.path.exists(os.path.join(self.dom, p))}

    def test_brez_purge_ostane_profil(self):
        ostalo = self._pozeni()
        self.assertEqual(ostalo, set(MAPE) - {"webkit_predpomnilnik", "star_predpomnilnik", "profil_predpomnilnik"})

    def test_purge_odstrani_samo_mape_brskalnika(self):
        ostalo = self._pozeni("--purge")
        self.assertEqual(ostalo, {"safeer_os", "safeer_os_podatki", "safeer_os_predpomnilnik", "tuje"})

    def test_purge_ne_brise_skupnega_profila_ob_namescenem_safeer_os(self):
        with open(self.namesceni, "w") as f:
            f.write("safeer-os\n")
        ostalo = self._pozeni("--purge")
        self.assertIn("profil", ostalo)
        self.assertIn("seznami", ostalo)
        self.assertNotIn("webkit_predpomnilnik", ostalo)


if __name__ == "__main__":
    unittest.main()
