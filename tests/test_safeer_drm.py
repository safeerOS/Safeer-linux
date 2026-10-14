"""Safeer DRM v Spletu Safeer OS (Linux): prenos, zaznava zascitenega videa, vstavitev v zavihek."""
import hashlib
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from core import drm, safeer_drm as p

KOREN = Path(__file__).resolve().parents[1]


class Prenos(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        k = mock.patch.object(p, "koren", return_value=self.tmp / "drm")
        k.start(); self.addCleanup(k.stop)

    def _paket(self, datoteke, pravice=0o755):
        pot = self.tmp / "paket.zip"
        with zipfile.ZipFile(pot, "w") as z:
            for ime, vsebina in datoteke.items():
                info = zipfile.ZipInfo(ime)
                info.external_attr = (0o100000 | pravice) << 16
                z.writestr(info, vsebina)
        return pot.as_uri(), hashlib.sha256(pot.read_bytes()).hexdigest()

    def test_pravilen_paket_in_izvrsljiv(self):
        url, sha = self._paket({"safeer-drm": b"ELF", "chrome-sandbox": b"x"}, 0o4755)
        self.assertTrue(p.prenesi(url, sha))
        exe = p.izvrsljiva()
        self.assertTrue(exe and os.access(exe, os.X_OK))
        self.assertFalse(os.stat(exe.parent / "chrome-sandbox").st_mode & 0o4000)   # brez setuid

    def test_napacen_sha(self):
        url, _ = self._paket({"safeer-drm": b"ELF"})
        self.assertFalse(p.prenesi(url, "0" * 64))
        self.assertIsNone(p.izvrsljiva())

    def test_nevarna_pot(self):
        url, sha = self._paket({"safeer-drm": b"ELF", "../ven": b"x"})
        self.assertFalse(p.prenesi(url, sha))
        self.assertFalse((self.tmp / "ven").exists())

    def test_storitve(self):
        self.assertTrue(p.je_storitev("https://www.netflix.com/si/"))
        self.assertFalse(p.je_storitev("https://player.vimeo.com/video/1"))


class Zaznava(unittest.TestCase):
    def test_skripta_zazna_eme_fairplay_in_zastoj(self):
        self.assertIn("WebKitMediaKeys", drm.SKRIPTA)
        self.assertIn('javi("safeer:zastoj")', drm.SKRIPTA)
        self.assertIn("com\\.apple\\.fps", drm.SKRIPTA)

    def test_sum_ne_odpre_drugega_brskalnika(self):
        vir = (KOREN / "core" / "drm.py").read_text(encoding="utf-8")
        self.assertIn('if _vsebina(_r).startswith("safeer:"):', vir)


class Splet(unittest.TestCase):
    def test_zavihek_vdela_safeer_drm(self):
        vir = (KOREN / "core" / "os_splet.py").read_text(encoding="utf-8")
        self.assertIn("vdelaj=self._drm_vdelaj", vir)
        self.assertIn("safeer_drm.Gostitelj(", vir)
        self.assertIn('z["drm"].ukaz("reload")', vir)
        self.assertIn("gost.tipka(e)", vir)
        self.assertIn("self._drm_konec(z)", vir)

    def test_flatpak_zazene_na_gostitelju(self):
        vir = (KOREN / "core" / "safeer_drm.py").read_text(encoding="utf-8")
        self.assertIn('["flatpak-spawn", "--host", "--watch-bus"]', vir)
        self.assertIn('f"--lastnik={os.getpid()}"', vir)

    def test_logika_je_s_safeer_os(self):
        self.assertTrue((KOREN / "assets" / "safeer_drm" / "main.js").is_file())
        js = (KOREN / "assets" / "safeer_drm" / "main.js").read_text(encoding="utf-8")
        self.assertIn("ukaz.startsWith('key:')", js)
        self.assertIn("argumenti.lastnik", js)


if __name__ == "__main__":
    unittest.main()
