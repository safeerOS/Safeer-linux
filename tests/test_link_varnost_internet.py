"""Varnost Linka, tocka 3 (pregled TV 10. 11. 2026): internet prek telefona na namizju. Umik naprave iz kroga takoj
konca njene tokove in pozabi izbiro; internet.* samo od naprave v krogu ali izrecno izbranega telefona, nikoli od
umaknjene. Brez omrezja: tokovi in krog so nadomestki."""
import json
import os
import re
import shutil
import tempfile
import unittest
from unittest import mock

from core import link_dostop, link_internet, link_internet_posrednik as lp

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JEDRO_TEL = "n-0123456789abcdef"
JEDRO_DRUG = "n-fedcba9876543210"


class LazenTok:
    def __init__(self, naprava):
        self.naprava, self.razlogi = naprava, []

    def prekini(self, razlog, obvesti=True):
        self.razlogi.append(razlog)

    def opis(self):
        return {"naprava": self.naprava}


class Sporocila(unittest.TestCase):
    def test_samo_od_zaupane_naprave(self):
        zaupane = {JEDRO_TEL}
        i = link_internet.InternetPrekLinka(lambda s: True, zaupan=lambda od: od in zaupane)
        stanja = []
        i.ob_stanju = lambda n, t: stanja.append(n)
        tok = LazenTok(JEDRO_DRUG)
        i._tokovi["s1"] = tok
        self.assertTrue(i.obdelaj({"type": "internet.status", "sender": JEDRO_DRUG, "payload": {"protocol": 2}}))
        self.assertTrue(i.obdelaj({"type": "internet.close", "sender": JEDRO_DRUG, "stream_id": "s1"}))
        self.assertTrue(i.obdelaj({"type": "internet.status", "sender": "", "payload": {"protocol": 2}}))
        self.assertEqual(stanja, [])
        self.assertIsNone(i.znano_stanje(JEDRO_DRUG))
        i.obdelaj({"type": "internet.status", "sender": JEDRO_TEL, "payload": {"protocol": 2}})
        self.assertEqual(stanja, [JEDRO_TEL])
        self.assertEqual(tok.razlogi, [], "tuja naprava toka ne konca")

    def test_zapri_napravo(self):
        i = link_internet.InternetPrekLinka(lambda s: True)
        a, b = LazenTok(JEDRO_TEL), LazenTok(JEDRO_DRUG)
        i._tokovi.update({"s1": a, "s2": b})
        i._ponudniki[JEDRO_TEL] = {"protokol": 2, "stanje": {}, "cas": 0.0}
        self.assertEqual(i.zapri_napravo(JEDRO_TEL), 1)
        self.assertEqual((a.razlogi, b.razlogi), (["revoked"], []))
        self.assertIsNone(i.znano_stanje(JEDRO_TEL))

    def test_control_poda_preverbo(self):
        vir = open(os.path.join(KOREN, "safeer_control.py"), encoding="utf-8").read()
        self.assertRegex(vir, r"InternetPrekLinka\(\s*lambda s: [^\n]+\n\s*zaupan=lambda od: self\.internet\.sme_sporocati\(od\)\)")


class Upravitelj(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-varnost-internet-")
        self.pot = os.path.join(self.mapa, "internet.json")
        self.internet = link_internet.InternetPrekLinka(lambda s: True)
        self.naprave = [{"id": JEDRO_TEL, "ime": "Telefon", "zmoznosti": ["internet.gateway"]}]
        self.umaknjene = set()
        self.p = mock.patch.object(lp, "umaknjena", side_effect=lambda i: i in self.umaknjene)
        self.p.start()
        self.u = lp.InternetUpravitelj(self.internet, lambda: self.naprave, self.pot,
                                       sonda=lp.Sonda(lambda _d: None, cilji=(("x", 1),), dosegljiv=lambda _c, _r: True))
        self.u.zaupana = lambda i: i == JEDRO_TEL and i not in self.umaknjene
        self.u.nastavi(naprava=JEDRO_TEL)

    def tearDown(self):
        self.p.stop()
        self.u.ustavi()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_umik_konca_tokove_in_pozabi_izbiro(self):
        tok = LazenTok(JEDRO_TEL)
        self.internet._tokovi["s1"] = tok
        self.assertEqual(self.u.telefon(), JEDRO_TEL)
        self.u.ob_odvzemu(JEDRO_TEL)                       # odvzem dostopa, a naprava ostane v krogu: nic
        self.assertEqual((tok.razlogi, self.u.naprava), ([], JEDRO_TEL))
        self.umaknjene.add(JEDRO_TEL)
        self.assertIsNone(self.u.telefon(), "umaknjen izbrani telefon ne dobi prometa")
        link_dostop._po_odvzemu(JEDRO_TEL)                 # isti klic kot ob umiku iz kroga (core/link_krog)
        self.assertEqual(tok.razlogi, ["revoked"])
        self.assertEqual(self.u.naprava, "")
        with open(self.pot, encoding="utf-8") as d:
            self.assertEqual(json.load(d)["naprava"], "")

    def test_kdo_sme_sporocati(self):
        self.assertTrue(self.u.sme_sporocati(JEDRO_TEL))
        self.u.zaupana = lambda _i: False
        self.assertTrue(self.u.sme_sporocati(JEDRO_TEL), "izrecno izbran telefon (tudi zunaj kroga)")
        self.assertFalse(self.u.sme_sporocati(JEDRO_DRUG))
        self.assertFalse(self.u.sme_sporocati(""))
        self.umaknjene.add(JEDRO_TEL)
        self.assertFalse(self.u.sme_sporocati(JEDRO_TEL), "umaknjena nikoli")


class Krog(unittest.TestCase):
    def test_umaknjena_po_krogu(self):
        with mock.patch("core.link_krog.je_umaknjen", side_effect=lambda i: i == JEDRO_DRUG):
            self.assertTrue(lp.umaknjena(JEDRO_DRUG))
            self.assertFalse(lp.umaknjena(JEDRO_TEL))
        self.assertTrue(re.fullmatch(r"n-[0-9a-f]{16}", lp._jedro_naprave(JEDRO_TEL)))


if __name__ == "__main__":
    unittest.main()
