"""Pregled 19. 10. 2026: sprotno pretvarjanje (core/link_sprotno.py) - seznami HLS, preusmeritve vira, domace omrezje.

A) Seznam HLS: relativni kosi niso delali nikoli (ffmpeg jih razresi glede na naslov posrednika -> 404), kosi https od
   77cb126 ne (ffmpeg sam ne sme https). Posrednik seznam prepise: vsak naslov -> zeton kosa tega toka na posredniku.
B) Preusmeritve: posrednik ffmpegu ne da glave Location, zato vir s 301/302 ni delal nikoli; zdaj jim sledi sam
   (najvec 5 skokov, vsak skozi preverbo cilja, https -> http ne, glave toka in zeton samo na izvoru glavnega vira).
C) Domace omrezje (Jellyfin, TVHeadend): kosi istega izvora imajo pravila glavnega vira; glave toka brez poverilnic
   (User-Agent, Referer ...) smejo v domace omrezje; zavrnjen video.stream ne ustavi toka, ki dela.

Strezniki tecejo na 127.0.0.1; kjer mora 127.0.0.1 veljati za javni ali domaci naslov, to doloci _vrsta_z_zanko.
127.0.0.2 in ::1 ostaneta prepovedana, zato preizkusi dokazejo tudi, da prepovedan naslov ostane zavrnjen.
"""
import http.client
import http.server
import os
import re
import secrets
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_datoteke, link_sprotno  # noqa: E402

IZVIRNIK = bytes(range(256)) * 128  # 32768 B "video"
HLS = "application/vnd.apple.mpegurl"

#: Lazni ffmpeg: vhod (zadnji -i) prebere kot pravi - z Range in prek http_proxy iz okolja -, izhod zapise.
LAZNI_FFMPEG = """#!/bin/sh
vhod=""; izhod=""
while [ $# -gt 0 ]; do
  if [ "$1" = "-i" ]; then shift; vhod="$1"; fi
  izhod="$1"; shift
done
exec python3 - "$vhod" "$izhod" <<'EOF'
import sys, urllib.request
vhod, izhod = sys.argv[1], sys.argv[2]
try:
    prvi = urllib.request.urlopen(urllib.request.Request(vhod, headers={"Range": "bytes=0-99"}), timeout=10).read()
    vse = urllib.request.urlopen(vhod, timeout=10).read()
except Exception as e:
    sys.stderr.write("vir: %s\\n" % e)
    sys.exit(1)
with open(izhod, "wb") as d:
    d.write(vse)
EOF
"""

#: ffmpeg, ki tece, dokler ga ne ustavimo (tok, ki dela).
SPECI_FFMPEG = "#!/bin/sh\nexec sleep 60\n"


class _Zapisnik(http.server.BaseHTTPRequestHandler):
    """Streznik vira: `server.vsebine` {pot: (bajti, vrsta)} ali {pot: (koda 3xx, Location)}; Range; zapise zahteve."""
    protocol_version = "HTTP/1.1"

    def log_message(self, *_a):
        pass

    def do_GET(self):  # noqa: N802
        h = self.headers
        self.server.zahteve.append({"pot": self.path, "host": h.get("Host"), "zeton": h.get("X-Safeer-Token"),
                                    "avtorizacija": h.get("Authorization"), "test": h.get("X-Safeer-Test"),
                                    "ua": h.get("User-Agent"), "range": h.get("Range"), "referer": h.get("Referer")})
        telo, vrsta = self.server.vsebine.get(self.path.split("?")[0], (None, ""))
        if isinstance(telo, int):
            self.send_response(telo)
            self.send_header("Location", vrsta)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if telo is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        a, b = 0, len(telo) - 1
        r = h.get("Range")
        if r:
            x, y = r[6:].split("-")
            a, b = int(x), (min(int(y), b) if y else b)
        self.send_response(206 if r else 200)
        self.send_header("Content-Type", vrsta)
        self.send_header("Content-Length", str(b - a + 1))
        if r:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, len(telo)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.wfile.write(telo[a:b + 1])


def _streznik(naslov="127.0.0.1", vsebine=None, tls=None):
    s = http.server.ThreadingHTTPServer((naslov, 0), _Zapisnik)
    s.zahteve, s.vsebine = [], dict(vsebine or {})
    if tls is not None:
        s.socket = tls.wrap_socket(s.socket, server_side=True)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def _ustavi_streznik(s):
    s.shutdown()
    s.server_close()


def _vrsta_z_zanko(kot: str):
    """vrsta_naslova, pri kateri je 127.0.0.1 (strezniki preizkusa) `kot`; 127.0.0.2, ::1 ... ostanejo prepovedani."""
    izvirna = link_sprotno.vrsta_naslova

    def vrsta(n):
        return kot if str(n) == "127.0.0.1" else izvirna(n)
    return mock.patch.object(link_sprotno, "vrsta_naslova", vrsta)


def _pocakaj(pogoj, rok=20.0) -> bool:
    konec = time.monotonic() + rok
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(0.05)
    return bool(pogoj())


def _zanka_127_0_0_2() -> bool:
    try:
        with socket.socket() as s:
            s.bind(("127.0.0.2", 0))
        return True
    except OSError:
        return False


def _poti(streznik):
    return [z["pot"] for z in streznik.zahteve]


class _LazniStreznik:
    """Namesto streznika datotek (link_datoteke): zacni() potrebuje samo osnovo, odtis in zeton."""
    odtis = "0" * 64

    def zazeni(self):
        pass

    def osnova(self, _naslov):
        return "https://127.0.0.1:9"

    def zeton_za(self, _kdo):
        return "zeton-naprave"


