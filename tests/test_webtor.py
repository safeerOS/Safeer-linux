"""Webtor rezerva na namizju (core/webtor.py, core/os_media.py, 25. 10. 2026).

Cisti preizkusi brez interneta: streznik je ponaredek (zahteva_fn), razresevanje imen za naslove IP je pravo (brez
omrezja). Varnost iz neodvisnega pregleda Androida (Grok U4): sonda ne sme slediti preusmeritvi na http, v zanko ali v
domace omrezje, najvec 5 preusmeritev; predvajalnik dobi koncni preverjeni naslov in ne sledi novim preusmeritvam;
zeton nikoli v dnevnik ali predvajalnik. Zeton v preizkusu je izmisljen.
"""
import contextlib
import io
import json
import shutil
import socket
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from core import debrid_pravila, media_servers, os_media, os_scit, skrivni_dodatki as S, webtor as W
from core.os_katalog import nacin_predvajanja, tok_za_predvajalnik
from core.os_predvajalnik import Predvajalnik, Skladba

ZETON = "Zt9xQ2mW7kLp4RvB8nYc3HdF"
DODATEK = "https://webtor.io/token/%s/stremio/manifest.json" % ZETON
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJoYXNoIjoiYWJhYmFiYWJhYmFiYWJhYmFiYWJhYmFiYWJhYmFiYWJhYmFiYWJhYiIsImlkeCI6MH0.c2lnbmF0dXJh"
RESOLVE = "https://webtor.io/token/%s/stremio/resolve/%s" % (ZETON, JWT)
CDN = "https://abra--x1.api.cosmic-crab.buzz/abababab/film.mkv"
JAVNI_IP = "93.184.216.34"


MKV = bytes.fromhex("1a45dfa3") + b"\x00" * 4092
MP4 = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 4084
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 4086
MP3 = b"ID3\x04\x00" + b"\x00" * 4091
FILM = "bytes 0-4095/7043825664"           # Content-Range: 6,5 GB


class Streznik:
    """Ponarejen splet: naslov -> (koda, Location[, prvi bajti, Content-Type]). Zapise, kam se je sonda povezala."""

    def __init__(self, odgovori: dict):
        self.odgovori = odgovori
        self.klici: list = []

    def zahteva(self, naslov, gostitelj, ip, vrata, rok):
        self.klici.append((naslov, gostitelj, ip, vrata))
        odgovor = self.odgovori.get(naslov, (404, None))
        koda, kam = odgovor[:2]
        bajti, vsebina = odgovor[2:4] if len(odgovor) > 2 else ((MKV, "video/x-matroska") if 200 <= koda <= 299 else (b"", ""))
        obseg = odgovor[4] if len(odgovor) > 4 else FILM
        return koda, kam, bajti, {"content-type": vsebina, "content-range": obseg, "content-length": str(len(bajti))}


def javni(gostitelj, vrata):
    """Ime -> javni naslov; naslov IP ostane, kot je (preverba ga zavrne, ce ni javen)."""
    try:
        socket.inet_pton(socket.AF_INET6 if ":" in gostitelj else socket.AF_INET, gostitelj)
        return W.razresi(gostitelj, vrata)
    except OSError as e:
        if isinstance(e, W.ZasebenNaslov):
            raise
        return JAVNI_IP


