"""Lastni vgrajeni viri (core/os_vgrajeni_viri.py, core/meritve_virov.py, most v core/os_katalog.py, stran vgrajeno.js).

Lastnik, 15. 10. 2026: uporabnik vgradi katerokoli stran ali svojo komponento React; Safeer ne prinasa nobenega vira;
viri ne podvajajo vsebine (ena kartica na naslov); najhitrejsi dosegljiv vir je privzet, nedosegljivih ni.
Zivi preizkus v WebKitu: tests/test_vgrajeni_viri_zivo.py."""
import json
import os
import re
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from core import meritve_virov as M
from core import os_katalog as K
from core import os_media
from core import os_vgrajeni_viri as V

KOREN = Path(__file__).resolve().parent.parent


def _nastavitve(**kw):
    d = {V.KLJUC_OBVESTILA: True}
    d.update(kw)
    return d


class Naslovi(unittest.TestCase):
    def test_samo_https_in_http_v_domacem_omrezju(self):
        self.assertEqual(V.preveri_naslov("https://primer.si/a"), "https://primer.si/a")
        for lan in ("http://192.168.1.5:8096/x", "http://10.0.0.2/", "http://127.0.0.1:8080/", "http://nas.local/",
                    "http://[fd00::1]/", "http://localhost:3000/"):
            self.assertTrue(V.preveri_naslov(lan), lan)
        with self.assertRaises(V.NapakaVira) as n:
            V.preveri_naslov("http://primer.si/")
        self.assertEqual(n.exception.koda, "http")
        for slab, koda in (("javascript:alert(1)", "shema"), ("data:text/html,<b>x</b>", "shema"),
                           ("file:///etc/passwd", "shema"), ("https://u:g@primer.si/", "geslo"),
                           ("https://primer.si/a b", "naslov"), ("https:///pot", "naslov"), ("", "naslov"),
                           ("ftp://primer.si/", "shema"), ("https://primer.si:99999/", "naslov")):
            with self.assertRaises(V.NapakaVira, msg=slab) as n:
                V.preveri_naslov(slab)
            self.assertEqual(n.exception.koda, koda, slab)

    def test_predloga(self):
        p = "https://pred.example/embed/{type}/{tmdb}?s={season}&e={episode}&imdb={imdb}&q={title}&y={year}&tv={tvdb}"
        self.assertEqual(V.preveri_predlogo(p), p)
        for slab, koda in (("https://{title}.example/x", "znacka_gostitelj"), ("https://x.example/{foo}", "znacka"),
                           ("javascript:{imdb}", "shema"), ("https://x.example/{imdb", "znacka"),
                           ("http://javni.example/{imdb}", "http"), ("https://x.example/{}", "znacka")):
            with self.assertRaises(V.NapakaVira, msg=slab) as n:
                V.preveri_predlogo(slab)
            self.assertEqual(n.exception.koda, koda, slab)

    def test_izpolni_kodira_vrednosti(self):
        p = "https://x.example/{type}/{imdb}/{season}/{episode}?t={title}"
        podatki = V.podatki_vnosa({"vrsta": "serija", "imdb_id": "tt0903747", "naslov": "A/B?c=d&e#f @x"}, 2, 3)
        url = V.izpolni(p, podatki)
        self.assertEqual(url, "https://x.example/tv/tt0903747/2/3?t=A%2FB%3Fc%3Dd%26e%23f%20%40x")
        self.assertIsNone(V.izpolni("https://x.example/{tvdb}", podatki), "manjka vrednost: ni gumba")
        # Neveljavni id-ji se ne prenesejo (samo tt\\d+, stevilke).
        self.assertEqual(V.podatki_vnosa({"imdb_id": "tt1<script>", "tmdb_id": "12a", "leto": "abcd"}),
                         {"type": "movie"})
        film = V.podatki_vnosa({"vrsta": "film", "imdb_id": "tt0111161", "tmdb_id": 278, "tvdb_id": 190,
                                "naslov": "The Shawshank Redemption", "leto": 1994})
        self.assertEqual(film, {"imdb": "tt0111161", "tmdb": "278", "tvdb": "190", "type": "movie",
                                "title": "The Shawshank Redemption", "year": "1994"})
        self.assertNotIn("season", film)

    def test_normalizacija(self):
        a = V.normaliziraj_url("HTTPS://Primer.SI:443/pot/?b=2&a=1")
        self.assertEqual(a, V.normaliziraj_url("https://primer.si/pot?a=1&b=2"))
        self.assertNotEqual(a, V.normaliziraj_url("https://primer.si:8443/pot?a=1&b=2"))
        self.assertEqual(V.normaliziraj_url("http://nas.local:80/x/"), "http://nas.local/x")

    def test_preizkusi(self):
        r = V.preizkusi({"url": "https://x.example/{type}/{imdb}/{season}"})
        self.assertIsNone(r["film"])
        self.assertEqual(r["serija"], "https://x.example/tv/tt0903747/1")
        with self.assertRaises(V.NapakaVira):
            V.preizkusi({"url": "https://x.example/{tvdb}/{season}/{foo}"})


