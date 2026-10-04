"""Krajevni posrednik Safeer Internet Gatewaya: protokoli programov, izbira poti, preklop ob izpadu.

Programi so pravi (vticnice, kjer je mogoce tudi curl), ponudnik je referencni (tests/pomoc_internet.py),
»domaci internet« je sonda z vbrizganim odgovorom.
"""
import json
import hashlib
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import unittest

from core import link_internet as li
from core import link_internet_posrednik as lp

import pomoc_internet as pi


class LazniSistemski:
    def __init__(self, podprt=True):
        self._podprt = podprt
        self.klici = []
        self._nastavljen = False

    def podprt(self):
        return self._podprt

    def nastavljen(self):
        return self._nastavljen

    def vklopi(self, vrata):
        self.klici.append(("vklopi", vrata))
        self._nastavljen = True
        return True

    def izklopi(self):
        if self._nastavljen:
            self.klici.append(("izklopi",))
        self._nastavljen = False
        return True

    def ob_zagonu(self):
        self.klici.append(("ob_zagonu",))


def _pocakaj(pogoj, rok=5.0):
    konec = time.monotonic() + rok
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(0.02)
    return pogoj()


class Osnova(unittest.TestCase):
    PROTOKOL = 2

    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-internet-")
        self.odjemalec, self.ponudnik, self.zica = pi.povezi(protokol=self.PROTOKOL)
        self.naprave = [{"id": "tel", "ime": "Telefon", "zmoznosti": ["url", "internet.gateway"]},
                        {"id": "tv", "ime": "Televizor", "zmoznosti": ["url"]}]
        self.fiksna = {"dela": True}
        self.sonda = lp.Sonda(lambda _d: None, cilji=(("x", 1),), dosegljiv=lambda _c, _r: self.fiksna["dela"])
        self.sistemski = LazniSistemski()
        self.obvestila = []
        self.u = lp.InternetUpravitelj(self.odjemalec, lambda: self.naprave, os.path.join(self.mapa, "internet.json"),
                                       sistemski=self.sistemski, obvesti=lambda k, p: self.obvestila.append((k, p)),
                                       sonda=self.sonda, krajevni_cilj=lambda _h: False)   # preizkusi ciljajo 127.0.0.1
        self.u.vrata = 0                       # katerakoli prosta vrata
        self.strezniki = []

    def tearDown(self):
        self.u.ustavi()
        for s in self.strezniki:
            s.zapri()
        self.zica.zapri()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def streznik(self, obravnava=pi.odmev):
        s = pi.Streznik(obravnava)
        self.strezniki.append(s)
        return s

    def povezi(self):
        c = socket.create_connection(("127.0.0.1", self.u.posrednik.vrata), timeout=5)
        c.settimeout(8)
        return c

    def socks5(self, host, vrata, ime=True):
        c = self.povezi()
        c.sendall(b"\x05\x01\x00")
        self.assertEqual(c.recv(2), b"\x05\x00")
        if ime:
            c.sendall(b"\x05\x01\x00\x03" + bytes([len(host)]) + host.encode() + struct.pack("!H", vrata))
        else:
            c.sendall(b"\x05\x01\x00\x01" + socket.inet_aton(host) + struct.pack("!H", vrata))
        odgovor = b""
        while len(odgovor) < 10:
            kos = c.recv(10 - len(odgovor))
            if not kos:
                break
            odgovor += kos
        return c, odgovor