class Sonda(unittest.TestCase):
    def sonda(self, odgovori, url=RESOLVE, **k):
        s = Streznik(odgovori)
        return W.sonda(url, k.pop("rok_ms", W.PRVI_BAJT_MS), razresi_fn=k.pop("razresi_fn", javni), zahteva_fn=s.zahteva, **k), s

    def test_glave_toka_samo_gostitelju_toka(self):
        """Grok 19, M3: glave toka (proxyHeaders) dobi sonda na gostitelju toka (brez Referer strezniki vracajo 429), po
        preusmeritvi na drug gostitelj ne; Authorization, Cookie in glave s prelomom vrstice nikoli."""
        klici = []
        s = Streznik({RESOLVE: (302, CDN), CDN: (206, None)})

        def zahteva(naslov, g, ip, vrata, rok, glave=None):
            klici.append((g, dict(glave or {})))
            return s.zahteva(naslov, g, ip, vrata, rok)
        izid = W.sonda(RESOLVE, razresi_fn=javni, zahteva_fn=zahteva,
                       glave={"Referer": "https://dodatek.test/", "Authorization": "Bearer x", "Cookie": "a=b",
                              "Origin": "https://a.test\r\nX-Vrinjeno: 1"})
        self.assertEqual(izid.izid, W.PREDVAJAJ)
        self.assertEqual(klici, [("webtor.io", {"Referer": "https://dodatek.test/"}), ("abra--x1.api.cosmic-crab.buzz", {})])

    def test_preusmeritev_na_cdn_da_koncni_naslov(self):
        izid, s = self.sonda({RESOLVE: (302, CDN), CDN: (206, None)})
        self.assertEqual(izid.izid, W.PREDVAJAJ)
        self.assertEqual(izid.koncni, CDN)
        # Povezava gre na preverjeni naslov IP (brez druge razresitve), ime je za SNI in Host.
        self.assertEqual([k[1:3] for k in s.klici], [("webtor.io", JAVNI_IP), ("abra--x1.api.cosmic-crab.buzz", JAVNI_IP)])

    def test_preusmeritev_na_http_zavrnjena(self):
        izid, s = self.sonda({RESOLVE: (302, "http://abra--x1.api.cosmic-crab.buzz/f.mkv")})
        self.assertEqual((izid.izid, izid.koncni, izid.razlog), (W.NAPAKA, None, "ni_https"))
        self.assertEqual(len(s.klici), 1)

    def test_preusmeritev_v_zanko_in_domace_omrezje_zavrnjena(self):
        for kam in ("https://127.0.0.1/x", "https://127.1.2.3:8443/x", "https://192.168.1.10/cgi-bin/x", "https://10.0.0.1/",
                    "https://172.16.5.4/", "https://169.254.169.254/latest", "https://100.64.0.1/", "https://0.0.0.0/",
                    "https://[::1]/x", "https://[fd00::1]/x", "https://[fe80::1]/x", "https://[::ffff:192.168.1.1]/x",
                    "https://[2002:c0a8:0101::1]/x", "https://224.0.0.1/"):
            with self.subTest(kam=kam):
                izid, s = self.sonda({RESOLVE: (302, kam)})
                self.assertEqual((izid.izid, izid.razlog), (W.NAPAKA, "zasebni_naslov"))
                self.assertEqual(len(s.klici), 1, "na zasebni naslov ni zahteve")

    def test_ime_z_zasebnim_naslovom_zavrnjeno(self):
        # DNS da javni in zasebni naslov: zavrnemo (povezava bi lahko sla na zasebnega).
        with mock.patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", (JAVNI_IP, 443)), (2, 1, 6, "", ("192.168.1.1", 443))]):
            izid, s = self.sonda({RESOLVE: (302, "https://notranji.example/f")}, razresi_fn=W.razresi)
        self.assertEqual(izid.razlog, "zasebni_naslov")
        self.assertEqual(s.klici, [])       # ze webtor.io se je razresil v zasebnega (isti ponaredek)

    def test_najvec_pet_preusmeritev(self):
        veriga = ["https://webtor.io/token/%s/stremio/resolve/%d" % (ZETON, i) for i in range(8)]
        odgovori = {veriga[i]: (302, veriga[i + 1]) for i in range(7)}
        odgovori[veriga[5]] = (206, None)
        izid, _s = self.sonda(odgovori, url=veriga[0])
        self.assertEqual(izid.izid, W.PREDVAJAJ)          # 5 preusmeritev je dovoljenih
        odgovori[veriga[5]] = (302, veriga[6])
        odgovori[veriga[6]] = (206, None)
        izid, s = self.sonda(odgovori, url=veriga[0])
        self.assertEqual((izid.izid, izid.razlog), (W.NAPAKA, "preusmeritve"))
        self.assertEqual(len(s.klici), 6)

    def test_uporabnik_v_naslovu_in_poševnica_zavrnjena(self):
        for kam in ("https://u:g@abra--x1.api.cosmic-crab.buzz/f", "https://zlo.example\\@webtor.io/f"):
            with self.subTest(kam=kam):
                izid, s = self.sonda({RESOLVE: (302, kam)})
                self.assertEqual(izid.razlog, "ni_https")
                self.assertEqual(len(s.klici), 1)

    def test_rok_in_kode(self):
        cas = iter([0.0, 0.0, 0.0, 20.0, 20.0, 20.0])
        izid, _s = self.sonda({RESOLVE: (302, CDN), CDN: (206, None)}, ura=lambda: next(cas))
        self.assertEqual(izid.izid, W.PREPOCASI)
        for koda, pricakovano in ((402, W.NI_PAKETA), (404, W.NI_TOKA), (429, W.OMEJITEV), (500, W.NAPAKA)):
            izid, _s = self.sonda({RESOLVE: (koda, None)})
            self.assertEqual(izid.izid, pricakovano)

    def test_206_ni_dovolj_vsebina_mora_biti_video(self):
        """Android 25. 10. popoldne: sonda je videla 206, predvajalnik pa je dobil naslovnico JPEG, MP3 ali vzorec."""
        for bajti, vsebina, obseg, pricakovano in (
                (JPEG, "image/jpeg", FILM, W.NI_VIDEO), (MP3, "audio/mpeg", FILM, W.NI_VIDEO),
                (JPEG, "application/octet-stream", FILM, W.NI_VIDEO), (MP3, "application/octet-stream", FILM, W.NI_VIDEO),
                (b"<html>" + b" " * 4090, "text/html", FILM, W.NI_VIDEO), (MKV, "audio/x-matroska", FILM, W.NI_VIDEO),
                (MKV, "video/x-matroska", "bytes 0-4095/60000000", W.PREMAJHNA)):
            with self.subTest(vsebina=vsebina, bajti=bajti[:4]):
                izid, _s = self.sonda({RESOLVE: (302, CDN), CDN: (206, None, bajti, vsebina, obseg)}, pricakovano_gb=6.56)
                self.assertEqual((izid.izid, izid.koncni, izid.vsebina), (W.NAPACNA_VSEBINA, None, pricakovano))
        for bajti, vsebina, vrsta in ((MKV, "video/x-matroska", "MKV"), (MP4, "video/mp4", "MP4"),
                                      (MKV, "application/octet-stream", "MKV"), (MP4, "", "MP4")):
            with self.subTest(vsebina=vsebina):
                izid, _s = self.sonda({RESOLVE: (302, CDN), CDN: (206, None, bajti, vsebina)})
                self.assertEqual((izid.izid, izid.posoda, izid.koncni), (W.PREDVAJAJ, vrsta, CDN))
        slika = "https://abra--x1.api.cosmic-crab.buzz/abab/cover.jpg"
        izid, _s = self.sonda({RESOLVE: (302, slika), slika: (206, None, MKV, "application/octet-stream")})
        self.assertEqual((izid.izid, izid.vsebina), (W.NAPACNA_VSEBINA, W.NI_VIDEO))

    def test_datoteka_toka(self):
        """Webtor ob izpuscenem fileIdx predvaja PRVO datoteko torrenta (idx 0) - brez imena je to negotovo."""
        self.assertEqual(W.datoteka(0, "", None, ""), W.NEGOTOVA)
        self.assertEqual(W.datoteka(0, "Film.1948.1080p.mkv", None, ""), W.VIDEO)
        self.assertEqual(W.datoteka(3, "poster.jpg", 3, "Film.mkv"), W.NI_VIDEO)
        self.assertEqual(W.datoteka(-1, "", None, ""), W.NAJVECJI)
        self.assertEqual(W.datoteka(W.IDX_NEZNAN, "Film.mkv", 0, "Film.mkv"), W.NEGOTOVA)
        self.assertFalse(W.je_video_ime("Movie/Sample/movie-sample.mkv"))
        self.assertIsNone(W.je_video_ime("Film [1948] 1080p"))

    def test_neveljavno_ime_in_napaka_razresevanja(self):
        """Grok N9: UnicodeError iz IDNA (prazna oznaka) ne uide iz sonde."""
        izid, s = self.sonda({RESOLVE: (302, "https://a..b/x")}, razresi_fn=W.razresi)
        self.assertEqual((izid.izid, izid.razlog), (W.NAPAKA, "dns"))

        def ime_predolgo(_g, _v):
            raise UnicodeError("label too long")
        izid, _s = self.sonda({}, razresi_fn=ime_predolgo)
        self.assertEqual(izid.razlog, "dns")

    def test_povezava_na_preverjeni_ip(self):
        """_PovezavaNaIp ne razresi imena znova (DNS rebinding): povezuje na dani naslov IP."""
        naslovi = []
        with mock.patch("socket.create_connection", side_effect=lambda a, t=None, *x: naslovi.append(a) or (_ for _ in ()).throw(OSError("x"))):
            with self.assertRaises(OSError):
                W.zahteva(CDN, "abra--x1.api.cosmic-crab.buzz", JAVNI_IP, 443, 2.0)
        self.assertEqual(naslovi, [(JAVNI_IP, 443)])

    def test_javni_ip(self):
        self.assertTrue(W.javen_ip("93.184.216.34"))
        self.assertTrue(W.javen_ip("2606:2800:220:1:248:1893:25c8:1946"))
        for n in ("127.0.0.1", "192.168.0.1", "10.1.1.1", "172.31.0.1", "100.100.0.1", "169.254.1.1", "::1", "fc00::1",
                  "fe80::1%eth0", "::ffff:10.0.0.1", "ni-ip"):
            self.assertFalse(W.javen_ip(n), n)


