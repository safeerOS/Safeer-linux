"""Seznam naprav kot posnetek + spremembe (core/link_spremembe.py, docs/LINK-MESH.md »Seznam naprav: samo spremembe«).

Lastnik, 18. 10. 2026: Safeer Link naj posilja samo spremembe seznama naprav, ne celega seznama ob vsaki spremembi - za
podjetja z veliko napravami. Preverjamo, kar mora drzati:

* pravilnost: odjemalec, ki zna, ima po vsaki objavi natanko isti seznam (tudi vrstni red), kot bi ga dobil cel;
* povratno zdruzljivost: odjemalec in sosed brez zmoznosti dobita cel seznam kot doslej - mesan krog dela;
* vrzel in dvom: po izgubljeni spremembi ali neskladni spremembi prejemnik zahteva posnetek in se seznam ujema;
* varnost: sprememba nikoli ne nosi naprave, ki je prejemnik v celem seznamu ne bi videl (isti filtri), in zahteva za
  posnetek ne gre nikomur naprej;
* zdruzevanje: val prijav v oknu je eno sporocilo, prva sprememba po mirovanju gre takoj.
"""
import json
import os
import random
import threading
import time
import unittest
from collections import OrderedDict
from unittest import mock

from core import link_hub, link_hub_streznik as lhs, link_spremembe as ls, link_zmoznosti

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TUJCI = {"tujec"}


def brez_casa(seznam):
    return [{k: v for k, v in d.items() if k != "last_seen"} for d in seznam]


class Odjemalec:
    """Povezava odjemalca pri sredisci: kar dobi, obdela kot pravi odjemalec (link_hub.Povezava: Prejemnik)."""

    def __init__(self, hub, did, nov=True, naslov="192.168.0.50", izgubi=None):
        self.hub = hub
        self.did = did
        self.nov = nov
        self.naslov = naslov
        self.podatki = {"id": did}
        self.poslano = []
        self.prejemnik = ls.Prejemnik(ura=lambda: 0.0 if not hasattr(self, "_ura") else self._ura)
        self.seznam = None
        self.zahtev = 0
        self.izgubi = izgubi        # funkcija(sporocilo) -> True: sporocilo se na poti izgubi
        self.zahteve_v_cakanju = []

    def poslji(self, besedilo):
        s = json.loads(besedilo)
        if self.izgubi is not None and self.izgubi(s):
            return True             # sredisce misli, da je poslalo; odjemalec ni dobil nic
        self.poslano.append(s)
        if s.get("type") in ("cast.devices", "cast.devices.delta"):
            if self.nov:
                s, zahtevaj = self.prejemnik.sprejmi(s)
                if zahtevaj:
                    self.zahtev += 1
                    self.zahteve_v_cakanju.append({"id": "z", "type": "cast.devices.sync"})
                if s is not None:
                    self.seznam = s["devices"]
            elif s["type"] == "cast.devices":
                self.seznam = s["devices"]
        return True

    def zapri(self, *_a, **_k):
        pass

    def prijavi(self, ime=None, zmoznosti=("url", "remote", "chat")):
        zm = list(zmoznosti) + ([ls.ZMOZNOST] if self.nov else [])
        odgovor = json.loads(self.hub.obdelaj(self, json.dumps({
            "id": "r", "type": "cast.register",
            "payload": {"device_id": self.did, "name": ime or self.did.upper(), "role": "receiver",
                        "capabilities": zm, "platform": "tv"}})))
        assert odgovor["status"] == "accepted", odgovor
        return self

    def izprazni_zahteve(self):
        while self.zahteve_v_cakanju:
            self.hub.obdelaj(self, json.dumps(self.zahteve_v_cakanju.pop(0)))

    def pricakovano(self):
        return brez_casa(json.loads(self.hub.seznam_json(self))["devices"])

    def vrste(self, tip):
        return [s for s in self.poslano if s.get("type") == tip]


class Krog(unittest.TestCase):
    def setUp(self):
        krog = mock.MagicMock()
        krog.json.return_value = {"v": 1, "clani": {}, "umiki": {}}
        krog.zdruzi.return_value = False
        krog.clan_za_id.return_value = None
        krog.clan.return_value = None
        p1 = mock.patch.object(lhs.link_krog, "krog", return_value=krog)
        p1.start()
        self.addCleanup(p1.stop)
        p2 = mock.patch.object(lhs.Hub, "_je_clan", lambda self, i: i not in TUJCI)
        p2.start()
        self.addCleanup(p2.stop)


# ---------------------------------------------------------------------------------------------- razlika in zrcalo

