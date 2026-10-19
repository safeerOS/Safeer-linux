"""Ostanki pregleda Safeer Link pred izdajo 1.0.128 (19. 10. 2026): vsak preizkus tu brez popravka pade.

1. umik, ki ga v krog prinese drug del programa mimo sredisca (odjemalec Linka), zapre povezave v delcku sekunde;
2. telo zahteve JSON ima skupni rok (ne le rok tisine za vsak recv);
3. sprejem datotek na sredisci pusti rezervo diska po pravilu link_viri.rezerva_diska;
4. prejeta nevarna datoteka (program, skripta) se s klikom na obvestilo ne odpre;
5. odjemalec ob 409 id_zaseden pove, kaj je narobe, ne ponavlja seznanitve in poskusi prijavo s podpisom;
A. sorodnik ne dobi identitete druge naprave (id iz kljuca drugega jedra, clan z drugim kljucem);
B. preimenuje vsak clan kroga s kljucem, naprava brez kljuca nicesar;
C. zavrnjen zacetek seznanitve (id_zaseden) steje v obrambi - clanstva ni mogoce preverjati brez meje;
D. umik primerja cas izdaje zetona s casom, ko je sredisce umik videlo (ure naprav niso usklajene);
E. odjemalec releja ima mejo celega sporocila;
F. link.json se shrani tudi brez os.O_NOFOLLOW in os.fchmod (Windows);
G. zeton mostu z ne-ASCII znakom ne podre primerjave.

Strezniki v teh preizkusih poslusajo samo na 127.0.0.1.
"""
import base64
import collections
import hashlib
import http.client
import io
import json
import os
import shutil
import socket
import ssl
import stat
import subprocess
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

from core import (link_hub, link_hub_deljenje, link_hub_streznik, link_kripto, link_krog, link_obramba, link_prejem,
                  link_rele, link_tls, link_viri)

TAB = "tablica-1"
NAS = "n-racunalnik"
KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _kljuc(mapa: str, ime: str) -> str:
    pot = os.path.join(mapa, ime + ".pem")
    link_kripto.ustvari_kljuc_in_potrdilo(pot, os.path.join(mapa, ime + "-potrdilo.pem"), ime)
    return base64.b64encode(link_kripto.javni_kljuc_der(pot)).decode("ascii")


class LaznaPovezava:
    def __init__(self, naslov="192.168.0.50"):
        self.naslov = naslov
        self.poslano = []
        self.podatki = {}
        self.zaprta_z = None
        self.zaprta = threading.Event()

    def poslji(self, besedilo, **_k):
        self.poslano.append(json.loads(besedilo))
        return True

    def zapri(self, koda=1000, razlog=""):
        self.zaprta_z = (koda, razlog)
        self.zaprta.set()


def _prijava(id_naprave, ime="Naprava"):
    return json.dumps({"id": "r1", "type": "cast.register",
                       "payload": {"device_id": id_naprave, "name": ime, "role": "receiver", "capabilities": ["url"],
                                   "platform": "android", "protocol": "1", "kind": "tablet", "version": "2.1.200"}})


class _Snemalka(link_obramba.Obramba):
    """Obramba, ki si dogodke samo zapomni (vira ne zapre)."""

    def __init__(self):
        super().__init__()
        self.dogodki = []

    def dogodek(self, vir, vrsta):
        self.dogodki.append((vir, vrsta))


def _streznik_na_zanki(test, hub, mapa, obramba=None) -> int:
    kljuc, potrdilo = os.path.join(mapa, "hub.pem"), os.path.join(mapa, "hub-potrdilo.pem")
    link_kripto.ustvari_kljuc_in_potrdilo(kljuc, potrdilo, "hub")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(potrdilo, kljuc)
    s = link_hub_streznik._Streznik(("127.0.0.1", 0), link_hub_streznik._Obravnava)
    s.socket = ctx.wrap_socket(s.socket, server_side=True, do_handshake_on_connect=False)
    s.hub = hub
    s.obramba = obramba if obramba is not None else link_obramba.Obramba()
    s.datoteke = lambda: None
    s.zaslon = lambda: None
    nit = threading.Thread(target=s.serve_forever, name="preizkus-ostanki-hub", daemon=True)
    nit.start()

    def konec():
        s.shutdown()
        s.server_close()
        nit.join(5)
    test.addCleanup(konec)
    return s.server_address[1]


def _tls_odjemalec() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _post(vrata, pot, telo, zeton=""):
    c = http.client.HTTPSConnection("127.0.0.1", vrata, timeout=5, context=_tls_odjemalec())
    try:
        podatki = json.dumps(telo).encode("utf-8")
        glave = {"Content-Type": "application/json", "Content-Length": str(len(podatki))}
        if zeton:
            glave["X-Safeer-Token"] = zeton
        c.request("POST", pot, body=podatki, headers=glave)
        r = c.getresponse()
        return r.status, json.loads(r.read() or b"{}")
    finally:
        c.close()


