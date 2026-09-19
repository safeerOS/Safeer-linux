"""blob: naslovi z izvorom strani (ali vgrajenega pregledovalnika PDF) so dovoljena navigacija -
WebKit jih z atributom download spremeni v prenos ("Shrani" v PDF, izvozi CSV na straneh)."""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from safeer_mint import is_safe_web_url  # noqa: E402


class BlobPrenos(unittest.TestCase):
    def test_dovoljeni(self):
        for u in ("blob:webkit-pdfjs-viewer://pdfjs/b48c8345-a4cd-4507-924d-dba818411e29",
                  "blob:https://primer.si/1234-5678",
                  "blob:http://localhost:8080/abc",
                  "BLOB:HTTPS://Primer.si/x"):
            self.assertTrue(is_safe_web_url(u), u)

    def test_prepovedani(self):
        for u in ("blob:", "blob:file:///etc/passwd", "blob:null/abc", "blob:javascript:alert(1)",
                  "blob:data:text/html,x", "javascript:alert(1)", "data:text/html,x"):
            self.assertFalse(is_safe_web_url(u), u)


if __name__ == "__main__":
    unittest.main()
