"""Safeer BankGuard on the desktop: fake banks get a warning, real banks are never touched.

The rules themselves are tested in safeer-threat-intel (clients/banks/cases.json, same file in
Kotlin and Python). These tests cover the browser glue (GTK4, core/os_splet.py).
"""

import json
import unittest

from core import adblock


class CatalogueTests(unittest.TestCase):
    def tearDown(self):
        adblock._fake_bank_allowed_hosts.clear()

    def test_real_banks_are_never_ads_or_threats_from_lists(self):
        for url in ("https://klik.nlb.si/", "https://bankanet.otpbanka.si/", "https://3ds.bankart.si/acs", "https://www.paypal.com/"):
            self.assertTrue(adblock.is_real_bank_host(url), url)
            self.assertFalse(adblock.is_ad_domain(url), url)
            self.assertFalse(adblock.is_threat_domain(url), url)
        self.assertFalse(adblock.is_real_bank_host("https://nlb.si.evil.example/"))

        def mistaken(url):
            return "phishing" if "nlb.si" in url else None

        adblock.register_threat_matcher(mistaken)
        try:
            self.assertFalse(adblock.is_threat_domain("https://www.nlb.si/"), "a mistaken phishing entry never blocks a bank")
        finally:
            adblock._extra_threat_matchers.remove(mistaken)

        def compromised(url):
            return "malware" if "cdn.nlb.si" in url else None

        adblock.register_threat_matcher(compromised)
        try:
            self.assertTrue(adblock.is_threat_domain("https://cdn.nlb.si/payload.exe"), "confirmed malware still blocks")
        finally:
            adblock._extra_threat_matchers.remove(compromised)

    def test_fake_bank_hosts_and_session_choice(self):
        verdict = adblock.fake_bank_verdict("https://nlb-klik-varnost.net/prijava")
        self.assertEqual((verdict.bank_id, verdict.official_domain), ("nlb", "nlb.si"))
        self.assertEqual(adblock.fake_bank_verdict("https://otpbamka.si/").bank_id, "otp")
        self.assertIsNone(adblock.fake_bank_verdict("https://klik.nlb.si/"))
        self.assertIsNone(adblock.fake_bank_verdict("file:///home/user/nlb-klik.html"))
        adblock.allow_fake_bank_host("https://nlb-klik-varnost.net/other")
        self.assertIsNone(adblock.fake_bank_verdict("https://nlb-klik-varnost.net/prijava"))
        self.assertTrue(adblock.is_fake_bank_host_allowed("nlb-klik-varnost.net"))

    def test_unicode_addresses_are_checked_in_their_xn_form(self):
        # Qt prints many internationalized hosts in Unicode, the page reports the xn-- form
        self.assertEqual(adblock.fake_bank_verdict("https://pаypаl-login.com/").reason, "homoglyph")
        signals = {"host": "xn--pypl-login-zqic.com", "scheme": "https", "password": True, "title": "Pay"}
        self.assertIsNone(adblock.fake_bank_page_verdict("https://pаypаl-login.com/", signals))  # no bank name on the page
        signals["title"] = "PayPal"
        self.assertEqual(adblock.fake_bank_page_verdict("https://pаypаl-login.com/", signals).bank_id, "paypal")
        self.assertIsNone(adblock.fake_bank_verdict("https://ljubljanska-delavska-čitalnica.si/"))

    def test_page_verdict_uses_the_page_that_answered(self):
        signals = {"host": "secure-login.example", "scheme": "https", "password": True, "title": "NLB Klik - prijava"}
        self.assertEqual(adblock.fake_bank_page_verdict("https://secure-login.example/x", signals).bank_id, "nlb")
        self.assertIsNone(adblock.fake_bank_page_verdict("https://other.example/", signals))
        self.assertIsNone(adblock.fake_bank_page_verdict("https://secure-login.example/", None))
        self.assertIsNone(adblock.fake_bank_page_verdict("https://klik.nlb.si/", dict(signals, host="klik.nlb.si")))
        self.assertIn("one-time-code", adblock.bank_guard_page_script())

    def test_local_attachment_and_card_lure_pages(self):
        # SI-CERT TZ009: the fake bank page is an HTML attachment opened from mail, so it has no host
        local = {"host": "", "scheme": "file", "password": True, "title": "NLB Klik"}
        verdict = adblock.fake_bank_page_verdict("file:///home/uporabnik/Prejemi/NLB_Klik.html", local)
        self.assertEqual((verdict.bank_id, verdict.reason), ("nlb", "local"))
        self.assertIsNone(adblock.fake_bank_page_verdict("https://secure-login.example/", local), "scheme must match the page")
        self.assertIsNone(adblock.fake_bank_page_verdict("file:///tmp/racun.html", dict(local, title="Moj racun")))
        self.assertIn("priponke", adblock.fake_bank_warning_text(verdict))
        self.assertIn("nikoli ne pokliče", adblock.fake_bank_warning_text(verdict))
        adblock.allow_fake_bank_host("file:///home/uporabnik/Prejemi/NLB_Klik.html")
        self.assertTrue(adblock.is_fake_bank_host_allowed("file:///anything.html"))
        self.assertIsNone(adblock.fake_bank_page_verdict("file:///home/uporabnik/Prejemi/NLB_Klik.html", local))
        # SI-CERT, May 2026: a card form dressed up as a police fine on a fresh domain
        lure = {"host": "kazen-placilo.example", "scheme": "https", "card": True, "title": "Placilo kazni",
                "headings": "Policija - prekrsek", "text": "Kazen 39 EUR placajte s kartico. Stevilka kartice"}
        verdict = adblock.fake_bank_page_verdict("https://kazen-placilo.example/pay", lure)
        self.assertEqual((verdict.bank_id, verdict.reason, verdict.official_domain), ("card", "lure", ""))
        self.assertIn("plačilne kartice", adblock.fake_bank_warning_text(verdict))
        self.assertIn("pretext", adblock.fake_bank_warning_text(verdict, "en"))
        # tax number and PIN fields count as credential fields
        taxid = {"host": "nlb-preverjanje.example", "scheme": "https", "taxid": True, "title": "NLB Klik - preverjanje"}
        self.assertEqual(adblock.fake_bank_page_verdict("https://nlb-preverjanje.example/", taxid).reason, "page")

    def test_bank_pages_run_without_cosmetic_scripts(self):
        self.assertIn("*://*.nlb.si/*", adblock.AUTH_SCRIPT_EXCLUSIONS)
        self.assertIn("*://bankart.si/*", adblock.AUTH_SCRIPT_EXCLUSIONS)

    def test_desktop_copies_match_the_catalogue_files(self):
        from pathlib import Path

        core = Path(adblock.__file__).resolve().parent
        data = json.loads((core / "banks.json").read_text("utf-8"))
        self.assertGreaterEqual(len(data["banks"]), 10)
        self.assertTrue((core / "bank_guard_page.js").read_text("utf-8").startswith("(function ()"))


