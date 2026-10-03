"""Safeer od vklopa (packaging/tema-cinnamon/od-vklopa): zagonski in prijavni zaslon v videzu Safeer.

Pomocnik tece kot root, zato preizkusamo predvsem to, da (1) spremeni samo svoje kljuce in pusti vse ostalo,
(2) izklop vrne natanko prejsnje stanje - tudi, ce datoteke prej ni bilo, in (3) ne povozi tistega, kar je
uporabnik medtem spremenil sam. Sistemskih ukazov preizkus ne klice (laznjak `tek`).
"""
import importlib.machinery
import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMA = os.path.join(KOREN, "packaging", "tema-cinnamon")


def _modul():
    pot = os.path.join(TEMA, "od-vklopa")
    nalagalnik = importlib.machinery.SourceFileLoader("od_vklopa", pot)
    spec = importlib.util.spec_from_loader("od_vklopa", nalagalnik)
    m = importlib.util.module_from_spec(spec)
    nalagalnik.exec_module(m)
    return m


M = _modul()


class Alternative:
    """Laznjak za update-alternatives in update-initramfs."""

    def __init__(self, status="auto", vrednost="/usr/share/plymouth/themes/mint-logo/mint-logo.plymouth", initramfs=0):
        self.status, self.vrednost, self.initramfs, self.klici = status, vrednost, initramfs, []
        self.samodejna = vrednost

    def __call__(self, ukaz):
        self.klici.append(ukaz[1:])
        if ukaz[0] == M.INITRAMFS:
            return self.initramfs, "napaka initramfs" if self.initramfs else ""
        if ukaz[1] == "--query":
            return 0, "Name: default.plymouth\nLink: x\nStatus: %s\nBest: b\nValue: %s\n\nAlternative: %s\nPriority: 200\n" % (
                self.status, self.vrednost, self.samodejna)
        if ukaz[1] == "--set":
            self.status, self.vrednost = "manual", ukaz[3]
        elif ukaz[1] == "--auto":
            self.status, self.vrednost = "auto", self.samodejna
        elif ukaz[1] == "--remove" and self.vrednost == ukaz[3]:
            self.status, self.vrednost = "auto", self.samodejna
        return 0, ""


class TestKljuci(unittest.TestCase):
    def test_nastavi_ohrani_ostalo(self):
        prej = "# moje nastavitve\n[Greeter]\nbackground=/x/moje.jpg\nshow-hostname=false\n\n[Drugo]\nkljuc=1\n"
        novo = M.nastavi_kljuce(prej, M.KLJUCI)
        self.assertIn("# moje nastavitve", novo)
        self.assertIn("show-hostname=false", novo)
        self.assertIn("[Drugo]\nkljuc=1", novo)
        self.assertEqual(M.preberi_kljuce(novo, M.KLJUCI), M.KLJUCI)
        self.assertEqual(novo.count("background="), 1)
        # Novi kljuci so v odseku [Greeter], ne za [Drugo].
        self.assertLess(novo.index("theme-name="), novo.index("[Drugo]"))

    def test_prazna_datoteka_dobi_odsek(self):
        novo = M.nastavi_kljuce("", M.KLJUCI)
        self.assertTrue(novo.startswith("[Greeter]\n"))
        self.assertEqual(M.preberi_kljuce(novo, M.KLJUCI), M.KLJUCI)

    def test_none_odstrani_kljuc(self):
        novo = M.nastavi_kljuce("[Greeter]\nbackground=/a\ntheme-name=B\n", {"background": None, "theme-name": "C"})
        self.assertEqual(novo, "[Greeter]\ntheme-name=C\n")

    def test_kljuc_drugega_odseka_ni_nas(self):
        self.assertEqual(M.preberi_kljuce("[Drugo]\nbackground=/a\n", M.KLJUCI)["background"], None)


