"""DoH posrednik (1.0.110): AAAA kot rezerva, razumljivo sporocilo ob neuspehu povezave, stikalo »dovoli lokalno omrezje«.

Neodvisni pregled 8. 10. 2026: (1) samo zapisi A - strani samo z IPv6 so padle s tihim 502; (2) lastni DoH (Pi-hole,
usmerjevalnik) prevede domace ime v domaci naslov, posrednik pa je zavrnil vse - uporabnik bi izklopil ves DoH."""
import os
import socket
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.doh_proxy as doh_proxy  # noqa: E402
from core.doh_proxy import DoHResolver, LocalDoHProxy, je_dovoljen_cilj  # noqa: E402

R = DoHResolver


def _rr(lastnik, tip, ttl, rdata):
    return lastnik + tip.to_bytes(2, "big") + b"\x00\x01" + ttl.to_bytes(4, "big") + len(rdata).to_bytes(2, "big") + rdata


def _odgovor(ime, qtype, zapisi):
    m = bytearray(b"\x00\x00\x81\x80\x00\x01" + len(zapisi).to_bytes(2, "big") + b"\x00\x00\x00\x00"
                  + R._ime_v_zapis(ime) + qtype.to_bytes(2, "big") + b"\x00\x01")
    for z in zapisi:
        m += z
    return bytes(m)


class Vtic:
    def __init__(self):
        self.poslano = b""
        self.zaprt = False

    def sendall(self, podatki):
        self.poslano += podatki

    def close(self):
        self.zaprt = True

    def settimeout(self, _):
        pass


class Razresevalnik:
    provider = "preizkus"

    def __init__(self, naslov):
        self.naslov = naslov

    def resolve(self, hostname, timeout=3.5):
        return self.naslov


class Aaaa(unittest.TestCase):

    def test_poizvedba_aaaa_ima_tip_28(self):
        self.assertTrue(R._build_dns_wire_query("example.com", 28).endswith(b"\x00\x1c\x00\x01"))
        self.assertTrue(R._build_dns_wire_query("example.com").endswith(b"\x00\x01\x00\x01"))

    def test_odgovor_aaaa_se_prebere(self):
        naslov = bytes.fromhex("26064700000000000000000000001111")
        m = _odgovor("ipv6.test", 28, [_rr(b"\xc0\x0c", 28, 120, naslov)])
        self.assertEqual(R._parse_dns_wire_response(m, "ipv6.test", 28), ("2606:4700::1111", 120))

    def test_a_odgovor_na_aaaa_vprasanje_ni_sprejet(self):
        m = _odgovor("ipv6.test", 28, [_rr(b"\xc0\x0c", 1, 120, bytes([9, 9, 9, 9]))])
        self.assertIsNone(R._parse_dns_wire_response(m, "ipv6.test", 28)[0])

    def test_aaaa_odgovor_na_a_vprasanje_ni_sprejet(self):
        naslov = bytes.fromhex("26064700000000000000000000001111")
        m = _odgovor("ipv6.test", 1, [_rr(b"\xc0\x0c", 28, 120, naslov)])
        self.assertIsNone(R._parse_dns_wire_response(m, "ipv6.test")[0])

    def test_aaaa_za_tuje_ime_ni_sprejet(self):
        naslov = bytes.fromhex("26064700000000000000000000001111")
        m = _odgovor("banka.si", 28, [_rr(R._ime_v_zapis("evil.test"), 28, 120, naslov)])
        self.assertIsNone(R._parse_dns_wire_response(m, "banka.si", 28)[0])

    def _razresevalnik(self, odgovori):
        r = DoHResolver("cloudflare")
        klici = []

        def poizvedba(ime, timeout, qtype=1):
            klici.append(qtype)
            return odgovori[qtype]
        r._poizvedba = poizvedba
        return r, klici

    def test_brez_a_vprasa_za_aaaa(self):
        r, klici = self._razresevalnik({1: (None, 300), 28: ("2606:4700::1111", 120)})
        self.assertEqual(r._query_doh("ipv6.test", 3.0), ("2606:4700::1111", 120))
        self.assertEqual(klici, [1, 28])

    def test_z_a_ne_vprasa_za_aaaa(self):
        r, klici = self._razresevalnik({1: ("93.184.215.14", 300), 28: ("2606::1", 1)})
        self.assertEqual(r._query_doh("example.com", 3.0), ("93.184.215.14", 300))
        self.assertEqual(klici, [1])

    def test_napaka_prenosa_ne_sprozi_aaaa(self):
        r, klici = self._razresevalnik({1: (None, 15), 28: ("2606::1", 1)})
        self.assertEqual(r._query_doh("example.com", 3.0), (None, 15))
        self.assertEqual(klici, [1])

    def test_nobenega_zapisa_ostane_neuspeh(self):
        r, klici = self._razresevalnik({1: (None, 300), 28: (None, 300)})
        self.assertIsNone(r._query_doh("ne-obstaja.test", 3.0)[0])
        self.assertEqual(klici, [1, 28])

    def test_ipv6_naslov_gre_skozi_varovalko_javnih_naslovov(self):
        p = LocalDoHProxy(Razresevalnik("2606:4700::1111"))
        self.assertEqual(p._pripravi_cilj(Vtic(), "ipv6.test", 443), "2606:4700::1111")
        v = Vtic()
        self.assertIsNone(LocalDoHProxy(Razresevalnik("fd00::1"))._pripravi_cilj(v, "zlo.test", 443))
        self.assertIn(b"403", v.poslano)


