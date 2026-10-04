"""Sistemski posrednik namizja (core/sistemski_posrednik.py): nastavi, vrne tocno kot je bilo, prezivi sesutje.

gsettings je laznen (slovar), ker preizkus ne sme spreminjati namizja, na katerem tece.
"""
import json
import os
import shutil
import tempfile
import unittest

from core import sistemski_posrednik as sp

PRAZNO = {
    "org.gnome.system.proxy mode": "'none'",
    "org.gnome.system.proxy.http host": "''", "org.gnome.system.proxy.http port": "8080",
    "org.gnome.system.proxy.https host": "''", "org.gnome.system.proxy.https port": "0",
    "org.gnome.system.proxy.socks host": "''", "org.gnome.system.proxy.socks port": "0",
}
SLUZBENI = {
    "org.gnome.system.proxy mode": "'manual'",
    "org.gnome.system.proxy.http host": "'posrednik.podjetje.example'", "org.gnome.system.proxy.http port": "3128",
    "org.gnome.system.proxy.https host": "'posrednik.podjetje.example'", "org.gnome.system.proxy.https port": "3128",
    "org.gnome.system.proxy.socks host": "''", "org.gnome.system.proxy.socks port": "0",
}


class LazniGsettings:
    def __init__(self, vrednosti):
        self.v = dict(vrednosti)
        self.klici = []
        self.pade_pri = None

    def __call__(self, *a):
        self.klici.append(a)
        ime = a[1] + " " + a[2]
        if a[0] == "get":
            return self.v.get(ime)
        if a[0] == "set":
            if self.pade_pri == ime:
                return None
            self.v[ime] = a[3]
            return ""
        return None


