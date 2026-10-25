"""Pravilo lastnika 25. 10. 2026 10:49 (velja povsod): naprava, ki jo uporabnik da v ozji krog, dobi z ISTO privolitvijo
upravljanje tega racunalnika in Safeer Vnos (core/link_dostop.ozji_krog); obvestilo to pove, preden uporabnik pritisne
»Dovoli«; umik iz kroga ali odvzem upravljanja tekoco sejo zaslona konca takoj (AGENTS.md), ne sele ob odhodu gledalca.
"""
import json
import os
import threading
import unittest
from unittest import mock

import pytest

from core import link_dostop, link_zaslon
from tests.test_link_dostop import A, B, _Osnova

pytestmark = pytest.mark.pravi_dostop


class Pravilo(unittest.TestCase):
    def test_ozji_krog_doda_upravljanje(self):
        self.assertEqual(link_dostop.ozji_krog(set()), set())
        self.assertEqual(link_dostop.ozji_krog("d"), {"d", "z"})
        self.assertEqual(link_dostop.ozji_krog({"v", "x"}), {"v", "d", "z"}, "neznana crka ne steje")
        self.assertEqual(link_dostop.ozji_krog("z"), {"d", "z"}, "ozji krog: tudi mape")
        self.assertEqual(link_dostop.ozji_krog("dpvz"), set(link_dostop.VSE_ZMOZNOSTI))


class EnaPrivolitev(_Osnova):
    def test_katerokoli_dovoljenje_odpre_upravljanje_in_vnos(self):
        # Stikala okna Link (izrecna privolitev): nastavi_ozji_krog; nastavi sam je natancen (test_ozji_krog_pregled7).
        self.assertTrue(link_dostop.nastavi_ozji_krog(B, "d"))
        self.assertEqual(link_dostop.zmoznosti(B), {"d", "z"})
        self.assertTrue(link_dostop.sme_dejanje(B, "screen.start"))
        self.assertTrue(link_dostop.sme_dejanje(B, "input.key"), "Safeer Vnos z isto privolitvijo")
        self.assertFalse(link_dostop.sme_dejanje(B, "apps.list"), "drugih zmoznosti ne doda")
        link_dostop.nastavi_ozji_krog(B, "")
        self.assertEqual(link_dostop.zmoznosti(B), set(), "umik iz kroga vzame vse")
        self.assertFalse(link_dostop.sme_dejanje(B, "input.key"))

    def test_dovoli_v_obvestilu_pove_in_doda_upravljanje(self):
        prosnja = {"jedro": B, "zmoznost": "d", "ime": "Tablica"}
        telo = link_dostop.telo_obvestila(prosnja, "sl")
        self.assertIn("ožji krog", telo)
        self.assertIn("Safeer Vnos", telo)
        for jezik in ("en", "de", "es", "fr", "it"):
            self.assertNotEqual(link_dostop.telo_obvestila(prosnja, jezik), link_dostop.telo_obvestila(
                dict(prosnja, zmoznost="z"), jezik), jezik)
        self.assertNotIn("ožji krog", link_dostop.telo_obvestila(dict(prosnja, zmoznost="dz"), "sl"),
                         "ce prosi za upravljanje in mape, ju obvestilo ze nasteje")
        with mock.patch.object(link_dostop, "_prosnje", {link_dostop.kljuc_prosnje(B, "d"): 1.0,
                                                          link_dostop.kljuc_prosnje(B, "z"): 1.0}), \
                mock.patch.object(link_dostop, "_osvezi_prikaz"), mock.patch.object(link_dostop, "_pocisti_prosnje"):
            self.assertTrue(link_dostop.odobri_prosnjo(B, "d"))
            self.assertEqual(link_dostop._prosnje, {}, "prosnja za upravljanje ne caka vec")
        self.assertEqual(link_dostop.zmoznosti(B), {"d", "z"})
        self.assertNotIn("ožji krog", link_dostop.telo_obvestila({"jedro": B, "zmoznost": "p"}, "sl"),
                         "naprava je ze v ozjem krogu")

    def test_star_zapis_brez_upravljanja_se_ne_siri_sam(self):
        pot = link_dostop._pot()
        with open(pot, "w", encoding="utf-8") as d:
            json.dump({"v": 1, "podedovano_ob": 1.0, "naprave": {B: "d"}}, d)
        os.chmod(pot, 0o600)
        link_dostop._za_preizkus(pot)
        self.assertEqual(link_dostop.zmoznosti(B), {"d"}, "brez nove privolitve uporabnika nic vec")


