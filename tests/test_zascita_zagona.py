"""Hladni zagon: prvi zunanji naslov in obnovljeni zavihki se nalozijo sele, ko so EasyList, vir grozenj in filter
sledilcev pripravljeni - ali po roku (pregled 4. 11. 2026, kot TV ZascitaZagona)."""
import ast
import os
import threading
import unittest
from types import SimpleNamespace

from core import zascita

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = "/usr/lib/safeer-os/ui"


class Ura:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class Pogled:
    def __init__(self):
        self.nalozeno = []

    def load_uri(self, uri):
        self.nalozeno.append(uri)


def _nalozi(p, u):
    p.load_uri(u)


class Odlocitev(unittest.TestCase):
    def test_zunanji_caka_do_pripravljenih(self):
        vse = zascita.ZASCITE_ZAGONA
        self.assertTrue(zascita.mora_cakati("https://banka.si/", set(), vse, 0.1))
        self.assertTrue(zascita.mora_cakati("http://x.si/", {"filter", "sledilci"}, vse, 1.9))
        self.assertFalse(zascita.mora_cakati("https://banka.si/", set(vse), vse, 0.1))

    def test_rok(self):
        self.assertFalse(zascita.mora_cakati("https://banka.si/", set(), zascita.ZASCITE_ZAGONA, zascita.ROK_ZAGONA_S))
        self.assertLessEqual(zascita.ROK_ZAGONA_S, 2.0)

    def test_notranje_strani_ne_cakajo(self):
        vse = zascita.ZASCITE_ZAGONA
        for naslov in ("file://%s/splet.html" % UI, "about:blank", "safeer://procesi", ""):
            self.assertFalse(zascita.mora_cakati(naslov, set(), vse, 0.0, nasa_mapa=UI), naslov)
        self.assertTrue(zascita.mora_cakati("file:///home/x/stran.html", set(), vse, 0.0, nasa_mapa=UI))
        self.assertTrue(zascita.mora_cakati("file://%s-zlo/x.html" % UI, set(), vse, 0.0, nasa_mapa=UI))


class VrstniRed(unittest.TestCase):
    def setUp(self):
        self.ura = Ura()
        self.z = zascita.ZascitaZagona(ura=self.ura, nasa_mapa=UI)

    def test_caka_in_nalozi_po_vrsti(self):
        a, b = Pogled(), Pogled()
        self.assertFalse(self.z.zahtevaj(a, "https://a.si/", _nalozi))
        self.assertFalse(self.z.zahtevaj(b, "https://b.si/", _nalozi))
        self.assertFalse(self.z.zahtevaj(a, "https://a2.si/", _nalozi))   # zadnja zahteva pogleda velja
        self.assertEqual((a.nalozeno, b.nalozeno), ([], []))
        self.z.pripravljena("filter")
        self.z.pripravljena("grozenj")
        self.assertFalse(self.z.preveri())
        self.assertEqual((a.nalozeno, b.nalozeno), ([], []), "brez filtra sledilcev se se ne nalozi")
        self.z.pripravljena("sledilci")
        self.assertTrue(self.z.preveri())
        self.assertEqual((a.nalozeno, b.nalozeno), (["https://a2.si/"], ["https://b.si/"]))
        self.assertEqual(self.z.cakajoci(), [])
        c = Pogled()
        self.assertTrue(self.z.zahtevaj(c, "https://c.si/", _nalozi), "po odprtju takoj")
        self.assertEqual(c.nalozeno, ["https://c.si/"])

    def test_rok_odpre(self):
        a = Pogled()
        self.z.zahtevaj(a, "https://a.si/", _nalozi)
        self.ura.t += zascita.ROK_ZAGONA_S - 0.01
        self.assertFalse(self.z.preveri())
        self.ura.t += 0.02
        self.assertTrue(self.z.preveri())
        self.assertEqual(a.nalozeno, ["https://a.si/"])

    def test_notranja_takoj_in_pozabi_cakajoco(self):
        a, b = Pogled(), Pogled()
        self.z.zahtevaj(a, "https://a.si/", _nalozi)
        self.assertTrue(self.z.zahtevaj(a, "file://%s/splet.html" % UI, _nalozi))
        self.z.zahtevaj(b, "https://b.si/", _nalozi)
        self.z.pozabi(b)                                           # zavihek zaprt
        for ime in zascita.ZASCITE_ZAGONA:
            self.z.pripravljena(ime)
        self.assertTrue(self.z.preveri())
        self.assertEqual(a.nalozeno, ["file://%s/splet.html" % UI])
        self.assertEqual(b.nalozeno, [])


