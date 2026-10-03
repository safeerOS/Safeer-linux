"""Računalnik ne zaspi sam, dokler Safeer predvaja ali dela za drugo napravo (core/budnost.py).

Ozadje (4. 10. 2026): v kodi ni bilo nobenega zadržanja. S privzetimi nastavitvami Linux Minta je ohranjevalnik zaslona
po 15 minutah prekril film v domačem predvajalniku, računalnik, ki je pretakal film televizorju, pa je smel zaspati
sredi predvajanja. Zadržimo samo samodejno spanje ob nedejavnosti - zaprt pokrov in ročno spanje ostaneta.
"""
import os
import sys
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)
from core import budnost  # noqa: E402


def beri(*pot):
    with open(os.path.join(KOREN, *pot), encoding="utf-8") as f:
        return f.read()


class LaznoVodilo:
    """Vodilo seje za preizkus: pozna samo naštete storitve, vsak Inhibit vrne nov žeton."""

    def __init__(self, storitve=("org.gnome.SessionManager",)):
        self.storitve, self.klici, self.zeton = set(storitve), [], 100

    def __call__(self, storitev, pot, vmesnik, metoda, podpis, vrednosti, vrne):
        self.klici.append((storitev, metoda, vrednosti))
        if storitev not in self.storitve:
            raise RuntimeError("storitve ni")
        if metoda == "Inhibit":
            self.zeton += 1
            return (self.zeton,)
        return ()


class TestBudnost(unittest.TestCase):
    def setUp(self):
        budnost._dejavnost.clear()

    def test_video_zadrzi_spanje_in_zaslon_zvok_samo_spanje(self):
        v = LaznoVodilo()
        b = budnost.Budnost("Safeer OS", v)
        self.assertTrue(b.nastavi("predvajanje", budnost.SPANJE | budnost.ZASLON, "Safeer predvaja"))
        self.assertEqual(v.klici, [("org.gnome.SessionManager", "Inhibit", ("Safeer OS", 0, "Safeer predvaja", 12))])
        # Enako stanje ne naredi nič: predvajalnik to kliče vsako sekundo.
        self.assertTrue(b.nastavi("predvajanje", budnost.SPANJE | budnost.ZASLON, "Safeer predvaja"))
        self.assertEqual(len(v.klici), 1)
        # Glasba: zaslon se sme ugasniti, računalnik pa ne zaspi.
        self.assertTrue(b.nastavi("predvajanje", budnost.SPANJE, "Safeer predvaja"))
        self.assertEqual([k[1:] for k in v.klici[1:]],
                         [("Uninhibit", (101,)), ("Inhibit", ("Safeer OS", 0, "Safeer predvaja", 4))])
        self.assertEqual(b.stanje(), {"predvajanje": 4})
        # Premor ali konec: sprostimo.
        self.assertFalse(b.nastavi("predvajanje", 0))
        self.assertEqual(v.klici[-1][1:], ("Uninhibit", (102,)))
        self.assertEqual(b.stanje(), {})

    def test_namizje_brez_upravitelja_seje_gnome(self):
        v = LaznoVodilo(("org.freedesktop.PowerManagement", "org.freedesktop.ScreenSaver"))
        b = budnost.Budnost("Safeer OS", v)
        self.assertTrue(b.nastavi("predvajanje", budnost.SPANJE | budnost.ZASLON, "x"))
        self.assertEqual([(k[0], k[1]) for k in v.klici],
                         [("org.gnome.SessionManager", "Inhibit"), ("org.freedesktop.PowerManagement", "Inhibit"),
                          ("org.freedesktop.ScreenSaver", "Inhibit")])
        b.sprosti_vse()
        self.assertEqual([(k[0], k[1], k[2]) for k in v.klici[3:]],
                         [("org.freedesktop.PowerManagement", "UnInhibit", (101,)), ("org.freedesktop.ScreenSaver", "UnInhibit", (102,))])

    def test_brez_vmesnikov_ne_poskusa_vsako_sekundo(self):
        v = LaznoVodilo(())
        b = budnost.Budnost("Safeer OS", v)
        self.assertFalse(b.nastavi("predvajanje", budnost.SPANJE))
        poskusov = len(v.klici)
        self.assertFalse(b.nastavi("predvajanje", budnost.SPANJE))
        self.assertEqual(len(v.klici), poskusov, "isto stanje ne sme znova klicati vodila")
        self.assertEqual(b.stanje(), {})
        b.sprosti_vse()                                    # nič ne držimo: brez klica in brez napake
        self.assertEqual(len(v.klici), poskusov)

    def test_pomoc_drugi_napravi_po_dejavnosti(self):
        v = LaznoVodilo()
        b = budnost.Budnost("Safeer Control", v)
        self.assertFalse(b.po_dejavnosti("pomoc"))
        self.assertEqual(v.klici, [])
        budnost.dotik("pomoc")                             # naprava bere tok
        self.assertTrue(b.po_dejavnosti("pomoc", "Safeer pretaka"))
        # Samo spanje: zaslon računalnika, ki pretaka televizorju, se sme ugasniti.
        self.assertEqual(v.klici[-1], ("org.gnome.SessionManager", "Inhibit", ("Safeer Control", 0, "Safeer pretaka", budnost.SPANJE)))
        self.assertTrue(b.po_dejavnosti("pomoc", "Safeer pretaka"))
        self.assertEqual(len(v.klici), 1)
        budnost._dejavnost["pomoc"] -= 200                 # več kot dve minuti in pol brez poslanega kosa
        self.assertFalse(b.po_dejavnosti("pomoc"))
        self.assertEqual(v.klici[-1][1:], ("Uninhibit", (101,)))

    def test_razlogi_so_neodvisni(self):
        v = LaznoVodilo()
        b = budnost.Budnost("Safeer", v)
        b.nastavi("predvajanje", budnost.SPANJE | budnost.ZASLON)
        b.nastavi("pomoc", budnost.SPANJE)
        self.assertEqual(b.stanje(), {"predvajanje": 12, "pomoc": 4})
        b.nastavi("predvajanje", 0)
        self.assertEqual(b.stanje(), {"pomoc": 4})

    def test_pokrov_in_rocno_spanje_ostaneta(self):
        # Zadržanja na ravni sistema (logind) bi prenosnik z zaprtim pokrovom pustila budnega v torbi.
        vir = beri("core", "budnost.py")
        for niz in ("login1", "handle-lid-switch", "systemd-inhibit"):
            self.assertNotIn(niz, vir)

    def test_povezava_z_vodilom_ostane(self):
        # Zadržanje pripada povezavi: če jo po klicu spustimo, ga upravitelj seje takoj odstrani (izmerjeno v Cinnamonu 6.6).
        vir = beri("core", "budnost.py")
        self.assertIn("global _vodilo", vir)
        self.assertIn("if _vodilo is None or _vodilo.is_closed():", vir)


