"""Pravila Scita (core/scit_pravila.py): vgrajen seznam, varovalo nujnih gostiteljev, podpisan seznam (isti kljuc in
preverjanje kot vir groznj), atomarna zamenjava in filter WebKit (zivo v WebKitGTK 6.0, ce je na voljo)."""
import base64
import http.server
import json
import os
import socketserver
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from core import scit_pravila as sp  # noqa: E402
from core import signed_feed  # noqa: E402
from core.signed_feed import FeedVerificationError  # noqa: E402

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except Exception:  # noqa: BLE001
    Ed25519PrivateKey = None

ZDAJ = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


class Vgrajena(unittest.TestCase):
    def test_vgrajen_seznam_je_veljaven(self):
        p = sp.vgrajena()
        self.assertEqual((p.vir, p.verzija), ("vgrajena", sp.VGRAJENA_VERZIJA))
        self.assertGreater(len(p.sledilci), 80)
        # Izmerjeno 18. 10. 2026 (osnova brez filtra, WebKitGTK 6.0): to so nalozile storitve, ki jih vgrajujemo.
        tretji = {"https://www.google-analytics.com/g/collect": "https://open.spotify.com/",
                  "https://analytics.google.com/g/collect": "https://open.spotify.com/",
                  "https://stats.g.doubleclick.net/g/collect": "https://open.spotify.com/",
                  "https://o22381.ingest.sentry.io/api/114855/envelope/": "https://open.spotify.com/",
                  "https://www.fastly-insights.com/x": "https://open.spotify.com/",
                  "https://sb.scorecardresearch.com/b": "https://www.twitch.tv/",
                  "https://secure-sts-prod.imrworldwide.com/cgi-bin/gn": "https://www.twitch.tv/",
                  "https://api.sprig.com/sdk/1/visitors/x/events": "https://www.twitch.tv/",
                  "https://s.amazon-adsystem.com/iu3": "https://www.twitch.tv/",
                  "https://script.dotmetrics.net/SiteEvent.dotmetrics": "https://365.rtvslo.si/",
                  "https://prd.jwpltx.com/v1/jwplayer6/ping.gif": "https://365.rtvslo.si/"}
        for url, stran in tretji.items():
            self.assertTrue(p.blokira(url, stran), url)
        for url in ("https://spade.twitch.tv/track", "https://edge.ads.twitch.tv/ads", "https://pixel.spotify.com/v2/sync",
                    "https://www.youtube-nocookie.com/api/stats/qoe?fmt=1", "https://www.youtube.com/youtubei/v1/log_event",
                    "https://web.whatsapp.com/ajax/bz", "https://www.messenger.com/ajax/bz", "https://dit.whatsapp.net/x",
                    "https://discord.com/api/v9/science"):
            self.assertTrue(p.blokira(url, "https://primer.si/"), url)
        # Kar storitve nujno potrebujejo (izmerjeno: prijava, predvajanje, sporocila), ostane.
        for url in ("https://www.youtube.com/youtubei/v1/player", "https://www.youtube.com/api/stats/playback",
                    "https://www.youtube.com/api/stats/watchtime", "https://jnn-pa.googleapis.com/$rpc/x",
                    "https://www.google.com/recaptcha/enterprise/anchor", "https://www.google.com/js/th/x.js",
                    "https://rr1---sn-x.googlevideo.com/videoplayback", "https://api-partner.spotify.com/pathfinder/v2/query",
                    "https://guc3-spclient.spotify.com/gabo-receiver-service/v3/events", "https://gql.twitch.tv/gql",
                    "https://usher.ttvnw.net/api/channel/hls/x.m3u8", "https://web.whatsapp.com/ajax/bootloader-endpoint/",
                    "https://static.whatsapp.net/rsrc.php/x", "https://www.facebook.com/login/async_sso/messenger_dot_com/",
                    "https://challenges.cloudflare.com/turnstile/v0/api.js", "https://cdn.cookielaw.org/x.js"):
            self.assertFalse(p.blokira(url, "https://primer.si/"), url)
        # Sledilec tretjih na svoji strani ni tretji.
        self.assertFalse(p.blokira("https://www.google-analytics.com/", "https://www.google-analytics.com/"))

    def test_spotify_pravila_v_drm(self):
        p = sp.vgrajena()
        d = p.za_drm(spotify=True)
        self.assertIn("adeventtracker.spotify.com", d["gostitelji"])
        self.assertIn("google-analytics.com", d["gostitelji"])
        self.assertIn(["spotify.com", "/ads/"], d["poti"])
        self.assertIn("upgrade-button", d["css"])
        self.assertTrue(d["css"].endswith("{ display: none !important; }"))
        drugo = p.za_drm(spotify=False)          # Netflix, Disney+ ...: sledilci da, oglasna pravila Spotifyja ne
        self.assertIn("google-analytics.com", drugo["gostitelji"])
        self.assertNotIn("adeventtracker.spotify.com", drugo["gostitelji"][:len(p.spotify_gostitelji)])
        self.assertEqual(drugo["css"], "")


