"""Nastavitve delov Safeerja v Nastavitvah Safeer OS (lastnik, 15. 10. 2026: »vse je en proces«) in kuverta v pultu.

Kar je bilo prej samo v pladnju Controla (mape, programi, ves racunalnik in zaslon za televizor, predvajanje za druge
naprave, samozagon Controla), v meniju Spleta (nastavitve brskalnika) ali v desnem kliku na namizje (Prilagodi
namizje), je zdaj tudi v Nastavitvah Safeer OS. Gumbi so pravi: brez Controla v procesu skupine ni.
"""
import os
import re
import sys
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class _Postavka:
    def __init__(self, nastavi):
        self.nastavi, self.aktivna = nastavi, None

    def set_active(self, v):           # kot pladenj_sni.Postavka: toggled poklice nastavitev Controla
        if v != self.aktivna:
            self.aktivna = v
            self.nastavi(v)


class _Control:
    def __init__(self, s_pladnjem=True):
        self.klici = []
        self.programi = mock.Mock(vklopljeno=False)
        self.datoteke = mock.Mock()
        self.datoteke.mape.ves_disk = False
        self.zaslon = mock.Mock(vklopljeno=False)
        self.nastavitve = {"predvajanje_za_naprave": True}
        self.pladenj = None
        if s_pladnjem:
            self.pladenj = mock.Mock()
            self.pladenj.programi = _Postavka(self.nastavi_programe)
            self.pladenj.ves_disk = _Postavka(self.nastavi_ves_disk)
            self.pladenj.zaslon = _Postavka(self.nastavi_zaslon)
            self.pladenj.predvajanje = _Postavka(self.nastavi_predvajanje_za_naprave)
            self.pladenj.samozagon = _Postavka(self.nastavi_samozagon)

    def nastavi_programe(self, v):
        self.klici.append(("programi", v)); self.programi.vklopljeno = v

    def nastavi_ves_disk(self, v):
        self.klici.append(("ves_disk", v)); self.datoteke.mape.ves_disk = v

    def nastavi_zaslon(self, v):
        self.klici.append(("zaslon", v)); self.zaslon.vklopljeno = v

    def nastavi_predvajanje_za_naprave(self, v):
        self.klici.append(("predvajanje", v)); self.nastavitve["predvajanje_za_naprave"] = v

    def nastavi_samozagon(self, v):
        self.klici.append(("samozagon", v))

    def izberi_mape(self):
        self.klici.append(("mape",))


class NastavitveControla(unittest.TestCase):
    def setUp(self):
        import safeer_os
        self.so = safeer_os
        self.samozagon = mock.Mock()
        self.samozagon.je_vklopljen.return_value = True
        self.p = mock.patch.dict(sys.modules, {"safeer_control": mock.Mock(Samozagon=self.samozagon)})
        self.p.start()
        self.addCleanup(self.p.stop)
        self.addCleanup(self.so.en_proces.nastavi_control, None)

    def test_brez_controla_v_procesu_ni_skupine(self):
        self.so.en_proces.nastavi_control(None)
        self.assertIsNone(self.so.nastavitve_controla())
        self.assertIsNone(self.so.nastavi_control("programi", True))

    def test_stanje_in_sprememba_gresta_prek_pladnja(self):
        c = _Control()
        self.so.en_proces.nastavi_control(c)
        self.assertEqual(self.so.nastavitve_controla(), {"programi": False, "vesDisk": False, "zaslon": False,
                                                         "predajanje": True, "samozagon": True})
        self.assertTrue(self.so.nastavi_control("programi", True))
        self.assertTrue(self.so.nastavi_control("vesDisk", True))
        self.assertTrue(self.so.nastavi_control("zaslon", True))
        self.assertFalse(self.so.nastavi_control("predajanje", False))
        self.so.nastavi_control("samozagon", False)
        self.assertEqual(c.klici, [("programi", True), ("ves_disk", True), ("zaslon", True), ("predvajanje", False),
                                   ("samozagon", False)])
        self.assertIsNone(self.so.nastavi_control("neznano", True))

    def test_pod_safeer_cinnamon_brez_samozagona_controla(self):
        """Namizje Safeer Cinnamon zazene Control v istem procesu: lastni samozagon bi pomenil drugi proces."""
        c = _Control()
        self.so.en_proces.nastavi_control(c)
        with mock.patch.object(self.so.en_proces, "delovna_safeer_cinnamon", return_value=True):
            self.assertNotIn("samozagon", self.so.nastavitve_controla())
            self.assertIsNone(self.so.nastavi_control("samozagon", True))
        self.assertEqual(c.klici, [])

    def test_brez_pladnja_neposredno(self):
        c = _Control(s_pladnjem=False)
        self.so.en_proces.nastavi_control(c)
        self.assertTrue(self.so.nastavi_control("zaslon", True))
        self.assertEqual(c.klici, [("zaslon", True)])

    def test_most_mape_splet_namizje(self):
        c = _Control()
        self.so.en_proces.nastavi_control(c)
        o = mock.Mock(lupina=None, okno=None, _spletni=None, _spletni_namizje=None)
        o._peskovnik_na_voljo.return_value = True
        self.assertEqual(self.so.SafeerOS._nastavitve_delov(o)["namizje"], False)
        self.assertTrue(self.so.SafeerOS._nastavitev_dela(o, None, "mape"))
        self.assertEqual(c.klici, [("mape",)])
        # Splet: obstojeci primerek odpre svoje okno nastavitev.
        o._spletni = mock.Mock()
        self.assertTrue(self.so.SafeerOS._nastavitev_dela(o, None, "splet"))
        o._spletni._nastavitve.assert_called_once_with()
        # Namizje QML: dogodek »prilagodi« (Namizje.qml odpre Prilagodi); brez lupine gumba ni.
        self.assertFalse(self.so.SafeerOS._nastavitev_dela(o, None, "namizje"))
        o.lupina = mock.Mock()
        self.assertTrue(self.so.SafeerOS._nastavitev_dela(o, mock.Mock(spec=[]), "namizje"))
        o.lupina.dogodek.assert_called_once_with("prilagodi", {})
        self.assertIn('vrsta === "prilagodi"', beri("assets", "os", "qml", "Namizje.qml"))


