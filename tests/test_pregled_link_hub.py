"""Varnostni pregled sredisca Safeer Link (19. 10. 2026): vsak preizkus tu brez popravka pade.

1. umik iz kroga velja takoj (zeton, vstopnica, ponoven vpis, sorodniki, vabila, povezava WebSocket);
2. vpis kljuca ne prevzame tujega id-ja, id iz kljuca dobi samo svoj kljuc;
3. ime spremeni samo clan kroga s kljucem, naprava brez kljuca nicesar (POST /cast/devices/rename in trust.names);
4. sestavljeno sporocilo WebSocket ima mejo za celoto, ne le za okvir;
5. vrstica zahteve in glave imajo skupni rok, nepreverjeni viri omejeno stevilo hkratnih povezav;
6. primerjava skrivnosti z ne-ASCII nizom ne podre obravnave;
7. vzporedne in nadaljevane oddaje ne napolnijo diska.

Strezniki v teh preizkusih poslusajo samo na 127.0.0.1.
"""
import base64
import hashlib
import http.client
import io
import json
import os
import shutil
import socket
import ssl
import tempfile
import threading
import time
import unittest
from unittest import mock

from core import link_hub_deljenje, link_hub_streznik, link_kripto, link_krog, link_obramba, link_ws

TAB = "tablica-1"          # star id (ni iz kljuca), kot v najdbi pregleda
NAS = "n-racunalnik"


def _kljuc(mapa: str, ime: str) -> str:
    """Javni kljuc nove naprave (SPKI DER v base64); zasebni kljuc in potrdilo ostaneta v `mapa`."""
    pot = os.path.join(mapa, ime + ".pem")
    link_kripto.ustvari_kljuc_in_potrdilo(pot, os.path.join(mapa, ime + "-potrdilo.pem"), ime)
    return base64.b64encode(link_kripto.javni_kljuc_der(pot)).decode("ascii")


class LaznaPovezava:
    def __init__(self, naslov="192.168.0.50"):
        self.naslov = naslov
        self.poslano = []
        self.podatki = {}
        self.zaprta_z = None

    def poslji(self, besedilo, **_k):
        self.poslano.append(json.loads(besedilo))
        return True

    def zapri(self, koda=1000, razlog=""):
        self.zaprta_z = (koda, razlog)

    def zadnje(self, tip):
        return next((s for s in reversed(self.poslano) if s.get("type") == tip), None)


def _prijava(id_naprave, ime="Naprava"):
    return json.dumps({"id": "r1", "type": "cast.register",
                       "payload": {"device_id": id_naprave, "name": ime, "role": "receiver", "capabilities": ["url"],
                                   "platform": "android", "protocol": "1", "kind": "tablet", "version": "2.1.200"}})


def _streznik_na_zanki(test: unittest.TestCase, hub, mapa: str) -> int:
    """Pravi streznik sredisca (TLS, _Obravnava) samo na 127.0.0.1; vrne vrata. Pospravi se sam."""
    kljuc, potrdilo = os.path.join(mapa, "hub.pem"), os.path.join(mapa, "hub-potrdilo.pem")
    link_kripto.ustvari_kljuc_in_potrdilo(kljuc, potrdilo, "hub")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(potrdilo, kljuc)
    s = link_hub_streznik._Streznik(("127.0.0.1", 0), link_hub_streznik._Obravnava)
    s.socket = ctx.wrap_socket(s.socket, server_side=True, do_handshake_on_connect=False)
    s.hub = hub
    s.obramba = link_obramba.Obramba()
    s.datoteke = lambda: None
    s.zaslon = lambda: None
    nit = threading.Thread(target=s.serve_forever, name="preizkus-pregled-hub", daemon=True)
    nit.start()

    def konec():
        s.shutdown()
        s.server_close()
        nit.join(5)
    test.addCleanup(konec)
    return s.server_address[1]


def _odjemalec_tls() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _post(vrata: int, pot: str, telo: dict, zeton: str = "") -> tuple:
    c = http.client.HTTPSConnection("127.0.0.1", vrata, timeout=5, context=_odjemalec_tls())
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
    """Pravi krog zaupanja (v pomnilniku) namesto kroga uporabnika."""

    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-pregled-hub-")
        self.addCleanup(shutil.rmtree, self.mapa, ignore_errors=True)
        self.krog = link_krog.Krog()
        p = mock.patch.object(link_krog, "krog", return_value=self.krog)
        p.start()
        self.addCleanup(p.stop)


# ---------------------------------------------------------------------- 1. umik velja takoj