class Razlika(unittest.TestCase):
    def test_nakljucna_zaporedja_dajo_isti_seznam_in_vrstni_red(self):
        rng = random.Random(7)
        for z_id in (True, False):
            pogled = ls.Pogled({"devices": z_id})
            zrcalo = ls.Zrcalo({"devices": z_id})
            stanje = OrderedDict()
            for korak in range(400):
                dejanje = rng.random()
                if dejanje < 0.4 or not stanje:
                    i = "n%d" % rng.randrange(60)
                    stanje[i] = {"name": "N" + i, "capabilities": ["url"], "last_seen": korak}
                elif dejanje < 0.6:
                    stanje.pop(rng.choice(list(stanje)))
                elif dejanje < 0.8:
                    i = rng.choice(list(stanje))
                    z = dict(stanje[i])
                    z["name"] = "ime%d" % korak
                    if rng.random() < 0.5:
                        z["apps"] = {"si.safeer.os": {"name": "OS"}}
                    else:
                        z.pop("apps", None)
                    stanje[i] = z
                else:
                    i = rng.choice(list(stanje))
                    stanje[i] = dict(stanje[i], last_seen=korak)      # samo cas: ni sprememba
                novo = OrderedDict((i, dict(z, id=i) if z_id else dict(z)) for i, z in stanje.items())
                prej = pogled.ver
                pogled.posodobi({"devices": novo})
                if pogled.ver == 1:
                    zrcalo.posnetek({"devices": pogled.posnetek() if z_id else pogled.slovar("devices")}, pogled.epoha, 1)
                elif pogled.ver != prej:
                    tovor = {"epoch": pogled.epoha, "base": pogled.ver - 1, "ver": pogled.ver}
                    tovor.update(pogled.zadnja)
                    self.assertEqual(zrcalo.uporabi(tovor), "ok", korak)
                self.assertEqual(brez_casa(zrcalo.seznam()), brez_casa(pogled.posnetek()), korak)
                self.assertEqual(list(zrcalo.deli["devices"]), list(pogled.deli["devices"]), "vrstni red")
                self.assertEqual(set(pogled.deli["devices"]), set(stanje))

    def test_samo_spremenjena_polja(self):
        star = OrderedDict(a={"id": "a", "name": "A", "capabilities": ["url"], "apps": {"x": 1}, "last_seen": 1})
        nov = OrderedDict(a={"id": "a", "name": "B", "capabilities": ["url"], "last_seen": 9})
        _o, d = ls.razlika(star, nov, True)
        self.assertEqual(d, {"chg": [{"id": "a", "set": {"name": "B"}, "unset": ["apps"]}]})
        _o, d = ls.razlika(star, OrderedDict(a=dict(star["a"], last_seen=50)), True)
        self.assertIsNone(d, "cas zadnjega stika ni sprememba")

    def test_vrzel_in_dvom(self):
        z = ls.Zrcalo({"devices": True})
        z.posnetek({"devices": [{"id": "a", "name": "A"}]}, "e1", 3)
        self.assertEqual(z.uporabi({"epoch": "e1", "base": 2, "ver": 3}), "vrzel")
        self.assertEqual(z.uporabi({"epoch": "drug", "base": 3, "ver": 4}), "vrzel")
        self.assertEqual(z.uporabi({"epoch": "e1", "base": 3, "ver": 3}), "vrzel", "verzija mora naprej")
        self.assertEqual(z.uporabi({"epoch": "e1", "base": 3, "ver": True}), "vrzel")
        self.assertEqual([d["id"] for d in z.seznam()], ["a"], "vrzel ne pokvari seznama")
        for slabo in ({"del": ["b"]}, {"chg": [{"id": "b", "set": {"name": "x"}}]}, {"add": [{"id": "a"}]},
                      {"chg": [{"id": "a", "set": {"id": "b"}}]}, {"chg": [{"id": "a", "unset": ["id"]}]},
                      {"add": [{"name": "brez id"}]}, {"add": "ni seznam"}):
            z.posnetek({"devices": [{"id": "a", "name": "A"}]}, "e1", 3)
            self.assertEqual(z.uporabi(dict({"epoch": "e1", "base": 3, "ver": 4}, devices=slabo)), "dvom", slabo)
            self.assertFalse(z.velja)
            self.assertEqual(z.seznam(), [])
        z.posnetek({"devices": [{"id": "a", "name": "A"}]}, "e1", 3)
        velik = {"add": [{"id": "v%d" % i, "x": "y" * 2000} for i in range(2100)]}
        self.assertEqual(z.uporabi({"epoch": "e1", "base": 3, "ver": 4, "devices": velik}), "dvom", "meja zrcala")

    def test_posnetek_brez_verzije_ne_sprejme_sprememb(self):
        """Starejse sredisce: cel seznam brez epoch/ver. Sprememba (ki je ne poslje) ne bi veljala."""
        z = ls.Zrcalo({"devices": True})
        z.posnetek({"devices": [{"id": "a"}]})
        self.assertEqual(z.uporabi({"epoch": None, "base": None, "ver": 1}), "vrzel")

    def test_zahteva_najvec_vsaki_dve_sekundi(self):
        ura = [0.0]
        p = ls.Prejemnik(ura=lambda: ura[0])
        p.sprejmi({"type": "cast.devices", "devices": [], "epoch": "e", "ver": 1})
        self.assertEqual(p.sprejmi({"type": "cast.devices.delta", "epoch": "e", "base": 5, "ver": 6}), (None, True))
        self.assertEqual(p.sprejmi({"type": "cast.devices.delta", "epoch": "e", "base": 6, "ver": 7}), (None, False))
        ura[0] = 2.5
        self.assertEqual(p.sprejmi({"type": "cast.devices.delta", "epoch": "e", "base": 7, "ver": 8}), (None, True))
        # Posnetek konca cakanje.
        s, z = p.sprejmi({"type": "cast.devices", "devices": [{"id": "a"}], "epoch": "e", "ver": 8})
        self.assertEqual((s["devices"], z), ([{"id": "a"}], False))


