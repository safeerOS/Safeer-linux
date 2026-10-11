"""Most Safeer OS za domace (GTK) poglede - isti most kot za spletne strani, brez podvajanja.

Spletna stran klice most z ``klic("metoda", [argumenti])`` in dobi odgovor ter dogodke (``safeerOsDogodek``). Domaci
pogled (npr. GTK Safeer Player) uporablja ISTE metode mostu v safeer_os.py: SafeerOS ga vodi v ``pogledi`` kot vsako
stran, odgovore in dogodke pa namesto v JavaScript poslje temu predmetu. Tako je vsa logika (knjiznica, katalog, viri,
seznami, predvajanje) na enem mestu, domaci pogled je samo drug izris.

Odgovori in dogodki gredo skozi JSON kot pri strani: domaci pogled dobi enake vrste podatkov (seznami, slovarji),
zato isti klic na obeh straneh vrne isto.
"""
from __future__ import annotations

import itertools
import json
from typing import Any, Callable, Optional


def kot_na_strani(podatki: Any) -> Any:
    """Podatki, kot jih vidi stran: skozi JSON (n-terice postanejo seznami, kljuci nizi)."""
    return json.loads(json.dumps(podatki, ensure_ascii=False, default=str))


class NativniPogled:
    """Domaci pogled na mostu Safeer OS. ``poslji(pogled, id_, metoda, argumenti)`` je SafeerOS._most_klic."""

    def __init__(self, poslji: Callable[["NativniPogled", int, str, list], None]) -> None:
        self._poslji = poslji
        self._stevec = itertools.count(1)
        self._cakajo: dict[int, tuple[Optional[Callable], Optional[Callable]]] = {}
        self._narocila: dict[str, list[Callable[[Any], None]]] = {}
        self.zaprt = False

    # ------------------------------------------------------------------ klici
    def klic(self, metoda: str, argumenti: Optional[list] = None, gotovo: Optional[Callable[[Any], None]] = None,
             napaka: Optional[Callable[[str], None]] = None) -> int:
        """Klic metode mostu. ``gotovo(podatki)`` ali ``napaka(sporocilo)`` se poklice na glavni niti."""
        id_ = next(self._stevec)
        self._cakajo[id_] = (gotovo, napaka)
        try:
            self._poslji(self, id_, str(metoda), list(argumenti or []))
        except Exception as e:  # noqa: BLE001 - napaka mostu je odgovor, ne sesutje pogleda
            self.odgovor(id_, False, str(e))
        return id_

    def odgovor(self, id_: int, ok: bool, podatki: Any) -> bool:
        """Odgovor mostu (SafeerOS._odgovori ga poklice na glavni niti). Vrne False za GLib.idle_add."""
        gotovo, napaka = self._cakajo.pop(int(id_), (None, None))
        if self.zaprt:
            return False
        try:
            if ok and gotovo is not None:
                gotovo(kot_na_strani(podatki))
            elif not ok and napaka is not None:
                napaka(str(podatki))
            elif not ok:
                print("[SafeerPlayer] most:", podatki)
        except Exception as e:  # noqa: BLE001
            print("[SafeerPlayer] odgovor:", e)
        return False

    # ------------------------------------------------------------------ dogodki
    def naroci(self, vrsta: str, fn: Callable[[Any], None]) -> None:
        self._narocila.setdefault(str(vrsta), []).append(fn)

    def dogodek(self, vrsta: str, podatki: Any) -> bool:
        """Dogodek mostu (kot safeerOsDogodek na strani). Vrne False za GLib.idle_add."""
        if self.zaprt:
            return False
        podatki = kot_na_strani(podatki)
        klici = [(fn, (podatki,)) for fn in self._narocila.get(str(vrsta), ())]
        klici += [(fn, (str(vrsta), podatki)) for fn in self._narocila.get("*", ())]   # vsi dogodki: fn(vrsta, podatki)
        for fn, argumenti in klici:
            try:
                fn(*argumenti)
            except Exception as e:  # noqa: BLE001
                print("[SafeerPlayer] dogodek", vrsta, e)
        return False

    def zapri(self) -> None:
        self.zaprt = True
        self._cakajo.clear()
        self._narocila.clear()