class Shramba(unittest.TestCase):
    def test_brez_vnaprej_nastavljenih_virov(self):
        self.assertEqual(V.seznam({}), [])
        if True:
            d = _zacasna(self)
            kat = K.Katalog(d, lambda *_: None, lambda f: f(), *(lambda *a, **k: True,) * 4)
            r = kat._vgr_seznam([])
            self.assertEqual((r["viri"], r["ploscice"], r["obvestilo"]), ([], [], False))
        # V kodi ni nobenega naslova tujega ponudnika predvajanja.
        self.assertFalse(re.search(r"https://[a-z0-9.-]+\.(?:to|cc|xyz|ru)/", (KOREN / "core" / "os_vgrajeni_viri.py").read_text()))

    def test_obvestilo_pred_prvim_virom(self):
        d = {}
        with self.assertRaises(V.NapakaVira) as n:
            V.shrani(d, {"ime": "A", "url": "https://a.example/{imdb}"})
        self.assertEqual(n.exception.koda, "obvestilo")
        d[V.KLJUC_OBVESTILA] = True
        vir = V.shrani(d, {"ime": "A", "url": "https://a.example/{imdb}"})
        self.assertTrue(vir["vklopljen"])
        self.assertFalse(vir["pojavna"], "pojavna okna privzeto izkljucena")

    def test_dodaj_uredi_izklopi_odstrani(self):
        d = _nastavitve()
        a = V.shrani(d, {"ime": "A", "url": "https://a.example/{imdb}", "pojavna": True})
        V.shrani(d, {"ime": "K", "vrsta": "komponenta", "koda": "export default function X(){return null}"})
        V.shrani(d, {"id": a["id"], "ime": "A2", "url": "https://a.example/e/{imdb}", "vklopljen": False})
        viri = V.seznam(d)
        self.assertEqual([(v["ime"], v["vklopljen"]) for v in viri], [("A2", False), ("K", True)])
        self.assertTrue(viri[0]["pojavna"], "urejanje ohrani pojavna okna")
        self.assertTrue(V.odstrani(d, a["id"]))
        self.assertEqual([v["ime"] for v in V.seznam(d)], ["K"])
        with self.assertRaises(V.NapakaVira):
            V.shrani(d, {"ime": "K2", "vrsta": "komponenta", "koda": "x" * (V.NAJVEC_KODE + 1)})
        with self.assertRaises(V.NapakaVira):
            V.shrani(d, {"ime": "", "url": "https://a.example/"})

    def test_navadna_stran_brez_podvojitve(self):
        d = _nastavitve()
        V.shrani(d, {"ime": "Stran", "url": "https://Stran.example/app/?b=1&a=2"})
        with self.assertRaises(V.NapakaVira) as n:
            V.shrani(d, {"ime": "Ista", "url": "https://stran.example:443/app?a=2&b=1"})
        self.assertEqual(n.exception.koda, "podvojen")                  # »Ta vir že imaš«
        self.assertEqual(len(V.ploscice(V.seznam(d))), 1)
        # Pokvarjen zapis v nastavitvah ne podre seznama.
        d[V.KLJUC_VIROV].append({"ime": "x", "url": "javascript:alert(1)"})
        self.assertEqual(len(V.seznam(d)), 1)

    def test_most_katalog_in_nastavitve_na_disku(self):
        if True:
            mapa = _zacasna(self)
            dogodki = []
            kat = K.Katalog(mapa, lambda v, p: dogodki.append(v), lambda f: f(), *(lambda *a, **k: True,) * 4)
            kat.mc._meritve._sonda = lambda url, cas: 5.0
            self.assertEqual(kat._vgr_shrani([{"ime": "A", "url": "https://a.example/{imdb}"}]),
                             {"ok": False, "napaka": "obvestilo"})
            self.assertTrue(kat._vgr_obvestilo([]))
            r = kat._vgr_shrani([{"ime": "A", "url": "https://a.example/{imdb}"}])
            self.assertTrue(r["ok"])
            na_disku = json.loads((Path(mapa) / "nastavitve.json").read_text())
            self.assertEqual(na_disku[V.KLJUC_VIROV][0]["url"], "https://a.example/{imdb}")
            self.assertEqual(kat._vgr_preizkusi([{"url": "https://a.example/{foo}"}]), {"ok": False, "napaka": "znacka"})
            for metoda in ("mediaVgrajeniViri", "mediaVgrajenVirShrani", "mediaVgrajenVirOdstrani", "mediaVgrajenVirPreizkusi",
                           "mediaVgrajeniObvestilo", "mediaVgrajeneMoznosti", "mediaVgrajenaKnjiznica", "mediaVgrajeniOsvezi",
                           "mediaVgrajenoPreveri"):
                self.assertIn(metoda, K.Katalog.METODE)
            self.assertNotIn("mediaVgrajenaIzbira", K.Katalog.METODE)            # rocne izbire ni (NALOGA 33)
            self.assertTrue(kat._vgr_odstrani([r["vir"]["id"]]))


