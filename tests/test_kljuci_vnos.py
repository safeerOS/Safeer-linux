"""Vnos kljuca debrid (TorBox, Real-Debrid, AllDebrid) in indeksatorja Usenet (npr. NZBFinder) na namizju kot na TV
(lastnik 25. 10. 2026; Android d1fdecc).

Vzorec (»XXXXXXXX-XXXX-…«) se zavrne brez klica storitve. Kljuc se ob vnosu preveri (TorBox user/me, Real-Debrid in
AllDebrid /user, indeksator z enim iskanjem): zavrnjen se ne shrani, izpad ga shrani kot NEPREVERJEN (ne »velja«).
Stanje (velja / ne velja / nepreverjen) je vezano na odtis kljuca, sledi uporabi (401 -> ne velja) in se nepreverjen
preveri znova najvec na 10 min. Shranjen je samo v zbirki skrivnosti (v nastavitvah le oznaka); odstranjen ali zamenjan
se izbrise tudi iz nje. Kljuc, e-naslov in uporabnisko ime racuna nikoli v izpis, dnevnik ali odgovor mostu. Brez pravega
omrezja: storitve so ponaredki (indeksator je lokalen streznik na 127.0.0.1). Kljuci so izmisljeni.
"""
import contextlib
import http.server
import io
import json
import logging
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

from core import debrid, debrid_pravila as P, os_media, usenet_pravila as U

#: Izmisljen; prejsnji (0f0e0d0c-…-050403020100, 17 nicel od 32 znakov) je vzorec (P.je_vzorec_kljuca).
KLJUC_TB = "7c1e9a4b-2f6d-4e8a-b3c5-9d0f1a2e6b74"
KLJUC_RD = "R7mK2pX9vL4qT8wN3zB6cH1jF5dS0gY2aE7uI4oP9kM3nV8bQ6xZ"
KLJUC_AD = "aB3dE5gH7jK9mN1pQ3sT"
UPORABNIK = "uporabnik-primer"
H1 = "a" * 39 + "1"
KLJUC_TB2 = "a1b2c3d4-e5f6-0718-293a-4b5c6d7e8f90"
KLJUC_IX = "0123456789abcdef0123456789abcdef"
EPOSTA = "oseba@primer.test"
#: Izmerjeno 25. 10. 2026 (nzbfinder.ws, izmisljen kljuc): HTTP 401 in to telo.
NZBFINDER_401 = '<?xml version="1.0" encoding="UTF-8"?>\n<error code="100" description="Incorrect user credentials (incorrect API key?)"/>'
RSS = '<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'


class Shramba:
    """Zbirka skrivnosti v pomnilniku: oznaka -> skrivnost (kot os_katalog.skrij/razkrij/pozabi)."""

    def __init__(self):
        self.zbirka: dict = {}
        self.n = 0

    def skrij(self, s: str) -> str:
        self.n += 1
        oznaka = "zbirka:%d" % self.n
        self.zbirka[oznaka] = s
        return oznaka

    def razkrij(self, v: str) -> str:
        return self.zbirka[v]

    def pozabi(self, v: str) -> None:
        self.zbirka.pop(v, None)


def _debrid():
    z = Shramba()
    nast = {"d": {}}
    d = debrid.Debrid(lambda: nast["d"], lambda x: nast.__setitem__("d", json.loads(json.dumps(x))),
                      z.skrij, z.razkrij, z.pozabi)
    return d, nast, z


