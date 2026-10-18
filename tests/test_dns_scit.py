#!/usr/bin/env python3
"""Izbira DNS (lastnik, 16. 10. 2026): Safeer Scit privzeto (filter + naprej na Cloudflare DoH), pet javnih ponudnikov
(tudi Cisco OpenDNS), DNS po meri (DoH ali navaden IP, tudi Pi-hole), selitev obstojecih uporabnikov in samodejna
rezerva (SERVFAIL, cas, lazna blokada ponudnika). Brez omrezja: zanka DoH je lazna, navaden DNS je streznik na 127.0.0.1."""

import contextlib
import io
import json
import os
import socket
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.doh_proxy as doh_proxy  # noqa: E402
from core import config, os_scit  # noqa: E402
from core.doh_proxy import DoHResolver  # noqa: E402


def odgovor(ime: str, naslov: str = "", rcode: int = 0, soa: bool = False, qtype: int = 1, ident: bytes = b"\x00\x00") -> bytes:
    """Odgovor DNS na vprasanje (ime, qtype): zapis A/AAAA, ali samo rcode (NXDOMAIN s SOA ali brez)."""
    vprasanje = DoHResolver._ime_v_zapis(ime) + struct.pack(">HH", qtype, 1)
    zapisi = b""
    an = 0
    if naslov:
        rdata = socket.inet_pton(socket.AF_INET6 if ":" in naslov else socket.AF_INET, naslov)
        zapisi = b"\xc0\x0c" + struct.pack(">HHIH", 28 if ":" in naslov else 1, 1, 300, len(rdata)) + rdata
        an = 1
    ns = 0
    if soa:
        zapisi += b"\xc0\x0c" + struct.pack(">HHIH", 6, 1, 300, 2) + b"\x00\x00"
        ns = 1
    return ident + struct.pack(">HHHHH", 0x8180 | rcode, 1, an, ns, 0) + vprasanje + zapisi


class LaznaZanka:
    """Namesto libsoup: zapomni si naslove in vrne odgovor, ki ga doloci funkcija (url, ime, qtype)."""

    def __init__(self, odgovori):
        self.odgovori = odgovori
        self.klici = []

    def poslji(self, url, telo, timeout, ime_potrdila=""):
        ime, idx = DoHResolver._preberi_ime(telo, 12)
        qtype = int.from_bytes(telo[idx:idx + 2], "big")
        self.klici.append(url)
        o = self.odgovori(url, ime.decode(), qtype)
        return None if o is None else (200, "application/dns-message", o)


def nabor(*domene):
    s = os_scit.Seznami.__new__(os_scit.Seznami)
    s.nabor = os_scit.Nabor.iz_domen((d, "malware") for d in domene)
    s.storitev = None
    s._kljuc = threading.Lock()
    return s


@contextlib.contextmanager
def okolje(zanka, seznami=None, scit_vrata=0):
    """Lazna zanka DoH, Scitov nabor (None = nabora ni) in vrata sistemskega Scita (0 = ne tece)."""
    with mock.patch.object(doh_proxy, "_zanka_doh", return_value=zanka), \
            mock.patch.object(doh_proxy, "sistemski_scit_vrata", return_value=scit_vrata), \
            mock.patch.object(os_scit, "skupni_seznami", return_value=seznami if seznami is not None else nabor()):
        yield


