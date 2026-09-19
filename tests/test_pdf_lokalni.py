"""PDF z diska (file://) je dovoljena navigacija samo, ce datoteka obstaja in je PDF; druge lokalne datoteke ostanejo zaprte."""
import os, pathlib, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from safeer_mint import is_safe_web_url, je_lokalni_dokument  # noqa: E402


class PdfLokalni(unittest.TestCase):
    def test_politika(self):
        with tempfile.TemporaryDirectory() as d:
            pdf = pathlib.Path(d) / "Moj dokument.pdf"
            pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
            html = pathlib.Path(d) / "stran.html"
            html.write_text("<script>1</script>")
            self.assertTrue(je_lokalni_dokument(pdf.as_uri()))
            self.assertTrue(is_safe_web_url(pdf.as_uri()))
            self.assertFalse(is_safe_web_url(html.as_uri()))
            self.assertFalse(is_safe_web_url((pathlib.Path(d) / "ni.pdf").as_uri()))
            self.assertFalse(is_safe_web_url("file:///etc/passwd"))
            self.assertFalse(je_lokalni_dokument("https://primer.si/x.pdf"))


if __name__ == "__main__":
    unittest.main()
