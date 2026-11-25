"""Rob slike (overscan) v kodirani sliki racunalnika (core/link_zaslon.py, screen.start "rob").

Lastnik 25. 11. 2026: TV obreze video ravnino (levo, desno, spodaj 11-20 pik od 1920x1080), zato pomanjsan pogled na
TV ne pomaga - okvir mora biti v sliki sami. Pravilo kot ZaslonRob na TV: levo/desno = sodo navzdol(sirina*p/1000),
zgoraj/spodaj = sodo navzdol(visina*p/1000), p = 0..80 promilov.
"""
import os
import tempfile
import unittest
from unittest import mock

from core import link_daljinec, link_kazalec, link_zaslon, link_zaslon_profil

VAAPI = "/dev/dri/renderD128"
# 1920x1080, rob 10: 1920*10/1000 = 19 -> 18, 1080*10/1000 = 10 -> 10; notranja 1884x1060.
FILTER_10 = "scale=1884:1060:flags=lanczos,pad=1920:1080:18:10:black"


def vf(u):
    return u[u.index("-vf") + 1]


class Pravilo(unittest.TestCase):
    def test_okvir_kot_na_tv(self):
        self.assertEqual(link_zaslon.okvir_roba(1920, 1080, 10), (18, 10))
        self.assertEqual(link_zaslon.okvir_roba(3840, 2160, 10), (38, 20))
        self.assertEqual(link_zaslon.okvir_roba(1920, 1080, 80), (152, 86))
        self.assertEqual(link_zaslon.okvir_roba(1920, 1080, 0), (0, 0))
        self.assertEqual(link_zaslon.okvir_roba(0, 1080, 10), (0, 0))

    def test_neveljaven_rob_je_nic(self):
        for v in (-1, 81, "10", None, 10.5, True, [10], {"rob": 10}):
            self.assertEqual(link_zaslon.rob_iz(v), 0, repr(v))
        for v in (0, 5, 10, 80):
            self.assertEqual(link_zaslon.rob_iz(v), v)

    def test_screen_start_strogo(self):
        self.assertEqual(link_daljinec._zmoznosti_zaslona({"rob": 10}), {"rob": 10})
        for v in (-1, 81, "10", None, 10.5, True, 0):
            self.assertNotIn("rob", link_daljinec._zmoznosti_zaslona({"rob": v}), repr(v))
        self.assertEqual(link_daljinec._zmoznosti_zaslona({}), {})


class Ukaz(unittest.TestCase):
    def test_libx264(self):
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 30, "8M", None, rob=10)
        self.assertEqual(vf(u), FILTER_10 + ",format=yuv420p")
        self.assertIn("libx264", u)

    def test_vaapi_procesor(self):
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 30, "8M", VAAPI, rob=10)
        self.assertEqual(vf(u), FILTER_10 + ",format=nv12,hwupload")

    def test_vaapi_gpu_brez_pad_vaapi_na_procesor(self):
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 2560, 1440, 30, "8M", VAAPI, gpu=True, rob=10)
        self.assertEqual(vf(u), FILTER_10 + ",format=nv12,hwupload")
        self.assertFalse(link_zaslon.ukaz_pomanjsa_gpu(u))

    def test_barve444_z_robom_ni_mogoc(self):
        """4:4:4 je samo brez pomanjsave; z robom se slika pomanjsa, zato 4:2:0 z okvirjem."""
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 30, "8M", VAAPI, kodek="hevc", barve444=True, rob=10)
        self.assertEqual(vf(u), FILTER_10 + ",format=nv12,hwupload")
        self.assertEqual(u[u.index("-profile:v") + 1], "main")

    def test_pomanjsava_in_rob(self):
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 2560, 1440, 30, "8M", None, rob=10)
        self.assertEqual(vf(u), FILTER_10 + ",format=yuv420p")

    def test_pipewire_vhod(self):
        vhod = ["-f", "rawvideo", "-pix_fmt", "bgr0", "-video_size", "1920x1080", "-i", "pipe:0"]
        u = link_zaslon.ukaz_ffmpeg("", 1920, 1080, 1920, 1080, 30, "8M", VAAPI, vhod=vhod, rob=10)
        self.assertEqual(vf(u), FILTER_10 + ",format=nv12,hwupload")

    def test_brezizgubno(self):
        u = link_zaslon_profil.ukaz_brezizgubno("ffmpeg", ":0", 1920, 1080, 60, (0, 0), rob=10)
        self.assertEqual(vf(u), FILTER_10 + ",format=bgr0")
        self.assertEqual(u[u.index("-video_size") + 1], "1920x1080")

    def test_rob_nic_enak_ukaz(self):
        primeri = [
            dict(vaapi=None), dict(vaapi=VAAPI), dict(vaapi=VAAPI, gpu=True),
            dict(vaapi=VAAPI, kodek="hevc", barve444=True), dict(vaapi=None, izvor=(2560, 1440)),
            dict(vaapi=VAAPI, gpu=True, izvor=(2560, 1440)),
        ]
        for p in primeri:
            p = dict(p)
            izvor = p.pop("izvor", (1920, 1080))
            vaapi = p.pop("vaapi")
            prej = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, izvor[0], izvor[1], 30, "8M", vaapi, **p)
            self.assertEqual(link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, izvor[0], izvor[1], 30, "8M", vaapi,
                                                     rob=0, **p), prej, repr(p))
        self.assertEqual(link_zaslon_profil.ukaz_brezizgubno("ffmpeg", ":0", 1920, 1080, 60, rob=0),
                         link_zaslon_profil.ukaz_brezizgubno("ffmpeg", ":0", 1920, 1080, 60))

    def test_rob_nic_filtri_kot_pred_spremembo(self):
        """Zlati filtri ukaza pred dodajanjem roba (commit 0a954275) - brez roba se nic ne spremeni."""
        u = lambda iz, vaapi, **p: vf(link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, iz[0], iz[1], 30, "8M", vaapi, **p))
        self.assertEqual(u((1920, 1080), None), "format=yuv420p")
        self.assertEqual(u((2560, 1440), None), "scale=1920:1080:flags=lanczos,format=yuv420p")
        self.assertEqual(u((1920, 1080), VAAPI), "format=nv12,hwupload")
        self.assertEqual(u((2560, 1440), VAAPI, gpu=True),
                         "hwupload,scale_vaapi=1920:1080:format=nv12:mode=default")
        self.assertEqual(u((1920, 1080), VAAPI, kodek="hevc", barve444=True), "format=vuyx,hwupload")
        self.assertEqual(vf(link_zaslon_profil.ukaz_brezizgubno("ffmpeg", ":0", 1920, 1080, 60)), "format=bgr0")


