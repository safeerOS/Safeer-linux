"""Seznami predvajanja med napravami v Safeer Linku na Linuxu: Control odgovarja (lists.get), Safeer OS prevzema."""
import json
import os
import tempfile
import unittest
from unittest import mock

from core import link_daljinec, link_seznami, os_media, seznami_sink

SKLADBE = [{"naslov": "Pesem %d" % i, "izvajalec": "Pevka", "youtube": "59o4m222aV%s" % "wxyz"[i % 4], "sekund": 200 + i,
            "slika": "https://i.ytimg.com/vi/x/hq.jpg", "interno": "ne gre naprej"} for i in range(230)]


class IzvozTests(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        with open(os.path.join(self.mapa.name, "seznami.json"), "w", encoding="utf-8") as f:
            json.dump([{"ime": "Uspešnice", "vir": "Spotify", "cas": 1790000000000, "skladbe": SKLADBE},
                       {"ime": "Kratek", "cas": 5, "skladbe": SKLADBE[:2]},
                       {"ime": "", "skladbe": []}, "smeti", {"ime": "Brez skladb"}], f)
        with open(os.path.join(self.mapa.name, "seznami_izbrisani.json"), "w", encoding="utf-8") as f:
            json.dump({"Star": 1780000000000, "Slab": "x", "Nic": 0}, f)

    def test_odgovor_je_enak_kot_v_jedru_medijskega_centra(self):
        """Control bere sam (brez jedra kataloga); odgovor mora biti do pike enak MediaCenter.seznami_izvoz."""
        mc = os_media.MediaCenter(self.mapa.name, roots=[])
        for parametri in ({}, None, {"ime": "Uspešnice"}, {"ime": "Uspešnice", "od": 100}, {"ime": "Uspešnice", "od": 200},
                          {"ime": "Uspešnice", "od": 5000}, {"ime": "Uspešnice", "od": "x"}, {"ime": "Uspešnice", "od": -5},
                          {"ime": "Kratek"}, {"ime": "Ni ga"}, {"ime": 5}, "smeti"):
            self.assertEqual(link_seznami.izvoz(parametri, self.mapa.name), mc.seznami_izvoz(parametri), parametri)
        self.assertEqual(link_seznami.STRAN, seznami_sink.STRAN)
        self.assertEqual(link_seznami.DEJANJE, seznami_sink.DEJANJE)

    def test_kazalo_in_strani(self):
        kazalo = link_seznami.izvoz({}, self.mapa.name)
        self.assertEqual([(x["ime"], x["stevilo"]) for x in kazalo["lists"]], [("Uspešnice", 230), ("Kratek", 2)])
        self.assertEqual(kazalo["deleted"], {"Star": 1780000000000})
        stran = link_seznami.izvoz({"ime": "Uspešnice", "od": 200}, self.mapa.name)
        self.assertEqual((stran["od"], len(stran["skladbe"]), stran["stevilo"]), (200, 30, 230))
        self.assertNotIn("interno", stran["skladbe"][0])           # naprej gredo samo znana polja

    def test_brez_mape_ali_s_pokvarjeno_datoteko_je_kazalo_prazno(self):
        self.assertEqual(link_seznami.izvoz({}, os.path.join(self.mapa.name, "ni")), {"lists": [], "deleted": {}})
        with open(os.path.join(self.mapa.name, "seznami.json"), "w", encoding="utf-8") as f:
            f.write("{napol zapisano")
        self.assertEqual(link_seznami.izvoz({}, self.mapa.name)["lists"], [])

    def test_mapa_je_mapa_medijskega_centra_safeer_os(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/x"}):
            self.assertEqual(link_seznami.mapa(), "/tmp/x/safeer-os/media")

    def test_druga_naprava_prevzame_seznam_prek_izvoza(self):
        """Celotna pot: naprava B vprasa (lists.get) napravo A in dobi njen seznam s 230 skladbami po straneh."""
        with tempfile.TemporaryDirectory() as b:
            mc_b = os_media.MediaCenter(b, roots=[])
            self.assertTrue(mc_b.seznami_uskladi(lambda parametri: link_seznami.izvoz(parametri, self.mapa.name)))
            moji = {x["ime"]: x for x in mc_b._seznami_beri()}
            self.assertEqual(len(moji["Uspešnice"]["skladbe"]), 230)
            self.assertEqual(moji["Uspešnice"]["cas"], 1790000000000)
            self.assertFalse(mc_b.seznami_uskladi(lambda parametri: link_seznami.izvoz(parametri, self.mapa.name)))


class ControlTests(unittest.TestCase):
    def test_control_odgovori_na_lists_get(self):
        izidi = []
        with tempfile.TemporaryDirectory() as mapa, mock.patch.object(link_seznami, "mapa", return_value=mapa):
            with open(os.path.join(mapa, "seznami.json"), "w", encoding="utf-8") as f:
                json.dump([{"ime": "A", "cas": 7, "skladbe": SKLADBE[:3]}], f)
            link_daljinec.izvedi_control("lists.get", {}, lambda _u: None, izidi.append)
            link_daljinec.izvedi_control("lists.get", {"ime": "A", "od": 1}, lambda _u: None, izidi.append)
        self.assertTrue(izidi[0]["ok"])
        self.assertEqual(izidi[0]["data"]["lists"], [{"ime": "A", "vir": "", "cas": 7, "stevilo": 3}])
        self.assertEqual([s["naslov"] for s in izidi[1]["data"]["skladbe"]], ["Pesem 1", "Pesem 2"])

    def test_zmoznost_in_dejanje_samo_s_safeer_os(self):
        """Seznami so v Medijskem centru Safeer OS: brez njega Control zmoznosti "lists" ne oglasa."""
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "safeer_link.py"), encoding="utf-8") as f:
            koda = f.read()
        self.assertIn('(["lists"] if self.control and _magnet_na_voljo() else [])', koda)
        for os_namescen, pricakovano in (("/usr/bin/safeer-os", True), ("", False)):
            izidi = []
            with mock.patch.object(link_daljinec, "_safeer_os", return_value=os_namescen), \
                    mock.patch.object(link_daljinec, "_glasnost", return_value={"ok": False}):
                link_daljinec.izvedi_control("status", {}, lambda _u: None, izidi.append)
            self.assertEqual("lists.get" in izidi[0]["data"]["actions"], pricakovano)


