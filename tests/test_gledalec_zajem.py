"""Gledalec zaslona na namizju, ko zajem na drugem racunalniku pade (core/link_zaslon.ZajemPada; v seji obvestilo
{"konec": "zajem", "razlog": ...}, ob zacetku odgovor s kodo »zajem_pada«): prej je uporabnik videl samo besedo »zajem«
oziroma tehnicni razlog (izhod_234). Zdaj stavek v jeziku uporabnika (sl, en, de, es, fr, it), kaj lahko naredi.

Besedila in izbira so v core/link_gledalec (brez GTK, tece povsod); kako ju uporabi Safeer Control, preverja
tests/test_gledalec_zajem_control.py (rabi GTK in nas WebKit)."""
import ast
import os
import re
import unittest

from core import link_gledalec

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JEZIKI = ("sl", "en", "de", "es", "fr", "it")
# Besede, ki uporabniku nic ne povedo (oznake protokola in razlogi iz dnevnika).
TEHNICNO = re.compile(r"(\bzajem\b|izhod_\d+|grim|portal|pipewire|x11|wayland|gstreamer|razlog|zajem_pada|\(\w+_\d+\))",
                      re.I)


class Besedilo(unittest.TestCase):
    def test_vsi_jeziki_stavek_brez_tehnicnih_besed(self):
        stavki = {}
        for j in JEZIKI:
            s = link_gledalec.sporocilo_konca(j, "zajem")
            self.assertNotEqual(s, "zajem", j)
            self.assertGreater(len(s), 60, (j, s))                    # stavek, ne oznaka
            self.assertIsNone(TEHNICNO.search(s), (j, s))
            stavki[j] = s
        self.assertEqual(len(set(stavki.values())), len(JEZIKI))     # vsak jezik svoje, ne anglescina povsod
        # Kaj lahko naredi: prizgi in odkleni zaslon tam, poskusi znova.
        for j, besede in (("sl", ("odkleni", "poskusi znova")), ("en", ("unlock", "try again")),
                          ("de", ("entsperre", "erneut")), ("es", ("desbloquea", "vuelve a intentarlo")),
                          ("fr", ("déverrouille", "réessaie")), ("it", ("sblocca", "riprova"))):
            for b in besede:
                self.assertIn(b, stavki[j], j)

    def test_neznan_jezik_anglesko(self):
        self.assertEqual(link_gledalec.sporocilo_konca("pt-BR", "zajem"), link_gledalec.sporocilo_konca("en", "zajem"))
        self.assertEqual(link_gledalec.sporocilo_konca(None, "zajem"), link_gledalec.sporocilo_konca("en", "zajem"))

    def test_sporocilo_naprave_ima_prednost_dostop_in_neznano(self):
        self.assertEqual(link_gledalec.sporocilo_konca("sl", "zajem", "Zaslon zdaj gleda tablica."),
                         "Zaslon zdaj gleda tablica.")
        self.assertIn("ožjem krogu", link_gledalec.sporocilo_konca("sl", "dostop"))
        self.assertEqual(link_gledalec.sporocilo_konca("sl", "prevzeto"), "prevzeto")
        self.assertEqual(link_gledalec.sporocilo_konca("sl", None), "")


def _funkcija(drevo, razred, ime):
    for r in ast.walk(drevo):
        if isinstance(r, ast.ClassDef) and r.name == razred:
            for f in r.body:
                if isinstance(f, ast.FunctionDef) and f.name == ime:
                    return f
    raise AssertionError("%s.%s ni najdena" % (razred, ime))


class UporabaVControlu(unittest.TestCase):
    """Brez GTK (lokalno) samo staticno: obe poti v safeer_control.py gresta skozi sporocilo_konca. Vedenje preveri
    tests/test_gledalec_zajem_control.py v poslu z nasim WebKitom."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(KOREN, "safeer_control.py"), encoding="utf-8") as f:
            cls.drevo = ast.parse(f.read())

    def _klici(self, f):
        return [k for k in ast.walk(f) if isinstance(k, ast.Call) and getattr(k.func, "id", "") == "sporocilo_konca"]

    def test_gledalec_v_seji(self):
        self.assertTrue(self._klici(_funkcija(self.drevo, "OddaljeniGledalec", "_zacni")))

    def test_zacetek_seje_zajem_pada(self):
        f = _funkcija(self.drevo, "SafeerControl", "_nova_oddaljena_seja")
        self.assertIn("zajem_pada", ast.unparse(f))
        self.assertTrue(self._klici(f))


if __name__ == "__main__":
    unittest.main()
