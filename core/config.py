#!/usr/bin/env python3
"""
Safeer Browser for Linux Mint - Configuration Manager
Manages user preferences, modular sidebar integrations, and virtual keyboard settings.
"""

import ipaddress
import os
import copy
import re
import json
import uuid
import time
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple

from core import nastavitve_shema, shramba_json


def normalize_web_url(url: str) -> str:
    """Validate and normalize a user-supplied web URL to safe http/https schemes."""
    if not url:
        return ""
    cleaned = url.strip()
    if not cleaned:
        return ""

    # If colon is present, determine if it is host:port or a URI scheme
    if ":" in cleaned:
        first_part, rest = cleaned.split(":", 1)
        port_candidate = rest.split("/", 1)[0]
        if port_candidate.isdigit():
            cleaned = "http://" + cleaned
        else:
            try:
                parsed = urllib.parse.urlparse(cleaned)
                if parsed.scheme.lower() not in ("http", "https"):
                    return ""
                if not (parsed.netloc or parsed.hostname):
                    return ""
                return cleaned
            except Exception:
                return ""
    else:
        cleaned = "https://" + cleaned

    try:
        parsed = urllib.parse.urlparse(cleaned)
        if parsed.scheme.lower() in ("http", "https") and (parsed.netloc or parsed.hostname):
            return cleaned
        return ""
    except Exception:
        return ""


#: Koncnice datotek, ki niso vrhnje domene: »racun.pdf« v naslovni vrstici je iskanje, ne https://racun.pdf
#: (.zip, .mov in .app SO vrhnje domene, zato jih ni na seznamu).
_KONCNICE_NE_DOMENE = frozenset(("pdf", "doc", "docx", "odt", "ods", "odp", "xls", "xlsx", "ppt", "pptx", "txt", "rtf",
                                 "csv", "jpg", "jpeg", "png", "gif", "webp", "svg", "mp3", "mp4", "mkv", "avi", "flac",
                                 "wav", "ogg", "7z", "rar", "tar", "gz", "deb", "rpm", "exe", "apk", "iso", "py", "js",
                                 "json", "md", "html", "htm"))
def _je_ip(ime: str) -> bool:
    """Naslov IP, ki je lahko cilj: brez obmocja (»fe80::1%eth0«) in brez »0.0.0.0« / »::«.

    Obmocja (zone ID) standard URL WHATWG ne pozna (ui/splet.js new URL ga zavrne), zato bi Python in JS odlocala razlicno.
    0.0.0.0 ni ciljni naslov (RFC 1122); brskalniki ga zapirajo (»0.0.0.0 day«, 2024), zato je iskanje (pregled 1.0.130)."""
    if "%" in ime:
        return False
    try:
        return not ipaddress.ip_address(ime).is_unspecified
    except ValueError:
        return False


#: Ne-spletne sheme, ki so brez »//« videti kot gostitelj:vrata (»tel:123« je bil http://tel:123) - vedno iskanje.
_NE_SPLETNE_SHEME = frozenset(("tel", "sms", "smsto", "mms", "mmsto", "fax", "callto", "sip", "sips", "mailto", "geo",
                               "xmpp", "skype", "facetime", "magnet", "news", "nntp", "urn", "data", "javascript",
                               "vbscript", "about", "blob", "file", "intent", "market", "content", "chrome"))


def _veljavna_vrata(vrata: str) -> bool:
    """1-65535 (»primer.si:99999« in »:0« nista naslova - pregled pomocnika 1.0.130, S5)."""
    return bool(re.fullmatch(r"[0-9]{1,5}", vrata)) and 1 <= int(vrata) <= 65535


def _veljavne_oznake(ime: str) -> bool:
    """Oznake domene niso prazne in se ne zacnejo ali koncajo z »-« (»-primer.si« je iskanje; S5)."""
    deli = ime.rstrip(".").split(".")
    return all(d and not d.startswith("-") and not d.endswith("-") for d in deli)


def _ipv6_v_oklepajih(gostitelj: str) -> bool:
    """»[IPv6]« ali »[IPv6]:vrata« z veljavnim naslovom in vrati."""
    konec = gostitelj.find("]")
    if konec <= 1:
        return False
    notranje, ostanek = gostitelj[1:konec], gostitelj[konec + 1:]
    return ":" in notranje and _je_ip(notranje) and (ostanek == "" or (ostanek.startswith(":") and
                                                                      _veljavna_vrata(ostanek[1:])))


def _izrecna_avtoriteta(avtoriteta: str) -> bool:
    """Gostitelj za izrecnim »http(s)://«: brez presledka, z veljavnimi vrati in oznakami. Vrhnja domena ni potrebna
    (»https://test/«). Uporabniski del (»https://admin:geslo@192.168.0.1/«) je naslov kot v Chromu in Safariju - gostitelj
    je za zadnjim »@«: neodvisni pregled Gemini 1.0.131 (VISOKA) - kot iskanje bi geslo ali zeton odsel iskalniku."""
    if not avtoriteta or any(c.isspace() for c in avtoriteta):
        return False
    if "@" in avtoriteta:
        uporabnik, avtoriteta = avtoriteta.rsplit("@", 1)
        if not uporabnik or not avtoriteta:
            return False
    if avtoriteta.startswith("["):
        return _ipv6_v_oklepajih(avtoriteta)
    ime, dvopicje, vrata = avtoriteta.partition(":")
    if dvopicje and not _veljavna_vrata(vrata):
        return False
    if ime.lower() == "localhost" or _je_ip(ime):
        return True
    return bool(ime) and _veljavne_oznake(ime) and not re.fullmatch(r"[0-9.]+", ime)


