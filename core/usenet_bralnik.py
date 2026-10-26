"""Bralnik za lasten pogon Usenet, korak 2: bajti filma z nakljucnim dostopom iz NZB (lastnik 26. 10. 2026).

Prototip 25. 10. 2026 (NzbDAV): za 60 s ogleda (~50 MiB s predpomnilnikom predvajalnika) je slo z Useneta 167-344 MiB,
tudi po zaprtju povezave - za TV in mobilne podatke nesprejemljivo. Tu:
- Okno vnaprej je OMEJENO in raste z zaporednim branjem: po odprtju ali skoku samo zacetno okno (predvajalnik pogosto
  prebere le glavo, indeks na koncu datoteke ali nekaj KiB po skoku), nato dvakratnik zaporedno prebranega do meje
  profila (okno_vnaprej; skupni primeri tok_okno). Ob skoku se cakajoca branja vnaprej zunaj novega okna zavrzejo.
- Segmenti hkrati prek bazena (usenet_nntp.Bazen) z lastnimi nitmi: zahtevano branje ima prednost pred branjem vnaprej.
- LRU v RAM z mejo po profilu naprave; zapri() ne caka na zahteve v teku (na Windows Bazen.zapri() zahteve v teku ne
  prekine - izmerjeno 26. 10. 2026, preizkusa test_zapiranje_prekine_* padeta) - niti so demonske in odvrzejo izid.
- message-id in imena niso v repr, izjemi ali dnevniku.
"""

from __future__ import annotations

import heapq
from bisect import bisect_right
import itertools
import logging
import os
import threading
from collections import OrderedDict
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from . import usenet_rar as R
from .usenet_nntp import NI_CLANKA, NapakaNntp
from .usenet_nzb import Datoteka, Nzb
from .usenet_tok import (IZVEN, LUKNJA, NAJVEC_ISKANJ, NESKLADNO, POKVARJEN, ZAPRTO, NapakaToka, Preslikava)
from .usenet_yenc import NapakaYenc, dekodiraj

_log = logging.getLogger("safeer.usenet")

MiB = 1024 * 1024


@dataclass(frozen=True)
class Profil:
    okno_bajtov: int  # najvecje okno vnaprej
    zacetno_okno: int  # okno po odprtju ali skoku
    lru_bajtov: int  # dekodirani segmenti v RAM
    vzporedno: int  # hkratnih branj segmentov


#: Po profilu naprave (lastnik: 8-16 MiB vnaprej; TV ima malo RAM - Philips: heapgrowthlimit 192 MB).
PROFILI = {
    "tv": Profil(8 * MiB, 1 * MiB, 32 * MiB, 4),
    "telefon": Profil(8 * MiB, 1 * MiB, 48 * MiB, 6),
    "namizje": Profil(16 * MiB, 1 * MiB, 96 * MiB, 8),
}


def okno_vnaprej(zaporedno_prebrano: int, zacetno: int, najvec: int) -> int:
    """Okno vnaprej (skupni primeri tok_okno): dvakratnik zaporedno prebranega od zadnjega skoka, najmanj zacetno,
    najvec meja profila. Predvajalnik, ki bere zaporedno, ima okno pred sabo; skok ga vrne na zacetno."""
    return max(int(zacetno), min(int(najvec), 2 * max(0, int(zaporedno_prebrano))))


@dataclass(frozen=True)
class KosVira:
    datoteka: int  # indeks v Vir.preslikave
    odmik: int  # odmik v datoteki NZB (zvezku)
    dolzina: int


