"""D2 (pregled 5. 11. 2026): prenos paketa posodobitve ima mejo - velikost iz podpisanega seznama ali NAJVEC_PAKETA.
Streznik, ki poslje vec, prenos prekine takoj (prej je brala do konca in disk napolnila; SHA-256 je paket zavrnil sele
na koncu). Preverba SHA-256 ostane nespremenjena. Brez omrezja (lazen odgovor)."""
import contextlib
import hashlib
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_posodobitve as P  # noqa: E402

KOS = 1 << 16


class _Odgovor:
    """Telo iz ponavljajocih se kosov; steje prebrane bajte."""

    def __init__(self, skupaj, dolzina=None):
        self.ostane = skupaj
        self.prebrano = 0
        self.headers = {"Content-Length": str(dolzina)} if dolzina is not None else {}

    def read(self, n):
        n = min(n, self.ostane)
        self.ostane -= n
        self.prebrano += n
        return b"x" * n

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class Meja(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.cilj = os.path.join(self.mapa.name, "paket.deb")

    def _prenesi(self, odgovor, velikost, sha=None):
        with mock.patch.object(P, "_odpri", lambda *a, **k: odgovor):
            return P.prenesi("https://safeer.si/os/paket.deb", self.cilj, sha or "0" * 64, velikost)

    def test_vec_od_podpisane_velikosti_prekine(self):
        o = _Odgovor(50 * 1024 * 1024)                  # 50 MiB brez Content-Length, seznam pravi 100 000 B
        with self.assertRaises(ValueError) as e:
            self._prenesi(o, 100000)
        self.assertIn("velikosti", str(e.exception))
        self.assertLessEqual(o.prebrano, 100000 + 1)
        self.assertFalse(os.path.exists(self.cilj) or os.path.exists(self.cilj + ".del"))

    def test_napovedana_dolzina_prevelika(self):
        o = _Odgovor(10, dolzina=10 ** 9)
        with self.assertRaises(ValueError):
            self._prenesi(o, 1000)
        self.assertEqual(o.prebrano, 0)

    def test_brez_velikosti_stalna_meja(self):
        o = _Odgovor(3 * KOS)
        with mock.patch.object(P, "NAJVEC_PAKETA", 2 * KOS), self.assertRaises(ValueError):
            self._prenesi(o, 0)
        self.assertLessEqual(o.prebrano, 2 * KOS + 1)

    def test_tocna_velikost_in_sha(self):
        telo = b"x" * (KOS + 5)
        self.assertEqual(self._prenesi(_Odgovor(len(telo)), len(telo), hashlib.sha256(telo).hexdigest()), self.cilj)
        with open(self.cilj, "rb") as f:
            self.assertEqual(f.read(), telo)
        # SHA-256 se vedno preveri (meja ga ne nadomesti).
        with contextlib.suppress(FileNotFoundError):
            os.remove(self.cilj)
        with self.assertRaises(ValueError) as e:
            self._prenesi(_Odgovor(len(telo)), len(telo), "1" * 64)
        self.assertIn("SHA-256", str(e.exception))


if __name__ == "__main__":
    unittest.main()
