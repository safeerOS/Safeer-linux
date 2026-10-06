# -*- coding: utf-8 -*-
"""Program, ki se na locenem zaslonu ne odpre: oznaka zagona, okno na namizju, hiter izid namesto 30 s praznega zaslona."""
import json
import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from core import link_daljinec, link_programi, link_sway, link_zaslon


def _lazni_proc(procesi):
    """Mapa kot /proc: {pid: (cmdline, environ)} za trenutnega uporabnika."""
    koren = tempfile.mkdtemp()
    for pid, (ukaz, okolje) in procesi.items():
        os.mkdir(os.path.join(koren, str(pid)))
        with open(os.path.join(koren, str(pid), "cmdline"), "wb") as f:
            f.write(ukaz)
        with open(os.path.join(koren, str(pid), "environ"), "wb") as f:
            f.write(okolje)
    os.mkdir(os.path.join(koren, "sys"))       # ni proces
    return koren


class OznakaZagona(unittest.TestCase):
    def test_lupina_z_oznako_v_ukazni_vrstici(self):
        proc = _lazni_proc({10: (b"sh\0-c\0SAFEER_ZAGON=abc123 gimp\0", b"PATH=/usr/bin\0")})
        self.assertTrue(link_sway.zivi_zagon("abc123", proc))
        self.assertFalse(link_sway.zivi_zagon("drugi", proc))

    def test_otrok_z_oznako_v_okolju(self):
        """Program, ki se odcepi od lupine (ali tece v vsebniku), oznako se vedno nosi v okolju."""
        proc = _lazni_proc({11: (b"/usr/bin/bwrap\0--args\0" + b"40\0etr\0", b"HOME=/home/x\0SAFEER_ZAGON=fff000\0")})
        self.assertTrue(link_sway.zivi_zagon("fff000", proc))

    def test_brez_oznake_in_brez_procesov(self):
        proc = _lazni_proc({12: (b"nemo\0", b"PATH=/usr/bin\0")})
        self.assertFalse(link_sway.zivi_zagon("abc123", proc))
        self.assertFalse(link_sway.zivi_zagon("", proc))

    def test_neberljiv_proc_pomeni_ne_vemo(self):
        """Raje cakamo, kot da program, ki se sele odpira, razglasimo za koncanega."""
        self.assertTrue(link_sway.zivi_zagon("abc123", "/ni/take/mape"))


class OknaNamizja(unittest.TestCase):
    IZPIS = ("0x03200048  0 26825  nemo-desktop.Nemo-desktop  racunalnik Namizje\n"
             "0x02c00004  0 3277    com.primer.program.com.primer.Program  racunalnik Okno programa\n"
             "0x05e00007  0 3280    gimp.Gimp             racunalnik GIMP\n"
             "0x0360000c -1 3108    plank.Plank           racunalnik plank\n"
             "pokvarjena vrstica\n")

    def test_razbere_id_proces_in_razred(self):
        okna = link_sway.razberi_okna(self.IZPIS)
        self.assertEqual(len(okna), 4)
        self.assertEqual(okna[1], {"id": "0x02c00004", "pid": 3277, "razred": "com.primer.program.com.primer.program"})

    def test_okno_po_procesu(self):
        okna = link_sway.razberi_okna(self.IZPIS)
        self.assertEqual(link_sway.okno_programa(okna, {3280}, []), "0x05e00007")

    def test_okno_po_razredu(self):
        okna = link_sway.razberi_okna(self.IZPIS)
        self.assertEqual(link_sway.okno_programa(okna, set(), ["com.primer.program"]), "0x02c00004")
        self.assertEqual(link_sway.okno_programa(okna, set(), ["gimp"]), "0x05e00007")
        # »nemo« ni »nemo-desktop«: namizja ne razglasimo za okno upravljalnika datotek
        self.assertEqual(link_sway.okno_programa(okna, set(), ["nemo"]), "")
        self.assertEqual(link_sway.okno_programa(okna, set(), ["ni", "x"]), "")

    def test_novo_okno_ima_prednost(self):
        okna = link_sway.razberi_okna(self.IZPIS + "0x07000001  0 3280    gimp.Gimp  racunalnik Novo okno\n"
                                                   "0x07000002  0 3280    gimp.Gimp  racunalnik Se eno\n")
        self.assertEqual(link_sway.okno_programa(okna, {3280}, [], nova={"0x07000001"}), "0x07000001")
        self.assertEqual(link_sway.okno_programa(okna, {3280}, [], nova=set()), "0x07000002")

    def test_razredi_iz_vnosa(self):
        self.assertEqual(link_programi.razredi_okna("com.primer.Program.desktop", "com.primer.Program", ["program-namizje", "%U"]),
                         ["com.primer.program", "program-namizje"])
        self.assertEqual(link_programi.razredi_okna("net.primer.Igra.desktop", "",
                                                    ["/usr/bin/flatpak", "run", "--branch=stable", "--command=igra", "net.primer.Igra"]),
                         ["net.primer.igra"])
        self.assertEqual(link_programi.razredi_okna("gimp.desktop", "", ["env", "X=1", "gimp-2.10", "%U"]), ["gimp", "gimp-2.10"])


