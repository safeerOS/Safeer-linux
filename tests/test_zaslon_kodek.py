# -*- coding: utf-8 -*-
"""Kodek slike po dogovoru naprav (HEVC, kadar ga naprava hoce in racunalnik strojno zmore) in dolga skupina slik.

Brez zajema in brez ffmpeg: ukaze samo sestavimo, preizkus kodirnika nadomestimo."""
import os
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec, link_sway, link_zaslon  # noqa: E402

VSE = {"muxer": True, "no_damage": True, "codec_param": True, "framerate": True}


class LazniDrugi:
    def __init__(self, graficna="/dev/dri/renderD128"):
        self.vnos = types.SimpleNamespace(mozno=True, porocaj_kazalec=False, sprosti_vse=lambda: None, zapri=lambda: None)
        self.zadnja_skupina = ""
        self.zadnji_profil = ""
        self.zajemi = []
        self._graficna = graficna

    def tece(self):
        return True

    def okna(self):
        return 1

    def velikost(self, s, v):
        pass

    def osnovno_merilo(self, m):
        pass

    def zvok_vir(self):
        return None

    def okolje(self):
        return dict(os.environ)

    def graficna(self):
        return self._graficna

    def ukaz_zajema(self, fps, qp, bitrate, **dodatki):
        self.zajemi.append((fps, qp, bitrate, dodatki))
        return ["/bin/true"]


class IzbiraKodeka(unittest.TestCase):
    def test_brez_seznama_ali_brez_strojnega_hevc_ostane_h264(self):
        da, ne = (lambda: True), (lambda: False)
        for zeleni in (None, "hevc", [], {}, 7):
            self.assertEqual(link_zaslon.izberi_kodek(zeleni, da), "h264", zeleni)
        self.assertEqual(link_zaslon.izberi_kodek(["hevc", "h264"], ne), "h264")
        self.assertEqual(link_zaslon.izberi_kodek(["hevc"], ne), "h264")
        self.assertEqual(link_zaslon.izberi_kodek(["av1", "vp9"], da), "h264")

    def test_prednost_doloci_naprava(self):
        da = lambda: True  # noqa: E731
        self.assertEqual(link_zaslon.izberi_kodek(["hevc", "h264"], da), "hevc")
        self.assertEqual(link_zaslon.izberi_kodek([" HEVC "], da), "hevc")
        self.assertEqual(link_zaslon.izberi_kodek(["h264", "hevc"], da), "h264")
        self.assertEqual(link_zaslon.izberi_kodek(["hevc", "h264"], True), "hevc")

    def test_kodirnika_ne_preizkusamo_ce_naprava_hevc_noce(self):
        klici = []

        def preizkus():
            klici.append(1)
            return True
        link_zaslon.izberi_kodek(None, preizkus)
        link_zaslon.izberi_kodek(["h264", "hevc"], preizkus)
        self.assertEqual(klici, [])
        link_zaslon.izberi_kodek(["hevc"], preizkus)
        self.assertEqual(klici, [1])


class PreizkusKodirnika(unittest.TestCase):
    def setUp(self):
        link_zaslon._HEVC.clear()

    def tearDown(self):
        link_zaslon._HEVC.clear()

    def test_brez_graficne_ali_ffmpeg_ni_hevc_in_ni_zagona(self):
        with mock.patch.object(link_zaslon.subprocess, "run", side_effect=AssertionError("ne sme zagnati")):
            self.assertFalse(link_zaslon.hevc_mozen("ffmpeg", None))
            self.assertFalse(link_zaslon.hevc_mozen("", "/dev/dri/renderD128"))

    def test_izid_si_zapomni(self):
        klici = []

        def tek(ukaz, **kw):
            klici.append(ukaz)
            return subprocess.CompletedProcess(ukaz, 0, b"", b"")
        with mock.patch.object(link_zaslon.subprocess, "run", tek):
            self.assertTrue(link_zaslon.hevc_mozen("ffmpeg", "/dev/dri/renderD128"))
            self.assertTrue(link_zaslon.hevc_mozen("ffmpeg", "/dev/dri/renderD128"))
        self.assertEqual(len(klici), 1)
        self.assertIn("hevc_vaapi", klici[0])
        self.assertEqual(klici[0][-3:], ["-f", "null", "-"])           # nic ne zapise in nicesar ne zajame

    def test_napaka_kodirnika_pomeni_h264(self):
        with mock.patch.object(link_zaslon.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 1, b"", b"No VA display")):
            self.assertFalse(link_zaslon.hevc_mozen("ffmpeg", "/dev/dri/renderD128"))
        with mock.patch.object(link_zaslon.subprocess, "run", side_effect=OSError("ni ffmpeg")):
            self.assertFalse(link_zaslon.hevc_mozen("ffmpeg", "/dev/dri/renderD129"))


