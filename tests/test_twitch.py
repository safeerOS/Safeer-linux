"""Twitch v Medijskem centru (core/twitch.py, core/twitch_hls.py): GQL, usher, izlocanje oglasov in potekla prijava -
vse z mock odgovori (brez omrezja in brez prikaza)."""
import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import os_katalog, os_media, os_scit, twitch, twitch_hls  # noqa: E402

ZETON = "abcdefghijklmnopqrstuvwxyz0123"     # izmisljen auth-token (30 znakov, kot pri Twitchu)
CDN = "https://abc.j.cloudfront.hls.ttvnw.net/v1/segment/"


def baza(mapa, vrstice):
    pot = os.path.join(mapa, "cookies.sqlite")
    c = sqlite3.connect(pot)
    c.execute("CREATE TABLE moz_cookies (id INTEGER PRIMARY KEY, name TEXT, value TEXT, host TEXT, path TEXT, expiry INTEGER, "
              "lastAccessed INTEGER, isSecure INTEGER, isHttpOnly INTEGER, sameSite INTEGER)")
    for ime, vrednost, gostitelj, potek in vrstice:
        c.execute("INSERT INTO moz_cookies (name, value, host, path, expiry) VALUES (?, ?, ?, '/', ?)",
                  (ime, vrednost, gostitelj, potek))
    c.commit()
    c.close()
    return pot


def prijavljena(mapa, potek=None):
    potek = int(time.time()) + 86400 if potek is None else potek
    return baza(mapa, [("auth-token", ZETON, ".twitch.tv", potek), ("login", "ana", ".twitch.tv", potek),
                       ("SID", "drugo", ".youtube.com", potek)])


def prenos(login, gledalcev=10, igra="Chess"):
    return {"id": "1", "title": "Prenos " + login, "viewersCount": gledalcev,
            "previewImageURL": "https://static-cdn.jtvnw.net/previews-ttv/live_user_%s-440x248.jpg" % login,
            "broadcaster": {"id": "9", "login": login, "displayName": login.title(),
                            "profileImageURL": "https://static-cdn.jtvnw.net/jtv_user_pictures/x.png"},
            "game": {"name": igra, "displayName": igra}}


def kanal(login, v_zivo=False, gledalcev=0):
    u = {"id": "9", "login": login, "displayName": login.title(), "profileImageURL": "https://static-cdn.jtvnw.net/p.png",
         "stream": None}
    if v_zivo:
        p = prenos(login, gledalcev)
        p.pop("broadcaster")
        u["stream"] = p
    return u


class MockGQL:
    """Odgovarja kot gql.twitch.tv; zapise vsako zahtevo (naslov, glave, telo)."""

    def __init__(self, status=200, zavrni_zeton=False):
        self.zahteve = []
        self.status = status
        self.zavrni_zeton = zavrni_zeton

    def __call__(self, naslov, glave, telo, _cas):
        o = json.loads(telo.decode("utf-8"))
        self.zahteve.append((naslov, dict(glave), o))
        if self.zavrni_zeton and "Authorization" in glave:
            return 401, ""
        if self.status != 200:
            return self.status, ""
        q, v = o["query"], o.get("variables") or {}
        if "PlaybackAccessToken" in q:
            kljuc = "videoPlaybackAccessToken" if "videoPlaybackAccessToken" in q else "streamPlaybackAccessToken"
            return 200, json.dumps({"data": {kljuc: {"value": json.dumps({"player_type": v.get("t")}),
                                                     "signature": "podpis-" + str(v.get("t"))}}})
        if "currentUser" in q:
            return 200, json.dumps({"data": {"currentUser": {"login": "ana", "displayName": "Ana", "follows": {"edges": [
                {"node": kanal("tiha")}, {"node": kanal("mala", True, 5)}, {"node": kanal("velika", True, 900)}]}}}})
        if "game(name" in q:
            return 200, json.dumps({"data": {"game": {"streams": {"edges": [{"node": prenos("sah", 3, v["n"])}]}}}})
        if "streams(first" in q:
            return 200, json.dumps({"data": {"streams": {"edges": [{"node": prenos("prvi", 1000)},
                                                                  {"node": prenos("drugi", 50)},
                                                                  {"node": {"broadcaster": {"login": "slab login!"}}}]}}})
        if "games(first" in q:
            return 200, json.dumps({"data": {"games": {"edges": [{"node": {"name": "Just Chatting", "displayName": "Just Chatting"}},
                                                                {"node": {"name": "", "displayName": "brez"}}]}}})
        if "searchUsers" in q:
            return 200, json.dumps({"data": {"searchUsers": {"edges": [{"node": kanal("brez")},
                                                                      {"node": kanal("zivo", True, 7)}]}}})
        if "videos(" in q:
            return 200, json.dumps({"data": {"user": {"displayName": "Prvi", "videos": {"edges": [
                {"node": {"id": "123", "title": "Vcerajsnji", "lengthSeconds": 3700, "publishedAt": "2026-10-16T10:00:00Z",
                          "previewThumbnailURL": "https://vod-secure.twitch.tv/_404/404_processing_320x180.png"}},
                {"node": {"id": "x1", "title": "slab id"}}]}}}})
        return 200, json.dumps({"data": {}})