class _Osnova(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapa = tempfile.mkdtemp(prefix="safeer-sprotno-hls-")
        cls.ffmpeg = cls._program("ffmpeg", LAZNI_FFMPEG)
        kljuc, potrdilo, cls.odtis = link_datoteke.zagotovi_potrdilo(os.path.join(cls.mapa, "tls"))
        cls.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.tls.load_cert_chain(potrdilo, kljuc)

    @classmethod
    def _program(cls, ime, vsebina):
        pot = os.path.join(cls.mapa, ime)
        with open(pot, "w", encoding="utf-8") as f:
            f.write(vsebina)
        os.chmod(pot, os.stat(pot).st_mode | stat.S_IEXEC)
        return pot

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.mapa, ignore_errors=True)

    def setUp(self):
        self.streznik = _LazniStreznik()
        # Disk preizkusnega racunalnika je lahko poln: prostor tu ni predmet preizkusa.
        p = mock.patch.object(link_sprotno, "prosto", lambda _m: 1 << 50)
        p.start()
        self.addCleanup(p.stop)

    def _sprotno(self, ffmpeg=None):
        s = link_sprotno.Sprotno(mapa=tempfile.mkdtemp(dir=self.mapa), ffmpeg=ffmpeg or self.ffmpeg, vaapi=lambda: None)
        self.addCleanup(self._pospravi, s)
        return s

    @staticmethod
    def _pospravi(s):
        for t in list(s.tokovi.values()):
            s.ustavi(t)
        if s._posrednik is not None:
            s._posrednik.shutdown()
            s._posrednik.server_close()

    def _streznik_vira(self, **k):
        s = _streznik(**k)
        self.addCleanup(_ustavi_streznik, s)
        return s

    def _izhod(self, s, o, rok=30.0) -> bytes:
        """Pocaka, da se pretvorba konca, in vrne pretvorjeni izhod (prazno ob napaki)."""
        _pocakaj(lambda: s.stanje(o["id"])["done"], rok)
        t = s.tokovi[o["id"]]
        if t.napaka or not os.path.exists(t.datoteka):
            return b""
        with open(t.datoteka, "rb") as f:
            return f.read()

    def _zacni(self, s, url, **p):
        return s.zacni(dict({"url": url, "name": "v"}, **p), "tv-1", self.streznik)

    # ---- posrednik brez ffmpeg

    def _na_posredniku(self, s, url, odtis="", zeton="", glave=None, zasebni=False):
        """Vir toka na posredniku (kot ga vpise zacni), brez ffmpeg: (vrata, skrivnost)."""
        vrata = s._zazeni_posrednik()
        skrivnost = secrets.token_urlsafe(18)
        v = link_sprotno._Vir(url, odtis, zeton, dict(glave or {}), zasebni=zasebni)
        v.skrivnost = skrivnost
        with s._kljucavnica:
            s._viri[skrivnost] = v
        return vrata, skrivnost

    @staticmethod
    def _zahtevaj(vrata, pot, glave=None):
        """Zahteva posredniku, kot jo poslje ffmpeg (polni naslov, ker je posrednik njegov http_proxy)."""
        p = http.client.HTTPConnection("127.0.0.1", vrata, timeout=20)
        try:
            p.request("GET", pot if pot.startswith("http://") else "http://127.0.0.1:%d%s" % (vrata, pot),
                      headers=glave or {})
            r = p.getresponse()
            return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
        finally:
            p.close()


# ----------------------------------------------------------------------------- prepis seznama (brez streznikov)

