"""Programi radijske postaje z domace strani (core/zakoniti_viri.tokovi_postaje) - brez omrezja."""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import zakoniti_viri as z  # noqa: E402

HTML = b"""<html><a href="https://www.facebook.com/postaja">fb</a><img src="https://cdn.x/slika.jpg">
<script>var s=["https://s.example/proxy/a?mp=/stream","https://s.example/proxy/b?mp=/stream",
"https://s.example/hls/live.m3u8","https://192.168.0.5:8000/stream"];</script></html>"""
GLAVE = {
    "https://s.example/proxy/a?mp=/stream": {"Content-Type": "audio/mpeg", "icy-name": "POSTAJA BALADE", "icy-br": "128"},
    "https://s.example/proxy/b?mp=/stream": {"Content-Type": "audio/aacp", "icy-name": "Postaja Classics", "icy-br": "160"},
    "https://s.example/hls/live.m3u8": {"Content-Type": "application/vnd.apple.mpegurl"},
}


class _Odgovor(io.BytesIO):
    def __init__(self, telo=b"", glave=None):
        super().__init__(telo)
        self.headers, self.status = glave or {}, 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TokoviPostaje(unittest.TestCase):
    def setUp(self):
        self.zahteve = []

        def odpri(req, timeout=0):
            url = req.full_url
            self.zahteve.append(url)
            if url == "https://postaja.example/":
                return _Odgovor(HTML)
            if url in GLAVE:
                return _Odgovor(b"", GLAVE[url])
            raise OSError("ni")
        self.v = z.ZakonitiViri(opener=odpri)

    def test_tokovi_z_imeni_streznika(self):
        tokovi = self.v.tokovi_postaje({"naslov": "Postaja", "domaca_stran": "http://postaja.example/"})
        self.assertEqual([t["naslov"] for t in tokovi], ["Postaja Balade", "Postaja Classics"])
        self.assertEqual(tokovi[0]["bitrate"], 128)
        # Slike, druzbena omrezja in naslovi v domacem omrezju se ne preverjajo.
        self.assertFalse(any("facebook" in u or "192.168" in u or u.endswith(".jpg") for u in self.zahteve))

    def test_brez_domace_strani_nic(self):
        self.assertEqual(self.v.tokovi_postaje({"naslov": "X"}), [])


if __name__ == "__main__":
    unittest.main()