class UmikVeljaTakoj(_SKrogom):
    def setUp(self):
        super().setUp()
        self.k_tab = _kljuc(self.mapa, "tablica")
        self.pot_zetonov = os.path.join(self.mapa, "hub-zetoni.json")
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=NAS, pot_zetonov=self.pot_zetonov)
        # Zeton, kakrsnega da seznanitev s kodo; z njim naprava vpise svoj kljuc v krog.
        self.zeton = self.hub.zeton_lastne_naprave(TAB, "Tablica")
        odgovor, napaka = self.hub.vpisi_v_krog(self.zeton, self.k_tab, "Tablica", "android")
        self.assertIsNone(napaka)
        self.assertTrue(self.krog.je_clan(TAB))

    def _umakni(self):
        """Uporabnik napravo odstrani iz Linka (na kateri koli napravi; umik pride v ta krog)."""
        self.assertTrue(self.krog.umakni(TAB, "n-televizor", max(time.time(), self.krog.clan(TAB)["dodano"] + 0.001)))
        time.sleep(0.01)
        self.assertTrue(self.krog.je_umaknjen(TAB))

    def test_zeton_po_umiku_ne_velja(self):
        self._umakni()
        self.assertIsNone(self.hub.naprava_zetona(self.zeton))
        self.assertIsNone(self.hub.vstopnica_z_zetonom(self.zeton), "brez vstopnice za WebSocket")
        with open(self.pot_zetonov, encoding="utf-8") as d:
            self.assertNotIn(self.zeton, json.load(d), "zeton gre tudi iz shrambe na disku")

    def test_umaknjena_se_s_starim_zetonom_ne_vpise_znova(self):
        self._umakni()
        self.assertEqual(self.hub.vpisi_v_krog(self.zeton, self.k_tab, "Tablica", "android"),
                         (None, "naprava_ni_seznanjena"))
        self.assertTrue(self.krog.je_umaknjen(TAB), "umik ostane")

    def test_umaknjena_ne_dobi_sorodnika(self):
        self._umakni()
        self.assertEqual(self.hub.sorodni_zeton(self.zeton, TAB + "-2", "Druga"), (None, "naprava_ni_seznanjena"))

    def test_sorodnik_umaknjene_naprave_ne_velja(self):
        sorodni, napaka = self.hub.sorodni_zeton(self.zeton, TAB + "-control", "Safeer Control")
        self.assertIsNone(napaka)
        self._umakni()
        self.assertIsNone(self.hub.naprava_zetona(sorodni), "sorodnik umaknjene naprave ne velja vec")

    def test_sorodnik_ne_podaljsa_veljavnosti_in_samo_ena_raven(self):
        cas = [1_000_000.0]
        hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=NAS, ura=lambda: cas[0])
        zeton = hub.zeton_lastne_naprave("fon-1", "Telefon")
        cas[0] += 3600.0
        sorodni, napaka = hub.sorodni_zeton(zeton, "fon-1-control", "Safeer Control")
        self.assertIsNone(napaka)
        self.assertEqual(hub.sorodni_zeton(sorodni, "fon-1-control-2", "Tretji"), (None, "ni_sorodnik"),
                         "zeton sorodnika ne izda novega sorodnika")
        cas[0] = 1_000_000.0 + link_hub_streznik.ZETON_VELJA_S + 1.0
        self.assertIsNone(hub.naprava_zetona(zeton))
        self.assertIsNone(hub.naprava_zetona(sorodni), "sorodnik potece skupaj z zetonom, iz katerega je nastal")

    def test_sprememba_kroga_zapre_povezavo_in_pobrise_seje(self):
        p = LaznaPovezava()
        p.podatki.update({"id": TAB, "izdano": time.time() - 5.0, "stars": ""})
        self.assertEqual(json.loads(self.hub.obdelaj(p, _prijava(TAB)))["status"], "accepted")
        seja = self.hub._nova_seja(TAB)
        self._umakni()
        self.hub._po_spremembi_kroga()          # kot ob mesh.trust ali pospravi_krog
        self.assertEqual((p.zaprta_z or (None,))[0], 1008, "povezava umaknjene naprave se zapre")
        self.assertIsNone(self.hub.najdi(TAB).povezava)
        self.assertNotIn(seja, self.hub._seje)
        self.assertNotIn(self.zeton, self.hub._zetoni)

    def test_umaknjena_povezava_ne_vabi(self):
        p = LaznaPovezava()
        p.podatki.update({"id": TAB, "izdano": time.time() - 5.0})
        self.hub.obdelaj(p, _prijava(TAB))
        self._umakni()                          # sredisce tega ne vidi: krog je spremenil drug del programa
        odgovor = json.loads(self.hub.obdelaj(p, json.dumps({"id": "v1", "type": "pair.invite", "payload": {}})))
        self.assertEqual((odgovor["status"], odgovor.get("error_code")), ("rejected", "umaknjen"))
        self.assertIsNone(p.zadnje("pair.invite.ok"), "umaknjena naprava ne dobi kode vabila")
        self.assertTrue(p.podatki.get("zapri_po_odgovoru"), "povezava se po zavrnitvi zapre")
        self.assertIsNone(self.hub.najdi(TAB).povezava)

    def test_napaka_branja_kroga_ne_izbrise_seznanitev(self):
        """Varovalka: ce kroga ta hip ni mogoce prebrati, se zahteva zavrne, zetoni in povezave pa ostanejo - sicer bi
        ena napaka branja (ali pokvarjen zapis v krogu) vse naprave odseznanila."""
        drugi = self.hub.zeton_lastne_naprave("fon-1", "Telefon")
        p = LaznaPovezava()
        p.podatki.update({"id": TAB, "izdano": time.time() - 5.0, "stars": ""})
        self.hub.obdelaj(p, _prijava(TAB))
        with mock.patch.object(self.krog, "umaknjen_ob", side_effect=RuntimeError("krog ni berljiv")):
            self.assertIsNone(self.hub.naprava_zetona(self.zeton), "ob neznanem stanju kroga zahteva ne gre skozi")
            self.hub.preklici_umaknjene()
        self.assertIsNone(p.zaprta_z, "povezava ostane")
        self.assertIsNotNone(self.hub.naprava_zetona(self.zeton), "zeton ostane in velja, ko je krog spet berljiv")
        self.assertIsNotNone(self.hub.naprava_zetona(drugi))
        with open(self.pot_zetonov, encoding="utf-8") as d:
            self.assertIn(self.zeton, json.load(d))

    def test_nova_seznanitev_po_umiku_velja(self):
        """Varovalka: uporabnik napravo po umiku znova poveze - novi zeton velja, vpis jo vrne v krog."""
        self._umakni()
        nov = self.hub.zeton_lastne_naprave(TAB, "Tablica")
        self.assertIsNotNone(self.hub.naprava_zetona(nov))
        self.assertIsNone(self.hub.vpisi_v_krog(nov, self.k_tab, "Tablica", "android")[1])
        self.assertFalse(self.krog.je_umaknjen(TAB))


