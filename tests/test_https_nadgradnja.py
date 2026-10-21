"""Samodejni https s povratkom (lastnik 21. 10. 2026: »strani samodejno preide na https, ce ti stran omogoca«).

Odlocitve so ciste (brez WebKita); vezavo na pogled preizkusimo z laznim pogledom, GLib in WebKitom."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core import https_nadgradnja as H  # noqa: E402

KOREN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


class _Dogodek:
    STARTED, REDIRECTED, COMMITTED, FINISHED = range(4)


class _Napaka:
    def __init__(self, preklic=False):
        self.preklic = preklic

    def matches(self, domena, koda):
        return self.preklic and koda == "CANCELLED"


W = types.SimpleNamespace(LoadEvent=_Dogodek, network_error_quark=lambda: "net",
                          NetworkError=types.SimpleNamespace(CANCELLED="CANCELLED"))


class _GLib:
    def __init__(self):
        self.ure, self.prosto, self.odstranjene = {}, [], []
        self._st = 0

    def timeout_add(self, ms, cb):
        self._st += 1
        self.ure[self._st] = (ms, cb)
        return self._st

    def source_remove(self, st):
        self.odstranjene.append(st)
        self.ure.pop(st, None)

    def idle_add(self, cb):
        self.prosto.append(cb)

    def pozeni(self):
        while self.prosto:
            self.prosto.pop(0)()


class _Pogled:
    def __init__(self):
        self.uri, self.nalozeno, self.ustavljen, self.signali = "", [], 0, {}

    def connect(self, ime, cb):
        self.signali[ime] = cb

    def get_uri(self):
        return self.uri

    def load_uri(self, uri):
        self.nalozeno.append(uri)

    def stop_loading(self):
        self.ustavljen += 1


def _vezava(metoda="GET"):
    p, g, s = _Pogled(), _GLib(), H.Seja()
    v = H.Pogled(p, s, W, g, lambda uri: metoda)
    return p, g, s, v


class TestOdlocitev(unittest.TestCase):
    def test_javni_http_get_se_nadgradi(self):
        s = H.Seja()
        for http, https in (("http://example.com/", "https://example.com/"),
                            ("http://www.rtvslo.si/novice?x=1#a", "https://www.rtvslo.si/novice?x=1#a"),
                            ("HTTP://Example.com", "https://Example.com"),
                            ("http://example.com:80/pot", "https://example.com/pot")):
            with self.subTest(http=http):
                self.assertEqual(s.nadgradnja(http, "GET"), https)

    def test_brez_poskusa(self):
        s = H.Seja()
        for uri in ("http://192.168.0.1/", "http://10.0.0.5/", "http://127.0.0.1:8080/", "http://localhost/",
                    "http://[::1]/", "http://[fe80::1]/", "http://169.254.1.1/", "http://8.8.8.8/",
                    "http://nas/", "http://tiskalnik.local/", "http://router.lan/", "http://nas.home.arpa/",
                    "http://sistem.internal/", "http://app.localhost/", "http://example.com:8080/",
                    "http://uporabnik:geslo@example.com/", "https://example.com/", "ftp://example.com/", "", "http://"):
            with self.subTest(uri=uri):
                self.assertIsNone(s.nadgradnja(uri, "GET"))

    def test_samo_get(self):
        s = H.Seja()
        for metoda in ("POST", "PUT", None, "get"):
            with self.subTest(metoda=metoda):
                self.assertIsNone(s.nadgradnja("http://example.com/obrazec", metoda))

    def test_povratek_velja_za_sejo(self):
        s = H.Seja()
        s.povratek("Example.com")
        self.assertIsNone(s.nadgradnja("http://example.com/druga", "GET"))
        self.assertEqual(s.nadgradnja("http://drugo.si/", "GET"), "https://drugo.si/")


class TestVezava(unittest.TestCase):
    def test_signali_so_povezani(self):
        p, _g, _s, _v = _vezava()
        self.assertEqual(set(p.signali), {"load-changed", "load-failed", "load-failed-with-tls-errors"})

    def test_povezava_na_http_poskusi_https(self):
        p, g, _s, v = _vezava()
        p.uri = "http://example.com/a"
        v.load_changed(p, _Dogodek.STARTED)
        g.pozeni()
        self.assertEqual(p.nalozeno, ["https://example.com/a"])
        self.assertEqual([ms for ms, _cb in g.ure.values()], [int(H.ROK_S * 1000)])

    def test_post_se_ne_nadgradi(self):
        p, g, _s, v = _vezava(metoda="POST")
        p.uri = "http://example.com/obrazec"
        v.load_changed(p, _Dogodek.STARTED)
        g.pozeni()
        self.assertEqual(p.nalozeno, [])

    def test_napaka_potrdila_vrne_http_in_si_zapomni(self):
        p, g, s, v = _vezava()
        self.assertEqual(v.pred_nalaganjem("http://example.com/"), "https://example.com/")
        self.assertTrue(v.tls_failed(p, "https://example.com/", None, 0))   # True: brez strani napake
        g.pozeni()
        self.assertEqual(p.nalozeno, ["http://example.com/"])
        self.assertIn("example.com", s.povratki)
        p.uri = "http://example.com/"                     # povratek se nalaga - ne poskusi znova
        v.load_changed(p, _Dogodek.STARTED)
        g.pozeni()
        self.assertEqual(p.nalozeno, ["http://example.com/"])
        self.assertEqual(g.ure, {})

    def test_zavrnjena_povezava_vrne_http(self):
        p, g, s, v = _vezava()
        v.pred_nalaganjem("http://example.com/x")
        self.assertTrue(v.load_failed(p, _Dogodek.STARTED, "https://example.com/x", _Napaka()))
        g.pozeni()
        self.assertEqual(p.nalozeno, ["http://example.com/x"])

    def test_preklic_ni_napaka_https(self):
        p, g, s, v = _vezava()
        v.pred_nalaganjem("http://example.com/")
        self.assertFalse(v.load_failed(p, _Dogodek.STARTED, "https://example.com/", _Napaka(preklic=True)))
        self.assertEqual(s.povratki, set())

    def test_napaka_druge_strani_ni_nasa(self):
        p, g, s, v = _vezava()
        v.pred_nalaganjem("http://example.com/")
        self.assertFalse(v.load_failed(p, _Dogodek.STARTED, "https://drugo.si/", _Napaka()))
        self.assertFalse(v.tls_failed(p, "https://drugo.si/", None, 0))

    def test_rok_vrne_http(self):
        p, g, s, v = _vezava()
        v.pred_nalaganjem("http://pocasno.si/")
        (_ms, rok), = g.ure.values()
        rok()
        g.pozeni()
        self.assertEqual(p.ustavljen, 1)
        self.assertEqual(p.nalozeno, ["http://pocasno.si/"])
        self.assertIn("pocasno.si", s.povratki)

    def test_zanka_https_nazaj_na_http(self):
        p, g, s, v = _vezava()
        v.pred_nalaganjem("http://example.com/")
        p.uri = "https://example.com/"
        v.load_changed(p, _Dogodek.STARTED)
        p.uri = "http://example.com/"                     # streznik https preusmeri nazaj na http
        v.load_changed(p, _Dogodek.REDIRECTED)
        g.pozeni()
        self.assertEqual(p.nalozeno, [])                  # ostane http, brez novega poskusa (zanka)
        self.assertIn("example.com", s.povratki)
        self.assertEqual(g.ure, {})

    def test_preusmeritev_znotraj_https_in_napaka(self):
        p, g, s, v = _vezava()
        v.pred_nalaganjem("http://example.com/")
        p.uri = "https://www.example.com/"
        v.load_changed(p, _Dogodek.REDIRECTED)
        self.assertTrue(v.tls_failed(p, "https://www.example.com/", None, 0))
        g.pozeni()
        self.assertEqual(p.nalozeno, ["http://example.com/"])

    def test_uspeh_ustavi_rok(self):
        p, g, s, v = _vezava()
        v.pred_nalaganjem("http://example.com/")
        p.uri = "https://example.com/"
        v.load_changed(p, _Dogodek.STARTED)
        v.load_changed(p, _Dogodek.COMMITTED)
        self.assertEqual(g.ure, {})
        self.assertIsNone(v.poskus)
        self.assertEqual(s.povratki, set())


class TestTrajnostDiska(unittest.TestCase):
    def test_povratek_trajno_na_disk_in_obnova(self):
        """gostitelji brez https se zapomnijo TRAJNO na disku (config_dir, z rokom 30 dni, atomski zapis),
        naslednji obisk takoj na http brez poskusa in brez cakanja."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            s1 = H.Seja(config_dir=tmp)
            s1.povratek("brez-https.si")
            pot = os.path.join(tmp, "https_brez.json")
            self.assertTrue(os.path.exists(pot), "datoteka https_brez.json mora obstajati")
            # Nova seja prebere z diska
            s2 = H.Seja(config_dir=tmp)
            self.assertTrue(s2.je_brez_https("brez-https.si"))
            self.assertIsNone(s2.nadgradnja("http://brez-https.si/novica", "GET"),
                              "naslednji obisk takoj na http brez poskusa")

    def test_rok_30_dni_iztece(self):
        """Zapis starejsi od 30 dni se opusti in poskus https se ponovi."""
        import tempfile
        import time
        from core import shramba_json
        with tempfile.TemporaryDirectory() as tmp:
            pot = os.path.join(tmp, "https_brez.json")
            stari_cas = time.time() - (31 * 86400)
            shramba_json.zapisi_atomsko(pot, {"stara.si": stari_cas, "sveza.si": time.time()})
            s = H.Seja(config_dir=tmp)
            self.assertFalse(s.je_brez_https("stara.si"), "po 30 dneh mora rok poteči")
            self.assertTrue(s.je_brez_https("sveza.si"), "znotraj 30 dni ostane v veljavi")
            self.assertEqual(s.nadgradnja("http://stara.si/", "GET"), "https://stara.si/")
            self.assertIsNone(s.nadgradnja("http://sveza.si/", "GET"))

    def test_zavrnjena_povezava_in_tls_takojsen_povratek(self):
        """zavrnjena povezava / napaka TLS = takojsen povratek (brez roka cakanja); brez opozorilne strani;
        zapomni se trajno na disku."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p, g = _Pogled(), _GLib()
            s = H.Seja(config_dir=tmp)
            v = H.Pogled(p, s, W, g, lambda uri: "GET")

            # 1. TLS napaka
            v.pred_nalaganjem("http://tls-napaka.si/")
            self.assertTrue(g.ure, "rok mora biti nastavljen ob zacetku")
            self.assertTrue(v.tls_failed(p, "https://tls-napaka.si/", None, 0), "True ustavi signal (brez opozorilne strani)")
            self.assertEqual(g.ure, {}, "rok cakanja mora biti takoj ustavljen")
            g.pozeni()
            self.assertEqual(p.nalozeno, ["http://tls-napaka.si/"], "takoj nalozi http")
            self.assertTrue(s.je_brez_https("tls-napaka.si"), "shranjeno na disk")

            # 2. Zavrnjena povezava
            p.nalozeno.clear()
            v.pred_nalaganjem("http://zavrnjena.si/")
            self.assertTrue(v.load_failed(p, _Dogodek.STARTED, "https://zavrnjena.si/", _Napaka()),
                            "True ustavi signal (brez opozorilne strani)")
            self.assertEqual(g.ure, {}, "rok cakanja mora biti takoj ustavljen")
            g.pozeni()
            self.assertEqual(p.nalozeno, ["http://zavrnjena.si/"], "takoj nalozi http")
            self.assertTrue(s.je_brez_https("zavrnjena.si"), "shranjeno na disk")

    def test_os_splet_posreduje_config_dir(self):
        """core/os_splet.py VdelaniSplet._https_seja mora Seji podati config_dir."""
        with open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8") as f:
            vir = f.read()
        seja_blok = vir[vir.index("def _https_seja"):vir.index("def _https_pred")]
        self.assertIn("config_dir", seja_blok, "_https_seja mora uporabiti config_dir")


class TestSplet(unittest.TestCase):
    """Splet in Safeer Browser (oba uporabljata core/os_splet.VdelaniSplet) nadgradnjo res uporabljata."""

    def test_vezava_pred_napakami_in_v_odpri(self):
        with open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8") as f:
            vir = f.read()
        a = vir.index("https_nadgradnja.Pogled(")
        b = vir.index("NetworkErrorHandler(pogled")
        self.assertLess(a, b, "nadgradnja mora biti povezana PRED NetworkErrorHandler (signal ustavi z True)")
        odpri = vir[vir.index("    def odpri(self"):vir.index("    def _vnesi_naslov")]
        self.assertEqual(odpri.count("load_uri(self._https_pred(pogled, normalen))"), 2)
        with open(os.path.join(KOREN, "safeer_brskalnik.py"), encoding="utf-8") as f:
            self.assertIn("VdelaniSplet(", f.read())

    def test_modul_v_tovoru(self):
        with open(os.path.join(KOREN, "packaging", "install_os_payload.sh"), encoding="utf-8") as f:
            self.assertIn(" https_nadgradnja ", f.read())


if __name__ == "__main__":
    unittest.main()