class Koordinate(unittest.TestCase):
    def zaslon(self, rob, slika=(1920, 1080), izvor=(1920, 1080)):
        z = link_zaslon.Zaslon.__new__(link_zaslon.Zaslon)
        z._slika = {"width": slika[0], "height": slika[1], "fps": 60}
        z._izvor = izvor
        z._rob = rob
        return z

    def tocka(self, z, x, y):
        d = z._v_zaslon({"vrsta": "tocka", "x": x, "y": y})
        return d["x"], d["y"]

    def test_kot_notranje_slike_je_kot_zaslona(self):
        self.assertEqual(self.tocka(self.zaslon(10), 18, 10), (0, 0))

    def test_sredina(self):
        self.assertEqual(self.tocka(self.zaslon(10), 960, 540), (960, 540))
        # (100-18)*1920/1884 = 83,6 -> 83; (100-10)*1080/1060 = 91,7 -> 91 (brez roba bi bilo 100, 100).
        self.assertEqual(self.tocka(self.zaslon(10), 100, 100), (83, 91))

    def test_okvir_se_omeji_na_rob_zaslona(self):
        z = self.zaslon(10)
        self.assertEqual(self.tocka(z, 0, 0), (0, 0))
        self.assertEqual(self.tocka(z, 5, 600)[0], 0)
        self.assertEqual(self.tocka(z, 1919, 1079), (1919, 1079))
        self.assertEqual(self.tocka(z, 1910, 1075), (1919, 1079))

    def test_rob_z_drugo_velikostjo_izvora(self):
        z = self.zaslon(10, slika=(1920, 1080), izvor=(2560, 1440))
        self.assertEqual(self.tocka(z, 18, 10), (0, 0))
        self.assertEqual(self.tocka(z, 960, 540), (1280, 720))

    def test_brez_roba_kot_prej(self):
        z = self.zaslon(0, slika=(1920, 1080), izvor=(2560, 1440))
        self.assertEqual(self.tocka(z, 960, 540), (1280, 720))
        self.assertEqual(self.tocka(z, 0, 0), (0, 0))
        # Skrajni rob pri pomanjsani sliki: kot pred spremembo (int(1919 * 2560 / 1920) = 2558).
        self.assertEqual(self.tocka(z, 1919.5, 1079.5), (2558, 1438))
        self.assertEqual(self.tocka(z, 5000, 5000), (2558, 1438))
        z = link_zaslon.Zaslon.__new__(link_zaslon.Zaslon)   # star objekt brez _rob
        z._slika, z._izvor = {"width": 1920, "height": 1080}, (1920, 1080)
        self.assertEqual(self.tocka(z, 960, 540), (960, 540))

    def test_kazalec_v_sliki_z_robom(self):
        self.assertEqual(link_kazalec.v_sliki(0, 0, (0, 0), (1920, 1080), (1920, 1080), (18, 10)), (18, 10, True))
        self.assertEqual(link_kazalec.v_sliki(960, 540, (0, 0), (1920, 1080), (1920, 1080), (18, 10)),
                         (960, 540, True))
        self.assertEqual(link_kazalec.v_sliki(1920, 1080, (0, 0), (1920, 1080), (1920, 1080), (18, 10))[:2],
                         (1902, 1070))
        self.assertEqual(link_kazalec.v_sliki(1280, 720, (0, 0), (2560, 1440), (1920, 1080)), (960, 540, True))