class Prepis(unittest.TestCase):
    PREDPONA = "http://127.0.0.1:1/skrivnost/k/"
    MRTVI = PREDPONA + "-"

    def _prepisi(self, besedilo, osnova="https://cdn.test/a/b/seznam.m3u8"):
        vpisani = []

        def vpisi(n):
            vpisani.append(n)
            return self.PREDPONA + "z%d" % len(vpisani)
        izid = link_sprotno.prepisi_seznam(besedilo if isinstance(besedilo, bytes) else besedilo.encode(), osnova,
                                           vpisi, self.MRTVI)
        return izid, vpisani

    def _samo_nasi(self, izid: bytes):
        """Vsak naslov, ki ga ffmpeg prebere (vrstica brez # in URI v oznakah), kaze na nas posrednik."""
        for vrstica in re.split(r"\r\n|[\r\n\x00]", izid.decode("utf-8", "surrogateescape")):
            vrstica = vrstica.rstrip()
            if not vrstica:
                continue
            if not vrstica.startswith("#"):
                self.assertTrue(vrstica.startswith(self.PREDPONA), vrstica)
            elif ":" in vrstica:
                for k, v in link_sprotno._atributi(vrstica.partition(":")[2]):
                    if k == "URI=":
                        self.assertTrue(v.startswith(self.PREDPONA), vrstica)

    def test_vsi_naslovi_kazejo_na_posrednik(self):
        seznam = ("\ufeff#EXTM3U\r\n#EXT-X-VERSION:7\r"
                  '#EXT-X-KEY:METHOD=AES-128,URI="kljuc.bin",IV=0x0\n'
                  '#EXT-X-MAP:URI="/init.mp4",BYTERANGE="100@0"\n'
                  '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="a",NAME="sl, \\"x\\"",URI="//drug.test/zvok.m3u8"\n'
                  '#EXT-X-I-FRAME-STREAM-INF:BANDWIDTH=1,URI="i.m3u8"\n'
                  "#EXTINF:1,\nkos0.ts\n#EXTINF:1,\x00../c/kos1.ts?a=1#frag\n"
                  "#EXTINF:1,\n   http://127.0.0.2/zanka.ts   \n"
                  "#EXTINF:1,\nk s\u017e.ts\n#EXTINF:1,\ndata:text/plain,zlo\n#EXTINF:1,\njavascript:zlo\n"
                  "#EXTINF:1,\nHTTPS://Drug.Test:443/x.TS\n")
        izid, vpisani = self._prepisi(seznam)
        self._samo_nasi(izid)
        self.assertTrue(izid.startswith(b"#EXTM3U\n"), izid[:20])       # BOM odstranjen, ffmpeg zahteva #EXTM3U
        self.assertEqual(vpisani, [
            "https://cdn.test/a/b/kljuc.bin", "https://cdn.test/init.mp4", "https://drug.test/zvok.m3u8",
            "https://cdn.test/a/b/i.m3u8", "https://cdn.test/a/b/kos0.ts", "https://cdn.test/a/c/kos1.ts?a=1",
            "http://127.0.0.2/zanka.ts", "https://cdn.test/a/b/k%20s%C5%BE.ts", "https://Drug.Test:443/x.TS"])
        self.assertEqual(izid.count(self.MRTVI.encode()), 2)              # data: in javascript: -> 404
        self.assertNotIn(b"127.0.0.2", izid)
        self.assertNotIn(b"zlo", izid)
        # Ostali atributi ostanejo (ffmpeg jih prebere enako), URI je zadnji.
        self.assertIn(b'#EXT-X-MAP:BYTERANGE="100@0",URI="' + self.PREDPONA.encode() + b'z2"', izid)
        self.assertIn(b'NAME="sl, \\"x\\""', izid)

    def test_vbrizgavanje_v_oznako(self):
        """URI z ubeznimi narekovaji, dvojni in nenavedeni URI, kontrolni znaki: ffmpeg ne vidi tujega naslova."""
        for oznaka in ('#EXT-X-KEY:METHOD=AES-128,URI="a\\",URI=\\"http://127.0.0.2/zlo"',
                       '#EXT-X-KEY:METHOD=AES-128,URI="http://127.0.0.2/a",URI=http://127.0.0.2/b',
                       '#EXT-X-KEY:METHOD=AES-128, URI="http://127.0.0.2/c',
                       '#EXT-X-MAP:URI="x"\x0bURI="http://127.0.0.2/d"',
                       '#EXT-X-MEDIA:URI="\x00http://127.0.0.2/e"'):
            with self.subTest(oznaka=oznaka):
                izid, _ = self._prepisi("#EXTM3U\n%s\n#EXTINF:1,\nkos.ts\n" % oznaka)
                self._samo_nasi(izid)
                self.assertNotIn(b"127.0.0.2", izid)

    def test_meje(self):
        with mock.patch.object(link_sprotno, "NAJVEC_KOSOV", 3):
            izid, _ = self._prepisi("#EXTM3U\n" + "".join("#EXTINF:1,\nk%d.ts\n" % i for i in range(3)))
            self.assertIsNotNone(izid)
            izid, _ = self._prepisi("#EXTM3U\n" + "".join("#EXTINF:1,\nk%d.ts\n" % i for i in range(4)))
            self.assertIsNone(izid)
        izid, vpisani = self._prepisi("#EXTM3U\n#EXTINF:1,\n" + "a" * 5000 + ".ts\n")
        self.assertEqual(vpisani, [])
        self.assertIn(self.MRTVI.encode(), izid)

    def test_kosi_toka_omejeni(self):
        kosi = link_sprotno._Kosi()
        with mock.patch.object(link_sprotno, "NAJVEC_KOSOV", 3):
            zetoni = [kosi.vpisi("https://cdn.test/k%d.ts" % i, True) for i in range(5)]
        self.assertEqual(len(kosi), 3)
        self.assertIsNone(kosi.naslov(zetoni[0]))
        self.assertEqual(kosi.naslov(zetoni[4]), ("https://cdn.test/k4.ts", True))
        self.assertEqual(kosi.vpisi("https://cdn.test/k4.ts", True), zetoni[4])        # isti naslov, isti zeton
        self.assertNotEqual(kosi.vpisi("https://cdn.test/k4.ts", False), zetoni[4])    # brez pravic: drug zeton
        self.assertGreaterEqual(len(zetoni[0]), 16)

    def test_pravice_samo_na_izvoru_glavnega_vira(self):
        g = link_sprotno._Vir("https://nas.test:8443/f/v.m3u8", "a" * 64, "zeton-vira", {"X-A": "1"}, zasebni=True)
        for url, zaupan, pravice in (("https://nas.test:8443/f/k.ts", True, True),
                                     ("https://NAS.test:8443/k.ts", True, True),
                                     ("https://nas.test:8443/k.ts", False, False),     # naslov iz tujega seznama
                                     ("https://nas.test/k.ts", True, False),           # druga vrata
                                     ("http://nas.test:8443/k.ts", True, False),       # druga shema
                                     ("https://drug.test:8443/k.ts", True, False)):
            with self.subTest(url=url, zaupan=zaupan):
                v = g.izpeljan(url, zaupan)
                self.assertEqual((v.zeton, v.odtis, v.glave, v.zasebni),
                                 ("zeton-vira", "a" * 64, {"X-A": "1"}, True) if pravice else ("", "", {}, False))
        # Preusmeritev: drug izvor in nazaj na glavnega ne vrne glav; https -> http in druge sheme ne.
        tuj = g.preusmeritev("https://drug.test/x")
        self.assertEqual(tuj.preusmeritev("https://nas.test:8443/y").glave, {})
        self.assertEqual(g.preusmeritev("/drugo.ts").url, "https://nas.test:8443/drugo.ts")
        # Zahteve s kljucem ne sledijo preusmeritvam (AGENTS.md): zeton naprave tudi na isti pripeti izvor ne.
        self.assertEqual(g.preusmeritev("/drugo.ts").zeton, "")
        self.assertEqual(g.preusmeritev("/drugo.ts").odtis, "a" * 64, "odtis ostane pripet")
        for lokacija, koda in (("http://nas.test:8443/x", "nedovoljen_cilj"), ("ftp://nas.test/x", "napaka"),
                               ("file:///etc/passwd", "napaka")):
            with self.subTest(lokacija=lokacija):
                with self.assertRaises(link_sprotno.NapakaPretoka) as e:
                    g.preusmeritev(lokacija)
                self.assertEqual(str(e.exception), koda)

    def test_varne_glave(self):
        self.assertTrue(link_sprotno.v_domace_omrezje({}))
        self.assertTrue(link_sprotno.v_domace_omrezje({"User-Agent": "a", "referer": "b", "Origin": "c", "Accept": "d",
                                                       "Accept-Language": "sl"}))
        for k in ("Authorization", "cookie", "X-Api-Key", "Proxy-Authorization", "X-Safeer-Token"):
            self.assertFalse(link_sprotno.v_domace_omrezje({"User-Agent": "a", k: "b"}), k)


