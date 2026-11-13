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
import socket
import ssl
import threading
import time
import urllib.parse
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
ODJAVNA_OD_DELEZA = 0.75
#: Odjavna in napoved morata segati do konca (skupnostna baza: odsek sredi filma bi prevzel OK/Enter).
ODJAVNA_DO_DELEZA = 0.9
GUMB_VIDEN_S = 15.0
_NAJVEC_ODSEKOV = 2
#: Pregledamo najvec toliko vnosov vrste: neveljavni na zacetku ne skrijejo veljavnega.
_NAJVEC_PREGLEDANIH = 16
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
        veljavnih = 0
        for o in seznam[:_NAJVEC_PREGLEDANIH]:
            if veljavnih >= _NAJVEC_ODSEKOV:
                break
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
            veljavnih += 1
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
    return trajanje > 0 and o.od >= trajanje * ODJAVNA_OD_DELEZA and k >= trajanje * ODJAVNA_DO_DELEZA


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


def ura() -> float:
    """Ura modula: preizkusi zamenjajo to funkcijo, ne time.monotonic (ta je skupen vsem nitim procesa)."""
    return time.monotonic()


_KONTEKST = ssl.create_default_context()     # lasten kontekst: preverba TLS ni odvisna od globalnega privzetega
_seja: dict = {}
_zaklep = threading.Lock()
#: url -> (zacetek, [izid, ...], zeton). Vsi, ki cakajo isti url, dobijo odgovor; zapis starejsi od _MRTEV_S se odvrze
#: (cakajoci dobijo prazen odgovor), staro vlakno pa ne pobere novejsega zapisa (zeton).
_v_teku: dict = {}
_zivih = [0]                                 # zivih vlaken (tudi odvrzenih): DNS nima roka, zato meja
_NAJVEC_HKRATI = 2
_NAJVEC_ZIVIH = 4
_NAJVEC_CAKA = 8
_MRTEV_S = SKUPNI_ROK_S + 2 * ROK_S
_NAJVEC_GLAV = 8 * 1024
_RX_POT = re.compile(r"/v4/media\?[A-Za-z0-9_=&%.-]{1,200}")


def _povezi(naslov, rok_s):
    """TCP povezava (preizkusi jo zamenjajo). DNS nima roka - zato meja zivih vlaken."""
    return socket.create_connection(naslov, timeout=rok_s)


def _ovij(surova):
    """TLS z nasim kontekstom in imenom gostitelja; rokovanje posebej, z rokom (preizkusi jo zamenjajo)."""
    return _KONTEKST.wrap_socket(surova, server_hostname=GOSTITELJ, do_handshake_on_connect=False)


def _odgovor(podatki: bytes) -> Optional[str]:
    """Telo odgovora HTTP/1.0, "" za 404 (ni podatkov - velja za sejo) ali None."""
    glava, locilo, telo = podatki.partition(b"\r\n\r\n")
    if not locilo or len(glava) > _NAJVEC_GLAV:
        return None
    vrstice = glava.decode("latin-1").split("\r\n")
    deli = vrstice[0].split(" ", 2)
    if len(deli) < 2 or not deli[0].startswith("HTTP/1.") or not deli[1].isdigit():
        return None
    status = int(deli[1])
    if status == 404:
        return ""
    if status != 200:
        return None                              # tudi preusmeritev: ne sledimo
    glave = {}
    for v in vrstice[1:]:
        ime, _, vrednost = v.partition(":")
        glave[ime.strip().lower()] = vrednost.strip()
    if glave.get("transfer-encoding") or glave.get("content-encoding", "identity").lower() != "identity":
        return None
    dolzina = glave.get("content-length")
    if dolzina is not None and (not dolzina.isdigit() or int(dolzina) != len(telo)):
        return None                              # odrezan ali podaljsan odgovor
    if len(telo) > NAJVEC_BAJTOV:
        return None
    return telo.decode("utf-8", "replace")


