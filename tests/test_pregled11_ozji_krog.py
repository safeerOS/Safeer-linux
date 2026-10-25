"""Neodvisni pregled 11 (25. 10. 2026) popravkov pregledov 5 in 6: vsak preizkus brez svojega popravka pade."""
import base64
import json
import os
import shutil
import stat
import tempfile
import threading
import time
import unittest
from unittest import mock

import pytest

from core import link_daljinec, link_datoteke, link_dostop, link_krog, link_slicice_naprav, link_teamwork, link_zaslon
from tests.test_link_dostop import A, B, _Osnova

pytestmark = pytest.mark.pravi_dostop


class N1Migracija(_Osnova):
    MEJA = link_dostop.MEJA_PODEDOVANJA
    clani = ({"id": "jaz", "kljuc": "KJAZ", "dodano": MEJA - 9000}, {"id": "a", "kljuc": "KA", "dodano": MEJA - 100},
             {"id": "b", "kljuc": "KB", "dodano": MEJA + 60})

    def _star_zapis(self, naprave):
        pot = link_dostop._pot()
        with open(pot, "w", encoding="utf-8") as d:
            json.dump({"v": 1, "podedovano_ob": self.MEJA + 100, "naprave": naprave}, d)
        link_dostop._za_preizkus(pot)
        return pot

    def test_podedovan_dpvz_izgubi_ozji_krog_enkrat(self):
        """Zapis prejsnje razlicice (dedovanje je dalo dpvz): podedovana naprava ozjega kroga nima brez privolitve;
        naprava, dodana po meji, ki ji je uporabnik sam dal vse, ostane."""
        pot = self._star_zapis({A: "dpvz", B: "dpvz"})
        self.assertEqual(link_dostop.zmoznosti(A), {"p", "v"})
        self.assertFalse(link_dostop.v_ozjem_krogu(A))
        self.assertEqual(link_dostop.zmoznosti(B), set("dpvz"))
        with open(pot, encoding="utf-8") as d:
            self.assertEqual(json.load(d)["naprave"][A], "pv")
        self.assertTrue(os.path.exists(pot + ".podedovano"))
        link_dostop.nastavi_ozji_krog(A, "pv")           # uporabnik odpre ozji krog z eno privolitvijo
        link_dostop._za_preizkus(pot)
        self.assertEqual(link_dostop.zmoznosti(A), set("dpvz"), "migracija je enkratna")

    def test_spremenjen_zapis_ostane(self):
        self._star_zapis({A: "dv"})
        self.assertEqual(link_dostop.zmoznosti(A), {"d", "v"})

    def test_ce_zapisa_ni_mogoce_spremeniti_velja_v_programu(self):
        self._star_zapis({A: "dpvz"})
        with mock.patch.object(link_dostop, "_na_disk", side_effect=OSError(28, "No space left on device")):
            self.assertEqual(link_dostop.zmoznosti(A), {"p", "v"})


class N2OdvzemBrezDatotek(_Osnova):
    def test_odvzem_programov_ne_prekine_datotek(self):
        from core import safeer_link
        link = safeer_link.SafeerLink.__new__(safeer_link.SafeerLink)
        link.zaslon, link.datoteke = mock.Mock(), mock.Mock()
        link._v_ozadju = lambda f: f()
        link_dostop.ob_odvzemu(link._ob_odvzemu_dostopa)
        link_dostop.nastavi_ozji_krog(B, "dpvz")
        with mock.patch.object(safeer_link.GLib, "idle_add"):
            link_dostop.nastavi_ozji_krog(B, "dvz")          # samo programi stran
            link.datoteke.preklici_napravo.assert_not_called()
            link.zaslon.preveri_dostop.assert_called()
            link_dostop.nastavi(B, "")
        link.datoteke.preklici_napravo.assert_called_once_with(B)


