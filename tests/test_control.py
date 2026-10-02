"""Safeer Control (namizna aplikacija): paket, ukazi brez brskalnika in stran v nacinu Control."""
import os
import subprocess
import sys
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec  # noqa: E402


class ControlUkazi(unittest.TestCase):
    def _izvedi(self, dejanje, parametri=None, odpri=None):
        izidi = []
        link_daljinec.izvedi_control(dejanje, parametri or {}, odpri or (lambda u: None), izidi.append)
        self.assertEqual(len(izidi), 1)
        return izidi[0]

    def test_stanje(self):
        i = self._izvedi("status")
        self.assertTrue(i["ok"])
        self.assertEqual(i["data"]["app"], "safeer-control-linux")
        # Brez deljenih map, programov in zaslona Control ponudi le osnovna dejanja in podatke o
        # racunalniku. Seznama ne pisemo na roko - tako test ne pade ob vsakem novem dejanju, pove
        # pa tisto, kar je res pomembno: kar potrebuje uporabnikovo dovoljenje, brez njega ni na
        # voljo.
        dejanja = i["data"]["actions"]
        # Magnet povezave z drugih naprav odpre Safeer OS - samo, ce je na tem racunalniku namescen.
        self.assertEqual(dejanja, link_daljinec.DEJANJA_CONTROL + link_daljinec.DEJANJA_HOST
                         + (link_daljinec.DEJANJA_MAGNET if link_daljinec._safeer_os() else []))
        for d in (link_daljinec.DEJANJA_DATOTEKE + link_daljinec.DEJANJA_PROGRAMI
                  + link_daljinec.DEJANJA_ZASLON):
            self.assertNotIn(d, dejanja)
        self.assertEqual(i["data"]["keys"], [])
        self.assertTrue(i["data"]["version"])

    def test_magnet_odpre_safeer_os(self):
        from unittest import mock
        zagnani = []
        with mock.patch.object(link_daljinec, "_safeer_os", lambda: "/usr/bin/safeer-os"), \
                mock.patch("subprocess.Popen", lambda ukaz, **_k: zagnani.append(ukaz)):
            i = self._izvedi("magnet.open", {"uri": "magnet:?xt=urn:btih:" + "a" * 40 + "&dn=Film"})
            self.assertTrue(i["ok"])
            self.assertEqual(zagnani[-1][:2], ["/usr/bin/safeer-os", "--magnet-naprava"])
            # Karkoli drugega (ukaz, pot, spletni naslov) naprava ne more podtakniti.
            for slab in ("--help", "https://x.si", "magnet:?xt=urn:btih:abc; rm -rf ~", ""):
                self.assertFalse(self._izvedi("magnet.open", {"uri": slab})["ok"], slab)
            self.assertEqual(len(zagnani), 1)
        with mock.patch.object(link_daljinec, "_safeer_os", lambda: ""):
            self.assertEqual(self._izvedi("magnet.open", {"uri": "magnet:?xt=urn:btih:" + "a" * 40})["code"], "ni_safeer_os")

    def test_odpri_samo_http(self):
        odprti = []
        i = self._izvedi("open_url", {"url": "https://safeer.si/"}, odprti.append)
        self.assertTrue(i["ok"])
        self.assertEqual(odprti, ["https://safeer.si/"])
        i = self._izvedi("open_url", {"url": "file:///etc/passwd"}, odprti.append)
        self.assertFalse(i["ok"])
        self.assertEqual(len(odprti), 1)

    def test_kar_rabi_brskalnik_vrne_razumljivo_napako(self):
        for dejanje in ("key", "scroll", "screenshot", "restart", "clear_cache"):
            i = self._izvedi(dejanje, {"key": "ok"})
            self.assertFalse(i["ok"], dejanje)
            self.assertEqual(i["code"], "ni_v_ospredju")
        self.assertEqual(self._izvedi("nekaj")["code"], "neznano_dejanje")


