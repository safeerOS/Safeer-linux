"""Pregled 19. 10. 2026: tokovi Safeer Linka.

1. video.stream (core/link_sprotno.py) zmore vsaka naprava z zmoznostjo "v": zeton naprave gre samo pripetemu
   https; zanka in povezavno-lokalni naslovi nikoli, domace omrezje samo brez glav toka; posrednik se poveze na
   preverjeni naslov (DNS rebinding); ffmpeg in ffprobe smeta samo HTTP prek posrednika - tudi kose seznama HLS,
   ki jih sestavita sama, preveri posrednik.
2. Zaslon in zvok (core/link_zaslon.py, core/link_zvok.py): rokovanje TLS in pozdrav imata en skupen rok, zato
   pocasen odjemalec ne zadrzi prave naprave (prej do 256 x 10 s).

Strezniki preizkusa tecejo na 127.0.0.1 (in 127.0.0.2 kot "tuja" zanka); kjer mora 127.0.0.1 veljati za javni ali
domaci naslov, to doloci _vrsta_z_zanko. Brez popravkov pade 13 od 15 preizkusov (19. 10. 2026);
test_pripeti_vir_dobi_zeton_in_tok in test_javni_tok_z_glavami_dela varujeta zakonito rabo.
"""
import http.server
import os
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

from core import link_datoteke, link_sprotno, link_zaslon, link_zvok  # noqa: E402

IZVIRNIK = bytes(range(256)) * 128  # 32768 B "video"

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


class _Zapisnik(http.server.BaseHTTPRequestHandler):
    """Streznik vira: streze `server.vsebine` {pot: (bajti, vrsta)} z Range in zapise vsako zahtevo."""
    protocol_version = "HTTP/1.1"

    def log_message(self, *_a):
        pass

    def do_GET(self):  # noqa: N802
        h = self.headers
        self.server.zahteve.append({"pot": self.path, "host": h.get("Host"), "zeton": h.get("X-Safeer-Token"),
                                    "avtorizacija": h.get("Authorization"), "test": h.get("X-Safeer-Test"),
                                    "ua": h.get("User-Agent"), "range": h.get("Range")})
        telo, vrsta = self.server.vsebine.get(self.path.split("?")[0], (None, ""))
        if telo is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        a, b = 0, len(telo) - 1
        r = h.get("Range")
        if r:
            x, y = r[6:].split("-")
            a, b = int(x), (int(y) if y else b)
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
    """vrsta_naslova, pri kateri je 127.0.0.1 (strezniki preizkusa) `kot` ("javni"/"zasebni"); 127.0.0.2 in drugi
    naslovi ostanejo, kar so."""
    izvirna = getattr(link_sprotno, "vrsta_naslova", None)

    def vrsta(n):
        if str(n) == "127.0.0.1":
            return kot
        return izvirna(n) if izvirna is not None else "javni"
    return mock.patch.object(link_sprotno, "vrsta_naslova", vrsta, create=True)


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


class _LazniStreznik:
    """Namesto streznika datotek (link_datoteke): zacni() potrebuje samo osnovo, odtis in zeton."""
    odtis = "0" * 64

    def zazeni(self):
        pass

    def osnova(self, _naslov):
        return "https://127.0.0.1:9"

    def zeton_za(self, _kdo):
        return "zeton-naprave"


class _Tokovi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapa = tempfile.mkdtemp(prefix="safeer-pregled-tokovi-")
        cls.ffmpeg = os.path.join(cls.mapa, "ffmpeg")
        with open(cls.ffmpeg, "w", encoding="utf-8") as f:
            f.write(LAZNI_FFMPEG)
        os.chmod(cls.ffmpeg, os.stat(cls.ffmpeg).st_mode | stat.S_IEXEC)
        kljuc, potrdilo, cls.odtis = link_datoteke.zagotovi_potrdilo(os.path.join(cls.mapa, "tls"))
        cls.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.tls.load_cert_chain(potrdilo, kljuc)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.mapa, ignore_errors=True)

    def setUp(self):
        self.s = self._sprotno(self.ffmpeg)
        self.streznik = _LazniStreznik()
        # Disk preizkusnega racunalnika je lahko poln: prostor tu ni predmet preizkusa.
        p = mock.patch.object(link_sprotno, "prosto", lambda _m: 1 << 50)
        p.start()
        self.addCleanup(p.stop)

    def _sprotno(self, ffmpeg):
        s = link_sprotno.Sprotno(mapa=tempfile.mkdtemp(dir=self.mapa), ffmpeg=ffmpeg, vaapi=lambda: None)
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

    def _izhod(self, s, o, rok=20.0) -> bytes:
        """Pocaka, da se pretvorba konca, in vrne pretvorjeni izhod (prazno ob napaki)."""
        _pocakaj(lambda: s.stanje(o["id"])["done"], rok)
        t = s.tokovi[o["id"]]
        if t.napaka or not os.path.exists(t.datoteka):
            return b""
        with open(t.datoteka, "rb") as f:
            return f.read()


