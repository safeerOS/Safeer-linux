"""Domaca mapa za ozji krog (core/link_datoteke.DeljeneMape.dom; pravilo lastnika 25. 10. 2026 10:49, odlocitev vodje):
naprava v ozjem krogu vidi uporabnikove mape brez skritih map, brez datotek s skrivnostmi in brez povezav ven; ves disk
skrivnosti tudi ne da vec."""
import os
import tempfile
import unittest
from unittest import mock

from core import link_datoteke


class DomacaMapa(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dom = os.path.realpath(self._tmp.name)
        for pot, vsebina in (("Dokumenti/pismo.txt", "a"), ("Slike/morje.jpg", "b"), (".ssh/id_ed25519", "k"),
                             (".config/brskalnik/Login Data", "g"), ("kljuc.pem", "p"), ("id_rsa", "r"),
                             ("Dokumenti/gesla.kdbx", "x"), (".local/share/keyrings/login.keyring", "y")):
            cela = os.path.join(self.dom, pot)
            os.makedirs(os.path.dirname(cela), exist_ok=True)
            with open(cela, "w", encoding="utf-8") as d:
                d.write(vsebina)
        os.symlink("/etc", os.path.join(self.dom, "sistem"))
        p = mock.patch.dict(os.environ, {"HOME": self.dom})
        p.start()
        self.addCleanup(p.stop)

    def test_koren_in_seznam_brez_skritih_in_skrivnosti(self):
        m = link_datoteke.DeljeneMape([], dom=True)
        # Nevtralno ime (ne ime mape - navadno uporabnisko ime; sedmi pregled, naloga 6).
        self.assertEqual(m.koren(), [{"id": "dom:", "name": "Home", "type": "folder"}])
        m.jezik = "sl"
        self.assertEqual(m.koren()[0]["name"], "Domača mapa")
        imena = [v["name"] for v in m.seznam("dom:")]
        self.assertEqual(imena, ["Dokumenti", "Slike"], "brez .ssh, .config, kljuc.pem, id_rsa, povezave na /etc")
        self.assertEqual([v["name"] for v in m.seznam("dom:Dokumenti")], ["pismo.txt"], "brez zbirke gesel")
        self.assertEqual(m.razresi("dom:Dokumenti/pismo.txt"), (-2, os.path.join(self.dom, "Dokumenti/pismo.txt")))
        self.assertEqual(m.oznaka_poti(os.path.join(self.dom, "Slike/morje.jpg")), "dom:Slike/morje.jpg")

    def test_izkljucene_poti(self):
        m = link_datoteke.DeljeneMape([], dom=True)
        for oznaka in ("dom:.ssh/id_ed25519", "dom:.ssh", "dom:.config/brskalnik/Login Data",
                       "dom:.local/share/keyrings/login.keyring", "dom:kljuc.pem", "dom:id_rsa",
                       "dom:Dokumenti/gesla.kdbx", "dom:../../etc/passwd", "dom:sistem/passwd", "dom:sistem",
                       "dom:/etc/passwd", "dom:Dokumenti/../.ssh/id_ed25519"):
            self.assertIsNone(m.razresi(oznaka), oznaka)

    def test_brez_ozjega_kroga_ni_domace_mape(self):
        m = link_datoteke.DeljeneMape([])
        self.assertEqual(m.koren(), [])
        self.assertIsNone(m.razresi("dom:Dokumenti/pismo.txt"))
        d = link_datoteke.Datoteke([], tls_mapa=self._tmp.name)
        self.assertFalse(d.seznam("", "n-1")["shared"])

    def test_ves_disk_ne_da_skrivnosti(self):
        m = link_datoteke.DeljeneMape([], ves_disk=True, dom=True)
        self.assertNotIn("dom:", [v["id"] for v in m.koren()], "ves disk ze vsebuje domaco mapo")
        self.assertIsNone(m.razresi("disk:" + os.path.join(self.dom, "kljuc.pem")))
        self.assertIsNone(m.razresi("disk:" + os.path.join(self.dom, "id_rsa")))
        self.assertIsNotNone(m.razresi("disk:" + os.path.join(self.dom, "Dokumenti/pismo.txt")))
        self.assertNotIn("kljuc.pem", [v["name"] for v in m.seznam("disk:" + self.dom)])


if __name__ == "__main__":
    unittest.main()
