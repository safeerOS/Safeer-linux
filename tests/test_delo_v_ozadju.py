"""Delo za druge naprave v Linku: pomoc v zivo po zmogljivosti, delo v ozadju sele po 10 min brez uporabe.

Lastnik 5. 11. 2026: »Ce je naprava povezana v Safeer Link in je prosta, je njena dolznost, da pomaga, kjer lahko.«
Pomoc je brez vprasanj, zato delo v ozadju (shranjevanje datotek drugih, pretvorba za kasneje) ne sme motiti
uporabnika, ki dela za racunalnikom. Film, ki ga nekdo gleda zdaj, ne caka.
"""
import unittest
from unittest import mock

from core import delo_v_ozadju as dvo

PROST = {"lahko": True, "razlog": ""}


class Presoja(unittest.TestCase):
    def test_v_zivo_ne_caka_na_nedejavnost(self):
        for dejanje in ("video.stream", "magnet.stream"):
            self.assertEqual(dvo.presodi(dejanje, PROST, 0.0), {"lahko": True, "razlog": ""}, dejanje)
            self.assertTrue(dvo.presodi(dejanje, PROST, None)["lahko"], "namizje ne pove: v zivo vseeno pomaga")

    def test_v_ozadju_sele_po_10_minutah(self):
        for dejanje in ("storage.put", "video.transcode"):
            self.assertEqual(dvo.presodi(dejanje, PROST, 599.0), {"lahko": False, "razlog": "v_uporabi"}, dejanje)
            self.assertTrue(dvo.presodi(dejanje, PROST, 600.0)["lahko"], dejanje)
            self.assertTrue(dvo.presodi(dejanje, PROST, 3600.0)["lahko"], dejanje)

    def test_neznana_nedejavnost_je_uporaba(self):
        self.assertEqual(dvo.presodi("storage.put", PROST, None), {"lahko": False, "razlog": "v_uporabi"})

    def test_zmogljivost_odloca_vedno(self):
        zaseden = {"lahko": False, "razlog": "baterija"}
        for dejanje in ("video.stream", "storage.put"):
            self.assertEqual(dvo.presodi(dejanje, zaseden, 3600.0), {"lahko": False, "razlog": "baterija"})

    def test_za_host_info(self):
        self.assertEqual(dvo.za_host_info(PROST, 30.0), {"ozadje": False, "razlog_ozadja": "v_uporabi"})
        self.assertEqual(dvo.za_host_info(PROST, 900.0), {"ozadje": True, "razlog_ozadja": ""})
        self.assertEqual(dvo.za_host_info({"lahko": False, "razlog": "preobremenjen"}, 900.0),
                         {"ozadje": False, "razlog_ozadja": "preobremenjen"})

    def test_nedejavnost_brez_namizja_ne_vrze(self):
        with mock.patch("core.nova_razlicica.nedejavnost_s", side_effect=RuntimeError("ni vodila")):
            self.assertIsNone(dvo.nedejavnost_s())


class HostInfo(unittest.TestCase):
    """host.info pove napravam, ali ta racunalnik zdaj sprejme delo v ozadju; pomoc v zivo ostane po `lahko`."""

    def test_podatki_hosta(self):
        from core import link_daljinec
        with mock.patch.object(dvo, "nedejavnost_s", return_value=5.0), \
                mock.patch.object(link_daljinec, "pomoc", return_value={"lahko": True, "razlog": ""}), \
                mock.patch.object(link_daljinec, "_graficna", return_value={}):
            p = link_daljinec.podatki_hosta()
        self.assertEqual(p["pomoc"], {"lahko": True, "razlog": "", "ozadje": False, "razlog_ozadja": "v_uporabi"})
        with mock.patch.object(dvo, "nedejavnost_s", return_value=700.0), \
                mock.patch.object(link_daljinec, "pomoc", return_value={"lahko": True, "razlog": ""}), \
                mock.patch.object(link_daljinec, "_graficna", return_value={}):
            self.assertTrue(link_daljinec.podatki_hosta()["pomoc"]["ozadje"])


class Izbira(unittest.TestCase):
    """Racunalnik, ki da delo v ozadju drugim, ne izbere naprave, ki zdaj ni prosta (`ozadje` False)."""

    def _naprava(self, ozadje):
        pomoc = {"lahko": True, "razlog": ""}
        if ozadje is not None:
            pomoc.update(ozadje=ozadje, razlog_ozadja="" if ozadje else "v_uporabi")
        return {"pomoc": pomoc, "disk": {"prosto": 50 * 1024 ** 3, "skupaj": 64 * 1024 ** 3}}

    def test_shramba(self):
        from core import link_shramba
        naprave = [{"id": "tv", "zmoznosti": ["files"], "platforma": "android"}]
        for ozadje, pricakovano in ((False, None), (True, "tv"), (None, "tv")):   # None: starejsa naprava brez polja
            izbrana = link_shramba.izberi_cilj(naprave, lambda _i, _d, _p: {"ok": True, "data": self._naprava(ozadje)},
                                               1024)
            self.assertEqual(izbrana and izbrana["id"], pricakovano, ozadje)

    def test_pretvorba(self):
        from core import link_pretvorba
        self.assertIn("v_uporabi", link_pretvorba._izlocitev(self._naprava(False), 1024, None))
        d = self._naprava(None)
        self.assertNotIn("ne sme pomagati", link_pretvorba._izlocitev(d, 1024, None), "starejsa naprava brez polja")


if __name__ == "__main__":
    unittest.main()
