"""Tok, ki zahteva glave, tiho nadomescanje razlicic, sonda brez ponavljanja in iskanje z rokom na vir.

Lazni strezniki tecejo na 127.0.0.1 (brez interneta)."""

import http.server
import tempfile
import threading
import time
import unittest
import urllib.parse
from types import SimpleNamespace
from unittest import mock

from core import media_servers, os_media
from core.os_katalog import tok_za_predvajalnik
from core.os_predvajalnik import Predvajalnik, Skladba, cisti_glave, status_napake


class _Tok(http.server.BaseHTTPRequestHandler):
    """/zahteva-referer: 429 brez glave Referer (kot streznik toka, izmerjen 15. 10. 2026), sicer 206.
    /pocakaj: 429 z Retry-After. /enkratni: prvi GET 206, nato 410. /stej: steje zahteve."""
    stevec: dict = {}

    def log_message(self, *_a):
        pass

    def do_GET(self):  # noqa: N802
        pot = self.path.split("?")[0]
        _Tok.stevec[pot] = _Tok.stevec.get(pot, 0) + 1
        if pot == "/zahteva-referer" and not self.headers.get("Referer"):
            return self._odgovor(429, b"<html>429</html>", "text/html")
        if pot == "/pocakaj":
            self.send_response(429)
            self.send_header("Retry-After", "7")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if pot == "/enkratni" and _Tok.stevec[pot] > 1:
            return self._odgovor(410, b"", "text/plain")
        return self._odgovor(206, b"\x00\x00", "video/mp4")

    def _odgovor(self, koda, telo, vrsta):
        self.send_response(koda)
        self.send_header("Content-Type", vrsta)
        self.send_header("Content-Length", str(len(telo)))
        self.end_headers()
        self.wfile.write(telo)


class StrezniTokaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Tok)
        threading.Thread(target=cls.streznik.serve_forever, daemon=True).start()
        cls.koren = "http://127.0.0.1:%d" % cls.streznik.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.streznik.shutdown()

    def test_tok_brez_glav_vrne_429_z_glavami_206(self):
        self.assertEqual(media_servers.tok_stanje(self.koren + "/zahteva-referer")[:2], (False, 429))
        self.assertEqual(media_servers.tok_stanje(self.koren + "/zahteva-referer", {"Referer": "https://a.test/"})[:2],
                         (True, 206))

    def test_429_z_retry_after_je_ziv_a_pocakaj(self):
        self.assertEqual(media_servers.tok_stanje(self.koren + "/pocakaj"), (True, 429, 7))

    def test_sonda_istega_naslova_ne_ponovi_zahteve(self):
        mc = os_media.MediaCenter(tempfile.mkdtemp(), roots=[])
        mc.preveri_tokove = True
        _Tok.stevec.clear()
        tokovi = [{"url": self.koren + "/enkratni?sign=x"}, {"url": self.koren + "/stej"}]
        self.assertEqual(mc._zivi_naprej(list(tokovi))[0]["url"], tokovi[0]["url"])
        # Drugi Predvajaj v minuti: brez nove zahteve (enkratni naslov bi drugo zahtevo zavrnil z 410).
        self.assertEqual(mc._zivi_naprej(list(tokovi))[0]["url"], tokovi[0]["url"])
        self.assertEqual(_Tok.stevec.get("/enkratni"), 1)


class _Element:
    def __init__(self):
        self.lastnosti, self.stanja, self.signali = {}, [], {}
        self.vodilo = SimpleNamespace(add_signal_watch=lambda: None, remove_signal_watch=lambda: None,
                                     connect=lambda *_: None)

    def get_bus(self):
        return self.vodilo

    def connect(self, ime, fn):
        self.signali[ime] = fn

    def set_state(self, stanje):
        self.stanja.append(stanje)
        return "ok"

    def set_property(self, ime, vrednost):
        self.lastnosti[ime] = vrednost

    def get_property(self, ime):
        return self.lastnosti.get(ime, {"flags": 0x17, "n-text": 0}.get(ime))


class _Struktura(dict):
    @classmethod
    def new_empty(cls, _ime):
        return cls()

    def set_value(self, k, v):
        self[k] = v


class _Vir:
    def __init__(self):
        self.lastnosti = {}

    def find_property(self, ime):
        return ime in ("extra-headers", "user-agent") or None

    def set_property(self, ime, vrednost):
        self.lastnosti[ime] = vrednost


