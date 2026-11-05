"""Scit ustavi ciste oglasne in merilne streznike (core/scit_pravila.py »oglasni_strezniki«) tudi v DNS za ves
racunalnik. Lastnik 5. 11. 2026: izmerjeno, da zivi Scit na Windows in TV spusti doubleclick.net, ker je bil v DNS
samo seznam »telemetrija«. Sledilci z uporabnisko stranjo (analytics.google.com, googletagmanager.com, hotjar.com)
ostanejo samo v filtru WebKit; prijava, preverjanje cloveka in predvajanje YouTube se ne ustavijo nikoli.
Ista datoteka preizkusa je v Safeer-windows (windows/tests/test_scit_oglasni_strezniki_win.py)."""
import os
import struct
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_scit, scit_pravila as sp  # noqa: E402
from core.signed_feed import FeedVerificationError  # noqa: E402

USTAVLJENI = ("doubleclick.net", "ad.doubleclick.net", "googleads.g.doubleclick.net", "stats.g.doubleclick.net",
              "pagead2.googlesyndication.com", "tpc.googlesyndication.com", "www.googleadservices.com",
              "www.googletagservices.com", "adservice.google.com", "app-measurement.com", "aax.amazon-adsystem.com",
              "match.adsrvr.org", "an.facebook.com", "bat.bing.com", "sb.scorecardresearch.com")
#: Sledilci z uporabnisko stranjo ali v dvomu - DNS jih spusti (filter WebKit jih ustavi kot tretjo stran).
SPUSCENI = ("analytics.google.com", "www.googletagmanager.com", "tagmanager.google.com", "www.google-analytics.com",
            "hotjar.com", "www.hotjar.com", "mixpanel.com", "amplitude.com", "analytics.twitter.com", "demdex.net",
            "ads.google.com", "adsense.google.com", "admanager.google.com", "marketingplatform.google.com",
            "advertising.amazon.com", "www.amazon.com", "www.facebook.com", "www.linkedin.com", "www.bing.com")
#: Prijava Google, reCAPTCHA, BotGuard, Turnstile, hCaptcha in predvajanje YouTube (NUJNO in ZASCITENI).
NUJNI = ("accounts.google.com", "accounts.youtube.com", "www.google.com", "www.gstatic.com", "www.recaptcha.net",
         "jnn-pa.googleapis.com", "challenges.cloudflare.com", "hcaptcha.com", "www.youtube.com", "m.youtube.com",
         "music.youtube.com", "www.youtube-nocookie.com", "youtubei.googleapis.com", "rr3---sn-a.googlevideo.com",
         "i.ytimg.com", "yt3.ggpht.com", "fonts.googleapis.com", "imasdk.googleapis.com", "googleapis.com")


def poizvedba(ime: str) -> bytes:
    telo = b"".join(struct.pack("B", len(o)) + o for o in (d.encode("utf-8") for d in ime.split(".") if d)) + b"\x00"
    return struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0) + telo + struct.pack("!HH", 1, 1)


class Shramba(dict):
    def get(self, k, d=None):
        return dict.get(self, k, d)

    def set(self, k, v):
        self[k] = v


class OglasniStrezniki(unittest.TestCase):
    def setUp(self):
        self._mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self._mapa.cleanup)

    def _izid(self, ime: str) -> str:
        """Pot razresevalnika (Razresevalnik._odgovori) s praznim seznamom oglasov: odloci samo seznam pravil Scita."""
        sc = os_scit.Scit(Shramba(), mapa=self._mapa.name)
        sc.seznami = os_scit.Seznami(self._mapa.name)
        sc.razresevalnik = os_scit.Razresevalnik(sc._kategorija, lambda: [])
        odgovor = sc.razresevalnik._odgovori(poizvedba(ime), False)
        rcode = odgovor[3] & 0x0F if odgovor else None
        if rcode in (None, 2):
            return "spuscen"
        return "ustavljeno" if rcode == 3 else "rcode %d" % rcode

    def test_oglasni_strezniki_ustavljeni_v_dns(self):
        for ime in USTAVLJENI:
            with self.subTest(ime=ime):
                self.assertEqual(self._izid(ime), "ustavljeno")

    def test_sledilci_z_uporabnisko_stranjo_spusceni(self):
        for ime in SPUSCENI:
            with self.subTest(ime=ime):
                self.assertEqual(self._izid(ime), "spuscen")

    def test_nujni_gostitelji_spusceni(self):
        for ime in NUJNI:
            with self.subTest(ime=ime):
                self.assertEqual(self._izid(ime), "spuscen")

    def test_kategorija_premora(self):
        """Ista kategorija kot telemetrija: premor Scita in izjema uporabnika (npr. klik na sponzoriran zadetek) jo spustita."""
        s = os_scit.Seznami.__new__(os_scit.Seznami)
        s.nabor, s.storitev, s._kljuc = os_scit.Nabor(), None, threading.Lock()
        self.assertEqual(s.kategorija("doubleclick.net"), os_scit.KATEGORIJA_PREMORA)
        self.assertIsNone(s.kategorija("analytics.google.com"))


class SeznamOglasnih(unittest.TestCase):
    def test_vgrajen_seznam(self):
        p = sp.vgrajena()
        self.assertIn("doubleclick.net", p.oglasni_strezniki)
        self.assertTrue(set(p.oglasni_strezniki) <= set(p.sledilci), "vsak je tudi v sledilci (filter WebKit enak)")
        for g in p.oglasni_strezniki:
            with self.subTest(g=g):
                self.assertFalse(sp._zadene_nujno(g))
                self.assertFalse(os_scit.je_zasciten(g))
                for n in NUJNI + SPUSCENI:
                    self.assertFalse(n == g or n.endswith("." + g), "%s bi ustavil %s" % (g, n))

    def test_seznam_brez_kljuca_obdrzi_vgrajenega(self):
        """Podpisan seznam starejsega streznika (brez kljuca) ne ugasne ustavljanja v DNS."""
        p = sp.preveri_pravila({"sledilci": ["sledilec.test"]}, sp.VGRAJENA_VERZIJA + 1, "podpisana")
        self.assertEqual(p.oglasni_strezniki, sp.vgrajena().oglasni_strezniki)
        self.assertEqual(sp.preveri_pravila({"oglasni_strezniki": []}, 1, "podpisana").oglasni_strezniki, ())

    def test_nujni_gostitelj_zavrnjen(self):
        for g in ("www.google.com", "google.com", "googleapis.com", "youtube.com", "googlevideo.com", "recaptcha.net",
                  "cloudflare.com", "accounts.google.com"):
            with self.subTest(g=g):
                with self.assertRaises(FeedVerificationError):
                    sp.preveri_pravila({"oglasni_strezniki": [g]}, 1, "preizkus")

    def test_stevilo_pravil_kot_prej(self):
        """rule_count podpisanega paketa ne steje novega kljuca: starejsi odjemalci paket se vedno sprejmejo."""
        d = {"sledilci": ["a.test"], "oglasni_strezniki": ["b.test", "c.test"]}
        self.assertEqual(sp._stevilo_pravil(d), 1)


if __name__ == "__main__":
    unittest.main()