class TestVgradnja(unittest.TestCase):
    """Kje se budnost uporablja (safeer_os.py in safeer_control.py ob uvozu potrebujeta GTK, zato beremo izvorno kodo)."""

    def test_predvajalnik(self):
        vir = beri("safeer_os.py")
        tik = vir[vir.index("    def _medijski_tik(self) -> bool:"):vir.index("    def _pot_lokalnega_videa(")]
        self.assertIn("self._budnost_predvajanja()", tik)
        self.assertLess(tik.index("self._budnost_predvajanja()"), tik.index('stanje == "predvaja"'),
                        "tudi premor in konec morata priti do budnosti (sprostitev)")
        telo = vir[vir.index("    def _budnost_predvajanja(self) -> None:"):vir.index("    def _medijski_tik(self) -> bool:")]
        self.assertIn('if servis is not None and servis.stanje == "predvaja":', telo)
        self.assertIn("budnost.SPANJE | (budnost.ZASLON if self._medij_ima_sliko() else 0)", telo)
        konec = vir[vir.index("    def _koncaj(self) -> None:"):vir.index("    def _koncaj(self) -> None:") + 700]
        self.assertIn("self._budnost.sprosti_vse()", konec)

    def test_control_in_streznik(self):
        control = beri("safeer_control.py")
        self.assertIn("GLib.timeout_add_seconds(30, self._budnost_tik)", control)
        self.assertIn('self._budnost.po_dejavnosti("pomoc", "Safeer pretaka na drugo napravo")', control)
        self.assertEqual(beri("core", "link_datoteke.py").count("budnost.dotik()"), 2, "datoteka z diska in tok torrenta")
        self.assertEqual(beri("core", "link_sprotno.py").count("budnost.dotik()"), 1, "sprotno pretvorjen tok")

    def test_poslana_datoteka_je_dejavnost(self):
        """Strežnik datotek ob vsakem poslanem kosu zabeleži dejavnost; samo glava (HEAD) ni branje."""
        import io
        import tempfile
        from core import link_datoteke

        class Obravnava:
            def __init__(self):
                self.headers, self.wfile, self.koda = {}, io.BytesIO(), 0

            def send_response(self, koda):
                self.koda = koda

            def send_header(self, *_a):
                pass

            def end_headers(self):
                pass

        budnost._dejavnost.clear()
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            f.write(b"film" * 1000)
            f.flush()
            glava = Obravnava()
            link_datoteke._poslji_datoteko(glava, f.name, True)
            self.assertEqual((glava.koda, glava.wfile.getvalue()), (200, b""))
            self.assertFalse(budnost.dejavno("pomoc"))
            celota = Obravnava()
            link_datoteke._poslji_datoteko(celota, f.name, False)
            self.assertEqual(len(celota.wfile.getvalue()), 4000)
        self.assertTrue(budnost.dejavno("pomoc"))
        v = LaznoVodilo()
        self.assertTrue(budnost.Budnost("Safeer Control", v).po_dejavnosti("pomoc", "Safeer pretaka na drugo napravo"))

    def test_modul_je_v_obeh_tovorih(self):
        for skripta in ("install_os_payload.sh", "install_control_payload.sh"):
            self.assertIn("for modul in budnost ", beri("packaging", skripta), skripta)


if __name__ == "__main__":
    unittest.main()