class IzidZagona(unittest.TestCase):
    def _drugi(self, zagon):
        d = link_sway.DrugiZaslon(mapa=tempfile.mkdtemp())
        d._zagon = zagon
        return d

    def test_brez_zagona_ali_prezgodaj_ne_vemo(self):
        self.assertEqual(self._drugi(None).izid_zagona(), "")
        d = self._drugi({"zeton": "a1", "cas": time.monotonic()})
        with mock.patch.object(link_sway, "zivi_zagon", return_value=False):
            self.assertEqual(d.izid_zagona(), "")

    def test_rod_viden_ziv_in_koncan_pove_pred_najkrajsim_casom(self):
        """Program ene same instance konca v sekundi: ko smo njegov rod videli ziv, na 2 s ne cakamo vec."""
        okna = link_sway.razberi_okna(OknaNamizja.IZPIS)
        d = self._drugi({"zeton": "a1", "cas": time.monotonic(), "videl": True, "pidi": lambda: [3277], "razredi": [],
                         "okna_pred": {o["id"] for o in okna}})
        with mock.patch.object(link_sway, "zivi_zagon", return_value=False), \
                mock.patch.object(link_sway, "_okna_namizja", return_value=okna):
            self.assertEqual(d.izid_zagona(), "na_namizju")

    def test_konec_rodu_potrdi_drugi_pogled(self):
        """Proces med `exec` za hip nima ne ukazne vrstice ne okolja: en sam pogled ni dovolj za »koncal«."""
        d = self._drugi({"zeton": "a1", "cas": time.monotonic() - 10})
        with mock.patch.object(link_sway, "zivi_zagon", side_effect=[False, True]) as zivi, \
                mock.patch.object(link_sway, "_okna_namizja", return_value=[]):
            self.assertEqual(d.izid_zagona(), "")
        self.assertEqual(zivi.call_count, 2)

    def test_ziv_rod_si_zapomnimo(self):
        d = self._drugi({"zeton": "a1", "cas": time.monotonic() - 10})
        with mock.patch.object(link_sway, "zivi_zagon", return_value=True):
            self.assertEqual(d.izid_zagona(), "")
        self.assertTrue(d._zagon["videl"])

    def test_opazovanje_zagona_vidi_ziv_rod(self):
        z = {"zeton": "a1", "cas": time.monotonic()}
        d = self._drugi(z)
        with mock.patch.object(link_sway, "zivi_zagon", side_effect=[False, False, True]) as zivi, \
                mock.patch.object(link_sway.time, "sleep", lambda s: None):
            d._opazuj_zagon(z)
        self.assertTrue(z["videl"])
        self.assertEqual(zivi.call_count, 3)

    def test_opazovanje_zagona_neha_ob_novem_zagonu_in_po_roku(self):
        star = {"zeton": "a1", "cas": time.monotonic()}
        d = self._drugi({"zeton": "b2", "cas": time.monotonic()})       # medtem je bil zagnan drug program
        with mock.patch.object(link_sway, "zivi_zagon", return_value=True) as zivi:
            d._opazuj_zagon(star)
        self.assertEqual(zivi.call_count, 0)
        self.assertNotIn("videl", star)
        pozno = {"zeton": "c3", "cas": time.monotonic() - 10}
        d = self._drugi(pozno)
        with mock.patch.object(link_sway, "zivi_zagon", return_value=False) as zivi:
            d._opazuj_zagon(pozno)
        self.assertEqual(zivi.call_count, 0)
        self.assertNotIn("videl", pozno)

    def test_rod_se_zivi_cakamo(self):
        d = self._drugi({"zeton": "a1", "cas": time.monotonic() - 10})
        with mock.patch.object(link_sway, "zivi_zagon", return_value=True):
            self.assertEqual(d.izid_zagona(), "")

    def test_rod_koncal_program_ima_okno_na_namizju(self):
        okna = link_sway.razberi_okna(OknaNamizja.IZPIS)
        d = self._drugi({"zeton": "a1", "cas": time.monotonic() - 10, "ime": "Program", "pidi": lambda: [3277],
                         "razredi": [], "okna_pred": {o["id"] for o in okna}})
        with mock.patch.object(link_sway, "zivi_zagon", return_value=False), \
                mock.patch.object(link_sway, "_okna_namizja", return_value=okna):
            self.assertEqual(d.izid_zagona(), "na_namizju")
        self.assertEqual(d._zagon["okno"], "0x02c00004")
        self.assertEqual(d.opis_zagona(), {"name": "Program"})

    def test_rod_koncal_brez_okna(self):
        okna = link_sway.razberi_okna(OknaNamizja.IZPIS)
        d = self._drugi({"zeton": "a1", "cas": time.monotonic() - 10, "pidi": lambda: [], "razredi": ["drugo"]})
        with mock.patch.object(link_sway, "zivi_zagon", return_value=False), \
                mock.patch.object(link_sway, "_okna_namizja", return_value=okna):
            self.assertEqual(d.izid_zagona(), "koncan")
        # namizja ne moremo pogledati (ni wmctrl): vemo samo, da je rod koncal
        with mock.patch.object(link_sway, "zivi_zagon", return_value=False), \
                mock.patch.object(link_sway, "_okna_namizja", return_value=None):
            self.assertEqual(d.izid_zagona(), "koncan")

    def test_zagon_dobi_oznako_in_opis(self):
        d = link_sway.DrugiZaslon(mapa=tempfile.mkdtemp())
        ukazi = []
        d.zazeni = lambda s, v: True
        d._msg = lambda argumenti, vrsta=None: (ukazi.append(argumenti) or '[{"success": true}]')
        with mock.patch.object(link_sway, "_okna_namizja", return_value=[{"id": "0x1", "pid": 5, "razred": "a.b"}]):
            self.assertTrue(d.zazeni_program(["gimp", "--novo okno"], opis={"ime": "GIMP", "razredi": ["gimp"]}))
        self.assertEqual(ukazi[0][0], "exec")
        self.assertRegex(ukazi[0][1], r"^SAFEER_ZAGON=[0-9a-f]{12} gimp '--novo okno'$")
        self.assertEqual(d._zagon["ime"], "GIMP")
        self.assertEqual(d._zagon["okna_pred"], {"0x1"})
        self.assertIn(d._zagon["zeton"], ukazi[0][1])

    def test_neuspel_zagon_ne_pusti_stare_oznake(self):
        d = link_sway.DrugiZaslon(mapa=tempfile.mkdtemp())
        d._zagon = {"zeton": "star", "cas": 0.0}
        d.zazeni = lambda s, v: True
        d._msg = lambda argumenti, vrsta=None: '[{"success": false}]'
        with mock.patch.object(link_sway, "_okna_namizja", return_value=None):
            self.assertFalse(d.zazeni_program(["gimp"]))
        self.assertIsNone(d._zagon)