class OdpovedZajema(unittest.TestCase):
    """Zajem s HEVC, ki konca sam in brez slike: do ponovnega zagona Controla H.264."""

    def setUp(self):
        link_zaslon._HEVC.clear()

    def tearDown(self):
        link_zaslon._HEVC.clear()

    def _proces(self, koda):
        return types.SimpleNamespace(wait=lambda timeout=None: koda)

    def _mozen(self):
        with mock.patch.object(link_zaslon.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, b"", b"")):
            return link_zaslon.hevc_mozen("ffmpeg", "/dev/dri/renderD128")

    def test_zajem_konca_sam_brez_slike(self):
        self.assertTrue(self._mozen())
        with mock.patch("builtins.print"):
            link_zaslon.Zaslon._preveri_hevc(self._proces(1), "hevc", [120, False])     # samo besedilo dnevnika
        self.assertFalse(self._mozen())
        self.assertEqual(link_zaslon.izberi_kodek(["hevc", "h264"], self._mozen), "h264")

    def test_zajem_s_sliko_ali_ustavljen_ni_odpoved(self):
        link_zaslon.Zaslon._preveri_hevc(self._proces(0), "hevc", [50000, True])       # slika je tekla
        link_zaslon.Zaslon._preveri_hevc(self._proces(-15), "hevc", [0, False])        # ustavili smo ga mi
        link_zaslon.Zaslon._preveri_hevc(self._proces(1), "h264", [0, False])          # ni HEVC

        def se_tece(timeout=None):
            raise subprocess.TimeoutExpired("wf-recorder", timeout)
        link_zaslon.Zaslon._preveri_hevc(types.SimpleNamespace(wait=se_tece), "hevc", [0, False])
        self.assertTrue(self._mozen())

    def test_crpalka_steje_bajte_in_vidi_enoto(self):
        kosi = [b"wf-recorder: zacenjam\n", b"\x00\x00\x00\x01\x40\x01", b""]
        proces = types.SimpleNamespace(stdout=types.SimpleNamespace(read=lambda n: kosi.pop(0)))
        poslano = []
        prebrano = [0, False]
        link_zaslon.Zaslon(vklopljeno=True)._crpaj(proces, link_zaslon.OKVIR_SLIKA,
                                                   types.SimpleNamespace(sendall=poslano.append), 32 * 1024, prebrano)
        self.assertEqual(prebrano, [28, True])
        self.assertEqual(len(poslano), 2)
        kosi = [b"napaka kodirnika\n", b""]
        prebrano = [0, False]
        link_zaslon.Zaslon(vklopljeno=True)._crpaj(proces, link_zaslon.OKVIR_SLIKA,
                                                   types.SimpleNamespace(sendall=poslano.append), 32 * 1024, prebrano)
        self.assertEqual(prebrano, [17, False])

    def test_crpalka_meri_cas_pisanja(self):
        """`merilo` (meritve seje) dobi vsak sendall: vrsto, bajte celega okvirja in koliko casa je pisanje cakalo."""
        import time
        kosi = [b"\x00\x00\x00\x01\x65" + bytes(95), bytes(20), b""]
        proces = types.SimpleNamespace(stdout=types.SimpleNamespace(read=lambda n: kosi.pop(0)))
        poslano = []

        def pocasi(b):
            time.sleep(0.03)
            poslano.append(b)

        class Merilo:
            def __init__(self):
                self.klici = []

            def poslano(self, vrsta, bajtov, cakal_s):
                self.klici.append((vrsta, bajtov, cakal_s))

        merilo = Merilo()
        link_zaslon.Zaslon(vklopljeno=True)._crpaj(proces, link_zaslon.OKVIR_SLIKA,
                                                   types.SimpleNamespace(sendall=pocasi), 32 * 1024, None,
                                                   merilo=merilo)
        self.assertEqual(len(poslano), 2)
        self.assertEqual([(v, b) for v, b, _ in merilo.klici], [(link_zaslon.OKVIR_SLIKA, 105), (link_zaslon.OKVIR_SLIKA, 25)])
        self.assertTrue(all(0.025 <= c < 1.0 for _, _, c in merilo.klici), merilo.klici)

        # Merilo, ki pade, slike ne ustavi.
        kosi = [bytes(10), bytes(10), b""]
        poslano.clear()

        class Pade:
            def poslano(self, *_a):
                raise RuntimeError("meritev")
        link_zaslon.Zaslon(vklopljeno=True)._crpaj(proces, link_zaslon.OKVIR_ZVOK,
                                                   types.SimpleNamespace(sendall=poslano.append), 1920, merilo=Pade())
        self.assertEqual(len(poslano), 2)

    def test_crpalka_pove_zacetek_pisanja(self):
        """Zastoj mora biti v meritvah viden, medtem ko traja: merilo izve za zacetek vsakega sendall. Pisanje, ki
        pade (rok pisanja), se vseeno konca - brez bajtov, s casom cakanja."""
        dogodki = []

        class Merilo:
            def zacni_pisanje(self, vrsta):
                dogodki.append(("zacni", vrsta))

            def poslano(self, vrsta, bajtov, _cakal_s):
                dogodki.append(("poslano", vrsta, bajtov))

        def sendall(b):
            dogodki.append(("sendall", len(b)))
            if len(dogodki) > 4:
                raise OSError("rok pisanja")

        kosi = [bytes(10), bytes(10), bytes(10), b""]
        proces = types.SimpleNamespace(stdout=types.SimpleNamespace(read=lambda n: kosi.pop(0)))
        slika = link_zaslon.OKVIR_SLIKA
        link_zaslon.Zaslon(vklopljeno=True)._crpaj(proces, slika, types.SimpleNamespace(sendall=sendall), 32 * 1024,
                                                   None, merilo=Merilo())
        self.assertEqual(dogodki, [("zacni", slika), ("sendall", 15), ("poslano", slika, 15),
                                   ("zacni", slika), ("sendall", 15), ("poslano", slika, 0)])


