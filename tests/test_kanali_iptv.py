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
import urllib.error
from pathlib import Path
from unittest import mock

from core import kanali_iptv, os_media, viri_sink, zakoniti_viri

PRIMERI = Path(__file__).resolve().parent / "skupni-primeri" / "iptv-m3u.json"
#: Zascita racuna (pregled 39, I1): ista datoteka kot Android tests/skupni-primeri (IptvPravila).
PRIMERI_RACUNA = PRIMERI.parent / "iptv-racun.json"


def _razcleni(seznam, vrstice, stevci=None):
    besedilo = "#EXTM3U\n" + "\n".join(vrstice) + "\n"
    return os_media.parse_payload(besedilo.encode("utf-8"), "audio/x-mpegurl", seznam, "vir1", "Seznam", stevci=stevci)


class SkupniPrimeri(unittest.TestCase):
    def test_privzeta_izbira(self):
        # Lastnik, 25. 10. 2026: privzeto drzava uporabnika in drzave z anglescino, ne vsi kanali v anglescini.
        d = json.loads(PRIMERI.read_text(encoding="utf-8"))
        izbira = kanali_iptv.privzeta_izbira(d["drzava_uporabnika"])
        self.assertEqual(izbira, {"drzave": d["privzete_drzave"], "jeziki": []})
        self.assertEqual(kanali_iptv.privzeta_izbira("gb")["drzave"], ["GB", "US", "CA", "AU", "IE", "NZ"])
        self.assertEqual(kanali_iptv.privzeta_izbira("")["drzave"], ["US", "GB", "CA", "AU", "IE", "NZ"])

    def test_primeri_racuna(self):
        d = json.loads(PRIMERI_RACUNA.read_text(encoding="utf-8"))
        self.assertGreaterEqual((len(d["seznami"]), len(d["kanali"])), (10, 8))
        for p in d["seznami"]:
            with self.subTest(p["url"]):
                self.assertIs(kanali_iptv.javni_brezplacni(p["url"]), p["javni"])
        for p in d["kanali"]:
            with self.subTest(p["url"]):
                self.assertIs(kanali_iptv.s_poverilnicami(p["url"]), p["racun"])

    def test_primeri_virov_ob_dvomu_ozji_krog(self):
        """Pregled 46, Ö1: vir gre napravam zunaj ozjega kroga in na zaslon s celim naslovom samo, ce je pozitivno znan
        javen (verzija 2 skupnih primerov - enako Android)."""
        d = json.loads(PRIMERI_RACUNA.read_text(encoding="utf-8"))
        self.assertGreaterEqual(d["verzija"], 2)
        self.assertGreaterEqual(len(d["viri"]), 15)
        for p in d["viri"]:
            with self.subTest(repr(p["naslov"]), oznacen=p.get("oznacen", False)):
                oznacen = p.get("oznacen", False)
                self.assertIs(viri_sink.za_ozji_krog(p["naslov"], oznacen), p["ozji"])
                self.assertIs(viri_sink.znan_javen(p["naslov"], oznacen), not p["ozji"])
                if "prikaz" in p:
                    self.assertEqual(viri_sink.prikaz_naslova(p["naslov"], oznacen), p["prikaz"])
                self.assertNotIn("skrito-geslo", viri_sink.prikaz_naslova(p["naslov"], oznacen) if p["ozji"] else "")

    def test_primeri_prevzema(self):
        """Pregled 46, Ö3: vir z druge naprave po odgovoru "ozji" (skupni primeri - enako Android)."""
        d = json.loads(PRIMERI_RACUNA.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(d["prevzem"]), 6)
        for p in d["prevzem"]:
            with self.subTest(p["naslov"], ozji=p["ozji"]):
                self.assertIs(viri_sink.prevzem_dovoljen(p["naslov"], p["ozji"]), p["prevzem"])

    def test_vsi_primeri(self):
        d = json.loads(PRIMERI.read_text(encoding="utf-8"))
        primeri = d["primeri"]
        izbira = kanali_iptv.privzeta_izbira(d["drzava_uporabnika"])
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
                if "privzeto_viden" in pricakovano:
                    # Rocno dodani seznami se ne filtrirajo po drzavi; javni (iptv-org) po privzeti izbiri.
                    viden = not kanali_iptv.je_javni_seznam(p["seznam"]) or kanali_iptv.v_izbiri(v, izbira)
                    self.assertEqual(viden, pricakovano["privzeto_viden"], "privzeto_viden")


