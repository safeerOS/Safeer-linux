"""Dodatki Stremio z osebnim zetonom v naslovu (core/skrivni_dodatki.py, 25. 10. 2026).

Do tega popravka je bil naslov dodatka z zetonom (Webtor, Torrentio z debrid kljucem) na namizju shranjen v cistopisu
(media.json) in je z usklajevanjem virov (lists.get) sel VSEM napravam v Safeer Linku. Preizkusi so cisti: brez
omrezja (razen lokalnega streznika na 127.0.0.1), brez zbirke skrivnosti (sifrirnik je ponaredek). Zetoni so izmisljeni.
"""
import contextlib
import http.server
import io
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from core import media_servers, os_media, skrivni_dodatki as S, viri_sink

ZETON = "Zt9xQ2mW7kLp4RvB8nYc3HdF"
WEBTOR = "https://webtor.io/token/%s/stremio/manifest.json" % ZETON
WEBTOR_OSNOVA = "https://webtor.io/token/%s/stremio" % ZETON
TORRENTIO = "https://torrentio.strem.fun/sort=qualitysize|realdebrid=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ABCD/manifest.json"


def _sifriraj(s: str) -> str:
    return "enc:" + "".join(reversed(s))


def _desifriraj(s: str) -> str:
    assert s.startswith("enc:")
    return "".join(reversed(s[4:]))


def _vse_datoteke(mapa: str) -> str:
    besedilo = []
    for koren, _mape, datoteke in os.walk(mapa):
        for d in datoteke:
            besedilo.append(Path(koren, d).read_text(encoding="utf-8", errors="replace"))
    return "\n".join(besedilo)


