"""Zvok racunalnika na napravi v Safeer Linku (core/link_zvok.py): seja, pozdrav, okvirji in pospravljanje.

Zvocni streznik in ffmpeg sta zamenjana: izhod ne nastane zares, zajem je kratek program, ki izpise
znane bajte. TLS, zeton in okvirji pa so pravi - tako kot jih bere televizor.
"""
import json
import os
import socket
import ssl
import sys
import tempfile
import unittest
from unittest import mock

from core import link_zvok


class ZvokNaNapravo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.z = link_zvok.ZvokNaNapravo(tls_mapa=self.tmp.name, ffmpeg=sys.executable)
        self.pripravljeno, self.obnovljeno, self.spremembe = [], [], []
        mock.patch.object(self.z, "_pripravi_izhod", lambda ime: self.pripravljeno.append(ime)).start()
        mock.patch.object(self.z, "_obnovi_izhod", lambda: self.obnovljeno.append(True)).start()
        mock.patch.object(link_zvok.shutil, "which", lambda x: "/usr/bin/" + x).start()
        mock.patch.object(link_zvok, "privzeti_izhod", lambda: "bluez_output.jbl").start()
        mock.patch.object(link_zvok, "ukaz_zajema", lambda vir, ff: [
            sys.executable, "-c", "import sys; sys.stdout.buffer.write(bytes(range(256)) * 15); sys.stdout.flush()"]).start()
        self.addCleanup(mock.patch.stopall)
        self.z.ob_spremembi = lambda opis: self.spremembe.append(opis["stanje"])

    def _povezi(self, parametri, zeton=None):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        s = ctx.wrap_socket(socket.create_connection(("127.0.0.1", parametri["port"]), timeout=10))
        s.sendall(("SAFEER-ZVOK %s\n" % (zeton or parametri["token"])).encode())
        return s

    @staticmethod
    def _beri(s, n):
        b = b""
        while len(b) < n:
            d = s.recv(n - len(b))
            if not d:
                break
            b += d
        return b

    def test_seja_poslje_zvok_in_pospravi(self):
        p = self.z.zacni("tv-1", "Philips TV")
        self.assertEqual(self.pripravljeno, ["Philips TV"])
        self.assertEqual((p["audio"]["hz"], p["audio"]["channels"], p["audio"]["format"]), (48000, 2, "s16le"))
        self.assertTrue(p["fp"] and p["token"] and p["port"])
        self.assertEqual(self.z.opis(), {"naprava": "tv-1", "ime": "Philips TV", "stanje": "caka"})
        s = self._povezi(p)
        vrstica = b""
        while not vrstica.endswith(b"\n"):
            vrstica += s.recv(1)
        glava = json.loads(vrstica)
        self.assertEqual(glava["zvok"], {"hz": 48000, "kanali": 2, "oblika": "s16le"})
        prejeto = b""
        while len(prejeto) < 256 * 15:
            g = self._beri(s, 5)
            if len(g) < 5:
                break
            self.assertEqual(g[0], link_zvok.OKVIR_ZVOK)
            prejeto += self._beri(s, int.from_bytes(g[1:5], "big"))
        self.assertEqual(prejeto, bytes(range(256)) * 15)
        # Zajem se je koncal: seja se konca sama, zvok gre nazaj na racunalnik.
        s.settimeout(5)
        self.assertEqual(self._beri(s, 1), b"")
        s.close()
        for _ in range(50):
            if self.obnovljeno:
                break
            import time
            time.sleep(0.05)
        self.assertTrue(self.obnovljeno)
        self.assertEqual(self.z.opis()["naprava"], "")
        self.assertIn("tece", self.spremembe)

    def test_napacen_zeton_ne_dobi_nicesar(self):
        p = self.z.zacni("tv-1", "TV")
        s = self._povezi(p, zeton="ponarejen")
        self.assertEqual(self._beri(s, 1), b"")
        s.close()
        # Tujec seje ne podre: prava naprava se se vedno lahko poveze.
        self.assertEqual(self.z.opis()["naprava"], "tv-1")
        s = self._povezi(p)
        self.assertTrue(self._beri(s, 1))
        s.close()
        # Kratek zajem se lahko konca sam, preden sejo ustavimo - izid je v obeh primerih enak.
        self.z.ustavi()
        self.assertFalse(self.z.ustavi())
        self.assertEqual(self.z.opis()["naprava"], "")
        self.assertTrue(self.obnovljeno)


class Pomozno(unittest.TestCase):
    def test_naslovi_in_ukaz(self):
        u = link_zvok.ukaz_zajema("safeer_link_zvok.monitor", "ffmpeg")
        self.assertEqual(u[u.index("-i") + 1], "safeer_link_zvok.monitor")
        self.assertEqual(u[-3:], ["-f", "s16le", "-"])
        naslovi = link_zvok.lastni_naslovi("wss://127.0.0.1:8990/cast/ws")
        for n in naslovi:
            socket.inet_aton(n)
            self.assertFalse(n.startswith("127."))


class Povezava(unittest.TestCase):
    def test_control_in_link(self):
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "safeer_control.py"), encoding="utf-8") as f:
            control = f.read()
        with open(os.path.join(koren, "core", "safeer_link.py"), encoding="utf-8") as f:
            link = f.read()
        for d in ('"zvok-na-napravo"', '"zvok-ustavi"'):
            self.assertIn(d, control)
        self.assertIn('"action": "audio.play"', link)
        self.assertIn('"action": "audio.stop"', link)
        self.assertIn("zapisi_stanje_za_os", link)


if __name__ == "__main__":
    unittest.main()