def _beri(url: str) -> Optional[str]:
    """Poizvedba z enim skupnim rokom: povezava, rokovanje TLS, posiljanje in vsako branje dobijo samo preostanek roka
    (kapljanje po bajt ga ne podaljsa). Brez straze iz druge niti: SSLSocket.shutdown iz druge niti bi lahko poslal
    zahtevo nesifrirano. DNS nima roka (meja zivih vlaken v pridobi)."""
    deli = urllib.parse.urlsplit(url)
    if deli.scheme != "https" or deli.hostname != GOSTITELJ or deli.port not in (None, 443):
        return None
    pot = deli.path + ("?" + deli.query if deli.query else "")
    if not _RX_POT.fullmatch(pot):
        return None
    rok = ura() + SKUPNI_ROK_S

    def ostane() -> float:
        r = rok - ura()
        if r <= 0:
            raise TimeoutError("skupni rok")
        return min(r, ROK_S)
    zahteva = ("GET %s HTTP/1.0\r\nHost: %s\r\nAccept: application/json\r\nAccept-Encoding: identity\r\n"
               "User-Agent: Safeer OS (https://safeer.si)\r\nConnection: close\r\n\r\n" % (pot, GOSTITELJ)).encode("ascii")
    try:
        with _povezi((GOSTITELJ, 443), ostane()) as surova:
            with _ovij(surova) as tls:
                tls.settimeout(ostane())
                tls.do_handshake()
                tls.settimeout(ostane())
                tls.sendall(zahteva)
                podatki = bytearray()
                while True:
                    tls.settimeout(ostane())
                    kos = tls.recv(4096)
                    if not kos:
                        break
                    podatki += kos
                    if len(podatki) > NAJVEC_BAJTOV + _NAJVEC_GLAV:
                        return None
        return _odgovor(bytes(podatki))
    except Exception:  # noqa: BLE001 - brez povezave, rok, TLS ali napaka: brez gumba, predvajanje tece naprej
        return None


def _poklici(f, odseki) -> None:
    try:
        f(odseki)
    except Exception:  # noqa: BLE001 - napaka enega klicatelja ne ustavi ostalih
        pass


def _delo(url: str, zeton) -> None:
    besedilo, odseki = None, []
    try:
        besedilo = _beri(url)
        odseki = razcleni(besedilo) if besedilo is not None else []
    except Exception:  # noqa: BLE001 - nobena napaka ne sme pustiti zasedenega mesta
        besedilo, odseki = None, []
    finally:
        with _zaklep:
            _zivih[0] -= 1
            zapis = _v_teku.get(url)
            if zapis is not None and zapis[2] is zeton:
                del _v_teku[url]
            else:
                zapis = None                 # odvrzen (obvisel) ali ga ima novejsa poizvedba
            # Odvrzeno (obviselo) vlakno ne prepise odgovora novejse poizvedbe za isti url (CodeRabbit 13. 11.).
            if besedilo is not None and (zapis is not None or url not in _seja):
                if len(_seja) >= 200:
                    _seja.clear()
                _seja[url] = odseki
    for f in (zapis[1] if zapis else ()):
        _poklici(f, odseki)


def pridobi(url: str, izid: Callable[[list], None]) -> bool:
    """Odseki za `url` v locenem vlaknu; `izid` se klice v tem vlaknu (ali takoj iz predpomnilnika seje) - klicatelj ga
    prenese v glavno nit. False: ni sprejeto (prevec hkratnih) - klicatelj poskusi znova ob naslednjem tiku."""
    zdaj = ura()
    odvrzeni, odseki, zeton = [], None, None
    with _zaklep:
        for u in [u for u, z in _v_teku.items() if zdaj - z[0] > _MRTEV_S]:
            odvrzeni += _v_teku.pop(u)[1]
        if url in _seja:
            sprejeto, odseki = True, _seja[url]
        elif url in _v_teku:
            cakajo = _v_teku[url][1]
            sprejeto = len(cakajo) < _NAJVEC_CAKA
            if sprejeto:
                cakajo.append(izid)
        elif len(_v_teku) >= _NAJVEC_HKRATI or _zivih[0] >= _NAJVEC_ZIVIH:
            sprejeto = False
        else:
            zeton = object()
            _v_teku[url] = (zdaj, [izid], zeton)
            _zivih[0] += 1
            sprejeto = True
    for f in odvrzeni:
        _poklici(f, [])
    if odseki is not None:
        _poklici(izid, odseki)
    if zeton is not None:
        try:
            threading.Thread(target=_delo, args=(url, zeton), name="safeer-theintrodb", daemon=True).start()
        except RuntimeError:                       # »can't start new thread« (pomnilnik): mesto ne sme ostati zasedeno
            with _zaklep:
                _zivih[0] -= 1
                if url in _v_teku and _v_teku[url][2] is zeton:
                    del _v_teku[url]
            return False
    return sprejeto
