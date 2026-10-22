"""Urejen izhod aplikacij Safeer (nacrt stabilnosti P2).

Nacrt stabilnosti (zapisnik 20. 10. 05:30):
  »P2 Urejen izhod: vrstni red UI -> strezniki/vticnice -> podprocesi -> baze -> stanje -> exit;
   preizkus SIGTERM v vsaki fazi zagona.«

Pravila:
  1. Vrstni red:
     - FAZA_UI: skrij/zapri okna, sprosti budnost, vrni Mintov pult, ustavi risanje/animacije,
       ustavi neposredni medij in zapri predvajalnik (GTK/GLib na glavni niti)
     - FAZA_STREZNIKI: Scit DNS (povrnitev do konca, rok 35 s), Link strezniki, posredniki, omrezne vticnice
     - FAZA_PODPROCESI: torrenti (rqbit), podprocesi vsak v svoji niti hkrati z rokom, sway/zajem
     - FAZA_BAZE: katalog medijev SQLite, baze sporocil, WAL checkpoint in zaprtje
     - FAZA_STANJE: shramba JSON (os.json, nastavitve), seja/zavihki za obnovo pod varuhom, zacasne mape
     - FAZA_EXIT: pospravi vse otroke (otroci.pospravi_vse), quit zanke GLib / unici okna / izhod procesa
  2. Roki:
     - Vsak korak ima dolocen rok (privzeto ROK_KORAKA_S = 2.0 s; Scit DNS rok 35 s).
     - Ce posamezen korak preseze rok ali sprozi izjemo, se to zabelezi v dnevnik,
       izhod pa se brezpogojno nadaljuje z naslednjim korakom.
  3. Varnost:
     - Ponovni klic _koncaj je varen (idempotentnost).
     - Deluje v vseh fazah zagona (pred oknom, med nalaganjem, po zagonu).
"""
from __future__ import annotations

import signal
import sys
import threading
import time
from typing import Any, Callable, Optional

FAZA_UI = "UI"
FAZA_STREZNIKI = "strezniki/vticnice"
FAZA_PODPROCESI = "podprocesi"
FAZA_BAZE = "baze"
FAZA_STANJE = "stanje"
FAZA_EXIT = "exit"

VRSTNI_RED_FAZ = (
    FAZA_UI,
    FAZA_STREZNIKI,
    FAZA_PODPROCESI,
    FAZA_BAZE,
    FAZA_STANJE,
    FAZA_EXIT,
)

ROK_KORAKA_S = 2.0
#: Povrnitev DNS Scita (resolvectl prek pkexec, cas=30 s po vmesniku): mora do konca, zgornja meja je nad njo, da izhod
#: ne visi vecno ob zatakniti.
ROK_SCITA_S = 35.0

_aktivni_program: dict[str, Any] = {"ime": "", "koncaj": None}
_zgodnji_signal: dict[str, Any] = {"signal": None}


def izvedi_korak(
    faza: str,
    ime: str,
    dejanje: Callable[[], Any],
    rok_s: Optional[float] = ROK_KORAKA_S,
    *,
    na_niti: bool = False,
) -> bool:
    """Izvede posamezen korak zapiranja z dolocenim rokom (rok_s=None: brez roka, samo za klice, ki jih ne smemo opustiti).

    Ce je na_niti=True, dejanje tece v stranski niti z join(timeout=rok_s),
    tako da blokiran klic (I/O, omrezje, podproces) ne zadrzi glavne niti.
    Za UI klice mora biti na_niti=False (GTK zahteva glavno nit).

    Vrne True, ce je korak uspel v roku brez izjeme.
    M4: lovi Exception; SystemExit/KeyboardInterrupt se po zapisu dvigneta.
    """
    if na_niti:
        napaka: list[Exception] = []
        prekinitev: list[BaseException] = []

        def delo():
            try:
                dejanje()
            except Exception as e:  # noqa: BLE001 - v loceni niti ujamemo izjeme koraka, da ne zrusijo niti
                napaka.append(e)
            except (SystemExit, KeyboardInterrupt) as e:
                prekinitev.append(e)

        t = threading.Thread(target=delo, name=f"izhod-{ime}", daemon=True)
        zacetek = time.monotonic()
        t.start()
        t.join(timeout=rok_s)
        porabljen = time.monotonic() - zacetek
        if t.is_alive():
            print(
                f"[UrejenIzhod] Korak '{ime}' v fazi '{faza}' je presegel rok ({rok_s:.1f} s), nadaljujem...",
                file=sys.stderr,
                flush=True,
            )
            return False
        if prekinitev:
            print(
                f"[UrejenIzhod] Korak '{ime}' faze '{faza}' prekinjen z {type(prekinitev[0]).__name__}",
                file=sys.stderr,
                flush=True,
            )
            raise prekinitev[0]
        if napaka:
            print(
                f"[UrejenIzhod] Napaka v koraku '{ime}' faze '{faza}': {napaka[0]}",
                file=sys.stderr,
                flush=True,
            )
            return False
        return True
    else:
        zacetek = time.monotonic()
        try:
            dejanje()
        except Exception as e:  # noqa: BLE001 - napaka koraka na glavni niti ne sme prekiniti ostalih korakov
            print(
                f"[UrejenIzhod] Napaka v koraku '{ime}' faze '{faza}': {e}",
                file=sys.stderr,
                flush=True,
            )
            return False
        except (SystemExit, KeyboardInterrupt) as e:
            print(
                f"[UrejenIzhod] Korak '{ime}' faze '{faza}' prekinjen z {type(e).__name__}",
                file=sys.stderr,
                flush=True,
            )
            raise
        porabljen = time.monotonic() - zacetek
        if rok_s is not None and porabljen > rok_s:
            print(
                f"[UrejenIzhod] Korak '{ime}' v fazi '{faza}' je presegel rok ({porabljen:.1f} s > {rok_s:.1f} s)",
                file=sys.stderr,
                flush=True,
            )
        return True


