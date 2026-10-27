"""Lasten pogon Usenet, korak 1 (25. 10. 2026): yEnc - hitra pot (translate, split) proti preprosti referenci po bajtih.

Skupna pravila z Androidom so v tests/skupni-primeri/usenet-pogon.json (tests/test_skupni_primeri.py); tu je nakljucno
preverjanje, da se hitra pot nikoli ne razlikuje od ocitno pravilnega dekodiranja po bajtih.
"""
import random
import unittest
import zlib
from unittest import mock

from core import usenet_yenc as Y


def referenca(telo: bytes) -> bytes:
    """Dekodiranje po bajtih (pocasno, ocitno pravilno): podatki med glavo (=ybegin, =ypart) in =yend; CR in LF nista
    nikoli podatek (yEnc 1.3), ubeznik velja za naslednji znak, ki ni CR/LF."""
    vrstice = telo.replace(b"\r\n", b"\n").split(b"\n")
    i = next(n for n, v in enumerate(vrstice) if v.startswith(b"=ybegin "))
    i += 2 if vrstice[i + 1].startswith(b"=ypart ") else 1
    izid, ubeznik = bytearray(), False
    for v in vrstice[i:]:
        if v.startswith(b"=yend"):
            break
        for c in v:
            if c in (10, 13):
                continue
            if ubeznik:
                izid.append((c - 106) & 255)
                ubeznik = False
            elif c == 61:
                ubeznik = True
            else:
                izid.append((c - 42) & 255)
    return bytes(izid)


class Yenc(unittest.TestCase):
    def test_nakljucno_enako_kot_referenca(self):
        r = random.Random(20261025)
        for _ in range(300):
            podatki = bytes(r.getrandbits(8) for _ in range(r.randrange(0, 3000)))
            telo = Y.kodiraj(podatki, "x.bin", dolzina=r.choice((1, 2, 3, 7, 64, 128, 200)))
            d = Y.dekodiraj(telo)
            self.assertEqual(d.podatki, podatki)
            self.assertEqual(referenca(telo), podatki)
            self.assertTrue(d.crc_preverjen)
            self.assertEqual(d.crc32, zlib.crc32(podatki))

    def test_dodatni_ubezni_znaki_kodirnikov(self):
        """Kodirniki ubezajo tudi druge znake (TAB, presledek, pika ...): vsak '=' + c pomeni (c - 106)."""
        r = random.Random(7)
        for _ in range(200):
            podatki = bytes(r.getrandbits(8) for _ in range(r.randrange(1, 600)))
            vrstica = bytearray()
            for b in podatki:
                o = (b + 42) & 255
                # ubezni znak ni nikoli CR/LF (kodirnik ubeza samo znake, katerih o + 64 ni CR/LF)
                if o in (0, 10, 13, 61) or (r.random() < 0.1 and (o + 64) & 255 not in (10, 13)):
                    vrstica += bytes((61, (o + 64) & 255))
                else:
                    vrstica.append(o)
            telo = (b"=ybegin line=128 size=%d name=a\r\n" % len(podatki) + bytes(vrstica) +
                    b"\r\n=yend size=%d crc32=%08x\r\n" % (len(podatki), zlib.crc32(podatki)))
            self.assertEqual(Y.dekodiraj(telo).podatki, podatki)

    def test_splosna_pot_z_dvojnim_ubeznikom(self):
        r = random.Random(11)
        for _ in range(200):
            blok = bytes(r.choice(b"==ab\r\n\x00+}") for _ in range(r.randrange(1, 80)))
            telo = b"=ybegin line=128 size=%d name=a\r\n" % 0 + blok + b"\r\n=yend size=0\r\n"
            pricakovano = referenca(telo)
            self.assertEqual(Y._odpakiraj(blok.translate(None, b"\r\n")), pricakovano, blok)

    def test_vecdelni_odmik(self):
        podatki = bytes(range(256)) * 10
        d = Y.dekodiraj(Y.kodiraj(podatki[100:600], "f.mkv", velikost=len(podatki), del_=2, skupaj=5, zacetek=101))
        self.assertEqual((d.del_, d.skupaj, d.velikost, d.zacetek, d.konec, d.odmik), (2, 5, 2560, 101, 600, 100))
        self.assertEqual(d.podatki, podatki[100:600])

    def test_izjema_in_repr_brez_podatkov(self):
        tajno = b"TAJNA-VSEBINA-123"
        d = Y.dekodiraj(Y.kodiraj(tajno, "t.bin"))
        self.assertNotIn("TAJNA", repr(d))
        crc = zlib.crc32(tajno)
        telo = Y.kodiraj(tajno, "t.bin").replace(b"crc32=%08x" % crc, b"crc32=%08x" % (crc ^ 1))
        with self.assertRaises(Y.NapakaYenc) as e:
            Y.dekodiraj(telo)
        self.assertEqual(e.exception.izid, Y.NAPAKA_CRC)
        self.assertNotIn("TAJNA", str(e.exception) + repr(e.exception))

    def test_meja_pred_dekodiranjem(self):
        telo = Y.kodiraj(b"x" * 2000, "a")
        with mock.patch.object(Y, "NAJVEC_DEL_BAJTOV", 1000):
            with self.assertRaises(Y.NapakaYenc) as e:
                Y.dekodiraj(telo)
        self.assertEqual(e.exception.izid, Y.PREVELIK)

    def test_predolg_blok_se_ne_dekodira(self):
        telo = b"=ybegin line=128 size=10 name=a\r\n" + b"+" * 5000 + b"\r\n=yend size=10\r\n"
        with mock.patch.object(Y, "_odpakiraj", side_effect=AssertionError("ne bi smel dekodirati")):
            with self.assertRaises(Y.NapakaYenc) as e:
                Y.dekodiraj(telo)
        self.assertEqual(e.exception.izid, Y.NAPAKA_VELIKOSTI)

    def test_ime_samo_ime(self):
        for ime, pricakovano in (("../../.bashrc", "_bashrc"), ("C:\\Windows\\x.dll", "x.dll"), ("/", None)):
            self.assertEqual(Y.dekodiraj(Y.kodiraj(b"a", ime)).ime, pricakovano)


if __name__ == "__main__":
    unittest.main()