# ----------------------------------------------------------------------------- preusmeritve in posrednik

class Posrednik(_Osnova):
    def test_preusmeritev_vira_z_ffmpeg(self):
        """Vir, ki preusmeri (povezave do datotek), se pretvori; glave toka in Range gredo istemu izvoru naprej."""
        vir = self._streznik_vira()
        port = vir.server_address[1]
        vir.vsebine.update({"/star.mkv": (302, "/vmes"), "/vmes": (307, "http://127.0.0.1:%d/nov.mkv" % port),
                            "/nov.mkv": (IZVIRNIK, "video/x-matroska")})
        s = self._sprotno()
        with _vrsta_z_zanko("javni"):
            o = self._zacni(s, "http://127.0.0.1:%d/star.mkv" % port, headers={"X-Safeer-Test": "da"})
            self.assertEqual(self._izhod(s, o), IZVIRNIK)
        nov = [z for z in vir.zahteve if z["pot"] == "/nov.mkv"]
        self.assertTrue(nov)
        self.assertTrue(all(z["test"] == "da" for z in vir.zahteve), vir.zahteve)
        self.assertTrue(any(z["range"] == "bytes=0-99" for z in nov), nov)

    def test_preusmeritev_na_prepovedan_naslov_in_zanka(self):
        tuj = self._streznik_vira(vsebine={"/v.mkv": (IZVIRNIK, "video/x-matroska")})
        vir = self._streznik_vira()
        port = vir.server_address[1]
        vir.vsebine.update({"/dober": (302, "http://127.0.0.1:%d/v.mkv" % tuj.server_address[1]),
                            "/zanka": (302, "/zanka"), "/2": (301, "/3"), "/3": (308, "/v.mkv"),
                            "/v.mkv": (IZVIRNIK, "video/x-matroska")})
        if _zanka_127_0_0_2():
            prepovedan = self._streznik_vira(naslov="127.0.0.2", vsebine={"/v.mkv": (IZVIRNIK, "video/x-matroska")})
            vir.vsebine["/127"] = (302, "http://127.0.0.2:%d/v.mkv" % prepovedan.server_address[1])
        vir.vsebine["/ipv6"] = (302, "http://[::1]:%d/v.mkv" % port)
        vir.vsebine["/povezava"] = (302, "http://169.254.169.254/latest/meta-data/")
        s = self._sprotno()
        with _vrsta_z_zanko("javni"):
            # Dovoljen cilj na drugem izvoru: dela (prej je ffmpeg dobil 302 brez Location).
            vrata, skr = self._na_posredniku(s, "http://127.0.0.1:%d/dober" % port)
            st, gl, telo = self._zahtevaj(vrata, "/" + skr, {"Range": "bytes=0-"})
            self.assertEqual((st, telo), (206, IZVIRNIK))
            self.assertEqual(gl.get("content-range"), "bytes 0-32767/32768")
            self.assertEqual([z["range"] for z in tuj.zahteve], ["bytes=0-"])
            vrata, skr = self._na_posredniku(s, "http://127.0.0.1:%d/2" % port)
            self.assertEqual(self._zahtevaj(vrata, "/" + skr)[::2], (200, IZVIRNIK))
            # Zanka, ::1, povezavno-lokalni (metapodatki oblaka) in 127.0.0.2: nikoli.
            for pot in ("/127", "/ipv6", "/povezava") if _zanka_127_0_0_2() else ("/ipv6", "/povezava"):
                with self.subTest(pot=pot):
                    vrata, skr = self._na_posredniku(s, "http://127.0.0.1:%d%s" % (port, pot))
                    self.assertEqual(self._zahtevaj(vrata, "/" + skr)[0], 403)
            if _zanka_127_0_0_2():
                self.assertEqual(prepovedan.zahteve, [])
            # Neskoncna veriga: najvec 5 skokov (6 zahtev), nato 502.
            vrata, skr = self._na_posredniku(s, "http://127.0.0.1:%d/zanka" % port)
            self.assertEqual(self._zahtevaj(vrata, "/" + skr)[0], 502)
        self.assertEqual(_poti(vir).count("/zanka"), 6)

    def test_https_na_http_zavrnjeno_zeton_samo_istemu_izvoru(self):
        """Pripet https z zetonom: preusmeritev na isti izvor deluje (odtis se preveri znova), a brez zetona naprave
        (zahteve s kljucem ne sledijo preusmeritvam, AGENTS.md); na http nikoli."""
        http_cilj = self._streznik_vira(vsebine={"/v.mkv": (IZVIRNIK, "video/x-matroska")})
        vir = self._streznik_vira(tls=self.tls)
        port = vir.server_address[1]
        vir.vsebine.update({"/ista": (302, "/d/film.mkv"), "/d/film.mkv": (IZVIRNIK, "video/x-matroska"),
                            "/na-http": (302, "http://127.0.0.1:%d/v.mkv" % http_cilj.server_address[1])})
        s = self._sprotno()
        with _vrsta_z_zanko("zasebni"):
            vrata, skr = self._na_posredniku(s, "https://127.0.0.1:%d/ista" % port, odtis=self.odtis,
                                             zeton="zeton-vira", zasebni=True)
            self.assertEqual(self._zahtevaj(vrata, "/" + skr)[::2], (200, IZVIRNIK))
            vrata, skr = self._na_posredniku(s, "https://127.0.0.1:%d/na-http" % port, odtis=self.odtis,
                                             zeton="zeton-vira", zasebni=True)
            self.assertEqual(self._zahtevaj(vrata, "/" + skr)[0], 403)
        self.assertEqual(http_cilj.zahteve, [])
        self.assertEqual([(z["pot"], z["zeton"]) for z in vir.zahteve],
                         [("/ista", "zeton-vira"), ("/d/film.mkv", None), ("/na-http", "zeton-vira")])

    def test_glave_toka_ne_gredo_drugemu_izvoru(self):
        """Glave toka (Authorization ...) gredo samo izvoru glavnega vira - tudi ne nazaj nanj prek tujega izvora."""
        drug = self._streznik_vira(vsebine={"/v.mkv": (IZVIRNIK, "video/x-matroska")})
        vir = self._streznik_vira(vsebine={"/v.mkv": (IZVIRNIK, "video/x-matroska")})
        port, port_drug = vir.server_address[1], drug.server_address[1]
        vir.vsebine.update({"/drug": (302, "http://127.0.0.1:%d/v.mkv" % port_drug),
                            "/tja": (302, "http://127.0.0.1:%d/nazaj" % port_drug)})
        drug.vsebine["/nazaj"] = (302, "http://127.0.0.1:%d/v.mkv" % port)
        glave = {"X-Safeer-Test": "da", "Authorization": "Bearer skrivnost"}
        s = self._sprotno()
        with _vrsta_z_zanko("javni"):
            for pot in ("/drug", "/tja"):
                vrata, skr = self._na_posredniku(s, "http://127.0.0.1:%d%s" % (port, pot), glave=glave)
                self.assertEqual(self._zahtevaj(vrata, "/" + skr)[::2], (200, IZVIRNIK))
        self.assertEqual(_poti(drug), ["/v.mkv", "/nazaj"])
        self.assertTrue(all(z["test"] is None and z["avtorizacija"] is None and z["ua"] == "Safeer Control"
                            for z in drug.zahteve), drug.zahteve)
        self.assertEqual([(z["pot"], z["test"]) for z in vir.zahteve], [("/drug", "da"), ("/tja", "da"), ("/v.mkv", None)])

    def test_seznam_prepisan_zeton_kosa_vezan_na_tok(self):
        seznam = b"#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nkos0.ts\n#EXT-X-ENDLIST\n"
        vir = self._streznik_vira(vsebine={"/p/s.m3u8": (seznam, "text/plain"), "/p/kos0.ts": (b"KOS", "video/mp2t"),
                                           "/velik.m3u8": (b"#EXTM3U\n" + b"#x\n" * 2000, HLS)})
        port = vir.server_address[1]
        s, drug = self._sprotno(), self._sprotno()
        with _vrsta_z_zanko("javni"):
            vrata, skr = self._na_posredniku(s, "http://127.0.0.1:%d/p/s.m3u8" % port)
            st, gl, telo = self._zahtevaj(vrata, "/" + skr, {"Range": "bytes=0-"})
            self.assertEqual((st, gl.get("content-type")), (200, HLS))     # cel seznam, popravljena dolzina
            self.assertEqual(int(gl["content-length"]), len(telo))
            kos = [v for v in telo.decode().splitlines() if v and not v.startswith("#")]
            self.assertEqual(len(kos), 1)
            self.assertRegex(kos[0], r"^http://127\.0\.0\.1:%d/%s/k/[A-Za-z0-9_-]{16}\.ts$" % (vrata, re.escape(skr)))
            self.assertEqual(self._zahtevaj(vrata, kos[0])[::2], (200, b"KOS"))
            # Zeton kosa velja samo s skrivnostjo svojega toka in samo, dokler tok tece.
            vrata2, skr2 = self._na_posredniku(drug, "http://127.0.0.1:%d/p/s.m3u8" % port)
            zeton = kos[0].rsplit("/", 1)[1]
            self.assertEqual(self._zahtevaj(vrata2, "/%s/k/%s" % (skr2, zeton))[0], 404)
            self.assertEqual(self._zahtevaj(vrata, "/%s/k/%s" % (skr, "A" * 16))[0], 404)
            with s._kljucavnica:
                s._viri.pop(skr)
            self.assertEqual(self._zahtevaj(vrata, kos[0])[0], 404)
            # Delen seznam (Range ne od zacetka do konca) in prevelik seznam se ne prepiseta.
            vrata, skr = self._na_posredniku(s, "http://127.0.0.1:%d/p/s.m3u8" % port)
            self.assertEqual(self._zahtevaj(vrata, "/" + skr, {"Range": "bytes=0-9"})[0], 502)
            vrata, skr = self._na_posredniku(s, "http://127.0.0.1:%d/velik.m3u8" % port)
            with mock.patch.object(link_sprotno, "NAJVEC_SEZNAM", 4096):
                self.assertEqual(self._zahtevaj(vrata, "/" + skr)[0], 502)
            self.assertEqual(self._zahtevaj(vrata, "/" + skr)[0], 200)
        self.assertEqual(_poti(vir).count("/p/kos0.ts"), 1)


