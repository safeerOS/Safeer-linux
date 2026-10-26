"""Lastnik 26. 10. 2026 (NALOGA 33, »shrani in pozabi«): uporabnik vira oziroma toka nikoli ne izbira - Safeer sam izbere
najboljsega, nedosegljivega zamenja naslednji. V vmesniku in jedru ni poti za rocno izbiro razlicice ali vgrajenega vira
(tudi ne zapomnjene izbire), nekdanja izbira se ob zagonu pozabi. Skupna koda velja tudi za Windows."""
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from core import os_katalog as K
from core import os_vgrajeni_viri as V

KOREN = Path(__file__).resolve().parent.parent
PREPOVEDANO = {
    "assets/os/os.js": ("mediaIzberiRazlicico", "mediaRazlicice", "mediaVgrajenaIzbira", "narisiRazlicice",
                        "vrsticaRazlicice", "razlViri", "razlIzbrana"),
    "assets/os/besedila.js": ('"razlNaslov"', '"razlViri"', '"razlIzbrana"', '"razlPrivzeta"'),
    "assets/os/katalog.css": ("kat-razlicic",),
    "core/os_katalog.py": ("mediaIzberiRazlicico", "mediaRazlicice", "mediaVgrajenaIzbira", "_izberi_razlicico",
                           "_vgr_izbira", "uporabi_izbiro"),
    "core/os_media.py": ("def izberi_razlicico", "def uporabi_izbiro", "def razlicice_naslova", "izbrana_razlicica"),
    "core/os_vgrajeni_viri.py": ("def zapomni_izbiro", "izbira: str"),
}


class BrezRocneIzbire(unittest.TestCase):
    def test_ni_poti_za_rocno_izbiro(self):
        for pot, nizi in PREPOVEDANO.items():
            besedilo = (KOREN / pot).read_text(encoding="utf-8")
            for niz in nizi:
                self.assertNotIn(niz, besedilo, "%s: %s" % (pot, niz))

    def test_seznam_razlicic_ne_klice_izbire(self):
        # Vse oblike klica mostu (klic("...", ...), klic('...')) za izbiro razlicice ali vira.
        js = (KOREN / "assets/os/os.js").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"""klic\(\s*["'](mediaIzberi\w*|mediaVgrajenaIzbira)""", js))

    def test_vgrajeni_viri_samodejno_ob_ni_toka(self):
        js = (KOREN / "assets/os/os.js").read_text(encoding="utf-8")
        i = js.index('if (item.napaka_koda === "ni_toka")')
        self.assertIn("vgrSamodejno(item)", js[i:i + 400])

    def test_nekdanja_izbira_vgrajenega_vira_se_ob_zagonu_pozabi(self):
        mapa = tempfile.mkdtemp()
        with open(os.path.join(mapa, "nastavitve.json"), "w", encoding="utf-8") as d:
            json.dump({V.KLJUC_IZBIRE: {"imdb:tt0111161": "abc"}, "media_watch_country": "SI"}, d)
        K.Katalog(mapa, lambda *_: None, lambda f: f(), *(lambda *a, **k: True,) * 4)
        d = json.loads(Path(mapa, "nastavitve.json").read_text(encoding="utf-8"))
        self.assertNotIn(V.KLJUC_IZBIRE, d)
        self.assertEqual(d.get("media_watch_country"), "SI")          # ostale nastavitve ostanejo


if __name__ == "__main__":
    unittest.main()
