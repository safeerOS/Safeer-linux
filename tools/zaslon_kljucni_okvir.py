"""Cista pravila za zahtevo po kljucnem okvirju (IDR) na strani racunalnika (KLJUC1-4).

Zrcalna kopija pravil iz si.safeer.tv.os.ZaslonKljucniOkvir (Kotlin, TV) in dodatno
drsece okno na strani kodirnika: najvec 1 IDR v 2000 ms, ne glede na to, kaj poslje
odjemalec (TV, pokvarjen odjemalec ali napadalec na omrezju).

Brez odvisnosti (samo standardna knjiznica). Cas je vedno podan kot parameter
(monotona ura v milisekundah, npr. int(time.monotonic() * 1000)), zato so pravila
deterministicna. Vsak razred ima lasten threading.Lock, zato ga lahko klice vec niti.

Uporaba (bot na Linuxu, pred kodirnikom):
    zascita = ZascitaKodirnika()
    izid = zascita.zahteva(Razlog.IZGUBA_PAKETA, int(time.monotonic() * 1000))
    if izid.poslji:
        kodirnik.ustvari_idr()
"""

from __future__ import annotations

import enum
import threading
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

# Konstante so enake kot v Kotlin razlicici.
NAJMANJ_RAZMIK_MS = 500
NAJVEC_RAZMIK_MS = 4000
ZACETNI_RAZMIK_MS = 500
TISINA_PO_USPEHU_MS = 2000
MIROVANJE_ZA_PONASTAVITEV_MS = 2 * NAJVEC_RAZMIK_MS
ROCNO_NAJMANJ_RAZMIK_MS = 100

# Drsece okno kodirnika: najvec OKNO_NAJVEC_IDR kljucnih okvirjev v OKNO_MS.
OKNO_MS = 2000
OKNO_NAJVEC_IDR = 1

# Obseg Long (64 bit) kot v Kotlinu, da so izidi pri skrajnih casih enaki.
LONG_MIN = -(2 ** 63)
LONG_MAX = 2 ** 63 - 1


class Razlog(enum.Enum):
    """Razlog za zahtevo po novem kljucnem okvirju."""

    NAPAKA_DEKODIRNIKA = "NAPAKA_DEKODIRNIKA"
    IZGUBA_PAKETA = "IZGUBA_PAKETA"
    ZASTOJ_SLIKE = "ZASTOJ_SLIKE"
    ROCNO = "ROCNO"


@dataclass(frozen=True)
class Odlocitev:
    """Izid presoje: ali naj se zahteva izvede takoj in koliko ms je treba sicer cakati."""

    poslji: bool
    cakaj_ms: int


def _preveri_cas(zdaj_ms: int) -> int:
    """Sprejme samo cela stevila (ne bool) v obsegu Long, sicer vrze izjemo."""
    if isinstance(zdaj_ms, bool) or not isinstance(zdaj_ms, int):
        raise TypeError("zdaj_ms mora biti int (milisekunde monotone ure)")
    if zdaj_ms < LONG_MIN or zdaj_ms > LONG_MAX:
        raise ValueError("zdaj_ms je zunaj obsega 64-bitnega stevila")
    return zdaj_ms


def _nasicena_razlika(a: int, b: int) -> int:
    """Razlika a - b, omejena na obseg Long (enako kot nasicenaRazlika v Kotlinu)."""
    return max(LONG_MIN, min(LONG_MAX, a - b))


def _preostali_cas(cas: int, zacetek: Optional[int], razmik_ms: int) -> int:
    if zacetek is None:
        return 0
    minilo = _nasicena_razlika(cas, zacetek)
    if minilo < 0:
        return razmik_ms
    return 0 if minilo >= razmik_ms else razmik_ms - minilo