class Scit(unittest.TestCase):
    class Shramba(dict):
        def get(self, k, d=None):
            return dict.get(self, k, d)

        def set(self, k, v):
            self[k] = v

    class Seznami:
        def kategorija(self, ime):
            if ime == "abra--zlo.api.cosmic-crab.buzz":
                return "malware"
            return "oglasi" if "crab" in ime or "webtor" in ime or ime.endswith("ads.example") else None

    class SezamiZGroznjami(Seznami):
        def groznja(self, ime):
            return False

    def test_groznja_nadrejene_domene_in_podpisanega_seznama_zmaga(self):
        """Grok N15: ime na oglasnem seznamu, nadrejena domena pa na seznamu grozenj -> blokirano (groznja)."""
        with tempfile.TemporaryDirectory() as m:
            seznami = os_scit.Seznami(m)
            seznami.nabor = os_scit.Nabor.iz_domen([("abra--x1.api.cosmic-crab.buzz", "oglasi"),
                                                    ("cosmic-crab.buzz", "malware"), ("api.webtor.io", "oglasi")])
            sc = os_scit.Scit(self.Shramba(), mapa=m)
            sc.seznami = seznami
            self.assertEqual(sc._kategorija("abra--x1.api.cosmic-crab.buzz"), "oglasi")   # ostane blokirano
            self.assertIsNone(sc._kategorija("api.webtor.io"))
            seznami.storitev = SimpleNamespace(loaded=SimpleNamespace(is_set=lambda: True),
                                               store=SimpleNamespace(match_host=lambda ime: "phishing"))
            self.assertEqual(sc._kategorija("api.webtor.io"), "oglasi")                   # podpisani seznam grozenj
            # Seznami brez preverbe grozenj (stara razlicica): izjema ne velja (fail-closed).
            sc.seznami = self.Seznami()
            self.assertEqual(sc._kategorija("api.webtor.io"), "oglasi")
        self.assertFalse(W.je_stalna_izjema_scita("abra--" + "a" * 58 + ".api.cosmic-crab.buzz"))   # oznaka > 63

    def test_ozka_izjema_samo_pred_oglasi(self):
        with tempfile.TemporaryDirectory() as m:
            sc = os_scit.Scit(self.Shramba(), mapa=m)
            sc.seznami = self.SezamiZGroznjami()
            self.assertIsNone(sc._kategorija("abra--x1.api.cosmic-crab.buzz"))
            self.assertIsNone(sc._kategorija("api.webtor.io"))
            self.assertIsNone(sc._kategorija("webtor.io"))
            self.assertEqual(sc._kategorija("abra--zlo.api.cosmic-crab.buzz"), "malware")   # grozenje vedno zmagajo
            for ime in ("cosmic-crab.buzz", "ads.cosmic-crab.buzz", "x.abra--1.api.cosmic-crab.buzz", "umami.webtor.io",
                        "evilwebtor.io", "webtor.io.ads.example"):
                self.assertEqual(sc._kategorija(ime), "oglasi", ime)


