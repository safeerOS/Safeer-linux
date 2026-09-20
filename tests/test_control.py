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
        self.assertEqual(dejanja, link_daljinec.DEJANJA_CONTROL + link_daljinec.DEJANJA_HOST)
        for d in (link_daljinec.DEJANJA_DATOTEKE + link_daljinec.DEJANJA_PROGRAMI
                  + link_daljinec.DEJANJA_ZASLON):
            self.assertNotIn(d, dejanja)
        self.assertEqual(i["data"]["keys"], [])
        self.assertTrue(i["data"]["version"])

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
        for razdelek in ("naprave", "daljinec", "poslji", "mape", "sync"):
            self.assertIn('data-razdelek="%s"' % razdelek, html)
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