class Protokoli(Osnova):
    def setUp(self):
        super().setUp()
        self.u.nastavi(nacin="vedno")

    def test_socks5_z_imenom_gre_skozi_telefon(self):
        s = self.streznik()
        c, odgovor = self.socks5("localhost", s.vrata)
        self.assertEqual(odgovor[:2], b"\x05\x00")
        c.sendall(b"zdravo")
        self.assertEqual(c.recv(100), b"zdravo")
        c.close()
        self.assertEqual(self.ponudnik.odprtih_skupaj, 1)
        self.assertEqual(self.ponudnik.zahtevane_poti, ["mobile"])

    def test_socks5_z_naslovom(self):
        s = self.streznik()
        c, odgovor = self.socks5("127.0.0.1", s.vrata, ime=False)
        self.assertEqual(odgovor[:2], b"\x05\x00")
        c.sendall(b"abc")
        self.assertEqual(c.recv(100), b"abc")
        c.close()

    def test_socks5_samo_connect(self):
        c = self.povezi()
        c.sendall(b"\x05\x01\x00")
        c.recv(2)
        c.sendall(b"\x05\x03\x00\x01\x7f\x00\x00\x01\x00\x50")       # UDP ASSOCIATE
        self.assertEqual(c.recv(10)[:2], b"\x05\x07")
        c.close()
        self.assertEqual(self.ponudnik.odprtih_skupaj, 0)

    def test_socks4a(self):
        s = self.streznik()
        c = self.povezi()
        c.sendall(b"\x04\x01" + struct.pack("!H", s.vrata) + b"\x00\x00\x00\x01" + b"uporabnik\x00" + b"localhost\x00")
        self.assertEqual(c.recv(8)[:2], b"\x00\x5a")
        c.sendall(b"stiri")
        self.assertEqual(c.recv(100), b"stiri")
        c.close()

    def test_http_connect(self):
        s = self.streznik()
        c = self.povezi()
        c.sendall(("CONNECT 127.0.0.1:%d HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n\r\n" % (s.vrata, s.vrata)).encode())
        self.assertTrue(c.recv(200).startswith(b"HTTP/1.1 200 "))
        c.sendall(b"tunel")
        self.assertEqual(c.recv(100), b"tunel")
        c.close()

    def test_navaden_http_se_prepise_v_obliko_izvora(self):
        videno = {}

        def http(c):
            zbrano = b""
            while b"\r\n\r\n" not in zbrano:
                zbrano += c.recv(4096)
            videno["glava"] = zbrano.decode()
            c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
        s = self.streznik(http)
        c = self.povezi()
        c.sendall(("GET http://127.0.0.1:%d/pot/datoteka?x=1 HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n"
                   "Proxy-Connection: keep-alive\r\nProxy-Authorization: Basic skrivnost\r\nAccept: */*\r\n\r\n"
                   % (s.vrata, s.vrata)).encode())
        self.assertTrue(pi.preberi_vse(c, 8).endswith(b"\r\n\r\nok"))
        vrstice = videno["glava"].split("\r\n")
        self.assertEqual(vrstice[0], "GET /pot/datoteka?x=1 HTTP/1.1")
        self.assertIn("Connection: close", vrstice)
        self.assertFalse(any(v.lower().startswith("proxy-") for v in vrstice), "glave za posrednika ne smejo do streznika")
        self.assertIn("Accept: */*", vrstice)

    def test_zahteva_v_obliki_izvora_ni_posredniska(self):
        """Spletna stran, ki poklice http://127.0.0.1:vrata/, ne sme skozi posrednika nikamor."""
        c = self.povezi()
        c.sendall(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        self.assertTrue(c.recv(200).startswith(b"HTTP/1.1 400 "))
        self.assertEqual(self.ponudnik.odprtih_skupaj, 0)
        c.close()

    def test_napaka_ponudnika_v_jeziku_programa(self):
        self.ponudnik.dovoljenje = "pending"
        _c, odgovor = self.socks5("localhost", 80)
        self.assertEqual(odgovor[:2], b"\x05\x02", "socks5: »ni dovoljeno«")
        c = self.povezi()
        c.sendall(b"CONNECT example.org:443 HTTP/1.1\r\n\r\n")
        o = c.recv(500).decode()
        self.assertTrue(o.startswith("HTTP/1.1 403 "), o)
        self.assertIn("X-Safeer-Reason: permission_required", o)
        self.assertEqual(self.u.stanje()["napaka"], "permission_required")

    def test_cilj_ne_odgovarja(self):
        prost = socket.socket()
        prost.bind(("127.0.0.1", 0))
        vrata = prost.getsockname()[1]
        prost.close()
        _c, odgovor = self.socks5("127.0.0.1", vrata, ime=False)
        self.assertEqual(odgovor[:2], b"\x05\x05", "socks5: »povezava zavrnjena«")

    @unittest.skipUnless(shutil.which("curl"), "curl ni namescen")
    def test_curl_skozi_socks5_in_http(self):
        def http(c):
            zbrano = b""
            while b"\r\n\r\n" not in zbrano:
                zbrano += c.recv(4096)
            telo = b"x" * 300000
            c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(telo) + telo)
        s = self.streznik(http)
        vrata = self.u.posrednik.vrata
        for posrednik in ("socks5h://127.0.0.1:%d" % vrata, "http://127.0.0.1:%d" % vrata, "socks4a://127.0.0.1:%d" % vrata):
            # --noproxy '' : curl sicer za 127.0.0.1 posrednika preskoci.
            o = subprocess.run(["curl", "-sS", "--noproxy", "", "-x", posrednik, "-o", "/dev/null", "-w", "%{http_code} %{size_download}",
                                "--max-time", "20", "http://127.0.0.1:%d/velika" % s.vrata], capture_output=True, text=True)
            self.assertEqual(o.stdout.strip(), "200 300000", posrednik + " " + o.stderr)
        self.assertEqual(self.ponudnik.odprtih_skupaj, 3)
        self.assertFalse(self.zica.prekoraceno)