MASTER = """#EXTM3U
#EXT-X-TWITCH-INFO:NODE="n",USER-IP="192.0.2.1"
#EXT-X-MEDIA:TYPE=VIDEO,GROUP-ID="chunked",NAME="1080p60 (source)",AUTOSELECT=YES,DEFAULT=YES
#EXT-X-STREAM-INF:BANDWIDTH=7966622,RESOLUTION=1920x1080,CODECS="avc1.64002A,mp4a.40.2",VIDEO="chunked",FRAME-RATE=60.000
https://video.ttvnw.net/{p}/chunked.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=3422999,RESOLUTION=1280x720,CODECS="avc1.4D401F,mp4a.40.2",VIDEO="720p60",FRAME-RATE=60.000
https://video.ttvnw.net/{p}/720p60.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=630000,RESOLUTION=640x360,CODECS="avc1.4D401F,mp4a.40.2",VIDEO="360p30",FRAME-RATE=30.000
https://video.ttvnw.net/{p}/360p30.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=160000,CODECS="mp4a.40.2",VIDEO="audio_only"
https://video.ttvnw.net/{p}/audio_only.m3u8
"""


def seznam(segmenti, oglas_od=None, oglas_do=None, zaporedje=0, konec=False):
    """Seznam predvajanja kot pri Twitchu: segmenti so (sekunda, ime); oglasni (oglas_od <= sekunda < oglas_do) imajo
    naslov »Amazon|...« in oznako twitch-stitched-ad."""
    v = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-TARGETDURATION:6", "#EXT-X-MEDIA-SEQUENCE:%d" % zaporedje]
    if oglas_od is not None:
        v.append('#EXT-X-DATERANGE:ID="stitched-ad-1-30",CLASS="twitch-stitched-ad",START-DATE="2026-10-17T02:00:%02d.000Z",'
                 'DURATION=%.3f,X-TV-TWITCH-AD-POD-POSITION="0"' % (oglas_od, oglas_do - oglas_od))
    for sekunda, ime in segmenti:
        oglas = oglas_od is not None and oglas_od <= sekunda < oglas_do
        v.append("#EXT-X-PROGRAM-DATE-TIME:2026-10-17T02:00:%02d.000Z" % sekunda)
        v.append("#EXTINF:2.000,%s" % ("Amazon|2474283100494" if oglas else "live"))
        v.append(CDN + ime)
    if konec:
        v.append("#EXT-X-ENDLIST")
    return "\n".join(v) + "\n"


class MockUsher:
    """GET za usher in sezname predvajanja: glavni seznam po igralcu (iz zetona), media po slovarju naslov -> besedilo."""

    def __init__(self, seznami=None, master_status=200):
        self.seznami = seznami or {}
        self.naslovi = []
        self.master_status = master_status

    def __call__(self, naslov, cas=10.0):
        self.naslovi.append(naslov)
        if naslov.startswith(twitch.USHER):
            if self.master_status != 200:
                return self.master_status, ""
            igralec = json.loads(urllib.parse.parse_qs(urllib.parse.urlsplit(naslov).query)["token"][0])["player_type"]
            return 200, MASTER.replace("{p}", igralec)
        if naslov in self.seznami:
            s = self.seznami[naslov]
            return (200, s() if callable(s) else s)
        return 404, ""



