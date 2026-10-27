"""Shema settings.json Safeer Browserja in Spleta (nacrt stabilnosti P2, naloga 43, 21. 10. 2026).

settings.json je bil brez razlicice in preverjanja. Napacen tip (npr. "splet_predpomnilnik_meja_mb": "veliko") je podrl
Splet ob int(...); seznam zaznamkov z nizom namesto slovarja je vrgel napako v selitvi in preskocil vse selitve. Zdaj ima
vsak kljuc, ki ga koda bere, tip in obseg; napacna vrednost v pomnilniku dobi privzeto (ali izgine, da velja privzeta
vrednost v kodi) in gre v dnevnik. Na disku ostane, dokler je uporabnik ne spremeni (nic se ne brise). Neznani kljuci
(prihodnje razlicice, drugi programi) ostanejo.

Nalaga in pise samo core/config.ConfigManager (z DEFAULT_SETTINGS). Ta modul je brez kode brskalnika (samo standardna
knjiznica): Safeer Control in Safeer OS z njim bereta en kljuc (preberi_kljuc), varuh procesov pa ne (glej varuh_procesov.jezik).
"""
from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict, List, Optional

#: Razlicica oblike settings.json. Datoteka brez kljuca je razlicica 0 (do 1.0.132).
SCHEMA_VERSION = 1
KLJUC_RAZLICICE = "schema_version"


class Polje:
    """Tip in obseg enega kljuca. `elementi`: tip elementov seznama ali vrednosti slovarja (napacni se izpustijo)."""

    __slots__ = ("tip", "najmanj", "najvec", "izbira", "elementi", "dolzina")

    def __init__(self, tip, najmanj=None, najvec=None, izbira=None, elementi=None, dolzina=None) -> None:
        self.tip, self.najmanj, self.najvec, self.izbira = tip, najmanj, najvec, izbira
        self.elementi, self.dolzina = elementi, dolzina

    def ustreza(self, v: Any) -> bool:
        if self.tip is bool:
            return isinstance(v, bool)
        if self.tip is int:
            if isinstance(v, bool) or not isinstance(v, int):
                return False
            return (self.najmanj is None or v >= self.najmanj) and (self.najvec is None or v <= self.najvec)
        if not isinstance(v, self.tip):
            return False
        if self.izbira is not None and v not in self.izbira:
            return False
        if self.dolzina is not None and len(v) > self.dolzina:
            return False
        return True

    def ocisti(self, v: Any) -> Any:
        """Seznam/slovar brez napacnih elementov (kopija) ali v sam."""
        if self.elementi is None:
            return v
        if isinstance(v, list):
            return [e for e in v if isinstance(e, self.elementi)]
        if isinstance(v, dict):
            return {k: e for k, e in v.items() if isinstance(k, str) and isinstance(e, self.elementi)}
        return v


_NIZ = Polje(str, dolzina=100_000)
_DA_NE = Polje(bool)
_SEKUNDE = Polje(int, 0, 7 * 86400)
_STEVEC = Polje(int, 0)
_MB = Polje(int, 0, 1 << 20)