class VideoStream(_Tokovi):
    def _zacni(self, p, s=None):
        return (s or self.s).zacni(dict({"name": "v.mkv"}, **p), "tv-1", self.streznik)

    def _zavrnjeno(self, p, koda):
        with self.assertRaises(link_sprotno.NapakaPretoka) as e:
            self._zacni(p)
        self.assertEqual(str(e.exception), koda)

    # ---- (a) zeton naprave

    def test_zeton_samo_pripetemu_https(self):
        """Zeton naprave nikoli po http:// in ne nepripetemu https (prej je sel na vsak naslov)."""
        vir = self._streznik_vira(vsebine={"/v.mkv": (IZVIRNIK, "video/x-matroska")})
        port = vir.server_address[1]
        with _vrsta_z_zanko("javni"), mock.patch.object(link_sprotno, "_razresi", lambda g, v: ["127.0.0.1"],
                                                        create=True):
            for url, fp in (("http://127.0.0.1:%d/v.mkv" % port, ""),
                            ("http://127.0.0.1:%d/v.mkv" % port, self.odtis),     # odtis pri http nic ne dokaze
                            ("https://vir.test:%d/v.mkv" % port, "")):
                with self.subTest(url=url, fp=bool(fp)):
                    self._zavrnjeno({"url": url, "fp": fp, "token": "zeton-vira"}, "napacna_zahteva")
        time.sleep(0.3)
        self.assertEqual(vir.zahteve, [], "zeton je odsel")

    def test_pripeti_vir_dobi_zeton_in_tok(self):
        """Obicajna pot: datoteka z naprave v domacem omrezju (pripeto https + zeton) se pretvori kot prej."""
        vir = self._streznik_vira(vsebine={"/d/share:0:film.mkv": (IZVIRNIK, "video/x-matroska")}, tls=self.tls)
        url = "https://127.0.0.1:%d/d/share:0:film.mkv" % vir.server_address[1]
        with _vrsta_z_zanko("zasebni"):
            o = self._zacni({"url": url, "fp": self.odtis, "token": "zeton-vira", "duration_ms": 60000})
            self.assertEqual(self._izhod(self.s, o), IZVIRNIK)
        self.assertTrue(vir.zahteve)
        self.assertTrue(all(z["zeton"] == "zeton-vira" and z["pot"] == "/d/share:0:film.mkv" for z in vir.zahteve))
        self.assertTrue(any(z["range"] == "bytes=0-99" for z in vir.zahteve))
        # Napacen odtis: zahteva (z zetonom) sploh ne odide.
        vir.zahteve.clear()
        s2 = self._sprotno(self.ffmpeg)
        with _vrsta_z_zanko("zasebni"):
            o = self._zacni({"url": url, "fp": "1" * 64, "token": "zeton-vira"}, s=s2)
            self.assertEqual(self._izhod(s2, o), b"")
        self.assertEqual(vir.zahteve, [])

    # ---- (b) cilji

    def test_vrsta_naslova(self):
        vrsta = link_sprotno.vrsta_naslova
        for n in ("127.0.0.1", "127.8.9.10", "::1", "169.254.169.254", "fe80::1", "fe80::1%eth0", "0.0.0.0",
                  "0.1.2.3", "224.0.0.1", "255.255.255.255", "240.0.0.1", "::ffff:127.0.0.1", "::ffff:169.254.1.1",
                  "::127.0.0.1", "::", "2002:7f00:1::", "64:ff9b::7f00:1", "ff02::1", "ni-naslov", ""):
            self.assertEqual(vrsta(n), "prepovedan", n)
        for n in ("192.168.1.1", "10.0.0.1", "172.16.0.1", "100.64.0.1", "fd00::1", "::ffff:192.168.1.1"):
            self.assertEqual(vrsta(n), "zasebni", n)
        for n in ("8.8.8.8", "1.1.1.1", "2a00:1450:4001::1", "::ffff:8.8.8.8"):
            self.assertEqual(vrsta(n), "javni", n)

    def test_zanka_in_povezavno_lokalni_nikoli(self):
        """Naprava prek posrednika ne doseze storitev, ki poslusajo samo na tem racunalniku, ne metapodatkov oblaka."""
        vir = self._streznik_vira(vsebine={"/v.mkv": (IZVIRNIK, "video/x-matroska")})
        port = vir.server_address[1]
        for url in ("http://127.0.0.1:%d/v.mkv", "http://localhost:%d/v.mkv", "http://127.1:%d/v.mkv",
                    "http://2130706433:%d/v.mkv", "http://[::ffff:127.0.0.1]:%d/v.mkv", "http://0.0.0.0:%d/v.mkv",
                    "http://[::1]:%d/v.mkv", "http://169.254.169.254/latest/meta-data/"):
            url = url % port if "%d" in url else url
            with self.subTest(url=url):
                self._zavrnjeno({"url": url}, "nedovoljen_cilj")
        time.sleep(0.3)
        self.assertEqual(vir.zahteve, [])

    def test_glave_toka_ne_gredo_v_domace_omrezje(self):
        """Cookie/Authorization, ki jih izbere naprava, ne gredo na naslov v domacem omrezju; brez glav pa je
        naprava v domacem omrezju (NAS, streznik toka) se vedno dosegljiva."""
        vir = self._streznik_vira(vsebine={"/v.mkv": (IZVIRNIK, "video/x-matroska")})
        url = "http://127.0.0.1:%d/v.mkv" % vir.server_address[1]
        with _vrsta_z_zanko("zasebni"):
            self._zavrnjeno({"url": url, "headers": {"Authorization": "Bearer skrivnost", "Cookie": "a=b"}},
                            "nedovoljen_cilj")
            time.sleep(0.3)
            self.assertEqual(vir.zahteve, [])
            o = self._zacni({"url": url})
            self.assertEqual(self._izhod(self.s, o), IZVIRNIK)
        self.assertTrue(vir.zahteve)
        self.assertTrue(all(z["avtorizacija"] is None and z["zeton"] is None for z in vir.zahteve))
        self.assertEqual(link_sprotno.dovoljeni_naslovi("192.168.1.20", 80, zasebni=True), ["192.168.1.20"])
        with self.assertRaises(link_sprotno.NapakaPretoka):
            link_sprotno.dovoljeni_naslovi("192.168.1.20", 80, zasebni=False)

    def test_javni_tok_z_glavami_dela(self):
        """Stremio proxyHeaders gredo javnemu izvirniku kot prej (Range doloca bralec, ne glave toka)."""
        vir = self._streznik_vira(vsebine={"/v.mkv": (IZVIRNIK, "video/x-matroska")})
        url = "http://127.0.0.1:%d/v.mkv" % vir.server_address[1]
        with _vrsta_z_zanko("javni"):
            o = self._zacni({"url": url, "headers": {"User-Agent": "SafeerTest/1.0", "X-Safeer-Test": "da",
                                                     "Range": "bytes=5-9"}})
            self.assertEqual(self._izhod(self.s, o), IZVIRNIK)
        self.assertTrue(all(z["ua"] == "SafeerTest/1.0" and z["test"] == "da" for z in vir.zahteve), vir.zahteve)
        self.assertTrue(any(z["range"] == "bytes=0-99" for z in vir.zahteve))

    def test_povezava_na_preverjeni_naslov(self):
        """Posrednik se poveze na naslov, ki ga je preveril, ne razresi imena znova; Host ostane ime."""
        vir = self._streznik_vira(vsebine={"/v.mkv": (IZVIRNIK, "video/x-matroska")})
        port = vir.server_address[1]
        razresi = mock.patch.object(link_sprotno, "_razresi",
                                    lambda g, v: ["127.0.0.1"] if g == "vir.test" else [], create=True)
        with _vrsta_z_zanko("javni"), razresi:
            o = self._zacni({"url": "http://vir.test:%d/v.mkv" % port})
            self.assertEqual(self._izhod(self.s, o), IZVIRNIK)
        self.assertTrue(vir.zahteve)
        self.assertTrue(all(z["host"] == "vir.test:%d" % port for z in vir.zahteve), vir.zahteve)

    @unittest.skipUnless(shutil.which("openssl"), "potrebuje openssl")
    def test_javni_https_s_potrdilom_overitelja(self):
        """Obicajen javni tok (https brez odtisa): potrdilo in ime se preverita, cetudi se povezemo na naslov."""
        mapa = tempfile.mkdtemp(dir=self.mapa)
        kljuc, potrdilo = os.path.join(mapa, "k.pem"), os.path.join(mapa, "c.pem")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
                        "-keyout", kljuc, "-out", potrdilo, "-days", "1", "-subj", "/CN=vir.test",
                        "-addext", "subjectAltName=DNS:vir.test"], check=True, capture_output=True, timeout=60)
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(potrdilo, kljuc)
        vir = self._streznik_vira(vsebine={"/v.mkv": (IZVIRNIK, "video/x-matroska")}, tls=tls)
        port = vir.server_address[1]
        izvirni_kontekst = ssl.create_default_context

        def kontekst(*a, **k):          # "overitelj" preizkusa je potrdilo samo
            return izvirni_kontekst(cafile=potrdilo)
        razresi = mock.patch.object(link_sprotno, "_razresi", lambda g, v: ["127.0.0.1"], create=True)
        with _vrsta_z_zanko("javni"), razresi, mock.patch.object(link_sprotno.ssl, "create_default_context", kontekst):
            o = self._zacni({"url": "https://vir.test:%d/v.mkv" % port, "headers": {"X-Safeer-Test": "da"}})
            self.assertEqual(self._izhod(self.s, o), IZVIRNIK)
            self.assertTrue(vir.zahteve)
            self.assertTrue(all(z["host"] == "vir.test:%d" % port and z["test"] == "da" and z["zeton"] is None
                                for z in vir.zahteve), vir.zahteve)
            # Drugo ime na istem naslovu: potrdilo ne velja, zahteva ne odide.
            vir.zahteve.clear()
            s2 = self._sprotno(self.ffmpeg)
            o = self._zacni({"url": "https://drug.test:%d/v.mkv" % port}, s=s2)
            self.assertEqual(self._izhod(s2, o), b"")
        self.assertEqual(vir.zahteve, [])

    def test_dns_rebinding_ob_povezavi(self):
        """Ime, ki je ob video.stream kazalo na javni naslov, ob povezavi pa kaze na zanko: posrednik zavrne."""
        v = link_sprotno._Vir("http://vir.test/v.mkv", "", "", {})
        with mock.patch.object(link_sprotno, "_razresi", lambda g, p: ["127.0.0.1"], create=True):
            with self.assertRaises(link_sprotno.NapakaPretoka) as e:
                v.povezava()
        self.assertEqual(str(e.exception), "nedovoljen_cilj")
        odgovori = iter([["8.8.8.8"], ["127.0.0.1"]])
        with mock.patch.object(link_sprotno, "_razresi", lambda g, p: next(odgovori), create=True):
            self.assertEqual(link_sprotno.dovoljeni_naslovi("vir.test", 80, zasebni=False), ["8.8.8.8"])
            with self.assertRaises(link_sprotno.NapakaPretoka):
                link_sprotno._Vir("http://vir.test/v.mkv", "", "", {}, zasebni=True).povezava()

    # ---- (c) ffmpeg samo prek posrednika

    def test_ffmpeg_in_ffprobe_samo_http_prek_posrednika(self):
        vhod = "http://127.0.0.1:4321/skrivnost"
        for vaapi in (None, "/dev/dri/renderD128"):
            u = self.s.ukaz(vhod, "/tmp/o.mp4", 0, 0, 2160, vaapi)
            i = u.index("-i")
            self.assertEqual(u[i + 1], vhod)
            self.assertEqual(u[u.index("-protocol_whitelist") + 1], "http,tcp,crypto")
            self.assertEqual(u[u.index("-http_proxy") + 1], "http://127.0.0.1:4321")
            self.assertLess(u.index("-protocol_whitelist"), i)
            self.assertLess(u.index("-http_proxy"), i)
        # Okolje: nas posrednik, brez no_proxy ("*" bi ffmpeg poslal mimo) in brez posrednikov sistema.
        okolje = link_sprotno.okolje_ffmpeg(vhod, {"PATH": "/usr/bin", "no_proxy": "*", "NO_PROXY": "*",
                                                   "HTTP_PROXY": "http://sistem:3128", "https_proxy": "http://s:1"})
        self.assertEqual(okolje, {"PATH": "/usr/bin", "http_proxy": "http://127.0.0.1:4321"})
        # ffprobe (izbira zvocne sledi) bere isti vhod: enaka omejitev.
        with mock.patch.object(link_sprotno.Sprotno, "ffprobe", lambda _s: "ffprobe"), \
                mock.patch.object(link_sprotno.subprocess, "run", return_value=mock.Mock(stdout="eng\n")) as run:
            self.s.zvocna_sled(vhod, ["en"])
        argumenti = run.call_args.args[0]
        self.assertEqual(argumenti[argumenti.index("-protocol_whitelist") + 1], "http,tcp,crypto")
        self.assertEqual(run.call_args.kwargs["env"].get("http_proxy"), "http://127.0.0.1:4321")
        # Pretvornik dobi isto okolje.
        proces = mock.Mock(returncode=0)
        proces.communicate.return_value = (b"", b"")
        with mock.patch.object(link_sprotno.subprocess, "Popen", return_value=proces) as popen:
            self.s._pretvarjaj(link_sprotno.Tok("a", os.path.join(self.mapa, "a.mp4")), vhod, 0, 0, 1080)
        self.assertEqual(popen.call_args.kwargs["env"].get("http_proxy"), "http://127.0.0.1:4321")
        self.assertFalse({"no_proxy", "https_proxy"} & {k.lower() for k in popen.call_args.kwargs["env"]})


