"""Sporocila Qt (QML, PySide6) v nas dnevnik, brez skrivnosti (nacrt stabilnosti P1, naloga 42).

Qt jih privzeto pise neposredno na deskriptor 2: mimo os_stabilnost.CistIzpis, zato naslovi z zetoni (napaka nalaganja
slike QML z ?token=..., Jellyfin/Plex) in domaca mapa v poteh datotek QML niso bili ocisceni. Zdaj gre vsako sporocilo
skozi os_stabilnost.cisto() v sys.stderr (zaganjalnik ga pise v sled.log), z vrsto in mestom v QML.

namesti() klice os_lupina.pripravi() pred nastankom QApplication - velja za Safeer OS (lupina v procesu) in za lupino v
svojem procesu (core/lupina_proces.py), ki pripravi() klice isto.
"""
from __future__ import annotations

import sys
from typing import Any, Optional

#: QtMsgType: QtDebugMsg 0, QtWarningMsg 1, QtCriticalMsg 2, QtFatalMsg 3, QtInfoMsg 4.
VRSTE = {0: "debug", 1: "opozorilo", 2: "kriticno", 3: "usodno", 4: "info"}
#: Razhroscevalna sporocila Qt (qDebug, console.log iz QML) so prepogosta za sled.log.
PREZRI = {0}
#: Najdaljse sporocilo v dnevniku (napaka QML z dolgim JSON ne sme napihniti sled.log).
NAJVEC_ZNAKOV = 2000

_namescen: dict = {"obravnava": None}


def _stevilka(vrsta: Any) -> int:
    for poskus in (lambda: int(vrsta), lambda: int(vrsta.value)):
        try:
            return poskus()
        except (TypeError, ValueError, AttributeError):
            continue
    return 1


def vrstica(vrsta: Any, kontekst: Any, sporocilo: Any) -> Optional[str]:
    """Vrstica za dnevnik ali None (prezrta vrsta). Brez zetonov, poizvedb naslovov in domace mape (cisto)."""
    from core.os_stabilnost import cisto
    st = _stevilka(vrsta)
    if st in PREZRI:
        return None
    mesto = ""
    datoteka = getattr(kontekst, "file", None)
    if datoteka:
        mesto = " %s:%s" % (datoteka, getattr(kontekst, "line", 0) or 0)
    besedilo = " ".join(str(sporocilo or "").split())
    if len(besedilo) > NAJVEC_ZNAKOV:
        besedilo = besedilo[:NAJVEC_ZNAKOV] + " ..."
    return cisto("[Qt %s]%s %s" % (VRSTE.get(st, str(st)), mesto, besedilo))


def obravnavaj(vrsta: Any, kontekst: Any, sporocilo: Any, tok=None) -> None:
    """qInstallMessageHandler: klice ga Qt iz katerekoli niti. Ne sme vreci izjeme (Qt bi proces koncal)."""
    try:
        v = vrstica(vrsta, kontekst, sporocilo)
        if v is None:
            return
        cilj = tok if tok is not None else sys.stderr
        cilj.write(v + "\n")
        if _stevilka(vrsta) == 3:
            cilj.flush()              # usodno: Qt po vrnitvi konca proces
    except Exception as e:  # noqa: BLE001 - dnevnik ne sme podreti programa (zaprt stderr ob odjavi)
        try:
            sys.__stderr__.write("[Qt] dnevnik: %s\n" % type(e).__name__)
        except Exception:  # noqa: BLE001
            return


def namesti(QtCore: Any = None) -> bool:
    """Namesti obravnavo sporocil Qt (enkrat na proces). Vrne True, ce je namescena."""
    if _namescen["obravnava"] is not None:
        return True
    try:
        if QtCore is None:
            from PySide6 import QtCore as _QtCore
            QtCore = _QtCore
        _namescen["obravnava"] = obravnavaj        # referenca ostane (PySide6 drzi samo klicatelja)
        QtCore.qInstallMessageHandler(obravnavaj)
        return True
    except Exception as e:  # noqa: BLE001 - brez Qt ni sporocil Qt
        _namescen["obravnava"] = None
        print("[Qt] obravnava sporocil ni namescena:", type(e).__name__, flush=True)
        return False


__all__ = ["VRSTE", "vrstica", "obravnavaj", "namesti"]