class Povezava(unittest.TestCase):

    def test_ipv6_brez_omrezja_pove_razlog(self):
        p = LocalDoHProxy(Razresevalnik("2606:4700::1111"))
        v = Vtic()
        with mock.patch("socket.create_connection", side_effect=OSError(101, "Network is unreachable")):
            self.assertIsNone(p._vzpostavi_povezavo(v, "2606:4700::1111", 443))
        self.assertIn(b"502", v.poslano)
        self.assertIn(b"IPv6", v.poslano)
        self.assertIn(b"Content-Length:", v.poslano)
        self.assertTrue(v.zaprt)

    def test_ipv4_neuspeh_pove_razlog(self):
        p = LocalDoHProxy(Razresevalnik("93.184.215.14"))
        v = Vtic()
        with mock.patch("socket.create_connection", side_effect=OSError("zavrnjeno")):
            self.assertIsNone(p._vzpostavi_povezavo(v, "93.184.215.14", 443))
        self.assertIn(b"502", v.poslano)
        self.assertNotIn(b"IPv6", v.poslano)

    def test_uspesna_povezava_vrne_vtic(self):
        p = LocalDoHProxy(Razresevalnik("93.184.215.14"))
        lazni = object()
        with mock.patch("socket.create_connection", return_value=lazni) as c:
            self.assertIs(p._vzpostavi_povezavo(Vtic(), "93.184.215.14", 443), lazni)
        c.assert_called_once()

    def test_neuspelo_razresevanje_je_razumljivo(self):
        p = LocalDoHProxy(Razresevalnik(None))
        v = Vtic()
        self.assertIsNone(p._pripravi_cilj(v, "ne-obstaja.test", 443))
        self.assertIn(b"502", v.poslano)
        self.assertIn(b"Content-Length:", v.poslano)