class UmikPoHttp(_SKrogom):
    def test_umaknjena_naprava_po_http_nima_nicesar(self):
        k_tab = _kljuc(self.mapa, "tablica")
        hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=NAS)
        vrata = _streznik_na_zanki(self, hub, self.mapa)
        zeton = hub.zeton_lastne_naprave(TAB, "Tablica")
        self.assertEqual(_post(vrata, "/cast/trust/enroll", {"pubkey": k_tab, "name": "Tablica"}, zeton)[0], 200)
        self.assertTrue(self.krog.umakni(TAB, "n-televizor", max(time.time(), self.krog.clan(TAB)["dodano"] + 0.001)))
        time.sleep(0.01)
        for pot, telo in (("/cast/ticket", {}),
                          ("/cast/trust/enroll", {"pubkey": k_tab, "name": "Tablica"}),
                          ("/cast/pair/sibling", {"device_id": TAB + "-2", "name": "Druga"}),
                          ("/cast/pair/qr/invite", {}),
                          ("/cast/pair/qr/approve", {"secret": "123456"})):
            self.assertEqual(_post(vrata, pot, telo, zeton)[0], 401, pot)
        self.assertTrue(self.krog.je_umaknjen(TAB), "umik ostane")


# ---------------------------------------------------------------------- 2. vpis kljuca

class VpisKljuca(_SKrogom):
    def setUp(self):
        super().setUp()
        self.k_tv, self.k_tujec = _kljuc(self.mapa, "tv"), _kljuc(self.mapa, "tujec")
        self.krog.dodaj("tv-1", self.k_tv, "Televizor", "tv", NAS, dodano=time.time() - 60.0)
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=NAS)

    def test_vpis_ne_zamenja_kljuca_clana(self):
        zeton = self.hub.zeton_lastne_naprave("tv-1", "Televizor")     # tujec se je seznanil pod id-jem televizorja
        self.assertEqual(self.hub.vpisi_v_krog(zeton, self.k_tujec, "Televizor", "tv"), (None, "id_zaseden"))
        self.assertEqual(self.krog.clan("tv-1")["kljuc"], self.k_tv)

    def test_isti_kljuc_znova_dovoljen(self):
        zeton = self.hub.zeton_lastne_naprave("tv-1", "Televizor")
        self.assertIsNone(self.hub.vpisi_v_krog(zeton, self.k_tv, "Televizor", "tv")[1])

    def test_id_iz_kljuca_samo_s_svojim_kljucem(self):
        id_tv = link_krog.id_iz_kljuca(self.k_tv)
        zeton = self.hub.zeton_lastne_naprave(id_tv, "Televizor")
        self.assertEqual(self.hub.vpisi_v_krog(zeton, self.k_tujec, "Televizor", "tv"), (None, "neveljaven_kljuc"))
        self.assertIsNone(self.krog.clan(id_tv))
        self.assertEqual(self.krog.clan_za_id(id_tv)["kljuc"], self.k_tv, "id iz kljuca televizorja ostane njegov")
        self.assertIsNone(self.hub.vpisi_v_krog(zeton, self.k_tv, "Televizor", "tv")[1], "pravi kljuc gre")


