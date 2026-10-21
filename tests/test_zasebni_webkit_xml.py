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
        self.wk = os.path.join(self.d, "wk")
        os.makedirs(os.path.join(self.wk, "lib"))
        self.nas = os.path.join(self.wk, "lib", "libxml2.so.2")
        with open(self.nas, "wb") as f:
            # Vgrajena knjiznica ima zaradi patchelf --set-rpath '$ORIGIN' drugacen SHA-256 kot sistemska
            f.write(b"nas libxml2 s patchelf rpath")
        self.doc_dir = os.path.join(self.wk, "share", "doc", "vgrajene", "libxml2")
        os.makedirs(self.doc_dir)
        self.razlicica_pot = os.path.join(self.doc_dir, "razlicica")
        with open(self.razlicica_pot, "w", encoding="utf-8") as f:
            f.write("libxml2.so.2.9.14\n")

    def _sistem(self, ciljno_ime: str, vsebina: bytes = b"sistemski libxml2"):
        p = os.path.join(self.d, ciljno_ime)
        with open(p, "wb") as f:
            f.write(vsebina)
        povezava = os.path.join(self.d, "sistem-libxml2.so.2")
        if os.path.islink(povezava) or os.path.exists(povezava):
            os.remove(povezava)
        os.symlink(ciljno_ime, povezava)
        return povezava

    def test_ista_razlicica_brez_izklopa(self):
        # Linux Mint 22: sistemski libxml2.so.2 kaze na libxml2.so.2.9.14 (enaka razlicica kot vgrajena),
        # a ima drugacen SHA-256 (patchelf). Vticniki se NE smejo izklopiti (vrne None).
        sistemski = self._sistem("libxml2.so.2.9.14", b"druga vsebina od nase")
        self.assertIsNone(z.rangi_brez_xml(self.wk, "", sistemski))

    def test_druga_razlicica_izklop(self):
        # Debian 13 / posodobitev (libxml2.so.2.12.8 namesto 2.9.14) -> izklop.
        sistemski = self._sistem("libxml2.so.2.12.8")
        self.assertIsNotNone(z.rangi_brez_xml(self.wk, "", sistemski))

    def test_manjka_sistemski_izklop(self):
        # Ubuntu 26.04 / Mint 23 (sistemski libxml2.so.2 ne obstaja, je samo .so.16) -> izklop.
        r = z.rangi_brez_xml(self.wk, "", os.path.join(self.d, "ni"))
        self.assertIsNotNone(r)
        for e in ("hlsdemux2:NONE", "dashdemux2:NONE", "ttmlparse:NONE"):
            self.assertIn(e, r.split(","))
        self.assertNotIn("hlsdemux:NONE", r.split(","))          # HLS ostane (vticnik hls brez libxml2)

    def test_nedoloceno_izklop(self):
        # Ce datoteka razlicica manjka ali je prazna -> izklop (varna stran).
        os.remove(self.razlicica_pot)
        sistemski = self._sistem("libxml2.so.2.9.14")
        self.assertIsNotNone(z.rangi_brez_xml(self.wk, "", sistemski))

    def test_nedoloceno_prazna_razlicica_izklop(self):
        with open(self.razlicica_pot, "w", encoding="utf-8") as f:
            f.write("   \n")
        sistemski = self._sistem("libxml2.so.2.9.14")
        self.assertIsNotNone(z.rangi_brez_xml(self.wk, "", sistemski))

    def test_brez_nasega_libxml2_ne_spremeni(self):
        os.remove(self.nas)
        self.assertIsNone(z.rangi_brez_xml(self.wk, "", os.path.join(self.d, "ni")))

    def test_obstojeci_rangi_ostanejo(self):
        r = z.rangi_brez_xml(self.wk, "vah264dec:MAX,hlsdemux2:PRIMARY", os.path.join(self.d, "ni"))
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
