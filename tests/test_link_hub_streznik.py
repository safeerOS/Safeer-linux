"""Hub na racunalniku: kdo sme noter, kam gre sporocilo in kaj dobi posiljatelj nazaj.

Tu je vsa logika, ki mora biti pravilna, zato je preizkusena brez vticnikov in TLS. Posebej
pazimo na sondo prijave, ki jo uporablja Safeer Control: prijavljena naprava mora dobiti
`isti_naprava`, osirotela vticnica pa `naprava_ni_povezana` - po tem odjemalec loci zivo povezavo
od mrtve in se po potrebi vrne.
"""
import json
import unittest
from unittest import mock

from core import link_hub_streznik, link_krog


class LaznaPovezava:
    def __init__(self, naslov="192.168.0.50"):
        self.naslov = naslov
        self.poslano = []
        self.podatki = {}
        self.zaprta_z = None

    def poslji(self, besedilo):
        self.poslano.append(json.loads(besedilo))
        return True

    def zapri(self, koda=1000, razlog=""):
        self.zaprta_z = (koda, razlog)

    def zadnje(self, tip):
        for s in reversed(self.poslano):
            if s.get("type") == tip:
                return s
        return None


def _prijava(id_naprave, ime="Naprava", vloga="receiver", zmoznosti=("url", "remote")):
    return json.dumps({"id": "r1", "type": "cast.register",
                       "payload": {"device_id": id_naprave, "name": ime, "role": vloga,
                                   "capabilities": list(zmoznosti), "platform": "tv",
                                   "protocol": "1", "kind": "tv", "version": "2.1.119"}})


class Register(unittest.TestCase):
    def setUp(self):
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id="n-racunalnik")

    def test_prijava_in_seznam(self):
        p = LaznaPovezava()
        odgovor = json.loads(self.hub.obdelaj(p, _prijava("tv1", "Televizor")))
        self.assertEqual(odgovor["type"], "cast.ack")
        self.assertEqual(odgovor["status"], "accepted")
        self.assertEqual(odgovor["ref_id"], "r1")
        seznam = p.zadnje("cast.devices")
        self.assertIsNotNone(seznam)
        self.assertEqual([d["id"] for d in seznam["devices"]], ["tv1"])
        naprava = seznam["devices"][0]
        self.assertEqual(naprava["name"], "Televizor")
        self.assertEqual(naprava["platform"], "tv")
        self.assertEqual(naprava["ip"], "192.168.0.50")

    def test_brez_device_id_zavrnjeno(self):
        p = LaznaPovezava()
        odgovor = json.loads(self.hub.obdelaj(p, json.dumps({"id": "r1", "type": "cast.register", "payload": {}})))
        self.assertEqual(odgovor["status"], "rejected")
        self.assertEqual(odgovor["error_code"], "manjka_device_id")

    def test_nova_povezava_iste_naprave_zamenja_staro(self):
        stara, nova = LaznaPovezava(), LaznaPovezava()
        self.hub.obdelaj(stara, _prijava("tv1"))
        self.hub.obdelaj(nova, _prijava("tv1"))
        self.assertEqual(stara.zaprta_z, (1000, "nova povezava iste naprave"))
        self.assertEqual(self.hub.stevilo(), 1, "naprava ostane ena, ne dve")
        self.assertIs(self.hub.najdi("tv1").povezava, nova)

    def test_vstopnica_velja_samo_za_svojo_napravo(self):
        p = LaznaPovezava()
        p.podatki["id"] = "tv1"
        odgovor = json.loads(self.hub.obdelaj(p, _prijava("tablica")))
        self.assertEqual(odgovor["status"], "rejected")
        self.assertEqual(odgovor["error_code"], "vstopnica_ni_za_to_napravo")

    def test_odklop_osvezi_seznam(self):
        a, b = LaznaPovezava(), LaznaPovezava("192.168.0.60")
        self.hub.obdelaj(a, _prijava("tv1"))
        self.hub.obdelaj(b, _prijava("tablica"))
        self.hub.odklopi(a)
        seznam = b.zadnje("cast.devices")
        self.assertEqual([d["id"] for d in seznam["devices"]], ["tablica"])

    def test_ping_vrne_pong(self):
        p = LaznaPovezava()
        odgovor = json.loads(self.hub.obdelaj(p, json.dumps({"id": "p1", "type": "cast.ping"})))
        self.assertEqual(odgovor["type"], "cast.pong")
        self.assertEqual(odgovor["id"], "p1")

    def test_pokvarjeno_sporocilo_ne_podre_nicesar(self):
        p = LaznaPovezava()
        for smeti in ("{", "[]", "ni json", '"niz"'):
            odgovor = json.loads(self.hub.obdelaj(p, smeti))
            self.assertEqual(odgovor["status"], "rejected")


