"""»Prikazi izvirnik«: slike v pismu ne smejo biti sirse od okna (testni PC 15. 10. 2026)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class SirinaSlik(unittest.TestCase):
    def test_slike_in_tabele_omejene(self):
        from core import predogled_datotek as p
        stran, _ = p.html_pisma('<p>x</p><img src="cid:a" width="3000"><table width="2400"><tr><td>t</td></tr></table>',
                                {"a": "data:image/png;base64,AAAA"})
        self.assertIn(".okvir img, .okvir video { max-width: 100% !important; height: auto !important; }", stran)
        self.assertIn(".okvir table { max-width: 100% !important; }", stran)
        self.assertIn('<div class="okvir">', stran)


if __name__ == "__main__":
    unittest.main()
