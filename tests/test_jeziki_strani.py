"""navigator.language ni »C« (core/jeziki_strani.py; JetStream Kotlin-compose-wasm, 17. 10. 2026)."""

import unittest

from core import jeziki_strani as js


class TestJezikiStrani(unittest.TestCase):
    def test_iz_seje(self):
        self.assertEqual(js.jeziki({"LANGUAGE": "sl", "LANG": "sl_SI.UTF-8"}), ["sl", "sl-SI", "en-US", "en"])
        self.assertEqual(js.jeziki({"LANG": "de_AT.UTF-8@euro"}), ["de-AT", "de", "en-US", "en"])

    def test_c_in_prazno_nikoli(self):
        for okolje in ({"LANG": "C"}, {"LANG": "POSIX", "LC_ALL": "C.UTF-8"}, {}):
            j = js.jeziki(okolje)
            self.assertEqual(j, ["en-US", "en"], okolje)
            self.assertNotIn("C", j)

    def test_nastavi_poklice_webkit(self):
        class K:
            def set_preferred_languages(self, j):
                self.j = j
        k = K()
        js.nastavi(k)
        self.assertTrue(k.j and "C" not in k.j)
        js.nastavi(object())              # WebKit brez te funkcije: brez napake


if __name__ == "__main__":
    unittest.main()
