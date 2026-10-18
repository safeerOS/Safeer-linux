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

    def test_nova_verzija_ohrani_profile(self):
        """Regresija (pregled 18. 10. 2026, drm_profil.py): nova verzija pobrise samo stare verzije paketa, ne
        profilov s prijavami (profil, profil-spotify) ali drugih map."""
        koren = self.tmp / "drm"
        for ime in ("profil", "profil-spotify", "0.2.0", "1.10.3", "0.2.0-x", "neznano"):
            (koren / ime).mkdir(parents=True)
        (koren / "profil-spotify" / "Cookies").write_bytes(b"prijava")
        url, sha = self._paket({"safeer-drm": b"ELF"})
        self.assertTrue(p.prenesi(url, sha))
        self.assertEqual(sorted(x.name for x in koren.iterdir() if x.is_dir()),
                         sorted([p.VERZIJA, "0.2.0-x", "neznano", "profil", "profil-spotify"]))
        self.assertEqual((koren / "profil-spotify" / "Cookies").read_bytes(), b"prijava")

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
        self.assertIn("com\\.apple\\.fps", drm.SKRIPTA)
        # Sum zazna samo loceni svet; stran (glavni svet) »safeer:« ne more poslati.
        self.assertIn('poslji("safeer:zastoj")', drm.SKRIPTA_SVET)
        self.assertNotIn("safeer:", drm.SKRIPTA)
        self.assertNotIn("messageHandlers", drm.SKRIPTA)
        self.assertIn("window.top !== window", drm.SKRIPTA_SVET)


class _Upravitelj:
    def __init__(self):
        self.most, self.skripte, self.rokovalnik = None, [], None

    def register_script_message_handler(self, ime, svet):
        self.most = (ime, svet)

    def connect(self, signal, f):
        self.rokovalnik = f

    def add_script(self, s):
        self.skripte.append(s)


class _Pogled:
    def __init__(self, uri):
        self.uri, self.upr, self.js = uri, _Upravitelj(), []

    def get_user_content_manager(self):
        return self.upr

    def get_uri(self):
        return self.uri

    def evaluate_javascript(self, koda, *a):
        self.js.append(koda)


class _Vrednost:
    def __init__(self, v):
        self.v = v

    def to_string(self):
        return self.v


def _W():
    import types

    class US:
        def __init__(self, vir, okvirji, cas, a, b):
            self.vir, self.okvirji, self.svet = vir, okvirji, None

        @staticmethod
        def new_for_world(vir, okvirji, cas, svet, a, b):
            u = US(vir, okvirji, cas, a, b)
            u.svet = svet
            return u
    return types.SimpleNamespace(UserScript=US, UserContentInjectedFrames=types.SimpleNamespace(TOP_FRAME="TOP",
                                                                                               ALL_FRAMES="ALL"),
                                 UserScriptInjectionTime=types.SimpleNamespace(START="START"))


class Privolitev(unittest.TestCase):
    """Pregled 14. 10. 2026: nobena stran (ne zastoj videa ne oglas) ne sme sama zagnati Safeer DRM."""

    def _prikljuci(self, **k):
        self.odprto, self.vdelano, self.ponujeno = [], [], []
        pre = mock.Mock()
        pre.odpri = lambda url: (self.odprto.append(url), ("odprto", "Brave"))[1]
        pogled = _Pogled("https://video.primer.si/film")
        drm.prikljuci(_W(), pogled, pre, lambda: "sl",
                      vdelaj=lambda p, u: self.vdelano.append(u) or True, **k)
        return pogled

    def test_rokovalnik_v_locenem_svetu_samo_glavni_okvir(self):
        p = self._prikljuci()
        self.assertEqual(p.upr.most, (drm.MOST, drm.SVET))
        self.assertEqual([(s.okvirji, s.svet) for s in p.upr.skripte], [("TOP", None), ("TOP", drm.SVET)])

    def test_sum_nikoli_ne_zazene(self):
        p = self._prikljuci()                     # Safeer Browser GTK3 (brez vrstice)
        p.upr.rokovalnik(None, _Vrednost("safeer:zastoj"))
        p.upr.rokovalnik(None, _Vrednost("safeer:zapis"))
        self.assertEqual((self.vdelano, self.odprto), ([], []))

    def test_splet_samo_ponudi(self):
        p = self._prikljuci(ponudi=lambda pg, u, s: self.ponujeno.append((u, s)))
        p.upr.rokovalnik(None, _Vrednost("com.widevine.alpha"))
        p.upr.rokovalnik(None, _Vrednost("safeer:zastoj"))
        self.assertEqual(self.ponujeno, [("https://video.primer.si/film", False), ("https://video.primer.si/film", True)])
        self.assertEqual((self.vdelano, self.odprto), ([], []))

    def test_zavrnjena_stran_nic(self):
        p = self._prikljuci(ponudi=lambda pg, u, s: self.ponujeno.append(u), dovoljeno=lambda u: "zavrni")
        p.upr.rokovalnik(None, _Vrednost("com.widevine.alpha"))
        self.assertEqual((self.ponujeno, self.vdelano, self.odprto), ([], [], []))
        p = self._prikljuci(dovoljeno=lambda u: "zavrni")
        p.upr.rokovalnik(None, _Vrednost("com.widevine.alpha"))
        self.assertEqual((self.vdelano, self.odprto), ([], []))

    def test_gtk3_zahteva_glavnega_okvirja_vdela(self):
        p = self._prikljuci(dovoljeno=lambda u: "dovoli")
        p.upr.rokovalnik(None, _Vrednost("com.widevine.alpha"))
        self.assertEqual(self.vdelano, ["https://video.primer.si/film"])


