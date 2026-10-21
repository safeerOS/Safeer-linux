"""Vgrajeni libxml2.so.2 (paket .deb od 1.0.131) in sistemski vticniki GStreamer z drugim libxml2 ne smejo v isti
spletni proces (neodvisni pregled Gemini 1.0.131: navzkrizna vezava simbolov, sesutje)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core import zasebni_webkit as z  # noqa: E402


class RangiBrezXml(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.d, "wk", "lib"))
        self.nas = os.path.join(self.d, "wk", "lib", "libxml2.so.2")
        with open(self.nas, "wb") as f:
            f.write(b"nas libxml2 2.9.14")

    def _sistem(self, vsebina):
        p = os.path.join(self.d, "sistem-libxml2.so.2")
        with open(p, "wb") as f:
            f.write(vsebina)
        return p

    def test_brez_sistemskega_izklopi_xml_elemente(self):      # Mint 23 / Ubuntu 26.04 (samo libxml2.so.16)
        r = z.rangi_brez_xml(os.path.join(self.d, "wk"), "", os.path.join(self.d, "ni"))
        for e in ("hlsdemux2:NONE", "dashdemux2:NONE", "ttmlparse:NONE"):
            self.assertIn(e, r.split(","))
        self.assertNotIn("hlsdemux:NONE", r.split(","))          # HLS ostane (vticnik hls brez libxml2)

    def test_drug_sistemski_izklopi(self):                      # Debian 13 (libxml2 2.12) ali varnostna posodobitev
        self.assertIsNotNone(z.rangi_brez_xml(os.path.join(self.d, "wk"), "", self._sistem(b"sistemski 2.12")))

    def test_ista_datoteka_ne_spremeni(self):                   # Mint 22: isti libxml2 - en sam v procesu
        self.assertIsNone(z.rangi_brez_xml(os.path.join(self.d, "wk"), "", self._sistem(b"nas libxml2 2.9.14")))

    def test_brez_nasega_libxml2_ne_spremeni(self):
        os.remove(self.nas)
        self.assertIsNone(z.rangi_brez_xml(os.path.join(self.d, "wk"), "", os.path.join(self.d, "ni")))

    def test_obstojeci_rangi_ostanejo(self):
        r = z.rangi_brez_xml(os.path.join(self.d, "wk"), "vah264dec:MAX,hlsdemux2:PRIMARY", os.path.join(self.d, "ni"))
        deli = r.split(",")
        self.assertEqual(deli[:2], ["vah264dec:MAX", "hlsdemux2:PRIMARY"])   # uporabnikova izbira ostane
        self.assertNotIn("hlsdemux2:NONE", deli)

    def test_nastavi_zapise_spremenljivko(self):
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core", "zasebni_webkit.py"),
                   encoding="utf-8").read()
        telo = src[src.index("def nastavi("):src.index("#: Elementi GStreamer")]
        self.assertIn('"GST_PLUGIN_FEATURE_RANK"', telo)


class ZunanjiProgrami(unittest.TestCase):
    def test_zunanji_program_nima_nasih_rangov(self):
        nasi = ",".join(f"{e}:NONE" for e in z.XML_ELEMENTI)
        self.assertNotIn("GST_PLUGIN_FEATURE_RANK", z.okolje_za_zunanje({"GST_PLUGIN_FEATURE_RANK": nasi, "PATH": "/usr/bin"}))
        o = z.okolje_za_zunanje({"GST_PLUGIN_FEATURE_RANK": "vah264dec:MAX," + nasi, "PATH": "/usr/bin"})
        self.assertEqual(o["GST_PLUGIN_FEATURE_RANK"], "vah264dec:MAX")


if __name__ == "__main__":
    unittest.main()
