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


MKV = bytes.fromhex("1a45dfa3") + b"\x00" * 372
MP4 = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 364
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 366
MP3 = b"ID3\x04\x00" + b"\x00" * 371


class Streznik:
    """Ponarejen splet: naslov -> (koda, Location[, prvi bajti, Content-Type]). Zapise, kam se je sonda povezala."""

    def __init__(self, odgovori: dict):
        self.odgovori = odgovori
        self.klici: list = []

    def zahteva(self, naslov, gostitelj, ip, vrata, rok):
        self.klici.append((naslov, gostitelj, ip, vrata))
        odgovor = self.odgovori.get(naslov, (404, None))
        koda, kam = odgovor[:2]
        bajti, vsebina = odgovor[2:] if len(odgovor) > 2 else ((MKV, "video/x-matroska") if 200 <= koda <= 299 else (b"", ""))
        return koda, kam, bajti, vsebina


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
        """Android 25. 10. 15:25: sonda je videla 206, predvajalnik pa je dobil naslovnico JPEG ali MP3."""
        for bajti, vsebina, razlog in ((JPEG, "image/jpeg", "vsebina"), (MP3, "audio/mpeg", "vsebina"),
                                       (JPEG, "application/octet-stream", "posoda"), (MP3, "application/octet-stream", "posoda"),
                                       (b"<html>" + b" " * 370, "text/html", "vsebina"), (MKV, "", "vsebina")):
            with self.subTest(vsebina=vsebina, bajti=bajti[:4]):
                izid, _s = self.sonda({RESOLVE: (302, CDN), CDN: (206, None, bajti, vsebina)})
                self.assertEqual((izid.izid, izid.koncni, izid.razlog), (W.NI_VIDEO, None, razlog))
        for bajti, vsebina, vrsta in ((MKV, "video/x-matroska", "mkv"), (MP4, "video/mp4", "mp4"),
                                      (MKV, "application/octet-stream", "mkv"), (MP4, "application/octet-stream; x=1", "mp4")):
            with self.subTest(vsebina=vsebina):
                izid, _s = self.sonda({RESOLVE: (302, CDN), CDN: (206, None, bajti, vsebina)})
                self.assertEqual((izid.izid, izid.posoda, izid.koncni), (W.PREDVAJAJ, vrsta, CDN))
        slika = "https://abra--x1.api.cosmic-crab.buzz/abab/cover.jpg"
        izid, _s = self.sonda({RESOLVE: (302, slika), slika: (206, None, MKV, "application/octet-stream")})
        self.assertEqual((izid.izid, izid.razlog), (W.NI_VIDEO, "datoteka"))

    def test_glavni_video_po_imenu(self):
        self.assertTrue(W.je_glavni_video("Film.2024.1080p.WEB-DL.mkv", 4_000_000_000))
        self.assertIsNone(W.je_glavni_video(""))
        for ime, velikost in (("Sample/film-sample.mkv", None), ("cover.jpg", None), ("01 - Song.mp3", None),
                              ("Film.2024.Trailer.mp4", None), ("film.mkv", 5_000_000), ("film.nfo", None)):
            self.assertFalse(W.je_glavni_video(ime, velikost), ime)

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

    def test_ozka_izjema_samo_pred_oglasi(self):
        with tempfile.TemporaryDirectory() as m:
            sc = os_scit.Scit(self.Shramba(), mapa=m)
            sc.seznami = self.Seznami()
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


class Izbira(unittest.TestCase):
    """Vrstni red virov v Medijskem centru: ⚡ debrid in neposredne povezave pred Webtorjem, Webtor pred cakanjem."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        S._PRAVI.clear()
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
        self.mc._webtor_sonda = lambda url, rok: self.sonde.append((url, rok)) or self.izidi.pop(0)
        self.drugi: list = []
        self.wt: list = [{"url": self.wt_url, "vir": "[WT] Torrentio", "kakovost": "1080p", "opis": "1080p"}]

    def tearDown(self):
        S._PRAVI.clear()
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
        self.izidi = [W.Sonda(koda=206, prvi_bajt_ms=300, koncni="https://abra--x1.api.cosmic-crab.buzz/abab/tok", posoda="mkv")]
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
        self.izidi = [W.Sonda(koda=206, prvi_bajt_ms=900, koncni=CDN, posoda="mkv")]
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
        self.izidi = [W.Sonda(koda=404), W.Sonda(koda=429), W.Sonda(koda=206, prvi_bajt_ms=5, koncni=CDN, posoda="mkv")]
        izid, _rd = self.resolve()
        self.assertEqual(izid.get("napaka_koda"), "ni_toka")
        self.assertEqual([u[-1] for u, _r in self.sonde], ["b", "c"])     # P2P (oglas) skrit, najvec 2 sondi
        self.assertTrue(all(r <= W.PRVI_BAJT_MS for _u, r in self.sonde))

    def test_koncni_naslov_z_zetonom_ne_gre_v_predvajalnik(self):
        self.izidi = [W.Sonda(koda=206, prvi_bajt_ms=5, koncni=RESOLVE, posoda="mkv")]         # brez preusmeritve (zeton v naslovu)
        izid, _rd = self.resolve()
        self.assertNotEqual(izid.get("url"), RESOLVE)
        self.assertNotIn(ZETON, json.dumps(izid))

    def test_vzorec_in_slika_nista_kandidata(self):
        self.wt = [{"url": self.wt_url + "a", "vir": "[WT] A", "datoteka": "cover.jpg"},
                   {"url": self.wt_url + "b", "vir": "[WT] B", "datoteka": "Film-sample.mkv", "velikost": 40_000_000},
                   {"url": self.wt_url + "c", "vir": "[WT] C", "datoteka": "Film.2024.1080p.mkv", "velikost": 4_000_000_000}]
        self.izidi = [W.Sonda(koda=206, prvi_bajt_ms=5, koncni=CDN, posoda="mkv")]
        izid, _rd = self.resolve()
        self.assertEqual(izid["url"], CDN)
        self.assertEqual([u[-1] for u, _r in self.sonde], ["c"])

    def test_tuj_dodatek_z_idjem_webtor_ni_webtor(self):
        self.assertFalse(self.mc._je_webtor_koren("https://evilwebtor.io/x"))
        with mock.patch.object(media_servers, "stremio_manifest", return_value={"id": W.ID_MANIFESTA}):
            self.assertFalse(self.mc._je_webtor_koren("https://zlo.example/stremio"))
            self.assertFalse(self.mc._je_webtor_koren("http://webtor.io/x"))


if __name__ == "__main__":
    unittest.main()