class Seja(unittest.TestCase):
    """zacni() na namizju X11: rob gre v ukaz, v vse ponovne sestave in v odgovor; KMS z robom ne."""

    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.z = link_zaslon.Zaslon(tls_mapa=self.mapa.name, ffmpeg="/bin/true", vklopljeno=True, kms=True)
        self.zajeto = []
        zajeto = self.zajeto
        izvirni_get = os.environ.get
        self.popravki = [
            mock.patch.object(link_zaslon.Zaslon, "_streci", lambda self, *a: zajeto.append(a)),
            mock.patch("core.seja_prikaza.je_wayland", return_value=False),
            mock.patch.object(link_zaslon, "_deljeni_monitor", return_value=None),
            mock.patch.object(link_zaslon, "_izvor_zaslona", return_value=(1920, 1080)),
            mock.patch.object(link_zaslon, "vaapi_naprava", return_value=VAAPI),
            mock.patch.object(link_zaslon, "hevc_vaapi_mozen", return_value=False),
            mock.patch.object(link_zaslon, "gpu_lestvica_mozna", return_value=True),
            # Privzeto graficna roba ne zna (stara pot); test_rob_na_graficni ga vklopi.
            mock.patch.object(link_zaslon, "rob_gpu_mozen", return_value=False),
            mock.patch.object(link_zaslon, "privzeti_monitor", return_value=None),
            mock.patch.object(link_zaslon, "kms_na_voljo", return_value=True),
            mock.patch.object(link_zaslon, "kms_monitorji", return_value=1),
            mock.patch.object(link_zaslon, "seja_aktivna", return_value=True),
            # DISPLAY samo za branje v zacni (os.environ ne spreminjamo: AGENTS.md, okolje procesa z nitmi).
            mock.patch.object(os.environ, "get",
                              side_effect=lambda k, d=None: ":0" if k == "DISPLAY" else izvirni_get(k, d)),
        ]
        for p in self.popravki:
            p.start()

    def tearDown(self):
        for p in reversed(self.popravki):
            p.stop()
        self.z.ustavi()
        self.mapa.cleanup()

    def test_rob_v_ukazu_sestavi_profilu_in_odgovoru(self):
        seja = self.z.zacni("tv", rob=10)
        self.assertEqual(seja["rob"], 10)
        posluh, ctx, ukaz, st, sestavi, kms, display = self.zajeto[-1]
        self.assertEqual(vf(ukaz), FILTER_10 + ",format=nv12,hwupload")
        self.assertIsNone(kms, "KMS pomocnik okvirja ne zna: z robom x11grab")
        self.assertIn(FILTER_10, vf(sestavi("h264", link_zaslon.KAKOVOSTI["visoka"])))
        po = self.z._po_profilu({"kodek": "h264rgb"}, link_zaslon.KAKOVOSTI["najvisja"], "h264")
        self.assertIn("pad=", vf(po[0]))
        po = self.z._po_profilu({"kodek": "hevc444"}, link_zaslon.KAKOVOSTI["najvisja"], "h264")
        self.assertIn("pad=", vf(po[0]))
        self.assertEqual(po[4], "420")

    def test_rob_na_graficni(self):
        """Graficna zna procamp+overlay: rob v ukazu, ponovni sestavi in profilu 4:4:4 brez procesorja; brezizgubni
        (libx264rgb, procesor) ostane s pad."""
        with mock.patch.object(link_zaslon, "rob_gpu_mozen", return_value=True):
            seja = self.z.zacni("tv", rob=10)
            self.assertEqual(seja["rob"], 10)
            ukaz, sestavi = self.zajeto[-1][2], self.zajeto[-1][4]
            gpu_filter = link_zaslon.filter_roba_gpu(1920, 1080, 10)
            self.assertEqual(vf(ukaz), gpu_filter)
            self.assertEqual(vf(sestavi("h264", link_zaslon.KAKOVOSTI["visoka"])), gpu_filter)
            po = self.z._po_profilu({"kodek": "hevc444"}, link_zaslon.KAKOVOSTI["najvisja"], "h264")
            self.assertEqual(vf(po[0]), gpu_filter)
            po = self.z._po_profilu({"kodek": "h264rgb"}, link_zaslon.KAKOVOSTI["najvisja"], "h264")
            self.assertIn("pad=", vf(po[0]))

    def test_brez_roba_odgovor_in_ukaz_kot_prej(self):
        seja = self.z.zacni("tv")
        self.assertNotIn("rob", seja)
        ukaz, kms = self.zajeto[-1][2], self.zajeto[-1][5]
        self.assertNotIn("pad=", " ".join(ukaz))
        self.assertIsNotNone(kms)