# ----------------------------------------------------------------------------- domace omrezje in vrstni red preverb

class DomaceOmrezje(_Osnova):
    def test_glave_brez_poverilnic_v_domace_omrezje(self):
        """Stremio proxyHeaders z User-Agent/Referer: tok iz domacega omrezja dela; s poverilnicami ne."""
        vir = self._streznik_vira(vsebine={"/v.mkv": (IZVIRNIK, "video/x-matroska")})
        url = "http://127.0.0.1:%d/v.mkv" % vir.server_address[1]
        s = self._sprotno()
        with _vrsta_z_zanko("zasebni"):
            o = self._zacni(s, url, headers={"User-Agent": "SafeerTest/1.0", "Referer": "https://stran.test/",
                                             "Accept-Language": "sl"})
            self.assertEqual(self._izhod(s, o), IZVIRNIK)
            self.assertTrue(vir.zahteve)
            self.assertTrue(all(z["ua"] == "SafeerTest/1.0" and z["referer"] == "https://stran.test/"
                                for z in vir.zahteve), vir.zahteve)
            vir.zahteve.clear()
            for glave in ({"User-Agent": "a", "X-Api-Key": "k"}, {"Cookie": "a=b"}, {"authorization": "Bearer x"},
                          {"Proxy-Authorization": "Basic eA=="}):
                with self.subTest(glave=glave):
                    with self.assertRaises(link_sprotno.NapakaPretoka) as e:
                        self._zacni(self._sprotno(), url, headers=glave)
                    self.assertEqual(str(e.exception), "nedovoljen_cilj")
        time.sleep(0.3)
        self.assertEqual(vir.zahteve, [])

    def test_zavrnjen_cilj_ne_ustavi_toka_ki_dela(self):
        vir = self._streznik_vira(vsebine={"/v.mkv": (IZVIRNIK, "video/x-matroska")})
        url = "http://127.0.0.1:%d/v.mkv" % vir.server_address[1]
        s = self._sprotno(self._program("ffmpeg-speci", SPECI_FFMPEG))
        izvirni = link_sprotno._razresi

        def razresi(g, v):
            if g == "ni.test":
                raise OSError("ni imena")
            return izvirni(g, v)
        with _vrsta_z_zanko("javni"), mock.patch.object(link_sprotno, "_razresi", razresi), \
                mock.patch.object(link_sprotno, "BREZ_BRALCA_S", 0.0):
            o = self._zacni(s, url)
            t = s.tokovi[o["id"]]
            self.assertTrue(_pocakaj(lambda: t.proces is not None))
            for zlo, koda in (("http://127.0.0.2:1/v.mkv", "nedovoljen_cilj"), ("http://[::1]:1/v.mkv", "nedovoljen_cilj"),
                              ("http://ni.test/v.mkv", "ni_vira")):
                with self.subTest(url=zlo):
                    with self.assertRaises(link_sprotno.NapakaPretoka) as e:
                        self._zacni(s, zlo)
                    self.assertEqual(str(e.exception), koda)
                    self.assertFalse(t.koncano, "zavrnjena zahteva je ustavila tok, ki dela")
                    self.assertIsNone(t.proces.poll())
            # Veljavna zahteva tok, ki ga nihce ne bere, se vedno umakne (en pretvornik naenkrat).
            nov = s.tokovi[self._zacni(s, url)["id"]]
            self.assertTrue(t.koncano)
            self.assertTrue(_pocakaj(lambda: t.proces.poll() is not None, 5))
            self.assertTrue(_pocakaj(lambda: nov.proces is not None))      # pospravi ga ustavi (ne ostane proces)

    def test_ustavljen_med_zagonom_ne_pusti_ffmpeg(self):
        """ustavi() med preverbo in zagonom pretvornika (procesa se ne vidi): pretvornik ne sme ostati."""
        s = self._sprotno(self._program("ffmpeg-speci", SPECI_FFMPEG))
        t = link_sprotno.Tok("v", os.path.join(self.mapa, "ustavljen.mp4"))
        izvirni = link_sprotno.subprocess.Popen

        def popen(*a, **k):
            s.ustavi(t)                  # kot ustavi_ukaz iz druge niti ravno pred zagonom
            return izvirni(*a, **k)

        def pocisti():                   # tudi ce preizkus pade, proces ne ostane
            if t.proces is not None and t.proces.poll() is None:
                t.proces.kill()
                t.proces.wait()
        self.addCleanup(pocisti)
        with mock.patch.object(link_sprotno.subprocess, "Popen", popen):
            nit = threading.Thread(target=s._pretvarjaj, args=(t, "http://127.0.0.1:9/x", 0, 0, 1080))
            nit.start()
            nit.join(10)
        self.assertFalse(nit.is_alive(), "pretvornik ustavljenega toka tece naprej")
        self.assertIsNotNone(t.proces.poll())