class Predvajalnik_(unittest.TestCase):
    def test_brez_preusmeritev_v_souphttpsrc(self):
        element = SimpleNamespace(lastnosti={}, signali={})
        element.get_bus = lambda: SimpleNamespace(add_signal_watch=lambda: None, remove_signal_watch=lambda: None,
                                                  connect=lambda *_: None)
        element.connect = lambda ime, fn: element.signali.__setitem__(ime, fn)
        element.set_state = lambda _s: "ok"
        element.set_property = lambda k, v: element.lastnosti.__setitem__(k, v)
        element.get_property = lambda k: element.lastnosti.get(k, {"flags": 0x17, "n-text": 0}.get(k))
        gst = SimpleNamespace(ElementFactory=SimpleNamespace(make=lambda *_: element),
                              State=SimpleNamespace(NULL="null", PLAYING="playing", PAUSED="paused", READY="ready"),
                              StateChangeReturn=SimpleNamespace(FAILURE="failure"),
                              MessageType=SimpleNamespace(EOS="eos", ERROR="error", ASYNC_DONE="async_done"))
        p = Predvajalnik(gst)

        class Vir:
            lastnosti: dict = {}

            def find_property(self, ime):
                return ime in ("automatic-redirect", "extra-headers") or None

            def set_property(self, ime, v):
                self.lastnosti[ime] = v
        for preusmeritve, pricakovano in ((False, {"automatic-redirect": False}), (True, {})):
            p.zamenjaj_vrsto([Skladba(CDN, "Film", "video", preusmeritve=preusmeritve)])
            vir = Vir()
            vir.lastnosti = {}
            element.signali["source-setup"](element, vir)
            self.assertEqual(vir.lastnosti, pricakovano)

        # Grok N7: vir brez te lastnosti tega toka ne predvaja (fail-closed), drug tok pa normalno.
        class VirBrez(Vir):
            def find_property(self, ime):
                return None
        for preusmeritve, ustavljeno in ((False, True), (True, False)):
            p.zamenjaj_vrsto([Skladba(CDN, "Film", "video", preusmeritve=preusmeritve)])
            klici = []
            with mock.patch.object(p, "ustavi", side_effect=lambda: klici.append(1)):
                element.signali["source-setup"](element, VirBrez())
            self.assertEqual(bool(klici), ustavljeno)


