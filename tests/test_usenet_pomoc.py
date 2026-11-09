"""Usenet za drugo napravo v Linku (lastnik 5. 11. 2026, zakon solidarnosti): core/link_usenet_pomoc, Sprotno.zacni s
krajevnim virom, host.info in video.stream s poljem usenet v core/link_daljinec. Skupni primeri z Android-tv
(UsenetPravila.odtisIzdaj / guid v tests/UsenetPravilaTest.kt)."""
import http.client
import http.server
import os
import shutil
import ssl
import stat
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import debrid_pravila as P  # noqa: E402
from core import link_daljinec, link_datoteke, link_sprotno, link_usenet_pomoc  # noqa: E402
from core import usenet_pravila as U  # noqa: E402

sys.path.insert(0, os.path.join(KOREN, "tests"))
from test_link_sprotno import IZVIRNIK, LAZNI_FFMPEG, _Vir  # noqa: E402

ZETON = "A" * 43
OSNOVA = "https://nzbfinder.ws"
IX = "55b27847b81bca8a"


class SkupniPrimeri(unittest.TestCase):
    def test_odtis_izdaj(self):
        self.assertEqual(U.odtis_izdaj(OSNOVA), IX)
        self.assertEqual(U.odtis_izdaj("https://WWW.NZBfinder.ws."), IX)
        self.assertEqual(U.odtis_izdaj("https://nzbfinder.ws:443"), IX)
        self.assertEqual(U.odtis_izdaj("https://api.example.org:8443"), "46297557973e633c")
        self.assertEqual(U.odtis_izdaj("http://192.168.1.5:5076"), "45537dd7dc7925fa")
        self.assertIsNone(U.odtis_izdaj("ftp://x.example"))

    def test_guid(self):
        self.assertEqual(U.guid("abc123def456"), "abc123def456")
        self.assertEqual(U.guid("https://nzbfinder.ws/details/0123456789abcdef0123456789abcdef"),
                         "0123456789abcdef0123456789abcdef")
        for slab in ("a&b=c123", "abc", "", None, "abc123def456&apikey=x"):
            self.assertIsNone(U.guid(slab), slab)

    def test_naslov_nzb_guid(self):
        self.assertEqual(U.naslov_nzb_guid(OSNOVA, "kljuc123", "abc123def456"),
                         "https://nzbfinder.ws/api?t=get&id=abc123def456&apikey=kljuc123")
        self.assertIsNone(U.naslov_nzb_guid(OSNOVA, "kljuc123", "abc&t=search"))


class _Vezava:
    """Lasten pogon: predvajaj vrne naslov krajevnega streznika (pravi streznik iz preizkusa ali izmisljen)."""

    def __init__(self, url):
        self.url, self.odprti, self.klici = url, set(), []
        self.lastnik_gleda = False

    def predvajaj(self, nzb, ime=""):
        self.klici.append((nzb, ime))
        self.odprti = {self.url}
        return self.url, ""

    def odprt(self, url):
        return url in self.odprti

    def predvaja(self):
        return len(self.odprti) + (1 if self.lastnik_gleda else 0)


class _Debrid:
    def __init__(self, url, ix=(OSNOVA, "kljuc123"), sme=True, lastni=True):
        self._ix, self._sme, self._lastni = ix, sme, lastni
        self.lastni_usenet = _Vezava(url)
        self.prenosi = []
        self.predpomnilnik = {}

    def indeksator(self):
        return self._ix

    def sme_klicati(self, p):
        return self._sme

    def lastni_usenet_na_voljo(self):
        return self._lastni

    def _nzb_zapomnjen(self, k):
        return self.predpomnilnik.get(k)

    def nzb_po_guid(self, g):
        self.prenosi.append(g)
        self.predpomnilnik[U.kljuc_nzb_guid(self._ix[0], g)] = b"<nzb/>"
        return b"<nzb/>", ""


