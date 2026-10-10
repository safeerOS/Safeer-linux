"""Spletni katalog za domaci Safeer Player (GTK, brez WebKita): izbire in podatki brez GTK.

Isti katalog kot stran Safeer OS (core/os_katalog.Katalog, metoda mediaKatalog): iste kategorije, filmske zvrsti,
zvrsti glasbe/radia, jezik vsebine in razvrstitev. Tu je samo logika (preizkusi jo brez zaslona); okno je v
core/os_player_gtk.py.

Plakati: najvec STEVILO_NITI hkratnih prenosov, samo https, najvec NAJVEC_BAJTOV na sliko, predpomnilnik zadnjih
NAJVEC_V_PREDPOMNILNIKU slik v pomnilniku (velik katalog ne sme rasti RAM brez meje).
"""
from __future__ import annotations

import threading
import urllib.parse
import urllib.request
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from core import izvirni_jezik, zakoniti_viri

#: (vrsta za mediaKatalog, napis) - enako kot KAT_VRSTE v assets/os/os.js.
KATEGORIJE: tuple = (("vse", "Vse"), ("film", "Filmi"), ("serija", "Serije"), ("video", "Video"),
                     ("glasba", "Glasba"), ("radio", "Radio"), ("tv-v-zivo", "TV v živo"))

#: Filmske zvrsti (TMDB id) - enako kot KAT_FILMSKI_ZANRI v assets/os/os.js.
FILMSKE_ZVRSTI: tuple = (("28", "Akcija"), ("878", "Znanstvena fantastika"), ("35", "Komedija"),
                         ("27", "Grozljivka"), ("18", "Drama"), ("53", "Triler"), ("16", "Animirani"),
                         ("10749", "Romantika"))

#: Razvrstitve - enako kot os_media.MediaCenter.RAZVRSTITVE.
RAZVRSTITVE: tuple = (("", "Priporočeno"), ("novo", "Leto izida: najnovejše"), ("staro", "Leto izida: najstarejše"),
                      ("az", "Po abecedi A–Ž"), ("za", "Po abecedi Ž–A"))

#: Slovenska imena jezikov vsebine (kode iz core/izvirni_jezik.KODE; manjkajoce ime = koda).
IMENA_JEZIKOV: dict = {
    "sl": "Slovenščina", "en": "Angleščina", "de": "Nemščina", "fr": "Francoščina", "es": "Španščina",
    "it": "Italijanščina", "pt": "Portugalščina", "hr": "Hrvaščina", "sr": "Srbščina", "bs": "Bosanščina",
    "mk": "Makedonščina", "ru": "Ruščina", "pl": "Poljščina", "cs": "Češčina", "sk": "Slovaščina",
    "hu": "Madžarščina", "nl": "Nizozemščina", "sv": "Švedščina", "da": "Danščina", "no": "Norveščina",
    "fi": "Finščina", "is": "Islandščina", "tr": "Turščina", "el": "Grščina", "ro": "Romunščina",
    "bg": "Bolgarščina", "sq": "Albanščina", "uk": "Ukrajinščina", "ja": "Japonščina", "ko": "Korejščina",
    "zh": "Kitajščina", "hi": "Hindijščina", "ta": "Tamilščina", "te": "Telugijščina", "th": "Tajščina",
    "ar": "Arabščina", "he": "Hebrejščina", "fa": "Perzijščina",
}

NA_STRAN = 24
STEVILO_NITI = 4
NAJVEC_BAJTOV = 2 * 1024 * 1024
NAJVEC_V_PREDPOMNILNIKU = 120
CAS_PRENOSA = 8


def skupina_zvrsti(vrsta: str) -> str:
    """Katere zvrsti pokazemo pod kategorijo (kot skupinaZanrov v os.js): "film", "glasba", "radio",
    "tv-v-zivo" ali "" (brez izbire zvrsti)."""
    if vrsta in ("film", "serija", "vse"):
        return "film"
    if vrsta in ("glasba", "radio", "tv-v-zivo"):
        return vrsta
    return ""


def jezik_velja(vrsta: str) -> bool:
    """Ali ima izbira jezika vsebine pri tej kategoriji smisel (kot jezikVelja v os.js)."""
    return vrsta in ("vse", "film", "serija", "video", "glasba")


def zvrsti(vrsta: str, katalog=None) -> list:
    """[(id, ime)] za izbiro zvrsti; prvi je vedno ("", "Vse ...")."""
    skupina = skupina_zvrsti(vrsta)
    if not skupina:
        return []
    prvi = {"radio": "Vse postaje", "tv-v-zivo": "Vse države", "glasba": "Vsa glasba"}.get(skupina, "Vse vsebine")
    if skupina == "film":
        return [("", prvi)] + list(FILMSKE_ZVRSTI)
    try:
        if katalog is not None:
            seznam = katalog.izvedi("mediaZvrsti", [skupina])
        else:
            seznam = zakoniti_viri.zvrsti_za(skupina)
    except Exception:
        seznam = []
    return [("", prvi)] + [(str(z.get("id") or ""), str(z.get("ime") or z.get("id") or ""))
                           for z in (seznam or []) if isinstance(z, dict) and z.get("id")]


