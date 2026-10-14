"""Odjemalec releja (core/link_rele.WsOdjemalec) s pravo povezavo TLS: branje in pisanje iz dveh niti.

Kanal skozi rele nosi obe smeri hkrati (`cev`: ena nit bere iz releja, druga vanj pise). Rele v preizkusu je
krajeven: TLS, rokovanje WebSocket, nato vsak okvir vrne posiljatelju. Preverjamo, da pridejo vsi bajti nazaj
nespremenjeni in da zaprtje iz druge niti takoj zbudi nit, ki bere.
"""
import base64
import hashlib
import re
import shutil
import socket
import ssl
import tempfile
import threading
import time
import unittest
from unittest import mock

from core import link_datoteke, link_rele, link_ws

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class _Rele:
    """Krajevni rele: sprejme vec povezav; `nacini[i]` doloci vedenje i-te povezave.

    "odmev" (privzeto): rokovanje WebSocket, nato vsak okvir vrne; "molk": prebere zahtevo in zapre brez
    odgovora; "403": zahtevo zavrne; "zapri": takoj po TLS zapre (rele zapre neuporabljeno povezavo).
    """

    def __init__(self, mapa: str, nacini=None) -> None:
        kljuc, potrdilo, _ = link_datoteke.zagotovi_potrdilo(mapa)
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(potrdilo, kljuc)
        self.posluh = socket.socket()
        self.posluh.bind(("127.0.0.1", 0))
        self.posluh.listen(8)
        self.vrata = self.posluh.getsockname()[1]
        self.nacini = list(nacini or [])
        self.napaka = ""
        self.okvirjev = 0
        self.povezav = 0
        self.zahtev = []        # (zaporedna stevilka povezave, prva vrstica zahteve)
        self.nit = threading.Thread(target=self._sprejemaj, daemon=True)
        self.nit.start()

    def _sprejemaj(self) -> None:
        while True:
            try:
                surov, _ = self.posluh.accept()
            except OSError:
                return
            st = self.povezav
            self.povezav += 1
            nacin = self.nacini[st] if st < len(self.nacini) else "odmev"
            threading.Thread(target=self._teci, args=(surov, st, nacin), daemon=True).start()

    def _teci(self, surov, st: int, nacin: str) -> None:
        s = None
        try:
            s = self.ctx.wrap_socket(surov, server_side=True)
            if nacin == "zapri":
                return
            zahteva = b""
            while b"\r\n\r\n" not in zahteva:
                kos = s.recv(4096)
                if not kos:
                    return
                zahteva += kos
            self.zahtev.append((st, zahteva.split(b"\r\n", 1)[0].decode()))
            if nacin == "molk":
                return
            if nacin == "403":
                s.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
                return
            kljuc = re.search(rb"Sec-WebSocket-Key: (\S+)", zahteva).group(1).decode()
            sprejem = base64.b64encode(hashlib.sha1((kljuc + _GUID).encode()).digest()).decode()
            s.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                       "Sec-WebSocket-Accept: %s\r\n\r\n" % sprejem).encode())
            medpomnilnik = b""

            def beri(n: int) -> bytes:
                nonlocal medpomnilnik
                while len(medpomnilnik) < n:
                    kos = s.recv(65536)
                    if not kos:
                        raise ConnectionError("konec")
                    medpomnilnik += kos
                vzeto, medpomnilnik = medpomnilnik[:n], medpomnilnik[n:]
                return vzeto

            while True:
                b0, b1 = beri(2)
                dolzina = b1 & 0x7F
                if dolzina == 126:
                    dolzina = int.from_bytes(beri(2), "big")
                elif dolzina == 127:
                    dolzina = int.from_bytes(beri(8), "big")
                maska = beri(4)
                telo = link_ws.odmaskiraj(beri(dolzina), maska)
                if b0 & 0x0F == 0x8:
                    return
                self.okvirjev += 1
                s.sendall(link_ws.okvir(b0 & 0x0F, telo))
        except (ConnectionError, ssl.SSLError):
            pass
        except Exception as e:  # noqa: BLE001
            self.napaka = "%s: %s" % (type(e).__name__, e)
        finally:
            for v in (s, surov):
                if v is not None:
                    try:
                        v.close()
                    except OSError:
                        pass

    def zapri(self) -> None:
        try:
            self.posluh.shutdown(socket.SHUT_RDWR)      # zbudi accept() (sam close ga na Linuxu ne)
        except OSError:
            pass
        try:
            self.posluh.close()
        except OSError:
            pass
        self.nit.join(5)