class SkupnaPogodba(unittest.TestCase):
    """Isti primeri (tests/fixtures/seznam_sprememb.json) preverja Android (tests/SeznamSprememb*Test.kt): oba sestavita
    isti seznam iz istih sporocil in oba proizvedeta spremembo, ki jo drugi razume."""

    def test_primeri(self):
        with open(os.path.join(KOREN, "tests", "fixtures", "seznam_sprememb.json"), encoding="utf-8") as f:
            primeri = json.load(f)
        for p in primeri["prejemnik"]:
            z = ls.Zrcalo({"devices": True})
            z.posnetek({"devices": p["posnetek"]["devices"]}, p["posnetek"]["epoch"], p["posnetek"]["ver"])
            for korak in p["spremembe"]:
                self.assertEqual(z.uporabi(korak["sporocilo"]), korak["izid"], (p["ime"], korak))
            self.assertEqual(z.seznam(), p["koncni"], p["ime"])
        for p in primeri["razlika"]:
            _o, d = ls.razlika(OrderedDict((z["id"], z) for z in p["staro"]),
                               OrderedDict((z["id"], z) for z in p["novo"]), True)
            self.assertEqual(d, p["sprememba"], p["ime"])


# ---------------------------------------------------------------------------------------------- sredisce in odjemalci