class Vir:
    """Film kot zaporedje kosov datotek iz NZB (gola datoteka: en kos; RAR store: kos v vsakem zvezku)."""

    def __init__(self, preslikave: List[Preslikava], kosi: List[KosVira], ime: Optional[str] = None):
        self.preslikave = list(preslikave)
        self.kosi = list(kosi)
        self.ime = ime
        self._zacetki = list(itertools.accumulate([0] + [k.dolzina for k in self.kosi]))
        self.velikost = self._zacetki[-1]
        for k in self.kosi:
            p = self.preslikave[k.datoteka]
            if k.dolzina <= 0 or k.odmik < 0 or k.odmik + k.dolzina > p.velikost:
                raise NapakaToka(NESKLADNO)

    def __repr__(self) -> str:
        return "Vir(%d B, %d kosov)" % (self.velikost, len(self.kosi))

    def kje(self, odmik: int) -> Tuple[int, int]:
        """(datoteka, odmik v datoteki) za odmik v filmu."""
        if not 0 <= odmik < self.velikost:
            raise NapakaToka(IZVEN)
        i = self._kos_za(odmik)
        k = self.kosi[i]
        return k.datoteka, k.odmik + (odmik - self._zacetki[i])

    def razponi(self, odmik: int, dolzina: int) -> List[Tuple[int, int, int]]:
        """[(datoteka, odmik v datoteki, dolzina)] za [odmik, odmik + dolzina) v filmu."""
        izid, konec = [], min(self.velikost, odmik + dolzina)
        while odmik < konec:
            d, o = self.kje(odmik)
            i = self._kos_za(odmik)
            n = min(konec, self._zacetki[i + 1]) - odmik
            izid.append((d, o, n))
            odmik += n
        return izid

    def _kos_za(self, odmik: int) -> int:
        return bisect_right(self._zacetki, odmik, 0, len(self.kosi)) - 1


