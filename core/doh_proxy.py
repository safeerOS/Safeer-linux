#!/usr/bin/env python3
"""
Safeer Browser for Linux Mint - DNS-over-HTTPS (DoH) & Encrypted Proxy Engine
Encrypted DNS with HTTP/2 support and bounded local HTTP/CONNECT and SOCKS5 tunneling.
Public target lookups fail closed; resolver endpoint bootstrap uses the system DNS.
The local proxy only ever connects outwards to public addresses, never to the Fetch
bad-port list: loopback, private, link-local (including cloud metadata) and reserved
ranges are refused.
"""

import socket
import select
import threading
import time
import urllib.parse
import ipaddress
import gi
gi.require_version("Soup", "3.0")
from gi.repository import Soup, Gio, GLib
from typing import Dict, Tuple, Optional, List

# Znani zanesljivi DoH ponudniki
DOH_PROVIDERS = {
    "quad9": {
        "name": "Quad9 Secure DNS (9.9.9.9)",
        "url": "https://dns.quad9.net/dns-query",
        "fallback_ip": "9.9.9.9"
    },
    "adguard": {
        "name": "AdGuard DNS (dns.adguard-dns.com)",
        "url": "https://dns.adguard-dns.com/dns-query",
        "fallback_ip": "94.140.14.14"
    },
    "cloudflare": {
        "name": "Cloudflare DNS (1.1.1.1)",
        "url": "https://1.1.1.1/dns-query",
        "fallback_ip": "1.1.1.1"
    },
    "google": {
        "name": "Google Public DNS (8.8.8.8)",
        "url": "https://dns.google/dns-query",
        "fallback_ip": "8.8.8.8"
    }
}

# Vrata, na katera lokalni posrednik nikoli ne vzpostavi povezave.
# Seznam sledi seznamu "bad ports" iz standarda Fetch -- enako delajo brskalniki --
# in mu doda strezniske baze in predpomnilnike, ki jih brskanje nikoli ne potrebuje.
# Vsa druga vrata so dovoljena, da strani na nestandardnih vratih delujejo naprej.
PREPOVEDANA_VRATA = frozenset({
    1, 7, 9, 11, 13, 15, 17, 19, 20, 21, 22, 23, 25, 37, 42, 43, 53, 69, 77, 79,
    87, 95, 101, 102, 103, 104, 109, 110, 111, 113, 115, 117, 119, 123, 135, 137,
    139, 143, 161, 179, 389, 427, 465, 512, 513, 514, 515, 526, 530, 531, 532,
    540, 548, 554, 556, 563, 587, 601, 636, 989, 990, 993, 995, 1719, 1720, 1723,
    2049, 3659, 4045, 4190, 5060, 5061, 6000, 6566, 6665, 6666, 6667, 6668, 6669,
    6679, 6697, 10080,
    # baze, predpomnilniki in iskalniki
    1433, 1521, 3306, 5432, 5984, 6379, 9042, 9200, 11211, 27017, 27018,
})

# Obsegi, ki niso javni internet in jih posrednik nikoli ne sme doseči.
# ipaddress.is_private pokriva 10/8, 172.16/12, 192.168/16, 100.64/10 (CGNAT),
# 0.0.0.0/8 in podobno; povratne, povezavno-lokalne (tudi 169.254.169.254),
# večvrstne in rezervirane naslove pokrijemo posebej.
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def je_javni_naslov(naslov: str) -> bool:
    """
    True samo za naslove na javnem internetu.
    Zavrne povratne, zasebne, povezavno-lokalne (metapodatki oblaka),
    CGNAT, večvrstne, rezervirane in nedoločene naslove.
    """
    if not naslov:
        return False
    try:
        ip = ipaddress.ip_address(naslov.strip().strip("[]"))
    except ValueError:
        return False

    # IPv6, ki v resnici nosi IPv4 naslov, presodimo po tem IPv4 naslovu.
    if ip.version == 6:
        mapped = getattr(ip, "ipv4_mapped", None)
        if mapped is not None:
            ip = mapped
        else:
            sixtofour = getattr(ip, "sixtofour", None)
            if sixtofour is not None:
                ip = sixtofour

    if (ip.is_loopback or ip.is_private or ip.is_link_local
            or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
        return False
    if ip.version == 4 and ip in _CGNAT:
        return False
    return True


#: Domace omrezje, ki ga uporabnik lahko izrecno dovoli (stikalo »dovoli lokalno omrezje«). Povratni, povezavno-lokalni
#: (metapodatki oblaka), vecvrstni, rezervirani in nedolocen naslov NISO med njimi in ostanejo zavrnjeni.
_DOMACE_MREZE = tuple(ipaddress.ip_network(n) for n in
                      ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "fc00::/7"))


def je_dovoljen_cilj(naslov: str, dovoli_lokalno: bool = False) -> bool:
    """Javni naslov, ali (le ce je uporabnik dovolil lokalno omrezje) naslov v domacem omrezju.

    Ime, ki ga javni razreševalnik prevede v domaci naslov, je sicer znak napada (DNS rebinding); pri lastnem DoH
    (Pi-hole, usmerjevalnik) pa je to pricakovano - zato izrecno stikalo, privzeto izklopljeno."""
    if je_javni_naslov(naslov):
        return True
    if not dovoli_lokalno:
        return False
    try:
        ip = ipaddress.ip_address(str(naslov).strip().strip("[]"))
    except ValueError:
        return False
    if ip.version == 6 and getattr(ip, "ipv4_mapped", None) is not None:
        ip = ip.ipv4_mapped
    return any(ip.version == n.version and ip in n for n in _DOMACE_MREZE)


#: Imena, ki jih javni DNS ne pozna in vodijo v notranja omrezja (tudi metapodatki oblaka).
NOTRANJA_IMENA = ("localhost", ".localhost", ".local", ".internal", ".home.arpa", ".lan")


