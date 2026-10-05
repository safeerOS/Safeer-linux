"""Seja deljenja zaslona s pravo povezavo TLS (core/link_zaslon.py): slika in zvok tja, vnos nazaj.

Namesto ffmpeg tece majhna skripta, ki brez prestanka pise bajte; televizor je odjemalec v eni niti
(neblokirajoca vticnica + select), da sam nima tekme med branjem in pisanjem. Vnos se ne izvede: seja dobi
lazni `Vnos`, ki dogodke samo steje - preizkus se uporabnikove miske in tipkovnice ne dotakne.

Kaj mora veljati (krog 106):
- slika, zvok in vnos tecejo hkrati, okvirji pridejo celi;
- televizor, ki ne bere vec, seje ne drzi v nedogled (omejitev pisanja), in zataknjena stara seja ne ustavi nove;
- konec stare seje ne podre nove;
- kdor pride z napacnim zetonom ali brez TLS, seje ne podre.
"""
import json
import os
import select
import shutil
import socket
import ssl
import stat
import tempfile
import threading
import time
import unittest

from core import link_datoteke, link_zaslon

LAZNI_FFMPEG = '''#!/usr/bin/env python3
import os, sys, time
razmik = float(os.environ.get("SAFEER_LAZNI_FFMPEG_RAZMIK_S", "0.0005"))
kos = bytes(int(os.environ.get("SAFEER_LAZNI_FFMPEG_KOS", "1500")))
izhod = sys.stdout.buffer
try:
    while True:
        izhod.write(kos)
        izhod.flush()
        if razmik:
            time.sleep(razmik)
except (BrokenPipeError, KeyboardInterrupt):
    pass
'''


class _LazniVnos:
    """Namesto core.link_vnos.Vnos: dogodke steje, na racunalniku ne naredi nicesar."""

    mozno = True

    def __init__(self) -> None:
        self.stevilo = 0

    def izvedi(self, dogodek) -> bool:
        self.stevilo += 1
        return True

    def sprosti_vse(self) -> None:
        pass


class _Televizor:
    """Odjemalec seje. `beri = False` pomeni televizor, ki je obstal: povezava ostane, bere pa ne vec."""

    def __init__(self, seja: dict, vnos_na_s: float = 0.0, zeton=None) -> None:
        self.vrata = seja["port"]
        self.zeton = seja["token"] if zeton is None else zeton
        self.vnos_na_s = vnos_na_s
        self.glava = None
        self.okvirjev = {1: 0, 2: 0, 3: 0}
        self.poslanih = 0
        self.napaka = ""
        self.konec_toka = False
        self.beri = True
        self.ustavi = threading.Event()
        self.povezan = threading.Event()
        self.koncan = threading.Event()
        self.nit = threading.Thread(target=self._teci, daemon=True)
        self.nit.start()

    def _razcleni(self, zbrano: bytearray) -> None:
        while len(zbrano) >= 5:
            vrsta, dolzina = zbrano[0], int.from_bytes(zbrano[1:5], "big")
            if vrsta not in (1, 2, 3) or not 0 < dolzina <= 8 * 1024 * 1024:
                self.napaka = "pokvarjen okvir: vrsta %d, dolzina %d" % (vrsta, dolzina)
                return
            if len(zbrano) < 5 + dolzina:
                return
            telo = bytes(zbrano[5:5 + dolzina])
            del zbrano[:5 + dolzina]
            if vrsta in (1, 2) and telo.count(0) != len(telo):
                self.napaka = "pokvarjeno telo okvirja vrste %d" % vrsta
                return
            self.okvirjev[vrsta] += 1

    def _teci(self) -> None:
        s = None
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            s = ctx.wrap_socket(socket.create_connection(("127.0.0.1", self.vrata), timeout=8))
            s.sendall(("SAFEER-ZASLON %s\n" % self.zeton).encode())
            vrstica = b""
            while not vrstica.endswith(b"\n"):
                znak = s.recv(1)
                if not znak:
                    self.konec_toka = True
                    return
                vrstica += znak
            self.glava = json.loads(vrstica)
            self.povezan.set()
            s.setblocking(False)
            zbrano = bytearray()
            caka = b""
            naslednji = time.monotonic()
            while not self.ustavi.is_set() and not self.napaka:
                zdaj = time.monotonic()
                if self.vnos_na_s and not caka and zdaj >= naslednji:
                    caka = b'{"vrsta":"premik","dx":1,"dy":0}\n'
                    naslednji = max(naslednji + 1.0 / self.vnos_na_s, zdaj - 0.01)
                if caka:
                    try:
                        poslano = s.send(caka)
                        caka = caka[poslano:]
                        if not caka:
                            self.poslanih += 1
                    except (ssl.SSLWantWriteError, ssl.SSLWantReadError):
                        pass
                if self.beri:
                    try:
                        kos = s.recv(262144)
                        if not kos:
                            self.konec_toka = True
                            return
                        zbrano += kos
                        self._razcleni(zbrano)
                        continue
                    except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                        pass
                cakaj = 0.05
                if self.vnos_na_s:
                    cakaj = max(0.0, min(cakaj, naslednji - time.monotonic()))
                select.select([s] if self.beri else [], [s] if caka else [], [], cakaj)
        except (OSError, ssl.SSLError, ValueError):
            if not self.ustavi.is_set():
                self.konec_toka = True
        finally:
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass
            self.koncan.set()

    def zapri(self) -> None:
        self.ustavi.set()
        self.nit.join(5)