class LazniOdjemalec:
    def __init__(self):
        self.poslano = []

    def sendall(self, b):
        self.poslano.append(b)

    def obvestila(self):
        return [json.loads(b[5:].decode("utf-8")) for b in self.poslano if b[0] == link_zaslon.OKVIR_OBVESTILO]


class LazniProces:
    def poll(self):
        return None


class StrazaPraznegaZaslona(unittest.TestCase):
    def _zaslon(self, izidi, zmoznosti, okna=0):
        z = link_zaslon.Zaslon(vklopljeno=True)
        z._cilj = "apps"
        z._zmoznosti = set(zmoznosti)
        vrsta = list(izidi)
        z.drugi = SimpleNamespace(okna=lambda: okna,
                                  izid_zagona=lambda: vrsta.pop(0) if len(vrsta) > 1 else vrsta[0],
                                  opis_zagona=lambda: {"name": "Program"})
        z.ustavi = lambda seja=None: setattr(z, "_proces", None)
        return z

    def _tece(self, z):
        odjemalec, slika = LazniOdjemalec(), LazniProces()
        z._proces = slika
        with mock.patch.object(link_zaslon.time, "sleep", lambda s: None):
            z._strazi_prazno(odjemalec, slika)
        return odjemalec.obvestila()

    def test_program_na_namizju_naprava_zna_preklop(self):
        o = self._tece(self._zaslon(["", "na_namizju"], {"handoff"}))
        self.assertEqual(o, [{"program": "caka", "name": "Program"}, {"konec": "na_namizju", "name": "Program"}])

    def test_program_na_namizju_starejsa_naprava(self):
        """Naprava, ki preklopa ne zna, dobi `ni_okna` - isto sporocilo kot doslej, le takoj."""
        o = self._tece(self._zaslon(["na_namizju"], set()))
        self.assertEqual(o, [{"konec": "ni_okna"}])

    def test_rod_koncal_brez_okna_takoj_pove(self):
        o = self._tece(self._zaslon(["koncan"], {"handoff"}))
        self.assertEqual(o, [{"konec": "ni_okna"}])

    def test_obvestilo_caka_samo_enkrat(self):
        o = self._tece(self._zaslon(["", "", "", "koncan"], set()))
        self.assertEqual(o, [{"program": "caka", "name": "Program"}, {"konec": "ni_okna"}])

    def test_okno_po_cakanju_javi_odprt(self):
        z = self._zaslon([""], set())
        stanje = {"n": 0}

        def okna():
            stanje["n"] += 1
            if stanje["n"] >= 4:
                z._proces = None          # konec preizkusa: seja se ustavi
            return 0 if stanje["n"] < 3 else 1
        z.drugi.okna = okna
        o = self._tece(z)
        self.assertEqual(o, [{"program": "caka", "name": "Program"}, {"program": "odprt"}])


class UkazZaslona(unittest.TestCase):
    def test_caps_pridejo_do_seje_in_handoff_pokaze_okno(self):
        klici = {}
        pokazano = []

        class LazniZaslon:
            drugi = SimpleNamespace(pokazi_na_namizju=lambda: pokazano.append(True))

            def na_voljo(self):
                return {"dovoljeno": True, "mozno": True}

            def zacni(self, naprava, kakovost, cilj, **dodatno):
                klici.update(dodatno, cilj=cilj)
                return {"port": 1, "screen": "desktop"}

        odgovori = []
        link_daljinec.izvedi_control("screen.start", {"screen": "desktop", "caps": ["handoff", 7, "x" * 99], "handoff": True},
                                     lambda u: None, odgovori.append, zaslon=LazniZaslon(), posiljatelj="fon")
        self.assertTrue(odgovori and odgovori[0].get("ok"), odgovori)
        self.assertEqual(klici["zmoznosti"], ["handoff", "x" * 32])
        for _ in range(50):
            if pokazano:
                break
            time.sleep(0.01)
        self.assertEqual(pokazano, [True])


if __name__ == "__main__":
    unittest.main()
