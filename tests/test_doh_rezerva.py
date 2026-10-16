#!/usr/bin/env python3
"""Rezerva DoH na fallback_ip: ko sistemski DNS ne razresi imena ponudnika (dns.quad9.net), gre poizvedba na njegov
stalni naslov IP - z obicajnim preverjanjem TLS in samo, ce potrdilo velja tudi za ime ponudnika. Brez omrezja (mock)."""

import os
import struct
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.doh_proxy as doh_proxy  # noqa: E402
from gi.repository import Gio  # noqa: E402


def _odgovor_a(ime: str, naslov: str) -> bytes:
    vprasanje = doh_proxy.DoHResolver._ime_v_zapis(ime) + struct.pack(">HH", 1, 1)
    zapis = b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 300, 4) + bytes(int(x) for x in naslov.split("."))
    return struct.pack(">HHHHHH", 0, 0x8180, 1, 1, 0, 0) + vprasanje + zapis


class LaznaZanka:
    """Ime ponudnika se ne razresi; na naslovu IP odgovori, ce klicatelj zahteva preverjanje potrdila za ime."""

    def __init__(self, ime_razreseno=False):
        self.klici = []
        self.ime_razreseno = ime_razreseno

    def poslji(self, url, telo, timeout, ime_potrdila=""):
        self.klici.append((url, ime_potrdila))
        if "dns.quad9.net" in url and not self.ime_razreseno:
            raise doh_proxy.ImeNiRazreseno(url)
        return 200, "application/dns-message", _odgovor_a("example.com", "93.184.215.14")


class PreizkusRezerve(unittest.TestCase):
    def _poizvedi(self, zanka, provider="quad9", custom_url=""):
        r = doh_proxy.DoHResolver(provider, custom_url)
        with mock.patch.object(doh_proxy, "_zanka_doh", return_value=zanka):
            return r, r._poizvedba("example.com", 1.0, 1)

    def test_neuspela_razresitev_gre_na_fallback_ip_s_preverjanjem_imena(self):
        zanka = LaznaZanka()
        _, (ip, ttl) = self._poizvedi(zanka)
        self.assertEqual(ip, "93.184.215.14")
        self.assertEqual(ttl, 300)
        self.assertEqual(zanka.klici, [
            ("https://dns.quad9.net/dns-query", ""),
            ("https://9.9.9.9/dns-query", "dns.quad9.net"),
        ])

    def test_ime_razreseno_brez_rezerve(self):
        zanka = LaznaZanka(ime_razreseno=True)
        self._poizvedi(zanka)
        self.assertEqual(zanka.klici, [("https://dns.quad9.net/dns-query", "")])

    def test_med_cakanjem_ne_sprasuje_dns_znova(self):
        zanka = LaznaZanka()
        r, _ = self._poizvedi(zanka)
        with mock.patch.object(doh_proxy, "_zanka_doh", return_value=zanka):
            r._poizvedba("example.org", 1.0, 1)
        self.assertEqual(zanka.klici[-1], ("https://9.9.9.9/dns-query", "dns.quad9.net"))
        self.assertEqual(len(zanka.klici), 3)
        r.set_provider("google")
        self.assertEqual(r._rezerva_do, 0.0)

    def test_lasten_streznik_nima_rezerve(self):
        zanka = LaznaZanka()
        _, (ip, _ttl) = self._poizvedi(zanka, "custom", "https://dns.quad9.net/dns-query")
        self.assertIsNone(ip)
        self.assertEqual(len(zanka.klici), 1)

    def test_vsi_vgrajeni_ponudniki_imajo_veljaven_fallback_ip(self):
        import ipaddress
        for ponudnik in doh_proxy.DOH_PROVIDERS.values():
            self.assertTrue(doh_proxy.je_javni_naslov(str(ipaddress.ip_address(ponudnik["fallback_ip"]))))


class LaznoPotrdilo:
    def __init__(self, zastavice):
        self.zastavice = zastavice
        self.identiteta = None

    def verify(self, identiteta, _ca):
        self.identiteta = identiteta
        return self.zastavice


class PreizkusPotrdila(unittest.TestCase):
    def test_potrdilo_za_ime_sprejeto(self):
        p = LaznoPotrdilo(Gio.TlsCertificateFlags(0))
        self.assertTrue(doh_proxy._potrdilo_velja_za(p, "dns.quad9.net"))
        self.assertEqual(p.identiteta.get_hostname(), "dns.quad9.net")

    def test_tuje_ime_ali_brez_potrdila_zavrnjeno(self):
        self.assertFalse(doh_proxy._potrdilo_velja_za(LaznoPotrdilo(Gio.TlsCertificateFlags.BAD_IDENTITY), "dns.quad9.net"))
        self.assertFalse(doh_proxy._potrdilo_velja_za(None, "dns.quad9.net"))


if __name__ == "__main__":
    unittest.main()
