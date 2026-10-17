"""Jeziki, ki jih spletne strani vidijo (navigator.languages, Accept-Language).

WebKitGTK jih sicer vzame iz okolja spletnega procesa; ta v peskovniku nima LANG/LANGUAGE, zato je bil
navigator.language »C« - neveljavna oznaka BCP 47. Strani, ki jo podajo Intl.Locale (Kotlin/Compose, JetStream 3
Kotlin-compose-wasm), so dobile RangeError in obstale (preizkus 17. 10. 2026). Jezike zato nastavimo sami iz jezika seje.
"""

from __future__ import annotations

import os
import re
from typing import List, Mapping, Optional

_OZNAKA = re.compile(r"^([a-zA-Z]{2,3})(?:[_-]([a-zA-Z]{2}|\d{3}))?")


def _bcp47(del_: str) -> str:
    """sl_SI.UTF-8@euro -> sl-SI; C, POSIX in prazno -> ''."""
    del_ = (del_ or "").split(".", 1)[0].split("@", 1)[0].strip()
    if del_.upper() in ("", "C", "POSIX"):
        return ""
    m = _OZNAKA.match(del_)
    if not m:
        return ""
    jezik, regija = m.group(1).lower(), m.group(2)
    return jezik + ("-" + regija.upper() if regija else "")


def jeziki(okolje: Optional[Mapping[str, str]] = None) -> List[str]:
    """Seznam jezikov po prednosti (npr. ['sl-SI', 'sl', 'en-US', 'en']); vedno vsaj angleščina."""
    okolje = os.environ if okolje is None else okolje
    izhod: List[str] = []

    def dodaj(oznaka: str) -> None:
        if oznaka and oznaka not in izhod:
            izhod.append(oznaka)

    for ime in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        for del_ in str(okolje.get(ime) or "").split(":"):
            oznaka = _bcp47(del_)
            dodaj(oznaka)
            if "-" in oznaka:
                dodaj(oznaka.split("-", 1)[0])
    dodaj("en-US")
    dodaj("en")
    return izhod[:8]


def nastavi(kontekst) -> None:
    """WebContext.set_preferred_languages; brez napake, ce ga ta WebKit nima."""
    try:
        kontekst.set_preferred_languages(jeziki())
    except Exception:  # noqa: BLE001
        pass