class Pravila(unittest.TestCase):
    def test_torbox_preverba(self):
        self.assertEqual(P.torbox_preverba(200, {"success": True, "data": {"plan": 2, "email": EPOSTA}}), (P.PREVERBA_VELJAVEN, 2))
        self.assertEqual(P.torbox_preverba(200, {"success": True, "data": {"plan": True}}), (P.PREVERBA_VELJAVEN, None))
        self.assertEqual(P.torbox_preverba(403, {"success": False, "error": "BAD_TOKEN"}), (P.PREVERBA_NEVELJAVEN, None))
        self.assertEqual(P.torbox_preverba(200, {"success": False, "error": "AUTH_ERROR"}), (P.PREVERBA_NEVELJAVEN, None))
        self.assertEqual(P.torbox_preverba(401, None), (P.PREVERBA_NEVELJAVEN, None))
        self.assertEqual(P.torbox_preverba(429, {}), (P.PREVERBA_MEJA, None))
        self.assertEqual(P.torbox_preverba(502, None), (P.PREVERBA_NI_ODGOVORA, None))
        self.assertEqual(P.torbox_preverba(0, None), (P.PREVERBA_NI_ODGOVORA, None))
        # Paket tega ne omogoca: storitev kljuc pozna - velja (kot Android preverbaIzNapake).
        self.assertEqual(P.torbox_preverba(200, {"success": False, "error": "PLAN_RESTRICTED_FEATURE"}), (P.PREVERBA_VELJAVEN, None))
        self.assertEqual((P.ime_paketa(2), P.ime_paketa(0), P.ime_paketa(9), P.ime_paketa(None)), ("Pro", "Free", "paket 9", ""))
        self.assertFalse(P.shrani_po_preverbi(P.PREVERBA_NEVELJAVEN))
        self.assertFalse(P.shrani_po_preverbi(P.PREVERBA_OBLIKA))
        for izid in (P.PREVERBA_VELJAVEN, P.PREVERBA_MEJA, P.PREVERBA_NI_ODGOVORA):
            self.assertTrue(P.shrani_po_preverbi(izid))
        self.assertFalse(P.shrani_po_preverbi(""))                # storitve brez preverbe ni vec (prej PREVERBA_NI)

    def test_preverba_indeksatorja(self):
        self.assertEqual(U.preverba_indeksatorja(401, NZBFINDER_401), P.PREVERBA_NEVELJAVEN)
        self.assertEqual(U.preverba_indeksatorja(200, NZBFINDER_401), P.PREVERBA_NEVELJAVEN)
        self.assertEqual(U.preverba_indeksatorja(200, RSS), P.PREVERBA_VELJAVEN)
        self.assertEqual(U.preverba_indeksatorja(200, '<error code="500" description="Request limit reached"/>'), P.PREVERBA_MEJA)
        self.assertEqual(U.preverba_indeksatorja(429, ""), P.PREVERBA_MEJA)
        self.assertEqual(U.preverba_indeksatorja(200, "<html><body>prijava</body></html>"), P.PREVERBA_NI_ODGOVORA)
        self.assertEqual(U.preverba_indeksatorja(503, ""), P.PREVERBA_NI_ODGOVORA)
        self.assertIn("apikey=", U.naslov_preverbe("https://nzbfinder.ws", KLJUC_IX))
        self.assertTrue(U.naslov_preverbe("https://nzbfinder.ws", KLJUC_IX).startswith("https://nzbfinder.ws/api?t=search"))

    def test_velja_samo_s_pozitivnim_dokazom(self):
        """Grokov pregled 36, D1: Real-Debrid 403 brez telesa (pozarni zid, CDN, VPN, IP podatkovnega centra) in 2xx z {}
        sta dala »velja« - napacen kljuc je dobil »kljuc velja ✓« in bi sel med naprave (P.za_uskladitev)."""
        for http, telo in ((403, None), (403, {}), (200, {}),
                           (200, None), (200, {"type": "premium"}), (200, {"id": "7"}), (200, {"id": True}),
                           (200, {"username": ""}), (204, None)):
            self.assertEqual(P.rd_preverba(http, telo), P.PREVERBA_NI_ODGOVORA, (http, telo))
        self.assertEqual(P.rd_preverba(200, {"id": 7}), P.PREVERBA_VELJAVEN)
        self.assertEqual(P.rd_preverba(200, {"username": UPORABNIK}), P.PREVERBA_VELJAVEN)
        # Lastnik 26. 10. 2026 (zaklep racuna): 9 ni nikoli »velja«, 14 in 22 sta zaklenjen racun.
        self.assertEqual(P.rd_preverba(403, {"error": "permission_denied", "error_code": 9}), P.PREVERBA_NEVELJAVEN)
        self.assertEqual(P.rd_preverba(403, {"error": "account_locked", "error_code": 14}), P.PREVERBA_ZAKLENJEN)
        self.assertEqual(P.rd_preverba(403, {"error": "ip_not_allowed", "error_code": 22}), P.PREVERBA_ZAKLENJEN)
        self.assertEqual(P.rd_preverba(401, None), P.PREVERBA_NEVELJAVEN)
        # TorBox (api.torbox.app za Cloudflare): 403 brez kode TorBox ni zavrnjen kljuc - ne ob vpisu ne med uporabo.
        self.assertEqual(P.torbox_preverba(403, None), (P.PREVERBA_NI_ODGOVORA, None))
        self.assertEqual(P.torbox_preverba(403, {}), (P.PREVERBA_NI_ODGOVORA, None))
        self.assertEqual(P.torbox_preverba(403, {"success": False, "error": "BAD_TOKEN"}), (P.PREVERBA_NEVELJAVEN, None))
        self.assertEqual(P.torbox_vrsta_napake(403, None), P.NAPAKA_STREZNIK)
        self.assertEqual(P.torbox_vrsta_napake(403, "PLAN_RESTRICTED_FEATURE"), P.NAPAKA_PAKET)
        self.assertEqual(P.torbox_vrsta_napake(401, None), P.NAPAKA_KLJUC)
        # AllDebrid in indeksator: 403 brez napake storitve je ze bil »ni odgovora«.
        self.assertEqual(P.ad_preverba(403, None), P.PREVERBA_NI_ODGOVORA)
        self.assertEqual(U.preverba_indeksatorja(403, "<html><title>Just a moment...</title></html>"), P.PREVERBA_NI_ODGOVORA)

    def test_izberi_usenet(self):
        self.assertEqual(U.izberi_usenet([None, False, None], True), U.NOBENA)
        self.assertEqual(U.izberi_usenet([], False), U.NOBENA)
        self.assertEqual(U.izberi_usenet([False, None], False), U.CAKAJ)