def _pocakaj(pogoj, najdlje: float = 5.0, korak: float = 0.02) -> bool:
    konec = time.monotonic() + najdlje
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(korak)
    return bool(pogoj())


class _Osnova(unittest.TestCase):
    #: Hitrost laznega zajema: privzeto majhni kosi z razmikom (kot slika v zivo); "hitro" napolni vticnico takoj.
    HITRO = False

    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-zaslon-seja-")
        try:
            link_datoteke.zagotovi_potrdilo(os.path.join(self.mapa, "tls"))
        except Exception as e:  # noqa: BLE001 - brez orodja za potrdilo preizkusa ni mogoce izvesti
            shutil.rmtree(self.mapa, ignore_errors=True)
            self.skipTest("potrdila ni mogoce ustvariti: %s" % e)
        self.ffmpeg = os.path.join(self.mapa, "lazni-ffmpeg")
        with open(self.ffmpeg, "w", encoding="utf-8") as d:
            d.write(LAZNI_FFMPEG)
        os.chmod(self.ffmpeg, os.stat(self.ffmpeg).st_mode | stat.S_IXUSR)
        self._okolje = {k: os.environ.get(k) for k in ("DISPLAY", "SAFEER_LAZNI_FFMPEG_RAZMIK_S", "SAFEER_LAZNI_FFMPEG_KOS")}
        os.environ.setdefault("DISPLAY", ":0")
        if self.HITRO:
            os.environ["SAFEER_LAZNI_FFMPEG_RAZMIK_S"] = "0"
            os.environ["SAFEER_LAZNI_FFMPEG_KOS"] = "32768"
        self.z = link_zaslon.Zaslon(tls_mapa=os.path.join(self.mapa, "tls"), vklopljeno=True, ffmpeg=self.ffmpeg)
        self.televizorji = []

    def tearDown(self):
        for t in self.televizorji:
            t.zapri()
        self.z.ustavi()
        for k, v in self._okolje.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.mapa, ignore_errors=True)

    def zacni(self) -> dict:
        seja = self.z.zacni("tv-test")
        self.vnos = _LazniVnos()
        self.z._vnos = self.vnos            # pred povezavo televizorja: noben dogodek ne pride do pravega vnosa
        return seja

    def televizor(self, seja: dict, **kw) -> _Televizor:
        t = _Televizor(seja, **kw)
        self.televizorji.append(t)
        return t


class SlikaZvokInVnos(_Osnova):
    def test_slika_in_vnos_hkrati(self):
        tv = self.televizor(self.zacni(), vnos_na_s=2000)
        self.assertTrue(tv.povezan.wait(8), "televizor se ni povezal")
        self.assertEqual(tv.glava["v"], 2)
        time.sleep(3.0)
        self.assertEqual(tv.napaka, "")
        self.assertFalse(tv.konec_toka, "seja se je koncala po %d okvirjih slike in %d dogodkih vnosa"
                         % (tv.okvirjev[1], tv.poslanih))
        self.assertGreater(tv.okvirjev[1], 300)
        self.assertGreater(tv.poslanih, 1000)
        self.assertTrue(_pocakaj(lambda: self.vnos.stevilo > 1000), "racunalnik je dobil le %d dogodkov" % self.vnos.stevilo)
        self.assertTrue(self.z.stanje()["povezan"])