class Varovalo(unittest.TestCase):
    """Seznam (tudi podpisan, tudi napacen) ne more blokirati prijave, predvajanja ali varnostnih preverjanj."""

    def _zavrni(self, pravila):
        with self.assertRaises(FeedVerificationError):
            sp.preveri_pravila(pravila, 1, "preizkus")

    def test_nujni_gostitelji(self):
        for g in ("googlevideo.com", "rr3---sn-a.googlevideo.com", "google.com", "www.google.com", "spotify.com",
                  "accounts.spotify.com", "twitch.tv", "ttvnw.net", "whatsapp.net", "telegram.org", "web.telegram.org",
                  "challenges.cloudflare.com", "cloudflare.com", "recaptcha.net", "safeer.si", "github.com",
                  "jnn-pa.googleapis.com", "googleapis.com"):
            with self.subTest(g=g):
                self._zavrni({"sledilci": [g]})
                self._zavrni({"telemetrija": [g]})

    def test_nujne_poti(self):
        for h, pot in (("youtube.com", "/youtubei/"), ("www.youtube.com", "/youtubei/v1/player"), ("youtube.com", "/w"),
                       ("google.com", "/recaptcha/api2"), ("spotify.com", "/api/"), ("twitch.tv", "/gql")):
            with self.subTest(pot=h + pot):
                self._zavrni({"poti": [[h, pot]]})

    def test_oblika(self):
        for slabo in ({"sledilci": ["ni domena"]}, {"sledilci": "x.com"}, {"poti": [["x.com", "brez-poseve"]]},
                      {"poti": [["x.com", "/a?b"]]}, {"poti": [["x.com"]]},
                      {"spotify": {"css": ["a { color: red } b"]}}, {"spotify": {"css": ["div[style*=url(x)]"]}},
                      {"spotify": {"css": ["@import"]}}, {"sledilci": ["a%d.example.com" % i for i in range(5001)]}, []):
            with self.subTest(slabo=str(slabo)[:60]):
                self._zavrni(slabo)
        # Neznan kljuc novejsega streznika se izpusti, ostalo velja.
        p = sp.preveri_pravila({"sledilci": ["sledilec.example"], "nova_vrsta": [1]}, 5, "preizkus")
        self.assertEqual(p.sledilci, ("sledilec.example",))


def _paket(kljuc, verzija, pravila=None, dni=14, zdaj=ZDAJ, key_id="preizkus"):
    import scit_pravila_podpisi
    return scit_pravila_podpisi.podpisi(pravila or {"sledilci": ["sledilec.example"]}, kljuc, key_id, verzija, zdaj, dni)


