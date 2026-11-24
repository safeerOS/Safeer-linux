"""Jezik zvoka pri izbiri toka (core/tok_izbira.py) - isti primeri kot tests/TokIzbiraTest.kt na Androidu.

Primer iz zivljenja (10. 10. 2026): »In the Grey« je na TV igral brazilsko sinhronizacijo v 4K, ker je dodatek pod
istim filmom ponudil sinhronizacijo brez oznake in izvirnik z oznako »(L) Legendado«.
"""
import unittest

from core import tok_izbira as ti

TV = ti.Zmoznosti(visina=2160)
ZONA = ["Na Zona Cinzenta - 2026 Iracemaflix 1 · 4K Servidor: cdn4k.cc",
        "Na Zona Cinzenta - 2026 (L) Iracemaflix 1 · 4K · Legendado Servidor: cdn4k.cc",
        "Na Zona Cinzenta (2026) Iracemaflix 1 · Auto Servidor: auth.urlsync.gy",
        "Na Zona Cinzenta - 2026 (L) Iracemaflix 1 · Auto · Legendado Servidor: 5ce.me"]


class TestJezikZvoka(unittest.TestCase):
    def test_oznake(self):
        self.assertEqual(ti.jezik_zvoka(ZONA[1]), "izvirnik")
        self.assertEqual(ti.jezik_zvoka(ZONA[0]), "")
        self.assertEqual(ti.jezik_zvoka("Film 2160p WEB-DL Hindi Dubbed 8 GB"), "hi")
        self.assertEqual(ti.jezik_zvoka("Film 1080p WEB-DL ENG 3 GB"), "en")
        self.assertEqual(ti.jezik_zvoka("Film 1080p Dual Audio ENG-HIN"), "vec")
        self.assertEqual(ti.jezik_zvoka("Film 1080p Dublado"), "pt")
        self.assertEqual(ti.jezik_zvoka("Film 1080p DUB"), "sinhronizacija")
        self.assertEqual(ti.jezik_zvoka("Film.2019.TRUEFRENCH.1080p"), "fr")

    def test_brez_zelje_staro_vedenje(self):
        self.assertEqual(ti.uredi(ZONA, lambda t: t, TV)[0], ZONA[0])

    def test_anglescina_izvirnik_pred_sinhronizacijo(self):
        self.assertEqual(ti.uredi(ZONA, lambda t: t, TV, zelen_jezik="en", izvirni="en")[0], ZONA[1])
        self.assertEqual(ti.uredi(ZONA, lambda t: t, TV, zelen_jezik="en")[0], ZONA[1])
        # samo izvirnik neznane locljivosti proti neoznacenemu 4K istega dodatka: izvirnik
        self.assertEqual(ti.uredi([ZONA[0], ZONA[3]], lambda t: t, TV, zelen_jezik="en", izvirni="en")[0], ZONA[3])

    def test_jezik_pred_locljivostjo_ne_pred_predvajljivostjo(self):
        hi = ["Film 2160p WEB-DL Hindi Dubbed 8 GB", "Film 1080p WEB-DL ENG 3 GB"]
        self.assertEqual(ti.uredi(hi, lambda t: t, TV, zelen_jezik="en")[0], hi[1])
        brez_hevc = ti.Zmoznosti(visina=2160, hevc=False)
        self.assertEqual(ti.uredi(["Film 1080p ENG x265", "Film 720p Latino"], lambda t: t, brez_hevc,
                                  zelen_jezik="en")[0], "Film 720p Latino")

    def test_slovenski_in_tuji_izvirnik(self):
        self.assertEqual((ti.zeleni_jezik("sl"), ti.zeleni_jezik("fr"), ti.zeleni_jezik("")), ("sl", "en", "en"))
        self.assertEqual(ti.tocke_jezika("Film FRENCH 1080p", "en", "fr"), 0)
        self.assertEqual(ti.tocke_jezika("Film Hindi 1080p", "en", "fr"), -800)
        self.assertEqual(ti.tocke_jezika("Film Sloven 1080p", "sl", "sl"), 800)

    def test_neoznacena_izdaja_angleskega_filma_ne_izgubi_pred_720p_english(self):
        # 24. 11. 2026: Usenet za Fight Club je dal 720p »English« pred 1080p BluRay brez oznake jezika.
        izdaje = ["Fight.Club.1999.English.720p.WEB-DL.H.264 1.6 GB", "Fight.Club.1999.1080p.BluRay.x264 8 GB"]
        urejeno = ti.uredi(izdaje, lambda t: t, ti.Zmoznosti(visina=1080), zelen_jezik="en", izvirni="en")
        self.assertEqual(urejeno[0], izdaje[1])
        # tuji film: neoznacena izdaja ostane brez tock (ni nujno angleska)
        self.assertEqual(ti.tocke_jezika("Film 1080p", "en", "fr"), 0)
        self.assertEqual(ti.tocke_jezika("Film 1080p", "en", "en"), 800)

    def test_ruski_vo_in_zastavice_niso_izvirnik(self):
        # 24. 11. 2026, Torrentio za Night of the Living Dead (1968): ruska izdaja »DVO + VO (Tycoon) ... 🇬🇧 / 🇷🇺« je
        # stela kot izvirnik s podnapisi, zato so vse neoznacene angleske izdaje (YTS 1080p, 100 sejalcev) dobile -800.
        # »VO« je v ruskih izdajah glas cez izvirnik (voice-over), ne »version originale«.
        ru = "Ночь живых мертвецов / Night of the Living Dead [1968 BDRemux 1080p] DVO (Film Prestige) + VO (Tycoon) 👤 21 🇬🇧 / 🇷🇺"
        self.assertEqual(ti.jezik_zvoka("Film 1080p VO (Tycoon)"), "")
        self.assertEqual(ti.jezik_zvoka(ru), "vec")
        self.assertEqual(ti.jezik_zvoka("Film 1080p 🇷🇺"), "ru")
        self.assertEqual(ti.jezik_zvoka("Film 1080p 🇯🇵"), "ja")
        self.assertEqual(ti.tocke_jezika("Film 1080p 🇯🇵", "en", "ja"), 0)
        self.assertEqual(ti.jezik_zvoka("Film 1080p 🇦🇶"), "zastava:AQ")
        self.assertEqual(ti.jezik_zvoka("Film 1080p 🇬🇧"), "en")
        self.assertEqual(ti.jezik_zvoka("Film 1080p ENG 🇬🇧"), "en")
        self.assertEqual(ti.jezik_zvoka("Film.VOSTFR.1080p"), "izvirnik")
        yts = "Night of the Living Dead 1968 1080p BluRay 👤 100 YTS"
        rip = "Ночь живых мертвецов / Night of the Living Dead [1968 1080p BDRip] 👤 100 🇬🇧 / 🇷🇺"
        sub = "Film Subbed 720p 👤 100"
        for seznam in ([ru.replace("👤 21", "👤 100"), yts], [rip, yts], [sub, yts]):
            self.assertEqual(ti.uredi(seznam, lambda t: t, ti.Zmoznosti(visina=1080), zelen_jezik="en", izvirni="en")[0], yts)

    def test_media_center_poda_jezik_samo_za_video(self):
        from core.os_media import MediaCenter
        self.assertEqual(MediaCenter._jezik_zvoka({"vrsta": "film", "jezik": "sl"}), {"zelen_jezik": "sl", "izvirni": "sl"})
        self.assertEqual(MediaCenter._jezik_zvoka({"vrsta": "film", "jezik": "en"})["zelen_jezik"], "en")
        self.assertEqual(MediaCenter._jezik_zvoka({"vrsta": "glasba"}), {})


if __name__ == "__main__":
    unittest.main()