class Osnova(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        S.pozabi_vse()

    def tearDown(self):
        S.pozabi_vse()
        S.nastavi_odklepalnik(None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def center(self, sifriraj=_sifriraj, desifriraj=_desifriraj):
        return os_media.MediaCenter(self.tmp, roots=[], secret_encryptor=sifriraj, secret_decryptor=desifriraj)

    def pisi_media(self, data: dict) -> None:
        Path(self.tmp, "media.json").write_text(json.dumps(data), encoding="utf-8")

    def preveri_brez_zetona(self, besedilo: str, kje: str) -> None:
        self.assertNotIn(ZETON, besedilo, kje)
        self.assertNotIn("/token/", besedilo, kje)


class Pravila(Osnova):
    def test_nadomestek_in_dejanski(self):
        z = S.odkleni(WEBTOR)
        self.assertTrue(z.startswith("https://webtor.io/" + S.OZNAKA))
        self.assertTrue(z.endswith("/manifest.json"))
        self.assertNotIn(ZETON, z)
        osnova = S.nadomestna_osnova(z)
        self.assertEqual(S.dejanski(osnova + "/stream/movie/tt1.json"), WEBTOR_OSNOVA + "/stream/movie/tt1.json")
        self.assertEqual(S.skrij(WEBTOR_OSNOVA + "/resolve/a.b.c"), osnova + "/resolve/a.b.c")
        # Drug dodatek z isto zacetno crko poti ni ta dodatek.
        self.assertEqual(S.skrij(WEBTOR_OSNOVA + "x/resolve/a"), WEBTOR_OSNOVA + "x/resolve/a")
        self.assertEqual(S.dejanski("https://cdn.example/a.mp4"), "https://cdn.example/a.mp4")

    def test_neodklenjen_nadomestek_ne_gre_na_streznik(self):
        z = S.v_nadomestek(WEBTOR)
        with self.assertRaises(S.NeodklenjenDodatek):
            S.dejanski(z)
        poslano = []
        with mock.patch("urllib.request.OpenerDirector.open", side_effect=lambda *a, **k: poslano.append(a)):
            with self.assertRaises(ValueError):
                media_servers._request(S.nadomestna_osnova(z) + "/manifest.json")
        self.assertEqual(poslano, [])

    def test_odklepalnik_odklene_ob_prvi_zahtevi(self):
        z = S.v_nadomestek(WEBTOR)
        S.nastavi_odklepalnik(lambda o: WEBTOR if o == S.nadomestna_osnova(z) else None)
        self.assertEqual(S.dejanski(z), WEBTOR)
        # Odklepalnik, ki vrne napacen naslov (drug dodatek), ne odklene.
        drug = S.v_nadomestek(TORRENTIO)
        S.nastavi_odklepalnik(lambda o: WEBTOR)
        with self.assertRaises(S.NeodklenjenDodatek):
            S.dejanski(drug)

    def test_zakrij_za_dnevnik(self):
        S.odkleni(WEBTOR)
        self.preveri_brez_zetona(S.zakrij("napaka pri %s/stream/x.json" % WEBTOR_OSNOVA), "zakrij znanega")
        self.preveri_brez_zetona(S.zakrij("drug https://webtor.io/token/%s/stremio/a" % ("Q" * 10 + "1" * 12)), "zakrij neznanega")

    def test_skrivni_dodatek_samo_https(self):
        self.assertTrue(S.veljaven_skrivni_dodatek(WEBTOR))
        self.assertFalse(S.veljaven_skrivni_dodatek(WEBTOR.replace("https://", "http://")))


class Lokalni(http.server.BaseHTTPRequestHandler):
    poti: list = []

    def do_GET(self):  # noqa: N802
        Lokalni.poti.append(self.path)
        self.send_response(404)
        self.end_headers()

    def log_message(self, *_a):
        pass


class Zahteva(Osnova):
    def test_zeton_nikoli_po_http(self):
        """Grok U5/N6: tudi »domace omrezje« po http ne - drugje je na tem naslovu tuj racunalnik."""
        streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Lokalni)
        nit = threading.Thread(target=streznik.serve_forever, daemon=True)
        nit.start()
        try:
            pravi = "http://127.0.0.1:%d/token/%s/stremio/manifest.json" % (streznik.server_address[1], ZETON)
            z = S.odkleni(pravi)
            Lokalni.poti = []
            with self.assertRaises(ValueError) as n:
                media_servers._request(S.nadomestna_osnova(z) + "/stream/movie/tt1.json")
            self.assertEqual(Lokalni.poti, [])                           # zahteva sploh ne gre ven
            self.preveri_brez_zetona(str(n.exception), "napaka")
            self.assertEqual(media_servers.tok_stanje(S.nadomestna_osnova(z) + "/x.mkv"), (False, 0, 0))
            self.assertEqual(Lokalni.poti, [])
        finally:
            streznik.shutdown()
            streznik.server_close()
            nit.join(5)

    def test_napake_ne_nosijo_zetona(self):
        """Grok U7/N14: HTTPError (naslov, glave), URLError in druge izjeme navzven samo brez zetona."""
        z = S.nadomestna_osnova(S.odkleni(WEBTOR))
        glave = __import__("email.message", fromlist=["Message"]).Message()
        glave["Location"] = WEBTOR_OSNOVA + "/drugam"
        glave["Retry-After"] = "7"
        for izjema in (urllib.error.HTTPError(WEBTOR_OSNOVA + "/stream/x.json", 429, "Too Many " + WEBTOR_OSNOVA, glave, None),
                       urllib.error.URLError("napaka za " + WEBTOR_OSNOVA + "/stream"),
                       ValueError("Streznik je ponudil " + WEBTOR_OSNOVA + "/x"),
                       OSError("TLS za " + WEBTOR_OSNOVA)):
            with self.subTest(izjema=type(izjema).__name__):
                with mock.patch("urllib.request.OpenerDirector.open", side_effect=izjema):
                    with self.assertRaises(Exception) as n:
                        media_servers._request(z + "/stream/x.json")
                e = n.exception
                self.assertIsInstance(e, type(izjema) if not isinstance(izjema, urllib.error.URLError) else urllib.error.URLError)
                besedila = [str(e), repr(e), str(getattr(e, "filename", "")), str(getattr(e, "reason", "")),
                            str(getattr(e, "headers", "") or "")]
                for b in besedila:
                    self.preveri_brez_zetona(b, type(izjema).__name__)
                self.assertIsNone(e.__cause__)
                if isinstance(e, urllib.error.HTTPError):
                    self.assertEqual((e.code, e.headers.get("Retry-After")), (429, "7"))

    def test_zaklenjena_zbirka_ne_sprasuje_ob_vsaki_zahtevi(self):
        """Grok N16: neuspel odklep velja 60 s - zaklenjena zbirka ne odpre okna za geslo ob vsaki zahtevi."""
        klici = []
        S.nastavi_odklepalnik(lambda o: klici.append(o))
        z = S.v_nadomestek(WEBTOR)
        for _ in range(3):
            with self.assertRaises(S.NeodklenjenDodatek):
                S.dejanski(z)
        self.assertEqual(len(klici), 1)


class TokoviSKljucem(Osnova):
    """Grok N2: Torrentio z debrid kljucem - tok `/resolve/realdebrid/<kljuc>/...` se ne zacne s predpono dodatka."""
    TOK = "https://torrentio.strem.fun/resolve/realdebrid/ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ABCD/" \
          "0123456789abcdef0123456789abcdef01234567/null/0/Film.2024.mkv"

    def test_tok_dobi_nadomestek(self):
        koren = S.nadomestna_osnova(S.odkleni(TORRENTIO))
        odgovor = json.dumps({"streams": [{"name": "Torrentio\n1080p", "title": "Film", "url": self.TOK}]}).encode()
        with mock.patch.object(media_servers, "_request", return_value=odgovor):
            tokovi = media_servers.stremio_tokovi(koren, "movie", "tt1")
        self.assertTrue(S.je_nadomestek(tokovi[0]["url"]))
        self.assertNotIn("ABCDEFGHIJKLMNOP", json.dumps(tokovi))
        self.assertEqual(S.dejanski(tokovi[0]["url"]), self.TOK)
        # Navaden dodatek: tok ostane, kot je (CDN z dolgim podpisom ni kljuc uporabnika).
        cdn = "https://cdn.example/d/ABCDEFGHIJ1234567890/film.mkv"
        odgovor = json.dumps({"streams": [{"name": "X", "url": cdn}]}).encode()
        with mock.patch.object(media_servers, "_request", return_value=odgovor):
            self.assertEqual(media_servers.stremio_tokovi("https://cinemeta.example", "movie", "tt1")[0]["url"], cdn)



class TokoviNeprepoznaniKljuc(Osnova):
    """Grok 19, M2: tok dodatka s kljucem, ki ga skrivna_predpona_toka ne prepozna (kratek kljuc za »/play/«, kljuc iz
    nastavitev base64), je prej sel s kljucem v predpomnilnik tokov, sondo zivosti in predvajalnik."""
    KRATEK = "Pm4Key7xQ2"
    DODATEK = "https://torrentio.strem.fun/premiumize=%s|sort=qualitysize/manifest.json" % KRATEK

    def tokovi(self, dodatek, odgovor):
        koren = S.nadomestna_osnova(S.odkleni(dodatek))
        with mock.patch.object(media_servers, "_request", return_value=json.dumps(odgovor).encode()), \
                contextlib.redirect_stdout(io.StringIO()):
            return media_servers.stremio_tokovi(koren, "movie", "tt1")

    def test_kratek_kljuc_v_toku_dobi_nadomestek(self):
        tok = "https://torrentio.strem.fun/play/%s/0123456789abcdef0123456789abcdef01234567/0/Film.mkv" % self.KRATEK
        tokovi = self.tokovi(self.DODATEK, {"streams": [
            {"name": "T", "url": tok, "subtitles": [{"url": "https://torrentio.strem.fun/sub/%s/1.srt" % self.KRATEK, "lang": "sl"}]},
            {"name": "Javni", "url": "https://cdn.example/a.mp4"}]})
        self.assertNotIn(self.KRATEK, json.dumps(tokovi))
        self.assertTrue(S.je_nadomestek(tokovi[0]["url"]))
        self.assertEqual(S.dejanski(tokovi[0]["url"]), tok)
        self.assertEqual(tokovi[1]["url"], "https://cdn.example/a.mp4")     # tok brez kljuca ostane, kot je
        # Koncni naslov sonde, ki nosi kljuc, ne gre v predvajalnik (os_media._razresi_skrivne_tokove).
        self.assertTrue(S.nosi_skrivnost("https://cdn.example/x/%s/f.mkv" % self.KRATEK, S.dejanski(tokovi[0]["url"])))
        self.assertFalse(S.nosi_skrivnost("https://cdn.example/x/f.mkv", S.dejanski(tokovi[0]["url"])))

    def test_kljuc_iz_nastavitev_base64(self):
        import base64
        kljuc = "Tb5Key9Zq1Lm"
        dodatek = "https://addon.example/%s/manifest.json" % base64.urlsafe_b64encode(
            json.dumps({"torboxKey": kljuc, "jezik": "sl"}).encode()).decode().rstrip("=")
        self.assertIsNotNone(S.skrivna_predpona_dodatka(dodatek))
        tokovi = self.tokovi(dodatek, {"streams": [{"name": "X", "url": "https://dl.addon.example/get?u=%s&f=1" % kljuc}]})
        self.assertNotIn(kljuc, json.dumps(tokovi))
        self.assertTrue(S.je_nadomestek(tokovi[0]["url"]))


class WebtorKratkaPovezava(Osnova):
    """Webtor, dodan s kratko povezavo »https://webtor.io/s/<koda>/manifest.json« (izmerjeno 25. 10. 2026 na Windows in
    na prenosniku): tokovi so »/token/<t>/stremio/resolve/<JWT>« in se ne zacnejo s predpono dodatka. JWT (exp, hash,
    idx) ni osebni zeton: nadomestek mora ohraniti »/resolve/<JWT>«, sicer tok ni prepoznan kot Webtor."""
    KRATKA = "https://webtor.io/s/k7Qp2x/manifest.json"
    JWT = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTMwMDAwMDAsImhhc2giOiJhNzc5ZmE3NThmMjIyOTU4NmVlYmMyZTU5Nj"
           "BlYjMyZmU1NjU5NTk2IiwiaWR4IjowfQ.c2lnbmF0dXJhLWJyZXotc21pc2xh")
    TOK = "https://webtor.io/token/%s/stremio/resolve/%s" % (ZETON, JWT)

    def test_nadomestek_ohrani_resolve(self):
        from core import webtor as W
        koren = S.nadomestna_osnova(S.odkleni(self.KRATKA))
        odgovor = json.dumps({"streams": [{"name": "[WT]", "title": "Film", "url": self.TOK}]}).encode()
        with mock.patch.object(media_servers, "_request", return_value=odgovor):
            tokovi = media_servers.stremio_tokovi(koren, "movie", "tt1")
        u = tokovi[0]["url"]
        self.assertTrue(S.je_nadomestek(u))
        self.assertNotIn(ZETON, json.dumps(tokovi))
        self.assertTrue(u.endswith("/resolve/" + self.JWT), u)
        self.assertTrue(W.je_resolve_naslov(u))
        self.assertEqual(S.dejanski(u), self.TOK)

    def test_koncni_naslov_z_jwt_ni_zeton(self):
        # Pot kot pri predvajanju: tok gre skozi stremio_tokovi (skrij_tok si zapomni predpono), nato sonda preveri,
        # ali koncni naslov nosi zeton (nosi_skrivnost) - JWT ni zeton, osebni zeton pa je.
        koren = S.nadomestna_osnova(S.odkleni(self.KRATKA))
        odgovor = json.dumps({"streams": [{"name": "[WT]", "title": "Film", "url": self.TOK}]}).encode()
        with mock.patch.object(media_servers, "_request", return_value=odgovor):
            media_servers.stremio_tokovi(koren, "movie", "tt1")
        koncni = "https://abra--1.api.cosmic-crab.buzz/%s/Film.mp4" % self.JWT
        self.assertFalse(S.nosi_skrivnost(koncni, self.TOK))
        self.assertTrue(S.nosi_skrivnost("https://abra--1.api.cosmic-crab.buzz/%s/Film.mp4" % ZETON, self.TOK))