class _SKrogom(unittest.TestCase):
    """Pravi krog zaupanja v pomnilniku namesto kroga uporabnika."""

    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-ostanki-")
        self.addCleanup(shutil.rmtree, self.mapa, ignore_errors=True)
        self.krog = link_krog.Krog()
        p = mock.patch.object(link_krog, "krog", return_value=self.krog)
        p.start()
        self.addCleanup(p.stop)


# ---------------------------------------------------------------------- 1. umik mimo sredisca

class UmikMimoSredisca(_SKrogom):
    def setUp(self):
        super().setUp()
        self.k_tab = _kljuc(self.mapa, "tablica")
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=NAS)
        zeton = self.hub.zeton_lastne_naprave(TAB, "Tablica")
        self.assertIsNone(self.hub.vpisi_v_krog(zeton, self.k_tab, "Tablica", "android")[1])
        self.p = LaznaPovezava()
        self.p.podatki.update({"id": TAB, "izdano": time.time() - 5.0, "stars": ""})
        self.assertEqual(json.loads(self.hub.obdelaj(self.p, _prijava(TAB)))["status"], "accepted")
        # HubStreznik brez vticnikov: samo nit pospravljanja nad tem srediscem.
        self.hs = link_hub_streznik.HubStreznik()
        self.hs.hub = self.hub
        self.hs._streznik = object()
        self.nit = threading.Thread(target=self.hs._pospravljanje, name="preizkus-pospravljanje", daemon=True)
        self.nit.start()
        self.addCleanup(self._ustavi)        # pred koncem nadomestnega kroga (cleanup gre v obratnem vrstnem redu)
        time.sleep(0.1)                      # nit je zacela cakati

    def _ustavi(self):
        with self.hs._zaklep:
            self.hs._streznik = None
        getattr(link_krog, "zbudi", lambda: None)()
        self.nit.join(2)

    def _umik_od_drugega_sredisca(self):
        """Kot odjemalec Linka (link_hub.Povezava: trust.update drugega sredisca -> link_krog.sprejmi)."""
        umaknjeno = max(time.time(), self.krog.clan(TAB)["dodano"] + 0.001)
        self.assertTrue(link_krog.sprejmi({"umiki": {TAB: {"umaknjeno": umaknjeno, "umaknil": "n-televizor"}}}))
        self.assertTrue(self.krog.je_umaknjen(TAB))

    def test_povezava_umaknjene_naprave_se_zapre_v_nekaj_sekundah(self):
        zacetek = time.monotonic()
        self._umik_od_drugega_sredisca()
        self.assertTrue(self.p.zaprta.wait(3.0), "povezava umaknjene naprave mora iti takoj, ne sele ob pospravljanju")
        self.assertLess(time.monotonic() - zacetek, 3.0)
        self.assertEqual(self.p.zaprta_z[0], 1008)
        self.assertIsNone(self.hub.najdi(TAB).povezava)

    def test_umaknjen_sosednji_hub_izgubi_povezavo(self):
        k_sosed = _kljuc(self.mapa, "sosed")
        sosed = link_krog.id_iz_kljuca(k_sosed)
        self.krog.dodaj(sosed, k_sosed, "Televizor", "tv", NAS, dodano=time.time() - 60.0)
        p = LaznaPovezava()
        with self.hub._zaklep:
            self.hub._sosedje[sosed] = p
        time.sleep(0.5)                       # dodajanje clana je ze uveljavljeno
        umaknjeno = max(time.time(), self.krog.clan(sosed)["dodano"] + 0.001)
        link_krog.sprejmi({"umiki": {sosed: {"umaknjeno": umaknjeno, "umaknil": "n-televizor"}}})
        self.assertTrue(p.zaprta.wait(3.0), "sosednji hub umaknjene naprave mora izgubiti povezavo")
        self.assertNotIn(sosed, self.hub.sosedje())

    def test_nit_se_ob_ustavitvi_konca_takoj(self):
        self._ustavi()
        self.assertFalse(self.nit.is_alive(), "nit pospravljanja ne sme ostati po ustavitvi sredisca")


# ---------------------------------------------------------------------- 2. skupni rok telesa JSON

