"""Testni arhivi RAR4/RAR5 v nacinu store, sestavljeni po objavljeni specifikaciji (RARLAB technote za RAR 2.9-4,
»RAR 5.0 archive format«) - za preizkuse in skupne primere, brez programa rar. Glava datoteke RAR5 ima ista polja v
istem vrstnem redu kot WinRAR 7 (primerjano 26. 10. 2026); WinRAR doda se zapis casa in 0 zapise kot dvobajtni vint.
Prave glave WinRAR (store, -m3, -p, -hp) so v test_usenet_tok.PraviRar."""
import struct
import zlib

PODPIS4 = b"Rar!\x1a\x07\x00"
PODPIS5 = b"Rar!\x1a\x07\x01\x00"


def vint(n: int) -> bytes:
    izid = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            izid.append(b | 0x80)
        else:
            izid.append(b)
            return bytes(izid)


# ------------------------------------------------------------------ RAR5

def blok5(vrsta: int, zast: int, polja: bytes, dodatno: bytes = b"", podatkov=None) -> bytes:
    z = zast | (0x1 if dodatno else 0) | (0x2 if podatkov is not None else 0)
    telo = vint(vrsta) + vint(z) + (vint(len(dodatno)) if dodatno else b"") + \
        (vint(podatkov) if podatkov is not None else b"") + polja + dodatno
    vel = vint(len(telo))
    return struct.pack("<I", zlib.crc32(vel + telo)) + vel + telo


def glava5_datoteke(ime: str, velikost: int, kos: bytes, metoda: int = 0, pred: bool = False, po: bool = False,
                    sifriran: bool = False, mapa: bool = False) -> bytes:
    ime_b = ime.encode("utf-8")
    polja = vint(0x4 | (0x1 if mapa else 0)) + vint(velikost) + vint(0x20) + struct.pack("<I", zlib.crc32(kos)) + \
        vint(metoda << 7) + vint(0) + vint(len(ime_b)) + ime_b
    dodatno = b""
    if sifriran:
        zapis = vint(0x01) + vint(0) + vint(0) + bytes(16 + 16)  # vrsta, razlicica, zastavice, sol, IV
        dodatno = vint(len(zapis)) + zapis
    return blok5(2, (0x8 if pred else 0) | (0x10 if po else 0), polja, dodatno, len(kos))


def rar5(datoteke, zvezek: int = None, vec: bool = False, zadnji: bool = True, sifrirane_glave: bool = False) -> bytes:
    """[datoteke] = [(ime, velikost, kos, dict(metoda, pred, po, sifriran, mapa))]."""
    if sifrirane_glave:
        return PODPIS5 + blok5(4, 0, vint(0) + vint(0x1) + vint(15) + bytes(16) + bytes(12))
    af = (0x1 if vec else 0) | (0x2 if zvezek else 0)
    izid = PODPIS5 + blok5(1, 0, vint(af) + (vint(zvezek) if zvezek else b""))
    for ime, velikost, kos, mozn in datoteke:
        izid += glava5_datoteke(ime, velikost, kos, **mozn) + kos
    return izid + blok5(5, 0, vint(0 if zadnji else 1))


# ------------------------------------------------------------------ RAR4

def blok4(vrsta: int, zast: int, telo: bytes) -> bytes:
    g = struct.pack("<BHH", vrsta, zast, 7 + len(telo)) + telo
    return struct.pack("<H", zlib.crc32(g) & 0xFFFF) + g


def glava4_datoteke(ime: str, velikost: int, kos: bytes, metoda: int = 0x30, pred: bool = False, po: bool = False,
                    sifriran: bool = False, unicode: bool = False, velika: bool = False) -> bytes:
    ime_b = ime.encode("utf-8") if not unicode else ime.encode("ascii", "replace") + b"\x00" + b"\x01\x02"
    zast = 0x8000 | (0x01 if pred else 0) | (0x02 if po else 0) | (0x04 if sifriran else 0) | \
        (0x200 if unicode else 0) | (0x100 if velika else 0)
    telo = struct.pack("<IIBIIBBHI", len(kos) & 0xFFFFFFFF, velikost & 0xFFFFFFFF, 2, zlib.crc32(kos), 0, 29, metoda,
                       len(ime_b), 0x20)
    if velika:
        telo += struct.pack("<II", len(kos) >> 32, velikost >> 32)
    return blok4(0x74, zast, telo + ime_b)


