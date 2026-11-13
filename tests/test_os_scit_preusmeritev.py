"""Prenos seznamov in preverba kljuca ne sledita preusmeritvam na http/notranja omrezja (neodvisni pregled 12. 11. 2026)."""
import http.server
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import os_scit  # noqa: E402


def _streznik(obravnava):
    s = http.server.HTTPServer(("127.0.0.1", 0), obravnava)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def _par():
    videno = []

    class B(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            videno.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"x")

        def log_message(self, *a):
            pass

    b = _streznik(B)

    class A(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:%d/notranji" % b.server_port)
            self.end_headers()

        def log_message(self, *a):
            pass

    return _streznik(A), b, videno


def test_prenesi_ne_sledi_preusmeritvi_na_http():
    a, b, videno = _par()
    try:
        assert os_scit.prenesi("http://127.0.0.1:%d/seznam" % a.server_port, "", 5) == (0, b"", "")
    finally:
        a.shutdown(); b.shutdown(); a.server_close(); b.server_close()
    assert videno == []


def test_preusmeritev_samo_na_isti_https():
    h = os_scit._PreusmeritevSamoNaIstiHttps()
    import urllib.request
    z = urllib.request.Request("https://seznam.example/a")
    for cilj in ("http://seznam.example/b", "https://drug.example/b", "ftp://seznam.example/b"):
        try:
            h.redirect_request(z, None, 302, "x", {}, cilj)
        except Exception as e:  # noqa: BLE001
            assert e.__class__.__name__ == "HTTPError"
        else:
            raise AssertionError(cilj)
    assert h.redirect_request(z, None, 302, "x", {}, "https://seznam.example/b") is not None


def test_osvezi_z_kljucem_ne_sledi_preusmeritvam():
    """Neodvisni pregled 13. 11. 2026 (4): zahteva s kljucem abuse.ch uporabi prenos brez sledenja preusmeritvam."""
    import tempfile
    klici = []
    stari = os_scit.prenesi_s_kljucem
    os_scit.prenesi_s_kljucem = lambda url, etag, cas=60.0: (klici.append(url), (0, b"", etag))[1]
    try:
        with tempfile.TemporaryDirectory() as m:
            s = os_scit.Seznami(m, kljuc_fn=lambda: "k" * 40)
            s.viri = lambda: [("urlhaus", "https://urlhaus-api.abuse.ch/v2/files/exports/{KLJUC}/hostfile.txt", "malware")]
            s._osvezi()
    finally:
        os_scit.prenesi_s_kljucem = stari
    assert klici == ["https://urlhaus-api.abuse.ch/v2/files/exports/%s/hostfile.txt" % ("k" * 40)]


def test_brez_preusmeritve_zavrne_tudi_isti_https():
    import urllib.request
    h = os_scit._BrezPreusmeritev()
    z = urllib.request.Request("https://seznam.example/a")
    try:
        h.redirect_request(z, None, 302, "x", {}, "https://seznam.example/b")
    except Exception as e:  # noqa: BLE001
        assert e.__class__.__name__ == "HTTPError"
    else:
        raise AssertionError("preusmeritev bi morala biti napaka")