class PredvajalnikRazliciceTests(unittest.TestCase):
    def setUp(self):
        self.element = _Element()
        self.gst = SimpleNamespace(ElementFactory=SimpleNamespace(make=lambda *_: self.element),
                                   State=SimpleNamespace(NULL="null", PLAYING="playing", PAUSED="paused", READY="ready"),
                                   StateChangeReturn=SimpleNamespace(FAILURE="failure"), Structure=_Struktura,
                                   MessageType=SimpleNamespace(EOS="eos", ERROR="error", ASYNC_DONE="async_done"))
        self.p = Predvajalnik(self.gst)
        self.neuspeli = []
        self.p.neuspeh = self.neuspeli.append
        self.zakasnjeni = []
        self.p.zakasni = lambda ms, f: self.zakasnjeni.append(ms) or f()

    def _napaka(self, status):
        napaka = SimpleNamespace(domain="gst-resource-error-quark", code=5)
        dbg = "gst_soup_http_src_parse_status (): Unknown Error (%d), URL: https://x/y?sign=SKRIVNO" % status
        self.p._sporocilo(None, SimpleNamespace(type="error", parse_error=lambda: (napaka, dbg)))

    def test_glave_toka_gredo_v_souphttpsrc(self):
        self.p.zamenjaj_vrsto([Skladba("https://cdn.test/a.mp4", "Film", "video",
                                       glave=cisti_glave({"Referer": "https://r.test/", "User-Agent": "UA", "Cookie": "x"}))])
        vir = _Vir()
        self.element.signali["source-setup"](self.element, vir)
        self.assertEqual(dict(vir.lastnosti["extra-headers"]), {"Referer": "https://r.test/"})
        self.assertEqual(vir.lastnosti["user-agent"], "UA")             # Cookie ni dovoljen (ne gre naprej)

    def test_429_tiho_naslednja_razlicica_najprej_drug_streznik(self):
        nadomestni = (("https://cdn.test/480.mp4", (("Referer", "https://r.test/"),)),
                      ("https://drug.test/720.mp4", ()))
        self.p.zamenjaj_vrsto([Skladba("https://cdn.test/720.mp4", "Film", "video", nadomestni=nadomestni)])
        self._napaka(429)
        self.assertEqual(self.p.stanje, "predvaja")
        self.assertEqual(self.element.lastnosti["uri"], "https://drug.test/720.mp4")   # drug streznik pred istim
        self.assertEqual(self.p.napaka, "")
        self._napaka(503)
        self.assertEqual(self.element.lastnosti["uri"], "https://cdn.test/480.mp4")
        self.assertEqual(self.zakasnjeni, [])            # po 503 drugega streznika ni premora
        self.assertEqual(self.p._glave, (("Referer", "https://r.test/"),))
        self._napaka(404)
        self.assertEqual((self.p.stanje, self.p.napaka), ("napaka", "tok"))
        self.assertEqual([s.naslov for s in self.neuspeli], ["Film"])      # naslov se oznaci kot nepredvajljiv

    def test_zakasnela_napaka_prejsnje_razlicice_ne_steje(self):
        # GStreamer po 429 poslje se »streaming stopped« istega vira (izmerjeno na testnem PC): ne sme preskociti
        # naslednje razlicice.
        self.p.zamenjaj_vrsto([Skladba("https://cdn.test/a.mp4", "Film", "video",
                                       nadomestni=(("https://drug.test/b.mp4", ()), ("https://tretji.test/c.mp4", ())))])
        napaka = SimpleNamespace(domain="gst-resource-error-quark", code=5)
        self.p._sporocilo(None, SimpleNamespace(type="error", parse_error=lambda: (
            napaka, "/GstPlayBin:safeer-media/GstURIDecodeBin:uridecodebin0/GstSoupHTTPSrc:source: Unknown Error (429)")))
        self.assertEqual(self.element.lastnosti["uri"], "https://drug.test/b.mp4")
        tok = SimpleNamespace(domain="gst-stream-error-quark", code=1)
        self.p._sporocilo(None, SimpleNamespace(type="error", parse_error=lambda: (
            tok, "/GstPlayBin:safeer-media/GstURIDecodeBin:uridecodebin0/GstSoupHTTPSrc:source: streaming stopped")))
        self.assertEqual(self.element.lastnosti["uri"], "https://drug.test/b.mp4")     # se vedno druga razlicica
        self.assertEqual(self.p.stanje, "predvaja")

    def test_stran_html_namesto_posnetka_tiho_naslednja(self):
        self.p.zamenjaj_vrsto([Skladba("https://cdn.test/a", "Film", "video", nadomestni=(("https://drug.test/b.mp4", ()),))])
        napaka = SimpleNamespace(domain="gst-stream-error-quark", code=4)          # TYPE_NOT_FOUND (stran HTML)
        self.p._sporocilo(None, SimpleNamespace(type="error", parse_error=lambda: (napaka, "")))
        self.assertEqual((self.p.stanje, self.element.lastnosti["uri"]), ("predvaja", "https://drug.test/b.mp4"))
        self.p._sporocilo(None, SimpleNamespace(type="error", parse_error=lambda: (napaka, "")))
        self.assertEqual((self.p.stanje, self.p.napaka), ("napaka", "format"))
        self.assertEqual(self.neuspeli, [])               # morda manjka kodek na tem racunalniku: naslova ne skrijemo

    def test_po_zacetku_predvajanja_ni_nadomescanja(self):
        self.p.zamenjaj_vrsto([Skladba("https://cdn.test/a.mp4", "Film", "video",
                                       nadomestni=(("https://cdn.test/b.mp4", ()),))])
        self.p._sporocilo(None, SimpleNamespace(type="async_done"))
        self._napaka(500)
        self.assertEqual(self.p.stanje, "napaka")
        self.assertEqual(self.neuspeli, [])               # film je ze tekel: ni »nepredvajljiv«

    def test_status_iz_sporocila(self):
        self.assertEqual(status_napake("Unknown Error (429), URL: https://x"), 429)
        self.assertEqual(status_napake("Could not resolve host"), 0)

    def test_razlicice_iz_vnosa(self):
        item = {"url": "https://cdn.test/a.mp4", "glave": {"Referer": "r"},
                "razlicice": [{"url": "https://cdn.test/a.mp4", "glave": {"Referer": "r"}, "tok": True},
                              {"url": "https://cdn.test/b", "glave": {"Referer": "q"}, "tok": True},
                              {"url": "https://stran.test/film/1", "vir": "Stran"}]}
        tok = tok_za_predvajalnik(item, "https://cdn.test/a.mp4")
        self.assertEqual(tok["glave"], {"Referer": "r"})
        self.assertEqual(tok["nadomestni"], [("https://cdn.test/b", {"Referer": "q"})])   # spletna stran ni tok