def je_dovoljen_doh_streznik(gostitelj: str) -> bool:
    """Ali sme uporabnikov lastni DoH streznik biti na tem naslovu.

    Domace omrezje je dovoljeno (Pi-hole ali AdGuard Home na usmerjevalniku), povratni,
    povezavno-lokalni (metapodatki oblaka, 169.254.169.254) in posebni naslovi pa ne:
    nastavitev ne sme postati pot do storitev, ki jih brskalnik sicer nikoli ne doseze."""
    g = str(gostitelj or "").strip().strip("[]").rstrip(".").lower()
    if not g:
        return False
    try:
        ip = ipaddress.ip_address(g)
    except ValueError:
        return not (g == "localhost" or g.endswith(NOTRANJA_IMENA))
    if ip.version == 6 and getattr(ip, "ipv4_mapped", None) is not None:
        ip = ip.ipv4_mapped
    return not (ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified)


def je_dovoljena_vrata(vrata: int) -> bool:
    """True za vsa vrata, ki jih brskanje potrebuje; nevarna so zavrnjena."""
    try:
        v = int(vrata)
    except (TypeError, ValueError):
        return False
    return 0 < v <= 65535 and v not in PREPOVEDANA_VRATA


class DoHResolver:
    """
    Kriptografski razreševalnik DNS-over-HTTPS z lokalnim predpomnilnikom (In-Memory TTL Cache).
    Poizvedbe pošilja prek šifriranega TLS protokola neposredno na DoH strežnike.
    """

    def __init__(self, provider: str = "cloudflare", custom_url: str = ""):
        self.provider = provider if (provider in DOH_PROVIDERS or provider == "custom") else "cloudflare"
        self.custom_url = custom_url.strip()
        # Predpomnilnik: hostname -> (ip_address, expire_timestamp)
        self._cache: Dict[str, Tuple[str, float]] = {}
        self._lock = threading.Lock()
        self._pending = {}

    def set_provider(self, provider: str, custom_url: str = ""):
        with self._lock:
            c_url = custom_url.strip()
            if (provider in DOH_PROVIDERS or provider == "custom") and (provider != self.provider or c_url != self.custom_url):
                self.provider = provider
                self.custom_url = c_url
                self._cache.clear()
                self._rezerva_do = 0.0

    def resolve(self, hostname: str, timeout: float = 3.5) -> Optional[str]:
        """
        Razreši domeno v IPv4 naslov prek DoH.
        Vrne IPv4 niz ali None, če poizvedba ne uspe.
        """
        if not hostname:
            return None

        h = hostname.lower().strip().rstrip(".")
        try:
            return str(ipaddress.ip_address(h))
        except ValueError:
            pass
        try:
            h = h.encode("idna").decode("ascii")
            if len(h) > 253 or any(not label or len(label) > 63 for label in h.split(".")):
                return None
        except UnicodeError:
            return None

        # Če je že IPv4 naslov
        parts = h.split(".")
        if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            return h

        now = time.time()

        # 1. Preveri predpomnilnik. Pretecen zapis (do STARO_S) vrnemo takoj in ga osvezimo v ozadju (RFC 8767,
        #    "serve stale"): stran ne caka na DoH zaradi kratkih TTL-jev CDN-jev. Ce stari naslov ne deluje vec,
        #    posrednik ime pozabi in ga razresi znova (LocalDoHProxy._povezi_z_osvezitvijo).
        staro = None
        with self._lock:
            cached = self._cache.get(h)
            if cached:
                ip, exp = cached
                if now < exp:
                    return ip
                if ip and now < exp + self.STARO_S:
                    staro = ip
                else:
                    del self._cache[h]
        if staro:
            self._osvezi_v_ozadju(h, timeout)
            return staro

        # Coalesce requests for one host and never fall back to plaintext DNS.
        with self._lock:
            generation = (self.provider, self.custom_url)
            key = (generation, h)
            event = self._pending.get(key)
            owner = event is None
            if owner:
                event = threading.Event()
                self._pending[key] = event
        if not owner:
            event.wait(timeout + 1)
            with self._lock:
                entry = self._cache.get(h)
                return entry[0] if entry and entry[1] > time.time() else None
        try:
            try:
                ip, ttl = self._query_doh(h, timeout)
            except Exception:  # noqa: BLE001 - kot neuspela poizvedba
                ip, ttl = None, 15
            with self._lock:
                if generation == (self.provider, self.custom_url):
                    self._cache[h] = (ip, time.time() + (max(1, min(ttl, 3600)) if ip else 15))
            return ip
        finally:
            with self._lock:
                self._pending.pop(key, None)
                event.set()

    #: Kako dolgo po izteku TTL se sme uporabiti star naslov (medtem ko se osvezuje v ozadju).
    STARO_S = 3600

    def ogrej(self) -> None:
        """Odpre (ali ohrani) povezavo do streznika DoH z vprasanjem po imenu samega streznika - nic ne izda."""
        try:
            if self.provider == "custom":
                gostitelj = urllib.parse.urlsplit(self.custom_url).hostname or ""
            else:
                gostitelj = urllib.parse.urlsplit(DOH_PROVIDERS.get(self.provider, DOH_PROVIDERS["cloudflare"])["url"]).hostname or ""
            try:
                ipaddress.ip_address(gostitelj)
                gostitelj = "example.com"      # streznik z IP naslovom: nevtralno ime (IANA, nic ne izda)
            except ValueError:
                pass
            if gostitelj:
                self._poizvedba(gostitelj, 3.5, 1)
        except Exception:  # noqa: BLE001
            pass

    def pozabi(self, hostname: str) -> None:
        """Pozabi naslov imena (npr. star naslov ne sprejme povezave): naslednji resolve vpraša DoH znova."""
        h = (hostname or "").lower().strip().rstrip(".")
        with self._lock:
            self._cache.pop(h, None)

    def _osvezi_v_ozadju(self, h: str, timeout: float) -> None:
        with self._lock:
            generation = (self.provider, self.custom_url)
            key = (generation, h)
            if key in self._pending:
                return
            event = threading.Event()
            self._pending[key] = event

        def osvezi() -> None:
            try:
                ip, ttl = self._query_doh(h, timeout)
                with self._lock:
                    # Neuspela osvezitev ne izbrise delujocega starega naslova.
                    if ip and generation == (self.provider, self.custom_url):
                        self._cache[h] = (ip, time.time() + max(1, min(ttl, 3600)))
            except Exception:  # noqa: BLE001
                pass
            finally:
                with self._lock:
                    self._pending.pop(key, None)
                event.set()

        threading.Thread(target=osvezi, name="safeer-doh-osvezi", daemon=True).start()

    @staticmethod
    def _build_dns_wire_query(hostname: str, qtype: int = 1) -> bytes:
        """Poizvedba tipa A (qtype 1) ali AAAA (28). ID je 0, kot priporoca RFC 8484 (DoH), odgovor pa preverimo po imenu.

        Ime mora biti ze v obliki ASCII (IDNA, "xn--"): cesar ni mogoce zapisati, zavrnemo (ValueError),
        namesto da bi tiho izpustili znake in vprasali za drugo ime."""
        return b"\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + DoHResolver._ime_v_zapis(hostname) + qtype.to_bytes(2, "big") + b"\x00\x01"

    @staticmethod
    def _ime_v_zapis(hostname: str) -> bytes:
        oznake = str(hostname or "").strip().rstrip(".").split(".")
        zapis = bytearray()
        for oznaka in oznake:
            b = oznaka.encode("ascii")  # UnicodeEncodeError je ValueError
            if not b or len(b) > 63:
                raise ValueError("neveljavno ime")
            zapis.append(len(b))
            zapis.extend(b)
        zapis.append(0)
        if len(zapis) > 255:
            raise ValueError("predolgo ime")
        return bytes(zapis)

    @staticmethod
    def _preberi_ime(data: bytes, idx: int) -> Tuple[bytes, int]:
        """Ime v sporocilu DNS po RFC 1035 4.1.4: oznake in kazalci, tudi kazalec sredi imena (»www« + kazalec).

        Vrne (ime z malimi crkami, oznake locene s piko; indeks takoj za imenom na mestu zapisa). Zanka kazalcev, kazalec
        izven sporocila, rezervirana oznaka ali ime, daljse od 255 bajtov, je napaka (ValueError)."""
        oznake = []
        konec = -1
        skokov = 0
        dolzina = 1
        while True:
            if idx >= len(data):
                raise ValueError("ime presega sporocilo")
            n = data[idx]
            if n == 0:
                idx += 1
                break
            if n & 0xC0 == 0xC0:
                if idx + 1 >= len(data):
                    raise ValueError("kazalec presega sporocilo")
                if konec < 0:
                    konec = idx + 2
                skokov += 1
                kazalec = ((n & 0x3F) << 8) | data[idx + 1]
                if skokov > 32 or kazalec >= len(data):
                    raise ValueError("zanka ali kazalec izven sporocila")
                idx = kazalec
                continue
            if n & 0xC0:
                raise ValueError("rezervirana oblika oznake")
            if idx + 1 + n > len(data):
                raise ValueError("oznaka presega sporocilo")
            dolzina += n + 1
            if dolzina > 255:
                raise ValueError("predolgo ime")
            oznake.append(bytes(data[idx + 1:idx + 1 + n]).lower())
            idx += 1 + n
        return b".".join(oznake), (konec if konec >= 0 else idx)

    @staticmethod
    def _parse_dns_wire_response(data: bytes, hostname: str, qtype: int = 1) -> Tuple[Optional[str], int]:
        """IPv4 (qtype 1) ali IPv6 (qtype 28) naslov iz odgovora - samo ce je odgovor res na nase vprasanje (ID 0, isto ime, tip A/AAAA) in samo iz zapisa A,
        katerega lastnik je vprasano ime ali ime v verigi CNAME od njega naprej (zunanji pregled kode 8. 10. 2026: prej je
        vrnil prvi zapis A ne glede na lastnika, kazalec sredi imena pa je odgovor podrl)."""
        if len(data) < 12 or not data[2] & 0x80 or data[2] & 0x02 or data[3] & 0x0f:
            return None, 300
        try:
            vprasanje = DoHResolver._ime_v_zapis(hostname) + qtype.to_bytes(2, "big") + b"\x00\x01"
        except ValueError:
            return None, 300
        # Odgovor mora ponoviti nase vprasanje: en vnos, isto ime (velikost crk ni pomembna), tip A.
        if (data[0:2] != b"\x00\x00" or int.from_bytes(data[4:6], "big") != 1
                or data[12:12 + len(vprasanje)].lower() != vprasanje.lower()):
            return None, 300
        ime = str(hostname).strip().rstrip(".").lower().encode("ascii")
        try:
            ancount = int.from_bytes(data[6:8], "big")
            idx = 12 + len(vprasanje)
            naslovi = {}   # lastnik -> (ip, ttl), prvi zapis A za lastnika
            cname = {}     # lastnik -> (cilj, ttl)
            for _ in range(ancount):
                lastnik, idx = DoHResolver._preberi_ime(data, idx)
                if idx + 10 > len(data):
                    return None, 300
                rtype = int.from_bytes(data[idx:idx + 2], "big")
                rclass = int.from_bytes(data[idx + 2:idx + 4], "big")
                ttl = int.from_bytes(data[idx + 4:idx + 8], "big")
                rdlength = int.from_bytes(data[idx + 8:idx + 10], "big")
                idx += 10
                if idx + rdlength > len(data):
                    return None, 300
                if rclass == 1 and rtype == 1 and rdlength == 4 and qtype == 1:
                    naslovi.setdefault(lastnik, (".".join(str(b) for b in data[idx:idx + 4]), ttl))
                elif rclass == 1 and rtype == 28 and rdlength == 16 and qtype == 28:
                    naslovi.setdefault(lastnik, (str(ipaddress.IPv6Address(bytes(data[idx:idx + 16]))), ttl))
                elif rclass == 1 and rtype == 5:
                    cilj, _ = DoHResolver._preberi_ime(data, idx)
                    cname.setdefault(lastnik, (cilj, ttl))
                idx += rdlength
            # Veriga od vprasanega imena: najvec 8 CNAME, TTL najkrajsi v verigi.
            trenutno, najmanj = ime, None
            for _ in range(9):
                if trenutno in naslovi:
                    ip, ttl = naslovi[trenutno]
                    return ip, ttl if najmanj is None else min(ttl, najmanj)
                if trenutno not in cname:
                    break
                trenutno, ttl = cname[trenutno]
                najmanj = ttl if najmanj is None else min(ttl, najmanj)
        except (ValueError, IndexError):
            pass
        return None, 300

    def _query_doh(self, hostname: str, timeout: float) -> Tuple[Optional[str], int]:
        """Najprej A. Samo ce je strezniku uspelo odgovoriti in zapisa A ni (ttl != 15: ne gre za napako prenosa), vprasamo se
        za AAAA: strani samo z IPv6 se tako odprejo, namesto da bi padle s tihim 502."""
        ip, ttl = self._poizvedba(hostname, timeout, 1)
        if ip or ttl == 15:
            return ip, ttl
        ip6, ttl6 = self._poizvedba(hostname, timeout, 28)
        return (ip6, ttl6) if ip6 else (None, ttl)

    def _poizvedba(self, hostname: str, timeout: float, qtype: int = 1) -> Tuple[Optional[str], int]:
        if self.provider == "custom":
            base_url = self.custom_url
        else:
            provider_info = DOH_PROVIDERS.get(self.provider, DOH_PROVIDERS["cloudflare"])
            base_url = provider_info["url"]

        # libsoup 3 negotiates HTTP/2 (required by Quad9). It is already used by
        # WebKitGTK; keep normal certificate validation and bypass proxy recursion.
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None, 15
        if self.provider == "custom" and not je_dovoljen_doh_streznik(parsed.hostname):
            return None, 15
        rezerva = "" if self.provider == "custom" else DOH_PROVIDERS.get(self.provider, {}).get("fallback_ip", "")
        if rezerva == parsed.hostname:
            rezerva = ""
        try:
            telo = self._build_dns_wire_query(hostname, qtype)
            odgovor = None
            if not (rezerva and time.time() < self._rezerva_do):
                try:
                    odgovor = _zanka_doh().poslji(base_url, telo, timeout)
                except ImeNiRazreseno:
                    if not rezerva:
                        return None, 15
                    self._rezerva_do = time.time() + self.REZERVA_S
            if odgovor is None and rezerva and time.time() < self._rezerva_do:
                odgovor = self._poslji_na_rezervo(base_url, parsed, rezerva, telo, timeout)
            if odgovor is None:
                return None, 15
            status, vrsta, data = odgovor
            if status != 200 or vrsta != "application/dns-message" or len(data) > 65535:
                return None, 15
            return self._parse_dns_wire_response(data, hostname, qtype)
        except Exception:
            return None, 15

    #: Kako dolgo po neuspeli razresitvi imena ponudnika gremo naravnost na fallback_ip (brez novega cakanja na DNS).
    REZERVA_S = 60
    _rezerva_do = 0.0

    @staticmethod
    def _poslji_na_rezervo(base_url: str, parsed, rezerva: str, telo: bytes, timeout: float):
        """Sistemski DNS ne razresi imena ponudnika (npr. dns.quad9.net): poizvedba gre na njegov stalni naslov IP.

        libsoup 3 ne zna povezati na izbran IP in hkrati poslati SNI/Host z imenom (identiteta TLS je vedno gostitelj
        iz URL-ja; ponarejen Gio.Resolver bi veljal za ves proces). Zato gre poizvedba na https://<IP>/..., kjer libsoup
        potrdilo preveri obicajno (veriga in IP v SAN; preverjeno 16. 10. 2026: Quad9, AdGuard, Google imajo IP v SAN),
        odgovor pa sprejmemo samo, ce isto potrdilo velja tudi za ime ponudnika. HTTP/2 ostane (Quad9 HTTP/1.1 zavrne s 505)."""
        url = urllib.parse.urlunsplit((parsed.scheme, rezerva + (f":{parsed.port}" if parsed.port else ""),
                                       parsed.path, parsed.query, ""))
        try:
            return _zanka_doh().poslji(url, telo, timeout, ime_potrdila=parsed.hostname)
        except ImeNiRazreseno:
            return None