class PrivzetoInSelitev(unittest.TestCase):
    def _profil(self, vsebina=None):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        pot = Path(d.name) / "settings.json"
        if vsebina is not None:
            pot.write_text(json.dumps(vsebina))
        for p in (mock.patch.object(config, "CONFIG_DIR", d.name), mock.patch.object(config, "CONFIG_FILE", str(pot))):
            p.start()
            self.addCleanup(p.stop)
        return pot

    def test_nova_namestitev_je_scit_z_cloudflare_naprej(self):
        self._profil()
        c = config.ConfigManager()
        self.assertEqual(c.get("doh_provider"), "scit")
        self.assertEqual(c.get("scit_naprej"), "cloudflare")
        self.assertTrue(c.get("doh_enabled"))
        self.assertTrue(c.get("dns_rezerva"))
        self.assertEqual(doh_proxy.IZBIRE_DNS[0], "scit")
        self.assertEqual(doh_proxy.IZBIRE_DNS[-2:], ("custom", "disabled"))

    def test_dosedanji_privzeti_cloudflare_se_preseli_na_scit(self):
        pot = self._profil({"doh_enabled": True, "doh_provider": "cloudflare"})
        c = config.ConfigManager()
        self.assertEqual(c.get("doh_provider"), "scit")
        self.assertEqual(c.get("scit_naprej"), "cloudflare")     # razresuje isti ponudnik kot prej
        self.assertTrue(json.loads(pot.read_text())["dns_scit_selitev"])
        c.set("doh_provider", "cloudflare")                      # izbere ga znova: selitev se ne ponovi
        self.assertEqual(config.ConfigManager().get("doh_provider"), "cloudflare")

    def test_izrecne_izbire_ostanejo(self):
        for prej in ({"doh_provider": "quad9"}, {"doh_provider": "custom", "custom_doh_url": "192.168.0.135"},
                     {"doh_provider": "cloudflare", "doh_enabled": False}, {"doh_provider": "disabled", "doh_enabled": False},
                     {"doh_provider": "cloudflare", "dns_izbira_uporabnika": True}):
            with self.subTest(prej=prej):
                self._profil(prej)
                c = config.ConfigManager()
                self.assertEqual(c.get("doh_provider"), prej["doh_provider"])
                self.assertEqual(c.get("doh_enabled"), prej.get("doh_enabled", True))


class PetPonudnikov(unittest.TestCase):
    PRICAKOVANO = {
        "quad9": "https://dns.quad9.net/dns-query",
        "cloudflare": "https://1.1.1.1/dns-query",
        "google": "https://dns.google/dns-query",
        "adguard": "https://dns.adguard-dns.com/dns-query",
        "opendns": "https://doh.opendns.com/dns-query",
    }

    def test_vsak_ponudnik_je_izbira_z_rezervnim_ip(self):
        for ponudnik, url in self.PRICAKOVANO.items():
            with self.subTest(ponudnik=ponudnik):
                self.assertIn(ponudnik, doh_proxy.IZBIRE_DNS)
                self.assertIn(ponudnik, doh_proxy.IZBIRE_NAPREJ)
                self.assertEqual(doh_proxy.DOH_PROVIDERS[ponudnik]["url"], url)
                self.assertTrue(doh_proxy.je_javni_naslov(doh_proxy.DOH_PROVIDERS[ponudnik]["fallback_ip"]))
        self.assertEqual(doh_proxy.DOH_PROVIDERS["opendns"]["fallback_ip"], "208.67.222.222")

    def test_izbrani_ponudnik_razresi(self):
        for ponudnik, url in self.PRICAKOVANO.items():
            with self.subTest(ponudnik=ponudnik):
                zanka = LaznaZanka(lambda u, ime, q: odgovor(ime, "93.184.215.14", qtype=q))
                with okolje(zanka):
                    r = DoHResolver(ponudnik)
                    self.assertEqual(r.resolve("example.com"), "93.184.215.14")
                self.assertEqual(zanka.klici, [url])

    def test_doh_iz_nastavitev_prenese_vse(self):
        klici = []
        with mock.patch.object(doh_proxy, "get_doh_proxy", side_effect=lambda **k: klici.append(k)):
            doh_proxy.doh_iz_nastavitev({"doh_provider": "opendns", "dns_rezerva": False})
            doh_proxy.doh_iz_nastavitev({"doh_provider": "disabled"})
            doh_proxy.doh_iz_nastavitev({"doh_provider": "neznan"})
        self.assertEqual((klici[0]["provider"], klici[0]["rezerva"]), ("opendns", False))
        self.assertEqual(klici[1], {"enabled": False})
        self.assertEqual((klici[2]["provider"], klici[2]["naprej"]), ("scit", "cloudflare"))