class ControlPaket(unittest.TestCase):
    def test_payload_brez_brskalnika(self):
        with tempfile.TemporaryDirectory() as mapa:
            subprocess.run(["bash", os.path.join(KOREN, "packaging", "install_control_payload.sh"), mapa + "/usr"],
                           check=True, capture_output=True)
            lib = os.path.join(mapa, "usr", "lib", "safeer-control")
            for pot in ("safeer_control.py", "core/safeer_link.py", "core/link_hub.py", "core/link_tls.py",
                        "core/link_deljenje.py", "core/link_daljinec.py", "core/link_datoteke.py", "core/spake2.py",
                        "assets/link/index.html", "assets/link/link.js", "assets/link/daljinec.js",
                        "packaging/VERSION_CONTROL"):
                self.assertTrue(os.path.isfile(os.path.join(lib, pot)), pot)
            self.assertFalse(os.path.exists(os.path.join(lib, "safeer_mint.py")))
            self.assertFalse(os.path.exists(os.path.join(lib, "core", "adblock.py")))
            self.assertTrue(os.path.isfile(os.path.join(mapa, "usr", "bin", "safeer-control")))
            self.assertTrue(os.path.isfile(os.path.join(mapa, "usr", "share", "applications", "safeer-control.desktop")))
        # Control se predstavi s svojo razlicico, tudi brez GTK (izpis pred uvozom okna ni potreben: --version).
        v = open(os.path.join(KOREN, "packaging", "VERSION_CONTROL"), encoding="utf-8").read().strip()
        self.assertRegex(v, r"^\d+\.\d+\.\d+$")

    def test_stran_pozna_nacin_control(self):
        js = open(os.path.join(KOREN, "assets", "link", "link.js"), encoding="utf-8").read()
        self.assertIn("stanje.control = !!s.control", js)
        self.assertIn("function narisiControl()", js)
        for id_ in ("gumbZapri", "panelCast", "panelSync", "predvajalnik"):
            self.assertIn('pokazi("%s", false)' % id_, js)
        # Deljene mape za televizor: plosca samo v Controlu, besedila v vseh jezikih, most zna dodati/odstraniti.
        html = open(os.path.join(KOREN, "assets", "link", "index.html"), encoding="utf-8").read()
        self.assertRegex(html, r'id="panelMape"[^>]*\bhidden\b')
        # Samostojna aplikacija: levi meni z razdelki je v strani, a skrit (telefon in TV ga ne vidita);
        # razdelke vklopi samo Control (body.namizje), Safeer OS na televizorju je en klik.
        self.assertRegex(html, r'<nav class="stranski" id="stranskiMeni" hidden')
        for razdelek in ("naprave", "poslji", "sync"):
            self.assertIn('data-razdelek="%s"' % razdelek, html)
        for razdelek in ("daljinec", "mape"):
            self.assertNotIn('<button data-razdelek="%s"' % razdelek, html)
        self.assertRegex(html, r'<details[^>]+id="panelMape"[^>]+data-razdelek="naprave"[^>]*\bhidden\b')
        self.assertIn('if (ime === "daljinec" || ime === "mape") ime = "naprave"', js)
        self.assertIn('(stanje.seznanjen || stanje.vKrogu) && imaTelevizor()', js)
        self.assertIn("function narisiMeni()", js)
        self.assertIn('classList.add("namizje")', js)
        self.assertIn('id="gumbOdpriSafeerOs"', html)
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            blok = js.split("\n    %s: {\n" % jezik, 1)[1]
            for kljuc in ("mapeNaslov", "mapeOpis", "mapeDodaj", "mapePrazno", "mapeOdstrani", "mapeStandardne"):
                self.assertIn(kljuc + ":", blok.split("\n    },", 1)[0], (jezik, kljuc))
        self.assertIn("most.dodajDeljenoMapo()", js)
        self.assertIn("most.odstraniDeljenoMapo(i)", js)
        most = open(os.path.join(KOREN, "core", "safeer_link.py"), encoding="utf-8").read()
        self.assertIn("dodajDeljenoMapo: function", most)


if __name__ == "__main__":
    unittest.main()


