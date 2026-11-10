"""Ime naprave v seznamu Safeer Linka (assets/link/link.js): pokazemo ime, ki ga naprava pove; skrijemo samo nas ID.

Lastnik 10. 11. 2026: prenosnik je bil v seznamu na testnem racunalniku pod imenom »Zaslon«, ker je vzorec za tehnicni
ID ujel vsako ime z vezajem (ime gostitelja oblike beseda-Model-215-54)."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("node"), "ni node")
class ImeNaprave(unittest.TestCase):
    def _je_id(self, imena):
        js = (ROOT / "assets/link/link.js").read_text(encoding="utf-8")
        m = re.search(r"function jeTehnicniId\(ime\) \{.*?\n  \}", js, re.S)
        self.assertIsNotNone(m, "funkcija jeTehnicniId v link.js")
        koda = m.group(0) + "\nconsole.log(JSON.stringify(%s.map(jeTehnicniId)));" % json.dumps(imena)
        r = subprocess.run(["node", "-e", koda], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_ime_gostitelja_z_vezaji_ni_id(self):
        imena = ["uporabnik-Extensa-215-54", "moj-prenosnik", "safeer-test", "Dnevna-soba-TV", "PC-1234"]
        self.assertEqual(self._je_id(imena), [False] * len(imena))

    def test_nas_id_ostane_skrit(self):
        imena = ["n-96bfc3da3b52ea80-control", "n-50d2bd37cb42e8eb", "tv-0123456789abcdef", "N-F1D0F648EA4E5602"]
        self.assertEqual(self._je_id(imena), [True] * len(imena))

    def test_prijazno_ime_uporablja_isto_pravilo(self):
        js = (ROOT / "assets/link/link.js").read_text(encoding="utf-8")
        telo = re.search(r"function prijaznoIme\(naprava\) \{.*?\n  \}", js, re.S).group(0)
        self.assertIn("jeTehnicniId(ime)", telo)
        self.assertNotIn("[a-z0-9]+-[a-z0-9-]{4,}", telo)


if __name__ == "__main__":
    unittest.main()