class IzbiraPoti(Osnova):
    def test_izklopljeno_posrednika_ni(self):
        self.assertFalse(self.u.posrednik.tece)
        self.assertEqual(self.u.stanje()["nacin"], "izklopljeno")
        self.assertEqual(self.sistemski.klici, [])

    def test_izpad_dokler_domaci_internet_dela_gre_neposredno(self):
        s = self.streznik()
        self.u.nastavi(nacin="izpad", sistemski=True)
        c, odgovor = self.socks5("127.0.0.1", s.vrata, ime=False)
        self.assertEqual(odgovor[:2], b"\x05\x00")
        c.sendall(b"doma")
        self.assertEqual(c.recv(100), b"doma")
        c.close()
        self.assertEqual(self.ponudnik.odprtih_skupaj, 0, "dokler domaci internet dela, telefona ne uporabljamo")
        self.assertFalse(self.u.prek_telefona)
        self.assertNotIn(("vklopi", self.u.posrednik.vrata), self.sistemski.klici)

    def test_izpad_preklopi_na_telefon_in_nazaj(self):
        s = self.streznik()
        self.u.nastavi(nacin="izpad", sistemski=True)
        self.fiksna["dela"] = False
        self.sonda.preveri()
        self.assertTrue(self.sonda.dela, "en neuspel krog se ni izpad")
        self.sonda.preveri()
        self.assertFalse(self.sonda.dela)
        self.assertTrue(self.u.prek_telefona)
        self.assertTrue(_pocakaj(lambda: ("vklopi", self.u.posrednik.vrata) in self.sistemski.klici))
        self.assertEqual(self.obvestila[-1][0], "prek_telefona")
        self.assertEqual(self.obvestila[-1][1]["telefon"], "Telefon")
        c, odgovor = self.socks5("127.0.0.1", s.vrata, ime=False)
        self.assertEqual(odgovor[:2], b"\x05\x00")
        c.sendall(b"mobilno")
        self.assertEqual(c.recv(100), b"mobilno")
        c.close()
        self.assertEqual(self.ponudnik.odprtih_skupaj, 1)
        # Domaci internet se vrne: novi tokovi spet neposredno, sistemski posrednik nazaj.
        self.fiksna["dela"] = True
        self.sonda.preveri()
        self.sonda.preveri()
        self.assertFalse(self.u.prek_telefona)
        self.assertTrue(_pocakaj(lambda: self.sistemski.klici[-1] == ("izklopi",)))
        self.assertEqual(self.obvestila[-1][0], "nazaj_doma")
        c, _odgovor = self.socks5("127.0.0.1", s.vrata, ime=False)
        c.close()
        self.assertEqual(self.ponudnik.odprtih_skupaj, 1)

    def test_prva_povezava_ob_izpadu_gre_ze_skozi_telefon(self):
        """Sonda izpada se ni opazila, neposredna povezava pa pade: ta ista povezava mora skozi telefon."""
        s = self.streznik()
        self.u.nastavi(nacin="izpad")
        self.fiksna["dela"] = False
        izvirna = socket.create_connection

        def brez_omrezja(naslov, timeout=None, **kw):
            if threading.current_thread().name == "safeer-internet-povezava":
                raise OSError(101, "Network is unreachable")
            return izvirna(naslov, timeout=timeout, **kw)
        socket.create_connection = brez_omrezja
        try:
            c, odgovor = self.socks5("127.0.0.1", s.vrata, ime=False)
        finally:
            socket.create_connection = izvirna
        self.assertEqual(odgovor[:2], b"\x05\x00")
        c.sendall(b"takoj")
        self.assertEqual(c.recv(100), b"takoj")
        c.close()
        self.assertEqual(self.ponudnik.odprtih_skupaj, 1)
        self.assertTrue(self.u.prek_telefona)

    def test_napaka_cilja_ob_delujocem_internetu_ni_izpad(self):
        self.u.nastavi(nacin="izpad")
        prost = socket.socket()
        prost.bind(("127.0.0.1", 0))
        vrata = prost.getsockname()[1]
        prost.close()
        _c, odgovor = self.socks5("127.0.0.1", vrata, ime=False)
        self.assertEqual(odgovor[:2], b"\x05\x05")
        self.assertEqual(self.ponudnik.odprtih_skupaj, 0)
        self.assertFalse(self.u.prek_telefona)

    def test_brez_telefona_ni_preklopa(self):
        self.naprave[:] = [n for n in self.naprave if n["id"] != "tel"]
        self.u.nastavi(nacin="izpad", sistemski=True)
        self.fiksna["dela"] = False
        self.sonda.preveri()
        self.sonda.preveri()
        self.assertFalse(self.u.prek_telefona, "brez telefona ni kam preklopiti")
        time.sleep(0.2)
        self.assertNotIn("vklopi", [k[0] for k in self.sistemski.klici])
        _c, odgovor = self.socks5("example.org", 443)
        self.assertEqual(odgovor[:2], b"\x05\x03")
        self.assertEqual(self.u.stanje()["napaka"], "ni_telefona")

    def test_izbran_telefon_ki_ga_ni_se_ne_zamenja_z_drugim(self):
        self.naprave.append({"id": "tel2", "ime": "Drugi telefon", "zmoznosti": ["internet.gateway"]})
        self.u.nastavi(nacin="vedno", naprava="tel2")
        self.assertEqual(self.u.telefon(), "tel2")
        self.naprave.pop()
        self.assertIsNone(self.u.telefon(), "izbran je bil drug telefon; tega ne uporabimo brez vprasanja")
        self.u.nastavi(naprava="")
        self.assertEqual(self.u.telefon(), "tel")

    def test_sistemski_posrednik_je_privzeto_vklopljen_in_se_da_izklopiti(self):
        """Brez sistemskega posrednika brskalnik ob izpadu ne dela, dokler ga uporabnik rocno ne nastavi."""
        self.assertTrue(self.u.sistemski_vklopljen)
        self.assertEqual(self.sistemski.klici, [], "dokler je nacin izklopljen, se sistema ne dotaknemo")
        self.u.nastavi(nacin="vedno")
        self.assertTrue(_pocakaj(lambda: ("vklopi", self.u.posrednik.vrata) in self.sistemski.klici))
        self.u.nastavi(sistemski=False)
        self.assertTrue(_pocakaj(lambda: self.sistemski.klici[-1] == ("izklopi",)))
        self.u.nastavi(sistemski=True)
        self.assertTrue(_pocakaj(lambda: self.sistemski.klici[-1] == ("vklopi", self.u.posrednik.vrata)))
        self.u.nastavi(nacin="izklopljeno")
        self.assertTrue(_pocakaj(lambda: self.sistemski.klici[-1] == ("izklopi",)))
        self.assertFalse(self.u.posrednik.tece)

    def test_izklopljen_sistemski_posrednik_ostane_izklopljen(self):
        self.u.nastavi(nacin="vedno", sistemski=False)
        time.sleep(0.3)
        self.assertNotIn("vklopi", [k[0] for k in self.sistemski.klici])
        drugi = lp.InternetUpravitelj(self.odjemalec, lambda: self.naprave, self.u.pot_nastavitev, sistemski=LazniSistemski(),
                                      sonda=self.sonda)
        self.assertFalse(drugi.sistemski_vklopljen, "izbira prezivi ponovni zagon")

    def test_po_izklopu_na_vratih_nihce_ne_poslusa(self):
        self.u.nastavi(nacin="vedno")
        vrata = self.u.posrednik.vrata
        socket.create_connection(("127.0.0.1", vrata), timeout=2).close()
        self.u.nastavi(nacin="izklopljeno")

        def zaprto():
            try:
                socket.create_connection(("127.0.0.1", vrata), timeout=1).close()
                return False
            except OSError:
                return True
        self.assertTrue(_pocakaj(zaprto, 3), "posrednik po izklopu se poslusa")

    def test_ustavitev_vrne_sistemski_posrednik(self):
        self.u.nastavi(nacin="vedno", sistemski=True)
        self.assertTrue(_pocakaj(lambda: self.sistemski.nastavljen()))
        self.u.ustavi()
        self.assertFalse(self.sistemski.nastavljen(), "ob izhodu sistemski posrednik ne sme ostati nas")


