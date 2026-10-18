"""Ukaz napravi pri sosednjem Hubu ne sme tiho izginiti (lastnik, 17. 10. 2026: programov in datotek s tablice
prenosnik ni pokazal, Naprave.Aplikacije je po 15 s vrnil "cas").

Vzrok: tablica je isti Hub klicala pod dvema id-jema (`n-x` in `n-x-control`); Hub je vsakic novo povezavo
zamenjal s staro, tablica zaprtja ni opazila in je odgovore pisala v zaprto vticnico. Preverjamo:
  * ziva sosednja povezava ostane, ponovni klic istega soseda se zavrne (konec nihanja);
  * polodprto (tiho) povezavo Hub zapre, ukaz pa takoj zavrne s kodo "ni_poti" namesto molka;
  * ukaz_pocakaj ukaz samo za branje enkrat ponovi (brez odgovora do polovice roka ali po "ni_poti");
  * Safeer OS ob napaki pokaze »Poskusi znova« v vseh jezikih.
"""
import json
import os
import socket
import struct
import threading
import time
import unittest
from unittest import mock

from core import link_hub_streznik as lhs
from core import link_ws
from tests.test_link_mesh import TUJCI, Cev, prijava, povezi

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tiha(cev, s=lhs.TIHI_SOSED_S + 1):
    cev.zadnji_prejem = time.monotonic() - s
    return cev


class _Hubi(unittest.TestCase):
    def setUp(self):
        krog = mock.MagicMock()
        krog.json.return_value = {"v": 1, "clani": {}, "umiki": {}}
        krog.zdruzi.return_value = False
        krog.clan_za_id.return_value = None
        for p in (mock.patch.object(lhs.link_krog, "krog", return_value=krog),
                  mock.patch.object(lhs.Hub, "_je_clan", lambda self, i: i not in TUJCI),
                  mock.patch("builtins.print")):
            p.start()
            self.addCleanup(p.stop)
        self.pc = lhs.Hub(odtis="aa" * 32, nas_id="hub-pc")
        self.tab = lhs.Hub(odtis="bb" * 32, nas_id="hub-tab")


class PodvojenaSosednja(_Hubi):
    def test_ziva_ostane_ponovni_klic_zavrnjen(self):
        stara = Cev(self.tab)
        stara.zadnji_prejem = time.monotonic()
        self.assertTrue(self.pc.dodaj_soseda("hub-tab", stara, "hub-tab"))
        nova = Cev(self.tab)
        self.assertFalse(self.pc.dodaj_soseda("hub-tab", nova, "hub-tab"))
        self.assertIs(self.pc._sosedje["hub-tab"], stara)
        self.assertFalse(stara.zaprta)

    def test_zavrnitev_soseda_ima_kodo(self):
        stara = Cev(self.tab)
        stara.zadnji_prejem = time.monotonic()
        self.pc.dodaj_soseda("hub-tab", stara, "hub-tab")
        nova = Cev(self.tab)
        nova.podatki.update(id="hub-tab", podpis=True)
        with mock.patch("core.link_mesh.brez_neposredne", return_value=set()):
            odgovor = json.loads(self.pc.obdelaj(nova, json.dumps({"id": "r", "type": "cast.register", "payload": {
                "device_id": "hub-tab", "role": "hub", "capabilities": [lhs.MESH]}})))
        self.assertEqual((odgovor["status"], odgovor["error_code"]), ("rejected", "podvojen_sosed"))
        self.assertTrue(nova.podatki.get("zapri_po_odgovoru"))

    def test_mrtva_stara_se_zamenja(self):
        stara = Cev(self.tab)
        stara.zadnji_prejem = time.monotonic() - lhs.ZIVA_SOSEDNJA_S - 1
        self.pc.dodaj_soseda("hub-tab", stara, "hub-tab")
        nova = Cev(self.tab)
        self.assertTrue(self.pc.dodaj_soseda("hub-tab", nova, "hub-tab"))
        self.assertIs(self.pc._sosedje["hub-tab"], nova)
        self.assertTrue(stara.zaprta)


