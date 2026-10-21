"""Logika vdelanega razdelka Splet, ki ne potrebuje zaslona."""

import json
import os
import unittest

from core.os_splet import BESEDILA, JEZIKI, besedila, je_domaca_stran, razcleni_sporocilo


KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_vseh_sest_jezikov_ima_vsa_besedila():
    assert tuple(BESEDILA) == JEZIKI
    assert all(set(BESEDILA["sl"]) == set(BESEDILA[jezik]) for jezik in JEZIKI)
    assert [BESEDILA[j]["nov"] for j in JEZIKI] == [
        "Nov zavihek", "New tab", "Neuer Tab", "Nueva pestaña", "Nouvel onglet", "Nuova scheda"
    ]
    assert besedila("xx") == BESEDILA["en"]


def test_most_sprejme_samo_navigacijo_http_in_dodajanje_bliznjice():
    assert razcleni_sporocilo({"action": "navigate", "url": "example.com"}) == {
        "action": "navigate", "url": "https://example.com"
    }
    assert razcleni_sporocilo(json.dumps({"action": "open_sidebar", "service": "add_portal"})) == {
        "action": "open_sidebar", "service": "add_portal"
    }
    assert razcleni_sporocilo({"action": "navigate", "url": "file:///etc/passwd"}) is None
    assert razcleni_sporocilo({"action": "open_sidebar", "service": "settings"}) is None
    assert razcleni_sporocilo("ni json") is None
    # Odstranjevanje bliznjic z zacetne strani (tudi vgrajenih) in obnova privzetih.
    assert razcleni_sporocilo({"action": "remove_portal", "url": "https://www.reddit.com"})["action"] == "remove_portal"
    assert razcleni_sporocilo({"action": "remove_portal", "url": "file:///etc/passwd"}) is None
    assert razcleni_sporocilo({"action": "reset_portals"}) == {"action": "reset_portals"}
    from core.os_splet import kljuc_bliznjice
    assert kljuc_bliznjice("https://www.Reddit.com/") == "reddit.com"
    assert kljuc_bliznjice("http://365.rtvslo.si") == "365.rtvslo.si"


class StevecScita(unittest.TestCase):
    """Zunanji pregled 8. 10. 2026: stevca scita (ads/threats) ne sme napihniti poljubna stran."""

    def test_increment_ne_gre_skozi_glavni_rokovalnik(self):
        self.assertIsNone(razcleni_sporocilo({"action": "increment_ads", "count": 5}))
        self.assertIsNone(razcleni_sporocilo({"action": "increment_threats", "count": 5}))

    def test_preveri_stevec(self):
        from core import adblock
        self.assertEqual(adblock.preveri_stevec({"action": "increment_ads", "count": 5}), {"action": "increment_ads", "count": 5})
        self.assertEqual(adblock.preveri_stevec({"action": "increment_threats", "count": 7}), {"action": "increment_threats", "count": 7})
        self.assertEqual(adblock.preveri_stevec({"action": "increment_ads", "count": 9999}), {"action": "increment_ads", "count": 100})
        for slabo in ({"action": "increment_ads", "count": 0}, {"action": "increment_ads", "count": -3},
                      {"action": "increment_ads", "count": "x"}, {"action": "navigate", "url": "https://x"},
                      {"action": "set_default_browser"}, "ni dict", None):
            self.assertIsNone(adblock.preveri_stevec(slabo), slabo)

    def test_kozmeticna_skripta_v_locenem_svetu(self):
        from core import adblock
        self.assertIn("messageHandlers.safeer_stevec.postMessage", adblock.GENERIC_COSMETIC_SCRIPT)
        self.assertNotIn("messageHandlers.safeer.postMessage", adblock.GENERIC_COSMETIC_SCRIPT)
        self.assertEqual(adblock.STEVEC_MOST, "safeer_stevec")
        self.assertTrue(adblock.STEVEC_SVET)

    def test_atribut_ne_zakrije_metode(self):
        """18. 10. 2026: celo stevilo self._stevec (stevec zavihkov) je zakrilo metodo _stevec (stevec Scita) in vsako
        sporocilo kozmeticne skripte je padlo s TypeError. Noben atribut primerka ne sme imeti imena metode razreda."""
        import ast
        drevo = ast.parse(open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8").read())
        napake = []
        for razred in (v for v in ast.walk(drevo) if isinstance(v, ast.ClassDef)):
            metode = {f.name for f in razred.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))}
            for v in ast.walk(razred):
                cilji = v.targets if isinstance(v, ast.Assign) else [v.target] if isinstance(v, (ast.AugAssign, ast.AnnAssign)) else []
                for c in cilji:
                    for e in (c.elts if isinstance(c, ast.Tuple) else [c]):
                        if (isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name) and e.value.id == "self"
                                and e.attr in metode):
                            napake.append("%s.%s (vrstica %d)" % (razred.name, e.attr, v.lineno))
        self.assertEqual(napake, [])


class NaslovZavihkaTests(unittest.TestCase):
    """Zavihek file:// brez title mora imeti ime datoteke (kot Safari/Chrome), ne »Nov zavihek«."""

    def test_naslov_zavihka_file_brez_naslova_strani(self):
        from core.os_splet import naslov_zavihka
        self.assertEqual(naslov_zavihka("file:///etc/os-release", None, "Nov zavihek", KOREN), "os-release")
        self.assertEqual(naslov_zavihka("file:///etc/os-release", "", "Nov zavihek", KOREN), "os-release")
        self.assertEqual(naslov_zavihka("file:///home/uporabnik/poro%C4%8Dilo.pdf", None, "Nov zavihek", KOREN), "poročilo.pdf")
        self.assertEqual(naslov_zavihka("file:///home/uporabnik/mapa/", None, "Nov zavihek", KOREN), "mapa")

    def test_naslov_zavihka_file_z_naslovom_strani(self):
        from core.os_splet import naslov_zavihka
        self.assertEqual(naslov_zavihka("file:///etc/os-release", "Linux Mint 22", "Nov zavihek", KOREN), "Linux Mint 22")

    def test_naslov_zavihka_domaca_ali_ne_file(self):
        from core.os_splet import naslov_zavihka
        domaca = "file://" + os.path.join(KOREN, "ui", "splet.html")
        self.assertEqual(naslov_zavihka(domaca, None, "Nov zavihek", KOREN), "Nov zavihek")
        self.assertEqual(naslov_zavihka("https://safeer.si/novice", None, "Nov zavihek", KOREN), "Nov zavihek")
        self.assertEqual(naslov_zavihka("https://safeer.si/novice", "Safeer Novice", "Nov zavihek", KOREN), "Safeer Novice")
        self.assertEqual(naslov_zavihka("file:///", None, "Nov zavihek", KOREN), "Nov zavihek")

    def test_splet_naslov_spremenjen_nastavi_ime_datoteke(self):
        from unittest import mock
        from core.os_splet import VdelaniSplet
        splet = mock.MagicMock(spec=VdelaniSplet)
        splet.koren = KOREN
        splet._t = lambda kljuc: "Nov zavihek" if kljuc == "nov" else kljuc
        pogled = mock.Mock()
        pogled.get_uri.return_value = "file:///etc/os-release"
        pogled.get_title.return_value = None
        label = mock.Mock()
        vrstica = mock.Mock()
        splet.zavihki = [{"pogled": pogled, "naslov": label, "vrstica": vrstica}]

        VdelaniSplet._naslov_spremenjen(splet, pogled, None)
        label.set_text.assert_called_with("os-release")
        vrstica.set_tooltip_text.assert_called_with("os-release")
