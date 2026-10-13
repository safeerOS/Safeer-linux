"""Seja agenta: eno narocilo z vec nalogami, trajanje od 1 minute do neomejeno, ustavitev z enim dotikom.
Spomin seje so samo kratki izidi (ne odgovori naprav)."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from core.agent import izvajanje, razumevanje


@dataclass
class Korak:
    naloga: dict
    izid: str
    ok: bool
    naprava: str = ""


@dataclass
class Seja:
    trajanje_min: Optional[int] = None          # None = neomejeno
    izvajalec: izvajanje.Izvajalec = field(default_factory=izvajanje.Izvajalec)
    klic_modela: Optional[Callable] = None
    tukaj: str = ""
    ura: Callable[[], float] = time.monotonic
    koraki: List[Korak] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.trajanje_min is not None:
            self.trajanje_min = max(1, int(self.trajanje_min))
        self._zacetek = self.ura()
        self._ustavi = threading.Event()

    def ustavi(self) -> None:
        self._ustavi.set()

    def tece(self) -> bool:
        if self._ustavi.is_set():
            return False
        return self.trajanje_min is None or self.ura() - self._zacetek < self.trajanje_min * 60

    def narocilo(self, besedilo: str) -> List[Korak]:
        """Razume stavek in izvede vse naloge po vrsti, dokler seja tece. Vrne korake tega narocila."""
        if not self.tece():
            return [Korak({}, "Seja je končana.", False)]
        r = razumevanje.razumi(besedilo, self.klic_modela)
        if not r.naloge:
            k = [Korak({}, "Nisem razumel." if r.napaka == "ni razumljivo" else r.napaka, False)]
            self.koraki += k
            return k
        izvedeni = []
        for n in r.naloge:
            if not self.tece():
                izvedeni.append(Korak(n.slovar(), "Ustavljeno.", False))
                break
            i = izvajanje.izvedi(n, self.izvajalec, self.tukaj)
            izvedeni.append(Korak(n.slovar(), i.besedilo, i.ok, i.naprava))
        self.koraki += izvedeni
        return izvedeni