class DiagnozaKodirnika(unittest.TestCase):
    """tools/preveri-kodirnik.py: kratki preizkusi na vsaki napravi, izid kot JSON (brez prave graficne kartice)."""

    def test_vsak_preizkus_na_vsaki_napravi(self):
        ukazi = []

        def zazeni(ukaz, **_k):
            ukazi.append(ukaz)
            # Gonilnik zna samo CQP (kot iHD brez HuC): bitna hitrost pade.
            ok = "VBR" not in ukaz and "CBR" not in ukaz
            return subprocess.CompletedProcess(ukaz, 0 if ok else 1, b"", b"" if ok else b"No usable RC mode\n")

        izid = link_zaslon.diagnoza_kodirnika("ffmpeg", ["/dev/dri/renderD128", "/dev/dri/renderD129"], zazeni=zazeni)
        self.assertEqual(len(ukazi), 2 * len(link_zaslon.PREIZKUSI_KODIRNIKA))
        d = izid["naprave"]["/dev/dri/renderD128"]
        self.assertEqual(sorted(d), sorted(["h264_cqp", "h264_cqp_async_depth_1", "h264_cqp_aud", "h264_vbr_4M",
                                            "h264_cbr_4M", "hevc_cqp"]))
        self.assertTrue(d["h264_cqp"]["ok"])
        self.assertTrue(d["h264_cqp_async_depth_1"]["ok"])
        self.assertFalse(d["h264_vbr_4M"]["ok"])
        self.assertIn("RC mode", d["h264_vbr_4M"]["napaka"])
        for ukaz in ukazi:
            self.assertIn("-frames:v", ukaz)
            self.assertEqual(ukaz[ukaz.index("-frames:v") + 1], "3")
        self.assertTrue(any("-async_depth" in u for u in ukazi))
        self.assertTrue(any("-aud" in u for u in ukazi))
        self.assertTrue(any("huc" in n for n in izid["namigi"]))

    def test_brez_ffmpeg_ali_naprave(self):
        with mock.patch.object(link_zaslon.shutil, "which", return_value=None):
            self.assertIn("napaka", link_zaslon.diagnoza_kodirnika(None, []))
        izid = link_zaslon.diagnoza_kodirnika("ffmpeg", [], zazeni=lambda *a, **k: self.fail("brez naprave ni preizkusa"))
        self.assertEqual(izid["naprave"], {})

    def test_kodirnik_ukaza(self):
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 60, "24M", "/dev/dri/renderD128", qp=16)
        self.assertEqual(link_zaslon.kodirnik_ukaza(u), "h264_vaapi")
        self.assertEqual(link_zaslon.vrsta_kodirnika("h264_vaapi"), "vaapi")
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 60, "24M", None)
        self.assertEqual(link_zaslon.kodirnik_ukaza(u), "libx264")
        self.assertEqual(link_zaslon.vrsta_kodirnika("libx264"), "x264")
        self.assertEqual(link_zaslon.kodirnik_ukaza(["/bin/true"], strojno=True), "h264_vaapi")