class StreznikDNS:
    """Navaden streznik DNS na 127.0.0.1 (kot Pi-hole): na vsako vprasanje A odgovori z naslovom."""

    def __init__(self, naslov="192.168.0.50"):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind(("127.0.0.1", 0))
        self.vrata = self.s.getsockname()[1]
        self.naslov = naslov
        self.vprasana = []
        threading.Thread(target=self._tek, daemon=True).start()

    def _tek(self):
        while True:
            try:
                paket, od = self.s.recvfrom(512)
            except OSError:
                return
            ime, idx = DoHResolver._preberi_ime(paket, 12)
            qtype = int.from_bytes(paket[idx:idx + 2], "big")
            self.vprasana.append(ime.decode())
            self.s.sendto(odgovor(ime.decode(), self.naslov if qtype == 1 else "", qtype=qtype, ident=paket[:2]), od)

    def zapri(self):
        self.s.close()


class DnsPoMeri(unittest.TestCase):
    def test_oblike(self):
        R = doh_proxy.razcleni_po_meri
        self.assertEqual(R("https://dns.nextdns.io/abc123"), ("doh", "https://dns.nextdns.io/abc123"))
        self.assertEqual(R("dns.primer.si"), ("doh", "https://dns.primer.si/dns-query"))
        self.assertEqual(R("192.168.0.135"), ("ip", "192.168.0.135"))       # Pi-hole v domacem omrezju
        self.assertEqual(R("10.0.0.2:5353"), ("ip", "10.0.0.2:5353"))
        self.assertEqual(R("2606:4700:4700::1111"), ("ip", "2606:4700:4700::1111"))
        self.assertEqual(R("[fd00::53]:53"), ("ip", "[fd00::53]:53"))
        self.assertEqual(R("94.130.0.1"), ("ip", "94.130.0.1"))              # ni na nasem seznamu: dovoljeno
        for slabo, kljuc in (("", "doh_po_meri_prazno"), ("http://dns.example/dns-query", "doh_po_meri_https"),
                             ("169.254.169.254", "doh_po_meri_naslov"), ("0.0.0.0", "doh_po_meri_naslov"),
                             ("dns example", "doh_po_meri_oblika"), ("https://localhost/dns-query", "doh_po_meri_oblika"),
                             ("1.2.3.4:99999", "doh_po_meri_oblika")):
            with self.subTest(slabo=slabo):
                self.assertEqual(R(slabo), ("", kljuc))

    def test_navaden_ip_streznik_razresi_tudi_lokalni(self):
        streznik = StreznikDNS("192.168.0.50")
        self.addCleanup(streznik.zapri)
        r = DoHResolver("custom", "127.0.0.1:%d" % streznik.vrata)
        self.assertEqual(r.resolve("nas.example.com"), "192.168.0.50")
        self.assertEqual(streznik.vprasana, ["nas.example.com"])
        self.assertEqual(doh_proxy.preizkusi_dns("127.0.0.1:%d" % streznik.vrata), (True, "doh_po_meri_dela"))

    def test_preizkus_pove_napako(self):
        self.assertEqual(doh_proxy.preizkusi_dns("http://x"), (False, "doh_po_meri_https"))
        prost = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        prost.bind(("127.0.0.1", 0))
        vrata = prost.getsockname()[1]
        prost.close()
        self.assertEqual(doh_proxy.preizkusi_dns("127.0.0.1:%d" % vrata, timeout=0.5), (False, "doh_po_meri_ne_odgovori"))

    def test_doh_url_po_meri(self):
        zanka = LaznaZanka(lambda u, ime, q: odgovor(ime, "203.0.113.9", qtype=q))
        with okolje(zanka):
            r = DoHResolver("custom", "https://dns.nextdns.io/abc123")
            self.assertEqual(r.resolve("example.com"), "203.0.113.9")
        self.assertEqual(zanka.klici, ["https://dns.nextdns.io/abc123"])

    def test_po_meri_brez_samodejne_rezerve(self):
        zanka = LaznaZanka(lambda u, ime, q: None)
        with okolje(zanka):
            r = DoHResolver("custom", "https://dns.nextdns.io/abc123", rezerva=True)
            self.assertIsNone(r.resolve("example.com"))
        self.assertEqual(set(zanka.klici), {"https://dns.nextdns.io/abc123"})