class ImeNiRazreseno(Exception):
    """Sistemski DNS ni razresil imena streznika DoH (Gio.ResolverError): smiselna je rezerva na fallback_ip."""


class _ZankaDoH:
    """Ena seja libsoup na lastni niti z zanko GLib: vse poizvedbe DoH gredo po eni topli povezavi HTTP/2
    (vzporedne poizvedbe so prepletene na njej). Meritev 13. 10. 2026: ime ~40 ms (prej ~120 ms: vsaka povezava
    brskalnika je odprla svojo sejo in svoj TLS), 20 hkratnih imen v ~95 ms.

    libsoup 3 sejo veze na nit/kontekst, v katerem je nastala, zato jo uporabljamo samo iz te niti."""

    def __init__(self) -> None:
        self._kontekst = GLib.MainContext.new()
        self._seja = None
        pripravljena = threading.Event()

        def tek() -> None:
            self._kontekst.push_thread_default()
            seja = Soup.Session()
            # Brez posrednika (sicer bi DoH sel skozi nas posrednik); obicajno preverjanje potrdil ostane.
            seja.set_proxy_resolver(Gio.SimpleProxyResolver.new(None, []))
            # libsoup privzeto zapre mirujoco povezavo po 60 s; streznik (Cloudflare) jo drzi vsaj 2 min.
            seja.set_idle_timeout(240)
            self._seja = seja
            pripravljena.set()
            GLib.MainLoop.new(self._kontekst, False).run()

        threading.Thread(target=tek, name="safeer-doh", daemon=True).start()
        pripravljena.wait(5)

    def poslji(self, url: str, telo: bytes, timeout: float, ime_potrdila: str = "") -> Optional[Tuple[int, str, bytes]]:
        """POST application/dns-message; vrne (status, vrsta vsebine, telo) ali None (napaka, cas potekel).

        ime_potrdila: odgovor velja samo, ce potrdilo streznika velja tudi za to ime (rezerva na naslov IP).
        Ce ime streznika ni razreseno, sprozi ImeNiRazreseno."""
        if self._seja is None:
            return None
        konec = threading.Event()
        izid: dict = {}
        preklic = Gio.Cancellable()

        def zacni(*_a) -> bool:
            try:
                sporocilo = Soup.Message.new("POST", url)
                # IDEMPOTENT: poizvedba DNS je varna za ponovitev, zato libsoup sme uporabiti obstojeco povezavo
                # (za POST brez te zastavice odpre novo TCP + TLS povezavo za vsako poizvedbo).
                sporocilo.set_flags(Soup.MessageFlags.NO_REDIRECT | Soup.MessageFlags.IDEMPOTENT)
                sporocilo.set_request_body_from_bytes("application/dns-message", GLib.Bytes.new(telo))
                sporocilo.get_request_headers().append("Accept", "application/dns-message")

                def koncano(seja, rezultat, *_b) -> None:
                    try:
                        podatki = seja.send_and_read_finish(rezultat)
                        if ime_potrdila and not _potrdilo_velja_za(sporocilo.get_tls_peer_certificate(), ime_potrdila):
                            konec.set()
                            return
                        vrsta = sporocilo.get_response_headers().get_content_type()[0] or ""
                        izid["o"] = (int(sporocilo.get_status()), vrsta, bytes(podatki.get_data() or b""))
                    except GLib.Error as napaka:
                        izid["ime"] = napaka.domain == "g-resolver-error-quark"
                    except Exception:  # noqa: BLE001
                        pass
                    konec.set()

                self._seja.send_and_read_async(sporocilo, GLib.PRIORITY_DEFAULT, preklic, koncano)
            except Exception:  # noqa: BLE001
                konec.set()
            return False

        vir = GLib.idle_source_new()
        vir.set_callback(zacni)
        vir.attach(self._kontekst)
        if not konec.wait(max(0.5, timeout)):
            preklic.cancel()
            return None
        if izid.get("ime"):
            raise ImeNiRazreseno(url)
        return izid.get("o")