class TeloPoKapljicah(unittest.TestCase):
    def test_pocasno_telo_json_zapre_povezavo(self):
        mapa = tempfile.mkdtemp(prefix="safeer-ostanki-")
        self.addCleanup(shutil.rmtree, mapa, ignore_errors=True)
        vrata = _streznik_na_zanki(self, link_hub_streznik.Hub(odtis="ab" * 32), mapa)
        with mock.patch.object(link_hub_streznik._Obravnava, "ROK_TELESA_S", 1.5, create=True):
            v = _tls_odjemalec().wrap_socket(socket.create_connection(("127.0.0.1", vrata), timeout=5),
                                             server_hostname="127.0.0.1")
            self.addCleanup(v.close)
            v.sendall(b"POST /cast/pair/start HTTP/1.1\r\nHost: preizkus\r\nContent-Type: application/json\r\n"
                      b"Content-Length: 400\r\n\r\n{")
            v.settimeout(0.3)
            zacetek, koncano = time.monotonic(), False
            while time.monotonic() - zacetek < 6.0:
                try:
                    v.sendall(b" ")              # en bajt na 0,3 s: rok tisine (60 s) tega nikoli ne ujame
                    v.recv(1024)                 # odgovor ali zaprtje: sredisce je branje telesa koncalo
                    koncano = True
                    break
                except socket.timeout:
                    continue
                except (OSError, ssl.SSLError):
                    koncano = True
                    break
            trajalo = time.monotonic() - zacetek
        self.assertTrue(koncano, "sredisce mora telo po kapljicah prekiniti")
        self.assertLess(trajalo, 4.5)


# ---------------------------------------------------------------------- 3. rezerva diska

_Disk = collections.namedtuple("_Disk", "total used free")


