"""Vsili temno (Dark Reader): nespremenjena skripta, nacini, izjeme in povezava v Splet ter paket."""
import hashlib
import unittest
from pathlib import Path

from core import splet_temno as T

KOREN = Path(__file__).resolve().parents[1]


class Skripta(unittest.TestCase):
    def test_kontrolna_vsota_in_licenca(self):
        d = (KOREN / "core" / "darkreader" / "darkreader.js").read_bytes()
        self.assertEqual(hashlib.sha256(d).hexdigest(), T.SHA256)
        self.assertIn(b"Dark Reader v" + T.RAZLICICA.encode(), d[:200])
        self.assertIn("MIT License", (KOREN / "core" / "darkreader" / "LICENSE").read_text(encoding="utf-8"))

    def test_koda_vsebuje_krmilnik(self):
        T._koda = None
        k = T.koda(str(KOREN / "core"))
        self.assertTrue(k and k.endswith(T.KRMILNIK))

    def test_spremenjena_skripta_se_ne_izvede(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as m:
            os.makedirs(os.path.join(m, "darkreader"))
            with open(os.path.join(m, "darkreader", "darkreader.js"), "w") as d:
                d.write("alert(1)")
            T._koda = None
            try:
                self.assertIsNone(T.koda(m))
            finally:
                T._koda = None


class Nacini(unittest.TestCase):
    def test_dejaven(self):
        self.assertFalse(T.dejaven("izklop", True))
        self.assertTrue(T.dejaven("samodejno", True))
        self.assertFalse(T.dejaven("samodejno", False))
        self.assertTrue(T.dejaven("vedno", False))
        self.assertEqual(T.dejaven("neznano", True), T.dejaven(T.PRIVZETO, True))

    def test_izjeme_in_gostitelj(self):
        self.assertEqual(T.gostitelj("https://www.Example.com/pot?x=1"), "example.com")
        v = T.vzorci_izjem(["example.com", "a/b", "*.zlo", ""])
        self.assertIn("*://example.com/*", v)
        self.assertIn("*://*.example.com/*", v)
        self.assertIn("file://*", v)
        self.assertFalse(any("a/b" in x or "zlo" in x for x in v))

    def test_besedila_vseh_jezikov(self):
        for j in ("sl", "en", "de", "es", "fr", "it"):
            self.assertEqual(set(T.BESEDILA[j]), set(T.BESEDILA["en"]), j)


class Povezano(unittest.TestCase):
    def test_splet_namesti_in_osvezi(self):
        s = (KOREN / "core" / "os_splet.py").read_text(encoding="utf-8")
        self.assertIn("self._temno_skripte[pogled] = self._temno_namesti(upravitelj)", s)
        self.assertIn('notify::gtk-application-prefer-dark-theme', s)
        self.assertIn("self._temno_preklopi_stran", s)

    def test_paket_vsebuje_skripto(self):
        s = (KOREN / "packaging" / "install_os_payload.sh").read_text(encoding="utf-8")
        self.assertIn("core/darkreader/darkreader.js", s)
        self.assertIn(" splet_temno ", s)


if __name__ == "__main__":
    unittest.main()


class AkcijaSplet(unittest.TestCase):
    def test_akcija_splet_samo_http(self):
        s = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
        self.assertIn('Gio.SimpleAction.new("splet", GLib.VariantType.new("s"))', s)
        i = s.index("def _splet_od_drugod")
        self.assertIn('startswith(("http://", "https://"))', s[i:i + 400])