class Izbira(unittest.TestCase):
    """Vrstni red virov v Medijskem centru: ⚡ debrid in neposredne povezave pred Webtorjem, Webtor pred cakanjem."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        S.pozabi_vse()
        self.mc = os_media.MediaCenter(self.tmp, roots=[], secret_encryptor=lambda s: "enc:" + s[::-1],
                                       secret_decryptor=lambda s: s[4:][::-1])
        with mock.patch.object(media_servers, "stremio_preveri", return_value=""), \
                mock.patch.object(media_servers, "stremio_manifest", return_value={"id": W.ID_MANIFESTA, "name": "Webtor"}):
            self.assertTrue(self.mc.add_server("stremio", "", DODATEK, "", "")["ok"])
        self.koren = media_servers._stremio_koren(self.mc.sources()[0]["url"])
        with self.mc._lock:                         # drug (navaden) dodatek: neposredne povezave in torrenti
            data = self.mc._load()
            data["osebni_strezniki"].append({"id": "streznik-drug", "vrsta": "streznik", "ponudnik": "stremio",
                                             "ime": "Drug", "url": "https://drug.test/manifest.json", "zaseben": False})
            self.mc._save(data)
        self.wt_url = self.koren + "/resolve/" + JWT                # tok dodatka, kot ga da stremio_tokovi (nadomestek)
        self.item = {"id": "f1", "naslov": "Film", "vrsta": "film", "url": "stremio:%s|movie|tt1" % self.koren}
        self.mc._dynamic_items["f1"] = self.item
        self.sonde: list = []
        self.izidi: list = []
        self.mc._webtor_sonda = lambda url, rok, *_a: self.sonde.append((url, rok)) or self.izidi.pop(0)
        self.drugi: list = []
        self.wt: list = [{"url": self.wt_url, "vir": "[WT] Torrentio", "kakovost": "1080p", "opis": "1080p"}]

    def tearDown(self):
        S.pozabi_vse()
        S.nastavi_odklepalnik(None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tokovi(self, koren, tip, ident):
        return list(self.wt) if koren == self.koren else list(self.drugi) if koren == "https://drug.test" else []

    @staticmethod
    def manifest(koren, sveze=False):
        return {"id": W.ID_MANIFESTA if "webtor.io" in koren else "drug", "name": "x"}

    def resolve(self, **debrid):
        self.mc._dynamic_items["f1"] = self.item      # razresen vnos ostane v pomnilniku - vsak primer od kartice
        izhod = io.StringIO()
        with mock.patch.object(media_servers, "stremio_tokovi", side_effect=self.tokovi), \
                mock.patch.object(media_servers, "stremio_manifest", side_effect=self.manifest), \
                mock.patch.object(self.mc.debrid, "aktivna", return_value=debrid.get("aktivna")), \
                mock.patch.object(self.mc.debrid, "predpomnjeni", return_value=debrid.get("pred", set())), \
                mock.patch.object(self.mc, "_razresi_debrid", side_effect=lambda *a: debrid["cakaj"](*a)) as rd, \
                mock.patch.object(self.mc, "_usenet_mogoc", return_value=False), \
                contextlib.redirect_stdout(izhod), contextlib.redirect_stderr(izhod):
            izid = self.mc.resolve("f1")
        self.assertNotIn(ZETON, izhod.getvalue())
        self.assertNotIn("/token/", izhod.getvalue())
        return izid, rd

    def test_webtor_predvaja_koncni_naslov_v_nasem_predvajalniku(self):
        self.izidi = [W.Sonda(koda=206, prvi_bajt_ms=300, koncni="https://abra--x1.api.cosmic-crab.buzz/abab/tok", vsebina="VIDEO", posoda="MKV")]
        izid, _rd = self.resolve()
        self.assertEqual(izid["url"], "https://abra--x1.api.cosmic-crab.buzz/abab/tok")
        self.assertTrue(izid["webtor"])
        self.assertEqual(self.sonde[0][0], RESOLVE)           # sonda dobi pravi naslov, zapisan ni nikjer
        self.assertNotIn(ZETON, json.dumps(izid))
        self.assertEqual(nacin_predvajanja(izid), "neposredno")   # brez koncnice: vseeno nas predvajalnik
        self.assertEqual(tok_za_predvajalnik(izid, izid["url"]), {"brez_preusmeritev": True})

    def test_pred_cakanjem_na_debrid_po_pripravljenem(self):
        self.wt[0]["vir"] = "[WT] Torrentio"
        self.drugi = [{"url": "", "torrent": True, "hash": "ab" * 20, "indeks": 0, "vir": "Torrentio", "opis": "1080p"}]
        # ⚡ pri nasem debridu zmaga brez sonde Webtor.
        self.izidi = []
        izid, rd = self.resolve(aktivna=debrid_pravila.TORBOX, pred={"ab" * 20},
                                cakaj=lambda *a: dict(self.item, url="https://cdn.torbox.test/f.mkv"))
        self.assertEqual((izid["url"], self.sonde), ("https://cdn.torbox.test/f.mkv", []))
        # Ni pripravljen: Webtor pred cakanjem na debrid (cakanja ni).
        self.izidi = [W.Sonda(koda=206, prvi_bajt_ms=900, koncni=CDN, vsebina="VIDEO", posoda="MKV")]
        izid, rd = self.resolve(aktivna=debrid_pravila.TORBOX, pred=set(), cakaj=lambda *a: self.fail("cakanje na debrid"))
        self.assertEqual(izid["url"], CDN)
        rd.assert_not_called()
        # Webtor ne odgovori: sele zdaj cakanje na debrid.
        self.sonde.clear()
        self.izidi = [W.Sonda(koda=404)]
        izid, rd = self.resolve(aktivna=debrid_pravila.TORBOX, pred=set(),
                                cakaj=lambda *a: dict(self.item, url="https://cdn.torbox.test/cakano.mkv"))
        self.assertEqual(izid["url"], "https://cdn.torbox.test/cakano.mkv")
        self.assertEqual(len(self.sonde), 1)

    def test_neposredna_povezava_pred_webtorjem(self):
        self.drugi = [{"url": "https://cdn.drug.test/f.mp4", "vir": "Drug", "kakovost": "1080p", "opis": "1080p"}]
        self.izidi = []
        izid, _rd = self.resolve()
        self.assertEqual((izid["url"], self.sonde), ("https://cdn.drug.test/f.mp4", []))
        self.assertNotIn(self.wt_url, json.dumps(izid))       # tok Webtor ni med neposrednimi razlicicami

    def test_najvec_dve_sondi_in_skrite_vrste(self):
        self.wt = [{"url": self.wt_url + "a", "vir": "[P2P] Torrentio"},
                   {"url": self.wt_url + "b", "vir": "[WT] A"}, {"url": self.wt_url + "c", "vir": "[WT] B"},
                   {"url": self.wt_url + "d", "vir": "[WT] C"}]
        self.izidi = [W.Sonda(koda=404), W.Sonda(koda=429), W.Sonda(koda=206, prvi_bajt_ms=5, koncni=CDN, vsebina="VIDEO", posoda="MKV")]
        izid, _rd = self.resolve()
        self.assertEqual(izid.get("napaka_koda"), "ni_toka")
        self.assertEqual([u[-1] for u, _r in self.sonde], ["b", "c"])     # P2P (oglas) skrit, najvec 2 sondi
        self.assertTrue(all(r <= W.PRVI_BAJT_MS for _u, r in self.sonde))

    def test_izrecen_p2p_ne_caka_znova_na_webtor(self):
        """Naloga 21, tocka 3: »Predvajaj neposredno« po neuspehu Webtorja - brez druge sonde Webtor (15 s), naravnost v roj;
        brez izbire pa nikoli v roj."""
        self.drugi = [{"url": "", "torrent": True, "hash": "ab" * 20, "indeks": 0, "vir": "Torrentio", "opis": "1080p"}]
        self.izidi = [W.Sonda(koda=404), W.Sonda(koda=404)]
        roj: list = []
        with mock.patch.object(os_media.os_torrent_tok, "podprto", return_value=True), \
                mock.patch.object(self.mc, "_razresi_torrent", side_effect=lambda item, t, **_k: roj.append(t) or dict(item, url="http://127.0.0.1:1/t")), \
                mock.patch.object(self.mc, "_p2p_dovoljeni", return_value=[]):
            izid, _rd = self.resolve()
            self.assertEqual((izid.get("napaka_koda"), len(self.sonde), roj), ("p2p_potrditev", 1, []))
            self.assertTrue(izid["p2p"]["webtor"])
            self.sonde.clear()
            self.mc._dynamic_items["f1"] = self.item
            with mock.patch.object(media_servers, "stremio_tokovi", side_effect=self.tokovi), \
                    mock.patch.object(media_servers, "stremio_manifest", side_effect=self.manifest), \
                    mock.patch.object(self.mc, "_usenet_mogoc", return_value=False), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                izid = self.mc.resolve("f1", p2p=True)
        self.assertEqual((izid.get("url"), self.sonde, len(roj)), ("http://127.0.0.1:1/t", [], 1))

    def test_hitro_zavrnjena_vsebina_ni_poskus(self):
        """Naloga 21 B1 (skupni primeri v4): pri torrentih YTS CDN TorBox za idx filma vrne .srt; sonda ga zavrne hitro
        (NAPACNA_VSEBINA v < 3 s) in to ne porabi enega od 2 poskusov - naslednji tokovi pridejo na vrsto."""
        self.wt = [{"url": self.wt_url + "a", "vir": "[WT] A"}, {"url": self.wt_url + "b", "vir": "[WT] B"},
                   {"url": self.wt_url + "c", "vir": "[WT] C"}]
        srt = W.Sonda(koda=206, prvi_bajt_ms=300, koncni="https://cdn.tb.test/f.srt", vsebina="BESEDILO", posoda="")
        self.izidi = [srt, srt, W.Sonda(koda=206, prvi_bajt_ms=400, koncni=CDN, vsebina="VIDEO", posoda="MKV")]
        izid, _rd = self.resolve()
        self.assertEqual((izid.get("url"), [u[-1] for u, _r in self.sonde]), (CDN, ["a", "b", "c"]))
        # Pocasne zavrnitve (in vse druge) stejejo naprej: 404 + 429 = konec (test_najvec_dve_sondi_in_skrite_vrste).

    def test_koncni_naslov_z_zetonom_ne_gre_v_predvajalnik(self):
        self.izidi = [W.Sonda(koda=206, prvi_bajt_ms=5, koncni=RESOLVE, vsebina="VIDEO", posoda="MKV")]         # brez preusmeritve (zeton v naslovu)
        izid, _rd = self.resolve()
        self.assertNotEqual(izid.get("url"), RESOLVE)
        self.assertNotIn(ZETON, json.dumps(izid))

    def test_vzorec_in_slika_nista_kandidata(self):
        self.wt = [{"url": self.wt_url + "a", "vir": "[WT] A", "datoteka": "cover.jpg"},
                   {"url": self.wt_url + "b", "vir": "[WT] B", "datoteka": "Film-sample.mkv"},
                   {"url": self.wt_url + "c", "vir": "[WT] C", "datoteka": "Film.2024.1080p.mkv"}]
        self.izidi = [W.Sonda(koda=206, prvi_bajt_ms=5, koncni=CDN, vsebina="VIDEO", posoda="MKV")]
        izid, _rd = self.resolve()
        self.assertEqual(izid["url"], CDN)
        self.assertEqual([u[-1] for u, _r in self.sonde], ["c"])

    def test_sonda_s_tezavo_ne_ustavi_izbire(self):
        """Grok N9: nepricakovana napaka sonde -> naslednji tok."""
        self.wt = [{"url": self.wt_url + "a", "vir": "[WT] A"}, {"url": self.wt_url + "b", "vir": "[WT] B"}]
        izidi = [UnicodeError("x"), W.Sonda(koda=206, prvi_bajt_ms=5, koncni=CDN, vsebina="VIDEO", posoda="MKV")]

        def sonda(url, rok, *_a):
            self.sonde.append((url, rok))
            i = izidi.pop(0)
            if isinstance(i, Exception):
                raise i
            return i
        self.mc._webtor_sonda = sonda
        izid, _rd = self.resolve()
        self.assertEqual(izid["url"], CDN)

    def test_tuj_dodatek_z_idjem_webtor_ni_webtor(self):
        self.assertFalse(self.mc._je_webtor_koren("https://evilwebtor.io/x"))
        with mock.patch.object(media_servers, "stremio_manifest", return_value={"id": W.ID_MANIFESTA}):
            self.assertFalse(self.mc._je_webtor_koren("https://zlo.example/stremio"))
            self.assertFalse(self.mc._je_webtor_koren("http://webtor.io/x"))


class PravaOblikaTokov(unittest.TestCase):
    """Zivi tek 25. 10. 2026 (lastnikov dodatek Webtor na prenosniku): dodatek je kratka povezava `/s/<koda>`, tokovi
    pa `/token/<uuid>/stremio/resolve/<JWT>`. skrij_tok skrije cel naslov toka (JWT je neprozoren odsek), zato tok ni bil
    prepoznan kot Webtor: sel je med neposredne povezave (sonda brez preverbe vsebine in brez izbire glavne datoteke).
    Tu stremio_tokovi NI ponarejen - tokove skrije prava pot (media_servers._request -> stremio_tokovi -> skrij_tok)."""
    KODA = "AbC123"
    UUID = "0f8fad5b-d9cb-469f-a165-70867728950e"
    KRATKA = "https://webtor.io/s/%s/manifest.json" % KODA
    TOK = "https://webtor.io/token/%s/stremio/resolve/%s" % (UUID, JWT)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        S.pozabi_vse()
        self.mc = os_media.MediaCenter(self.tmp, roots=[], secret_encryptor=lambda s: "enc:" + s[::-1],
                                       secret_decryptor=lambda s: s[4:][::-1])
        self.sonde: list = []

    def tearDown(self):
        S.pozabi_vse()
        S.nastavi_odklepalnik(None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def resolve(self, dodatek: str, tok: str, *zetoni: str) -> dict:
        with mock.patch.object(media_servers, "stremio_preveri", return_value=""), \
                mock.patch.object(media_servers, "stremio_manifest", return_value={"id": W.ID_MANIFESTA, "name": "Webtor"}):
            self.assertTrue(self.mc.add_server("stremio", "Webtor", dodatek, "", "")["ok"])
        koren = media_servers._stremio_koren(self.mc.sources()[0]["url"])
        self.mc._dynamic_items["f1"] = {"id": "f1", "naslov": "Film", "vrsta": "film", "url": "stremio:%s|movie|tt1" % koren}
        self.mc._webtor_sonda = lambda url, rok, *_a: self.sonde.append(url) or W.Sonda(
            koda=206, prvi_bajt_ms=300, koncni=CDN, vsebina="VIDEO", posoda="MKV")
        self.mc._skrivni_sonda = lambda *_a: self.fail("tok Webtor je sel med neposredne povezave")
        odgovor = json.dumps({"streams": [{"name": "[⚡WT] Torrentio\n1080p", "title": "Film 1080p", "url": tok,
                                           "behaviorHints": {"filename": "Film.2024.1080p.mkv"}}]}).encode()
        izhod = io.StringIO()
        with mock.patch.object(media_servers, "_request", return_value=odgovor), \
                mock.patch.object(media_servers, "stremio_manifest", return_value={"id": W.ID_MANIFESTA}), \
                mock.patch.object(media_servers, "tok_stanje", side_effect=AssertionError("brez sonde zivosti s kljucem")), \
                mock.patch.object(self.mc, "_usenet_mogoc", return_value=False), \
                contextlib.redirect_stdout(izhod), contextlib.redirect_stderr(izhod):
            izid = self.mc.resolve("f1")
        for z in zetoni:
            self.assertNotIn(z, izhod.getvalue())
            self.assertNotIn(z, json.dumps(izid))
        return izid

    def test_kratka_povezava_s_kodo(self):
        izid = self.resolve(self.KRATKA, self.TOK, self.KODA, self.UUID)
        self.assertEqual((izid.get("url"), izid.get("webtor")), (CDN, True))
        self.assertEqual(self.sonde, [self.TOK])            # sonda Webtor (s preverbo vsebine) dobi pravi naslov

    def test_povezava_z_zetonom(self):
        izid = self.resolve(DODATEK, RESOLVE, ZETON)
        self.assertEqual((izid.get("url"), izid.get("webtor")), (CDN, True))
        self.assertEqual(self.sonde, [RESOLVE])


if __name__ == "__main__":
    unittest.main()


class TokSKljucem(unittest.TestCase):
    """Grok N2, N5: tok dodatka z debrid kljucem (Torrentio `/resolve/realdebrid/<kljuc>/...`) - v predvajalnik ne gre ne
    nadomestek ne naslov s kljucem, ampak koncni naslov sonde."""
    KLJUC = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ABCD"
    DODATEK = "https://torrentio.strem.fun/sort=qualitysize|realdebrid=%s/manifest.json" % KLJUC
    TOK = "https://torrentio.strem.fun/resolve/realdebrid/%s/0123456789abcdef0123456789abcdef01234567/null/0/Film.mkv" % KLJUC
    RD = "https://abc.download.real-debrid.com/d/XYZ123/Film.mkv"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        S.pozabi_vse()
        self.mc = os_media.MediaCenter(self.tmp, roots=[], secret_encryptor=lambda s: "enc:" + s[::-1],
                                       secret_decryptor=lambda s: s[4:][::-1])
        with mock.patch.object(media_servers, "stremio_preveri", return_value=""), \
                mock.patch.object(media_servers, "stremio_manifest", return_value={"id": "com.stremio.torrentio.addon"}):
            self.assertTrue(self.mc.add_server("stremio", "Torrentio", self.DODATEK, "", "")["ok"])
        self.koren = media_servers._stremio_koren(self.mc.sources()[0]["url"])
        self.item = {"id": "f1", "naslov": "Film", "vrsta": "film", "url": "stremio:%s|movie|tt1" % self.koren}
        self.sonde: list = []

    def tearDown(self):
        S.pozabi_vse()
        S.nastavi_odklepalnik(None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def resolve(self, izid_sonde):
        self.mc._dynamic_items["f1"] = self.item
        self.mc._skrivni_sonda = lambda url, rok, *_a: self.sonde.append(url) or izid_sonde
        odgovor = json.dumps({"streams": [{"name": "Torrentio\n1080p", "title": "Film 1080p", "url": self.TOK},
                                          {"name": "Torrentio\n720p", "title": "Film 720p", "url": self.TOK + "2"}]}).encode()
        izhod = io.StringIO()
        with mock.patch.object(media_servers, "_request", return_value=odgovor), \
                mock.patch.object(media_servers, "stremio_manifest", return_value={"id": "com.stremio.torrentio.addon"}), \
                mock.patch.object(media_servers, "tok_stanje", side_effect=AssertionError("brez sonde zivosti s kljucem")), \
                mock.patch.object(self.mc, "_usenet_mogoc", return_value=False), \
                contextlib.redirect_stdout(izhod), contextlib.redirect_stderr(izhod):
            izid = self.mc.resolve("f1")
        self.assertNotIn(self.KLJUC, izhod.getvalue())
        return izid

    def test_glave_toka_sondi_in_ne_drugemu_gostitelju(self):
        """Grok 19, M3: sonda toka s kljucem dobi glave toka; predvajalnik jih dobi samo, ce je koncni gostitelj isti."""
        for koncni, glave_ostanejo in ((self.RD, False), ("https://torrentio.strem.fun/cdn/abc123/Film.mkv", True)):
            S.pozabi_vse()
            prejete: list = []
            self.mc._dynamic_items["f1"] = self.item
            self.mc._skrivni_sonda = lambda url, rok, glave=None, k=koncni: prejete.append(glave) or W.Sonda(
                koda=206, prvi_bajt_ms=5, gostitelj=W.gostitelj(k), koncni=k)
            odgovor = json.dumps({"streams": [{"name": "Torrentio\n1080p", "title": "Film 1080p", "url": self.TOK,
                                               "behaviorHints": {"proxyHeaders": {"request": {"Referer": "https://torrentio.strem.fun/"}}}}]}).encode()
            with mock.patch.object(media_servers, "_request", return_value=odgovor), \
                    mock.patch.object(media_servers, "stremio_manifest", return_value={"id": "com.stremio.torrentio.addon"}), \
                    mock.patch.object(media_servers, "tok_stanje", side_effect=AssertionError("brez sonde zivosti s kljucem")), \
                    mock.patch.object(self.mc, "_usenet_mogoc", return_value=False), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                izid = self.mc.resolve("f1")
            self.assertEqual(prejete, [{"Referer": "https://torrentio.strem.fun/"}])
            self.assertEqual(izid["url"], koncni)
            self.assertEqual("glave" in izid, glave_ostanejo, koncni)
            self.assertEqual(any("glave" in r for r in izid["razlicice"]), glave_ostanejo, koncni)

    def test_predvajalnik_dobi_koncni_naslov_brez_kljuca(self):
        izid = self.resolve(W.Sonda(koda=206, prvi_bajt_ms=200, koncni=self.RD))
        self.assertEqual(self.sonde, [self.TOK])                 # sonda dobi pravi naslov (samo v pomnilniku)
        self.assertEqual((izid["url"], izid.get("preverjen")), (self.RD, True))
        self.assertNotIn(self.KLJUC, json.dumps(izid))
        self.assertFalse(any(S.je_nadomestek(r.get("url", "")) for r in izid.get("razlicice") or []))
        self.assertEqual(tok_za_predvajalnik(izid, izid["url"]), {"brez_preusmeritev": True})
        self.assertEqual(nacin_predvajanja(dict(izid, url="https://abc.download.real-debrid.com/d/XYZ")), "neposredno")

    def test_koncni_s_kljucem_se_ne_predvaja(self):
        izid = self.resolve(W.Sonda(koda=206, prvi_bajt_ms=200, koncni=self.TOK))
        self.assertNotIn(self.KLJUC, json.dumps(izid))
        self.assertFalse(S.je_nadomestek(str(izid.get("url") or "")))
        self.assertEqual(izid.get("napaka_koda"), "ni_toka")