class _Krog(_Osnova):
    def setUp(self):
        super().setUp()
        self.kljuc = base64.b64encode(b"\x30" + bytes(range(90))).decode("ascii")
        self.jedro = link_krog.id_iz_kljuca(self.kljuc)
        self.k = link_krog.Krog(None)
        for cilj, ime, vrednost in ((link_krog, "_krog", self.k), (link_krog.Krog, "_smo_mi", lambda s, i: False),
                                    (link_dostop, "_krog", lambda: self.k),
                                    (link_dostop, "_id_iz_kljuca", link_krog.id_iz_kljuca)):
            p = mock.patch.object(cilj, ime, vrednost)
            p.start()
            self.addCleanup(p.stop)
        self.assertTrue(self.k.dodaj(self.jedro, self.kljuc, "Telefon", "android", "n-0000000000000001",
                                     dodano=time.time() - 60))


class N3UmikSePonovi(_Krog):
    def test_neuspel_zapis_umika_ne_pusti_dostopa(self):
        link_dostop.nastavi_ozji_krog(self.jedro, "dpvz")
        with mock.patch.object(link_dostop, "_na_disk", side_effect=OSError(28, "No space left on device")):
            self.k.umakni(self.jedro, "n-0000000000000001")
            self.assertEqual(link_dostop.zmoznosti(self.jedro), set(), "v tem programu umik velja takoj")
        link_dostop._ponovi_v_ozadju()                  # ponovni poskus zapisa (casovnik) uspe
        self.assertEqual(link_dostop.zmoznosti(self.jedro), set())
        with open(link_dostop._pot(), encoding="utf-8") as d:
            self.assertEqual(json.load(d)["naprave"].get(self.jedro, ""), "")

    def test_ponovna_seznanitev_vzame_ostanek(self):
        """Ostanek vnosa (umik ni bil zapisan, program se je med tem znova zagnal): ponovna seznanitev ga vzame."""
        self.k.umakni(self.jedro, "n-0000000000000001")
        pot = link_dostop._pot()
        with open(pot, encoding="utf-8") as d:
            zapis = json.load(d)
        zapis["naprave"][self.jedro] = "dpvz"
        with open(pot, "w", encoding="utf-8") as d:
            json.dump(zapis, d)
        link_dostop._za_preizkus(pot)
        self.assertTrue(self.k.dodaj(self.jedro, self.kljuc, "Telefon", "android", "n-0000000000000001"))
        self.assertEqual(link_dostop.zmoznosti(self.jedro), set())


class N15EnZapis(_Krog):
    def test_odjava_z_vec_napravami_je_en_zapis(self):
        jedra = ["n-%016x" % (0x5000 + i) for i in range(4)]
        for j in jedra:
            link_dostop.nastavi(j, "dz")
        pravi, klici = link_dostop._spremeni, []

        def stej(*a, **k):
            klici.append(1)
            return pravi(*a, **k)
        with mock.patch.object(link_dostop, "_spremeni", stej):
            link_dostop.ob_umiku_iz_kroga(jedra)
        self.assertEqual(len(klici), 1)
        self.assertTrue(all(link_dostop.zmoznosti(j) == set() for j in jedra))


class N16Zaklepi(unittest.TestCase):
    def test_umik_pod_modulskim_zaklepom_kroga_gre_v_svojo_nit(self):
        niti = []
        with mock.patch("core.link_dostop.ob_umiku_iz_kroga", lambda j: niti.append(threading.current_thread())):
            with link_krog._zaklep:
                link_krog._po_umiku({"n-0123456789abcdef"})
            for _ in range(100):
                if niti:
                    break
                time.sleep(0.02)
        self.assertEqual(len(niti), 1)
        self.assertIsNot(niti[0], threading.current_thread())

    def test_teamwork_pripada_brez_zaklepa_seje(self):
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa, True)
        tw = link_teamwork.Teamwork(lambda o: "", lambda i: i, mock.Mock(), mock.Mock(), lambda: [], mapa=mapa,
                                    procesi=lambda: set())
        s = link_teamwork._Seja("x", os.path.join(mapa, "a.txt"))
        s.udelezenci = {B: {"ime": "B", "odprto": True, "cas": time.time()}}
        tw._seje["x"] = s
        prosto = []

        def pripada(_i):
            izid = []

            def poskusi():
                dobil = s.zaklep.acquire(timeout=0.3)
                izid.append(dobil)
                if dobil:
                    s.zaklep.release()
            t = threading.Thread(target=poskusi)
            t.start()
            t.join()
            prosto.append(izid[0])
            return True
        self.assertEqual(tw.odjavi_napravo(pripada), 1)
        self.assertEqual(prosto, [True], "pripada() (link_dostop, krog) se klice brez zaklepa seje")