class Sredisce(Krog):
    def test_posnetek_nato_samo_spremembe(self):
        hub = lhs.Hub(odtis="ab" * 32, nas_id="n-pc")
        a = Odjemalec(hub, "tv").prijavi()
        self.assertEqual(a.vrste("cast.devices")[-1]["ver"], 1)
        b = Odjemalec(hub, "tel").prijavi()
        self.assertEqual(len(b.vrste("cast.devices")), 1, "novi dobi posnetek")
        delta = a.vrste("cast.devices.delta")[-1]
        self.assertEqual([d["id"] for d in delta["devices"]["add"]], ["tel"])
        self.assertEqual((delta["base"], delta["ver"]), (1, 2))
        self.assertEqual(len(a.vrste("cast.devices")), 1, "star clan ne dobi vec celega seznama")
        for o in (a, b):
            self.assertEqual(brez_casa(o.seznam), o.pricakovano())
        hub.odklopi(b)
        self.assertEqual(a.vrste("cast.devices.delta")[-1]["devices"], {"del": ["tel"]})
        self.assertEqual(brez_casa(a.seznam), a.pricakovano())

    def test_star_odjemalec_dobi_cel_seznam(self):
        hub = lhs.Hub(odtis="ab" * 32, nas_id="n-pc")
        star = Odjemalec(hub, "star", nov=False).prijavi()
        Odjemalec(hub, "nov").prijavi()
        self.assertEqual(star.vrste("cast.devices.delta"), [])
        self.assertEqual([d["id"] for d in star.vrste("cast.devices")[-1]["devices"]], ["star", "nov"])

    def test_mesan_krog_nakljucno(self):
        """Prijave, odhodi, ponovne prijave, katalogi in preimenovanja v nakljucnem vrstnem redu: vsak odjemalec (star ali
        nov, z istega racunalnika ali od drugod) ima po vsaki spremembi natanko cel seznam, ki mu pripada."""
        rng = random.Random(11)
        hub = lhs.Hub(odtis="ab" * 32, nas_id="n-pc")
        povezani = {}
        for korak in range(300):
            dejanje = rng.random()
            did = "d%d" % rng.randrange(25)
            if dejanje < 0.45:
                naslov = "127.0.0.1" if rng.random() < 0.3 else "192.168.0.%d" % rng.randrange(2, 200)
                o = Odjemalec(hub, did, nov=rng.random() < 0.6, naslov=naslov)
                o.prijavi(ime="Ime %d" % korak)
                povezani[did] = o
            elif dejanje < 0.65 and did in povezani:
                hub.odklopi(povezani.pop(did))
            elif dejanje < 0.85 and did in povezani:
                hub.obdelaj(povezani[did], json.dumps({"id": "k", "type": "apps.announce", "payload": {"apps": {
                    "si.safeer.os": {"name": "OS %d" % korak}} if rng.random() < 0.7 else {}}}))
            elif did in povezani:
                povezani[did].prijavi(ime="Novo ime %d" % korak)          # ponovna prijava po isti povezavi
            for o in povezani.values():
                self.assertEqual(brez_casa(o.seznam), o.pricakovano(), (korak, o.did, o.nov))
                self.assertEqual(o.zahtev, 0)
        stevilo = sum(len(o.vrste("cast.devices.delta")) for o in povezani.values() if o.nov)
        self.assertGreater(stevilo, 0)

    def test_tukaj_in_naslov_kot_pri_celem_seznamu(self):
        """Odjemalec od drugod dobi nas naslov namesto zanke (pravilo 7), odjemalec s tega racunalnika zanko - tudi v
        spremembah, ker so to razlike istega seznama."""
        hub = lhs.Hub(odtis="ab" * 32, nas_id="n-pc")
        domaci = Odjemalec(hub, "control", naslov="127.0.0.1").prijavi()
        tuj = Odjemalec(hub, "tel", naslov="192.168.0.40")
        with mock.patch.object(lhs, "_nas_naslov_za_odjemalca",
                               lambda p: None if p is None or lhs._samo_tukaj(p.naslov) else "192.168.0.10"):
            tuj.prijavi()
            Odjemalec(hub, "os", naslov="127.0.0.1").prijavi()
            self.assertEqual({d["id"]: d["ip"] for d in tuj.seznam}, {"control": "192.168.0.10", "tel": "192.168.0.40",
                                                                    "os": "192.168.0.10"})
            self.assertEqual({d["id"]: d["ip"] for d in domaci.seznam}["os"], "127.0.0.1")
            self.assertTrue(all(d.get("here") for d in tuj.seznam if d["id"] != "tel"))
            self.assertEqual(brez_casa(tuj.seznam), tuj.pricakovano())

    def test_izgubljena_sprememba_vrne_posnetek(self):
        hub = lhs.Hub(odtis="ab" * 32, nas_id="n-pc")
        izgubi = {"da": False}
        a = Odjemalec(hub, "tv", izgubi=lambda s: izgubi["da"] and s.get("type") == "cast.devices.delta").prijavi()
        Odjemalec(hub, "tel").prijavi()
        izgubi["da"] = True
        Odjemalec(hub, "tablica").prijavi()           # ta sprememba se izgubi
        izgubi["da"] = False
        self.assertNotEqual(brez_casa(a.seznam), a.pricakovano())
        Odjemalec(hub, "pc2").prijavi()               # naslednja: vrzel -> zahteva posnetka
        self.assertEqual(a.zahtev, 1)
        posnetkov = len(a.vrste("cast.devices"))
        a.izprazni_zahteve()
        self.assertEqual(len(a.vrste("cast.devices")), posnetkov + 1)
        self.assertEqual(brez_casa(a.seznam), a.pricakovano())
        Odjemalec(hub, "ura").prijavi()               # od posnetka naprej spet spremembe
        self.assertEqual(a.poslano[-1]["type"], "cast.devices.delta")
        self.assertEqual(brez_casa(a.seznam), a.pricakovano())

    def test_neuspelo_posiljanje_pomeni_posnetek(self):
        hub = lhs.Hub(odtis="ab" * 32, nas_id="n-pc")
        a = Odjemalec(hub, "tv").prijavi()
        izvirni = a.poslji
        a.poslji = lambda b: False
        Odjemalec(hub, "tel").prijavi()
        a.poslji = izvirni
        Odjemalec(hub, "tablica").prijavi()
        self.assertEqual(a.poslano[-1]["type"], "cast.devices", "po neuspelem posiljanju posnetek, ne vrzel")
        self.assertEqual(brez_casa(a.seznam), a.pricakovano())

    def test_zahteva_posnetka_ne_gre_nikomur_naprej(self):
        hub = lhs.Hub(odtis="ab" * 32, nas_id="n-pc")
        a = Odjemalec(hub, "tv").prijavi()
        b = Odjemalec(hub, "tel").prijavi()
        pred = len(b.poslano)
        self.assertIsNone(hub.obdelaj(a, json.dumps({"id": "z", "type": "cast.devices.sync"})))
        self.assertEqual(len(b.poslano), pred, "zahteva ni oddaja")
        self.assertEqual(a.poslano[-1]["type"], "cast.devices")
        # Neprijavljena povezava posnetka ne dobi.
        tujec = Odjemalec(hub, "nihce")
        odgovor = json.loads(hub.obdelaj(tujec, json.dumps({"id": "z", "type": "cast.devices.sync"})))
        self.assertEqual(odgovor["error_code"], "naprava_ni_povezana")
        self.assertEqual(tujec.vrste("cast.devices"), [])

    def test_ponovna_prijava_zacne_s_posnetkom(self):
        hub = lhs.Hub(odtis="ab" * 32, nas_id="n-pc")
        a = Odjemalec(hub, "tv").prijavi()
        Odjemalec(hub, "tel").prijavi()
        a.prijavi()
        self.assertEqual(a.poslano[-2]["type"], "cast.devices")   # zadnji je trust.update
        self.assertEqual(a.vrste("cast.devices")[-1]["epoch"], a.vrste("cast.devices")[0]["epoch"])