class SafeerOsTests(unittest.TestCase):
    def test_vprasa_samo_naprave_ki_znajo_sezname(self):
        import safeer_os
        naprave = {"ok": True, "naprave": [
            {"id": "ta", "ta": True, "zmoznosti": ["remote", "lists"]},
            {"id": "telefon", "zmoznosti": ["url", "remote", "lists"]},
            {"id": "stara-tv", "zmoznosti": ["url", "remote"]},
            {"id": "brez-daljinca", "zmoznosti": ["lists"]},
        ]}
        klici = []

        def control(metoda, *a):
            klici.append((metoda, *a))
            if metoda == "Seznam":
                return naprave
            return {"ok": True, "data": {"lists": [], "deleted": {}}} if a[0] == "telefon" else {"ok": False}

        vprasani = []

        def uskladi(vprasaj):
            vprasani.append(vprasaj({}))
            return True
        with mock.patch.object(safeer_os, "_control_na_vodilu", return_value=True), \
                mock.patch.object(safeer_os.Gio, "bus_get_sync", return_value=object()), \
                mock.patch.object(safeer_os, "_control_naprave", side_effect=control):
            self.assertTrue(safeer_os._seznami_z_naprav(uskladi))
        self.assertEqual(vprasani, [{"lists": [], "deleted": {}}])
        self.assertEqual(klici, [("Seznam",), ("Ukaz", "telefon", "lists.get", "{}")])

    def test_controla_zaradi_seznamov_ne_zazene(self):
        import safeer_os
        with mock.patch.object(safeer_os, "_control_na_vodilu", return_value=False), \
                mock.patch.object(safeer_os.Gio, "bus_get_sync", return_value=object()), \
                mock.patch.object(safeer_os, "_control_naprave", side_effect=AssertionError("Control se ne sme zagnati")):
            self.assertFalse(safeer_os._seznami_z_naprav(lambda _v: True))


if __name__ == "__main__":
    unittest.main()
