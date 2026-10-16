"""Stabilnost Safeer OS in Safeer Controla na racunalniku: sled ob sesutju in varni nacin.

Do 20. 9. 2026 se je ob sesutju (SIGSEGV v knjiznici C) zgodilo natanko nic: okno je izginilo,
uporabnik ni vedel zakaj, mi pa nismo imeli sledi - sesutje je bilo videti samo v sistemskem
dnevniku jedra. Tu je troje, kar to odpravi:

  * `faulthandler` zapise sled Pythona tudi ob SIGSEGV, SIGABRT, SIGBUS in SIGFPE. Sled pove,
    katera vrstica nase kode je tekla, ko je padla knjiznica C pod njo.
  * Neujete izjeme (tudi v nitih) gredo v isti dnevnik, ne le na zaslon, ki ga nihce ne vidi.
  * Stejemo zagone in sesutja: ce se program v kratkem casu sesuje veckrat, naslednjic tece v
    **varnem nacinu** - brez delov, ki so zadnjic padli (npr. seznam oken prek libwnck).

Dnevnik je v ~/.cache/safeer-os/ (oz. safeer-control) in se sam obrezuje.
"""

from __future__ import annotations

import datetime
import faulthandler
import json
import os
import sys
import threading
import time
from typing import Callable, Optional

NAJVECJI_DNEVNIK = 256 * 1024
#: Toliko sesutij v tem casu pomeni, da nekaj ni v redu in je pametneje teci okrnjeno.
OKNO_SESUTIJ_S = 10 * 60
SESUTIJ_ZA_VARNI_NACIN = 2

_datoteka = None


def _mapa(ime: str) -> str:
    koren = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    pot = os.path.join(koren, ime)
    os.makedirs(pot, exist_ok=True)
    return pot