class NiPoti(_Hubi):
    def test_ukaz_po_mrtvi_poti_takoj_ni_poti(self):
        tablica = prijava(self.tab, "tablica")
        control = prijava(self.pc, "pc-control")
        pc_tab, _ = povezi(self.pc, self.tab)
        _tiha(pc_tab)
        odgovor = json.loads(self.pc.obdelaj(control, json.dumps(
            {"id": "cakaj-1", "type": "control.command", "target": "tablica", "payload": {"action": "apps.list"}})))
        self.assertEqual((odgovor["status"], odgovor["error_code"]), ("rejected", "ni_poti"))
        self.assertIsNone(tablica.zadnje("control.command"))
        self.assertTrue(pc_tab.zaprta)
        self.assertEqual(self.pc.sosedje(), [])
        # Naprava ostane znana, a brez poti: naslednji ukaz dobi jasno "ni_naprave", ne molka.
        odgovor = json.loads(self.pc.obdelaj(control, json.dumps(
            {"id": "cakaj-2", "type": "control.command", "target": "tablica", "payload": {"action": "apps.list"}})))
        self.assertEqual(odgovor["error_code"], "ni_naprave")

    def test_ziva_pot_ukaz_dostavi(self):
        tablica = prijava(self.tab, "tablica")
        control = prijava(self.pc, "pc-control")
        pc_tab, _ = povezi(self.pc, self.tab)
        pc_tab.zadnji_prejem = time.monotonic()
        odgovor = json.loads(self.pc.obdelaj(control, json.dumps(
            {"id": "cakaj-1", "type": "control.command", "target": "tablica", "payload": {"action": "apps.list"}})))
        self.assertEqual(odgovor["status"], "accepted")
        self.assertIsNotNone(tablica.zadnje("control.command"))

    def test_zapri_tihe_samo_tihe(self):
        tiha, ziva = _tiha(Cev(self.tab)), Cev(self.tab)
        ziva.zadnji_prejem = time.monotonic()
        self.pc.dodaj_soseda("hub-tab", tiha, "hub-tab")
        self.pc.dodaj_soseda("hub-tv", ziva, "hub-tv")
        odsli = []
        self.pc.ob_sosedu = lambda sid, naslov: odsli.append((sid, naslov))
        self.assertEqual(self.pc.zapri_tihe_sosede(), ["hub-tab"])
        self.assertEqual(self.pc.sosedje(), ["hub-tv"])
        self.assertTrue(tiha.zaprta)
        self.assertFalse(ziva.zaprta)
        self.assertIn(("hub-tab", ""), odsli, "odstranitev zbudi Mesh (ponoven klic)")

    def test_mesh_krog_zapre_tihe(self):
        from core import link_mesh
        hub = mock.Mock()
        m = link_mesh.MeshPovezovalec(hub, "n-m", poisci=lambda: [])
        with mock.patch.object(m, "kandidati", return_value=[]), mock.patch.object(m, "izmeri_poti"):
            m.en_krog(isci=False)
        hub.zapri_tihe_sosede.assert_called_once_with()


class CasPrejema(unittest.TestCase):
    def test_vsak_okvir_osvezi_zadnji_prejem(self):
        a, b = socket.socketpair()
        self.addCleanup(b.close)
        p = link_ws.Povezava(a, "192.168.0.50", lambda _p, _s: None)
        p.zadnji_prejem = 0.0
        nit = threading.Thread(target=p.zanka_branja, daemon=True)
        nit.start()
        maska = b"\x01\x02\x03\x04"
        b.sendall(bytes([0x80 | link_ws.OPKODA_PING, 0x80]) + maska)      # prazen maskiran ping odjemalca
        rok = time.monotonic() + 3
        while p.zadnji_prejem == 0.0 and time.monotonic() < rok:
            time.sleep(0.01)
        self.assertGreater(p.zadnji_prejem, 0.0)
        p.zapri()
        nit.join(2)
        self.assertEqual(struct.unpack(">B", b.recv(1))[0] & 0x0F, link_ws.OPKODA_PONG)


