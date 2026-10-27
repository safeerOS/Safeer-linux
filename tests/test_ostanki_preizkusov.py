"""Lastnik 27. 10. 2026: Splet je ob vsakem zagonu javil »Strani trenutno ni mogoce odpreti« (g-io-error-quark 39).

Vzrok (izmerjeno s pravim VdelaniSplet in kopijo lastnikovih nastavitev, tudi na testnem PC s 1.0.132): preizkusi pred
izolacijo okolja (25. 10.) so v pravi ~/.config/safeer-mint/settings.json zapisali lasten posrednik http://127.0.0.1:9,
izklop DNS in EasyList ter dovoljenje za klepet.primer.invalid. Preizkus preveri (1) ciscenje teh vrednosti ob nalaganju
nastavitev in (2) stran napake, ki pove, da lasten posrednik ne sprejme povezave.
"""
import json
import os
import tempfile
import unittest

from gi.repository import Gio, GLib

from core import config as _config
from core.network_errors import NetworkErrorHandler, error_html, napaka_posrednika

ONESNAZENO = {
    "doh_enabled": False, "doh_provider": "quad9", "secure_proxy_mode": "custom",
    "secure_proxy_url": "http://127.0.0.1:9", "easylist_enabled": False,
    "dovoljenja_strani": {"klepet.primer.invalid": {"obvestila": "dovoli"}, "primer.si": {"obvestila": "dovoli"}},
    "dns_scit_selitev": True,
}


def _nalozi(vsebina):
    mapa = tempfile.mkdtemp(prefix="ostanki-")
    with open(os.path.join(mapa, "settings.json"), "w", encoding="utf-8") as f:
        json.dump(vsebina, f)
    return mapa, _config.ConfigManager(config_dir=mapa)


