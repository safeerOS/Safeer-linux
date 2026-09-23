import unittest

from core import os_spletne


class SpletneAplikacije(unittest.TestCase):
    def test_isti_vir_se_shrani_samo_enkrat(self):
        self.assertEqual(
            os_spletne.pocisti([
                {"ime": "Prvi", "url": "HTTPS://Example.COM/filmi/"},
                {"ime": "Drugi", "url": "https://example.com/filmi#zacetek"},
            ]),
            [{"ime": "Prvi", "url": "https://example.com/filmi"}],
        )

    def test_razlicni_poti_iste_domene_ostanejo(self):
        self.assertEqual(len(os_spletne.pocisti([
            {"ime": "Video", "url": "https://example.com/video"},
            {"ime": "Glasba", "url": "https://example.com/glasba"},
        ])), 2)

    def test_dovoljena_sta_samo_http_in_https(self):
        self.assertEqual(os_spletne.pocisti([
            {"ime": "Datoteka", "url": "file:///tmp/video"},
            {"ime": "Skript", "url": "javascript:alert(1)"},
            {"ime": "Krajevni vir", "url": "http://192.168.0.20:8096/"},
        ]), [{"ime": "Krajevni vir", "url": "http://192.168.0.20:8096"}])


if __name__ == "__main__":
    unittest.main()
