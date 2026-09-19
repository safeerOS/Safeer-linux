"""Daljinec Safeer Controla na Linuxu (core/link_daljinec.py) brez GTK: izidi in sporocila."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import link_daljinec  # noqa: E402


class LazniWebView:
    def __init__(self):
        self.js = []
        self.nazaj = True
        self.uri = "https://safeer.si/"
        self.naslov = "Safeer"
        self.osvezen = False

    def can_go_back(self):
        return self.nazaj

    def go_back(self):
        self.js.append("go_back")

    def can_go_forward(self):
        return False

    def reload(self):
        self.osvezen = True

    def run_javascript(self, js, *_):
        self.js.append(js)

    def get_uri(self):
        return self.uri

    def get_title(self):
        return self.naslov


class LazniBrskalnik:
    def __init__(self):
        self.wv = LazniWebView()
        self.domov = 0
        self.odprto = []

    def get_active_webview(self):
        return self.wv

    def load_homepage(self):
        self.domov += 1


class TestLinkDaljinec(unittest.TestCase):
    def setUp(self):
        self.app = LazniBrskalnik()
        self.izidi = []

    def izvedi(self, dejanje, parametri=None):
        link_daljinec.izvedi(self.app, dejanje, parametri or {}, self.app.odprto.append, self.izidi.append)
        self.assertEqual(len(self.izidi), 1, "izid mora priti natanko enkrat")
        return self.izidi[0]

    def test_neznano_dejanje(self):
        izid = self.izvedi("explode")
        self.assertFalse(izid["ok"])
        self.assertIn("Neznano dejanje", izid["message"])

    def test_tipke(self):
        self.assertTrue(self.izvedi("key", {"key": "back"})["ok"])
        self.assertIn("go_back", self.app.wv.js)
        self.izidi.clear()
        self.assertTrue(self.izvedi("key", {"key": "home"})["ok"])
        self.assertEqual(self.app.domov, 1)
        self.izidi.clear()
        self.assertTrue(self.izvedi("key", {"key": "reload"})["ok"])
        self.assertTrue(self.app.wv.osvezen)
        self.izidi.clear()
        self.assertTrue(self.izvedi("key", {"key": "play_pause"})["ok"])
        self.assertTrue(any("v.play()" in js for js in self.app.wv.js))
        self.izidi.clear()
        izid = self.izvedi("key", {"key": "ok"})
        self.assertFalse(izid["ok"])  # D-pada na racunalniku ni

    def test_drsenje(self):
        self.assertTrue(self.izvedi("scroll", {"direction": "down"})["ok"])
        self.assertTrue(any("scrollBy" in js for js in self.app.wv.js))
        self.izidi.clear()
        self.assertFalse(self.izvedi("scroll", {"direction": "sideways"})["ok"])

    def test_odpri_stran(self):
        self.assertTrue(self.izvedi("open_url", {"url": "https://example.org/x"})["ok"])
        self.assertEqual(self.app.odprto, ["https://example.org/x"])
        self.izidi.clear()
        self.assertFalse(self.izvedi("open_url", {"url": "javascript:alert(1)"})["ok"])
        self.assertEqual(len(self.app.odprto), 1)
        self.izidi.clear()
        self.assertTrue(self.izvedi("open_url", {"url": "home"})["ok"])
        self.assertEqual(self.app.domov, 1)

    def test_stanje(self):
        izid = self.izvedi("status")
        self.assertTrue(izid["ok"])
        self.assertEqual(izid["data"]["url"], "https://safeer.si/")
        self.assertIn("screenshot", izid["data"]["actions"])
        self.assertIn("back", izid["data"]["keys"])

    def test_sporocilo_izida(self):
        s = link_daljinec.sporocilo_izida("pc1", "u1", "key", link_daljinec.izid(True, "Tipka"))
        self.assertEqual(s["type"], "control.result")
        self.assertEqual(s["target"], "pc1")
        self.assertEqual(s["ref_id"], "u1")
        self.assertEqual(s["payload"]["action"], "key")
        self.assertTrue(s["payload"]["ok"])
        json.dumps(s)  # mora biti serializabilno

    def test_glasnost_brez_pactl(self):
        stara = link_daljinec.shutil.which
        link_daljinec.shutil.which = lambda _: None
        try:
            izid = self.izvedi("volume", {"direction": "up"})
        finally:
            link_daljinec.shutil.which = stara
        self.assertFalse(izid["ok"])


if __name__ == "__main__":
    unittest.main()
