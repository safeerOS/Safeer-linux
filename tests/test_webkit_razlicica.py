"""Tedenski preizkus pripetega WebKitGTK (tools/webkit_razlicica.py, pregled 14. 10. 2026) - brez omrezja."""
import importlib.util
import os
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("webkit_razlicica", os.path.join(KOREN, "tools", "webkit_razlicica.py"))
wr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wr)

SEZNAM = ('<a href="webkitgtk-2.52.3.tar.xz">x</a> <a href="webkitgtk-2.53.92.tar.xz">x</a> '
          '<a href="webkitgtk-2.54.1.tar.xz">x</a> <a href="webkitgtk-2.54.1.tar.xz.asc">x</a> %s')


class Razlicica(unittest.TestCase):
    def test_razvojne_ne_stejejo(self):
        self.assertEqual(wr.najnovejsa_stabilna(SEZNAM % '<a href="webkitgtk-2.55.1.tar.xz">'), (2, 54, 1))
        self.assertEqual(wr.najnovejsa_stabilna(SEZNAM % '<a href="webkitgtk-2.54.10.tar.xz">'), (2, 54, 10))
        self.assertIsNone(wr.najnovejsa_stabilna("brez izdaj"))

    def test_manifesti_so_pripeti(self):
        pripeto = wr.pripete()
        self.assertIn("webkitgtk6-safeer.yml", pripeto)
        self.assertTrue(all(r[1] % 2 == 0 for r in pripeto.values()), pripeto)

    def _izhod(self, html):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
            f.write(html)
        try:
            return wr.main(["--html", f.name])
        finally:
            os.unlink(f.name)

    def test_izhod(self):
        najvisja = max(wr.pripete().values())
        self.assertEqual(self._izhod('<a href="webkitgtk-%d.%d.%d.tar.xz">' % najvisja), 0)
        novejsa = (najvisja[0], najvisja[1], najvisja[2] + 1)
        self.assertEqual(self._izhod('<a href="webkitgtk-%d.%d.%d.tar.xz">' % novejsa), 1)
        self.assertEqual(self._izhod("404 Not Found"), 2)

    def test_tedenski_tek(self):
        wf = open(os.path.join(KOREN, ".github", "workflows", "webkit-razlicica.yml"), encoding="utf-8").read()
        for niz in ("schedule:", "cron:", "workflow_dispatch:", "python3 tools/webkit_razlicica.py"):
            self.assertIn(niz, wf)


if __name__ == "__main__":
    unittest.main()