class Presojevalec:
    """Ista pravila kot ZaslonKljucniOkvir.Presojevalec v Kotlinu.

    - Cas nazaj se steje kot zadnji znani cas.
    - Samodejni razlogi: razmik 500 -> 1000 -> 2000 -> 4000 (strop) ob zaporednih poslanih
      zahtevah brez uspeha, tisina 2000 ms po uspehu, cakaj_ms je vecji od obeh preostankov.
    - ROCNO: samo najkrajsi razmik 100 ms od zadnje zahteve; poslana ROCNO zahteva steje v stevec
      in podvoji razmik enako kot samodejna.
    - Meje so vkljucne (pri tocno 500 ms gre).
    - Po mirovanju > MIROVANJE_ZA_PONASTAVITEV_MS od zadnje poslane zahteve se ob naslednji presoji
      razmik in stevec ponastavita (tisina po uspehu ostane).
    - zaporednih_neuspelih se poveca za 1 natanko ob vsaki presoji s poslji=True.
    """

    def __init__(self) -> None:
        self._zaklep = threading.Lock()
        self._zadnja_zahteva_ms: Optional[int] = None
        self._zadnji_uspeh_ms: Optional[int] = None
        self._zadnji_znani_cas_ms: Optional[int] = None
        self._trenutni_razmik_ms = ZACETNI_RAZMIK_MS
        self._stevec_zaporednih = 0

    @property
    def zaporednih_neuspelih(self) -> int:
        with self._zaklep:
            return self._stevec_zaporednih

    def presodi(self, razlog: Razlog, zdaj_ms: int) -> Odlocitev:
        if not isinstance(razlog, Razlog):
            raise TypeError("razlog mora biti Razlog")
        _preveri_cas(zdaj_ms)
        with self._zaklep:
            cas = self._uskladi_cas(zdaj_ms)
            self._ponastavi_po_mirovanju(cas)
            zadnja = self._zadnja_zahteva_ms

            if razlog is Razlog.ROCNO:
                preostalo = _preostali_cas(cas, zadnja, ROCNO_NAJMANJ_RAZMIK_MS)
                if preostalo > 0:
                    return Odlocitev(poslji=False, cakaj_ms=preostalo)
                self._zabelezi_poslano_zahtevo(cas)
                return Odlocitev(poslji=True, cakaj_ms=0)

            preostalo = max(
                _preostali_cas(cas, zadnja, self._trenutni_razmik_ms),
                _preostali_cas(cas, self._zadnji_uspeh_ms, TISINA_PO_USPEHU_MS),
            )
            if preostalo > 0:
                return Odlocitev(poslji=False, cakaj_ms=preostalo)
            self._zabelezi_poslano_zahtevo(cas)
            return Odlocitev(poslji=True, cakaj_ms=0)

    def uspeh(self, zdaj_ms: int) -> None:
        _preveri_cas(zdaj_ms)
        with self._zaklep:
            cas = self._uskladi_cas(zdaj_ms)
            self._trenutni_razmik_ms = ZACETNI_RAZMIK_MS
            self._stevec_zaporednih = 0
            self._zadnji_uspeh_ms = cas

    def ponastavi(self) -> None:
        with self._zaklep:
            self._zadnja_zahteva_ms = None
            self._zadnji_uspeh_ms = None
            self._zadnji_znani_cas_ms = None
            self._trenutni_razmik_ms = ZACETNI_RAZMIK_MS
            self._stevec_zaporednih = 0

    def _uskladi_cas(self, zdaj_ms: int) -> int:
        prejsnji = self._zadnji_znani_cas_ms
        usklajen = prejsnji if (prejsnji is not None and zdaj_ms < prejsnji) else zdaj_ms
        self._zadnji_znani_cas_ms = usklajen
        return usklajen

    def _ponastavi_po_mirovanju(self, cas: int) -> None:
        zadnja = self._zadnja_zahteva_ms
        if zadnja is None:
            return
        if _nasicena_razlika(cas, zadnja) > MIROVANJE_ZA_PONASTAVITEV_MS:
            self._trenutni_razmik_ms = ZACETNI_RAZMIK_MS
            self._stevec_zaporednih = 0

    def _zabelezi_poslano_zahtevo(self, cas: int) -> None:
        if self._stevec_zaporednih > 0:
            self._trenutni_razmik_ms = max(
                NAJMANJ_RAZMIK_MS, min(NAJVEC_RAZMIK_MS, self._trenutni_razmik_ms * 2)
            )
        self._stevec_zaporednih += 1
        self._zadnja_zahteva_ms = cas


