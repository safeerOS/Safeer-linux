"""Vticniki (plugins) uporabnikovega streznika Jellyfin: pregled, vklop/izklop, namestitev, odstranitev, ponovni zagon.

Vticniki tecejo na strezniku, ne v Safeerju: Safeer jih samo upravlja prek uradnega vmesnika REST z zetonom, ki ga
je dobil ob prijavi (shranjen v sistemski zbirki skrivnosti, core/os_katalog.py). Poti in parametri so preverjeni v
uradnih opisih OpenAPI (api.jellyfin.org: 10.9.11, 10.10.7, 10.11.6, 12.2.0; 15. 10. 2026) in v izvorni kodi
PackageController.cs / InstallationManager.cs (10.11):

- GET  /System/Info/Public                    ime in razlicica streznika (brez prijave; ob zagonu 10.11+ vrne 503)
- GET  /Users/Me                              Policy.IsAdministrator - samo skrbnik sme upravljati vticnike
- GET  /Plugins                               namesceni vticniki (Id brez pomisljajev, Version, Status, CanUninstall)
- POST /Plugins/{id}/{version}/Enable|Disable vklop in izklop (velja po ponovnem zagonu)
- DELETE /Plugins/{id}/{version}              odstranitev (DELETE /Plugins/{id} je od 10.9 opusceno, rezerva ob 404)
- GET  /Packages                              katalog iz repozitorijev, ki jih je skrbnik vklopil na strezniku;
                                              strežnik sam izloci razlicice, ki z njim niso zdruzljive (targetAbi)
- GET  /Repositories                          seznam repozitorijev (uradni in morebitni tretjih oseb)
- POST /Packages/Installed/{name}?assemblyGuid=&repositoryUrl=   namestitev; brez `version` strežnik izbere najnovejso
                                              zdruzljivo razlicico
- POST /System/Restart                        ponovni zagon (spremembe vticnikov veljajo sele po njem)

Status vticnika: Active, Restart, Deleted, Superceded (10.11+ tudi Superseded), Malfunctioned, NotSupported, Disabled.

Priporoceni vticniki so samo podatki (PRIPOROCENO) - brez posebnih poti kode za posamezen vticnik.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Optional

from core import media_servers

#: Uradni repozitorij Jellyfina (repo.jellyfin.org in zrcala *.jellyfin.org).
URADNI_GOSTITELJ = "jellyfin.org"

#: Kratka, izbrana lista z uporabnikove strani: kar Safeerju res doda vrednost. Kljuc `razlog` je besedilo v
#: assets/os/besedila.js (vseh 6 jezikov). `safeer_zna`: Safeer to ze naredi sam - ne ponudimo namestitve, da
#: uporabnik iste stvari ne dobi dvakrat. Preverjeno 15. 10. 2026 v uradnem katalogu (repo.jellyfin.org).
PRIPOROCENO: tuple = (
    # Safeer kaze plakate in ozadja s strežnika (Items/{id}/Images): Fanart jih doda, kjer jih knjiznica nima.
    {"guid": "170a157f-ac6c-437a-abdd-ca9c25cebd39", "ime": "Fanart", "razlog": "jfRazlogFanart"},
    # Naslovnice albumov za glasbo s strežnika (polica Glasba, kolaz samodejnih seznamov).
    {"guid": "8119f3c6-cfc2-4d9c-a0ba-028f1d93e526", "ime": "Cover Art Archive", "razlog": "jfRazlogCoverArt"},
    # Zanesljive stevilke sezon in epizod - Safeer po njih zdruzi epizodo s strežnika z istimi iz dodatkov Stremio.
    {"guid": "a677c0da-fac5-4cde-941a-7134223f14c8", "ime": "TheTVDB", "razlog": "jfRazlogTvdb"},
    # Safeer isce podnapise na spletu sam (core/podnapisi_splet.py, OpenSubtitles v3) - v predvajalniku.
    {"guid": "4b9ed42f-5185-48b5-9803-6ff2989014c4", "ime": "Open Subtitles", "razlog": "jfZnaPodnapisi", "safeer_zna": True},
    # Vgrajene podnapise Safeerjev predvajalnik bere iz posnetka sam (GStreamer, meni Podnapisi > Vgrajeni).
    {"guid": "cd893c24-b59e-4060-87b2-184070e1bf68", "ime": "Subtitle Extract", "razlog": "jfZnaVgrajeni", "safeer_zna": True},
    # TVHeadend Safeer poveze neposredno (Dodatki > TVHeadend), brez Jellyfina vmes.
    {"guid": "3fd018e5-5e78-4e58-b280-a0c068febee0", "ime": "TVHeadend", "razlog": "jfZnaTvheadend", "safeer_zna": True},
    # Safeer bere knjiznico Jellyfina neposredno; DLNA mu ne doda nicesar (zna pa DLNA tudi sam).
    {"guid": "33eba9cd-7da1-4720-967f-dd7dae7b74a1", "ime": "DLNA", "razlog": "jfZnaDlna", "safeer_zna": True},
)

#: Kategorije, za katere Safeer vsebine s strežnika (se) ne prikaze: TV v zivo iz Jellyfina zahteva odpiranje
#: prenosa (PlaybackInfo + LiveStreamId), tega Safeer se ne dela - vticnik deluje za druge odjemalce.
NI_V_SAFEERJU = frozenset({"livetv", "live tv"})

_RX_GUID = re.compile(r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$")
_RX_RAZLICICA = re.compile(r"^\d{1,9}(?:\.\d{1,9}){0,3}$")
_STANJA = ("Active", "Restart", "Deleted", "Superceded", "Superseded", "Malfunctioned", "NotSupported", "Disabled")


class NapakaJellyfin(Exception):
    """Napaka z razlogom za uporabnika (`koda`: prijava, skrbnik, zaganja, ni_najdeno, omrezje, neveljavno)."""

    def __init__(self, koda: str, sporocilo: str = "") -> None:
        super().__init__(sporocilo or koda)
        self.koda = koda


def cist_guid(vrednost: object) -> str:
    """GUID brez pomisljajev, z malimi crkami (Jellyfin ga v /Plugins pise brez, v katalogu s pomisljaji)."""
    v = str(vrednost or "").strip()
    return v.replace("-", "").lower() if _RX_GUID.match(v) else ""


def _razlicica_tuple(v: object) -> tuple:
    try:
        return tuple(int(x) for x in str(v or "").split("."))
    except ValueError:
        return ()


def je_uradni(url: object) -> bool:
    """Repozitorij Jellyfina (repo.jellyfin.org ali njegovo zrcalo), ne tretje osebe."""
    gostitelj = (urllib.parse.urlsplit(str(url or "")).hostname or "").lower()
    return gostitelj == URADNI_GOSTITELJ or gostitelj.endswith("." + URADNI_GOSTITELJ)


# ------------------------------------------------------------------------------------------ HTTP

def _zahteva(metoda: str, base: str, pot: str, zeton: str = "", parametri: Optional[dict] = None,
             rok: float = 10.0) -> object:
    """Klic vmesnika Jellyfin. 200 z JSON -> podatki, 204 -> None. Napake prevede v NapakaJellyfin."""
    url = media_servers._url(base, pot, parametri)
    if not media_servers.dovoljen_naslov(url):
        raise NapakaJellyfin("neveljavno", "Strežnik zunaj domačega omrežja zahteva HTTPS.")
    glave = {"Accept": "application/json", "User-Agent": "SafeerOS/1.0"}
    if zeton:
        glave.update(media_servers._glave_mediabrowser("jellyfin", zeton))
    else:
        glave["Authorization"] = media_servers._glava_mediabrowser()
    podatki = b"" if metoda == "POST" else None
    zahteva = urllib.request.Request(url, data=podatki, headers=glave, method=metoda)
    opener = urllib.request.build_opener(media_servers._HTTPSOnlyRedirect())
    try:
        with opener.open(zahteva, timeout=rok) as odgovor:
            telo = odgovor.read(8 * 1024 * 1024 + 1)
            if len(telo) > 8 * 1024 * 1024:
                raise NapakaJellyfin("omrezje", "Odgovor strežnika je prevelik.")
            if odgovor.status == 204 or not telo.strip():
                return None
            return json.loads(telo)
    except urllib.error.HTTPError as napaka:
        if napaka.code == 401:
            raise NapakaJellyfin("prijava", "Prijava na strežnik je potekla.") from napaka
        if napaka.code == 403:
            raise NapakaJellyfin("skrbnik", "Za to je potreben skrbniški račun strežnika.") from napaka
        if napaka.code == 404:
            raise NapakaJellyfin("ni_najdeno", "Strežnik tega ne pozna.") from napaka
        if napaka.code == 503:
            raise NapakaJellyfin("zaganja", "Strežnik se še zaganja.") from napaka
        raise NapakaJellyfin("omrezje", "Strežnik je vrnil napako %d." % napaka.code) from napaka
    except NapakaJellyfin:
        raise
    except (OSError, ValueError) as napaka:
        raise NapakaJellyfin("omrezje", "Strežnik se ne odziva.") from napaka


def odgovarja(base: str, rok: float = 4.0) -> bool:
    """Strežnik tece in je pripravljen (javni podatki, brez prijave; 503 med zagonom ne steje)."""
    try:
        info = _zahteva("GET", base, "/System/Info/Public", rok=rok)
    except NapakaJellyfin:
        return False
    return isinstance(info, dict) and bool(info.get("Id") or info.get("Version"))


# ------------------------------------------------------------------------------------------ branje

def _je_skrbnik(base: str, zeton: str) -> bool:
    jaz = _zahteva("GET", base, "/Users/Me", zeton)
    policy = (jaz or {}).get("Policy") if isinstance(jaz, dict) else None
    return bool(isinstance(policy, dict) and policy.get("IsAdministrator") is True)


def _namesceni(surovi: object) -> list:
    """Namesceni vticniki; od vec razlicic istega (Superceded/Superseded = stara, zamenjana) ostane trenutna."""
    po_id: dict = {}
    for p in surovi if isinstance(surovi, list) else []:
        if not isinstance(p, dict):
            continue
        ident = cist_guid(p.get("Id"))
        razlicica = str(p.get("Version") or "")
        if not ident or not _RX_RAZLICICA.match(razlicica):
            continue
        stanje = str(p.get("Status") or "Active")
        stanje = stanje if stanje in _STANJA else "Active"
        vnos = {"id": ident, "ime": str(p.get("Name") or "")[:120], "razlicica": razlicica,
                "opis": str(p.get("Description") or "")[:400], "stanje": stanje,
                "lahko_odstrani": bool(p.get("CanUninstall")) and stanje != "Deleted",
                # Vklop/izklop ima smisel za delujoc, izklopljen ali pravkar spremenjen vticnik.
                "lahko_preklopi": stanje in ("Active", "Disabled", "Restart"),
                "vklopljen": stanje not in ("Disabled", "Deleted", "NotSupported", "Malfunctioned")}
        def rang(v: dict) -> tuple:
            return (v["stanje"] not in ("Superceded", "Superseded"), _razlicica_tuple(v["razlicica"]))
        if ident not in po_id or rang(vnos) > rang(po_id[ident]):
            po_id[ident] = vnos
    return sorted((v for v in po_id.values() if v["stanje"] not in ("Superceded", "Superseded")),
                  key=lambda v: v["ime"].casefold())


def _katalog(surovi: object, namesceni: list) -> list:
    """Paketi iz /Packages: najnovejsa zdruzljiva razlicica, njen repozitorij in ali je uradni."""
    po_id = {v["id"]: v for v in namesceni}
    priporoceni = {cist_guid(p["guid"]): p for p in PRIPOROCENO}
    izid = []
    for paket in surovi if isinstance(surovi, list) else []:
        if not isinstance(paket, dict):
            continue
        guid = cist_guid(paket.get("guid"))
        ime = str(paket.get("name") or "").strip()[:120]
        razlicice = [v for v in (paket.get("versions") or []) if isinstance(v, dict)
                     and _RX_RAZLICICA.match(str(v.get("version") or ""))]
        if not guid or not ime or not razlicice:
            continue      # strežnik je izlocil vse nezdruzljive razlicice: paketa ni mogoce namestiti
        najnovejsa = max(razlicice, key=lambda v: _razlicica_tuple(v.get("version")))
        repo_url = str(najnovejsa.get("repositoryUrl") or "")
        kategorija = str(paket.get("category") or "").strip()[:40] or "Other"
        namescen = po_id.get(guid)
        prip = priporoceni.get(guid) or {}
        izid.append({
            "guid": guid, "ime": ime, "opis": str(paket.get("overview") or paket.get("description") or "").strip()[:400],
            "kategorija": kategorija, "lastnik": str(paket.get("owner") or "")[:60],
            "razlicica": str(najnovejsa.get("version")),
            "repozitorij": str(najnovejsa.get("repositoryName") or "")[:80], "repozitorij_url": repo_url[:500],
            "uradni": je_uradni(repo_url),
            "namescen": bool(namescen), "namescena_razlicica": namescen["razlicica"] if namescen else "",
            "posodobitev": bool(namescen) and _razlicica_tuple(najnovejsa.get("version")) > _razlicica_tuple(namescen["razlicica"]),
            "safeer_zna": prip.get("razlog", "") if prip.get("safeer_zna") else "",
            "priporocen": bool(prip) and not prip.get("safeer_zna"),
            "ni_v_safeerju": kategorija.casefold() in NI_V_SAFEERJU,
        })
    return sorted(izid, key=lambda p: (p["kategorija"].casefold(), p["ime"].casefold()))


def _priporoceno(katalog: Optional[list], namesceni: list) -> list:
    """Vrstica »Priporočeno«: vsak vnos z razlogom; ali je v katalogu strežnika in ali je ze namescen."""
    po_guid = {p["guid"]: p for p in (katalog or [])}
    namesceni_id = {v["id"] for v in namesceni}
    izid = []
    for p in PRIPOROCENO:
        guid = cist_guid(p["guid"])
        paket = po_guid.get(guid)
        izid.append({"guid": guid, "ime": p["ime"], "razlog": p["razlog"], "safeer_zna": bool(p.get("safeer_zna")),
                     "namescen": guid in namesceni_id, "v_katalogu": paket is not None,
                     "paket": paket})
    return izid


def stanje(base: str, zeton: str) -> dict:
    """Vse za ploscico Vticniki. Ne-skrbnik dobi samo branje (strežnik in priporocila) - brez gumbov, ki ne bi delovali."""
    info = _zahteva("GET", base, "/System/Info/Public")
    info = info if isinstance(info, dict) else {}
    streznik = {"ime": str(info.get("ServerName") or "")[:80], "razlicica": str(info.get("Version") or "")[:20]}
    if not _je_skrbnik(base, zeton):
        return {"ok": True, "skrbnik": False, "streznik": streznik, "namesceni": [], "katalog": [],
                "repozitoriji": [], "priporoceno": _priporoceno(None, []), "potreben_zagon": False}
    try:
        namesceni = _namesceni(_zahteva("GET", base, "/Plugins", zeton))
    except NapakaJellyfin as napaka:
        if napaka.koda != "skrbnik":
            raise
        # Strežnik je skrbniske pravice zavrnil (npr. zahteva z omrezja, ki ga skrbnik ne dovoli): samo branje.
        return {"ok": True, "skrbnik": False, "streznik": streznik, "namesceni": [], "katalog": [],
                "repozitoriji": [], "priporoceno": _priporoceno(None, []), "potreben_zagon": False}
    repozitoriji = []
    try:
        for r in _zahteva("GET", base, "/Repositories", zeton) or []:
            if isinstance(r, dict) and r.get("Url"):
                repozitoriji.append({"ime": str(r.get("Name") or "")[:80], "url": str(r.get("Url"))[:500],
                                     "vklopljen": r.get("Enabled") is not False, "uradni": je_uradni(r.get("Url"))})
    except NapakaJellyfin:
        pass
    napaka_kataloga = ""
    try:
        # Strežnik ob tem prenese manifeste repozitorijev z interneta - zato daljsi rok.
        katalog = _katalog(_zahteva("GET", base, "/Packages", zeton, rok=40.0), namesceni)
    except NapakaJellyfin as napaka:
        katalog, napaka_kataloga = [], napaka.koda
    return {"ok": True, "skrbnik": True, "streznik": streznik, "namesceni": namesceni, "katalog": katalog,
            "napaka_kataloga": napaka_kataloga, "repozitoriji": repozitoriji,
            "priporoceno": _priporoceno(katalog, namesceni),
            "potreben_zagon": any(v["stanje"] in ("Restart", "Deleted") for v in namesceni)}


# ------------------------------------------------------------------------------------------ spremembe

def _preveri_vticnik(ident: str, razlicica: str) -> tuple:
    g = cist_guid(ident)
    r = str(razlicica or "")
    if not g or not _RX_RAZLICICA.match(r):
        raise NapakaJellyfin("neveljavno", "Neveljaven vtičnik.")
    return g, r


def preklopi(base: str, zeton: str, ident: str, razlicica: str, vklopi: bool) -> dict:
    g, r = _preveri_vticnik(ident, razlicica)
    _zahteva("POST", base, "/Plugins/%s/%s/%s" % (g, urllib.parse.quote(r, safe=""), "Enable" if vklopi else "Disable"), zeton)
    return {"ok": True, "potreben_zagon": True}


def odstrani(base: str, zeton: str, ident: str, razlicica: str) -> dict:
    g, r = _preveri_vticnik(ident, razlicica)
    try:
        _zahteva("DELETE", base, "/Plugins/%s/%s" % (g, urllib.parse.quote(r, safe="")), zeton)
    except NapakaJellyfin as napaka:
        if napaka.koda != "ni_najdeno":
            raise
        # Starejsi strezniki (pred 10.7) poznajo samo pot brez razlicice (od 10.9 opusceno, se vedno deluje).
        _zahteva("DELETE", base, "/Plugins/%s" % g, zeton)
    return {"ok": True, "potreben_zagon": True}


def namesti(base: str, zeton: str, ime: str, guid: str, repozitorij_url: str = "") -> dict:
    """Namestitev najnovejse zdruzljive razlicice. Repozitorij mora biti eden od tistih, ki jih je skrbnik ze dodal
    na strezniku (Safeer repozitorijev ne dodaja), sicer ga ne posljemo."""
    g = cist_guid(guid)
    ime = str(ime or "").strip()
    if not g or not ime or len(ime) > 120 or any(c in ime for c in "\r\n"):
        raise NapakaJellyfin("neveljavno", "Neveljaven paket.")
    parametri = {"assemblyGuid": g}
    if repozitorij_url:
        znani = [str(r.get("Url") or "") for r in (_zahteva("GET", base, "/Repositories", zeton) or []) if isinstance(r, dict)]
        if repozitorij_url not in znani:
            raise NapakaJellyfin("neveljavno", "Repozitorija ni na strežniku.")
        parametri["repositoryUrl"] = repozitorij_url
    _zahteva("POST", base, "/Packages/Installed/" + urllib.parse.quote(ime, safe=""), zeton, parametri, rok=60.0)
    return {"ok": True, "potreben_zagon": True}


def ponovni_zagon(base: str, zeton: str, napredek: Optional[Callable[[str, int], None]] = None,
                  spi: Callable[[float], None] = time.sleep, ura: Callable[[], float] = time.monotonic,
                  rok_ustavitve: float = 20.0, rok: float = 180.0) -> dict:
    """POST /System/Restart, nato pocakamo, da strežnik neha odgovarjati in spet odgovori. Ce ustavitve ne
    opazimo (hiter zagon), velja zagon za koncan sele, ko noben vticnik ni vec v stanju Restart/Deleted."""
    javi = napredek or (lambda _faza, _s: None)
    _zahteva("POST", base, "/System/Restart", zeton)
    zacetek = ura()
    javi("ustavljam", 0)
    ustavljen = False
    while ura() - zacetek < rok_ustavitve:
        if not odgovarja(base, rok=3.0):
            ustavljen = True
            break
        spi(1.0)
    javi("zaganjam", int(ura() - zacetek))
    while ura() - zacetek < rok:
        if odgovarja(base, rok=3.0):
            if ustavljen:
                javi("pripravljen", int(ura() - zacetek))
                return {"ok": True, "sekund": int(ura() - zacetek)}
            try:
                cakajo = [v for v in _namesceni(_zahteva("GET", base, "/Plugins", zeton)) if v["stanje"] in ("Restart", "Deleted")]
            except NapakaJellyfin:
                cakajo = [True]
            if not cakajo:
                javi("pripravljen", int(ura() - zacetek))
                return {"ok": True, "sekund": int(ura() - zacetek)}
        spi(2.0)
    javi("napaka", int(ura() - zacetek))
    return {"ok": False, "napaka": "cas", "sekund": int(ura() - zacetek)}