class IskanjeRokTests(unittest.TestCase):
    def setUp(self):
        self.mc = os_media.MediaCenter(tempfile.mkdtemp(), roots=[], secret_decryptor=lambda s: s)
        with self.mc._lock:
            data = self.mc._load()
            data.setdefault("osebni_strezniki", []).extend([
                {"id": "hiter", "ponudnik": "kodi", "ime": "Hiter", "url": "https://hiter.test"},
                {"id": "pocasen", "ponudnik": "kodi", "ime": "Pocasen", "url": "https://pocasen.test"}])
            self.mc._save(data)
        self.mc.rok_vira = 0.3

        def katalog(_ponudnik, url, server, _skrivnost, _q=""):
            if server["id"] == "pocasen":
                time.sleep(1.2)
            return [{"id": "v:" + server["id"], "naslov": "Dune " + server["ime"], "vrsta": "film",
                     "url": url + "/dune.mkv", "vir": server["ime"], "vir_id": server["id"]}]
        self.zakrpe = [mock.patch.object(media_servers, "catalog", katalog),
                       mock.patch.object(self.mc._zakoniti_viri, "get", lambda *a, **k: []),
                       mock.patch.object(self.mc, "_cinemeta_items", lambda *a: [])]
        for z in self.zakrpe:
            z.start()

    def tearDown(self):
        for z in self.zakrpe:
            z.stop()

    def test_pocasen_vir_ne_zadrzi_prvih_zadetkov(self):
        osvezitve = []
        zacetek = time.monotonic()
        prvi = self.mc.catalog_hitro("Dune", "vse", ob_osvezitvi=lambda k, r: osvezitve.append(r))
        cas = time.monotonic() - zacetek
        self.assertLess(cas, 1.0)                            # brez roka bi cakali 1,2 s na pocasni vir
        self.assertEqual([v["vir"] for v in prvi["vnosi"]], ["Hiter"])
        self.assertTrue(prvi["osvezujem"])
        konec = time.monotonic() + 5
        while not osvezitve and time.monotonic() < konec:
            time.sleep(0.05)
        self.assertEqual(sorted(v["vir"] for v in osvezitve[0]["vnosi"]), ["Hiter", "Pocasen"])
        # Isto iskanje znova: zdaj iz predpomnilnika vira, takoj in v celoti.
        zacetek = time.monotonic()
        self.assertEqual(len(self.mc.catalog("Dune")["vnosi"]), 2)
        self.assertLess(time.monotonic() - zacetek, 0.3)

    def test_brez_roka_pocaka_vse(self):
        self.mc.rok_vira = None
        self.assertEqual(len(self.mc.catalog("Dune")["vnosi"]), 2)