class DomaceOmrezje(Osnova):
    """Cilji v domacem omrezju gredo vedno neposredno - tudi ko gre internet skozi telefon."""

    def test_kateri_cilji_so_krajevni(self):
        for cilj in ("192.168.0.1", "10.1.2.3", "172.16.5.5", "127.0.0.1", "169.254.10.10", "localhost", "tiskalnik",
                     "nas.local", "Tiskalnik.Local.", "::1", "[fe80::1]", "fd12:3456::1", "fe80::1%eth0"):
            self.assertTrue(lp.je_krajevni_cilj(cilj), cilj)
        for cilj in ("safeer.si", "8.8.8.8", "172.32.0.1", "example.org.", "2606:4700::1111", "local.example.com", "",
                     "192.168.0.1.nip.io"):
            self.assertFalse(lp.je_krajevni_cilj(cilj), cilj)

    def test_krajevni_cilj_ne_gre_skozi_telefon(self):
        s = self.streznik()
        self.u._krajevni_cilj = lp.je_krajevni_cilj
        self.u.nastavi(nacin="vedno")
        c, odgovor = self.socks5("127.0.0.1", s.vrata, ime=False)
        self.assertEqual(odgovor[:2], b"\x05\x00")
        c.sendall(b"tiskalnik")
        self.assertEqual(c.recv(100), b"tiskalnik")
        c.close()
        self.assertEqual(self.ponudnik.odprtih_skupaj, 0, "krajevni cilj ne sme do telefona")
        self.assertEqual(self.zica.gor.po_vrsti.get("internet.open", 0), 0)

    def test_krajevni_cilj_ki_ne_odgovarja_javi_napako(self):
        self.u._krajevni_cilj = lp.je_krajevni_cilj
        self.u.nastavi(nacin="vedno")
        prost = socket.socket()
        prost.bind(("127.0.0.1", 0))
        vrata = prost.getsockname()[1]
        prost.close()
        _c, odgovor = self.socks5("127.0.0.1", vrata, ime=False)
        self.assertEqual(odgovor[0], 5)
        self.assertNotEqual(odgovor[1], 0)
        self.assertEqual(self.ponudnik.odprtih_skupaj, 0)