#: Izrecno (ne ipaddress.is_private, ta steje tudi dokumentacijska omrezja): isti seznam kot ui/splet.js lokalniGostitelj.
_LOKALNA_OMREZJA = tuple(ipaddress.ip_network(m) for m in (
    "10.0.0.0/8", "127.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "::1/128", "fc00::/7", "fe80::/10"))


def _lokalni_gostitelj(s: str) -> bool:
    """localhost ali zasebni/loopback/link-local naslov IP (tudi [IPv6]) - tam je http obicajen in ostane v omrezju."""
    gost = re.split(r"[/?#]", s, 1)[0].rsplit("@", 1)[-1]
    if gost.startswith("["):
        ime = gost[1:gost.find("]")] if "]" in gost else ""
    else:
        ime = gost.rsplit(":", 1)[0] if re.search(r":\d+$", gost) else gost
    if ime.lower() == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(ime)
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:      # [::ffff:192.168.0.1] je IPv4 - lokalen samo, ce je lokalen IPv4
        ip = ip.ipv4_mapped
    return any(ip in m for m in _LOKALNA_OMREZJA if m.version == ip.version)


def je_spletni_naslov(besedilo: str) -> bool:
    """Ali je vpis v naslovno vrstico spletni naslov (True) ali iskanje (False) - kot v sodobnih brskalnikih.

    Lastnik 21. 10. 2026: v Spletu je »test« odprl https://test/ (»Strani trenutno ni mogoče odpreti«) namesto iskanja;
    normalize_web_url iz vsake besede brez dvopicja naredi naslov, tudi iz »vreme ljubljana«. Naslov je: shema http(s),
    localhost, IP, gostitelj z vrati, beseda s posevnico na koncu (»nas/«) ali gostitelj s piko in vrhnjo domeno iz crk.
    Iskanje je: ena beseda brez pike, vse s presledkom, »python 3.12«, »racun.pdf«, vpis, ki se zacne z »?«.
    Isto pravilo ima zacetna stran Spleta (ui/splet.js jeSpletniNaslov) - preizkus tests/test_naslovna_vrstica.py."""
    s = (besedilo or "").strip()
    if not s or s.startswith("?"):
        return False
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):(//)?", s)
    if m and m.group(2):
        # Izrecen http(s):// z veljavnim gostiteljem je naslov tudi s presledkom za gostiteljem (naslov_ali_iskanje ga
        # zakodira v %20): sicer bi cel naslov z zetonom odsel iskalniku (pregled pomocnika 1.0.130, S3).
        return m.group(1).lower() in ("http", "https") and _izrecna_avtoriteta(re.split(r"[/?#]", s[m.end():], 1)[0])
    if any(c.isspace() for c in s):
        return False
    gostitelj = re.split(r"[/?#]", s, 1)[0]
    pot = s[len(gostitelj):]
    if not gostitelj:
        return False
    if "@" in gostitelj:
        uporabnik, gost = gostitelj.rsplit("@", 1)
        if ":" not in uporabnik or not gost or uporabnik.split(":", 1)[0].lower() in _NE_SPLETNE_SHEME:
            return False                               # »ime@posta.si«, »mailto:a@b.si« niso naslov strani - iskanje
        return je_spletni_naslov(gost + pot)           # »admin:geslo@192.168.0.1« - geslo ne sme k iskalniku
    if gostitelj.startswith("["):                      # [IPv6] ali [IPv6]:vrata
        return _ipv6_v_oklepajih(gostitelj)
    ime, dvopicje, vrata = gostitelj.partition(":")
    if dvopicje:                                       # localhost:8080, test:3000 (»localhost:«, »tel:123« ne)
        return bool(ime) and _veljavna_vrata(vrata) and ime.lower() not in _NE_SPLETNE_SHEME and \
            (ime.lower() == "localhost" or _je_ip(ime) or (_veljavne_oznake(ime) and not re.fullmatch(r"[0-9.]+", ime)))
    if ime.lower() == "localhost" or _je_ip(ime):
        return True
    if "." not in ime:
        return pot == "/" and _veljavne_oznake(ime)    # »nas/« (gostitelj v domacem omrezju, kot Chrome)
    deli = ime.rstrip(".").split(".")
    if len(deli) < 2 or not all(deli) or not _veljavne_oznake(ime):
        return False
    vrh = deli[-1].lower()
    if vrh.startswith("xn--"):
        return len(vrh) > 4
    if len(vrh) < 2 or not vrh.isalpha():
        return False
    # »racun.pdf« je ime datoteke, »lanacion.com.py« (Paragvaj) ali »safeer.si/x.md« pa naslov (pregled pomocnika 1.0.130)
    return not (len(deli) == 2 and not pot and vrh in _KONCNICE_NE_DOMENE)


def prikazni_naslov(uri: str) -> str:
    """Naslov za prikaz v naslovni vrstici brez uporabniskega dela (kot Chrome in Safari): »https://safeer.si@evil.com/«
    pokaze »https://evil.com/« - pravi gostitelj, ne vabe, in gesla ali zetona ne kaze na zaslonu (Gemini 1.0.131)."""
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*://)([^/?#]*)(.*)$", uri or "", re.S)
    if not m or "@" not in m.group(2):
        return uri or ""
    return m.group(1) + m.group(2).rsplit("@", 1)[1] + m.group(3)


def gostitelj_bliznjice(url: str) -> str:
    """Pravi gostitelj za ploscico bliznjice (kot ui/splet.js narisiBliznjice): brez uporabniskega dela (userinfo)
    in brez »www.«. Za »http://x@evil.com/« vrne »evil.com« (ne »x« ali »x@evil.com«)."""
    try:
        parsed = urllib.parse.urlsplit(url or "")
        gost = parsed.hostname or (parsed.netloc.rsplit("@", 1)[-1] if "@" in parsed.netloc else parsed.netloc)
        gost = (gost or "").lower()
        if gost.startswith("www."):
            gost = gost[4:]
        return gost
    except Exception:
        return ""


def naslov_ali_iskanje(besedilo: str, iskalnik_url: str) -> str:
    """Naslov za vpis v naslovno vrstico: spletni naslov ali stran rezultatov izbranega iskalnika."""
    s = (besedilo or "").strip()
    if not s:
        return ""
    if re.match(r"^file:", s, re.I):
        return s                                       # kot ui/splet.js vNaslov - lokalna pot ne sme k iskalniku (Gemini 1.0.131)
    if je_spletni_naslov(s):
        # Naslov sestavimo sami (kot ui/splet.js vNaslov): normalize_web_url je »router.lan:8443?token=x« zavrnil in cel niz
        # z zetonom poslal iskalniku (neodvisni pregled OpenAI 1.0.130, krog A). Privzeto https; http samo za dokazljivo
        # lokalne naslove (localhost, zasebni/loopback/link-local IP) - vrata ne dokazujejo domacega omrezja (krog B).
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", s):
            naslov = re.sub(r"\s", "%20", s)          # presledek za gostiteljem (S3): »?token=abc 123« -> abc%20123
        else:
            naslov = ("http://" if _lokalni_gostitelj(s) else "https://") + s
        if naslov:
            return naslov
    return iskalnik_url + urllib.parse.quote_plus(s[1:].strip() if s.startswith("?") else s)


def naslov_za_lupo(besedilo: str) -> str:
    """Naslov za prvi zadetek lupe »Odpri safeer.si« (kot omnibox Chrome/Safari; lastnik 21. 10. 2026) ali "", ce
    vpis ni spletni naslov. Isto pravilo kot naslovna vrstica Spleta, zato lupa in Splet odpreta isti naslov."""
    s = (besedilo or "").strip()
    return naslov_ali_iskanje(s, "") if je_spletni_naslov(s) else ""


# SAFEER_MINT_CONFIG_DIR: Safeer Browser v Flatpaku (safeer_brskalnik.py) - ista mapa kot .deb (~/.config/safeer-mint),
# ki jo manifest pokaze kot edino mapo v ~/.config; XDG_CONFIG_HOME ostane zasebna mapa peskovnika.
CONFIG_DIR = os.environ.get("SAFEER_MINT_CONFIG_DIR") or os.path.join(
    (os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")), "safeer-mint")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

SEARCH_ENGINES = {
    "google": {
        "name": "Google",
        "url": "https://www.google.com/search?q=",
        "icon": "🔍"
    },
    "duckduckgo": {
        "name": "DuckDuckGo",
        "url": "https://duckduckgo.com/?q=",
        "icon": "🦆"
    },
    "brave": {
        "name": "Brave Search",
        "url": "https://search.brave.com/search?q=",
        "icon": "🦁"
    },
    "ecosia": {
        "name": "Ecosia",
        "url": "https://www.ecosia.org/search?q=",
        "icon": "🌲"
    },
    "bing": {
        "name": "Bing",
        "url": "https://www.bing.com/search?q=",
        "icon": "🔎"
    }
}

DEFAULT_SETTINGS: Dict[str, Any] = {
    "language": "auto",                 # "auto", "en", "sl", "de", "es", "fr", "it"
    "force_dark_mode": False,          # Privzeto izklopljen, da ne kvari prikaza zemljevidov in bančnih strani
    "theme": "safeer",                  # "safeer" (barve safeer.si), "midnight", "mint", "neon", "amoled"
    "custom_css": "",                   # Lasten CSS slog uporabnika
    "user_scripts": [
        {
            "id": "sample_banner_cleaner",
            "name": "Primer: Konzola obvestilo",
            "pattern": "*",
            "code": "// Safeer Uporabniška skripta\nconsole.log('🛡️ Safeer Custom Script teče na: ' + window.location.href);",
            "enabled": False,
            "run_at": "end"
        }
    ],
    "virtual_keyboard_enabled": False,  # Privzeto izklopljeno kot zahtevano
    "sidebar_enabled": True,            # Trajni vklop/izklop stranske vrstice
    "sidebar_width": 680,
    "search_engine": "duckduckgo",
    "adblock_enabled": True,
    "easylist_enabled": True,            # EasyList rules as a WebKit content filter (network layer)
    "adguard_protection_enabled": True,  # Vgrajena napredna AdGuard zaščita (anti-adblock defuser, cosmetic rules)
    "sleep_heavy_background_tabs": True,  # Težek zavihek v ozadju brez zvoka po minuti zaspi (klik ga znova naloži)
    "tab_freeze_after_s": 60,              # Neaktiven tih zavihek po tem času ustavi časovnike (0 = izklop)
    "tab_discard_after_s": 600,            # Neaktiven tih zavihek po tem času sprosti spletni proces (0 = izklop)
    "network_process_limit_mb": 300,       # Meja recikliranja omreznega procesa (0 = izklop); v 1.0.129 ne velja (RECIKLIRANJE_OMREZNEGA = False)
    "tracking_protection_enabled": True,  # Odstranjevanje sledilnih parametrov (UTM, fbclid, gclid, si, itd.)
    "gpc_dnt_enabled": True,             # W3C Global Privacy Control & Do Not Track signal
    "doh_enabled": True,                 # Šifriran DNS (DNS-over-HTTPS) za zaščito pred ISP cenzuro in prisluškovanjem
    "doh_provider": "scit",              # "scit" (privzeto: Safeer Ščit + naprej), "quad9", "cloudflare", "google", "adguard", "opendns", "custom", "disabled"
    "custom_doh_url": "https://1.1.1.1/dns-query",  # DNS po meri: naslov DoH (https://…/dns-query) ali IP strežnika (tudi Pi-hole)
    "scit_naprej": "cloudflare",         # Ščit v brskalniku pošlje dovoljena imena naprej: ponudnik, "custom" ali "router" (DNS usmerjevalnika)
    "scit_naprej_po_meri": "",           # strežnik naprej po meri (DoH ali IP)
    "dns_rezerva": True,                 # SERVFAIL/časovna odpoved/lažna blokada ponudnika -> drug ponudnik (Ščitove blokade ostanejo)
    "dns_scit_selitev": True,            # nove namestitve: selitev na Ščit ni potrebna
    "dns_izbira_uporabnika": False,      # True, ko uporabnik sam shrani izbiro DNS (prihodnje spremembe privzetega je ne povozijo)
    "doh_lokalno_omrezje": False,        # Imena, ki se prevedejo v domaci naslov (Pi-hole, usmerjevalnik), se odprejo; povratni in metapodatkovni naslovi ostanejo zavrnjeni
    "secure_proxy_mode": "disabled",     # "disabled", "custom" (Lasten šifriran proxy)
    "secure_proxy_url": "http://127.0.0.1:8080",    # URL za lasten varen SOCKS5/HTTPS proxy
    # Datoteka nastavitev te in novejsih razlicic: ostanki preizkusov (pocisti_ostanke_preizkusov) so ze pregledani.
    # Brez kljuca = datoteka stare razlicice: ciscenje enkrat. Kar nastavi kdo potem (tudi preizkus namerno), ostane.
    "ostanki_preizkusov_pregledani": True,
    "total_ads_blocked": 0,              # Kumulativno število blokiranih oglasov
    "total_threats_blocked": 0,          # Kumulativno število preprečenih groženj (C2, malware, phishing)
    "hardware_acceleration": "on_demand",  # "on_demand", "always", "never"
    "permissions_policy": "ask",          # "ask", "allow", "deny"
    "always_ask_download_dir": False,     # Privzeto samodejno prenese v mapo Prenosi brez vsiljenih modalnih oken
    "homepage": "safeer://home",
    "integrations": {
        "remote_control": {
            "name": "Remote Control",
            "url": "http://localhost:8080",
            "icon": "🎮",
            "enabled": False,
            "color": "#3b82f6"
        },
        "messenger": {
            "name": "Facebook Messenger",
            # Meta je messenger.com ukinila 15. 4. 2026 (preusmeri sem); naslov iz kataloga core/spletni_klepeti.py.
            "url": "https://www.facebook.com/messages/",
            "icon": "💬",
            "enabled": False,
            "color": "#0084ff"
        },
        "gmail": {
            "name": "Gmail",
            "url": "https://mail.google.com/mail/",
            "icon": "✉️",
            "enabled": False,
            "color": "#ea4335"
        }
    },
    "custom_portals": [],
    "default_bookmarks_removed": True
}


# Shema settings.json (tipi, obsegi, razlicica, selitve) je v core/nastavitve_shema.py - brez kode brskalnika, da jo
# lahko uvozita tudi Safeer Control in Safeer OS za branje enega kljuca (naloga 43). Nalaga in pise samo ConfigManager.
DEFAULT_SETTINGS[nastavitve_shema.KLJUC_RAZLICICE] = nastavitve_shema.SCHEMA_VERSION
KLJUC_RAZLICICE = nastavitve_shema.KLJUC_RAZLICICE
SCHEMA_VERSION = nastavitve_shema.SCHEMA_VERSION
SHEMA = nastavitve_shema.SHEMA
razlicica_datoteke = nastavitve_shema.razlicica_datoteke
varnostna_kopija = nastavitve_shema.varnostna_kopija
preseli_razlicico = nastavitve_shema.preseli_razlicico


def uveljavi_shemo(nastavitve: Dict[str, Any], tiho: bool = False) -> List[str]:
    """nastavitve_shema.uveljavi_shemo s privzetimi vrednostmi brskalnika (DEFAULT_SETTINGS)."""
    return nastavitve_shema.uveljavi_shemo(nastavitve, DEFAULT_SETTINGS, tiho=tiho)


def preberi_kljuc(kljuc: str, privzeto: Any = None, pot: Optional[str] = None) -> Any:
    return nastavitve_shema.preberi_kljuc(kljuc, privzeto, pot or CONFIG_FILE)


LEGACY_DEFAULT_PORTALS = [
        {"id": "p0", "title": "YouTube", "url": "https://www.youtube.com", "mark": "📺", "bg": "linear-gradient(145deg, #4a0b0b, #cc0000)", "color": "#cc0000"},
        {"id": "p1", "title": "Wikipedia", "url": "https://www.wikipedia.org", "mark": "🌐", "bg": "linear-gradient(145deg, #1e293b, #475569)", "color": "#64748b"},
        {"id": "p2", "title": "GitHub", "url": "https://github.com", "mark": "🐙", "bg": "linear-gradient(145deg, #1b1f24, #24292e)", "color": "#24292e"},
        {"id": "p3", "title": "DuckDuckGo", "url": "https://duckduckgo.com", "mark": "🦆", "bg": "linear-gradient(145deg, #3d2303, #de5833)", "color": "#de5833"}
    ]


def dodaj_katalog_integracijam(nastavitve: Dict[str, Any]) -> bool:
    """Integracije stranske plosce iz kataloga spletnih klepetov; vrne True, ce je bilo kaj spremenjeno."""
    from core import spletni_klepeti
    integracije = nastavitve.setdefault("integrations", {})
    spremenjeno = spletni_klepeti.preseli_integracije(integracije)
    ponujeni = list(nastavitve.get("integrations_katalog", []) or [])
    for kid, vnos in spletni_klepeti.integracije(str(nastavitve.get("language", "sl") or "sl")[:2]).items():
        if kid in ponujeni:
            continue
        ponujeni.append(kid)
        spremenjeno = True
        if kid not in integracije and not any(isinstance(v, dict) and v.get("url") == vnos["url"]
                                              for v in integracije.values()):
            integracije[kid] = vnos
    nastavitve["integrations_katalog"] = ponujeni
    return spremenjeno


def preseli_dns_na_scit(merged: Dict[str, Any], user_settings: Dict[str, Any]) -> bool:
    """Enkratna selitev (1.0.128, lastnik 16. 10. 2026: »DNS naj bo prevzeto od Safeer Scita«).

    Nastavitve se ob prvem zagonu shranijo v celoti (save_settings zapise vse privzete vrednosti), zato »cloudflare«
    v datoteki ne pove, ali ga je uporabnik izbral sam. Na Scit zato preselimo vse z »cloudflare«: Scit dovoljena
    imena privzeto poslje naprej prav Cloudflaru (1.1.1.1, DoH), torej razresuje isti ponudnik - doda se le filter.
    Kdor je izbral drugega ponudnika, svoj DoH ali izklop, obdrzi svojo izbiro. Od zdaj si izrecno izbiro zapomnimo
    (dns_izbira_uporabnika)."""
    if user_settings.get("dns_scit_selitev"):
        return False
    merged["dns_scit_selitev"] = True
    if (merged.get("doh_provider", "cloudflare") == "cloudflare" and merged.get("doh_enabled", True)
            and not user_settings.get("dns_izbira_uporabnika")):
        merged["doh_provider"] = "scit"
        merged["scit_naprej"] = "cloudflare"
    return True


#: Vrednosti, ki so jih preizkusi pred izolacijo okolja (25. 10. 2026) zapisali v PRAVE nastavitve uporabnika
#: (tests/test_kanali_sporocil.py, test_kanali_most_zivo.py, test_stranska_plosca.py): zaprt posrednik na vratih 9 in
#: dovoljenje za izmisljeno stran *.invalid. Lastnik 27. 10. 2026: Splet je ob vsakem zagonu javil »Strani trenutno ni
#: mogoce odpreti« (g-io-error-quark 39), ker je seja sla na http://127.0.0.1:9; Chrome in Firefox sta delala.
VRATA_ZAPRTEGA_POSREDNIKA = 9          # discard: tu nikoli ne poslusa noben posrednik
TESTNA_DOMENA = ".invalid"             # RFC 2606: ime, ki ga v omrezju ni


def _zaprt_posrednik_preizkusov(url: Any) -> bool:
    """http(s)/socks posrednik na povratnem naslovu z vrati 9 - nikoli ni uporaben, zapisali so ga preizkusi."""
    try:
        d = urllib.parse.urlsplit(str(url or "").strip())
        if d.port != VRATA_ZAPRTEGA_POSREDNIKA or not d.hostname:
            return False
        return d.hostname == "localhost" or ipaddress.ip_address(d.hostname).is_loopback
    except ValueError:
        return False


def pocisti_ostanke_preizkusov(merged: Dict[str, Any]) -> List[str]:
    """Odstrani iz nastavitev, kar so zapisali preizkusi pred izolacijo; vrne spremenjene kljuce ([] = nic).

    - Lasten posrednik na zaprtih vratih 9 -> posrednik izklopljen (privzeto). Drug lasten posrednik ostane.
    - Dovoljenja strani za *.invalid -> odstranjena (take strani ni).
    - Samo, ce sta OBE sledi preizkusov (posrednik 9 in *.invalid), so tudi izklop DNS in EasyList delo preizkusov
      (isti setUp jih je nastavil skupaj) -> privzete vrednosti. Sicer ju pustimo: morda ju je izklopil uporabnik.
    """
    spremenjeno: List[str] = []
    posrednik = merged.get("secure_proxy_mode") == "custom" and _zaprt_posrednik_preizkusov(merged.get("secure_proxy_url"))
    if posrednik:
        merged["secure_proxy_mode"] = DEFAULT_SETTINGS["secure_proxy_mode"]
        merged["secure_proxy_url"] = DEFAULT_SETTINGS["secure_proxy_url"]
        spremenjeno += ["secure_proxy_mode", "secure_proxy_url"]
    dovoljenja = merged.get("dovoljenja_strani")
    testne = [k for k in dovoljenja if str(k).lower().rstrip(".").endswith(TESTNA_DOMENA)] if isinstance(dovoljenja, dict) else []
    if testne:
        merged["dovoljenja_strani"] = {k: v for k, v in dovoljenja.items() if k not in testne}
        spremenjeno.append("dovoljenja_strani")
    if posrednik and testne:
        for k in ("doh_enabled", "doh_provider", "easylist_enabled"):
            if k in DEFAULT_SETTINGS and merged.get(k) != DEFAULT_SETTINGS[k]:
                merged[k] = copy.deepcopy(DEFAULT_SETTINGS[k])
                spremenjeno.append(k)
    return spremenjeno


class ConfigManager:
    def __init__(self, config_dir: str | None = None):
        self.config_dir = config_dir if config_dir is not None else CONFIG_DIR
        self.config_file = os.path.join(self.config_dir, "settings.json") if config_dir is not None else CONFIG_FILE
        # Stanje datoteke, ki ga ta primerek pozna (zadnje branje ali zapis). Zapis zapise samo kljuce, ki so se tu
        # spremenili glede na to stanje, vse drugo vzame z diska: drug proces (Safeer OS / Safeer Browser) ima svojo
        # kopijo nastavitev in je prej ob vsakem zapisu prepisal spremembe drugega (stresni preizkus 20. 10. 2026).
        self._na_disku: Dict[str, Any] = {}
        self.settings = self.load_settings()

    def _pokvarjena(self, napaka) -> None:
        """Neberljive nastavitve ne prepisemo s privzetimi: shranimo jo ob strani (rocna obnova) in zacnemo znova."""
        if shramba_json.umakni_pokvarjeno(self.config_file, napaka) is None:
            print(f"[Config] Nastavitve niso berljive ({napaka}) in jih ni mogoce umakniti", flush=True)

    def load_settings(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_dir):
            try:
                os.makedirs(self.config_dir, exist_ok=True)
            except Exception as e:
                print(f"[Config] Napaka pri ustvarjanju mape: {e}")

        if os.path.exists(self.config_file):
            user_settings = None
            for poskus in range(2):
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        user_settings = json.load(f)
                    if not isinstance(user_settings, dict):
                        raise ValueError("vsebina ni slovar")
                    break
                except OSError as e:
                    # Neberljiva (dovoljenja ...): privzete samo v pomnilniku, datoteke ne prepisemo.
                    print(f"[Config] Napaka pri branju nastavitev: {e}")
                    nove = copy.deepcopy(DEFAULT_SETTINGS)
                    dodaj_katalog_integracijam(nove)
                    self._na_disku = copy.deepcopy(nove)
                    return nove
                except ValueError as e:
                    user_settings = None
                    if poskus == 0:
                        time.sleep(0.2)      # starejsa razlicica drugega procesa morda ravno pise (brez os.replace)
                        continue
                    self._pokvarjena(e)
            if user_settings is not None:
                self._na_disku = copy.deepcopy(user_settings)
                try:
                    merged = copy.deepcopy(DEFAULT_SETTINGS)
                    merged.update(user_settings)
                    # Shema (naloga 43): razlicica iz DATOTEKE (privzete imajo trenutno); pred selitvijo varnostna kopija.
                    stara = razlicica_datoteke(user_settings)
                    merged[KLJUC_RAZLICICE] = stara
                    if stara < SCHEMA_VERSION:
                        varnostna_kopija(self.config_file, stara)
                    # Tipi in obsegi pred selitvami (selitve spodaj pricakujejo seznam slovarjev). Popravek velja v
                    # pomnilniku; na disku ostane uporabnikova vrednost, dokler je ne spremeni (glej _brez_popravkov).
                    popravljeni = uveljavi_shemo(merged)
                    # Popravljene vrednosti pred selitvami: kljuc, ki ga selitev nato spremeni, se zapise (s popravkom).
                    popravki = {k: copy.deepcopy(merged[k]) for k in popravljeni if k in merged}
                    # If youtube was previously in integrations, remove it as requested
                    if "integrations" in merged and "youtube" in merged["integrations"]:
                        del merged["integrations"]["youtube"]
                    # Migracija: star privzeti zaznamek zamenjamo z RTV 365 in ugasnemo vzorcno skripto
                    migrated = False
                    if not user_settings.get("default_bookmarks_removed", False):
                        merged["custom_portals"] = [p for p in merged.get("custom_portals", []) if p not in LEGACY_DEFAULT_PORTALS]
                        merged["default_bookmarks_removed"] = True
                        migrated = True
                    for p in merged.get("custom_portals", []):
                        if "hydrahd.ws" in p.get("url", ""):
                            p["url"] = "https://365.rtvslo.si"
                            if p.get("title") in ("Filmi & Serije", "Filmi"):
                                p["title"] = "RTV 365"
                            migrated = True
                    for s in merged.get("user_scripts", []):
                        if s.get("id") == "sample_banner_cleaner" and s.get("enabled") is True:
                            s["enabled"] = False
                            migrated = True
                    # Stranska plosca bere katalog spletnih klepetov (core/spletni_klepeti.py - en vir za Sporocila in
                    # vse brskalnike): ukinjeni naslovi se preselijo, nove storitve kataloga se ponudijo (izklopljene)
                    # enkrat - ce jih uporabnik odstrani, se ne vracajo.
                    if dodaj_katalog_integracijam(merged):
                        migrated = True
                    if preseli_dns_na_scit(merged, user_settings):
                        migrated = True
                    # Samo enkrat, za datoteko stare razlicice (brez oznake): kasnejse namerne nastavitve (tudi preizkusi,
                    # ki namenoma uporabijo zaprta vrata 9 brez omrezja) ostanejo. CI 40474119558: brez te oznake je
                    # ciscenje ob vsakem nalaganju pobrisalo nastavitve preizkusa Sporocil.
                    ostanki = []
                    if "ostanki_preizkusov_pregledani" not in user_settings:
                        ostanki = pocisti_ostanke_preizkusov(merged)
                        merged["ostanki_preizkusov_pregledani"] = True
                        migrated = True
                    if ostanki:
                        # Kopija pred ciscenjem (rocna obnova), enkrat - ne prepisemo prejsnje.
                        kopija = self.config_file + ".pred-ciscenjem-preizkusov"
                        if not os.path.exists(kopija):
                            try:
                                shramba_json.zapisi_atomsko(kopija, user_settings)
                            except OSError as napaka:
                                print("[Config] kopija pred ciscenjem ni zapisana: %s" % napaka, flush=True)
                        print("[Config] odstranjene vrednosti preizkusov: %s" % ", ".join(ostanki), flush=True)
                        migrated = True
                    if preseli_razlicico(merged, stara):
                        migrated = True
                    if migrated:
                        # Popravljeni kljuci veljajo za nespremenjene: selitev zapise samo svoje spremembe.
                        self._na_disku = self._brez_popravkov(user_settings, popravki, popravljeni)
                        self.save_settings(merged)
                        uveljavi_shemo(merged, tiho=True)        # kar je zapis prevzel z diska
                    # Primerjava za naslednji zapis: stanje ob nalaganju (s privzetimi in popravki). Privzeta vrednost,
                    # ki je ta proces ni spremenil, ne sme prekriti izbire, ki jo drug proces medtem zapise.
                    self._na_disku = copy.deepcopy(merged)
                    return merged
                except Exception as e:  # noqa: BLE001 - napaka v selitvi ne sme izbrisati uporabnikovih nastavitev
                    print(f"[Config] Napaka pri selitvi nastavitev: {e}")
                    merged = copy.deepcopy(DEFAULT_SETTINGS)
                    merged.update(copy.deepcopy(user_settings))
                    merged[KLJUC_RAZLICICE] = razlicica_datoteke(user_settings)
                    uveljavi_shemo(merged)
                    self._na_disku = copy.deepcopy(merged)
                    return merged

        self._na_disku = {}
        nove = copy.deepcopy(DEFAULT_SETTINGS)
        dodaj_katalog_integracijam(nove)
        self.save_settings(copy.deepcopy(nove))
        return nove

    @staticmethod
    def _brez_popravkov(disk: Dict[str, Any], popravki: Dict[str, Any], popravljeni: List[str]) -> Dict[str, Any]:
        """Znano stanje diska, v katerem imajo popravljeni kljuci popravljeno vrednost: zapis jih prepise samo, ce jih
        je selitev spremenila naprej."""
        znano = copy.deepcopy(disk)
        for k in popravljeni:
            if k in popravki:
                znano[k] = copy.deepcopy(popravki[k])
            else:
                znano.pop(k, None)
        return znano

    def save_settings(self, settings: Dict[str, Any] = None) -> bool:
        """Zapise kljuce, ki so se v tem procesu spremenili, na trenutno vsebino datoteke (pod zaklepom, atomsko).
        Kljuce, ki jih je medtem spremenil drug proces, prevzame tudi v pomnilnik."""
        if settings is not None:
            self.settings = settings
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            self._na_disku = shramba_json.zdruzi_in_zapisi(self.config_file, self.settings,
                                                           getattr(self, "_na_disku", {}), indent=4)
            # Kljuce, ki jih je zapis prevzel z diska (drug proces, rocno urejanje), preveri tudi shema - tiho,
            # popravek samo v pomnilniku (znano stanje enako pomnilniku: zapis ga ne prepise).
            if uveljavi_shemo(self.settings, tiho=True):
                self._na_disku = copy.deepcopy(self.settings)
            return True
        except Exception as e:  # noqa: BLE001 - shranjevanje ne sme podreti brskalnika
            print(f"[Config] Napaka pri shranjevanju: {e}", flush=True)
            return False

    def get(self, key: str, default=None):
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        # Dodelitev in zapis pod istim zaklepom niti: sicer ju zapis druge niti (zdruzi_in_zapisi prevzame kljuce z
        # diska) lahko loci in vrednost se izgubi (neodvisni pregled 1.0.129).
        with shramba_json.ZAKLEP_NITI:
            self.settings[key] = value
            return self.save_settings()

    def _povecaj(self, kljuc: str, n: int) -> bool:
        """Stevec povecaj na vrednosti z diska pod zaklepom (shramba_json.zdruzi_in_zapisi, pristej): stejeta ga
        Safeer OS in Safeer Browser - povecanje iz stare kopije v pomnilniku bi prepisalo stetje drugega procesa."""
        try:
            n = int(n)
        except (TypeError, ValueError):
            return False
        if n <= 0:
            return False
        with shramba_json.ZAKLEP_NITI:
            try:
                os.makedirs(self.config_dir, exist_ok=True)
                self._na_disku = shramba_json.zdruzi_in_zapisi(self.config_file, self.settings,
                                                               getattr(self, "_na_disku", {}), indent=4,
                                                               pristej={kljuc: n})
                return True
            except Exception as e:  # noqa: BLE001 - shranjevanje ne sme podreti brskalnika
                print(f"[Config] Napaka pri shranjevanju: {e}", flush=True)
                return False

    def increment_ads_blocked(self, count: int = 1):
        """Increments the cumulative blocked ads counter and saves settings."""
        self._povecaj("total_ads_blocked", count)

    def increment_threats_blocked(self, count: int = 1):
        """Increments the cumulative blocked threats counter and saves settings."""
        self._povecaj("total_threats_blocked", count)

    def toggle_virtual_keyboard(self) -> bool:
        new_state = not self.settings.get("virtual_keyboard_enabled", False)
        self.settings["virtual_keyboard_enabled"] = new_state
        self.save_settings()
        return new_state

    def toggle_force_dark(self) -> bool:
        """Trajno vklopi ali izklopi prisilni temni način za vse spletne strani."""
        cur = self.settings.get("force_dark_mode", True)
        self.settings["force_dark_mode"] = not cur
        self.save_settings()
        return not cur

    def toggle_sidebar_permanent(self) -> bool:
        """Trajno vklopi ali izklopi prikaz stranske vrstice."""
        cur = self.settings.get("sidebar_enabled", True)
        self.settings["sidebar_enabled"] = not cur
        self.save_settings()
        return not cur

    def toggle_integration(self, integration_id: str) -> bool:
        if "integrations" in self.settings and integration_id in self.settings["integrations"]:
            cur = self.settings["integrations"][integration_id].get("enabled", True)
            self.settings["integrations"][integration_id]["enabled"] = not cur
            self.save_settings()
            return not cur
        return False

    def add_integration(self, name: str, url: str, icon: str = "🌐") -> str:
        """Doda poljubno novo spletno stran v stransko orodno vrstico."""
        if not name or not url:
            return ""
        norm_url = normalize_web_url(url)
        if not norm_url:
            return ""

        item_id = "custom_" + str(uuid.uuid4())[:8]
        if "integrations" not in self.settings:
            self.settings["integrations"] = {}

        self.settings["integrations"][item_id] = {
            "name": name.strip(),
            "url": norm_url,
            "icon": icon.strip() if icon.strip() else "🌐",
            "enabled": True,
            "color": "#00d2ff"
        }
        self.save_settings()
        return item_id

    def remove_integration(self, integration_id: str) -> bool:
        """Odstrani spletno stran iz stranske orodne vrstice."""
        if "integrations" in self.settings and integration_id in self.settings["integrations"]:
            del self.settings["integrations"][integration_id]
            self.save_settings()
            return True
        return False

    # --- Shramba vrednosti uporabniških skript (GM_getValue / GM_setValue) ---
    # Vsaka skripta ima svoj predal; ena skripta ne vidi vrednosti druge.

    NAJVEC_KLJUCEV = 200
    NAJVEC_BAJTOV = 64 * 1024

    def get_script_values(self, script_id: str) -> Dict[str, Any]:
        """Vrne shranjene vrednosti ene uporabniške skripte."""
        return dict(self.settings.get("user_script_values", {}).get(script_id, {}))

    def set_script_value(self, script_id: str, key: str, value: Any) -> bool:
        """
        Shrani eno vrednost uporabniške skripte.
        Vrednost pride iz spletne strani, zato je omejena po dolžini in številu.
        """
        if not script_id or not isinstance(key, str) or not key or len(key) > 200:
            return False
        try:
            if len(json.dumps(value, ensure_ascii=False)) > self.NAJVEC_BAJTOV:
                return False
        except (TypeError, ValueError):
            return False
        vse = self.settings.setdefault("user_script_values", {})
        predal = vse.setdefault(script_id, {})
        if key not in predal and len(predal) >= self.NAJVEC_KLJUCEV:
            return False
        predal[key] = value
        self.save_settings()
        return True

    def delete_script_value(self, script_id: str, key: str) -> bool:
        """Izbriše eno vrednost uporabniške skripte."""
        predal = self.settings.get("user_script_values", {}).get(script_id)
        if not predal or key not in predal:
            return False
        del predal[key]
        self.save_settings()
        return True

    def clear_script_values(self, script_id: str) -> None:
        """Pozabi vse vrednosti ene skripte (ob njenem izbrisu)."""
        vse = self.settings.get("user_script_values", {})
        if script_id in vse:
            del vse[script_id]
            self.save_settings()

    def get_user_scripts(self):
        """Vrne seznam vseh uporabniških skript."""
        return self.settings.get("user_scripts", [])

    def save_user_scripts(self, scripts):
        """Shrani posodobljen seznam uporabniških skript."""
        self.settings["user_scripts"] = scripts
        self.save_settings()

    def add_user_script(self, name: str, pattern: str, code: str, run_at: str = "end") -> str:
        """Doda novo uporabniško skripto."""
        script_id = "script_" + str(uuid.uuid4())[:8]
        new_script = {
            "id": script_id,
            "name": name.strip() or "Brez imena",
            "pattern": pattern.strip() or "*",
            "code": code,
            "enabled": True,
            "run_at": run_at
        }
        scripts = self.get_user_scripts()
        scripts.append(new_script)
        self.save_user_scripts(scripts)
        return script_id

    def update_user_script(self, script_id: str, name: str, pattern: str, code: str, enabled: bool, run_at: str = "end") -> bool:
        """Posodobi obstoječo uporabniško skripto."""
        scripts = self.get_user_scripts()
        for s in scripts:
            if s["id"] == script_id:
                s["name"] = name.strip()
                s["pattern"] = pattern.strip()
                s["code"] = code
                s["enabled"] = enabled
                s["run_at"] = run_at
                self.save_user_scripts(scripts)
                return True
        return False

    def delete_user_script(self, script_id: str) -> bool:
        """Izbriše uporabniško skripto."""
        scripts = self.get_user_scripts()
        new_scripts = [s for s in scripts if s["id"] != script_id]
        if len(new_scripts) != len(scripts):
            self.save_user_scripts(new_scripts)
            self.clear_script_values(script_id)
            return True
        return False

    def toggle_user_script(self, script_id: str) -> bool:
        """Vklopi ali izklopi uporabniško skripto."""
        scripts = self.get_user_scripts()
        for s in scripts:
            if s["id"] == script_id:
                s["enabled"] = not s.get("enabled", True)
                self.save_user_scripts(scripts)
                return s["enabled"]
        return False

    # -------------------------------------------------------------------------
    # Upravljanje Priljubljenih Strani in Portalov
    # -------------------------------------------------------------------------
    def get_portals(self):
        """Vrne seznam priljubljenih strani in portalov ter zagotovi enolične ID-je."""
        portals = self.get("custom_portals", [])

        modified = False
        seen_ids = set()
        for idx, p in enumerate(portals):
            curr_id = p.get("id")
            if not curr_id or curr_id in seen_ids:
                p["id"] = f"p_{idx}_{str(uuid.uuid4())[:8]}"
                modified = True
            seen_ids.add(p["id"])
            if not p.get("mark") or p.get("mark") == "🌐":
                if p.get("icon"):
                    p["mark"] = p.get("icon")
                    modified = True
                elif not p.get("mark"):
                    p["mark"] = "🌐"
                    modified = True

            p_url = (p.get("url") or "").strip()
            curr_title = (p.get("title") or "").strip()
            if not curr_title or curr_title == p_url:
                if p.get("name") and p.get("name").strip() != p_url:
                    p["title"] = p.get("name").strip()
                    modified = True
                elif not curr_title:
                    gost = gostitelj_bliznjice(p_url)
                    p["title"] = gost if gost else (prikazni_naslov(p_url) or "Priljubljena stran")
                    modified = True

        if modified:
            self.save_portals(portals)
        return portals

    def save_portals(self, portals):
        """Shrani seznam priljubljenih strani."""
        self.set("custom_portals", portals)

    def get_home_portals(self):
        """Bliznjice za zacetno stran: brez uvozenih zaznamkov (ti so v seznamu zaznamkov), sicer bi uvoz stotih
        zaznamkov iz drugega brskalnika preplavil zacetno stran (lastnik, 12. 10. 2026). Uvozeni imajo kljuc folder."""
        return [p for p in self.get_portals() if "folder" not in p and not p.get("uvozen")]

    def add_portal(self, title: str, url: str, mark: str = "🌐", bg: str = "", color: str = "#00d2ff") -> str:
        """Doda novo priljubljeno stran. Uporabnisko ime in geslo se odstranita (neodvisni pregled 1.0.131)."""
        norm_url = normalize_web_url(url)
        if not norm_url:
            return ""
        norm_url = prikazni_naslov(norm_url)
        cist_title = prikazni_naslov(title) if title.startswith(("http://", "https://")) else title
        p_id = "p_" + str(uuid.uuid4())[:8]
        if not bg:
            bg = f"linear-gradient(145deg, #091a28, {color})"
        new_portal = {
            "id": p_id,
            "title": cist_title.strip() or gostitelj_bliznjice(norm_url) or "Priljubljena stran",
            "url": norm_url,
            "mark": mark.strip() or "🌐",
            "bg": bg,
            "color": color
        }
        portals = self.get_portals()
        portals.append(new_portal)
        self.save_portals(portals)
        return p_id

    def update_portal(self, portal_id: str, title: str, url: str, mark: str, bg: str = "", color: str = "") -> bool:
        """Posodobi obstoječo priljubljeno stran. Uporabnisko ime in geslo se odstranita."""
        norm_url = normalize_web_url(url)
        if not norm_url:
            return False
        norm_url = prikazni_naslov(norm_url)
        cist_title = prikazni_naslov(title) if title.startswith(("http://", "https://")) else title
        portals = self.get_portals()
        for p in portals:
            if p.get("id") == portal_id:
                p["title"] = cist_title.strip() or gostitelj_bliznjice(norm_url) or "Priljubljena stran"
                p["url"] = norm_url
                p["mark"] = mark.strip()
                if color:
                    p["color"] = color
                if bg:
                    p["bg"] = bg
                elif color:
                    p["bg"] = f"linear-gradient(145deg, #091a28, {color})"
                self.save_portals(portals)
                return True
        return False

    def delete_portal(self, portal_id: str) -> bool:
        """Izbriše priljubljeno stran glede na ID ali URL."""
        if not portal_id:
            return False
        portals = self.get_portals()
        new_portals = [p for p in portals if p.get("id") != portal_id and p.get("url") != portal_id]
        if len(new_portals) != len(portals):
            self.save_portals(new_portals)
            return True
        return False

    def move_portal_up(self, portal_id: str) -> bool:
        """Premakne priljubljeno stran eno mesto navzgor."""
        if not portal_id:
            return False
        portals = self.get_portals()
        for idx, p in enumerate(portals):
            if p.get("id") == portal_id and idx > 0:
                portals[idx], portals[idx - 1] = portals[idx - 1], portals[idx]
                self.save_portals(portals)
                return True
        return False

    def move_portal_down(self, portal_id: str) -> bool:
        """Premakne priljubljeno stran eno mesto navzdol."""
        if not portal_id:
            return False
        portals = self.get_portals()
        for idx, p in enumerate(portals):
            if p.get("id") == portal_id and idx < len(portals) - 1:
                portals[idx], portals[idx + 1] = portals[idx + 1], portals[idx]
                self.save_portals(portals)
                return True
        return False

    def reset_portals(self):
        """Ponastavi priljubljene strani na privzete."""
        default_p = [dict(p) for p in DEFAULT_SETTINGS["custom_portals"]]
        self.save_portals(default_p)
        return default_p

    def import_bookmarks_items(self, items: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Doda seznam zaznamkov med priljubljene portale, prepreči podvajanje in shrani.
        Vrne (dodani_zaznamki, preskoceni_duplikati).
        """
        if not items:
            return 0, 0

        portals = self.get_portals()
        existing_urls = {re.sub(r"/+$", "", p.get("url", "").strip()).lower() for p in portals if p.get("url")}

        added_count = 0
        skipped_count = 0

        for item in items:
            u = item.get("url", "").strip()
            norm_key = re.sub(r"/+$", "", u).lower()
            if norm_key in existing_urls:
                skipped_count += 1
                continue
            p_id = "p_" + str(uuid.uuid4())[:8]
            portals.append({
                "id": p_id,
                "title": item.get("title", "").strip() or "Uvožen zaznamek",
                "url": u,
                "mark": item.get("mark", "🌐"),
                "bg": item.get("bg", f"linear-gradient(145deg, #091a28, {item.get('color', '#00d2ff')})"),
                "color": item.get("color", "#00d2ff"),
                "domain": item.get("domain", ""),
                "favicon": item.get("favicon", ""),
                "folder": item.get("folder", ""),
                "uvozen": True
            })
            existing_urls.add(norm_key)
            added_count += 1

        if added_count > 0:
            self.save_portals(portals)
        return added_count, skipped_count

    def import_bookmarks_from_html(self, file_path: str) -> int:
        """
        Uvozi zaznamke iz izvožene HTML datoteke (Firefox, Chrome, Brave, Edge itd.).
        Prepreči podvajanje obstoječih povezav in shrani v konfiguracijo.
        Vrne število na novo dodanih zaznamkov.
        """
        try:
            from core.bookmarks_importer import parse_bookmarks_html
            items = parse_bookmarks_html(file_path)
            added, _ = self.import_bookmarks_items(items)
            return added
        except Exception as e:
            print(f"[ConfigManager] Napaka pri uvozu zaznamkov iz HTML: {e}")
            return 0

    def auto_import_from_browser(self, browser_type: str = "all") -> Dict[str, Any]:
        """
        Samodejno uvozi zaznamke neposredno iz profilov nameščenih brskalnikov.
        browser_type: 'all', 'firefox', 'chrome', 'brave'
        Vrne slovar z rezultati: {'added': int, 'skipped': int, 'total': int, 'stats': dict}
        """
        try:
            from core.bookmarks_importer import (
                auto_import_all_profiles,
                import_from_firefox_profiles,
                import_from_chromium_profiles
            )
            if browser_type == "firefox":
                items = import_from_firefox_profiles()
                stats = {"Firefox": len(items)}
            elif browser_type in ["chrome", "brave", "chromium"]:
                items = import_from_chromium_profiles()
                stats = {"Chrome/Brave": len(items)}
            else:
                items, stats = auto_import_all_profiles()

            added, skipped = self.import_bookmarks_items(items)
            return {
                "added": added,
                "skipped": skipped,
                "total": len(items),
                "stats": stats
            }
        except Exception as e:
            print(f"[ConfigManager] Napaka pri samodejnem uvozu: {e}")
            return {"added": 0, "skipped": 0, "total": 0, "stats": {}}