class Usmerjanje(unittest.TestCase):
    def setUp(self):
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32)
        self.tv = LaznaPovezava("192.168.0.77")
        self.pc = LaznaPovezava("192.168.0.10")
        self.hub.obdelaj(self.tv, _prijava("tv1", "Televizor"))
        self.hub.obdelaj(self.pc, _prijava("pc1", "Racunalnik", vloga="sender"))

    def test_ukaz_pride_do_cilja_s_posiljateljem(self):
        odgovor = json.loads(self.hub.obdelaj(self.pc, json.dumps(
            {"id": "u1", "type": "control.command", "target": "tv1",
             "payload": {"action": "apps.launch"}})))
        self.assertEqual(odgovor["type"], "control.ack")
        self.assertEqual(odgovor["status"], "accepted")
        prejeto = self.tv.zadnje("control.command")
        self.assertEqual(prejeto["sender"], "pc1", "Hub mora vpisati posiljatelja")
        self.assertEqual(prejeto["payload"]["action"], "apps.launch")
        self.assertEqual(prejeto["id"], "u1", "id ukaza ostane isti (ref za odgovor)")

    def test_odgovora_hub_ne_potrjuje(self):
        self.assertIsNone(self.hub.obdelaj(self.tv, json.dumps(
            {"id": "o1", "type": "control.result", "target": "pc1", "payload": {"ok": True}})))
        self.assertIsNotNone(self.pc.zadnje("control.result"))

    def test_neznan_cilj_zavrnjen(self):
        odgovor = json.loads(self.hub.obdelaj(self.pc, json.dumps(
            {"id": "u1", "type": "control.command", "target": "telefon"})))
        self.assertEqual(odgovor["status"], "rejected")
        self.assertEqual(odgovor["error_code"], "ni_naprave")

    def test_sonda_prijavljene_naprave_dobi_isti_naprava(self):
        """Safeer Control po tem loci zivo prijavo od osirotele - mora biti natanko tako."""
        odgovor = json.loads(self.hub.obdelaj(self.pc, json.dumps(
            {"id": "sonda-prijave-1", "type": "control.command", "target": "pc1",
             "payload": {"action": "status"}})))
        self.assertEqual(odgovor["status"], "rejected")
        self.assertEqual(odgovor["error_code"], "isti_naprava")
        self.assertEqual(odgovor["ref_id"], "sonda-prijave-1")

    def test_sonda_osirotele_vticnice_dobi_naprava_ni_povezana(self):
        osirotela = LaznaPovezava()
        odgovor = json.loads(self.hub.obdelaj(osirotela, json.dumps(
            {"id": "sonda-prijave-2", "type": "control.command", "target": "tv1"})))
        self.assertEqual(odgovor["error_code"], "naprava_ni_povezana")

    def test_deljenje_je_v_svojem_prostoru(self):
        odgovor = json.loads(self.hub.obdelaj(self.pc, json.dumps(
            {"id": "d1", "type": "share.text", "target": "tv1", "payload": {"text": "zivjo"}})))
        self.assertEqual(odgovor["type"], "share.ack", "potrditev mora biti v prostoru share")
        self.assertEqual(self.tv.zadnje("share.text")["payload"]["text"], "zivjo")

    def test_brez_cilja_gre_vsem_drugim(self):
        self.hub.obdelaj(self.pc, json.dumps(
            {"id": "s1", "type": "sync.data", "payload": {"category": "bookmarks"}}))
        self.assertIsNotNone(self.tv.zadnje("sync.data"))
        self.assertIsNone(self.pc.zadnje("sync.data"), "posiljatelj sam sebi ne posilja")

    def test_katalog_aplikacij_se_objavi(self):
        self.hub.obdelaj(self.tv, json.dumps(
            {"id": "a1", "type": "apps.announce", "payload": {"apps": {"x": {"name": "X"}}}}))
        seznam = self.pc.zadnje("cast.devices")
        tv = [d for d in seznam["devices"] if d["id"] == "tv1"][0]
        self.assertEqual(tv["apps"], {"x": {"name": "X"}})