class RezervaDiska(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Disk 500 GB: pravilo link_viri.rezerva_diska da 10 GiB (2 %, najvec 10 GiB). Prost prostor je lazen.
        lazni = types.SimpleNamespace(disk_usage=lambda _m: _Disk(500 * 1024 ** 3, 0, 0))
        p = mock.patch.object(link_viri, "shutil", lazni)
        p.start()
        self.addCleanup(p.stop)
        self.prosto = 5 * 1024 ** 3
        self.z = link_hub_deljenje.Deljenje(mapa=lambda: os.path.join(self.tmp.name, "zaloga"),
                                            prosto=lambda _m: self.prosto)

    def test_isto_pravilo_kot_drugod_v_linku(self):
        self.assertEqual(link_viri.rezerva_diska(self.tmp.name), 10 * 1024 ** 3)
        koda, odgovor, d = self.z.sprejmi(io.BytesIO(b"x" * 1024), 1024, "a.bin", "tv1", "fon1")
        self.assertEqual((koda, odgovor.get("koda"), d), (507, "ni_prostora", None),
                         "5 GiB prostega na disku 500 GB je pod rezervo (prej 200 MiB)")
        self.assertEqual(self.z.preveri("a.bin", "tv1", 1024)[0], 507)
        self.prosto = 11 * 1024 ** 3
        self.assertEqual(self.z.sprejmi(io.BytesIO(b"x" * 1024), 1024, "a.bin", "tv1", "fon1")[0], 200)


# ---------------------------------------------------------------------- 4. prejeta nevarna datoteka

class NevarnaPrejeta(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(link_prejem, "OBVESTILO_RAZMIK_S", 0.0)
        p.start()
        self.addCleanup(p.stop)
        self.obvestila, self.odprto, self.pokazano = {}, [], []
        self.vsebine = {}
        self.p = link_prejem.Prejem(
            prevzemi=self._prevzemi, obvesti=self._obvesti, brez_vprasanja=lambda i, z: True,
            odpri=self.odprto.append, pokazi=self.pokazano.append, jezik=lambda: "sl", v_ozadju=lambda f: f())

    def _prevzemi(self, t):
        pot = os.path.join(self.tmp.name, t["name"])
        with open(pot, "wb") as d:
            d.write(self.vsebine.get(t["name"], b"vsebina"))
        return pot, ""

    def _obvesti(self, ident, naslov, besedilo, gumbi=None, privzeto=None, prioriteta="normal"):
        self.obvestila[ident] = {"gumbi": {k: f for k, _n, f in gumbi or []}, "privzeto": privzeto}

    def _prejmi(self, ime, od="tel"):
        self.p.prispela(od, "Telefon", {"name": ime, "path": "/cast/file/x?k=y", "size": 7, "sha256": "0" * 64})
        return self.obvestila[next(i for i in self.obvestila if i.startswith("safeer-prejem"))]

    def test_program_po_imenu_se_ne_odpre(self):
        for i, ime in enumerate(("racun.pdf.exe", "zagon.desktop", "skripta.sh", "Program.AppImage")):
            self.obvestila.clear()
            o = self._prejmi(ime, od="tel-%d" % i)
            self.assertNotIn("odpri", o["gumbi"], ime)
            o["privzeto"]()
            pot = os.path.join(self.tmp.name, ime)
            self.assertEqual(self.odprto, [], "%s se s klikom ne sme odpreti" % ime)
            self.assertEqual(self.pokazano[-1], pot, "pokazemo, kje je - ime ostane")
            self.assertTrue(os.path.exists(pot))

    def test_program_po_vsebini_se_ne_odpre(self):
        self.vsebine["slika.jpg"] = b"MZ\x90\x00 program"
        o = self._prejmi("slika.jpg")
        self.assertNotIn("odpri", o["gumbi"])
        o["privzeto"]()
        self.assertEqual(self.odprto, [])

    def test_navadna_datoteka_se_odpre(self):
        o = self._prejmi("foto.jpg")
        o["gumbi"]["odpri"]()
        self.assertEqual(self.odprto, [os.path.join(self.tmp.name, "foto.jpg")])


class PrejetaNiIzvrsljiva(unittest.TestCase):
    """Varovalka (napake ni bilo: prevzem pise z open(..., "wb"), 0666 & ~umask): prejeta skripta nima bita +x."""

    def test_prevzeta_skripta_brez_izvrsljivega_bita(self):
        from core import link_deljenje
        mapa = tempfile.mkdtemp(prefix="safeer-ostanki-")
        self.addCleanup(shutil.rmtree, mapa, ignore_errors=True)
        hub = link_hub_streznik.Hub(odtis="ab" * 32)
        hub.deljenje = link_hub_deljenje.Deljenje(mapa=lambda: os.path.join(mapa, "zaloga"),
                                                  prosto=lambda _m: 50 * 1024 ** 3, rezerva=lambda _m: 1024 ** 3)
        vrata = _streznik_na_zanki(self, hub, mapa)
        vsebina = b"#!/bin/sh\necho zivjo\n"
        koda, _odgovor, d = hub.deljenje.sprejmi(io.BytesIO(vsebina), len(vsebina), "zagon.sh", "pc", "fon")
        self.assertEqual(koda, 200)
        naslov = "wss://127.0.0.1:%d/cast/ws" % vrata
        odtis, _k = link_tls.potrdilo_huba(naslov)
        prejemi = os.path.join(mapa, "Prejemi")
        os.makedirs(prejemi)
        rezerva = mock.patch.object(link_viri, "rezerva_diska", lambda _m: 0)     # pravi disk vsebnika je majhen
        rezerva.start()
        self.addCleanup(rezerva.stop)
        pot, razlog = link_deljenje.prevzemi_datoteko(naslov, odtis, d.pot_prevzema(), "zagon.sh",
                                                      hashlib.sha256(vsebina).hexdigest(), mapa=prejemi)
        self.assertTrue(pot, razlog)
        self.assertEqual(os.path.basename(pot), "zagon.sh", "ime ostane razpoznavno")
        self.assertEqual(stat.S_IMODE(os.stat(pot).st_mode) & 0o111, 0)


# ---------------------------------------------------------------------- 5. odjemalec ob id_zaseden

class _Most:
    """Del SafeerLink, ki ga potrebujejo seznanitev, QR in prijava s podpisom (brez okna in GTK)."""

    def __init__(self, naslov, mapa, clan_kroga=False):
        from core import safeer_link
        self._naslov = naslov
        self.odzivi = []
        self.iskanj = 0
        self.povezav = 0
        self._seznanjanje = False
        self._prijava = None
        self._qr_rod = 0
        self._qr = None
        self.ob_seznanitvi = None
        self._clan = clan_kroga
        self.nastavitve = link_hub.Nastavitve(os.path.join(mapa, "link.json"))
        for ime in ("_seznani", "_potrdi_kodo", "_zacni_qr_notranje", "_prijava_ob_zasedenem"):
            f = getattr(safeer_link.SafeerLink, ime, None)
            if f is not None:
                setattr(self, ime, types.MethodType(f, self))

    def _hub(self):
        return self._naslov

    def _id(self):
        return TAB

    def _ime(self):
        return "Tablica"

    def _odziv(self, vrsta, podatki):
        self.odzivi.append((vrsta, podatki))

    def _poisci_hub(self):
        self.iskanj += 1

    def _preklici_qr(self):
        pass

    def _clan_kroga(self):
        return self._clan

    def _povezi(self):
        self.povezav += 1


class IdZasedenPriOdjemalcu(_SKrogom):
    def setUp(self):
        super().setUp()
        self.k_tab = _kljuc(self.mapa, "tablica")
        self.krog.dodaj(TAB, self.k_tab, "Tablica", "android", NAS, dodano=time.time() - 60.0)
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=NAS)
        self.vrata = _streznik_na_zanki(self, self.hub, self.mapa)
        self.naslov = "wss://127.0.0.1:%d/cast/ws" % self.vrata

    def test_zacetek_seznanitve_in_qr_povesta_id_zaseden(self):
        self.assertEqual(link_hub.zacni_seznanitev(self.naslov, TAB, "Tablica"), {"napaka": "id_zaseden"})
        self.assertEqual(link_hub.zacni_qr(self.naslov, TAB, "Tablica"), {"napaka": "id_zaseden"})

    def test_seznanitev_s_kodo_razumljivo_besedilo(self):
        m = _Most(self.naslov, self.mapa)
        m._seznani()
        napake = [p for v, p in m.odzivi if v == "napaka"]
        self.assertEqual(len(napake), 1, m.odzivi)
        self.assertEqual(napake[0]["koda"], "id_zaseden")
        self.assertIn("odstrani", napake[0]["sporocilo"])

    def test_qr_brez_zanke(self):
        """Prej: zacni_qr je vrnil None -> »ni Safeer Linka«, iskanje in nova koda QR vsakih 8 s (link.js)."""
        m = _Most(self.naslov, self.mapa)
        m._zacni_qr_notranje()
        self.assertEqual([p for v, p in m.odzivi if v == "qr"], [{"napaka": "id_zaseden"}])
        self.assertEqual(m.iskanj, 0, "id_zaseden ni izgubljeno sredisce: brez iskanja in ponavljanja")

    def test_potrditev_kode_konca_prijavo(self):
        m = _Most(self.naslov, self.mapa)
        m._prijava = {"pair_id": "p1", "odtis": "ab" * 32, "hub_id": "safeer-link-hub"}
        with mock.patch.object(link_hub, "potrdi_kodo", return_value=(None, "id_zaseden")):
            m._potrdi_kodo("123456")
        self.assertEqual(m.odzivi, [("kodaNiSprejeta", {"razlog": "id_zaseden"})])
        self.assertIsNone(m._prijava, "nova koda ne pomaga: prijava se konca")

    def test_clan_kroga_se_prijavi_s_podpisom(self):
        k_tv = _kljuc(self.mapa, "tv")
        self.krog.dodaj("n-tv", k_tv, "Televizor", "tv", NAS, dodano=time.time() - 60.0)
        m = _Most(self.naslov, self.mapa, clan_kroga=True)
        with mock.patch.object(link_tls, "potrdilo_huba", return_value=("cd" * 32, k_tv)), \
                mock.patch.object(link_hub, "vzemi_vstopnico_s_podpisom", return_value=("vstopnica", 200)) as podpis:
            m._seznani()
        podpis.assert_called_once()
        self.assertEqual(m.povezav, 1)
        self.assertIn(("seznanitev", True), m.odzivi)
        self.assertEqual(m.nastavitve.get("hub_fp"), "cd" * 32)
        self.assertEqual([v for v, _p in m.odzivi if v == "napaka"], [])

    def test_sredisca_zunaj_kroga_ne_vprasa_za_podpis(self):
        m = _Most(self.naslov, self.mapa, clan_kroga=True)
        with mock.patch.object(link_tls, "potrdilo_huba", return_value=("cd" * 32, _kljuc(self.mapa, "tuj"))), \
                mock.patch.object(link_hub, "vzemi_vstopnico_s_podpisom", return_value=("vstopnica", 200)) as podpis:
            m._seznani()
        podpis.assert_not_called()
        self.assertEqual([p["koda"] for v, p in m.odzivi if v == "napaka"], ["id_zaseden"])

    def test_stran_ima_besedilo_v_vseh_jezikih(self):
        if not shutil.which("node"):
            self.skipTest("node ni namescen")
        skripta = r"""
const s = require('fs').readFileSync(process.argv[1], 'utf8');
const i = s.indexOf('var BESEDILA = {');
let g = 0, j = s.indexOf('{', i);
const z = j;
for (; j < s.length; j++) { if (s[j] === '{') g++; else if (s[j] === '}') { g--; if (g === 0) break; } }
const B = new Function('return ' + s.slice(z, j + 1))();
const izid = {};
for (const jez of ['sl', 'en', 'de', 'es', 'fr', 'it']) izid[jez] = (B[jez] || {}).napIdZaseden || '';
izid.napaka = /id_zaseden:\s*"napIdZaseden"/.test(s);
izid.qr = /n === "id_zaseden" \? "napIdZaseden"/.test(s);
izid.koda = /rp === "id_zaseden" \? "napIdZaseden"/.test(s) && /razlog === "id_zaseden" \? "napIdZaseden"/.test(s);
izid.dovoli = /r === "id_zaseden" \? "napIdZaseden"/.test(s);
console.log(JSON.stringify(izid));
"""
        izid = json.loads(subprocess.run(["node", "-e", skripta, os.path.join(KOREN, "assets", "link", "link.js")],
                                         capture_output=True, text=True, timeout=30, check=True).stdout)
        for jez in ("sl", "en", "de", "es", "fr", "it"):
            self.assertTrue(izid[jez], jez)
        self.assertEqual(len({izid[j] for j in ("sl", "en", "de", "es", "fr", "it")}), 6, "prevedeno, ne kopirano")
        self.assertTrue(izid["napaka"] and izid["qr"] and izid["koda"] and izid["dovoli"], izid)


# ---------------------------------------------------------------------- A. sorodnik ne prevzame identitete

class SorodnikNePrevzameIdentitete(_SKrogom):
    def setUp(self):
        super().setUp()
        self.k_pc = _kljuc(self.mapa, "pc")
        self.pc = link_krog.id_iz_kljuca(self.k_pc)
        self.krog.dodaj(self.pc, self.k_pc, "Racunalnik", "linux", self.pc, dodano=time.time() - 60.0)
        self.k_tv = _kljuc(self.mapa, "tv")
        self.krog.dodaj("tv-1", self.k_tv, "Televizor", "tv", self.pc, dodano=time.time() - 60.0)
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=self.pc)

    def test_id_iz_kljuca_drugega_jedra(self):
        zeton = self.hub.zeton_lastne_naprave("n", "Napadalec")
        self.assertEqual(self.hub.sorodni_zeton(zeton, self.pc + "-os", "Safeer OS"), (None, "ni_sorodnik"),
                         "naprava »n« ne sme dobiti identitete tega racunalnika (n-<jedro>-os)")

    def test_clan_z_drugim_kljucem(self):
        zeton = self.hub.zeton_lastne_naprave("tv", "Napadalec")
        self.assertEqual(self.hub.sorodni_zeton(zeton, "tv-1", "Televizor"), (None, "ni_sorodnik"))

    def test_zakoniti_sorodniki(self):
        z_pc = self.hub.zeton_lastne_naprave(self.pc, "Racunalnik")
        for sorodnik in (self.pc + "-os", self.pc + "-control"):
            self.assertIsNone(self.hub.sorodni_zeton(z_pc, sorodnik, "Safeer")[1], sorodnik)
        z_tab = self.hub.zeton_lastne_naprave(TAB, "Tablica")
        self.assertIsNone(self.hub.sorodni_zeton(z_tab, TAB + "-control", "Safeer Control")[1])
        # Clan s kljucem: sorodnik pod drugim id-jem z ISTIM kljucem ostane sorodnik.
        k_tab = _kljuc(self.mapa, "tablica")
        self.krog.dodaj(TAB, k_tab, "Tablica", "android", self.pc, dodano=time.time() - 30.0)
        self.krog.dodaj(TAB + "-os", k_tab, "Safeer OS", "android", self.pc, dodano=time.time() - 30.0)
        self.assertIsNone(self.hub.sorodni_zeton(z_tab, TAB + "-os", "Safeer OS")[1])
        # Clan s kljucem sme dobiti sorodnika z jedrom SVOJEGA kljuca, ne pa jedra drugega clana.
        jedro_tab = link_krog.id_iz_kljuca(k_tab)
        z_jedro = self.hub.zeton_lastne_naprave(jedro_tab, "Tablica")
        self.assertIsNone(self.hub.sorodni_zeton(z_jedro, jedro_tab + "-control", "Safeer Control")[1])