def _kontekst_preizkusa():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class OdjemalecReleja(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-rele-")
        try:
            self.rele = _Rele(self.mapa)
        except Exception as e:  # noqa: BLE001 - brez orodja za potrdilo preizkusa ni mogoce izvesti
            shutil.rmtree(self.mapa, ignore_errors=True)
            self.skipTest("potrdila ni mogoce ustvariti: %s" % e)
        self.ws = None

    def tearDown(self):
        if self.ws is not None:
            self.ws.sprosti()
        self.rele.zapri()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def _povezi(self) -> link_rele.WsOdjemalec:
        """Odjemalec releja, usmerjen na krajevni rele (pravi gre na link.safeer.si:443 s preverjenim potrdilom)."""
        def kontekst():
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx

        prava = socket.create_connection
        with mock.patch.object(link_rele.ssl, "create_default_context", kontekst), \
                mock.patch.object(link_rele.socket, "create_connection",
                                  lambda naslov, timeout=None: prava(("127.0.0.1", self.rele.vrata), timeout=timeout)):
            self.ws = link_rele.WsOdjemalec("/v1/listen", {"X-Preizkus": "1"}, gostitelj="127.0.0.1")
        return self.ws

    def test_obe_smeri_hkrati(self):
        ws = self._povezi()
        okvirjev, velikost = 400, link_rele.KOS
        napake = []
        poslano, prejeto = hashlib.sha256(), hashlib.sha256()
        stanje = {"prejeto": 0}

        def beri() -> None:
            try:
                while stanje["prejeto"] < okvirjev * velikost:
                    op, podatki = ws.prejmi()
                    if op != 0x2:
                        napake.append("nepricakovan okvir %r" % op)
                        return
                    prejeto.update(podatki)
                    stanje["prejeto"] += len(podatki)
            except Exception as e:  # noqa: BLE001
                napake.append("branje %s: %s" % (type(e).__name__, e))

        def pisi() -> None:
            try:
                for i in range(okvirjev):
                    kos = (i.to_bytes(4, "big") * (velikost // 4 + 1))[:velikost]
                    poslano.update(kos)
                    ws.poslji(kos)
            except Exception as e:  # noqa: BLE001
                napake.append("pisanje %s: %s" % (type(e).__name__, e))

        niti = [threading.Thread(target=beri, daemon=True), threading.Thread(target=pisi, daemon=True)]
        for n in niti:
            n.start()
        for n in niti:
            n.join(30)
        self.assertEqual(napake, [])
        self.assertFalse(any(n.is_alive() for n in niti), "prenos se ni koncal (prejeto %d B)" % stanje["prejeto"])
        self.assertEqual(self.rele.napaka, "")
        self.assertEqual(stanje["prejeto"], okvirjev * velikost)
        self.assertEqual(prejeto.hexdigest(), poslano.hexdigest(), "bajti so se skozi rele vrnili spremenjeni")

    def test_zapri_iz_druge_niti_zbudi_branje(self):
        ws = self._povezi()
        izid = {}

        def beri() -> None:
            zacetek = time.monotonic()
            try:
                izid["okvir"] = ws.prejmi()
            except Exception as e:  # noqa: BLE001
                izid["napaka"] = e
            izid["cas"] = time.monotonic() - zacetek

        nit = threading.Thread(target=beri, daemon=True)
        nit.start()
        time.sleep(0.3)
        ws.zapri()
        nit.join(5)
        self.assertFalse(nit.is_alive(), "nit, ki bere iz releja, se po zaprtju ni zbudila")
        self.assertLess(izid["cas"], 3.0)
        self.assertIsInstance(izid.get("napaka"), ConnectionError)

    def test_omejitev_med_cakanjem_na_hub(self):
        """LokalniRele pred prvim sporocilom nastavi omejitev (hub mora kanal sprejeti v 20 s) in jo nato umakne."""
        ws = self._povezi()
        ws.s.settimeout(0.3)
        zacetek = time.monotonic()
        with self.assertRaises(socket.timeout):
            ws.prejmi()
        self.assertLess(time.monotonic() - zacetek, 3.0)
        ws.s.settimeout(None)
        ws.poslji(b"potem tece naprej")
        self.assertEqual(ws.prejmi(), (0x2, b"potem tece naprej"))


if __name__ == "__main__":
    unittest.main()


class ToplaPovezava(unittest.TestCase):
    """Nov kanal gre po vnaprej odprti povezavi TLS (brez TCP in TLS rokovanja); mrtva se zamenja z novo."""

    def _rele(self, nacini=None) -> _Rele:
        self.mapa = tempfile.mkdtemp(prefix="safeer-rele-")
        self.addCleanup(shutil.rmtree, self.mapa, True)
        try:
            rele = _Rele(self.mapa, nacini)
        except Exception as e:  # noqa: BLE001
            self.skipTest("potrdila ni mogoce ustvariti: %s" % e)
        self.addCleanup(rele.zapri)
        prava = socket.create_connection
        for zamenjava in (mock.patch.object(link_rele.ssl, "create_default_context", _kontekst_preizkusa),
                          mock.patch.object(link_rele.socket, "create_connection",
                                            lambda naslov, timeout=None: prava(("127.0.0.1", rele.vrata), timeout=timeout))):
            zamenjava.start()
            self.addCleanup(zamenjava.stop)
        return rele

    def _topla(self) -> link_rele.TopleTls:
        topla = link_rele.TopleTls(gostitelj="127.0.0.1", rok_s=5.0)
        self.addCleanup(topla.ustavi)
        return topla

    @staticmethod
    def _pocakaj(pogoj, rok: float = 5.0) -> bool:
        konec = time.monotonic() + rok
        while time.monotonic() < konec:
            if pogoj():
                return True
            time.sleep(0.02)
        return pogoj()

    def test_kanal_po_topli_povezavi(self):
        rele = self._rele()
        topla = self._topla()
        topla.zelim()
        self.assertTrue(self._pocakaj(lambda: topla._s is not None), "topla povezava ni nastala")
        self.assertEqual(rele.povezav, 1)
        self.assertEqual(rele.zahtev, [], "topla povezava ne sme poslati zahteve, dokler je ne uporabimo")
        ws = link_rele.odpri_kanal("/v1/listen", lambda: {"X-Preizkus": "1"}, topla)
        self.addCleanup(ws.sprosti)
        self.assertEqual(rele.zahtev[0][0], 0, "kanal ni sel po topli povezavi")
        ws.poslji(b"zivjo")
        self.assertEqual(ws.prejmi(), (0x2, b"zivjo"))
        # Naslednja topla se pripravi takoj (za naslednji kanal).
        self.assertTrue(self._pocakaj(lambda: topla._s is not None and rele.povezav == 2))

    def test_mrtva_topla_se_zamenja_z_novo(self):
        rele = self._rele(["molk"])
        topla = self._topla()
        topla.zelim()
        self.assertTrue(self._pocakaj(lambda: topla._s is not None))
        ws = link_rele.odpri_kanal("/v1/listen", lambda: {"X-Preizkus": "1"}, topla)
        self.addCleanup(ws.sprosti)
        self.assertEqual([st for st, _ in rele.zahtev][:1], [0])
        self.assertNotEqual(rele.zahtev[-1][0], 0, "po mrtvi topli ni bilo nove povezave")
        ws.poslji(b"naprej")
        self.assertEqual(ws.prejmi(), (0x2, b"naprej"))

    def test_zavrnitve_ne_ponovi(self):
        rele = self._rele(["403", "403", "403"])
        topla = self._topla()
        topla.zelim()
        self.assertTrue(self._pocakaj(lambda: topla._s is not None))
        with self.assertRaises(ConnectionError) as napaka:
            link_rele.odpri_kanal("/v1/connect?to=x&kanal=y", lambda: {"X-Preizkus": "1"}, topla)
        self.assertNotIsInstance(napaka.exception, link_rele.BrezOdgovora)
        self.assertIn("403", str(napaka.exception))
        self.assertEqual(len(rele.zahtev), 1, "zavrnjeno zahtevo je poslal dvakrat")

    def test_povezave_ki_jo_rele_zapre_ne_ponudi(self):
        rele = self._rele(["zapri", "zapri"])
        topla = self._topla()
        odprte = []
        nova = topla._nova
        topla._nova = lambda: odprte.append(nova()) or odprte[-1]
        topla.zelim()
        # Nit zazna zaprtje in nastavi premor pred naslednjo povezavo.
        self.assertTrue(self._pocakaj(lambda: topla._ne_pred > 0), "zaprtja ni zaznal")
        self.assertIsNone(topla._s)
        self.assertFalse(link_rele._mirna(odprte[0]))
        # Rele je zaprl takoj: nove ne odpre prej kot po premoru (tudi ce ga kdo zbudi).
        topla.zelim()
        time.sleep(0.3)
        self.assertEqual(rele.povezav, 1)
        self.assertIsNone(topla.vzemi())

    def test_brez_zelje_se_ne_obnavlja(self):
        rele = self._rele()
        topla = self._topla()
        with mock.patch.object(link_rele, "TOPLA_ZELJA_S", 0.2):
            topla.zelim()
            self.assertTrue(self._pocakaj(lambda: topla._s is not None))
            topla._zbudi()
            self.assertTrue(self._pocakaj(lambda: topla._nit is None, 3.0), "nit se po poteku zelje ni ustavila")
        self.assertIsNone(topla._s)
        self.assertEqual(rele.povezav, 1)

    def test_redna_zamenjava_brez_premora_in_z_obnovo_seje(self):
        """Cloudflare zapre povezavo brez zahteve po 10-15 s: bazen jo zamenja prej, brez premora, z obnovo seje TLS."""
        self._rele()
        topla = self._topla()
        odprte = []
        nova = topla._nova
        topla._nova = lambda: odprte.append(nova()) or odprte[-1]
        with mock.patch.object(link_rele, "TOPLA_STAROST_S", 0.3):
            topla.zelim()
            # Brez premora (ta bi bil vsaj 5 s) v ~2 s nastane vec zaporednih povezav.
            self.assertTrue(self._pocakaj(lambda: len(odprte) >= 4, 4.0),
                            "redna zamenjava je cakala kot po zgodnjem zaprtju (%d povezav)" % len(odprte))
            self.assertEqual(topla._ne_pred, 0.0)
            # Prva je polno rokovanje, naslednje obnovijo sejo prejsnje (vstopnico TLS 1.3 prebere _mirna).
            self.assertFalse(odprte[0].session_reused)
            self.assertTrue(any(s.session_reused for s in odprte[1:]), "nobena zamenjava ni obnovila seje TLS")
            ws = link_rele.odpri_kanal("/v1/listen", lambda: {"X-Preizkus": "1"}, topla)
        self.addCleanup(ws.sprosti)
        ws.poslji(b"po zamenjavi")
        self.assertEqual(ws.prejmi(), (0x2, b"po zamenjavi"))