@unittest.skipUnless(shutil.which("ffmpeg") and _zanka_127_0_0_2(), "potrebuje ffmpeg in 127.0.0.2")
class SeznamHls(_Tokovi):
    """Pravi ffmpeg: kose seznama HLS sestavi sam; prej jih je bral naravnost (mimo posrednika in preverjanj)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kos = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
             "testsrc=duration=1:size=64x64:rate=10", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-f", "mpegts", "-"],
            capture_output=True, timeout=60, check=True).stdout

    @staticmethod
    def _seznam(*kosi) -> bytes:
        v = "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:1\n#EXT-X-MEDIA-SEQUENCE:0\n"
        return (v + "".join("#EXTINF:1.0,\n%s\n" % k for k in kosi) + "#EXT-X-ENDLIST\n").encode()

    def _pretvori(self, seznam: bytes):
        vir = self._streznik_vira(vsebine={"/seznam.m3u8": (seznam, "application/vnd.apple.mpegurl")})
        s = self._sprotno(shutil.which("ffmpeg"))
        o = s.zacni({"url": "http://127.0.0.1:%d/seznam.m3u8" % vir.server_address[1], "name": "v",
                     "duration_ms": 1000, "headers": {"X-Safeer-Test": "da"}}, "tv-1", self.streznik)
        return s, o

    def test_kos_na_zanki_ne_mimo_posrednika(self):
        cilj = self._streznik_vira(naslov="127.0.0.2", vsebine={"/kos.ts": (self.kos, "video/mp2t")})
        with _vrsta_z_zanko("javni"):
            s, o = self._pretvori(self._seznam("http://127.0.0.2:%d/kos.ts" % cilj.server_address[1]))
            self.assertTrue(_pocakaj(lambda: s.stanje(o["id"])["done"], 30))
        self.assertEqual(cilj.zahteve, [], "ffmpeg je kos seznama bral na zanki mimo posrednika")
        self.assertEqual(s.stanje(o["id"])["error"], "napaka")

    def test_javni_kos_gre_prek_posrednika_brez_glav_toka(self):
        """Seznam z javnimi kosi se pretvori kot prej; kos ne dobi glav toka ali zetona."""
        kosi = self._streznik_vira(vsebine={"/kos0.ts": (self.kos, "video/mp2t")})
        with _vrsta_z_zanko("javni"):
            s, o = self._pretvori(self._seznam("http://127.0.0.1:%d/kos0.ts" % kosi.server_address[1]))
            izhod = self._izhod(s, o, 30)
        self.assertGreater(len(izhod), 1000)
        self.assertTrue(kosi.zahteve)
        self.assertTrue(all(z["test"] is None and z["zeton"] is None and z["ua"] == "Safeer Control"
                            for z in kosi.zahteve), kosi.zahteve)


class Pozdrav(unittest.TestCase):
    """Pocasen odjemalec (bajt pozdrava na 0,25 s ali tiho rokovanje) ne sme zadrzati prave naprave."""

    @classmethod
    def setUpClass(cls):
        cls.mapa = tempfile.mkdtemp(prefix="safeer-pregled-pozdrav-")
        kljuc, potrdilo, _ = link_datoteke.zagotovi_potrdilo(cls.mapa)
        cls.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.ctx.load_cert_chain(potrdilo, kljuc)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.mapa, ignore_errors=True)

    @staticmethod
    def _tls(port):
        k = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        k.check_hostname = False
        k.verify_mode = ssl.CERT_NONE
        return k.wrap_socket(socket.create_connection(("127.0.0.1", port), timeout=15))

    def _pocasni(self, port, konec, rokovanje):
        s = None
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=15) if not rokovanje else self._tls(port)
            while not konec.is_set():
                if rokovanje:
                    s.sendall(b"S")       # pozdrav po en bajt, nikoli do konca vrstice
                konec.wait(0.25)
        except OSError:
            pass
        finally:
            if s is not None:
                s.close()

    def _pravi(self, port, pozdrav, izid):
        try:
            s = self._tls(port)
            s.sendall(pozdrav.encode())
            izid["pravi"] = s
        except OSError as e:
            izid["napaka"] = e

    def _preveri(self, modul, sprejmi, pozdrav, rokovanje=True):
        posluh = socket.socket()
        posluh.bind(("127.0.0.1", 0))
        posluh.listen(8)
        port = posluh.getsockname()[1]
        izid, konec = {}, threading.Event()
        with mock.patch.object(modul, "ROKOVANJE_S", 1.0, create=True):
            nit = threading.Thread(target=lambda: izid.update(sprejeto=sprejmi(posluh, self.ctx)), daemon=True)
            nit.start()
            pocasni = threading.Thread(target=self._pocasni, args=(port, konec, rokovanje), daemon=True)
            pocasni.start()
            time.sleep(0.5)                         # pocasni je ze sprejet in zaseda sprejem
            zacetek = time.monotonic()
            pravi = threading.Thread(target=self._pravi, args=(port, pozdrav, izid), daemon=True)
            pravi.start()
            nit.join(6.0)
            trajalo = time.monotonic() - zacetek
        konec.set()
        pocasni.join(5)
        pravi.join(5)
        for s in (izid.get("pravi"), izid.get("sprejeto")):
            s = s[0] if isinstance(s, tuple) else s
            if s is not None:
                s.close()
        posluh.close()
        nit.join(15)
        self.assertIsNotNone(izid.get("sprejeto"), "pocasen odjemalec je zadrzal pravo napravo")
        self.assertLess(trajalo, 4.0)

    def test_zaslon_pocasen_pozdrav(self):
        z = link_zaslon.Zaslon(tls_mapa=self.mapa)
        z._zeton = "pravi-zeton"
        self._preveri(link_zaslon, z._sprejmi, "SAFEER-ZASLON pravi-zeton\n")

    def test_zvok_pocasen_pozdrav(self):
        z = link_zvok.ZvokNaNapravo(tls_mapa=self.mapa, ffmpeg=sys.executable)
        z._zeton = "pravi-zeton"
        self._preveri(link_zvok, z._sprejmi, "SAFEER-ZVOK pravi-zeton\n")

    def test_zvok_tiho_rokovanje(self):
        """Povezava brez TLS (nic ne poslje) je prej drzala sprejem 10 s, ne glede na ROKOVANJE_S."""
        z = link_zvok.ZvokNaNapravo(tls_mapa=self.mapa, ffmpeg=sys.executable)
        z._zeton = "pravi-zeton"
        self._preveri(link_zvok, z._sprejmi, "SAFEER-ZVOK pravi-zeton\n", rokovanje=False)


if __name__ == "__main__":
    unittest.main()