# ---------------------------------------------------------------------- B. preimenovanje (odlocitev lastnika)

class PreimenujeClanKroga(_SKrogom):
    def setUp(self):
        super().setUp()
        k_tv, k_tab = _kljuc(self.mapa, "tv"), _kljuc(self.mapa, "tab")
        self.tv, self.tab = link_krog.id_iz_kljuca(k_tv), link_krog.id_iz_kljuca(k_tab)
        self.krog.dodaj(self.tv, k_tv, "Android TV", "tv", NAS, dodano=100.0)
        self.krog.dodaj(self.tab, k_tab, "Tablica", "android", NAS, dodano=101.0)
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=NAS)

    def test_televizor_poimenuje_drugo_napravo(self):
        z_tv = self.hub.zeton_lastne_naprave(self.tv, "Android TV")
        self.assertEqual(self.hub.preimenuj_napravo(z_tv, self.tab, "Tablica v kuhinji")[0], 200)
        self.assertEqual(self.krog.clan(self.tab)["ime"], "Tablica v kuhinji")

    def test_trust_names_od_clana(self):
        p = LaznaPovezava()
        self.hub.obdelaj(p, _prijava(self.tv))
        ponujeno = self.krog.json()
        ponujeno["clani"][self.tab].update(ime="Tablica v kuhinji", imenovano=time.time())
        self.hub.obdelaj(p, json.dumps({"id": "n1", "type": "trust.names", "payload": ponujeno}))
        self.assertEqual(self.krog.clan(self.tab)["ime"], "Tablica v kuhinji")

    def test_brez_kljuca_ne(self):
        z = self.hub.zeton_lastne_naprave("fon-1", "Telefon")
        self.assertEqual(self.hub.preimenuj_napravo(z, self.tab, "Vdrto")[0], 403)
        self.assertEqual(self.krog.clan(self.tab)["ime"], "Tablica")