def _funkcija(drevo, razred, ime):
    for vozel in ast.walk(drevo):
        if isinstance(vozel, ast.ClassDef) and vozel.name == razred:
            for f in vozel.body:
                if isinstance(f, ast.FunctionDef) and f.name == ime:
                    return f
    raise AssertionError("%s.%s ni" % (razred, ime))


def _klici(f):
    return [v for v in ast.walk(f) if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)]


class SpletVrstniRed(unittest.TestCase):
    """Brez WebKita (ast): vsa nalaganja ob zagonu gredo skozi _nalozi_zasciteno, zascita se zazene pred zavihkom."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8") as f:
            cls.drevo = ast.parse(f.read())

    def test_odpri_ne_nalaga_mimo_zascite(self):
        for razred, ime in (("VdelaniSplet", "odpri"), ("VdelaniSplet", "odpri_povezavo"),
                            ("VdelaniSplet", "odpri_domov"), ("SpletnaAplikacija", "__init__")):
            f = _funkcija(self.drevo, razred, ime)
            imena = [k.func.attr for k in _klici(f)]
            self.assertNotIn("load_uri", imena, "%s.%s nalozi mimo zascite zagona" % (razred, ime))
            self.assertIn("_nalozi_zasciteno", imena, "%s.%s" % (razred, ime))

    def test_zascita_pred_prvim_zavihkom(self):
        f = _funkcija(self.drevo, "VdelaniSplet", "__init__")
        vrstice = {k.func.attr: k.lineno for k in reversed(_klici(f))}
        self.assertLess(vrstice["_zazeni_zascito"], vrstice["nov_zavihek"])
        z = _funkcija(self.drevo, "VdelaniSplet", "_zazeni_zascito")
        prvi = [k.func.attr for k in _klici(z)]
        self.assertIn("ZascitaZagona", prvi)
        self.assertIn("timeout_add", prvi, "cakanje prek casovnika GLib, ne sleep")
        self.assertNotIn("sleep", prvi)


try:
    from core import os_splet
except Exception:  # noqa: BLE001 - brez WebKitGTK 6.0
    os_splet = None


@unittest.skipIf(os_splet is None, "WebKitGTK 6.0 ni na voljo")
class SpletZascitaZagona(unittest.TestCase):
    def test_caka_na_vir_grozenj_in_sledilce(self):
        ura = Ura()
        ti = SimpleNamespace(enabled=True, loaded=threading.Event())
        splet = SimpleNamespace(_zascita_zagona=zascita.ZascitaZagona(ura=ura), _threat_service=ti,
                                sledilci=SimpleNamespace(filter=None))
        p = Pogled()
        os_splet.VdelaniSplet._nalozi_zasciteno(splet, p, "https://banka.si/")
        self.assertEqual(p.nalozeno, [])
        splet._zascita_zagona.pripravljena("filter")
        self.assertTrue(os_splet.VdelaniSplet._preveri_zascito_zagona(splet), "casovnik tece naprej")
        ti.loaded.set()
        splet.sledilci.filter = object()
        self.assertFalse(os_splet.VdelaniSplet._preveri_zascito_zagona(splet), "casovnik se ustavi")
        self.assertEqual(p.nalozeno, ["https://banka.si/"])

    def test_brez_vira_grozenj_ne_caka_nanj(self):
        splet = SimpleNamespace(_zascita_zagona=zascita.ZascitaZagona(ura=Ura()), _threat_service=None, sledilci=None)
        p = Pogled()
        os_splet.VdelaniSplet._nalozi_zasciteno(splet, p, "https://a.si/")
        splet._zascita_zagona.pripravljena("filter")
        self.assertFalse(os_splet.VdelaniSplet._preveri_zascito_zagona(splet))
        self.assertEqual(p.nalozeno, ["https://a.si/"])


if __name__ == "__main__":
    unittest.main()