class TorBox(unittest.TestCase):
    def test_veljaven_kljuc_shranjen_samo_v_zbirki_s_paketom(self):
        d, nast, z = _debrid()
        izhod = io.StringIO()
        odgovor = debrid.Odgovor(200, json.dumps({"success": True, "data": {"plan": 2, "email": EPOSTA}}))
        with mock.patch.object(debrid, "klic", return_value=odgovor) as k, self.assertLogs("safeer.debrid", logging.INFO) as dnevnik, \
                contextlib.redirect_stdout(izhod), contextlib.redirect_stderr(izhod):
            s = debrid.most(d, ["kljuc", P.TORBOX, " %s\n" % KLJUC_TB])
        self.assertEqual(k.call_args[0][:2], (P.TORBOX_UPORABNIK, KLJUC_TB))          # kljuc v glavi, ne v naslovu
        self.assertEqual((s["ok"], s["preverba"], s["paket"]), (True, P.PREVERBA_VELJAVEN, "Pro"))
        tb = next(x for x in s["storitve"] if x["id"] == P.TORBOX)
        self.assertEqual((tb["kljuc"], tb["paket"]), (True, "Pro"))
        self.assertIs(s["usenet"]["torbox_pro"], True)
        self.assertEqual(list(z.zbirka.values()), [KLJUC_TB])
        self.assertEqual(nast["d"]["kljuci"][P.TORBOX], "zbirka:1")                   # v nastavitvah samo oznaka
        for besedilo in (json.dumps(s), json.dumps(nast["d"]), izhod.getvalue(), "\n".join(dnevnik.output)):
            self.assertNotIn(KLJUC_TB, besedilo)
            self.assertNotIn(EPOSTA, besedilo)

    def test_zavrnjen_kljuc_ni_shranjen(self):
        d, nast, z = _debrid()
        with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(403, '{"success": false, "error": "BAD_TOKEN"}')):
            s = debrid.most(d, ["kljuc", P.TORBOX, KLJUC_TB])
        self.assertEqual((s["ok"], s["preverba"]), (False, P.PREVERBA_NEVELJAVEN))
        self.assertEqual((z.zbirka, nast["d"].get("kljuci")), ({}, None))

    def test_403_brez_json_ni_potrditev_ne_zavrnitev(self):
        """Grokov pregled 36, D1: RD 403 brez JSON (VPN, podatkovni center) je bil »kljuc velja ✓«; TorBox 403 s stranjo
        Cloudflare je veljaven kljuc zavrnil (ni shranjen) in med uporabo trajno oznacil »ne velja«."""
        stran = "<!DOCTYPE html><html><title>Attention Required! | Cloudflare</title></html>"
        for p, kljuc in ((P.REAL_DEBRID, KLJUC_RD), (P.TORBOX, KLJUC_TB), (P.ALLDEBRID, KLJUC_AD)):
            d, _nast, z = _debrid()
            with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(403, stran)):
                s = debrid.most(d, ["kljuc", p, kljuc])
            self.assertEqual((s["ok"], s["preverba"], _vrstica(s, p)["stanje"]),
                             (True, P.PREVERBA_NI_ODGOVORA, P.STANJE_NEPREVERJEN), p)
            self.assertFalse(d.kljuc_velja(p), p)                  # ne gre med naprave
            self.assertEqual(list(z.zbirka.values()), [kljuc], p)
        d, _nast, _z = _debrid()
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, 2)):
            d.vpisi_kljuc(P.TORBOX, KLJUC_TB)
        with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(403, stran)):
            self.assertEqual(d.predpomnjeni([H1]), set())
        self.assertEqual(d.stanje_kljuca(P.TORBOX), P.STANJE_VELJA)    # Cloudflare med uporabo kljuca ne zavrne

    def test_brez_povezave_shranjen_brez_paketa(self):
        d, _nast, z = _debrid()
        with mock.patch.object(debrid, "klic", side_effect=OSError("brez omrezja")):
            s = debrid.most(d, ["kljuc", P.TORBOX, KLJUC_TB])
        self.assertEqual((s["ok"], s["preverba"], s["paket"]), (True, P.PREVERBA_NI_ODGOVORA, ""))
        self.assertIsNone(s["usenet"]["torbox_pro"])
        self.assertEqual(list(z.zbirka.values()), [KLJUC_TB])
        # Izpad ni potrditev: nepreverjen, ne »velja« (prej je bil enak preverjenemu - »kljuc vpisan ✓«).
        self.assertEqual(next(x for x in s["storitve"] if x["id"] == P.TORBOX)["stanje"], P.STANJE_NEPREVERJEN)
        self.assertFalse(d.kljuc_velja(P.TORBOX))

    def test_napacna_oblika_brez_klica(self):
        d, _nast, z = _debrid()
        with mock.patch.object(debrid, "klic", side_effect=AssertionError("brez klica storitve")):
            s = debrid.most(d, ["kljuc", P.TORBOX, "https://torbox.app/settings"])
        self.assertEqual((s["ok"], s["preverba"], z.zbirka), (False, P.PREVERBA_OBLIKA, {}))

    def test_real_debrid_in_alldebrid_preverjena_ob_vnosu(self):
        """Prej sta se RD in AD shranila brez preverbe (PREVERBA_NI) - tudi vzorec in zavrnjen kljuc."""
        for p, kljuc, naslov, zavrnjen in (
                (P.REAL_DEBRID, KLJUC_RD, P.RD_UPORABNIK, debrid.Odgovor(401, '{"error": "bad_token", "error_code": 8}')),
                (P.ALLDEBRID, KLJUC_AD, P.AD_UPORABNIK,
                 debrid.Odgovor(200, '{"status": "error", "error": {"code": "AUTH_BAD_APIKEY"}}'))):
            d, nast, z = _debrid()
            with mock.patch.object(debrid, "klic", return_value=zavrnjen) as k:
                s = debrid.most(d, ["kljuc", p, kljuc])
            self.assertEqual(k.call_args[0][:2], (naslov, kljuc))                   # kljuc v glavi, ne v naslovu
            self.assertEqual((s["ok"], s["preverba"], z.zbirka, nast["d"].get("kljuci")), (False, P.PREVERBA_NEVELJAVEN, {}, None))
            racun = {"id": 7, "username": UPORABNIK, "email": EPOSTA} if p == P.REAL_DEBRID else \
                {"status": "success", "data": {"user": {"username": UPORABNIK, "email": EPOSTA, "isPremium": True}}}
            izhod = io.StringIO()
            with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(200, json.dumps(racun))), \
                    self.assertLogs("safeer.debrid", logging.INFO) as dnevnik, contextlib.redirect_stdout(izhod), \
                    contextlib.redirect_stderr(izhod):
                s = debrid.most(d, ["kljuc", p, kljuc])
            self.assertEqual((s["ok"], s["preverba"]), (True, P.PREVERBA_VELJAVEN))
            self.assertEqual(next(x for x in s["storitve"] if x["id"] == p)["stanje"], P.STANJE_VELJA)
            self.assertEqual(list(z.zbirka.values()), [kljuc])
            # Odgovor /user nosi uporabnisko ime in e-naslov: nic od tega (ne kljuc) v most, nastavitve, dnevnik ali izpis.
            for besedilo in (json.dumps(s), json.dumps(nast["d"]), izhod.getvalue(), "\n".join(dnevnik.output)):
                for skrito in (kljuc, EPOSTA, UPORABNIK):
                    self.assertNotIn(skrito, besedilo)

    def test_zamenjan_in_odstranjen_kljuc_izbrisan_iz_zbirke(self):
        """Prej je odstranitev pobrisala samo oznako v nastavitvah - kljuc je ostal v zbirki skrivnosti."""
        d, nast, z = _debrid()
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, 1)):
            self.assertTrue(debrid.most(d, ["kljuc", P.TORBOX, KLJUC_TB])["ok"])
            s = debrid.most(d, ["kljuc", P.TORBOX, KLJUC_TB2])
        self.assertEqual(list(z.zbirka.values()), [KLJUC_TB2])                       # stari izbrisan
        self.assertIs(s["usenet"]["torbox_pro"], False)
        self.assertEqual(d.kljuc(P.TORBOX), KLJUC_TB2)
        s = debrid.most(d, ["pozabi", P.TORBOX])
        self.assertEqual(z.zbirka, {})
        self.assertNotIn(P.TORBOX, nast["d"].get("paketi") or {})
        self.assertFalse(next(x for x in s["storitve"] if x["id"] == P.TORBOX)["kljuc"])

    def test_medijski_center_brise_iz_zbirke(self):
        tmp = tempfile.mkdtemp()
        try:
            z = Shramba()
            mc = os_media.MediaCenter(tmp, roots=[], secret_encryptor=z.skrij, secret_decryptor=z.razkrij,
                                      secret_forget=z.pozabi)
            with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, 2)):
                self.assertTrue(debrid.most(mc.debrid, ["kljuc", P.TORBOX, KLJUC_TB])["ok"])
            with open(tmp + "/debrid.json", encoding="utf-8") as f:
                self.assertNotIn(KLJUC_TB, f.read())
            debrid.most(mc.debrid, ["pozabi", P.TORBOX])
            self.assertEqual(z.zbirka, {})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class _Indeksator(http.server.BaseHTTPRequestHandler):
    odgovori: dict = {}
    zahteve: list = []

    def do_GET(self):  # noqa: N802 - ime iz http.server
        type(self).zahteve.append(self.path)
        koda, telo, glave = type(self).odgovori.get(self.path.split("?", 1)[0], (404, "", {}))
        self.send_response(koda)
        for k, v in glave.items():
            self.send_header(k, v)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.end_headers()
        self.wfile.write(telo.encode())

    def log_message(self, *_a):
        pass


