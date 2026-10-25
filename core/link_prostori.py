"""Prostori (Safeer Link Spaces, MVP): kateri zasloni povezanih naprav so v preklopniku Prostori in kako se odprejo.

Zamisel lastnika (24. 10. 2026, nacrti/safeer-link-spaces.md): v namizju Safeer OS vrstica s tem racunalnikom in vsemi
povezanimi napravami, ki znajo pokazati svoj zaslon; izbira odpre zaslon naprave tukaj, z misko in tipkovnico tega
racunalnika. Ta modul so cista pravila brez GTK in brez omrezja (tests/test_link_prostori.py); most in vmesnik sta v
safeer_os.py (`prostori`, `prostorOdpri`) in assets/os/os.js (sloj #slojProstori).

Kar je ze narejeno, uporabimo, ne gradimo znova:
  * racunalnik (Linux, Windows) z zmoznostjo "desktop" (core/link_zaslon.Zaslon.ZMOZNOST): Safeer Control
    `Upravljaj` -> `screen.start`, gledalec H.264 z misko in tipkovnico (safeer_control.OddaljeniGledalec);
  * naprava Android (telefon, tablica, televizor s Safeer OS) z zmoznostjo "zaslon.deli" (Android
    link/Daljinec.ZMOZNOST_DELI_ZASLON): Safeer Control `OdpriTukaj` s programom CEL_ZASLON -> naprava pokaze
    sistemsko potrditev deljenja (Android jo zahteva ZA VSAKO sejo), slika pride kot share.screen v gledalec Controla,
    vnos gre prek Safeer Vnos (enaka pot kot »Povezani zasloni« na Androidu, os/PovezaniZasloni.kt).

Pravila (enaka kot os/SeznamZaslonov.kt na Androidu, kjer je smiselno):
  * samo naprave v OZJEM krogu zaupanja (lastnik, 17. 10. 2026: naprav izven njega za zaslon sploh ne vidimo);
  * ta racunalnik (in njegovi sorodniki) ni nikoli prostor - ima svojo ploscico »Ta racunalnik« v vmesniku;
  * sorodniki ene naprave (TV: "n-x" in "n-x-os", racunalnik: "pc-y" in "pc-y-control") so en prostor; ukaz gre
    vnosu, ki zaslon zna (namizje pred deljenjem zaslona, nato vec zmoznosti);
  * naprava, ki je bila prostor, pa je zdaj ni v Linku, ostane na svojem mestu oznacena »ni povezana« (ne izgine);
    naprava, ki je v Linku, a ni vec v ozjem krogu ali zaslona ne zna vec, izpade;
  * vrstni red je STALEN (po tem, kdaj je bila naprava prvic prostor): mesto prostora se ne spreminja, ko naprave
    pridejo in odidejo - tako kot pri navideznih namizjih uporabnik ve, kje je kaj (Super+Tab, puscice).

Slicice v zivo (cilj 60 fps) v MVP NISO: naprave danes ne ponujajo posnetka celega zaslona brez potrditve (Android
`screenshot` je samo posnetek odprtega brskalnika, MediaProjection zahteva potrditev za vsako sejo). Ploscica zato
pokaze vrsto naprave (ikona), ime, stanje povezave in kdaj je bila nazadnje videna. Glej nacrti/safeer-link-spaces-adr.md.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional

#: Zmoznost racunalnika, ki deli namizje (Safeer Control na Linuxu in Windows).
ZMOZNOST_NAMIZJE = "desktop"
#: Zmoznost naprave Android, ki na zahtevo deli cel zaslon (Android link/Daljinec.ZMOZNOST_DELI_ZASLON).
ZMOZNOST_DELI_ZASLON = "zaslon.deli"
#: »Program«, ki pomeni »deli cel zaslon, nicesar ne odpri« (Android link/Daljinec.CEL_ZASLON).
CEL_ZASLON = "safeer.cel.zaslon"

#: Kako se prostor odpre: oddaljeni zaslon racunalnika (Upravljaj) ali deljenje zaslona naprave (OdpriTukaj).
NACIN_RACUNALNIK = "racunalnik"
NACIN_ZASLON = "zaslon"
NACINI = (NACIN_RACUNALNIK, NACIN_ZASLON)
#: Vrsta naprave za ikono ploscice.
VRSTE = ("racunalnik", "tablica", "telefon", "tv", "naprava")

#: Toliko prostorov si zapomnimo (povezane ostanejo vedno; brez povezave izpadejo najdlje nevidene).
NAJVEC_ZNANIH = 16
_NAJDALJSI_ID = 128
_NAJDALJSE_IME = 80
_PRIPONA_SORODNIKA = re.compile(r"-(os|control)$")


def _niz(v, najvec: int) -> str:
    return str(v if v is not None else "").replace("\n", " ").replace("\t", " ").strip()[:najvec]


def _cas(v) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


def zmoznosti(n: dict) -> List[str]:
    z = n.get("zmoznosti") if isinstance(n, dict) else None
    return [str(x) for x in z] if isinstance(z, (list, tuple)) else []


def nacin(n: dict) -> str:
    """Kako se zaslon naprave odpre tukaj ali "" (naprava zaslona ne deli). Namizje racunalnika ima prednost."""
    z = zmoznosti(n)
    if ZMOZNOST_NAMIZJE in z:
        return NACIN_RACUNALNIK
    if ZMOZNOST_DELI_ZASLON in z:
        return NACIN_ZASLON
    return ""


def vrsta(n: dict) -> str:
    """Vrsta naprave za ikono: racunalnik, tablica, telefon, tv ali naprava (neznano)."""
    platforma = str(n.get("platforma") or "").lower()
    vr = str(n.get("vrsta") or "").lower()
    if ZMOZNOST_NAMIZJE in zmoznosti(n) or platforma in ("linux", "windows", "win32", "macos") \
            or vr in ("computer", "control", "desktop"):
        return "racunalnik"
    if platforma == "tv" or vr == "tv":
        return "tv"
    if platforma in ("tablet", "tablica") or vr == "tablet":
        return "tablica"
    if platforma in ("phone", "telefon") or vr == "phone":
        return "telefon"
    return "naprava"


def kljuc(id_naprave: str) -> str:
    """Kljuc fizicne naprave iz id-ja: sorodniki "x", "x-os" in "x-control" so ena naprava (kot zdruziSorodnike v os.js)."""
    return _PRIPONA_SORODNIKA.sub("", str(id_naprave or ""))


def _boljsi(a: dict, b: dict) -> dict:
    """Med sorodnikoma ostane tisti, ki zaslon zna (namizje pred deljenjem), nato tisti z vec zmoznostmi."""
    red = {NACIN_RACUNALNIK: 2, NACIN_ZASLON: 1, "": 0}
    ka, kb = (red[nacin(a)], len(zmoznosti(a))), (red[nacin(b)], len(zmoznosti(b)))
    return b if kb > ka else a


def zive_s_prostorom(zive: Iterable[dict]) -> Dict[str, dict]:
    """Naprave v Linku, ki so lahko prostor, po kljucu fizicne naprave: {kljuc: {id, ime, vrsta, nacin, aplikacije}}.

    Ce je kateri koli sorodnik ta racunalnik, skupina ni prostor. Ozji krog velja, ce je v njem kateri koli sorodnik
    (kot v os.js); dostop vseeno preveri ciljna naprava sama ob ukazu (core/link_dostop.py, Android DostopPravila)."""
    skupine: Dict[str, List[dict]] = {}
    for n in zive or []:
        if not isinstance(n, dict) or not _niz(n.get("id"), _NAJDALJSI_ID):
            continue
        skupine.setdefault(kljuc(_niz(n.get("id"), _NAJDALJSI_ID)), []).append(n)
    izhod: Dict[str, dict] = {}
    for k, clani in skupine.items():
        if any(c.get("ta") for c in clani) or not any(c.get("ozji") for c in clani):
            continue
        izbran = clani[0]
        for c in clani[1:]:
            izbran = _boljsi(izbran, c)
        nc = nacin(izbran)
        if not nc:
            continue
        osnovni = next((c for c in clani if _niz(c.get("id"), _NAJDALJSI_ID) == k), izbran)
        ime = _niz(osnovni.get("ime") or izbran.get("ime") or izbran.get("id"), _NAJDALJSE_IME)
        vse_zm = set()
        for c in clani:
            vse_zm.update(zmoznosti(c))
        izhod[k] = {"kljuc": k, "id": _niz(izbran.get("id"), _NAJDALJSI_ID), "ime": ime, "vrsta": vrsta(izbran),
                    "nacin": nc, "aplikacije": bool({"apps", "remote"} & vse_zm)}
    return izhod


def ocisti_znane(surovo) -> List[dict]:
    """Zapis iz shrambe (os.json, kljuc "prostori") v preverjeno obliko; pokvarjen zapis se tiho izpusti."""
    izhod: List[dict] = []
    videni = set()
    for z in surovo if isinstance(surovo, list) else []:
        if not isinstance(z, dict):
            continue
        k = _niz(z.get("kljuc"), _NAJDALJSI_ID)
        idn = _niz(z.get("id"), _NAJDALJSI_ID) or k
        if not k or k in videni:
            continue
        videni.add(k)
        izhod.append({"kljuc": k, "id": idn, "ime": _niz(z.get("ime"), _NAJDALJSE_IME) or idn,
                      "vrsta": z.get("vrsta") if z.get("vrsta") in VRSTE else "naprava",
                      "nacin": z.get("nacin") if z.get("nacin") in NACINI else NACIN_ZASLON,
                      "dodana": _cas(z.get("dodana")), "videna": _cas(z.get("videna"))})
        if len(izhod) >= NAJVEC_ZNANIH:
            break
    return izhod


def zapomni(znane: List[dict], zive: Iterable[dict], zdaj: int) -> List[dict]:
    """Nov zapis prostorov: znane posodobi z zivimi, nove doda na konec, odvzete (ni ozji krog, ni zaslona) odstrani.

    Vrstni red ostane stalen (po `dodana`). Nad NAJVEC_ZNANIH izpadejo najdlje nevidene naprave brez povezave."""
    zive = list(zive or [])
    zdaj = _cas(zdaj)
    s_prostorom = zive_s_prostorom(zive)
    # V Linku, a ne vec prostor (odvzet ozji krog, izklopljeno deljenje zaslona): izpade iz zapisa.
    v_linku = {kljuc(_niz(n.get("id"), _NAJDALJSI_ID)) for n in zive if isinstance(n, dict) and n.get("id")}
    nove: List[dict] = []
    for z in ocisti_znane(znane):
        k = z["kljuc"]
        if k in s_prostorom:
            nove.append(dict(z, **{x: s_prostorom[k][x] for x in ("id", "ime", "vrsta", "nacin")}, videna=zdaj))
        elif k not in v_linku:
            nove.append(z)
    ze = {z["kljuc"] for z in nove}
    for k, p in s_prostorom.items():
        if k not in ze:
            nove.append({"kljuc": k, "id": p["id"], "ime": p["ime"], "vrsta": p["vrsta"], "nacin": p["nacin"],
                         "dodana": zdaj, "videna": zdaj})
    nove.sort(key=lambda z: (z["dodana"], z["ime"].lower()))
    while len(nove) > NAJVEC_ZNANIH:
        brez = [z for z in nove if z["kljuc"] not in s_prostorom]
        if not brez:
            break
        nove.remove(min(brez, key=lambda z: z["videna"]))
    return nove


def prostori(znane: List[dict], zive: Iterable[dict]) -> List[dict]:
    """Prostori za vmesnik v stalnem vrstnem redu zapisa: id, ime, vrsta, nacin, povezana, aplikacije, videna."""
    s_prostorom = zive_s_prostorom(zive)
    izhod = []
    for z in ocisti_znane(znane):
        ziv = s_prostorom.get(z["kljuc"])
        izhod.append({"id": (ziv or z)["id"], "ime": (ziv or z)["ime"], "vrsta": (ziv or z)["vrsta"],
                      "nacin": (ziv or z)["nacin"], "povezana": ziv is not None,
                      "aplikacije": bool(ziv and ziv["aplikacije"]), "videna": z["videna"]})
    return izhod


def za_odpiranje(zive: Iterable[dict], id_naprave: str) -> Optional[dict]:
    """Ziva naprava, ki je prostor, za id iz vmesnika (tudi id sorodnika) ali None.

    Stran ne more zahtevati poljubnega id-ja ali programa: odpre se samo prostor iz tega seznama, s programom CEL_ZASLON."""
    k = kljuc(_niz(id_naprave, _NAJDALJSI_ID))
    return zive_s_prostorom(zive).get(k) if k else None