class StariTelefon(Osnova):
    PROTOKOL = 1

    def test_telefon_brez_nadzora_pretoka_se_ne_uporablja(self):
        self.u.nastavi(nacin="vedno")
        zacetek = time.monotonic()
        _c, odgovor = self.socks5("example.org", 443)
        self.assertEqual(odgovor[:2], b"\x05\x03")
        _c, odgovor = self.socks5("example.org", 443)           # drugic brez ponovnega cakanja na odgovor
        self.assertEqual(odgovor[:2], b"\x05\x03")
        self.assertEqual(self.u.stanje()["napaka"], "old_provider")
        self.assertEqual(self.ponudnik.odprtih_skupaj, 0)
        self.assertLess(time.monotonic() - zacetek, li.ROK_STANJA_S + 3)


    def test_z_diagnosticno_zastavico_dela_brez_oken(self):
        """Samo za diagnostiko: telefon s protokolom 1 se sme uporabiti, ce to rocno vklopimo."""
        s = self.streznik()
        self.u.stari_ponudniki = True
        self.u.nastavi(nacin="vedno")
        c, odgovor = self.socks5("localhost", s.vrata)
        self.assertEqual(odgovor[:2], b"\x05\x00")
        c.sendall(b"zdravo")
        self.assertEqual(c.recv(100), b"zdravo")
        c.close()
        self.assertEqual(self.zica.gor.po_vrsti.get("internet.window", 0), 0, "stari telefon oken ne pozna")