#: Vsi kljuci settings.json, ki jih bere koda (grep .get("...")/.set("...") na 08d2234: core/config, os_splet,
#: safeer_brskalnik, safeer_link, dovoljenja_strani, zascita, uporabniske_skripte, safeer_os). Izbire samo, kjer jih
#: koda omejuje sama (sicer bi nova vrednost novejse razlicice veljala za napacno).
SHEMA: Dict[str, Polje] = {
    KLJUC_RAZLICICE: Polje(int, 0),
    "language": Polje(str, dolzina=16),
    "ui_language": Polje(str, dolzina=16),
    "force_dark_mode": _DA_NE,
    "theme": Polje(str, dolzina=64),
    "custom_css": _NIZ,
    "user_scripts": Polje(list, elementi=dict),
    "user_script_values": Polje(dict, elementi=dict),
    "virtual_keyboard_enabled": _DA_NE,
    "sidebar_enabled": _DA_NE,
    "sidebar_width": Polje(int, 120, 8192),
    "search_engine": Polje(str, dolzina=64),
    "adblock_enabled": _DA_NE,
    "easylist_enabled": _DA_NE,
    "adguard_protection_enabled": _DA_NE,
    "sleep_heavy_background_tabs": _DA_NE,
    "tab_freeze_after_s": _SEKUNDE,
    "tab_discard_after_s": _SEKUNDE,
    "network_process_limit_mb": _MB,
    "tracking_protection_enabled": _DA_NE,
    "gpc_dnt_enabled": _DA_NE,
    "doh_enabled": _DA_NE,
    "doh_provider": Polje(str, dolzina=64),
    "custom_doh_url": Polje(str, dolzina=2048),
    "scit_naprej": Polje(str, dolzina=64),
    "scit_naprej_po_meri": Polje(str, dolzina=2048),
    "dns_rezerva": _DA_NE,
    "dns_scit_selitev": _DA_NE,
    "dns_izbira_uporabnika": _DA_NE,
    "doh_lokalno_omrezje": _DA_NE,
    "secure_proxy_mode": Polje(str, izbira=("disabled", "custom")),
    "secure_proxy_url": Polje(str, dolzina=2048),
    "ostanki_preizkusov_pregledani": Polje(bool),
    "total_ads_blocked": _STEVEC,
    "total_threats_blocked": _STEVEC,
    "hardware_acceleration": Polje(str, izbira=("on_demand", "always", "never")),
    "permissions_policy": Polje(str, izbira=("ask", "allow", "deny")),
    "always_ask_download_dir": _DA_NE,
    "homepage": Polje(str, dolzina=8192),
    "integrations": Polje(dict, elementi=dict),
    "integrations_katalog": Polje(list, elementi=str),
    "custom_portals": Polje(list, elementi=dict),
    "default_bookmarks_removed": _DA_NE,
    # Spletni pogled in zasebnost (core/os_splet.py)
    "developer_extras_enabled": _DA_NE,
    "popup_blokiraj": _DA_NE,
    "popup_dovoljeni": Polje(list, elementi=str),
    "splet_skrite_bliznjice": Polje(list, elementi=str),
    "splet_brez_privzetih": _DA_NE,
    "splet_brez_pospesevanja": Polje(list),
    "splet_predpomnilnik_meja_mb": _MB,
    "splet_kompozitor_v": _STEVEC,
    "splet_gpu_dom": _DA_NE,
    "splet_skia_kompozitor": _DA_NE,
    "external_app_permissions": Polje(dict),
    "brisi_ob_izhodu": Polje(list, elementi=str),
    "brisi_obdobje": Polje(str, izbira=("ura", "dan", "teden", "vse")),
    "brisi_vrste": Polje(list, elementi=str),
    "zascita_izjeme": Polje(list, elementi=str),
    "zascita_itp": _DA_NE,
    "zascita_brez_webrtc": _DA_NE,
    "temno_nacin": Polje(str, izbira=("izklop", "samodejno", "vedno")),
    "temno_izjeme": Polje(list, elementi=str),
    "dovoljenja_strani": Polje(dict, elementi=dict),
    "dovoljenja_privzeto": Polje(dict),
    "samodejno_predvajanje": Polje(str, izbira=("dovoli", "brez_zvoka", "blokiraj")),
    # Safeer Browser (safeer_brskalnik.py) in Link (core/safeer_link.py)
    "splet_seja": Polje(list),
    "splet_seja_izbran": _STEVEC,
    "check_default_browser": _DA_NE,
    "sync_bookmarks": _DA_NE,
    "sync_bookmarks_version": _STEVEC,
}