class BrowserGlueTests(unittest.TestCase):
    """Splet in Safeer Browser (GTK4, core/os_splet.py): lazna banka se ustavi pred nalaganjem in pokaze opozorilo
    z gumbom za uradno stran (GTK3 umaknjen 18. 10. 2026)."""

    def setUp(self):
        import pathlib
        self.vir = (pathlib.Path(__file__).resolve().parents[1] / "core" / "os_splet.py").read_text(encoding="utf-8")

    def test_fake_bank_navigation_is_stopped_and_warned(self):
        politika = self.vir[self.vir.index("    def _politika("):self.vir.index("    def _odziv(")]
        self.assertIn("sodba = adblock.fake_bank_verdict(naslov)", politika)
        self.assertIn("odlocitev.ignore(); self._opozorilo_bank(pogled, naslov, sodba); return True", politika)

    def test_warning_choices(self):
        opozorilo = self.vir[self.vir.index("    def _opozorilo_bank("):self.vir.index("    def _opozorilo(")]
        self.assertIn('[self._t("nazaj")] + ([sodba.official_domain] if sodba.official_domain else [])', opozorilo)
        self.assertIn("adblock.fake_bank_warning_text(sodba, self.jezik())", opozorilo)


if __name__ == "__main__":
    unittest.main()
