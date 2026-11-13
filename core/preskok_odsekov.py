"""Preskok uvoda, povzetka, odjavne spice in napovedi v Medijskem centru (lastnik 13. 11. 2026, ideja iz IPVIO Stream;
kode nismo prevzeli). Ista pravila kot TV (si.safeer.tv.os.PreskokPravila) - skupno Linuxu in Windows.

Casi so iz skupnostne baze TheIntroDB (api.theintrodb.org/v4/media, brez kljuca). Pogoji (20. 9. 2026): samo
nekomercialna uporaba, klic neposredno z uporabnikove naprave, predpomnjenje samo za sejo - zato casi ostanejo v
pomnilniku procesa. Casi so lahko netocni: gumb ponudi preskok, samodejnega ni. Poizvedba tretji osebi pove, kaj
uporabnik gleda (TMDB/IMDb id, sezona, epizoda, naslov IP) - zato je privzeto IZKLOPLJENA (neodvisni pregled 13. 11.).
Odsek, ki ni smiseln (uvod 0..24 h, odjavna od zacetka), se zavrze: baza je skupnostna.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

GOSTITELJ = "api.theintrodb.org"
KLJUC = "preskok_odsekov"
NAJVEC_BAJTOV = 16 * 1024
ROK_S = 4.0
SKUPNI_ROK_S = 8.0
NAJKRAJSI_S = 5.0
PRED_KONCEM_S = 1.5
NAJDALJSI_UVOD_S = 300.0
UVOD_NAJPOZNEJE_S = 1200.0
ODJAVNA_OD_DELEZA = 0.5
GUMB_VIDEN_S = 15.0
_NAJVEC_ODSEKOV = 8
_NAJVEC_CAS_MS = 24 * 3600 * 1000
VRSTE = (("recap", "povzetek"), ("intro", "uvod"), ("credits", "odjavna"), ("preview", "napoved"))
_RX_IMDB = re.compile(r"tt\d{7,10}")


@dataclass(frozen=True)
class Odsek:
    vrsta: str            # uvod, povzetek, odjavna, napoved
    od: float             # sekunde
    do: Optional[float]   # sekunde, None = do konca


def naslov(tmdb_id: int = 0, imdb_id: str = "", sezona: int = 0, epizoda: int = 0) -> Optional[str]:
    """Naslov poizvedbe ali None. Prednost ima IMDb, sicer TMDB (oba API sprejme). Film: sezona in epizoda 0."""
    if not isinstance(sezona, int) or not isinstance(epizoda, int) or isinstance(sezona, bool) or isinstance(epizoda, bool):
        return None
    if not (0 <= sezona <= 999 and 0 <= epizoda <= 9999) or (sezona != 0 and epizoda == 0):
        return None
    imdb = str(imdb_id or "").strip()
    if imdb and _RX_IMDB.fullmatch(imdb):
        q = {"imdb_id": imdb}
    elif isinstance(tmdb_id, int) and not isinstance(tmdb_id, bool) and 0 < tmdb_id < 10**9:
        q = {"tmdb_id": str(tmdb_id)}
    else:
        return None
    if epizoda > 0:
        q.update(season=str(sezona), episode=str(epizoda))
    return "https://%s/v4/media?%s" % (GOSTITELJ, urllib.parse.urlencode(q))


def iz_kljuca(kljuc: str) -> Optional[str]:
    """Kljuc kataloga (tmdb:tv:<id>:<s>:<e>, tmdb:film:<id>) -> naslov poizvedbe."""
    m = re.fullmatch(r"tmdb:tv:(\d{1,9}):(\d{1,3}):(\d{1,4})", str(kljuc or ""))
    if m:
        return naslov(int(m.group(1)), "", int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"tmdb:film:(\d{1,9})", str(kljuc or ""))
    return naslov(int(m.group(1))) if m else None


def _ms(v) -> Optional[float]:
    """Sekunde iz ms; None ostane None; neveljavno -> ValueError."""
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= _NAJVEC_CAS_MS:
        raise ValueError
    return v / 1000.0


def razcleni(besedilo: str) -> list:
    if not isinstance(besedilo, str) or len(besedilo) > NAJVEC_BAJTOV:
        return []
    try:
        d = json.loads(besedilo)
    except (ValueError, RecursionError):   # 16 KB »[[[[« -> RecursionError (ni ValueError), slepi pregled 13. 11.
        return []
    if not isinstance(d, dict):
        return []
    izid = []
    for api, vrsta in VRSTE:
        seznam = d.get(api)
        if not isinstance(seznam, list):
            continue
        for o in seznam[:_NAJVEC_ODSEKOV]:
            if not isinstance(o, dict):
                continue
            try:
                od, do = _ms(o.get("start_ms")), _ms(o.get("end_ms"))
            except ValueError:
                continue
            if od is None:
                if vrsta not in ("uvod", "povzetek"):
                    continue
                od = 0.0
            if vrsta in ("uvod", "povzetek") and do is None:
                continue
            if do is not None and do <= od:
                continue
            izid.append(Odsek(vrsta, od, do))
    return sorted(izid, key=lambda x: x.od)


def _konec(o: Odsek, trajanje: float) -> Optional[float]:
    k = o.do if o.do is not None else (trajanje if trajanje > 0 else None)
    if k is None:
        return None
    return min(k, trajanje) if trajanje > 0 else k


def smiseln(o: Odsek, trajanje: float) -> bool:
    k = _konec(o, trajanje)
    if k is None or k - o.od < NAJKRAJSI_S:
        return False
    if o.vrsta in ("uvod", "povzetek"):
        return k - o.od <= NAJDALJSI_UVOD_S and o.od <= max(UVOD_NAJPOZNEJE_S, trajanje / 3 if trajanje > 0 else 0)
    return trajanje > 0 and o.od >= trajanje * ODJAVNA_OD_DELEZA


def aktiven(odseki: list, polozaj: float, trajanje: float) -> Optional[Odsek]:
    for o in odseki:
        if smiseln(o, trajanje):
            k = _konec(o, trajanje)
            if o.od <= polozaj < k - PRED_KONCEM_S:
                return o
    return None


def cilj(o: Odsek, trajanje: float) -> Optional[float]:
    """Konec odseka; pri »do konca« zadnja sekunda (konec posnetka sprozi ponudbo naslednje epizode)."""
    k = _konec(o, trajanje)
    if k is None:
        return None
    return min(k, max(0.0, trajanje - 1.0)) if trajanje > 0 else k


def gumb_viden(vstop: float, zdaj: float) -> bool:
    return zdaj - vstop < GUMB_VIDEN_S


class _BrezPreusmeritev(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_a, **_k):  # noqa: D401 - preusmeritve ne sledimo (samo nas gostitelj)
        return None


_odpiralnik = urllib.request.build_opener(_BrezPreusmeritev())
_seja: dict = {}
_zaklep = threading.Lock()
#: url -> (zacetek, [izid, ...]); vsi, ki cakajo isti url, dobijo odgovor. Zapis starejsi od _MRTEV_S ne zaseda mesta
#: (vlakno lahko obvisi v DNS, ki nima roka) - tako dve obviseli poizvedbi ne izklopita preskoka do ponovnega zagona.
_v_teku: dict = {}
_NAJVEC_HKRATI = 2
_NAJVEC_CAKA = 8
_MRTEV_S = SKUPNI_ROK_S + 2 * ROK_S


def _beri(url: str) -> Optional[str]:
    deli = urllib.parse.urlsplit(url)
    if deli.scheme != "https" or deli.hostname != GOSTITELJ:
        return None
    zahteva = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Safeer OS (https://safeer.si)"})
    rok = time.monotonic() + SKUPNI_ROK_S
    try:
        with _odpiralnik.open(zahteva, timeout=ROK_S) as o:
            if o.status != 200:
                return None
            dolzina = o.headers.get("Content-Length")
            if dolzina and dolzina.isdigit() and int(dolzina) > NAJVEC_BAJTOV:
                return None
            kosi, skupaj = [], 0
            while True:
                if time.monotonic() > rok:
                    return None
                # read1: vrne po enem recv; read(n) bi cakal na n bajtov in skupni rok ne bi veljal (kapljanje)
                kos = o.read1(min(4096, NAJVEC_BAJTOV + 1 - skupaj))
                if not kos:
                    break
                kosi.append(kos)
                skupaj += len(kos)
                if skupaj > NAJVEC_BAJTOV:
                    return None
            return b"".join(kosi).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - brez povezave ali napaka: brez gumba, predvajanje tece naprej
        return None


def pridobi(url: str, izid: Callable[[list], None]) -> bool:
    """Odseki za `url` v locenem vlaknu; `izid` se klice v tem vlaknu (ali takoj iz predpomnilnika seje) - klicatelj ga
    prenese v glavno nit. False: zahteva ni sprejeta (prevec hkratnih) - klicatelj poskusi znova ob naslednjem tiku."""
    zdaj = time.monotonic()
    with _zaklep:
        for u in [u for u, (z, _c) in _v_teku.items() if zdaj - z > _MRTEV_S]:
            del _v_teku[u]
        if url in _seja:
            odseki = _seja[url]
        elif url in _v_teku:
            cakajo = _v_teku[url][1]
            if len(cakajo) >= _NAJVEC_CAKA:
                return False
            cakajo.append(izid)
            return True
        elif len(_v_teku) >= _NAJVEC_HKRATI:
            return False
        else:
            _v_teku[url] = (zdaj, [izid])
            odseki = None
    if odseki is not None:
        izid(odseki)
        return True

    def delo():
        besedilo, odseki = None, []
        try:
            besedilo = _beri(url)
            odseki = razcleni(besedilo) if besedilo is not None else []
        except Exception:  # noqa: BLE001 - nobena napaka ne sme pustiti zasedenega mesta
            besedilo, odseki = None, []
        finally:
            with _zaklep:
                zapis = _v_teku.pop(url, None)
                if besedilo is not None:
                    if len(_seja) >= 200:
                        _seja.clear()
                    _seja[url] = odseki
        for f in (zapis[1] if zapis else ()):
            try:
                f(odseki)
            except Exception:  # noqa: BLE001 - napaka enega klicatelja ne ustavi ostalih
                pass
    threading.Thread(target=delo, name="safeer-theintrodb", daemon=True).start()
    return True