class Osnova(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-sistemski-")
        self.pot = os.path.join(self.mapa, "sistemski-posrednik.json")

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def nov(self, vrednosti=PRAZNO, okolje=None):
        g = LazniGsettings(vrednosti)
        return sp.SistemskiPosrednik(self.pot, gsettings=g, okolje=okolje or {"XDG_CURRENT_DESKTOP": "X-Cinnamon"}), g


class VklopInIzklop(Osnova):
    def test_vklop_nastavi_vse_tri_in_nacin_zadnjega(self):
        s, g = self.nov()
        self.assertTrue(s.vklopi(47890))
        self.assertEqual(g.v["org.gnome.system.proxy mode"], "'manual'")
        for vrsta in ("http", "https", "socks"):
            self.assertEqual(g.v["org.gnome.system.proxy.%s host" % vrsta], "'127.0.0.1'")
            self.assertEqual(g.v["org.gnome.system.proxy.%s port" % vrsta], "47890")
        nastavitve = [k for k in g.klici if k[0] == "set"]
        self.assertEqual(nastavitve[-1][1:3], ("org.gnome.system.proxy", "mode"), "nacin gre zadnji: prej morajo biti naslovi")
        self.assertTrue(s.nastavljen())
        with open(self.pot) as f:
            self.assertEqual(json.load(f)["prej"], PRAZNO)

    def test_izklop_vrne_tocno_kot_je_bilo(self):
        for prej in (PRAZNO, SLUZBENI):
            s, g = self.nov(prej)
            self.assertTrue(s.vklopi(47890))
            self.assertTrue(s.izklopi())
            self.assertEqual(g.v, prej)
            self.assertFalse(os.path.exists(self.pot))
            self.assertFalse(s.nastavljen())

    def test_izklop_najprej_nacin(self):
        s, g = self.nov()
        s.vklopi(47890)
        g.klici.clear()
        s.izklopi()
        nastavitve = [k for k in g.klici if k[0] == "set"]
        self.assertEqual(nastavitve[0][1:3], ("org.gnome.system.proxy", "mode"))

    def test_dvojni_vklop_ne_prepise_prejsnjih_vrednosti(self):
        s, g = self.nov(SLUZBENI)
        s.vklopi(47890)
        klicev = len(g.klici)
        self.assertTrue(s.vklopi(47890))
        self.assertEqual(len(g.klici), klicev, "isti vklop ne klice gsettings")
        drugi, _ = self.nov(SLUZBENI)
        drugi._gsettings = g                        # nov proces, isto namizje: vrednosti so ze nase
        self.assertTrue(drugi.vklopi(47891))
        with open(self.pot) as f:
            self.assertEqual(json.load(f)["prej"], SLUZBENI, "prej = uporabnikove vrednosti, ne nase")
        self.assertTrue(drugi.izklopi())
        self.assertEqual(g.v, SLUZBENI)

    def test_izklop_brez_vklopa_ne_naredi_nic(self):
        s, g = self.nov()
        self.assertTrue(s.izklopi())
        self.assertEqual(g.klici, [])


class Varnost(Osnova):
    def test_po_sesutju_naslednji_zagon_vrne(self):
        s, g = self.nov(SLUZBENI)
        s.vklopi(47890)
        # Safeer Control pade; nov proces nima nicesar v pomnilniku.
        nov, _ = self.nov()
        nov._gsettings = g
        self.assertTrue(nov.nastavljen())
        nov.ob_zagonu()
        self.assertEqual(g.v, SLUZBENI)
        self.assertFalse(os.path.exists(self.pot))

    def test_kar_je_uporabnik_spremenil_ostane_njegovo(self):
        s, g = self.nov()
        s.vklopi(47890)
        g.v["org.gnome.system.proxy mode"] = "'auto'"                       # uporabnik je vmes izbral samodejno
        g.v["org.gnome.system.proxy.http host"] = "'moj.posrednik.example'"
        self.assertTrue(s.izklopi())
        self.assertEqual(g.v["org.gnome.system.proxy mode"], "'auto'")
        self.assertEqual(g.v["org.gnome.system.proxy.http host"], "'moj.posrednik.example'")
        self.assertEqual(g.v["org.gnome.system.proxy.socks host"], "''", "nasa vrednost gre nazaj na prejsnjo")
        self.assertEqual(g.v["org.gnome.system.proxy.https port"], "0")

    def test_napaka_sredi_vklopa_vrne_vse(self):
        s, g = self.nov(SLUZBENI)
        g.pade_pri = "org.gnome.system.proxy.socks port"
        self.assertFalse(s.vklopi(47890))
        g.pade_pri = None
        self.assertEqual(g.v, SLUZBENI)
        self.assertFalse(s.nastavljen())

    def test_brez_zapisa_prejsnjih_vrednosti_se_nic_ne_spremeni(self):
        s, g = self.nov()
        s.pot_stanja = os.path.join(self.mapa, "datoteka")
        open(s.pot_stanja, "w").close()
        s.pot_stanja = os.path.join(s.pot_stanja, "pod", "stanje.json")     # mape ni mogoce ustvariti
        self.assertFalse(s.vklopi(47890))
        self.assertEqual(g.v, PRAZNO)
        self.assertEqual([k for k in g.klici if k[0] == "set"], [])

    def test_neveljavna_vrata(self):
        s, g = self.nov()
        self.assertFalse(s.vklopi(0))
        self.assertFalse(s.vklopi(70000))
        self.assertEqual([k for k in g.klici if k[0] == "set"], [])


class Podpora(Osnova):
    def test_cinnamon_s_shemo(self):
        s, _ = self.nov()
        self.assertTrue(s.podprt())

    def test_kde_ne(self):
        s, g = self.nov(okolje={"XDG_CURRENT_DESKTOP": "KDE"})
        self.assertFalse(s.podprt())
        self.assertFalse(s.vklopi(47890))
        self.assertEqual(g.klici, [])

    def test_brez_sheme_ne(self):
        s, _ = self.nov(vrednosti={})
        self.assertFalse(s.podprt())
        self.assertFalse(s.vklopi(47890))


if __name__ == "__main__":
    unittest.main()