def _potrdilo_velja_za(potrdilo, ime: str) -> bool:
    """Potrdilo (ze preverjeno za naslov IP) velja tudi za ime ponudnika. Veriga je preverjena ob rokovanju, tu samo
    identiteta: brez potrdila ali z BAD_IDENTITY odgovora ne sprejmemo."""
    if potrdilo is None:
        return False
    try:
        zastavice = potrdilo.verify(Gio.NetworkAddress.new(ime, 443), None)
    except Exception:  # noqa: BLE001
        return False
    return not (zastavice & Gio.TlsCertificateFlags.BAD_IDENTITY)


_zanka: Optional[_ZankaDoH] = None
_zanka_zaklep = threading.Lock()


def _zanka_doh() -> _ZankaDoH:
    global _zanka
    with _zanka_zaklep:
        if _zanka is None:
            _zanka = _ZankaDoH()
        return _zanka

#: Najvec hkratnih tunelov (vsak je nit; nit miruje v select, dokler ni podatkov).
NAJVEC_POVEZAV = 256


def _brez_zamika(vticnica: socket.socket) -> None:
    """TCP_NODELAY: posrednik majhnih zapisov TLS (rokovanje, glave HTTP/2) ne zadrzuje (Nagle + zakasnjen ACK)."""
    try:
        vticnica.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception:   # noqa: BLE001 - ni vticnica TCP (preizkus) ali je ze zaprta
        pass