class PrijavaSPodpisom(unittest.TestCase):
    def setUp(self):
        self.hub = link_hub_streznik.Hub(odtis="AB" * 32)
        self.kljuc = link_krog.javni_kljuc_b64()
        self.clan = {"kljuc": self.kljuc, "ime": "Tablica", "platforma": "tablet"}

    def _izziv_in_podpis(self, device_id="n-0123456789abcdef"):
        izziv = self.hub.izziv(device_id)
        podatki = link_krog.podatki_za_podpis(izziv["fp"], izziv["nonce"], device_id)
        return izziv, link_krog.podpisi(podatki)

    def test_pravi_podpis_da_vstopnico(self):
        izziv, podpis = self._izziv_in_podpis()
        with mock.patch.object(link_krog, "krog") as k:
            k.return_value.clan_za_id.return_value = self.clan
            k.return_value.json.return_value = {"v": 1, "clani": {}}
            odgovor = self.hub.vstopnica_s_podpisom("n-0123456789abcdef", izziv["nonce"], podpis)
        self.assertIsNotNone(odgovor)
        self.assertTrue(odgovor["ticket"])
        self.assertEqual(odgovor["fp"], "ab" * 32, "odtis je vedno z malimi crkami")
        self.assertIn("ring", odgovor, "naprava mora dobiti krog, da pozna ostale")

    def test_vstopnica_velja_enkrat(self):
        izziv, podpis = self._izziv_in_podpis()
        with mock.patch.object(link_krog, "krog") as k:
            k.return_value.clan_za_id.return_value = self.clan
            k.return_value.json.return_value = {}
            odgovor = self.hub.vstopnica_s_podpisom("n-0123456789abcdef", izziv["nonce"], podpis)
        self.assertEqual(self.hub.porabi_vstopnico(odgovor["ticket"]), "n-0123456789abcdef")
        self.assertIsNone(self.hub.porabi_vstopnico(odgovor["ticket"]), "drugic ne velja")

    def test_izziv_velja_enkrat_tudi_ob_napacnem_podpisu(self):
        """Sicer bi lahko kdo na istem izzivu poskusal podpise, dokler eden ne bi ustrezal."""
        izziv, _ = self._izziv_in_podpis()
        with mock.patch.object(link_krog, "krog") as k:
            k.return_value.clan_za_id.return_value = self.clan
            self.assertIsNone(self.hub.vstopnica_s_podpisom("n-0123456789abcdef", izziv["nonce"], "napacen"))
        izziv2, podpis = self._izziv_in_podpis()
        with mock.patch.object(link_krog, "krog") as k:
            k.return_value.clan_za_id.return_value = self.clan
            k.return_value.json.return_value = {}
            self.assertIsNone(self.hub.vstopnica_s_podpisom("n-0123456789abcdef", izziv["nonce"], podpis),
                              "porabljen izziv ne sme vec veljati")

    def test_naprava_zunaj_kroga_ne_dobi_vstopnice(self):
        izziv, podpis = self._izziv_in_podpis()
        with mock.patch.object(link_krog, "krog") as k:
            k.return_value.clan_za_id.return_value = None
            self.assertIsNone(self.hub.vstopnica_s_podpisom("n-0123456789abcdef", izziv["nonce"], podpis))

    def test_tuj_nonce_ne_velja(self):
        self.hub.izziv("n-0123456789abcdef")
        with mock.patch.object(link_krog, "krog") as k:
            k.return_value.clan_za_id.return_value = self.clan
            self.assertIsNone(self.hub.vstopnica_s_podpisom("n-0123456789abcdef", "izmisljen", "x"))

    def test_izziv_za_drugo_napravo_ne_velja(self):
        izziv, podpis = self._izziv_in_podpis("n-0123456789abcdef")
        with mock.patch.object(link_krog, "krog") as k:
            k.return_value.clan_za_id.return_value = self.clan
            self.assertIsNone(self.hub.vstopnica_s_podpisom("n-ffffffffffffffff", izziv["nonce"], podpis))