def _obrezi(pot: str) -> None:
    try:
        if os.path.getsize(pot) > NAJVECJI_DNEVNIK:
            with open(pot, "rb") as d:
                d.seek(-NAJVECJI_DNEVNIK // 2, os.SEEK_END)
                rep = d.read()
            with open(pot, "wb") as d:
                d.write(b"... (starejsi zapisi so odrezani)\n" + rep)
    except OSError:
        pass


def zapisi(ime_programa: str, besedilo: str) -> None:
    """Vrstica v dnevnik programa (z uro). Nikoli ne vrze izjeme."""
    try:
        pot = os.path.join(_mapa(ime_programa), "dnevnik.log")
        _obrezi(pot)
        with open(pot, "a", encoding="utf-8") as d:
            d.write("%s %s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), besedilo))
    except Exception:  # noqa: BLE001
        pass


def _stanje_pot(ime_programa: str) -> str:
    return os.path.join(_mapa(ime_programa), "zagoni.json")


def _beri_stanje(ime_programa: str) -> dict:
    try:
        with open(_stanje_pot(ime_programa), encoding="utf-8") as d:
            s = json.load(d)
            return s if isinstance(s, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _pisi_stanje(ime_programa: str, s: dict) -> None:
    try:
        with open(_stanje_pot(ime_programa), "w", encoding="utf-8") as d:
            json.dump(s, d)
    except Exception:  # noqa: BLE001
        pass


def zabelezi_sesutje(ime_programa: str, koda: int, cas: Optional[float] = None) -> int:
    """Zaganjalnik javi, da se je program koncal nenormalno. Vrne stevilo sesutij v zadnjem oknu."""
    import time
    zdaj = cas if cas is not None else time.time()
    s = _beri_stanje(ime_programa)
    sesutja = [t for t in s.get("sesutja", []) if isinstance(t, (int, float)) and zdaj - t < OKNO_SESUTIJ_S]
    sesutja.append(zdaj)
    s["sesutja"] = sesutja[-10:]
    _pisi_stanje(ime_programa, s)
    zapisi(ime_programa, "sesutje (koda %s); v zadnjih %d minutah: %d" % (koda, OKNO_SESUTIJ_S // 60, len(sesutja)))
    return len(sesutja)


def naj_bo_varni_nacin(ime_programa: str, cas: Optional[float] = None) -> bool:
    """Ali naj se program zdaj zazene okrnjeno (zaradi ponovljenih sesutij)."""
    import time
    zdaj = cas if cas is not None else time.time()
    sesutja = [t for t in _beri_stanje(ime_programa).get("sesutja", [])
               if isinstance(t, (int, float)) and zdaj - t < OKNO_SESUTIJ_S]
    return len(sesutja) >= SESUTIJ_ZA_VARNI_NACIN


def pozabi_sesutja(ime_programa: str) -> None:
    """Program je dolgo tekel brez tezav: zgodovina sesutij ni vec pomembna."""
    s = _beri_stanje(ime_programa)
    if s.get("sesutja"):
        s["sesutja"] = []
        _pisi_stanje(ime_programa, s)


def zakleni_primerek(ime: str):
    """Zaklep enega primerka programa (flock v XDG_RUNTIME_DIR). Vrne odprto datoteko - drzi jo do konca programa,
    sprosti se sama, tudi ob sesutju -, None, ce program ze tece ali se pravkar zaganja, in False, ce zaklepa ni
    mogoce preveriti (potem naj program ravna kot brez njega)."""
    try:
        import fcntl
    except ImportError:
        return False
    mapa = os.environ.get("XDG_RUNTIME_DIR") or os.path.join(os.path.expanduser("~"), ".cache", ime)
    try:
        os.makedirs(mapa, exist_ok=True)
        datoteka = open(os.path.join(mapa, ime + ".zaklep"), "a")  # noqa: SIM115 - odprta ostane do konca programa
    except OSError:
        return False
    try:
        fcntl.flock(datoteka, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return datoteka
    except OSError:
        datoteka.close()
        return None


#: Zgornja meja mehke omejitve odprtih datotek, na katero jo dvignemo (trda meja je lahko 1048576).
NAJVEC_DATOTEK = 65536


def dvigni_omejitev_datotek() -> int:
    """Mehko omejitev odprtih datotek (RLIMIT_NOFILE) dvigne do trde (najvec NAJVEC_DATOTEK) in vrne novo mehko mejo.
    Lastnik, 16. 10. 2026, 20:12: Safeer OS (--delovna, 14 h) je ob odpiranju Sporocil koncal s SIGTRAP - WebKit ob
    zagonu novega spletnega procesa pokliče g_error("Failed to create memfd"), ko memfd_create ne dobi deskriptorja
    (EMFILE). Mehka meja je bila 1024; novi proces je imel po 16 minutah ze 204 odprte deskriptorje (132 vticnic).
    GLib in Python (selectors/epoll) select() z mejo 1024 ne uporabljata, zato je visja meja varna."""
    try:
        import resource
        mehka, trda = resource.getrlimit(resource.RLIMIT_NOFILE)
        cilj = NAJVEC_DATOTEK if trda == resource.RLIM_INFINITY else min(trda, NAJVEC_DATOTEK)
        if mehka != resource.RLIM_INFINITY and mehka < cilj:
            resource.setrlimit(resource.RLIMIT_NOFILE, (cilj, trda))
            return cilj
        return mehka
    except (ImportError, ValueError, OSError):
        return -1


#: Kako pogosto se med delom preveri velikost sled.log.
OBREZI_SLED_VSAKIH_S = 600


def _obrezuj_periodicno(pot: str) -> None:
    while True:
        time.sleep(OBREZI_SLED_VSAKIH_S)
        _obrezi(pot)


def vkljuci(ime_programa: str = "safeer-os") -> str:
    """Vklopi zapisovanje sledi in dnevnik neujetih izjem. Vrne pot dnevnika sledi."""
    global _datoteka
    dvigni_omejitev_datotek()
    pot = os.path.join(_mapa(ime_programa), "sled.log")
    try:
        _obrezi(pot)
        _datoteka = open(pot, "a", buffering=1, encoding="utf-8")  # noqa: SIM115 - odprto, dokler tece program
        _datoteka.write("\n=== %s zagon %d (%s) ===\n" % (
            ime_programa, os.getpid(), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        faulthandler.enable(file=_datoteka, all_threads=True)
        # Zaganjalnik sem preusmeri stderr Pythona in WebKita (packaging/safeer-os-launcher): med dolgim delom omejimo
        # velikost tudi tu, ne le ob zagonu.
        threading.Thread(target=_obrezuj_periodicno, args=(pot,), name="safeer-sled-obrezi", daemon=True).start()
    except Exception as e:  # noqa: BLE001
        print("[stabilnost] sledi ni mogoce zapisovati:", e)

    def ob_izjemi(vrsta, vrednost, sled):
        import traceback
        besedilo = "".join(traceback.format_exception(vrsta, vrednost, sled))
        zapisi(ime_programa, "neujeta izjema:\n" + besedilo)
        sys.__excepthook__(vrsta, vrednost, sled)

    def ob_izjemi_niti(podatki):
        import traceback
        besedilo = "".join(traceback.format_exception(podatki.exc_type, podatki.exc_value, podatki.exc_traceback))
        zapisi(ime_programa, "neujeta izjema v niti %s:\n%s" % (getattr(podatki.thread, "name", "?"), besedilo))

    sys.excepthook = ob_izjemi
    try:
        threading.excepthook = ob_izjemi_niti
    except Exception:  # noqa: BLE001
        pass
    return pot


# ---------------------------------------------------------------------------- padec spletnega procesa
#: Najvec toliko samodejnih ponovnih nalaganj enega pogleda v OKNO_SESUTIJ_S; potem pogled ostane, kot je
#: (vec ponovitev bi pomenilo zanko sesutij, ki jo bolje vidi uporabnik kot procesor).
NAJVEC_OBNOV = 3


class ObnovaPogleda:
    """Ponovno nalozi pogled WebKit, ko njegov spletni proces pade (sesutje ali OOM).

    Stresni preizkus 12. 10. 2026 (naloga #77): jedro je zaradi pomanjkanja pomnilnika ubilo WebKitWebProcess
    delovne povrsine; Python je tekel naprej, namizje pa je ostalo prazno do ponovnega zagona Safeer OS.
    WebKit v tem primeru javi `web-process-terminated` - tu na to odgovorimo z reload (kot brskalnik).
    """

    def __init__(self, ime_programa: str, ime_strani: str, zakasnitev_ms: int = 400, ura=None):
        import time
        self.ime_programa, self.ime_strani = ime_programa, ime_strani
        self.zakasnitev_ms = zakasnitev_ms
        self._ura = ura or time.monotonic
        self._obnove: list = []

    def odlocitev(self, razlog: str) -> bool:
        """Ali naj pogled ponovno nalozimo (in zabelezi)."""
        if razlog == "api":            # program je proces koncal sam (npr. sprosti_zavihke) - ni napaka
            return False
        zdaj = self._ura()
        self._obnove = [t for t in self._obnove if zdaj - t[0] < OKNO_SESUTIJ_S]
        # Stran, ki je enkrat ze presegla mejo pomnilnika, bi jo spet: znova jo nalozimo le enkrat v oknu.
        pomnilnik_ze = razlog == "pomnilnik" and any(r == "pomnilnik" for _t, r in self._obnove)
        if len(self._obnove) >= NAJVEC_OBNOV or pomnilnik_ze:
            zapisi(self.ime_programa, "spletni proces (%s) je padel (%s); prevec obnov v %d min - brez ponovnega nalaganja"
                   % (self.ime_strani, razlog, OKNO_SESUTIJ_S // 60))
            return False
        self._obnove.append((zdaj, razlog))
        zapisi(self.ime_programa, "spletni proces (%s) je padel (%s); stran nalozena znova (%d/%d)"
               % (self.ime_strani, razlog, len(self._obnove), NAJVEC_OBNOV))
        return True


def razlog_padca(WebKit2, razlog) -> str:
    """WebProcessTerminationReason v kratko besedo: sesutje | pomnilnik | api."""
    R = getattr(WebKit2, "WebProcessTerminationReason", None)
    if R is not None:
        if razlog == getattr(R, "EXCEEDED_MEMORY_LIMIT", object()):
            return "pomnilnik"
        if razlog == getattr(R, "TERMINATED_BY_API", object()):
            return "api"
    return "sesutje"


def oznaci_zaprt(pogled) -> None:
    """Zavihek se zapira: cakajoca obnova (obnovi_ob_padcu) ga ne sme vec nalagati (pregled 14. 10. 2026)."""
    try:
        pogled._safeer_zaprt = True
    except Exception:  # noqa: BLE001
        pass


def obnovi_ob_padcu(WebKit2, GLib, pogled, ime_programa: str, ime_strani: str,
                    ob_odpovedi: Optional[Callable] = None) -> Optional[ObnovaPogleda]:
    """Prikljuci obnovo na pogled. Brez signala (zelo star WebKit) ne naredi nicesar.
    ob_odpovedi(pogled, razlog): ko strani ne nalozimo vec znova (prevec padcev, ponovno prekoracen pomnilnik) -
    npr. Splet pokaze razlago z gumbom, da zavihek ne ostane bel."""
    obnova = ObnovaPogleda(ime_programa, ime_strani)

    def ob_padcu(p, razlog):
        beseda = razlog_padca(WebKit2, razlog)
        if not obnova.odlocitev(beseda):
            if ob_odpovedi is not None and beseda != "api":
                try:
                    ob_odpovedi(p, beseda)
                except Exception:  # noqa: BLE001
                    pass
            return

        def znova():
            if getattr(p, "_safeer_zaprt", False):
                return False   # zavihek je medtem zaprt ali zamenjan (ucenje brez pospesevanja) - ne klici unicenega pogleda
            try:
                p.reload()
            except Exception:  # noqa: BLE001 - pogled je ze unicen
                pass
            return False
        GLib.timeout_add(obnova.zakasnitev_ms, znova)
    try:
        pogled.connect("web-process-terminated", ob_padcu)
    except TypeError:
        return None
    return obnova
