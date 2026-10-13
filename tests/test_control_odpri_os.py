"""»Odpri Safeer OS« in »Safeer brskalnik« z druge naprave na racunalniku (launch_app).
Do 13. 10. 2026 Control ukaza launch_app ni poznal: odgovor je bil »Neznano dejanje«, okno je ostalo pri »Odpiram …«."""
import os
import sys
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec  # noqa: E402


class OdpriSafeerOs(unittest.TestCase):
    def _izvedi(self, parametri):
        izidi = []
        link_daljinec.izvedi_control("launch_app", parametri, lambda u: None, izidi.append)
        self.assertEqual(len(izidi), 1)
        return izidi[0]

    def test_safeer_os_se_zazene(self):
        zagnani = []
        with mock.patch.object(link_daljinec, "_safeer_os", return_value="/app/bin/safeer-os"), \
             mock.patch("subprocess.Popen", side_effect=lambda ukaz, **_k: zagnani.append(ukaz)):
            for paket in ("si.safeer.os", "si.safeer.tablet"):
                i = self._izvedi({"package": paket})
                self.assertTrue(i["ok"], i)
        self.assertEqual(zagnani, [["/app/bin/safeer-os"], ["/app/bin/safeer-os"]])

    def test_brskalnik_safeer_browser_sicer_safeer_os(self):
        zagnani = []
        with mock.patch.object(link_daljinec, "_safeer_os", return_value="/usr/bin/safeer-os"), \
             mock.patch("subprocess.Popen", side_effect=lambda ukaz, **_k: zagnani.append(ukaz)):
            with mock.patch.object(link_daljinec, "_safeer_browser", return_value="/usr/bin/safeer-browser"):
                self.assertTrue(self._izvedi({"package": "si.safeer.tv"})["ok"])
            with mock.patch.object(link_daljinec, "_safeer_browser", return_value=""):
                self.assertTrue(self._izvedi({"package": "si.safeer.tv"})["ok"])
        self.assertEqual(zagnani, [["/usr/bin/safeer-browser"], ["/usr/bin/safeer-os"]])

    def test_ni_namescen_ali_tuj_paket(self):
        with mock.patch.object(link_daljinec, "_safeer_os", return_value=""), \
             mock.patch("subprocess.Popen") as popen:
            i = self._izvedi({"package": "si.safeer.os"})
            self.assertFalse(i["ok"])
            self.assertEqual(i["code"] if "code" in i else i.get("koda"), "ni_programa")
            # Aplikacij Android (YouTube na televizorju ipd.) racunalnik nima in jih ne zaganja.
            self.assertFalse(self._izvedi({"package": "com.google.android.youtube.tv"})["ok"])
            self.assertFalse(self._izvedi({})["ok"])
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
