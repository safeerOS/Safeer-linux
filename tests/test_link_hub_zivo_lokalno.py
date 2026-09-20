"""Hub racunalnika v zivo: pravi odjemalec Safeer Linka se prijavi cez TLS in WebSocket.

To je preizkus cele zice, ne le logike: potrdilo, rokovanje, vstopnica s podpisom, prijava,
seznam naprav in posredovanje med dvema napravama. Ce je tu zeleno, zna racunalnik biti sredisce.
"""
import json
import threading
import time
import unittest
from unittest import mock

from core import link_hub, link_hub_streznik, link_krog


class HubVZivo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.streznik = link_hub_streznik.HubStreznik()
        if not cls.streznik.zazeni():
            raise unittest.SkipTest("huba ni bilo mogoce zagnati")
        cls.naslov = "wss://127.0.0.1:%d%s" % (cls.streznik.vrata, link_hub_streznik.POT_WS)
        cls.odtis = cls.streznik.odtis
        # V krogu smo mi sami: vsaka "naprava" v tem preizkusu se podpise z istim kljucem
        # racunalnika, kar je natanko tisto, kar Hub preverja.
        cls.clan = {"kljuc": link_krog.javni_kljuc_b64(), "ime": "Preizkus", "platforma": "linux"}

    @classmethod
    def tearDownClass(cls):
        cls.streznik.ustavi()

    def _povezava(self, device_id, ime="Preizkus", sinhronizira=False):
        p = link_hub.Povezava(self.naslov, "", device_id, ime, odtis=self.odtis)
        p.v_krog = True
        return p

    def _s_krogom(self):
        """Krog, ki vsako napravo prepozna po nasem kljucu (podpisujemo z istim kljucem)."""
        lazni = mock.MagicMock()
        lazni.clan_za_id.return_value = self.clan
        lazni.json.return_value = {"v": 1, "clani": {}, "umiki": {}}
        return mock.patch.object(link_krog, "krog", return_value=lazni)

    def test_a_hub_se_predstavi(self):
        """je_hub mora Hub prepoznati - sicer ga odjemalci sploh ne bodo poskusili."""
        osnova = link_hub._osnova(self.naslov)
        self.assertTrue(link_hub.je_hub(osnova, odtis=self.odtis), "Hub se mora prepoznati")

    def test_b_prijava_s_podpisom_in_seznam(self):
        with self._s_krogom(), mock.patch.object(link_krog, "lahko_s_podpisom", return_value=True), \
                mock.patch.object(link_krog, "sprejmi", return_value=True):
            naprave = []
            dogodek = threading.Event()
            p = self._povezava("n-0123456789abcdef", "Tablica")
            p.ob_sporocilu = lambda s: (naprave.append(s), dogodek.set()) if s.get("type") == "cast.devices" else None
            self.assertTrue(p.poveži(), "prijava s podpisom mora uspeti")
            try:
                self.assertTrue(dogodek.wait(5), "po prijavi mora priti seznam naprav")
                self.assertTrue(p.prijava_s_podpisom, "prijava je sla s podpisom, ne z zetonom")
                ids = [d["id"] for d in naprave[-1]["devices"]]
                self.assertEqual(ids, ["n-0123456789abcdef"])
            finally:
                p.zapri()

    def test_c_dve_napravi_se_vidita_in_si_posiljata(self):
        with self._s_krogom(), mock.patch.object(link_krog, "lahko_s_podpisom", return_value=True), \
                mock.patch.object(link_krog, "sprejmi", return_value=True):
            prejeto_b = []
            dogodek_b = threading.Event()
            potrditve_a = []
            a = self._povezava("n-aaaaaaaaaaaaaaaa", "Racunalnik")
            b = self._povezava("n-bbbbbbbbbbbbbbbb", "Tablica")
            potrjeno_a = threading.Event()

            def na_a(s):
                potrditve_a.append(s)
                if s.get("type") == "control.ack":
                    potrjeno_a.set()

            a.ob_sporocilu = na_a

            def na_b(s):
                prejeto_b.append(s)
                if s.get("type") == "control.command":
                    dogodek_b.set()

            b.ob_sporocilu = na_b
            self.assertTrue(a.poveži())
            try:
                self.assertTrue(b.poveži())
                try:
                    time.sleep(0.6)
                    self.assertTrue(a.poslji({"id": "u1", "type": "control.command",
                                              "target": "n-bbbbbbbbbbbbbbbb",
                                              "payload": {"action": "status"}}))
                    self.assertTrue(dogodek_b.wait(5), "ukaz mora priti do druge naprave")
                    self.assertTrue(potrjeno_a.wait(5), "posiljatelj mora dobiti potrditev")
                    ukaz = [s for s in prejeto_b if s.get("type") == "control.command"][-1]
                    self.assertEqual(ukaz["sender"], "n-aaaaaaaaaaaaaaaa", "Hub vpise posiljatelja")
                    self.assertEqual(ukaz["payload"]["action"], "status")
                    potrditev = [s for s in potrditve_a if s.get("type") == "control.ack"]
                    self.assertTrue(potrditev and potrditev[-1]["status"] == "accepted", potrditve_a)
                    # Seznam naprav mora imeti obe
                    seznami = [s for s in potrditve_a if s.get("type") == "cast.devices"]
                    self.assertTrue(any(len(s["devices"]) == 2 for s in seznami),
                                    [len(s["devices"]) for s in seznami])
                finally:
                    b.zapri()
            finally:
                a.zapri()

    def test_d_naprava_zunaj_kroga_ne_pride_noter(self):
        lazni = mock.MagicMock()
        lazni.clan_za_id.return_value = None      # te naprave v krogu ni
        lazni.json.return_value = {}
        with mock.patch.object(link_krog, "krog", return_value=lazni), \
                mock.patch.object(link_krog, "lahko_s_podpisom", return_value=True):
            p = self._povezava("n-ffffffffffffffff", "Tujec")
            try:
                self.assertFalse(p.poveži(), "naprave zunaj kroga Hub ne sme spustiti")
            finally:
                p.zapri()

    def test_e_brez_vstopnice_ni_povezave(self):
        """Neposredna povezava na /cast/ws brez vstopnice mora pasti."""
        odjemalec = link_hub.WsOdjemalec(self.naslov, odtis=self.odtis)
        with self.assertRaises(Exception):
            odjemalec.odpri()


if __name__ == "__main__":
    unittest.main()