class SeznanitevNePrevzameId(_SKrogom):
    """Seznanitev s kodo ali QR ne da zetona za id, ki ze pripada napravi v krogu: id si naprava izbere sama, krog in
    link_dostop.jedro pa bi jo (brez dokaza kljuca) obravnavala kot to napravo - tudi kot ta racunalnik."""

    def setUp(self):
        super().setUp()
        k_pc, k_tv = _kljuc(self.mapa, "pc"), _kljuc(self.mapa, "tv")
        self.pc = link_krog.id_iz_kljuca(k_pc)
        self.krog.dodaj(self.pc, k_pc, "Racunalnik", "linux", self.pc, dodano=time.time() - 60.0)
        self.krog.dodaj("tv-1", k_tv, "Televizor", "tv", self.pc, dodano=time.time() - 60.0)
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=self.pc)

    def _koda(self, device_id):
        """Celotna seznanitev s kodo (SPAKE2), kot jo naredi nova naprava. Vrne (zeton, napaka)."""
        from core.spake2 import Spake2
        zacetek = self.hub.zacni_seznanitev(device_id, "Nova")
        if not zacetek or zacetek.get("napaka"):
            return None, (zacetek or {}).get("napaka")
        pair_id = zacetek["pair_id"]
        odjemalec = Spake2.odjemalec(self.hub._prijave[pair_id]["pin"], device_id,
                                     link_hub_streznik.IDENTITETA_HUBA, b"ab" * 32, pair_id.encode())
        pa, _ca, napaka = self.hub.spake_korak1(pair_id, device_id, odjemalec.sporocilo())
        if napaka:
            return None, napaka
        _k, cb = odjemalec.zakljuci(pa)
        return self.hub.spake_korak2(pair_id, device_id, cb)

    def test_koda_ne_da_identitete_tega_racunalnika(self):
        self.assertEqual(self._koda(self.pc + "-x"), (None, "id_zaseden"))
        self.assertEqual(self._koda(self.pc), (None, "id_zaseden"))

    def test_koda_ne_da_identitete_clana(self):
        self.assertEqual(self._koda("tv-1"), (None, "id_zaseden"))

    def test_clan_med_seznanitvijo(self):
        """Id, ki ga je clan dobil med zacetkom in koncem seznanitve, ne dobi zetona."""
        from core.spake2 import Spake2
        k_tab = _kljuc(self.mapa, "tab")
        tab = link_krog.id_iz_kljuca(k_tab)
        zacetek = self.hub.zacni_seznanitev(tab + "-x", "Nova")
        pair_id = zacetek["pair_id"]
        odjemalec = Spake2.odjemalec(self.hub._prijave[pair_id]["pin"], tab + "-x",
                                     link_hub_streznik.IDENTITETA_HUBA, b"ab" * 32, pair_id.encode())
        pa, _ca, _n = self.hub.spake_korak1(pair_id, tab + "-x", odjemalec.sporocilo())
        self.krog.dodaj(tab, k_tab, "Tablica", "android", self.pc)
        self.assertEqual(self.hub.spake_korak2(pair_id, tab + "-x", odjemalec.zakljuci(pa)[1]), (None, "id_zaseden"))

    def test_qr_ne_da_identitete_clana(self):
        qr_id, skrivnost = self.hub.ustvari_pridruzitev()
        self.assertEqual(self.hub.pridruzi(qr_id, skrivnost, self.pc + "-x", "Nova"), (None, "id_zaseden"))
        self.assertEqual(self.hub.zacni_qr(self.pc + "-x", "Nova", "android", "ab" * 32, "p" * 20),
                         (None, "id_zaseden"))

    def test_qr_odobritev_ne_da_identitete_clana(self):
        """Prijava QR, ki se je zacela, preden je id dobil clan: odobritev zetona ne izda."""
        k_tab = _kljuc(self.mapa, "tab")
        tab = link_krog.id_iz_kljuca(k_tab)
        skrivnost = "s" * 32
        qr_id, napaka = self.hub.zacni_qr(tab, "Tablica", "android", hashlib.sha256(skrivnost.encode()).hexdigest(),
                                          "p" * 20)
        self.assertIsNone(napaka)
        self.krog.dodaj(tab, k_tab, "Tablica", "android", self.pc)
        self.assertEqual(self.hub.odobri_qr(qr_id, skrivnost, self.pc), (None, "id_zaseden"))

    def test_nova_in_umaknjena_naprava_se_seznanita(self):
        """Varovalka: nova naprava in naprava, umaknjena iz kroga, se s kodo in QR seznanita kot doslej."""
        zeton, napaka = self._koda("telefon-1")
        self.assertIsNone(napaka)
        self.assertEqual(self.hub.naprava_zetona(zeton)[0], "telefon-1")
        self.assertTrue(self.krog.umakni("tv-1", self.pc, time.time()))
        time.sleep(0.01)
        self.assertIsNone(self._koda("tv-1")[1])
        qr_id, skrivnost = self.hub.ustvari_pridruzitev()
        self.assertIsNone(self.hub.pridruzi(qr_id, skrivnost, "telefon-2", "Telefon")[1])

    def test_http_vrne_409(self):
        vrata = _streznik_na_zanki(self, self.hub, self.mapa)
        koda, odgovor = _post(vrata, "/cast/pair/start", {"device_id": self.pc + "-x", "name": "Nova"})
        self.assertEqual((koda, odgovor.get("code") or odgovor.get("error_code")), (409, "id_zaseden"))