class Bralnik:
    """Branje filma z omejenim oknom vnaprej. Varno za vec niti. [telo] = Bazen.telo (message-id -> telo clanka)."""

    def __init__(self, telo: Callable[[str], bytes], vir: Vir, profil: Profil = PROFILI["namizje"]):
        self._telo = telo
        self.vir = vir
        self.profil = profil
        # LRU mora drzati vsaj okno in segment ob njem, sicer bi branje vnaprej izrinilo samo sebe.
        self._lru_meja = max(profil.lru_bajtov, 2 * profil.okno_bajtov + 8 * MiB)
        self._lru: "OrderedDict[tuple, bytes]" = OrderedDict()
        self._lru_bajtov = 0
        self._v_teku: Dict[tuple, Future] = {}
        self._vrsta: list = []  # (prednost, zaporedje, kljuc)
        self._cakajo: Dict[tuple, Future] = {}
        self._zap = itertools.count()
        self._pogoj = threading.Condition(threading.Lock())
        self._zaprt = False
        self._konec = 0  # konec zadnjega branja (za zaporednost)
        self._zaporedno = 0
        self.z_omrezja = 0  # bajti teles clankov z Useneta
        self.segmentov = 0
        self.postrezeno = 0
        self._niti = [threading.Thread(target=self._delavec, name="safeer-usenet-bralnik", daemon=True)
                      for _ in range(max(1, profil.vzporedno))]
        for t in self._niti:
            t.start()

    def __repr__(self) -> str:
        return "Bralnik(%r, z omrezja %d B)" % (self.vir, self.z_omrezja)

    # -------------------------------------------------------------- niti
    def _delavec(self) -> None:
        while True:
            with self._pogoj:
                while not self._vrsta and not self._zaprt:
                    self._pogoj.wait()
                if self._zaprt:
                    return
                _p, _z, kljuc = heapq.heappop(self._vrsta)
                f = self._cakajo.pop(kljuc, None)
                if f is None:
                    continue  # zavrzeno ob skoku
            try:
                podatki = self._prenesi(kljuc)
            except BaseException as e:  # noqa: BLE001 - izid gre bralcu
                with self._pogoj:
                    self._v_teku.pop(kljuc, None)
                f.set_exception(e)
                continue
            with self._pogoj:
                self._v_teku.pop(kljuc, None)
                if not self._zaprt:
                    self._v_lru(kljuc, podatki)
            f.set_result(podatki)

    def _prenesi(self, kljuc: tuple) -> bytes:
        d, st = kljuc
        p = self.vir.preslikave[d]
        seg = p.segment(st)
        try:
            surovo = self._telo(seg.id)
        except NapakaNntp as e:
            raise NapakaToka(LUKNJA if e.izid == NI_CLANKA else e.izid) from None
        with self._pogoj:
            self.z_omrezja += len(surovo)
            self.segmentov += 1
        try:
            del_ = dekodiraj(surovo)
        except NapakaYenc:
            raise NapakaToka(POKVARJEN) from None
        p.vnesi(st, del_)
        return del_.podatki

    def _v_lru(self, kljuc: tuple, podatki: bytes) -> None:
        if kljuc in self._lru:
            self._lru.move_to_end(kljuc)
            return
        self._lru[kljuc] = podatki
        self._lru_bajtov += len(podatki)
        while self._lru_bajtov > self._lru_meja and len(self._lru) > 1:
            _k, staro = self._lru.popitem(last=False)
            self._lru_bajtov -= len(staro)

    def _zahtevaj(self, kljuc: tuple, prednost: int) -> Optional[Future]:
        """Future segmenta (None = ze v LRU). Pod self._pogoj."""
        if kljuc in self._lru:
            return None
        f = self._v_teku.get(kljuc)
        if f is not None:
            if prednost == 0 and kljuc in self._cakajo:
                heapq.heappush(self._vrsta, (0, next(self._zap), kljuc))  # vnaprej -> zahtevano: naprej v vrsti
                self._pogoj.notify()
            return f
        f = Future()
        self._v_teku[kljuc] = f
        self._cakajo[kljuc] = f
        heapq.heappush(self._vrsta, (prednost, next(self._zap), kljuc))
        self._pogoj.notify()
        return f

    def _segment(self, kljuc: tuple) -> bytes:
        while True:
            with self._pogoj:
                if self._zaprt:
                    raise NapakaToka(ZAPRTO)
                if kljuc in self._lru:
                    self._lru.move_to_end(kljuc)
                    return self._lru[kljuc]
                f = self._zahtevaj(kljuc, 0)
            try:
                return f.result()
            except CancelledError:
                continue  # branje vnaprej, na katero smo cakali, je skok iz druge povezave zavrgel: znova zahtevano

    # -------------------------------------------------------------- branje
    def _beri_datoteko(self, d: int, odmik: int, n: int) -> bytes:
        """Do [n] bajtov iz datoteke [d] od [odmik] (iz enega segmenta)."""
        p = self.vir.preslikave[d]
        for _ in range(NAJVEC_ISKANJ):
            u = p.poisci(odmik)
            podatki = self._segment((d, u.stevilka))
            u2 = p.poisci(odmik)  # segment je zdaj sidro: natancen odmik ali nov ugib
            if u2.natancno and u2.stevilka == u.stevilka:
                return podatki[u2.odmik:u2.odmik + n]
        raise NapakaToka(NESKLADNO)

    def _vnaprej(self, od: int) -> None:
        okno = okno_vnaprej(self._zaporedno, self.profil.zacetno_okno, self.profil.okno_bajtov)
        kljuci = []
        for d, o, n in self.vir.razponi(od, okno):
            kljuci += [(d, st) for st in self.vir.preslikave[d].segmenti_okna(o, n)]
        with self._pogoj:
            zelja = set(kljuci)
            for k in [k for k in self._cakajo if k not in zelja]:  # skok: cakajoca branja zunaj okna proc
                f = self._cakajo.pop(k)
                self._v_teku.pop(k, None)
                f.cancel()
            for i, k in enumerate(kljuci):
                self._zahtevaj(k, 1 + i)

    def beri(self, odmik: int, n: int) -> bytes:
        """Do [n] bajtov filma od [odmik]; b"" na koncu. Napaka: NapakaToka (luknja, pokvarjen, zaprto ...)."""
        if odmik >= self.vir.velikost or n <= 0:
            return b""
        if odmik < 0:
            raise NapakaToka(IZVEN)
        with self._pogoj:
            if self._zaprt:
                raise NapakaToka(ZAPRTO)
            if abs(odmik - self._konec) <= self.profil.zacetno_okno:
                self._zaporedno += max(0, odmik + n - max(odmik, self._konec))
            else:
                self._zaporedno = 0  # skok
        d, o = self.vir.kje(odmik)
        razpon = self.vir.razponi(odmik, n)[0]
        podatki = self._beri_datoteko(d, o, razpon[2])
        konec = odmik + len(podatki)
        with self._pogoj:
            self._konec = konec
            self.postrezeno += len(podatki)
        self._vnaprej(konec)
        return podatki

    def zapri(self) -> None:
        """Konec predvajanja: vrsta proc, LRU sproscen, niti koncajo; zahteve v teku se ne caka."""
        with self._pogoj:
            self._zaprt = True
            for f in self._cakajo.values():
                f.cancel()
            self._cakajo.clear()
            self._vrsta.clear()
            self._lru.clear()
            self._lru_bajtov = 0
            self._pogoj.notify_all()

    @property
    def zaprt(self) -> bool:
        return self._zaprt


