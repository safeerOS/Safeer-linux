"""Vsi naslovi IPv4 vmesnika, ne samo primarni (17. 11. 2026).

SIOCGIFADDR vrne en naslov na vmesnik. Racunalnik z dodatnim naslovom na kablu (npr. podomrezje, ki ga ima TV) je zato
napravi povedal samo primarnega, naprava pa kabelskega kandidata ni imela. getifaddrs vrne vsak naslov posebej.
Naslovi iz dokumentacijskih obsegov (RFC 5737), vmesniki so nadomestni (brez roota ne moremo dodati naslova).
"""
import socket
import subprocess
import unittest

from core import link_zvok

UP = 0x1
AF_INET6, AF_PACKET = 10, 17


class _Vsebnik:
    def __init__(self, contents):
        self.contents = contents

    def __bool__(self):
        return self.contents is not None


class _Naslov:
    def __init__(self, druzina, ip=None):
        self.sa_family = druzina
        self.sa_data = [0, 0] + (list(socket.inet_aton(ip)) if ip else [0, 0, 0, 0]) + [0] * 8


class _Zapis:
    def __init__(self, ime, naslov, zastavice=UP, naslednji=None):
        self.ifa_name = ime.encode()
        self.ifa_addr = _Vsebnik(naslov) if naslov is not None else None
        self.ifa_flags = zastavice
        self.ifa_next = _Vsebnik(naslednji) if naslednji is not None else None


def _veriga(*zapisi):
    for a, b in zip(zapisi, zapisi[1:]):
        a.ifa_next = _Vsebnik(b)
    return _Vsebnik(zapisi[0]) if zapisi else None


class Veriga(unittest.TestCase):
    def test_primarni_in_dodatni_naslov_istega_vmesnika(self):
        v = _veriga(_Zapis("enp1s0", _Naslov(socket.AF_INET, "198.51.100.1")),
                    _Zapis("enp1s0", _Naslov(socket.AF_INET, "203.0.113.3")))
        self.assertEqual(link_zvok._ifaddrs_v_seznam(v),
                         [("enp1s0", "198.51.100.1", UP), ("enp1s0", "203.0.113.3", UP)])

    def test_druge_druzine_in_zapisi_brez_naslova_se_preskocijo(self):
        v = _veriga(_Zapis("enp1s0", _Naslov(AF_INET6)), _Zapis("enp1s0", _Naslov(AF_PACKET)),
                    _Zapis("tun0", None), _Zapis("wlp0s20f3", _Naslov(socket.AF_INET, "192.0.2.10")))
        self.assertEqual(link_zvok._ifaddrs_v_seznam(v), [("wlp0s20f3", "192.0.2.10", UP)])

    def test_prazna_veriga(self):
        self.assertEqual(link_zvok._ifaddrs_v_seznam(None), [])


class Prava(unittest.TestCase):
    def test_vsak_naslov_iz_ip_je_med_nasteti(self):
        try:
            izpis = subprocess.run(["ip", "-4", "-o", "addr", "show"], capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            self.skipTest("ukaza ip ni")
        pricakovani = {(v[1], v[3].split("/")[0]) for v in (l.split() for l in izpis.splitlines()) if len(v) > 3}
        if not pricakovani:
            self.skipTest("ip ne pove naslovov")
        dobljeni = {(i, n) for i, n, _z in link_zvok.naslovi_vmesnikov()}
        self.assertTrue(pricakovani <= dobljeni, "manjka: %s" % sorted(pricakovani - dobljeni))

    def test_zanka_je_med_nasteti(self):
        self.assertIn("127.0.0.1", [n for _i, n, _z in link_zvok.naslovi_vmesnikov()])


class DodatniNaslovPridePredNapravo(unittest.TestCase):
    def test_hosts_vsebuje_dodatni_naslov_kabla(self):
        vmesniki = [("lo", "127.0.0.1", UP | 0x8), ("enp1s0", "198.51.100.1", UP), ("enp1s0", "203.0.113.3", UP),
                    ("wlp0s20f3", "192.0.2.10", UP)]
        naslovi = link_zvok.lastni_naslovi("", lambda: vmesniki, lambda c: "192.0.2.10")
        self.assertIn("203.0.113.3", naslovi)
        self.assertIn("198.51.100.1", naslovi)
        self.assertEqual(naslovi[0], "192.0.2.10")


if __name__ == "__main__":
    unittest.main()