# ---------------------------------------------------------------------------------------------- sosedje (Link Mesh)

class Cev:
    def __init__(self, cilj_hub, naslov="192.168.0.9"):
        self.cilj_hub = cilj_hub
        self.druga = None
        self.podatki = {}
        self.naslov = naslov
        self.poslano = []
        self.izgubi = None
        self.vrsta = []
        self.zadrzi = True

    def poslji(self, besedilo):
        s = json.loads(besedilo)
        if self.izgubi is not None and self.izgubi(s):
            return True
        self.poslano.append(s)
        if self.zadrzi:
            self.vrsta.append(besedilo)
            return True
        self.cilj_hub.obdelaj(self.druga, besedilo)
        return True

    def spusti(self):
        self.zadrzi = False
        vrsta, self.vrsta = self.vrsta, []
        for b in vrsta:
            self.cilj_hub.obdelaj(self.druga, b)

    def zapri(self, *_a, **_k):
        pass


def povezi(a, b, zna_a=True, zna_b=True):
    """Sosednja povezava; `zna_*` False: ta stran je starejse sredisce (brez sprememb in brez caps)."""
    a_proti_b, b_proti_a = Cev(b), Cev(a)
    a_proti_b.druga, b_proti_a.druga = b_proti_a, a_proti_b
    for hub, cev, zna in ((a, a_proti_b, zna_a), (b, b_proti_a, zna_b)):
        if not zna:
            _postaraj(hub, cev)
    a.dodaj_soseda(b.nas_id, a_proti_b, a.nas_id)
    b.dodaj_soseda(a.nas_id, b_proti_a, a.nas_id)
    a_proti_b.spusti()
    b_proti_a.spusti()
    return a_proti_b, b_proti_a


def _postaraj(hub, cev):
    """Starejse sredisce: posilja cel mesh.devices brez epoch/ver/caps."""
    izvirni = cev.poslji

    def poslji(besedilo):
        s = json.loads(besedilo)
        if s.get("type") == "mesh.devices.delta":
            raise AssertionError("starejsemu sosedu ne smemo poslati sprememb")
        if s.get("type") == "mesh.devices":
            for k in ("epoch", "ver", "caps"):
                s["payload"].pop(k, None)
            besedilo = json.dumps(s)
        return izvirni(besedilo)
    cev.poslji = poslji


def seznam_soseda(cev):
    z = ls.Zrcalo({"devices": False, "relay": False})
    for s in cev.poslano:
        if s["type"] == "mesh.devices":
            t = s["payload"]
            z.posnetek({"devices": t.get("devices"), "relay": t.get("relay")}, t.get("epoch"), t.get("ver"))
        elif s["type"] == "mesh.devices.delta":
            z.uporabi(s["payload"])       # vrzel: kot pravi prejemnik ostane pri starem do posnetka
    return z


