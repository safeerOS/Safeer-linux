"""Deljenje v Safeer Linku na Linuxu: besedilo, datoteka in zaslon - pošiljanje in sprejem.

Protokol je isti kot na telefonu (vsebina po HTTPS, nadzor pri Hubu):
 - besedilo:  POST /cast/share/text {device_id, target, text}
 - datoteka:  PUT  /cast/file?name&target&from  (telo = datoteka, glava x-safeer-sha256);
              Hub vrne svoj odtis in cilju pošlje share.file {name, path, sha256}
 - zaslon:    POST /cast/share/screen/start {device_id, target} -> {id, push_path};
              okvirje (4 bajti dolžine, big-endian + JPEG) potiskamo po eni TLS vtičnici;
              POST /cast/share/screen/stop {id}
 - sprejem datoteke: GET <hub>/<path>, preverjen SHA-256, v mapo prenosov.

Vse gre samo po TLS s pripetim odtisom Huba (link_tls). Zajem zaslona: na X11 primarni monitor prek Xlib (core/x11.py),
na Waylandu prek portala ScreenCast in PipeWire (core/portal_zaslon.py, uporabnik zaslon izbere enkrat); stisnjeno z
GdkPixbuf.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import select
import shutil
import socket
import ssl
import threading
import time
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import quote, urlparse

from core import gneca
from core import link_tls

KAKOVOST_JPEG = 60
NAJVEC_PX = 1280
RAZMIK_S = 0.25          # ~4 okvirji/s: dovolj za pogled, prijazno do procesorja
UTRIP_S = 4.0            # zadnji okvir ponovimo, da Hub ve, da še živimo
KOS = 64 * 1024


def _osnova(ws_naslov: str) -> str:
    u = urlparse(ws_naslov)
    return f"https://{u.netloc}"


#: Razlogi, zakaj datoteke ni mogoce oddati sredisci druge naprave (core/link_mesh.sredisce_naprave).
SPOROCILA_SREDISCA = {
    "naprava_pri_drugem_srediscu": "Naprava je povezana prek drugega središča; datoteke ji od tu ni mogoče poslati.",
    "sredisce_naprave_ni_dosegljivo": "Naprava v tem omrežju ni dosegljiva.",
}
#: Isto za deljenje zaslona (sredisce_za_zaslon); stran prevede po kodi, to besedilo je za dnevnik in ukazno vrstico.
SPOROCILA_ZASLONA = {
    "naprava_pri_drugem_srediscu": "Naprava je povezana prek drugega središča; zaslona ji od tu ni mogoče pokazati.",
    "sredisce_naprave_ni_dosegljivo": "Naprava v tem omrežju ni dosegljiva.",
    "zaslon_ni_na_voljo": "Ta naprava zaslona še ne zna prikazati. Posodobi Safeer na njej.",
    "hub_ni_znan": "Zaslon lahko deliš po varni povezavi s Safeer Linkom.",
    "konec_pri_napravi": "Naprava zaslona ne prikazuje več, zato se je deljenje končalo.",
}


def napaka_huba(koda: int, odgovor: dict) -> Dict[str, str]:
    """Stabilna koda napake in - pri zasedeni napravi - kdo z njo deli (kot na telefonu)."""
    oznaka = odgovor.get("koda") or odgovor.get("error_code") or ""
    if koda in (405, 501) or (koda == 404 and oznaka in ("", "ni_poti")):
        # Sredisce te poti nima: racunalnik s Safeerjem pred 2.1.45 (deljenje je znal samo Hub na Androidu).
        return {"sporocilo": "Središče tega še ne zna; posodobi Safeer na napravi, ki je središče.",
                "koda": "sredisce_ne_zna", "zasedenaOd": ""}
    return {
        "sporocilo": odgovor.get("napaka") or odgovor.get("error") or f"Hub je odgovoril {koda}",
        "koda": oznaka,
        "zasedenaOd": odgovor.get("busy_by_name") or odgovor.get("busy_by") or "",
    }


# ----------------------------------------------------------------------
# Besedilo
# ----------------------------------------------------------------------

def poslji_besedilo(ws_naslov: str, zeton: str, odtis: str, moj_id: str, cilj: str, besedilo: str) -> Tuple[bool, Dict[str, str]]:
    koda, odgovor, _ = link_tls.zahteva(_osnova(ws_naslov) + "/cast/share/text",
                                        {"device_id": moj_id, "target": cilj, "text": besedilo},
                                        zeton=zeton, timeout=8.0, pripeti=odtis)
    if koda == 200:
        return True, {}
    return False, napaka_huba(koda, odgovor)


def preimenuj_napravo(ws_naslov: str, zeton: str, odtis: str, id_naprave: str, ime: str) -> Tuple[bool, str, Dict[str, str]]:
    koda, odgovor, _ = link_tls.zahteva(_osnova(ws_naslov) + "/cast/devices/rename",
                                        {"device_id": id_naprave, "name": ime.strip()},
                                        zeton=zeton, timeout=8.0, pripeti=odtis)
    if koda == 200:
        return True, str(odgovor.get("name", "") or ""), {}
    return False, "", napaka_huba(koda, odgovor)


# ----------------------------------------------------------------------
# Datoteka - pošiljanje
# ----------------------------------------------------------------------

def _sha256_datoteke(pot: str) -> str:
    h = hashlib.sha256()
    with open(pot, "rb") as f:
        while True:
            kos = f.read(KOS)
            if not kos:
                break
            h.update(kos)
    return h.hexdigest()


#: Prekinjeno oddajo (izpad Wi-Fi, spanje naprave) poskusimo znova toliko krat; vmes cakamo vedno dlje.
POSKUSOV = 6
CAKANJE_S = (2.0, 4.0, 8.0, 15.0, 30.0)
#: Odgovori sredisca, po katerih nov poskus nima smisla (napacen zeton, ni prostora, prevelika, napacen odtis ...).
_KONCNE_NAPAKE = (400, 401, 403, 404, 413, 507)


def _odmik_na_hubu(gostitelj: str, vrata: int, odtis: str, zeton: str, cilj: str, sha: str,
                   velikost: int) -> Tuple[bool, int, int]:
    """(sredisce zna nadaljevati, koliko ze ima, koda HTTP). Starejse sredisce na HEAD /cast/file odgovori 404:
    (False, 0, 404); brez odgovora (False, 0, 0)."""
    povezava = link_tls._PripetaHttps(gostitelj, vrata, odtis, 10.0)
    try:
        povezava.request("HEAD", "/cast/file?target=" + quote(cilj, safe="") + "&sha256=" + sha + "&size=%d" % velikost,
                         headers={"X-Safeer-Token": zeton})
        odgovor = povezava.getresponse()
        odgovor.read()
        if odgovor.status != 200 or odgovor.getheader("x-safeer-resume") != "1":
            return False, 0, int(odgovor.status)
        n = int(odgovor.getheader("x-safeer-offset") or 0)
        return True, (n if 0 <= n < velikost else 0), 200
    except link_tls.NeujemanjeOdtisa:
        raise
    except Exception:  # noqa: BLE001 - brez odgovora: oddaja gre od zacetka
        return False, 0, 0
    finally:
        try:
            povezava.close()
        except Exception:
            pass


def poslji_datoteko(ws_naslov: str, zeton: str, odtis: str, moj_id: str, cilj: str, pot: str,
                    napredek: Optional[Callable[[int], None]] = None, mapa: str = "",
                    spi: Callable[[float], None] = time.sleep) -> Tuple[bool, Dict[str, str]]:
    """Pošlje datoteko Hubu za cilj. Vrne (uspeh, napaka). Napredek dobi odstotek.

    Brez meje 4 GB in z nadaljevanjem (lastnik, 11. 10. 2026): ce se povezava prekine, vprasamo sredisce, koliko ze
    ima (HEAD), in posljemo samo se ostanek - do POSKUSOV krat. Starejse sredisce nadaljevanja ne zna: takrat nov
    poskus posilja od zacetka. `mapa`: relativna mapa pri posiljanju cele mape (cilj jo ustvari)."""
    ime = os.path.basename(pot)
    velikost = os.path.getsize(pot)
    odtis_dat = _sha256_datoteke(pot)
    u = urlparse(ws_naslov)
    gostitelj, vrata = u.hostname or "127.0.0.1", u.port or 443
    cilj_pot = ("/cast/file?name=" + quote(ime, safe="") + "&target=" + quote(cilj, safe="")
                + "&from=" + quote(moj_id, safe="") + ("&dir=" + quote(mapa, safe="") if mapa else ""))
    zadnji = [-1]

    def javi(poslano: int) -> None:
        odst = int(poslano * 100 / velikost) if velikost else 100
        if napredek and odst != zadnji[0]:
            zadnji[0] = odst
            napredek(odst)

    zadnja_napaka: Dict[str, str] = {}
    for poskus in range(POSKUSOV):
        if poskus:
            spi(CAKANJE_S[min(poskus - 1, len(CAKANJE_S) - 1)])
        try:
            zna, odmik, koda_glave = _odmik_na_hubu(gostitelj, vrata, odtis, zeton, cilj, odtis_dat, velikost)
        except link_tls.NeujemanjeOdtisa:
            return False, {"sporocilo": "Hub ima drugo potrdilo, kot je bilo ob seznanitvi.", "koda": "odtis_se_ne_ujema", "zasedenaOd": ""}
        izid, koda_http, j = _oddaja(gostitelj, vrata, odtis, zeton, cilj_pot, pot, velikost, odtis_dat,
                                     odmik if zna else 0, zna, javi)
        if izid == "ok":
            hubov = str(j.get("sha256", "") or "")
            if hubov and hubov != odtis_dat:
                return False, {"sporocilo": "Datoteka je po poti spremenjena (odtis se ne ujema).", "koda": "odtis_se_ne_ujema", "zasedenaOd": ""}
            return True, {}
        if izid == "odtis":
            return False, {"sporocilo": "Hub ima drugo potrdilo, kot je bilo ob seznanitvi.", "koda": "odtis_se_ne_ujema", "zasedenaOd": ""}
        if koda_http:
            zadnja_napaka = napaka_huba(koda_http, j)
            if koda_http in _KONCNE_NAPAKE:
                return False, zadnja_napaka
        elif koda_glave == 401:
            # Sredisce nas ne pozna (zavrglo je telo in zaprlo povezavo): nov poskus ne pomaga.
            return False, {"sporocilo": "Naprava ni seznanjena.", "koda": "naprava_ni_seznanjena", "zasedenaOd": ""}
        else:
            zadnja_napaka = {"sporocilo": "Pošiljanje ni uspelo: " + str(j.get("napaka") or "povezava prekinjena"),
                             "koda": "posiljanje_ni_uspelo", "zasedenaOd": ""}
    return False, zadnja_napaka or {"sporocilo": "Pošiljanje ni uspelo.", "koda": "posiljanje_ni_uspelo", "zasedenaOd": ""}


def _oddaja(gostitelj: str, vrata: int, odtis: str, zeton: str, cilj_pot: str, pot: str, velikost: int, odtis_dat: str,
            odmik: int, zna: bool, javi: Callable[[int], None]) -> Tuple[str, int, dict]:
    """Ena oddaja (PUT) od `odmik` do konca. Vrne ("ok" | "napaka" | "odtis", koda HTTP ali 0, json odgovora).

    Velika oddaja: ob gneci na domaci liniji jo krajevni konec Global Linka odpre skozi telefon (core/gneca.py)."""
    povezava = link_tls._PripetaHttps(gostitelj, vrata, odtis, 30.0, odpri=gneca.odpri_oddajo)
    try:
        povezava.putrequest("PUT", cilj_pot)
        povezava.putheader("X-Safeer-Token", zeton)
        povezava.putheader("Content-Type", "application/octet-stream")
        povezava.putheader("Content-Length", str(velikost - odmik))
        povezava.putheader("x-safeer-sha256", odtis_dat)
        if zna:
            povezava.putheader("x-safeer-size", str(velikost))
            povezava.putheader("x-safeer-offset", str(odmik))
        povezava.endheaders()
        poslano = odmik
        prekinjeno: Optional[Exception] = None
        with open(pot, "rb") as f:
            f.seek(odmik)
            while True:
                kos = f.read(KOS)
                if not kos:
                    break
                try:
                    povezava.send(kos)
                except OSError as e:
                    # Sredisce je oddajo zavrnilo ali se je povezava prekinila: razlog je morda ze v odgovoru.
                    prekinjeno = e
                    break
                poslano += len(kos)
                javi(poslano)
        try:
            odgovor = povezava.getresponse()
        except Exception as e:  # noqa: BLE001
            return "napaka", 0, {"napaka": str(prekinjeno or e)}
        telo = odgovor.read().decode("utf-8", "replace")
        try:
            j = json.loads(telo) if telo else {}
        except json.JSONDecodeError:
            j = {}
        j = j if isinstance(j, dict) else {}
        return ("ok" if odgovor.status == 200 else "napaka"), (0 if odgovor.status == 200 else odgovor.status), j
    except link_tls.NeujemanjeOdtisa:
        return "odtis", 0, {}
    except Exception as e:  # noqa: BLE001 - povezava: nov poskus
        return "napaka", 0, {"napaka": str(e) or type(e).__name__}
    finally:
        try:
            povezava.close()
        except Exception:
            pass


# ----------------------------------------------------------------------
# Datoteka - sprejem
# ----------------------------------------------------------------------

def mapa_prenosov() -> str:
    """Mapa prenosov po XDG (na slovenskem Mintu »Prejemi«; lastnik, 18. 10. 2026). Prej sta bili tu samo Prenosi in
    Downloads - na slovenskem namizju je zato prejeta datoteka koncala v novi mapi Prenosi poleg prave Prejemi."""
    from core import splet_prenosi
    return splet_prenosi.mapa_prenosov(None)


def varno_ime(ime: str) -> str:
    ime = os.path.basename(ime.replace("\\", "/")).strip() or "datoteka"
    return "".join(z if (z.isalnum() or z in " ._-()[]") else "_" for z in ime)[:180]


def enolicna_pot(mapa: str, ime: str) -> str:
    osnova, konc = os.path.splitext(ime)
    pot = os.path.join(mapa, ime)
    n = 1
    while os.path.exists(pot):
        pot = os.path.join(mapa, f"{osnova} ({n}){konc}")
        n += 1
    return pot


def varna_podmapa(mapa: str) -> str:
    """Relativna mapa iz share.file (`dir`, posiljanje cele mape): samo varna imena, brez »..« in absolutnih poti."""
    deli = [varno_ime(d) for d in str(mapa or "").replace("\\", "/").split("/") if d.strip() not in ("", ".", "..")]
    return os.path.join(*deli[:16]) if deli else ""


def _ciljna_mapa(mapa: Optional[str], podmapa: str) -> str:
    koren = mapa or mapa_prenosov()
    pod = varna_podmapa(podmapa)
    if not pod:
        return koren
    cilj = os.path.realpath(os.path.join(koren, pod))
    if not cilj.startswith(os.path.realpath(koren) + os.sep):
        return koren                      # ne sme iz mape prenosov
    os.makedirs(cilj, exist_ok=True)
    return cilj


def prevzemi_datoteko(ws_naslov: str, odtis: str, pot_huba: str, ime: str, pricakovan_odtis: str,
                      mapa: Optional[str] = None, podmapa: str = "", velikost: int = -1) -> Tuple[Optional[str], str]:
    """Prenese datoteko s Huba v mapo prenosov. Vrne (pot, "") ali (None, razlog)."""
    cilj, razlog, _koda = _prevzemi(ws_naslov, odtis, pot_huba, ime, pricakovan_odtis, mapa, podmapa,
                                    velikost=velikost)
    return cilj, razlog


def prevzemi_pri_srediscih(sredisca, pot_huba: str, ime: str, pricakovan_odtis: str,
                           mapa: Optional[str] = None, podmapa: str = "", velikost: int = -1) -> Tuple[Optional[str], str]:
    """Datoteko prevzame pri prvem sredisci s seznama [(naslov, odtis), ...], ki jo ima. Vrne kot prevzemi_datoteko.

    Pot v `share.file` je relativna na sredisce, ki je datoteko sprejelo - to pa je lahko nase (posiljatelj jo je
    oddal nam; tako delajo racunalniki) ali posiljateljevo (oddal jo je svojemu, sporocilo je prislo cez sosede).
    Iz sporocila se tega ne vidi, zato vprasamo po vrsti. Naslednje sredisce pride na vrsto samo, ce prejsnje
    odgovori, da te datoteke nima (404); vsaka druga napaka je koncna (ni prostora, napacen odtis, ni povezave)."""
    razlog = "Središče ni znano."
    for naslov, odtis in sredisca:
        if not naslov or not odtis:
            continue
        cilj, razlog, koda = _prevzemi(naslov, odtis, pot_huba, ime, pricakovan_odtis, mapa, podmapa,
                                       velikost=velikost)
        if cilj or koda != 404:
            return cilj, razlog
    return None, razlog


def _prevzemi(ws_naslov: str, odtis: str, pot_huba: str, ime: str, pricakovan_odtis: str,
              mapa: Optional[str] = None, podmapa: str = "",
              spi: Callable[[float], None] = time.sleep, velikost: int = -1) -> Tuple[Optional[str], str, int]:
    """(pot, "", 200) ali (None, razlog, koda HTTP sredisca); koda 0 = do odgovora ni prislo ali prenos ni uspel.

    `velikost` (share.file size, -1 = neznana): ce po prejemu na disku ne bi ostala rezerva, prevzema ne zacnemo -
    sredisce datoteko obdrzi za nov poskus (prej je prejem pisal do polnega diska, ENOSPC; koncni pregled 19. 10. 2026).

    Prekinjen prevzem (izpad Wi-Fi) nadaljuje, kjer je ostal (Range), do POSKUSOV krat; kar je ze prislo, je v
    datoteki ».safeer-delno« ob cilju in dobi koncno ime sele, ko je cela in se odtis ujema."""
    u = urlparse(ws_naslov)
    gostitelj, vrata = u.hostname or "127.0.0.1", u.port or 443
    mapa_cilja = _ciljna_mapa(mapa, podmapa)
    if velikost >= 0 and not _dovolj_prostora(mapa_cilja, velikost):
        return None, "ni prostora", 0
    delno = enolicna_pot(mapa_cilja, varno_ime(ime) + ".safeer-delno")
    razlog, koda = "", 0
    try:
        for poskus in range(POSKUSOV):
            if poskus:
                spi(CAKANJE_S[min(poskus - 1, len(CAKANJE_S) - 1)])
            izid, razlog, koda = _prevzem_enkrat(gostitelj, vrata, odtis, pot_huba, delno, pricakovan_odtis)
            if izid == "ok":
                cilj = enolicna_pot(mapa_cilja, varno_ime(ime))
                os.replace(delno, cilj)
                return cilj, "", 200
            if izid == "koncno":
                break
        _odstrani(delno)
        return None, razlog, koda
    except Exception as e:  # noqa: BLE001
        _odstrani(delno)
        return None, str(e), 0


def _dovolj_prostora(mapa: str, bajtov: int) -> bool:
    """Ali po prejemu `bajtov` na disku ostane rezerva (link_viri.rezerva_diska, kot pri srediscu in drugod v Linku).
    Prej je prejem pisal do polnega diska (ENOSPC) in sele nato delno datoteko zbrisal - za trenutek je bil disk
    sistema poln (koncni pregled 19. 10. 2026)."""
    try:
        from core import link_viri
        return shutil.disk_usage(mapa).free - max(0, bajtov) >= link_viri.rezerva_diska(mapa)
    except (OSError, ImportError):
        return True                      # prostora ne znamo izmeriti: kot prej (ENOSPC ostane varovalka)


def _odstrani(pot: str) -> None:
    try:
        os.remove(pot)
    except OSError:
        pass


def _prevzem_enkrat(gostitelj: str, vrata: int, odtis: str, pot_huba: str, delno: str,
                    pricakovan_odtis: str) -> Tuple[str, str, int]:
    """("ok" | "znova" | "koncno", razlog, koda HTTP). Nadaljuje od velikosti `delno`, ce sredisce zna Range."""
    imamo = os.path.getsize(delno) if os.path.isfile(delno) else 0
    povezava = link_tls._PripetaHttps(gostitelj, vrata, odtis, 30.0)
    try:
        povezava.request("GET", pot_huba, headers={"Range": "bytes=%d-" % imamo} if imamo else {})
        odgovor = povezava.getresponse()
        if odgovor.status not in (200, 206):
            return "koncno", f"Hub je odgovoril {odgovor.status}", int(odgovor.status)
        h = hashlib.sha256()
        if odgovor.status == 206 and imamo:
            with open(delno, "rb") as f:
                for kos in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(kos)
            nacin = "ab"
        else:
            nacin = "wb"                      # sredisce Range ne zna (ali ga ni bilo): od zacetka
        pricakovan = pricakovan_odtis or (odgovor.getheader("x-safeer-sha256") or "")
        try:
            with open(delno, nacin) as f:
                while True:
                    kos = odgovor.read(KOS)
                    if not kos:
                        break
                    f.write(kos)
                    h.update(kos)
        except (OSError, http.client.HTTPException) as e:
            if isinstance(e, OSError) and e.errno == 28:      # ENOSPC
                return "koncno", "ni prostora", 0
            return "znova", str(e) or type(e).__name__, 0
        dolzina = odgovor.getheader("Content-Length")
        if dolzina and dolzina.isdigit():
            pricakovana = int(dolzina) + (imamo if odgovor.status == 206 else 0)
            if os.path.getsize(delno) < pricakovana:
                return "znova", "prevzem prekinjen", 0
        if pricakovan and h.hexdigest() != pricakovan:
            _odstrani(delno)
            return "koncno", "prstni odtis se ne ujema", 0
        return "ok", "", 200
    except link_tls.NeujemanjeOdtisa as e:
        return "koncno", str(e), 0
    except Exception as e:  # noqa: BLE001 - povezava: nov poskus
        return "znova", str(e) or type(e).__name__, 0
    finally:
        try:
            povezava.close()
        except Exception:
            pass


# ----------------------------------------------------------------------
# Zaslon
# ----------------------------------------------------------------------

def gledalec_pri_srediscih(sredisca, pot: str, timeout: float = 4.0) -> Tuple[str, str]:
    """Kje je stran gledalca iz `share.screen`: (naslov strani, odtis sredisca) ali ("", ""), ce je nima nobeno.

    Pot v sporocilu je relativna na sredisce, ki je deljenje sprejelo - nase (posiljatelj ga je zacel pri nas; tako
    delajo racunalniki, docs/LINK-MESH.md pravilo 9) ali posiljateljevo (telefon ga zacne pri svojem, sporocilo je
    prislo cez sosede). Iz sporocila se tega ne vidi, zato vprasamo po vrsti `sredisca` = [(naslov, odtis), ...];
    zmaga prvo, ki stran ima (200). Izmerjeno 5. 10. 2026: racunalnik je iskal samo pri svojem in telefonov zaslon
    se je odprl kot {"error": "Ni te poti."}."""
    for naslov, odtis in sredisca:
        if not naslov or not odtis:
            continue
        u = urlparse(naslov)
        povezava = link_tls._PripetaHttps(u.hostname or "127.0.0.1", u.port or 443, odtis, timeout)
        odgovor = None
        try:
            povezava.request("GET", pot)
            odgovor = povezava.getresponse()
            koda = odgovor.status
        except Exception:  # noqa: BLE001 - nedosegljivo sredisce ali tuje potrdilo: vprasamo naslednje
            koda = 0
        finally:
            for odprto in (odgovor, povezava):
                try:
                    if odprto is not None:
                        odprto.close()
                except Exception:
                    pass
        if koda == 200:
            return _osnova(naslov) + pot, odtis
    return "", ""


def sredisce_za_zaslon(sredisce_naprave: Callable[[str], tuple], seja: Callable[[str, str], tuple],
                       lastno: Callable[[], tuple], cilj: str) -> tuple:
    """Pri katerem sredisci posiljatelj zacne deljenje zaslona za napravo `cilj`.

    Link Mesh: vsaka naprava ima svoje sredisce in zaslon ji pokaze ONO (gledalec bere okvirje pri njem), zato
    deljenje zacnemo tam - s sejo s podpisom, kot oddamo datoteko. Napravi brez svojega sredisca (prijavljena je
    pri tistem, na katerega smo prijavljeni mi) zaslon pokaze to sredisce.

    sredisce_naprave(cilj) -> ((naslov, odtis), "") | (None, "") | (None, koda)      (link_mesh.sredisce_naprave)
    seja(naslov, odtis)    -> (sejni zeton ali None, nas id pri tem sredisci)
    lastno()               -> ((naslov, zeton, odtis, nas id), "") za sredisce, na katero smo prijavljeni (nase ali
                              tuje); (None, "hub_ni_znan"), ce zanj nimamo zetona.
    Vrne ((naslov, zeton, odtis, nas id), opis) ali (None, {"sporocilo", "koda", "zasedenaOd"}). V opisu je
    `pri_napravi`: True, kadar je izbrano sredisce ciljne naprave same. Caka na omrezje."""
    def napaka(koda: str) -> tuple:
        return None, {"sporocilo": SPOROCILA_ZASLONA.get(koda, koda), "koda": koda, "zasedenaOd": ""}

    izbrano, koda = sredisce_naprave(cilj)
    if koda:
        return napaka(koda)
    if izbrano is not None:
        naslov, odtis = izbrano
        zeton, nas_id = seja(naslov, odtis)
        if not zeton:
            return napaka("sredisce_naprave_ni_dosegljivo")
        return (naslov, zeton, odtis, nas_id), {"pri_napravi": True}
    nase, koda = lastno()
    if nase is None:
        return napaka(koda or "zaslon_ni_na_voljo")
    return nase, {}


class _ZajemPortala:
    """Wayland: seja portala in okvirji PipeWire z vmesnikom x11.Povezava (zajemi, zapri)."""

    def __init__(self, seja, slike) -> None:
        self.seja, self.slike = seja, slike

    def zajemi(self):
        return self.slike.zajemi()

    def zapri(self) -> None:
        self.slike.zapri()
        self.seja.zapri()


class DeljenjeZaslona:
    """Deli zaslon tega računalnika z eno napravo, dokler ga uporabnik ne prekine."""

    def __init__(self, ws_naslov: str, zeton: str, odtis: str, moj_id: str, cilj: str, ime_cilja: str,
                 ob_spremembi: Optional[Callable[[dict], None]] = None,
                 sredisce: Optional[Callable[[], tuple]] = None) -> None:
        #: Link Mesh: kje deljenje zacnemo, izvemo sele v delovni niti (prijava s podpisom caka na omrezje).
        #: Klic vrne ((naslov, zeton, odtis, moj id), {}) ali (None, napaka) - glej sredisce_za_zaslon.
        self._sredisce = sredisce
        self._pri_napravi = False
        self.ws_naslov = ws_naslov
        self.zeton = zeton
        self.odtis = odtis
        self.moj_id = moj_id
        self.cilj = cilj
        self.ime_cilja = ime_cilja
        self.ob_spremembi = ob_spremembi
        self.tece = False
        self.napaka = ""
        self.koda = ""
        self.zasedena_od = ""
        self._id = ""
        self._ustavi = threading.Event()
        self._nit: Optional[threading.Thread] = None

    def stanje(self) -> dict:
        return {"tece": self.tece, "cilj": self.cilj, "ime": self.ime_cilja, "napaka": self.napaka,
                "koda": self.koda, "zasedenaOd": self.zasedena_od}

    def _javi(self) -> None:
        if self.ob_spremembi:
            self.ob_spremembi(self.stanje())

    def zacni(self) -> None:
        # libX11 in rokovalnik napak X nastavimo tu (glavna nit), ne v niti zajema: GDK med pastjo napak (trap push/pop)
        # bi rokovalnik, nastavljen iz druge niti, ob pop prepisal.
        try:
            from core import x11
            x11._knjiznica()
        except Exception:  # noqa: BLE001 - brez X11 zajem javi napako sam
            pass
        self._ustavi.clear()
        self._nit = threading.Thread(target=self._tok, daemon=True)
        self._nit.start()

    def ustavi(self) -> None:
        self._ustavi.set()

    # --- odgovor sredisca ------------------------------------------------
    @staticmethod
    def _odgovor_sredisca(vticnik, cakaj_s: float = 0.0) -> Optional[dict]:
        """Odgovor sredisca na nas tok okvirjev, ce je ze prisel; None = sredisce se sprejema.

        Sredisce med deljenjem ne poslje nicesar. Ko deljenje konca samo (nihce vec ne gleda, ustavlja se),
        odgovori z razlogom in zapre povezavo - po tem locimo konec deljenja od padle povezave. Vrne telo odgovora;
        {} = povezava je zaprta brez berljivega razloga."""
        try:
            pripravljen = bool(vticnik.pending()) or bool(select.select([vticnik], [], [], cakaj_s)[0])
        except Exception:  # noqa: BLE001 - vticnik brez opisnika (preizkusi) ali ze zaprt
            return None
        if not pripravljen:
            return None
        surovo = b""
        try:
            # Prvo branje kratko: zapis TLS brez podatkov (vstopnica seje takoj po rokovanju) ne sme ustaviti okvirjev.
            vticnik.settimeout(0.05)
            for _ in range(8):
                kos = vticnik.recv(8192)
                if not kos:
                    break
                surovo += kos
                vticnik.settimeout(1.0)
                glava, locilo, telo = surovo.partition(b"\r\n\r\n")
                dolzina = re.search(rb"(?i)content-length:\s*(\d+)", glava) if locilo else None
                if locilo and (dolzina is None or len(telo) >= int(dolzina.group(1))):
                    break
        except (socket.timeout, ssl.SSLWantReadError):
            if not surovo:
                return None
        except OSError:
            pass
        finally:
            try:
                vticnik.settimeout(None)
            except Exception:
                pass
        try:
            j = json.loads(surovo.partition(b"\r\n\r\n")[2].decode("utf-8"))
        except Exception:
            j = {}
        return j if isinstance(j, dict) else {}

    def _konec_pri_srediscu(self, odgovor: dict) -> None:
        """Deljenje je koncalo sredisce. Ce zato, ker ga nihce vec ne gleda, to povemo; sicer je navaden konec."""
        if str(odgovor.get("razlog") or "") == "ni_gledalcev":
            self.koda = "konec_pri_napravi"
            self.napaka = SPOROCILA_ZASLONA["konec_pri_napravi"]

    # --- zajem -----------------------------------------------------------
    @staticmethod
    def zajem_na_voljo() -> Tuple[bool, str]:
        from core import seja_prikaza
        if seja_prikaza.je_wayland():
            # Prej: »Zajem zaslona na Waylandu še ni na voljo« samo brez DISPLAY; z XWaylandom pa crna slika.
            from core import portal_zaslon
            if portal_zaslon.zmoznosti()["zajem"] and portal_zaslon.gstreamer_pipewire():
                return True, ""
            return False, portal_zaslon.SPOROCILA["ni_portala"]
        try:
            # Xlib (core/x11.py), ne Gdk: ista pot v procesu GTK3 in GTK4 (Gdk 3 se v GTK4 ne da naloziti).
            from core import x11
            p = x11.Povezava()
            try:
                if not all(p.velikost_korena()):
                    return False, "Zaslona ni mogoče zajeti."
            finally:
                p.zapri()
            return True, ""
        except Exception as e:  # noqa: BLE001
            return False, f"Zajem zaslona ni na voljo: {e}"

    def _okvir(self) -> Optional[bytes]:
        """En okvir zaslona kot JPEG. Tece v niti deljenja: ima svojo povezavo z X (ne GDK-jeve) ali svojo sejo
        portala (Wayland). Vec monitorjev (X11): primarni monitor, ne ves koren."""
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf, GLib
        from core import x11
        if getattr(self, "_x11", None) is None:
            self._pripravi_zajem()
        zajem = self._x11.zajemi(getattr(self, "_obmocje", None)) if isinstance(self._x11, x11.Povezava) \
            else self._x11.zajemi()
        if zajem is None:
            return None
        s, v, rgb = zajem
        pb = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(rgb), GdkPixbuf.Colorspace.RGB, False, 8, s, v, s * 3)
        if max(s, v) > NAJVEC_PX:
            if s >= v:
                ns, nv = NAJVEC_PX, max(1, int(v * NAJVEC_PX / s))
            else:
                ns, nv = max(1, int(s * NAJVEC_PX / v)), NAJVEC_PX
            pb = pb.scale_simple(ns, nv, GdkPixbuf.InterpType.BILINEAR)
        ok, podatki = pb.save_to_bufferv("jpeg", ["quality"], [str(KAKOVOST_JPEG)])
        return bytes(podatki) if ok else None

    def _pripravi_zajem(self) -> None:
        """Vir slik: X11 (primarni monitor, ce jih je vec) ali portal na Waylandu. Portal vprasa uporabnika samo
        prvic (zeton obnovitve, core/portal_zaslon) - zato ga odpremo ENKRAT ob zacetku (_tok), ne ob vsakem okvirju."""
        from core import seja_prikaza, x11
        self._obmocje = None
        if seja_prikaza.je_wayland():
            from core import portal_zaslon
            seja = portal_zaslon.Seja(vnos=False)
            try:
                seja.odpri()
                self._x11 = _ZajemPortala(seja, portal_zaslon.SlikePipewire(seja, NAJVEC_PX))
            except Exception:
                seja.zapri()
                raise
            return
        self._x11 = x11.Povezava()
        m = x11.primarni_monitor(self._x11)
        if m and len(self._x11.monitorji()) > 1:
            self._obmocje = (m["x"], m["y"], m["sirina"], m["visina"])

    def _zapri_x11(self) -> None:
        p, self._x11 = getattr(self, "_x11", None), None
        if p is not None:
            try:
                p.zapri()
            except Exception:  # noqa: BLE001
                pass

    def _tok(self) -> None:
        vticnik = None
        try:
            from core import seja_prikaza
            if seja_prikaza.je_wayland():
                # Najprej zaslon (portal): ce ga uporabnik ne dovoli, deljenja pri srediscu sploh ne zacnemo.
                from core import portal_zaslon
                try:
                    self._pripravi_zajem()
                except portal_zaslon.NapakaPortala as e:
                    # Kode za assets/link/link.js (prevodi): zavrnjeno = isto kot zavrnjeno dovoljenje na napravi.
                    self.napaka = portal_zaslon.SPOROCILA.get(e.koda, str(e))
                    self.koda = {"zavrnjeno": "dovoljenje_zavrnjeno", "rok": "zajem_ni_potrjen"}.get(e.koda, "zajem_ni_mogoc")
                    return          # stanje javi `finally`
            if self._sredisce is not None:
                izbrano, n = self._sredisce()
                if izbrano is None:
                    self.napaka, self.koda = str(n.get("sporocilo") or ""), str(n.get("koda") or "")
                    self.zasedena_od = str(n.get("zasedenaOd") or "")
                    return          # stanje javi `finally`
                self.ws_naslov, self.zeton, self.odtis, self.moj_id = izbrano
                self._pri_napravi = bool(n.get("pri_napravi"))
            koda, odgovor, _ = link_tls.zahteva(_osnova(self.ws_naslov) + "/cast/share/screen/start",
                                                {"device_id": self.moj_id, "target": self.cilj},
                                                zeton=self.zeton, timeout=8.0, pripeti=self.odtis)
            if koda != 200:
                n = napaka_huba(koda, odgovor)
                if self._pri_napravi and n["koda"] == "sredisce_ne_zna":
                    # To sredisce JE ciljna naprava (Link Mesh). Ce poti nima, tujega zaslona ne zna prikazati -
                    # danes sredisce racunalnika. »Posodobi Safeer na napravi, ki je središče« bi zavedlo.
                    n = {"sporocilo": SPOROCILA_ZASLONA["zaslon_ni_na_voljo"], "koda": "zaslon_ni_na_voljo", "zasedenaOd": ""}
                self.napaka, self.koda, self.zasedena_od = n["sporocilo"], n["koda"], n["zasedenaOd"]
                self._javi()
                return
            self._id = str(odgovor.get("id", "") or "")
            pot = str(odgovor.get("push_path", "") or "")
            if not self._id or not pot:
                self.napaka = "Hub ni vrnil poti za deljenje."
                self._javi()
                return
            u = urlparse(self.ws_naslov)
            gostitelj, vrata = u.hostname or "127.0.0.1", u.port or 443
            surov = socket.create_connection((gostitelj, vrata), timeout=10.0)
            surov.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            vticnik, _ = link_tls.ovij(surov, gostitelj, self.odtis)
            vticnik.settimeout(None)
            vticnik.sendall((f"POST {pot} HTTP/1.1\r\nHost: {gostitelj}\r\n"
                             f"x-safeer-token: {self.zeton}\r\nContent-Type: application/octet-stream\r\n"
                             "Connection: close\r\n\r\n").encode("ascii"))
            self.tece = True
            self.napaka = self.koda = self.zasedena_od = ""
            self._javi()
            zadnji = b""
            zadnji_cas = 0.0
            while not self._ustavi.is_set():
                zacetek = time.time()
                okvir = None
                try:
                    okvir = self._okvir()
                except Exception:  # noqa: BLE001 - en neuspel zajem ne konca deljenja
                    okvir = None
                if okvir is not None and okvir != zadnji:
                    vticnik.sendall(len(okvir).to_bytes(4, "big") + okvir)
                    zadnji, zadnji_cas = okvir, time.time()
                elif zadnji and time.time() - zadnji_cas > UTRIP_S:
                    vticnik.sendall(len(zadnji).to_bytes(4, "big") + zadnji)
                    zadnji_cas = time.time()
                konec = self._odgovor_sredisca(vticnik)
                if konec is not None:
                    self._konec_pri_srediscu(konec)
                    break
                ostane = RAZMIK_S - (time.time() - zacetek)
                if ostane > 0:
                    self._ustavi.wait(ostane)
        except link_tls.NeujemanjeOdtisa:
            self.napaka, self.koda = "Hub ima drugo potrdilo, kot je bilo ob seznanitvi.", "odtis_se_ne_ujema"
        except Exception as e:  # noqa: BLE001
            if not self._ustavi.is_set():
                # Pisanje je padlo. Ce je sredisce pred tem odgovorilo, je deljenje koncalo ono - to ni napaka.
                konec = self._odgovor_sredisca(vticnik, 1.0) if vticnik is not None else None
                if konec:
                    self._konec_pri_srediscu(konec)
                else:
                    self.napaka = f"Deljenje zaslona je padlo: {e}"
        finally:
            self.tece = False
            self._zapri_x11()
            if vticnik is not None:
                try:
                    vticnik.close()
                except Exception:
                    pass
            if self._id:
                # Hub ob zaprti vtičnici konča sam; izrecen stop pove cilju takoj.
                try:
                    link_tls.zahteva(_osnova(self.ws_naslov) + "/cast/share/screen/stop", {"id": self._id},
                                     zeton=self.zeton, timeout=5.0, pripeti=self.odtis)
                except Exception:
                    pass
                self._id = ""
            self._javi()
