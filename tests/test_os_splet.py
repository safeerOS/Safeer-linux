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