class Sosedje(Krog):
    def setUp(self):
        super().setUp()
        self.a = lhs.Hub(odtis="aa" * 32, nas_id="hub-a")
        self.b = lhs.Hub(odtis="bb" * 32, nas_id="hub-b")
        self.c = lhs.Hub(odtis="cc" * 32, nas_id="hub-c")

    def _preveri(self, *pari):
        for hub, cev in pari:
            z = seznam_soseda(cev)
            self.assertIsNotNone(z)
            self.assertEqual(z.slovar("devices"), hub._lokalne_json(lhs._nas_naslov_proti(cev)))
            self.assertEqual(z.slovar("relay"), hub._posredne_json())

    def test_soseda_si_po_posnetku_posiljata_samo_spremembe(self):
        Odjemalec(self.a, "tv").prijavi()
        ab, ba = povezi(self.a, self.b)
        Odjemalec(self.b, "tel").prijavi()
        Odjemalec(self.a, "tablica").prijavi()
        self.assertEqual([s["type"] for s in ab.poslano if s["type"].startswith("mesh.devices")][0], "mesh.devices")
        self.assertIn("mesh.devices.delta", [s["type"] for s in ab.poslano])
        self.assertIn("mesh.devices.delta", [s["type"] for s in ba.poslano])
        self._preveri((self.a, ab), (self.b, ba))
        # Odjemalci obeh vidijo vse.
        o = Odjemalec(self.b, "ura").prijavi()
        self.assertEqual(sorted(d["id"] for d in o.seznam), ["tablica", "tel", "tv", "ura"])

    def test_starejsi_sosed_dobi_cel_seznam(self):
        Odjemalec(self.a, "tv").prijavi()
        ab, ba = povezi(self.a, self.b, zna_b=False)
        Odjemalec(self.a, "tablica").prijavi()
        Odjemalec(self.b, "tel").prijavi()
        self.assertNotIn("mesh.devices.delta", [s["type"] for s in ab.poslano], "b ne zna: samo celi seznami")
        self.assertNotIn("mesh.devices.delta", [s["type"] for s in ba.poslano])
        o = Odjemalec(self.b, "ura").prijavi()
        self.assertEqual(sorted(d["id"] for d in o.seznam), ["tablica", "tel", "tv", "ura"])
        self.assertEqual(sorted(d["id"] for d in Odjemalec(self.a, "x").prijavi().seznam),
                         ["tablica", "tel", "tv", "ura", "x"])

    def test_tujec_in_pomoc_kot_pri_celem_seznamu(self):
        """Naprava, ki ni clan kroga, ne gre cez mejo sredisca ne v posnetku ne v spremembi; brez pomoci drugim
        napravam sosed ne dobi naprav drugih sosedov (relay) - tudi ne kot spremembe."""
        ab, ba = povezi(self.a, self.b)
        bc, cb = povezi(self.b, self.c)
        Odjemalec(self.a, "tujec").prijavi()
        Odjemalec(self.a, "tv").prijavi()
        Odjemalec(self.c, "tel").prijavi()
        vse_id = set()
        for s in ab.poslano + ba.poslano + bc.poslano + cb.poslano:
            t = s.get("payload") or {}
            for del_ in ("devices", "relay"):
                d = t.get(del_)
                if isinstance(d, dict) and set(d) <= {"add", "chg", "del"} and s["type"] == "mesh.devices.delta":
                    vse_id |= {z["id"] for z in d.get("add", [])} | {z["id"] for z in d.get("chg", [])}
                elif isinstance(d, dict):
                    vse_id |= set(d)
        self.assertNotIn("tujec", vse_id)
        self.assertIn("tel", seznam_soseda(ba).slovar("relay"), "b pomaga: a vidi napravo soseda c")
        self.b.pomaga = lambda: False
        self.b.osvezi_pomoc()
        self.assertEqual(ba.poslano[-1]["type"], "mesh.devices.delta")
        self.assertEqual(seznam_soseda(ba).slovar("relay"), {})
        Odjemalec(self.c, "ura").prijavi()
        self.assertEqual(seznam_soseda(ba).slovar("relay"), {}, "brez pomoci tudi nove naprave c ne")
        self._preveri((self.a, ab), (self.b, ba), (self.b, bc), (self.c, cb))

    def test_izgubljena_sprememba_soseda_vrne_posnetek(self):
        Odjemalec(self.a, "tv").prijavi()
        tel = Odjemalec(self.b, "tel").prijavi()
        ab, ba = povezi(self.a, self.b)
        izgubi = {"da": True}
        ab.izgubi = lambda s: izgubi["da"] and s["type"] == "mesh.devices.delta"
        Odjemalec(self.a, "tablica").prijavi()        # sprememba za b se izgubi
        izgubi["da"] = False
        self.assertEqual(sorted(d["id"] for d in tel.seznam), ["tel", "tv"], "b o tablici ne ve nic")
        self.assertNotIn("mesh.devices.sync", [s["type"] for s in ba.poslano])
        Odjemalec(self.a, "ura").prijavi()            # naslednja: vrzel -> b zahteva posnetek -> a ga poslje
        self.assertEqual([s["type"] for s in ba.poslano].count("mesh.devices.sync"), 1)
        self.assertEqual(sorted(d["id"] for d in tel.seznam), ["tablica", "tel", "tv", "ura"])
        self._preveri((self.a, ab), (self.b, ba))

    def test_zahteva_soseda_nepovezane_povezave_se_zavrne(self):
        p = Odjemalec(self.a, "nihce")
        odgovor = json.loads(self.a.obdelaj(p, json.dumps({"type": "mesh.devices.sync", "payload": {}})))
        self.assertEqual(odgovor["error_code"], "ni_sosed")


