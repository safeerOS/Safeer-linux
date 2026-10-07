"""Dostop drugih naprav v Safeer Linku do vsebin TEGA racunalnika (ista pravila kot cast/DostopPravila.kt na Androidu).

Seznanitev v Safeer Link ni dovoljenje za vsebine. Safeer Link je sirsi krog (»EU«): vsaka naprava v njem pomaga pri
povezavi (sredisce, posredovanje, pot prek mobilnega omrezja) in sprejme, kar ji kdo izrecno poslje. Dostop do vsebin
je ozji krog (»Schengen«): na VSAKI napravi posebej in za VSAKO drugo napravo posebej uporabnik odloci, kaj ji odpre -
datoteke, programe, predvajalnik, zaslon in upravljanje. Brez tega racunalnik zahtevo zavrne sam.

Prej je bila vsaka seznanjena naprava enakovredna in stikala (mape, programi, zaslon, predvajanje) so veljala za ves
Link: telefon druge osebe, dodan v Link, je takoj dobil vse, kar racunalnik deli (izmerjeno 6. 10. 2026).

Zapis (dostop.json v mapi nastavitev, 0600; berejo ga Control, brskalnik in sredisce na tem racunalniku):
  {"v": 1, "podedovano_ob": 1791300000.0, "naprave": {"n-<16 hex>": "dpvz"}, "zascita": ["n-<16 hex>"]}
»zascita«: naprave, ki so s tem racunalnikom ze vzpostavile zascito od naprave do naprave (core/link_e2e). Od take
naprave nezascitenega ukaza ne sprejmemo vec - sicer bi se kdorkoli z njeno oznako predstavil kot starejsa razlicica.
Crke: d = datoteke, p = programi, v = predvajalnik, z = zaslon in upravljanje. Naprava brez zapisa nima dostopa.
Ob prvem zagonu z dovoljenji se enkrat vpisejo naprave, ki so bile z racunalnikom v krogu ze prej (`podedovani`);
pozneje se nic vec ne podeduje - nov vnos v krogu s starim datumom dostopa ne dobi.

Zapis pise VEC programov tega racunalnika hkrati (ko naprava dokaze kljuc, to zabelezi vsak program, ki jo vidi). Zato je
vsako pisanje en korak pod zaklepom datoteke: stanje z diska -> sprememba -> zapis v svojo zacasno datoteko -> zamenjava
(glej _spremeni). Prej je vsak program pisal stanje iz svojega pomnilnika v skupno `dostop.json.tmp`: izmerjeno
7. 10. 2026 sta dva programa pri socasnem pisanju padla (FileNotFoundError) in spremembe so se izgubljale.

Varna stran ob napakah (peti neodvisni pregled, 7. 10. 2026):
- Zapisa NI (prvi zagon): dosedanje naprave podedujejo. Zapis JE, a ga ni mogoce pregledati ali prebrati (pravice,
  napaka diska): dostopa nima nihce, nicesar ne pisemo (NapakaBranja) - »ne vem« ni »ni«. Prej je program ob taki
  napaki veljaven zapis zamenjal s praznim ali pa v pomnilniku znova podedoval.
- Starejsi program na istem racunalniku polja »zascita« ne pozna in ga ob svojem pisanju izpusti: ta program ga ob
  naslednji potrditvi seje vrne na disk (zabelezi_zascito).
- Na zaklep datoteke cakamo najvec ZAKLEP_CAKA_S: zamrznjen program, ki ga drzi, ne sme ustaviti tega.
- Tik pred zamenjavo datoteke preverimo, da je zapis se tak, kot smo ga prebrali; ce ga je vmes spremenil drug program
  (pisal je brez zaklepa ali pa smo brez zaklepa mi), preberemo znova in spremembo ponovimo. Brez tega je program, ki je
  zaklep predolgo drzal, povozil spremembo drugega - tudi odvzem dostopa (sesti pregled, 7. 10. 2026).
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
import threading
import time
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

#: 6. 10. 2026 00:00:00 UTC. Naprave, ki so bile s to napravo v krogu ze prej, ob uvedbi dovoljenj obdrzijo dostop.
MEJA_PODEDOVANJA = 1_791_244_800.0
#: Najdlje toliko cakamo na zaklep zapisa, ki ga drzi drug program; potem pisemo brez zaklepa (zamenjava je en korak).
ZAKLEP_CAKA_S = 2.0
#: Po zapisu, ki ni uspel, popravila zapisa »zascita« toliko casa ne poskusamo znova (glej zabelezi_zascito).
POPRAVILO_PO_NEUSPEHU_S = 60.0
#: Kolikokrat preberemo znova, ce se zapis med pripravo nasega spremeni; zadnjic pisemo brez preverbe (da se konca).
NAJVEC_POSKUSOV_ZAPISA = 4


class NapakaBranja(OSError):
    """Zapis dovoljenj obstaja, a ga trenutno ni mogoce pregledati ali prebrati. Ne beremo, ne pisemo, nihce nima dostopa."""

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


_PRIPONA_OZNAKE = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
NAJVEC_OZNAKE = 128


def je_id_iz_kljuca(device_id: str) -> bool:
    """Oznaka iz kljuca: `n-<16 hex>`, po zelji s pripono programa iz crk, stevk, pike, podcrtaja in vezaja (isto
    pravilo kot link_krog.je_id_iz_kljuca). Oznaka z drugimi znaki ni oznaka iz kljuca."""
    if not isinstance(device_id, str) or not (DOLZINA_JEDRA <= len(device_id) <= NAJVEC_OZNAKE):
        return False
    if not device_id.startswith("n-") or any(z not in "0123456789abcdef" for z in device_id[2:DOLZINA_JEDRA]):
        return False
    if len(device_id) == DOLZINA_JEDRA:
        return True
    return device_id[DOLZINA_JEDRA] == "-" and all(z in _PRIPONA_OZNAKE for z in device_id[DOLZINA_JEDRA + 1:])


def jedro_iz(device_id: str, kljuc_clana: Callable[[str], Optional[str]], id_iz_kljuca: Callable[[str], str]) -> str:
    """Stalna oznaka naprave ne glede na id, pod katerim se javi. Odloca KLJUC, pod katerim je naprava v krogu:

    - id iz kljuca (`n-<16 hex>`, po zelji s pripono sorodnika `-os`, `-control` ...) da svoje jedro - RAZEN ce je pod
      tem id-jem v krogu vpisan drug kljuc. Tak vnos je videti kot druga naprava, a to ni (izmerjeno 7. 10. 2026: krog ga
      je sprejel in preverba dostopa mu je dala dostop posnemane naprave); dobi prazno jedro, torej nic.
    - star id se prevede prek kljuca v krogu; naprava, ki je krog ne pozna, ostane pri svojem id-ju (zanjo ni zapisa,
      torej nima dostopa)."""
    device_id = str(device_id or "")
    try:
        kljuc = kljuc_clana(device_id)
        jedro_kljuca = id_iz_kljuca(kljuc) if kljuc else ""
    except Exception:  # noqa: BLE001 - pokvarjen kljuc ne sme odpreti nicesar
        return ""
    if je_id_iz_kljuca(device_id):
        if jedro_kljuca and jedro_kljuca != device_id[:DOLZINA_JEDRA]:
            return ""
        return device_id[:DOLZINA_JEDRA]
    return jedro_kljuca or device_id


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
_zascita: Set[str] = set()
#: Po cem prepoznamo, da je zapis na disku spremenil drug program: (cas spremembe v ns, stevilka datoteke, velikost).
#: Samo cas ni dovolj - dva zapisa v istem trenutku imata lahko isti cas; vsak zapis pa je nova datoteka.
_prebran_odtis: Optional[Tuple[int, int, int]] = None
_prebrana_pot = ""
_pot_preglasena: Optional[str] = None
#: Kar je bilo v polju »zascita« na disku, ko smo ga nazadnje prebrali ali zapisali (v pomnilniku je lahko vec).
_zascita_disk: Set[str] = set()
#: Kdaj (time.monotonic) zapis nazadnje ni uspel; None = zadnji je uspel.
_zapis_spodletel_ob: Optional[float] = None


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


def _odtis_zapisa(pot: str) -> Optional[Tuple[int, int, int]]:
    """Odtis zapisa na disku ali None, ce zapisa NI. Vsaka druga napaka (pravice, disk) vrze NapakaBranja."""
    try:
        st = os.stat(pot)
    except FileNotFoundError:
        return None
    except OSError as e:
        raise NapakaBranja(e.errno, "zapisa dovoljenj ni mogoce pregledati") from e
    return (st.st_mtime_ns, st.st_ino, st.st_size)


@contextlib.contextmanager
def _zaklenjen_zapis(pot: str):
    """Zaklep zapisa med PROGRAMI tega racunalnika. Zaklep je svoja datoteka ob zapisu (zapis sam se ob vsakem pisanju
    zamenja z novo datoteko). Kjer zaklepa ni (ni fcntl, datoteke ni mogoce odpreti), ostane zaklep v programu -
    slabse, a zapis mora delovati."""
    rocaj = None
    try:
        try:
            import fcntl
            rocaj = os.open(pot + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
            # Brez cakanja v jedru: program, ki zaklep drzi in stoji (zamrznjen, v razhroscevalniku), bi nas sicer
            # ustavil za vedno - in z nami vse preverbe dostopa. Po ZAKLEP_CAKA_S pisemo brez zaklepa (pred zamenjavo
            # datoteke se vedno preverimo, da je zapis nespremenjen - glej _spremeni).
            rok = time.monotonic() + ZAKLEP_CAKA_S
            while True:
                try:
                    fcntl.flock(rocaj, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= rok:
                        break
                    time.sleep(0.01)
                except OSError:
                    break       # zaklepanje tu ni mogoce (datotecni sistem ga ne podpira): ne cakamo
        except Exception:  # noqa: BLE001
            pass
        yield
    finally:
        if rocaj is not None:
            try:
                os.close(rocaj)         # zaprtje zaklep sprosti
            except OSError:
                pass


def _z_diska(pot: str) -> Tuple[str, Dict[str, Set[str]], Set[str], float]:
    """Zapis na disku: (stanje, naprave, zascita, podedovano_ob). Stanje je "ok", "ni" (datoteke ni), "napaka"
    (datoteka je, a je ni mogoce prebrati - pravice, disk) ali "pokvarjen" (vsebina ni pravilen zapis); razen pri "ok"
    sta naprave in zascita prazna."""
    try:
        with open(pot, "r", encoding="utf-8") as d:
            besedilo = d.read()
    except FileNotFoundError:
        return "ni", {}, set(), 0.0
    except OSError:
        return "napaka", {}, set(), 0.0
    except ValueError:
        return "pokvarjen", {}, set(), 0.0
    try:
        surovo = json.loads(besedilo) or {}
        naprave = {str(k): iz_niza(str(crke)) for k, crke in (surovo.get("naprave") or {}).items()}
        zascita = {str(j) for j in (surovo.get("zascita") or []) if isinstance(j, str) and je_id_iz_kljuca(j)}
        try:
            ob = float(surovo.get("podedovano_ob") or 0.0)
        except (TypeError, ValueError):
            ob = 0.0
        return "ok", naprave, zascita, ob
    except Exception:  # noqa: BLE001
        return "pokvarjen", {}, set(), 0.0


_NE_PREVERJAJ = object()


def _na_disk(pot: str, naprave: Dict[str, Set[str]], zascita: Set[str], podedovano_ob: float,
             pricakovan: object = _NE_PREVERJAJ) -> Optional[Tuple[int, int, int]]:
    """Zapis v SVOJO zacasno datoteko (0600) in zamenjava: nikoli pol zapisa, nikoli datoteka, ki bi jo hkrati pisal
    drug program. Vrne odtis novega zapisa (zamenjava ohrani stevilko datoteke, cas in velikost zacasne datoteke).

    `pricakovan` je odtis zapisa, kot smo ga prebrali (None = zapisa ni bilo): ce je zapis tik pred zamenjavo drugacen,
    ga je vmes spremenil drug program - NE zamenjamo in vrnemo None (klicatelj prebere znova in spremembo ponovi)."""
    rocaj, zacasna = tempfile.mkstemp(prefix=os.path.basename(pot) + ".", suffix=".tmp", dir=os.path.dirname(pot))
    try:
        with os.fdopen(rocaj, "w", encoding="utf-8") as d:
            json.dump({"v": 1, "podedovano_ob": podedovano_ob, "naprave": {k: v_niz(v) for k, v in sorted(naprave.items())},
                       "zascita": sorted(zascita)}, d, indent=1)
            d.flush()
            os.fchmod(d.fileno(), 0o600)
            os.fsync(d.fileno())
            st = os.fstat(d.fileno())
        if pricakovan is not _NE_PREVERJAJ and _odtis_zapisa(pot) != pricakovan:
            os.unlink(zacasna)
            return None
        os.replace(zacasna, pot)
        return (st.st_mtime_ns, st.st_ino, st.st_size)
    except BaseException:
        try:
            os.unlink(zacasna)
        except OSError:
            pass
        raise


def _podedovane_naprave() -> Dict[str, Set[str]]:
    """Prvi zagon z dovoljenji: dosedanje naprave obdrzijo, kar so imele (vse); pozneje dodane zacnejo brez dostopa."""
    try:
        k = _krog()
        with k._zaklep:
            clani = [dict(c) for c in k.clani.values() if k._veljaven(c)]
        stari = podedovani(clani, _lastni_kljuc(), _id_iz_kljuca)
    except Exception:  # noqa: BLE001 - brez kroga ni podedovanih
        stari = set()
    return {j: set(VSE_ZMOZNOSTI) for j in stari}


def _spremeni(sprememba: Callable[[Dict[str, Set[str]], Set[str]], None]) -> Dict[str, Set[str]]:
    """Branje-sprememba-zapis kot en korak, pod zaklepom programa IN datoteke. `sprememba(naprave, zascita)` spremeni
    oba na mestu. Izhodisce je vedno stanje z DISKA - spremembe drugih programov ostanejo. Zapis »zascita« samo raste:
    kar ima ta program v pomnilniku, gre zraven (tudi kadar je zapis na disku pokvarjen ali ga je pisal starejsi
    program, ki zascite ne pozna). Ce zapisa se ni, je to prvi zagon z dovoljenji (podedovane naprave); pokvarjen
    zapis pomeni, da nima dostopa nihce (varna stran). Zapisa, ki ga ni mogoce PREBRATI, ne prepisemo: NapakaBranja.
    Vrne nove naprave in posodobi stanje v pomnilniku."""
    global _zapis, _zascita, _prebran_odtis, _prebrana_pot, _zascita_disk, _zapis_spodletel_ob
    with _zaklep:
        pot = _pot()
        try:
            os.makedirs(os.path.dirname(pot), exist_ok=True)
            with _zaklenjen_zapis(pot):
                for poskus in range(NAJVEC_POSKUSOV_ZAPISA):
                    odtis_prej = _odtis_zapisa(pot)
                    stanje, naprave, zascita, ob = _z_diska(pot)
                    if stanje == "napaka":
                        raise NapakaBranja(5, "zapisa dovoljenj ni mogoce prebrati - ne prepisemo ga")
                    if stanje == "ni":
                        naprave, ob = _podedovane_naprave(), time.time()
                    elif stanje == "pokvarjen":
                        ob = time.time()
                    if pot == _prebrana_pot:
                        zascita |= _zascita
                    sprememba(naprave, zascita)
                    # Zamenjamo samo, ce je zapis se tak, kot smo ga prebrali (zadnji poskus brez preverbe, da se konca).
                    zadnji = poskus == NAJVEC_POSKUSOV_ZAPISA - 1
                    odtis = _na_disk(pot, naprave, zascita, ob, _NE_PREVERJAJ if zadnji else odtis_prej)
                    if odtis is not None:
                        break
        except OSError:
            _zapis_spodletel_ob = time.monotonic()
            raise
        _zapis, _zascita, _prebran_odtis, _prebrana_pot = naprave, zascita, odtis, pot
        _zascita_disk, _zapis_spodletel_ob = set(zascita), None
        return naprave


def _nalozen() -> Dict[str, Set[str]]:
    """Zapis dovoljenj; znova prebran, ce ga je spremenil drug program na tem racunalniku (Control, brskalnik)."""
    global _zapis, _prebran_odtis, _prebrana_pot, _zascita, _zascita_disk
    with _zaklep:
        pot = _pot()
        if pot != _prebrana_pot:
            # Drug zapis (preizkusi): kar smo vedeli za prejsnjega, zanj ne velja.
            _zascita, _zascita_disk, _zapis, _prebran_odtis, _prebrana_pot = set(), set(), None, None, pot
        try:
            odtis = _odtis_zapisa(pot)
        except OSError:
            # Zapis je, a ga ni mogoce niti pregledati: dostopa nima nihce, nicesar ne pisemo in si ne zapomnimo
            # (naslednji klic poskusi znova). To NI prvi zagon - podedovanega dostopa ni.
            _zapis, _prebran_odtis = None, None
            return {}
        if _zapis is not None and odtis == _prebran_odtis:
            return _zapis
        if odtis is None:
            # Zapisa (se) ni: prvi zagon z dovoljenji. Pod zaklepom datoteke - ce ga je medtem ustvaril drug program,
            # se samo prebere.
            try:
                return _spremeni(lambda naprave, zascita: None)
            except NapakaBranja:
                _zapis, _prebran_odtis = None, None     # zapis se je pojavil, a ni berljiv: nihce (glej zgoraj)
                return {}
            except OSError:
                zapis = _podedovane_naprave()      # zapisa res ni in ustvariti se ga ne da: velja vsaj v tem programu
                _zapis, _prebran_odtis = zapis, None
                _zascita_disk = set()              # na disku ni nicesar: zapis »zascita« se vrne ob prvi priloznosti
                return zapis
        stanje, naprave, zascita, _ob = _z_diska(pot)
        if stanje == "napaka":
            _zapis, _prebran_odtis = None, None         # ni berljiv: nihce, brez pisanja, naslednjic znova
            return {}
        if stanje == "ok":
            _zascita = _zascita | zascita
            _zascita_disk = set(zascita)
        else:
            # Pokvarjen zapis: nihce nima dostopa (varna stran), uporabnik ga odpre znova. Kar ta program ze ve o
            # napravah z dokazanim kljucem, OSTANE: pokvarjen zapis ne sme ugasniti pravila »samo zasciteno«.
            naprave = {}
            _zascita_disk = set()
        _zapis, _prebran_odtis = naprave, odtis
        return naprave


def jedro(device_id: str) -> str:
    def kljuc(i: str) -> Optional[str]:
        try:
            c = _krog().clan_za_id(i)
            return str(c.get("kljuc") or "") if c else None
        except Exception:  # noqa: BLE001
            return None
    return jedro_iz(device_id, kljuc, _id_iz_kljuca)


#: Predpona kljuca shrambe za oznako brez jedra (glej kljuc_shrambe).
BREZ_JEDRA = "brez-jedra:"


def kljuc_shrambe(device_id: str) -> str:
    """Kljuc, pod katerim shrambe (izrecno poslane datoteke, seznami prejemnikov oddaj) vodijo napravo: njeno jedro.
    Oznaka, pod katero je v krogu DRUG kljuc, jedra nima. Dobi kljuc, ki ne more biti enak jedru ali oznaki nobene
    druge naprave - tudi kadar je taka oznaka kar golo jedro prave naprave (`n-<16 hex>`): kar je shranjeno za pravo
    napravo, zanjo ne velja."""
    j = jedro(device_id)
    return j if j else BREZ_JEDRA + str(device_id or "")


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
    """Ali je napravi z to oznako odprto `zahteva` (za zeton streznika datotek, seznam naprav in oddaje sredisca -
    povsod, kjer ne presojamo posameznega sporocila)."""
    return zahteva == PROSTO or sme_z(zmoznosti(device_id), zahteva)


def zmoznosti_jedra(jedro_naprave: str) -> Set[str]:
    """Kaj je odprto napravi s tem jedrom (jedro pride iz PREVERJENEGA kljuca - core/link_e2e)."""
    if not jedro_naprave:
        return set()
    if jedro_naprave == lastno_jedro():
        return set(VSE_ZMOZNOSTI)
    return set(_nalozen().get(jedro_naprave) or ())


def zna_zascito(jedro_naprave: str) -> bool:
    """Ali je naprava s tem jedrom ze kdaj vzpostavila zascito s tem racunalnikom (ali pa je to ta racunalnik sam -
    njegovi programi jo znajo vedno, kadar je kriptografija na voljo)."""
    if not jedro_naprave:
        return False
    _nalozen()
    if jedro_naprave in _zascita:
        return True
    if jedro_naprave == lastno_jedro():
        try:
            from core import link_e2e
            return link_e2e.na_voljo()
        except Exception:  # noqa: BLE001
            return False
    return False


def zahteva_zascito(device_id: str) -> bool:
    """Ali od naprave s to oznako sprejmemo samo zascitena sporocila (ker vemo, da jih zna poslati) - in ji zascitene
    tipe tudi posiljamo samo zasciteno.

    Pri oznaki iz kljuca odloca jedro iz OBLIKE oznake, ne vnos v krogu: vnos s to oznako in DRUGIM kljucem (podtakne
    ga lahko clan ali sredisce, novejsi vnos krog sprejme) da prazno jedro in je prej zahtevo ugasnil - odgovori taki
    napravi so potem sli nezasciteni (drugi neodvisni pregled, 7. 10. 2026)."""
    device_id = str(device_id or "")
    if je_id_iz_kljuca(device_id) and zna_zascito(device_id[:DOLZINA_JEDRA]):
        return True
    return zna_zascito(jedro(device_id))


def zabelezi_zascito(jedro_naprave: str) -> None:
    """Z napravo je vzpostavljena preverjena seja: odslej od nje (in v njenem imenu) ne sprejmemo nezascitenega."""
    if not je_id_iz_kljuca(jedro_naprave) or len(jedro_naprave) != DOLZINA_JEDRA:
        return
    with _zaklep:
        _nalozen()
        if jedro_naprave == lastno_jedro():
            return
        nova = jedro_naprave not in _zascita
        if not nova:
            # V tem programu ze velja. Na disku je lahko ni vec: starejsi program na istem racunalniku polja »zascita«
            # ne pozna in ga ob svojem pisanju izpusti - po ponovnem zagonu bi ta program od naprave spet sprejel
            # nezascitene ukaze. Zato ga vrnemo (klic pride ob vsakem seznamu naprav); po neuspelem zapisu ne takoj znova.
            if jedro_naprave in _zascita_disk:
                return
            if _zapis_spodletel_ob is not None and time.monotonic() - _zapis_spodletel_ob < POPRAVILO_PO_NEUSPEHU_S:
                return
        _zascita.add(jedro_naprave)         # v tem programu velja takoj, tudi ce zapis ne uspe
        try:
            _spremeni(lambda naprave, zascita: zascita.add(jedro_naprave))
        except OSError:
            pass
        if nova:
            print("[SafeerLink] naprava %s…%s je dokazala kljuc: odslej od nje samo zasciteni ukazi"
                  % (jedro_naprave[:2], jedro_naprave[-4:]), flush=True)


def _sme_posiljatelj(device_id: str, zahteva: str, zascita: Optional[str], zascitljivo: bool) -> bool:
    if zahteva == PROSTO:
        return True
    if zascita:
        return sme_z(zmoznosti_jedra(str(zascita)), zahteva)
    if zascitljivo and zahteva_zascito(device_id):
        return False
    return sme_z(zmoznosti(device_id), zahteva)


def sme_dejanje(device_id: str, dejanje: str, zascita: Optional[str] = None) -> bool:
    """Ali sme posiljatelj izvesti ukaz. `zascita` je jedro iz preverjenega kljuca, kadar je sporocilo prislo zasciteno;
    brez nje velja oznaka, ki jo je vpisalo sredisce - a samo za napravo, ki zascite (se) ne zna."""
    return _sme_posiljatelj(device_id, zahteva_dejanja(dejanje), zascita, True)


def sme_sporocilo(device_id: str, tip: str, dejanje: str = "", zascita: Optional[str] = None) -> bool:
    """Kot sme_dejanje, za sporocila, ki niso ukaz. Pravilo »od naprave z zascito samo zasciteno« velja za tipe, ki jih
    naprave z zascito res posiljajo zascitene (link_e2e.ZASCITENI_TIPI); usklajevanje in zaslon gresta se po starem."""
    from core import link_e2e
    return _sme_posiljatelj(device_id, zahteva_sporocila(tip, dejanje), zascita, tip in link_e2e.ZASCITENI_TIPI)


def nastavi(device_id: str, dano: Iterable[str]) -> bool:
    """Uporabnik je napravi dolocil dostop; prazen nabor = brez dostopa (naprava samo pomaga pri povezavi)."""
    if not device_id or je_ta_naprava(device_id):
        return False
    j = jedro(device_id)
    if not j:
        return False
    nabor = iz_niza(v_niz(dano))

    def sprememba(naprave: Dict[str, Set[str]], zascita: Set[str]) -> None:
        naprave[j] = nabor
    with _zaklep:
        _nalozen()                      # prvi zagon (podedovane naprave) se zgodi pred prvo spremembo
        try:
            _spremeni(sprememba)
        except OSError:
            return False                # zapisa ni mogoce prebrati ali zapisati: spremembe ni (klicatelj to pove)
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
    izid.add(kljuc_shrambe(posiljatelj))
    izid.discard("")
    izid.discard(BREZ_JEDRA)
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
    global _pot_preglasena, _zapis, _prebran_odtis, _prebrana_pot, _zascita, _zascita_disk, _zapis_spodletel_ob
    with _zaklep:
        _pot_preglasena, _zapis, _prebran_odtis, _prebrana_pot, _zascita = pot, None, None, "", set()
        _zascita_disk, _zapis_spodletel_ob = set(), None