class Splet(unittest.TestCase):
    def test_zavihek_vdela_safeer_drm(self):
        vir = (KOREN / "core" / "os_splet.py").read_text(encoding="utf-8")
        self.assertIn("vdelaj=self._drm_vdelaj", vir)
        self.assertIn("safeer_drm.Gostitelj(", vir)
        self.assertIn('z["drm"].ukaz("reload")', vir)
        self.assertIn("gost.tipka(e)", vir)
        self.assertIn("self._drm_konec(z)", vir)

    def test_flatpak_safeer_os_zazene_na_gostitelju(self):
        """Safeer OS (Flatpak z org.freedesktop.Flatpak): kot doslej na gostitelju."""
        ukaz = p.ukaz_zagona(["/d/safeer-drm", "--url=https://a.test/"], peskovnik=False, gostitelj=True)
        self.assertEqual(ukaz[:3], ["flatpak-spawn", "--host", "--watch-bus"])
        self.assertTrue(any(a.startswith("--env=DISPLAY=") for a in ukaz))
        self.assertEqual(ukaz[-2:], ["/d/safeer-drm", "--url=https://a.test/"])
        vir = (KOREN / "core" / "safeer_drm.py").read_text(encoding="utf-8")
        self.assertIn('f"--lastnik={os.getpid()}"', vir)

    def test_brskalnik_v_peskovniku_prek_zypaka(self):
        """Safeer Browser (Flatpak brez dostopa do gostitelja): zypak-wrapper v istem peskovniku, nikoli na gostitelju
        in nikoli brez peskovnika Chromiuma (brez zypaka se ne zazene)."""
        with tempfile.TemporaryDirectory() as d:
            zypak = os.path.join(d, "zypak-wrapper")
            with open(zypak, "w") as f:
                f.write("#!/bin/sh\n")
            os.chmod(zypak, 0o755)
            ukaz = p.ukaz_zagona(["/d/safeer-drm", "--parent=5"], peskovnik=True, zypak=zypak)
            self.assertEqual(ukaz, [zypak, "/d/safeer-drm", "--parent=5"])
            self.assertNotIn("--no-sandbox", ukaz)
            self.assertIsNone(p.ukaz_zagona(["/d/safeer-drm"], peskovnik=True, zypak=os.path.join(d, "ni")))
        self.assertEqual(p.ukaz_zagona(["/d/safeer-drm"], peskovnik=False, gostitelj=False), ["/d/safeer-drm"])

    def test_peskovnik_mape_in_widevine(self):
        """V peskovniku so paket, seje in Widevine v zasebnih mapah XDG Flatpaka; mapa WidevineCdm obstaja pred zagonom
        (zypak izpostavi samo obstojeco)."""
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"XDG_DATA_HOME": d + "/data", "XDG_CACHE_HOME": d + "/cache",
                                             "XDG_CONFIG_HOME": d + "/config"}), \
                mock.patch.object(p, "v_peskovniku", return_value=True):
            self.assertEqual(str(p.koren()), d + "/data/safeer-drm")
            self.assertEqual(str(p.mapa_sej()), d + "/cache/safeer-drm")
            okolje = p.okolje_zagona(True)
            self.assertEqual(okolje["ZYPAK_EXPOSE_WIDEVINE_PATH"], d + "/config/Safeer DRM/WidevineCdm")
            self.assertTrue(os.path.isdir(okolje["ZYPAK_EXPOSE_WIDEVINE_PATH"]))
            # Program je v zasebni mapi podatkov: podpeskovnik ga vidi samo prek ZYPAK_EXPOSE_PATHS (nas popravek zypaka).
            self.assertEqual(okolje["ZYPAK_EXPOSE_PATHS"], str(p.mapa_verzije()))
        manifest = (KOREN / "io.github.memelandfaner.SafeerBrowser.yml").read_text(encoding="utf-8")
        self.assertIn("path: packaging/zypak/zypak-expose-paths.patch", manifest)
        self.assertIn("ZYPAK_EXPOSE_PATHS", (KOREN / "packaging/zypak/zypak-expose-paths.patch").read_text())
        self.assertIsNone(p.okolje_zagona(False))

    def test_logika_je_s_safeer_os(self):
        self.assertTrue((KOREN / "assets" / "safeer_drm" / "main.js").is_file())
        js = (KOREN / "assets" / "safeer_drm" / "main.js").read_text(encoding="utf-8")
        self.assertIn("ukaz.startsWith('key:')", js)
        self.assertIn("argumenti.lastnik", js)


if __name__ == "__main__":
    unittest.main()
