"""Safeer Scit v svojem procesu pod varuhom (core/varuh_procesov.py) - 1.0.129, lastnik 20. 10. 2026.

Preizkus odpornosti na testnem PC (20. 10. 2026, odpornost.py) je pokazal: Scit (razresevalnik DNS 127.0.0.1:5354 in
straza) je tekel v procesu Safeer OS z vmesnikom. Ko je ta zamrznil (SIGSTOP), je systemd-resolved po ~7 s presel na
usmerjevalnik - ~22 s brez blokiranja oglasov in nevarnih strani; ob sesutju je 1 oglas sel mimo. Zdaj:

  * vticnici UDP in TCP na 127.0.0.1:5354 odpre VARUH in ju da temu procesu (fd 3 in 4, SAFEER_SCIT_FDS). Ko se ta
    proces sesuje ali ga varuh zamenja, vrata ostanejo odprta: poizvedbe pocakajo v vrsti jedra in jih odgovori nov
    proces - resolved ne preide na usmerjevalnik;
  * proces je majhen (brez Gtk, Qt, WebKit) in ga zamrznitev vmesnika ne doseze;
  * utrip (WATCHDOG=1) poslje sele, ko razresevalnik na lastna vrata odgovori kanarcku - zataknjen razresevalnik varuh
    zamenja v ZAMRZNITEV_SCIT_S;
  * Safeer OS ga vprasa prek vticnice scit.sock (core/scit_odjemalec.py, en JSON v vrstici, samo nas uid).

Zagon: varuh (python3 core/scit_proces.py). `--pospravi`: samo vrne DNS vmesnikov, ki jih je Scit pustil brez
delujocega razresevalnika (varuh ob obupu).
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__" and not __package__:
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import faulthandler
import json
import signal
import socket
import struct
import threading
from typing import Any, Callable, Dict, Optional

#: Metode Scita, ki jih sme poklicati Safeer OS (nic drugega - vticnica ne sme postati splosen klic v proces).
METODE: Dict[str, Callable[..., Any]] = {
    "stanje": lambda s: s.stanje(),
    "stanje_pulta": lambda s: s.stanje_pulta(),
    "nastavi": lambda s, vklop=False: s.nastavi(bool(vklop)),
    "nastavi_naprej": lambda s, izbira="", po_meri="": s.nastavi_naprej(str(izbira or ""), str(po_meri or "")),
    "dovoli": lambda s, domena="", dovoli=True: s.dovoli(str(domena or ""), bool(dovoli)),
    "premor": lambda s, minut=0: s.premor(minut if isinstance(minut, (int, float)) and not isinstance(minut, bool) else 0),
    "nastavi_twitch": lambda s, vklop=True: s.nastavi_twitch(bool(vklop)),
}
#: Najvecja zahteva (bajtov) in najvec hkratnih povezav na vticnici.
NAJVEC_ZAHTEVA = 4096
NAJVEC_POVEZAV = 8
#: Utrip: toliko sekund med preverbami razresevalnika (varuh: ZAMRZNITEV_SCIT_S brez utripa = zamenjava).
UTRIP_SCIT_S = 1.0
#: Rok kanarcka (s): zaseden razresevalnik (pocasen DoH) ne sme sproziti lazne zamrznitve - kanarcek ne gre naprej.
ROK_KANARCKA_S = 1.5


def pot_vticnice() -> str:
    from core import varuh_procesov
    return os.path.join(varuh_procesov.mapa_izvajanja(), "scit.sock")


def pot_nastavitev() -> str:
    """Ista datoteka kot core/os_programi.Shramba (os.json Safeer OS) - brez uvoza os_programi (WebKit, Gio)."""
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "safeer-os", "os.json")


def podedovane_vticnice(vrednost: str) -> Optional[tuple]:
    """'3,4' -> (UDP, TCP) vticnici na 127.0.0.1:<VRATA>, ki ju je odprl varuh; sicer None (proces odpre svoje)."""
    from core import os_scit
    try:
        fd_u, fd_t = (int(x) for x in vrednost.split(","))
        u = socket.socket(fileno=fd_u)
        t = socket.socket(fileno=fd_t)
    except (ValueError, OSError):
        return None
    try:
        if (u.type != socket.SOCK_DGRAM or t.type != socket.SOCK_STREAM or u.getsockname()[0] != os_scit.NASLOV
                or u.getsockname() != t.getsockname() or u.getsockname()[1] not in os_scit.VRATA):
            raise ValueError(u.getsockname())
    except (OSError, ValueError) as e:
        print("[Scit] podedovani vticnici nista nasi (%s): odprem svoje" % e, flush=True)
        for s in (u, t):
            s.close()
        return None
    u.set_inheritable(False)
    t.set_inheritable(False)
    return u, t


class Streznik:
    """Vticnica scit.sock: zahteva {"m": metoda, "a": {...}} v eni vrstici, odgovor {"ok": ...} ali {"napaka": ...}."""

    def __init__(self, scit, pot: str) -> None:
        self.scit = scit
        self.pot = pot
        self._proste = threading.BoundedSemaphore(NAJVEC_POVEZAV)
        try:
            os.unlink(pot)
        except OSError:
            pass
        self.vtic = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
        stara = os.umask(0o177)
        try:
            self.vtic.bind(pot)
        finally:
            os.umask(stara)
        self.vtic.listen(NAJVEC_POVEZAV)

    def tek(self) -> None:
        while True:
            try:
                s, _ = self.vtic.accept()
            except OSError:
                return
            if not self._proste.acquire(blocking=False):
                s.close()
                continue
            threading.Thread(target=self._streci, args=(s,), name="safeer-scit-ipc", daemon=True).start()

    def _streci(self, s: socket.socket) -> None:
        try:
            cred = s.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            _pid, uid, _gid = struct.unpack("3i", cred)
            if uid != os.getuid():
                return
            s.settimeout(10)
            podatki = b""
            while not podatki.endswith(b"\n"):
                del_ = s.recv(NAJVEC_ZAHTEVA)
                if not del_:
                    return
                podatki += del_
                if len(podatki) > NAJVEC_ZAHTEVA:
                    return
            s.settimeout(None)
            odgovor = self.odgovori(podatki)
            s.sendall(json.dumps(odgovor, ensure_ascii=False).encode("utf-8") + b"\n")
        except (OSError, struct.error):
            pass
        finally:
            s.close()
            self._proste.release()

    def odgovori(self, podatki: bytes) -> dict:
        try:
            zahteva = json.loads(podatki.decode("utf-8"))
            metoda = METODE[zahteva["m"]]
            argumenti = zahteva.get("a") or {}
            if not isinstance(argumenti, dict):
                raise TypeError("a")
        except (ValueError, KeyError, TypeError, AttributeError, UnicodeError):
            return {"napaka": "zahteva"}
        try:
            return {"ok": metoda(self.scit, **argumenti)}
        except TypeError:
            return {"napaka": "argumenti"}
        except Exception as e:  # noqa: BLE001 - napaka ene zahteve ne sme ustaviti Scita
            print("[Scit] %s: %s %s" % (zahteva.get("m"), type(e).__name__, e), flush=True)
            return {"napaka": "scit"}


def utripaj(scit, konec: threading.Event) -> None:
    """WATCHDOG=1 vsakih UTRIP_SCIT_S, ce razresevalnik odgovori kanarcku (ali Scit ni vklopljen)."""
    from core import os_scit, varuh_procesov
    while not konec.wait(UTRIP_SCIT_S):
        r = scit.razresevalnik
        if r is not None and r.vrata and not os_scit._odgovori_kanarcku(r.vrata, ROK_KANARCKA_S):
            continue
        varuh_procesov.obvesti("WATCHDOG=1")


def pospravi_nasa_vrata(vrata: int) -> list:
    """Scit je izklopljen, vmesnik pa ima se nas streznik (127.0.0.1:<vrata>) na prvem mestu - ostanek sesutja starejse
    razlicice. Vrata drzi varuh, zato os_scit.je_ostanek misli, da Scit tece (nekdo poslusa), resolved pa bi na vsako
    ime cakal odgovor, ki ga ne bo. Takim vmesnikom vrnemo DNS usmerjevalnika (samo s pravilom polkit, brez gesla)."""
    from core import os_scit
    nas = "%s:%d" % (os_scit.NASLOV, vrata)
    popravljeni = []
    try:
        for v in os_scit.vmesniki_povezani():
            prvi = (os_scit.dns_vmesnika(v).split() or [""])[0]
            if prvi == nas and os_scit.upstream_strezniki(v) and os_scit.pravilo_namesceno() and os_scit.povrni(v):
                popravljeni.append(v)
    except Exception as e:  # noqa: BLE001
        print("[Scit] ostanki:", e, flush=True)
    return popravljeni


def pospravi() -> int:
    """Varuh je obupal (Scit se je vec krat zapored ustavil) in zaprl vrata: vmesnikom vrni DNS usmerjevalnika."""
    from core import os_scit, shramba_json
    popravljeni = os_scit.Scit(shramba_json.Shramba(pot_nastavitev())).pospravi_ostanke()
    print("[Scit] pospravljeno:", ", ".join(popravljeni) or "nic", flush=True)
    return 0


def main(argumenti: Optional[list] = None) -> int:
    argumenti = list(sys.argv[1:] if argumenti is None else argumenti)
    faulthandler.enable()            # SIGABRT varuha ob zamrznitvi: sled vseh niti v sled.log
    if "--pospravi" in argumenti:
        return pospravi()
    from core import os_scit, shramba_json, varuh_procesov
    varuh_procesov.pripravi_obvestila()
    podedovane = podedovane_vticnice(os.environ.get("SAFEER_SCIT_FDS", ""))
    if podedovane is not None:
        os_scit.uporabi_podedovane(*podedovane)
    scit = os_scit.Scit(shramba_json.Shramba(pot_nastavitev()))
    konec = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_a: konec.set())
    signal.signal(signal.SIGINT, lambda *_a: konec.set())
    streznik = Streznik(scit, os.environ.get("SAFEER_SCIT_VTIC") or pot_vticnice())
    threading.Thread(target=streznik.tek, name="safeer-scit-vticnica", daemon=True).start()
    scit._zagon()                    # vklopljen: razresevalnik in straza; izklopljen: pospravi ostanke
    if podedovane is not None and not scit.vklopljen:
        pospravi_nasa_vrata(podedovane[0].getsockname()[1])
    varuh_procesov.obvesti("READY=1")
    print("[Scit] pripravljen (pid %d, vrata %s, %s)" % (
        os.getpid(), scit.razresevalnik.vrata if scit.razresevalnik else 0,
        "podedovana" if podedovane else "lastna"), flush=True)
    threading.Thread(target=utripaj, args=(scit, konec), name="safeer-scit-utrip", daemon=True).start()
    while not konec.wait(3600):
        pass
    # Konec seje (varuh: SIGTERM vsem): DNS vmesnikov nazaj na usmerjevalnik, kot prej ob koncu Safeer OS.
    scit.koncaj()
    try:
        os.unlink(streznik.pot)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
