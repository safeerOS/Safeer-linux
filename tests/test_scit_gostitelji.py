"""Scit grozenj na Googlovih gostiteljih (5. 11. 2026, kot telefon tests/ScitGoogleTest.kt in TV): lazna prijava na
sites.google.com / script.google.com je blokirana po tocnem naslovu, iskanje in prijava Googla pa nikoli - tudi ce vir
(napaka ali zastrupitev) navede google.com, sites.google.com ali web.app kot malware. DNS Scit na korenu in skupnih
gostiteljih nikoli ne blokira (pozna samo ime), projekt (zlo.web.app) da."""
import tempfile
import threading
import unittest

from core import adblock, os_scit, scit_gostitelji as g
from core.threat_intel import ThreatIntelService, _load_feed_module

LAZNE = [
    "https://sites.google.com/view/nlb-prijava-2026",
    "https://script.google.com/macros/s/AKfyc-lazno/exec",
    "https://docs.google.com/forms/d/e/1FAIpQ-lazno/viewform",
    "https://storage.googleapis.com/zlo-vedro/prijava.html",
    "https://www.googleapis.com/download/storage/v1/b/zlo-vedro/o/prijava.html",
    "https://lh3.googleusercontent.com/zlo/prijava.html",
]
PROJEKTI = ["https://lazna-banka.web.app/prijava", "https://zlo-vedro.storage.googleapis.com/prijava.html"]
PODTAKNJENE_DOMENE = ["sites.google.com", "script.google.com", "google.com", "google.si", "web.app", "googleusercontent.com",
                      "googleapis.com", "storage.googleapis.com", "www.googleapis.com", "accounts.youtube.com",
                      "oauth2.googleapis.com", "gstatic.com"]
PODTAKNJENI_NASLOVI = ["https://sites.google.com/", "https://docs.google.com/forms", "https://www.google.si/search?q=safeer",
                       "https://accounts.google.com/signin", "https://accounts.google.com/", "https://oauth2.googleapis.com/token"]
VARNI = [
    "https://www.google.si/search?q=safeer", "https://www.google.com/search?q=safeer", "https://www.google.com./",
    "https://google.si/", "https://www.google.co.uk/", "https://accounts.google.com/", "https://accounts.google.com/signin",
    "https://myaccount.google.com/", "https://accounts.youtube.com/accounts/SetSID", "https://oauth2.googleapis.com/token",
    "https://mail.google.com/mail/u/0/", "https://sites.google.com/", "https://sites.google.com/view/prava-stran-sole",
    "https://script.google.com/home", "https://docs.google.com/forms", "https://www.googleapis.com/oauth2/v3/certs",
    "https://druga.web.app/", "https://drugo-vedro.storage.googleapis.com/x.html", "https://lh3.googleusercontent.com/a/slika",
    "https://fonts.gstatic.com/s/roboto.woff2",
]


def _indeks(podtaknjeno: bool):
    feed = _load_feed_module()
    pravila = [(u, "url", "phishing", "fixture") for u in LAZNE]
    pravila[3] = (LAZNE[3], "url", "malware", "fixture")
    pravila += [("lazna-banka.web.app", "domain", "phishing", "fixture"),
                ("zlo-vedro.storage.googleapis.com", "domain", "malware", "fixture")]
    if podtaknjeno:
        pravila += [(d, "domain", "malware", "fixture") for d in PODTAKNJENE_DOMENE]
        pravila += [(u, "url", "malware", "fixture") for u in PODTAKNJENI_NASLOVI]
        pravila.append(("google.co.zz", "domain", "phishing", "fixture"))  # ni Googlova domena
    return feed.ThreatIndex(pravila)


class ScitGostiteljiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storitev = ThreatIntelService(self.tmp.name, trusted_keys={"k": "AAAA"}, base_urls=["https://intel.test"],
                                           fetch=lambda url, limit: b"")
        self.storitev.loaded.set()
        adblock.register_threat_matcher(self.storitev.match)

    def tearDown(self):
        adblock._extra_threat_matchers.remove(self.storitev.match)
        self.tmp.cleanup()

    def test_razvrstitev(self):
        self.assertEqual(len(g.GOOGLE_PRIPONE), 187)
        for h in ("www.google.com", "google.si", "www.google.co.uk", "accounts.google.de", "myaccount.google.com",
                  "accounts.youtube.com", "oauth2.googleapis.com", "fonts.gstatic.com", "GOOGLE.COM."):
            self.assertEqual(g.vrsta(h), g.KOREN, h)
        for h in ("www.google.co.zz", "accounts.google.zz", "google.example", "mail.google.com", "x.storage.googleapis.com"):
            self.assertEqual(g.vrsta(h), g.NAVADEN, h)
        for h in ("sites.google.com", "www.googleapis.com", "lh3.googleusercontent.com", "web.app", "x.web.app"):
            self.assertEqual(g.vrsta(h), g.VSEBINA, h)
        self.assertFalse(g.sme_pot("https://docs.google.com/forms", "docs.google.com"))
        self.assertFalse(g.sme_pot("https://sites.google.com/view?x=/a/b", "sites.google.com"))
        self.assertTrue(g.sme_pot("https://sites.google.com/view/ime", "sites.google.com"))

    def test_brskalnik_lazne_poti_in_projekti(self):
        self.storitev.store.index = _indeks(podtaknjeno=False)
        for u in LAZNE + PROJEKTI:
            self.assertTrue(adblock.is_threat_domain(u), u)
        self.assertEqual(self.storitev.match(LAZNE[3]), "malware")
        self.assertFalse(adblock.is_threat_domain("https://sites.google.com/view/prava-stran-sole"))

    def test_brskalnik_podtaknjeni_vnosi_ne_blokirajo_googla(self):
        self.storitev.store.index = _indeks(podtaknjeno=True)
        for u in LAZNE + PROJEKTI:
            self.assertTrue(adblock.is_threat_domain(u), u)
        for u in VARNI:
            self.assertFalse(adblock.is_threat_domain(u), u)
        # Ponarejen »Google« z neobstojeco pripono ni koren in ga vir sme blokirati.
        self.assertTrue(adblock.is_threat_domain("https://www.google.co.zz/prijava"))
        self.assertTrue(adblock.is_threat_domain("https://accounts.google.co.zz/"))

    def test_vgrajen_seznam_brskalnika(self):
        star = adblock._threat_trie
        try:
            adblock._threat_trie = adblock.ReverseDomainTrie()
            for d in ("google.com", "www.google.com", "accounts.google.com", "script.google.com", "appspot.com",
                      "evil-c2.appspot.com", "storage.googleapis.com", ".googleapis.com", "evil-c2.example"):
                adblock._threat_trie.insert(d)
            self.storitev.store.index = _load_feed_module().ThreatIndex()
            for u in ("https://evil-c2.appspot.com/gate", "https://evil-c2.example/"):
                self.assertTrue(adblock.is_threat_domain(u), u)
            for u in ("https://www.google.com/", "https://accounts.google.com/", "https://script.google.com/home",
                      "https://mail.google.com/", "https://drugi-projekt.appspot.com/", "https://x.storage.googleapis.com/a",
                      "https://storage.googleapis.com/vedro/x"):
                self.assertFalse(adblock.is_threat_domain(u), u)
        finally:
            adblock._threat_trie = star

    def test_dns_scit(self):
        with tempfile.TemporaryDirectory() as m:
            s = os_scit.Seznami(m, prenesi_fn=lambda *a, **k: None)
            s.nabor = os_scit.Nabor.iz_domen([(d, "malware") for d in PODTAKNJENE_DOMENE + ["www.google.com", "mail.google.com",
                                               "evil-c2.appspot.com", "zlo-vedro.storage.googleapis.com", "mail.example"]]
                                              + [("google.com", "oglasi")])
            self.storitev.store.index = _indeks(podtaknjeno=True)
            s.storitev = self.storitev
            for ime in ("www.google.com", "google.si", "accounts.google.com", "accounts.youtube.com", "oauth2.googleapis.com",
                        "sites.google.com", "script.google.com", "storage.googleapis.com", "www.googleapis.com",
                        "lh3.googleusercontent.com", "web.app", "druga.web.app", "x.storage.googleapis.com",
                        "fonts.gstatic.com", "drive.google.com"):
                self.assertIsNone(s.kategorija(ime), ime)
                self.assertFalse(s.groznja(ime), ime)
            # Vnos za tocno ime pod Googlom ali za projekt ostane: kdor ga navede, ga navede namenoma.
            for ime in ("evil-c2.appspot.com", "zlo-vedro.storage.googleapis.com", "lazna-banka.web.app", "mail.example",
                        "www.google.co.zz"):
                self.assertTrue(s.groznja(ime), ime)
            self.assertEqual(s.kategorija("mail.google.com"), "malware")  # navaden gostitelj, izrecen vnos
            # Seznam oglasov: izrecen oglasni gostitelj pod skupno infrastrukturo ostane, celotna domena in koren ne.
            s.nabor = os_scit.Nabor.iz_domen([("afs.googleusercontent.com", "oglasi"), ("googleusercontent.com", "oglasi"),
                                              ("google.com", "oglasi"), ("www.google.com", "oglasi"),
                                              ("script.googleusercontent.com", "phishing")])
            self.assertEqual(s.kategorija("afs.googleusercontent.com"), "oglasi")
            for ime in ("lh3.googleusercontent.com", "mail.google.com", "www.google.com", "script.googleusercontent.com"):
                self.assertIsNone(s.kategorija(ime), ime)


if __name__ == "__main__":
    unittest.main()