def _preberi_tocno(vticnica: socket.socket, n: int) -> bytes:
    """Prebere natanko n bajtov (SOCKS5 pozdrav in zahteva); ob prekinjeni povezavi vrze OSError."""
    podatki = b""
    while len(podatki) < n:
        kos = vticnica.recv(n - len(podatki))
        if not kos:
            raise OSError("povezava prekinjena")
        podatki += kos
    return podatki


# Odgovori SOCKS5 (RFC 1928): 0 uspeh, 2 ni dovoljeno, 4 gostitelj nedosegljiv, 5 povezava zavrnjena,
# 7 ukaz ni podprt, 8 vrsta naslova ni podprta.
def _socks5_odgovor(koda: int) -> bytes:
    return bytes([5, koda, 0, 1, 0, 0, 0, 0, 0, 0])


def socks_ima_http2() -> bool:
    """Ali libsoup prek posrednika SOCKS5 govori HTTP/2.

    libsoup HTTP/2 izklopi za vsak posrednik "http" (soup-connection.c, is_not_using_http_proxy), za SOCKS5
    pa ne. Izmerjeno 13. 10. 2026: libsoup 3.6.6 (Flatpak GNOME 50) prek SOCKS5 http-2-0, libsoup 3.4.4 (Mint)
    ostane pri HTTP/1.1. Zato SOCKS5 uporabimo samo od 3.6 naprej; starejsi ostane pri preizkusenem HTTP CONNECT.
    """
    try:
        return (Soup.get_major_version(), Soup.get_minor_version()) >= (3, 6)
    except Exception:  # noqa: BLE001
        return False