# ---------------------------------------------------------------------- C. preverjanje clanstva steje

class ClanstvaNiMogocePreverjatiBrezMeje(_SKrogom):
    def setUp(self):
        super().setUp()
        self.krog.dodaj(TAB, _kljuc(self.mapa, "tablica"), "Tablica", "android", NAS, dodano=time.time() - 60.0)
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=NAS)
        self.obramba = _Snemalka()
        self.vrata = _streznik_na_zanki(self, self.hub, self.mapa, self.obramba)

    def _dogodki(self):
        return [v for _vir, v in self.obramba.dogodki]

    def test_zacetek_seznanitve(self):
        self.assertEqual(_post(self.vrata, "/cast/pair/start", {"device_id": TAB, "name": "x"})[0], 409)
        self.assertIn("zacetek_seznanitve", self._dogodki())

    def test_zacetek_qr(self):
        status, _o = _post(self.vrata, "/cast/pair/qr/start", {"device_id": TAB, "secret_sha256": "a" * 64,
                                                                "poll_secret": "p" * 16})
        self.assertEqual(status, 409)
        self.assertIn("seznanitev", self._dogodki())

    def test_pridruzitev_qr(self):
        qr_id, skrivnost = self.hub.ustvari_pridruzitev()
        status, _o = _post(self.vrata, "/cast/pair/qr/join", {"qr_id": qr_id, "secret": skrivnost, "device_id": TAB})
        self.assertEqual(status, 409)
        self.assertIn("seznanitev", self._dogodki())