class DiagnosticnaZastavica(Osnova):
    """`stari_ponudniki` ne sme izklopiti nadzora pretoka pri telefonu, ki ga zna (izmerjeno v krogu 102:
    po ponovnem zagonu Controla protokol se ni bil znan, tok je stekel brez oken in obstal po 128 KiB)."""

    def test_nov_telefon_vedno_najprej_vprasamo(self):
        vsebina = os.urandom(600 * 1024)
        s = self.streznik(lambda c: c.sendall(vsebina))
        self.u.stari_ponudniki = True
        self.u.nastavi(nacin="vedno")
        self.assertEqual(self.odjemalec.protokol("tel"), 0, "pred prvo povezavo protokola se ne poznamo")
        c, odgovor = self.socks5("localhost", s.vrata)
        self.assertEqual(odgovor[:2], b"\x05\x00")
        prejeto = pi.preberi_vse(c, 15.0)
        self.assertEqual(hashlib.sha256(prejeto).hexdigest(), hashlib.sha256(vsebina).hexdigest())
        self.assertEqual(self.odjemalec.protokol("tel"), 2)
        self.assertGreaterEqual(self.zica.gor.po_vrsti.get("internet.window", 0), 1, "tok mora teci z okni")
        self.assertFalse(self.zica.prekoraceno)
        c.close()