class BrezPodvajanja(unittest.TestCase):
    """Ena kartica na naslov: Stremio + Jellyfin + dva lastna vira na istem filmu = ena kartica, viri so le gumbi."""

    def test_stremio_jellyfin_in_dva_vira_ena_kartica(self):
        stremio = os_media._item("Film X", "https://cdn.stremio-dodatek.example/x.mp4", base="", source_id="stremio:1",
                                 source_name="Dodatek", kind="film", year=2020, imdb_id="tt1234567")
        jellyfin = os_media._item("Film X (2020)", "http://192.168.1.5:8096/Videos/1/stream.mp4", base="",
                                  source_id="jf", source_name="Jellyfin", kind="film", year=2020, imdb_id="tt1234567")
        kartice = os_media.merge_duplicates([stremio, jellyfin])
        self.assertEqual(len(kartice), 1)
        d = _nastavitve()
        V.shrani(d, {"ime": "Prvi", "url": "https://prvi.example/embed/{imdb}"})
        V.shrani(d, {"ime": "Drugi", "url": "https://drugi.example/movie?id={imdb}"})
        katalog_po = os_media.merge_duplicates([stremio, jellyfin])
        self.assertEqual(len(katalog_po), 1, "viri ne dodajo kartic")
        moznosti = V.moznosti_za(V.seznam(d), kartice[0])
        self.assertEqual([m["ime"] for m in moznosti], ["Prvi", "Drugi"])
        self.assertTrue(moznosti[0]["privzeta"])

    def test_isti_koncni_naslov_enkrat(self):
        d = _nastavitve()
        V.shrani(d, {"ime": "A", "url": "https://p.example/e/{imdb}/?x=1&y=2"})
        V.shrani(d, {"ime": "B", "url": "HTTPS://P.example:443/e/{imdb}?y=2&x=1"})
        V.shrani(d, {"ime": "C", "url": "https://q.example/{imdb}"})
        moznosti = V.moznosti_za(V.seznam(d), {"vrsta": "film", "imdb_id": "tt0111161"})
        self.assertEqual([m["ime"] for m in moznosti], ["A", "C"])
        self.assertEqual(moznosti[0]["tudi"], ["B"])

    def test_komponenta_ne_da_vnosov(self):
        js = (KOREN / "assets" / "os" / "vgrajeno.js").read_text(encoding="utf-8")
        dovoljena = re.search(r"var DOVOLJENA = \{([^}]*)\}", js).group(1)
        self.assertEqual(set(re.findall(r"(\w+): 1", dovoljena)),
                         {"nalozen", "pripravljen", "zapri", "celozaslonsko", "napaka", "potrebujemBabel"})
        self.assertIn("e.source !== okvir.contentWindow", js)
        # Komponenta in navadna stran nista v katalogu: katalog ne bere nastavitev vgrajenih virov.
        self.assertNotIn("import os_vgrajeni_viri", (KOREN / "core" / "os_media.py").read_text(encoding="utf-8"))

    def test_navadna_stran_ni_gumb_naslova(self):
        d = _nastavitve()
        V.shrani(d, {"ime": "Portal", "url": "https://portal.example/"})
        self.assertEqual(V.moznosti_za(V.seznam(d), {"imdb_id": "tt0111161"}), [])
        self.assertEqual([p["ime"] for p in V.ploscice(V.seznam(d))], ["Portal"])