# ---------------------------------------------------------------------- D. ure razlicnih naprav

class UreNaprav(_SKrogom):
    def setUp(self):
        super().setUp()
        self.k_tab = _kljuc(self.mapa, "tablica")
        self.krog.dodaj(TAB, self.k_tab, "Tablica", "android", NAS, dodano=time.time() - 1000.0)

    def test_ura_umikajoce_naprave_prehiteva(self):
        hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=NAS)
        star = hub.zeton_lastne_naprave(TAB, "Tablica")
        # Televizor z uro 10 min naprej umakne tablico; sredisce umik vidi zdaj.
        self.krog.zdruzi({"umiki": {TAB: {"umaknjeno": time.time() + 600.0, "umaknil": "n-televizor"}}})
        hub.uveljavi_krog() if hasattr(hub, "uveljavi_krog") else hub.preklici_umaknjene()
        self.assertIsNone(hub.naprava_zetona(star), "zeton pred umikom ne velja")
        time.sleep(0.01)
        nov = hub.zeton_lastne_naprave(TAB, "Tablica")
        self.assertIsNotNone(hub.naprava_zetona(nov), "nova seznanitev takoj po umiku velja")
        self.assertIsNone(hub.vpisi_v_krog(nov, self.k_tab, "Tablica", "android")[1])
        self.assertTrue(self.krog.je_clan(TAB), "naprava je spet v krogu")
        # Umik, ki ga uporabnik naredi pozneje, velja kljub vnosu z ure, ki prehiteva.
        self.assertTrue(self.krog.umakni(TAB, "n-racunalnik"))
        self.assertTrue(self.krog.je_umaknjen(TAB))

    def test_ura_umikajoce_naprave_zaostaja(self):
        cas = [time.time() - 50.0]
        hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=NAS, ura=lambda: cas[0])
        zeton = hub.zeton_lastne_naprave(TAB, "Tablica")          # izdan pred 50 s (po uri sredisca)
        cas[0] = time.time()
        # Umik pride zdaj, a z uro, ki zaostaja 10 min: zeton iz razmika ne sme preziveti.
        self.krog.zdruzi({"umiki": {TAB: {"umaknjeno": time.time() - 600.0, "umaknil": "n-televizor"}}})
        self.assertTrue(self.krog.je_umaknjen(TAB))
        self.assertIsNone(hub.naprava_zetona(zeton))

    def test_po_ponovnem_zagonu_min_casa_umika_in_zdaj(self):
        pot = os.path.join(self.mapa, "krog.json")
        prihodnost, preteklost = time.time() + 600.0, time.time() - 600.0
        with open(pot, "w", encoding="utf-8") as d:
            json.dump({"v": 1, "clani": {"a": {"kljuc": self.k_tab, "ime": "A", "platforma": "", "dodano": 1.0,
                                               "dodal": ""},
                                         "b": {"kljuc": self.k_tab, "ime": "B", "platforma": "", "dodano": 1.0,
                                               "dodal": ""}},
                       "umiki": {"a": {"umaknjeno": prihodnost, "umaknil": "x"},
                                 "b": {"umaknjeno": preteklost, "umaknil": "x"}}}, d)
        k = link_krog.Krog(pot)
        self.assertLessEqual(k.umaknjen_videno("a"), time.time(), "umik iz prihodnosti velja od zdaj")
        self.assertEqual(k.umaknjen_videno("b"), preteklost)
        self.assertNotIn("videno", json.dumps(k.json()), "lokalni cas ne gre v zapis kroga")


