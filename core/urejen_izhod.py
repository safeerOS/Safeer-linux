"""Urejen izhod aplikacij Safeer (nacrt stabilnosti P2).

Nacrt stabilnosti (zapisnik 20. 10. 05:30):
  »P2 Urejen izhod: vrstni red UI -> strezniki/vticnice -> podprocesi -> baze -> stanje -> exit;
   preizkus SIGTERM v vsaki fazi zagona.«

Pravila:
  1. Vrstni red:
     - FAZA_UI: skrij/zapri okna, sprosti budnost, vrni Mintov pult, ustavi risanje/animacije
     - FAZA_STREZNIKI: Scit DNS, Link strezniki, posredniki, omrezne vticnice
     - FAZA_PODPROCESI: torrenti (rqbit), medijski predvajalniki (mpv, ffmpeg), DRM, sway/zajem
     - FAZA_BAZE: katalog medijev SQLite, baze sporocil, WAL checkpoint in zaprtje
     - FAZA_STANJE: shramba JSON (os.json, nastavitve), seja/zavihki za obnovo, zacasne mape
     - FAZA_EXIT: quit zanke GLib / unici okna / izhod procesa
  2. Roki:
     - Vsak korak ima dolocen rok (privzeto ROK_KORAKA_S = 2.0 s).
     - Ce posamezen korak preseze rok ali sprozi izjemo, se to zabelezi v dnevnik,
       izhod pa se brezpogojno nadaljuje z naslednjim korakom.
  3. Varnost:
     - Ponovni klic _koncaj je varen (idempotentnost).
     - Deluje v vseh fazah zagona (pred oknom, med nalaganjem, po zagonu).
"""
from __future__ import annotations

import os
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

_aktivni_program: dict[str, Any] = {"ime": "", "koncaj": None}


def izvedi_korak(
    faza: str,
    ime: str,
    dejanje: Callable[[], Any],
    rok_s: float = ROK_KORAKA_S,
    *,
    na_niti: bool = False,
) -> bool:
    """Izvede posamezen korak zapiranja z dolocenim rokom.

    Ce je na_niti=True, dejanje tece v stranski niti z join(timeout=rok_s),
    tako da blokiran klic (I/O, omrezje, podproces) ne zadrzi glavne niti.
    Za UI klice mora biti na_niti=False (GTK zahteva glavno nit).

    Vrne True, ce je korak uspel v roku brez izjeme.
    """
    if na_niti:
        napaka: list[BaseException] = []

        def delo():
            try:
                dejanje()
            except BaseException as e:  # noqa: BLE001 - v loceni niti ujamemo vse izjeme koraka, da ne zrusijo niti
                napaka.append(e)

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
        except BaseException as e:  # noqa: BLE001 - napaka koraka na glavni niti ne sme prekiniti ostalih korakov
            print(
                f"[UrejenIzhod] Napaka v koraku '{ime}' faze '{faza}': {e}",
                file=sys.stderr,
                flush=True,
            )
            return False
        porabljen = time.monotonic() - zacetek
        if porabljen > rok_s:
            print(
                f"[UrejenIzhod] Korak '{ime}' v fazi '{faza}' je presegel rok ({porabljen:.1f} s > {rok_s:.1f} s)",
                file=sys.stderr,
                flush=True,
            )
        return True


def namesti_zgodnje_signale(ime_programa: str) -> None:
    """Namesti rokovalnike signalov takoj ob uvozu ali na zacetku zagona modula.

    Ce signal SIGTERM/SIGINT/SIGHUP pride v fazi pred oknom (preden se ustvari aplikacija),
    zgodnji rokovalnik poskrbi, da se proces zakljuci varno, z zapisanem zacetnim stanjem.
    """
    _aktivni_program["ime"] = ime_programa

    def ob_zgodnjem_signalu(sig, frame=None):
        koncaj_fn = _aktivni_program.get("koncaj")
        if koncaj_fn is not None:
            try:
                from gi.repository import GLib
                if GLib.main_depth() > 0:
                    GLib.idle_add(koncaj_fn)
                    return
            except Exception:  # noqa: BLE001, S110 - izhod/pospravljanje: nobena napaka ne sme ustaviti naslednjih korakov
                pass
            koncaj_fn()
            return

        prog = _aktivni_program.get("ime") or "safeer"
        try:
            from core import nova_razlicica
            nova_razlicica.shrani_stanje(prog, {"pid": os.getpid(), "zgodnji_izhod": True},
                                         ime=nova_razlicica.OBNOVA)
        except Exception as e:  # noqa: BLE001 - izhod/pospravljanje: nobena napaka ne sme ustaviti naslednjih korakov
            print(f"[UrejenIzhod] Zgodnje shranjevanje stanja ni uspelo: {e}", file=sys.stderr, flush=True)
        sys.exit(0)

    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(s, ob_zgodnjem_signalu)
        except Exception:  # noqa: BLE001, S110 - izhod/pospravljanje: nobena napaka ne sme ustaviti naslednjih korakov
            pass


def povezi_signale(koncaj_fn: Callable[[], Any], ime_programa: Optional[str] = None) -> None:
    """Poveze signale SIGTERM, SIGINT, SIGHUP s podano funkcijo koncaj_fn."""
    if ime_programa:
        _aktivni_program["ime"] = ime_programa
    _aktivni_program["koncaj"] = koncaj_fn

    def ob_signalu(sig, frame=None):
        fn = _aktivni_program.get("koncaj") or koncaj_fn
        try:
            from gi.repository import GLib
            if GLib.main_depth() > 0:
                GLib.idle_add(fn)
                return
        except Exception:  # noqa: BLE001, S110 - izhod/pospravljanje: nobena napaka ne sme ustaviti naslednjih korakov
            pass
        fn()

    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(s, ob_signalu)
        except Exception:  # noqa: BLE001, S110 - izhod/pospravljanje: nobena napaka ne sme ustaviti naslednjih korakov
            pass
        try:
            from gi.repository import GLib
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, s, lambda *a: (koncaj_fn(), False)[1])
        except Exception:  # noqa: BLE001, S110 - izhod/pospravljanje: nobena napaka ne sme ustaviti naslednjih korakov
            pass
