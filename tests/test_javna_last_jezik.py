"""Filmi v javni lasti: jezik in zvrst izbere ze Internet Archive (lastnik 10. 10. 2026: »V tem jeziku tukaj ni vsebine«
pri Filmi · Komedija · Anglescina - vecina filmov v javni lasti nima jezika v podatkih, zvrst se ni upostevala)."""
import os, sys, unittest
from urllib.parse import parse_qs, urlsplit
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import zakoniti_viri as z

DOC = {"identifier": "his_girl_friday", "title": "His Girl Friday", "year": "1940", "format": ["h.264"]}


class JavnaLastJezikZvrst(unittest.TestCase):
    def setUp(self):
        self.urlji = []
        self.v = z.ZakonitiViri()
        self.v._json = lambda url: self.urlji.append(url) or {"response": {"docs": [dict(DOC)]}}

    def q(self):
        return parse_qs(urlsplit(self.urlji[-1]).query)["q"][0]

    def test_brez_izbire_isti_pogoj_kot_prej(self):
        self.v.javna_last()
        self.assertEqual(self.q(), z.ARCHIVE_PD_QUERY)

    def test_jezik_gre_v_poizvedbo_in_zadetek_dobi_jezik(self):
        r = self.v.javna_last("", "en")
        self.assertIn('language:("eng" OR "english")', self.q())
        self.assertEqual(r[0]["jezik"], "en")

    def test_zvrst_gre_v_poizvedbo(self):
        self.v.javna_last("", "", "35")
        self.assertIn('subject:("comedy")', self.q())

    def test_neznana_zvrst_in_neveljaven_jezik_brez_pogoja(self):
        self.v.javna_last("", "xyz", "999")
        self.assertEqual(self.q(), z.ARCHIVE_PD_QUERY)

    def test_predpomnilnik_loci_jezik_in_zvrst(self):
        self.v.javna_last("", "en", "35"); self.v.javna_last("", "de", "35"); self.v.javna_last("", "en", "35")
        self.assertEqual(len(self.urlji), 2)

    def test_zvrsti_enake_kot_v_os_js(self):
        js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "os", "os.js"),
                  encoding="utf-8").read()
        for kljuc in z.ARCHIVE_ZVRSTI:
            self.assertIn('["%s", "katZanr_' % kljuc, js)


if __name__ == "__main__":
    unittest.main()