class Razclenitev(unittest.TestCase):
    def test_vejica_zunaj_narekovajev(self):
        trajanje, atributi, ime = kanali_iptv.razcleni_extinf(
            '#EXTINF:-1 tvg-id="a.si" http-user-agent="X (KHTML, like Gecko) Y" group-title="A,B",Ime, z vejico')
        self.assertEqual((trajanje, ime), (-1.0, "Ime, z vejico"))
        self.assertEqual(atributi["group-title"], "A,B")
        self.assertEqual(atributi["http-user-agent"], "X (KHTML, like Gecko) Y")

    def test_unicode_locilo_vrstic_v_imenu(self):
        vnosi = _razcleni("https://iptv-org.github.io/iptv/countries/si.m3u",
                          ['#EXTINF:-1 tvg-id="A.si@SD" group-title="News",Kanal\u2028Dva\x85Tri',
                           "https://tok.primer.test/a.m3u8"])
        self.assertEqual([(v["naslov"], v["url"]) for v in vnosi], [("Kanal Dva Tri", "https://tok.primer.test/a.m3u8")])

    def test_ime_iz_tvg_name(self):
        self.assertEqual(kanali_iptv.razcleni_extinf('#EXTINF:-1 tvg-name="Rezerva" group-title="X",')[2], "Rezerva")

    def test_kind_ne_naredi_serije_iz_podniza_tv(self):
        # Splosni viri (JSON, HTML): »Exodus TV« ali gostitelj ».tv« nista serija; beseda za serijo ali pot /tv/ je.
        self.assertNotEqual(os_media._kind("", "https://primer.test/exodus.m3u8", "Exodus TV"), "serija")
        self.assertNotEqual(os_media._kind("", "https://kanal.tv/v/1.mp4", "Oddaja"), "serija")
        self.assertEqual(os_media._kind("", "https://primer.test/tv/123", "Naslov"), "serija")
        self.assertEqual(os_media._kind("series", "https://primer.test/1.mp4", "Naslov"), "serija")

    def test_dolga_vrstica_extinf_v_linearnem_casu(self):
        """Pregled 30, J4: regularni izrazi atributov in opomb so bili kvadratni v dolzini vrstice (izmerjeno 26. 10.
        2026: 20 KB crk 5,7 s; 1 MB bi bile ure ob vsakem zagonu). Vrstica 1 MB se mora razcleniti hitro - v locenem
        procesu z rokom, da kvadraten izraz ne ustavi preizkusov za ure."""
        import subprocess
        import sys
        koren = str(Path(__file__).resolve().parents[1])
        koda = (
            "import json, sys, time\n"
            "sys.path.insert(0, %r)\n"
            "from core import os_media\n"
            "casi = {}\n"
            "for ime, znak in (('crke', 'a'), ('presledki', ' '), ('narekovaji', 'a=\"')):\n"
            "    telo = znak * (1000000 // len(znak))\n"
            "    s = '#EXTM3U\\n#EXTINF:-1 tvg-id=\"x.si\" ' + telo + ',Kanal ' + telo + ' (720p)\\nhttp://p.test/k.m3u8\\n'\n"
            "    z = time.perf_counter()\n"
            "    os_media.parse_payload(s.encode(), 'audio/x-mpegurl', 'http://p.test/s.m3u', 'v', 'S')\n"
            "    casi[ime] = time.perf_counter() - z\n"
            "print(json.dumps(casi))\n" % koren)
        izid = subprocess.run([sys.executable, "-c", koda], capture_output=True, text=True, timeout=120, cwd=koren)
        self.assertEqual(izid.returncode, 0, izid.stderr[-2000:])
        casi = json.loads(izid.stdout.strip().splitlines()[-1])
        for ime, cas in casi.items():
            self.assertLess(cas, 3.0, "%s: %.1f s" % (ime, cas))

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
_IZVIRNI_DOVOLJEN_IP = kanali_iptv.dovoljen_ip
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
        if pot == "/preusmeri-glave":
            return self._poslji(302, glave={"Location": "http://drug.test:%d/glave" % self.server.server_address[1]})
        if pot == "/glave":
            return self._poslji(200, TS) if self.headers.get("Referer") and not self.headers.get("Cookie") \
                else self._poslji(403)
        if pot == "/preusmeri-drugam":
            return self._poslji(302, glave={"Location": "http://127.0.0.2:%d/ts" % self.server.server_address[1]})
        if pot == "/ua":
            return self._poslji(200, TS) if self.headers.get("User-Agent") == "Posebni/1.0" else self._poslji(403)
        if pot == "/pocasi":
            time.sleep(2.5)
            return self._poslji(200, TS)
        if pot in ("/kaplja-glave", "/kaplja-telo"):
            # Streznik po kapljicah (pregled 30, J1): vsak bajt pred rokom vticnice, vsega skupaj pa ~18 s.
            self.close_connection = True
            try:
                self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Type: video/mp2t\r\n")
                if pot == "/kaplja-telo":
                    self.wfile.write(b"\r\n")
                for i in range(60):
                    time.sleep(0.3)
                    self.wfile.write(b"G" if pot == "/kaplja-telo" else b"X-K%d: a\r\n" % i)
            except OSError:
                pass
            return None
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

    def setUp(self):
        # Preizkusni streznik je na 127.0.0.1; v izdelku loopback ni dovoljen nikoli (pregled 30, J2).
        izvirni = kanali_iptv.dovoljen_ip
        p = mock.patch.object(kanali_iptv, "dovoljen_ip",
                              lambda naslov, domace: (domace and naslov == "127.0.0.1") or izvirni(naslov, domace))
        p.start()
        self.addCleanup(p.stop)

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

    def test_loopback_nikoli_nat64_in_6to4_kot_ipv4(self):
        izvirni = _IZVIRNI_DOVOLJEN_IP                                 # setUp zamenja dovoljen_ip za 127.0.0.1
        for naslov in ("127.0.0.1", "127.1.2.3", "::1", "::ffff:127.0.0.1"):
            self.assertFalse(izvirni(naslov, True), naslov)
        self.assertTrue(izvirni("192.168.1.5", True))
        self.assertFalse(izvirni("192.168.1.5", False))
        self.assertTrue(izvirni("8.8.8.8", False))
        self.assertFalse(izvirni("64:ff9b::c0a8:101", False))         # NAT64 -> 192.168.1.1
        self.assertFalse(izvirni("2002:c0a8:101::1", False))           # 6to4 -> 192.168.1.1
        self.assertTrue(izvirni("64:ff9b::808:808", False))            # NAT64 -> 8.8.8.8

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

    def test_piskotek_seznama_samo_izvornemu_gostitelju(self):
        razresi = lambda gost, vrata, **k: [(2, 1, 6, "", ("127.0.0.1", vrata))]  # noqa: E731
        izid = kanali_iptv.preveri_tok("http://izvor.test:%d/preusmeri-glave" % self.vrata, domace=True, razresi=razresi,
                                       glave={"Cookie": "seja=SKRIVNO", "Referer": "https://seznam.test/"})
        self.assertEqual(izid, (kanali_iptv.DELUJE, "ts"), "piskotek seznama je sel drugemu gostitelju")

    def test_glave_seznama(self):
        self.assertEqual(self.preveri("/ua")[0], kanali_iptv.ZAKLENJEN)
        self.assertEqual(self.preveri("/ua", glave={"User-Agent": "Posebni/1.0"}), (kanali_iptv.DELUJE, "ts"))

    def test_rok(self):
        zacetek = time.monotonic()
        self.assertEqual(self.preveri("/pocasi", rok=1.0), (kanali_iptv.MRTEV, "rok"))
        self.assertLess(time.monotonic() - zacetek, 2.0)

    def test_skupni_rok_glave_in_telo_po_kapljicah(self):
        for pot in ("/kaplja-glave", "/kaplja-telo"):
            with self.subTest(pot):
                zacetek = time.monotonic()
                izid = self.preveri(pot, rok=1.0)
                self.assertEqual(izid[0], kanali_iptv.MRTEV)
                self.assertLess(time.monotonic() - zacetek, 2.5, "rok vticnice ni skupni rok")
        self.assertEqual(self.preveri("/kaplja-glave", rok=1.0), (kanali_iptv.MRTEV, "rok"))

    def test_dns_z_rokom(self):
        def pocasen(gost, vrata, **k):
            time.sleep(4)
            return [(2, 1, 6, "", ("127.0.0.1", vrata))]
        zacetek = time.monotonic()
        izid = kanali_iptv.preveri_tok("http://pocasen.test:%d/ts" % self.vrata, rok=1.0, domace=True, razresi=pocasen)
        self.assertEqual(izid, (kanali_iptv.MRTEV, "rok"))
        self.assertLess(time.monotonic() - zacetek, 2.0)

    def test_stirje_pocasni_gostitelji_ne_ustavijo_preverbe(self):
        razresi = lambda gost, vrata, **k: [(2, 1, 6, "", ("127.0.0.1", vrata))]  # noqa: E731
        mapa = tempfile.TemporaryDirectory()
        self.addCleanup(mapa.cleanup)
        p = kanali_iptv.PreverbaKanalov(
            Path(mapa.name) / "p.json",
            preveri=lambda url, glave, rok, domace: kanali_iptv.preveri_tok(url, glave, rok, True, razresi=razresi))
        kanali = [("http://p%d.test:%d/kaplja-glave" % (i, self.vrata), {}, False) for i in range(4)]
        kanali.append(("http://dober.test:%d/ts" % self.vrata, {}, False))
        with mock.patch.object(kanali_iptv, "ROK_S", 1.0), mock.patch.object(kanali_iptv, "PREMOR_GOSTITELJA_S", 0.0):
            p.preveri_v_ozadju(kanali)
            self.assertTrue(p.pocakaj(6), "stirje pocasni gostitelji so ustavili preverbo")
        self.assertTrue(p.deluje("http://dober.test:%d/ts" % self.vrata))

    def test_dnevna_meja_steje_vsako_zahtevo(self):
        """Pregled 39, I8: ena preverba HLS je vec zahtev (glavni seznam, razlicica, kos) - meja jih steje vse, stevec
        je na disku (velja po ponovnem zagonu). Prej je stela samo izbiro kanala (1)."""
        with tempfile.TemporaryDirectory() as mapa:
            pot = Path(mapa) / "kanali-preverba.json"
            p = kanali_iptv.PreverbaKanalov(pot, preveri=lambda url, glave, rok, domace:
                                            kanali_iptv.preveri_tok(url, glave, rok, True))
            url = "http://127.0.0.1:%d/glavni.m3u8" % self.vrata
            _Streznik.zahteve[:] = []
            p.preveri_v_ozadju([(url, {}, False)])
            self.assertTrue(p.pocakaj(10))
            self.assertEqual(p.izid(url), kanali_iptv.DELUJE)
            zahtev = len(_Streznik.zahteve)
            self.assertGreaterEqual(zahtev, 3)
            odtis = kanali_iptv.kljuc("127.0.0.1")[:12]
            self.assertEqual(p.meta()["odprtja"]["g"][odtis], zahtev)
            self.assertEqual(json.loads(pot.read_text(encoding="utf-8"))["meta"]["odprtja"]["g"][odtis], zahtev)

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

    def test_rok_se_enkrat_ponovi_z_daljsim_rokom(self):
        # Izmerjeno 25. 10. 2026: 14 od 50 kanalov z »rok« (4 s) je ob ponovni preverbi delovalo.
        ura = [1000.0]
        roki = []
        p = kanali_iptv.PreverbaKanalov(self.pot, preveri=lambda u, g, rok, d: (roki.append(rok), (kanali_iptv.MRTEV, "rok"))[1],
                                        ura=lambda: ura[0])
        p.zapisi("https://a.test/r", kanali_iptv.MRTEV, "rok")
        p.zapisi("https://a.test/404", kanali_iptv.MRTEV, "http-404")
        self.assertFalse(p.potrebuje_preverbo("https://a.test/r"))
        ura[0] += kanali_iptv.PONOVI_PO_S
        self.assertTrue(p.potrebuje_preverbo("https://a.test/r"))
        self.assertFalse(p.potrebuje_preverbo("https://a.test/404"))      # 404 velja 24 h
        p.preveri_v_ozadju([("https://a.test/r", {}, False)])
        self.assertTrue(p.pocakaj(5))
        self.assertEqual(roki, [kanali_iptv.ROK_PONOVNO_S])
        ura[0] += kanali_iptv.PONOVI_PO_S
        self.assertFalse(p.potrebuje_preverbo("https://a.test/r"))        # drugi neuspeh: 24 h
        p.oznaci_mrtev("https://a.test/klik")
        ura[0] += kanali_iptv.PONOVI_PO_S
        self.assertFalse(p.potrebuje_preverbo("https://a.test/klik"))     # klik brez predvajanja ni »rok«

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
        premor = mock.patch.object(kanali_iptv, "PREMOR_GOSTITELJA_S", 0.0)
        premor.start()
        self.addCleanup(premor.stop)
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

    def test_neznani_kanal_je_viden_z_oznako_in_gre_v_preverbo(self):
        # Pregled 30, J3: neznan kanal je viden (»preverjam«), dokler preverba ne pove, da ne oddaja - prej je bil TV v
        # zivo prazen, dokler preverba (pri ponudniku ure) ni koncala.
        self.mc.kanali.pozabi(["http://tok.primer.test/kanala.m3u8"], (kanali_iptv.DELUJE,))
        vnosi = {x["naslov"]: x for x in self.mc.catalog("", "tv-v-zivo")["vnosi"]}
        self.assertEqual(sorted(vnosi), ["H2 HD", "Kanal A"])
        self.assertTrue(vnosi["Kanal A"].get("preverjam"))
        self.assertFalse(vnosi["H2 HD"].get("preverjam"))
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


