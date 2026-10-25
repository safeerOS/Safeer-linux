"""Vnos kljuca TorBox in indeksatorja Usenet (npr. NZBFinder) na namizju kot na TV (lastnik 25. 10. 2026).

Kljuc se ob vnosu preveri (TorBox »user/me«, indeksator z enim iskanjem): zavrnjen se ne shrani, izpad storitve ga ne
zavrne. Shranjen je samo v zbirki skrivnosti (v nastavitvah le oznaka); odstranjen ali zamenjan se izbrise tudi iz zbirke.
Kljuc in e-naslov racuna nikoli v izpis, dnevnik ali odgovor mostu. Brez pravega omrezja: storitve so ponaredki
(indeksator je lokalen streznik na 127.0.0.1). Kljuci so izmisljeni.
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

KLJUC_TB = "0f0e0d0c-0b0a-0908-0706-050403020100"
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
        self.assertEqual((P.ime_paketa(2), P.ime_paketa(0), P.ime_paketa(9), P.ime_paketa(None)), ("Pro", "Free", "paket 9", ""))
        self.assertFalse(P.shrani_po_preverbi(P.PREVERBA_NEVELJAVEN))
        self.assertFalse(P.shrani_po_preverbi(P.PREVERBA_OBLIKA))
        for izid in (P.PREVERBA_VELJAVEN, P.PREVERBA_MEJA, P.PREVERBA_NI_ODGOVORA, P.PREVERBA_NI):
            self.assertTrue(P.shrani_po_preverbi(izid))

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

    def test_brez_povezave_shranjen_brez_paketa(self):
        d, _nast, z = _debrid()
        with mock.patch.object(debrid, "klic", side_effect=OSError("brez omrezja")):
            s = debrid.most(d, ["kljuc", P.TORBOX, KLJUC_TB])
        self.assertEqual((s["ok"], s["preverba"], s["paket"]), (True, P.PREVERBA_NI_ODGOVORA, ""))
        self.assertIsNone(s["usenet"]["torbox_pro"])
        self.assertEqual(list(z.zbirka.values()), [KLJUC_TB])

    def test_napacna_oblika_brez_klica(self):
        d, _nast, z = _debrid()
        with mock.patch.object(debrid, "klic", side_effect=AssertionError("brez klica storitve")):
            s = debrid.most(d, ["kljuc", P.TORBOX, "https://torbox.app/settings"])
        self.assertEqual((s["ok"], s["preverba"], z.zbirka), (False, P.PREVERBA_OBLIKA, {}))

    def test_drugi_storitvi_brez_preverbe(self):
        d, _nast, _z = _debrid()
        with mock.patch.object(debrid, "klic", side_effect=AssertionError("Real-Debrid se ob vnosu ne preverja")):
            s = debrid.most(d, ["kljuc", P.REAL_DEBRID, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ABCDEFGHIJKLMNOP"])
        self.assertEqual((s["ok"], s["preverba"]), (True, P.PREVERBA_NI))

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


if __name__ == "__main__":
    unittest.main()