class LupaBrezDatotekNaGlavniNiti(unittest.TestCase):
    """nastavitveDelov in nastavitevDela tecejo na glavni niti (slovar »glavna« v _obdelaj_klic). Stanje priljubljenih
    (Priljubljeno.stanje) pregleda vsako priljubljeno datoteko (stat, exists - tudi na omreznem ali odklopljenem disku),
    caka na zaklep niti in datoteke in ob pospravljanju zapise s fsync - zato so vsi klici priljubljeno* v ozadju.
    Nastavitev »lupa« (19. 10. 2026) se tega ne sme dotakniti na glavni niti (zamrznitev, varuh po 30 s SIGABRT)."""

    def test_branje_in_preklop_lupe_brez_stanja_priljubljenih(self):
        import tempfile
        import safeer_os as so
        from core import priljubljeno
        with tempfile.TemporaryDirectory() as d:
            p = priljubljeno.Priljubljeno(pot=os.path.join(d, "priljubljeno.json"))
            p.nastavi("lupa", "razsirjena")
            o = mock.Mock(lupina=mock.Mock(), okno=None, _spletni=None, _spletni_namizje=None)
            o._peskovnik_na_voljo.return_value = True
            o._priljubljeno.return_value = p
            niti = []

            def nit(target=None, **_k):
                niti.append(target)
                return mock.Mock()
            with mock.patch.object(priljubljeno.Priljubljeno, "stanje", side_effect=AssertionError("glavna nit")), \
                    mock.patch.object(so.threading, "Thread", side_effect=nit):
                self.assertEqual(so.SafeerOS._nastavitve_delov(o)["lupa"], "razsirjena")
                self.assertIs(so.SafeerOS._nastavitev_dela(o, None, "lupa", True), True)
            self.assertEqual(len(niti), 1)          # shranjevanje (fsync, dogodek s stanjem) v ozadju
            niti[0]()
            self.assertEqual(p.stanje()["nastavitve"]["lupa"], "zlozena")
            self.assertEqual(so.SafeerOS._nastavitve_delov(o)["lupa"], "zlozena")


class Vmesnik(unittest.TestCase):
    def test_besedila_v_vseh_jezikih(self):
        besedila = beri("assets", "os", "besedila.js")
        os_js = beri("assets", "os", "os.js")
        kljuci = set(re.findall(r't\("((?:nd|g)[A-Z][A-Za-z]*)"\)', os_js.split("function narisiNastavitveDelov", 1)[1]
                                .split("// ------------------------------------------------------------------ napajanje", 1)[0]))
        kljuci |= {k + "Pod" for k in re.findall(r'"(nd[A-Z][A-Za-z]*)"', os_js) if not k.endswith("Pod")}
        self.assertTrue({"gNapraveLink", "gSplet", "gNamizje", "ndMapePod"} <= kljuci, kljuci)
        for kljuc in kljuci:
            self.assertEqual(len(re.findall(r"\b%s: \"" % kljuc, besedila)), 6, kljuc)
        self.assertIn('id="nastavitveDelov"', beri("assets", "os", "index.html"))


class KuvertaSni(unittest.TestCase):
    def test_kuverta_je_sni_qt_samo_nadomestek(self):
        vir = beri("safeer_os.py")
        telo = vir.split("    def _namesti_kuverto(self):", 1)[1].split("\n    def ", 1)[0]
        self.assertLess(telo.index("pladenj_sni.Kuverta("), telo.index("os_lupina.Kuverta("))
        zacni = vir.split("    def _zacni_kuverto(self) -> None:", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("os_sporocila.ob_spremembi(", zacni)


if __name__ == "__main__":
    unittest.main()