# ---------------------------------------------------------------------- 3. preimenovanje

class Preimenovanje(_SKrogom):
    def setUp(self):
        super().setUp()
        k_tv, k_pc, k_tab = _kljuc(self.mapa, "tv"), _kljuc(self.mapa, "pc"), _kljuc(self.mapa, "tab")
        self.tv, self.pc, self.tab = (link_krog.id_iz_kljuca(k) for k in (k_tv, k_pc, k_tab))
        self.krog.dodaj(self.tv, k_tv, "Android TV", "tv", self.pc, dodano=100.0)
        self.krog.dodaj(self.pc, k_pc, "Racunalnik", "linux", self.pc, dodano=101.0)
        self.krog.dodaj(self.pc + "-control", k_pc, "Safeer Control", "linux", self.pc, dodano=102.0)
        self.krog.dodaj(self.tab, k_tab, "Tablica", "android", self.pc, dodano=103.0)
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=self.pc)
        self.z_tab = self.hub.zeton_lastne_naprave(self.tab, "Tablica")
        self.z_control = self.hub.zeton_lastne_naprave(self.pc + "-control", "Safeer Control")
        # Naprava samo z zetonom seznanitve (kljuca se ni vpisala v krog).
        self.z_brez = self.hub.zeton_lastne_naprave("fon-1", "Telefon")

    def test_naprava_brez_kljuca_ne_preimenuje(self):
        """Lastnik 19. 10. 2026: preimenuje lahko vsak clan kroga s kljucem, naprava brez kljuca v krogu nicesar."""
        koda, odgovor = self.hub.preimenuj_napravo(self.z_brez, self.tv, "Vdrto")
        self.assertEqual((koda, odgovor.get("koda")), (403, "tuja_naprava"))
        self.assertEqual(self.krog.clan(self.tv)["ime"], "Android TV")

    def test_clan_preimenuje_drugo_napravo(self):
        """Safeer OS na televizorju poimenuje naprave za vse v hisi (LinkMost.preimenujNapravo)."""
        self.assertEqual(self.hub.preimenuj_napravo(self.z_tab, self.tv, "Dnevna soba")[0], 200)
        self.assertEqual(self.krog.clan(self.tv)["ime"], "Dnevna soba")

    def test_naprava_preimenuje_sebe(self):
        self.assertEqual(self.hub.preimenuj_napravo(self.z_tab, self.tab, "Moja tablica")[0], 200)
        self.assertEqual(self.krog.clan(self.tab)["ime"], "Moja tablica")

    def test_control_tega_racunalnika_preimenuje_vse(self):
        self.assertEqual(self.hub.preimenuj_napravo(self.z_control, self.tv, "Dnevna soba")[0], 200)
        self.assertEqual(self.krog.clan(self.tv)["ime"], "Dnevna soba")

    def _ponudi_imena(self, kdo):
        p = LaznaPovezava()
        self.hub.obdelaj(p, _prijava(kdo))
        ponujeno = self.krog.json()
        zdaj = time.time()
        ponujeno["clani"][self.tv].update(ime="Vdrto", imenovano=zdaj)
        ponujeno["clani"][self.tab].update(ime="Moja tablica", imenovano=zdaj)
        self.hub.obdelaj(p, json.dumps({"id": "n1", "type": "trust.names", "payload": ponujeno}))

    def test_trust_names_clana_s_kljucem(self):
        """Televizor ob povezavi poslje imena vseh clanov iz svojega kroga: clan s kljucem jih sme dati."""
        self._ponudi_imena(self.tab)
        self.assertEqual(self.krog.clan(self.tv)["ime"], "Vdrto")
        self.assertEqual(self.krog.clan(self.tab)["ime"], "Moja tablica")

    def test_trust_names_naprave_brez_kljuca(self):
        self._ponudi_imena("fon-1")
        self.assertEqual(self.krog.clan(self.tv)["ime"], "Android TV", "naprava brez kljuca imen ne daje")
        self.assertEqual(self.krog.clan(self.tab)["ime"], "Tablica")

    def test_trust_names_tega_racunalnika(self):
        self._ponudi_imena(self.pc + "-control")
        self.assertEqual(self.krog.clan(self.tv)["ime"], "Vdrto")