class Indeksator(unittest.TestCase):
    def setUp(self):
        _Indeksator.odgovori, _Indeksator.zahteve = {}, []
        self.streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Indeksator)
        threading.Thread(target=self.streznik.serve_forever, daemon=True).start()
        self.osn = "http://127.0.0.1:%d" % self.streznik.server_address[1]     # http samo v domace omrezje (U.osnova)

    def tearDown(self):
        self.streznik.shutdown()
        self.streznik.server_close()

    def test_nzbfinder_zavrne_kljuc(self):
        _Indeksator.odgovori["/api"] = (401, NZBFINDER_401, {})
        d, nast, z = _debrid()
        izhod = io.StringIO()
        with self.assertLogs("safeer.debrid", logging.INFO) as dnevnik, contextlib.redirect_stdout(izhod), \
                contextlib.redirect_stderr(izhod):
            s = debrid.most(d, ["usenet", self.osn + "/api?", KLJUC_IX])
        self.assertEqual((s["ok"], s["preverba"]), (False, P.PREVERBA_NEVELJAVEN))
        self.assertEqual((z.zbirka, nast["d"].get("usenet")), ({}, None))
        self.assertEqual(len(_Indeksator.zahteve), 1)
        for besedilo in (json.dumps(s), izhod.getvalue(), "\n".join(dnevnik.output)):
            self.assertNotIn(KLJUC_IX, besedilo)

    def test_potrjen_kljuc_shranjen_samo_v_zbirki(self):
        _Indeksator.odgovori["/api"] = (200, RSS, {})
        d, nast, z = _debrid()
        s = debrid.most(d, ["usenet", self.osn, KLJUC_IX])
        self.assertEqual((s["ok"], s["preverba"], s["usenet"]["gostitelj"]), (True, P.PREVERBA_VELJAVEN, "127.0.0.1"))
        self.assertEqual(sorted(z.zbirka.values()), sorted([self.osn, KLJUC_IX]))
        self.assertNotIn(KLJUC_IX, json.dumps(nast["d"]))
        self.assertNotIn(KLJUC_IX, json.dumps(s))
        # Zamenjava in odstranitev izbriseta stare zapise iz zbirke.
        self.assertTrue(debrid.most(d, ["usenet", self.osn, KLJUC_IX[::-1]])["ok"])
        self.assertEqual(sorted(z.zbirka.values()), sorted([self.osn, KLJUC_IX[::-1]]))
        debrid.most(d, ["pozabi_usenet"])
        self.assertEqual(z.zbirka, {})

    def test_preusmeritve_ne_sledi(self):
        """Naslov preverbe nosi kljuc: preusmeritev (tudi na drug streznik) se ne sledi - kljuc ne gre naprej."""
        _Indeksator.odgovori["/api"] = (302, "", {"Location": self.osn + "/drugam"})
        _Indeksator.odgovori["/drugam"] = (200, RSS, {})
        d, _nast, z = _debrid()
        s = debrid.most(d, ["usenet", self.osn, KLJUC_IX])
        self.assertEqual(s["preverba"], P.PREVERBA_NI_ODGOVORA)
        self.assertEqual([p.split("?", 1)[0] for p in _Indeksator.zahteve], ["/api"])

    def test_kljuc_v_polju_za_naslov_ne_gre_nikamor(self):
        """Grokov pregled 31, H1: kljuc, prilepljen v polje za naslov, se ne shrani in ne gre v DNS ali do storitve;
        gola domena (»nzbfinder.ws«) dobi https:// sama (lastnik 25. 10. 2026, kot Android)."""
        d, nast, z = _debrid()
        with mock.patch.object(debrid, "indeksator_preveri", side_effect=AssertionError("brez klica")), \
                mock.patch("socket.getaddrinfo", side_effect=AssertionError("brez DNS")):
            for naslov in (KLJUC_IX, " %s " % KLJUC_TB, "https://%s/api" % KLJUC_IX, KLJUC_RD):
                s = debrid.most(d, ["usenet", naslov, KLJUC_IX])
                self.assertEqual((s["ok"], s["preverba"], z.zbirka), (False, U.PREVERBA_NASLOV_JE_KLJUC, {}), naslov)
                self.assertNotIn(KLJUC_IX, json.dumps(s))
        self.assertIsNone(nast["d"].get("usenet"))
        with mock.patch.object(debrid, "indeksator_preveri", return_value=P.PREVERBA_VELJAVEN) as pv:
            s = debrid.most(d, ["usenet", " nzbfinder.ws ", KLJUC_IX])
        self.assertEqual(pv.call_args[0], ("https://nzbfinder.ws", KLJUC_IX))
        self.assertEqual((s["ok"], s["usenet"]["gostitelj"]), (True, "nzbfinder.ws"))
        # Kljuc kot gostitelj, ki ga je shranila prejsnja razlicica: indeksatorja ni (nic ne gre v DNS).
        d2, nast2, z2 = _debrid()
        nast2["d"] = {"usenet": {"url": z2.skrij("https://" + KLJUC_IX), "kljuc": z2.skrij(KLJUC_IX)}}
        self.assertIsNone(d2.indeksator())

    def test_http_na_javni_naslov_zavrnjen_brez_klica(self):
        d, _nast, z = _debrid()
        with mock.patch.object(debrid, "indeksator_preveri", side_effect=AssertionError("brez klica")):
            s = debrid.most(d, ["usenet", "http://nzbfinder.ws", KLJUC_IX])
        self.assertEqual((s["ok"], s["preverba"], z.zbirka), (False, P.PREVERBA_OBLIKA, {}))


