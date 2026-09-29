import unittest

from core.os_mediji import izberi_nivo, je_neposredni_medij


class NivoMedijaTests(unittest.TestCase):
    def test_neposredne_koncnice_gredo_v_gstreamer(self):
        for naslov in (
            "https://example.test/film.MP4?token=skrivnost",
            "https://radio.test/tok.m3u8#v-zivo",
            "https://tv.test/prenos.mpd?token=abc",
            "http://example.test/pesem.mp3",
            "https://example.test/posnetek.webm",
            "https://example.test/zvok.ogg",
        ):
            self.assertTrue(je_neposredni_medij(naslov), naslov)
            self.assertEqual(izberi_nivo(naslov), "neposredno")

    def test_spletna_stran_gre_najprej_v_lahki_pogled(self):
        self.assertEqual(izberi_nivo("https://365.rtvslo.si/oddaja/nekaj"), "lahki_splet")
        self.assertEqual(izberi_nivo("https://www.youtube.com/watch?v=abc"), "lahki_splet")

    def test_nevarne_in_nepopolne_sheme_so_zavrnjene(self):
        for naslov in ("javascript:alert(1)", "file:///tmp/video.mp4", "data:video/mp4,x", "https:///brez-gostitelja"):
            self.assertEqual(izberi_nivo(naslov), "", naslov)


if __name__ == "__main__":
    unittest.main()