class _Ura:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


class Meritve(unittest.TestCase):
    def test_razvrstitev_lastni_najhitrejsi_nedosegljivi(self):
        ura = _Ura()
        casi = {"hitri.example": 20.0, "pocasni.example": 90.0}

        def sonda(url, _cas):
            g = url.split("/")[2]
            if g not in casi:
                raise OSError("zaprto")
            return casi[g]
        m = M.Meritve(None, sonda=sonda, ura=ura)
        for g in ("hitri", "pocasni", "mrtvi"):
            m.izmeri("https://%s.example/" % g)
        moznosti = [{"url": "https://mrtvi.example/a", "vir": "mrtvi"}, {"url": "https://pocasni.example/a", "vir": "p"},
                    {"url": "https://neizmerjeni.example/a", "vir": "n"}, {"url": "https://hitri.example/a", "vir": "h"},
                    {"url": "http://192.168.1.5:8096/a", "vir": "jellyfin", "lastni": True}]
        self.assertEqual([x["vir"] for x in M.razvrsti(moznosti, m)], ["jellyfin", "h", "p", "n", "mrtvi"])
        # Lastni vgrajeni viri: nedosegljivega ni, najhitrejsi je privzet; rocne izbire ni (NALOGA 33).
        d = _nastavitve()
        for ime in ("mrtvi", "pocasni", "hitri"):
            V.shrani(d, {"ime": ime, "url": "https://%s.example/{imdb}" % ime})
        item = {"vrsta": "film", "imdb_id": "tt0111161"}
        moz = V.moznosti_za(V.seznam(d), item, meritve=m)
        self.assertEqual([(x["ime"], x["ms"]) for x in moz], [("hitri", 20.0), ("pocasni", 90.0)])
        self.assertTrue(moz[0]["privzeta"])
        # Nekdanja rocna izbira v nastavitvah ne spremeni vrstnega reda in se pozabi.
        d[V.KLJUC_IZBIRE] = {"imdb:tt0111161": next(v["id"] for v in V.seznam(d) if v["ime"] == "pocasni")}
        self.assertEqual([x["ime"] for x in V.moznosti_za(V.seznam(d), item, meritve=m)], ["hitri", "pocasni"])
        self.assertTrue(V.pozabi_rocne_izbire(d))
        self.assertNotIn(V.KLJUC_IZBIRE, d)
        self.assertFalse(V.pozabi_rocne_izbire(d))
        # Ko meritev spet uspe, se vir vrne sam.
        casi["mrtvi.example"] = 10.0
        ura.t += M.STAROST_NEDOSEGLJIV_S + 1
        self.assertTrue(m.zastarelo("https://mrtvi.example/"))
        m.izmeri_v_ozadju(["https://mrtvi.example/x"]).join(5)
        self.assertEqual([x["ime"] for x in V.moznosti_za(V.seznam(d), item, meritve=m)], ["mrtvi", "hitri", "pocasni"])

    def test_ploscica_nedosegljive_strani_skrita(self):
        if True:
            mapa = _zacasna(self)
            kat = K.Katalog(mapa, lambda *_: None, lambda f: f(), *(lambda *a, **k: True,) * 4)
            meritve = kat.mc._meritve
            meritve._sonda = mock.Mock(side_effect=OSError("zaprto"))
            kat._vgr_obvestilo([])
            kat._vgr_shrani([{"ime": "Portal", "url": "https://portal.example/"}])
            self.assertTrue(_cakaj(lambda: meritve.nedosegljiv("https://portal.example/")))
            r = kat._vgr_seznam([])
            self.assertEqual(r["ploscice"], [])
            self.assertFalse(r["viri"][0]["meritev"]["ok"], "v nastavitvah ostane, z »ni dosegljiv«")

    def test_predpomnilnik_brez_ponovnega_merjenja_in_osvezitev(self):
        ura = _Ura()
        sonda = mock.Mock(return_value=12.0)
        with tempfile.TemporaryDirectory() as d:
            pot = Path(d) / "meritve.json"
            m = M.Meritve(pot, sonda=sonda, ura=ura)
            m.izmeri("https://a.example/x")
            self.assertEqual(sonda.call_count, M.VZORCEV)
            self.assertEqual(m.stanje("https://a.example/y")["ms"], 12.0)
            self.assertIsNone(m.izmeri_v_ozadju(["https://a.example/z"]), "sveza meritev: brez sonde")
            # Na disku: nov primerek (ponovni zagon) meritev ze ima.
            m2 = M.Meritve(pot, sonda=sonda, ura=ura)
            self.assertEqual(m2.ms("https://a.example/"), 12.0)
            self.assertIsNone(m2.izmeri_v_ozadju(["https://a.example/"]))
            self.assertEqual(sonda.call_count, M.VZORCEV)
            ura.t += M.STAROST_DOSEGLJIV_S + 1                  # po 24 h zastarela: izmeri znova
            m2.izmeri_v_ozadju(["https://a.example/"]).join(5)
            self.assertEqual(sonda.call_count, 2 * M.VZORCEV)

    def test_meritev_ni_v_glavni_niti_in_ena_na_gostitelja(self):
        niti, vrata = [], threading.Event()

        def sonda(_url, _cas):
            niti.append(threading.current_thread())
            vrata.wait(5)
            return 3.0
        m = M.Meritve(None, sonda=sonda)
        zacetek = time.monotonic()
        nit = m.izmeri_v_ozadju(["https://a.example/1", "https://a.example/2"])
        self.assertLess(time.monotonic() - zacetek, 0.5, "klic se vrne takoj")
        self.assertTrue(_cakaj(lambda: niti))
        self.assertIsNone(m.izmeri("https://a.example/3"), "isti gostitelj se ze meri")
        vrata.set()
        nit.join(5)
        self.assertTrue(all(n is not threading.main_thread() for n in niti))
        self.assertEqual(len(niti), M.VZORCEV, "dva naslova istega gostitelja = ena meritev")

    def test_zaprt_in_pocasen_strežnik(self):
        # Zaprta vrata: hitro »ni dosegljiv«.
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        zaprta = s.getsockname()[1]
        s.close()
        m = M.Meritve(None)
        zacetek = time.monotonic()
        z = m.izmeri("https://127.0.0.1:%d/" % zaprta, cas_s=0.5)
        self.assertFalse(z["ok"])
        self.assertLess(time.monotonic() - zacetek, 2.0)
        # Pocasen: sprejme TCP, rokovanja TLS nikoli ne konca - meritev se konca po casu vzorca.
        pocasen = socket.socket()
        pocasen.bind(("127.0.0.1", 0))
        pocasen.listen(5)
        self.addCleanup(pocasen.close)
        zacetek = time.monotonic()
        z = m.izmeri("https://127.0.0.1:%d/" % pocasen.getsockname()[1], cas_s=0.4)
        self.assertFalse(z["ok"])
        self.assertLess(time.monotonic() - zacetek, 2.0, "en neuspel vzorec konca meritev")
        # Dosegljiv strežnik http v domacem omrezju: ok z izmerjenim casom.
        z = m.izmeri("http://127.0.0.1:%d/" % pocasen.getsockname()[1], cas_s=0.5)
        self.assertTrue(z["ok"])
        self.assertIsNotNone(z["ms"])

    def test_scit_ne_meri_blokiranih(self):
        sonda = mock.Mock(return_value=1.0)
        m = M.Meritve(None, sonda=sonda, blokirano=lambda u: "oglas" in u)
        self.assertFalse(m.izmeri("https://oglas.example/")["ok"])
        sonda.assert_not_called()

    def test_os_media_uporablja_iste_meritve(self):
        with tempfile.TemporaryDirectory() as d:
            mc = os_media.MediaCenter(d, roots=[])
            mc._meritve._sonda = lambda url, cas: {"a.example": 50.0, "b.example": 5.0}[url.split("/")[2]]
            mc._meritve.izmeri("https://a.example/")
            mc._meritve.izmeri("https://b.example/")
            item = {"url": "https://a.example/1", "razlicice": [{"url": "https://a.example/1", "vir": "A"},
                                                                {"url": "https://b.example/1", "vir": "B"}]}
            izid = mc._izberi_najhitrejsi(item)
            self.assertEqual((izid["izbran_vir"], izid["izbran_ping_ms"]), ("B", 5.0))