@unittest.skipIf(Ed25519PrivateKey is None, "ni knjiznice cryptography")
class PodpisanSeznam(unittest.TestCase):
    def setUp(self):
        self.kljuc = Ed25519PrivateKey.generate()
        javni = self.kljuc.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.zaupani = {"preizkus": base64.b64encode(javni).decode()}
        self.mapa = tempfile.mkdtemp()
        self.streznik = {}

    def tearDown(self):
        import shutil
        shutil.rmtree(self.mapa, ignore_errors=True)

    def _objavi(self, manifest, paket, verzija):
        self.streznik = {"https://intel.test/v1/scit/latest.json": manifest,
                         "https://intel.test/v1/scit/scit-%d.json" % verzija: paket}

    def _fetch(self, url, meja):
        if url not in self.streznik:
            raise OSError("404")
        return self.streznik[url][:meja + 1]

    def _seznam(self):
        return sp.PodpisanSeznam(self.mapa, self.zaupani, ["https://intel.test"], fetch=self._fetch)

    def test_namesti_preveri_samo_naprej(self):
        m, p = _paket(self.kljuc, 202610200000, {"sledilci": ["novi-sledilec.example"], "poti": [["x.example", "/log"]]})
        self._objavi(m, p, 202610200000)
        s = self._seznam()
        nova = s.posodobi(ZDAJ)
        self.assertEqual((nova.vir, nova.verzija, nova.sledilci), ("podpisana", 202610200000, ("novi-sledilec.example",)))
        self.assertEqual(s.namescena_verzija(), 202610200000)
        self.assertEqual(s.nalozi().poti, (("x.example", "/log"),))         # znova preverjen z diska
        self.assertIsNone(s.posodobi(ZDAJ))                                  # ista verzija: nic novega
        # Starejsa verzija (vrnitev nazaj) se zavrne, namesceni ostane.
        m2, p2 = _paket(self.kljuc, 202610190000)
        self._objavi(m2, p2, 202610190000)
        self.assertIsNone(s.posodobi(ZDAJ))
        self.assertIn("RollbackError", s.zadnja_napaka)
        self.assertEqual(s.nalozi().verzija, 202610200000)

    def test_ponarejen_ali_pokvarjen_se_zavrne(self):
        tuj = Ed25519PrivateKey.generate()
        primeri = {}
        m, p = _paket(tuj, 202610210000)
        primeri["tuj kljuc"] = (m, p)
        m, p = _paket(self.kljuc, 202610210000)
        primeri["spremenjen paket"] = (m, p.replace(b"sledilec.example", b"sledilec.exampla"))
        m, p = _paket(self.kljuc, 202610210000, dni=1, zdaj=ZDAJ - timedelta(days=5))
        primeri["pretecen"] = (m, p)
        m, p = _paket(self.kljuc, 202610210000, key_id="neznan")
        primeri["neznan id kljuca"] = (m, p)
        # Podpisan, a s pravilom, ki bi zaprlo YouTube: odjemalec ga zavrne kljub veljavnemu podpisu.
        paket, man = sp.zgradi_paket({"sledilci": ["ok.example"]}, 202610210000, ZDAJ, ZDAJ + timedelta(days=9))
        vsebina = json.loads(paket)
        vsebina["rules"] = {"sledilci": ["googlevideo.com"]}
        vsebina["sha256"] = __import__("hashlib").sha256(signed_feed.canonical_json(vsebina["rules"])).hexdigest()
        paket = signed_feed.canonical_json(vsebina)
        man.update(rules_sha256=vsebina["sha256"])
        man["bundle"].update(size=len(paket), sha256=__import__("hashlib").sha256(paket).hexdigest(),
                             signature={"alg": "ed25519", "key_id": "preizkus",
                                        "sig": base64.b64encode(self.kljuc.sign(signed_feed.BUNDLE_CONTEXT + paket)).decode()})
        podpisano = signed_feed.canonical_json(man)
        ovoj = {"signed": base64.b64encode(podpisano).decode(), "signatures": [
            {"alg": "ed25519", "key_id": "preizkus",
             "sig": base64.b64encode(self.kljuc.sign(signed_feed.MANIFEST_CONTEXT + podpisano)).decode()}]}
        primeri["nujen gostitelj"] = (signed_feed.canonical_json(ovoj), paket)
        for opis, (m, p) in primeri.items():
            with self.subTest(opis):
                self._objavi(m, p, 202610210000)
                s = self._seznam()
                self.assertIsNone(s.posodobi(ZDAJ))
                self.assertTrue(s.zadnja_napaka)
                self.assertEqual(s.namescena_verzija(), 0)
                self.assertEqual(os.listdir(self.mapa), [])           # nic zapisano

    def test_storitev_vgrajeni_kot_rezerva_in_zamenjava_naenkrat(self):
        st = sp.StoritevPravil(self.mapa, self.zaupani, ["https://intel.test"], fetch=self._fetch, prva=0)
        self.assertEqual(st.pravila.vir, "vgrajena")
        self.assertFalse(st.posodobi_zdaj())                                   # streznik nima seznama (404)
        self.assertEqual(st.pravila.vir, "vgrajena")
        self.assertTrue(st.stanje()["napaka"])
        prejeto = []
        st.ob_spremembi(prejeto.append)
        nova_v = sp.VGRAJENA_VERZIJA + 1
        m, p = _paket(self.kljuc, nova_v, {"sledilci": ["samo-to.example"]}, zdaj=datetime.now(timezone.utc))
        self._objavi(m, p, nova_v)
        self.assertTrue(st.posodobi_zdaj())
        self.assertEqual([x.verzija for x in prejeto], [nova_v])
        self.assertEqual(st.pravila.sledilci, ("samo-to.example",))
        # Nova storitev (ponovni zagon) nalozi shranjeni seznam.
        st2 = sp.StoritevPravil(self.mapa, self.zaupani, ["https://intel.test"], fetch=lambda *a: (_ for _ in ()).throw(OSError()))
        st2._uporabi(st2.seznam.nalozi())
        self.assertEqual(st2.pravila.verzija, nova_v)

    def test_novejsi_vgrajen_ostane(self):
        """Program z novejsim vgrajenim seznamom ne vzame starejsega shranjenega podpisanega."""
        stara = sp.VGRAJENA_VERZIJA - 1
        m, p = _paket(self.kljuc, stara, zdaj=datetime.now(timezone.utc))
        self._objavi(m, p, stara)
        st = sp.StoritevPravil(self.mapa, self.zaupani, ["https://intel.test"], fetch=self._fetch)
        self.assertFalse(st.posodobi_zdaj())
        self.assertEqual(st.pravila.vir, "vgrajena")

    def test_isti_kljuc_kot_vir_groznj(self):
        from core import threat_intel
        st = sp.StoritevPravil(self.mapa)
        self.assertEqual(st.seznam.kljuci, threat_intel.TRUSTED_KEYS)
        self.assertEqual(st.seznam.osnove, [u.rstrip("/") for u in threat_intel.BASE_URLS])