class Zdravje(unittest.TestCase):
    def test_steje_prejemnike_in_posiljatelje(self):
        hub = link_hub_streznik.Hub(odtis="ab" * 32)
        hub.obdelaj(LaznaPovezava(), _prijava("tv1", vloga="receiver"))
        hub.obdelaj(LaznaPovezava(), _prijava("pc1", vloga="sender", zmoznosti=("sync",)))
        z = hub.zdravje()
        self.assertEqual((z["receivers"], z["senders"], z["sync_peers"]), (1, 1, 1))
        self.assertEqual(z["status"], "ok")


class Razsirljivost(unittest.TestCase):
    """Naprava iz leta 2028 se mora znati pogovarjati z Hubom iz leta 2026 in obratno.

    Pogoj je, da neznana polja nikogar ne podrejo: nova zmoznost se doda kot novo polje, stara
    stran ga preskoci in dela naprej s tistim, kar pozna. To je isto, kar je pri BitTorrentu
    razsiritev v rokovanju - le da tu ni treba nicesar dodajati, ker protokol to ze prenese.
    """

    def setUp(self):
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32)

    def test_neznana_polja_v_prijavi_ne_motijo(self):
        p = LaznaPovezava()
        prijava = json.dumps({
            "id": "r1", "type": "cast.register", "nekaj_novega": {"x": 1},
            "payload": {"device_id": "novost", "name": "Naprava 2028", "role": "receiver",
                        "capabilities": ["url", "files", "neznana_zmoznost"],
                        "capability_versions": {"files": 3, "screen": 2},
                        "prihodnje_polje": [1, 2, 3]},
        })
        odgovor = json.loads(self.hub.obdelaj(p, prijava))
        self.assertEqual(odgovor["status"], "accepted", "neznana polja ne smejo zavrniti prijave")
        naprava = p.zadnje("cast.devices")["devices"][0]
        self.assertIn("neznana_zmoznost", naprava["capabilities"],
                      "neznano zmoznost posredujemo naprej, da jo razume, kdor jo pozna")

    def test_neznana_vrsta_sporocila_se_posreduje_naprej(self):
        """Hub ni razsodnik vsebine: sporocilo, ki ga ne pozna, mora priti do cilja."""
        a, b = LaznaPovezava(), LaznaPovezava("192.168.0.60")
        self.hub.obdelaj(a, _prijava("a1"))
        self.hub.obdelaj(b, _prijava("b1"))
        odgovor = json.loads(self.hub.obdelaj(a, json.dumps(
            {"id": "n1", "type": "prihodnost.novost", "target": "b1", "payload": {"kaj": "novo"}})))
        self.assertEqual(odgovor["status"], "accepted")
        self.assertEqual(odgovor["type"], "prihodnost.ack")
        prejeto = b.zadnje("prihodnost.novost")
        self.assertIsNotNone(prejeto, "neznano sporocilo mora priti do cilja nespremenjeno")
        self.assertEqual(prejeto["payload"], {"kaj": "novo"})

    def test_stara_naprava_brez_novih_polj_dela_naprej(self):
        """Naprava protokola 0.2 ne poslje platform/kind/version - to ne sme biti tezava."""
        p = LaznaPovezava()
        odgovor = json.loads(self.hub.obdelaj(p, json.dumps(
            {"id": "r1", "type": "cast.register",
             "payload": {"device_id": "stara", "name": "Naprava 2024", "role": "receiver"}})))
        self.assertEqual(odgovor["status"], "accepted")
        naprava = p.zadnje("cast.devices")["devices"][0]
        self.assertNotIn("platform", naprava, "praznih polj ne izmisljujemo")
        self.assertEqual(naprava["capabilities"], [])


if __name__ == "__main__":
    unittest.main()