class ScreenStart(unittest.TestCase):
    def test_rob_gre_v_zacni_samo_veljaven(self):
        klici = []

        class Lazni:
            def na_voljo(self):
                return {"dovoljeno": True, "mozno": True, "ffmpeg": True}

            def zacni(self, *a, **k):
                klici.append(k)
                return {"port": 1, "screen": "desktop"}

        for parametri, pricakovano in (({"rob": 10}, 10), ({"rob": "10"}, None), ({}, None)):
            izidi = []
            link_daljinec.izvedi_control("screen.start", parametri, lambda u: None, izidi.append, zaslon=Lazni())
            self.assertTrue(izidi[-1]["ok"], izidi[-1])
            self.assertEqual(klici[-1].get("rob"), pricakovano)


class RobNaGraficni(unittest.TestCase):
    """Rob na graficni (25. 11. 2026): procamp_vaapi + overlay_vaapi namesto lanczos+pad na procesorju."""

    def test_filter_gpu(self):
        self.assertEqual(
            link_zaslon.filter_roba_gpu(1920, 1080, 10),
            "hwupload,scale_vaapi=1920:1080:format=nv12:mode=default,split[safeer_a][safeer_b];"
            "[safeer_a]procamp_vaapi=b=-100:c=0[safeer_crno];[safeer_b]scale_vaapi=1884:1060:mode=default[safeer_v];"
            "[safeer_crno][safeer_v]overlay_vaapi=x=18:y=10")
        self.assertEqual(link_zaslon.filter_roba_gpu(1920, 1080, 0), "")

    def test_ukaz_z_rob_gpu(self):
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 2560, 1440, 30, "8M", VAAPI, gpu=True, rob=10, rob_gpu=True)
        self.assertEqual(vf(u), link_zaslon.filter_roba_gpu(1920, 1080, 10))
        self.assertTrue(link_zaslon.ukaz_pomanjsa_gpu(u))
        self.assertIn("h264_vaapi", u)

    def test_rob_gpu_brez_gpu_ali_vaapi_na_procesor(self):
        for kw in (dict(vaapi=VAAPI, gpu=False), dict(vaapi=None, gpu=True)):
            u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 30, "8M", kw["vaapi"], gpu=kw["gpu"],
                                        rob=10, rob_gpu=True)
            self.assertNotIn("overlay_vaapi", vf(u))

    def test_rob_0_z_rob_gpu_kot_prej(self):
        a = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 2560, 1440, 30, "8M", VAAPI, gpu=True)
        b = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 2560, 1440, 30, "8M", VAAPI, gpu=True, rob=0, rob_gpu=True)
        self.assertEqual(a, b)

    def test_rob_gpu_mozen_samo_z_gpu(self):
        with mock.patch.object(link_zaslon, "gpu_lestvica_mozna", return_value=False), \
                mock.patch.object(link_zaslon.subprocess, "run") as run:
            self.assertFalse(link_zaslon.rob_gpu_mozen("/x/ffmpeg", VAAPI))
            run.assert_not_called()

    def test_rob_gpu_mozen_po_izhodni_kodi_in_zapomni(self):
        link_zaslon._ROB_GPU.clear()
        try:
            with mock.patch.object(link_zaslon, "gpu_lestvica_mozna", return_value=True), \
                    mock.patch.object(link_zaslon.subprocess, "run",
                                      return_value=mock.Mock(returncode=1)) as run:
                self.assertFalse(link_zaslon.rob_gpu_mozen("/x/ffmpeg", VAAPI))
                self.assertFalse(link_zaslon.rob_gpu_mozen("/x/ffmpeg", VAAPI))
                self.assertEqual(run.call_count, 1)
                self.assertIn("overlay_vaapi", " ".join(run.call_args[0][0]))
        finally:
            link_zaslon._ROB_GPU.clear()


if __name__ == "__main__":
    unittest.main()