class IzbiraRazliciceTests(unittest.TestCase):
    def test_rocna_izbira_se_zapomni_za_naslov(self):
        mapa = tempfile.mkdtemp()
        mc = os_media.MediaCenter(mapa, roots=[])
        razlicice = [{"url": "https://cdn.test/720.mp4?sign=1", "dodatek": "Dodatek A", "opis": "720p", "tok": True,
                      "glave": {"Referer": "https://a.test/"}},
                     {"url": "https://drug.test/480.mp4?sign=1", "dodatek": "Dodatek B", "opis": "480p", "tok": True}]
        vnos = {"id": "x", "vrsta": "film", "url": razlicice[0]["url"], "glave": {"Referer": "https://a.test/"},
                "razlicice": razlicice, "imdb_id": "tt0000001"}
        mc._dynamic_items["x"] = vnos
        with mock.patch.object(mc, "resolve", lambda i, pripravi_torrent=True: mc._dynamic_items[i]), \
                mock.patch.object(mc, "_izmeri_ping", lambda u: None), mock.patch.object(mc._meritve, "ms", lambda u: None):
            seznam = mc.razlicice_naslova("x")["razlicice"]
        self.assertEqual([(r["vir"], r["privzeta"]) for r in seznam], [("Dodatek A", True), ("Dodatek B", False)])
        self.assertEqual([r["najhitrejsi"] for r in seznam], [False, False])      # odziv ni izmerjen: brez oznake
        pingi = {"cdn.test": 80.0, "drug.test": 20.0}
        with mock.patch.object(mc, "resolve", lambda i, pripravi_torrent=True: mc._dynamic_items[i]), \
                mock.patch.object(mc._meritve, "ms", lambda u: pingi.get(urllib.parse.urlsplit(u).hostname)), \
                mock.patch.object(mc._meritve, "zastarelo", lambda u: False):
            hitri = mc.razlicice_naslova("x")["razlicice"]
        self.assertEqual([(r["ping"], r["najhitrejsi"]) for r in hitri], [(80, False), (20, True)])
        self.assertNotIn("sign", str(seznam))                       # podpisani naslovi ne gredo na stran
        self.assertTrue(mc.izberi_razlicico("x", seznam[1]["podpis"]))
        izbran = mc.uporabi_izbiro(mc._dynamic_items["x"])
        self.assertEqual(izbran["url"], razlicice[1]["url"])
        self.assertNotIn("glave", izbran)                          # glave prve razlicice ne veljajo za drugo
        # Nov zagon, nov podpisan naslov iste razlicice: izbira velja (podpis ni naslov).
        mc2 = os_media.MediaCenter(mapa, roots=[])
        novo = dict(vnos, razlicice=[dict(razlicice[0], url="https://cdn.test/720.mp4?sign=2"),
                                     dict(razlicice[1], url="https://drug.test/480.mp4?sign=2")])
        self.assertEqual(mc2.uporabi_izbiro(novo)["url"], "https://drug.test/480.mp4?sign=2")
        # Izbira privzete pobrise rocno izbiro.
        mc2._dynamic_items["x"] = novo
        self.assertTrue(mc2.izberi_razlicico("x", ""))
        self.assertEqual(mc2.uporabi_izbiro(novo)["url"], novo["url"])


if __name__ == "__main__":
    unittest.main()