class NastavitveInStanje(Osnova):
    def test_nastavitve_prezivijo_ponovni_zagon(self):
        self.u.nastavi(nacin="izpad", naprava="tel", sistemski=True, pot="any")
        vrata = self.u.posrednik.vrata
        self.u.ustavi()
        drugi = lp.InternetUpravitelj(self.odjemalec, lambda: self.naprave, self.u.pot_nastavitev, sonda=self.sonda)
        self.assertEqual((drugi.nacin, drugi.naprava, drugi.sistemski_vklopljen, drugi.pot, drugi.vrata),
                         ("izpad", "tel", True, "any", vrata))

    def test_neveljavne_nastavitve(self):
        self.assertFalse(self.u.nastavi(nacin="hitro")["ok"])
        self.assertFalse(self.u.nastavi(pot="satelit")["ok"])
        self.assertEqual(self.u.nacin, "izklopljeno")

    def test_pokvarjena_datoteka_nastavitev(self):
        with open(self.u.pot_nastavitev, "w") as f:
            f.write("{ni json")
        drugi = lp.InternetUpravitelj(self.odjemalec, lambda: self.naprave, self.u.pot_nastavitev, sonda=self.sonda)
        self.assertEqual(drugi.nacin, "izklopljeno")

    def test_zasedena_vrata_naslednja(self):
        zasedena = socket.socket()
        zasedena.bind(("127.0.0.1", 0))
        zasedena.listen(1)
        self.u.vrata = zasedena.getsockname()[1]
        self.u.nastavi(nacin="vedno")
        self.assertTrue(self.u.posrednik.tece)
        self.assertNotEqual(self.u.posrednik.vrata, zasedena.getsockname()[1])
        self.assertEqual(self.u.stanje()["posrednik"]["vrata"], self.u.posrednik.vrata)
        zasedena.close()

    def test_poraba_se_steje_in_shrani(self):
        s = self.streznik()
        self.u.nastavi(nacin="vedno")
        c, _ = self.socks5("127.0.0.1", s.vrata, ime=False)
        c.sendall(b"x" * 5000)
        prejeto = b""
        while len(prejeto) < 5000:
            prejeto += c.recv(65536)
        c.close()
        self.assertTrue(_pocakaj(lambda: self.u.stanje()["poraba"]["seja"] == 10000))
        stanje = self.u.stanje()
        self.assertEqual(stanje["poraba"]["danes"], 10000)
        self.assertEqual(stanje["poraba"]["mesec"], 10000)
        self.u.ustavi()
        with open(self.u.pot_nastavitev) as f:
            self.assertEqual(json.load(f)["poraba"]["mesec_bajti"], 10000)

    def test_stanje_ima_vse_za_vmesnik(self):
        self.u.nastavi(nacin="vedno")
        self.assertTrue(_pocakaj(self.sistemski.nastavljen), "v nacinu »vedno« je sistemski posrednik nas")
        s = self.u.stanje(vprasaj=True)
        self.assertEqual(s["telefon"], "tel")
        self.assertEqual(s["telefoni"], [{"id": "tel", "ime": "Telefon"}])
        self.assertEqual(s["protokol"], 2)
        self.assertEqual(s["ponudnik"]["permission"], "allowed")
        self.assertFalse(s["brez_odgovora"])
        self.assertTrue(s["posrednik"]["tece"])
        self.assertEqual(s["sistemski"], {"vklopljen": True, "podprt": True, "nastavljen": True})

    def test_stanje_pove_da_telefon_ne_odgovarja(self):
        """Telefon oglasa deljenje, na vprasanje pa molci (starejsi Safeer OS): vmesnik to pove, ne caka v nedogled."""
        self.ponudnik.protokol = 1
        self.u.nastavi(nacin="vedno")
        prej = li.ROK_STANJA_S
        li.ROK_STANJA_S = 0.4
        try:
            # vprasaj() ima privzeti rok kot privzeto vrednost parametra: klicemo ga s krajsim rokom.
            izvirni = self.odjemalec.vprasaj
            self.odjemalec.vprasaj = lambda naprava, cas=0.4: izvirni(naprava, cas)
            s = self.u.stanje(vprasaj=True)
            self.assertIsNone(s["ponudnik"])
            self.assertTrue(s["brez_odgovora"])
            self.assertTrue(self.u.stanje()["brez_odgovora"], "tudi brez novega vprasanja, dokler velja")
        finally:
            li.ROK_STANJA_S = prej

    def test_okolje_za_ukazno_vrstico(self):
        self.u.nastavi(nacin="vedno")
        o = self.u.okolje()
        self.assertEqual(o["ALL_PROXY"], "socks5h://127.0.0.1:%d" % self.u.posrednik.vrata)
        self.assertEqual(o["HTTPS_PROXY"], "http://127.0.0.1:%d" % self.u.posrednik.vrata)