class _Posrednik(http.server.BaseHTTPRequestHandler):
    """Lazni posrednik HTTP: zapise vsak zahtevan naslov in vrne stran ali prazno sliko."""
    zahteve: list = []
    STRAN = b"""<!doctype html><title>t</title>
<img src="http://www.google-analytics.com/collect.gif"><img src="http://cdn.stran.test/ok.gif">
<img src="http://www.youtube.com/api/stats/qoe?a=1"><img src="http://www.youtube.com/api/stats/playback?a=1">
<img src="http://dit.whatsapp.net/t.gif"><img src="http://sledilec-iz-seznama.test/p.gif">"""
    LASTNA = b"""<!doctype html><title>t</title><img src="http://www.google-analytics.com/self.gif">"""
    PING = b"""<!doctype html><title>t</title><a id="a" href="http://www.stran.test/cilj" ping="http://ping.stran.test/p">x</a>
<script>addEventListener('load', function () { navigator.sendBeacon('http://www.stran.test/beacon', 'x');
setTimeout(function () { document.getElementById('a').click(); }, 300); });</script>"""

    def do_GET(self):  # noqa: N802
        _Posrednik.zahteve.append(self.path)
        if self.path.endswith("/ping"):
            telo, vrsta = self.PING, "text/html"
        elif self.path.endswith("/stran"):
            telo, vrsta = (self.LASTNA if "google-analytics" in self.path else self.STRAN), "text/html"
        else:
            telo, vrsta = b"GIF89a\x01\x00\x01\x00\x00\x00\x00;", "image/gif"
        self.send_response(200)
        self.send_header("Content-Type", vrsta)
        self.send_header("Content-Length", str(len(telo)))
        self.end_headers()
        self.wfile.write(telo)

    def do_POST(self):  # noqa: N802 - <a ping> poslje POST
        _Posrednik.zahteve.append("POST " + self.path)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


