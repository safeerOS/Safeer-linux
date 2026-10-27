"""Naloga 76: pregled 71 L1 (meja prometa priprave pred ponudbo) in pregled 72 N1 (film iz celega seznama glav).

Brez omrezja: zvezki RAR5 in clanki yEnc se zgradijo v pomnilniku, telo() steje klice. Brez popravka padejo vsi
preizkusi razen zadnjega (varovalo, da popravek ne zavrne obicajne izdaje).
Zagon: pytest tests/test_usenet_naloga76.py (korenska mapa s core/ je NALOGA76_KORIJEN ali mapa nad tests/).
"""
import os
import struct
import sys
import threading
import zlib

import pytest

sys.path.insert(0, os.environ.get("NALOGA76_KORIJEN", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core import usenet_bralnik as B  # noqa: E402
from core import usenet_rar as R  # noqa: E402
from core.usenet_nzb import Datoteka, Nzb, Segment  # noqa: E402
from core.usenet_tok import PREVEC, NapakaToka  # noqa: E402

DEL = 16384  # bajtov v delu yEnc
PODPIS5 = b"Rar!\x1a\x07\x01\x00"


# ------------------------------------------------------------------ gradnja RAR5 in yEnc

def vint(v: int) -> bytes:
    out = bytearray()
    while True:
        b, v = v & 0x7F, v >> 7
        out.append(b | (0x80 if v else 0))
        if not v:
            return bytes(out)


def blok(vrsta: int, zast: int, polja: bytes, pod=None, dod: bytes = b"") -> bytes:
    if dod:
        zast |= 0x1
    if pod is not None:
        zast |= 0x2
    h = vint(vrsta) + vint(zast) + (vint(len(dod)) if dod else b"") + (vint(pod) if pod is not None else b"") + polja + dod
    s = vint(len(h)) + h
    return struct.pack("<I", zlib.crc32(s)) + s


def zvezek(n: int, datoteke: list) -> bytes:
    """datoteke: (ime, podatki v tem zvezku, cela velikost, pred, po, metoda, sifriran)."""
    out = bytearray(PODPIS5)
    out += blok(1, 0, vint(0x3) + vint(n) if n else vint(0x1))
    for ime, pod, vel, pred, po, metoda, sif in datoteke:
        ib = ime.encode()
        polja = vint(0) + vint(vel) + vint(0x20) + vint(metoda << 7) + vint(0) + vint(len(ib)) + ib
        out += blok(2, (0x8 if pred else 0) | (0x10 if po else 0), polja, len(pod), b"\x01\x01" if sif else b"")
        out += pod
    out += blok(5, 0, vint(0))
    return bytes(out)


def podatki(n: int, seme: int) -> bytes:
    return bytes((i * 31 + seme * 7 + (i >> 8)) & 0xFF for i in range(n))


def yenc(ime: str, vse: bytes, k: int, skupaj: int) -> bytes:
    z, kon = (k - 1) * DEL, min(k * DEL, len(vse))
    kos = vse[z:kon]
    enc = bytearray()
    for i, c in enumerate(kos):
        e = (c + 42) & 0xFF
        if e in (0, 10, 13, 61):
            enc += bytes((61, (e + 64) & 0xFF))
        else:
            enc.append(e)
        if i % 128 == 127:
            enc += b"\r\n"
    return (b"=ybegin part=%d total=%d line=128 size=%d name=%s\r\n=ypart begin=%d end=%d\r\n"
            % (k, skupaj, len(vse), ime.encode(), z + 1, kon) + bytes(enc)
            + b"\r\n=yend size=%d part=%d pcrc32=%08x\r\n" % (len(kos), k, zlib.crc32(kos)))


class Izdaja:
    """Zvezki se zgradijo sele ob prvem klicu (800 zvezkov brez pomnilnika); [klici] steje telo()."""

    def __init__(self, imena: list, gradnja, bajtov_nzb=None):
        self.imena, self.gradnja, self.bajtov_nzb = imena, gradnja, bajtov_nzb
        self._zv: dict = {}
        self.klici = 0
        self._zaklep = threading.Lock()

    def zvezek(self, n: int) -> bytes:
        with self._zaklep:
            if n not in self._zv:
                self._zv[n] = self.gradnja(n)
            return self._zv[n]

    def telo(self, mid: str) -> bytes:
        with self._zaklep:
            self.klici += 1
        n, k = (int(x) for x in mid.strip("<>").split("@")[0][1:].split("s"))
        v = self.zvezek(n)
        return yenc(self.imena[n], v, k, -(-len(v) // DEL))

    def nzb(self, segmentov=None) -> Nzb:
        dat = []
        for n, ime in enumerate(self.imena):
            st = segmentov(n) if segmentov else -(-len(self.zvezek(n)) // DEL)
            # bajtov_nzb je v core/usenet_nzb lastnost (vsota segmentov): zelena velikost iz NZB se razdeli na segmente.
            skupaj = self.bajtov_nzb(n) if self.bajtov_nzb else st * DEL
            dolzine = [skupaj // st + (1 if k < skupaj % st else 0) for k in range(st)]
            seg = tuple(Segment(stevilka=k, bajtov=dolzine[k - 1], id="<v%ds%d@test>" % (n, k)) for k in range(1, st + 1))
            dat.append(Datoteka(ime=ime, skupine=(), segmenti=seg, manjka=0))
        return Nzb(naslov=None, datoteke=tuple(dat))


def preberi(vir) -> bytes:
    b = B.Bralnik(lambda m: IZ.telo(m), vir, B.PROFILI["namizje"])
    try:
        out = bytearray()
        while len(out) < vir.velikost:
            kos = b.beri(len(out), 1 << 20)
            if not kos:
                break
            out += kos
        return bytes(out)
    finally:
        b.zapri()


IZ = None  # izdaja, ki jo bere preberi()

# ------------------------------------------------------------------ N1: vzorec pred filmom v arhivu z vec zvezki

VZOREC = podatki(110_000, 1)  # 61 % prvega zvezka
FILM = podatki(120_000, 2)
FILM_V0 = 70_000


def izdaja_n1(metoda: int = 0, sifriran: bool = False) -> Izdaja:
    def gradnja(n):
        if n == 0:
            return zvezek(0, [("Film.Sample.mkv", VZOREC, len(VZOREC), False, False, 0, False),
                              ("Film.2026.mkv", FILM[:FILM_V0], len(FILM), False, True, metoda, sifriran)])
        return zvezek(1, [("Film.2026.mkv", FILM[FILM_V0:], len(FILM), True, False, metoda, sifriran)])
    return Izdaja(["film.part1.rar", "film.part2.rar"], gradnja)


def test_n1_prvi_segment_ne_odloci():
    v0 = izdaja_n1().zvezek(0)
    assert len(VZOREC) * 2 >= len(v0)  # stari pogoj »pol zvezka« bi odlocil
    assert R.preveri(v0[:DEL], len(v0)) == R.NEPOPOLNO


def test_n1_stisnjen_film_za_vzorcem():
    iz = izdaja_n1(metoda=3)
    assert B.preveri_izdajo(iz.nzb(), iz.telo) == R.STISNJEN
    with pytest.raises(R.NapakaRar) as e:
        B.pripravi(iz.nzb(), iz.telo)
    assert e.value.izid == R.STISNJEN


def test_n1_sifriran_film_za_vzorcem():
    iz = izdaja_n1(sifriran=True)
    assert B.preveri_izdajo(iz.nzb(), iz.telo) == R.SIFRIRAN


def test_n1_priprava_vrne_film_ne_vzorca():
    global IZ
    IZ = izdaja_n1()
    assert B.preveri_izdajo(IZ.nzb(), IZ.telo) == R.OK
    vir, _b = B.pripravi(IZ.nzb(), IZ.telo)
    assert vir.ime == "Film.2026.mkv"
    assert vir.velikost == len(FILM)
    assert preberi(vir) == FILM


# ------------------------------------------------------------------ L1: meja prometa pred ponudbo

KOS = 2000  # filma v zvezku: zvezek je en clanek


def izdaja_l1(n_zvezkov: int, bajtov_nzb=None, konec_filma=None) -> Izdaja:
    """Film cez [konec_filma] zvezkov (privzeto vse), za njim dodatek do zadnjega zvezka."""
    kf = konec_filma or n_zvezkov
    film = podatki(kf * KOS, 3)

    def gradnja(n):
        if n < kf:
            dat = [("Film.2026.mkv", film[n * KOS:(n + 1) * KOS], len(film), n > 0, n < kf - 1, 0, False)]
            if n == kf - 1 and kf < n_zvezkov:
                dat.append(("Bonus.Featurette.mkv", podatki(KOS, 9), (n_zvezkov - kf + 1) * KOS, False, True, 0, False))
            return zvezek(n, dat)
        return zvezek(n, [("Bonus.Featurette.mkv", podatki(KOS, 9), (n_zvezkov - kf + 1) * KOS, True,
                           n < n_zvezkov - 1, 0, False)])
    iz = Izdaja(["film.part%03d.rar" % (n + 1) for n in range(n_zvezkov)], gradnja, bajtov_nzb)
    iz.film = film
    return iz


def test_l1_800_zvezkov_preveri_brez_prometa():
    iz = izdaja_l1(800, bajtov_nzb=lambda n: 700 * 1024)  # 800 x 700 KiB = 547 MiB > 512 MiB
    nzb = iz.nzb(segmentov=lambda n: 1)
    assert B.preveri_izdajo(nzb, iz.telo) == PREVEC
    assert iz.klici == 0


def test_l1_800_zvezkov_priprava_brez_prometa():
    iz = izdaja_l1(800, bajtov_nzb=lambda n: 700 * 1024)
    nzb = iz.nzb(segmentov=lambda n: 1)
    with pytest.raises(NapakaToka) as e:
        B.pripravi(nzb, iz.telo)
    assert e.value.izid == PREVEC
    assert iz.klici == 0


def test_l1_lazni_nzb_ustavi_po_prvem_clanku():
    iz = izdaja_l1(20, bajtov_nzb=lambda n: 1)  # NZB laze: 1 B na zvezek
    r1 = len(iz.telo("<v0s1@test>"))
    iz.klici = 0
    with pytest.raises(NapakaToka) as e:
        B.pripravi(iz.nzb(), iz.telo, 4, 5 * r1)
    assert e.value.izid == PREVEC
    assert iz.klici == 1  # prej: vsaj 5 zvezkov in se do 4 v teku


def test_l1_ne_bere_zvezkov_za_filmom():
    global IZ
    IZ = iz = izdaja_l1(8, konec_filma=2)
    vir, _b = B.pripravi(iz.nzb(), iz.telo, 1)
    assert iz.klici == 2
    assert vir.ime == "Film.2026.mkv"
    assert preberi(vir) == iz.film


def test_l1_obicajna_izdaja_uspe():
    global IZ
    IZ = iz = izdaja_l1(20)
    nzb = iz.nzb()
    assert B.preveri_izdajo(nzb, iz.telo) == R.OK
    iz.klici = 0
    vir, _b = B.pripravi(nzb, iz.telo)
    assert iz.klici == 20
    assert vir.velikost == len(iz.film)
    assert preberi(vir) == iz.film
