"""Hub, s katerim je naprava ze seznanjena, ima pri iskanju prednost pred izvoljenim hubom kroga (11. 10. 2026:
nezaupan racunalnik se je preselil na hub telefona, kjer zetona nima, in ostal na prijavnem oknu)."""
import unittest
from unittest import mock

from core import link_hub

TV = {"naslov": "wss://tv.local:8990/cast/ws", "fp": "aa" * 32, "tls": True, "id": "tv"}
TEL = {"naslov": "wss://tel.local:8990/cast/ws", "fp": "bb" * 32, "tls": True, "id": "tel"}


class Prednost(unittest.TestCase):
    def poisci(self, seznanjeni):
        krog = mock.Mock()
        krog.clan.side_effect = lambda i: {"kljuc": "K"} if i == "tel" else None
        with mock.patch.object(link_hub, "poisci_hube_mdns", return_value=[TEL, TV]), \
                mock.patch.object(link_hub, "je_hub", return_value=True), \
                mock.patch.object(link_hub.link_krog, "krog", return_value=krog), \
                mock.patch.object(link_hub.link_tls, "potrdilo_huba", return_value=(TEL["fp"], "K")):
            return link_hub.poisci_hub_z_odtisom("", None, seznanjeni)

    def test_seznanjeni_pred_krogom(self):
        self.assertEqual(self.poisci((TV["fp"],))["naslov"], TV["naslov"])

    def test_brez_seznanitve_izvoljeni_hub(self):
        n = self.poisci(())
        self.assertEqual((n["naslov"], n.get("krog")), (TEL["naslov"], True))


if __name__ == "__main__":
    unittest.main()