class TestVklopIzklop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="od-vklopa-")
        self.conf = os.path.join(self.tmp, "etc", "slick-greeter.conf")
        self.tema = os.path.join(self.tmp, "safeer.plymouth")
        self.greeter = os.path.join(self.tmp, "slick-greeter")
        for pot in (self.tema, self.greeter):
            open(pot, "w").close()
        self.izpis = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _o(self, alt, greeter=True):
        return M.OdVklopa(stanje=os.path.join(self.tmp, "stanje"), conf=self.conf, tema=self.tema, tek=alt,
                          greeterji=(self.greeter,) if greeter else (), izpis=self.izpis.append,
                          obstaja=lambda pot: True)      # preizkus ne sme biti odvisen od orodij na racunalniku

    def test_brez_datoteke_vklop_izklop_ne_pusti_sledi(self):
        alt = Alternative()
        o = self._o(alt)
        self.assertEqual(o.vklopi(), 0)
        self.assertEqual(M.preberi_kljuce(open(self.conf).read(), M.KLJUCI), M.KLJUCI)
        self.assertEqual((alt.status, alt.vrednost), ("manual", self.tema))
        self.assertIn(["-u"], alt.klici)
        self.assertTrue(o.vklopljeno())
        self.assertEqual(o.izklopi(), 0)
        self.assertFalse(os.path.exists(self.conf), "datoteke prej ni bilo, zato je tudi po izklopu ne sme biti")
        self.assertEqual((alt.status, alt.vrednost), ("auto", alt.samodejna))
        self.assertFalse(o.vklopljeno())

    def test_izklop_vrne_prejsnje_in_pusti_uporabnikove_spremembe(self):
        os.makedirs(os.path.dirname(self.conf))
        izvirnik = "[Greeter]\nbackground=/x/moje.jpg\nshow-hostname=false\n"
        with open(self.conf, "w") as f:
            f.write(izvirnik)
        rocna = "/usr/share/plymouth/themes/bgrt/bgrt.plymouth"
        alt = Alternative(status="manual", vrednost=rocna)
        o = self._o(alt)
        self.assertEqual(o.vklopi(), 0)
        self.assertEqual(o.vklopi(), 0, "ponovni vklop ne sme povoziti zapomnjenega stanja")
        # Uporabnik medtem v Mintovih nastavitvah izbere drugo temo prijavnega zaslona: ta ostane.
        with open(self.conf) as f:
            b = f.read().replace("theme-name=Safeer-Cinnamon", "theme-name=Mint-Y-Dark")
        with open(self.conf, "w") as f:
            f.write(b)
        self.assertEqual(o.izklopi(), 0)
        with open(self.conf) as f:
            po = f.read()
        self.assertIn("background=/x/moje.jpg", po)
        self.assertIn("show-hostname=false", po)
        self.assertIn("theme-name=Mint-Y-Dark", po)
        self.assertNotIn("background-color", po)
        # Rocno izbrano temo vrnemo le, ce se obstaja; sicer samodejna izbira sistema.
        self.assertEqual((alt.status, alt.vrednost), ("manual", rocna) if os.path.exists(rocna) else ("auto", alt.samodejna))

    def test_neuspel_initramfs_ne_pozabi_stanja(self):
        alt = Alternative(initramfs=1)
        o = self._o(alt)
        self.assertEqual(o.vklopi(), 1)
        self.assertTrue(o.vklopljeno(), "po neuspehu mora izklop se vedno znati vrniti prejsnje stanje")

    def test_sistem_brez_plymoutha_in_greeterja_ostane_kot_je(self):
        alt = Alternative()
        o = M.OdVklopa(stanje=os.path.join(self.tmp, "stanje"), conf=self.conf, tema=self.tema, tek=alt, greeterji=(),
                       izpis=self.izpis.append, obstaja=lambda pot: False)
        self.assertEqual(o.vklopi(), 0)
        self.assertFalse(os.path.exists(self.conf))
        self.assertEqual(alt.klici, [])
        self.assertEqual(o.izklopi(), 0)

    def test_brez_teme_nic_ne_spremeni(self):
        os.remove(self.tema)
        alt = Alternative()
        self.assertEqual(self._o(alt).vklopi(), 1)
        self.assertFalse(os.path.exists(self.conf))
        self.assertEqual(alt.klici, [])

    def test_izklop_brez_vklopa_je_prazen(self):
        alt = Alternative()
        self.assertEqual(self._o(alt).izklopi(), 0)
        self.assertEqual(alt.klici, [])