class Pomoc(unittest.TestCase):
    def setUp(self):
        self.url = "http://127.0.0.1:5555/%s/video.mkv" % ZETON
        self.d = _Debrid(self.url)
        link_usenet_pomoc.nastavi(self.d)
        link_usenet_pomoc._prenosi.clear()
        link_usenet_pomoc._zadnji = None

    def tearDown(self):
        link_usenet_pomoc.nastavi(None)
        link_usenet_pomoc._zadnji = None
        link_usenet_pomoc._prenosi.clear()

    def konec_filma(self):
        """TV je nehal gledati: krajevni streznik se je zaprl (nedejavnost)."""
        self.d.lastni_usenet.odprti = set()

    def koda(self, polje, **k):
        with self.assertRaises(link_usenet_pomoc.NapakaPomoci) as e:
            link_usenet_pomoc.vir(polje, **k)
        return str(e.exception)

    def test_zmoznost_brez_ffmpeg(self):
        # CodeRabbit 6. 11. 2026: racunalnik brez ffmpeg ne more pretvoriti - pomoci ne oglasa.
        self.assertIsNone(link_usenet_pomoc.zmoznost(lambda: False))

    def test_predpomnjen_nzb_istega_indeksatorja_ne_steje(self):
        # CodeRabbit 6. 11. 2026: pomocnik bere predpomnilnik s kljucem, vezanim na indeksator (kot Debrid.nzb_po_guid).
        self.d.predpomnilnik[U.kljuc_nzb_guid(OSNOVA, "abc123def456")] = b"<nzb/>"
        self.assertEqual(link_usenet_pomoc.vir({"guid": "abc123def456", "ix": IX}), self.url)
        self.assertEqual(self.d.prenosi, [])
        self.assertEqual(len(link_usenet_pomoc._prenosi), 0)

    def test_zmoznost(self):
        self.assertEqual(link_usenet_pomoc.zmoznost(lambda: True), {"lahko": True, "ix": IX})
        self.d._sme = False                      # kljuc zavrnjen ali zaklenjen: ne ponudimo pomoci
        self.assertIsNone(link_usenet_pomoc.zmoznost(lambda: True))
        self.d._sme, self.d._lastni = True, False  # brez lastnega ponudnika NNTP: ne
        self.assertIsNone(link_usenet_pomoc.zmoznost(lambda: True))
        link_usenet_pomoc.nastavi(None)
        self.assertIsNone(link_usenet_pomoc.zmoznost(lambda: True))

    def test_izdaja_z_lastnim_racunom(self):
        u = {"guid": "abc123def456", "name": "Film.2023.2160p.x265", "ix": IX}
        self.assertEqual(link_usenet_pomoc.vir(u), self.url)
        self.assertEqual(self.d.prenosi, ["abc123def456"])
        self.assertEqual(self.d.lastni_usenet.klici, [(b"<nzb/>", "Film.2023.2160p.x265")])
        # Previjanje istega filma: brez nove zahteve indeksatorju in brez novega bazena NNTP.
        self.assertEqual(link_usenet_pomoc.vir(dict(u)), self.url)
        self.assertEqual(len(self.d.prenosi), 1)
        self.assertEqual(len(self.d.lastni_usenet.klici), 1)

    def test_drug_indeksator_in_napacna_zahteva(self):
        self.assertEqual(self.koda({"guid": "abc123def456", "name": "x", "ix": "0000000000000000"}), "drug_indeksator")
        self.assertEqual(self.koda({"guid": "abc&apikey=x", "name": "x", "ix": IX}), "napacna_zahteva")
        self.assertEqual(self.koda({"guid": "abc123def456", "ix": "https://nzbfinder.ws"}), "napacna_zahteva")
        self.assertEqual(self.koda("abc123def456"), "napacna_zahteva")
        # Kljuc ali povezava NZB z druge naprave se ne uporabi nikoli: samo guid gre k indeksatorju s NASIM kljucem.
        link_usenet_pomoc.vir({"guid": "abc123def456", "ix": IX, "url": "https://evil.example/getnzb?r=TUJ", "key": "TUJ"})
        self.assertEqual(self.d.prenosi, ["abc123def456"])
        self.assertEqual(self.d.lastni_usenet.klici, [(b"<nzb/>", "")])

    def test_ni_usenet(self):
        link_usenet_pomoc.nastavi(None)
        self.assertEqual(self.koda({"guid": "abc123def456", "ix": IX}), "ni_usenet")

    def test_meja_prenosov_na_uro(self):
        ura = [1000.0]
        for i in range(link_usenet_pomoc.NAJVEC_NZB_NA_URO):
            self.konec_filma()
            link_usenet_pomoc.vir({"guid": "guid%08d" % i, "ix": IX}, ura=lambda: ura[0])
        self.konec_filma()
        self.assertEqual(self.koda({"guid": "guidnovi01", "ix": IX}, ura=lambda: ura[0]), "meja")
        # Ze prenesen NZB (isti guid) ne steje v mejo.
        self.konec_filma()
        self.assertEqual(link_usenet_pomoc.vir({"guid": "guid00000000", "ix": IX}, ura=lambda: ura[0]), self.url)
        ura[0] += link_usenet_pomoc.URA_S
        self.konec_filma()
        self.assertEqual(link_usenet_pomoc.vir({"guid": "guidnovi01", "ix": IX}, ura=lambda: ura[0]), self.url)
        self.assertEqual(len(self.d.prenosi), link_usenet_pomoc.NAJVEC_NZB_NA_URO + 1)

    def test_lastnikovega_filma_ne_prekinemo(self):
        self.d.lastni_usenet.lastnik_gleda = True
        self.assertEqual(self.koda({"guid": "abc123def456", "ix": IX}), "preobremenjen")
        self.assertEqual(self.d.prenosi, [])

    def test_ena_priprava_hkrati(self):
        with link_usenet_pomoc._ena_hkrati:
            self.assertEqual(self.koda({"guid": "abc123def456", "ix": IX}), "preobremenjen")