# ------------------------------------------------------------------ priprava iz NZB

VIDEO = (".mkv", ".mp4", ".m4v", ".avi", ".ts", ".m2ts", ".webm", ".mov", ".wmv", ".mpg", ".mpeg")
NI_VSEBINA = (".par2", ".nfo", ".sfv", ".nzb", ".jpg", ".jpeg", ".png", ".txt", ".srr", ".url", ".md5")
NI_PODPRTO = "ni_podprto"  # 7z, zip, gnezden arhiv ... (F2)
NI_FILMA = "ni_filma"


def _je_vzorec(ime: str) -> bool:
    return "sample" in ime.lower() or "vzorec" in ime.lower()


def izberi_datoteke(nzb: Nzb) -> Tuple[str, List[int]]:
    """('rar' | 'video', indeksi datotek v vrstnem redu). Napaka: NapakaToka(NI_FILMA / NI_PODPRTO)."""
    imena = [d.ime or "" for d in nzb.datoteke]
    rar = [i for i, ime in enumerate(imena) if R.vrstni_red_zvezkov([ime]) is not None
           or ime.lower().endswith(".rar") or os.path.splitext(ime)[1].lower()[:2] == ".r"
           and os.path.splitext(ime)[1][2:].isdigit()]
    rar = [i for i in rar if not _je_vzorec(imena[i])]
    if rar:
        red = R.vrstni_red_zvezkov([imena[i] for i in rar])
        if red is None:
            raise NapakaToka(NI_PODPRTO)  # vec arhivov ali nepopolna vrsta - par2/deobfuskacija je F2
        return "rar", [rar[i] for i in red]
    video = [i for i, ime in enumerate(imena) if ime.lower().endswith(VIDEO) and not _je_vzorec(ime)]
    if video:
        return "video", [max(video, key=lambda i: nzb.datoteke[i].bajtov_nzb)]
    if any(ime.lower().endswith((".7z", ".zip", ".001")) for ime in imena):
        raise NapakaToka(NI_PODPRTO)
    kandidati = [i for i, ime in enumerate(imena) if not ime.lower().endswith(NI_VSEBINA)]
    if not kandidati:
        raise NapakaToka(NI_FILMA)
    return "video", [max(kandidati, key=lambda i: nzb.datoteke[i].bajtov_nzb)]  # zakrito ime: najvecja datoteka