class TestGQL(unittest.TestCase):
    def tw(self, gql=None, mapa=None, beri=None):
        mapa = mapa or tempfile.mkdtemp()
        return twitch.Twitch(pot=os.path.join(mapa, "cookies.sqlite"), poslji=gql or MockGQL(), beri=beri or MockUsher(),
                             nastavitve=os.path.join(mapa, "twitch.json"))

    def test_priljubljeni_brez_prijave(self):
        gql = MockGQL()
        r = self.tw(gql).priljubljeni()
        self.assertEqual([v["login"] for v in r["vnosi"]], ["prvi", "drugi"])     # neveljaven login izpade
        v = r["vnosi"][0]
        self.assertEqual((v["id"], v["vrsta"], v["gledalcev"], v["igra"]), ("twitch:prvi", "twitch", 1000, "Chess"))
        self.assertEqual(r["skupaj_strani"], 1)
        naslov, glave, _ = gql.zahteve[0]
        self.assertEqual(naslov, "https://gql.twitch.tv/gql")
        self.assertEqual(glave["Client-Id"], twitch.CLIENT_ID)
        self.assertNotIn("Authorization", glave)

    def test_kategorija_kategorije_iskanje_posnetki(self):
        gql = MockGQL()
        tw = self.tw(gql)
        self.assertEqual(tw.priljubljeni("Chess")["vnosi"][0]["igra"], "Chess")
        self.assertEqual(gql.zahteve[-1][2]["variables"], {"n": "Chess"})
        self.assertEqual(tw.kategorije(), [{"id": "Just Chatting", "ime": "Just Chatting"}])
        iskanje = tw.isci("z")["vnosi"]
        self.assertEqual([(v["vrsta"], v["login"]) for v in iskanje], [("twitch", "zivo"), ("twitch-kanal", "brez")])
        self.assertEqual(tw.isci("   ")["vnosi"], [])
        p = tw.posnetki("Prvi")
        self.assertEqual(p["ime"], "Prvi")
        self.assertEqual([(v["id"], v["trajanje"], v["slika"]) for v in p["vnosi"]], [("twitch-posnetek:123", 3700, "")])
        self.assertEqual(tw.posnetki("ni login!"), {"ime": "", "vnosi": []})

    def test_napaka_gql_je_izjema_ki_jo_medijski_center_ujame(self):
        with tempfile.TemporaryDirectory() as mapa:
            m = os_media.MediaCenter(os.path.join(mapa, "media"), roots=[])
            m._twitch = self.tw(MockGQL(status=500), mapa)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(m.twitch_katalog()["vnosi"], [])
                self.assertEqual(m.twitch_kategorije(), [])
                self.assertEqual(m.twitch_posnetki("prvi"), {"napaka": "ni_uspel"})