class Dodajanje(Osnova):
    def dodaj(self, mc, url):
        with mock.patch.object(media_servers, "stremio_preveri", return_value=""), \
                mock.patch.object(media_servers, "stremio_manifest", return_value={"id": "org.stremio.webtor.io", "name": "Webtor"}):
            return mc.add_server("stremio", "", url, "", "")

    def test_dodan_dodatek_ni_v_cistopisu(self):
        mc = self.center()
        izid = self.dodaj(mc, WEBTOR)
        self.assertTrue(izid["ok"], izid)
        self.preveri_brez_zetona(json.dumps(izid), "odgovor strani")
        zapis = json.loads(Path(self.tmp, "media.json").read_text(encoding="utf-8"))["osebni_strezniki"][0]
        self.assertTrue(S.je_nadomestek(zapis["url"]))
        self.assertEqual(_desifriraj(zapis["url_enc"]), WEBTOR)
        self.preveri_brez_zetona(json.dumps(mc.sources()), "sources")
        self.assertEqual([v.get("prikaz") for v in mc.sources()], ["https://webtor.io/…/manifest.json"])
        self.preveri_brez_zetona(json.dumps(mc.viri_izvoz()), "lists.get")
        self.assertEqual(mc.viri_izvoz()["sources"], [])
        self.preveri_brez_zetona(_vse_datoteke(self.tmp), "datoteke")
        # Omrezni klic z nadomestkom gre na pravi naslov.
        poslano = []
        with mock.patch("urllib.request.OpenerDirector.open", side_effect=lambda r, timeout=0: poslano.append(r.full_url) or (_ for _ in ()).throw(OSError("x"))):
            with self.assertRaises(OSError):
                media_servers._request(S.nadomestna_osnova(zapis["url"]) + "/manifest.json")
        self.assertEqual(poslano, [WEBTOR])

    def test_brez_zbirke_skrivnosti_ne_shrani(self):
        def ni_zbirke(s):
            if not s:
                return ""       # kot core/os_katalog.skrij: prazno ostane prazno (dodatki nimajo gesla)
            raise RuntimeError("Zbirka skrivnosti ni na voljo.")
        mc = self.center(sifriraj=ni_zbirke)
        izid = self.dodaj(mc, WEBTOR)
        self.assertFalse(izid["ok"])
        self.assertIn("zbirka gesel", izid["napaka"])
        self.assertEqual(mc.sources(), [])
        self.preveri_brez_zetona(_vse_datoteke(self.tmp), "datoteke")

    def test_navaden_dodatek_ostane_enak(self):
        mc = self.center()
        with mock.patch.object(mc, "_vir_potrjen"):
            izid = self.dodaj(mc, "https://v3-cinemeta.strem.io/manifest.json")
        self.assertTrue(izid["ok"])
        self.assertEqual(mc.sources()[0]["url"], "https://v3-cinemeta.strem.io/manifest.json")
        self.assertNotIn("url_enc", json.loads(Path(self.tmp, "media.json").read_text())["osebni_strezniki"][0])

    def test_odstranitev_ne_gre_v_link(self):
        mc = self.center()
        self.dodaj(mc, WEBTOR)
        ident = mc.sources()[0]["id"]
        self.assertTrue(mc.remove_source(ident))
        self.assertEqual(mc.viri_izvoz()["sources_deleted"], {})
        self.preveri_brez_zetona(_vse_datoteke(self.tmp), "datoteke")