def _prvi_segment(telo: Callable[[str], bytes], d: Datoteka) -> Tuple[Preslikava, bytes, int]:
    s = d.segmenti[0]
    try:
        surovo = telo(s.id)
    except NapakaNntp as e:
        raise NapakaToka(LUKNJA if e.izid == NI_CLANKA else e.izid) from None
    try:
        del_ = dekodiraj(surovo)
    except NapakaYenc:
        raise NapakaToka(POKVARJEN) from None
    return Preslikava(d, del_, s.stevilka), del_.podatki if del_.odmik == 0 else b"", len(surovo)


def pripravi(nzb: Nzb, telo: Callable[[str], bytes], vzporedno: int = 8) -> Tuple[Vir, int]:
    """NZB -> (Vir filma, bajti z omrezja za pripravo). Prvi segment vsake izbrane datoteke (vzporedno) da preslikavo
    in glave RAR; stisnjen ali sifriran RAR = NapakaRar PRED ponudbo. Glave, ki segajo cez prvi segment, prebere
    bralnik tega zvezka (z zacetnim oknom)."""
    vrsta, izbrane = izberi_datoteke(nzb)
    with ThreadPoolExecutor(max_workers=max(1, min(vzporedno, len(izbrane)))) as ex:
        prvi = list(ex.map(lambda i: _prvi_segment(telo, nzb.datoteke[i]), izbrane))
    bajtov = sum(x[2] for x in prvi)
    preslikave = [x[0] for x in prvi]
    if vrsta == "video":
        p = preslikave[0]
        return Vir(preslikave, [KosVira(0, 0, p.velikost)], nzb.datoteke[izbrane[0]].ime), bajtov
    zvezki = []
    for n, (p, zacetek, _b) in enumerate(prvi):
        if n == 0:
            izid = R.preveri(zacetek, p.velikost)
            if izid not in (R.OK, R.NEPOPOLNO):
                raise R.NapakaRar(izid)
        z = R.razcleni_zvezek(zacetek, p.velikost) if zacetek else None
        if z is None or z.nepopolno and not z.vnosi:
            # glave cez prvi segment (dolg komentar, veliko datotek): beri zvezek prek bralnika
            b = Bralnik(telo, Vir([p], [KosVira(0, 0, p.velikost)]), Profil(1 * MiB, 1 * MiB, 8 * MiB, 2))
            try:
                z = R.razcleni_zvezek(lambda o, k: _beri_vse(b, o, k), p.velikost)
            finally:
                bajtov += b.z_omrezja
                b.zapri()
        zvezki.append(z)
    ime, _velikost, kosi = R.sestavi(zvezki)
    return Vir(preslikave, [KosVira(k.zvezek, k.odmik, k.dolzina) for k in kosi], ime), bajtov


def _beri_vse(b: Bralnik, odmik: int, n: int) -> bytes:
    deli = []
    while n > 0:
        kos = b.beri(odmik, n)
        if not kos:
            break
        deli.append(kos)
        odmik += len(kos)
        n -= len(kos)
    return b"".join(deli)


def preveri_izdajo(nzb: Nzb, telo: Callable[[str], bytes]) -> str:
    """Pred ponudbo: ali izdajo lahko predvajamo - EN clanek (prvi segment prvega zvezka ali datoteke). OK ali izid
    (stisnjen, sifriran, sifrirane_glave, poskodovan, ni_podprto, ni_filma, luknja ...). STAT vzorca segmentov je
    korak 3 (zivi preizkus s ponudnikom)."""
    try:
        vrsta, izbrane = izberi_datoteke(nzb)
        p, zacetek, _b = _prvi_segment(telo, nzb.datoteke[izbrane[0]])
    except NapakaToka as e:
        return e.izid
    if vrsta == "video":
        # Zakrito ime (brez koncnice) je lahko RAR: tudi tega zavrnemo, ce ni store.
        return R.preveri(zacetek, p.velikost) if zacetek.startswith((R.PODPIS4, R.PODPIS5[:7])) else R.OK
    izid = R.preveri(zacetek, p.velikost)
    return R.OK if izid == R.NEPOPOLNO else izid  # glave cez prvi segment: odloci pripravi()