def uveljavi_shemo(nastavitve: Dict[str, Any], privzete: Dict[str, Any], tiho: bool = False) -> List[str]:
    """Popravi `nastavitve` na mestu: napacen tip ali obseg -> privzeta vrednost (kljuc iz `privzete`, v brskalniku
    config.DEFAULT_SETTINGS) ali brez kljuca (koda vzame svojo privzeto); napacni elementi seznamov in slovarjev
    izpadejo. Neznani kljuci ostanejo.
    Vrne popravljene kljuce (v dnevnik, razen tiho=True)."""
    popravljeni = []
    for kljuc, polje in SHEMA.items():
        if kljuc not in nastavitve:
            continue
        v = nastavitve[kljuc]
        if polje.ustreza(v):
            cisto = polje.ocisti(v)
            if cisto is not v and cisto != v:
                nastavitve[kljuc] = cisto
                popravljeni.append(kljuc)
            continue
        if kljuc in privzete:
            nastavitve[kljuc] = copy.deepcopy(privzete[kljuc])
        else:
            del nastavitve[kljuc]
        popravljeni.append(kljuc)
    if popravljeni and not tiho:
        # Samo imena kljucev in tipi: vrednost je lahko osebna (naslov, skripta).
        print("[Config] Nastavitve z napacnim tipom ali obsegom (velja privzeto): %s" % ", ".join(popravljeni),
              flush=True)
    return popravljeni


def _selitev_1(nastavitve: Dict[str, Any]) -> None:
    """0 -> 1: uvedba sheme (razlicica v datoteki). Vsebina ostane; preverjanje tipov je v uveljavi_shemo."""


#: Selitve po razlicicah: SELITVE[n] preseli razlicico n-1 v n. Pred prvo selitvijo varnostna kopija
#: settings.json.v<stara>.bak (enkrat na razlicico, atomsko).
SELITVE: Dict[int, Any] = {1: _selitev_1}


def razlicica_datoteke(podatki: Dict[str, Any]) -> int:
    v = podatki.get(KLJUC_RAZLICICE, 0)
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def varnostna_kopija(pot: str, razlicica: int) -> Optional[str]:
    """Bajti datoteke v <pot>.v<razlicica>.bak (atomsko, 0600); obstojece kopije ne prepise. Vrne pot ali None."""
    kopija = "%s.v%d.bak" % (pot, razlicica)
    if os.path.exists(kopija):
        return kopija
    zacasna = kopija + ".tmp"
    try:
        with open(pot, "rb") as vir:
            vsebina = vir.read()
        fd = os.open(zacasna, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as cilj:
            cilj.write(vsebina)
            cilj.flush()
            os.fsync(cilj.fileno())
        os.replace(zacasna, kopija)
        return kopija
    except OSError as e:
        print("[Config] Varnostne kopije nastavitev ni bilo mogoce narediti: %s" % type(e).__name__, flush=True)
        try:
            os.unlink(zacasna)
        except OSError as e2:
            print("[Config] zacasna kopija ostala: %s" % type(e2).__name__, flush=True)
        return None


def preseli_razlicico(nastavitve: Dict[str, Any], stara: int) -> bool:
    """Selitve stara+1 .. SCHEMA_VERSION na mestu. Novejse razlicice (drug, novejsi program) ne znizamo. True ob selitvi."""
    if stara >= SCHEMA_VERSION:
        if stara > SCHEMA_VERSION:
            nastavitve[KLJUC_RAZLICICE] = stara
        return False
    for n in range(stara + 1, SCHEMA_VERSION + 1):
        SELITVE[n](nastavitve)
        nastavitve[KLJUC_RAZLICICE] = n
    return True


def preberi_kljuc(kljuc: str, privzeto: Any, pot: str) -> Any:
    """En kljuc iz settings.json brez ConfigManager: datoteke ne ustvari, ne seli in ne pise (Safeer OS in Control
    bereta jezik in iskalnik brskalnika, ki morda ni namescen). Vrednost z napacnim tipom ali obsegom (SHEMA) -> privzeto."""
    try:
        with open(pot, "r", encoding="utf-8") as f:
            podatki = json.load(f)
    except (OSError, ValueError):
        return privzeto
    if not isinstance(podatki, dict) or kljuc not in podatki:
        return privzeto
    v = podatki[kljuc]
    polje = SHEMA.get(kljuc)
    if polje is not None and not polje.ustreza(v):
        return privzeto
    return v


__all__ = ["SCHEMA_VERSION", "KLJUC_RAZLICICE", "Polje", "SHEMA", "SELITVE", "uveljavi_shemo",
           "razlicica_datoteke", "varnostna_kopija", "preseli_razlicico", "preberi_kljuc"]