def rar4(datoteke, vec: bool = False, prvi: bool = True, sifrirane_glave: bool = False) -> bytes:
    zast = (0x0001 if vec else 0) | (0x0010 if vec else 0) | (0x0100 if vec and prvi else 0) | \
        (0x0080 if sifrirane_glave else 0)
    izid = PODPIS4 + blok4(0x73, zast, bytes(6))
    for ime, velikost, kos, mozn in datoteke:
        izid += glava4_datoteke(ime, velikost, kos, **mozn) + kos
    return izid + blok4(0x7B, 0x4000, b"")


def zvezki(razlicica: int, ime: str, podatki: bytes, na_zvezek: int, **mozn) -> list:
    """Vec zvezkov store: [na_zvezek] bajtov podatkov na zvezek (zadnji manj)."""
    kosi = [podatki[i:i + na_zvezek] for i in range(0, len(podatki), na_zvezek)] or [b""]
    izid = []
    for n, kos in enumerate(kosi):
        m = dict(mozn, pred=n > 0, po=n < len(kosi) - 1)
        d = [(ime, len(podatki), kos, m)]
        if razlicica == 5:
            izid.append(rar5(d, zvezek=n, vec=True, zadnji=n == len(kosi) - 1))
        else:
            izid.append(rar4(d, vec=True, prvi=n == 0))
    return izid


# ------------------------------------------------------------------ objava na Usenetu (za bralnik in meritve)

class Leno:
    """Ponovljiva psevdonakljucna vsebina [velikost] bajtov brez drzanja v RAM (bloki po 64 KiB iz semena)."""
    BLOK = 65536

    def __init__(self, velikost: int, seme: int = 1):
        self.velikost, self.seme = int(velikost), int(seme)
        self._zadnji = (-1, b"")

    def _blok(self, k: int) -> bytes:
        if self._zadnji[0] != k:
            import random
            n = min(self.BLOK, self.velikost - k * self.BLOK)
            self._zadnji = (k, random.Random(self.seme * 1_000_003 + k).randbytes(n))
        return self._zadnji[1]

    def beri(self, o: int, n: int) -> bytes:
        deli, konec = [], min(self.velikost, o + n)
        while o < konec:
            k, z = divmod(o, self.BLOK)
            b = self._blok(k)[z:z + konec - o]
            deli.append(b)
            o += len(b)
        return b"".join(deli)


class Bajti:
    def __init__(self, podatki: bytes):
        self.podatki, self.velikost = bytes(podatki), len(podatki)

    def beri(self, o: int, n: int) -> bytes:
        return self.podatki[o:o + n]


class Zlepek:
    """Zaporedje vsebin (bajti glave RAR + kos lenega filma + konec) kot ena vsebina."""

    def __init__(self, deli: list):
        self.deli = deli  # [(vsebina, od, dolzina)]
        self.velikost = sum(d for _v, _o, d in deli)

    def beri(self, o: int, n: int) -> bytes:
        izid, z = [], 0
        for v, od, d in self.deli:
            if n <= 0:
                break
            if o < z + d:
                k = max(0, o - z)
                kos = v.beri(od + k, min(d - k, n))
                izid.append(kos)
                n -= len(kos)
                o += len(kos)
            z += d
        return b"".join(izid)


def zvezki_leno(razlicica: int, ime: str, film, na_zvezek: int) -> list:
    """Vec zvezkov RAR store nad leno vsebino [film] (glave so prave, podatki se ne kopirajo)."""
    n = (film.velikost + na_zvezek - 1) // na_zvezek
    izid = []
    for i in range(n):
        od, d = i * na_zvezek, min(na_zvezek, film.velikost - i * na_zvezek)
        kos = film.beri(od, d)  # za CRC v glavi (enkrat ob gradnji)
        pred, po = i > 0, i < n - 1
        if razlicica == 5:
            af = 0x1 | (0x2 if i else 0)
            glava = PODPIS5 + blok5(1, 0, vint(af) + (vint(i) if i else b"")) + \
                glava5_datoteke(ime, film.velikost, kos, pred=pred, po=po)
            rep = blok5(5, 0, vint(0 if i == n - 1 else 1))
        else:
            zast = 0x0001 | 0x0010 | (0x0100 if i == 0 else 0)
            glava = PODPIS4 + blok4(0x73, zast, bytes(6)) + glava4_datoteke(ime, film.velikost, kos, pred=pred, po=po)
            rep = blok4(0x7B, 0x4000, b"")
        izid.append(Zlepek([(Bajti(glava), 0, len(glava)), (film, od, d), (Bajti(rep), 0, len(rep))]))
    return izid


