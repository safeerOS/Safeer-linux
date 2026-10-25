"""Kanali seznamov IPTV v Medijskem centru (core/kanali_iptv.py, core/os_media.py).

Lastnik, 25. 10. 2026 (posnetek TV): v »Serije« je bilo polno kanalov TV v zivo (Exodus TV, H2, Kanal A, Star Crime ...),
klik je pokazal »Sezone niso na voljo«. Vzrok: razrez #EXTINF pri prvi vejici (vejica v http-user-agent) in ugibanje
vrste po podnizu »tv«. Preizkusi: razclenitev (skupni primeri za vse platforme), razvrstitev, preverba toka (pravi
HTTP streznik na 127.0.0.1, brez interneta), predpomnilnik preverb in katalog (samo delujoci kanali, nikjer drugje).
"""
import http.server
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from core import kanali_iptv, os_media, zakoniti_viri

PRIMERI = Path(__file__).resolve().parent / "skupni-primeri" / "iptv-m3u.json"


def _razcleni(seznam, vrstice, stevci=None):
    besedilo = "#EXTM3U\n" + "\n".join(vrstice) + "\n"
    return os_media.parse_payload(besedilo.encode("utf-8"), "audio/x-mpegurl", seznam, "vir1", "Seznam", stevci=stevci)


class SkupniPrimeri(unittest.TestCase):
    def test_vsi_primeri(self):
        primeri = json.loads(PRIMERI.read_text(encoding="utf-8"))["primeri"]
        self.assertGreaterEqual(len(primeri), 10)
        for p in primeri:
            with self.subTest(p["opis"]):
                stevci = {}
                vnosi = _razcleni(p["seznam"], p["vrstice"], stevci)
                pricakovano = p["pricakovano"]
                if pricakovano.get("izlocen"):
                    self.assertEqual(vnosi, [])
                    self.assertEqual(stevci.get("ne_24_7"), 1)
                    continue
                self.assertEqual(len(vnosi), 1, vnosi)
                v = vnosi[0]
                self.assertEqual(v["naslov"], pricakovano["ime"])
                self.assertEqual(v["vrsta"], pricakovano["vrsta"])
                for polje, kljuc in (("drzava", "drzava"), ("jezik", "jezik"), ("logo", "slika"),
                                     ("kategorija", "kategorija_kanala"), ("referer", "referer"),
                                     ("sezona", "sezona"), ("epizoda", "epizoda")):
                    if polje in pricakovano:
                        self.assertEqual(v.get(kljuc), pricakovano[polje], polje)
                if "user_agent" in pricakovano:
                    self.assertEqual(v["glave"].get("User-Agent"), pricakovano["user_agent"])
                self.assertEqual(bool(v.get("iptv")), pricakovano["vrsta"] == "tv-v-zivo")