class Ukazi(unittest.TestCase):
    def setUp(self):
        link_sway._WF = dict(VSE)

    def tearDown(self):
        link_sway._WF = None

    def test_namizje_hevc_in_dolga_skupina(self):
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 60, "24M", "/dev/dri/renderD128", qp=16,
                                    kodek="hevc", gop=600)
        self.assertEqual(u[u.index("-c:v") + 1], "hevc_vaapi")
        self.assertEqual(u[u.index("-profile:v") + 1], "main")
        self.assertEqual(u[u.index("-qp") + 1], "16")                  # kvantizator (kakovost) ostane isti
        self.assertEqual(u[u.index("-g") + 1], "600")
        self.assertEqual(u[u.index("-f", u.index("-g")) + 1], "hevc")
        self.assertEqual(u[u.index("-bf") + 1], "0")

    def test_namizje_privzeto_kot_doslej(self):
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 60, "24M", "/dev/dri/renderD128", qp=16)
        self.assertEqual(u[u.index("-c:v") + 1], "h264_vaapi")
        self.assertEqual(u[u.index("-profile:v") + 1], "high")
        self.assertEqual(u[u.index("-g") + 1], "60")                   # starejsi gledalec: kljucna slika vsako sekundo
        self.assertEqual(u[-2:], ["h264", "-"])

    def test_brez_graficne_hevc_ni(self):
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 30, "8M", None, kodek="hevc", gop=300)
        self.assertEqual(u[u.index("-c:v") + 1], "libx264")
        self.assertEqual(u[-2:], ["h264", "-"])
        self.assertEqual(u[u.index("-g") + 1], "300")

    def test_loceni_zaslon_hevc_in_dolga_skupina(self):
        d = link_sway.DrugiZaslon(mapa=tempfile.mkdtemp())
        d.graficna = lambda: "/dev/dri/renderD128"
        u = d.ukaz_zajema(60, 16, "24M", kodek="hevc", gop=600)
        self.assertEqual(u[u.index("-m") + 1], "hevc")
        self.assertEqual(u[u.index("-c") + 1], "hevc_vaapi")
        parametri = [u[i + 1] for i, v in enumerate(u) if v == "-p"]
        self.assertEqual(parametri, ["rc_mode=CQP", "qp=16", "profile=main", "bf=0", "g=600"])

    def test_loceni_zaslon_privzeto_kot_doslej(self):
        d = link_sway.DrugiZaslon(mapa=tempfile.mkdtemp())
        d.graficna = lambda: "/dev/dri/renderD128"
        u = d.ukaz_zajema(60, 16, "24M")
        self.assertEqual(u[u.index("-m") + 1], "h264")
        self.assertEqual(u[u.index("-c") + 1], "h264_vaapi")
        self.assertEqual([u[i + 1] for i, v in enumerate(u) if v == "-p"],
                         ["rc_mode=CQP", "qp=16", "profile=high", "bf=0", "g=60"])

    def test_loceni_zaslon_brez_graficne_ostane_x264(self):
        d = link_sway.DrugiZaslon(mapa=tempfile.mkdtemp())
        d.graficna = lambda: None
        u = d.ukaz_zajema(30, 20, "8M", kodek="hevc", gop=300)
        self.assertEqual(u[u.index("-m") + 1], "h264")
        self.assertIn("libx264", u)
        self.assertIn("g=300", u)