# ---------------------------------------------------------------------- 4. WebSocket: meja sestavljenega sporocila

def _okvir(opkoda: int, telo: bytes, fin: bool = True, maska: bytes = b"\x01\x02\x03\x04") -> bytes:
    """Maskiran okvir odjemalca; `fin=False` = sporocilo se nadaljuje v naslednjem okvirju."""
    dolzina = len(telo)
    glava = bytes([(0x80 if fin else 0) | opkoda])
    if dolzina < 126:
        glava += bytes([0x80 | dolzina])
    elif dolzina < 65536:
        glava += bytes([0x80 | 126]) + dolzina.to_bytes(2, "big")
    else:
        glava += bytes([0x80 | 127]) + dolzina.to_bytes(8, "big")
    return glava + maska + link_ws.odmaskiraj(telo, maska)


class SestavljenoSporociloWs(unittest.TestCase):
    def setUp(self):
        self.a, self.b = socket.socketpair()
        self.prejeto = []
        self.koncano = threading.Event()
        self.p = link_ws.Povezava(self.a, "127.0.0.1", lambda _p, s: self.prejeto.append(s),
                                  lambda _p: self.koncano.set())
        threading.Thread(target=self.p.zanka_branja, daemon=True).start()

    def tearDown(self):
        self.p.zapri()
        for v in (self.a, self.b):
            try:
                v.close()
            except OSError:
                pass

    def _poslji(self, *okvirji):
        def poslji():
            try:
                for o in okvirji:
                    self.b.sendall(o)
            except OSError:
                pass                     # sredisce je povezavo zaprlo
        threading.Thread(target=poslji, daemon=True).start()

    def test_razdeljeno_sporocilo_nad_mejo_zapre_povezavo(self):
        pol = link_ws.NAJVECJE_SPOROCILO // 2 + 1
        self._poslji(_okvir(link_ws.OPKODA_BESEDILO, b"a" * pol, fin=False),
                     _okvir(link_ws.OPKODA_NADALJEVANJE, b"a" * pol, fin=False),
                     _okvir(link_ws.OPKODA_NADALJEVANJE, b"a", fin=True))
        self.assertTrue(self.koncano.wait(5), "sestavljeno sporocilo nad NAJVECJE_SPOROCILO mora zapreti povezavo")
        self.assertEqual(self.prejeto, [])

    def test_razdeljeno_do_meje_pride_skozi(self):
        cetrt = link_ws.NAJVECJE_SPOROCILO // 4
        self._poslji(_okvir(link_ws.OPKODA_BESEDILO, b"b" * cetrt, fin=False),
                     *[_okvir(link_ws.OPKODA_NADALJEVANJE, b"b" * cetrt, fin=(i == 2)) for i in range(3)])
        konec = time.time() + 5
        while not self.prejeto and time.time() < konec:
            time.sleep(0.01)
        self.assertEqual([len(s) for s in self.prejeto], [link_ws.NAJVECJE_SPOROCILO])
        self.assertFalse(self.koncano.is_set())


# ---------------------------------------------------------------------- 5. slowloris in meja povezav

class _LaznaZahteva:
    def shutdown(self, *_a):
        pass

    def close(self):
        pass