class N17PreverbaNaDisku(_Osnova):
    def test_star_program_povozi_odvzem_napaka(self):
        link_dostop.nastavi(B, "dz")
        pot = link_dostop._pot()
        pravi = link_dostop._fsync_mape

        def star_program(mapa):
            pravi(mapa)
            try:
                with open(pot, encoding="utf-8") as d:
                    zapis = json.load(d)
            except (OSError, ValueError):
                return
            if zapis.get("naprave", {}).get(B) == "":
                zapis["naprave"][B] = "dz"           # starejsi program pise brez preverbe staro stanje
                with open(pot + ".star", "w", encoding="utf-8") as d:
                    json.dump(zapis, d)
                os.replace(pot + ".star", pot)
        with mock.patch.object(link_dostop, "_fsync_mape", star_program):
            self.assertFalse(link_dostop.nastavi(B, ""), "uporabnik vidi, da odvzem ni zapisan")


class _Dom(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dom = os.path.realpath(self._tmp.name)
        for pot, vsebina in (("Dokumenti/pismo.txt", "a"), ("Dokumenti/zagon.desktop", "[Desktop Entry]\n"),
                             ("orodja/bin/x", ""), ("skripte/y", ""), ("Namizje/.gitkeep", "")):
            cela = os.path.join(self.dom, pot)
            os.makedirs(os.path.dirname(cela), exist_ok=True)
            with open(cela, "w", encoding="utf-8") as d:
                d.write(vsebina)
        os.symlink(os.path.join(self.dom, "orodja", "bin"), os.path.join(self.dom, "bin"))
        p = mock.patch.dict(os.environ, {"HOME": self.dom,
                                         "PATH": os.path.join(self.dom, "skripte") + os.pathsep + "/usr/bin:/bin"})
        p.start()
        self.addCleanup(p.stop)
        self.s = link_datoteke.StreznikDatotek(link_datoteke.DeljeneMape([], dom=True),
                                               tls_mapa=os.path.join(self.dom, ".tls"))
        self.s.v_ozjem_krogu = lambda n: n == A


class N11N12Urejanje(_Dom):
    def test_zagonske_mape_tudi_prek_povezave_in_path(self):
        for mapa in ("dom:orodja/bin", "dom:skripte"):
            koda, _ = self.s.uredi("dom:Dokumenti/pismo.txt", {"op": "move", "folder": mapa}, naprava=A)
            self.assertEqual(koda, 403, mapa)
        koda, _ = self.s.uredi("dom:Dokumenti/zagon.desktop", {"op": "move", "folder": "dom:Namizje"}, naprava=A)
        self.assertEqual(koda, 403, "zaganjalnik na namizje")

    def test_neznana_naprava_ne_ureja_domace_mape(self):
        koda, _ = self.s.uredi("dom:Dokumenti/pismo.txt", {"op": "rename", "name": "b.txt"}, naprava=None)
        self.assertEqual(koda, 404)
        self.assertTrue(os.path.exists(os.path.join(self.dom, "Dokumenti/pismo.txt")))


class V8VesDiskSamoOzjemu(_Dom):
    def test_ves_disk_ne_obide_pravila_domace_mape(self):
        """Domaca mapa v »vsem disku« samo ozjemu krogu (zunanje diske vidi vsak - pregled 17, M3)."""
        d = link_datoteke.Datoteke([], tls_mapa=os.path.join(self.dom, ".tls2"), ves_disk=True)
        self.addCleanup(d.ustavi)
        with mock.patch.object(link_datoteke, "_v_ozjem_krogu", lambda n: n == A), \
                mock.patch.object(d, "streznik_za", return_value={}):
            self.assertNotIn("disk:" + self.dom, [v["id"] for v in d.seznam("", B)["items"]])
            self.assertIn("disk:" + self.dom, [v["id"] for v in d.seznam("", A)["items"]])
        s = d.streznik
        s.sme, s.umaknjena, s.v_ozjem_krogu = (lambda n, z: True), (lambda n: False), (lambda n: n == A)
        self.assertFalse(s.zeton_velja(s.zeton_za(B), zmoznost="d", oznaka="disk:" + self.dom + "/Dokumenti/pismo.txt"))


class N5N8N9N10Skrivnosti(unittest.TestCase):
    def setUp(self):
        self.mapa = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.mapa, True)

    def _datoteka(self, ime, vsebina=b"x"):
        pot = os.path.join(self.mapa, ime)
        os.makedirs(os.path.dirname(pot), exist_ok=True)
        with open(pot, "wb") as d:
            d.write(vsebina)
        return pot

    def test_seznam_ne_bere_varnih_in_velikih(self):
        for ime, vsebina in (("a.jpg", b"\xff\xd8" + b"x" * 10), ("velik.bin", b"y" * 200_000), ("opomba.txt", b"z")):
            self._datoteka(ime, vsebina)
        m = link_datoteke.DeljeneMape([self.mapa])
        odprte = []
        pravi_os_open, pravi_open = os.open, open

        def os_open(pot, *a, **k):
            if str(pot).startswith(self.mapa):
                odprte.append(pot)
            return pravi_os_open(pot, *a, **k)

        def b_open(pot, *a, **k):
            if str(pot).startswith(self.mapa):
                odprte.append(pot)
            return pravi_open(pot, *a, **k)
        getattr(link_datoteke, "_vsebina_spomin", {}).clear()
        with mock.patch.object(link_datoteke.os, "open", os_open), mock.patch("builtins.open", b_open):
            imena = [v["name"] for v in m.seznam("share:0:")]
        self.assertEqual(sorted(imena), ["a.jpg", "opomba.txt", "velik.bin"])
        self.assertEqual([os.path.basename(p) for p in odprte], ["opomba.txt"], "fotografij in velikih ne beremo")

    def test_brez_lazno_pozitivnih(self):
        imena = ("vaje_dsa.pdf", "izpit_dsa_2024.pdf", "id_dsa_porocilo.pdf", "naloga_rsa.docx", "test_ecdsa.py",
                 "predstavitev.key", "javni.asc")
        for ime in imena:
            self._datoteka(ime, b"navadna vsebina")
        self._datoteka("Recepti/Cookies", b"Piskoti s cokolado")
        self._datoteka("projekt_rsa/opis.txt", b"projekt")
        m = link_datoteke.DeljeneMape([self.mapa])
        for ime in imena:
            self.assertIsNotNone(m.razresi("share:0:" + ime), ime)
        self.assertIsNotNone(m.razresi("share:0:Recepti/Cookies"))
        self.assertIn("projekt_rsa", [v["name"] for v in m.seznam("share:0:")], "mapa ni skrivnost po imenu")
        self.assertIsNotNone(m.razresi("share:0:projekt_rsa/opis.txt"))

    def test_brez_lazno_negativnih(self):
        self._datoteka("Default/Cookies", b"SQLite format 3\x00" + b"\x00" * 100)
        self._datoteka("Default/Login Data-journal", b"x")
        self._datoteka("kube.yaml", b"users:\n- user:\n    client-key-data: QUJD\n")
        self._datoteka("orodje.bin", b"\xfe\xed\xfe\xed\x00\x00\x00\x02")
        self._datoteka("veriga.crt", b"-----BEGIN CERTIFICATE-----\n" + b"A" * 6000 + b"\n-----END CERTIFICATE-----\n"
                       b"-----BEGIN PRIVATE KEY-----\nMII\n-----END PRIVATE KEY-----\n")
        self._datoteka("Gesla.docx", b"PK")
        m = link_datoteke.DeljeneMape([self.mapa])
        for rel in ("Default/Cookies", "Default/Login Data-journal", "kube.yaml", "orodje.bin", "veriga.crt",
                    "Gesla.docx"):
            self.assertIsNone(m.razresi("share:0:" + rel), rel)

    def test_napaka_branja_je_skrivnost(self):
        pot = self._datoteka("dok.txt", b"besedilo")
        getattr(link_datoteke, "_vsebina_spomin", {}).clear()
        with mock.patch.object(link_datoteke.os, "open", side_effect=OSError(5, "Input/output error")):
            self.assertTrue(link_datoteke._vsebina_skrivnost(pot))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "cev FIFO samo na POSIX")
    def test_cev_namesto_datoteke_ne_obvisi(self):
        cev = os.path.join(self.mapa, "zamenjana")
        os.mkfifo(cev)
        pravi = os.stat

        def stat_kot_datoteka(pot, *a, **k):
            st = pravi(pot, *a, **k)
            if pot == cev:          # med preverbo in odprtjem je bila to se navadna datoteka
                return os.stat_result((stat.S_IFREG | 0o644,) + tuple(st)[1:])
            return st
        izid = []
        with mock.patch.object(link_datoteke.os, "stat", stat_kot_datoteka):
            t = threading.Thread(target=lambda: izid.append(link_datoteke._vsebina_skrivnost(cev)), daemon=True)
            t.start()
            t.join(2)
        self.assertFalse(t.is_alive(), "odprtje cevi ne caka pisca")
        self.assertEqual(izid, [False])


