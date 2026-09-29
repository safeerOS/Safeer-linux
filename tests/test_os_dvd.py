"""DVD brez zaščite (core/os_dvd.py): prepoznava slike ISO in mape VIDEO_TS, naslov dvd://, knjižnica."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import os_dvd, os_knjiznica  # noqa: E402
from core.os_predvajalnik import medij, vrsta_napake  # noqa: E402
from types import SimpleNamespace  # noqa: E402


def zapis(ime: bytes, sektor: int, mapa: bool) -> bytes:
    z = bytearray(33 + len(ime) + (0 if len(ime) % 2 else 1))
    z[0] = len(z)
    z[2:6] = sektor.to_bytes(4, "little")
    z[10:14] = (2048).to_bytes(4, "little")
    z[25] = 2 if mapa else 0
    z[32] = len(ime)
    z[33:33 + len(ime)] = ime
    return bytes(z)


def iso(pot: str, imena) -> None:
    slika = bytearray(2048 * 24)
    pvd = bytearray(2048)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[156:190] = zapis(b"\x00", 20, True)[:34]
    slika[16 * 2048:17 * 2048] = pvd
    koren = b"".join(zapis(i, 21, True) for i in [b"\x00", b"\x01"] + list(imena))
    slika[20 * 2048:20 * 2048 + len(koren)] = koren
    with open(pot, "wb") as d:
        d.write(slika)


class Dvd(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_iso_z_video_ts(self):
        film = os.path.join(self.d, "Moj_film.iso")
        iso(film, [b"AUDIO_TS", b"VIDEO_TS"])
        podatki = os.path.join(self.d, "podatki.iso")
        iso(podatki, [b"DOKUMENTI"])
        self.assertTrue(os_dvd.je_dvd(film))
        self.assertFalse(os_dvd.je_dvd(podatki))
        self.assertEqual(os_dvd.uri(film), "dvd://" + os.path.realpath(film))
        self.assertEqual(os_knjiznica.vrsta_datoteke(Path(film)), "filmi")
        self.assertEqual(os_knjiznica.vrsta_datoteke(Path(podatki)), "")
        self.assertEqual(os_knjiznica.naslov_datoteke(Path(film)), "Moj film")
        self.assertEqual(medij(os_dvd.uri(film)).vrsta, "video")

    def test_mapa_video_ts(self):
        disk = os.path.join(self.d, "Počitnice 2003")
        os.makedirs(os.path.join(disk, "VIDEO_TS"))
        open(os.path.join(disk, "VIDEO_TS", "VIDEO_TS.IFO"), "wb").close()
        ifo = os.path.join(disk, "VIDEO_TS", "VIDEO_TS.IFO")
        self.assertTrue(os_dvd.je_dvd(ifo))
        self.assertEqual(os_dvd.uri(ifo), "dvd://" + os.path.realpath(disk))
        self.assertEqual(os_dvd.naslov(ifo), "Počitnice 2003")
        self.assertEqual(os_knjiznica.vrsta_datoteke(Path(ifo)), "filmi")
        self.assertEqual(medij(os_dvd.uri(ifo)).naslov, "Počitnice 2003")
        with self.assertRaises(ValueError):
            medij("dvd:///ni/tega/diska.iso")

    def test_zasciten_disk_ima_razumljivo_sporocilo(self):
        napaka = SimpleNamespace(domain="gst-resource-error-quark", code=5)
        self.assertEqual(vrsta_napake(napaka, "dvd:///x.iso"), "dvd")


if __name__ == "__main__":
    unittest.main()