def nastavitve_posrednika(WebKit, vrata: int, izjeme: List[str]):
    """NetworkProxySettings za lokalni DoH posrednik.

    Privzeto http://127.0.0.1:vrata (navaden HTTP dobi razumljive strani napak). Kjer libsoup prek SOCKS5 zna
    HTTP/2, gre https skozi socks5:// na istih vratih: brez tega je bil github.com hladno 1171 ms namesto 600 ms
    (HTTP/1.1 namesto HTTP/2). GLib ime poslje posredniku (SOCKS5 vrsta 3), zato DNS se vedno tece prek DoH.
    """
    p = WebKit.NetworkProxySettings.new("http://127.0.0.1:%d" % vrata, izjeme)
    if socks_ima_http2():
        p.add_proxy_for_scheme("https", "socks5://127.0.0.1:%d" % vrata)
    return p


class LocalDoHProxy:
    """
    Visoko-zmogljiv lokalni posredniški strežnik (Loopback CONNECT Proxy).
    Prestreza omrežne zahteve brskalnika WebKit2 ter razrešuje vsa imena gostiteljev
    prek DoH brez puščanja DNS podatkov lokalnemu ponudniku interneta.
    Posreduje samo na javne naslove in nikoli na nevarna vrata (SSH, SMTP, baze);
    povezav v lokalno omrežje, na povratni naslov ali na metapodatkovne naslove
    oblaka ne vzpostavi.
    """

    def __init__(self, resolver: DoHResolver, bind_host: str = "127.0.0.1", port: int = 0, dovoli_lokalno: bool = False):
        self.resolver = resolver
        self.dovoli_lokalno = bool(dovoli_lokalno)
        self.bind_host = bind_host
        self.requested_port = port
        self.actual_port = 0
        self.is_running = False
        self._server_sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        # Brskalnik drzi odprte povezave HTTP/2 in jih odpre vec na stran (novicarske strani: deset in vec gostiteljev).
        # S 64 je bil posrednik na velikih straneh poln in je nove povezave zavrnil (slike so cakale).
        self._slots = threading.BoundedSemaphore(NAJVEC_POVEZAV)
        self.zavrnjenih = 0
        self._sockets = set()
        self._socket_lock = threading.Lock()

    def start(self) -> int:
        """Zažene posrednika v ločeni niti in vrne dodeljena lokalna vrata."""
        if self.is_running:
            return self.actual_port

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.bind_host, self.requested_port))
        self.actual_port = self._server_sock.getsockname()[1]
        self._server_sock.listen(128)
        self._server_sock.settimeout(1.0)

        self.is_running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True, name="SafeerDoHProxy")
        self._thread.start()
        # Povezavo do streznika DoH odpremo takoj (TCP + TLS ~110 ms), da je prva stran ne caka: meritev 13. 10. 2026,
        # 25 novih imen hkrati s toplo povezavo ~175 ms, s hladno ~330 ms.
        ogrej = getattr(self.resolver, "ogrej", None)
        if callable(ogrej):
            threading.Thread(target=ogrej, daemon=True, name="safeer-doh-ogrej").start()

        print(f"[DoH Proxy] Lokalni posrednik aktiviran na http://{self.bind_host}:{self.actual_port} (DoH: {self.resolver.provider})")
        return self.actual_port

    def stop(self):
        """Varno ustavi posredniški strežnik."""
        self.is_running = False
        with self._socket_lock:
            for sock in list(self._sockets):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                sock.close()
            self._sockets.clear()
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

    def _accept_loop(self):
        while self.is_running:
            try:
                client_sock, _ = self._server_sock.accept()
                if not self._slots.acquire(blocking=False):
                    self.zavrnjenih += 1
                    client_sock.close()
                    continue
                _brez_zamika(client_sock)
                with self._socket_lock:
                    self._sockets.add(client_sock)
                t = threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True)
                t.start()
            except Exception:
                if not self.is_running:
                    break

    @staticmethod
    def _zavrni(client_sock: socket.socket, sporocilo: bytes):
        """Odgovori s 403 in zapre povezavo (cilj je zunaj dovoljenega obsega)."""
        try:
            client_sock.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n" + sporocilo)
        except Exception:
            pass
        try:
            client_sock.close()
        except Exception:
            pass

    @staticmethod
    def _napaka_502(client_sock: socket.socket, besedilo: str):
        """Razumljiv odgovor namesto praznega 502 (besedilo je ASCII, brez vsebine iz zahtevka)."""
        # Stran v barvah Safeerja namesto golega besedila (preizkus 14. 10. 2026: http:// naslov brez DNS je pokazal
        # vrstico »Safeer: ...« v pisavi terminala). Besedilo je nase (brez vsebine iz zahtevka), CSP brez skript.
        import html as _html
        deli = [_html.escape(d.strip()) for d in besedilo.split(" / ", 1)]
        telo = ("<!doctype html><html lang=sl><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                "<meta http-equiv=Content-Security-Policy content=\"default-src 'none'; style-src 'unsafe-inline'\">"
                "<title>Safeer</title><style>html{color-scheme:dark}body{background:#0c1420;color:#eef4fa;"
                "font:18px system-ui,sans-serif;max-width:620px;margin:12vh auto;padding:28px;line-height:1.6}"
                "h1{font-size:26px}p{color:#bdcadd}</style><h1>" + deli[0] + "</h1>"
                + ("<p>" + deli[1] + "</p>" if len(deli) > 1 else "") + "</html>").encode("utf-8")
        try:
            client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/html; charset=utf-8\r\n"
                                b"Content-Length: " + str(len(telo)).encode() + b"\r\nConnection: close\r\n\r\n" + telo)
        except Exception:
            pass
        try:
            client_sock.close()
        except Exception:
            pass

    def _povezi_z_osvezitvijo(self, client_sock: socket.socket, host: str, naslov: str,
                              vrata: int) -> Optional[socket.socket]:
        """Kot _vzpostavi_povezavo; ce naslov (morda star iz predpomnilnika) ne sprejme povezave, ime razresi
        znova in poskusi se enkrat na novem naslovu."""
        try:
            povezava = socket.create_connection((naslov, vrata), timeout=10.0)
            _brez_zamika(povezava)
            return povezava
        except OSError:
            pass
        try:
            self.resolver.pozabi(host)
            nov = self.resolver.resolve(host)
        except Exception:  # noqa: BLE001
            nov = None
        if nov and nov != naslov and je_dovoljen_cilj(nov, self.dovoli_lokalno):
            return self._vzpostavi_povezavo(client_sock, nov, vrata)
        self._napaka_povezave(client_sock, naslov)   # isti naslov: ne cakamo se enkrat do 10 s
        return None

    def _vzpostavi_povezavo(self, client_sock: socket.socket, naslov: str, vrata: int) -> Optional[socket.socket]:
        """Povezava na razresen naslov; pri neuspehu (npr. stran samo z IPv6, omrezje pa IPv6 nima) razumljiva napaka."""
        try:
            povezava = socket.create_connection((naslov, vrata), timeout=10.0)
            _brez_zamika(povezava)
            return povezava
        except OSError:
            self._napaka_povezave(client_sock, naslov)
            return None

    def _napaka_povezave(self, client_sock: socket.socket, naslov: str) -> None:
        if ":" in naslov:
            self._napaka_502(client_sock, "Ta stran je dosegljiva samo prek IPv6, vaše omrežje pa IPv6 ne omogoča. / "
                                          "This site is reachable only over IPv6, and your network does not provide it.")
        else:
            self._napaka_502(client_sock, "Povezava s strežnikom ni uspela. / Could not connect to the server.")

    def _pripravi_cilj(self, client_sock: socket.socket, host: str, port: int) -> Optional[str]:
        """
        Razreši ime prek DoH in preveri, ali je cilj sploh dovoljen.
        Vrne IP niz ali None, če je bila povezava zavrnjena (odgovor je že poslan).
        """
        if not je_dovoljena_vrata(port):
            self._zavrni(client_sock, b"Safeer: ta vrata niso dovoljena.")
            return None

        resolved_ip = self.resolver.resolve(host)
        if not resolved_ip:
            self._napaka_502(client_sock, "Strani s tem imenom ni bilo mogoče najti (DNS). / The site name could not be found (DNS).")
            return None

        if not je_dovoljen_cilj(resolved_ip, self.dovoli_lokalno):
            self._zavrni(client_sock, b"Safeer: povezava v lokalno omrezje je zavrnjena.")
            return None

        return resolved_ip

    def _handle_client(self, client_sock: socket.socket):
        remote_sock = None
        try:
            client_sock.settimeout(10.0)
            if client_sock.recv(1, socket.MSG_PEEK) == b"\x05":
                remote_sock = self._socks5(client_sock)
                return
            req_data = b""
            while b"\r\n\r\n" not in req_data and len(req_data) < 8192:
                chunk = client_sock.recv(2048)
                if not chunk:
                    break
                req_data += chunk

            if b"\r\n\r\n" not in req_data:
                client_sock.close()
                return

            headers, initial_body = req_data.split(b"\r\n\r\n", 1)
            header_line = req_data.split(b"\r\n", 1)[0].decode("latin1", errors="ignore")
            parts = header_line.split()
            if len(parts) < 2:
                client_sock.close()
                return

            method, target = parts[0].upper(), parts[1]

            if method == "CONNECT":
                # HTTPS Tunel: CONNECT example.com:443 HTTP/1.1
                if ":" in target:
                    host, port_s = target.rsplit(":", 1)
                    host = host.strip("[]")
                    port = int(port_s) if port_s.isdigit() else 443
                else:
                    host = target
                    port = 443

                resolved_ip = self._pripravi_cilj(client_sock, host, port)
                if not resolved_ip:
                    return

                remote_sock = self._povezi_z_osvezitvijo(client_sock, host, resolved_ip, port)
                if remote_sock is None:
                    return
                with self._socket_lock:
                    self._sockets.add(remote_sock)
                if not self.is_running:
                    return

                # Potrdi tunel narocniku
                client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

                # Odstrani timeoute za neomejen podatkovni prenos (streaming, web)
                client_sock.settimeout(30.0)
                remote_sock.settimeout(30.0)

                if initial_body:
                    remote_sock.sendall(initial_body)

                # Dvosmerno pretakanje bajtov med klientom in oddaljenim streznikom
                self._pipe_sockets(client_sock, remote_sock)

            elif method in ("GET", "POST", "HEAD", "PUT", "DELETE", "OPTIONS", "PATCH"):
                # Obicajni HTTP Proxy zahtevek
                parsed = urllib.parse.urlparse(target)
                host = parsed.hostname or ""
                try:
                    port = parsed.port or 80
                except ValueError:
                    port = 0

                resolved_ip = self._pripravi_cilj(client_sock, host, port)
                if not resolved_ip:
                    return

                remote_sock = self._povezi_z_osvezitvijo(client_sock, host, resolved_ip, port)
                if remote_sock is None:
                    return
                with self._socket_lock:
                    self._sockets.add(remote_sock)
                if not self.is_running:
                    return

                # Preuredi zahtevek v relativno pot za ciljni streznik
                path = parsed.path or "/"
                if parsed.query:
                    path += f"?{parsed.query}"
                new_first_line = f"{method} {path} {parts[2] if len(parts) > 2 else 'HTTP/1.1'}\r\n".encode("latin1")
                rest_of_headers = b"\r\n".join(line for line in headers.split(b"\r\n")[1:]
                    if line.split(b":", 1)[0].lower() not in (b"proxy-authorization", b"proxy-connection")) + b"\r\n\r\n" + initial_body
                remote_sock.sendall(new_first_line + rest_of_headers)

                client_sock.settimeout(30.0)
                remote_sock.settimeout(30.0)
                self._pipe_sockets(client_sock, remote_sock)

            else:
                client_sock.close()

        except Exception:
            pass
        finally:
            with self._socket_lock:
                self._sockets.discard(client_sock)
                self._sockets.discard(remote_sock)
            self._slots.release()
            try:
                client_sock.close()
            except Exception:
                pass
            if remote_sock:
                try:
                    remote_sock.close()
                except Exception:
                    pass

    def _socks5(self, client_sock: socket.socket) -> Optional[socket.socket]:
        """SOCKS5 CONNECT brez prijave (RFC 1928), z istimi pravili kot HTTP CONNECT: dovoljena vrata, ime prek
        DoH, samo javni naslovi. Vrne oddaljeno vticnico (za pospravljanje v finally) ali None."""
        _ver, n = _preberi_tocno(client_sock, 2)
        metode = _preberi_tocno(client_sock, n)
        if 0 not in metode:
            client_sock.sendall(b"\x05\xff")
            return None
        client_sock.sendall(b"\x05\x00")
        ver, ukaz, _rez, vrsta = _preberi_tocno(client_sock, 4)
        if vrsta == 1:
            host = socket.inet_ntoa(_preberi_tocno(client_sock, 4))
        elif vrsta == 3:
            host = _preberi_tocno(client_sock, _preberi_tocno(client_sock, 1)[0]).decode("ascii", errors="replace")
        elif vrsta == 4:
            host = socket.inet_ntop(socket.AF_INET6, _preberi_tocno(client_sock, 16))
        else:
            client_sock.sendall(_socks5_odgovor(8))
            return None
        port = int.from_bytes(_preberi_tocno(client_sock, 2), "big")
        if ver != 5 or ukaz != 1:
            client_sock.sendall(_socks5_odgovor(7))
            return None
        if not je_dovoljena_vrata(port):
            client_sock.sendall(_socks5_odgovor(2))
            return None
        try:
            ipaddress.ip_address(host)
            naslov: Optional[str] = host
        except ValueError:
            naslov = self.resolver.resolve(host)
            if not naslov:
                client_sock.sendall(_socks5_odgovor(4))
                return None
        if not je_dovoljen_cilj(naslov, self.dovoli_lokalno):
            client_sock.sendall(_socks5_odgovor(2))
            return None
        remote_sock = self._socks5_povezi(host, naslov, port)
        if remote_sock is None:
            client_sock.sendall(_socks5_odgovor(5))
            return None
        with self._socket_lock:
            self._sockets.add(remote_sock)
        if not self.is_running:
            return remote_sock
        client_sock.sendall(_socks5_odgovor(0))
        client_sock.settimeout(30.0)
        remote_sock.settimeout(30.0)
        self._pipe_sockets(client_sock, remote_sock)
        return remote_sock

    def _socks5_povezi(self, host: str, naslov: str, vrata: int) -> Optional[socket.socket]:
        """Kot _povezi_z_osvezitvijo, a brez odgovora HTTP (napako SOCKS5 poslje klicatelj)."""
        for poskus in range(2):
            try:
                povezava = socket.create_connection((naslov, vrata), timeout=10.0)
                _brez_zamika(povezava)
                return povezava
            except OSError:
                pass
            if poskus or host == naslov:
                return None
            try:
                self.resolver.pozabi(host)
                nov = self.resolver.resolve(host)
            except Exception:  # noqa: BLE001
                nov = None
            if not nov or nov == naslov or not je_dovoljen_cilj(nov, self.dovoli_lokalno):
                return None
            naslov = nov
        return None

    def _pipe_sockets(self, s1: socket.socket, s2: socket.socket):
        """Asinhrono dvosmerno posredovanje podatkov z nicelno zakasnitvijo."""
        sockets = [s1, s2]
        bufsize = 65536
        while self.is_running:
            try:
                readable, _, exceptional = select.select(sockets, [], sockets, 60.0)
                if exceptional:
                    break
                if not readable:
                    break

                for s in readable:
                    data = s.recv(bufsize)
                    if not data:
                        return
                    target = s2 if s is s1 else s1
                    target.sendall(data)
            except Exception:
                break


# Globalni primerek posrednika za enojni vir resnice (Single Source of Truth)
_global_resolver: Optional[DoHResolver] = None
_global_proxy: Optional[LocalDoHProxy] = None
_proxy_lock = threading.Lock()


def get_doh_proxy(provider: str = "cloudflare", custom_url: str = "", enabled: bool = True,
                  lokalno: bool = False) -> Optional[LocalDoHProxy]:
    """Pridobi ali inicializira globalni primerek DoH posrednika."""
    global _global_resolver, _global_proxy
    with _proxy_lock:
        if not enabled:
            if _global_proxy:
                _global_proxy.stop()
                _global_proxy = None
            return None

        if _global_resolver is None:
            _global_resolver = DoHResolver(provider, custom_url)
        else:
            _global_resolver.set_provider(provider, custom_url)

        if _global_proxy is None:
            _global_proxy = LocalDoHProxy(_global_resolver, dovoli_lokalno=lokalno)
            _global_proxy.start()
        else:
            _global_proxy.dovoli_lokalno = bool(lokalno)

        return _global_proxy