class Knjiznice(unittest.TestCase):
    def test_sha256_in_licence(self):
        for ime, (datoteka, _sha) in V.KNJIZNICE.items():
            self.assertTrue(V.knjiznica(ime), ime)
        mapa = KOREN / "assets" / "os" / "vendor"
        for licenca in ("LICENSE-react", "LICENSE-react-dom", "LICENSE-babel"):
            self.assertIn("MIT License", (mapa / licenca).read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "react.production.min.js").write_text("spremenjeno")
            with self.assertRaises(V.NapakaVira):
                V.knjiznica("react", Path(d))
        with self.assertRaises(V.NapakaVira):
            V.knjiznica("../os.js")


class StranInMost(unittest.TestCase):
    def setUp(self):
        self.js = (KOREN / "assets" / "os" / "vgrajeno.js").read_text(encoding="utf-8")
        self.os_js = (KOREN / "assets" / "os" / "os.js").read_text(encoding="utf-8")
        self.html = (KOREN / "assets" / "os" / "index.html").read_text(encoding="utf-8")
        self.py = (KOREN / "safeer_os.py").read_text(encoding="utf-8")

    def test_peskovnik_okvirjev(self):
        self.assertIn('"allow-scripts allow-same-origin allow-forms allow-presentation"', self.js)
        self.assertIn('(opts.allowPopups ? " allow-popups" : "")', self.js)
        peskovniki = re.findall(r'setAttribute\("sandbox", ([^;]*)\);', self.js)
        self.assertEqual(len(peskovniki), 2)
        self.assertFalse(any("top-navigation" in p for p in peskovniki))
        self.assertIn('okvir.setAttribute("sandbox", "allow-scripts");', self.js)
        self.assertEqual(self.js.count('setAttribute("referrerpolicy", "no-referrer")'), 2)
        # Peskovnik komponente: datoteka (ne srcdoc - ta bi podedoval politiko strani), vrinjena skripta samo po odtisu.
        import base64
        import hashlib
        pesk = (KOREN / "assets" / "os" / "peskovnik.html").read_text(encoding="utf-8")
        csp = re.search(r'Content-Security-Policy" content="([^"]+)"', pesk).group(1)
        self.assertIn("connect-src 'none'", csp)
        self.assertIn("default-src 'none'", csp)
        self.assertNotIn("unsafe-inline' 'unsafe-eval", csp.split("script-src", 1)[1].split(";", 1)[0])
        skripta = re.search(r"<script>(.*?)</script>", pesk, re.S).group(1)
        odtis = "sha256-" + base64.b64encode(hashlib.sha256(skripta.encode("utf-8")).digest()).decode()
        self.assertIn("script-src '%s' 'unsafe-eval'" % odtis, csp)
        self.assertEqual(pesk.count("<script"), 1)
        self.assertIn('okvir.src = opts.peskovnik || "peskovnik.html";', self.js)
        self.assertNotIn("srcdoc =", self.js)
        self.assertIn('"autoplay; "', self.js)
        self.assertIn('"encrypted-media; picture-in-picture"', self.js)

    def test_most_zeton_in_politika(self):
        self.assertIn("ZETON_MOSTU = secrets.token_urlsafe(32)", self.py)
        self.assertIn("if not zeton_velja(s):", self.py)
        self.assertIn('WebKit2.UserScriptInjectionTime.START, ["file:///*"], None))', self.py)
        self.assertIn("odlocitev.is_main_frame_main_resource() and os_vgrajeni_viri.tuja_glavna_stran(", self.py)
        self.assertTrue(V.dovoli_okvir("about:srcdoc"))
        self.assertFalse(V.dovoli_okvir("javascript:alert(1)"))
        self.assertFalse(V.dovoli_okvir("http://javni.example/"))
        self.assertTrue(V.tuja_glavna_stran("https://zlo.example/", "file:///usr/lib/safeer-os/assets/os"))
        self.assertFalse(V.tuja_glavna_stran("file:///usr/lib/safeer-os/assets/os/index.html", "file:///usr/lib/safeer-os/assets/os"))

    def test_stran_klici_obstajajo(self):
        klici = set(re.findall(r'klic\("(mediaVgrajen[A-Za-z]*)"', self.os_js))
        self.assertTrue(klici and klici <= set(K.Katalog.METODE), klici - set(K.Katalog.METODE))
        self.assertIn('"vgrajenoAktivno": lambda: self._vgrajeno_aktivno(pogled', self.py)
        for ident in ("vgrSeznam", "vgrObrazec", "slojVgrOdgovornost", "vgrOdgPotrdi", "mediaVgrajenePloscice"):
            self.assertIn('id="%s"' % ident, self.html)
        # NALOGA 33: vgrajeni vir naslova se odpre samodejno, ko noben tok ne predvaja - brez seznama in gumbov za izbiro.
        self.assertIn("function vgrSamodejno(item)", self.os_js)
        self.assertNotIn('id="mediaVgrajeneMoznosti"', self.html)
        self.assertNotIn("narisiVgrajeneMoznosti", self.os_js)
        self.assertLess(self.html.index('src="vgrajeno.js"'), self.html.index('src="os.js"'))

    def test_besedila_v_vseh_jezikih(self):
        besedila = (KOREN / "assets" / "os" / "besedila.js").read_text(encoding="utf-8")
        bloki = re.findall(r"Object\.assign\(BESEDILA_OS\.(\w\w), (\{\"vgrNaslov\".*?\})\);", besedila)
        self.assertEqual([j for j, _ in bloki], ["sl", "en", "de", "es", "fr", "it"])
        kljuci = [set(json.loads(b)) for _, b in bloki]
        self.assertTrue(all(k == kljuci[0] for k in kljuci))
        uporabljeni = set(re.findall(r't\("(vgr[A-Z]\w*[a-z0-9])"', self.os_js)) | set(re.findall(r'data-(?:t|ph)="(vgr\w+)"', self.html))
        self.assertTrue(uporabljeni <= kljuci[0], uporabljeni - kljuci[0])
        for koda in ("naslov", "shema", "geslo", "http", "znacka", "znacka_gostitelj", "ime", "vnos", "koda", "obvestilo",
                     "prevec", "podvojen", "vzorec", "knjiznica"):
            self.assertIn("vgrNapaka_" + koda, kljuci[0])
        sl = json.loads(bloki[0][1])
        self.assertEqual(sl["vgrNapaka_podvojen"], "Ta vir že imaš.")
        self.assertIn("lastno odgovornost", sl["vgrOdgovornost"])

    def test_barve_iz_tokens(self):
        css = (KOREN / "assets" / "os" / "katalog.css").read_text(encoding="utf-8")
        blok = css[css.index("/* Lastni vgrajeni viri"):]
        self.assertFalse(re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", blok))

    def test_tovor(self):
        tovor = (KOREN / "packaging" / "install_os_payload.sh").read_text(encoding="utf-8")
        self.assertIn(" os_vgrajeni_viri ", tovor)
        self.assertIn(" meritve_virov ", tovor)


def _zacasna(test):
    """Zacasna mapa; meritve v ozadju lahko pisejo se po koncu preizkusa, zato brisemo brez napake."""
    import shutil
    d = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, d, True)
    return d


def _cakaj(pogoj, cas=5.0):
    rok = time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        time.sleep(0.01)
    return pogoj()


if __name__ == "__main__":
    unittest.main()