class ScitVBrskalniku(unittest.TestCase):
    def test_blokirano_zavrne_dovoljeno_razresi_prek_cloudflare(self):
        zanka = LaznaZanka(lambda u, ime, q: odgovor(ime, "93.184.215.14", qtype=q))
        with okolje(zanka, nabor("zlo.example")):
            r = DoHResolver("scit")
            self.assertIsNone(r.resolve("cdn.zlo.example"))
            self.assertEqual(r.blokiral_scit("cdn.zlo.example"), "malware")
            self.assertEqual(r.resolve("example.com"), "93.184.215.14")
        self.assertEqual(zanka.klici, ["https://1.1.1.1/dns-query"])        # blokirano ime ni zapustilo racunalnika
        self.assertEqual(r.stevci["scit_blokiral"], 1)

    def test_naprej_usmerjevalnik_je_sistemski_dns(self):
        zanka = LaznaZanka(lambda u, ime, q: self.fail("DoH ne sme biti vprasan"))
        with okolje(zanka, nabor("zlo.example")), \
                mock.patch.object(socket, "getaddrinfo", return_value=[(socket.AF_INET, 1, 6, "", ("198.51.100.4", 443))]):
            r = DoHResolver("scit", naprej="router")
            self.assertEqual(r.resolve("example.com"), "198.51.100.4")
            self.assertIsNone(r.resolve("zlo.example"))

    def test_cloudflare_odpove_gre_na_usmerjevalnik(self):
        zanka = LaznaZanka(lambda u, ime, q: None)                  # cas potece
        with okolje(zanka, nabor()), \
                mock.patch.object(socket, "getaddrinfo", return_value=[(socket.AF_INET, 1, 6, "", ("198.51.100.4", 443))]):
            r = DoHResolver("scit", rezerva=True)
            self.assertEqual(r.resolve("example.com"), "198.51.100.4")
            self.assertEqual(r.stevci["rezerva"], 1)

    def test_tekoci_sistemski_scit_ima_prednost(self):
        """Ce sistemski Scit tece, brskalnik vprasa njega (filtrira in posreduje sam) - lastnega nabora ne potrebuje."""
        def naprej(paket):
            ime = os_scit.ime_poizvedbe(paket)
            return odgovor(ime, "192.0.2.7", ident=paket[:2]) if paket[-4:-2] == b"\x00\x01" else odgovor(ime, ident=paket[:2])
        razresevalnik = os_scit.Razresevalnik(lambda ime: "oglasi" if ime.endswith("oglas.example") else None,
                                              lambda: [], naprej)
        vrata = razresevalnik.zazeni()
        if not vrata:
            self.skipTest("vrata 5354-5357 so zasedena")
        self.addCleanup(razresevalnik.ustavi)
        self.assertIn(os_scit.tekoci_scit(), os_scit.VRATA)
        zanka = LaznaZanka(lambda u, ime, q: self.fail("DoH ne sme biti vprasan"))
        with okolje(zanka, scit_vrata=vrata), mock.patch.object(os_scit, "skupni_seznami", side_effect=AssertionError):
            r = DoHResolver("scit")
            self.assertEqual(r.resolve("example.com"), "192.0.2.7")
            self.assertIsNone(r.resolve("ads.oglas.example"))
        self.assertEqual(razresevalnik.blokiranih, 1)

    def test_iskanje_sistemskega_scita_ne_zadrzi_poizvedbe(self):
        """Na 5355 je lahko LLMNR, ki ne odgovori: preverjanje vrat tece v ozadju, poizvedba ne caka nanj."""
        import time
        konec = threading.Event()
        with mock.patch.object(doh_proxy, "_scit_vrata", (0.0, 0)), \
                mock.patch.object(os_scit, "tekoci_scit", side_effect=lambda: (konec.wait(2), 5354)[1]):
            zacetek = time.monotonic()
            self.assertEqual(doh_proxy.sistemski_scit_vrata(), 0)
            self.assertLess(time.monotonic() - zacetek, 0.2)
            konec.set()
            for _ in range(50):
                if doh_proxy._scit_vrata[1]:
                    break
                time.sleep(0.02)
            self.assertEqual(doh_proxy.sistemski_scit_vrata(), 5354)

    def test_stran_napake_pove_da_je_blokiral_scit(self):
        class R:
            def resolve(self, h):
                return None

            def blokiral_scit(self, h):
                return "phishing"
        a, b = socket.socketpair()
        self.addCleanup(b.close)
        p = doh_proxy.LocalDoHProxy(R())
        self.assertIsNone(p._pripravi_cilj(a, "zlo.example", 443))
        self.assertIn("Ščit".encode(), b.recv(65536))