# ---------------------------------------------------------------------- E. rele: meja celega sporocila

class _VirOkvirjev:
    """Vticnica releja, ki posilja nadaljevalne okvirje brez konca (zlonameren rele)."""
    KOS = 1024 * 1024

    def __init__(self, najvec):
        self.najvec = najvec
        self.prebrano = 0
        self._medpomnilnik = b""
        self._prvi = True

    def _okvir(self):
        op = 0x2 if self._prvi else 0x0
        self._prvi = False
        return bytes([op, 127]) + self.KOS.to_bytes(8, "big") + b"\0" * self.KOS     # FIN=0, brez maske

    def recv(self, n):
        if self.prebrano >= self.najvec:
            raise AssertionError("odjemalec bere brez meje")
        if not self._medpomnilnik:
            self._medpomnilnik = self._okvir()
        kos, self._medpomnilnik = self._medpomnilnik[:n], self._medpomnilnik[n:]
        self.prebrano += len(kos)
        return kos


class MejaSporocilaReleja(unittest.TestCase):
    def test_nadaljevalni_okvirji_ne_porabijo_pomnilnika(self):
        ws = link_rele.WsOdjemalec.__new__(link_rele.WsOdjemalec)
        ws.s = _VirOkvirjev(24 * 1024 * 1024)
        ws._ostanek = b""
        ws._pisi = threading.Lock()
        with self.assertRaises(ConnectionError):
            ws.prejmi()
        self.assertLessEqual(ws.s.prebrano, 6 * 1024 * 1024, "meja velja za celo sporocilo (4 MiB)")


# ---------------------------------------------------------------------- F. link.json na Windows

class _OsBrez:
    """Modul os brez O_NOFOLLOW in fchmod (Windows, Python pred 3.13)."""

    def __getattr__(self, ime):
        if ime in ("O_NOFOLLOW", "fchmod"):
            raise AttributeError(ime)
        return getattr(os, ime)


class NastavitveNaWindows(unittest.TestCase):
    def test_shrani_brez_o_nofollow_in_fchmod(self):
        mapa = tempfile.mkdtemp(prefix="safeer-ostanki-")
        self.addCleanup(shutil.rmtree, mapa, ignore_errors=True)
        pot = os.path.join(mapa, "link", "link.json")
        n = link_hub.Nastavitve(pot)
        n.podatki["control_token"] = "z"
        with mock.patch.object(link_hub, "os", _OsBrez()):
            n.shrani()
        with open(pot, encoding="utf-8") as d:
            self.assertEqual(json.load(d), {"control_token": "z"}, "seznanitev se ne sme izgubiti")


class DovoljenjaNaWindows(unittest.TestCase):
    """Koncni pregled b8e39da: ista napaka kot link.json - link_dostop._na_disk je klical os.fchmod, ki ga Windows
    (Python pred 3.13) nima; AttributeError ni OSError, zapis dovoljenj se ni shranil."""

    def test_na_disk_brez_fchmod(self):
        from core import link_dostop
        mapa = tempfile.mkdtemp(prefix="safeer-ostanki-")
        self.addCleanup(shutil.rmtree, mapa, ignore_errors=True)
        pot = os.path.join(mapa, "dovoljenja.json")
        with mock.patch.object(link_dostop, "os", _OsBrez()):
            self.assertIsNotNone(link_dostop._na_disk(pot, {"n-0123456789abcdef": {"files"}}, set(), 0.0))
        with open(pot, encoding="utf-8") as d:
            self.assertIn("n-0123456789abcdef", json.load(d)["naprave"])


# ---------------------------------------------------------------------- G. zeton mostu z ne-ASCII

class ZetonMostu(unittest.TestCase):
    def test_ne_ascii_ni_napaka(self):
        from core import safeer_link
        self.assertFalse(safeer_link.zeton_velja({"t": "žeton"}))
        self.assertTrue(safeer_link.zeton_velja({"t": safeer_link.ZETON_MOSTU}))


if __name__ == "__main__":
    unittest.main()
