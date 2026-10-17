"""Medijski center v dolgotrajnem procesu: predpomnilnika TMDB in iskanj po strezniki v pomnilniku ne rasteta za vedno.

Vsako iskanje in vsaka stran kataloga je dodala zapis (cel odgovor JSON), odstranjenega nikoli; disk je bil obrezan
(PREDPOMNILNIK_TMDB), pomnilnik ne."""
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import os_media  # noqa: E402


class _Odgovor:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def read(self, _n=-1):
        return json.dumps({"results": []}).encode()


class PredpomnilnikSeCisti(unittest.TestCase):
    def test_stari_zapisi_izginejo_knjiznice_ostanejo(self):
        with tempfile.TemporaryDirectory() as td:
            c = os_media.MediaCenter(td, roots=[])
            star = time.time() - c.PREDPOMNILNIK_POMNILNIK_S - 60
            for i in range(300):
                c._tmdb_cache["https://tmdb/search?q=%d" % i] = (star, {"results": [i]})
                c._server_cache["jf1:iskanje %d" % i] = (star, [{"i": i}])
            c._server_cache["jf1:"] = (star, [{"knjiznica": True}])
            c._server_cache["jf1:svezo"] = (time.time(), [])
            c._predpomnilnika_pociscena = 0.0
            with mock.patch.object(os_media.urllib.request, "urlopen", return_value=_Odgovor()):
                c._tmdb("/trending/movie/week")
            self.assertEqual(len(c._tmdb_cache), 1)
            self.assertEqual(set(c._server_cache), {"jf1:", "jf1:svezo"})


if __name__ == "__main__":
    unittest.main()