class PreverjanjeVednoDela(unittest.TestCase):
    """Strani s preverjanjem (Turnstile, hCaptcha, reCAPTCHA) Scit nikoli ne blokira, tudi ce so na seznamu."""

    def test_seznami_ne_blokirajo_preverjanja(self):
        s = nabor("cloudflare.com", "challenges.cloudflare.com", "hcaptcha.com", "google.com", "gstatic.com",
                  "recaptcha.net", "zlo.example")
        for ime in ("challenges.cloudflare.com", "cloudflare.com", "www.cloudflare.com", "hcaptcha.com",
                    "newassets.hcaptcha.com", "js.hcaptcha.com", "www.google.com", "www.gstatic.com", "www.recaptcha.net"):
            with self.subTest(ime=ime):
                self.assertIsNone(s.kategorija(ime))
        self.assertEqual(s.kategorija("zlo.example"), "malware")
        self.assertEqual(s.kategorija("cloudflare.com.zlo.example"), "malware")    # ne samo po koncnici niza


class SamodejnaRezerva(unittest.TestCase):
    def _r(self, odgovori, seznami=None, ponudnik="quad9", rezerva=True):
        zanka = LaznaZanka(odgovori)
        r = DoHResolver(ponudnik, rezerva=rezerva)
        return r, zanka, okolje(zanka, seznami if seznami is not None else nabor("x.invalid"))

    @staticmethod
    def quad9(odg):
        return lambda u, ime, q: odg(ime, q) if "quad9" in u else odgovor(ime, "104.16.1.1", qtype=q)

    def test_servfail_gre_na_cloudflare(self):
        r, zanka, ok = self._r(self.quad9(lambda ime, q: odgovor(ime, rcode=2)))
        izpis = io.StringIO()
        with ok, contextlib.redirect_stdout(izpis):
            self.assertEqual(r.resolve("pokvarjen-dnssec.example"), "104.16.1.1")
        self.assertEqual(zanka.klici, ["https://dns.quad9.net/dns-query", "https://1.1.1.1/dns-query"])
        self.assertEqual(r.stevci["rezerva"], 1)
        self.assertIn("quad9 -> cloudflare", izpis.getvalue())
        self.assertNotIn("pokvarjen-dnssec", izpis.getvalue())             # dnevnik brez imen domen

    def test_cas_potece_gre_na_cloudflare(self):
        r, zanka, ok = self._r(self.quad9(lambda ime, q: None))
        with ok, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(r.resolve("example.com"), "104.16.1.1")

    def test_cloudflare_odpove_gre_na_google(self):
        r, zanka, ok = self._r(lambda u, ime, q: None if "1.1.1.1" in u else odgovor(ime, "8.8.4.4", qtype=q),
                               ponudnik="cloudflare")
        with ok, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(r.resolve("example.com"), "8.8.4.4")
        self.assertEqual(zanka.klici[-1], "https://dns.google/dns-query")

    def test_blokade_ponudnika_rezerva_ne_obide(self):
        """Pregled 18. 10. 2026: uporabnik je izbral filtrirni (druzinski) DNS - njegove blokade rezerva ne sme obiti s
        Cloudflarom; drug ponudnik samo ob pravi napaki (SERVFAIL, cas)."""
        primeri = {
            "quad9": lambda ime, q: odgovor(ime, rcode=3),                   # NXDOMAIN brez SOA
            "adguard": lambda ime, q: odgovor(ime, "0.0.0.0" if q == 1 else "::", qtype=q),
            "opendns": lambda ime, q: odgovor(ime, "146.112.61.108", qtype=q),
        }
        for ponudnik, odg in primeri.items():
            with self.subTest(ponudnik=ponudnik):
                r, zanka, ok = self._r(lambda u, ime, q, o=odg: o(ime, q) if "1.1.1.1" not in u
                                       else odgovor(ime, "104.16.1.1", qtype=q), ponudnik=ponudnik)
                with ok, contextlib.redirect_stdout(io.StringIO()):
                    self.assertIsNone(r.resolve("blokirano-pri-ponudniku.example"))
                self.assertTrue(zanka.klici and all("1.1.1.1" not in u for u in zanka.klici), zanka.klici)
                self.assertEqual(r.stevci["rezerva"], 0)

    def test_scit_naprej_blokada_ponudnika_ne_gre_v_sistemski_dns(self):
        """Splet z izbiro »Safeer Scit« in filtrirnim streznikom naprej: blokada ponudnika ostane (ne sistemski DNS);
        ob pravi napaki gre ime nesifrirano v sistemski DNS - to Splet mirno pokaze (dns_nesifriran)."""
        r = DoHResolver("scit", naprej="adguard", rezerva=True)
        zanka = LaznaZanka(lambda u, ime, q: odgovor(ime, "0.0.0.0" if q == 1 else "::", qtype=q))
        with okolje(zanka), mock.patch.object(doh_proxy, "sistemski_dns", side_effect=AssertionError("mimo filtra")), \
                mock.patch.object(doh_proxy, "_global_resolver", r):
            self.assertIsNone(r.resolve("druzinsko-blokirano.example"))
            self.assertFalse(doh_proxy.dns_nesifriran())
        r2 = DoHResolver("scit", naprej="adguard", rezerva=True)
        zanka2 = LaznaZanka(lambda u, ime, q: None)                       # DoH ne odgovori
        with okolje(zanka2), contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(doh_proxy, "sistemski_dns", return_value=doh_proxy._izid("192.0.2.9", 60, "ok")), \
                mock.patch.object(doh_proxy, "_global_resolver", r2):
            self.assertEqual(r2.resolve("example.com"), "192.0.2.9")
            self.assertTrue(doh_proxy.dns_nesifriran())

    def test_pravi_nxdomain_ni_blokada(self):
        r, zanka, ok = self._r(self.quad9(lambda ime, q: odgovor(ime, rcode=3, soa=True)))
        with ok:
            self.assertIsNone(r.resolve("ne-obstaja.example"))
        self.assertTrue(all("quad9" in u for u in zanka.klici))

    def test_scitova_blokada_ostane(self):
        r, zanka, ok = self._r(self.quad9(lambda ime, q: odgovor(ime, rcode=2)), nabor("zlo.example"))
        with ok:
            self.assertIsNone(r.resolve("zlo.example"))
        self.assertTrue(all("quad9" in u for u in zanka.klici))

    def test_brez_nabora_blokade_ponudnika_ne_obidemo(self):
        prazno = nabor()
        r, zanka, ok = self._r(self.quad9(lambda ime, q: odgovor(ime, rcode=3)), prazno)
        with ok:
            self.assertIsNone(r.resolve("morda-nevarno.example"))
        self.assertTrue(all("quad9" in u for u in zanka.klici))

    def test_rezervo_lahko_izklopi(self):
        r, zanka, ok = self._r(self.quad9(lambda ime, q: odgovor(ime, rcode=2)), rezerva=False)
        with ok:
            self.assertIsNone(r.resolve("example.com"))
        self.assertEqual(zanka.klici, ["https://dns.quad9.net/dns-query"])