class Razclenitev(unittest.TestCase):
    def test_vejica_zunaj_narekovajev(self):
        trajanje, atributi, ime = kanali_iptv.razcleni_extinf(
            '#EXTINF:-1 tvg-id="a.si" http-user-agent="X (KHTML, like Gecko) Y" group-title="A,B",Ime, z vejico')
        self.assertEqual((trajanje, ime), (-1.0, "Ime, z vejico"))
        self.assertEqual(atributi["group-title"], "A,B")
        self.assertEqual(atributi["http-user-agent"], "X (KHTML, like Gecko) Y")

    def test_ime_iz_tvg_name(self):
        self.assertEqual(kanali_iptv.razcleni_extinf('#EXTINF:-1 tvg-name="Rezerva" group-title="X",')[2], "Rezerva")

    def test_kind_ne_naredi_serije_iz_podniza_tv(self):
        # Splosni viri (JSON, HTML): »Exodus TV« ali gostitelj ».tv« nista serija; beseda za serijo ali pot /tv/ je.
        self.assertNotEqual(os_media._kind("", "https://primer.test/exodus.m3u8", "Exodus TV"), "serija")
        self.assertNotEqual(os_media._kind("", "https://kanal.tv/v/1.mp4", "Oddaja"), "serija")
        self.assertEqual(os_media._kind("", "https://primer.test/tv/123", "Naslov"), "serija")
        self.assertEqual(os_media._kind("series", "https://primer.test/1.mp4", "Naslov"), "serija")

    def test_lastnikov_seznam_brez_serij(self):
        """Lastnikov si.m3u (posnetek 25. 10. 2026) v obliki iptv-org: noben kanal ni serija, film ali glasba."""
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        vrstice = []
        for i, (ime, skupina) in enumerate((("H2 HD", "Documentary"), ("Kanal A", "General"), ("Star Life (Slovenia)", "Series"),
                                            ("Star Movies (Slovenia)", "Movies"), ("Folx Slovenija", "Music"),
                                            ("Viasat Explore (Slovenia)", "Documentary"), ("TV SLO 1", "General"))):
            vrstice += ['#EXTINF:-1 tvg-id="K%d.si@SD" tvg-logo="https://primer.test/%d.png" http-user-agent="%s" group-title="%s",%s'
                        % (i, i, ua, skupina, ime), "#EXTVLCOPT:http-user-agent=" + ua, "http://primer.test/play/k%d" % i]
        vnosi = _razcleni("https://iptv-org.github.io/iptv/countries/si.m3u", vrstice)
        self.assertEqual({v["vrsta"] for v in vnosi}, {"tv-v-zivo"})
        self.assertNotIn("like Gecko", " ".join(v["naslov"] for v in vnosi))
        self.assertTrue(all(v["glave"].get("User-Agent") == ua for v in vnosi))


# ---------------------------------------------------------------------------------------------- preverba toka

TS = (b"\x47" + b"\x00" * 187) * 12
MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64
MKV = b"\x1a\x45\xdf\xa3" + b"\x00" * 64


