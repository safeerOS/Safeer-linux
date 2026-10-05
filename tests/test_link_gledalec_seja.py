"""Seja oddaljenega zaslona s pravo povezavo TLS: okvirji prihajajo, vnos gre nazaj - iz dveh niti hkrati.

Gledalec bere okvirje v eni niti in posilja vnos (miska, tipke) iz druge. Vticnica ima casovno omejitev (iz
create_connection), zato je pod OpenSSL neblokirajoca; navaden ssl.SSLSocket takrat bralni niti lazno javi konec
povezave (core/link_vticnik.py, krog 102). Za uporabnika: oddaljeni zaslon se prekine, medtem ko premika misko.

Naprava v preizkusu je namenoma ena sama nit z neblokirajoco vticnico (select): tako sama nima te napake in
preizkus meri samo gledalca.
"""
import json
import select
import shutil
import socket
import ssl
import struct
import tempfile
import threading
import time
import unittest

from core import link_datoteke, link_gledalec

#: Okvir slike v preizkusu (vrsta 1) in razmik med okvirji. Majhni in pogosti okvirji pomenijo, da bralna nit
#: velikokrat izprazni vticnico - prav takrat se pokaze tekma s pisalno nitjo.
TELO = b"x" * 1500
RAZMIK_S = 0.0005


class _Naprava:
    """Naprava, ki deli zaslon: po pozdravu poslje glavo, nato okvirje v enakomernem ritmu in bere vnos."""

    def __init__(self, mapa: str) -> None:
        kljuc, potrdilo, self.odtis = link_datoteke.zagotovi_potrdilo(mapa)
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(potrdilo, kljuc)
        self.posluh = socket.socket()
        self.posluh.bind(("127.0.0.1", 0))
        self.posluh.listen(1)
        self.vrata = self.posluh.getsockname()[1]
        self.vnosov = 0
        self.okvirjev = 0
        self.konec = threading.Event()
        self.napaka = ""
        self.nit = threading.Thread(target=self._teci, daemon=True)
        self.nit.start()

    def _teci(self) -> None:
        s = None
        try:
            surov, _ = self.posluh.accept()
            surov.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s = self.ctx.wrap_socket(surov, server_side=True)
            vrstica = b""
            while not vrstica.endswith(b"\n"):
                znak = s.recv(1)
                if not znak:
                    raise ConnectionError("gledalec je odsel pred pozdravom")
                vrstica += znak
            if not vrstica.startswith(b"SAFEER-ZASLON zeton"):
                raise ValueError("napacen pozdrav")
            s.sendall((json.dumps({"v": 2, "w": 1280, "h": 720, "fps": 30}) + "\n").encode())
            s.setblocking(False)
            okvir = bytes([1]) + struct.pack(">I", len(TELO)) + TELO
            caka = b""
            ostanek = b""
            naslednji = time.monotonic()
            while not self.konec.is_set():
                zdaj = time.monotonic()
                if not caka and zdaj >= naslednji:
                    caka, naslednji = okvir, max(naslednji + RAZMIK_S, zdaj - 0.01)
                if caka:
                    try:
                        poslano = s.send(caka)
                        caka = caka[poslano:]
                        if not caka:
                            self.okvirjev += 1
                    except (ssl.SSLWantWriteError, ssl.SSLWantReadError):
                        pass
                try:
                    kos = s.recv(65536)
                    if not kos:
                        break
                    ostanek += kos
                    *vrstice, ostanek = ostanek.split(b"\n")
                    self.vnosov += len(vrstice)
                    continue
                except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                    pass
                select.select([s], [s] if caka else [], [], max(0.0, min(naslednji - time.monotonic(), 0.05)))
        except Exception as e:  # noqa: BLE001
            if not self.konec.is_set():
                self.napaka = "%s: %s" % (type(e).__name__, e)
        finally:
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass

    def zapri(self) -> None:
        self.konec.set()
        try:
            self.posluh.close()
        except OSError:
            pass
        self.nit.join(5)


class SejaGledalca(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-gledalec-")
        try:
            self.naprava = _Naprava(self.mapa)
        except Exception as e:  # noqa: BLE001 - brez orodja za potrdilo preizkusa ni mogoce izvesti
            shutil.rmtree(self.mapa, ignore_errors=True)
            self.skipTest("potrdila ni mogoce ustvariti: %s" % e)

    def tearDown(self):
        self.naprava.zapri()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_okvirji_in_vnos_hkrati(self):
        g = link_gledalec.Gledalec("127.0.0.1", {"ok": True, "port": self.naprava.vrata, "token": "zeton",
                                                 "fp": self.naprava.odtis})
        glava = g.povezi()
        self.assertEqual((glava.sirina, glava.visina), (1280, 720))
        stanje = {"okvirjev": 0, "napaka": "", "poslanih": 0}
        konec = time.monotonic() + 3.0

        def beri() -> None:
            try:
                for vrsta, telo in g.okvirji():
                    if vrsta != 1 or telo != TELO:
                        stanje["napaka"] = "pokvarjen okvir (vrsta %d, %d B)" % (vrsta, len(telo))
                        return
                    stanje["okvirjev"] += 1
                    if time.monotonic() >= konec:
                        return
            except Exception as e:  # noqa: BLE001
                if time.monotonic() < konec:
                    stanje["napaka"] = "branje %s: %s" % (type(e).__name__, e)

        def pisi() -> None:
            try:
                while time.monotonic() < konec and not stanje["napaka"]:
                    g.poslji({"vrsta": "tocka", "x": 640, "y": 360})
                    stanje["poslanih"] += 1
                    time.sleep(0.0002)
            except Exception as e:  # noqa: BLE001
                if time.monotonic() < konec:
                    stanje["napaka"] = "pisanje %s: %s" % (type(e).__name__, e)

        niti = [threading.Thread(target=beri, daemon=True), threading.Thread(target=pisi, daemon=True)]
        for n in niti:
            n.start()
        for n in niti:
            n.join(15)
        g.zapri()
        self.assertEqual(stanje["napaka"], "", "seja se je prekinila po %d okvirjih in %d dogodkih vnosa"
                         % (stanje["okvirjev"], stanje["poslanih"]))
        self.assertEqual(self.naprava.napaka, "")
        self.assertFalse(any(n.is_alive() for n in niti), "seja se ni koncala")
        self.assertGreater(stanje["okvirjev"], 500)
        self.assertGreater(stanje["poslanih"], 500)
        # Naprava je morala vnos tudi dobiti (vrstice JSON), ne le gledalec poslati.
        self.assertGreater(self.naprava.vnosov, 500)


if __name__ == "__main__":
    unittest.main()