class UkazPocakaj(unittest.TestCase):
    def setUp(self):
        from core import safeer_link      # GTK4 + WebKitGTK 6.0
        self.link = safeer_link.SafeerLink.__new__(safeer_link.SafeerLink)
        self.link._cakajoci = {}
        self.poslano = []
        self.odgovori = {}          # zaporedna stevilka poskusa -> odgovor (control.result ali control.ack)
        povezava = mock.Mock()
        povezava.tece = True
        povezava.poslji = self._poslji
        self.link.povezava = povezava
        p = mock.patch.object(safeer_link, "PONOVI_PO_NI_POTI_S", 0.01)
        p.start()
        self.addCleanup(p.stop)

    def _poslji(self, s):
        self.poslano.append(s)
        odgovor = self.odgovori.get(len(self.poslano))
        if odgovor is not None:
            o = dict(odgovor, ref_id=s["id"])
            threading.Timer(0.01, self.link._ukaz_odziv, args=(o,)).start()
        return True

    @staticmethod
    def _uspeh():
        return {"type": "control.result", "payload": {"ok": True, "data": {"items": [1]}}}

    def test_brez_odgovora_ponovi_enkrat(self):
        self.odgovori[2] = self._uspeh()
        r = self.link.ukaz_pocakaj("tablica", "apps.list", {}, cas=0.6)
        self.assertTrue(r["ok"])
        self.assertEqual(len(self.poslano), 2)
        self.assertNotEqual(self.poslano[0]["id"], self.poslano[1]["id"])
        self.assertEqual(self.link._cakajoci, {})

    def test_ni_poti_pocaka_in_ponovi(self):
        self.odgovori[1] = {"type": "control.ack", "status": "rejected", "error_code": "ni_poti", "error": "x"}
        self.odgovori[2] = self._uspeh()
        r = self.link.ukaz_pocakaj("tablica", "files.list", {}, cas=0.6)
        self.assertTrue(r["ok"])
        self.assertEqual(len(self.poslano), 2)

    def test_dvakrat_brez_odgovora_cas(self):
        r = self.link.ukaz_pocakaj("tablica", "apps.list", {}, cas=0.3)
        self.assertEqual(r["koda"], "cas")
        self.assertEqual(len(self.poslano), 2)
        self.assertEqual(self.link._cakajoci, {})

    def test_ukaz_s_ucinkom_se_ne_ponovi(self):
        self.odgovori[1] = {"type": "control.ack", "status": "rejected", "error_code": "ni_poti", "error": "x"}
        zacetek = time.monotonic()
        r = self.link.ukaz_pocakaj("tablica", "apps.launch", {"app": "x"}, cas=5.0)
        self.assertEqual(r["koda"], "ni_poti")
        self.assertLess(time.monotonic() - zacetek, 2.0, "ni_poti brez cakanja na rok")
        self.assertEqual(len(self.poslano), 1)

    def test_prvi_odgovor_brez_ponovitve(self):
        self.odgovori[1] = self._uspeh()
        r = self.link.ukaz_pocakaj("tablica", "apps.list", {}, cas=2.0)
        self.assertTrue(r["ok"])
        self.assertEqual(len(self.poslano), 1)


class PoskusiZnova(unittest.TestCase):
    def test_gumb_v_vseh_jezikih_in_na_obeh_straneh(self):
        with open(os.path.join(KOREN, "assets", "os", "besedila-namizja.js"), encoding="utf-8") as d:
            besedila = d.read()
        self.assertEqual(besedila.count("    poskusiZnova: "), 6)
        with open(os.path.join(KOREN, "assets", "os", "delovna.js"), encoding="utf-8") as d:
            js = d.read()
        self.assertIn('t("napravaNeOdgovori"), true, znova)', js)          # Datoteke › naprava
        self.assertIn("nedosegljive.length) sp.appendChild(gumbZnova(", js)  # Programi › naprave
