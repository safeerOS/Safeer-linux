"""Deljenje zaslona v Safeer Controlu je brez izbire uporabnika pripravljeno (14. 10. 2026).

Varno, ker zaslon vsaka druga naprava dobi sele z zmoznostjo »z«, ki jo uporabnik odpre NA TEM racunalniku (za vsako
napravo posebej, rocno ali z »Dovoli« v obvestilu s prosnjo); izrecen izklop uporabnika velja naprej.
"""
import os
import unittest

import pytest

from core import link_dostop, link_zaslon

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PrivzetoZaslon(unittest.TestCase):
    def test_brez_izbire_vklopljeno_izbira_velja(self):
        self.assertTrue(link_zaslon.vklopljeno_iz_nastavitev(None))       # kljuca v control.json ni
        self.assertFalse(link_zaslon.vklopljeno_iz_nastavitev(False))     # uporabnik je izklopil
        self.assertTrue(link_zaslon.vklopljeno_iz_nastavitev(True))

    def test_control_uporabi_privzeto_in_pladenj_kaze_pravo_stanje(self):
        """safeer_control.py (GTK3, tu ga ni mogoce uvoziti): stanje pride iz pravila zgoraj, pladenj bere Zaslon."""
        with open(os.path.join(KOREN, "safeer_control.py"), encoding="utf-8") as d:
            koda = d.read()
        self.assertIn('link_zaslon.Zaslon(vklopljeno=link_zaslon.vklopljeno_iz_nastavitev(self.nastavitve.get("zaslon_za_tv")))',
                      koda)
        self.assertNotIn('get("zaslon_za_tv", False)', koda)
        self.assertIn("self.zaslon.set_active(bool(app.zaslon.vklopljeno))", koda)
        self.assertIn('self.nastavitve.set("zaslon_za_tv", bool(vklopljeno))', koda)    # izklop se zapomni


@pytest.mark.pravi_dostop
class ZaslonSamoZDovoljenjem(unittest.TestCase):
    def test_vklopljen_zaslon_ne_odpre_naprave_brez_z(self):
        import tempfile
        from unittest import mock
        mapa = tempfile.TemporaryDirectory()
        self.addCleanup(mapa.cleanup)
        link_dostop._za_preizkus(os.path.join(mapa.name, "dostop.json"))
        self.addCleanup(lambda: link_dostop._za_preizkus(None))
        naprava = "n-aaaaaaaaaaaaaaaa"
        with mock.patch.object(link_dostop, "_lastni_kljuc", lambda: None), \
                mock.patch.object(link_dostop, "_krog", side_effect=RuntimeError("brez kroga")):
            self.assertFalse(link_dostop.sme_dejanje(naprava, "screen.start", zascita=naprava))
            # Star zapis brez upravljanja (pred pravilom ozjega kroga 25. 10. 2026): zaslon ostane zaprt.
            with mock.patch.object(link_dostop, "ozji_krog", lambda dano: set(dano)):
                link_dostop.nastavi(naprava, "dpv")
            self.assertFalse(link_dostop.sme_dejanje(naprava, "screen.start", zascita=naprava))
            link_dostop.nastavi(naprava, "z")
            self.assertTrue(link_dostop.sme_dejanje(naprava, "screen.start", zascita=naprava))
