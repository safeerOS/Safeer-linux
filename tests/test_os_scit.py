"""Scit za Safeer OS na Linuxu: razresevalnik DNS, nabor domen, seznami (brez omrezja in brez resolvectl)."""
import os
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_scit  # noqa: E402


def vprasanje(ime: str, id_: int = 0x1234, vrsta: int = 1) -> bytes:
    telo = b"".join(struct.pack("B", len(d)) + d.encode() for d in ime.split(".")) + b"\x00"
    return struct.pack("!HHHHHH", id_, 0x0100, 1, 0, 0, 0) + telo + struct.pack("!HH", vrsta, 1)


class Paketi(unittest.TestCase):
    def test_ime_poizvedbe(self):
        self.assertEqual(os_scit.ime_poizvedbe(vprasanje("Ads.Example.COM")), "ads.example.com")
        self.assertEqual(os_scit.ime_poizvedbe(b"\x00" * 10), "")
        odgovor = bytearray(vprasanje("a.si"))
        odgovor[2] |= 0x80
        self.assertEqual(os_scit.ime_poizvedbe(bytes(odgovor)), "")

    def test_odgovor_zavrnjeno(self):
        p = vprasanje("bad.example", id_=0xBEEF)
        o = os_scit.odgovor_zavrnjeno(p)
        self.assertEqual(o[:2], b"\xbe\xef")
        zastavice, vprasanj, odgovorov = struct.unpack("!HHH", o[2:8])
        self.assertEqual(zastavice & 0x8000, 0x8000)   # odgovor
        self.assertEqual(zastavice & 0x000F, 3)        # NXDOMAIN
        self.assertEqual((vprasanj, odgovorov), (1, 0))
        self.assertEqual(o[12:], p[12:])               # vprasanje ponovljeno v celoti
        self.assertEqual(os_scit.ime_poizvedbe(bytes([o[0], o[1], 0x01]) + o[3:]), "bad.example")


class NaborDomen(unittest.TestCase):
    def test_razcleni_seznam(self):
        besedilo = "# komentar\n0.0.0.0 ads.example.com\n127.0.0.1 localhost\nplain.example\n" \
                   "phish.example.si CNAME .\n*.wild.example\n! easylist\n||ne.sme.com^\nlocalhost\n"
        self.assertEqual(list(os_scit.razcleni_seznam(besedilo)),
                         ["ads.example.com", "plain.example", "phish.example.si", "wild.example"])

    def test_nabor_poddomene_in_kategorija(self):
        n = os_scit.Nabor.iz_domen([("ads.example.com", "oglasi"), ("bad.example", "malware"),
                                    ("bad.example", "oglasi")])
        self.assertEqual(n.kategorija("ads.example.com"), "oglasi")
        self.assertEqual(n.kategorija("cdn.ads.example.com"), "oglasi")
        self.assertIsNone(n.kategorija("example.com"))
        self.assertEqual(n.kategorija("x.bad.example"), "malware")   # nevarnejsa kategorija prevlada
        self.assertIsNone(n.kategorija("safe.example"))

    def test_nabor_shrani_nalozi(self):
        n = os_scit.Nabor.iz_domen([("a.example", "phishing"), ("b.example", "groznje")])
        with tempfile.TemporaryDirectory() as m:
            pot = os.path.join(m, "domene.bin")
            n.shrani(pot)
            n2 = os_scit.Nabor.nalozi(pot)
            self.assertEqual(len(n2), 2)
            self.assertEqual(n2.kategorija("www.a.example"), "phishing")
            self.assertEqual(n2.kategorija("b.example"), "groznje")
            with open(pot, "wb") as f:
                f.write(b"smeti")
            self.assertIsNone(os_scit.Nabor.nalozi(pot))


class SeznamiTest(unittest.TestCase):
    def test_osvezi_iz_lokalnih_prenosov(self):
        vsebine = {
            "hagezi-pro": "\n".join("ad%d.example" % i for i in range(1200)),
            "hagezi-tif": "\n".join("t%d.example" % i for i in range(1100)),
            "hagezi-fake": "\n".join("f%d.example" % i for i in range(1050)),
            "urlhaus": "# urlhaus\n127.0.0.1 mal.example\n",
            "phishing-army": "phish.example\n",
            "si-cert": "cert.example CNAME .\n",
        }
        klici = []

        def prenesi(url, etag, cas=60.0):
            oznaka = [o for o, u, _k in os_scit.VIRI if u == url][0]
            klici.append((oznaka, etag))
            if etag == "e-" + oznaka:
                return 304, b"", etag
            return 200, vsebine[oznaka].encode(), "e-" + oznaka

        with tempfile.TemporaryDirectory() as m:
            s = os_scit.Seznami(m, prenesi_fn=prenesi)
            self.assertTrue(s.osvezi())
            self.assertEqual(len(s.nabor), 1200 + 1100 + 1050 + 3)
            self.assertEqual(s.kategorija("ad7.example"), "oglasi")
            self.assertEqual(s.kategorija("x.mal.example"), "malware")
            self.assertEqual(s.kategorija("cert.example"), "phishing")
            self.assertIsNone(s.kategorija("printer.local"))
            self.assertIsNone(s.kategorija("safeer.si"))
            self.assertIsNone(s.kategorija("ad7.example.safeer.si"))
            # Drugi zagon iz iste mape: nabor je na disku, brez prenosa; osvezitev vrne 304 in nic ne prezida.
            s2 = os_scit.Seznami(m, prenesi_fn=prenesi)
            self.assertEqual(len(s2.nabor), len(s.nabor))
            self.assertTrue(s2.osvezi())
            self.assertEqual(klici[-1][1], "e-si-cert")
            self.assertEqual(s2.stanje()["seznami"]["urlhaus"], 1)

    def test_napaka_prenosa_ohrani_nabor(self):
        def prenesi(url, etag, cas=60.0):
            raise OSError("ni omrezja")
        with tempfile.TemporaryDirectory() as m:
            s = os_scit.Seznami(m, prenesi_fn=prenesi)
            self.assertFalse(s.osvezi())
            self.assertIn("hagezi-pro: OSError", s.napaka)
            self.assertEqual(len(s.nabor), 0)