# ---------------------------------------------------------------------------------------------- zdruzevanje

class Zdruzevanje(Krog):
    def test_prva_takoj_naslednje_ob_koncu_okna(self):
        klici = []
        casovniki = []
        ura = [100.0]
        d = ls.Dusilec(lambda: klici.append(ura[0]), 0.15, ura=lambda: ura[0],
                       casovnik=lambda zamik, f: casovniki.append((zamik, f)))
        d.sprozi()
        self.assertEqual([z for z, _ in casovniki], [0.0], "prva po mirovanju takoj")
        casovniki.pop()[1]()
        ura[0] += 0.01
        for _ in range(50):
            d.sprozi()
        self.assertEqual(len(casovniki), 1, "50 sprememb v oknu: ena objava")
        self.assertAlmostEqual(casovniki[0][0], 0.14)
        casovniki.pop()[1]()
        self.assertEqual(len(klici), 2)
        d.ustavi()
        d.sprozi()
        self.assertEqual(casovniki, [])

    def test_val_prijav_z_oknom(self):
        """Pravi casovnik: 60 prijav v oknu je nekaj sporocil (ne 60), vsi imajo na koncu cel seznam."""
        hub = lhs.Hub(odtis="ab" * 32, nas_id="n-pc", okno_s=0.1)
        zaklep = threading.Lock()

        class Varen(Odjemalec):
            def poslji(self, besedilo):
                with zaklep:
                    return super().poslji(besedilo)
        prvi = Varen(hub, "prvi").prijavi()
        time.sleep(0.25)
        ostali = [Varen(hub, "n%02d" % i).prijavi() for i in range(60)]
        konec = time.monotonic() + 3
        while time.monotonic() < konec and any(o.seznam is None or len(o.seznam) != 61 for o in ostali + [prvi]):
            time.sleep(0.02)
        hub.ustavi_objave()
        for o in ostali + [prvi]:
            self.assertEqual(brez_casa(o.seznam), o.pricakovano())
        self.assertLessEqual(len(prvi.vrste("cast.devices.delta")), 4, "zdruzeno, ne 60 sporocil")
        self.assertEqual(len(prvi.vrste("cast.devices")), 1)


# ---------------------------------------------------------------------------------------------- vrsta in sprejem

class VrstaInSprejem(unittest.TestCase):
    def test_starejsemu_cel_seznam_nadomesti_cakajocega(self):
        """Starejsi odjemalec dobi samo cele sezname: v izhodni vrsti caka najvec eden (novejsi nadomesti starega na istem
        mestu). Prej se jih je ob valu nabralo do meje vrste in odjemalec je izpadel (meritev: 200 naprav, 128 izpadlih)."""
        import socket
        from core import link_ws
        a, b = socket.socketpair()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        p = link_ws.Povezava(a, "127.0.0.1", lambda *_a: None)     # brez pisca: vse ostane v vrsti
        self.assertTrue(p.poslji('{"type":"cast.devices","devices":[1]}', nadomesti="cast.devices"))
        self.assertTrue(p.poslji('{"type":"chat.send"}'))
        for i in range(200):
            self.assertTrue(p.poslji('{"type":"cast.devices","devices":[%d]}' % i, nadomesti="cast.devices"))
        self.assertEqual(len(p._vrsta), 2, "en sam seznam v vrsti, na prvotnem mestu")
        self.assertIn(b'"devices":[199]', p._vrsta[0])
        self.assertEqual(p._bajtov, sum(len(f) for f in p._vrsta))
        self.assertFalse(p.zaprta)
        # Spremembe (odjemalec, ki zna) se ne nadomescajo: gredo vse po vrsti.
        c, d = socket.socketpair()
        self.addCleanup(c.close)
        self.addCleanup(d.close)
        p2 = link_ws.Povezava(c, "127.0.0.1", lambda *_a: None)
        for i in range(3):
            p2.poslji('{"type":"cast.devices.delta","ver":%d}' % i)
        self.assertEqual(len(p2._vrsta), 3)

    def test_razposlji_nadomesca_samo_pri_starejsem(self):
        class P:
            NADOMESTI = True

            def __init__(self, zna):
                self.podatki = {ls.ZNA: zna}
                self.klici = []

            def poslji(self, b, nadomesti=None):
                self.klici.append(nadomesti)
                return True
        pogled = ls.Pogled({"devices": True})
        pogled.posodobi({"devices": OrderedDict(a={"id": "a"})})
        star, nov = P(False), P(True)
        ls.razposlji(pogled, [star, nov], lambda: "posnetek", lambda: "spremembe")
        self.assertEqual((star.klici, nov.klici), ([ls.POSNETEK], [None]))

    def test_vrsta_sprejema_ob_valu(self):
        """Privzeta vrsta v Pythonu (5) je ob valu prijav zavrgla klice; naprave so cakale ponovni SYN 1-15 s."""
        self.assertGreaterEqual(lhs._Streznik.request_queue_size, 512)


