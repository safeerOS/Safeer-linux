"""Nova mapa / datoteka v Datotekah Safeer OS (core/os_datoteke): nic se ne prepise, ime je varno."""
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from core import os_datoteke


class Ustvari(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_mapa_in_drugo_ime(self):
        a = os_datoteke.ustvari_mapo(self.mapa, "Nova mapa")
        b = os_datoteke.ustvari_mapo(self.mapa, "Nova mapa")
        self.assertTrue(a["ok"] and b["ok"])
        self.assertEqual(os.path.basename(b["pot"]), "Nova mapa (2)")
        self.assertTrue(os.path.isdir(a["pot"]) and os.path.isdir(b["pot"]))

    def test_datoteke_ne_prepisejo(self):
        with open(os.path.join(self.mapa, "zapiski.txt"), "w") as f:
            f.write("moje")
        r = os_datoteke.ustvari_datoteko(self.mapa, "zapiski", "besedilo")
        self.assertEqual(os.path.basename(r["pot"]), "zapiski (2).txt")
        with open(os.path.join(self.mapa, "zapiski.txt")) as f:
            self.assertEqual(f.read(), "moje")

    def test_nevarna_imena(self):
        for ime in ("../ven", ".skrita", "a/b", ""):
            r = os_datoteke.ustvari_mapo(self.mapa, ime) if ime else {"ok": False}
            if ime:
                self.assertFalse(r["ok"], ime)
        self.assertEqual(os.listdir(self.mapa), [])

    def test_odf_je_veljaven(self):
        for vrsta, konc in (("dokument", ".odt"), ("preglednica", ".ods"), ("predstavitev", ".odp")):
            r = os_datoteke.ustvari_datoteko(self.mapa, "Nov", vrsta)
            self.assertTrue(r["ok"], vrsta)
            self.assertTrue(r["pot"].endswith(konc))
            with zipfile.ZipFile(r["pot"]) as z:
                self.assertEqual(z.namelist()[0], "mimetype")
                self.assertEqual(z.getinfo("mimetype").compress_type, zipfile.ZIP_STORED)

    @unittest.skipUnless(shutil.which("soffice"), "LibreOffice ni namescen")
    def test_libreoffice_odpre_dokument(self):
        r = os_datoteke.ustvari_datoteko(self.mapa, "Preizkus", "dokument")
        izhod = tempfile.mkdtemp()
        try:
            subprocess.run(["soffice", "--headless", "-env:UserInstallation=file://" + izhod + "/profil",
                            "--convert-to", "txt", "--outdir", izhod, r["pot"]],
                           capture_output=True, timeout=90)
            self.assertTrue(os.path.isfile(os.path.join(izhod, "Preizkus.txt")))
        finally:
            shutil.rmtree(izhod, ignore_errors=True)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root sme pisati povsod (CI vsebnik)")
    def test_ni_dovoljenja(self):
        r = os_datoteke.ustvari_mapo("/", "safeer-preizkus")
        self.assertFalse(r["ok"])
        self.assertEqual(r["napaka"], "ni_dovoljenja")

    def test_preimenuj_in_smeti(self):
        r = os_datoteke.ustvari_datoteko(self.mapa, "a", "besedilo")
        p = os_datoteke.preimenuj(r["pot"], "b.txt")
        self.assertTrue(p["ok"])
        self.assertTrue(os.path.isfile(os.path.join(self.mapa, "b.txt")))
        self.assertFalse(os_datoteke.v_smeti(os.path.expanduser("~"))["ok"])


if __name__ == "__main__":
    unittest.main()
