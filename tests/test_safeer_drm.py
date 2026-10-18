"""Safeer DRM v Spletu Safeer OS (Linux): paket (od 1.0.127 brez prenosa programa; Widevine CDM namesti ECS sam),
zaznava zascitenega videa, vstavitev v zavihek."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import drm, gostitelj, safeer_drm as p

KOREN = Path(__file__).resolve().parents[1]


def _lazni_paket(mapa: Path, izvrsljiv=True) -> Path:
    """Mapa kot <tovor>/safeer-drm: program (Widevine CDM ni v paketu)."""
    exe = mapa / "safeer-drm"
    mapa.mkdir(parents=True, exist_ok=True)
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755 if izvrsljiv else 0o644)
    return mapa


class Paket(unittest.TestCase):
    """Lastnik, 18. 10. 2026: Safeer DRM je v paketu in se med delovanjem ne prenasa; Widevine CDM ni v paketu (ECS ga
    ob prvi zasciteni vsebini sam namesti z Googlovih streznikov)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def test_privzeto_ob_tovoru_paketa(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(p.SPREMENLJIVKA_MAPE, None)
            self.assertEqual(p.vgrajena_mapa(), KOREN / "safeer-drm")    # <tovor>/safeer-drm zraven core/

    def test_izvrsljiva_iz_paketa(self):
        mapa = _lazni_paket(self.tmp / "safeer-drm")
        with mock.patch.dict(os.environ, {p.SPREMENLJIVKA_MAPE: str(mapa)}):
            self.assertEqual(p.izvrsljiva(), mapa / "safeer-drm")
            self.assertTrue(p.Gostitelj.na_voljo())
        self.assertFalse(hasattr(p, "mapa_cdm"))                  # CDM ni del paketa

    def test_neizvrsljiv_ali_brez_paketa_ni_na_voljo(self):
        for mapa in (_lazni_paket(self.tmp / "b", izvrsljiv=False), self.tmp / "ni"):
            with mock.patch.dict(os.environ, {p.SPREMENLJIVKA_MAPE: str(mapa)}):
                self.assertIsNone(p.izvrsljiva(), mapa)
                self.assertFalse(p.Gostitelj.na_voljo())

    def test_med_delovanjem_ni_prenosa(self):
        """Safeer DRM se ne prenasa vec (prej prenesi/pripravi_vnaprej); CDM prenese ECS sam (main.js, ne Python)."""
        for ime in ("prenesi", "prenesi_v_ozadju", "pripravi_vnaprej", "uskladi_logiko", "URL", "SHA256"):
            self.assertFalse(hasattr(p, ime), ime)
        vir = (KOREN / "core" / "safeer_drm.py").read_text(encoding="utf-8")
        self.assertNotIn("urllib.request", vir)
        self.assertNotIn("urlopen", vir)
        self.assertNotIn("zipfile", vir)

    def test_storitve(self):
        self.assertTrue(p.je_storitev("https://www.netflix.com/si/"))
        self.assertFalse(p.je_storitev("https://player.vimeo.com/video/1"))


class Selitev(unittest.TestCase):
    """Nekoc prenesen paket (koren()/X.Y.Z) pospravimo; prijave (profil, profil-spotify) in tuje mape ostanejo."""

    def setUp(self):
        self.koren = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.koren, ignore_errors=True))

    def test_pospravi_samo_nase_stare_kopije(self):
        k = self.koren
        (k / "0.2.0").mkdir(); (k / "0.2.0" / "safeer-drm").write_bytes(b"ELF")
        (k / "0.1.9").mkdir(); (k / "0.1.9" / ".preverjeno").write_text("sha")
        (k / "0.2.0.nova").mkdir()
        (k / "prenos-0.2.0.part").write_bytes(b"x")
        for ime in ("profil", "profil-spotify", "1.10.3", "neznano"):
            (k / ime).mkdir()
        (k / "profil-spotify" / "Cookies").write_bytes(b"prijava")
        (k / "povezava").symlink_to(k / "0.2.0")
        odstranjeno = p.pospravi_staro(k)
        self.assertEqual(sorted(odstranjeno), ["0.1.9", "0.2.0", "0.2.0.nova", "prenos-0.2.0.part"])
        self.assertEqual(sorted(x.name for x in k.iterdir()), ["1.10.3", "neznano", "povezava", "profil", "profil-spotify"])
        self.assertEqual((k / "profil-spotify" / "Cookies").read_bytes(), b"prijava")

    def test_brez_mape_nic(self):
        self.assertEqual(p.pospravi_staro(self.koren / "ni"), [])

    def test_zagon_pospravi_in_ne_prenasa(self):
        """Safeer OS in Safeer Browser ob zagonu samo pospravita staro kopijo (v ozadju), nicesar ne preneseta."""
        os_ = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
        brskalnik = (KOREN / "safeer_brskalnik.py").read_text(encoding="utf-8")
        for vir in (os_, brskalnik):
            self.assertIn("safeer_drm.pospravi_staro_v_ozadju()", vir)
            self.assertNotIn("pripravi_vnaprej", vir)
        splet = (KOREN / "core" / "os_splet.py").read_text(encoding="utf-8")
        self.assertNotIn("prenesi_v_ozadju", splet)
        self.assertNotIn("drm_prenos", splet)


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
        """Safeer OS (Flatpak z org.freedesktop.Flatpak): na gostitelju, program iz paketa po poti, kot jo vidi gostitelj
        ([Instance] app-path v /.flatpak-info)."""
        ukaz = p.ukaz_zagona(["/d/safeer-drm", "--url=https://a.test/"], peskovnik=False, gostitelj=True)
        self.assertEqual(ukaz[:3], ["flatpak-spawn", "--host", "--watch-bus"])
        self.assertTrue(any(a.startswith("--env=DISPLAY=") for a in ukaz))
        self.assertEqual(ukaz[-2:], ["/d/safeer-drm", "--url=https://a.test/"])
        vir = (KOREN / "core" / "safeer_drm.py").read_text(encoding="utf-8")
        self.assertIn('f"--lastnik={os.getpid()}"', vir)
        with tempfile.TemporaryDirectory() as d:
            info = os.path.join(d, "flatpak-info")
            with open(info, "w") as f:
                f.write("[Application]\nname=io.github.memelandfaner.SafeerOS\n\n[Instance]\n"
                        "app-path=/var/lib/flatpak/app/io.github.memelandfaner.SafeerOS/x86_64/master/abc/files\n")
            izvirna = gostitelj.app_na_gostitelju
            with mock.patch.object(gostitelj, "app_na_gostitelju", lambda pot: izvirna(pot, info)):
                ukaz = p.ukaz_zagona(["/app/lib/safeer-os/safeer-drm/safeer-drm", "--parent=5"], peskovnik=False,
                                     gostitelj=True)
            # Zaslon gre samo z neprazno vrednostjo (gostitelj.env_zaslona), zato stevilo --env ni stalno.
            self.assertEqual(ukaz[-2:], ["/var/lib/flatpak/app/io.github.memelandfaner.SafeerOS/x86_64/master/abc/files"
                                         "/lib/safeer-os/safeer-drm/safeer-drm", "--parent=5"])
            # Brez app-path ne ugibamo poti: Safeer DRM se ne zazene (Splet ponudi brskalnik z Widevine).
            with mock.patch.object(gostitelj, "app_na_gostitelju", lambda pot: izvirna(pot, os.path.join(d, "ni"))):
                self.assertIsNone(p.ukaz_zagona(["/app/lib/safeer-os/safeer-drm/safeer-drm"], peskovnik=False,
                                                gostitelj=True))
        self.assertEqual(gostitelj.app_na_gostitelju("/usr/lib/safeer-os/x"), "/usr/lib/safeer-os/x")

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
        """V peskovniku so profili, seje in Widevine CDM (ki ga ECS prenese sam) v zasebnih mapah XDG Flatpaka; mapa
        WidevineCdm obstaja pred zagonom (zypak izpostavi samo obstojeco). Program je v /app (podpeskovniki ga vidijo)."""
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"XDG_DATA_HOME": d + "/data", "XDG_CACHE_HOME": d + "/cache",
                                             "XDG_CONFIG_HOME": d + "/config"}), \
                mock.patch.object(p, "v_peskovniku", return_value=True):
            self.assertEqual(str(p.koren()), d + "/data/safeer-drm")
            self.assertEqual(str(p.mapa_sej()), d + "/cache/safeer-drm")
            okolje = p.okolje_zagona(True)
            self.assertEqual(okolje["ZYPAK_EXPOSE_WIDEVINE_PATH"], d + "/config/Safeer DRM/WidevineCdm")
            self.assertTrue(os.path.isdir(okolje["ZYPAK_EXPOSE_WIDEVINE_PATH"]))
            # Program je od 1.0.127 v /app: brez dodatnih izpostavljenih poti (prej zasebna mapa podatkov).
            self.assertNotIn("ZYPAK_EXPOSE_PATHS", okolje)
        self.assertIsNone(p.okolje_zagona(False))

    def test_logika_je_s_safeer_os(self):
        self.assertTrue((KOREN / "assets" / "safeer_drm" / "main.js").is_file())
        js = (KOREN / "assets" / "safeer_drm" / "main.js").read_text(encoding="utf-8")
        self.assertIn("ukaz.startsWith('key:')", js)
        self.assertIn("argumenti.lastnik", js)

    def test_main_js_cdm_namesti_ecs_brez_slovarjev(self):
        """main.js: Widevine CDM namesti in posodablja ECS sam (components.whenReady, Googlovi strezniki - lastnik,
        18. 10. 2026 po FAQ castLabs), brez gumba in brez namiga na CDM v paketu; slovarji crkovalnika ostanejo izklopljeni
        ob nastanku seje (prej jih je Electron prenesel z redirector.gvt1.com)."""
        js = (KOREN / "assets" / "safeer_drm" / "main.js").read_text(encoding="utf-8")
        self.assertIn("const { app, components, BrowserWindow, session, webFrameMain } = require('electron');", js)
        self.assertIn("components.whenReady()", js)
        self.assertLess(js.index("components.whenReady()"), js.index("odpri(prviUrl);"))     # stran sele s CDM
        self.assertIn("zapisi('DRM_READY'", js)
        self.assertIn("zapisi('DRM_FAILED'", js)
        for odpadlo in ("disable-component-update", "latest-component-updated-widevine-cdm", "process.execPath"):
            self.assertNotIn(odpadlo, js)
        self.assertIn("app.on('session-created'", js)
        self.assertIn("ses.setSpellCheckerLanguages([])", js)
        self.assertEqual(js.count("spellcheck: false"), 2)       # glavno okno in okno prijave

if __name__ == "__main__":
    unittest.main()
