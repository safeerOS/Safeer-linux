"""Safeer Link ob prijavi v namizje (lastnik 12. 10. 2026; 13. 10.: brez okna, le tiho obvestilo z gumbom »Poveži«).

Ob prijavi v namizje (delovna povrsina) Safeer OS ponudi povezavo (obvestilo, ki odpre prijavno okno),
razen ce je racunalnik ze povezan, ce je uporabnik v tej seji izbral »brez povezave« ali ce je bilo okno v tej seji
ze pokazano. »Nadaljuj brez povezave« v vgrajenem Controlu samo umakne okno (ne odpre se ene lupine).
"""
import os
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Shramba(dict):
    def set(self, k, v):
        self[k] = v


class _Nastavitve:
    def __init__(self, podatki):
        self.podatki = podatki


class _Link:
    def __init__(self, podatki, v_krogu=False):
        self.nastavitve = _Nastavitve(podatki)
        self._vk = v_krogu

    def _v_krogu(self):
        return self._vk


class _Os:
    def __init__(self):
        self.shramba = _Shramba()
        self.prijav = 0

    def _ponudi_prijavo(self):
        self.prijav += 1


class PrijavnoOknoObPrijavi(unittest.TestCase):
    def setUp(self):
        import safeer_os
        from core import link_seja
        self.so, self.ls = safeer_os, link_seja
        p = mock.patch.object(link_seja, "trenutna_seja", return_value="zagon:seja1")
        p.start()
        self.addCleanup(p.stop)

    def _pozeni(self, podatki, v_krogu=False, os_=None):
        os_ = os_ or _Os()
        c = mock.Mock()
        c.link = _Link(podatki, v_krogu)
        with mock.patch.object(self.so.en_proces, "control_app", return_value=c):
            ponovi = self.so.SafeerOS._prijavno_okno_ob_prijavi(os_)
        return os_, ponovi

    def test_nepovezan_racunalnik_dobi_prijavno_okno(self):
        os_, ponovi = self._pozeni({})
        self.assertEqual((os_.prijav, ponovi), (1, False))

    def test_zaupan_povezan_racunalnik_ne(self):
        os_, _ = self._pozeni({"control_token": "z", "hub_fp": "f", "zaupana": True})
        self.assertEqual(os_.prijav, 0)

    def test_nezaupan_iz_prejsnje_seje_dobi_okno(self):
        os_, _ = self._pozeni({"control_token": "z", "hub_fp": "f", "zaupana": False, "seja_prijave": "staro"})
        self.assertEqual(os_.prijav, 1)

    def test_clan_kroga_ne(self):
        os_, _ = self._pozeni({"zaupana": True}, v_krogu=True)
        self.assertEqual(os_.prijav, 0)

    def test_brez_povezave_v_tej_seji_ne(self):
        os_, _ = self._pozeni({"brez_povezave": "zagon:seja1"})
        self.assertEqual(os_.prijav, 0)

    def test_po_sesutju_v_isti_seji_ne_znova(self):
        os_, _ = self._pozeni({})
        os_, _ = self._pozeni({}, os_=os_)
        self.assertEqual(os_.prijav, 1)

    def test_control_se_ni_pripravljen_pocaka(self):
        os_ = _Os()
        with mock.patch.object(self.so.en_proces, "control_app", return_value=None):
            self.assertTrue(self.so.SafeerOS._prijavno_okno_ob_prijavi(os_))
        self.assertEqual(os_.prijav, 0)

    def test_delovna_povrsina_ob_zagonu_nacrtuje_okno(self):
        vir = open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8").read()
        delovna = vir.split("if self.delovna and not _ima_delovno(self):", 1)[1].split("return", 1)[0]
        self.assertIn("self._ob_namizju()", delovna)
        # Skupno ob zagonu z --delovna in ob poznejsem vklopu (_vklopi_delovno), pregled celovitosti 15. 10. 2026.
        ob_namizju = vir.split("def _ob_namizju(self)", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("self._prijavno_okno_ob_prijavi", ob_namizju)
        vklop = vir.split("def _vklopi_delovno(self)", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("self._ob_namizju()", vklop)

    def test_brez_povezave_v_vgrajenem_controlu_ne_odpre_lupine(self):
        vir = open(os.path.join(KOREN, "safeer_control.py"), encoding="utf-8").read()
        telo = vir.split("def odpri_safeer_os(self)", 1)[1].split("\n    def ", 1)[0]
        vgrajen = telo.index("if VGRAJEN:")
        self.assertLess(vgrajen, telo.index("subprocess.Popen"))
        self.assertIn("self.link.okno.set_visible(False)", telo[vgrajen:telo.index("subprocess.Popen")])   # GTK4: hide()


if __name__ == "__main__":
    unittest.main()


class ObvestiloNamestoOkna(unittest.TestCase):
    def test_ob_zagonu_ni_okna_ampak_obvestilo(self):
        vir = open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8").read()
        telo = vir.split("def _prijavno_okno_ob_prijavi(self)", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("self._ponudi_prijavo()", telo)
        self.assertNotIn("self._prijava()", telo)
        ponudba = vir.split("def _ponudi_prijavo(self)", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("send_notification", ponudba)
        self.assertIn('"app.prijava-iz-obvestila"', ponudba)