class SistemskiScitNaprej(unittest.TestCase):
    class Shramba(dict):
        def set(self, k, v):
            self[k] = v

    def _scit(self, **kw):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return os_scit.Scit(self.Shramba(kw), mapa=d.name)

    def test_privzeto_cloudflare_in_izbira(self):
        s = self._scit()
        self.assertEqual(s.naprej(), ("cloudflare", ""))
        with mock.patch.object(os_scit, "izprazni_predpomnilnik"), mock.patch.object(os_scit, "pravilo_namesceno", return_value=False):
            for izbira in ("quad9", "google", "adguard", "opendns", "router"):
                s.nastavi_naprej(izbira)
                self.assertEqual(s.naprej()[0], izbira)
            st = s.nastavi_naprej("custom", "192.168.0.135")
            self.assertEqual((st["naprej"], st["naprejPoMeri"], st["napaka"]), ("custom", "192.168.0.135", ""))
            self.assertEqual(s.nastavi_naprej("custom", "127.0.0.1:5354")["napaka"], "naprej_zanka")   # sam sebi ne
            self.assertEqual(s.nastavi_naprej("custom", "http://x")["napaka"], "naprej")
            self.assertEqual(s.naprej(), ("custom", "192.168.0.135"))

    def test_usmerjevalnik_ne_klice_doh(self):
        s = self._scit(scit_naprej="router")
        with mock.patch.object(doh_proxy, "posreduj_paket", side_effect=AssertionError):
            self.assertIsNone(s._naprej(b"\x12\x34" + b"\x00" * 20))

    def test_posreduj_paket_vrne_izvirni_id_servfail_je_rezerva(self):
        paket = b"\xab\xcd" + DoHResolver._build_dns_wire_query("example.com")[2:]
        poslano = []

        def poslji(_self, ponudnik, url, telo, timeout):
            poslano.append((url, telo[:2]))
            return 200, "application/dns-message", odgovor("example.com", "104.16.1.1")
        with mock.patch.object(DoHResolver, "_poslji_doh", poslji):
            o = doh_proxy.posreduj_paket("cloudflare", "", paket, 1.0)
        self.assertEqual(o[:2], b"\xab\xcd")
        self.assertEqual(poslano, [("https://1.1.1.1/dns-query", b"\x00\x00")])     # DoH: ID 0 (RFC 8484)
        with mock.patch.object(DoHResolver, "_poslji_doh",
                               lambda *a: (200, "application/dns-message", odgovor("example.com", rcode=2))):
            self.assertIsNone(doh_proxy.posreduj_paket("quad9", "", paket, 1.0))          # SERVFAIL: usmerjevalnik
        # Blokada filtrirnega ponudnika ni napaka: Scit odgovori NXDOMAIN (ne vprasa usmerjevalnika, pregled 18. 10.).
        for ponudnik, slab in (("quad9", odgovor("example.com", rcode=3)), ("adguard", odgovor("example.com", "0.0.0.0")),
                               ("custom", odgovor("example.com", "0.0.0.0"))):
            with mock.patch.object(DoHResolver, "_poslji_doh", lambda *a, s=slab: (200, "application/dns-message", s)):
                o = doh_proxy.posreduj_paket(ponudnik, "https://druzina.example/dns-query", paket, 1.0)
            self.assertIsNotNone(o, ponudnik)
            self.assertEqual((o[:2], o[3] & 0x0F, o[6:8]), (b"\xab\xcd", 3, b"\x00\x00"), ponudnik)
        with mock.patch.object(DoHResolver, "_poslji_doh",
                               lambda *a: (200, "application/dns-message", odgovor("example.com", rcode=3))):
            self.assertIsNotNone(doh_proxy.posreduj_paket("cloudflare", "", paket, 1.0))  # Cloudflare ne blokira

    def test_razresevalnik_ob_odpovedi_vprasa_usmerjevalnik(self):
        r = os_scit.Razresevalnik(lambda ime: None, lambda: [], lambda paket: None)
        self.assertIsNone(r._posreduj(b"\x00" * 30, False))
        self.assertEqual(r.rezerv, 1)
        velik = os_scit.Razresevalnik(lambda ime: None, lambda: [], lambda paket: paket[:2] + b"\x81\x80" + b"\x00" * 2000)
        paket = b"\x55\x66" + DoHResolver._build_dns_wire_query("example.com")[2:]
        prirezan = velik._posreduj(paket, False)
        self.assertTrue(prirezan[2] & 0x02)                              # TC: odjemalec vprasa prek TCP
        self.assertEqual(len(velik._posreduj(paket, True)), 2004)

    def test_opis_pove_kdo_vidi_poizvedbe(self):
        vir = Path(os_scit.__file__).read_text(encoding="utf-8")
        self.assertNotIn("Nic ne gre v oblak, noben tuj streznik ne vidi poizvedb", vir)
        self.assertIn("Cloudflare pa\nvidi dovoljena imena", vir)
        js = (Path(os_scit.__file__).parents[1] / "assets" / "os" / "besedila.js").read_text(encoding="utf-8")
        self.assertNotIn("nič ne gre v oblak.", js)
        self.assertEqual(js.count("scitKdo_ponudnik:"), 6)


if __name__ == "__main__":
    unittest.main()