# ---------------------------------------------------------------------------------------------- odjemalec

class _LazniWs:
    def __init__(self, sporocila):
        self.sporocila = list(sporocila)
        self.poslano = []
        self.vticnik = None

    def prejmi(self):
        return self.sporocila.pop(0) if self.sporocila else None

    def poslji(self, besedilo):
        self.poslano.append(json.loads(besedilo))

    def zapri(self):
        pass


class OdjemalecLinka(unittest.TestCase):
    def test_program_dobi_cel_seznam_in_ob_vrzeli_zahteva_posnetek(self):
        p = link_hub.Povezava("wss://x/cast/ws", "", "n-tu", "Tu", odtis="ab")
        zapisi = [
            {"type": "cast.devices", "devices": [{"id": "a", "name": "A"}], "epoch": "e", "ver": 1},
            {"type": "cast.devices.delta", "epoch": "e", "base": 1, "ver": 2, "devices": {"add": [{"id": "b", "name": "B"}]}},
            {"type": "cast.devices.delta", "epoch": "e", "base": 2, "ver": 3,
             "devices": {"chg": [{"id": "a", "set": {"name": "A2"}}]}},
            {"type": "cast.devices.delta", "epoch": "e", "base": 7, "ver": 8, "devices": {"del": ["a"]}},  # vrzel
            {"type": "cast.devices", "devices": [{"id": "b", "name": "B"}], "epoch": "e", "ver": 8},
        ]
        p.odjemalec = _LazniWs([json.dumps(z) for z in zapisi])
        p.tece = True
        dobil = []
        p.ob_sporocilu = dobil.append
        with mock.patch.object(p, "_dokazi_kljuce"):
            p._poslusaj()
        seznami = [[(d["id"], d["name"]) for d in s["devices"]] for s in dobil if s["type"] == "cast.devices"]
        self.assertEqual(seznami, [[("a", "A")], [("a", "A"), ("b", "B")], [("a", "A2"), ("b", "B")], [("b", "B")]])
        self.assertNotIn("cast.devices.delta", [s["type"] for s in dobil], "program ne vidi sprememb")

    def test_zahteva_gre_srediscu(self):
        p = link_hub.Povezava("wss://x/cast/ws", "", "n-tu", "Tu", odtis="ab")
        ws = _LazniWs([json.dumps({"type": "cast.devices", "devices": [], "epoch": "e", "ver": 1}),
                       json.dumps({"type": "cast.devices.delta", "epoch": "e", "base": 4, "ver": 5})])
        p.odjemalec = ws
        p.tece = True
        p.ob_sporocilu = lambda s: None
        with mock.patch.object(p, "_dokazi_kljuce"):
            # bralnik ob koncu zapre odjemalca: poslano preberemo iz laznega
            p._poslusaj()
        self.assertEqual([s["type"] for s in ws.poslano], ["cast.devices.sync"])

    def test_zmoznost_v_prijavi_in_registru(self):
        with open(os.path.join(KOREN, "core", "link_hub.py"), encoding="utf-8") as f:
            self.assertIn('zmoznosti.append("devdelta1")', f.read())
        self.assertEqual(ls.ZMOZNOST, "devdelta1")
        self.assertIn(ls.ZMOZNOST, link_zmoznosti.ZMOZNOSTI)
        with open(os.path.join(KOREN, "core", "link_mesh.py"), encoding="utf-8") as f:
            self.assertIn("link_spremembe.ZMOZNOST", f.read())


if __name__ == "__main__":
    unittest.main()