class _Streznik(http.server.BaseHTTPRequestHandler):
    zahteve: list = []

    def log_message(self, *a):
        pass

    def _poslji(self, status, telo=b"", vrsta="application/octet-stream", glave=None):
        self.send_response(status)
        self.send_header("Content-Type", vrsta)
        for k, v in (glave or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(telo)))
        self.end_headers()
        if telo:
            self.wfile.write(telo)

    def do_GET(self):
        _Streznik.zahteve.append((self.path, self.headers.get("Host"), self.headers.get("User-Agent"), self.headers.get("Range")))
        pot = self.path
        hls = "application/vnd.apple.mpegurl"
        if pot == "/glavni.m3u8":
            return self._poslji(200, b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nrazlicica.m3u8\n", hls)
        if pot == "/razlicica.m3u8":
            return self._poslji(200, b"#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2,\nkos0.ts\n#EXTINF:2,\nkos1.ts\n", hls)
        if pot in ("/kos0.ts", "/kos1.ts", "/ts"):
            return self._poslji(200, TS)
        if pot == "/mrtva-razlicica.m3u8":
            return self._poslji(200, b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nni.m3u8\n", hls)
        if pot == "/geo.m3u8":
            return self._poslji(200, b"#EXTM3U\n#EXTINF:2,\ngeo.ts\n", hls)
        if pot == "/geo.ts":
            return self._poslji(403)
        if pot == "/prazen.m3u8":
            return self._poslji(200, b"#EXTM3U\n#EXT-X-TARGETDURATION:2\n", hls)
        if pot == "/mp4":
            return self._poslji(200, MP4)
        if pot == "/mkv":
            return self._poslji(200, MKV)
        if pot == "/html":
            return self._poslji(200, b"<html>reklama</html>", "text/html")
        if pot in ("/401", "/403", "/451", "/404", "/410", "/500"):
            return self._poslji(int(pot[1:]))
        if pot == "/preusmeri":
            return self._poslji(302, glave={"Location": "/ts"})
        if pot == "/preusmeri-drugam":
            return self._poslji(302, glave={"Location": "http://127.0.0.2:%d/ts" % self.server.server_address[1]})
        if pot == "/ua":
            return self._poslji(200, TS) if self.headers.get("User-Agent") == "Posebni/1.0" else self._poslji(403)
        if pot == "/pocasi":
            time.sleep(2.5)
            return self._poslji(200, TS)
        if pot == "/neskoncno":
            self.send_response(200)
            self.send_header("Content-Type", "video/mp2t")
            self.end_headers()
            try:
                for _ in range(2000):                 # ~3,7 MB, ce bi preverba brala vse
                    self.wfile.write(TS)
            except OSError:
                pass
            return None
        return self._poslji(404)


class PreverbaToka(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Streznik)
        cls.streznik.daemon_threads = True
        cls.nit = threading.Thread(target=cls.streznik.serve_forever, daemon=True)
        cls.nit.start()
        cls.vrata = cls.streznik.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.streznik.shutdown()
        cls.streznik.server_close()

    def preveri(self, pot, domace=True, **k):
        return kanali_iptv.preveri_tok("http://127.0.0.1:%d%s" % (self.vrata, pot), domace=domace, **k)

    def test_hls_z_razlicico_in_kosom_deluje(self):
        self.assertEqual(self.preveri("/glavni.m3u8"), (kanali_iptv.DELUJE, "hls"))

    def test_hls_brez_zive_razlicice_ali_kosa_ne_deluje(self):
        self.assertEqual(self.preveri("/mrtva-razlicica.m3u8"), (kanali_iptv.MRTEV, "http-404"))
        self.assertEqual(self.preveri("/prazen.m3u8"), (kanali_iptv.MRTEV, "vsebina"))
        # Geografsko omejen: seznam 200, kos 403 (izmerjeno na Androidu 25. 10. 2026) - zaklenjen, ne »deluje«.
        self.assertEqual(self.preveri("/geo.m3u8"), (kanali_iptv.ZAKLENJEN, "http-403"))

    def test_magicni_bajti(self):
        self.assertEqual(self.preveri("/ts"), (kanali_iptv.DELUJE, "ts"))
        self.assertEqual(self.preveri("/mp4"), (kanali_iptv.DELUJE, "mp4"))
        self.assertEqual(self.preveri("/mkv"), (kanali_iptv.DELUJE, "mkv"))
        self.assertEqual(self.preveri("/html"), (kanali_iptv.MRTEV, "vsebina"))

    def test_statusi(self):
        for status, izid in ((401, kanali_iptv.ZAKLENJEN), (403, kanali_iptv.ZAKLENJEN), (451, kanali_iptv.ZAKLENJEN),
                             (404, kanali_iptv.MRTEV), (410, kanali_iptv.MRTEV), (500, kanali_iptv.MRTEV)):
            self.assertEqual(self.preveri("/%d" % status), (izid, "http-%d" % status))

    def test_zasebni_naslov_samo_za_domaci_seznam(self):
        # Javni seznam ne sme preveriti naslova v lokalnem omrezju ali na tem racunalniku (SSRF).
        self.assertEqual(self.preveri("/ts", domace=False), (kanali_iptv.MRTEV, "zasebni-naslov"))

    def test_preusmeritev_preverjena_na_vsakem_skoku(self):
        self.assertEqual(self.preveri("/preusmeri"), (kanali_iptv.DELUJE, "ts"))
        # Prvi skok je dovoljen (127.0.0.1), drugi (127.0.0.2) ne: preverba ne sme slediti.
        dovoljen = lambda naslov, domace: naslov == "127.0.0.1"  # noqa: E731
        with mock.patch.object(kanali_iptv, "dovoljen_ip", dovoljen):
            self.assertEqual(self.preveri("/preusmeri-drugam"), (kanali_iptv.MRTEV, "zasebni-naslov"))
            self.assertEqual(self.preveri("/preusmeri"), (kanali_iptv.DELUJE, "ts"))

    def test_povezava_na_preverjen_naslov_z_imenom_gostitelja(self):
        _Streznik.zahteve.clear()
        razresi = lambda gost, vrata, **k: [(2, 1, 6, "", ("127.0.0.1", vrata))]  # noqa: E731
        izid = kanali_iptv.preveri_tok("http://kanal.test:%d/ts" % self.vrata, domace=True, razresi=razresi)
        self.assertEqual(izid, (kanali_iptv.DELUJE, "ts"))
        self.assertEqual(_Streznik.zahteve[-1][1], "kanal.test:%d" % self.vrata)

    def test_glave_seznama(self):
        self.assertEqual(self.preveri("/ua")[0], kanali_iptv.ZAKLENJEN)
        self.assertEqual(self.preveri("/ua", glave={"User-Agent": "Posebni/1.0"}), (kanali_iptv.DELUJE, "ts"))

    def test_rok(self):
        zacetek = time.monotonic()
        self.assertEqual(self.preveri("/pocasi", rok=1.0), (kanali_iptv.MRTEV, "rok"))
        self.assertLess(time.monotonic() - zacetek, 2.0)

    def test_neskoncen_tok_prebere_samo_zacetek(self):
        zacetek = time.monotonic()
        self.assertEqual(self.preveri("/neskoncno"), (kanali_iptv.DELUJE, "ts"))
        self.assertLess(time.monotonic() - zacetek, 2.0)


class PredpomnilnikPreverb(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.pot = Path(self.mapa.name) / "kanali-preverba.json"

    def test_na_disku_ni_naslovov(self):
        p = kanali_iptv.PreverbaKanalov(self.pot)
        p.zapisi("https://primer.test/tok.m3u8?token=SKRIVNO", kanali_iptv.DELUJE, "hls")
        p._pisi(takoj=True)
        besedilo = self.pot.read_text(encoding="utf-8")
        self.assertNotIn("SKRIVNO", besedilo)
        self.assertNotIn("primer.test", besedilo)
        self.assertTrue(kanali_iptv.PreverbaKanalov(self.pot).deluje("https://primer.test/tok.m3u8?token=SKRIVNO"))

    def test_roki_veljavnosti(self):
        ura = [1000.0]
        p = kanali_iptv.PreverbaKanalov(self.pot, ura=lambda: ura[0])
        self.assertTrue(p.potrebuje_preverbo("https://a.test/1"))
        p.zapisi("https://a.test/1", kanali_iptv.DELUJE)
        p.zapisi("https://a.test/2", kanali_iptv.MRTEV)
        self.assertFalse(p.potrebuje_preverbo("https://a.test/1"))
        ura[0] += kanali_iptv.VELJA_S[kanali_iptv.DELUJE] + 1
        self.assertTrue(p.potrebuje_preverbo("https://a.test/1"))
        ura[0] += kanali_iptv.VELJA_S[kanali_iptv.MRTEV]
        self.assertTrue(p.potrebuje_preverbo("https://a.test/2"))
        with mock.patch.object(kanali_iptv, "PONOVNO_PREVERI_MRTVE", False):
            self.assertFalse(p.potrebuje_preverbo("https://a.test/2"))

    def test_mrtev_kanal_se_vrne_in_steje(self):
        p = kanali_iptv.PreverbaKanalov(self.pot)
        p.oznaci_mrtev("https://a.test/1")
        self.assertFalse(p.deluje("https://a.test/1"))
        p.zapisi("https://a.test/1", kanali_iptv.DELUJE)
        self.assertTrue(p.deluje("https://a.test/1"))
        self.assertEqual(p.meta().get("vrnjeni"), 1)

    def test_pozabi_zaklenjene(self):
        p = kanali_iptv.PreverbaKanalov(self.pot)
        p.zapisi("https://a.test/z", kanali_iptv.ZAKLENJEN)
        p.zapisi("https://a.test/m", kanali_iptv.MRTEV)
        self.assertEqual(p.pozabi(["https://a.test/z", "https://a.test/m"]), 1)
        self.assertIsNone(p.izid("https://a.test/z"))
        self.assertEqual(p.izid("https://a.test/m"), kanali_iptv.MRTEV)

    def test_vzporedno_najvec_stiri_in_en_na_gostitelja(self):
        zaklep = threading.Lock()
        hkrati, na_gostitelja, najvec = [0], {}, {"skupaj": 0, "gostitelj": 0}

        def preveri(url, glave, rok, domace):
            gost = url.split("/")[2]
            with zaklep:
                hkrati[0] += 1
                na_gostitelja[gost] = na_gostitelja.get(gost, 0) + 1
                najvec["skupaj"] = max(najvec["skupaj"], hkrati[0])
                najvec["gostitelj"] = max(najvec["gostitelj"], na_gostitelja[gost])
            time.sleep(0.02)
            with zaklep:
                hkrati[0] -= 1
                na_gostitelja[gost] -= 1
            return kanali_iptv.DELUJE, "ts"

        obvestila = []
        p = kanali_iptv.PreverbaKanalov(self.pot, preveri=preveri)
        p.ob_spremembi = lambda: obvestila.append(1)
        kanali = [("https://g%d.test/k%d" % (i % 6, i), {}, False) for i in range(60)]
        self.assertEqual(p.preveri_v_ozadju(kanali), 60)
        self.assertEqual(p.preveri_v_ozadju(kanali), 0)          # ze v vrsti: ne dvakrat
        self.assertTrue(p.pocakaj(20))
        self.assertLessEqual(najvec["skupaj"], kanali_iptv.VZPOREDNO)
        self.assertEqual(najvec["gostitelj"], 1)
        self.assertEqual(p.povzetek(u for u, _g, _d in kanali)[kanali_iptv.DELUJE], 60)
        self.assertTrue(obvestila)


# ---------------------------------------------------------------------------------------------- katalog

def _seznam_si():
    return ["#EXTINF:-1 tvg-id=\"H2.si@SD\" http-user-agent=\"A (KHTML, like Gecko) B\" group-title=\"Documentary\",H2 HD",
            "http://tok.primer.test/h2.m3u8",
            "#EXTINF:-1 tvg-id=\"KanalA.si@SD\" group-title=\"General\",Kanal A",
            "http://tok.primer.test/kanala.m3u8",
            "#EXTINF:-1 tvg-id=\"Mrtev.si@SD\" group-title=\"General\",Mrtvi kanal",
            "http://tok.primer.test/mrtev.m3u8",
            "#EXTINF:-1 tvg-id=\"Zaklenjen.si@SD\" group-title=\"Sports\",Zaklenjeni sport",
            "http://tok.primer.test/zaklenjen.m3u8",
            "#EXTINF:-1 tvg-id=\"Sosed.hu@SD\" group-title=\"General\",Sosednji kanal (Hungary)",
            "http://tok.primer.test/sosed.m3u8",
            "#EXTINF:-1 tvg-id=\"NeVesCas.si@SD\" group-title=\"General\",Lokalni kanal [Not 24/7]",
            "http://tok.primer.test/ne247.m3u8"]


class Katalog(unittest.TestCase):
    SEZNAM = "https://iptv-org.github.io/iptv/countries/si.m3u"

    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        stevci = {}
        vnosi = _razcleni(self.SEZNAM, _seznam_si(), stevci)
        vir = {"id": "si", "url": self.SEZNAM, "ime": "si (25)", "posodobljeno": 1, "napaka": "", "stevilo": len(vnosi),
               "vnosi": vnosi, "razclenitev": kanali_iptv.RAZCLENITEV, "ne_24_7": stevci.get("ne_24_7", 0)}
        (Path(self.mapa.name) / "media.json").write_text(json.dumps({"viri": [vir], "osebni_strezniki": []}), encoding="utf-8")
        self.mc = os_media.MediaCenter(self.mapa.name, roots=[], secret_decryptor=lambda v: "")
        self.mc._ima_embed_vir = lambda data=None: False
        self.mc._zakoniti_viri.get = lambda *a, **k: []
        self.mc._personal_items = lambda *a, **k: []
        self.mc.izbrana_drzava = "SI"
        self.mc._drzava_uporabnika = lambda: "SI"
        self.preverjeni = []
        self.mc.kanali.preveri_v_ozadju = lambda kanali: self.preverjeni.extend(u for u, _g, _d in kanali) or 0
        for konec, izid in (("h2", kanali_iptv.DELUJE), ("kanala", kanali_iptv.DELUJE), ("mrtev", kanali_iptv.MRTEV),
                            ("zaklenjen", kanali_iptv.ZAKLENJEN), ("sosed", kanali_iptv.DELUJE)):
            self.mc.kanali.zapisi("http://tok.primer.test/%s.m3u8" % konec, izid)
        p = mock.patch.object(zakoniti_viri, "tv_v_zivo", lambda drzava="": [])
        p.start()
        self.addCleanup(p.stop)

    def naslovi(self, vrsta, iskanje=""):
        return sorted(x["naslov"] for x in self.mc.catalog(iskanje, vrsta)["vnosi"])

    def test_serije_in_filmi_brez_kanalov(self):
        self.assertEqual(self.naslovi("serija"), [])
        self.assertEqual(self.naslovi("film"), [])

    def test_tv_v_zivo_samo_delujoci_iz_drzave_uporabnika(self):
        # Mrtev, zaklenjen in »Not 24/7« ne; sosednja drzava (HU) privzeto ne.
        self.assertEqual(self.naslovi("tv-v-zivo"), ["H2 HD", "Kanal A"])

    def test_iskanje_in_predlogi_brez_mrtvih(self):
        self.assertEqual(self.naslovi("vse", "kanal"), ["Kanal A"])
        self.assertEqual([x["naslov"] for x in self.mc.isci_v_predpomnilniku("kanal")], ["Kanal A"])

    def test_izbira_drzave_v_virih(self):
        self.mc.nastavi_tv_izbiro(["SI", "HU"], ["en"])
        self.assertEqual(self.naslovi("tv-v-zivo"), ["H2 HD", "Kanal A", "Sosednji kanal (Hungary)"])
        na_voljo = self.mc.tv_izbira_na_voljo()
        self.assertEqual({d["id"] for d in na_voljo["drzave"]}, {"SI", "HU"})

    def test_gumbi_drzav_tv_samo_z_dovolj_kanali(self):
        self.mc.nastavi_tv_izbiro(["SI", "HU"], ["en"])
        self.assertNotIn("HU", [d["id"] for d in self.mc.tv_drzave()])           # en sam kanal: brez gumba
        with mock.patch.object(os_media.MediaCenter, "TV_DRZAVA_KANALOV", 1):
            self.assertIn("HU", [d["id"] for d in self.mc.tv_drzave()])
        self.assertEqual(self.mc.catalog("", "tv-v-zivo", "HU")["vnosi"][0]["naslov"], "Sosednji kanal (Hungary)")

    def test_stevec_virov_steje_samo_delujoce(self):
        vir = next(v for v in self.mc.sources() if v.get("id") == "si")
        self.assertEqual(vir["stevilo"], 2)
        self.assertEqual(vir["kanali"]["zaklenjenih"], 1)
        self.assertEqual(vir["kanali"]["mrtvih"], 1)
        self.assertEqual(vir["kanali"]["ne_24_7"], 1)
        self.assertTrue(vir["kanali"]["javni"])

    def test_neznani_kanali_gredo_v_preverbo_ne_na_zaslon(self):
        self.mc.kanali.pozabi(["http://tok.primer.test/kanala.m3u8"], (kanali_iptv.DELUJE,))
        self.assertEqual(self.naslovi("tv-v-zivo"), ["H2 HD"])
        self.assertIn("http://tok.primer.test/kanala.m3u8", self.preverjeni)
        self.assertNotIn("http://tok.primer.test/ne247.m3u8", self.preverjeni)
        self.assertNotIn("http://tok.primer.test/sosed.m3u8", self.preverjeni)    # ni izbran: vira ne bremenimo

    def test_kanal_ki_ne_zaigra_izgine(self):
        kartica = next(x for x in self.mc.catalog("", "tv-v-zivo")["vnosi"] if x["naslov"] == "Kanal A")
        self.assertTrue(self.mc.skrij_kanal(kartica))
        self.assertEqual(self.naslovi("tv-v-zivo"), ["H2 HD"])
        self.assertTrue(self.mc.kanal_skrit(kartica))
        self.assertEqual(self.mc.brez_nerazpolozljivih({"vnosi": [kartica], "skupaj": 1})["vnosi"], [])

    def test_preverba_ne_nalozi_mreze_znova(self):
        # Preverba v ozadju traja minute: stran ne sme vsakih 5 s nalagati mreze znova (drsenje bi skakalo na zacetek).
        klici = []
        self.mc.ob_virih = lambda: klici.append("viri")
        self.mc.ob_kanalih = lambda: klici.append("kanali")
        self.mc._kanali_spremenjeni()
        self.assertEqual(klici, ["kanali"])
        self.mc._kanali_spremenjeni(viri=True)               # vir je bil prebran znova: viri in katalog
        self.assertEqual(klici, ["kanali", "viri"])

    def test_stara_razclenitev_se_ne_pokaze_in_se_osvezi(self):
        data = json.loads((Path(self.mapa.name) / "media.json").read_text(encoding="utf-8"))
        data["viri"][0].pop("razclenitev")
        for v in data["viri"][0]["vnosi"]:
            v.pop("iptv", None)
            v["vrsta"] = "serija"                     # kot v lastnikovem media.json pred popravkom
        (Path(self.mapa.name) / "media.json").write_text(json.dumps(data), encoding="utf-8")
        osvezeni = []
        self.mc._osvezi_zastarele_v_ozadju = lambda idji: osvezeni.extend(idji)
        self.assertEqual(self.naslovi("serija"), [])
        self.assertEqual(osvezeni, ["si"])


class SerijaSeznama(unittest.TestCase):
    def test_epizode_so_ena_kartica_s_sezonami(self):
        vrstice = []
        for s, e in ((1, 1), (1, 2), (2, 1)):
            vrstice += ['#EXTINF:-1 tvg-name="Primer S%02dE%02d" group-title="Serije",Primer S%02dE%02d' % (s, e, s, e),
                        "https://primer.test/series/u/g/%d%d.mkv" % (s, e)]
        with tempfile.TemporaryDirectory() as td:
            vnosi = _razcleni("https://primer.test/vod.m3u", vrstice)
            vir = {"id": "vod", "url": "https://primer.test/vod.m3u", "ime": "VOD", "vnosi": vnosi,
                   "razclenitev": kanali_iptv.RAZCLENITEV, "stevilo": 3}
            (Path(td) / "media.json").write_text(json.dumps({"viri": [vir], "osebni_strezniki": []}), encoding="utf-8")
            mc = os_media.MediaCenter(td, roots=[], secret_decryptor=lambda v: "")
            mc._ima_embed_vir = lambda data=None: False
            mc._zakoniti_viri.get = lambda *a, **k: []
            mc._personal_items = lambda *a, **k: []
            serije = mc.catalog("", "serija")["vnosi"]
            self.assertEqual([x["naslov"] for x in serije], ["Primer"])
            podrobnosti = mc.details(serije[0]["id"])
            self.assertEqual([s["stevilka"] for s in podrobnosti["sezone"]], [1, 2])     # ne »Sezone niso na voljo«
            self.assertEqual([e["stevilka"] for e in mc.season_seznama(serije[0]["id"], 1)["epizode"]], [1, 2])
            epizoda = mc.epizoda_seznama(serije[0]["id"], 1, 2)
            self.assertEqual(epizoda["url"], "https://primer.test/series/u/g/12.mkv")


class Vmesnik(unittest.TestCase):
    """Stran (assets/os/os.js): polica »Na tvojih napravah« v Serijah brez filmov, sporocilo ob skritem kanalu,
    besedila v vseh sestih jezikih."""

    def setUp(self):
        koren = Path(__file__).resolve().parent.parent
        self.js = (koren / "assets" / "os" / "os.js").read_text(encoding="utf-8")
        self.besedila = (koren / "assets" / "os" / "besedila.js").read_text(encoding="utf-8")

    def test_polica_v_serijah_samo_serije(self):
        # Lastnik, 25. 10. 2026: kartica »Preizkus« (film, preizkusni prenos s testnega telefona) je bila prva v Serijah.
        from tests.test_medijski_center_videz import _funkcija, _node
        koda = "var kat = {};\n" + _funkcija(self.js, "knjiznicaZaFilter") + """
        var vnosi = [{naslov: "Preizkus", vrsta: "film"}, {naslov: "Serija", vrsta: "serija"}];
        var izid = [];
        ["serija", "film", "vse"].forEach(function (f) { kat.filter = f; izid.push(knjiznicaZaFilter(vnosi).map(function (x) { return x.naslov; })); });
        console.log(JSON.stringify(izid));"""
        self.assertEqual(_node(koda), [["Serija"], ["Preizkus"], ["Preizkus", "Serija"]])
        self.assertIn("knjiznicaZaFilter(kat.knjiznica || [])", _funkcija(self.js, "narisiKnjiznico"))

    def test_sporocilo_in_besedila(self):
        self.assertIn('obvesti(t("katKanalSkrit", { ime: podatki.kanal }))', self.js)
        import shutil
        import subprocess
        if not shutil.which("node"):
            raise unittest.SkipTest("node ni namescen")
        kljuci = ["katKanalSkrit", "katKanaliDeluje", "katKanaliPreverjam", "katKanaliZaklenjeni", "katKanaliIzbira",
                  "katKanaliIzbiraNamig", "katKanaliDrzave", "katKanaliJeziki"]
        koda = self.besedila + "\nconsole.log(JSON.stringify(%s.map(function (k) { return ['sl','en','de','es','fr','it'].filter(function (j) { return !BESEDILA_OS[j][k]; }); })));" % json.dumps(kljuci)
        with tempfile.TemporaryDirectory() as td:
            datoteka = Path(td) / "besedila.js"
            datoteka.write_text(koda, encoding="utf-8")
            izid = subprocess.run(["node", str(datoteka)], capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(izid), [[] for _ in kljuci])
        for k in kljuci:
            self.assertIn('"%s"' % k, self.js)

    def test_preverba_kanalov_osvezi_samo_nepolno_mrezo(self):
        dogodek = self.js.split('if (vrsta === "mediaKanaliPreverjeni" && katVidno()) {', 1)[1].split("\n    }\n", 1)[0]
        self.assertIn("kat.katalog.length < 24) naloziKatalog();", dogodek)
        self.assertIn("!viriKanalov.contains(document.activeElement)", dogodek)
        py = (Path(__file__).resolve().parent.parent / "core" / "os_katalog.py").read_text(encoding="utf-8")
        self.assertIn('self._mc.ob_kanalih = lambda: self.dogodek("mediaKanaliPreverjeni", None)', py)

    def test_serija_seznama_poslje_id_kartice(self):
        self.assertIn('klic("mediaSezona", [item.tmdb_id, season, item.id])', self.js)
        self.assertEqual(self.js.count('ep.stevilka, item.naslov + " · " + ep.naslov, item.id]'), 2)


if __name__ == "__main__":
    unittest.main()