def izvedi_vzporedno(
    faza: str,
    koraki: list[tuple[str, Callable[[], Any]]],
    rok_s: float = ROK_KORAKA_S,
) -> bool:
    """Izvede vec korakov zapiranja hkrati, vsak v svoji niti, s skupnim rokom (K3).

    Vse niti se zacnejo socasno. Glavna nit pocaka do izteka skupnega roka.
    Ce kateri od korakov ne zakljuci v roku, se v dnevnik zapise natancen seznam
    tistih korakov, ki niso koncali.
    """
    if not koraki:
        return True

    napake: dict[str, Exception] = {}
    prekinitve: list[BaseException] = []
    niti: list[tuple[str, threading.Thread]] = []

    for ime, dejanje in koraki:
        def delo(korak_ime=ime, korak_dejanje=dejanje):
            try:
                korak_dejanje()
            except Exception as e:  # noqa: BLE001 - v loceni niti ujamemo izjemo koraka, da ne zrusi niti
                napake[korak_ime] = e
            except (SystemExit, KeyboardInterrupt) as e:
                prekinitve.append(e)

        t = threading.Thread(target=delo, name=f"izhod-{ime}", daemon=True)
        niti.append((ime, t))

    zacetek = time.monotonic()
    for _ime, t in niti:
        t.start()

    rok_konec = zacetek + rok_s
    for _ime, t in niti:
        preostanek = max(0.0, rok_konec - time.monotonic())
        t.join(timeout=preostanek)

    prekoraceni = [ime for ime, t in niti if t.is_alive()]
    if prekoraceni:
        print(
            f"[UrejenIzhod] Koraki v fazi '{faza}' so presegli rok ({rok_s:.1f} s), nadaljujem: {', '.join(prekoraceni)}",
            file=sys.stderr,
            flush=True,
        )

    for ime, e in napake.items():
        print(
            f"[UrejenIzhod] Napaka v koraku '{ime}' faze '{faza}': {e}",
            file=sys.stderr,
            flush=True,
        )

    if prekinitve:
        print(
            f"[UrejenIzhod] Koraki faze '{faza}' prekinjeni z {type(prekinitve[0]).__name__}",
            file=sys.stderr,
            flush=True,
        )
        raise prekinitve[0]

    return len(prekoraceni) == 0 and len(napake) == 0


def namesti_zgodnje_signale(ime_programa: str) -> None:
    """Namesti rokovalnike signalov takoj ob uvozu ali na zacetku zagona modula (P4).

    Rokovalnik samo zabelezi prejeti signal v zastavico, main pa jo preveri
    po vsaki fazi zagona in ob prejetem signalu zakljuci proces s kodo 128+signal.
    Stanja brez vsebine ne pise.
    """
    if _aktivni_program.get("koncaj") is not None:
        # Modul programa uvozen drugic (npr. Control ali preizkus uvozi safeer_os): povezi_signale ze drzi
        # GLib vire; Python signal.signal bi jih prepisal in SIGTERM po zagonu ne bi nic naredil (izmerjeno 22. 10.: strace).
        return
    _aktivni_program["ime"] = ime_programa

    def ob_zgodnjem_signalu(sig, frame=None):
        _zgodnji_signal["signal"] = sig

    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(s, ob_zgodnjem_signalu)
        except Exception:  # noqa: BLE001, S110 - izhod/pospravljanje: nobena napaka ne sme ustaviti naslednjih korakov
            pass


def prejeti_zgodnji_signal() -> Optional[int]:
    """Vrne signal, prejet med zagonom (ali None)."""
    return _zgodnji_signal.get("signal")


def preveri_zgodnji_signal() -> None:
    """Ce je bil med zagonom prejet zgodnji signal, takoj izstopi s kodo 128+signal (P4)."""
    sig = _zgodnji_signal.get("signal")
    if sig is not None:
        koncaj_fn = _aktivni_program.get("koncaj")
        if koncaj_fn is not None:
            try:
                koncaj_fn()
            except Exception:  # noqa: BLE001, S110 - izhod/pospravljanje: nobena napaka ne sme ustaviti izhoda
                pass
        sys.exit(128 + sig)


def povezi_signale(koncaj_fn: Callable[[], Any], ime_programa: Optional[str] = None) -> None:
    """Poveze signale SIGTERM, SIGINT, SIGHUP s podano funkcijo koncaj_fn (M5).

    Uporablja izkljucno GLib.unix_signal_add, brez podvojenih Python signal.signal rokovalnikov.
    """
    if ime_programa:
        _aktivni_program["ime"] = ime_programa
    _aktivni_program["koncaj"] = koncaj_fn

    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            from gi.repository import GLib

            def _ob_glib_signalu(*_a, fn=koncaj_fn, snum=s):
                fn()
                return False

            GLib.unix_signal_add(
                GLib.PRIORITY_HIGH,
                s,
                _ob_glib_signalu,
            )
        except Exception:  # noqa: BLE001, S110 - izhod/pospravljanje: nobena napaka ne sme ustaviti naslednjih korakov
            pass