class UsenetTakojPravilo(unittest.TestCase):
    def test_boljsa_izdaja_se_pocaka(self):
        """izberi_usenet: dokler boljsa izdaja ni odgovorila, slabsa pripravljena se ne izbere (do roka)."""
        d, _nast, _z = _debrid()
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, 2)):
            d.vpisi_kljuc(P.TORBOX, KLJUC_TB)

        def tok(id_toka, *_a, **_k):
            if id_toka.endswith("1"):
                time.sleep(0.3)
            return debrid.Izid(url="https://cdn.tb/" + id_toka[-1], ponudnik=P.TORBOX)
        tokovi = [{"url": "usenet:000000000000000%d" % i, "naslov": "F%d" % i, "gb": 2.0} for i in (1, 2)]
        with mock.patch.object(d, "usenet_tok", side_effect=tok):
            izid = d.usenet_takoj(tokovi, rok=3.0)
        self.assertEqual((izid[0], izid[1].url), (0, "https://cdn.tb/1"))


def _vrstica(s: dict, p: str) -> dict:
    return next(x for x in s["storitve"] if x["id"] == p)


class StanjeKljuca(unittest.TestCase):
    """M1-M8 nacrta kljuci-namizje (Android d1fdecc): vzorec, stanje po odtisu, ponovna preverba, 401 med uporabo."""

    def test_vzorec_zavrnjen_brez_klica_storitve(self):
        """Lastnik 25. 10. 2026: vzorec »XXXXXXXX-XXXX-…« se je shranil kot »kljuc vpisan ✓«. Zdaj oblika, nic ne gre ven."""
        for p, vnos in ((P.TORBOX, "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"), (P.TORBOX, " your_api_key_here_123456 "),
                        (P.REAL_DEBRID, "abcabcabcabcabcabcabc"), (P.ALLDEBRID, "0000000000000000"),
                        (P.TORBOX, "k7Q2m9X4p1R8t5W3z6Y")):                   # 19 znakov: TorBox najmanj 20 (M8)
            d, nast, z = _debrid()
            with mock.patch.object(debrid, "klic", side_effect=AssertionError("vzorec ne gre do storitve")) as k:
                s = debrid.most(d, ["kljuc", p, vnos])
            self.assertEqual((s["ok"], s["preverba"], k.call_count, z.zbirka), (False, P.PREVERBA_OBLIKA, 0, {}), vnos)
            self.assertEqual(_vrstica(s, p)["stanje"], "")
        d, _nast, z = _debrid()
        with mock.patch.object(debrid, "indeksator_preveri", side_effect=AssertionError("vzorec ne gre do indeksatorja")):
            s = debrid.most(d, ["usenet", "https://nzbfinder.ws", "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"])
        self.assertEqual((s["ok"], s["preverba"], z.zbirka), (False, P.PREVERBA_OBLIKA, {}))

    def test_stanje_vezano_na_kljuc(self):
        """Zamenjan kljuc nima stanja prejsnjega; v nastavitvah je samo odtis (ne kljuc)."""
        d, nast, _z = _debrid()
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, P.TORBOX_PRO)):
            self.assertEqual(_vrstica(debrid.most(d, ["kljuc", P.TORBOX, KLJUC_TB]), P.TORBOX)["stanje"], P.STANJE_VELJA)
        self.assertTrue(d.kljuc_velja(P.TORBOX))
        zapis = nast["d"]["stanja"][P.TORBOX]
        self.assertEqual(zapis["odtis"], P.odtis_stanja(KLJUC_TB))
        self.assertNotIn(KLJUC_TB, json.dumps(nast["d"]))
        self.assertNotIn(KLJUC_TB[:8], zapis["odtis"])
        d.nastavi_kljuc(P.TORBOX, KLJUC_TB2)                    # npr. razlicica pred to - kljuc brez stanja
        self.assertIsNone(d.stanje_kljuca(P.TORBOX))
        self.assertEqual(_vrstica(d.stanje(), P.TORBOX)["stanje"], P.STANJE_NEPREVERJEN)
        with mock.patch.object(debrid, "klic", side_effect=OSError("brez omrezja")):
            debrid.most(d, ["kljuc", P.TORBOX, KLJUC_TB])       # spet prvi kljuc, a storitev ne odgovori
        self.assertEqual(d.stanje_kljuca(P.TORBOX), P.STANJE_NEPREVERJEN)   # ne »velja« od prej

    def test_401_med_uporabo_ne_velja_povezava_velja(self):
        d, _nast, _z = _debrid()
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, 2)):
            d.vpisi_kljuc(P.TORBOX, KLJUC_TB)
        with mock.patch.object(debrid, "torbox_tok", return_value=debrid.Izid(napaka=P.NAPAKA_KLJUC, ponudnik=P.TORBOX)), \
                self.assertLogs("safeer.debrid", logging.INFO) as dnevnik:
            self.assertEqual(d.tok(H1).napaka, P.NAPAKA_KLJUC)
        self.assertEqual(_vrstica(debrid.most(d, []), P.TORBOX)["stanje"], P.STANJE_NE_VELJA)
        self.assertNotIn(KLJUC_TB, "\n".join(dnevnik.output))
        self.assertEqual(d.kljuc(P.TORBOX), KLJUC_TB)           # kljuc ostane - uporabnik ga vpise znova ali »Preveri«
        # Lastnik 26. 10. 2026 (zaklep racuna): zavrnjenega kljuca ne posljemo vec, tudi ob predvajanju ne.
        with mock.patch.object(debrid, "torbox_tok", side_effect=AssertionError("brez klica")):
            self.assertEqual(d.tok(H1).napaka, P.NAPAKA_KLJUC)
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, 2)) as pv:
            s = debrid.most(d, ["preveri", P.TORBOX])            # uporabnik pritisne »Preveri«
        self.assertEqual((pv.call_count, s["ok"], _vrstica(s, P.TORBOX)["stanje"]), (1, True, P.STANJE_VELJA))
        with mock.patch.object(debrid, "torbox_tok", return_value=debrid.Izid(url="https://cdn.tb/f", ponudnik=P.TORBOX)):
            self.assertTrue(d.tok(H1).url)
        self.assertEqual(d.stanje_kljuca(P.TORBOX), P.STANJE_VELJA)
        # Zavrnjen kljuc ze ob preverbi ⚡ (checkcached 401).
        with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(401, '{"success": false, "error": "BAD_TOKEN"}')):
            self.assertEqual(d.predpomnjeni([H1]), set())
        self.assertEqual(d.stanje_kljuca(P.TORBOX), P.STANJE_NE_VELJA)

    def test_meja_in_izpad_med_uporabo_ne_spremenita_stanja(self):
        d, _nast, _z = _debrid()
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, 2)):
            d.vpisi_kljuc(P.TORBOX, KLJUC_TB)
        for napaka in (P.NAPAKA_MEJA, P.NAPAKA_STREZNIK, P.NAPAKA_NI_PREDPOMNJENO):
            with mock.patch.object(debrid, "torbox_tok", return_value=debrid.Izid(napaka=napaka, ponudnik=P.TORBOX)):
                d.tok(H1, samo_takoj=True)
            self.assertEqual(d.stanje_kljuca(P.TORBOX), P.STANJE_VELJA, napaka)

    def test_nepreverjen_preveri_znova_najvec_na_10_min(self):
        d, _nast, _z = _debrid()
        with mock.patch.object(debrid, "klic", side_effect=OSError("brez omrezja")):
            d.vpisi_kljuc(P.TORBOX, KLJUC_TB)
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, 2)) as pv:
            s = debrid.most(d, ["preveri"])                    # takoj po vpisu: ne (zadnja preverba < 10 min)
            self.assertEqual((pv.call_count, _vrstica(s, P.TORBOX)["stanje"]), (0, P.STANJE_NEPREVERJEN))
            d._zadnja_preverba[P.TORBOX] -= P.PREVERI_ZNOVA_S + 1
            s = debrid.most(d, ["preveri"])
            self.assertEqual((pv.call_count, _vrstica(s, P.TORBOX)["stanje"], _vrstica(s, P.TORBOX)["paket"]),
                             (1, P.STANJE_VELJA, "Pro"))
            debrid.most(d, ["preveri"])                         # veljaven se ne preverja znova (do 401 med uporabo)
            self.assertEqual(pv.call_count, 1)

    def test_kljuc_brez_stanja_preverjen_ob_odprtju_okna(self):
        """Kljuc iz razlicice pred to (brez stanja): okno ga preveri; zavrnjen ostane shranjen kot »ne velja«."""
        d, _nast, z = _debrid()
        d.nastavi_kljuc(P.REAL_DEBRID, KLJUC_RD)
        with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(401, '{"error": "bad_token", "error_code": 8}')) as k:
            s = debrid.most(d, ["preveri"])
            debrid.most(d, ["preveri"])
        self.assertEqual((k.call_count, k.call_args[0][0]), (1, P.RD_UPORABNIK))
        self.assertEqual(_vrstica(s, P.REAL_DEBRID)["stanje"], P.STANJE_NE_VELJA)
        self.assertEqual(list(z.zbirka.values()), [KLJUC_RD])
        self.assertFalse(d.kljuc_velja(P.REAL_DEBRID))

    def test_brez_stanja_najvec_ena_preverba_na_10_min(self):
        """Lastnik 26. 10. 2026 (zaklep racuna): kljuc brez stanja je bil preverjen ob VSAKEM odprtju okna, dokler se
        stanje ni zapisalo - ce zapis ne uspe (zbirka, disk), je bil vsak klik nov klic storitve."""
        d, _nast, _z = _debrid()
        d.nastavi_kljuc(P.TORBOX, KLJUC_TB)
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_NI_ODGOVORA, None)) as pv, \
                mock.patch.object(d, "_zapisi_stanje", return_value=False):
            for _ in range(5):
                debrid.most(d, ["preveri"])
            self.assertEqual(pv.call_count, 1)
            d.nastavi_kljuc(P.TORBOX, KLJUC_TB2)                 # drug kljuc: preveri se takoj
            debrid.most(d, ["preveri"])
            self.assertEqual(pv.call_count, 2)
            d._zadnja_preverba[P.TORBOX] -= P.PREVERI_ZNOVA_S + 1
            debrid.most(d, ["preveri"])
            self.assertEqual(pv.call_count, 3)

    def test_shranjen_vzorec_ne_gre_storitvi(self):
        """Grokov pregled 36, D7: vzorec iz prejsnje razlicice je samodejna preverba poslala storitvi (zavrnjen vpis)."""
        d, _nast, _z = _debrid()
        d.nastavi_kljuc(P.TORBOX, "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX")
        with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(401, "{}")) as k:
            s = debrid.most(d, ["preveri"])
            debrid.most(d, ["preveri"])
        self.assertEqual((k.call_count, _vrstica(s, P.TORBOX)["stanje"]), (0, P.STANJE_NE_VELJA))

    def test_zavrnjen_kljuc_ne_gre_v_samodejne_klice(self):
        """Lastnik 26. 10. 2026 (zaklep racuna): kljuc, ki ga je storitev zavrnila, je sel ob vsakem seznamu virov znova
        v ⚡ (checkcached) ter v iskanje in prenos NZB - vsak klic se en zavrnjen vpis pri storitvi."""
        d, _nast, _z = _debrid()
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, P.TORBOX_PRO)), \
                mock.patch.object(debrid, "indeksator_preveri", return_value=P.PREVERBA_VELJAVEN):
            d.vpisi_kljuc(P.TORBOX, KLJUC_TB)
            d.vpisi_indeksator("https://nzbfinder.ws", KLJUC_IX)
        self.assertTrue(d.usenet_na_voljo())
        d.ob_izidu(P.TORBOX, P.NAPAKA_KLJUC, False)
        with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(401, '{"success": false, "error": "BAD_TOKEN"}')) as k:
            self.assertEqual(d.predpomnjeni([H1]), set())
        self.assertEqual(k.call_count, 0)
        self.assertFalse(d.usenet_na_voljo())
        with mock.patch.object(debrid, "torbox_tok", side_effect=AssertionError("brez klica")):
            self.assertEqual(d.tok(H1).napaka, P.NAPAKA_KLJUC)  # tudi predvajanje ne (lastnik 26. 10. 2026)
        with mock.patch.object(debrid, "usenet_nzb", side_effect=AssertionError("brez klica")), \
                mock.patch.object(debrid, "torbox_usenet", side_effect=AssertionError("brez klica")):
            self.assertEqual(d.usenet_tok("usenet:0000000000000001", "F").napaka, P.NAPAKA_KLJUC)
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, P.TORBOX_PRO)):
            debrid.most(d, ["preveri", P.TORBOX])                # »Preveri« ga vrne v rabo
        self.assertTrue(d.usenet_na_voljo())
        d.ob_izidu(P.INDEKSATOR, P.NAPAKA_KLJUC, False)
        self.assertFalse(d.usenet_na_voljo())
        with mock.patch.object(debrid, "usenet_isci", side_effect=AssertionError("brez klica")):
            self.assertEqual(d.usenet_isci("tt0111161"), [])

    def test_zaklenjen_racun_ne_klicemo_do_preveri(self):
        """Lastnik 26. 10. 2026 (zaklep racuna): RD 14 »account locked« je bil »kljuc velja« (paket) in racun smo
        uporabljali naprej; RD 22 »ip not allowed« preverba na 10 min; AllDebrid AUTH_BLOCKED »ne velja«. Zdaj zaklenjen:
        kljuc shranjen, vrstica pove, kaj narediti, nobenega klica (ne ⚡, ne predvajanje, ne samodejna preverba) do
        uporabnikovega »Preveri«."""
        for p, kljuc, odgovor in (
                (P.REAL_DEBRID, KLJUC_RD, debrid.Odgovor(403, '{"error": "account_locked", "error_code": 14}')),
                (P.REAL_DEBRID, KLJUC_RD, debrid.Odgovor(403, '{"error": "ip_not_allowed", "error_code": 22}')),
                (P.ALLDEBRID, KLJUC_AD, debrid.Odgovor(200, '{"status": "error", "error": {"code": "AUTH_BLOCKED"}}'))):
            d, _nast, z = _debrid()
            with mock.patch.object(debrid, "klic", return_value=odgovor) as k:
                s = debrid.most(d, ["kljuc", p, kljuc])
            self.assertEqual((k.call_count, s["ok"], s["preverba"]), (1, True, P.PREVERBA_ZAKLENJEN), odgovor.telo)
            self.assertEqual(_vrstica(s, p)["stanje"], P.STANJE_ZAKLENJEN)
            self.assertEqual(list(z.zbirka.values()), [kljuc])
            self.assertFalse(d.kljuc_velja(p))                   # ne gre med naprave
            with mock.patch.object(debrid, "klic", side_effect=AssertionError("brez klica")) as k, \
                    mock.patch.object(debrid, "rd_tok", side_effect=AssertionError("brez klica")), \
                    mock.patch.object(debrid, "ad_tok", side_effect=AssertionError("brez klica")):
                self.assertEqual(d.tok(H1).napaka, P.NAPAKA_ZAKLENJEN)
                d._zadnja_preverba[p] -= 10 * P.PREVERI_ZNOVA_S
                debrid.most(d, ["preveri"])                      # samodejna preverba ga ne poskusi
            self.assertEqual(d.stanje_kljuca(p), P.STANJE_ZAKLENJEN)
            racun = '{"id": 7, "username": "u"}' if p == P.REAL_DEBRID else '{"status": "success", "data": {"user": {}}}'
            with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(200, racun)) as k:
                s = debrid.most(d, ["preveri", p])               # po odklepu uporabnik pritisne »Preveri«
            self.assertEqual((k.call_count, _vrstica(s, p)["stanje"]), (1, P.STANJE_VELJA))
        # RD 9 »permission denied« ni nikoli »velja« (ni premium ali ni dovoljenja): zavrnjen, ni shranjen.
        d, _nast, z = _debrid()
        with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(403, '{"error": "permission_denied", "error_code": 9}')):
            s = debrid.most(d, ["kljuc", P.REAL_DEBRID, KLJUC_RD])
        self.assertEqual((s["ok"], s["preverba"], z.zbirka), (False, P.PREVERBA_NEVELJAVEN, {}))

    def test_zaklenjen_med_uporabo(self):
        """AllDebrid AUTH_BLOCKED med predvajanjem (nova lokacija): zaklenjen, naslednje predvajanje brez klica."""
        d, _nast, _z = _debrid()
        with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(200, '{"status": "success", "data": {"user": {}}}')):
            d.vpisi_kljuc(P.ALLDEBRID, KLJUC_AD)
        blokiran = debrid.Odgovor(200, '{"status": "error", "error": {"code": "AUTH_BLOCKED", "message": "new location"}}')
        with mock.patch.object(debrid, "klic", return_value=blokiran) as k:
            self.assertEqual(d.tok(H1).napaka, P.NAPAKA_ZAKLENJEN)
            n = k.call_count
            self.assertEqual(d.tok(H1).napaka, P.NAPAKA_ZAKLENJEN)
        self.assertEqual((n, k.call_count, d.stanje_kljuca(P.ALLDEBRID)), (1, 1, P.STANJE_ZAKLENJEN))

    def test_zamenjan_med_preverbo_ne_dobi_stanja_starega(self):
        d, _nast, _z = _debrid()
        d.nastavi_kljuc(P.TORBOX, KLJUC_TB)

        def preveri(_k):
            d.nastavi_kljuc(P.TORBOX, KLJUC_TB2)               # uporabnik je medtem vpisal drug kljuc
            return P.PREVERBA_NEVELJAVEN, None
        with mock.patch.object(debrid, "torbox_preveri", side_effect=preveri):
            self.assertFalse(d.preveri_nepreverjene())
        self.assertIsNone(d.stanje_kljuca(P.TORBOX))
        self.assertIsNone(d._nastavitve().get("stanja", {}).get(P.TORBOX))

    def test_pravila_za_uskladitev_in_prejem(self):
        """secrets.sync na namizju se ni: pravili sta tu, da ju uskladitev uporabi od prvega dne (M7)."""
        self.assertEqual([P.za_uskladitev(s) for s in (P.STANJE_VELJA, P.STANJE_NEPREVERJEN, P.STANJE_NE_VELJA, None)],
                         [True, False, False, False])
        self.assertEqual([P.sprejmi_prejetega(i) for i in (P.PREVERBA_VELJAVEN, P.PREVERBA_MEJA, P.PREVERBA_NI_ODGOVORA,
                                                           P.PREVERBA_NEVELJAVEN, P.PREVERBA_OBLIKA)],
                         [True, False, False, False, False])