class TestPaket(unittest.TestCase):
    def test_slike_zagonskega_zaslona(self):
        mapa = os.path.join(TEMA, "plymouth", "safeer")
        for ime in ("safeer.plymouth", "watermark.png", "throbber-0001.png", "throbber-0030.png", "animation-0030.png",
                    "bullet.png", "entry.png", "lock.png"):
            self.assertTrue(os.path.isfile(os.path.join(mapa, ime)), ime)
        with open(os.path.join(mapa, "safeer.plymouth")) as f:
            opis = f.read()
        self.assertIn("ImageDir=/usr/share/plymouth/themes/safeer", opis)
        self.assertIn("ModuleName=two-step", opis)

    def test_pomocnik_ne_bere_poti_od_zunaj(self):
        with open(os.path.join(TEMA, "od-vklopa")) as f:
            koda = f.read()
        self.assertTrue(koda.startswith("#!/usr/bin/python3 -I\n"))
        self.assertNotIn("os.environ", koda)
        self.assertNotIn("shell=True", koda)
        self.assertIn('len(argi) == 2', koda)

    def test_pravilo_polkit_kaze_na_pomocnika(self):
        with open(os.path.join(TEMA, "si.safeer.cinnamon.od-vklopa.policy")) as f:
            pravilo = f.read()
        self.assertIn(">/usr/lib/safeer-cinnamon/od-vklopa</annotate>", pravilo)
        self.assertEqual(len(re.findall(r">auth_admin<", pravilo)), 3, "sprememba zagona vedno zahteva skrbnisko geslo")

    def test_ukaz_pozna_od_vklopa(self):
        with open(os.path.join(TEMA, "safeer-cinnamon")) as f:
            s = f.read()
        for niz in ("--od-vklopa)", "--od-vklopa-izklopi)", 'pkexec "$POMOCNIK"'):
            self.assertIn(niz, s)
        self.assertEqual(subprocess.run(["bash", "-n", os.path.join(TEMA, "safeer-cinnamon")]).returncode, 0)

    @unittest.skipUnless(shutil.which("dpkg-deb"), "dpkg-deb ni namescen")
    def test_paket_vsebuje_od_vklopa(self):
        r = subprocess.run(["bash", os.path.join(KOREN, "build_cinnamon_tema_deb.sh")], cwd=KOREN, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(KOREN, "packaging", "VERSION_CINNAMON")) as f:
            deb = os.path.join(KOREN, "safeer-cinnamon_%s_all.deb" % f.read().strip())
        try:
            vsebina = subprocess.run(["dpkg-deb", "-c", deb], capture_output=True, text=True).stdout
            for pot in ("./usr/lib/safeer-cinnamon/od-vklopa", "./usr/share/plymouth/themes/safeer/safeer.plymouth",
                        "./usr/share/plymouth/themes/safeer/watermark.png",
                        "./usr/share/polkit-1/actions/si.safeer.cinnamon.od-vklopa.policy",
                        "./usr/share/applications/safeer-cinnamon-od-vklopa.desktop"):
                self.assertIn(pot, vsebina)
            self.assertRegex(vsebina, r"-rwxr-xr-x root/root\s+\d+ \S+ \S+ \./usr/lib/safeer-cinnamon/od-vklopa")
            prerm = subprocess.run(["dpkg-deb", "-I", deb, "prerm"], capture_output=True, text=True).stdout
            self.assertIn("od-vklopa izklopi", prerm, "odstranitev paketa mora vrniti zagonski in prijavni zaslon")
        finally:
            os.remove(deb)


if __name__ == "__main__":
    unittest.main()