class TestPrijava(unittest.TestCase):
    def test_brez_piskotkov_ni_prijave_in_ni_omrezja(self):
        with tempfile.TemporaryDirectory() as mapa:
            gql = MockGQL()
            tw = twitch.Twitch(pot=os.path.join(mapa, "cookies.sqlite"), poslji=gql)
            self.assertEqual(tw.stanje(), {"prijavljen": False, "ime": "", "kanali": [], "potekla": False})
            self.assertEqual(gql.zahteve, [])

    def test_kanali_ki_jim_slediš_v_zivo_najprej_zeton_samo_na_gql(self):
        with tempfile.TemporaryDirectory() as mapa:
            gql = MockGQL()
            tw = twitch.Twitch(pot=prijavljena(mapa), poslji=gql)
            st = tw.stanje()
            self.assertTrue(st["prijavljen"])
            self.assertTrue(st["zaseben"])
            self.assertEqual(st["ime"], "Ana")
            self.assertEqual([v["login"] for v in st["kanali"]], ["velika", "mala", "tiha"])
            self.assertEqual([v["vrsta"] for v in st["kanali"]], ["twitch", "twitch", "twitch-kanal"])
            naslov, glave, _ = gql.zahteve[0]
            self.assertEqual(urllib.parse.urlsplit(naslov).hostname, "gql.twitch.tv")
            self.assertEqual(glave["Authorization"], "OAuth " + ZETON)
            self.assertNotIn("Cookie", glave)

    def test_potekel_piskotek_ni_prijava(self):
        with tempfile.TemporaryDirectory() as mapa:
            tw = twitch.Twitch(pot=prijavljena(mapa, potek=int(time.time()) - 10), poslji=MockGQL())
            self.assertFalse(tw.prijavljen())

    def test_potekla_prijava_jasno_brez_izjem_in_brez_zetona_v_dnevniku(self):
        with tempfile.TemporaryDirectory() as mapa:
            tw = twitch.Twitch(pot=prijavljena(mapa), poslji=MockGQL(zavrni_zeton=True), beri=MockUsher())
            izpis = io.StringIO()
            with contextlib.redirect_stdout(izpis):
                st = tw.stanje()
                # Zeton predvajanja: prijava ne velja -> brez nje (prenos se vseeno predvaja).
                t = tw._zeton_predvajanja("prvi")
            self.assertEqual(st, {"prijavljen": False, "ime": "", "kanali": [], "potekla": True})
            self.assertEqual(t["signature"], "podpis-site")
            self.assertNotIn(ZETON, izpis.getvalue())

    def test_zeton_gre_samo_v_glavni_zeton_predvajanja_nikoli_na_usher(self):
        with tempfile.TemporaryDirectory() as mapa:
            gql, usher = MockGQL(), MockUsher()
            tw = twitch.Twitch(pot=prijavljena(mapa), poslji=gql, beri=usher)
            tw._master("prvi")
            tw._master("prvi", igralec=("embed", "web"))
            self.assertEqual([("Authorization" in g) for _, g, _ in gql.zahteve], [True, False])
            self.assertTrue(all(ZETON not in n for n in usher.naslovi))

    def test_zeton_cudne_oblike_se_ne_poslje(self):
        self.assertEqual(twitch.zeton_iz({"auth-token": "abc\r\nX-Evil: 1"}), "")
        self.assertEqual(twitch.zeton_iz({"auth-token": ZETON}), ZETON)

    def test_medijski_center_kanale_le_zapomni_ne_shrani(self):
        with tempfile.TemporaryDirectory() as mapa:
            m = os_media.MediaCenter(os.path.join(mapa, "media"), roots=[])
            m._twitch = twitch.Twitch(pot=prijavljena(mapa), poslji=MockGQL())
            st = m.twitch_stanje()
            self.assertIn("twitch:velika", m._dynamic_items)
            self.assertEqual(len(st["kanali"]), 3)
            self.assertFalse(any("velika" in open(os.path.join(r, f), encoding="utf-8", errors="replace").read()
                                 for r, _, fs in os.walk(os.path.join(mapa, "media")) for f in fs))


class TestUsherInKakovost(unittest.TestCase):
    def test_razlicice_in_izbira(self):
        r = twitch_hls.razlicice(MASTER.replace("{p}", "site"))
        self.assertEqual([x["ime"] for x in r], ["1080p60 (source)", "720p60", "360p30", "audio_only"])
        self.assertEqual(twitch_hls.izberi(r, "auto", 1080)["visina"], 1080)
        self.assertEqual(twitch_hls.izberi(r, "auto", 800)["ime"], "720p60")
        self.assertEqual(twitch_hls.izberi(r, "480")["ime"], "360p30")
        self.assertEqual(twitch_hls.izberi(r, "160")["ime"], "360p30")       # nizje ni: najnizja video
        self.assertEqual(twitch_hls.izberi(r, "audio_only")["ime"], "audio_only")
        self.assertIsNone(twitch_hls.izberi([], "auto"))

    def test_kanal_ni_v_zivo(self):
        tw = twitch.Twitch(pot="/nic", poslji=MockGQL(), beri=MockUsher(master_status=404))
        self.assertEqual(tw.predvajaj({"vrsta": "twitch", "login": "prvi"}), {"napaka_koda": "twitch_ni_v_zivo"})
        self.assertIsNone(tw.predvajaj({"vrsta": "twitch", "login": "../x"}))

    def test_posnetek_neposredno_z_usherja_v_izbrani_kakovosti(self):
        with tempfile.TemporaryDirectory() as mapa:
            usher = MockUsher()
            tw = twitch.Twitch(pot="/nic", poslji=MockGQL(), beri=usher, nastavitve=os.path.join(mapa, "twitch.json"))
            self.assertEqual(tw.nastavi_kakovost("720"), "720")
            self.assertEqual(twitch.Twitch(nastavitve=os.path.join(mapa, "twitch.json")).kakovost(), "720")
            self.assertEqual(tw.nastavi_kakovost("8k"), "auto")
            tw.nastavi_kakovost("720")
            r = tw.predvajaj({"vrsta": "twitch-posnetek", "id": "twitch-posnetek:123"})
            self.assertEqual(r, {"url": "https://video.ttvnw.net/site/720p60.m3u8", "kakovost": "720p60"})
            self.assertTrue(usher.naslovi[0].startswith("https://usher.ttvnw.net/vod/123.m3u8?"))

    def test_prenos_v_zivo_gre_skozi_lokalni_seznam(self):
        usher = MockUsher({"https://video.ttvnw.net/site/chunked.m3u8": seznam([(0, "a"), (2, "b")])})
        tw = twitch.Twitch(pot="/nic", poslji=MockGQL(), beri=usher)
        try:
            r = tw.predvajaj({"vrsta": "twitch", "login": "prvi"})
            self.assertRegex(r["url"], r"^http://127\.0\.0\.1:\d+/twitch/[A-Za-z0-9_-]{16,}\.m3u8$")
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(usher.naslovi[0]).query)
            self.assertEqual((q["sig"], q["allow_source"]), (["podpis-site"], ["true"]))
            besedilo = urllib.request.urlopen(r["url"], timeout=5).read().decode()
            self.assertIn(CDN + "a", besedilo)
            self.assertIn(CDN + "b", besedilo)
            # Napacen zeton seje: 404, nic drugega.
            napacen = r["url"].rsplit("/", 1)[0] + "/" + "x" * 24 + ".m3u8"
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(napacen, timeout=5)
            self.assertEqual(e.exception.code, 404)
        finally:
            tw.posrednik.ustavi()

    def test_posrednik_bere_samo_streznike_twitcha(self):
        self.assertTrue(twitch_hls.dovoljen("https://usher.ttvnw.net/api/channel/hls/x.m3u8"))
        self.assertTrue(twitch_hls.dovoljen(CDN + "a"))
        self.assertFalse(twitch_hls.dovoljen("http://usher.ttvnw.net/x"))
        self.assertFalse(twitch_hls.dovoljen("https://ttvnw.net.zlo.example/x"))
        self.assertEqual(twitch_hls._beri("https://zlo.example/x"), (0, ""))