class Prehod(Osnova):
    """Dodatek, shranjen pred popravkom (zeton v media.json in v drugih datotekah mape)."""

    def stari(self):
        self.pisi_media({"viri": [], "osebni_strezniki": [
            {"id": "streznik-1", "vrsta": "streznik", "ponudnik": "stremio", "ime": "Webtor", "url": WEBTOR,
             "secret_enc": "", "zaseben": False, "dodan": 5},
            {"id": "streznik-2", "vrsta": "streznik", "ponudnik": "stremio", "ime": "Cinemeta",
             "url": "https://v3-cinemeta.strem.io/manifest.json", "secret_enc": "", "zaseben": False, "dodan": 6}]})
        Path(self.tmp, "media-predpomnilnik.json").write_text(json.dumps(
            {"vnosi": [{"id": "x", "url": "stremio:%s|movie|tt1" % WEBTOR_OSNOVA, "stremio": {"koren": WEBTOR_OSNOVA}}]}),
            encoding="utf-8")
        Path(self.tmp, "viri_sink.json").write_text(json.dumps(
            {"izbrisani": {"stremio|" + TORRENTIO: 7, "stremio|https://a.example/manifest.json": 8}, "zavrnjeni": {}}),
            encoding="utf-8")
        Path(self.tmp, "viri_za_naprave.json").write_text(json.dumps(
            {"sources": [{"tip": "stremio", "naslov": WEBTOR, "ime": "Webtor", "cas": 5}], "sources_deleted": {}}),
            encoding="utf-8")

    def test_prehod_sifrira_in_pocisti_vse_datoteke(self):
        self.stari()
        mc = self.center()
        zapis = mc._load()["osebni_strezniki"][0]
        self.assertTrue(zapis["skriven"])
        self.assertEqual(_desifriraj(zapis["url_enc"]), WEBTOR)
        vse = _vse_datoteke(self.tmp)
        self.preveri_brez_zetona(vse.replace(zapis["url_enc"], ""), "datoteke po prehodu")
        self.assertIn(S.nadomestna_osnova(zapis["url"]), Path(self.tmp, "media-predpomnilnik.json").read_text())
        izvoz = mc.viri_izvoz()
        self.assertEqual([v["naslov"] for v in izvoz["sources"]], ["https://v3-cinemeta.strem.io/manifest.json"])
        # Izbris dodatka, ki ni znan javen, gre samo ozjemu krogu (mc-iptv-serije, pregled 51; zdruzitev 26. 10. 2026).
        self.assertEqual(izvoz["sources_deleted"], {})
        self.assertEqual(mc.viri_izvoz(ozji=True)["sources_deleted"], {"stremio|https://a.example/manifest.json": 8})
        self.assertNotIn("webtor", Path(self.tmp, "viri_za_naprave.json").read_text())
        # Drugi zagon: nic novega, nadomestek ostane.
        os_media.MediaCenter(self.tmp, roots=[], secret_encryptor=_sifriraj, secret_decryptor=_desifriraj)
        self.assertEqual(json.loads(Path(self.tmp, "media.json").read_text())["osebni_strezniki"][0]["url"], zapis["url"])

    def test_prehod_brez_zbirke_skrivnosti(self):
        """Grok U6: ce sifriranje ne uspe, pravi naslov ne gre na nova mesta; Moji viri povedo, da ni zavarovan."""
        self.stari()

        def ni_zbirke(_s):
            raise RuntimeError("Zbirka skrivnosti ni na voljo.")
        izhod = io.StringIO()
        with contextlib.redirect_stdout(izhod), contextlib.redirect_stderr(izhod):
            mc = self.center(sifriraj=ni_zbirke)
        self.preveri_brez_zetona(izhod.getvalue(), "dnevnik")
        zapis = mc._load()["osebni_strezniki"][0]
        self.assertTrue(zapis["nezavarovan"])
        self.assertNotIn("url_enc", zapis)
        vir = mc.sources()[0]
        self.assertTrue(vir["nezavarovan"])
        self.preveri_brez_zetona(vir["prikaz"], "prikaz")
        self.preveri_brez_zetona(json.dumps(mc.viri_izvoz()), "lists.get")
        self.preveri_brez_zetona(Path(self.tmp, "viri_za_naprave.json").read_text(), "izvoz za Control")

    def test_dnevnik_brez_zetona(self):
        self.stari()
        izhod = io.StringIO()
        with contextlib.redirect_stdout(izhod), contextlib.redirect_stderr(izhod), self.assertLogs(level="DEBUG") as dnevnik:
            mc = self.center()
            import logging
            logging.getLogger("preizkus").debug("konec")
            with mock.patch("urllib.request.OpenerDirector.open", side_effect=OSError("ni omrezja")):
                with contextlib.suppress(Exception):
                    media_servers._request(S.nadomestna_osnova(mc.sources()[0]["url"]) + "/manifest.json")
        self.preveri_brez_zetona(izhod.getvalue() + "\n".join(dnevnik.output), "dnevnik")