class ZastareliVirZnova(unittest.TestCase):
    """Pregled 30, J9: vir s staro razclenitvijo, ki ga ni bilo mogoce prebrati, je ostal skrit do ponovnega zagona."""

    def test_neuspela_ponovna_razclenitev_se_ponovi(self):
        mapa = tempfile.TemporaryDirectory()
        self.addCleanup(mapa.cleanup)
        mc = os_media.MediaCenter(mapa.name, roots=[], secret_decryptor=lambda v: "")
        klici = []

        def refresh_source(ident):
            klici.append(ident)
            raise OSError("brez povezave")
        mc.refresh_source = refresh_source
        mc._kanali_spremenjeni = lambda viri=False: None
        mc._osvezi_zastarele_v_ozadju(["vir1"])
        time.sleep(0.3)
        mc._osvezi_zastarele_v_ozadju(["vir1"])                     # takoj: ne znova
        time.sleep(0.3)
        with mock.patch.object(os_media.MediaCenter, "ZASTARELI_ZNOVA_S", 0.0):
            mc._osvezi_zastarele_v_ozadju(["vir1"])                 # po casu: znova
            time.sleep(0.3)
        self.assertEqual(klici, ["vir1", "vir1"])


class ZavrnjenSeznam(unittest.TestCase):
    """Pregled 39, I5: seznam, ki ga ponudnik zavrne (401/403 - racun potekel ali zaklenjen), se je ob odprtju kataloga
    prenesel znova vsakih 10 min; neuspeh brez izjeme (refresh_source napako zapise v vir) pa je vir skril do
    ponovnega zagona (J9 ni deloval)."""
    XTREAM = "http://ponudnik.test:8080/get.php?username=uporabnik&password=geslo&type=m3u_plus"

    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        vir = {"id": "xt", "url": self.XTREAM, "ime": "Ponudnik", "posodobljeno": 1, "napaka": "", "stevilo": 0,
               "vnosi": []}                     # brez »razclenitev«: stara razclenitev, katalog ga prebere znova
        (Path(self.mapa.name) / "media.json").write_text(json.dumps({"viri": [vir], "osebni_strezniki": []}),
                                                        encoding="utf-8")
        self.mc = os_media.MediaCenter(self.mapa.name, roots=[], secret_decryptor=lambda v: "")
        self.mc._kanali_spremenjeni = lambda viri=False: None
        self.prenosi = []

        def prenesi(url):
            self.prenosi.append(url)
            raise urllib.error.HTTPError(url, 403, "Forbidden", None, None)
        self.mc._download = prenesi

    def _odpri_katalog(self):
        self.mc._vnosi_virov(self.mc._load(), "tv-v-zivo")
        for nit in threading.enumerate():
            if nit.name == "media-razclenitev":
                nit.join(5)

    def _vir(self):
        return next(v for v in self.mc._load()["viri"] if v["id"] == "xt")

    def _postaraj(self, sekund):
        with self.mc._lock:
            data = self.mc._load()
            data["viri"][0]["zavrnjen"]["ob"] -= sekund
            self.mc._save(data)

    def test_zavrnjen_seznam_vse_redkeje(self):
        with mock.patch.object(os_media, "_resolve_embed_or_direct_source",
                               side_effect=AssertionError("se ena zahteva na naslov, ki ga je ponudnik zavrnil")), \
                mock.patch.object(os_media.MediaCenter, "ZASTARELI_ZNOVA_S", 0.0):
            self._odpri_katalog()
            self.assertEqual(len(self.prenosi), 1)
            self.assertEqual((self._vir()["zavrnjen"]["koda"], self._vir()["zavrnjen"]["n"]), (403, 1))
            # (sekund od zadnje zavrnitve, skupno stevilo prenosov): premori 10 min, 1 h, 6 h, nato 24 h
            for sekund, prenosov in ((0, 1), (601, 2), (601, 2), (3601, 3), (6 * 3600 + 1, 4), (24 * 3600 + 1, 5),
                                     (6 * 3600 + 1, 5), (24 * 3600 + 1, 6)):
                if sekund:
                    self._postaraj(sekund)
                self._odpri_katalog()
                self.assertEqual(len(self.prenosi), prenosov, (sekund, self._vir().get("zavrnjen")))
        vir = next(v for v in self.mc.sources() if v["id"] == "xt")
        self.assertEqual(vir["zavrnjen"]["koda"], 403)          # stran pokaze katVirZavrnjen (6 jezikov)
        self.assertTrue(vir["napaka"])
        # Rocna osvezitev velja takoj; ko ponudnik seznam spet da, oznake ni vec.
        self.mc._download = lambda url: (b"#EXTM3U\n#EXTINF:-1 tvg-id=\"K1.si\",Kanal 1\n"
                                         b"http://ponudnik.test:8080/live/u/g/1.ts\n", "audio/x-mpegurl", url)
        self.assertTrue(self.mc.refresh_source("xt")["ok"])
        self.assertNotIn("zavrnjen", self._vir())

    def test_neuspeh_brez_izjeme_se_ponovi(self):
        def prenesi(url):
            self.prenosi.append(url)
            raise OSError("brez povezave")
        self.mc._download = prenesi
        with mock.patch.object(os_media, "_resolve_embed_or_direct_source", lambda *a, **k: []):
            self._odpri_katalog()
            self._odpri_katalog()                                # takoj: ne znova (ZASTARELI_ZNOVA_S)
            self.assertEqual(len(self.prenosi), 1)
            with mock.patch.object(os_media.MediaCenter, "ZASTARELI_ZNOVA_S", 0.0):
                self._odpri_katalog()
            self.assertEqual(len(self.prenosi), 2, "vir je ostal skrit do ponovnega zagona")
        self.assertNotIn("zavrnjen", self._vir())


