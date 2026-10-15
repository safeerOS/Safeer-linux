"""Vklop Sporocil in posameznih kanalov (lastnik, 15. 10. 2026): izklopljen kanal se ne nalozi, ne steje neprebranih in
ne obvesca, nastavitve ostanejo; izklopljena Sporocila - storitev ne tece. core/sporocila/vklop.py, core/os_sporocila.py."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import os_sporocila
from core.sporocila import vklop
from core.sporocila.model import Kanal


class _Adapter:
    vrsta = "matrix"

    def __init__(self):
        self.zaprt = False

    def zapri(self):
        self.zaprt = True


class Vklop(unittest.TestCase):
    def setUp(self):
        self.mapa = Path(tempfile.mkdtemp())
        self.pot_vklopa = self.mapa / "vklop.json"
        p = mock.patch.object(vklop, "PRIVZETA_POT", self.mapa / "sporocila.sqlite3")
        p.start()
        self.addCleanup(p.stop)

    def test_privzeto_vse_vklopljeno_in_datoteka_zasebna(self):
        self.assertTrue(vklop.sporocila_vklopljena())
        self.assertTrue(vklop.kanal_vklopljen("x"))
        vklop.nastavi_kanal("x", False)
        self.assertEqual(oct(self.pot_vklopa.stat().st_mode & 0o777), "0o600")
        self.assertFalse(vklop.kanal_vklopljen("x"))
        self.assertEqual(vklop.izklopljeni_kanali(), {"x"})
        vklop.pozabi_kanal("x")
        self.assertTrue(vklop.kanal_vklopljen("x"))

    def test_izklopljena_sporocila_izklopijo_vse_kanale(self):
        vklop.nastavi_sporocila(False)
        self.assertFalse(vklop.sporocila_vklopljena())
        self.assertFalse(vklop.kanal_vklopljen("katerikoli"))
        vklop.nastavi_sporocila(True)
        self.assertTrue(vklop.kanal_vklopljen("katerikoli"))

    def test_pokvarjena_datoteka_ne_podre(self):
        self.pot_vklopa.write_text("{nevel", "utf-8")
        self.assertTrue(vklop.sporocila_vklopljena())
        self.pot_vklopa.write_text(json.dumps({"sporocila": True, "izklopljeni": "ni seznam"}), "utf-8")
        self.assertEqual(vklop.izklopljeni_kanali(), set())

    def _sporocila(self, zazeni=False):
        s = os_sporocila.SporocilaOS(self.mapa / "sporocila.sqlite3", zazeni=zazeni)
        self.addCleanup(s.zapri)
        return s

    def test_izklopljen_kanal_ne_tece_in_ne_steje(self):
        s = self._sporocila()
        a = _Adapter()
        s.storitev.registriraj(Kanal("k1", "matrix", "Matrix", "povezan"), a, {"streznik": "https://m.example.org"})
        oseba = s.storitev.graf.dodaj("Ana", [("matrix", "@ana:m")]).id
        with s.storitev.db:
            s.storitev.db.execute("INSERT INTO pogovori(id,kanal_id,oseba_id,zadeva,zadnje_sporocilo,neprebrano,cas,identiteta)"
                                  " VALUES('p1','k1',?,'','zivjo',3,'2026-10-15T10:00:00+00:00','@ana:m')", (oseba,))
        self.assertEqual(sum(g["neprebrano"] for g in s.seznam()["skupine"]), 3)
        self.assertEqual(s.neprebrano_skupaj(), 3)
        with mock.patch.object(s.storitev, "ustavi_kanal", wraps=s.storitev.ustavi_kanal) as ustavi_kanal:
            p = s.vklopi_kanal("k1", False)
        ustavi_kanal.assert_called_once_with("k1")    # sprotna storitev: nit kanala se ustavi
        self.assertTrue(a.zaprt, "izklop zapre povezavo kanala")
        self.assertEqual(s.neprebrano_skupaj(), 0, "kuverta ne steje izklopljenega kanala")
        self.assertNotIn("k1", s.storitev.adapterji, "izklopljen kanal se ne sinhronizira")
        self.assertEqual(p["kanali"][0]["vklopljen"], False)
        self.assertEqual(p["skupine"], [], "pogovori izklopljenega kanala se ne stejejo")
        # Ponovni zagon: izklopljen kanal se ne nalozi; nastavitve so v bazi
        s2 = os_sporocila.SporocilaOS(self.mapa / "sporocila.sqlite3", zazeni=False)
        self.addCleanup(s2.zapri)
        self.assertNotIn("k1", s2.storitev.adapterji)
        self.assertEqual([k["id"] for k in s2.seznam()["kanali"]], ["k1"], "kanal ostane na seznamu")
        s2._samodejno = True
        with mock.patch.object(s2.storitev, "zazeni_kanal") as zazeni_kanal:
            p = s2.vklopi_kanal("k1", True)
        zazeni_kanal.assert_called_once_with("k1")    # nit kanala takoj (sinhronizacija in realni cas)
        self.assertIn("k1", s2.storitev.adapterji, "vklop ga takoj nalozi")
        self.assertEqual(sum(g["neprebrano"] for g in p["skupine"]), 3)
        with self.assertRaises(ValueError):
            s2.vklopi_kanal("ni-ga", False)

    def test_izklopljen_safeer_chat_shrani_tiho(self):
        s = self._sporocila()
        self.assertTrue(s.prejmi_klepet("telefon", "Telefon", "prvo", sid="1"))
        vklop.nastavi_kanal(os_sporocila.KANAL_LINKA, False)
        self.assertFalse(s.prejmi_klepet("telefon", "Telefon", "drugo", sid="2"), "brez obvestila")
        vrstice = s.storitev.db.execute("SELECT neprebrano FROM pogovori WHERE kanal_id=?", (os_sporocila.KANAL_LINKA,)).fetchall()
        self.assertEqual([r[0] for r in vrstice], [1], "tiho sporocilo se ne steje")
        self.assertEqual(len(s.storitev.sporocila(os_sporocila.KANAL_LINKA, "telefon")), 2, "nicesar ne izgubimo")

    def test_izklopljena_sporocila_ne_zazenejo_storitve(self):
        s = self._sporocila()
        s.storitev.registriraj(Kanal("k1", "matrix", "Matrix", "povezan"), _Adapter(), {})
        vklop.nastavi_sporocila(False)
        with mock.patch.object(os_sporocila.SporocilaOS, "_adapter", lambda *a: _Adapter()):
            s2 = self._sporocila(zazeni=True)
        self.assertEqual(s2.storitev.delavci(), {}, "storitev ne tece (nic ne preverja poste)")
        self.assertFalse(getattr(s2.storitev, "_tece", False))
        vklop.nastavi_sporocila(True)
        with mock.patch.object(s2.storitev, "zazeni") as zazeni:
            s2.nadaljuj()
        zazeni.assert_called_once()


if __name__ == "__main__":
    unittest.main()