class Zahteve(unittest.TestCase):
    def test_uid_iz_proc_net_tcp(self):
        vsebina = ("  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
                   "   0: 0100007F:BB12 0100007F:D5F2 01 00000000:00000000 00:00000000 00000000  1000        0 12345 1 0000 20 4 30 10 -1\n"
                   "   1: 0100007F:D5F2 0100007F:BB12 01 00000000:00000000 00:00000000 00000000  1001        0 12346 1 0000 20 4 30 10 -1\n")
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(vsebina)
        try:
            self.assertEqual(lp.uid_odjemalca(("127.0.0.1", 0xD5F2), 0xBB12, f.name), 1001)
            self.assertEqual(lp.uid_odjemalca(("127.0.0.1", 0xBB12), 0xD5F2, f.name), 1000)
            self.assertIsNone(lp.uid_odjemalca(("127.0.0.1", 1), 2, f.name))
            self.assertIsNone(lp.uid_odjemalca(("127.0.0.1", 1), 2, "/ni/te/datoteke"))
        finally:
            os.unlink(f.name)

    def test_cilji(self):
        self.assertEqual(lp._razdeli_cilj("example.org:8443", 443), ("example.org", 8443))
        self.assertEqual(lp._razdeli_cilj("example.org", 80), ("example.org", 80))
        self.assertEqual(lp._razdeli_cilj("[2001:db8::1]:443", 80), ("2001:db8::1", 443))
        for slab in ("", "a b:80", "host:0", "host:99999", "host:x", "a/b:80", "[::1"):
            with self.assertRaises((lp.NapakaZahteve, ValueError), msg=slab):
                lp._razdeli_cilj(slab, 80)

    def test_razlog_povezave(self):
        self.assertEqual(lp.razlog_povezave(socket.gaierror(-2, "Name or service not known")), "dns_failed")
        self.assertEqual(lp.razlog_povezave(socket.timeout()), "timeout")
        self.assertEqual(lp.razlog_povezave(OSError(101, "Network is unreachable")), "no_path")
        self.assertEqual(lp.razlog_povezave(ConnectionRefusedError(111, "refused")), "connect_failed")


class SondaTest(unittest.TestCase):
    def test_dva_zaporedna_izida_spremenita_stanje(self):
        izidi = {"ok": True}
        spremembe = []
        s = lp.Sonda(spremembe.append, cilji=(("a", 1), ("b", 2)), dosegljiv=lambda _c, _r: izidi["ok"])
        self.assertTrue(s.preveri())
        izidi["ok"] = False
        self.assertTrue(s.preveri(), "en izgubljen krog ni izpad")
        izidi["ok"] = True
        s.preveri()
        izidi["ok"] = False
        s.preveri()
        self.assertTrue(s.dela, "neuspeha nista bila zaporedna")
        self.assertFalse(s.preveri())
        self.assertEqual(spremembe, [False])
        izidi["ok"] = True
        s.preveri()
        self.assertFalse(s.dela)
        self.assertTrue(s.preveri())
        self.assertEqual(spremembe, [False, True])

    def test_dovolj_je_en_dosegljiv_cilj(self):
        s = lp.Sonda(lambda _d: None, cilji=(("a", 1), ("b", 2), ("c", 3)), dosegljiv=lambda c, _r: c[0] == "c")
        self.assertTrue(s.krog())

    def test_takoj_ob_lastni_napaki(self):
        spremembe = []
        s = lp.Sonda(spremembe.append, cilji=(("a", 1),), dosegljiv=lambda _c, _r: False)
        self.assertFalse(s.preveri(takoj=True))
        self.assertEqual(spremembe, [False])


if __name__ == "__main__":
    unittest.main()