class PredpomnilnikPoIndeksatorju(unittest.TestCase):
    """CodeRabbit 6. 11. 2026: isti guid pri drugem indeksatorju ni ista izdaja (Debrid.nzb_po_guid)."""

    def test_zamenjan_indeksator(self):
        from core import debrid
        d = debrid.Debrid(lambda: {}, lambda _d: None, lambda s: s, lambda s: s)
        ix = [(OSNOVA, "kljuc123")]
        with mock.patch.object(d, "indeksator", side_effect=lambda: ix[0]), \
                mock.patch.object(d, "sme_klicati", return_value=True), \
                mock.patch.object(debrid, "usenet_nzb", side_effect=[(b"<nzb>A</nzb>", ""), (b"<nzb>B</nzb>", "")]) as prenos:
            self.assertEqual(d.nzb_po_guid("abc123def456"), (b"<nzb>A</nzb>", ""))
            self.assertEqual(d.nzb_po_guid("abc123def456"), (b"<nzb>A</nzb>", ""))      # predpomnjen
            ix[0] = ("https://drug.example", "kljuc456")
            self.assertEqual(d.nzb_po_guid("abc123def456"), (b"<nzb>B</nzb>", ""))
        self.assertEqual(prenos.call_count, 2)
        self.assertIn("drug.example", prenos.call_args.args[0])

    def test_vezava_pred_kljucem(self):
        # CodeRabbit 9. 11. 2026: nzb_po_guid prebere vezavo kljuca PRED kljucem (kot usenet_isci, Grok 36, D2).
        from core import debrid
        d = debrid.Debrid(lambda: {}, lambda _d: None, lambda s: s, lambda s: s)
        vrstni_red = []
        with mock.patch.object(d, "_vezava", side_effect=lambda p: vrstni_red.append("vezava") or ("o", "odtis")), \
                mock.patch.object(d, "indeksator", side_effect=lambda: vrstni_red.append("kljuc") or (OSNOVA, "k1")), \
                mock.patch.object(d, "sme_klicati", return_value=True), \
                mock.patch.object(d, "ob_izidu"), \
                mock.patch.object(debrid, "usenet_nzb", return_value=(b"<nzb>A</nzb>", "")):
            self.assertEqual(d.nzb_po_guid("abc123def456"), (b"<nzb>A</nzb>", ""))
        self.assertEqual(vrstni_red, ["vezava", "kljuc"])


class _UsenetStreznik(http.server.BaseHTTPRequestHandler):
    """Krajevni streznik lastnega pogona (kot usenet_streznik): samo /<zeton>/video.mkv."""
    protocol_version = "HTTP/1.1"

    def log_message(self, *_a):
        pass

    def do_GET(self):
        if self.path != "/%s/video.mkv" % ZETON:
            self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return
        _Vir.do_GET(self)


