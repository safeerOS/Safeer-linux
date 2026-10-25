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
    vnosu, ki zaslon zna (namizje pred deljenjem zaslona, nato vec zmoznosti) - in je SAM v ozjem krogu (sorodnik
    izven njega se izloci, preden izberemo; pregled 25. 10. 2026);
  * naprava, ki je bila prostor, pa je zdaj ni v Linku ali je v njem brez zaslona (TV: tece samo brskalnik "n-x", ne
    Safeer OS "n-x-os"), ostane na svojem mestu oznacena »ni povezana« (ne izgine, ne gre na konec); izpade samo
    naprava, ki je v Linku, a ni vec v ozjem krogu;
  * vrstni red je STALEN (po tem, kdaj je bila naprava prvic prostor): mesto prostora se ne spreminja, ko naprave
    pridejo in odidejo - tako kot pri navideznih namizjih uporabnik ve, kje je kaj (Super+Tab, puscice).

Slicice v zivo (krog 2, 25. 10. 2026): RACUNALNIK v krogu (Linux; Windows, ko dobi isto dejanje) na zahtevo vrne
majhen posnetek namizja (`screen.thumb`, core/link_zaslon.Zaslon.slicica) - samo ce je deljenje zaslona tam vklopljeno
in samo na X11 (na Waylandu bi portal vsakic vprasal). Preklopnik ga zahteva vsakih nekaj sekund SAMO, dokler je odprt
(razred Slicice spodaj: najvec en klic na napravo hkrati, premor, daljsi premor za napravo, ki dejanja ne zna). Naprave
Android ostanejo pri ikoni: posnetka celega zaslona brez potrditve MediaProjection za vsako sejo ni (omejitev sistema).
Glej nacrti/safeer-link-spaces-adr.md.
"""
from __future__ import annotations

import re
import threading
import time
from typing import Callable, Dict, Iterable, List, Optional

#: Zmoznost racunalnika, ki deli namizje (Safeer Control na Linuxu in Windows).
ZMOZNOST_NAMIZJE = "desktop"
#: Zmoznost naprave Android, ki na zahtevo deli cel zaslon (Android link/Daljinec.ZMOZNOST_DELI_ZASLON).
ZMOZNOST_DELI_ZASLON = "zaslon.deli"
#: »Program«, ki pomeni »deli cel zaslon, nicesar ne odpri« (Android link/Daljinec.CEL_ZASLON).
CEL_ZASLON = "safeer.cel.zaslon"
#: Kljuka za NAMIZNI NACIN naprave Android (lasten zaganjalnik na navideznem zaslonu; Android veja »zaganjalnik«): naprava,
#: ki ga zna, to pove s to zmoznostjo, program PROGRAM_NAMIZNI pa ji pove, naj deli namizje zaganjalnika namesto zrcaljenja.
#: Dokler je nobena naprava ne sporoca, menija »Namizni nacin« ni (ne obljubljamo, cesar ni).
ZMOZNOST_NAMIZNI = "zaslon.namizje"
PROGRAM_NAMIZNI = "safeer.namizni.nacin"
#: Nacini prikaza v meniju »+« (lastnik 19. 10.: zrcaljenje / samo ena aplikacija / namizni nacin). Razsirjen zaslon
#: (naprava kot drugi monitor) ni mogoc brez navideznega monitorja - omejitev v ADR, ne gumb.
PRIKAZ_ZRCALJENJE, PRIKAZ_APLIKACIJA, PRIKAZ_NAMIZNI = "zrcaljenje", "aplikacija", "namizni"
PRIKAZI = (PRIKAZ_ZRCALJENJE, PRIKAZ_APLIKACIJA, PRIKAZ_NAMIZNI)

#: Kako se prostor odpre: oddaljeni zaslon racunalnika (Upravljaj) ali deljenje zaslona naprave (OdpriTukaj).
NACIN_RACUNALNIK = "racunalnik"
NACIN_ZASLON = "zaslon"
NACINI = (NACIN_RACUNALNIK, NACIN_ZASLON)
#: Vrsta naprave za ikono ploscice.
VRSTE = ("racunalnik", "tablica", "telefon", "tv", "naprava")

#: Toliko prostorov si zapomnimo in pokazemo (ena meja za zapis in vmesnik; najprej izpadejo najdlje nevidene brez
#: povezave, ce so vse povezane, pa nazadnje dodane).
NAJVEC_ZNANIH = 16
#: »Nazadnje videna« povezane naprave se zapise najvec tako pogosto (s): osvezitev odprtega preklopnika vsakih 5 s sicer
#: vsakic znova zapise os.json (dva fsync) - pregled 25. 10. 2026.
VIDENA_NAJVEC_NA_S = 60
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


def _skupine(zive: Iterable[dict]) -> Dict[str, List[dict]]:
    """Zive naprave po kljucu fizicne naprave (sorodniki skupaj); pokvarjeni vnosi se izpustijo."""
    skupine: Dict[str, List[dict]] = {}
    for n in zive or []:
        if not isinstance(n, dict) or not _niz(n.get("id"), _NAJDALJSI_ID):
            continue
        skupine.setdefault(kljuc(_niz(n.get("id"), _NAJDALJSI_ID)), []).append(n)
    return skupine


def _izven_kroga(clani: List[dict]) -> bool:
    """Skupina v Linku ni (vec) prostor zaradi zaupanja: sorodnik je ta racunalnik ali noben clan ni v ozjem krogu."""
    return any(c.get("ta") for c in clani) or not any(c.get("ozji") for c in clani)


def zive_s_prostorom(zive: Iterable[dict]) -> Dict[str, dict]:
    """Naprave v Linku, ki so lahko prostor, po kljucu fizicne naprave: {kljuc: {id, ime, vrsta, nacin, aplikacije}}.

    Ce je kateri koli sorodnik ta racunalnik, skupina ni prostor. Ukaz (Upravljaj z misko in tipkovnico tega racunalnika)
    gre samo clanu, ki je SAM v ozjem krogu: sorodnike izven njega izlocimo, preden izberemo vnos z zaslonom - sicer bi
    lazen "x-control" ob pravem "x" (stari id-ji brez kljuca) dobil vnos (pregled 25. 10. 2026). Dostop vseeno preveri
    ciljna naprava sama ob ukazu (core/link_dostop.py, Android DostopPravila)."""
    izhod: Dict[str, dict] = {}
    for k, vsi in _skupine(zive).items():
        if _izven_kroga(vsi):
            continue
        clani = [c for c in vsi if c.get("ozji")]
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
                    "nacin": nc, "aplikacije": bool({"apps", "remote"} & vse_zm),
                    # Namizni nacin mora znati ISTI clan, ki dobi ukaz (ne kateri koli sorodnik).
                    "namizni": nc == NACIN_ZASLON and ZMOZNOST_NAMIZNI in zmoznosti(izbran)}
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
    """Nov zapis prostorov: znane posodobi z zivimi, nove doda na konec, odvzete (v Linku, a ne v ozjem krogu) odstrani.

    Vrstni red ostane stalen (po `dodana`); znana naprava brez zaslona v Linku ostane na svojem mestu. Zapis ostane enak,
    ce se ni spremenilo nic bistvenega (nova naprava, ime, vrsta, nacin) - `videna` povezane naprave se posodobi najvec
    vsakih VIDENA_NAJVEC_NA_S. Zapis ima najvec NAJVEC_ZNANIH prostorov (enako kot ocisti_znane in vmesnik)."""
    zive = list(zive or [])
    zdaj = _cas(zdaj)
    s_prostorom = zive_s_prostorom(zive)
    # V Linku, a ne vec v ozjem krogu (ali je postal ta racunalnik): izpade iz zapisa. Brez zaslona ostane.
    odvzete = {k for k, clani in _skupine(zive).items() if _izven_kroga(clani)}
    nove: List[dict] = []
    for z in ocisti_znane(znane):
        k = z["kljuc"]
        if k in s_prostorom:
            nov = dict(z, **{x: s_prostorom[k][x] for x in ("id", "ime", "vrsta", "nacin")})
            if nov != z or zdaj - z["videna"] >= VIDENA_NAJVEC_NA_S:
                nov["videna"] = zdaj
            nove.append(nov)
        elif k not in odvzete:
            nove.append(z)
    ze = {z["kljuc"] for z in nove}
    for k, p in s_prostorom.items():
        if k not in ze:
            nove.append({"kljuc": k, "id": p["id"], "ime": p["ime"], "vrsta": p["vrsta"], "nacin": p["nacin"],
                         "dodana": zdaj, "videna": zdaj})
    nove.sort(key=lambda z: (z["dodana"], z["ime"].lower()))
    while len(nove) > NAJVEC_ZNANIH:
        brez = [z for z in nove if z["kljuc"] not in s_prostorom]
        # Najprej najdlje nevidena brez povezave; ce so vse povezane, nazadnje dodana (stara mesta ostanejo).
        nove.remove(min(brez, key=lambda z: z["videna"]) if brez else nove[-1])
    return nove


def prostori(znane: List[dict], zive: Iterable[dict]) -> List[dict]:
    """Prostori za vmesnik v stalnem vrstnem redu zapisa: id, ime, vrsta, nacin, povezana, aplikacije, videna."""
    s_prostorom = zive_s_prostorom(zive)
    izhod = []
    for z in ocisti_znane(znane):
        ziv = s_prostorom.get(z["kljuc"])
        izhod.append({"id": (ziv or z)["id"], "ime": (ziv or z)["ime"], "vrsta": (ziv or z)["vrsta"],
                      "nacin": (ziv or z)["nacin"], "povezana": ziv is not None,
                      "aplikacije": bool(ziv and ziv["aplikacije"]), "videna": z["videna"],
                      "nacini": nacini_prikaza(ziv)})
    return izhod


def nacini_prikaza(p: Optional[dict]) -> List[str]:
    """Nacini prikaza povezanega prostora za meni »+«: zrcaljenje vedno, »samo ena aplikacija«, ce naprava deli
    programe, namizni nacin samo, ce ga naprava sama sporoca (ZMOZNOST_NAMIZNI)."""
    if not p:
        return []
    izhod = [PRIKAZ_ZRCALJENJE]
    if p.get("aplikacije"):
        izhod.append(PRIKAZ_APLIKACIJA)
    if p.get("namizni"):
        izhod.append(PRIKAZ_NAMIZNI)
    return izhod


def program_za(p: Optional[dict], prikaz: str) -> Optional[str]:
    """Kaj Control odpre za prostor (iz za_odpiranje) v nacinu `prikaz`; None = ta nacin tu ni mogoc.

    Racunalnik: "" (oddaljeni zaslon, Upravljaj) samo za zrcaljenje. Android: CEL_ZASLON ali PROGRAM_NAMIZNI (samo,
    ce ga naprava zna). »Samo ena aplikacija« ni ukaz zaslona - gre po poti Programi -> Odpri tukaj. Nacin preveri
    Python: stran ne more izbrati programa ali nacina, ki ga naprava ni sporocila."""
    if not p or prikaz not in (PRIKAZ_ZRCALJENJE, PRIKAZ_NAMIZNI):
        return None
    if p.get("nacin") == NACIN_RACUNALNIK:
        return "" if prikaz == PRIKAZ_ZRCALJENJE else None
    if prikaz == PRIKAZ_NAMIZNI:
        return PROGRAM_NAMIZNI if p.get("namizni") else None
    return CEL_ZASLON


# ---------------------------------------------------------------------- slicice v zivo (racunalniki v krogu)
#: Najmanjsi premik med dvema posnetkoma iste naprave (s) - preklopnik je odprt kratek cas, namizje se pocasi spreminja.
SLICICA_VSAKIH_S = 2.5
#: Naprava, ki dejanja ne zna ali ga ne dovoli (starejsi Control, Windows brez screen.thumb, deljenje izklopljeno,
#: Wayland), se toliko casa ne vprasa znova - ploscica ostane pri ikoni.
SLICICA_NI_S = 120.0
#: Najvecja sprejeta slicica (znakov data URL): 320 px JPEG je ~15-30 KB; vec pomeni napako ali tujo vsebino.
SLICICA_NAJVEC = 256 * 1024
#: Toliko naprav si zapomnimo (vec jih preklopnik tudi ne pokaze).
SLICICA_NAPRAV = 32
PREDPONA_SLICICE = "data:image/jpeg;base64,"
_BASE64 = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
#: Kode, ob katerih naprave dolgo ne sprasujemo (ne bo se spremenilo v nekaj sekundah).
_KODE_NI = frozenset(("neznano_dejanje", "ni_dovoljeno", "ni_brez_potrditve", "ni_na_racunalniku", "ni_zajema",
                      "dostop", "ni_dostopa", "prepovedano"))


def veljavna_slicica(podatki) -> Optional[dict]:
    """Odgovor `screen.thumb` -> {slika, w, h} ali None. Sprejme samo JPEG kot data URL v base64 (nic drugega ne pride
    v atribut src) in razumno velikost."""
    if not isinstance(podatki, dict):
        return None
    s = podatki.get("image")
    if not isinstance(s, str) or not s.startswith(PREDPONA_SLICICE) or len(s) > SLICICA_NAJVEC:
        return None
    if not _BASE64.match(s[len(PREDPONA_SLICICE):]):
        return None

    def mera(v) -> int:
        return v if isinstance(v, int) and not isinstance(v, bool) and 0 < v <= 4096 else 0
    return {"slika": s, "w": mera(podatki.get("width")), "h": mera(podatki.get("height"))}


class Slicice:
    """Zadnja slicica vsake naprave. Naprava se vprasa najvec vsakih SLICICA_VSAKIH_S in nikoli dvakrat hkrati (pocasna
    povezava ne nabira niti); vmes vrnemo zadnjo dobro sliko. `vprasaj` tece v klicateljevi niti (most: nit ozadja)."""

    def __init__(self, ura: Callable[[], float] = time.monotonic) -> None:
        self._ura = ura
        self._zaklep = threading.Lock()
        self._z: Dict[str, dict] = {}

    def dobi(self, kljuc: str, vprasaj: Callable[[], dict]) -> dict:
        with self._zaklep:
            z = self._z.get(kljuc)
            zdaj = self._ura()
            if z is not None and (z["tece"] or zdaj < z["naslednjic"]):
                return dict(z["izid"])
            if z is None:
                if len(self._z) >= SLICICA_NAPRAV:
                    del self._z[min(self._z, key=lambda k: self._z[k]["naslednjic"])]
                z = self._z[kljuc] = {"tece": False, "naslednjic": 0.0, "izid": {"ok": False, "koda": "pocakaj"}}
            z["tece"] = True
        try:
            r = vprasaj()
        except Exception as e:  # noqa: BLE001 - napaka ene naprave ne sme ustaviti drugih ploscic
            r = {"ok": False, "koda": "napaka", "message": str(e)}
        r = r if isinstance(r, dict) else {}
        slika = veljavna_slicica(r.get("data")) if r.get("ok") else None
        # Odgovor naprave prek Linka ima kodo v "code" (link_daljinec.izid), Control sam pa v "koda".
        koda = "" if slika else str(r.get("koda") or r.get("code") or ("napacna_slika" if r.get("ok") else "napaka"))[:32]
        with self._zaklep:
            z["tece"] = False
            z["naslednjic"] = self._ura() + (SLICICA_NI_S if koda in _KODE_NI else SLICICA_VSAKIH_S)
            if slika:
                z["izid"] = dict(slika, ok=True)
            elif not z["izid"].get("ok"):
                z["izid"] = {"ok": False, "koda": koda}
            # Ob kratki napaki ostane zadnja dobra slika (ploscica ne utripa); ob trajni (_KODE_NI) jo pozabimo.
            if koda in _KODE_NI:
                z["izid"] = {"ok": False, "koda": koda}
            return dict(z["izid"])


def za_odpiranje(zive: Iterable[dict], id_naprave: str) -> Optional[dict]:
    """Ziva naprava, ki je prostor, za id iz vmesnika (tudi id sorodnika) ali None.

    Stran ne more zahtevati poljubnega id-ja ali programa: odpre se samo prostor iz tega seznama, s programom CEL_ZASLON."""
    k = kljuc(_niz(id_naprave, _NAJDALJSI_ID))
    return zive_s_prostorom(zive).get(k) if k else None