class Seja(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("DISPLAY", ":0")
        self.z = link_zaslon.Zaslon(vklopljeno=True, ffmpeg="/bin/true")
        self.z.drugi = LazniDrugi()

    def tearDown(self):
        self.z.ustavi()

    def test_nova_naprava_dobi_hevc_in_dolgo_skupino(self):
        with mock.patch.object(link_zaslon, "hevc_mozen", return_value=True):
            seja = self.z.zacni("fon", "najvisja", "apps", kodeki=["hevc", "h264"], zmoznosti=["gop", "handoff"])
        self.assertEqual(seja["codec"], "hevc")
        fps, qp, _bitrate, dodatki = self.z.drugi.zajemi[-1]
        self.assertEqual((fps, qp), (60, 16))                           # kakovost ostane
        self.assertEqual(dodatki, {"kodek": "hevc", "gop": 600})

    def test_starejsa_naprava_dobi_tok_kot_doslej(self):
        with mock.patch.object(link_zaslon, "hevc_mozen", side_effect=AssertionError("preizkus ni potreben")):
            seja = self.z.zacni("tv", "najvisja", "apps")
        self.assertEqual(seja["codec"], "h264")
        self.assertEqual(self.z.drugi.zajemi[-1][3], {})

    def test_racunalnik_brez_strojnega_hevc(self):
        with mock.patch.object(link_zaslon, "hevc_mozen", return_value=False):
            seja = self.z.zacni("fon", "najvisja", "apps", kodeki=["hevc", "h264"], zmoznosti=["gop"])
        self.assertEqual(seja["codec"], "h264")
        self.assertEqual(self.z.drugi.zajemi[-1][3], {"gop": 600})

    def test_namizje_po_dogovoru(self):
        klici = []

        def ukaz(*a, **kw):
            klici.append(kw)
            return ["/bin/true"]
        with mock.patch.object(link_zaslon, "hevc_mozen", return_value=True), \
                mock.patch.object(link_zaslon, "ukaz_ffmpeg", ukaz), \
                mock.patch.object(link_zaslon, "_zaslon_geometrija", return_value=(1920, 1080)), \
                mock.patch.object(link_zaslon, "gpu_lestvica_mozna",
                                  side_effect=AssertionError("brez pomanjsave preizkus ni potreben")), \
                mock.patch.object(link_zaslon, "vaapi_naprava", return_value="/dev/dri/renderD128"):
            seja = self.z.zacni("fon", "najvisja", "desktop", kodeki=["hevc", "h264"], zmoznosti=["gop"])
            self.assertEqual(seja["codec"], "hevc")
            self.assertEqual(klici[-1], {"kodek": "hevc", "gop": 600, "gpu": False})
            seja = self.z.zacni("tv", "najvisja", "desktop")
            self.assertEqual(seja["codec"], "h264")
            self.assertEqual(klici[-1], {"kodek": "h264", "gop": 0, "gpu": False})

    def test_vecji_zaslon_pomanjsa_graficna(self):
        """F2: zaslon 2560x1440 -> 1080p pomanjsa graficna, ce preizkus uspe; sicer procesor kot prej."""
        klici = []

        def ukaz(*a, **kw):
            klici.append((a, kw))
            return ["/bin/true"]
        for mozna in (True, False):
            with mock.patch.object(link_zaslon, "hevc_mozen", return_value=False), \
                    mock.patch.object(link_zaslon, "ukaz_ffmpeg", ukaz), \
                    mock.patch.object(link_zaslon, "_zaslon_geometrija", return_value=(2560, 1440)), \
                    mock.patch.object(link_zaslon, "gpu_lestvica_mozna", return_value=mozna), \
                    mock.patch.object(link_zaslon, "vaapi_naprava", return_value="/dev/dri/renderD128"):
                self.z.zacni("fon", "najvisja", "desktop", zmoznosti=["gop"])
            a, kw = klici[-1]
            self.assertEqual(a[3:5], (2560, 1440))
            self.assertNotEqual(a[1:3], (2560, 1440))
            self.assertEqual(kw["gpu"], mozna)


class LazniGledalec:
    """Povezava gledalca: zapomni si, kar racunalnik poslje; vnosa ne posilja."""

    def __init__(self):
        self.poslano = []

    def sendall(self, b):
        self.poslano.append(bytes(b))

    def settimeout(self, t):
        pass

    def recv(self, n):
        return b""

    def shutdown(self, kako):
        pass

    def close(self):
        pass

    def glava(self):
        return __import__("json").loads(self.poslano[0].decode("utf-8"))


class LazniZajem:
    """Zajem, ki takoj konca (brez slike); belezi se samo ukaz."""
    returncode = -15

    def __init__(self):
        self.stdout = types.SimpleNamespace(read=lambda n: b"", close=lambda: None)

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        pass

    def kill(self):
        pass


class KodekPoPoti(unittest.TestCase):
    """HEVC samo gledalcu, ki pride prek Huba (Global Link); v domacem omrezju H.264."""

    def test_pravilo(self):
        self.assertEqual(link_zaslon.kodek_za_pot("hevc", True), "hevc")
        self.assertEqual(link_zaslon.kodek_za_pot("hevc", False), "h264")
        self.assertEqual(link_zaslon.kodek_za_pot("h264", True), "h264")
        self.assertEqual(link_zaslon.kodek_za_pot("h264", False), "h264")

    def _seja(self, prek_huba, kodeki, omrezje=""):
        """Seja za namizje do trenutka, ko se gledalec poveze: vrne (glava toka, ukaz zajema)."""
        os.environ.setdefault("DISPLAY", ":0")
        z = link_zaslon.Zaslon(vklopljeno=True, ffmpeg="/bin/true")
        klic = {}
        z._streci = lambda *a: klic.setdefault("a", a)          # nit seje: samo zapomni si, s cim bi tekla
        zagnano = []

        def popen(ukaz, **kw):
            zagnano.append(list(ukaz))
            return LazniZajem()
        gledalec = LazniGledalec()
        import threading
        try:
            with mock.patch.object(link_zaslon, "hevc_mozen", return_value=True), \
                    mock.patch.object(link_zaslon, "vaapi_naprava", return_value="/dev/dri/renderD128"), \
                    mock.patch.object(link_zaslon, "privzeti_monitor", return_value=None):
                seja = z.zacni("fon", "najvisja", "desktop", kodeki=kodeki, zmoznosti=["gop"], omrezje=omrezje)
                z._nit.join(timeout=2)
                z._sprejmi = lambda posluh, ctx: (gledalec, threading.Event() if prek_huba else None)
                with mock.patch.object(link_zaslon.subprocess, "Popen", popen), mock.patch("builtins.print"):
                    link_zaslon.Zaslon._streci(z, *klic["a"])
        finally:
            z.ustavi()
        return seja, gledalec.glava(), zagnano[0]

    def test_prek_huba_hevc(self):
        seja, glava, ukaz = self._seja(True, ["hevc", "h264"])
        self.assertEqual((seja["codec"], glava["kodek"]), ("hevc", "hevc"))
        self.assertIn("hevc_vaapi", ukaz)
        self.assertEqual(ukaz[ukaz.index("-g") + 1], "600")
        # zdoma brez podatka o omrezju: stopnja za obicajno povezavo 4G
        self.assertEqual(ukaz[ukaz.index("-qp") + 1], "20")
        self.assertEqual((glava["qp"], glava["kakovost"]), (20, "mobilna"))

    def test_kakovost_po_omrezju_gledalca(self):
        for omrezje, qp, stopnja in (("4g", "20", "mobilna"), ("wifi", "20", "mobilna"), ("ethernet", "20", "mobilna"),
                                     ("celicno", "20", "mobilna"), ("5g", "18", "visoka"), ("5G", "18", "visoka")):
            _seja, glava, ukaz = self._seja(True, ["hevc", "h264"], omrezje)
            self.assertEqual(ukaz[ukaz.index("-qp") + 1], qp, omrezje)
            self.assertEqual((glava["qp"], glava["kakovost"], glava["fps"]), (int(qp), stopnja, 60), omrezje)
        # doma omrezje gledalca ne spremeni nicesar: najvisja kakovost
        for omrezje in ("4g", "5g", "wifi", ""):
            _seja, glava, ukaz = self._seja(False, ["hevc", "h264"], omrezje)
            self.assertEqual(ukaz[ukaz.index("-qp") + 1], "16", omrezje)
            self.assertEqual((glava["qp"], glava["kakovost"]), (16, "najvisja"), omrezje)

    def test_pravilo_kakovosti(self):
        k = link_zaslon.kakovost_za_pot
        self.assertEqual(k("najvisja", False, "4g"), "najvisja")
        self.assertEqual(k("najvisja", True, ""), "mobilna")
        self.assertEqual(k("najvisja", True, "4g"), "mobilna")
        self.assertEqual(k("najvisja", True, "5g"), "visoka")
        self.assertEqual(k("visoka", True, "4g"), "mobilna")
        self.assertEqual(k("visoka", True, "5g"), "visoka")
        # nikoli vec, kot je naprava zahtevala
        self.assertEqual(k("srednja", True, "5g"), "srednja")
        self.assertEqual(k("nizka", True, "4g"), "nizka")
        self.assertEqual(k("mobilna", True, "5g"), "mobilna")
        # neznana stopnja je privzeta (najvisja)
        self.assertEqual(k("ni-take", False, ""), "najvisja")
        self.assertEqual(k("ni-take", True, ""), "mobilna")
        # stopnje so urejene po podatkih; vse so v seznamu
        self.assertEqual(set(link_zaslon.VRSTNI_RED_KAKOVOSTI), set(link_zaslon.KAKOVOSTI))
        qp = [link_zaslon.KAKOVOSTI[x]["qp"] for x in link_zaslon.VRSTNI_RED_KAKOVOSTI]
        self.assertEqual(qp, sorted(qp, reverse=True))
        self.assertEqual(link_zaslon.KAKOVOSTI["mobilna"]["fps"], 60)

    def test_neposredno_h264_z_isto_skupino_slik(self):
        seja, glava, ukaz = self._seja(False, ["hevc", "h264"])
        self.assertEqual(seja["codec"], "hevc")                 # dogovor; velja glava toka
        self.assertEqual(glava["kodek"], "h264")
        self.assertIn("h264_vaapi", ukaz)
        self.assertNotIn("hevc_vaapi", ukaz)
        self.assertEqual(ukaz[ukaz.index("-g") + 1], "600")     # dolga skupina slik ostane
        self.assertEqual(ukaz[ukaz.index("-qp") + 1], "16")     # kakovost ostane

    def test_naprava_brez_hevc_ostane_kot_je(self):
        for prek_huba in (True, False):
            seja, glava, ukaz = self._seja(prek_huba, ["h264"])
            self.assertEqual((seja["codec"], glava["kodek"]), ("h264", "h264"))
            self.assertIn("h264_vaapi", ukaz)


class UkazZaslona(unittest.TestCase):
    def test_codecs_pridejo_do_seje(self):
        klici = []

        class Zaslon:
            drugi = None

            def na_voljo(self):
                return {"dovoljeno": True, "mozno": True}

            def zacni(self, posiljatelj, kakovost, cilj, **dodatno):
                klici.append(dodatno)
                return {"port": 1, "screen": "apps"}

        izidi = []
        link_daljinec.izvedi_control("screen.start", {"screen": "apps", "codecs": ["hevc", 5, "h264"], "caps": ["gop"]},
                                     lambda u: None, izidi.append, zaslon=Zaslon(), posiljatelj="fon")
        link_daljinec.izvedi_control("screen.start", {"screen": "apps", "codecs": "hevc"},
                                     lambda u: None, izidi.append, zaslon=Zaslon(), posiljatelj="fon")
        self.assertTrue(all(i.get("ok") for i in izidi), izidi)
        self.assertEqual(klici[0], {"kodeki": ["hevc", "h264"], "zmoznosti": ["gop"]})
        self.assertEqual(klici[1], {})                                 # neveljaven seznam se ne preda
        link_daljinec.izvedi_control("screen.start", {"screen": "apps", "net": "4g"},
                                     lambda u: None, izidi.append, zaslon=Zaslon(), posiljatelj="fon")
        link_daljinec.izvedi_control("screen.start", {"screen": "apps", "net": 5},
                                     lambda u: None, izidi.append, zaslon=Zaslon(), posiljatelj="fon")
        self.assertEqual(klici[2], {"omrezje": "4g"})
        self.assertEqual(klici[3], {})                                 # omrezje mora biti besedilo


class PomanjsavaNaGraficni(unittest.TestCase):
    """F2: sliko, ki jo je treba pomanjsati, pretvori in pomanjsa graficna (hwupload,scale_vaapi), ne lanczos."""

    VAAPI = "/dev/dri/renderD128"

    def setUp(self):
        link_zaslon._GPU.clear()

    def tearDown(self):
        link_zaslon._GPU.clear()

    def _vf(self, u):
        return u[u.index("-vf") + 1]

    def test_ukaz_pomanjsa_na_graficni(self):
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 2560, 1440, 60, "8M", self.VAAPI, qp=18, kodek="hevc", gpu=True)
        self.assertEqual(self._vf(u), "hwupload,scale_vaapi=1920:1080:format=nv12")
        self.assertNotIn("lanczos", " ".join(u))
        self.assertEqual(u[u.index("-c:v") + 1], "hevc_vaapi")
        self.assertEqual(u[u.index("-qp") + 1], "18")
        self.assertTrue(link_zaslon.ukaz_pomanjsa_gpu(u))

    def test_brez_pomanjsave_ali_brez_graficne_ostane_stara_pot(self):
        enako = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 60, "8M", self.VAAPI, gpu=True)
        self.assertEqual(self._vf(enako), "format=nv12,hwupload")
        self.assertFalse(link_zaslon.ukaz_pomanjsa_gpu(enako))
        procesor = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 2560, 1440, 60, "8M", None, gpu=True)
        self.assertIn("libx264", procesor)
        self.assertNotIn("scale_vaapi", " ".join(procesor))
        prej = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 2560, 1440, 60, "8M", self.VAAPI)
        self.assertEqual(self._vf(prej), "scale=1920:1080:flags=lanczos,format=nv12,hwupload")

    def test_preizkus_brez_graficne_ali_izklopljen_se_ne_zazene(self):
        with mock.patch.object(link_zaslon.subprocess, "run", side_effect=AssertionError("ne sme zagnati")):
            self.assertFalse(link_zaslon.gpu_lestvica_mozna("ffmpeg", None))
            self.assertFalse(link_zaslon.gpu_lestvica_mozna("", self.VAAPI))
            with mock.patch.dict(os.environ, {"SAFEER_ZASLON_GPU": "0"}):
                self.assertFalse(link_zaslon.gpu_lestvica_mozna("ffmpeg", self.VAAPI))

    def test_preizkus_na_obliki_x11grab_in_izid_si_zapomni(self):
        klici = []

        def tek(ukaz, **kw):
            klici.append(ukaz)
            return subprocess.CompletedProcess(ukaz, 0, b"", b"")
        with mock.patch.object(link_zaslon.subprocess, "run", tek), mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAFEER_ZASLON_GPU", None)
            self.assertTrue(link_zaslon.gpu_lestvica_mozna("ffmpeg", self.VAAPI))
            self.assertTrue(link_zaslon.gpu_lestvica_mozna("ffmpeg", self.VAAPI))
        self.assertEqual(len(klici), 1)
        ukaz = " ".join(klici[0])
        self.assertIn("format=bgr0", ukaz)                              # kot x11grab
        self.assertIn("hwupload,scale_vaapi=", ukaz)
        self.assertEqual(klici[0][-3:], ["-f", "null", "-"])

    def test_napaka_pomeni_procesor(self):
        with mock.patch.object(link_zaslon.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 1, b"", b"Failed to upload frame")):
            self.assertFalse(link_zaslon.gpu_lestvica_mozna("ffmpeg", self.VAAPI))
        with mock.patch.object(link_zaslon.subprocess, "run", side_effect=OSError("ni ffmpeg")):
            self.assertFalse(link_zaslon.gpu_lestvica_mozna("ffmpeg", "/dev/dri/renderD129"))

    def test_zajem_brez_slike_vrne_procesor(self):
        def mozna():
            with mock.patch.object(link_zaslon.subprocess, "run",
                                   return_value=subprocess.CompletedProcess([], 0, b"", b"")):
                return link_zaslon.gpu_lestvica_mozna("ffmpeg", self.VAAPI)
        gpu = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 2560, 1440, 60, "8M", self.VAAPI, gpu=True)
        cpu = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 2560, 1440, 60, "8M", self.VAAPI)

        def proces(koda):
            return types.SimpleNamespace(wait=lambda timeout=None: koda)
        self.assertTrue(mozna())
        link_zaslon.Zaslon._preveri_gpu(proces(0), gpu, [50000, True])     # slika je tekla
        link_zaslon.Zaslon._preveri_gpu(proces(-15), gpu, [0, False])      # ustavili smo ga mi
        link_zaslon.Zaslon._preveri_gpu(proces(1), cpu, [0, False])        # ni pomanjsave na graficni
        self.assertTrue(mozna())
        with mock.patch("builtins.print"):
            link_zaslon.Zaslon._preveri_gpu(proces(1), gpu, [0, False])
        self.assertFalse(mozna())


if __name__ == "__main__":
    unittest.main()
