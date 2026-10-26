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
