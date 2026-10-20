"""core/shramba_json: atomski zapis in zdruzevanje kljucev med procesi (os.json Safeer OS in Scit, 20. 10. 2026).

Pred popravkom je vsak proces ob zapisu zapisal celo svojo kopijo os.json - sprememba drugega procesa (npr. Scit v
svojem procesu nastavi scit_naprej) se je tiho izgubila.
"""
import json
import multiprocessing
import os
import stat
import tempfile
import unittest

from core import shramba_json


def _otrok_nastavi(pot, kljuc, vrednost, ponovitev):
    s = shramba_json.Shramba(pot)
    for i in range(ponovitev):
        s.set(kljuc, "%s-%d" % (vrednost, i))


class TestShrambaJson(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.pot = os.path.join(self.mapa, "os.json")

    def test_drug_proces_ne_povozi_kljuca(self):
        a = shramba_json.Shramba(self.pot)
        b = shramba_json.Shramba(self.pot)
        a.set("scit", True)
        b.set("tema", "temna")           # b ne pozna kljuca "scit" - prej ga je zbrisal
        with open(self.pot, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"scit": True, "tema": "temna"})
        self.assertEqual(b.get("scit"), True)   # b je kljuc drugega procesa prevzel

    def test_brisanje_kljuca_se_ohrani(self):
        a = shramba_json.Shramba(self.pot)
        a.set("x", 1)
        a.set("y", 2)
        b = shramba_json.Shramba(self.pot)
        del a.podatki["x"]
        a.shrani()
        b.set("z", 3)
        self.assertEqual(shramba_json.preberi_slovar(self.pot), {"y": 2, "z": 3})

    def test_vec_procesov_hkrati(self):
        ctx = multiprocessing.get_context("spawn")
        otroci = [ctx.Process(target=_otrok_nastavi, args=(self.pot, "k%d" % i, "v", 25)) for i in range(4)]
        for p in otroci:
            p.start()
        for p in otroci:
            p.join(60)
            self.assertEqual(p.exitcode, 0)
        self.assertEqual(shramba_json.preberi_slovar(self.pot), {"k%d" % i: "v-24" for i in range(4)})
        self.assertEqual([n for n in os.listdir(self.mapa) if n.endswith(".tmp")], [])

    def test_pravice_0600(self):
        shramba_json.Shramba(self.pot).set("a", 1)
        self.assertEqual(stat.S_IMODE(os.stat(self.pot).st_mode), 0o600)

    def test_pokvarjena_datoteka_se_umakne_ne_prepise(self):
        with open(self.pot, "w", encoding="utf-8") as f:
            f.write('{"scit": tr')
        s = shramba_json.Shramba(self.pot)
        self.assertEqual(s.podatki, {})
        umaknjene = [n for n in os.listdir(self.mapa) if n.startswith("os.json.pokvarjen-")]
        self.assertEqual(len(umaknjene), 1)
        with open(os.path.join(self.mapa, umaknjene[0]), encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"scit": tr')

    def test_osvezi_prevzame_tuje_ohrani_svoje(self):
        a = shramba_json.Shramba(self.pot)
        a.set("x", 1)
        b = shramba_json.Shramba(self.pot)
        a.set("x", 2)
        b.podatki["y"] = "lokalno"       # se ni shranjeno
        b.osvezi()
        self.assertEqual(b.get("x"), 2)
        self.assertEqual(b.get("y"), "lokalno")

    def test_napaka_zapisa_ne_pusti_zacasne(self):
        with self.assertRaises(TypeError):
            shramba_json.zapisi_atomsko(self.pot, {"a": object()})
        self.assertEqual(os.listdir(self.mapa), [])


if __name__ == "__main__":
    unittest.main()