class KrajevniVir(unittest.TestCase):
    """Sprotno.zacni s krajevnim virom: posrednik sme natanko vrata streznika lastnega pogona, nic drugega na zanki."""

    @classmethod
    def setUpClass(cls):
        cls.mapa = tempfile.mkdtemp(prefix="safeer-usenet-pomoc-")
        cls.usenet = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _UsenetStreznik)
        threading.Thread(target=cls.usenet.serve_forever, daemon=True).start()
        cls.url = "http://127.0.0.1:%d/%s/video.mkv" % (cls.usenet.server_address[1], ZETON)
        cls.d = link_datoteke.Datoteke([], tls_mapa=os.path.join(cls.mapa, "tls"))
        cls.ffmpeg = os.path.join(cls.mapa, "ffmpeg")
        with open(cls.ffmpeg, "w", encoding="utf-8") as f:
            f.write(LAZNI_FFMPEG)
        os.chmod(cls.ffmpeg, os.stat(cls.ffmpeg).st_mode | stat.S_IEXEC)
        cls.s = link_sprotno.Sprotno(mapa=os.path.join(cls.mapa, "pretok"), ffmpeg=cls.ffmpeg, vaapi=lambda: None)

    @classmethod
    def tearDownClass(cls):
        for t in list(cls.s.tokovi.values()):
            cls.s.ustavi(t)
        cls.d.ustavi()
        cls.usenet.shutdown()
        cls.usenet.server_close()
        shutil.rmtree(cls.mapa, ignore_errors=True)

    def _zahteva(self, pot, glave=None):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        p = http.client.HTTPSConnection("127.0.0.1", self.d.streznik.vrata, context=ctx, timeout=15)
        p.request("GET", pot, headers=glave or {})
        o = p.getresponse()
        telo = o.read()
        p.close()
        return o.status, telo

    def test_ovira_naslov_zanke_iz_sporocila(self):
        # Zakaj je bila pomoc za Usenet pred 5. 11. 2026 nemogoca: TV poslje svoj 127.0.0.1, pomocnik ga zavrne.
        with self.assertRaises(link_sprotno.NapakaPretoka) as e:
            self.s.zacni({"url": self.url, "name": "Film.mkv"}, "tv-1", self.d.streznik)
        self.assertEqual(str(e.exception), "nedovoljen_cilj")

    def test_krajevni_vir_tece(self):
        o = self.s.zacni({"name": "Film.mkv", "duration_ms": 60000, "url": "https://evil.example/x",
                          "fp": "0" * 64, "token": "tuj", "headers": {"Cookie": "x"}},
                         "tv-1", self.d.streznik, krajevni=self.url)
        vir = next(iter(self.s._viri.values()))
        self.assertEqual((vir.url, vir.odtis, vir.zeton, vir.glave), (self.url, "", "", {}))   # nic iz sporocila
        st, telo = self._zahteva("/live/" + o["id"], {"X-Safeer-Token": o["token"]})
        self.assertEqual(st, 200)
        self.assertEqual(telo, IZVIRNIK)
        self.assertTrue(self.s.ustavi_ukaz(o["id"]))

    def test_krajevni_vir_samo_nasa_oblika(self):
        for slab in ("http://127.0.0.1:22/", "http://localhost:5555/%s/video.mkv" % ZETON,
                     "https://127.0.0.1:5555/%s/video.mkv" % ZETON, "http://127.0.0.1:5555/kratek/video.mkv",
                     "http://192.168.1.5:5555/%s/video.mkv" % ZETON):
            with self.assertRaises(link_sprotno.NapakaPretoka, msg=slab):
                self.s.zacni({"name": "x"}, "tv-1", self.d.streznik, krajevni=slab)

    def test_vgnezdena_zahteva_ne_na_zanko(self):
        # Vsebina z Useneta je tuja: kos seznama ali preusmeritev iz nje ne doseze drugih vrat na zanki (izpeljan vir).
        v = link_sprotno._Vir(self.url, "", "", {}, krajevna_vrata=self.usenet.server_address[1])
        v.povezava().close()
        for drug in ("http://127.0.0.1:%d/%s/drugo" % (self.usenet.server_address[1], ZETON), "http://127.0.0.1:22/x"):
            with self.assertRaises(link_sprotno.NapakaPretoka):
                v.izpeljan(drug, True).povezava()
        with self.assertRaises(link_sprotno.NapakaPretoka):
            link_sprotno._Vir("http://127.0.0.1:22/x", "", "", {}, krajevna_vrata=self.usenet.server_address[1]).povezava()