class PrehodPonovljiv(Osnova):
    """Grok N1, N3, N11, N12, N13: prehod se ponovi, dokler ne uspe povsod; tudi podmape, druge oblike in odstranjeni."""
    stari = Prehod.stari

    def test_prekinjen_prehod_se_ponovi(self):
        self.stari()
        policke = Path(self.tmp, "police.json")
        policke.write_text(json.dumps({"x": {"koren": WEBTOR_OSNOVA}}), encoding="utf-8")
        pravi_replace = os.replace

        def zaklenjena(a, b, *k):
            if str(b).endswith("police.json"):
                raise PermissionError("zaklenjeno")       # Windows: datoteko drzi drug proces
            return pravi_replace(a, b, *k)
        with mock.patch("os.replace", side_effect=zaklenjena), contextlib.redirect_stdout(io.StringIO()):
            mc = self.center()
        self.assertIn(ZETON, policke.read_text())                       # ta datoteka se ni ociscena ...
        self.assertEqual(len(mc._load().get("skrivni_prehod") or []), 1)  # ... in prehod caka
        self.assertNotIn(ZETON, Path(self.tmp, "media.json").read_text().replace(mc._load()["osebni_strezniki"][0]["url_enc"], ""))
        self.assertEqual(list(Path(self.tmp).glob("*.prehod")), [])       # zacasna datoteka ne ostane
        with contextlib.redirect_stdout(io.StringIO()):
            mc = self.center()                                         # naslednji zagon: prava predpona iz zbirke
        self.assertNotIn(ZETON, policke.read_text())
        self.assertNotIn("skrivni_prehod", mc._load())

    def _prekinjen_prvi_zagon(self, ime: str, vsebina: str) -> Path:
        """Prvi zagon: prehod druge datoteke `ime` (oblika zunaj vzorcev _RX_KORENI) ne uspe - prehod caka."""
        self.stari()
        druga = Path(self.tmp, ime)
        druga.write_text(vsebina, encoding="utf-8")
        pravi_replace = os.replace

        def zaklenjena(a, b, *k):
            if str(b).endswith(ime):
                raise PermissionError("zaklenjeno")
            return pravi_replace(a, b, *k)
        with mock.patch("os.replace", side_effect=zaklenjena), contextlib.redirect_stdout(io.StringIO()):
            mc = self.center()
        self.assertEqual(len(mc._load().get("skrivni_prehod") or []), 1)
        return druga

    def test_zaklenjena_zbirka_ob_ponovitvi_prehod_caka(self):
        """Grok 19, M1: ob naslednjem zagonu je zbirka skrivnosti zaklenjena - prava predpona ni znana. Prej se je oznaka
        skrivni_prehod vseeno izbrisala in zeton v obliki zunaj vzorcev je ostal v cistopisu za vedno."""
        druga = self._prekinjen_prvi_zagon("tokovi.json", json.dumps({"url": WEBTOR_OSNOVA + "/stream/movie/tt1.json"}))

        def zaklenjena(_s):
            raise RuntimeError("zbirka skrivnosti je zaklenjena")
        with contextlib.redirect_stdout(io.StringIO()):
            mc = self.center(desifriraj=zaklenjena)
        self.assertIn(ZETON, druga.read_text())                         # predpone ni bilo mogoce dobiti ...
        self.assertEqual(len(mc._load().get("skrivni_prehod") or []), 1)  # ... zato prehod caka naprej
        with contextlib.redirect_stdout(io.StringIO()):
            mc = self.center()                                         # odklenjena: prehod se konca
        self.assertNotIn(ZETON, druga.read_text())
        self.assertNotIn("skrivni_prehod", mc._load())

    def test_odstranitev_z_zaklenjeno_zbirko_ohrani_sifriran_naslov(self):
        """Grok 19, M1: dodatek odstranjen, ko prehod se ni koncan in je zbirka zaklenjena - sifriran naslov ostane
        (os_katalog ga ne pozabi), naslednji zagon prehod konca in sele nato naslov pozabi."""
        from core import os_katalog
        druga = self._prekinjen_prvi_zagon("tokovi.json", json.dumps({"url": WEBTOR_OSNOVA + "/stream/movie/tt1.json"}))

        def zaklenjena(_s):
            raise RuntimeError("zbirka skrivnosti je zaklenjena")
        pozabljeni: list = []
        with contextlib.redirect_stdout(io.StringIO()):
            mc = os_media.MediaCenter(self.tmp, roots=[], secret_encryptor=_sifriraj, secret_decryptor=zaklenjena,
                                      secret_forget=pozabljeni.append)
        enc = mc._load()["osebni_strezniki"][0]["url_enc"]
        k = os_katalog.Katalog.__new__(os_katalog.Katalog)
        k._zaklep = threading.RLock()
        k._mc = mc
        with mock.patch.object(os_katalog, "pozabi", side_effect=pozabljeni.append), contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(k._odstrani_vir(["streznik-1"]))
        self.assertEqual(pozabljeni, [])                               # naslov ostane, dokler ga prehod potrebuje
        self.assertEqual(mc.skrivnosti_v_prehodu(), {enc})
        self.assertIn(ZETON, druga.read_text())
        with contextlib.redirect_stdout(io.StringIO()):
            mc = os_media.MediaCenter(self.tmp, roots=[], secret_encryptor=_sifriraj, secret_decryptor=_desifriraj,
                                      secret_forget=pozabljeni.append)
        self.assertNotIn(ZETON, druga.read_text())
        self.assertNotIn("skrivni_prehod", mc._load())
        self.assertNotIn("skrivni_prehod_enc", mc._load())
        self.assertEqual(pozabljeni, [enc])                            # prehod koncan: zdaj pozabljen

    def test_padec_pred_zapisom_media_json(self):
        self.stari()
        pozabljeni = []
        with mock.patch.object(os_media.MediaCenter, "_save", side_effect=OSError("disk poln")), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(OSError):
                os_media.MediaCenter(self.tmp, roots=[], secret_encryptor=_sifriraj, secret_decryptor=_desifriraj,
                                     secret_forget=pozabljeni.append)
        self.assertEqual(len(pozabljeni), 1)                           # sifriran zapis ne ostane sirota v zbirki
        with contextlib.redirect_stdout(io.StringIO()):
            mc = self.center()
        self.preveri_brez_zetona(_vse_datoteke(self.tmp).replace(mc._load()["osebni_strezniki"][0]["url_enc"], ""),
                                 "po ponovnem zagonu")

    def test_podmape_druge_oblike_odstranjeni_in_dovoljenja(self):
        self.stari()
        Path(self.tmp, "predpomnilnik").mkdir()
        Path(self.tmp, "predpomnilnik", "tokovi.json").write_text(
            '{"u": "stremio:%s|movie|tt2"}' % WEBTOR_OSNOVA.replace("/", "\\/"), encoding="utf-8")
        latin = Path(self.tmp, "stari.bin")
        latin.write_bytes(b"\xff\xfe stremio:" + WEBTOR_OSNOVA.encode() + b"|movie|tt3 \xe9")
        os.chmod(latin, 0o600)
        # Odstranjen dodatek: samo se kljuc izbrisa in katalog ga omenjata.
        drug = "https://addon.example.org/torbox=Q8zR2LmX0pVt7WbN4kHs1Dxx"
        Path(self.tmp, "viri_sink.json").write_text(json.dumps({"izbrisani": {"stremio|%s/manifest.json" % drug: 7},
                                                                "zavrnjeni": {}}), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            mc = self.center()
        vse = _vse_datoteke(self.tmp).replace(mc._load()["osebni_strezniki"][0]["url_enc"], "")
        self.preveri_brez_zetona(vse, "vse datoteke")
        self.assertNotIn("Q8zR2LmX0pVt7WbN4kHs1Dxx", vse)
        self.assertNotIn(ZETON.encode(), latin.read_bytes())
        if os.name != "nt":     # Windows nima bitov POSIX (dovoljenja so ACL)
            self.assertEqual(os.stat(latin).st_mode & 0o777, 0o600)

    def test_nezavarovan_ne_gre_na_stran_tokovi_dobijo_nadomestek(self):
        self.stari()

        def ni_zbirke(_s):
            raise RuntimeError("Zbirka skrivnosti ni na voljo.")
        with contextlib.redirect_stdout(io.StringIO()):
            mc = self.center(sifriraj=ni_zbirke)
        self.preveri_brez_zetona(json.dumps(mc.sources()), "sources (nezavarovan)")
        self.assertTrue(S.je_nadomestek(S.skrij(WEBTOR_OSNOVA + "/resolve/a.b.c")))

    def test_razkrit_dodatek_pove_uporabniku(self):
        """Grok N8: dodatek, ki je pred popravkom sel napravam v Linku (zaseben=False), dobi oznako za Moji viri."""
        self.stari()
        with contextlib.redirect_stdout(io.StringIO()):
            mc = self.center()
        vir = next(v for v in mc.sources() if v.get("skriven"))
        self.assertTrue(vir["razkrit"])


class DodajanjeVarno(Osnova):
    dodaj = Dodajanje.dodaj
    def test_http_dodatek_z_zetonom_zavrnjen(self):
        izid = self.dodaj(self.center(), "http://192.168.1.20:7000/token/%s/stremio/manifest.json" % ZETON)
        self.assertFalse(izid["ok"])
        self.assertIn("HTTPS", izid["napaka"])
        self.preveri_brez_zetona(_vse_datoteke(self.tmp), "datoteke")

    def test_podvojen_ne_pusti_sirote(self):
        sifrirani, pozabljeni = [], []
        mc = os_media.MediaCenter(self.tmp, roots=[], secret_encryptor=lambda v: sifrirani.append(v) or _sifriraj(v),
                                  secret_decryptor=_desifriraj, secret_forget=pozabljeni.append)
        self.assertTrue(self.dodaj(mc, WEBTOR)["ok"])
        self.assertFalse(self.dodaj(mc, WEBTOR)["ok"])
        self.assertEqual(len([v for v in sifrirani if v]), 1)              # drugic sploh ne sifrira
        self.assertEqual(pozabljeni, [])


class UsklajevanjeVirov(unittest.TestCase):
    def test_tuj_skrivni_dodatek_ne_pride_sem(self):
        self.assertIsNone(viri_sink.cist_vir({"tip": "stremio", "ime": "Webtor", "naslov": WEBTOR, "cas": 1}))
        self.assertIsNone(viri_sink.cist_vir({"tip": "stremio", "ime": "T", "naslov": S.v_nadomestek(TORRENTIO), "cas": 1}))
        self.assertIsNotNone(viri_sink.cist_vir({"tip": "stremio", "ime": "C", "naslov": "https://v3-cinemeta.strem.io/manifest.json"}))
        self.assertIsNotNone(viri_sink.cist_vir({"tip": "podkast", "ime": "P", "naslov": "https://feeds.example.org/oddaja.xml"}))

    def test_izbris_s_skrivnostjo_ne_velja(self):
        izbrisi = viri_sink.cisti_izbrisi({"stremio|" + WEBTOR: 5, "stremio|https://a.example/manifest.json": 6})
        self.assertEqual(izbrisi, {"stremio|https://a.example/manifest.json": 6})


if __name__ == "__main__":
    unittest.main()