class ControlSorodnik(unittest.TestCase):
    """Prevzem seznanitve od brskalnika: zahteva gre na /cast/pair/sibling z brskalnikovim zetonom."""

    def test_prevzem(self):
        try:
            import safeer_control as sc
        except ImportError as e:  # brez GTK/WebKita (npr. goli vsebnik) tega dela ni mogoce preizkusiti
            self.skipTest(f"GTK ni na voljo: {e}")
        from core import link_hub, link_tls
        with tempfile.TemporaryDirectory() as mapa:
            brskalnik = os.path.join(mapa, "brskalnik", "link.json")
            os.makedirs(os.path.dirname(brskalnik))
            with open(brskalnik, "w", encoding="utf-8") as d:
                d.write('{"hub_url": "wss://192.0.2.10:8990/cast/ws", "control_token": "saf_tv_brskalnik", "hub_fp": "AB:CD",'
                        ' "seznanitve": {"AB:CD": {"token": "saf_tv_brskalnik", "hub_url": "wss://192.0.2.10:8990/cast/ws"},'
                        ' "EF:01": {"token": "saf_tv_telefon", "hub_url": "wss://192.0.2.20:8990/cast/ws"}}}')
            klici = []

            def lazna_zahteva(url, telo=None, zeton=None, timeout=5.0, pripeti=None, metoda=None):
                klici.append((url, telo, zeton, pripeti))
                if "192.0.2.10" in url:
                    return 200, {"token": "saf_tv_control", "fp": "AB:CD"}, "AB:CD"
                return 0, {}, ""

            stara_mapa, stara_zahteva = link_hub.NASTAVITVE_MAPA, link_tls.zahteva
            link_hub.NASTAVITVE_MAPA = os.path.dirname(brskalnik)
            link_tls.zahteva = lazna_zahteva
            try:
                n = link_hub.Nastavitve(os.path.join(mapa, "control", "link.json"))
                self.assertTrue(sc.prevzemi_seznanitev_brskalnika(n, "pc-primer-control", "Safeer Control (primer)"))
                self.assertEqual(n.get("control_token"), "saf_tv_control")
                self.assertEqual(n.get("hub_fp"), "AB:CD")
                self.assertEqual(n.get("hub_url"), "wss://192.0.2.10:8990/cast/ws")
                self.assertEqual(n.get("seznanitve"), {"AB:CD": {"token": "saf_tv_control", "hub_url": "wss://192.0.2.10:8990/cast/ws"}})
                self.assertEqual(klici[0][0], "https://192.0.2.10:8990/cast/pair/sibling")
                self.assertEqual(klici[0][1], {"device_id": "pc-primer-control", "name": "Safeer Control (primer)"})
                self.assertEqual((klici[0][2], klici[0][3]), ("saf_tv_brskalnik", "AB:CD"))
                self.assertTrue(any("192.0.2.20" in k[0] for k in klici), "poskusi tudi druge Hube brskalnika")
                # Ze seznanjen Control brskalnika ne sprasuje vec.
                klici.clear()
                self.assertFalse(sc.prevzemi_seznanitev_brskalnika(n, "pc-primer-control", "Safeer Control (primer)"))
                self.assertEqual(klici, [])
            finally:
                link_hub.NASTAVITVE_MAPA, link_tls.zahteva = stara_mapa, stara_zahteva


class ControlOzadje(unittest.TestCase):
    """Tihi zagon: vnos za zagon ob prijavi in besedila pladnja."""

    def test_samozagon_in_besedila(self):
        try:
            import safeer_control as sc
        except ImportError as e:
            self.skipTest(f"GTK ni na voljo: {e}")
        with tempfile.TemporaryDirectory() as mapa:
            pot = os.path.join(mapa, "autostart", "safeer-control.desktop")
            stara = sc.SAMOZAGON_POT
            sc.SAMOZAGON_POT = pot
            try:
                self.assertFalse(sc.Samozagon.je_vklopljen())
                sc.Samozagon.nastavi(True)
                self.assertTrue(sc.Samozagon.je_vklopljen())
                vsebina = open(pot, encoding="utf-8").read()
                self.assertIn("[Desktop Entry]", vsebina)
                self.assertIn("--ozadje", vsebina)
                self.assertIn("X-GNOME-Autostart-enabled=true", vsebina)
                sc.Samozagon.nastavi(False)
                self.assertFalse(os.path.exists(pot))
                self.assertFalse(sc.Samozagon.je_vklopljen())
            finally:
                sc.SAMOZAGON_POT = stara
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            for kljuc in ("odpri", "samozagon", "koncaj", "povezan", "ni"):
                self.assertTrue(sc.besedilo(jezik, kljuc))
        self.assertEqual(sc.besedilo("xx", "koncaj"), sc.besedilo("en", "koncaj"))
        self.assertEqual(sc.besedilo(None, "odpri"), sc.besedilo("en", "odpri"))


