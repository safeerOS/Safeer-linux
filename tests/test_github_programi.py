"""Programi z GitHuba (core/os_github_programi.py): samo branje javnega API-ja, prenos le z GitHuba v izbrano mapo."""
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from core import os_github_programi as g


class Odgovor(io.BytesIO):
    def __init__(self, podatki: bytes, url="https://github.com/x", glave=None):
        super().__init__(podatki)
        self._url = url
        self.headers = glave or {}

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Pravila(unittest.TestCase):
    def test_isci_in_izdaje(self):
        repo = {"items": [{"full_name": "a/b", "description": "opis", "stargazers_count": 5, "license": {"spdx_id": "MIT"},
                           "pushed_at": "2026-10-01T00:00:00Z", "archived": False}]}
        r = g.isci("b", odpri=lambda z, timeout: Odgovor(json.dumps(repo).encode()))
        self.assertEqual(r["repozitoriji"][0]["repo"], "a/b")
        izd = [{"tag_name": "v1", "name": "1.0", "published_at": "2026-10-01T00:00:00Z", "draft": False, "prerelease": False,
                "assets": [{"name": "app.deb", "size": 1048576, "download_count": 3, "browser_download_url": "https://github.com/a/b/releases/download/v1/app.deb"},
                           {"name": "app.exe", "size": 10, "download_count": 1, "browser_download_url": "https://github.com/a/b/x.exe"}]},
               {"tag_name": "osnutek", "draft": True, "assets": []}]
        r = g.izdaje("a/b", odpri=lambda z, timeout: Odgovor(json.dumps(izd).encode()))
        self.assertEqual(len(r["izdaje"]), 1)
        self.assertEqual([(d["ime"], d["linux"], d["mb"]) for d in r["izdaje"][0]["datoteke"]], [("app.deb", True, 1.0), ("app.exe", False, 0.0)])

    def test_neveljaven_repo_in_omejitev(self):
        self.assertEqual(g.izdaje("../../etc")["napaka"], "neveljaven")
        def omejeno(z, timeout):
            raise OSError("HTTP Error 403: rate limit exceeded")
        self.assertEqual(g.isci("x", odpri=omejeno)["napaka"], "omejitev")

    def test_dovoljeni_naslovi_in_imena(self):
        self.assertTrue(g.dovoljen_naslov("https://github.com/a/b/releases/download/v1/x.deb"))
        self.assertTrue(g.dovoljen_naslov("https://objects.githubusercontent.com/x"))
        self.assertFalse(g.dovoljen_naslov("http://github.com/x"))
        self.assertFalse(g.dovoljen_naslov("https://evil.example/github.com/x"))
        self.assertEqual(g.varno_ime("../../.bashrc"), "bashrc")
        with tempfile.TemporaryDirectory() as t:
            open(os.path.join(t, "a.tar.gz"), "w").close()
            self.assertEqual(os.path.basename(g.ciljna_pot(t, "a.tar.gz")), "a (2).tar.gz")

    def test_prenos_v_mapo_brez_prepisa(self):
        with tempfile.TemporaryDirectory() as t:
            open(os.path.join(t, "app.deb"), "wb").write(b"staro")
            p = g.Prenosi(odpri=lambda z, timeout: Odgovor(b"novo" * 1000, glave={"Content-Length": "4000"}))
            r = p.zacni("https://github.com/a/b/releases/download/v1/app.deb", "app.deb", t)
            for _ in range(100):
                if p.stanje(r["id"])["stanje"] != "prenasam":
                    break
                time.sleep(0.02)
            s = p.stanje(r["id"])
            self.assertEqual(s["stanje"], "koncano")
            self.assertEqual(os.path.basename(s["pot"]), "app (2).deb")
            self.assertEqual(open(os.path.join(t, "app.deb"), "rb").read(), b"staro")
            self.assertEqual(sorted(os.listdir(t)), ["app (2).deb", "app.deb"])

    def test_linux_in_ta_racunalnik(self):
        self.assertFalse(g.za_linux("app-windows-x86-64.zip"))
        self.assertFalse(g.za_linux("app-macos-arm-64.tar.gz"))
        self.assertTrue(g.za_linux("app-linux-x86-64.deb"))
        self.assertTrue(g.za_ta_racunalnik("app-linux-x86-64.deb", "x86_64"))
        self.assertFalse(g.za_ta_racunalnik("app-linux-arm-64.deb", "x86_64"))
        self.assertTrue(g.za_ta_racunalnik("app.AppImage", "x86_64"))
        self.assertTrue(g.za_ta_racunalnik("app_arm64.deb", "aarch64"))

    def test_sistem_datoteke_in_zvrst(self):
        pricakovano = {"app-windows-x86-64.zip": "windows", "app.msi": "windows", "app-macos-arm-64.tar.gz": "macos",
                       "app.dmg": "macos", "app-android-arm64.apk": "android", "app.ipa": "ios", "app-linux-x86-64.deb": "linux",
                       "app.AppImage": "linux", "app-x86_64.flatpak": "linux", "source.tar.gz": "drugo",
                       "mpv-v0.41.0-x86_64-w64-mingw32.zip": "windows", "libmpv-v0.41.0-i686-w64-mingw32-gpl.zip": "windows",
                       "app-win-x64.zip": "windows"}
        self.assertFalse(g.za_ta_racunalnik("mpv-v0.41.0-x86_64-w64-mingw32.zip", "x86_64"))
        for ime, sistem in pricakovano.items():
            self.assertEqual(g.sistem_datoteke(ime), sistem, ime)
        self.assertEqual(g.zvrst(["video-player", "mpv"], "A media player"), "mediji")
        self.assertEqual(g.zvrst([], "An open-source cross-platform alternative to AirDrop"), "komunikacija")
        self.assertEqual(g.zvrst(["game", "emulator"], ""), "igre")
        self.assertEqual(g.zvrst([], ""), "drugo")
        js = (Path(__file__).resolve().parent.parent / "assets/os/delovna.js").read_text(encoding="utf-8")
        for k in g.ZVRSTI:
            self.assertEqual(js.count("ppZvrst_" + k + ":"), 2, k)

    def test_sha256_ujemanje_in_neujemanje(self):
        import hashlib
        vsebina = b"paket" * 100
        prav = hashlib.sha256(vsebina).hexdigest()
        with tempfile.TemporaryDirectory() as t:
            p = g.Prenosi(odpri=lambda z, timeout: Odgovor(vsebina))
            for sha, stanje in ((prav, "koncano"), ("0" * 64, "napaka")):
                r = p.zacni("https://github.com/a/b/x.deb", "x.deb", t, sha)
                for _ in range(100):
                    if p.stanje(r["id"])["stanje"] != "prenasam":
                        break
                    time.sleep(0.02)
                s = p.stanje(r["id"])
                self.assertEqual(s["stanje"], stanje)
                if stanje == "koncano":
                    self.assertTrue(s["preverjeno"])
                else:
                    self.assertEqual(s["koda"], "kontrolna")
            self.assertEqual(sorted(os.listdir(t)), ["x.deb"], "neujemajoca datoteka ne ostane")

    def test_prenos_zavrne_tuj_naslov_in_preusmeritev(self):
        with tempfile.TemporaryDirectory() as t:
            p = g.Prenosi(odpri=lambda z, timeout: Odgovor(b"x", url="https://evil.example/x"))
            self.assertEqual(p.zacni("https://evil.example/x", "x", t)["koda"], "naslov")
            r = p.zacni("https://github.com/a/b/x.deb", "x.deb", t)
            for _ in range(100):
                if p.stanje(r["id"])["stanje"] != "prenasam":
                    break
                time.sleep(0.02)
            self.assertEqual(p.stanje(r["id"])["koda"], "naslov")
            self.assertEqual(os.listdir(t), [])


if __name__ == "__main__":
    unittest.main()
