"""Orodje tools/tema_cinnamon_prebarvaj.py: Mintove sivine in modra -> paleta Safeer (packaging/tema-cinnamon).

Varovala iz izkusenj (krog 91): (1) temen rob na temno modri povrsini se ne vidi - rob mora postati svetel;
(2) risba potrditvenega polja ne sme zadeti GUMBOV z razredom .check/.radio (napis kartice v oknu z izbiro je izginil);
(3) Mint-Y se med izdajami Minta spreminja, zato je izid unija vec razlicic osnove.
"""
import importlib.util
import os
import re
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMA = os.path.join(KOREN, "packaging", "tema-cinnamon", "Safeer-Cinnamon")


def orodje():
    spec = importlib.util.spec_from_file_location("tema_cinnamon_prebarvaj", os.path.join(KOREN, "tools", "tema_cinnamon_prebarvaj.py"))
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class TestPrebarvaj(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = orodje()

    def test_sivina_gre_na_modro_lestvico(self):
        izid = self.p.prebarvaj(".a { background-color: #383838; color: #DADADA; }")
        self.assertIn("background-color: #0e1727;", izid)
        self.assertIn("color: #eaf2ff;", izid)

    def test_mintova_modra_postane_poudarek_s_temno_pisavo(self):
        izid = self.p.prebarvaj(".a:checked { background-color: #0c75de; color: #ffffff; }")
        self.assertIn("background-color: #8ac7ff;", izid)
        # Bela pisava na svetlo modri bi bila neberljiva: postane temna.
        self.assertIn("color: #0b1424;", izid)

    def test_temen_rob_postane_viden(self):
        self.assertIn("border: 1px solid #22344f;", self.p.prebarvaj(".a { border: 1px solid #292929; }"))
        izid = self.p.prebarvaj(".a { box-shadow: inset 0 1px rgba(41, 41, 41, 0.5); }")
        self.assertIn("rgba(215, 234, 255, 0.21)", izid)
        # Ista temna sivina kot PODLAGA ostane temna (lestvica), ne postane rob.
        self.assertIn("background-color: #0b1422;", self.p.prebarvaj(".a { background-color: #292929; }"))

    def test_crna_bela_in_druge_barve_ostanejo(self):
        self.assertEqual(self.p.prebarvaj(".a { color: #ffffff; background-color: #ff0000; border-color: #000000; }"), "")
        self.assertEqual(self.p.prebarvaj(".a { color: #f27835; }"), "")

    def test_risba_polja_ne_zadene_gumbov(self):
        css = ('.radio:checked, radio:checked, treeview.radio:checked { -gtk-icon-source: -gtk-scaled('
               'url("assets/radio-checked-dark.png"), url("assets/radio-checked-dark@2.png")); }')
        izid = self.p.prebarvaj(css)
        self.assertTrue(izid.startswith("radio:checked, treeview.radio:checked {"), izid)
        self.assertIn("radial-gradient(", izid)
        self.assertIn("-gtk-icon-source: none;", izid)
        self.assertNotIn("url(", izid)
        # Pravilo samo z golim razredom odpade v celoti.
        self.assertEqual(self.p.prebarvaj('.check { -gtk-icon-source: url("assets/checkbox-unchecked-dark.png"); }'), "")

    def test_potrditveno_polje_in_stikalo_brez_slik(self):
        izid = self.p.prebarvaj('check:checked { -gtk-icon-source: url("assets/checkbox-checked-dark.png"); }')
        self.assertIn('-gtk-icontheme("object-select-symbolic")', izid)
        self.assertIn("background-color: #8ac7ff;", izid)
        izid = self.p.prebarvaj('switch:checked { background-image: url("assets/switch-active-dark.png"); }')
        self.assertIn("background-image: none;", izid)
        self.assertIn("background-color: #8ac7ff;", izid)

    def test_druge_slike_preskoci(self):
        # Pot do slike bi iz nase datoteke kazala v prazno.
        self.assertEqual(self.p.prebarvaj('.a { background-image: url("assets/nekaj.png"); }'), "")

    def test_unija_razlicic_osnove(self):
        stara = list(self.p.prebarvana_pravila(".a { color: #383838; } .samo-stara { color: #404040; }"))
        nova = list(self.p.prebarvana_pravila(".nova { color: #404040; } .a { color: #404040; background-color: #383838; }"))
        skupaj = self.p.zdruzi([stara, nova])
        self.assertEqual([s for s, _ in skupaj], [".nova", ".a", ".samo-stara"], "vrstni red najnovejse, starejsa na koncu")
        a = dict(skupaj)[".a"]
        self.assertEqual(a["color"], "#0f1a2a", "velja vrednost iz novejse razlicice")
        self.assertEqual(a["background-color"], "#0e1727")
        # Isti selektor na dveh mestih v osnovi ostane dve pravili (kaskada osnove se ohrani).
        dvakrat = list(self.p.prebarvana_pravila(".a { color: #383838; } .b { color: #404040; } .a { background-color: #404040; }"))
        self.assertEqual([s for s, _ in self.p.zdruzi([dvakrat])], [".a", ".b", ".a"])


class TestIzidVRepozitoriju(unittest.TestCase):
    def test_prebarvano_je_uvozeno_in_brez_slik(self):
        for mapa, rocna in (("gtk-3.0", "gtk.css"), ("gtk-4.0", "gtk.css"), ("cinnamon", "cinnamon.css")):
            pot = os.path.join(TEMA, mapa, "prebarvano.css")
            with open(pot, encoding="utf-8") as f:
                css = f.read()
            self.assertIn("SAMODEJNO: tools/tema_cinnamon_prebarvaj.py", css[:400], pot)
            self.assertNotIn("url(", css, "%s: pot do slike bi kazala v prazno" % pot)
            self.assertGreater(css.count("}\n"), 100, pot)
            with open(os.path.join(TEMA, mapa, rocna), encoding="utf-8") as f:
                self.assertIn("prebarvano.css", f.read(), "%s mora uvoziti prebarvano.css" % rocna)
        # Risba polja samo na pravih gradnikih (gumb z razredom .radio bi ostal brez napisa).
        with open(os.path.join(TEMA, "gtk-3.0", "prebarvano.css"), encoding="utf-8") as f:
            gtk3 = f.read()
        for selektor in re.findall(r"^([^{}\n]+) \{\n(?:  [^\n]*\n)*?  color: transparent;", gtk3, flags=re.M):
            for del_ in selektor.split(","):
                self.assertIsNone(re.match(r"\.(check|radio)(?![\w-])", del_.strip()), selektor)

    def test_gtk3_brez_psevdo_razredov_gtk4(self):
        # GTK 3 ne pozna :focus-visible; neznan psevdo-razred razveljavi celo pravilo.
        for tema in ("Safeer-Cinnamon", "Safeer-Cinnamon-Kontrast"):
            for ime in ("gtk.css", "gtk-dark.css", "prebarvano.css"):
                pot = os.path.join(os.path.dirname(TEMA), tema, "gtk-3.0", ime)
                if os.path.isfile(pot):
                    with open(pot, encoding="utf-8") as f:
                        self.assertNotIn(":focus-visible", f.read(), pot)


if __name__ == "__main__":
    unittest.main()
