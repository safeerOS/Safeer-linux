"""Preslikava odmikov za lasten pogon Usenet, korak 2 (lastnik 26. 10. 2026: »dokoncajmo Usenet za nase naprave«).

Datoteka iz NZB je zaporedje segmentov (clankov); vsak clanek je del yEnc z '=ypart begin= end=' (od 1, vkljucno) in
'=ybegin size=' (velikost CELE datoteke). NZB pove samo velikost clankov (kodiranih, z glavami) - ne odmikov. Zato:
1. Prvi segment datoteke (z najnizjo stevilko) da velikost datoteke in velikost dela (end - begin + 1).
2. Kodirniki (Nyuu, ngPost, newsmangler ...) delijo datoteko na enake dele, zadnji je krajsi: odmik o lezi v segmentu
   o // del + 1, na odmiku o % del. To je samo UGIB: vsak prebran segment pove svoj pravi razpon (vnesi), ugib pa
   se popravi med znanimi razponi (sidri) z enakomerno razdelitvijo vmesnih segmentov - neenakomerna objava (npr.
   dve objavi zdruzeni v en NZB) se tako najde v nekaj branjih, namesto da bi brali napacne bajte.
3. Luknje: segment, ki ga v NZB ni (stevilka manjka med 1 in celoto) - branje odmika v njem da LUKNJA (pri pretakanju
   ni popravila par2: preklop na drugo izdajo je odlocitev klicatelja). Clanek, ki ga ponudnik nima (430), je luknja,
   ki jo odkrije sele branje (bralnik).

Pravila so skupna z Android-tv (Kotlin): tests/skupni-primeri/usenet-pogon.json v4 (tok_odmik, tok_segmenti).
Brez omrezja; message-id ni v repr ali izjemi.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional

from .usenet_nzb import Datoteka, Segment
from .usenet_yenc import DelYenc

OK = "ok"
IZVEN = "izven"  # odmik zunaj datoteke
LUKNJA = "luknja"  # segment manjka (v NZB ali pri ponudniku)
NESKLADNO = "neskladno"  # razponi segmentov si nasprotujejo (pokvarjen ali zlonameren NZB/clanek)
POKVARJEN = "pokvarjen"  # clanek ni veljaven yEnc ali CRC se ne ujema (bralnik)
ZAPRTO = "zaprto"  # bralnik je zaprt

#: Najvec branj, s katerimi bralnik isce segment za odmik (enakomerna objava: 1; dve zdruzeni objavi: nekaj).
NAJVEC_ISKANJ = 24


class NapakaToka(ValueError):
    """Izid brez message-id in brez imena datoteke v sporocilu."""

    def __init__(self, izid: str):
        super().__init__("usenet tok: " + izid)
        self.izid = izid


@dataclass(frozen=True)
class Ugib:
    stevilka: int  # segment (od 1)
    odmik: int  # odmik v segmentu (dekodiranem delu)
    natancno: bool  # razpon segmenta je znan (prebran), ne ugibamo


def _preveri_znane(velikost: int, celota: int, znani: dict) -> list:
    """Znani razponi {stevilka: (odmik, dolzina)} po stevilki; nasprotje = NESKLADNO."""
    vrsta = sorted(znani.items())
    prejsnji_st, prejsnji_konec = 0, 0
    for st, (z, d) in vrsta:
        if not 1 <= st <= celota or d < 1 or z < 0 or z + d > velikost:
            raise NapakaToka(NESKLADNO)
        # vsak vmesni segment ima vsaj en bajt; sosednja segmenta se stikata
        if z - prejsnji_konec < st - prejsnji_st - 1 or (st == prejsnji_st + 1 and z != prejsnji_konec):
            raise NapakaToka(NESKLADNO)
        prejsnji_st, prejsnji_konec = st, z + d
    if velikost - prejsnji_konec < celota - prejsnji_st or (prejsnji_st == celota and prejsnji_konec != velikost):
        raise NapakaToka(NESKLADNO)
    return vrsta


def _sidri(vrsta: list, odmik: int, velikost: int, celota: int) -> tuple:
    """(levo_st, levo_konec, desno_st, desno_zacetek): najblizja znana razpona okoli odmika (navidezna 0 in celota+1)."""
    lst, lkon, dst, dzac = 0, 0, celota + 1, velikost
    for st, (z, d) in vrsta:
        if z + d <= odmik:
            lst, lkon = st, z + d
        elif z > odmik:
            dst, dzac = st, z
            break
    return lst, lkon, dst, dzac


def _enakomerno(lst: int, lkon: int, dst: int, dzac: int, del_bajtov: Optional[int], celota: int) -> bool:
    """Ali je vrzel med sidroma skladna z enakimi deli [del_bajtov] (zadnji del datoteke je lahko krajsi)."""
    if not del_bajtov or del_bajtov <= 0 or lkon != lst * del_bajtov:
        return False
    if dst == celota + 1:
        return (celota - 1) * del_bajtov < dzac <= celota * del_bajtov
    return dzac == (dst - 1) * del_bajtov


def poisci(velikost: int, celota: int, del_bajtov: Optional[int], znani: dict, odmik: int) -> Ugib:
    """Segment za odmik (skupni primeri tok_odmik). [del_bajtov] = velikost dela iz prvega segmenta (None = ni znana),
    [znani] = {stevilka: (odmik, dolzina)} prebranih segmentov. Ugib: odmik // del + 1, ce je vrzel med sidroma
    skladna z enakimi deli (_enakomerno), sicer enakomerna razdelitev vrzeli na vmesne segmente. Napaka: NapakaToka(IZVEN / NESKLADNO)."""
    if not 0 <= odmik < velikost:
        raise NapakaToka(IZVEN)
    if celota < 1 or velikost < celota:
        raise NapakaToka(NESKLADNO)
    vrsta = _preveri_znane(velikost, celota, znani)
    for st, (z, d) in vrsta:
        if z <= odmik < z + d:
            return Ugib(st, odmik - z, True)
    lst, lkon, dst, dzac = _sidri(vrsta, odmik, velikost, celota)
    if _enakomerno(lst, lkon, dst, dzac, del_bajtov, celota):
        st = odmik // del_bajtov + 1
        return Ugib(st, odmik - (st - 1) * del_bajtov, False)
    vmes = dst - lst - 1  # >= 1 (preverjeno v _preveri_znane)
    na = (dzac - lkon) / vmes
    st = min(dst - 1, max(lst + 1, lst + 1 + int((odmik - lkon) // na)))
    return Ugib(st, odmik - (lkon + int((st - lst - 1) * na)), False)


def razpon(velikost: int, celota: int, del_bajtov: Optional[int], znani: dict, stevilka: int) -> tuple:
    """(odmik, dolzina, natancno) segmenta - znan ali ocenjen enako kot v poisci (za okno vnaprej)."""
    if not 1 <= stevilka <= celota:
        raise NapakaToka(IZVEN)
    vrsta = _preveri_znane(velikost, celota, znani)
    if stevilka in znani:
        z, d = znani[stevilka]
        return z, d, True
    lst, lkon, dst, dzac = 0, 0, celota + 1, velikost
    for st, (z, d) in vrsta:
        if st < stevilka:
            lst, lkon = st, z + d
        else:
            dst, dzac = st, z
            break
    if _enakomerno(lst, lkon, dst, dzac, del_bajtov, celota):
        z = (stevilka - 1) * del_bajtov
        return z, min(del_bajtov, dzac - z), False
    na = (dzac - lkon) / (dst - lst - 1)
    z = lkon + int((stevilka - lst - 1) * na)
    k = lkon + int((stevilka - lst) * na) if stevilka + 1 < dst else dzac
    return z, max(1, k - z), False


def segmenti_okna(velikost: int, celota: int, del_bajtov: Optional[int], znani: dict, odmik: int,
                  dolzina: int) -> list:
    """Stevilke segmentov, ki (po znanem ali ocenjenem razponu) pokrivajo [odmik, odmik + dolzina) - skupni primeri
    tok_segmenti. Konec datoteke okno prireze."""
    if dolzina <= 0 or not 0 <= odmik < velikost:
        return []
    konec = min(velikost, odmik + dolzina)
    st = poisci(velikost, celota, del_bajtov, znani, odmik).stevilka
    izid = []
    while st <= celota:
        z, d, _ = razpon(velikost, celota, del_bajtov, znani, st)
        if z >= konec:
            break
        izid.append(st)
        st += 1
    return izid


class Preslikava:
    """Odmiki ene datoteke iz NZB. Varna za vec niti (bralnik vnasa prebrane segmente vzporedno)."""

    def __init__(self, datoteka: Datoteka, prvi: DelYenc, stevilka_prvega: Optional[int] = None):
        """[prvi] = dekodiran segment z najnizjo stevilko v NZB (ali [stevilka_prvega])."""
        st = stevilka_prvega if stevilka_prvega is not None else datoteka.segmenti[0].stevilka
        self._segmenti = {s.stevilka: s for s in datoteka.segmenti}
        if st not in self._segmenti:
            raise NapakaToka(NESKLADNO)
        self.ime = datoteka.ime
        self.velikost = prvi.velikost
        celota = len(datoteka.segmenti) + datoteka.manjka
        if prvi.skupaj is not None:
            celota = max(celota, prvi.skupaj)  # yEnc total: segmenti na koncu, ki jih NZB nima
        self.celota = celota
        if self.velikost < celota:
            raise NapakaToka(NESKLADNO)
        self.manjkajo = tuple(n for n in range(1, celota + 1) if n not in self._segmenti)
        # del iz segmenta, ki ni zadnji (zadnji je krajsi); enodelna datoteka: del = velikost
        self.del_bajtov: Optional[int] = len(prvi.podatki) if st < celota or celota == 1 else None
        self._znani: dict = {}
        self._zaklep = threading.Lock()
        self.vnesi(st, prvi)

    def __repr__(self) -> str:
        return "Preslikava(%d B, %d segmentov, %d manjka)" % (self.velikost, self.celota, len(self.manjkajo))

    @property
    def ima_luknje(self) -> bool:
        return bool(self.manjkajo)

    def segment(self, stevilka: int) -> Segment:
        s = self._segmenti.get(stevilka)
        if s is None:
            raise NapakaToka(LUKNJA)
        return s

    def znani(self) -> dict:
        with self._zaklep:
            return dict(self._znani)

    def vnesi(self, stevilka: int, d: DelYenc) -> None:
        """Prebran segment: njegov pravi razpon postane sidro. Druga velikost datoteke ali razpon, ki nasprotuje
        znanim, je NESKLADNO (segment druge datoteke ali pokvarjen NZB)."""
        if d.velikost != self.velikost or not d.podatki:
            raise NapakaToka(NESKLADNO)
        with self._zaklep:
            znani = dict(self._znani)
            znani[stevilka] = (d.odmik, len(d.podatki))
            _preveri_znane(self.velikost, self.celota, znani)
            self._znani = znani

    def poisci(self, odmik: int) -> Ugib:
        """Segment za odmik; manjkajoc segment = NapakaToka(LUKNJA)."""
        u = poisci(self.velikost, self.celota, self.del_bajtov, self.znani(), odmik)
        if u.stevilka not in self._segmenti:
            raise NapakaToka(LUKNJA)
        return u

    def razpon(self, stevilka: int) -> tuple:
        return razpon(self.velikost, self.celota, self.del_bajtov, self.znani(), stevilka)

    def segmenti_okna(self, odmik: int, dolzina: int) -> list:
        """Segmenti okna brez manjkajocih (teh ni smiselno brati vnaprej - branje jih javi kot luknjo)."""
        return [n for n in segmenti_okna(self.velikost, self.celota, self.del_bajtov, self.znani(), odmik, dolzina)
                if n in self._segmenti]