class ControlJezik(unittest.TestCase):
    """Pladenj govori v jeziku seje, kadar Safeer Browser nima nastavljenega jezika."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("safeer_control_jezik", os.path.join(KOREN, "safeer_control.py"))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.prej = {k: os.environ.get(k) for k in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG", "XDG_CONFIG_HOME")}
        self.mapa = tempfile.mkdtemp()
        os.environ["XDG_CONFIG_HOME"] = self.mapa
        for k in ("LANGUAGE", "LC_ALL", "LC_MESSAGES"):
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self.prej.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_jezik_seje(self):
        os.environ["LANG"] = "sl_SI.UTF-8"
        n = self.m.Nastavitve(os.path.join(self.mapa, "control.json"))
        self.assertEqual(n.get("ui_language"), "sl")
        self.assertEqual(self.m.besedilo(n.get("ui_language"), "koncaj"), "Končaj")

    def test_nepodprt_jezik_pade_na_anglescino(self):
        os.environ["LANG"] = "pt_BR.UTF-8"
        n = self.m.Nastavitve(os.path.join(self.mapa, "control.json"))
        self.assertEqual(self.m.besedilo(n.get("ui_language"), "koncaj"), "Quit")


class ControlPredaja(unittest.TestCase):
    """D-Bus za Safeer OS: Predaja (vprasaj naprave), Prevzemi (igraj tu), Ponudi (poslji napravi) - z laznim Linkom."""

    def _app(self):
        try:
            import safeer_control as sc
        except ImportError as e:
            self.skipTest(f"GTK ni na voljo: {e}")
        from core import link_predvajanje

        class Link:
            def __init__(self):
                self.naprave = [{"id": "n-jaz-control", "ime": "Jaz", "zmoznosti": ["remote"]},
                                {"id": "n-tel", "ime": "Telefon", "zmoznosti": ["remote", "files"]},
                                {"id": "n-tv", "ime": "TV", "zmoznosti": ["remote"]},
                                {"id": "n-brez", "ime": "Brez", "zmoznosti": ["files"]}]
                self.ukazi = []
                self.odgovori = {}
                self.predvajanje = link_predvajanje.Predvajanje(lambda: self.stanje, lambda: True, None, None, lambda: True)
                self.stanje = {"stanje": "predvaja", "uri": "https://primer.si/film.mp4", "naslov": "Film", "vrsta": "video",
                               "pozicija": 61, "trajanje": 100}

            def _id(self):
                return "n-jaz-control"

            def _hub(self):
                return ""

            def ukaz_pocakaj(self, naprava, dejanje, parametri=None, cas=15.0):
                self.ukazi.append((naprava, dejanje, parametri))
                return self.odgovori.get((naprava, dejanje), {"ok": False, "koda": "cas"})

        import types
        # GObject razreda ne ustvarjamo (okno, D-Bus): metodo klicemo nad preprostim nadomestkom z istimi polji.
        app = types.SimpleNamespace(link=Link(), datoteke=None, sprejete=[])
        app.predaja_sprejmi = lambda: app.sprejete.append(app.link.predvajanje.vzemi_ponudbo())
        app._naprave_metoda = lambda metoda, a: sc.SafeerControl._naprave_metoda(app, metoda, a)
        return app

    def test_predaja_vprasa_vse_z_daljincem(self):
        app = self._app()
        app.link.odgovori[("n-tv", "play.state")] = {"ok": True, "data": {"shared": True, "playing": True, "is_playing": True, "position_ms": 754000,
                                                                          "duration_ms": 5400000, "item": {"id": "x", "naslov": "Sintel", "zvok": "https://a/b"}}}
        app.link.odgovori[("n-tel", "play.state")] = {"ok": True, "data": {"shared": True, "playing": False, "last": True, "position_ms": 1000,
                                                                           "duration_ms": 2000, "item": {"id": "y", "naslov": "Glasba", "zvok": "https://a/c"}}}
        r = app._naprave_metoda("Predaja", [])
        self.assertTrue(r["ok"])
        self.assertEqual([p["naprava"]["id"] for p in r["ponudbe"]], ["n-tv", "n-tel"])  # najprej, kar igra
        self.assertEqual(r["ponudbe"][0]["opis"], "Sintel (12:34)")
        self.assertTrue(r["ponudbe"][0]["igra"] and not r["ponudbe"][1]["igra"] and r["ponudbe"][1]["nazadnje"])
        vprasane = sorted(n for n, d, _ in app.link.ukazi if d == "play.state")
        self.assertEqual(vprasane, ["n-tel", "n-tv"])  # ne sebe in ne naprave brez daljinca

    def test_prevzemi_preda_safeer_os_in_po_zelji_ustavi_tam(self):
        import json
        app = self._app()
        podatki = {"item": {"id": "x", "naslov": "Sintel", "zvok": "https://a/b", "video": True}, "position_ms": 5000, "duration_ms": 9000,
                   "server": {"base_url": "https://192.168.0.5:4433", "fp": "ab", "token": "t"}}
        r = app._naprave_metoda("Prevzemi", ["n-tv", json.dumps(podatki), "1"])
        self.assertTrue(r["ok"])
        self.assertIn(("n-tv", "play.stop", {}), app.link.ukazi)
        # predaja_sprejmi gre prek GLib.idle_add: tu ga poklicemo sami
        app.predaja_sprejmi()
        self.assertEqual(app.sprejete[-1]["od_ime"], "TV")
        self.assertEqual(app.sprejete[-1]["server"]["token"], "t")
        r = app._naprave_metoda("Prevzemi", ["n-tv", "{}", "0"])
        self.assertFalse(r["ok"])

    def test_stikalo_predvajanje_za_naprave_iz_safeer_os(self):
        """Dejanje predvajanje-za-naprave (Safeer OS, poleg Zaupaj) zapise nastavitev in uskladi postavko v pladnju."""
        import safeer_control as sc
        import types
        shramba = {}
        klici = []
        app = types.SimpleNamespace(nastavitve=types.SimpleNamespace(set=lambda k, v: shramba.__setitem__(k, v),
                                                                     get=lambda k, d=None: shramba.get(k, d)),
                                    pladenj=types.SimpleNamespace(osvezi_predvajanje=lambda: klici.append("osvezi")))
        sc.SafeerControl.nastavi_predvajanje_za_naprave(app, False)
        self.assertEqual((shramba, klici), ({"predvajanje_za_naprave": False}, ["osvezi"]))
        app.pladenj = None
        sc.SafeerControl.nastavi_predvajanje_za_naprave(app, True)
        self.assertTrue(shramba["predvajanje_za_naprave"])

    def test_ponudi_poslje_play_offer_z_zetonom_za_cilj(self):
        app = self._app()
        app.link.odgovori[("n-tel", "play.offer")] = {"ok": True, "data": {"queued": True}}
        r = app._naprave_metoda("Ponudi", ["n-tel"])
        self.assertTrue(r["ok"])
        self.assertEqual(r["prikaz"], "")
        # Android brez dovoljenja za obvestila: ponudba caka, uporabnik naj tam odpre Safeer OS.
        app.link.odgovori[("n-tel", "play.offer")] = {"ok": True, "data": {"queued": True, "shown": "later"}}
        self.assertEqual(app._naprave_metoda("Ponudi", ["n-tel"]), {"ok": True, "prikaz": "later"})
        app.link.odgovori[("n-tel", "play.offer")] = {"ok": True, "data": {"queued": False, "reason": "izklopljeno"}}
        self.assertEqual(app._naprave_metoda("Ponudi", ["n-tel"])["koda"], "izklopljeno")
        naprava, dejanje, parametri = app.link.ukazi[-1]
        self.assertEqual((naprava, dejanje), ("n-tel", "play.offer"))
        self.assertEqual((parametri["item"]["naslov"], parametri["position_ms"], parametri["from"]), ("Film", 61000, "Jaz"))
        app.link.odgovori[("n-tv", "play.offer")] = {"ok": False, "koda": "neznano_dejanje"}
        self.assertEqual(app._naprave_metoda("Ponudi", ["n-tv"])["koda"], "stara")
        app.link.stanje = {"stanje": "ustavljeno"}
        self.assertEqual(app._naprave_metoda("Ponudi", ["n-tel"])["koda"], "ni_predvajanja")