class Ura:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def vir(ime, besedila):
    """Vir s seznami po vrsti (vsak klic seznam() vzame naslednjega; zadnji ostane)."""
    vrsta = list(besedila)

    def beri(_naslov):
        return 200, (vrsta.pop(0) if len(vrsta) > 1 else vrsta[0])
    return twitch_hls.Vir(ime, lambda: (MASTER.replace("{p}", ime), "https://usher.ttvnw.net/m"), "auto", 1080, beri)


def uri_v(besedilo):
    return [v.rsplit("/", 1)[1] for v in besedilo.splitlines() if v.startswith("https://")]


class TestOglasi(unittest.TestCase):
    def test_razcleni_prepozna_oglas_po_naslovu_in_daterange(self):
        sz = twitch_hls.razcleni(seznam([(0, "a"), (2, "b"), (4, "c")], oglas_od=2, oglas_do=4))
        self.assertEqual([s["oglas"] for s in sz["segmenti"]], [False, True, False])
        # Samo DATERANGE (naslov brez »Amazon«): segment v intervalu je oglas.
        brez_naslova = seznam([(0, "a"), (2, "b")], oglas_od=2, oglas_do=4).replace("Amazon|2474283100494", "live")
        self.assertEqual([s["oglas"] for s in twitch_hls.razcleni(brez_naslova)["segmenti"]], [False, True])
        self.assertTrue(twitch_hls.je_oglas(seznam([(0, "a")], oglas_od=0, oglas_do=2)))
        self.assertFalse(twitch_hls.je_oglas(seznam([(0, "a")])))

    def test_oglas_nadomesti_rezerva_brez_oglasa(self):
        glavni = vir("site", [seznam([(0, "g0"), (2, "g2")]),
                              seznam([(0, "g0"), (2, "g2"), (4, "ad4"), (6, "ad6")], oglas_od=4, oglas_do=8),
                              seznam([(4, "ad4"), (6, "ad6"), (8, "g8")], oglas_od=4, oglas_do=8)])
        rezerva = vir("embed", [seznam([(2, "r2"), (4, "r4"), (6, "r6")])])
        ura = Ura()
        seja = twitch_hls.Seja(glavni, [rezerva], ura=ura)
        self.assertEqual(uri_v(seja.besedilo()), ["g0", "g2"])
        ura.t += 2
        b = seja.besedilo()
        self.assertEqual(uri_v(b), ["g0", "g2", "r4", "r6"])
        self.assertNotIn("Amazon", b)
        self.assertNotIn("stitched", b)
        self.assertEqual(b.count("#EXT-X-DISCONTINUITY\n"), 1)                # preklop na rezervo
        ura.t += 2
        b = seja.besedilo()
        self.assertEqual(uri_v(b), ["g0", "g2", "r4", "r6", "g8"])
        self.assertEqual(b.count("#EXT-X-DISCONTINUITY\n"), 2)                # in nazaj na glavni tok
        self.assertEqual((seja.nadomescenih, seja.izpuscenih), (2, 0))

    def test_ce_ima_oglas_tudi_rezerva_oglas_izpustimo(self):
        glavni = vir("site", [seznam([(0, "g0"), (2, "ad2"), (4, "ad4")], oglas_od=2, oglas_do=6),
                              seznam([(2, "ad2"), (4, "ad4"), (6, "g6")], oglas_od=2, oglas_do=6)])
        rezerva = vir("embed", [seznam([(2, "rad2"), (4, "rad4")], oglas_od=2, oglas_do=6)])
        ura = Ura()
        seja = twitch_hls.Seja(glavni, [rezerva], ura=ura)
        self.assertEqual(uri_v(seja.besedilo()), ["g0"])
        ura.t += 2
        self.assertEqual(uri_v(seja.besedilo()), ["g0", "g6"])
        self.assertEqual(seja.izpuscenih, 2)

    def test_izklopljeno_v_scitu_oglasi_ostanejo(self):
        glavni = vir("site", [seznam([(0, "g0"), (2, "ad2")], oglas_od=2, oglas_do=4)])
        seja = twitch_hls.Seja(glavni, [], brez_oglasov=lambda: False, ura=Ura())
        self.assertEqual(uri_v(seja.besedilo()), ["g0", "ad2"])

    def test_okno_drsi_zaporedje_in_prekinitve_se_stejejo(self):
        ura = Ura()
        seznami = [seznam([(s, "g%d" % s) for s in range(max(0, k - 10), k + 1, 2)]) for k in range(0, 60, 2)]
        glavni = vir("site", seznami)
        seja = twitch_hls.Seja(glavni, [], ura=ura)
        for _ in seznami:
            b = seja.besedilo()
            ura.t += 2
        self.assertEqual(len(uri_v(b)), twitch_hls.OKNO)
        self.assertEqual(uri_v(b)[-1], "g58")
        self.assertIn("#EXT-X-MEDIA-SEQUENCE:%d" % (30 - twitch_hls.OKNO), b)
        # Prekinitev, ki izpade iz okna, se steje v DISCONTINUITY-SEQUENCE.
        seja._okno = [dict(s) for s in seja._okno]
        seja._izdaj({"uri": CDN + "x", "trajanje": 2.0, "naslov": "live", "pdt": 1e10, "oglas": False}, "druga")
        for i in range(twitch_hls.OKNO):
            seja._izdaj({"uri": CDN + "y%d" % i, "trajanje": 2.0, "naslov": "live", "pdt": 1e10 + i + 1, "oglas": False}, "druga")
        self.assertIn("#EXT-X-DISCONTINUITY-SEQUENCE:1", seja.besedilo())

    def test_glavni_seznam_potekel_nov_zeton(self):
        klici = []

        def master():
            klici.append(1)
            return MASTER.replace("{p}", "site"), "https://usher.ttvnw.net/m"
        odgovori = [(403, ""), (200, seznam([(0, "g0")]))]
        v = twitch_hls.Vir("site", master, "auto", 1080, lambda _n: odgovori.pop(0))
        self.assertEqual([s["uri"] for s in v.seznam()["segmenti"]], [CDN + "g0"])
        self.assertEqual(len(klici), 2)

    def test_konec_prenosa(self):
        seja = twitch_hls.Seja(vir("site", [seznam([(0, "g0")], konec=True)]), [], ura=Ura())
        self.assertTrue(seja.besedilo().rstrip().endswith("#EXT-X-ENDLIST"))