def _seznam_eng():
    return ["#EXTINF:-1 tvg-id=\"3ABNTVUganda.ug@SD\" group-title=\"Religious\",3ABN TV Uganda (720p)",
            "https://tok.primer.test/ug.m3u8",
            "#EXTINF:-1 tvg-id=\"BBCNews.uk@SD\" group-title=\"News\",BBC News",
            "https://tok.primer.test/bbc.m3u8",
            "#EXTINF:-1 tvg-id=\"KanalNZ.nz@SD\" group-title=\"General\",Kanal NZ",
            "https://tok.primer.test/nz.m3u8",
            "#EXTINF:-1 group-title=\"Music\",Primer Music TV",
            "https://tok.primer.test/music.m3u8"]


class KatalogAngleskeDrzave(unittest.TestCase):
    """Lastnik, 25. 10. 2026 (»TV Uganda niti ne rabimo«, »mojo drzavo in angleske«): iz seznama languages/eng.m3u so
    privzeto vidni samo kanali drzav z anglescino; Uganda in kanali brez drzave sele po izbiri v Virih."""
    SEZNAM = "https://iptv-org.github.io/iptv/languages/eng.m3u"

    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        vnosi = _razcleni(self.SEZNAM, _seznam_eng(), {})
        vir = {"id": "eng", "url": self.SEZNAM, "ime": "eng", "posodobljeno": 1, "napaka": "", "stevilo": len(vnosi),
               "vnosi": vnosi, "razclenitev": kanali_iptv.RAZCLENITEV, "ne_24_7": 0}
        (Path(self.mapa.name) / "media.json").write_text(json.dumps({"viri": [vir], "osebni_strezniki": []}), encoding="utf-8")
        self.mc = os_media.MediaCenter(self.mapa.name, roots=[], secret_decryptor=lambda v: "")
        self.mc._ima_embed_vir = lambda data=None: False
        self.mc._zakoniti_viri.get = lambda *a, **k: []
        self.mc._personal_items = lambda *a, **k: []
        self.mc.izbrana_drzava = "SI"
        self.mc.kanali.preveri_v_ozadju = lambda kanali: 0
        for konec in ("ug", "bbc", "nz", "music"):
            self.mc.kanali.zapisi("https://tok.primer.test/%s.m3u8" % konec, kanali_iptv.DELUJE)
        p = mock.patch.object(zakoniti_viri, "tv_v_zivo", lambda drzava="": [])
        p.start()
        self.addCleanup(p.stop)

    def naslovi(self):
        return sorted(x["naslov"] for x in self.mc.catalog("", "tv-v-zivo")["vnosi"])

    def test_privzeto_samo_drzave_z_anglescino(self):
        self.assertEqual(self.naslovi(), ["BBC News", "Kanal NZ"])
        self.assertEqual(self.mc.tv_izbira(), {"drzave": ["SI", "US", "GB", "CA", "AU", "IE", "NZ"], "jeziki": []})

    def test_uganda_po_izbiri_v_virih(self):
        self.mc.nastavi_tv_izbiro(["SI", "GB", "UG"], [])
        self.assertEqual(self.naslovi(), ["3ABN TV Uganda", "BBC News"])
        # Jezik v Virih vklopi vse kanale v anglescini, tudi brez znane drzave.
        self.mc.nastavi_tv_izbiro(["SI"], ["en"])
        self.assertEqual(self.naslovi(), ["3ABN TV Uganda", "BBC News", "Kanal NZ", "Primer Music TV"])



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
                  "katKanaliIzbiraNamig", "katKanaliDrzave", "katKanaliJeziki", "katKanaliBrezPreverbe", "katKanaliJavni",
                  "katKanaliJavniNamig", "katVirZavrnjen"]
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