class StanjeIndeksatorja(unittest.TestCase):
    def setUp(self):
        _Indeksator.odgovori, _Indeksator.zahteve = {}, []
        self.streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Indeksator)
        threading.Thread(target=self.streznik.serve_forever, daemon=True).start()
        self.osn = "http://127.0.0.1:%d" % self.streznik.server_address[1]
        self.addCleanup(self.streznik.server_close)
        self.addCleanup(self.streznik.shutdown)

    def test_izpad_nepreverjen_iskanje_potrdi_401_zavrne_403_ne(self):
        d, _nast, _z = _debrid()
        _Indeksator.odgovori["/api"] = (503, "", {})
        s = debrid.most(d, ["usenet", self.osn, KLJUC_IX])
        self.assertEqual((s["ok"], s["preverba"], s["usenet"]["stanje"]), (True, P.PREVERBA_NI_ODGOVORA, P.STANJE_NEPREVERJEN))
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, P.TORBOX_PRO)):
            d.vpisi_kljuc(P.TORBOX, KLJUC_TB)
        _Indeksator.odgovori["/api"] = (200, RSS, {})
        d.usenet_isci("tt0111161")
        self.assertEqual(d.stanje_kljuca(P.INDEKSATOR), P.STANJE_VELJA)
        # Cloudflare (izmerjeno 25. 10. 2026 na nzbfinder.ws): 403 s stranjo HTML ni zavrnjen kljuc.
        _Indeksator.odgovori["/api"] = (403, "<!DOCTYPE html><html><title>Just a moment...</title></html>", {})
        d.usenet_isci("tt0111161")
        self.assertEqual(d.stanje_kljuca(P.INDEKSATOR), P.STANJE_VELJA)
        _Indeksator.odgovori["/api"] = (401, NZBFINDER_401, {})
        d.usenet_isci("tt0111161")
        self.assertEqual(debrid.most(d, [])["usenet"]["stanje"], P.STANJE_NE_VELJA)
        self.assertNotIn(KLJUC_IX, json.dumps(debrid.most(d, [])))
        # Zavrnjen: iskanje se ne ponavlja (lastnik 26. 10. 2026) - do »Preveri«.
        n = len(_Indeksator.zahteve)
        self.assertEqual((d.usenet_isci("tt0111161"), len(_Indeksator.zahteve)), ([], n))
        _Indeksator.odgovori["/api"] = (200, '<error code="101" description="Account suspended"/>', {})
        s = debrid.most(d, ["preveri", "usenet"])
        self.assertEqual((len(_Indeksator.zahteve), s["usenet"]["stanje"]), (n + 1, P.STANJE_ZAKLENJEN))
        self.assertFalse(d.usenet_na_voljo())
        _Indeksator.odgovori["/api"] = (200, RSS, {})
        self.assertEqual(debrid.most(d, ["preveri", "usenet"])["usenet"]["stanje"], P.STANJE_VELJA)


if __name__ == "__main__":
    unittest.main()