class Ciscenje(unittest.TestCase):
    def test_onesnazene_nastavitve_dobijo_privzete(self):
        mapa, c = _nalozi(ONESNAZENO)
        self.assertEqual(c.get("secure_proxy_mode"), "disabled")
        self.assertTrue(c.get("doh_enabled"))
        self.assertEqual(c.get("doh_provider"), _config.DEFAULT_SETTINGS["doh_provider"])
        self.assertTrue(c.get("easylist_enabled"))
        self.assertEqual(c.get("dovoljenja_strani"), {"primer.si": {"obvestila": "dovoli"}})
        # Zapisano na disk (drug proces jih prebere ociscene) in kopija pred ciscenjem za rocno obnovo.
        with open(os.path.join(mapa, "settings.json"), encoding="utf-8") as f:
            disk = json.load(f)
        self.assertEqual(disk["secure_proxy_mode"], "disabled")
        with open(os.path.join(mapa, "settings.json.pred-ciscenjem-preizkusov"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["secure_proxy_url"], "http://127.0.0.1:9")

    def test_pravi_lasten_posrednik_ostane(self):
        _m, c = _nalozi(dict(ONESNAZENO, secure_proxy_url="http://127.0.0.1:8118"))
        self.assertEqual(c.get("secure_proxy_mode"), "custom")
        self.assertEqual(c.get("secure_proxy_url"), "http://127.0.0.1:8118")
        # Brez obeh sledi preizkusov je izklop DNS in EasyList morda uporabnikova izbira - ostane.
        self.assertFalse(c.get("doh_enabled"))
        self.assertFalse(c.get("easylist_enabled"))
        self.assertNotIn("klepet.primer.invalid", c.get("dovoljenja_strani"))

    def test_posrednik_9_na_drugem_gostitelju_ni_sled(self):
        _m, c = _nalozi(dict(ONESNAZENO, secure_proxy_url="http://10.0.0.5:9", dovoljenja_strani={}))
        self.assertEqual(c.get("secure_proxy_url"), "http://10.0.0.5:9")

    def test_ciste_nastavitve_niso_spremenjene(self):
        cisto = {"doh_enabled": False, "secure_proxy_mode": "disabled", "dns_scit_selitev": True}
        mapa, c = _nalozi(cisto)
        self.assertFalse(c.get("doh_enabled"))
        self.assertFalse(os.path.exists(os.path.join(mapa, "settings.json.pred-ciscenjem-preizkusov")))


class Enkrat(unittest.TestCase):
    """CI 40474119558: ciscenje ob VSAKEM nalaganju je preizkusu Sporocil pobrisalo namerne nastavitve (zaprt posrednik 9
    brez omrezja, dovoljenje za klepet.primer.invalid) - obvestilo ni prislo. Ciscenje velja samo enkrat, za datoteko stare
    razlicice (brez oznake ostanki_preizkusov_pregledani)."""

    def test_namerne_nastavitve_v_svezi_mapi_ostanejo(self):
        mapa = tempfile.mkdtemp(prefix="ostanki-")
        c = _config.ConfigManager(config_dir=mapa)          # kot setUpClass v test_kanali_sporocil
        c.set("secure_proxy_mode", "custom")
        c.set("secure_proxy_url", "http://127.0.0.1:9")
        c.set("dovoljenja_strani", {"klepet.primer.invalid": {"obvestila": "dovoli"}})
        d = _config.ConfigManager(config_dir=mapa)          # drugo nalaganje (drug del kode, drug proces)
        self.assertEqual(d.get("secure_proxy_url"), "http://127.0.0.1:9")
        self.assertEqual(d.get("secure_proxy_mode"), "custom")
        self.assertIn("klepet.primer.invalid", d.get("dovoljenja_strani"))

    def test_po_ciscenju_ponovno_nastavljeno_ostane(self):
        mapa, c = _nalozi(ONESNAZENO)                       # stara razlicica: enkrat pocisceno
        self.assertEqual(c.get("secure_proxy_mode"), "disabled")
        c.set("secure_proxy_mode", "custom")
        c.set("secure_proxy_url", "http://127.0.0.1:9")
        d = _config.ConfigManager(config_dir=mapa)
        self.assertEqual(d.get("secure_proxy_url"), "http://127.0.0.1:9")

    def test_datoteka_z_oznako_se_ne_cisti(self):
        _m, c = _nalozi(dict(ONESNAZENO, ostanki_preizkusov_pregledani=True))
        self.assertEqual(c.get("secure_proxy_mode"), "custom")
        self.assertFalse(c.get("doh_enabled"))


class StranNapake(unittest.TestCase):
    def test_zavrnjen_posrednik_je_napaka_posrednika(self):
        e = GLib.Error.new_literal(Gio.io_error_quark(), "Could not connect to proxy server 127.0.0.1: Connection refused",
                                   Gio.IOErrorEnum.CONNECTION_REFUSED)
        self.assertTrue(napaka_posrednika(e))
        tls = GLib.Error.new_literal(Gio.tls_error_quark(), "EOF", Gio.TlsError.EOF)
        self.assertFalse(napaka_posrednika(tls))

    def test_stran_pove_posrednik_brez_gesla(self):
        h = error_html("https://www.google.com/", "GET", jezik="sl", posrednik="http://uporabnik:geslo@127.0.0.1:9")
        self.assertIn("lasten posrednik http://127.0.0.1:9", h)
        self.assertNotIn("geslo", h)
        self.assertNotIn("lasten posrednik", error_html("https://www.google.com/", "GET", jezik="sl"))

    def test_upravljalnik_poda_posrednik_strani(self):
        class Pogled:
            def __init__(self): self.html = ""
            def connect(self, *a): pass
            def get_uri(self): return "about:blank"
            def load_alternate_html(self, h, *_a): self.html = h
        from core.network_errors import WebKit2
        p = Pogled()
        h = NetworkErrorHandler(p, "sl", posrednik=lambda: "http://127.0.0.1:9")
        e = GLib.Error.new_literal(Gio.io_error_quark(), "refused", Gio.IOErrorEnum.CONNECTION_REFUSED)
        h.retried["https://www.google.com/"] = 9          # brez samodejnih ponovitev: takoj stran napake
        h.requests["https://www.google.com/"] = "GET"
        self.assertTrue(h.load_failed(p, WebKit2.LoadEvent.STARTED, "https://www.google.com/", e))
        self.assertIn("127.0.0.1:9", p.html)


if __name__ == "__main__":
    unittest.main()