class _Odjemalec:
    def __init__(self):
        self.poslano = []

    def sendall(self, podatki):
        self.poslano.append(bytes(podatki))


class SejaZaslona(unittest.TestCase):
    def _seja(self, dostop):
        z = link_zaslon.Zaslon(vklopljeno=True)
        z._naprava, z._povezan, z._seja_st = B, True, 7
        z._odjemalec = _Odjemalec()
        z.dostop = dostop
        z.ustavi = mock.Mock()
        return z

    def test_odvzem_konca_sejo_takoj(self):
        z = self._seja(lambda naprava: False)
        self.assertTrue(z.preveri_dostop())
        # Gledalec izve, zakaj je konec - obvestilo poslje ustavi() v svoji niti, ko sta zajem in vnos ze ustavljena.
        z.ustavi.assert_called_once_with(seja=7, obvestilo={"konec": "dostop"})

    def test_z_dostopom_seja_tece(self):
        z = self._seja(lambda naprava: naprava == B)
        self.assertFalse(z.preveri_dostop())
        z.ustavi.assert_not_called()

    def test_napaka_branja_je_ne(self):
        def pade(_n):
            raise link_dostop.NapakaBranja("disk")
        z = self._seja(pade)
        self.assertTrue(z.preveri_dostop())

    def test_straza_preverja_med_sejo(self):
        klici = []
        z = self._seja(lambda naprava: klici.append(naprava) or len(klici) < 2)
        konec = threading.Event()
        with mock.patch.object(link_zaslon, "DOSTOP_PREVERI_S", 0.01):
            nit = threading.Thread(target=z._strazi_dostop, args=(7, konec), daemon=True)
            nit.start()
            nit.join(2.0)
        konec.set()
        self.assertFalse(nit.is_alive())
        z.ustavi.assert_called_once_with(seja=7, obvestilo={"konec": "dostop"})

    def test_brez_seje_ni_dela(self):
        z = link_zaslon.Zaslon(vklopljeno=True)
        z.dostop = lambda naprava: False
        z.ustavi = mock.Mock()
        self.assertFalse(z.preveri_dostop())
        z.ustavi.assert_not_called()


class SafeerLinkOdvzem(_Osnova):
    def test_sprememba_dostopa_preveri_sejo(self):
        from core import safeer_link
        link = safeer_link.SafeerLink.__new__(safeer_link.SafeerLink)
        link.naprave, link.naprave_vse = [], None
        link._odziv = lambda *a: None
        link.zaslon = mock.Mock()
        link._v_ozadju = lambda f: f()          # preverba gre v delovno nit (ne na glavno); tu takoj
        link._po_spremembi_dostopa(A, True)
        link.zaslon.preveri_dostop.assert_called_once_with()


class OknoLink(unittest.TestCase):
    def test_ozji_krog_je_prvo_stikalo_in_vodi_ostala(self):
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "assets", "link", "index.html"), encoding="utf-8") as d:
            html = d.read()
        blok = html[html.index('id="dostopBlok"'):]
        self.assertLess(blok.index('id="dostop_z"'), blok.index('id="dostop_p"'))
        with open(os.path.join(koren, "assets", "link", "link.js"), encoding="utf-8") as d:
            js = d.read()
        self.assertEqual(js.count('dostopZaslon: "'), 6, "besedilo v vseh 6 jezikih")
        self.assertNotIn('id="dostop_d"', blok, "mape so del ozjega kroga, ne posebno stikalo")
        self.assertIn("Safeer Vnos", js)