class LazniUpstream:
    """Streznik DNS na 127.0.0.1, ki na vsako vprasanje vrne odgovor z istim id in zastavico odgovora."""

    def __init__(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind(("127.0.0.1", 0))
        self.vrata = self.s.getsockname()[1]
        self.prejeto = []
        threading.Thread(target=self._tek, daemon=True).start()

    def _tek(self):
        while True:
            try:
                p, od = self.s.recvfrom(4096)
            except OSError:
                return
            self.prejeto.append(os_scit.ime_poizvedbe(p))
            self.s.sendto(p[:2] + b"\x81\x80" + p[4:], od)

    def zapri(self):
        self.s.close()


class RazresevalnikTest(unittest.TestCase):
    def test_zavrne_in_posreduje(self):
        gor = LazniUpstream()
        r = os_scit.Razresevalnik(lambda ime: "oglasi" if ime.endswith("ads.example") else None, lambda: ["127.0.0.1"])
        # Upstream na drugih vratih: posredovanje preusmerimo na lazni streznik.
        izvirni = r._posreduj

        def posreduj(paket, tcp):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.sendto(paket, ("127.0.0.1", gor.vrata))
            o, _ = s.recvfrom(4096)
            s.close()
            return o
        r._posreduj = posreduj
        vrata = r.zazeni()
        self.assertIn(vrata, os_scit.VRATA)
        try:
            k = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            k.settimeout(3)
            k.sendto(vprasanje("x.ads.example", id_=7), (os_scit.NASLOV, vrata))
            o, _ = k.recvfrom(4096)
            self.assertEqual(o[:2], b"\x00\x07")
            self.assertEqual(struct.unpack("!H", o[2:4])[0] & 0xF, 3)
            k.sendto(vprasanje("safeer.si", id_=8), (os_scit.NASLOV, vrata))
            o, _ = k.recvfrom(4096)
            self.assertEqual(o[:2], b"\x00\x08")
            self.assertEqual(o[2:4], b"\x81\x80")
            self.assertEqual(gor.prejeto, ["safeer.si"])
            # TCP: dolzina + paket.
            with socket.create_connection((os_scit.NASLOV, vrata), timeout=3) as t:
                p = vprasanje("y.ads.example", id_=9)
                t.sendall(struct.pack("!H", len(p)) + p)
                n = struct.unpack("!H", t.recv(2))[0]
                o = t.recv(n)
            self.assertEqual(o[:2], b"\x00\x09")
            self.assertEqual(r.blokiranih, 2)
            self.assertEqual(r.poizvedb, 3)
            self.assertEqual([z["ime"] for z in r.zadnje], ["y.ads.example", "x.ads.example"])
            k.close()
        finally:
            izvirni  # noqa: B018 - le da ostane sklic
            r.ustavi()
            gor.zapri()
        self.assertEqual(r.vrata, 0)


class UsmeriTest(unittest.TestCase):
    def test_rezerva_za_docker(self):
        """resolvectl dobi nas razresevalnik PRVI in streznike usmerjevalnika kot rezervo: brez njih bi
        /run/systemd/resolve/resolv.conf ostal brez uporabnega streznika (Docker izpusti loopback)."""
        klici = []

        def zazeni(ukaz, cas=8.0):
            klici.append(ukaz)
            return 0, ""
        izvirni = os_scit._zazeni
        os_scit._zazeni = zazeni
        try:
            self.assertTrue(os_scit.usmeri("eth9", 5354, ["192.168.0.1", "1.1.1.1"]))
        finally:
            os_scit._zazeni = izvirni
        self.assertEqual(klici[0], ["resolvectl", "dns", "eth9", "127.0.0.1:5354", "192.168.0.1", "1.1.1.1"])
        self.assertEqual(klici[1], ["resolvectl", "domain", "eth9", "~."])

    def test_trenutni_streznik(self):
        izvirni = os_scit._zazeni
        os_scit._zazeni = lambda ukaz, cas=8.0: (0, "Link 2 (eth9)\n    Current DNS Server: 192.168.0.1\n       DNS Servers: 127.0.0.1:5354 192.168.0.1\n")
        try:
            self.assertEqual(os_scit.trenutni_streznik("eth9"), "192.168.0.1")
        finally:
            os_scit._zazeni = izvirni


class ScitTest(unittest.TestCase):
    def test_stanje_brez_sistema(self):
        class Shramba(dict):
            def get(self, k, d=None):
                return dict.get(self, k, d)

            def set(self, k, v):
                self[k] = v
        with tempfile.TemporaryDirectory() as m:
            sc = os_scit.Scit(Shramba(), mapa=m)
            st = sc.stanje()
            self.assertFalse(st["vklop"])
            self.assertFalse(st["tece"])
            self.assertEqual(st["blokiranih"], 0)
            self.assertIn("pravilo", st)
            # Izklop brez vklopa nic ne pokvari.
            self.assertFalse(sc.nastavi(False)["vklop"])


if __name__ == "__main__":
    unittest.main()