# ----------------------------------------------------------------------------- pravi ffmpeg

@unittest.skipUnless(shutil.which("ffmpeg") and _zanka_127_0_0_2(), "potrebuje ffmpeg in 127.0.0.2")
class SeznamHls(_Osnova):
    """Pravi ffmpeg bere seznam, ki ga je prepisal posrednik: kosi, kljuc AES-128, init (EXT-X-MAP), seznami kakovosti."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ff = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
              "testsrc=duration=3:size=64x64:rate=10", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "10"]
        cls.kos = subprocess.run(ff + ["-t", "1", "-f", "mpegts", "-"], capture_output=True, timeout=60,
                                 check=True).stdout
        kljuc = os.path.join(cls.mapa, "kljuc.bin")
        with open(kljuc, "wb") as f:
            f.write(os.urandom(16))
        with open(os.path.join(cls.mapa, "kljuc.info"), "w", encoding="utf-8") as f:
            f.write("kljuc.bin\n%s\n" % kljuc)
        # Pravi seznami muxerja hls: navaden (3 kosi), sifriran AES-128 (EXT-X-KEY) in fMP4 (EXT-X-MAP).
        cls.datoteke = {}
        for ime, dodatno, koncnica in (("ts", [], "ts"),
                                       ("aes", ["-hls_key_info_file", os.path.join(cls.mapa, "kljuc.info")], "ts"),
                                       ("fmp4", ["-hls_segment_type", "fmp4"], "m4s")):
            mapa = os.path.join(cls.mapa, ime)
            os.makedirs(mapa)
            subprocess.run(ff + ["-f", "hls", "-hls_time", "1", "-hls_list_size", "0"] + dodatno +
                           ["-hls_segment_filename", os.path.join(mapa, "k%d." + koncnica), os.path.join(mapa, "s.m3u8")],
                           capture_output=True, timeout=60, check=True)
            cls.datoteke[ime] = {}
            for f in os.listdir(mapa):
                with open(os.path.join(mapa, f), "rb") as d:
                    cls.datoteke[ime][f] = d.read()
        with open(kljuc, "rb") as f:
            cls.datoteke["aes"]["kljuc.bin"] = f.read()

    @staticmethod
    def _seznam(*kosi) -> bytes:
        v = "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:1\n#EXT-X-MEDIA-SEQUENCE:0\n"
        return (v + "".join("#EXTINF:1.0,\n%s\n" % k for k in kosi) + "#EXT-X-ENDLIST\n").encode()

    def _pretvori(self, vir, pot, **p):
        s = self._sprotno(shutil.which("ffmpeg"))
        o = self._zacni(s, "http://127.0.0.1:%d%s" % (vir.server_address[1], pot), duration_ms=1000, **p)
        return s, o

    def test_relativni_kosi_z_glavami_toka(self):
        """Relativni kosi (prej 404 na posredniku) gredo izvoru glavnega vira z njegovimi glavami toka."""
        ts = self.datoteke["ts"]
        vir = self._streznik_vira(vsebine={"/v/seznam.m3u8": (self._seznam("kos0.ts", "../v/kos1.ts", "/v/kos2.ts"), HLS),
                                           "/v/kos0.ts": (ts["k0.ts"], "video/mp2t"), "/v/kos1.ts": (ts["k1.ts"], "video/mp2t"),
                                           "/v/kos2.ts": (ts["k2.ts"], "video/mp2t")})
        with _vrsta_z_zanko("javni"):
            s, o = self._pretvori(vir, "/v/seznam.m3u8", headers={"X-Safeer-Test": "da"})
            self.assertGreater(len(self._izhod(s, o)), 1000)
        for kos in ("/v/kos0.ts", "/v/kos1.ts", "/v/kos2.ts"):
            self.assertIn(kos, _poti(vir))
        self.assertTrue(all(z["test"] == "da" for z in vir.zahteve), vir.zahteve)

    @unittest.skipUnless(shutil.which("openssl"), "potrebuje openssl")
    def test_kosi_https(self):
        """Kos https (od 77cb126 ffmpeg sam ne sme https) bere posrednik: potrdilo overitelja, brez glav toka."""
        mapa = tempfile.mkdtemp(dir=self.mapa)
        kljuc, potrdilo = os.path.join(mapa, "k.pem"), os.path.join(mapa, "c.pem")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
                        "-keyout", kljuc, "-out", potrdilo, "-days", "1", "-subj", "/CN=127.0.0.1",
                        "-addext", "subjectAltName=IP:127.0.0.1"], check=True, capture_output=True, timeout=60)
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(potrdilo, kljuc)
        kosi = self._streznik_vira(vsebine={"/kos0.ts": (self.kos, "video/mp2t"), "/kos1.ts": (self.kos, "video/mp2t")},
                                   tls=tls)
        cilj = "https://127.0.0.1:%d/" % kosi.server_address[1]
        vir = self._streznik_vira(vsebine={"/s.m3u8": (self._seznam(cilj + "kos0.ts", cilj + "kos1.ts"), HLS)})
        izvirni_kontekst = ssl.create_default_context

        def kontekst(*a, **k):          # "overitelj" preizkusa je potrdilo samo
            return izvirni_kontekst(cafile=potrdilo)
        with _vrsta_z_zanko("javni"), mock.patch.object(link_sprotno.ssl, "create_default_context", kontekst):
            s, o = self._pretvori(vir, "/s.m3u8", headers={"X-Safeer-Test": "da"})
            self.assertGreater(len(self._izhod(s, o)), 1000)
        self.assertEqual(sorted(set(_poti(kosi))), ["/kos0.ts", "/kos1.ts"])
        self.assertTrue(all(z["test"] is None and z["zeton"] is None and z["ua"] == "Safeer Control"
                            for z in kosi.zahteve), kosi.zahteve)

    def test_glavni_seznam_in_kljuc_aes(self):
        """Glavni seznam -> seznam kakovosti (prepisan znova) -> kljuc AES-128 (EXT-X-KEY) in kosi, vse relativno."""
        glavni = b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=200000,RESOLUTION=64x64\nkakovost/s.m3u8\n"
        vsebine = {"/m/glavni.m3u8": (glavni, HLS)}
        vsebine.update({"/m/kakovost/" + f: (b, HLS if f.endswith(".m3u8") else "application/octet-stream")
                        for f, b in self.datoteke["aes"].items()})
        self.assertIn(b'URI="kljuc.bin"', vsebine["/m/kakovost/s.m3u8"][0])
        vir = self._streznik_vira(vsebine=vsebine)
        with _vrsta_z_zanko("javni"):
            s, o = self._pretvori(vir, "/m/glavni.m3u8")
            self.assertGreater(len(self._izhod(s, o)), 1000)
        for pot in ("/m/kakovost/s.m3u8", "/m/kakovost/kljuc.bin", "/m/kakovost/k0.ts", "/m/kakovost/k1.ts"):
            self.assertIn(pot, _poti(vir))

    def test_init_odsek_fmp4(self):
        """fMP4: odsek init (EXT-X-MAP) in kosi .m4s."""
        vir = self._streznik_vira(vsebine={"/f/" + f: (b, HLS if f.endswith(".m3u8") else "video/mp4")
                                           for f, b in self.datoteke["fmp4"].items()})
        self.assertIn(b'#EXT-X-MAP:URI="init.mp4"', vir.vsebine["/f/s.m3u8"][0])
        with _vrsta_z_zanko("javni"):
            s, o = self._pretvori(vir, "/f/s.m3u8")
            self.assertGreater(len(self._izhod(s, o)), 1000)
        for pot in ("/f/init.mp4", "/f/k0.m4s", "/f/k1.m4s"):
            self.assertIn(pot, _poti(vir))

    def test_prepovedan_naslov_v_seznamu_ostane_zavrnjen(self):
        """Seznam z naslovi na zanki (127.0.0.2, ::1) in povezavno-lokalnem naslovu: ti kosi ne odidejo, ostali delajo."""
        zanka = self._streznik_vira(naslov="127.0.0.2", vsebine={"/kos.ts": (self.kos, "video/mp2t")})
        z = "127.0.0.2:%d" % zanka.server_address[1]
        vir = self._streznik_vira(vsebine={"/s.m3u8": (self._seznam(
            "kos0.ts", "http://%s/kos.ts" % z, "https://%s/kos.ts" % z, "httpproxy://%s/kos.ts" % z,
            "http://[::1]:%d/kos.ts" % zanka.server_address[1], "http://169.254.169.254/kos.ts", "kos1.ts"), HLS),
            "/kos0.ts": (self.kos, "video/mp2t"), "/kos1.ts": (self.kos, "video/mp2t")})
        with _vrsta_z_zanko("javni"):
            s, o = self._pretvori(vir, "/s.m3u8")
            self.assertTrue(_pocakaj(lambda: s.stanje(o["id"])["done"], 30))
        self.assertEqual(zanka.zahteve, [], "kos seznama je odsel na zanko")
        self.assertIn("/kos0.ts", _poti(vir))
        self.assertIn("/kos1.ts", _poti(vir))

    def test_domaci_seznam_kosi_istega_izvora(self):
        """Seznam z domacega streznika (Jellyfin, TVHeadend): kosi istega izvora smejo v domace omrezje (prej 403 kot
        vgnezdena zahteva), kos drugega izvora v domacem omrezju ne."""
        ts = self.datoteke["ts"]
        drug = self._streznik_vira(vsebine={"/kos.ts": (ts["k0.ts"], "video/mp2t")})
        vir = self._streznik_vira(vsebine={"/kos0.ts": (ts["k0.ts"], "video/mp2t"), "/kos1.ts": (ts["k1.ts"], "video/mp2t")})
        port = vir.server_address[1]
        vir.vsebine["/s.m3u8"] = (self._seznam("http://127.0.0.1:%d/kos.ts" % drug.server_address[1], "kos0.ts",
                                               "http://127.0.0.1:%d/kos1.ts" % port), HLS)
        with _vrsta_z_zanko("zasebni"):
            s, o = self._pretvori(vir, "/s.m3u8")
            self.assertTrue(_pocakaj(lambda: s.stanje(o["id"])["done"], 30))
        self.assertIn("/kos0.ts", _poti(vir))          # relativen
        self.assertIn("/kos1.ts", _poti(vir))          # absoluten, isti izvor (prej vgnezdena zahteva -> 403)
        self.assertEqual(drug.zahteve, [], "kos drugega izvora je odsel v domace omrezje")


if __name__ == "__main__":
    unittest.main()