class MejaNepreverjenihPovezav(unittest.TestCase):
    def setUp(self):
        self.s = link_hub_streznik._Streznik(("127.0.0.1", 0), link_hub_streznik._Obravnava)
        self.addCleanup(self.s.server_close)
        self.s.obramba = link_obramba.Obramba()
        self.na_vir = getattr(link_hub_streznik, "NAJVEC_NEPREVERJENIH_NA_VIR", 16)

    def test_en_vir_ima_omejeno_stevilo_hkratnih_povezav(self):
        zahteve = [_LaznaZahteva() for _ in range(self.na_vir + 4)]
        sprejete = [self.s.verify_request(z, ("192.0.2.7", 40000 + i)) for i, z in enumerate(zahteve)]
        self.assertEqual(sprejete, [True] * self.na_vir + [False] * 4)
        drugi, nova = _LaznaZahteva(), _LaznaZahteva()
        self.assertTrue(self.s.verify_request(drugi, ("192.0.2.8", 1)), "drug vir ni prizadet")
        self.s.shutdown_request(zahteve[0])
        self.assertTrue(self.s.verify_request(nova, ("192.0.2.7", 2)), "zaprta povezava sprosti mesto")

    def test_skupna_meja_nepreverjenih(self):
        skupaj = getattr(link_hub_streznik, "NAJVEC_NEPREVERJENIH", 256)
        zahteve = [_LaznaZahteva() for _ in range(skupaj + 10)]      # odprte povezave: predmeti zivijo do konca
        sprejete = sum(self.s.verify_request(z, ("10.1.%d.%d" % (i // 200, i % 200 + 1), 1))
                       for i, z in enumerate(zahteve))
        self.assertEqual(sprejete, skupaj)

    def test_clan_in_ta_racunalnik_brez_meje(self):
        self.s.obramba.zaupaj("192.0.2.9")
        zahteve = [_LaznaZahteva() for _ in range(self.na_vir * 6)]
        self.assertTrue(all(self.s.verify_request(z, ("192.0.2.9", i)) for i, z in enumerate(zahteve[:self.na_vir * 3])))
        self.assertTrue(all(self.s.verify_request(z, ("127.0.0.1", i)) for i, z in enumerate(zahteve[self.na_vir * 3:])))


class GlavePoKapljicah(unittest.TestCase):
    def test_pocasne_glave_zaprejo_povezavo(self):
        mapa = tempfile.mkdtemp(prefix="safeer-pregled-hub-")
        self.addCleanup(shutil.rmtree, mapa, ignore_errors=True)
        vrata = _streznik_na_zanki(self, link_hub_streznik.Hub(odtis="ab" * 32), mapa)
        with mock.patch.object(link_hub_streznik._Obravnava, "ROK_GLAV_S", 1.5, create=True):
            v = _odjemalec_tls().wrap_socket(socket.create_connection(("127.0.0.1", vrata), timeout=5),
                                             server_hostname="127.0.0.1")
            self.addCleanup(v.close)
            v.sendall(b"GET /cast/health HTTP/1.1\r\nHost: preizkus\r\nX-Kapljice: ")
            v.settimeout(0.3)
            zacetek, zaprta = time.monotonic(), False
            while time.monotonic() - zacetek < 6.0:
                try:
                    v.sendall(b"x")          # en bajt na 0,3 s: rok enega recv (10 s) tega nikoli ne ujame
                    if v.recv(1024) == b"":
                        zaprta = True
                        break
                except socket.timeout:
                    continue
                except (OSError, ssl.SSLError):
                    zaprta = True
                    break
            trajalo = time.monotonic() - zacetek
        self.assertTrue(zaprta, "sredisce mora povezavo z glavami po kapljicah zapreti")
        self.assertLess(trajalo, 4.5)


# ---------------------------------------------------------------------- 6. primerjava skrivnosti

class PrimerjavaSkrivnosti(_SKrogom):
    def setUp(self):
        super().setUp()
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32, nas_id=NAS)

    def test_qr_skrivnost_z_neascii(self):
        qr_id, napaka = self.hub.zacni_qr("fon-1", "Telefon", "android", "a" * 64, "p" * 16)
        self.assertIsNone(napaka)
        self.assertEqual(self.hub.prevzemi_qr(qr_id, "fon-1", "č" * 16), ("qr_ne_obstaja", None))
        self.assertFalse(self.hub.preklici_qr(qr_id, "fon-1", "č" * 16))
        self.assertEqual(self.hub.prevzemi_qr(qr_id, "fon-1", "p" * 16), ("caka", None), "prava skrivnost dela")

    def test_zeton_z_neascii(self):
        self.hub.zeton_lastne_naprave("fon-1", "Telefon")
        self.assertIsNone(self.hub.naprava_zetona("žeton"))

    def test_kljuc_datoteke_in_zaslona_z_neascii(self):
        z = link_hub_deljenje.Deljenje(mapa=lambda: os.path.join(self.mapa, "zaloga"), prosto=lambda _m: 50 * 1024 ** 3)
        koda, _odgovor, d = z.sprejmi(io.BytesIO(b"abc"), 3, "a.txt", "tv1", "fon1")
        self.assertEqual(koda, 200)
        self.assertIsNone(z.najdi(d.id, "ključ"))
        zasloni = link_hub_deljenje.Zasloni(casovnik=lambda *_a: None)
        zs, _koda, _kdo = zasloni.zacni("fon1", "tv1")
        self.assertIsNotNone(zs)
        self.assertIsNone(zasloni.najdi(zs.id, "ključ"))

    def test_kljuc_clana_primerjan_v_stalnem_casu(self):
        k = _kljuc(self.mapa, "tv")
        self.krog.dodaj("tv-1", k, "Televizor", "tv", NAS, dodano=time.time() - 60.0)
        zeton = self.hub.zeton_lastne_naprave("tv-1", "Televizor")
        izvirna = getattr(link_hub_deljenje, "varno_enako", lambda a, b: a == b)
        with mock.patch.object(link_hub_deljenje, "varno_enako", side_effect=izvirna, create=True) as vohun:
            self.assertIsNone(self.hub.vpisi_v_krog(zeton, k, "Televizor", "tv")[1])
        self.assertIn(mock.call(k, k), vohun.call_args_list, "kljuc clana se primerja s compare_digest na bajtih")


# ---------------------------------------------------------------------- 7. prostor na disku

class _ZadrzanVhod:
    """Telo oddaje, ki se ustavi na prvem branju, dokler preizkus ne reče »naprej« (oddaja v teku)."""

    def __init__(self, vsebina: bytes) -> None:
        self._vhod = io.BytesIO(vsebina)
        self.zacel = threading.Event()
        self.naprej = threading.Event()

    def read(self, n):
        if not self.zacel.is_set():
            self.zacel.set()
            self.naprej.wait(10)
        return self._vhod.read(n)


class ProstorNaDisku(unittest.TestCase):
    S = 256 * 1024
    #: Rezerva diska v preizkusu (sicer link_viri.rezerva_diska pravega diska - preizkus ne sme odvisen od okolja).
    REZERVA = 1024 ** 3

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.prosto = self.REZERVA + self.S + self.S // 2      # prostor za eno oddajo, ne za dve
        self.z = link_hub_deljenje.Deljenje(mapa=lambda: os.path.join(self.tmp.name, "zaloga"),
                                            prosto=lambda _m: self.prosto, rezerva=lambda _m: self.REZERVA)

    def test_vzporedni_oddaji_ne_napolnita_diska(self):
        vsebina = os.urandom(self.S)
        vhod = _ZadrzanVhod(vsebina)
        izid = {}
        nit = threading.Thread(target=lambda: izid.update(a=self.z.sprejmi(vhod, self.S, "a.bin", "tv1", "fon1")),
                               daemon=True)
        nit.start()
        try:
            self.assertTrue(vhod.zacel.wait(5))
            koda, odgovor, d = self.z.sprejmi(io.BytesIO(vsebina), self.S, "b.bin", "tv1", "fon2")
        finally:
            vhod.naprej.set()
            nit.join(5)
        self.assertEqual((koda, odgovor.get("koda"), d), (507, "ni_prostora", None))
        self.assertEqual(izid["a"][0], 200)
        # Ko je prva oddaja koncana, je rezervacija sproscena: naslednja gre.
        self.assertEqual(self.z.sprejmi(io.BytesIO(vsebina), self.S, "c.bin", "tv1", "fon2")[0], 200)

    def test_nadaljevanje_preveri_prostor(self):
        vsebina = os.urandom(2 * self.S)
        sha = hashlib.sha256(vsebina).hexdigest()
        self.prosto = 10 * 1024 ** 3
        koda, odgovor, _d = self.z.sprejmi(io.BytesIO(vsebina[:self.S]), 2 * self.S, "v.bin", "tv1", "fon1", sha,
                                           skupaj=2 * self.S, odmik=0)
        self.assertEqual((koda, odgovor.get("odmik")), (400, self.S), "prekinjena oddaja pocaka na nadaljevanje")
        self.prosto = self.REZERVA + self.S // 2
        koda, odgovor, d = self.z.sprejmi(io.BytesIO(vsebina[self.S:]), self.S, "v.bin", "tv1", "fon1", sha,
                                          skupaj=2 * self.S, odmik=self.S)
        self.assertEqual((koda, odgovor.get("koda"), d), (507, "ni_prostora", None))
        self.prosto = 10 * 1024 ** 3
        koda, _odgovor, d = self.z.sprejmi(io.BytesIO(vsebina[self.S:]), self.S, "v.bin", "tv1", "fon1", sha,
                                           skupaj=2 * self.S, odmik=self.S)
        self.assertEqual((koda, d.sha256), (200, sha), "ko je prostor, se nadaljevanje konca")


if __name__ == "__main__":
    unittest.main()