class N6SlicicaRokBranja(unittest.TestCase):
    STREZNIK = {"base_url": "https://192.168.0.20:8443", "fp": "ab" * 32, "token": "z"}

    def test_eno_branje_ne_raztegne_roka(self):
        prekinjeno = threading.Event()

        class Vticnica:
            def settimeout(self, _t):
                pass

            def shutdown(self, _kako):
                prekinjeno.set()

        class Odgovor:
            status = 200

            def read(self, _n):
                prekinjeno.wait(5)       # en read, ki sestavlja vec recv (naprava poslje bajt na nekaj sekund)
                raise OSError(104, "Connection reset by peer")

        class Povezava:
            def __init__(self, *_a, **_k):
                self.sock = Vticnica()

            def request(self, *_a, **_k):
                pass

            def getresponse(self):
                return Odgovor()

            def close(self):
                pass
        with mock.patch("core.link_tls._PripetaHttps", Povezava):
            zacetek = time.monotonic()
            self.assertIsNone(link_slicice_naprav.prenesi_https(self.STREZNIK, "a", rok_s=0.3))
            self.assertLess(time.monotonic() - zacetek, 1.5)


class N7N13Zaslon(unittest.TestCase):
    def test_seja_brez_naprave_se_ne_zacne(self):
        z = link_zaslon.Zaslon(vklopljeno=True)
        z.ffmpeg = "/bin/true"
        with self.assertRaisesRegex(RuntimeError, "brez naprave"):
            z.zacni("")

    def test_umik_zapre_okna_svoje_seje(self):
        z = link_zaslon.Zaslon(vklopljeno=True)
        prvi, drugi = mock.Mock(), mock.Mock()
        z._naprava, z._povezan, z._seja_st, z._cilj, z.drugi = B, True, 5, "apps", prvi
        z.dostop = lambda n: False

        def ustavi(**_k):
            z._cilj, z.drugi = "desktop", drugi          # medtem nova seja druge naprave
        z.ustavi = ustavi
        self.assertTrue(z.preveri_dostop())
        for _ in range(100):
            if prvi.zapri_okna.called:
                break
            time.sleep(0.02)
        prvi.zapri_okna.assert_called_once()
        drugi.zapri_okna.assert_not_called()


if __name__ == "__main__":
    unittest.main()