class StaraInNovaSeja(_Osnova):
    HITRO = True

    def _zataknjena(self):
        """Seja, v kateri televizor ne bere vec: racunalnikovo pisanje obstane, ko se vticnica napolni."""
        tv = self.televizor(self.zacni())
        self.assertTrue(tv.povezan.wait(8))
        self.assertTrue(_pocakaj(lambda: tv.okvirjev[1] > 20), "slika ni stekla")
        tv.beri = False
        time.sleep(0.6)
        return tv

    def test_zataknjena_stara_seja_ne_ustavi_nove(self):
        self._zataknjena()
        tv2 = self.televizor(self.zacni())
        self.assertTrue(tv2.povezan.wait(8), "nova seja se ni povezala")
        self.assertTrue(_pocakaj(lambda: tv2.okvirjev[1] > 50, 4.0),
                        "nova seja je povezana, slike pa ne dobi (%d okvirjev): stara seja jo drzi" % tv2.okvirjev[1])
        self.assertEqual(tv2.napaka, "")

    def test_konec_stare_seje_ne_podre_nove(self):
        tv1 = self._zataknjena()
        tv2 = self.televizor(self.zacni())
        self.assertTrue(tv2.povezan.wait(8), "nova seja se ni povezala")
        tv1.zapri()                         # stari televizor dokoncno odide: stara seja se sele zdaj konca
        time.sleep(1.5)
        pred = tv2.okvirjev[1]
        self.assertFalse(tv2.konec_toka, "konec stare seje je zaprl novo")
        self.assertTrue(_pocakaj(lambda: tv2.okvirjev[1] > pred + 50, 4.0), "nova seja po koncu stare ne dobi vec slike")
        self.assertTrue(self.z.stanje()["tece"])
        self.assertTrue(self.z.stanje()["povezan"])


class TelevizorKiNeBere(_Osnova):
    HITRO = True

    def test_seja_se_konca_po_omejitvi_pisanja(self):
        staro = getattr(link_zaslon, "ROK_PISANJA_S", None)
        link_zaslon.ROK_PISANJA_S = 0.5
        try:
            tv = self.televizor(self.zacni())
            self.assertTrue(tv.povezan.wait(8))
            self.assertTrue(_pocakaj(lambda: tv.okvirjev[1] > 20), "slika ni stekla")
            zajem = self.z._proces
            self.assertIsNotNone(zajem)
            tv.beri = False
            self.assertTrue(_pocakaj(lambda: not self.z.stanje()["tece"], 6.0),
                            "televizor ne bere, seja pa po omejitvi pisanja se vedno tece")
            self.assertTrue(_pocakaj(lambda: zajem.poll() is not None, 4.0), "zajem slike po koncu seje se tece")
        finally:
            if staro is None:
                del link_zaslon.ROK_PISANJA_S
            else:
                link_zaslon.ROK_PISANJA_S = staro


class TujaPovezava(_Osnova):
    def test_napacen_zeton_ne_podre_seje(self):
        seja = self.zacni()
        tuj = self.televizor(seja, zeton="napacen-zeton")
        self.assertTrue(tuj.koncan.wait(8))
        self.assertIsNone(tuj.glava)                 # brez pravega zetona ne dobi niti glave
        tv = self.televizor(seja)
        self.assertTrue(tv.povezan.wait(8), "po tuji povezavi pravi televizor ne pride vec do seje")
        self.assertTrue(_pocakaj(lambda: tv.okvirjev[1] > 20), "slika ni stekla")

    def test_pozdrav_z_ne_ascii_znaki_ne_podre_seje(self):
        seja = self.zacni()
        tuj = self.televizor(seja, zeton="napa\u010den-\u017eeton")
        self.assertTrue(tuj.koncan.wait(8))
        self.assertIsNone(tuj.glava)
        tv = self.televizor(seja)
        self.assertTrue(tv.povezan.wait(8), "po tujem pozdravu pravi televizor ne pride vec do seje")

    def test_povezava_brez_tls_ne_podre_seje(self):
        seja = self.zacni()
        s = socket.create_connection(("127.0.0.1", seja["port"]), timeout=5)
        s.sendall(b"GET / HTTP/1.0\r\n\r\n")
        s.settimeout(5)
        try:
            self.assertEqual(s.recv(64), b"")        # nicesar ne dobi
        except OSError:
            pass                                     # ali pa je povezava prekinjena: prav tako v redu
        s.close()
        tv = self.televizor(seja)
        self.assertTrue(tv.povezan.wait(8), "po povezavi brez TLS pravi televizor ne pride vec do seje")
        self.assertTrue(_pocakaj(lambda: tv.okvirjev[1] > 20), "slika ni stekla")


if __name__ == "__main__":
    unittest.main()
