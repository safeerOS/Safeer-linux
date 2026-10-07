"""Dostop naprav v Safeer Linku do vsebin tega racunalnika (core/link_dostop).

Seznanitev v Link ni dovoljenje za vsebine: naprava brez zapisa samo pomaga pri povezavi. Tu je preverjeno, da racunalnik
zavrne sam - pri ukazih, pri strezniku datotek in pri oddajah, ki jih posreduje sredisce na njem.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

import pytest

from core import link_datoteke, link_dostop, link_hub_streznik

pytestmark = pytest.mark.pravi_dostop

A = "n-aaaaaaaaaaaaaaaa"      # naprava istega uporabnika
B = "n-bbbbbbbbbbbbbbbb"      # naprava, ki v Linku samo pomaga
S = "n-dddddddddddddddd"      # izvor oddaje
JAZ = "n-cccccccccccccccc"    # ta racunalnik
KLJUCI = {"KJAZ": JAZ, "KA": A, "KB": B, "KS": S}


class _Krog:
    def __init__(self, clani=()):
        import threading
        self._zaklep = threading.RLock()
        self.clani = {c["id"]: c for c in clani}

    def _veljaven(self, c):
        return True

    def clan_za_id(self, device_id):
        return self.clani.get(device_id)


class _Osnova(unittest.TestCase):
    clani = ()

    def setUp(self):
        self._mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self._mapa.cleanup)
        link_dostop._za_preizkus(os.path.join(self._mapa.name, "dostop.json"))
        self.addCleanup(lambda: link_dostop._za_preizkus(None))
        for ime, vrednost in (("_lastni_kljuc", lambda: "KJAZ"), ("_id_iz_kljuca", lambda k: KLJUCI[k]),
                              ("_krog", lambda: _Krog(self.clani))):
            p = mock.patch.object(link_dostop, ime, vrednost)
            p.start()
            self.addCleanup(p.stop)


class Pravila(unittest.TestCase):
    def test_zahteve_dejanj(self):
        z = link_dostop.zahteva_dejanja
        self.assertEqual(z("files.list"), link_dostop.DATOTEKE)
        self.assertEqual(z("files.search"), link_dostop.DATOTEKE)
        self.assertEqual(z("apps.list"), link_dostop.PROGRAMI)
        self.assertEqual(z("apps.launch"), link_dostop.PROGRAMI)
        self.assertEqual(z("play.state"), link_dostop.PREDVAJALNIK)
        self.assertEqual(z("lists.get"), link_dostop.PREDVAJALNIK)
        self.assertEqual(z("open_url"), link_dostop.PREDVAJALNIK)
        self.assertEqual(z("screen.start"), link_dostop.ZASLON)
        self.assertEqual(z("input.key"), link_dostop.ZASLON)
        self.assertEqual(z("Files.List "), link_dostop.DATOTEKE)

    def test_ponudba_je_prosta_neznano_zahteva_vse(self):
        self.assertEqual(link_dostop.zahteva_dejanja("play.offer"), link_dostop.PROSTO)
        self.assertEqual(link_dostop.zahteva_dejanja("novo.dejanje"), link_dostop.VSE)
        self.assertEqual(link_dostop.zahteva_dejanja(""), link_dostop.VSE)

    def test_sporocila(self):
        z = link_dostop.zahteva_sporocila
        self.assertEqual(z("share.text"), link_dostop.PROSTO)
        self.assertEqual(z("share.file"), link_dostop.PROSTO)
        self.assertEqual(z("chat.send"), link_dostop.PROSTO)
        self.assertEqual(z("cast.url"), link_dostop.PREDVAJALNIK)
        self.assertEqual(z("sync.data"), link_dostop.VSE)
        self.assertEqual(z("share.screen", "start"), link_dostop.ZASLON)
        self.assertEqual(z("share.screen", "stop"), link_dostop.PROSTO)

    def test_sme_z(self):
        self.assertTrue(link_dostop.sme_z("", link_dostop.PROSTO))
        self.assertFalse(link_dostop.sme_z("", link_dostop.DATOTEKE))
        self.assertTrue(link_dostop.sme_z("dv", link_dostop.PREDVAJALNIK))
        self.assertFalse(link_dostop.sme_z("dpv", link_dostop.VSE))
        self.assertTrue(link_dostop.sme_z("dpvz", link_dostop.VSE))

    def test_zavrnitev_ima_obliko_naprava_ne_deli(self):
        d = link_dostop.zavrnitev("files.list")
        self.assertTrue(d["ok"])
        self.assertEqual(d["data"]["items"], [])
        self.assertFalse(d["data"]["shared"])
        p = link_dostop.zavrnitev("apps.list")
        self.assertEqual((p["ok"], p["data"]["items"], p["data"]["enabled"]), (True, [], False))
        self.assertFalse(link_dostop.zavrnitev("play.state")["data"]["shared"])
        z = link_dostop.zavrnitev("screen.start")
        self.assertEqual((z["ok"], z["code"]), (False, "ni_dovoljeno"))


class Podedovanje(unittest.TestCase):
    MEJA = link_dostop.MEJA_PODEDOVANJA

    def _podedovani(self, clani, lastni="KJAZ"):
        return link_dostop.podedovani(clani, lastni, lambda k: KLJUCI[k])

    def test_naprave_od_prej_obdrzijo_dostop(self):
        clani = [{"kljuc": "KJAZ", "dodano": self.MEJA - 5000}, {"kljuc": "KA", "dodano": self.MEJA - 10},
                 {"kljuc": "KB", "dodano": self.MEJA + 3600}]
        self.assertEqual(self._podedovani(clani), {A})

    def test_naprava_dodana_po_meji_ne_podeduje_nikogar(self):
        clani = [{"kljuc": "KJAZ", "dodano": self.MEJA + 60}, {"kljuc": "KA", "dodano": self.MEJA - 10}]
        self.assertEqual(self._podedovani(clani), set())

    def test_steje_najstarejsi_vnos_istega_kljuca(self):
        clani = [{"kljuc": "KJAZ", "dodano": self.MEJA - 5000},
                 {"kljuc": "KA", "dodano": self.MEJA + 100}, {"kljuc": "KA", "dodano": self.MEJA - 100}]
        self.assertEqual(self._podedovani(clani), {A})

    def test_brez_kljuca_ali_na_meji(self):
        self.assertEqual(self._podedovani([{"kljuc": "KA", "dodano": 1.0}], lastni=None), set())
        clani = [{"kljuc": "KJAZ", "dodano": 1.0}, {"kljuc": "KA", "dodano": self.MEJA}]
        self.assertEqual(self._podedovani(clani), set())


class Zapis(_Osnova):
    def test_naprava_brez_zapisa_samo_pomaga(self):
        self.assertEqual(link_dostop.zmoznosti(B), set())
        self.assertFalse(link_dostop.sme_dejanje(B, "files.list"))
        self.assertFalse(link_dostop.sme_dejanje(B, "apps.list"))
        self.assertFalse(link_dostop.sme_dejanje(B, "play.state"))
        self.assertFalse(link_dostop.sme_sporocilo(B, "sync.data"))
        self.assertTrue(link_dostop.sme_dejanje(B, "play.offer"))
        self.assertTrue(link_dostop.sme_sporocilo(B, "share.file"))
        self.assertFalse(link_dostop.sme_dejanje("", "files.list"))

    def test_odpri_in_vzemi(self):
        self.assertTrue(link_dostop.nastavi(B, "dv"))
        self.assertTrue(link_dostop.sme_dejanje(B, "files.list"))
        self.assertTrue(link_dostop.sme_dejanje(B, "play.state"))
        self.assertFalse(link_dostop.sme_dejanje(B, "apps.list"))
        self.assertFalse(link_dostop.sme_sporocilo(B, "sync.data"))     # usklajevanje samo ozji krog (vse stiri)
        self.assertEqual(link_dostop.vsi(), {B: "dv"})
        link_dostop.nastavi(B, "")
        self.assertFalse(link_dostop.sme_dejanje(B, "files.list"))

    def test_sorodni_programi_iste_naprave_delijo_zapis(self):
        link_dostop.nastavi(A + "-os", "dpvz")
        self.assertTrue(link_dostop.sme_dejanje(A + "-control", "apps.launch"))
        self.assertTrue(link_dostop.sme_sporocilo(A, "sync.data"))

    def test_ta_racunalnik_ima_vse_in_se_ga_ne_da_nastaviti(self):
        self.assertTrue(link_dostop.sme_dejanje(JAZ + "-control", "files.list", zascita=JAZ))
        self.assertTrue(link_dostop.je_ta_naprava(JAZ))
        self.assertFalse(link_dostop.nastavi(JAZ, ""))
        self.assertTrue(link_dostop.sme_sporocilo(JAZ + "-os", "sync.data"))
        self.assertEqual(link_dostop.zmoznosti(JAZ + "-control"), set(link_dostop.VSE_ZMOZNOSTI))

    def test_oznaka_tega_racunalnika_brez_zascite_ni_dovolj_za_ukaz(self):
        """Programi tega racunalnika zascito znajo: kdor se z njegovo oznako javi brez nje, ni ta racunalnik."""
        with mock.patch("core.link_e2e.na_voljo", return_value=True):
            self.assertFalse(link_dostop.sme_dejanje(JAZ + "-control", "files.list"))
            self.assertFalse(link_dostop.sme_sporocilo(JAZ + "-x", "cast.url"))
        with mock.patch("core.link_e2e.na_voljo", return_value=False):       # brez kriptografije zascite ni: kot doslej
            self.assertTrue(link_dostop.sme_dejanje(JAZ + "-control", "files.list"))

    def test_zapis_je_samo_za_lastnika_in_prezivi_ponovni_zagon(self):
        link_dostop.nastavi(B, "p")
        pot = link_dostop._pot()
        self.assertEqual(os.stat(pot).st_mode & 0o777, 0o600)
        link_dostop._za_preizkus(pot)                   # kot nov zagon programa: zapis se prebere z diska
        self.assertEqual(link_dostop.zmoznosti(B), {"p"})

    def test_pokvarjen_zapis_ne_odpre_nicesar(self):
        link_dostop.nastavi(B, "dpvz")
        pot = link_dostop._pot()
        with open(pot, "w", encoding="utf-8") as d:
            d.write("{ni json")
        link_dostop._za_preizkus(pot)
        self.assertEqual(link_dostop.zmoznosti(B), set())

    def test_prejemniki_oddaje(self):
        link_dostop.nastavi(A, "dpvz")
        # izvor navede sam: tocno ti (in on sam)
        self.assertEqual(link_dostop.prejemniki([B], S, link_dostop.VSE), {B, S})
        self.assertEqual(link_dostop.prejemniki([], S, link_dostop.VSE), {S})
        # starejsi izvor brez seznama, ki ni v ozjem krogu tega racunalnika: nikomur
        self.assertEqual(link_dostop.prejemniki(None, S, link_dostop.VSE), {S})
        # starejsi izvor iz ozjega kroga: ozjemu krogu tega racunalnika in programom na njem
        link_dostop.nastavi(S, "dpvz")
        self.assertEqual(link_dostop.prejemniki(None, S, link_dostop.VSE), {A, S, JAZ})


class Zascita(_Osnova):
    """Zascita od naprave do naprave (core/link_e2e): dostop se veze na preverjen kljuc; naprava, ki zascito zna, se
    brez nje ne more vec javiti - tudi nihce v njenem imenu."""

    def test_po_vzpostavljeni_zasciti_nezascitenega_ukaza_ne_sprejmemo(self):
        link_dostop.nastavi(A, "dp")
        self.assertTrue(link_dostop.sme_dejanje(A + "-os", "files.list"))               # starejsa razlicica: po oznaki
        link_dostop.zabelezi_zascito(A)
        self.assertTrue(link_dostop.zahteva_zascito(A + "-os"))
        self.assertFalse(link_dostop.sme_dejanje(A + "-os", "files.list"))              # isto brez zascite: ne vec
        self.assertTrue(link_dostop.sme_dejanje(A + "-os", "files.list", zascita=A))    # zasciteno: po kljucu
        self.assertFalse(link_dostop.sme_dejanje(A + "-os", "screen.start", zascita=A))  # zascita ni dovoljenje
        self.assertFalse(link_dostop.sme_sporocilo(A + "-os", "cast.url"))
        self.assertTrue(link_dostop.sme_dejanje(A + "-os", "play.offer"))               # prosto ostane prosto
        self.assertTrue(link_dostop.sme(A + "-os", link_dostop.DATOTEKE))               # zeton streznika datotek

    def test_usklajevanje_in_zaslon_gresta_se_po_starem(self):
        link_dostop.nastavi(A, "dpvz")
        link_dostop.zabelezi_zascito(A)
        self.assertTrue(link_dostop.sme_sporocilo(A + "-os", "sync.data"))
        self.assertTrue(link_dostop.sme_sporocilo(A + "-os", "share.screen", "start"))

    def test_zascita_odloca_po_kljucu_ne_po_oznaki(self):
        link_dostop.nastavi(A, "dpvz")
        self.assertFalse(link_dostop.sme_dejanje(A + "-os", "files.list", zascita=B))   # oznaka A, kljuc B
        self.assertTrue(link_dostop.sme_dejanje(B, "files.list", zascita=A))            # oznaka B, kljuc A
        self.assertEqual(link_dostop.zmoznosti_jedra(""), set())
        self.assertEqual(link_dostop.zmoznosti_jedra(JAZ), set(link_dostop.VSE_ZMOZNOSTI))

    def test_zapis_zascite_prezivi_ponovni_zagon_in_spremembo_dostopa(self):
        link_dostop.zabelezi_zascito(A)
        link_dostop.nastavi(B, "p")
        pot = link_dostop._pot()
        link_dostop._za_preizkus(pot)
        self.assertTrue(link_dostop.zna_zascito(A))
        self.assertFalse(link_dostop.zna_zascito(B))
        with open(pot, encoding="utf-8") as d:
            self.assertEqual(json.load(d)["zascita"], [A])

    def test_zabelezi_se_samo_jedro_iz_kljuca(self):
        for neveljavno in (A + "-os", "karkoli", "", "n-12345"):
            link_dostop.zabelezi_zascito(neveljavno)
        self.assertFalse(link_dostop.zna_zascito(A))
        self.assertFalse(link_dostop.zna_zascito(""))


class PodobnaOznaka(_Osnova):
    """Izmerjeno 7. 10. 2026: krog sprejme vnos z oznako, ki je videti kot oznaka druge naprave, a z drugim kljucem."""
    clani = ({"id": A + "-x", "kljuc": "KB", "dodano": 1.0}, {"id": JAZ + "-x", "kljuc": "KB", "dodano": 1.0})

    def test_vnos_z_oznako_druge_naprave_in_svojim_kljucem_ne_dobi_njenega_dostopa(self):
        link_dostop.nastavi(A, "dpvz")
        self.assertEqual(link_dostop.jedro(A + "-x"), "")
        self.assertEqual(link_dostop.zmoznosti(A + "-x"), set())
        self.assertFalse(link_dostop.sme_dejanje(A + "-x", "files.list"))
        self.assertTrue(link_dostop.sme_dejanje(A + "-os", "files.list"))       # prava naprava A
        self.assertFalse(link_dostop.nastavi(A + "-x", "dpvz"))

    def test_oznaka_z_drugim_kljucem_ne_deli_shrambe_z_drugo_tako_oznako(self):
        """Prazno jedro ne sme postati skupni kljuc: izrecno poslana datoteka in prejemniki oddaje ostanejo pri oznaki."""
        from core import link_hub_streznik
        brez = link_dostop.BREZ_JEDRA               # kljuc shrambe oznake brez jedra ni enak nobenemu jedru
        self.assertEqual(link_datoteke._jedro_naprave(A + "-x"), brez + A + "-x")
        self.assertEqual(link_datoteke._jedro_naprave(A + "-os"), A)
        self.assertEqual(link_hub_streznik._jedro_naprave(JAZ + "-x"), brez + JAZ + "-x")
        s = link_datoteke.StreznikDatotek(mock.Mock())
        s.umaknjena = lambda n: False
        s.dovoli_izrecno(A + "-x", "film-1")
        self.assertTrue(s.izrecno_dovoljena(A + "-x", "film-1"))
        self.assertFalse(s.izrecno_dovoljena(JAZ + "-x", "film-1"))       # druga oznaka s praznim jedrom
        self.assertFalse(s.izrecno_dovoljena(A, "film-1"))               # prava naprava A tega ni dobila
        self.assertEqual(link_dostop.prejemniki(None, A + "-x", link_dostop.VSE), {brez + A + "-x"})
        self.assertEqual(link_dostop.prejemniki(["", B], S, link_dostop.VSE), {B, S})       # praznega jedra ni v seznamu
        self.assertEqual(link_dostop.prejemniki([], "", link_dostop.VSE), set())            # izvor brez oznake: nihce

    def test_vnos_z_oznako_tega_racunalnika_in_tujim_kljucem_ni_ta_racunalnik(self):
        self.assertFalse(link_dostop.je_ta_naprava(JAZ + "-x"))
        self.assertEqual(link_dostop.zmoznosti(JAZ + "-x"), set())
        self.assertTrue(link_dostop.je_ta_naprava(JAZ + "-control"))


class GoloJedroSTujimKljucem(_Osnova):
    """Vnos, katerega oznaka je kar GOLO jedro druge naprave, kljuc pa tuj (neodvisni pregled 7. 10. 2026): kljuc
    shrambe take oznake ne sme biti enak jedru prave naprave - sicer bi dobila, kar je bilo izrecno poslano pravi."""
    clani = ({"id": A, "kljuc": "KB", "dodano": 1.0},)

    def test_kljuc_shrambe_ni_jedro_prave_naprave(self):
        self.assertEqual(link_dostop.jedro(A), "")                             # pod oznako A je v krogu drug kljuc
        self.assertEqual(link_dostop.jedro(A + "-os"), A)                      # program prave naprave A
        self.assertEqual(link_dostop.kljuc_shrambe(A), link_dostop.BREZ_JEDRA + A)
        self.assertEqual(link_dostop.kljuc_shrambe(A + "-os"), A)
        self.assertNotEqual(link_datoteke._jedro_naprave(A), link_datoteke._jedro_naprave(A + "-os"))
        self.assertNotEqual(link_hub_streznik._jedro_naprave(A), A)

    def test_izrecno_poslana_datoteka_prave_naprave_ne_velja_za_vnos_s_tujim_kljucem(self):
        s = link_datoteke.StreznikDatotek(mock.Mock())
        s.umaknjena = lambda n: False
        s.dovoli_izrecno(A + "-os", "film-1")                                  # poslano pravi napravi
        self.assertTrue(s.izrecno_dovoljena(A + "-os", "film-1"))
        self.assertFalse(s.izrecno_dovoljena(A, "film-1"))                     # oznaka z golim jedrom in tujim kljucem

    def test_vnos_s_tujim_kljucem_ni_med_prejemniki_za_jedro_prave_naprave(self):
        smejo = link_dostop.prejemniki([A], S, link_dostop.VSE)                # izvor navede jedro prave naprave A
        self.assertIn(link_hub_streznik._jedro_naprave(A + "-os"), smejo)      # njen program oddajo dobi
        self.assertNotIn(link_hub_streznik._jedro_naprave(A), smejo)           # vnos z golim jedrom in tujim kljucem ne


class ZascitaPoOblikiOznake(_Osnova):
    """Drugi neodvisni pregled (7. 10. 2026): pod oznako programa naprave A je v krogu podtaknjen DRUG kljuc (novejsi
    vnos krog sprejme). Tak vnos ne sme ugasniti pravila »od naprave, ki je kljuc dokazala, samo zasciteno«."""
    clani = ({"id": A + "-os", "kljuc": "KB", "dodano": 2.0}, {"id": A, "kljuc": "KA", "dodano": 1.0})

    def test_podtaknjen_vnos_ne_ugasne_zahteve_po_zasciti(self):
        link_dostop.nastavi(A, "dpvz")
        link_dostop.zabelezi_zascito(A)
        self.assertEqual(link_dostop.jedro(A + "-os"), "")                     # vnos s tujim kljucem: brez jedra
        self.assertTrue(link_dostop.zahteva_zascito(A + "-os"))                # ... zascita se od te oznake se zahteva
        self.assertTrue(link_dostop.zahteva_zascito(A))
        self.assertFalse(link_dostop.sme_sporocilo(A + "-os", "cast.url"))
        self.assertFalse(link_dostop.sme_dejanje(A + "-os", "files.list"))

    def test_brez_dokazanega_kljuca_zascite_ne_zahtevamo(self):
        self.assertFalse(link_dostop.zahteva_zascito(A + "-os"))
        self.assertFalse(link_dostop.zahteva_zascito(B))
        self.assertFalse(link_dostop.zahteva_zascito(""))
        self.assertFalse(link_dostop.zahteva_zascito("stara-naprava"))


class OblikaOznakeIzKljuca(unittest.TestCase):
    """Oznaka iz kljuca ima za jedrom samo pripono programa iz crk, stevk, pike, podcrtaja in vezaja. Oznaka z drugimi
    znaki (prelom vrstice, presledek ...) NI oznaka iz kljuca in kljuca po jedru ne dobi."""

    def test_oblika(self):
        from core import link_krog
        j = "n-0123456789abcdef"
        for preveri in (link_dostop.je_id_iz_kljuca, link_krog.je_id_iz_kljuca):
            for dobra in (j, j + "-os", j + "-control", j + "-a.b_c-1", j + "-"):
                self.assertTrue(preveri(dobra), dobra)
            for slaba in (j + "-x\ny", j + "-x y", j + "-\u010d", j + "-" + "a" * 200, j + "\n", j + "x",
                          "n-0123456789ABCDEF", "n-0123456789abcde", "x-0123456789abcdef", ""):
                self.assertFalse(preveri(slaba), repr(slaba))


class VecProgramov(_Osnova):
    """Zapis dovoljenj pise vec programov tega racunalnika hkrati (Control, brskalnik, Safeer OS, pomozni programi).
    Cetrti neodvisni pregled (7. 10. 2026): skupno ime zacasne datoteke in pisanje stanja iz pomnilnika brez zaklepa med
    programi. Vsak preizkus je najprej padel."""

    def test_zapis_zascite_ne_povozi_spremembe_drugega_programa(self):
        """Drug program odpre napravi B dostop tik preden ta program zapise, da je naprava A dokazala kljuc (stanje v
        pomnilniku tega programa je takrat ze staro). Sprememba drugega programa mora ostati."""
        link_dostop.nastavi(A, "d")
        pot = link_dostop._pot()
        pravi = os.makedirs
        klici = []

        def drug_program(*a, **k):
            if not klici:
                klici.append(1)
                with open(pot, encoding="utf-8") as d:
                    zapis = json.load(d)
                zapis["naprave"][B] = "dpvz"
                with open(pot, "w", encoding="utf-8") as d:
                    json.dump(zapis, d)
            return pravi(*a, **k)
        with mock.patch.object(link_dostop.os, "makedirs", drug_program):
            link_dostop.zabelezi_zascito(A)
        self.assertEqual(klici, [1])
        link_dostop._za_preizkus(pot)                   # kot nov zagon programa: stanje z diska
        self.assertEqual(link_dostop.zmoznosti(B), set("dpvz"))
        self.assertEqual(link_dostop.zmoznosti(A), {"d"})
        self.assertTrue(link_dostop.zna_zascito(A))

    def test_dva_programa_hkrati_ne_pokvarita_zapisa(self):
        """Pravi drug proces 100-krat spremeni dostop, ta proces medtem 100-krat zabelezi dokazan kljuc: na koncu so v
        zapisu vse spremembe obeh, zapis je veljaven JSON in v mapi ni ostankov."""
        import subprocess
        import sys
        import time
        pot = link_dostop._pot()
        link_dostop.nastavi(A, "d")
        koda = (
            "import sys\n"
            "from core import link_dostop\n"
            "link_dostop._za_preizkus(sys.argv[1])\n"
            "link_dostop.je_ta_naprava = lambda i: False\n"
            "link_dostop.jedro = lambda i: i[:18]\n"
            "link_dostop._lastni_kljuc = lambda: None\n"
            "def _brez_kroga():\n"
            "    raise RuntimeError('preizkus ne bere pravega kroga')\n"
            "link_dostop._krog = _brez_kroga\n"
            "for i in range(100):\n"
            "    link_dostop.nastavi('n-%016x' % (0x1000 + i), 'dp')\n")
        koren = os.path.dirname(os.path.dirname(os.path.abspath(link_dostop.__file__)))
        proces = subprocess.Popen([sys.executable, "-c", koda, pot], cwd=koren)
        try:
            rok = time.time() + 30
            while time.time() < rok and proces.poll() is None:      # pocakamo, da drugi proces res pise
                try:
                    with open(pot, encoding="utf-8") as d:
                        if "n-%016x" % 0x1000 in json.load(d).get("naprave", {}):
                            break
                except (OSError, ValueError):
                    pass
                time.sleep(0.005)
            for i in range(100):
                link_dostop.zabelezi_zascito("n-%016x" % (0x2000 + i))
            self.assertEqual(proces.wait(timeout=60), 0)
        finally:
            if proces.poll() is None:
                proces.kill()
        with open(pot, encoding="utf-8") as d:
            zapis = json.load(d)
        self.assertEqual(sorted(zapis["naprave"]), sorted([A] + ["n-%016x" % (0x1000 + i) for i in range(100)]))
        self.assertEqual(zapis["zascita"], ["n-%016x" % (0x2000 + i) for i in range(100)])
        self.assertEqual(sorted(os.listdir(os.path.dirname(pot))), ["dostop.json", "dostop.json.lock"])

    def test_pokvarjen_zapis_ne_zbrise_zascite_v_pomnilniku(self):
        """Zapis na disku se pokvari: dostopa nima nihce (varna stran), za napravo, ki je kljuc ze dokazala, pa v tem
        programu se naprej velja »samo zasciteno« - prej je pokvarjen zapis zascito ugasnil."""
        link_dostop.nastavi(A, "dp")
        link_dostop.zabelezi_zascito(A)
        pot = link_dostop._pot()
        with open(pot, "w", encoding="utf-8") as d:
            d.write("{ni json")
        os.utime(pot, (1, 1))
        self.assertEqual(link_dostop.zmoznosti(A), set())
        self.assertTrue(link_dostop.zna_zascito(A))
        self.assertTrue(link_dostop.zahteva_zascito(A + "-os"))
        link_dostop.nastavi(B, "p")                     # naslednji zapis zascito vrne tudi na disk
        with open(pot, encoding="utf-8") as d:
            zapis = json.load(d)
        self.assertEqual((zapis["zascita"], zapis["naprave"]), ([A], {B: "p"}))

    def test_sprememba_drugega_programa_v_istem_trenutku_se_opazi(self):
        """Dva zapisa v istem trenutku imata lahko isti cas spremembe: spremembo drugega programa moramo vseeno opaziti
        (vsak zapis je nova datoteka)."""
        link_dostop.nastavi(B, "dpvz")
        pot = link_dostop._pot()
        cas = os.stat(pot)
        with open(pot, encoding="utf-8") as d:
            zapis = json.load(d)
        zapis["naprave"][B] = ""                        # drug program napravi B dostop vzame ...
        with open(pot + ".drug", "w", encoding="utf-8") as d:
            json.dump(zapis, d, indent=1)
        os.replace(pot + ".drug", pot)
        os.utime(pot, ns=(cas.st_atime_ns, cas.st_mtime_ns))        # ... v istem trenutku (isti cas spremembe)
        self.assertEqual(link_dostop.zmoznosti(B), set())


class PetiPregled(_Osnova):
    """Peti neodvisni pregled (7. 10. 2026): zapis dovoljenj ob starejsem programu na istem racunalniku, ob napaki pri
    branju in ob zaklepu, ki ga drzi zamrznjen program. Vsak preizkus je najprej padel."""
    MEJA = link_dostop.MEJA_PODEDOVANJA
    clani = ({"id": "jaz", "kljuc": "KJAZ", "dodano": MEJA - 9000}, {"id": "a", "kljuc": "KA", "dodano": MEJA - 100})

    def _zapis(self):
        with open(link_dostop._pot(), encoding="utf-8") as d:
            return json.load(d)

    def test_zapis_zascite_se_po_pisanju_starejsega_programa_vrne_na_disk(self):
        """Starejsi program na istem racunalniku (ne pozna polja »zascita«) zapise dovoljenja po svoje: polje izgine z
        diska. Ta program ga ima se v pomnilniku in ga ob naslednji potrditvi seje vrne na disk - sicer bi po svojem
        ponovnem zagonu od naprave spet sprejel nezascitene ukaze."""
        link_dostop.nastavi(A, "dp")
        link_dostop.zabelezi_zascito(A)
        pot = link_dostop._pot()
        with open(pot, "w", encoding="utf-8") as d:            # starejsi program: brez polja »zascita«
            json.dump({"v": 1, "podedovano_ob": 1.0, "naprave": {A: "dp", B: "d"}}, d)
        os.utime(pot, (1, 1))
        self.assertTrue(link_dostop.zna_zascito(A))             # v tem programu velja naprej
        link_dostop.zabelezi_zascito(A)                         # seja je potrjena znova (ob vsakem seznamu naprav)
        zapis = self._zapis()
        self.assertEqual((zapis.get("zascita"), zapis["naprave"]), ([A], {A: "dp", B: "d"}))

    def test_popravilo_zapisa_ki_ne_uspe_se_ne_ponavlja_ob_vsakem_klicu(self):
        link_dostop.nastavi(A, "dp")
        link_dostop.zabelezi_zascito(A)
        pot = link_dostop._pot()
        with open(pot, "w", encoding="utf-8") as d:
            json.dump({"v": 1, "podedovano_ob": 1.0, "naprave": {A: "dp"}}, d)
        os.utime(pot, (1, 1))
        ura = [5000.0]
        with mock.patch.object(link_dostop, "_na_disk", side_effect=OSError(30, "Read-only file system")) as pisi, \
                mock.patch.object(link_dostop.time, "monotonic", lambda: ura[0]):
            for _ in range(5):
                link_dostop.zabelezi_zascito(A)
            self.assertEqual(pisi.call_count, 1)
            ura[0] += 61
            link_dostop.zabelezi_zascito(A)
            self.assertEqual(pisi.call_count, 2)
        self.assertTrue(link_dostop.zna_zascito(A))

    def _neberljiv(self, pot):
        """Popravka, ob katerih zapisa ni mogoce ne pregledati ne prebrati (napaka diska)."""
        pravi_stat, pravi_open = os.stat, open

        def stat(p, *a, **k):
            if p == pot:
                raise OSError(5, "Input/output error")
            return pravi_stat(p, *a, **k)

        def odpri(p, *a, **k):
            if p == pot:
                raise OSError(5, "Input/output error")
            return pravi_open(p, *a, **k)
        return mock.patch.object(link_dostop.os, "stat", stat), mock.patch.object(link_dostop, "open", odpri, create=True)

    def test_zapis_ki_se_ne_da_prebrati_ne_da_dostopa_in_ostane_na_disku(self):
        """Uporabnik je napravi A (ki bi ob prvem zagonu dostop podedovala) dostop vzel, napravi B ga je odprl. Zapis
        je trenutno neberljiv: dostopa nima nihce, spremembe ni mogoce shraniti - in veljavnega zapisa ne prepisemo
        (prej ga je program ob taki napaki zamenjal s praznim)."""
        self.assertEqual(link_dostop.zmoznosti(A), set(link_dostop.VSE_ZMOZNOSTI))     # prvi zagon: podedovano
        link_dostop.nastavi(A, "")
        link_dostop.nastavi(B, "dp")
        pot = link_dostop._pot()
        with open(pot, encoding="utf-8") as d:
            prej = d.read()
        link_dostop._za_preizkus(pot)                           # nov zagon programa
        stat, odpri = self._neberljiv(pot)
        with stat, odpri:
            self.assertEqual((link_dostop.zmoznosti(A), link_dostop.zmoznosti(B)), (set(), set()))
            self.assertFalse(link_dostop.nastavi(B, "d"))
            link_dostop.zabelezi_zascito(A)                     # ne vrze; v tem programu velja
            self.assertTrue(link_dostop.zna_zascito(A))
        with open(pot, encoding="utf-8") as d:
            self.assertEqual(d.read(), prej)
        self.assertEqual((link_dostop.zmoznosti(A), link_dostop.zmoznosti(B)), (set(), {"d", "p"}))     # spet berljiv

    def test_napaka_pri_branju_ni_prvi_zagon(self):
        """Zapis je neberljiv IN pisati se ne da (disk samo za branje): prej je program takrat v pomnilniku znova
        podedoval dostop - naprava A, ki ji ga je uporabnik vzel, ga je dobila nazaj."""
        self.assertEqual(link_dostop.zmoznosti(A), set(link_dostop.VSE_ZMOZNOSTI))
        link_dostop.nastavi(A, "")
        pot = link_dostop._pot()
        link_dostop._za_preizkus(pot)
        stat, odpri = self._neberljiv(pot)
        with stat, odpri, mock.patch.object(link_dostop, "_na_disk", side_effect=OSError(30, "Read-only file system")):
            self.assertEqual(link_dostop.zmoznosti(A), set())
            self.assertEqual(link_dostop.naprave_z(link_dostop.VSE), set())

    def test_zaklep_ki_ga_drzi_zamrznjen_program_ne_ustavi_tega(self):
        """Drug program drzi zaklep zapisa in stoji (zamrznjen): ta program ne sme obstati za vedno - po kratkem
        cakanju pise brez zaklepa (zamenjava datoteke je se vedno en korak)."""
        import fcntl
        import threading
        import time
        link_dostop.nastavi(A, "d")
        pot = link_dostop._pot()
        rocaj = os.open(pot + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(rocaj, fcntl.LOCK_EX)       # »drug program«: zaklep velja na odprto datoteko, tudi v istem procesu
        izid = []
        try:
            with mock.patch.object(link_dostop, "ZAKLEP_CAKA_S", 0.3, create=True):
                nit = threading.Thread(target=lambda: izid.append(link_dostop.nastavi(B, "p")), daemon=True)
                zacetek = time.monotonic()
                nit.start()
                nit.join(5)
                trajalo = time.monotonic() - zacetek
            self.assertFalse(nit.is_alive())
            self.assertEqual(izid, [True])
            self.assertLess(trajalo, 3)
        finally:
            os.close(rocaj)
        self.assertEqual(link_dostop.zmoznosti(B), {"p"})


class SestiPregled(_Osnova):
    """Sesti (ozki) neodvisni pregled sprememb po petem (7. 10. 2026). Vsak preizkus je najprej padel."""

    def test_zapis_drugega_programa_tik_pred_zamenjavo_se_ne_izgubi(self):
        """Ta program je stanje ze prebral in pripravil svoj zapis, ko drug program (ki zaklepa ni dobil - po dveh
        sekundah pise brez njega) napravi A dostop VZAME. Pred zamenjavo datoteke ta program opazi spremembo, prebere
        znova in svojo spremembo doda: odvzem ostane. Prej ga je povozil (najdba sestega pregleda; nastala je z
        omejenim cakanjem na zaklep)."""
        link_dostop.nastavi(A, "dpvz")
        pot = link_dostop._pot()
        pravi_fsync = os.fsync
        klici = []

        def fsync(rocaj):
            pravi_fsync(rocaj)
            if not klici:
                klici.append(1)
                with open(pot, encoding="utf-8") as d:
                    zapis = json.load(d)
                zapis["naprave"][A] = ""                        # drug program: odvzem dostopa
                with open(pot + ".drug", "w", encoding="utf-8") as d:
                    json.dump(zapis, d)
                os.replace(pot + ".drug", pot)
        with mock.patch.object(link_dostop.os, "fsync", fsync):
            self.assertTrue(link_dostop.nastavi(B, "d"))
        self.assertEqual(klici, [1])
        self.assertEqual((link_dostop.zmoznosti(A), link_dostop.zmoznosti(B)), (set(), {"d"}))
        link_dostop._za_preizkus(pot)                           # kot nov zagon programa: stanje z diska
        self.assertEqual((link_dostop.zmoznosti(A), link_dostop.zmoznosti(B)), (set(), {"d"}))
        self.assertEqual(sorted(os.listdir(os.path.dirname(pot))), ["dostop.json", "dostop.json.lock"])

    def test_brez_podpore_za_zaklep_pisanje_ne_caka(self):
        """Datotecni sistem zaklepanja ne podpira (napaka, ki ni »zaseden«): pisemo takoj - prej je vsak zapis cakal
        polni dve sekundi, in z njim vse preverbe dostopa."""
        import time
        link_dostop.nastavi(A, "d")
        with mock.patch("fcntl.flock", side_effect=OSError(37, "No locks available")):
            zacetek = time.monotonic()
            self.assertTrue(link_dostop.nastavi(B, "p"))
            trajalo = time.monotonic() - zacetek
        self.assertLess(trajalo, 0.5)
        self.assertEqual(link_dostop.zmoznosti(B), {"p"})

    def test_zapis_zascite_se_vrne_tudi_ko_je_zapis_izginil_in_ga_ni_bilo_mogoce_ustvariti(self):
        """Zapis izgine in ga takrat ni mogoce ustvariti znova (disk je poln). Ko disk spet dela, se zapis »zascita«
        ob naslednji potrditvi seje vrne na disk (prej je program mislil, da je tam ze)."""
        link_dostop.zabelezi_zascito(A)
        pot = link_dostop._pot()
        os.unlink(pot)
        ura = [1000.0]
        with mock.patch.object(link_dostop.time, "monotonic", lambda: ura[0]):
            with mock.patch.object(link_dostop, "_na_disk", side_effect=OSError(28, "No space left on device")):
                link_dostop.zmoznosti(B)
                self.assertTrue(link_dostop.zna_zascito(A))     # v tem programu velja naprej
            ura[0] += 61
            link_dostop.zabelezi_zascito(A)
        with open(pot, encoding="utf-8") as d:
            self.assertEqual(json.load(d)["zascita"], [A])


class PrviZagon(_Osnova):
    MEJA = link_dostop.MEJA_PODEDOVANJA
    clani = ({"id": "jaz", "kljuc": "KJAZ", "dodano": MEJA - 9000}, {"id": "a", "kljuc": "KA", "dodano": MEJA - 100},
             {"id": "b", "kljuc": "KB", "dodano": MEJA + 68580})

    def test_dosedanje_naprave_obdrzijo_nova_zacne_brez(self):
        self.assertEqual(link_dostop.zmoznosti(A), set(link_dostop.VSE_ZMOZNOSTI))
        self.assertEqual(link_dostop.zmoznosti(B), set())
        self.assertEqual(link_dostop.zmoznosti("b"), set())       # star id iste naprave se prevede prek kljuca
        self.assertEqual(link_dostop.zmoznosti("a"), set(link_dostop.VSE_ZMOZNOSTI))
        with open(link_dostop._pot(), encoding="utf-8") as d:
            self.assertEqual(json.load(d)["naprave"], {A: "dpvz"})

    def test_podeduje_se_samo_enkrat(self):
        link_dostop.zmoznosti(A)
        link_dostop.nastavi(A, "")
        link_dostop._za_preizkus(link_dostop._pot())
        self.assertEqual(link_dostop.zmoznosti(A), set())


class StreznikDatotek(_Osnova):
    def setUp(self):
        super().setUp()
        self.s = link_datoteke.StreznikDatotek(mock.Mock())
        self.s.umaknjena = lambda n: False

    def test_zeton_brez_odprtih_datotek_ne_odpre_datotek(self):
        z = self.s.zeton_za(B)
        self.assertTrue(self.s.zeton_velja(z))                                   # tok z lastno skrivnostjo
        self.assertFalse(self.s.zeton_velja(z, zmoznost="d", oznaka="x"))        # datoteka deljene mape
        link_dostop.nastavi(B, "d")
        self.assertTrue(self.s.zeton_velja(z, zmoznost="d", oznaka="x"))
        link_dostop.nastavi(B, "")                                               # vzet dostop velja takoj
        self.assertFalse(self.s.zeton_velja(z, zmoznost="d", oznaka="x"))

    def test_izrecno_poslana_datoteka_samo_ta_in_samo_branje(self):
        z = self.s.zeton_za(B)
        self.s.dovoli_izrecno(B, "film-1")
        self.assertTrue(self.s.zeton_velja(z, zmoznost="d", oznaka="film-1"))
        self.assertFalse(self.s.zeton_velja(z, zmoznost="d", oznaka="film-2"))
        self.assertFalse(self.s.zeton_velja(z, zmoznost="d"))                    # urejanje: brez oznake
        self.assertFalse(self.s.zeton_velja(self.s.zeton_za(A), zmoznost="d", oznaka="film-1"))   # druga naprava

    def test_izrecno_dovoljenje_potece(self):
        self.s.dovoli_izrecno(B, "film-1", zdaj=1000.0)
        self.assertTrue(self.s.izrecno_dovoljena(B, "film-1", zdaj=1000.0 + link_datoteke.NAJDLJE_S - 1))
        self.assertFalse(self.s.izrecno_dovoljena(B, "film-1", zdaj=1000.0 + link_datoteke.NAJDLJE_S + 1))

    def test_neznana_naprava_nima_dostopa(self):
        z = self.s.zeton_za("naprava")
        self.assertFalse(self.s.zeton_velja(z, zmoznost="d", oznaka="x"))


class RacunalnikZavrneSam(_Osnova):
    """Sprejem na racunalniku (core/safeer_link): napravo brez dostopa zavrne racunalnik sam - nic se ne izvede."""

    def setUp(self):
        super().setUp()
        from core import safeer_link
        self.link = safeer_link.SafeerLink.__new__(safeer_link.SafeerLink)
        self.odzivi = []
        self.link._odziv = lambda vrsta, podatki: self.odzivi.append((vrsta, podatki))
        self.poslano = []
        self.link.povezava = mock.Mock()
        self.link.povezava.poslji = lambda s: self.poslano.append(s) or True
        self.nezasciteno = []
        self.link.povezava.poslji_nezasciteno = lambda s: self.nezasciteno.append(s) or True
        self.link.control = True
        self.link.gledani_zaslon = ""
        self.link.gledani_zaslon_id = ""
        self.link._v_ozadju = mock.Mock()
        self.link._prejmi_zaznamke = mock.Mock()
        p = mock.patch.object(safeer_link.GLib, "idle_add")
        self.idle_add = p.start()
        self.addCleanup(p.stop)
        link_dostop.nastavi(A, "dpvz")

    def _ukaz(self, od, dejanje):
        self.poslano.clear()
        self.idle_add.reset_mock()
        self.link._na_sporocilo_huba({"id": "u1", "type": "control.command", "sender": od,
                                      "payload": {"action": dejanje, "params": {}}})

    def test_ukaz_brez_dostopa_zavrne_racunalnik_in_nic_ne_izvede(self):
        self._ukaz(B, "files.list")
        self.idle_add.assert_not_called()
        self.assertEqual(len(self.poslano), 1)
        o = self.poslano[0]
        self.assertEqual((o["type"], o["target"], o["ref_id"], o["payload"]["action"]), ("control.result", B, "u1", "files.list"))
        self.assertEqual(o["payload"]["data"]["items"], [])
        self.assertFalse(o["payload"]["data"]["shared"])
        for dejanje in ("apps.launch", "screen.start", "open_url", "lists.get", "host.info", "novo.dejanje"):
            self._ukaz(B, dejanje)
            self.idle_add.assert_not_called()
            self.assertEqual(self.poslano[0]["payload"].get("code"), "ni_dovoljeno", dejanje)
        self._ukaz(B, "play.state")
        self.idle_add.assert_not_called()
        self.assertFalse(self.poslano[0]["payload"]["data"]["shared"])

    def test_ukaz_brez_posiljatelja_se_ne_izvede(self):
        self._ukaz("", "files.list")
        self.idle_add.assert_not_called()

    def test_ukaz_naprave_z_dostopom_in_ponudba_gresta_naprej(self):
        self._ukaz(A, "files.list")
        self.idle_add.assert_called_once()
        self.assertEqual(self.poslano, [])
        self._ukaz(B, "play.offer")            # ponudba je prosta: uporabnik jo tu sprejme ali zavrne
        self.idle_add.assert_called_once()

    def test_delni_dostop_odpre_samo_svoje(self):
        link_dostop.nastavi(B, "d")
        self._ukaz(B, "files.list")
        self.idle_add.assert_called_once()
        self._ukaz(B, "apps.list")
        self.idle_add.assert_not_called()

    def test_stran_se_od_naprave_brez_dostopa_ne_odpre_sama(self):
        self.link._na_sporocilo_huba({"id": "c1", "type": "cast.url", "sender": B, "payload": {"url": "https://primer.si/"}})
        self.assertEqual((self.poslano[-1]["type"], self.poslano[-1]["status"]), ("cast.ack", "rejected"))
        self.idle_add.assert_not_called()
        self.assertEqual(self.odzivi, [])
        self.link._na_sporocilo_huba({"id": "c2", "type": "cast.url", "sender": A, "payload": {"url": "https://primer.si/"}})
        self.assertEqual(self.poslano[-1]["status"], "accepted")
        self.idle_add.assert_called_once()

    def test_usklajevanje_samo_od_ozjega_kroga(self):
        self.link._na_sporocilo_huba({"type": "sync.data", "sender": B, "payload": {"category": "bookmarks"}})
        link_dostop.nastavi(B, "dpv")          # tri od stirih: se vedno ni ozji krog
        self.link._na_sporocilo_huba({"type": "sync.data", "sender": B, "payload": {"category": "bookmarks"}})
        self.link._na_sporocilo_huba({"type": "sync.data", "payload": {"category": "bookmarks"}})   # brez posiljatelja
        self.link._prejmi_zaznamke.assert_not_called()
        self.link._na_sporocilo_huba({"type": "sync.data", "sender": A, "payload": {"category": "bookmarks"}})
        self.link._prejmi_zaznamke.assert_called_once()

    def test_nezasciten_ukaz_v_imenu_naprave_z_zascito_se_ne_izvede(self):
        """Naprava A ima poln dostop in zascito zna. Ukaz z njeno oznako, ki pride brez zascite, ni njen."""
        link_dostop.zabelezi_zascito(A)
        self._ukaz(A + "-os", "files.list")
        self.idle_add.assert_not_called()
        # Zavrnitev gre nezascitena tistemu, ki je ukaz poslal (starejsi program iste naprave jo tako lahko prebere);
        # po zasciteni poti ne gre nic.
        self.assertEqual(self.poslano, [])
        self.assertEqual(len(self.nezasciteno), 1)
        o = self.nezasciteno[0]
        self.assertEqual((o["type"], o["target"], o["ref_id"], o["payload"]["code"]), ("control.result", A + "-os", "u1", "zascita"))
        self.assertEqual(set(o["payload"]) - {"ok", "message", "code", "action"}, set())      # brez vsebine
        self.link._na_sporocilo_huba({"id": "c1", "type": "cast.url", "sender": A, "payload": {"url": "https://primer.si/"}})
        self.link._na_sporocilo_huba({"id": "r1", "type": "control.result", "sender": A, "ref_id": "x", "payload": {"ok": True}})
        self.link._na_sporocilo_huba({"id": "h1", "type": "handoff.request", "sender": A, "payload": {"url": "https://primer.si/"}})
        self.idle_add.assert_not_called()
        self.assertEqual(self.odzivi, [])
        self.assertEqual((self.poslano, len(self.nezasciteno)), ([], 1))   # strani in odgovora brez zascite niti ne potrdimo

    def test_zasciten_ukaz_velja_po_kljucu(self):
        link_dostop.zabelezi_zascito(A)
        self.poslano.clear()
        self.link._na_sporocilo_huba({"id": "u1", "type": "control.command", "sender": A + "-os", "_zascita": A,
                                      "payload": {"action": "files.list", "params": {}}})
        self.idle_add.assert_called_once()
        self.assertEqual(self.poslano, [])
        # Zascita dokaze kljuc, ne dovoljenja: naprava B z zascito, a brez dostopa, je zavrnjena kot prej.
        self.idle_add.reset_mock()
        self.link._na_sporocilo_huba({"id": "u2", "type": "control.command", "sender": B, "_zascita": B,
                                      "payload": {"action": "files.list", "params": {}}})
        self.idle_add.assert_not_called()
        self.assertFalse(self.poslano[0]["payload"]["data"]["shared"])
        # Oznaka naprave A, kljuc naprave B: velja kljuc.
        self.idle_add.reset_mock()
        self.link._na_sporocilo_huba({"id": "u3", "type": "control.command", "sender": A, "_zascita": B,
                                      "payload": {"action": "apps.launch", "params": {}}})
        self.idle_add.assert_not_called()

    def test_zaslon_druge_naprave_se_ne_odpre_sam(self):
        start = {"action": "start", "id": "z1", "path": "/cast/screen/z1", "fp": "ab"}
        self.link._na_sporocilo_huba({"type": "share.screen", "sender": B, "payload": start})
        self.assertEqual(self.link.gledani_zaslon, "")
        self.link._v_ozadju.assert_not_called()
        self.link._na_sporocilo_huba({"type": "share.screen", "sender": A, "payload": start})
        self.assertEqual(self.link.gledani_zaslon, A)
        self.link._v_ozadju.assert_called_once()


class _Povezava:
    def __init__(self, naslov="192.168.0.50"):
        self.naslov = naslov
        self.poslano = []
        self.podatki = {}

    def poslji(self, besedilo):
        self.poslano.append(json.loads(besedilo))
        return True

    def zapri(self, *_a, **_k):
        pass

    def vrste(self):
        return [s.get("type") for s in self.poslano]


def _prijava(id_naprave, aplikacije=None):
    tovor = {"device_id": id_naprave, "name": id_naprave, "role": "sender", "capabilities": ["url"], "platform": "phone",
             "protocol": "1"}
    if aplikacije is not None:
        tovor["apps"] = aplikacije
    return json.dumps({"id": "r", "type": "cast.register", "payload": tovor})


class SredisceOddaja(_Osnova):
    def setUp(self):
        super().setUp()
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=JAZ)
        self.p = {i: _Povezava() for i in (A, B, S, S + "-os")}
        for i, pov in self.p.items():
            self.hub.obdelaj(pov, _prijava(i))
        for pov in self.p.values():
            pov.poslano.clear()

    def _oddaj(self, tip, **polja):
        s = {"id": "m1", "type": tip, "payload": {"state": "playing", "title": "zasebno"}}
        s.update(polja)
        return json.loads(self.hub.obdelaj(self.p[S], json.dumps(s)))

    def test_stanje_predvajanja_samo_navedenim(self):
        self.assertEqual(self._oddaj("cast.status", allow=[A])["status"], "accepted")
        self.assertIn("cast.status", self.p[A].vrste())
        self.assertNotIn("cast.status", self.p[B].vrste())
        self.assertIn("cast.status", self.p[S + "-os"].vrste())          # drug program iste naprave
        poslano = [s for s in self.p[A].poslano if s["type"] == "cast.status"][0]
        self.assertNotIn("allow", poslano)                                # seznam je za sredisce, ne gre naprej
        self.assertEqual(poslano["sender"], S)

    def test_starejsi_izvor_brez_seznama(self):
        self._oddaj("cast.status")
        self.assertNotIn("cast.status", self.p[A].vrste())                # izvor ni v ozjem krogu tega racunalnika
        self.assertNotIn("cast.status", self.p[B].vrste())
        link_dostop.nastavi(S, "dpvz")
        link_dostop.nastavi(A, "dpvz")
        self._oddaj("cast.status")
        self.assertIn("cast.status", self.p[A].vrste())                   # naprave istega uporabnika delajo naprej
        self.assertNotIn("cast.status", self.p[B].vrste())

    def test_usklajevanje_samo_navedenim(self):
        self._oddaj("sync.data", target="all", allow=[A])
        self.assertIn("sync.data", self.p[A].vrste())
        self.assertNotIn("sync.data", self.p[B].vrste())
        self._oddaj("sync.request", allow=[])
        self.assertNotIn("sync.request", self.p[A].vrste())
        self.assertNotIn("sync.request", self.p[B].vrste())

    def test_druge_oddaje_in_ciljana_sporocila_gredo_kot_prej(self):
        self._oddaj("share.announce")
        self.assertIn("share.announce", self.p[B].vrste())
        self.hub.obdelaj(self.p[B], json.dumps({"id": "c1", "type": "control.command", "target": A,
                                                "payload": {"action": "files.list"}}))
        ukaz = [s for s in self.p[A].poslano if s["type"] == "control.command"][0]
        self.assertEqual(ukaz["sender"], B)                               # zavrne ga naprava A sama, po posiljatelju

    def test_katalog_programov_ne_gre_v_seznam_naprav(self):
        p = _Povezava()
        self.hub.obdelaj(p, _prijava("n-eeeeeeeeeeeeeeee", {"si.safeer.os": {"name": "Safeer OS"},
                                                           "app:posta.desktop": {"name": "Zasebna posta"}}))
        seznam = [s for s in self.p[B].poslano if s["type"] == "cast.devices"][-1]
        zapis = [d for d in seznam["devices"] if d["id"] == "n-eeeeeeeeeeeeeeee"][0]
        self.assertEqual(list(zapis.get("apps", {})), ["si.safeer.os"])
        self.assertNotIn("Zasebna posta", json.dumps(seznam))


if __name__ == "__main__":
    unittest.main()
