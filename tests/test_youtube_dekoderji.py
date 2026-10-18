"""YouTube v Medijskem centru (18. 10. 2026): napaka strojnega dekoderja (VA-API) ni prepoved vgradnje.

- core/video_dekoderji.py: strojni dekoderji imajo rang NONE (programsko dekodiranje), razen ce uporabnik zeli drugace.
- Seznami YouTube (tocni posnetki uporabnika) se nikoli ne zamenjajo z zadetkom iskanja.
- Enkratna selitev vrne posnetke, ki jih je Safeer do 1.0.127 zaradi napake dekoderja zamenjal (izvirni = prvi zavrnjeni).
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import os_media, uvoz_seznama as u, video_dekoderji as vd

KOREN = Path(__file__).resolve().parent.parent


class DekoderjiTests(unittest.TestCase):
    def test_strojni_dekoderji_rang_none_obstojece_ostane(self):
        env = {"GST_PLUGIN_FEATURE_RANK": "vavp9dec:PRIMARY,neki:MAX"}
        self.assertTrue(vd.programsko(env))
        deli = env["GST_PLUGIN_FEATURE_RANK"].split(",")
        self.assertIn("vavp9dec:PRIMARY", deli)            # izrecna izbira uporabnika ostane
        self.assertIn("neki:MAX", deli)
        for ime in ("vaav1dec", "vah264dec", "vaapivp9dec"):
            self.assertIn(ime + ":NONE", deli)
        vd.programsko(env)                                   # drugic nic ne podvoji
        self.assertEqual(len(env["GST_PLUGIN_FEATURE_RANK"].split(",")), len(deli))

    def test_uporabnik_lahko_obdrzi_strojno(self):
        env = {"SAFEER_STROJNO_DEKODIRANJE": "1"}
        self.assertFalse(vd.programsko(env))
        self.assertNotIn("GST_PLUGIN_FEATURE_RANK", env)

    def test_vstopne_tocke_pred_webkitom(self):
        for ime in ("safeer_os.py", "safeer_brskalnik.py", "safeer_control.py"):
            besedilo = (KOREN / ime).read_text(encoding="utf-8")
            klic = besedilo.index("video_dekoderji.programsko()")
            self.assertLess(klic, besedilo.index('"WebKit"') if '"WebKit"' in besedilo else len(besedilo), ime)


class SeznamiYoutubeTests(unittest.TestCase):
    def _seznami(self, mapa, podatki):
        Path(mapa, "seznami.json").write_text(json.dumps(podatki), encoding="utf-8")
        return os_media.MediaCenter(mapa, roots=[])

    def test_selitev_vrne_izvirne_posnetke_samo_na_seznamih_youtube(self):
        with tempfile.TemporaryDirectory() as mapa:
            m = self._seznami(mapa, [
                {"ime": "Oglej si pozneje", "vir": "YouTube", "yt_kljuc": "WL", "cas": 1, "skladbe": [
                    {"naslov": "A", "youtube": "ccccccccccc", "zavrnjeni": ["aaaaaaaaaaa", "bbbbbbbbbbb"]},
                    {"naslov": "B", "youtube": "ddddddddddd"}]},
                {"ime": "Top", "vir": "Spotify", "cas": 1, "skladbe": [
                    {"naslov": "C", "youtube": "fffffffffff", "zavrnjeni": ["eeeeeeeeeee"]}]}])
            vsi = {x["ime"]: x for x in m._seznami_beri()}
            a = vsi["Oglej si pozneje"]["skladbe"][0]
            self.assertEqual(a["youtube"], "aaaaaaaaaaa")
            self.assertNotIn("zavrnjeni", a)
            self.assertIn("aaaaaaaaaaa", a["slika"])
            self.assertGreater(vsi["Oglej si pozneje"]["cas"], 1)       # sinhronizacija s Linkom vzame nase stanje
            self.assertEqual(vsi["Top"]["skladbe"][0]["youtube"], "fffffffffff")  # uvozen seznam (iskanje) ostane
            na_disku = json.loads(Path(mapa, "seznami.json").read_text(encoding="utf-8"))
            self.assertEqual(na_disku[0]["skladbe"][0]["youtube"], "aaaaaaaaaaa")

    def test_seznam_youtube_se_nikoli_ne_zamenja(self):
        with tempfile.TemporaryDirectory() as mapa:
            m = self._seznami(mapa, [{"ime": "Moji", "vir": "YouTube", "cas": 1, "skladbe": [
                {"naslov": "A", "izvajalec": "X", "youtube": "aaaaaaaaaaa"}]}])
            vnos = m.seznam("Moji")["vnosi"][0]
            with mock.patch.object(u, "najdi", side_effect=AssertionError("ne isce")):
                self.assertIsNone(m.seznam_posnetek(vnos["id"], zamenjaj=True))
            self.assertEqual(m.seznam("Moji")["vnosi"][0]["youtube"], "aaaaaaaaaaa")

    def test_stran_ne_zamenja_ob_napaki_dekoderja(self):
        js = (KOREN / "assets/os/os.js").read_text(encoding="utf-8")
        i = js.index('vrsta === "mediaYtNapaka"')
        odsek = js[i:i + 900]
        self.assertLess(odsek.index("podatki.zamenjaj === false"), odsek.index('klic("mediaSeznamZamenjava"'))
        # Lastnik: napak predvajalnika uporabniku ne izpisujemo - lovilci napak tiho poskrbijo za naslednjo vsebino.
        self.assertNotIn("obvesti(", odsek[:odsek.index("ustaviKatPredvajanje")])


if __name__ == "__main__":
    unittest.main()
