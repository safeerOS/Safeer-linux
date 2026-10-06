"""Dostop drugih naprav v Safeer Linku do vsebin TEGA racunalnika (ista pravila kot cast/DostopPravila.kt na Androidu).

Seznanitev v Safeer Link ni dovoljenje za vsebine. Safeer Link je sirsi krog (»EU«): vsaka naprava v njem pomaga pri
povezavi (sredisce, posredovanje, pot prek mobilnega omrezja) in sprejme, kar ji kdo izrecno poslje. Dostop do vsebin
je ozji krog (»Schengen«): na VSAKI napravi posebej in za VSAKO drugo napravo posebej uporabnik odloci, kaj ji odpre -
datoteke, programe, predvajalnik, zaslon in upravljanje. Brez tega racunalnik zahtevo zavrne sam.

Prej je bila vsaka seznanjena naprava enakovredna in stikala (mape, programi, zaslon, predvajanje) so veljala za ves
Link: telefon druge osebe, dodan v Link, je takoj dobil vse, kar racunalnik deli (izmerjeno 6. 10. 2026).

Zapis (dostop.json v mapi nastavitev, 0600; berejo ga Control, brskalnik in sredisce na tem racunalniku):
  {"v": 1, "podedovano_ob": 1791300000.0, "naprave": {"n-<16 hex>": "dpvz"}}
Crke: d = datoteke, p = programi, v = predvajalnik, z = zaslon in upravljanje. Naprava brez zapisa nima dostopa.
Ob prvem zagonu z dovoljenji se enkrat vpisejo naprave, ki so bile z racunalnikom v krogu ze prej (`podedovani`);
pozneje se nic vec ne podeduje - nov vnos v krogu s starim datumom dostopa ne dobi.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable, Dict, Iterable, List, Optional, Set

#: 6. 10. 2026 00:00:00 UTC. Naprave, ki so bile s to napravo v krogu ze prej, ob uvedbi dovoljenj obdrzijo dostop.
MEJA_PODEDOVANJA = 1_791_244_800.0

DATOTEKE, PROGRAMI, PREDVAJALNIK, ZASLON = "d", "p", "v", "z"
VSE_ZMOZNOSTI = frozenset((DATOTEKE, PROGRAMI, PREDVAJALNIK, ZASLON))
#: Kaj zahteva dejanje: "" = prosto (vsaka naprava v Linku), crka zmoznosti ali "*" = vse (samo ozji krog).
PROSTO, VSE = "", "*"

_DEJANJA = {
    DATOTEKE: {"files.list", "files.search", "files.open", "storage.put", "storage.status"},
    PROGRAMI: {"apps.list", "apps.launch", "apps.close", "apps.running", "apps", "launch_app", "open_in_app"},
    PREDVAJALNIK: {
        # Kaj naprava predvaja, nadaljevanje in ustavitev; seznami in viri Medijskega centra.
        "play.state", "play.stop", "lists.get",
        # Odpiranje vsebine na tej napravi brez vprasanja in zvok druge naprave na njenih zvocnikih.
        "open_url", "magnet.open", "audio.play", "audio.stop",
        # Pomoc pri predvajanju vidi, kaj druga naprava gleda, in trosi to napravo (prenos, pretvorba, dodatki).
        "magnet.stream", "magnet.list", "magnet.remove", "magnet.keep",
        "video.transcode", "video.status", "video.stream", "video.stream_stop", "video.stream_status",
        "avail.get", "host.info",
    },
    ZASLON: {"screen.start", "screen.stop", "screen.status", "key", "scroll", "screenshot",
             "volume", "restart", "clear_cache", "status"},
}


def zahteva_dejanja(dejanje: str) -> str:
    """Kaj zahteva ukaz `control.command`. Ponudba »Poslji na napravo« (`play.offer`) je prosta: nic se ne zacne,
    dokler uporabnik tu ne sprejme. Neznano dejanje zahteva vse - novo dejanje ni odprto po pomoti."""
    d = (dejanje or "").strip().lower()
    if d == "play.offer":
        return PROSTO
    for zmoznost, dejanja in _DEJANJA.items():
        if d in dejanja:
            return zmoznost
    if d.startswith("input.") or d.startswith("gamepad."):
        return ZASLON
    return VSE


def zahteva_sporocila(tip: str, dejanje: str = "") -> str:
    """Kaj zahteva sporocilo, ki ni ukaz. Besedilo, datoteka in klepet so izrecno poslani (prosto). Stran ali
    predvajanje, ki se odpre samo, zahteva predvajalnik; usklajevanje (zaznamki, stanje) samo ozji krog; zaslon druge
    naprave, ki se tu odpre sam, zahteva zaslon. Konec deljenja je vedno dovoljen."""
    if tip in ("cast.url", "cast.control", "cast.media", "handoff.request"):
        return PREDVAJALNIK
    if tip == "sync.data":
        return VSE
    if tip == "share.screen":
        return PROSTO if dejanje == "stop" else ZASLON
    return PROSTO


def sme_z(dano: Iterable[str], zahteva: str) -> bool:
    dano = set(dano)
    if zahteva == PROSTO:
        return True
    if zahteva == VSE:
        return VSE_ZMOZNOSTI <= dano
    return zahteva in dano


def iz_niza(s: Optional[str]) -> Set[str]:
    return {c for c in (s or "") if c in VSE_ZMOZNOSTI}


def v_niz(dano: Iterable[str]) -> str:
    dano = set(dano)
    return "".join(c for c in (DATOTEKE, PROGRAMI, PREDVAJALNIK, ZASLON) if c in dano)


DOLZINA_JEDRA = 18


def je_id_iz_kljuca(device_id: str) -> bool:
    if len(device_id) < DOLZINA_JEDRA or not device_id.startswith("n-"):
        return False
    if any(z not in "0123456789abcdef" for z in device_id[2:DOLZINA_JEDRA]):
        return False
    return len(device_id) == DOLZINA_JEDRA or device_id[DOLZINA_JEDRA] == "-"


def jedro_iz(device_id: str, kljuc_clana: Callable[[str], Optional[str]], id_iz_kljuca: Callable[[str], str]) -> str:
    """Stalna oznaka naprave ne glede na id, pod katerim se javi: id iz kljuca (`n-<16 hex>`) brez pripone sorodnika
    (`-os`, `-control` ...). Star id se prevede prek kljuca v krogu; naprava, ki je krog ne pozna, ostane pri svojem
    id-ju (zanjo ni zapisa, torej nima dostopa)."""
    device_id = str(device_id or "")
    if je_id_iz_kljuca(device_id):
        return device_id[:DOLZINA_JEDRA]
    try:
        kljuc = kljuc_clana(device_id)
        return id_iz_kljuca(kljuc) if kljuc else device_id
    except Exception:  # noqa: BLE001 - pokvarjen kljuc ne sme odpreti nicesar
        return device_id


def podedovani(clani: Iterable[dict], lastni_kljuc: Optional[str], id_iz_kljuca: Callable[[str], str],
               meja: float = MEJA_PODEDOVANJA) -> Set[str]:
    """Naprave (jedra), ki ob uvedbi dovoljenj obdrzijo dostop: tiste, ki so v krogu ze od prej kot `meja` - a le, ce
    je bila v krogu ze prej tudi TA naprava. Naprava, dodana po meji (telefon druge osebe, nova namestitev), ne podeduje
    nikogar. Steje najstarejsi veljavni vnos istega kljuca (naprava ima lahko vec id-jev)."""
    if not lastni_kljuc:
        return set()
    najstarejsi: Dict[str, float] = {}
    for c in clani:
        kljuc = str(c.get("kljuc") or "")
        if not kljuc:
            continue
        try:
            dodano = float(c.get("dodano") or 0.0)
        except (TypeError, ValueError):
            continue
        if kljuc not in najstarejsi or dodano < najstarejsi[kljuc]:
            najstarejsi[kljuc] = dodano
    nas = najstarejsi.get(lastni_kljuc)
    if nas is None or nas >= meja:
        return set()
    izid: Set[str] = set()
    for kljuc, dodano in najstarejsi.items():
        if kljuc == lastni_kljuc or dodano >= meja:
            continue
        try:
            izid.add(id_iz_kljuca(kljuc))
        except Exception:  # noqa: BLE001
            pass
    return izid


def zavrnitev(dejanje: str) -> dict:
    """Odgovor napravi, ki ji uporabnik zmoznosti ni odprl. Pri seznamih ima obliko »naprava tega ne deli«, kot jo
    naprave ze poznajo (prazen seznam, shared/enabled = false) - starejsa razlicica na drugi strani ne pokaze napake,
    ampak napravo brez deljenja. Vse drugo dobi kratko zavrnitev s kodo."""
    d = (dejanje or "").strip().lower()
    if d in ("files.list", "files.search"):
        return {"ok": True, "message": "Naprava datotek ne deli",
                "data": {"folder": "", "items": [], "shared": False, "reason": "access"}}
    if d == "apps.list":
        return {"ok": True, "message": "Računalnik programov ne deli", "data": {"items": [], "enabled": False, "reason": "access"}}
    if d == "apps.running":
        return {"ok": True, "message": "Odprti programi", "data": {"running": [], "reason": "access"}}
    if d == "play.state":
        return {"ok": True, "message": "Predvajanje", "data": {"shared": False, "reason": "access"}}
    return {"ok": False, "message": "Ta naprava ti tega ne dovoli. Dostop odpre njen uporabnik v Safeer Linku.",
            "code": "ni_dovoljeno"}


# ---------------------------------------------------------------------- zapis na tem racunalniku

_zaklep = threading.RLock()
_zapis: Optional[Dict[str, Set[str]]] = None
_prebrano_mtime = -1.0
_prebrana_pot = ""
_pot_preglasena: Optional[str] = None


def _pot() -> str:
    if _pot_preglasena:
        return _pot_preglasena
    from core import link_hub
    return os.path.join(link_hub.NASTAVITVE_MAPA, "dostop.json")


def _krog():
    from core import link_krog
    return link_krog.krog()


def _lastni_kljuc() -> Optional[str]:
    from core import link_krog
    try:
        return link_krog.javni_kljuc_b64()
    except Exception:  # noqa: BLE001
        return None


def _id_iz_kljuca(kljuc: str) -> str:
    from core import link_krog
    return link_krog.id_iz_kljuca(kljuc)


def _shrani(zapis: Dict[str, Set[str]], podedovano_ob: Optional[float] = None) -> None:
    pot = _pot()
    stari_ob = podedovano_ob
    if stari_ob is None:
        try:
            with open(pot, "r", encoding="utf-8") as d:
                stari_ob = float((json.load(d) or {}).get("podedovano_ob") or 0.0)
        except Exception:  # noqa: BLE001
            stari_ob = time.time()
    os.makedirs(os.path.dirname(pot), exist_ok=True)
    zacasna = pot + ".tmp"
    with open(zacasna, "w", encoding="utf-8") as d:
        json.dump({"v": 1, "podedovano_ob": stari_ob, "naprave": {k: v_niz(v) for k, v in sorted(zapis.items())}}, d, indent=1)
    os.chmod(zacasna, 0o600)
    os.replace(zacasna, pot)


def _nalozen() -> Dict[str, Set[str]]:
    """Zapis dovoljenj; znova prebran, ce ga je spremenil drug program na tem racunalniku (Control, brskalnik)."""
    global _zapis, _prebrano_mtime, _prebrana_pot
    with _zaklep:
        pot = _pot()
        try:
            mtime = os.stat(pot).st_mtime
        except OSError:
            mtime = -1.0
        if _zapis is not None and mtime == _prebrano_mtime and pot == _prebrana_pot:
            return _zapis
        _prebrana_pot = pot
        if mtime < 0:
            # Prvi zagon z dovoljenji: dosedanje naprave obdrzijo, kar so imele (vse); pozneje dodane zacnejo brez dostopa.
            try:
                k = _krog()
                with k._zaklep:
                    clani = [dict(c) for c in k.clani.values() if k._veljaven(c)]
                stari = podedovani(clani, _lastni_kljuc(), _id_iz_kljuca)
            except Exception:  # noqa: BLE001 - brez kroga ni podedovanih
                stari = set()
            zapis = {j: set(VSE_ZMOZNOSTI) for j in stari}
            try:
                _shrani(zapis, time.time())
                mtime = os.stat(pot).st_mtime
            except OSError:
                pass
            _zapis, _prebrano_mtime = zapis, mtime
            return zapis
        zapis = {}
        try:
            with open(pot, "r", encoding="utf-8") as d:
                surovo = json.load(d) or {}
            for kljuc, crke in (surovo.get("naprave") or {}).items():
                zapis[str(kljuc)] = iz_niza(str(crke))
        except Exception:  # noqa: BLE001 - pokvarjen zapis: nihce nima dostopa (varna stran), uporabnik ga odpre znova
            zapis = {}
        _zapis, _prebrano_mtime = zapis, mtime
        return zapis


def jedro(device_id: str) -> str:
    def kljuc(i: str) -> Optional[str]:
        try:
            c = _krog().clan_za_id(i)
            return str(c.get("kljuc") or "") if c else None
        except Exception:  # noqa: BLE001
            return None
    return jedro_iz(device_id, kljuc, _id_iz_kljuca)


def je_ta_naprava(device_id: str) -> bool:
    """Ali je id ta racunalnik sam (isti kljuc: Control, brskalnik, Safeer OS in pomozne identitete)."""
    if not device_id:
        return False
    nas = _lastni_kljuc()
    if not nas:
        return False
    try:
        return jedro(device_id) == _id_iz_kljuca(nas)
    except Exception:  # noqa: BLE001
        return False


def zmoznosti(device_id: str) -> Set[str]:
    """Kaj je napravi na tem racunalniku odprto."""
    if not device_id:
        return set()
    if je_ta_naprava(device_id):
        return set(VSE_ZMOZNOSTI)
    return set(_nalozen().get(jedro(device_id)) or ())


def sme(device_id: str, zahteva: str) -> bool:
    return zahteva == PROSTO or sme_z(zmoznosti(device_id), zahteva)


def sme_dejanje(device_id: str, dejanje: str) -> bool:
    return sme(device_id, zahteva_dejanja(dejanje))


def sme_sporocilo(device_id: str, tip: str, dejanje: str = "") -> bool:
    return sme(device_id, zahteva_sporocila(tip, dejanje))


def nastavi(device_id: str, dano: Iterable[str]) -> bool:
    """Uporabnik je napravi dolocil dostop; prazen nabor = brez dostopa (naprava samo pomaga pri povezavi)."""
    if not device_id or je_ta_naprava(device_id):
        return False
    global _zapis, _prebrano_mtime, _prebrana_pot
    with _zaklep:
        zapis = dict(_nalozen())
        zapis[jedro(device_id)] = iz_niza(v_niz(dano))
        _shrani(zapis)
        _zapis = zapis
        try:
            _prebrano_mtime = os.stat(_pot()).st_mtime
        except OSError:
            _prebrano_mtime = -1.0
    return True


def naprave_z(zahteva: str) -> Set[str]:
    """Jedra naprav, ki jim je tu odprto `zahteva` (crka zmoznosti ali VSE = ozji krog)."""
    return {j for j, dano in _nalozen().items() if sme_z(dano, zahteva)}


def vsi() -> Dict[str, str]:
    """Ves zapis (jedro -> crke) za vmesnik."""
    return {j: v_niz(d) for j, d in _nalozen().items()}


def lastno_jedro() -> str:
    """Jedro tega racunalnika (prazno, dokler nima kljuca)."""
    nas = _lastni_kljuc()
    if not nas:
        return ""
    try:
        return _id_iz_kljuca(nas)
    except Exception:  # noqa: BLE001
        return ""


def prejemniki(navedeni, posiljatelj: str, zahteva: str = VSE) -> Set[str]:
    """Komu sme sredisce na tem racunalniku posredovati sporocilo brez cilja (stanje predvajanja, usklajevanje).

    Izvor jih navede sam (polje `allow`: jedra naprav, ki jim je pri NJEM odprto). Izvor brez polja (starejsa
    razlicica) ne more povedati, komu zaupa: ce je sam v ozjem krogu TEGA racunalnika, gre sporocilo ozjemu krogu tega
    racunalnika (naprave istega uporabnika delajo naprej, dokler niso posodobljene); sicer nikomur. Posiljatelj sam je
    vedno zraven (njegovi drugi programi na isti napravi)."""
    if isinstance(navedeni, list):
        izid = {str(x) for x in navedeni if isinstance(x, str)}
    elif sme(posiljatelj, zahteva):
        izid = naprave_z(zahteva)
        nas = lastno_jedro()
        if nas:
            izid.add(nas)
    else:
        izid = set()
    izid.add(jedro(posiljatelj))
    return izid


_zabelezeno: Dict[str, List[float]] = {}


def zabelezi(posiljatelj: str, kaj: str, zdaj: Optional[float] = None) -> None:
    """Zavrnitev v dnevnik - najvec ena vrstica na minuto za isto napravo in isto stvar (stara razlicica na drugi
    strani sprasuje vsakih nekaj sekund), s stevilom vmesnih ponovitev."""
    zdaj = time.monotonic() if zdaj is None else zdaj
    kljuc = f"{posiljatelj}|{kaj}"
    with _zaklep:
        vnos = _zabelezeno.get(kljuc)
        if vnos is not None and zdaj - vnos[0] < 60.0:
            vnos[1] += 1
            return
        ponovitev = int(vnos[1]) if vnos is not None else 0
        _zabelezeno[kljuc] = [zdaj, 0]
        if len(_zabelezeno) > 256:
            for k in sorted(_zabelezeno, key=lambda x: _zabelezeno[x][0])[:64]:
                _zabelezeno.pop(k, None)
    dodatek = f" (+{ponovitev} enakih)" if ponovitev else ""
    print(f"[SafeerDostop] Zavrnjeno: {posiljatelj or 'neznana naprava'} nima dostopa za {kaj}{dodatek}")


def _za_preizkus(pot: Optional[str]) -> None:
    """Preizkusi: zapis v zacasni datoteki (None vrne pravo pot)."""
    global _pot_preglasena, _zapis, _prebrano_mtime
    with _zaklep:
        _pot_preglasena, _zapis, _prebrano_mtime = pot, None, -1.0
