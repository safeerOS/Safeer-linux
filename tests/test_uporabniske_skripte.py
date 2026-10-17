"""Skripte, ki jih uporabnik sam uvozi (core/uporabniske_skripte.py): JavaScript v strani Spotify, shell na ukaz."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core import uporabniske_skripte as us

KOREN = Path(__file__).resolve().parent.parent


class TestSkripte(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="skripte-")
        self.stari = os.environ.get("SAFEER_SKRIPTE_MAPA")
        os.environ["SAFEER_SKRIPTE_MAPA"] = self.mapa

    def tearDown(self):
        if self.stari is None:
            os.environ.pop("SAFEER_SKRIPTE_MAPA", None)
        else:
            os.environ["SAFEER_SKRIPTE_MAPA"] = self.stari
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_uvoz_je_privzeto_izklopljen_in_zasebni(self):
        r = us.uvozi("pomozna.js", "console.log(1)")
        self.assertTrue(r["ok"])
        s = r["skripta"]
        self.assertEqual((s["vrsta"], s["vklopljena"]), ("js", False))
        self.assertEqual(us.aktivne_js(), [])
        pot = Path(self.mapa) / ("%s.js" % s["id"])
        self.assertEqual(oct(pot.stat().st_mode & 0o777), "0o600")
        self.assertEqual(oct(Path(self.mapa).stat().st_mode & 0o777), "0o700")

    def test_vklop_odstranitev_in_aktivne(self):
        s = us.uvozi("a.js", "window.x = 1;")["skripta"]
        self.assertTrue(us.vklopi(s["id"], True)["ok"])
        self.assertEqual(us.aktivne_js(), [{"ime": "a.js", "koda": "window.x = 1;"}])
        self.assertTrue(us.odstrani(s["id"])["ok"])
        self.assertEqual((us.seznam(), us.aktivne_js()), ([], []))
        self.assertFalse((Path(self.mapa) / ("%s.js" % s["id"])).exists())
        self.assertEqual(us.vklopi("0" * 12, True)["napaka"], "ni_skripte")

    def test_neveljavni_vnosi(self):
        self.assertEqual(us.uvozi("a.txt", "x")["napaka"], "vrsta")
        self.assertEqual(us.uvozi("a.js", "  ")["napaka"], "prazno")
        self.assertEqual(us.uvozi("a.js", "x" * (us.NAJVEC_BAJTOV + 1))["napaka"], "velikost")
        self.assertEqual(us.uvozi("a.js", "a\x00b")["napaka"], "velikost")
        # ime brez poti, brez krmilnih znakov
        s = us.uvozi("../../etc/\x07zlo.sh", "echo")["skripta"]
        self.assertEqual(s["ime"], "zlo.sh")

    def test_shell_tece_samo_na_ukaz_in_ujame_izpis(self):
        s = us.uvozi("pozdrav.sh", "echo zdravo; echo napaka >&2; exit 3")["skripta"]
        r = us.zazeni_shell(s["id"])
        self.assertEqual((r["ok"], r["koda"]), (False, 3))
        self.assertIn("zdravo", r["izpis"])
        self.assertIn("napaka", r["izpis"])
        # skripta JavaScript se ne zazene kot shell
        j = us.uvozi("a.js", "echo ne")["skripta"]
        self.assertEqual(us.zazeni_shell(j["id"])["napaka"], "ni_skripte")

    def test_shell_ima_mejo_casa(self):
        s = us.uvozi("pocasi.sh", "echo zacetek; sleep 5")["skripta"]
        r = us.zazeni_shell(s["id"], cas=0.5)
        self.assertEqual(r["napaka"], "cas")

    def test_kazalo_z_neveljavnimi_zapisi_se_ne_podre(self):
        Path(self.mapa).mkdir(parents=True, exist_ok=True)
        (Path(self.mapa) / "kazalo.json").write_text(json.dumps([{"id": "../x", "vrsta": "js", "ime": "x"}, 5, None]))
        self.assertEqual(us.seznam(), [])


class TestVezava(unittest.TestCase):
    def test_zagon_spotifyja_da_skripte_v_sejo_in_main_js_jih_vstavi(self):
        racun = (KOREN / "core" / "spotify_racun.py").read_text(encoding="utf-8")
        self.assertIn('"--skripte="', racun.replace("'", '"'))
        self.assertIn("uporabniske_skripte.aktivne_js()", racun)
        main = (KOREN / "assets" / "safeer_drm" / "main.js").read_text(encoding="utf-8")
        self.assertIn("argumenti.skripte", main)
        self.assertIn("uporabniskeSkripte.reduce", main)

    def test_vmesnik_in_besedila(self):
        js = (KOREN / "assets" / "os" / "os.js").read_text(encoding="utf-8")
        bes = (KOREN / "assets" / "os" / "besedila.js").read_text(encoding="utf-8")
        for klic in ("mediaSkripte", "mediaSkriptaUvozi", "mediaSkriptaVklop", "mediaSkriptaOdstrani", "mediaSkriptaZazeni"):
            self.assertIn('"%s"' % klic, js + (KOREN / "core" / "os_katalog.py").read_text(encoding="utf-8"))
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            self.assertIn('Object.assign(BESEDILA_OS.%s, {"skriptePrilagodi"' % jezik, bes)
        self.assertIn("skriptaOpozorilo", js)           # opozorilo pred uvozom
        self.assertIn("uporabniske_skripte", (KOREN / "packaging" / "install_os_payload.sh").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