class Daljinec(unittest.TestCase):
    """host.info in video.stream s poljem usenet: samo ozji krog."""

    def setUp(self):
        link_usenet_pomoc.nastavi(_Debrid("http://127.0.0.1:5555/%s/video.mkv" % ZETON))

    def tearDown(self):
        link_usenet_pomoc.nastavi(None)

    def _host_info(self, ozji):
        izidi = []
        with mock.patch.object(link_daljinec, "_v_ozjem_krogu", return_value=ozji), \
                mock.patch.object(link_usenet_pomoc, "_ima_ffmpeg", return_value=True):
            link_daljinec.izvedi_control("host.info", {}, lambda _u: None, izidi.append, posiljatelj="tv-1")
        return izidi[0]["data"]

    def test_host_info_usenet_samo_ozji_krog(self):
        self.assertEqual(self._host_info(True).get("usenet"), {"lahko": True, "ix": IX})
        self.assertNotIn("usenet", self._host_info(False))

    def test_video_stream_usenet_zunaj_ozjega_kroga(self):
        izidi = []
        with mock.patch.object(link_daljinec, "_v_ozjem_krogu", return_value=False), \
                mock.patch.object(link_usenet_pomoc, "vir") as vir:
            link_daljinec.izvedi_control("video.stream", {"usenet": {"guid": "abc123def456", "ix": IX}, "name": "x"},
                                         lambda _u: None, izidi.append, datoteke=mock.Mock(), posiljatelj="tv-1")
        self.assertFalse(izidi[0]["ok"])
        self.assertEqual(izidi[0].get("code"), "ni_ozji_krog")
        vir.assert_not_called()                  # kvota in racun lastnika nedotaknjena

    def test_poceni_preverbe_pred_virom(self):
        # CodeRabbit 6. 11. 2026: brez ffmpeg (ali zaseden, brez prostora) se NZB ne prenese in NNTP se ne odpre.
        izidi = []
        dogodek = threading.Event()
        pr = mock.Mock()
        pr.predpreverba.side_effect = link_sprotno.NapakaPretoka("ni_ffmpeg")

        def koncaj(i):
            izidi.append(i); dogodek.set()
        with mock.patch.object(link_daljinec, "_v_ozjem_krogu", return_value=True), \
                mock.patch.object(link_daljinec, "pomoc", return_value={"lahko": True}), \
                mock.patch.object(link_sprotno, "sprotno", return_value=pr), \
                mock.patch.object(link_usenet_pomoc, "vir") as vir:
            link_daljinec.izvedi_control("video.stream", {"usenet": {"guid": "abc123def456", "ix": IX}, "name": "x"},
                                         lambda _u: None, koncaj, datoteke=mock.Mock(), posiljatelj="tv-1")
            self.assertTrue(dogodek.wait(5))
        self.assertEqual(izidi[0].get("code"), "ni_ffmpeg")
        vir.assert_not_called()

    def test_video_stream_usenet_ozji_krog(self):
        izidi = []
        dogodek = threading.Event()
        pr = mock.Mock()
        pr.zacni.return_value = {"id": "1", "url": "https://x/live/1", "fp": "f", "token": "t"}

        def koncaj(i):
            izidi.append(i); dogodek.set()
        with mock.patch.object(link_daljinec, "_v_ozjem_krogu", return_value=True), \
                mock.patch.object(link_daljinec, "pomoc", return_value={"lahko": True}), \
                mock.patch.object(link_sprotno, "sprotno", return_value=pr), \
                mock.patch.object(link_usenet_pomoc, "vir", return_value="http://127.0.0.1:5555/%s/video.mkv" % ZETON):
            link_daljinec.izvedi_control("video.stream", {"usenet": {"guid": "abc123def456", "ix": IX}, "name": "x"},
                                         lambda _u: None, koncaj, datoteke=mock.Mock(), posiljatelj="tv-1")
            self.assertTrue(dogodek.wait(5))
        self.assertTrue(izidi[0]["ok"], izidi)
        self.assertEqual(pr.zacni.call_args.kwargs["krajevni"], "http://127.0.0.1:5555/%s/video.mkv" % ZETON)


if __name__ == "__main__":
    unittest.main()
