"""Sedmi neodvisni pregled, naloga 6 (25. 10. 2026): domaca mapa za ozji krog in slicice naprav - vsak preizkus brez
svojega popravka pade.

Pravilo lastnika (25. 10. 2026 10:49): domaco mapo (brez skritih map in skrivnosti) vidi samo naprava v ozjem krogu
(ena izrecna privolitev); umik jo takoj zapre.
"""
import io
import os
import shutil
import struct
import tempfile
import threading
import time
import unittest
from unittest import mock

import pytest

from core import link_daljinec, link_datoteke, link_dostop, link_slicice_naprav

OZJI, ZUNANJI = "n-aaaaaaaaaaaaaaaa", "n-bbbbbbbbbbbbbbbb"


class _Dom(unittest.TestCase):
    """Zacasna domaca mapa z vsebino, kot jo ima uporabnik."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dom = os.path.realpath(self._tmp.name)
        for pot, vsebina in (("Dokumenti/pismo.txt", "a"), ("Slike/morje.jpg", "b"), ("bin/.gitkeep", ""),
                             ("Dokumenti/opomba.txt", "-----BEGIN OPENSSH PRIVATE KEY-----\nb3Blbn\n"),
                             ("Dokumenti/baza.dat", "\x03\xd9\xa2\x9a"),
                             ("Dokumenti/aws.ini", "[default]\naws_secret_access_key = x\n"),
                             ("Dokumenti/id_rsa.bak", "k"), ("Dokumenti/github_rsa", "k"),
                             ("Dokumenti/Chrome Passwords.csv", "url,user,pass"), ("Dokumenti/prod.env", "TOKEN=1"),
                             ("snap/chromium/common/chromium/Default/Login Data", "g"),
                             ("snap/chromium/common/izvoz.txt", "x")):
            cela = os.path.join(self.dom, pot)
            os.makedirs(os.path.dirname(cela), exist_ok=True)
            with open(cela, "w", encoding="latin-1") as d:
                d.write(vsebina)
        p = mock.patch.dict(os.environ, {"HOME": self.dom})
        p.start()
        self.addCleanup(p.stop)


class U1SamoOzjiKrog(_Dom):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(link_datoteke, "_v_ozjem_krogu", lambda n: n == OZJI)
        p.start()
        self.addCleanup(p.stop)
        self.d = link_datoteke.Datoteke([], tls_mapa=os.path.join(self.dom, ".tls"), dom=True)
        self.addCleanup(self.d.ustavi)

    def test_seznam_domace_mape_samo_ozjemu_krogu(self):
        """»d« iz starejse razlicice (izbrane mape) ne odpre domace mape: ta je samo za ozji krog."""
        with mock.patch.object(self.d, "streznik_za", return_value={}):
            self.assertEqual(self.d.seznam("", ZUNANJI)["shared"], False)
            self.assertEqual(self.d.seznam("dom:", ZUNANJI)["items"], [])
            self.assertIn("dom:", [v["id"] for v in self.d.seznam("", OZJI)["items"]])
            self.d.nastavi([os.path.join(self.dom, "Slike")])        # izbrana mapa: to naprava z »d« vidi
            self.assertEqual([v["id"] for v in self.d.seznam("", ZUNANJI)["items"]], ["share:0:"])
            with self.assertRaises(FileNotFoundError):
                self.d.seznam("dom:", ZUNANJI)
            self.assertEqual(len(self.d.seznam("dom:", OZJI)["items"]), 3)

    def test_zeton_za_domaco_mapo_samo_ozjemu_krogu(self):
        s = self.d.streznik
        s.sme = lambda naprava, zmoznost: True
        s.umaknjena = lambda n: False
        z_zunanji, z_ozji = s.zeton_za(ZUNANJI), s.zeton_za(OZJI)
        self.assertFalse(s.zeton_velja(z_zunanji, zmoznost="d", oznaka="dom:Slike/morje.jpg"))
        self.assertTrue(s.zeton_velja(z_ozji, zmoznost="d", oznaka="dom:Slike/morje.jpg"))
        s.dovoli_izrecno(ZUNANJI, "dom:Slike/morje.jpg")       # uporabnik ji je to datoteko sam poslal
        self.assertTrue(s.zeton_velja(z_zunanji, zmoznost="d", oznaka="dom:Slike/morje.jpg"))

    def test_urejanje_domace_mape_samo_ozjemu_krogu(self):
        koda, odgovor = self.d.streznik.uredi("dom:Dokumenti/pismo.txt", {"op": "rename", "name": "b.txt"},
                                              naprava=ZUNANJI)
        self.assertEqual((koda, odgovor["napaka"]), (404, "ni_datoteke"))
        self.assertTrue(os.path.exists(os.path.join(self.dom, "Dokumenti/pismo.txt")))

    def test_ukazi_z_oznako_domace_mape(self):
        self.d.teamwork = mock.Mock()
        for dejanje in ("files.session", "files.open", "files.open_locen"):
            izidi = []
            link_daljinec.izvedi_control(dejanje, {"id": "dom:Dokumenti/pismo.txt"}, lambda u: None, izidi.append,
                                         datoteke=self.d, posiljatelj=ZUNANJI)
            self.assertEqual((izidi[-1]["ok"], izidi[-1].get("code")), (False, "ni_datoteke"), dejanje)
        self.d.teamwork.prijava.assert_not_called()


@pytest.mark.pravi_dostop
class U1OzjiKrogVLinkDostop(unittest.TestCase):
    def setUp(self):
        from tests.test_link_dostop import _Osnova
        self.osnova = _Osnova("run")
        self.osnova.setUp()
        self.addCleanup(self.osnova.doCleanups)

    def test_samo_d_ni_ozji_krog(self):
        link_dostop.nastavi(ZUNANJI, "dpv")
        self.assertFalse(link_dostop.v_ozjem_krogu(ZUNANJI))
        link_dostop.nastavi_ozji_krog(ZUNANJI, "p")
        self.assertTrue(link_dostop.v_ozjem_krogu(ZUNANJI))
        link_dostop.nastavi(ZUNANJI, "")
        self.assertFalse(link_dostop.v_ozjem_krogu(ZUNANJI))


class U2Skrivnosti(_Dom):
    def test_skrivnosti_po_imenu_in_vsebini_ter_profili_snap(self):
        m = link_datoteke.DeljeneMape([], dom=True)
        for oznaka in ("dom:Dokumenti/opomba.txt", "dom:Dokumenti/baza.dat", "dom:Dokumenti/aws.ini",
                       "dom:Dokumenti/id_rsa.bak", "dom:Dokumenti/github_rsa", "dom:Dokumenti/Chrome Passwords.csv",
                       "dom:Dokumenti/prod.env", "dom:snap", "dom:snap/chromium/common/chromium/Default/Login Data",
                       "dom:snap/chromium/common/izvoz.txt"):
            self.assertIsNone(m.razresi(oznaka), oznaka)
        self.assertEqual([v["name"] for v in m.seznam("dom:Dokumenti")], ["pismo.txt"])
        self.assertNotIn("snap", [v["name"] for v in m.seznam("dom:")])

    def test_izbrana_deljena_mapa_tudi_brez_skrivnosti(self):
        """U13: deljena mapa (share:) ne da skrivnosti - enako kot domaca mapa."""
        m = link_datoteke.DeljeneMape([os.path.join(self.dom, "Dokumenti")])
        self.assertIsNone(m.razresi("share:0:id_rsa.bak"))
        self.assertIsNone(m.razresi("share:0:opomba.txt"))
        self.assertIsNotNone(m.razresi("share:0:pismo.txt"))
        self.assertEqual([v["name"] for v in m.seznam("share:0:")], ["pismo.txt"])


class U3VesDisk(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.disk = os.path.join(os.path.realpath(self._tmp.name), "Windows")
        for pot in ("Users/ana/AppData/Local/Google/Chrome/User Data/Default/Login Data", "Users/ana/NTUSER.DAT",
                    "Windows/System32/config/SAM", "pagefile.sys", "Users/ana/Documents/pismo.txt", "krb5cc_1000"):
            cela = os.path.join(self.disk, pot)
            os.makedirs(os.path.dirname(cela), exist_ok=True)
            with open(cela, "w", encoding="utf-8") as d:
                d.write("x")

    def test_zasebni_deli_windows_in_sistem(self):
        m = link_datoteke.DeljeneMape([], ves_disk=True)
        for rel in ("Users/ana/AppData", "Users/ana/AppData/Local/Google/Chrome/User Data/Default/Login Data",
                    "Users/ana/NTUSER.DAT", "Windows/System32/config/SAM", "pagefile.sys", "krb5cc_1000"):
            self.assertIsNone(m.razresi("disk:" + os.path.join(self.disk, rel)), rel)
        self.assertIsNotNone(m.razresi("disk:" + os.path.join(self.disk, "Users/ana/Documents/pismo.txt")))
        self.assertEqual([v["name"] for v in m.seznam("disk:" + os.path.join(self.disk, "Users/ana"))], ["Documents"])
        if os.path.isdir("/var"):
            self.assertIsNone(m.razresi("disk:/var"), "posta, dnevniki in podatki storitev")
            self.assertNotIn("var", [v["name"] for v in m.seznam("disk:/")])


def _slika(oblika: str, velikost=(64, 48)) -> bytes:
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", velikost).save(b, oblika)
    return b.getvalue()


class U4U8Slicice(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mapa, True)

    def test_eps_v_jpg_ne_pride_do_ghostscripta(self):
        """Pillow format ugane po vsebini: slika.jpg z vsebino EPS se ne sme odpreti z EpsImagePlugin (Ghostscript)."""
        from PIL import EpsImagePlugin
        pot = os.path.join(self.mapa, "racun.jpg")
        with open(pot, "wb") as d:
            d.write(b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\nshowpage\n")
        odprto = []

        def _open(self_):
            odprto.append(1)
            raise SyntaxError("preizkus: EPS se ne odpira")
        with mock.patch.object(EpsImagePlugin.EpsImageFile, "_open", _open):
            self.assertIsNone(link_datoteke._slicica_slike(pot, 256))
        self.assertEqual(odprto, [])

    def test_png_meja_brez_draft_in_najprej_pomanjsanje(self):
        vrstni_red = []

        class Lazna:
            def __init__(self, velikost, oblika):
                self.size, self.format, self.mode = velikost, oblika, "RGB"

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def draft(self, *_a):
                pass

            def thumbnail(self, *_a):
                vrstni_red.append("pomanjsaj")

            def save(self, izhod, *_a, **_k):
                izhod.write(b"\xff\xd8x")
        velikost = [(6000, 5000)]          # 30 MP PNG: nad mejo za slike brez pomanjsanega dekodiranja
        with mock.patch("PIL.Image.open", lambda pot, formats=None: Lazna(velikost[0], "PNG")), \
                mock.patch("PIL.ImageOps.exif_transpose", lambda im: vrstni_red.append("obrni") or im):
            self.assertIsNone(link_datoteke._slicica_slike("/x/velika.png", 256))
            velikost[0] = (4000, 3000)
            self.assertTrue(link_datoteke._slicica_slike("/x/manjsa.png", 256))
        self.assertEqual(vrstni_red, ["pomanjsaj", "obrni"], "obracanje po EXIF sele na majhni sliki")


class U14Video(unittest.TestCase):
    def test_samo_protokol_file_in_rok_za_mesto(self):
        ukazi = []

        def run(ukaz, **_k):
            ukazi.append(list(ukaz))
            import subprocess
            return subprocess.CompletedProcess(ukaz, 0, b"\xff\xd8" + b"x" * 300, b"")
        with mock.patch.object(link_datoteke.shutil, "which", return_value="/usr/bin/ffmpeg"), \
                mock.patch.object(link_datoteke.subprocess, "run", run):
            self.assertTrue(link_datoteke._slicica_videa("/x/film.mp4", 256))
        self.assertIn("-protocol_whitelist", ukazi[0])
        self.assertEqual(ukazi[0][ukazi[0].index("-protocol_whitelist") + 1], "file")
        self.assertLess(ukazi[0].index("-protocol_whitelist"), ukazi[0].index("-i"))

    def test_brez_mesta_ne_caka_brez_konca(self):
        zasedeno = 0
        while link_datoteke._SLICICE_VIDEA.acquire(blocking=False):
            zasedeno += 1
        try:
            izid = []
            with mock.patch.object(link_datoteke, "CAKAJ_NA_SLICICO_S", 0.2), \
                    mock.patch.object(link_datoteke.shutil, "which", return_value="/usr/bin/ffmpeg"):
                nit = threading.Thread(target=lambda: izid.append(link_datoteke._slicica_videa("/x/a.mp4", 256)),
                                       daemon=True)
                nit.start()
                nit.join(3)
            self.assertFalse(nit.is_alive(), "zahteva caka na mesto najvec CAKAJ_NA_SLICICO_S")
            self.assertEqual(izid, [None])
        finally:
            for _ in range(zasedeno):
                link_datoteke._SLICICE_VIDEA.release()


class U5Urejanje(_Dom):
    def setUp(self):
        super().setUp()
        self.s = link_datoteke.StreznikDatotek(link_datoteke.DeljeneMape([], dom=True), tls_mapa=os.path.join(self.dom, ".tls"))
        self.s.v_ozjem_krogu = lambda n: True

    def test_ne_naredi_zagonske_datoteke_ali_skrivnosti(self):
        for ime in (".bash_profile", ".xprofile", "id_rsa", ".config"):
            koda, _ = self.s.uredi("dom:Dokumenti/pismo.txt", {"op": "rename", "name": ime}, naprava=OZJI)
            self.assertEqual(koda, 403, ime)
        for mapa in ("dom:", "dom:bin"):
            koda, _ = self.s.uredi("dom:Dokumenti/pismo.txt", {"op": "move", "folder": mapa}, naprava=OZJI)
            self.assertEqual(koda, 403, mapa)
        self.assertTrue(os.path.exists(os.path.join(self.dom, "Dokumenti/pismo.txt")))

    def test_mape_namizja_ostanejo(self):
        for zahteva in ({"op": "rename", "name": "Stari"}, {"op": "move", "folder": "dom:Slike"}):
            koda, _ = self.s.uredi("dom:Dokumenti", zahteva, naprava=OZJI)
            self.assertEqual(koda, 403, zahteva)
        koda, _ = self.s.uredi("dom:Dokumenti/pismo.txt", {"op": "rename", "name": "pismo-staro.txt"}, naprava=OZJI)
        self.assertEqual(koda, 200, "vsebino map ureja naprej")


def _png_glava(sirina: int, visina: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", sirina, visina) + b"\x08\x02\x00\x00\x00"


class U6U7U15SlicicePrejem(unittest.TestCase):
    STREZNIK = {"base_url": "https://192.168.0.20:8443", "fp": "ab" * 32, "token": "z"}

    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mapa, True)

    def test_bomba_dekompresije_se_ne_shrani(self):
        self.assertEqual(link_slicice_naprav.ustrezna_slicica(_png_glava(30000, 30000) + b"x" * 100), "")
        self.assertEqual(link_slicice_naprav.ustrezna_slicica(_png_glava(256, 192) + b"x" * 100), "png")
        s = link_slicice_naprav.Slicice(self.mapa, lambda st, o, r: _png_glava(30000, 30000) + b"x" * 100)
        self.assertEqual(s.dobi("n", self.STREZNIK, [{"id": "a", "size": 1}]), {})

    def test_pocasna_naprava_ne_zadrzi_klicatelja(self):
        def pocasi(st, o, r):
            time.sleep(2.0)
            return _png_glava(64, 64)
        s = link_slicice_naprav.Slicice(self.mapa, pocasi)
        zacetek = time.monotonic()
        s.dobi("n", self.STREZNIK, [{"id": "a", "size": 1}, {"id": "b", "size": 1}, {"id": "c", "size": 1}], rok=0.3)
        self.assertLess(time.monotonic() - zacetek, 1.5)

    def test_skupen_rok_prenosa(self):
        """Naprava, ki posilja po malem, ne raztegne prenosa cez rok (rok ni vec samo za vsak recv)."""
        class Odgovor:
            status = 200

            def read(self, _n):
                time.sleep(0.2)
                return b"x"

        class Povezava:
            sock = None

            def __init__(self, *_a, **_k):
                pass

            def request(self, *_a, **_k):
                pass

            def getresponse(self):
                return Odgovor()

            def close(self):
                pass
        with mock.patch("core.link_tls._PripetaHttps", Povezava):
            zacetek = time.monotonic()
            self.assertIsNone(link_slicice_naprav.prenesi_https(self.STREZNIK, "a", rok_s=0.6))
            self.assertLess(time.monotonic() - zacetek, 1.5)

    def test_napaka_zapisa_ne_pride_do_klicatelja_in_ciscenje_pusti_tuje_part(self):
        s = link_slicice_naprav.Slicice(self.mapa, lambda st, o, r: _png_glava(64, 64), najvec=1)
        with mock.patch.object(s, "_shrani", side_effect=OSError(28, "No space left on device")):
            self.assertEqual(s.dobi("n", self.STREZNIK, [{"id": "a", "size": 1}]), {})
        os.makedirs(os.path.join(self.mapa, "ab"))
        tuja = os.path.join(self.mapa, "ab", "x.part")
        with open(tuja, "wb") as d:
            d.write(b"y" * 100)
        s._pocisti()
        self.assertTrue(os.path.exists(tuja), "zapis druge niti ostane")


class U9SprotniTok(unittest.TestCase):
    """Naloga 5, U9: sprotno pretvorjen tok (/live/) tece dolgo - odvzem predvajalnika ga konca, ko ze tece."""

    def test_tok_se_konca_ob_odvzemu(self):
        from core import link_sprotno
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa, True)
        pot = os.path.join(mapa, "tok.mp4")
        with open(pot, "wb") as d:
            d.write(b"x" * 1000)
        sprotno = link_sprotno.Sprotno.__new__(link_sprotno.Sprotno)
        t = link_sprotno.Tok("film", pot)
        sprotno.tokovi = {t.id: t}
        zapisano = []
        obravnava = mock.Mock(wfile=mock.Mock(write=lambda b: zapisano.append(bytes(b))))
        obravnava.safeer_se_velja = lambda: False             # naprava je predvajalnik pravkar izgubila
        nit = threading.Thread(target=sprotno.postrezi, args=(obravnava, t.id, False), daemon=True)
        nit.start()
        nit.join(3)
        t.koncano = True                                       # pospravi nit tudi, ce preizkus pade
        self.assertFalse(nit.is_alive(), "tok ne caka novih podatkov za napravo brez dostopa")
        self.assertEqual(b"".join(zapisano), b"0\r\n\r\n")

    def test_streznik_datotek_da_tokovi_preverbo(self):
        s = link_datoteke.StreznikDatotek(mock.Mock(), tls_mapa=tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, s.tls_mapa, True)
        s.umaknjena = lambda n: False
        dostop = {"v": True}
        s.sme = lambda naprava, zmoznost: dostop["v"]
        zeton = s.zeton_za("tv")
        sprotno = mock.Mock()
        s.sprotno = sprotno
        obravnava = mock.Mock(headers={"X-Safeer-Token": zeton})
        with mock.patch.object(link_datoteke, "PREVERI_MED_POSILJANJEM_S", 0.0):
            link_datoteke.postrezi_pot(obravnava, s, "/live/abc", False)
            se_velja = obravnava.safeer_se_velja
            self.assertTrue(se_velja())
            dostop["v"] = False
            self.assertFalse(se_velja())
        sprotno.postrezi.assert_called_once()


class U10ImeDoma(_Dom):
    def test_ime_domace_mape_ni_uporabnisko_ime(self):
        m = link_datoteke.DeljeneMape([], dom=True)
        self.assertNotEqual(m.koren()[0]["name"], os.path.basename(self.dom))
        m = link_datoteke.DeljeneMape([], ves_disk=True)
        self.assertNotIn(os.path.basename(self.dom), [v["name"] for v in m.koren()])


if __name__ == "__main__":
    unittest.main()
