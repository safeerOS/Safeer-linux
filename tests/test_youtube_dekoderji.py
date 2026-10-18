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
        self.assertNotIn("obvesti(", odsek[:odsek.index("naprejPoNapaki()")])
        self.assertNotIn("predvajajIzVrste(1)", odsek)          # vedno prek stevca napak (naprejPoNapaki)

    def _vrsta(self, n, ponovi="0", ponovi_vse="1", napake=99):
        """Simulacija vrste v node: prvih `napake` skladb pade (mediaYtNapaka), nato vse igrajo."""
        import json
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("node ni namescen")
        js = (KOREN / "assets/os/os.js").read_text(encoding="utf-8")

        def fn(ime):
            return "function %s(" % ime + js.split("  function %s(" % ime, 1)[1].split("\n  }\n", 1)[0] + "\n  }\n"
        meja = js.split("var VRSTA_ZGODOVINA_NAJVEC = ", 1)[1].split(";", 1)[0]
        koda = ("var VRSTA_ZGODOVINA_NAJVEC = " + meja + ";\n" + "".join(fn(x) for x in (
            "naslednjiVVrsti", "predvajajIzVrste", "zapomniMestoVrste", "naprejPoNapaki", "redVrste", "jeVZivo", "vrstaPostaj",
            "zacetekKroga", "nakljucnoVklopljeno", "premesaj")) + """
var nast = %s, kat = { vrsta: [], vrstaMesto: 0, vrstaZgodovina: [], vrstaNapake: 0 }, odprtih = 0, ustavljeno = 0;
for (var i = 0; i < %d; i++) kat.vrsta.push("s" + i);
function vrstaNastavitev(k, p) { return k in nast ? nast[k] : p; }
function narisiVrsto() {}
function ustaviKatPredvajanje() { ustavljeno++; kat.vrsta = []; }
function odpriKatalogVnos(id) { odprtih++; }
var napake = %d, korakov = 0;
odprtih = 1;
while (kat.vrsta.length && korakov < 1000) {
  korakov++;
  if (napake > 0) { napake--; naprejPoNapaki(); }
  else { kat.vrstaNapake = 0; if (!predvajajIzVrste(1)) break; }   // mediaYt igra, nato mediaKonec
}
console.log(JSON.stringify({ odprtih: odprtih, ustavljeno: ustavljeno, korakov: korakov, zgodovina: kat.vrstaZgodovina.length }));
""" % (json.dumps({"ponovi": ponovi, "ponoviVse": ponovi_vse}), n, napake))
        izid = subprocess.run(["node", "-e", koda], capture_output=True, text=True, check=True).stdout
        return json.loads(izid)

    def test_vrsta_brez_delujocih_skladb_se_tiho_ustavi(self):
        """Regresija (pregled 18. 10. 2026): s »ponovi vse« ali »ponovi skladbo« vrsta, v kateri vse pade, ni vec
        krozila v nedogled - ustavi se, ko je vsaka skladba enkrat padla (ponovi skladbo: po dveh napakah)."""
        self.assertEqual(self._vrsta(5), {"odprtih": 5, "ustavljeno": 1, "korakov": 5, "zgodovina": 4})
        self.assertEqual(self._vrsta(1)["ustavljeno"], 1)
        r = self._vrsta(5, ponovi="1")
        self.assertEqual((r["odprtih"], r["ustavljeno"]), (2, 1))
        r = self._vrsta(5, ponovi_vse="0")
        self.assertEqual((r["odprtih"], r["ustavljeno"]), (5, 1))

    def test_uspeh_ponastavi_stevec_in_zgodovina_omejena(self):
        # 3 napake, nato vse igra: vrsta (ponovi vse) tece naprej do omejitve zanke; zgodovina ostane omejena
        r = self._vrsta(4, napake=3)
        self.assertEqual(r["ustavljeno"], 0)
        self.assertEqual(r["korakov"], 1000)
        self.assertEqual(r["zgodovina"], 200)


if __name__ == "__main__":
    unittest.main()