# ---------------------------------------------------------------------------------------------- zascita racuna (J3)

class ZascitaRacuna(unittest.TestCase):
    """Lastnik, 26. 10. 2026: »Nevarnost zaklepa racuna je prioriteta.« Seznamov z racunom v ozadju ne preverjamo;
    javne preverjamo z eno zahtevo na gostitelja, premorom, dnevno mejo in nikoli med predvajanjem."""
    XTREAM = "http://ponudnik.test:8080/get.php?username=uporabnik&password=geslo&type=m3u_plus"

    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.pot = Path(self.mapa.name) / "kanali-preverba.json"

    def test_poverilnice_v_naslovu(self):
        s = kanali_iptv.s_poverilnicami
        self.assertTrue(s("http://p.test:8080/live/uporabnik/geslo/123.ts"))
        self.assertTrue(s("http://p.test/movie/u/p/5.mkv"))
        self.assertTrue(s("http://uporabnik:geslo@tvh.lan:9981/stream/channel/1"))
        self.assertTrue(s(self.XTREAM, seznam=True))
        self.assertTrue(s("https://p.test/seznam.m3u?token=abc", seznam=True))
        self.assertFalse(s("https://cdn.test/live/kanal/index.m3u8?token=abc"))       # podpis CDN ni racun
        self.assertFalse(s("https://iptv-org.github.io/iptv/countries/si.m3u", seznam=True))
        j = kanali_iptv.javni_brezplacni
        self.assertTrue(j("https://iptv-org.github.io/iptv/countries/si.m3u"))
        self.assertTrue(j("https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"))
        self.assertFalse(j(self.XTREAM))
        self.assertFalse(j("http://tvh.lan:9981/playlist"))                           # domace omrezje: ne v ozadju
        self.assertFalse(j("https://ponudnik.test/moj-seznam.m3u"))

    def test_seznam_xtream_s_5000_kanali_ne_odpre_nobene_povezave(self):
        vrstice = []
        for i in range(5000):
            vrstice += ['#EXTINF:-1 tvg-id="K%d.si" tvg-name="Kanal %d" group-title="SI",Kanal %d' % (i, i, i),
                        "http://ponudnik.test:8080/live/uporabnik/geslo/%d.ts" % i]
        vnosi = _razcleni(self.XTREAM, vrstice)
        self.assertEqual(len(vnosi), 5000)
        vir = {"id": "xt", "url": self.XTREAM, "ime": "Ponudnik", "posodobljeno": 1, "napaka": "", "stevilo": 5000,
               "vnosi": vnosi, "razclenitev": kanali_iptv.RAZCLENITEV}
        (Path(self.mapa.name) / "media.json").write_text(json.dumps({"viri": [vir], "osebni_strezniki": []}),
                                                        encoding="utf-8")
        mc = os_media.MediaCenter(self.mapa.name, roots=[], secret_decryptor=lambda v: "")
        mc._ima_embed_vir = lambda data=None: False
        mc._zakoniti_viri.get = lambda *a, **k: []
        mc._personal_items = lambda *a, **k: []
        preverjeni, povezave = [], []

        def zabelezi(*a, **k):
            if "ponudnik.test" in repr(a):           # drugi gostitelji (TMDB) v preizkusu: brez omrezja
                povezave.append(a)
            raise OSError("brez omrezja v preizkusu")
        mc.kanali._preveri = lambda url, *a: (preverjeni.append(url), (kanali_iptv.MRTEV, "rok"))[1]
        with mock.patch.object(zakoniti_viri, "tv_v_zivo", lambda drzava="": []), \
                mock.patch.object(kanali_iptv.socket, "create_connection", side_effect=zabelezi), \
                mock.patch.object(kanali_iptv.socket, "getaddrinfo", side_effect=zabelezi):
            izid = mc.catalog("", "tv-v-zivo")
            self.assertTrue(mc.kanali.pocakaj(3))
        self.assertEqual((preverjeni, povezave), ([], []), "seznam z racunom je odprl tokove v ozadju")
        self.assertEqual(mc.kanali.v_teku(), 0)
        self.assertTrue(izid["vnosi"], "kanal seznama z racunom mora biti viden")
        self.assertFalse(any(x.get("preverjam") for x in izid["vnosi"]))
        vir = next(v for v in mc.sources() if v.get("id") == "xt")
        self.assertIs(vir["kanali"]["preverba"], False)

    def _preverba(self, klici):
        def preveri(url, glave, rok, domace):
            klici.append((url, time.monotonic()))
            return kanali_iptv.DELUJE, "ts"
        return kanali_iptv.PreverbaKanalov(self.pot, preveri=preveri)

    def test_premor_in_dnevna_meja_gostitelja(self):
        klici = []
        p = self._preverba(klici)
        with mock.patch.object(kanali_iptv, "PREMOR_GOSTITELJA_S", 0.3), \
                mock.patch.object(kanali_iptv, "NAJVEC_NA_GOSTITELJA_DAN", 3):
            p.preveri_v_ozadju([("https://javni.test/k%d" % i, {}, False) for i in range(5)])
            self.assertTrue(p.pocakaj(10))
        self.assertEqual(len(klici), 3, "dnevna meja odprtij na gostitelja")
        razmiki = [b[1] - a[1] for a, b in zip(klici, klici[1:])]
        self.assertTrue(all(r >= 0.29 for r in razmiki), razmiki)
        self.assertIsNone(p.izid("https://javni.test/k4"))          # neznan ostane neznan (viden), ni mrtev

    def test_med_predvajanjem_preverba_stoji(self):
        klici = []
        p = self._preverba(klici)
        p.gleda(60)
        with mock.patch.object(kanali_iptv, "PREMOR_GOSTITELJA_S", 0.0):
            p.preveri_v_ozadju([("https://a.test/1", {}, False), ("https://b.test/1", {}, False)])
            time.sleep(0.6)
            self.assertEqual(klici, [], "preverba med predvajanjem")
            p.ne_gleda()
            self.assertTrue(p.pocakaj(5))
        self.assertEqual(len(klici), 2)

    def test_najprej_kanali_na_zaslonu(self):
        klici = []
        p = self._preverba(klici)
        p.gleda(60)
        with mock.patch.object(kanali_iptv, "VZPOREDNO", 1), mock.patch.object(kanali_iptv, "PREMOR_GOSTITELJA_S", 0.0):
            p.preveri_v_ozadju([("https://a.test/1", {}, False), ("https://b.test/1", {}, False)])
            p.preveri_v_ozadju([("https://c.test/1", {}, False), ("https://b.test/1", {}, False)])   # nova stran
            p.ne_gleda()
            self.assertTrue(p.pocakaj(5))
        self.assertEqual([u for u, _t in klici], ["https://c.test/1", "https://b.test/1", "https://a.test/1"])

    # ---------------------------------------------------------------------------------- pregled 39, I1 (ob dvomu ne)
    def _mc_z_viri(self, viri):
        (Path(self.mapa.name) / "media.json").write_text(json.dumps({"viri": viri, "osebni_strezniki": []}),
                                                        encoding="utf-8")
        mc = os_media.MediaCenter(self.mapa.name, roots=[], secret_decryptor=lambda v: "")
        mc._ima_embed_vir = lambda data=None: False
        mc._zakoniti_viri.get = lambda *a, **k: []
        mc._personal_items = lambda *a, **k: []
        return mc

    @staticmethod
    def _vir(ident, url, kanali):
        vrstice = []
        for i, kanal in enumerate(kanali):
            vrstice += ['#EXTINF:-1 tvg-id="%s%d.si" group-title="SI",Kanal %s %d' % (ident, i, ident, i), kanal]
        vnosi = _razcleni(url, vrstice)
        return {"id": ident, "url": url, "ime": ident, "posodobljeno": 1, "napaka": "", "stevilo": len(vnosi),
                "vnosi": vnosi, "razclenitev": kanali_iptv.RAZCLENITEV}

    def test_samo_znani_javni_ali_oznaceni_seznami(self):
        """Gostitelj kode ni dokaz, da seznam ni placljiv: tja si uporabniki shranijo seznam ponudnika."""
        j = kanali_iptv.javni_brezplacni
        for url in ("https://gist.githubusercontent.com/uporabnik/0123abcd/raw/seznam.m3u",
                    "https://uporabnik.github.io/tv/seznam.m3u", "https://gitlab.com/u/tv/-/raw/main/seznam.m3u",
                    "https://codeberg.org/u/tv/raw/branch/main/seznam.m3u",
                    "https://raw.githubusercontent.com/uporabnik/tv/main/ponudnik.m3u"):
            self.assertFalse(j(url), url)
            self.assertTrue(j(url, True), url)                       # uporabnik ga je oznacil kot javnega
            self.assertTrue(kanali_iptv.oznacljiv_javni(url), url)
        self.assertFalse(j(self.XTREAM, True), "seznam z racunom v naslovu ne postane javen z oznako")
        self.assertFalse(kanali_iptv.oznacljiv_javni(self.XTREAM))
        self.assertFalse(kanali_iptv.oznacljiv_javni("https://iptv-org.github.io/iptv/countries/si.m3u"))   # ze znan
        s = kanali_iptv.s_poverilnicami
        self.assertTrue(s("http://ponudnik.test:8080/uporabnik/geslo/123"))           # kratka oblika Xtream
        self.assertTrue(s("http://ponudnik.test:8080/uporabnik/geslo/123.ts"))
        self.assertTrue(s("http://portal.test/play/live.php?mac=00:1A:79:00:00:01&stream=5"))      # Stalker
        self.assertFalse(s("https://cdn.test/hls/kanal/index.m3u8"))

    def test_skrivni_gist_s_kratko_obliko_xtream_ne_odpre_povezave(self):
        gist = "https://gist.githubusercontent.com/uporabnik/0123abcd/raw/moj-ponudnik.m3u"
        mc = self._mc_z_viri([self._vir("gist", gist, ["http://ponudnik.test:8080/uporabnik/geslo/%d" % i
                                                       for i in range(50)])])
        preverjeni = []
        mc.kanali._preveri = lambda url, *a: (preverjeni.append(url), (kanali_iptv.MRTEV, "rok"))[1]

        def brez_omrezja(*a, **k):
            raise OSError("brez omrezja v preizkusu")
        with mock.patch.object(zakoniti_viri, "tv_v_zivo", lambda drzava="": []), \
                mock.patch.object(kanali_iptv.socket, "create_connection", side_effect=brez_omrezja), \
                mock.patch.object(kanali_iptv.socket, "getaddrinfo", side_effect=brez_omrezja):
            izid = mc.catalog("", "tv-v-zivo")
            self.assertTrue(mc.kanali.pocakaj(3))
        self.assertEqual(preverjeni, [], "skrivni gist s seznamom ponudnika je sel v preverbo v ozadju")
        self.assertTrue(izid["vnosi"], "kanal seznama, ki ni znan javni vir, mora biti viden")
        self.assertFalse(any(x.get("preverjam") for x in izid["vnosi"]))
        stat = next(v for v in mc.sources() if v.get("id") == "gist")["kanali"]
        self.assertEqual((stat["preverba"], stat["oznacljiv"], stat["oznacen_javni"]), (False, True, False))

    def test_uporabnik_oznaci_seznam_kot_javnega(self):
        url = "https://uporabnik.github.io/tv/brezplacni.m3u"
        kanali = ["https://tok%d.test/k.m3u8" % i for i in range(3)]
        mc = self._mc_z_viri([self._vir("gh", url, kanali), self._vir("xt", self.XTREAM, ["https://tok9.test/k.m3u8"])])
        v_vrsti, odstranjeni = [], []
        mc.kanali.preveri_v_ozadju = lambda k: v_vrsti.extend(u for u, _g, _d in k) or 0
        mc.kanali.odstrani_iz_vrste = lambda urlji: odstranjeni.extend(urlji) or 0
        with mock.patch.object(zakoniti_viri, "tv_v_zivo", lambda drzava="": []):
            mc.catalog("", "tv-v-zivo")
            self.assertEqual(v_vrsti, [])
            self.assertEqual(mc.nastavi_javni_seznam("gh", True), {"ok": True, "javni": True})
            self.assertEqual(sorted(v_vrsti), kanali)
            stat = next(v for v in mc.sources() if v.get("id") == "gh")["kanali"]
            self.assertEqual((stat["preverba"], stat["oznacen_javni"]), (True, True))
            self.assertTrue(all(x.get("preverjam") for x in mc.catalog("", "tv-v-zivo")["vnosi"]
                                if x.get("url") in kanali))
            self.assertEqual(mc.nastavi_javni_seznam("gh", False), {"ok": True, "javni": False})
            self.assertEqual(sorted(odstranjeni), kanali, "kanali niso sli iz vrste preverbe")
            self.assertIs(next(v for v in mc.sources() if v.get("id") == "gh")["kanali"]["preverba"], False)
            self.assertEqual(mc.nastavi_javni_seznam("xt", True), {"ok": False, "napaka": "racun"})
            self.assertIs(next(v for v in mc.sources() if v.get("id") == "xt")["kanali"]["preverba"], False)

    def test_odstrani_iz_vrste(self):
        klici = []
        p = self._preverba(klici)
        p.gleda(60)                                     # preverba stoji: oba ostaneta v vrsti
        with mock.patch.object(kanali_iptv, "PREMOR_GOSTITELJA_S", 0.0):
            p.preveri_v_ozadju([("https://a.test/1", {}, False), ("https://b.test/1", {}, False)])
            self.assertEqual(p.odstrani_iz_vrste(["https://a.test/1"]), 1)
            self.assertEqual(p.v_teku(), 1)
            p.ne_gleda()
            self.assertTrue(p.pocakaj(5))
        self.assertEqual([u for u, _t in klici], ["https://b.test/1"])