class TestMedijskiCenterInScit(unittest.TestCase):
    def test_resolve_twitch_in_po_ponovnem_zagonu(self):
        with tempfile.TemporaryDirectory() as mapa:
            m = os_media.MediaCenter(os.path.join(mapa, "media"), roots=[])

            class Lazni:
                def predvajaj(self, vnos):
                    return {"url": "http://127.0.0.1:1/twitch/%s.m3u8" % ("z" * 20), "kakovost": "720p60", "vnos": vnos}
            m._twitch = Lazni()
            r = m.resolve("twitch:prvi")
            self.assertEqual((r["vrsta"], r["login"], r["kakovost"]), ("twitch", "prvi", "720p60"))
            self.assertTrue(r["url"].endswith(".m3u8"))
            self.assertEqual(os_katalog.nacin_predvajanja(r), "neposredno")
            self.assertEqual(os_katalog.vrsta_predvajalnika(r), "tv")
            self.assertEqual(os_katalog.vrsta_predvajalnika({"vrsta": "twitch-posnetek"}), "video")

            class NiVZivo:
                def predvajaj(self, _v):
                    return {"napaka_koda": "twitch_ni_v_zivo"}
            m._twitch = NiVZivo()
            self.assertEqual(m.resolve("twitch:prvi")["napaka_koda"], "twitch_ni_v_zivo")

    def test_katalog_zavihek_twitch_in_zvrsti(self):
        klici = []

        class Lazni:
            def twitch_katalog(self, q, k):
                klici.append((q, k))
                return {"vnosi": [], "skupaj_strani": 1}

            def twitch_kategorije(self):
                return [{"id": "Chess", "ime": "Chess"}]
        with tempfile.TemporaryDirectory() as td:
            katalog = os_katalog.Katalog(td, lambda *a: None, lambda f: f(), lambda *a, **k: True, lambda u: True,
                                         lambda a, b: True, lambda u: True)
            katalog._mc = Lazni()
            r = katalog.izvedi("mediaKatalog", ["sah", "twitch", "Chess", 1, "", [], False, [], "sl"])
            self.assertTrue(r["zvrsti"])
            self.assertEqual(klici, [("sah", "Chess")])
            self.assertEqual(katalog.izvedi("mediaZvrsti", ["twitch"]), [{"id": "Chess", "ime": "Chess"}])

    def test_twitch_ne_gre_na_police(self):
        predvajano = []
        with tempfile.TemporaryDirectory() as td:
            katalog = os_katalog.Katalog(td, lambda *a: None, lambda f: f(),
                                         lambda *a, **k: predvajano.append(a) or True, lambda u: True,
                                         lambda a, b: True, lambda u: True)
            izid = katalog._predvajaj_razresen({"id": "twitch:prvi", "vrsta": "twitch", "naslov": "Prenos",
                                                "url": "http://127.0.0.1:1/twitch/%s.m3u8" % ("z" * 20)}, "twitch:prvi")
            self.assertTrue(izid["native"])
            self.assertEqual(predvajano[0][1], "tv")
            self.assertEqual(katalog.police.predvajanja(), {})

    def test_scit_twitch_privzeto_vklopljen(self):
        class Shramba(dict):
            def set(self, k, v):
                self[k] = v
        with tempfile.TemporaryDirectory() as mapa:
            sc = os_scit.Scit(Shramba(), mapa=mapa)
            self.assertTrue(sc.twitch_brez_oglasov())
            self.assertFalse(sc.nastavi_twitch(False)["twitchOglasi"])
            self.assertFalse(sc.twitch_brez_oglasov())
            self.assertTrue(sc.nastavi_twitch(True)["twitchOglasi"])

    def test_moduli_v_tovoru_in_besedila_v_vseh_jezikih(self):
        koren = os.path.join(os.path.dirname(__file__), "..")
        with open(os.path.join(koren, "packaging", "install_os_payload.sh"), encoding="utf-8") as f:
            tovor = f.read()
        self.assertIn(" twitch twitch_hls ", tovor)
        with open(os.path.join(koren, "assets", "os", "besedila.js"), encoding="utf-8") as f:
            besedila = f.read()
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            vrstica = next(v for v in besedila.splitlines() if v.startswith("Object.assign(BESEDILA_OS.%s, {\"media_twitch\"" % jezik))
            for kljuc in ("scitTwitch", "twitchPrijava", "twitchPotekla", "mediaNapaka_twitch_ni_v_zivo", "twitchKakovost"):
                self.assertIn('"%s"' % kljuc, vrstica)


if __name__ == "__main__":
    unittest.main()
