#!/usr/bin/env python3
"""
Safeer Browser for Linux Mint - Configuration Manager
Manages user preferences, modular sidebar integrations, and virtual keyboard settings.
"""

import os
import copy
import re
import json
import uuid
import time
import urllib.parse
from typing import Dict, Any, List, Tuple

from core import shramba_json


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
_IPV4 = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def je_spletni_naslov(besedilo: str) -> bool:
    """Ali je vpis v naslovno vrstico spletni naslov (True) ali iskanje (False) - kot v sodobnih brskalnikih.

    Lastnik 21. 10. 2026: v Spletu je »test« odprl https://test/ (»Strani trenutno ni mogoče odpreti«) namesto iskanja;
    normalize_web_url iz vsake besede brez dvopicja naredi naslov, tudi iz »vreme ljubljana«. Naslov je: shema http(s),
    localhost, IP, gostitelj z vrati ali gostitelj s piko in vrhnjo domeno iz crk (ne stevilka, ne koncnica datoteke).
    Iskanje je: ena beseda brez pike, vse s presledkom, »python 3.12«, »racun.pdf«, vpis, ki se zacne z »?«."""
    s = (besedilo or "").strip()
    if not s or s.startswith("?") or any(c.isspace() for c in s):
        return False
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):(//)?", s)
    if m and m.group(2):
        return m.group(1).lower() in ("http", "https")
    gostitelj = re.split(r"[/?#]", s, 1)[0]
    if "@" in gostitelj:
        return False                                   # »ime@posta.si« ni naslov strani
    if gostitelj.startswith("["):                      # [IPv6]:vrata
        return gostitelj.find("]") > 1
    ime, _, vrata = gostitelj.partition(":")
    if vrata:
        return vrata.isdigit() and bool(ime)           # localhost:8080, test:3000, 192.168.0.1:8080
    if ime.lower() == "localhost" or _IPV4.match(ime):
        return True
    deli = ime.rstrip(".").split(".")
    if len(deli) < 2 or not all(deli):
        return False
    vrh = deli[-1].lower()
    if vrh.startswith("xn--"):
        return len(vrh) > 4
    return len(vrh) >= 2 and vrh.isalpha() and vrh not in _KONCNICE_NE_DOMENE


def naslov_ali_iskanje(besedilo: str, iskalnik_url: str) -> str:
    """Naslov za vpis v naslovno vrstico: spletni naslov ali stran rezultatov izbranega iskalnika."""
    s = (besedilo or "").strip()
    if not s:
        return ""
    if je_spletni_naslov(s):
        # [IPv6]:vrata: normalize_web_url deli pri prvem dvopicju in ga ne pozna
        naslov = ("http://" + s) if s.startswith("[") else normalize_web_url(s)
        if naslov:
            return naslov
    return iskalnik_url + urllib.parse.quote_plus(s[1:].strip() if s.startswith("?") else s)


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


class ConfigManager:
    def __init__(self):
        self.config_dir = CONFIG_DIR
        self.config_file = CONFIG_FILE
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
                    if migrated:
                        self.save_settings(merged)
                    else:
                        # Primerjava za naslednji zapis: stanje ob nalaganju (s privzetimi). Privzeta vrednost, ki je ta
                        # proces ni spremenil, ne sme prekriti izbire, ki jo drug proces medtem zapise.
                        self._na_disku = copy.deepcopy(merged)
                    return merged
                except Exception as e:  # noqa: BLE001 - napaka v selitvi ne sme izbrisati uporabnikovih nastavitev
                    print(f"[Config] Napaka pri selitvi nastavitev: {e}")
                    merged = copy.deepcopy(DEFAULT_SETTINGS)
                    merged.update(copy.deepcopy(user_settings))
                    self._na_disku = copy.deepcopy(merged)
                    return merged

        self._na_disku = {}
        nove = copy.deepcopy(DEFAULT_SETTINGS)
        dodaj_katalog_integracijam(nove)
        self.save_settings(copy.deepcopy(nove))
        return nove

    def save_settings(self, settings: Dict[str, Any] = None) -> bool:
        """Zapise kljuce, ki so se v tem procesu spremenili, na trenutno vsebino datoteke (pod zaklepom, atomsko).
        Kljuce, ki jih je medtem spremenil drug proces, prevzame tudi v pomnilnik."""
        if settings is not None:
            self.settings = settings
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            self._na_disku = shramba_json.zdruzi_in_zapisi(self.config_file, self.settings,
                                                           getattr(self, "_na_disku", {}), indent=4)
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
                    try:
                        parsed = urllib.parse.urlparse(p_url)
                        netloc = parsed.netloc.replace("www.", "")
                        p["title"] = netloc if netloc else p_url
                    except Exception:
                        p["title"] = p_url or "Priljubljena stran"
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
        """Doda novo priljubljeno stran."""
        norm_url = normalize_web_url(url)
        if not norm_url:
            return ""
        p_id = "p_" + str(uuid.uuid4())[:8]
        if not bg:
            bg = f"linear-gradient(145deg, #091a28, {color})"
        new_portal = {
            "id": p_id,
            "title": title.strip() or "Priljubljena stran",
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
        """Posodobi obstoječo priljubljeno stran."""
        norm_url = normalize_web_url(url)
        if not norm_url:
            return False
        portals = self.get_portals()
        for p in portals:
            if p.get("id") == portal_id:
                p["title"] = title.strip()
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

