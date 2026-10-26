"""Lastni vgrajeni viri Medijskega centra (lastnik, 15. 10. 2026).

Safeer uporabnika ne omejuje na doloceno vsebino: vgradi (iframe) lahko katerokoli stran ali svojo komponento React,
Safeer da samo orodje, Scit (oglasi, botneti, zlonamerne strani) pa ga varuje ne glede na stran. Safeer NE prinasa
nobenega vnaprej nastavljenega vira tretje osebe: seznam je ob namestitvi prazen, vsak vnos doda uporabnik sam in ga
uporablja na lastno odgovornost (obvestilo potrdi ob prvem viru).

Tri vrste vnosa, en mehanizem:
  - stran ali predloga naslova (Basic IFrame Integration, tudi aplikacija Next.js na svojem naslovu): {imdb}, {tmdb},
    {tvdb}, {type}, {season}, {episode}, {title}, {year}; vrednosti so kodirane (quote), predloge v gostitelju ni;
  - komponenta React (prilepljena koda JSX/JS): tece samo v peskovniku srcdoc brez allow-same-origin (assets/os/vgrajeno.js).

Brez podvajanja (lastnik, 15. 10. 2026): vir NE ustvari kartice v katalogu - je samo dodatna moznost »Predvajaj prek«
na eni kartici, ki jo katalog ze zdruzi po id-jih (os_media.merge_duplicates). Vira, ki za isti naslov dasta isti
koncni naslov (po normalizaciji), se pokazeta enkrat; navadna stran (brez predlog) je ena ploscica na naslov.
Komponente in strani katalogu ne dajejo vnosov (most sprejme le zapri / celozaslonsko / napaka / pripravljen).

Ta modul je brez GTK in WebKita (preizkusi: tests/test_os_vgrajeni_viri.py).
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
import secrets
import time
import unicodedata
import urllib.parse
from pathlib import Path
from typing import Any, Optional

from . import meritve_virov

ZNACKE = ("imdb", "tmdb", "tvdb", "type", "season", "episode", "title", "year")
_ZNACKA = re.compile(r"\{([^{}]*)\}")
NAJVEC_VIROV = 50
NAJVEC_IME = 80
NAJVEC_URL = 2048
#: Koda komponente: dovolj za vecjo komponento, premalo za prenos knjiznice v nastavitve.
NAJVEC_KODE = 200_000
VRSTE = ("url", "komponenta")
#: Kljuca v nastavitve.json Medijskega centra (core/os_katalog.py).
KLJUC_VIROV = "vgrajeni_viri"
KLJUC_OBVESTILA = "vgrajeni_viri_obvestilo"
#: Nekdanja rocna izbira vira za naslov ({kljuc naslova: id vira}). Lastnik 26. 10. 2026 (NALOGA 33): uporabnik vira ne
#: izbira - kljuc se ob prvem zagonu pozabi (pozabi_rocne_izbire), da stara izbira ne ostane skrita prednost.
KLJUC_IZBIRE = "vgrajeni_viri_izbira"

#: Vzorcni naslov za »Preizkusi« (javni film in serija z znanimi id-ji).
VZOREC_FILM = {"imdb": "tt0111161", "tmdb": "278", "tvdb": "190", "type": "movie", "title": "The Shawshank Redemption",
               "year": "1994"}
VZOREC_SERIJA = {"imdb": "tt0903747", "tmdb": "1396", "tvdb": "81189", "type": "tv", "season": "1", "episode": "1",
                 "title": "Breaking Bad", "year": "2008"}

#: Knjiznice za komponente React (MIT; prenesene iz registra npm s preverjeno celovitostjo sha512, 15. 10. 2026).
#: Pred uporabo preverimo SHA-256 - spremenjena datoteka se ne nalozi (kot core/darkreader).
KNJIZNICE = {
    "react": ("react.production.min.js", "d949f1c3687aedadcedac85261865f29b17cd273997e7f6b2bfc53b2f9d4c4dd"),        # react@18.3.1
    "react-dom": ("react-dom.production.min.js", "35f4f974f4b2bcd44da73963347f8952e341f83909e4498227d4e26b98f66f0d"),  # react-dom@18.3.1
    "babel": ("babel.min.js", "7acf405141ca9e611b6d40aeef52071432d5f387cf906fc3556fb9f0b1a28601"),                    # @babel/standalone@7.26.10
}
MAPA_KNJIZNIC = Path(__file__).resolve().parent.parent / "assets" / "os" / "vendor"


class NapakaVira(ValueError):
    """Neveljaven vnos; .koda je kljuc besedila na strani (vgrNapaka_<koda>)."""

    def __init__(self, koda: str):
        super().__init__(koda)
        self.koda = koda


# ------------------------------------------------------------------ naslovi
def je_zasebni_gostitelj(gostitelj: str) -> bool:
    """Naslov v domacem omrezju (http je dovoljen samo tja): zasebni IPv4/IPv6, zanka, lokalna imena (.local, .lan,
    .home.arpa, localhost)."""
    g = (gostitelj or "").strip().strip("[]").rstrip(".").lower()
    if not g:
        return False
    try:
        ip = ipaddress.ip_address(g)
        # ::ffff:8.8.8.8 je javni IPv4; Python pred 3.12.4 ga steje za zasebnega (CVE-2024-4032).
        ip = getattr(ip, "ipv4_mapped", None) or ip
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        pass
    return g == "localhost" or g.endswith((".localhost", ".local", ".lan", ".home.arpa", ".internal"))


def _brez_kontrolnih(niz: str) -> bool:
    return not any(ord(c) < 33 or ord(c) == 127 for c in niz)


def preveri_naslov(naslov: str) -> str:
    """Koncni naslov za iframe: samo https://, http:// le v domace omrezje; brez javascript:, data:, file:, brez
    uporabnika/gesla v naslovu. Vrne naslov ali dvigne NapakaVira."""
    naslov = str(naslov or "").strip()
    if not naslov or len(naslov) > NAJVEC_URL:
        raise NapakaVira("naslov")
    if not _brez_kontrolnih(naslov) or "\\" in naslov:
        raise NapakaVira("naslov")
    deli = urllib.parse.urlsplit(naslov)
    shema = deli.scheme.lower()
    if shema not in ("https", "http"):
        raise NapakaVira("shema")
    if deli.username is not None or deli.password is not None or "@" in deli.netloc:
        raise NapakaVira("geslo")
    try:
        gostitelj = deli.hostname or ""
        deli.port                                     # neveljavna vrata dvignejo ValueError
    except ValueError:
        raise NapakaVira("naslov") from None
    if not gostitelj:
        raise NapakaVira("naslov")
    if shema == "http" and not je_zasebni_gostitelj(gostitelj):
        raise NapakaVira("http")
    return naslov


def znacke(predloga: str) -> list:
    """Znacke v predlogi po vrsti (brez ponovitev); neznana znacka dvigne NapakaVira."""
    najdene = []
    for m in _ZNACKA.finditer(str(predloga or "")):
        ime = m.group(1).strip().lower()
        if ime not in ZNACKE:
            raise NapakaVira("znacka")
        if ime not in najdene:
            najdene.append(ime)
    return najdene


def preveri_predlogo(predloga: str) -> str:
    """Predloga vira: znane znacke samo v poti, poizvedbi ali odlomku (ne v shemi ali gostitelju - vrednost ne sme
    zamenjati strani); z vzorcnimi vrednostmi mora dati veljaven naslov."""
    predloga = str(predloga or "").strip()
    if not predloga or len(predloga) > NAJVEC_URL:
        raise NapakaVira("naslov")
    if predloga.count("{") != predloga.count("}") or "{}" in predloga:
        raise NapakaVira("znacka")
    imena = znacke(predloga)
    m = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://[^/?#]*", predloga)
    if not m:
        shema = urllib.parse.urlsplit(predloga).scheme.lower()
        raise NapakaVira("shema" if shema and shema not in ("http", "https") else "naslov")
    if "{" in m.group(0):
        raise NapakaVira("znacka_gostitelj")
    vzorec = dict(VZOREC_SERIJA)
    preveri_naslov(_ZNACKA.sub(lambda z: urllib.parse.quote(vzorec.get(z.group(1).strip().lower(), "1"), safe=""), predloga))
    return predloga if imena else preveri_naslov(predloga)


def podatki_vnosa(item: dict, sezona: Any = 0, epizoda: Any = 0) -> dict:
    """Vrednosti znack iz vnosa kataloga (os_media: imdb_id, tmdb_id, tvdb_id, vrsta, leto, naslov) - samo veljavne."""
    item = item if isinstance(item, dict) else {}
    izid: dict = {}
    imdb = str(item.get("imdb_id") or item.get("imdb") or "").strip()
    if re.fullmatch(r"tt\d{5,10}", imdb):
        izid["imdb"] = imdb
    for kljuc, ime in (("tmdb_id", "tmdb"), ("tvdb_id", "tvdb")):
        v = str(item.get(kljuc) or item.get(ime) or "").strip()
        if re.fullmatch(r"\d{1,10}", v) and int(v) > 0:
            izid[ime] = str(int(v))
    serija = item.get("vrsta") == "serija" or item.get("type") == "tv"
    izid["type"] = "tv" if serija else "movie"
    s = int(sezona or item.get("sezona") or 0) if str(sezona or item.get("sezona") or 0).isdigit() else 0
    e = int(epizoda or item.get("epizoda") or 0) if str(epizoda or item.get("epizoda") or 0).isdigit() else 0
    if serija and s > 0 and e > 0:
        izid["season"], izid["episode"] = str(s), str(e)
    naslov = unicodedata.normalize("NFC", str(item.get("naslov") or item.get("title") or "")).strip()[:200]
    if naslov and _brez_kontrolnih(naslov.replace(" ", "")):
        izid["title"] = naslov
    leto = str(item.get("leto") or item.get("year") or "").strip()[:4]
    if re.fullmatch(r"(18|19|20|21)\d{2}", leto):
        izid["year"] = leto
    return izid


def izpolni(predloga: str, podatki: dict) -> Optional[str]:
    """Predloga z vrednostmi (vsaka kodirana s quote(safe="") - ne more dodati poti, poizvedbe ali gostitelja).
    None: predloga potrebuje vrednost, ki je vnos nima (gumba za ta vnos ni)."""
    predloga = preveri_predlogo(predloga)
    podatki = podatki if isinstance(podatki, dict) else {}
    for ime in znacke(predloga):
        if not str(podatki.get(ime) or ""):
            return None
    naslov = _ZNACKA.sub(lambda z: urllib.parse.quote(str(podatki[z.group(1).strip().lower()]), safe=""), predloga)
    return preveri_naslov(naslov)


def normaliziraj_url(naslov: str) -> str:
    """Kljuc za primerjavo naslovov: mala shema in gostitelj, brez privzetih vrat, brez koncne posevnice v poti,
    razvrscena poizvedba. Odlomek (#...) ostane, ker nekateri predvajalniki nosijo izbiro v njem."""
    d = urllib.parse.urlsplit(str(naslov or "").strip())
    shema = d.scheme.lower()
    gostitelj = (d.hostname or "").lower().rstrip(".")
    try:
        vrata = d.port
    except ValueError:
        vrata = None
    if vrata and not ((shema == "https" and vrata == 443) or (shema == "http" and vrata == 80)):
        gostitelj = "%s:%d" % (gostitelj if ":" not in gostitelj else "[%s]" % gostitelj, vrata)
    elif ":" in gostitelj:
        gostitelj = "[%s]" % gostitelj
    pot = d.path.rstrip("/")
    poizvedba = urllib.parse.urlencode(sorted(urllib.parse.parse_qsl(d.query, keep_blank_values=True)))
    return urllib.parse.urlunsplit((shema, gostitelj, pot, poizvedba, d.fragment))


# ------------------------------------------------------------------ vnosi
def _bool(v: Any, privzeto: bool) -> bool:
    return v if isinstance(v, bool) else privzeto


def normaliziraj_vir(vnos: dict, obstojec: Optional[dict] = None) -> dict:
    """Preveren vnos za shrambo: {id, ime, vrsta, url, koda, vklopljen, pojavna, ustvarjen}."""
    if not isinstance(vnos, dict):
        raise NapakaVira("vnos")
    prej = obstojec or {}
    ime = unicodedata.normalize("NFC", str(vnos.get("ime") or "")).strip()
    if not ime or len(ime) > NAJVEC_IME or not _brez_kontrolnih(ime.replace(" ", "")):
        raise NapakaVira("ime")
    vrsta = str(vnos.get("vrsta") or prej.get("vrsta") or "url")
    if vrsta not in VRSTE:
        raise NapakaVira("vnos")
    izid = {"id": str(prej.get("id") or secrets.token_hex(6)), "ime": ime, "vrsta": vrsta,
            "vklopljen": _bool(vnos.get("vklopljen"), _bool(prej.get("vklopljen"), True)),
            "ustvarjen": int(prej.get("ustvarjen") or time.time())}
    if vrsta == "url":
        izid["url"] = preveri_predlogo(str(vnos.get("url") or ""))
        # Pojavna okna: privzeto izkljucena (standard brskalnikov Safeer: nezelenih ne, zelenih - prijava - da).
        izid["pojavna"] = _bool(vnos.get("pojavna"), _bool(prej.get("pojavna"), False))
    else:
        koda = str(vnos.get("koda") or "")
        if not koda.strip() or len(koda) > NAJVEC_KODE or "\x00" in koda:
            raise NapakaVira("koda")
        izid["koda"] = koda
    return izid


def seznam(nastavitve: dict) -> list:
    """Shranjeni viri (pokvarjeni vnosi se preskocijo, ne podrejo seznama)."""
    izid = []
    for v in (nastavitve or {}).get(KLJUC_VIROV) or []:
        try:
            izid.append(normaliziraj_vir(v, v))
        except (NapakaVira, TypeError, ValueError):
            continue
    return izid[:NAJVEC_VIROV]


def je_navadna_stran(vir: dict) -> bool:
    """Vir brez znack: ploscica na polici Medijskega centra (ne gumb v podrobnostih)."""
    if vir.get("vrsta") != "url":
        return False
    try:
        return not znacke(vir.get("url") or "")
    except NapakaVira:
        return False


def shrani(nastavitve: dict, vnos: dict) -> dict:
    """Doda ali spremeni vir v slovarju nastavitev (klicatelj ga zapise). Nov vir zahteva potrjeno obvestilo; navadna
    stran, ki jo uporabnik ze ima (isti normaliziran naslov), se ne doda znova (»Ta vir že imaš«)."""
    viri = seznam(nastavitve)
    vid = str((vnos or {}).get("id") or "")
    obstojec = next((v for v in viri if v["id"] == vid), None) if vid else None
    if obstojec is None and not nastavitve.get(KLJUC_OBVESTILA):
        raise NapakaVira("obvestilo")
    if obstojec is None and len(viri) >= NAJVEC_VIROV:
        raise NapakaVira("prevec")
    nov = normaliziraj_vir(vnos, obstojec)
    if je_navadna_stran(nov):
        kljuc = normaliziraj_url(nov["url"])
        if any(v["id"] != nov["id"] and je_navadna_stran(v) and normaliziraj_url(v["url"]) == kljuc for v in viri):
            raise NapakaVira("podvojen")
    if obstojec is None:
        viri.append(nov)
    else:
        viri = [nov if v["id"] == nov["id"] else v for v in viri]
    nastavitve[KLJUC_VIROV] = viri
    return nov


def odstrani(nastavitve: dict, vid: str) -> bool:
    viri = seznam(nastavitve)
    ostali = [v for v in viri if v["id"] != str(vid or "")]
    nastavitve[KLJUC_VIROV] = ostali
    return len(ostali) != len(viri)


def javni(vir: dict, meritve: Optional[meritve_virov.Meritve] = None) -> dict:
    """Vir za stran (koda komponente gre zraven - stran jo pokaze v urejevalniku in jo zazene v peskovniku) z zadnjo
    meritvijo gostitelja ({ms, ok, cas} ali None - »34 ms · pred 2 h«, »ni dosegljiv«)."""
    izid = dict(vir)
    izid["navadna"] = je_navadna_stran(vir)
    izid["meritev"] = meritve.stanje(vir["url"]) if meritve is not None and vir.get("vrsta") == "url" else None
    if vir.get("vrsta") == "url":
        try:
            izid["znacke"] = znacke(vir.get("url") or "")
        except NapakaVira:
            izid["znacke"] = []
    return izid


def pozabi_rocne_izbire(nastavitve: dict) -> bool:
    """Ob zagonu: nekdanje rocne izbire vira (KLJUC_IZBIRE) se ne uporabijo in se zbrisejo. True = nastavitve so se
    spremenile (shrani jih klicatelj)."""
    return nastavitve.pop(KLJUC_IZBIRE, None) is not None


def moznosti_za(viri: list, item: dict, sezona: Any = 0, epizoda: Any = 0,
                meritve: Optional[meritve_virov.Meritve] = None) -> list:
    """Gumbi »Predvajaj prek <ime>« za EN vnos kataloga (kartica je ze zdruzena po id-jih - viri ne dodajo kartice).

    Vklopljeni viri s predlogo, ki jo vnos izpolni, in komponente. Isti koncni naslov se pokaze enkrat (prvi po vrstnem
    redu uporabnika, ostali v »tudi«). Nedosegljivih (zadnja meritev ok=False) ni - ko meritev v ozadju spet uspe, se
    vrnejo sami. Vrstni red je skupno pravilo meritve_virov.razvrsti (najhitrejsi dosegljivi prvi) - rocne izbire ni
    (NALOGA 33); stran odpre prvo in nedosegljivo zamenja z naslednjo iste vrste. Prva moznost ima »privzeta«: True."""
    podatki = podatki_vnosa(item, sezona, epizoda)
    izid: list = []
    po_naslovu: dict = {}
    for vir in viri or []:
        if not vir.get("vklopljen", True):
            continue
        if vir.get("vrsta") == "komponenta":
            izid.append({"id": vir["id"], "ime": vir["ime"], "vrsta": "komponenta", "podatki": podatki, "tudi": []})
            continue
        if je_navadna_stran(vir):
            continue                      # navadna stran je ploscica na polici, ne moznost naslova
        try:
            naslov = izpolni(vir.get("url") or "", podatki)
        except NapakaVira:
            continue
        if not naslov:
            continue
        if meritve is not None and meritve.nedosegljiv(naslov):
            continue                      # nedelujocih gumbov ne kazemo (lastnik, 15. 10. 2026)
        kljuc = normaliziraj_url(naslov)
        if kljuc in po_naslovu:
            po_naslovu[kljuc]["tudi"].append(vir["ime"])
            continue
        moznost = {"id": vir["id"], "ime": vir["ime"], "vrsta": "url", "url": naslov,
                   "pojavna": bool(vir.get("pojavna")), "podatki": podatki, "tudi": [],
                   "ms": meritve.ms(naslov) if meritve is not None else None}
        po_naslovu[kljuc] = moznost
        izid.append(moznost)
    izid = meritve_virov.razvrsti(izid, meritve, kakovost=lambda _m: 0)
    if izid:
        izid[0]["privzeta"] = True
    return izid


def ploscice(viri: list) -> list:
    """Navadne strani za polico: vklopljene, ena na normaliziran naslov."""
    izid, videni = [], set()
    for vir in viri or []:
        if not vir.get("vklopljen", True) or not je_navadna_stran(vir):
            continue
        kljuc = normaliziraj_url(vir["url"])
        if kljuc in videni:
            continue
        videni.add(kljuc)
        izid.append({"id": vir["id"], "ime": vir["ime"], "url": vir["url"], "pojavna": bool(vir.get("pojavna"))})
    return izid


def preizkusi(vnos: dict) -> dict:
    """»Preizkusi«: koncni naslov za vzorcni film in serijo (brez shranjevanja)."""
    predloga = preveri_predlogo(str((vnos or {}).get("url") or ""))
    izid = {"film": izpolni(predloga, VZOREC_FILM), "serija": izpolni(predloga, VZOREC_SERIJA)}
    if not izid["film"] and not izid["serija"]:
        raise NapakaVira("vzorec")
    return izid


# ------------------------------------------------------------------ knjiznice za komponente
def knjiznica(ime: str, mapa: Optional[Path] = None) -> str:
    """Besedilo knjiznice (react, react-dom, babel) po preverbi SHA-256; spremenjena ali manjkajoca dvigne NapakaVira."""
    if ime not in KNJIZNICE:
        raise NapakaVira("knjiznica")
    datoteka, sha = KNJIZNICE[ime]
    try:
        podatki = ((mapa or MAPA_KNJIZNIC) / datoteka).read_bytes()
    except OSError:
        raise NapakaVira("knjiznica") from None
    if hashlib.sha256(podatki).hexdigest() != sha:
        raise NapakaVira("knjiznica")
    return podatki.decode("utf-8")


# ------------------------------------------------------------------ pravila pogleda Medijskega centra
def dovoli_okvir(naslov: str) -> bool:
    """Ali sme okvir (iframe) v Medijskem centru naloziti ta naslov, ko je vgrajen vir odprt: about:srcdoc in
    about:blank (peskovnik komponente) ter http(s) po pravilih preveri_naslov. Scit (oglasi, grozni) preveri klicatelj."""
    if naslov in ("about:srcdoc", "about:blank"):
        return True
    try:
        preveri_naslov(naslov)
        return True
    except NapakaVira:
        return False


def tuja_glavna_stran(naslov: str, koren: str) -> bool:
    """Glavni okvir pogleda z mostom sme kazati samo strani Safeer OS (koren) in about:; vse drugo zavrnemo."""
    naslov = str(naslov or "")
    return not (naslov.startswith(str(koren or "") + "/") or naslov.startswith("about:")) if koren else not naslov.startswith(("file://", "about:"))