class LokalnoOmrezje(unittest.TestCase):
    DOMACI = ["192.168.0.1", "10.1.2.3", "172.16.5.5", "172.31.255.254", "100.64.0.1", "fd00::1", "fc00::5", "::ffff:192.168.1.1"]
    VEDNO_ZAVRNJENI = ["127.0.0.1", "127.1.2.3", "169.254.169.254", "169.254.0.1", "0.0.0.0", "0.1.2.3", "224.0.0.1",
                       "240.0.0.1", "255.255.255.255", "::1", "fe80::1", "::", "ff02::1", "::ffff:127.0.0.1",
                       "::ffff:169.254.169.254", "11.0.0.1x", ""]
    JAVNI = ["1.1.1.1", "93.184.216.34", "2606:4700::1111"]

    def test_privzeto_je_lokalno_zavrnjeno(self):
        for n in self.DOMACI:
            with self.subTest(n):
                self.assertFalse(je_dovoljen_cilj(n))
                self.assertFalse(je_dovoljen_cilj(n, False))

    def test_s_stikalom_je_domace_omrezje_dovoljeno(self):
        for n in self.DOMACI:
            with self.subTest(n):
                self.assertTrue(je_dovoljen_cilj(n, True))

    def test_stikalo_nikoli_ne_odpre_nevarnih_naslovov(self):
        for n in self.VEDNO_ZAVRNJENI:
            with self.subTest(n):
                self.assertFalse(je_dovoljen_cilj(n, True))

    def test_javni_so_vedno_dovoljeni(self):
        for n in self.JAVNI:
            for stikalo in (False, True):
                with self.subTest((n, stikalo)):
                    self.assertTrue(je_dovoljen_cilj(n, stikalo))

    def test_posrednik_privzeto_zavrne_domaci_naslov(self):
        v = Vtic()
        self.assertIsNone(LocalDoHProxy(Razresevalnik("192.168.0.1"))._pripravi_cilj(v, "router.lan", 80))
        self.assertIn(b"403", v.poslano)

    def test_posrednik_s_stikalom_spusti_domaci_naslov(self):
        v = Vtic()
        p = LocalDoHProxy(Razresevalnik("192.168.0.1"), dovoli_lokalno=True)
        self.assertEqual(p._pripravi_cilj(v, "router.lan", 80), "192.168.0.1")
        self.assertEqual(v.poslano, b"")

    def test_posrednik_s_stikalom_se_vedno_zavrne_metapodatke(self):
        v = Vtic()
        p = LocalDoHProxy(Razresevalnik("169.254.169.254"), dovoli_lokalno=True)
        self.assertIsNone(p._pripravi_cilj(v, "metapodatki.test", 80))
        self.assertIn(b"403", v.poslano)

    def test_vrata_ostanejo_omejena_tudi_s_stikalom(self):
        v = Vtic()
        p = LocalDoHProxy(Razresevalnik("192.168.0.1"), dovoli_lokalno=True)
        self.assertIsNone(p._pripravi_cilj(v, "router.lan", 22))
        self.assertIn(b"403", v.poslano)

    def test_get_doh_proxy_posodobi_stikalo(self):
        with mock.patch.object(LocalDoHProxy, "start", return_value=1234):
            try:
                a = doh_proxy.get_doh_proxy("cloudflare", "", True, lokalno=False)
                self.assertFalse(a.dovoli_lokalno)
                b = doh_proxy.get_doh_proxy("cloudflare", "", True, lokalno=True)
                self.assertIs(a, b)
                self.assertTrue(b.dovoli_lokalno)
            finally:
                doh_proxy._global_proxy = None
                doh_proxy._global_resolver = None


class Priklop(unittest.TestCase):
    """Stikalo mora v resnici priti do posrednika in imeti privzeto izklopljeno vrednost."""

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _src(self, rel):
        with open(os.path.join(self.ROOT, rel), encoding="utf-8") as f:
            return f.read()

    def test_privzeta_nastavitev_je_izklopljena(self):
        from core.config import DEFAULT_SETTINGS
        self.assertIs(DEFAULT_SETTINGS.get("doh_lokalno_omrezje"), False)

    def test_oba_klicatelja_posredujeta_stikalo(self):
        for rel in ("safeer_mint.py", "core/os_splet.py"):
            with self.subTest(rel):
                self.assertRegex(self._src(rel), r'(?s)get_doh_proxy\(.{0,400}?lokalno=.{0,100}?doh_lokalno_omrezje')

    def test_nastavitev_je_v_vmesniku(self):
        s = self._src("safeer_mint.py")
        self.assertIn("doh_lokalno_lbl", s)
        self.assertIn('"doh_lokalno_omrezje"', s)


if __name__ == "__main__":
    unittest.main()