class FilterWebKit(unittest.TestCase):
    """Pravila v pravem WebKitGTK 6.0 (prevedena kot v Spletu): tretji sledilec in poti telemetrije ne gredo ven,
    ostalo da. Brez zaslona ali WebKita se preskoci."""

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            raise unittest.SkipTest("ni zaslona (xvfb-run)")
        try:
            import gi
            gi.require_version("WebKit", "6.0")
            gi.require_version("Gtk", "4.0")
            from gi.repository import GLib, Gtk, WebKit
        except (ImportError, ValueError) as e:
            raise unittest.SkipTest("ni WebKitGTK 6.0: %s" % e)
        cls.GLib, cls.Gtk, cls.WebKit = GLib, Gtk, WebKit
        Gtk.init()
        cls.streznik = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Posrednik)
        cls.streznik.daemon_threads = True
        threading.Thread(target=cls.streznik.serve_forever, daemon=True).start()
        cls.mapa = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        cls.streznik.shutdown()
        cls.streznik.server_close()
        import shutil
        shutil.rmtree(cls.mapa, ignore_errors=True)

    def _nalozi(self, url, pravila_json=None, nastavi=None, js=None):
        WebKit, GLib = self.WebKit, self.GLib
        _Posrednik.zahteve = []
        zanka = GLib.MainLoop()
        ucm = WebKit.UserContentManager()
        izid = {}
        if pravila_json is not None:
            shramba = WebKit.UserContentFilterStore.new(self.mapa)

            def shranjen(st, r, *_):
                try:
                    ucm.add_filter(st.save_finish(r))
                except Exception as e:  # noqa: BLE001
                    izid["napaka"] = str(e)
                zanka.quit()
            shramba.save(sp.FILTER_ID, GLib.Bytes.new(pravila_json.encode()), None, shranjen)
            GLib.timeout_add_seconds(20, zanka.quit)
            zanka.run()
            self.assertNotIn("napaka", izid, izid.get("napaka"))
        seja = WebKit.NetworkSession.new_ephemeral()
        seja.set_proxy_settings(WebKit.NetworkProxyMode.CUSTOM,
                                WebKit.NetworkProxySettings.new("http://127.0.0.1:%d" % self.streznik.server_address[1], []))
        pogled = WebKit.WebView(network_session=seja, user_content_manager=ucm)
        if nastavi is not None:
            nastavi(pogled.get_settings())
        okno = self.Gtk.Window()
        okno.set_child(pogled)
        okno.present()
        zanka = GLib.MainLoop()

        def nalozeno(_p, dogodek):
            if dogodek == WebKit.LoadEvent.FINISHED:
                GLib.timeout_add(1500, zanka.quit)
        pogled.connect("load-changed", nalozeno)
        pogled.load_uri(url)
        GLib.timeout_add_seconds(25, zanka.quit)
        zanka.run()
        if js is not None:
            zanka = GLib.MainLoop()
            izid = {}

            def koncano(p, r, *_):
                try:
                    izid["v"] = p.call_async_javascript_function_finish(r).to_string()
                except Exception as e:  # noqa: BLE001
                    izid["v"] = "napaka: %s" % e
                zanka.quit()
            pogled.call_async_javascript_function(js, -1, None, None, None, None, koncano)
            GLib.timeout_add_seconds(20, zanka.quit)
            zanka.run()
            okno.destroy()
            return izid.get("v")
        okno.destroy()
        return list(_Posrednik.zahteve)

    def test_tretji_sledilec_in_telemetrija_ne_gresta_ven(self):
        pravila = sp.preveri_pravila(dict(sp.VGRAJENA, sledilci=list(sp.VGRAJENA["sledilci"]) + ["sledilec-iz-seznama.test"]),
                                     1, "preizkus")
        brez = self._nalozi("http://www.stran.test/stran")
        self.assertIn("http://www.google-analytics.com/collect.gif", brez)       # kontrola: brez filtra gre ven
        z = self._nalozi("http://www.stran.test/stran", pravila.webkit_json())
        self.assertIn("http://cdn.stran.test/ok.gif", z)
        self.assertIn("http://www.youtube.com/api/stats/playback?a=1", z)       # zgodovina ogledov ostane
        for blok in ("http://www.google-analytics.com/collect.gif", "http://www.youtube.com/api/stats/qoe?a=1",
                     "http://dit.whatsapp.net/t.gif", "http://sledilec-iz-seznama.test/p.gif"):
            self.assertNotIn(blok, z)
        # Na svoji strani sledilec ni »tretji«: uporabnik, ki ga odpre, ga dobi.
        lastna = self._nalozi("http://www.google-analytics.com/stran", pravila.webkit_json())
        self.assertIn("http://www.google-analytics.com/self.gif", lastna)

    def test_ping_pri_kliku_ne_gre_ven(self):
        """<a ping> (sledenje klikov) WebKitGTK 6.0 poslje tudi z izklopljenim enable-hyperlink-auditing (ta ne dela vec);
        ustavi ga pravilo filtra vrste »ping«. navigator.sendBeacon na prvo stran ostane (ni sledilec s seznama)."""
        def izklopi(n):
            with __import__("warnings").catch_warnings():
                n.set_property("enable-hyperlink-auditing", False)
        brez = self._nalozi("http://www.stran.test/ping", nastavi=izklopi)
        self.assertIn("POST http://ping.stran.test/p", brez)            # kontrola: nastavitev ga ne ustavi
        z = self._nalozi("http://www.stran.test/ping", sp.vgrajena().webkit_json())
        self.assertNotIn("POST http://ping.stran.test/p", z)
        self.assertIn("http://www.stran.test/cilj", z)                   # povezava sama deluje
        self.assertIn("POST http://www.stran.test/beacon", z)

    ICE = """
        if (typeof RTCPeerConnection === 'undefined') return 'brez';
        const pc = new RTCPeerConnection({iceServers: []});
        const c = [];
        pc.onicecandidate = e => { if (e.candidate && e.candidate.candidate) c.push(e.candidate.candidate); };
        pc.createDataChannel('x');
        await pc.setLocalDescription(await pc.createOffer());
        await new Promise(r => setTimeout(r, 2500));
        pc.close();
        return JSON.stringify({c: c, uad: typeof navigator.userAgentData});"""

    def test_webrtc_ne_izda_lokalnih_naslovov(self):
        def nastavi(filtriraj):
            def f(n):
                n.set_enable_webrtc(True)
                sp.zasebnost_pogleda(self.WebKit, n)
                if not filtriraj:                                       # kontrola: brez filtra kandidatov
                    sez = self.WebKit.Settings.get_all_features()
                    for i in range(sez.get_length()):
                        if sez.get(i).get_identifier() == "ICECandidateFiltering":
                            n.set_feature_enabled(sez.get(i), False)
            return f
        import re
        z = self._nalozi("http://www.stran.test/stran", nastavi=nastavi(True), js=self.ICE)
        if z in (None, "brez") or z.startswith("napaka"):
            self.skipTest("WebKit brez WebRTC: %s" % z)
        z = json.loads(z)
        ip = re.compile(r"\b\d{1,3}(\.\d{1,3}){3}\b")
        self.assertFalse([c for c in z["c"] if ip.search(c)], z["c"])
        self.assertEqual(z["uad"], "undefined")                          # brez navigator.userAgentData
        kontrola = json.loads(self._nalozi("http://www.stran.test/stran", nastavi=nastavi(False), js=self.ICE))
        if not [c for c in kontrola["c"] if ip.search(c)]:
            self.skipTest("ta sistem nima vmesnika z naslovom IPv4 - kontrole ni mogoce narediti")

    def test_nov_seznam_zamenja_filter_v_pogledih(self):
        """FilterSledilcev: preveden ob zagonu, ob novem (podpisanem) seznamu preveden znova in zamenjan naenkrat."""
        GLib = self.GLib
        st = sp.StoritevPravil(tempfile.mkdtemp(dir=self.mapa), kljuci={}, osnove=[])
        f = sp.FilterSledilcev(self.WebKit, GLib, os.path.join(self.mapa, "sledilci"), storitev=st)

        def cakaj(pogoj, s=20):
            konec = time.monotonic() + s
            ctx = GLib.MainContext.default()
            while not pogoj() and time.monotonic() < konec:
                ctx.iteration(False)
                time.sleep(0.01)
            return pogoj()
        self.assertTrue(cakaj(lambda: f.filter is not None))
        prejeti = []
        f.ob_novem(prejeti.append)
        self.assertEqual(len(prejeti), 1)                         # ze preveden: takoj
        nova = sp.preveri_pravila({"sledilci": ["sledilec-iz-seznama.test"]}, sp.VGRAJENA_VERZIJA + 5, "podpisana")
        self.assertTrue(st._uporabi(nova))
        self.assertTrue(cakaj(lambda: len(prejeti) == 2))
        self.assertIsNot(prejeti[0], prejeti[1])

    def test_banke_izvzete(self):
        z = self._nalozi("http://www.stran.test/stran", sp.vgrajena().webkit_json(nikoli=["stran.test"]))
        self.assertIn("http://www.google-analytics.com/collect.gif", z)