def jeziki(vmesnik: str = "sl") -> list:
    """[(koda, ime)]: najprej »Vsi jeziki«, nato jezik vmesnika in anglescina, ostali po abecedi imen."""
    kode = [k for k in izvirni_jezik.KODE]
    prvi = [k for k in dict.fromkeys([vmesnik, "en"]) if k in kode]
    ostali = sorted((k for k in kode if k not in prvi), key=lambda k: IMENA_JEZIKOV.get(k, k))
    return [("", "Vsi jeziki")] + [(k, IMENA_JEZIKOV.get(k, k)) for k in prvi + ostali]


def argumenti(iskanje: str = "", vrsta: str = "vse", zvrst: str = "", stran: int = 1, razvrsti: str = "",
              jezik: str = "") -> list:
    """Argumenti za Katalog.izvedi("mediaKatalog", ...) - isti vrstni red kot klic na strani (os.js)."""
    vrsta = vrsta if vrsta in dict(KATEGORIJE) else "vse"
    razvrsti = razvrsti if razvrsti in dict(RAZVRSTITVE) else ""
    jezik = jezik if (jezik in izvirni_jezik.KODE and jezik_velja(vrsta)) else ""
    return [str(iskanje or "")[:120], vrsta, str(zvrst or "")[:40], max(1, int(stran or 1)), razvrsti, [], False, [],
            jezik]


def _ikona(vrsta: str) -> str:
    """Ikona teme (freedesktop) za kartico brez plakata - emoji brez pisave z emoji ne bi bili vidni."""
    return {"glasba": "audio-x-generic", "podcast": "audio-x-generic", "radio": "audio-x-generic",
            "tv-v-zivo": "video-display", "tv": "video-display"}.get(vrsta, "video-x-generic")


def kartica(item: dict) -> dict:
    """Kar kartica v mrezi pokaze: naslov, podnaslov (leto · vir ali izvajalec), plakat, ikona, id."""
    vrsta = str(item.get("vrsta") or "")
    deli = []
    izvajalec = item.get("izvajalec")
    if izvajalec and str(izvajalec) != "None":
        deli.append(str(izvajalec))
    if item.get("leto"):
        deli.append(str(item["leto"])[:4])
    if vrsta == "tv-v-zivo":
        deli.append("V ŽIVO")
    elif item.get("vir") and not izvajalec:
        deli.append(str(item["vir"]).split(" · ")[0])
    slika = str(item.get("slika") or "")
    return {"id": str(item.get("id") or ""), "naslov": str(item.get("naslov") or "Brez naslova")[:200],
            "podnaslov": " · ".join(deli)[:120], "slika": slika if slika.startswith("https://") else "",
            "ikona": _ikona(vrsta), "vrsta": vrsta}


def strani(rezultat: dict) -> int:
    try:
        return max(1, int((rezultat or {}).get("skupaj_strani") or 1))
    except (TypeError, ValueError):
        return 1


def prenesi_sliko(url: str, odpri=urllib.request.urlopen) -> Optional[bytes]:
    """Plakat (samo https, najvec NAJVEC_BAJTOV). None ob napaki ali preveliki sliki."""
    if not str(url or "").startswith("https://") or not urllib.parse.urlsplit(url).hostname:
        return None
    try:
        zahteva = urllib.request.Request(url, headers={"User-Agent": "SafeerPlayer/1"})
        with odpri(zahteva, timeout=CAS_PRENOSA) as odgovor:
            podatki = odgovor.read(NAJVEC_BAJTOV + 1)
    except Exception:
        return None
    return podatki if podatki and len(podatki) <= NAJVEC_BAJTOV else None


class Plakati:
    """Prenos plakatov v ozadju z omejenim predpomnilnikom. gotovo(url, bajti_ali_None) se poklice v niti prenosa;
    okno ga prestavi v glavno nit (GLib.idle_add)."""

    def __init__(self, prenesi: Callable[[str], Optional[bytes]] = prenesi_sliko,
                 najvec: int = NAJVEC_V_PREDPOMNILNIKU) -> None:
        self._prenesi = prenesi
        self._najvec = max(1, int(najvec))
        self._shramba: "OrderedDict[str, bytes]" = OrderedDict()
        self._zaklep = threading.Lock()
        self._izvajalec: Optional[ThreadPoolExecutor] = None
        self.rod = 0          # nov pogled kataloga poveca rod: stari prenosi ne risejo vec

    def v_predpomnilniku(self, url: str) -> Optional[bytes]:
        with self._zaklep:
            podatki = self._shramba.get(url)
            if podatki is not None:
                self._shramba.move_to_end(url)
            return podatki

    def _shrani(self, url: str, podatki: bytes) -> None:
        with self._zaklep:
            self._shramba[url] = podatki
            self._shramba.move_to_end(url)
            while len(self._shramba) > self._najvec:
                self._shramba.popitem(last=False)

    def zahtevaj(self, url: str, gotovo: Callable[[str, Optional[bytes], int], None]) -> None:
        rod = self.rod
        podatki = self.v_predpomnilniku(url)
        if podatki is not None:
            gotovo(url, podatki, rod)
            return
        if self._izvajalec is None:
            self._izvajalec = ThreadPoolExecutor(max_workers=STEVILO_NITI, thread_name_prefix="safeer-plakat")

        def delo() -> None:
            if rod != self.rod:
                return                     # uporabnik je medtem zamenjal pogled
            p = self._prenesi(url)
            if p is not None:
                self._shrani(url, p)
            gotovo(url, p, rod)

        self._izvajalec.submit(delo)

    def ustavi(self) -> None:
        self.rod += 1
        if self._izvajalec is not None:
            self._izvajalec.shutdown(wait=False, cancel_futures=True)
            self._izvajalec = None