class Objava:
    """Datoteke, razrezane v clanke yEnc kot pri objavi (Nyuu: enaki deli, zadnji krajsi). Kot slovar message-id ->
    telo clanka (CRLF, brez podvojenih pik) - za LazniStreznik (CLANKI) in neposredne preizkuse. Steje poslane bajte."""

    def __init__(self, del_bajtov: int = 700 * 1024):
        self.del_bajtov = del_bajtov
        self.datoteke = []  # (ime, vsebina, [message-id])
        self._clanki = {}  # mid -> (datoteka, stevilka)
        self.poslano = 0
        self.poslanih = 0
        self.manjka = set()  # message-id, ki jih »ponudnik nima« (430)

    def dodaj(self, ime: str, vsebina) -> list:
        n = max(1, (vsebina.velikost + self.del_bajtov - 1) // self.del_bajtov)
        idji = ["o%d.s%d.%s@primer.invalid" % (len(self.datoteke), s + 1, "x" * 8) for s in range(n)]
        for s, mid in enumerate(idji):
            self._clanki[mid] = (len(self.datoteke), s + 1)
        self.datoteke.append((ime, vsebina, idji))
        return idji

    def __contains__(self, mid) -> bool:
        return mid in self._clanki and mid not in self.manjka

    def __getitem__(self, mid) -> bytes:
        import importlib
        Y = importlib.import_module("core.usenet_yenc")
        d, st = self._clanki[mid]
        ime, v, idji = self.datoteke[d]
        od = (st - 1) * self.del_bajtov
        kos = v.beri(od, self.del_bajtov)
        telo = Y.kodiraj(kos, ime, v.velikost, st, len(idji), od + 1)
        self.poslano += len(telo)
        self.poslanih += 1
        return telo

    def telo(self, mid: str) -> bytes:
        """Kot Bazen.telo (brez omrezja): 430 za manjkajoce."""
        if mid not in self:
            import importlib
            N = importlib.import_module("core.usenet_nntp")
            raise N.NapakaNntp(N.NI_CLANKA, 430)
        return self[mid]

    def nzb(self, izpusti: tuple = ()) -> bytes:
        deli = ['<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE nzb PUBLIC "-//newzBin//DTD NZB 1.1//EN" '
                '"http://www.newzbin.com/DTD/nzb/nzb-1.1.dtd">\n<nzb xmlns="http://www.newzbin.com/DTD/2003/nzb">']
        for ime, v, idji in self.datoteke:
            seg = "".join('<segment bytes="%d" number="%d">%s</segment>' % (self.del_bajtov + 30000, s + 1, mid)
                          for s, mid in enumerate(idji) if mid not in izpusti)
            deli.append('<file poster="p@primer.invalid" date="1" subject="[1/1] - &quot;%s&quot; yEnc (1/%d)">'
                        '<groups><group>alt.binaries.test</group></groups><segments>%s</segments></file>'
                        % (ime, len(idji), seg))
        deli.append("</nzb>")
        return "".join(deli).encode("utf-8")


def ogled(beri, velikost: int, bitov_na_s: float, sekund: float = 60.0, vnaprej_s: float = 20.0,
          kos: int = 256 * 1024, sonda: bool = True, od: int = 0, korak_s: float = 0.5) -> int:
    """Model predvajalnika (mpv z --cache-secs=20): ob odprtju glava (1 MiB) in indeks na koncu (64 KiB pri -2 MiB),
    nato od [od] zaporedno, nikoli vec kot [vnaprej_s] pred mestom predvajanja. Vrne bajte, ki jih je predvajalnik
    prebral (»pogledano« kot v prototipu 25. 10. 2026: 60 s + 20 s vnaprej)."""
    prebrano = 0

    def vzemi(o, n):
        nonlocal prebrano
        b = beri(o, n)
        prebrano += len(b)
        return b
    if sonda:
        vzemi(0, 1024 * 1024)
        vzemi(max(0, velikost - 2 * 1024 * 1024), 65536)
    poz, t = od, 0.0
    na_s = bitov_na_s / 8.0
    while t < sekund:
        t += korak_s
        cilj = min(velikost, int(od + na_s * (t + vnaprej_s)))
        while poz < cilj:
            b = vzemi(poz, min(kos, cilj - poz))
            if not b:
                return prebrano
            poz += len(b)
    return prebrano


def pocakaj_mir(bralnik, rok_s: float = 30.0) -> None:
    """Pocaka, da bralnik nima vec branj v teku (za stetje prometa po ogledu)."""
    import time
    konec = time.monotonic() + rok_s
    while time.monotonic() < konec:
        with bralnik._pogoj:
            if not bralnik._v_teku:
                return
        time.sleep(0.02)