if __name__ == "__main__":
    unittest.main()


def test_navigator_storage_v_zivem_webkitu():
    """Webmaster pregled motorja 20. 10. 2026: navigator.storage je bil undefined (StorageAPI privzeto izklopljen).
    Pravi WebKitGTK 6.0 (Xvfb): po funkcije_spleta je estimate() na voljo. Brez zaslona/WebKita se preskoci."""
    import os
    import pytest
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        pytest.skip("potrebuje zaslon")
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("WebKit", "6.0")
        from gi.repository import GLib, Gtk, WebKit
    except Exception:  # noqa: BLE001
        pytest.skip("potrebuje WebKitGTK")
    from core import scit_pravila as sp

    def preveri(vklop):
        v = WebKit.WebView(network_session=WebKit.NetworkSession.new_ephemeral())
        o = Gtk.Window()
        o.set_child(v)
        if vklop:
            assert "StorageAPI" in sp.funkcije_spleta(WebKit, v.get_settings())
        izid, zanka = [], GLib.MainLoop()

        def nalozeno(p, d):
            if d == WebKit.LoadEvent.FINISHED:
                p.evaluate_javascript("typeof navigator.storage === 'object' && typeof navigator.storage.estimate",
                                      -1, None, None, None,
                                      lambda w, r: (izid.append(w.evaluate_javascript_finish(r).to_string()), zanka.quit()))
        v.connect("load-changed", nalozeno)
        v.load_html("<p>x</p>", "https://example.org/")      # varen kontekst (https), brez omrezja
        GLib.timeout_add(10000, lambda: (zanka.quit(), False)[1])
        zanka.run()
        o.set_child(None)
        return izid[0] if izid else None
    assert preveri(True) == "function"
    assert preveri(False) != "function"      # brez vklopa ga ni - preizkus res meri popravek