class DrseceOkno:
    """Drsece okno: najvec `najvec` dogodkov v zadnjih `okno_ms` milisekundah.

    Dogodek ob casu t je v oknu ob casu zdaj, ce velja zdaj - t < okno_ms (meja vkljucna:
    tocno okno_ms po dogodku je nov dogodek ze dovoljen). Cas nazaj se steje kot zadnji
    znani cas. Pomnilnik je omejen na `najvec` zapisov.
    """

    def __init__(self, najvec: int = OKNO_NAJVEC_IDR, okno_ms: int = OKNO_MS) -> None:
        if isinstance(najvec, bool) or not isinstance(najvec, int) or najvec < 1:
            raise ValueError("najvec mora biti int >= 1")
        if isinstance(okno_ms, bool) or not isinstance(okno_ms, int) or okno_ms < 1:
            raise ValueError("okno_ms mora biti int >= 1")
        self._zaklep = threading.Lock()
        self._najvec = najvec
        self._okno_ms = okno_ms
        self._casi: Deque[int] = deque()
        self._zadnji_znani_cas_ms: Optional[int] = None

    def _uskladi_cas(self, zdaj_ms: int) -> int:
        prejsnji = self._zadnji_znani_cas_ms
        usklajen = prejsnji if (prejsnji is not None and zdaj_ms < prejsnji) else zdaj_ms
        self._zadnji_znani_cas_ms = usklajen
        return usklajen

    def _pocisti(self, cas: int) -> None:
        while self._casi and _nasicena_razlika(cas, self._casi[0]) >= self._okno_ms:
            self._casi.popleft()

    def preveri(self, zdaj_ms: int) -> Odlocitev:
        """Pove, ali bi bil dogodek zdaj dovoljen, brez zapisa dogodka."""
        _preveri_cas(zdaj_ms)
        with self._zaklep:
            cas = self._uskladi_cas(zdaj_ms)
            return self._preveri_brez_zaklepa(cas)

    def _preveri_brez_zaklepa(self, cas: int) -> Odlocitev:
        self._pocisti(cas)
        if len(self._casi) < self._najvec:
            return Odlocitev(poslji=True, cakaj_ms=0)
        najstarejsi = self._casi[0]
        return Odlocitev(
            poslji=False,
            cakaj_ms=_preostali_cas(cas, najstarejsi, self._okno_ms),
        )

    def poskusi(self, zdaj_ms: int) -> Odlocitev:
        """Ce je dogodek dovoljen, ga zapise in vrne poslji=True, sicer poslji=False s cakaj_ms."""
        _preveri_cas(zdaj_ms)
        with self._zaklep:
            cas = self._uskladi_cas(zdaj_ms)
            odlocitev = self._preveri_brez_zaklepa(cas)
            if odlocitev.poslji:
                self._casi.append(cas)
            return odlocitev

    def ponastavi(self) -> None:
        with self._zaklep:
            self._casi.clear()
            self._zadnji_znani_cas_ms = None


class ZascitaKodirnika:
    """Vrata na racunalniku pred kodirnikom: zahteva od odjemalca sprozi IDR le, ce jo
    dovolita ista pravila kot na TV (Presojevalec) IN drsece okno (1 IDR v 2 s).

    Okno se preveri prvo in brez zapisa; Presojevalec se poklice samo, ce okno dovoli,
    zato zavrnjena zahteva ne spremeni stanja presojevalca (stevca in razmika).
    Ob poslji=True je klicatelj dolzan takoj ustvariti IDR. ROCNO je prav tako omejen z oknom.
    """

    def __init__(self, najvec: int = OKNO_NAJVEC_IDR, okno_ms: int = OKNO_MS) -> None:
        self._zaklep = threading.Lock()
        self.presojevalec = Presojevalec()
        self.okno = DrseceOkno(najvec=najvec, okno_ms=okno_ms)

    def zahteva(self, razlog: Razlog, zdaj_ms: int) -> Odlocitev:
        if not isinstance(razlog, Razlog):
            raise TypeError("razlog mora biti Razlog")
        _preveri_cas(zdaj_ms)
        with self._zaklep:
            izid_okna = self.okno.preveri(zdaj_ms)
            if not izid_okna.poslji:
                return izid_okna
            izid = self.presojevalec.presodi(razlog, zdaj_ms)
            if izid.poslji:
                self.okno.poskusi(zdaj_ms)
            return izid

    def uspeh(self, zdaj_ms: int) -> None:
        with self._zaklep:
            self.presojevalec.uspeh(zdaj_ms)

    def ponastavi(self) -> None:
        with self._zaklep:
            self.presojevalec.ponastavi()
            self.okno.ponastavi()
