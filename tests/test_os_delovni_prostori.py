"""Lokalna navidezna namizja (core/os_delovni_prostori.py): razclenjevanje wmctrl, shema oken, preklop in dodajanje
brez pravega upravljalnika oken (wmctrl je nadomescen). Ziv preizkus z Muffinom je v tests/test_prostori_namizja_zivo.py."""
import subprocess
import unittest

from core import os_delovni_prostori as dp

D = """0  * DG: 2560x1440  VP: 0,0  WA: 0,41 2560x1399  Delovna površina 1
1  - DG: 2560x1440  VP: N/A  WA: 0,41 2560x1399  Delovna površina 2
smeti
2  - DG: 2560x1440  VP: N/A  WA: 0,41 2560x1399  Delo
"""
L = """0x03a00003 -1 0    0    2560 1440 racunalnik Safeer OS namizje
0x04000007  0 100  141  1280 720  racunalnik Firefox – Novice
0x04000009  1 2400 900  800  800  racunalnik Terminal
0x0400000b  1 10   50   10   10   racunalnik drobno
0x0400000c  0 3000 0    500  500  racunalnik zunaj
pokvarjena vrstica
"""


class _Wm:
    """Nadomestni wmctrl: hrani stevilo namizij in trenutno, kot bi ga Muffin."""

    def __init__(self, n=3, trenutno=0, sprejme_n=True):
        self.n, self.trenutno, self.sprejme_n = n, trenutno, sprejme_n
        self.klici = []

    def __call__(self, ukaz, **kw):
        self.klici.append(ukaz[1:])
        assert kw.get("timeout") == dp.ROK_S
        izpis = ""
        if ukaz[1] == "-d":
            # Zadnje (novo) namizje ima delovno povrsino N/A, kot jo Muffin pokaze takoj po dodajanju.
            izpis = "".join("%d  %s DG: 1920x1080  VP: %s  WA: %s  N%d\n"
                            % (i, "*" if i == self.trenutno else "-", "0,0" if i == self.trenutno else "N/A",
                               "N/A" if i == self.n - 1 and i else "0,0 1920x1080", i + 1) for i in range(self.n))
        elif ukaz[1] == "-lG":
            izpis = "0x01 1 0 0 960 540 h Okno\n"
        elif ukaz[1] == "-s":
            self.trenutno = int(ukaz[2])
        elif ukaz[1] == "-n" and self.sprejme_n:
            self.n = int(ukaz[2])
        return subprocess.CompletedProcess(ukaz, 0, izpis, "")


def _nam(wm, **kw):
    return dp.Namizja(zazeni=wm, wmctrl="/usr/bin/wmctrl", okolje=dict({"DISPLAY": ":0"}, **kw), cakaj=lambda _s: None)


class Razclenjevanje(unittest.TestCase):
    def test_namizja(self):
        n = dp.razcleni_namizja(D)
        self.assertEqual([x["st"] for x in n], [0, 1, 2])
        self.assertTrue(n[0]["trenutno"])
        self.assertFalse(n[1]["trenutno"])
        self.assertEqual(n[0]["ime"], "Delovna površina 1")
        self.assertEqual((n[2]["sirina"], n[2]["visina"]), (2560, 1440))

    def test_novo_namizje_brez_delovne_povrsine(self):
        # Muffin takoj po dodajanju: »WA: N/A« (izmerjeno 25. 10. 2026) - se vedno je namizje.
        n = dp.razcleni_namizja("0  * DG: 1280x800  VP: 0,0  WA: 0,0 1280x800  W1\n"
                                "4  - DG: 1280x800  VP: N/A  WA: N/A  Workspace 5\n"
                                "5  - DG: N/A  VP: N/A  WA: N/A  Workspace 6\n")
        self.assertEqual([(x["st"], x["ime"]) for x in n], [(0, "W1"), (4, "Workspace 5"), (5, "Workspace 6")])
        self.assertEqual(n[2]["sirina"], 0)
        # Brez velikosti namizja (DG: N/A) velja velikost drugih namizij - okno ostane v shemi.
        o = dp.postavitev(n, [{"id": "0x1", "namizje": 5, "x": 0, "y": 0, "w": 640, "h": 400}])[2]["okna"]
        self.assertEqual((o[0]["w"], o[0]["h"]), (0.5, 0.5))

    def test_okna(self):
        o = dp.razcleni_okna(L)
        self.assertEqual(len(o), 5)
        self.assertEqual(o[0]["namizje"], -1)
        self.assertEqual(o[1]["naslov"], "Firefox – Novice")

    def test_shema(self):
        p = dp.postavitev(dp.razcleni_namizja(D), dp.razcleni_okna(L))
        self.assertEqual(len(p), 3)
        # Lepljivo okno (namizje -1), drobno in okno zunaj zaslona ne stejejo.
        self.assertEqual([o["naslov"] for o in p[0]["okna"]], ["Firefox – Novice"])
        self.assertEqual(p[0]["okna"][0], {"x": 0.0391, "y": 0.0979, "w": 0.5, "h": 0.5, "naslov": "Firefox – Novice"})
        # Okno, ki sega cez rob, je obrezano na zaslon (delez nikoli nad 1).
        t = p[1]["okna"][0]
        self.assertEqual(t["naslov"], "Terminal")
        self.assertLessEqual(t["x"] + t["w"], 1.0)
        self.assertLessEqual(t["y"] + t["h"], 1.0)
        self.assertEqual(p[2]["okna"], [])

    def test_izloci_lastna_okna(self):
        p = dp.postavitev(dp.razcleni_namizja(D), dp.razcleni_okna(L), {"0x04000007"})
        self.assertEqual(p[0]["okna"], [])

    def test_meja(self):
        veliko = "".join("%d  - DG: 100x100  VP: 0,0  WA: 0,0 100x100  N\n" % i for i in range(40))
        self.assertEqual(len(dp.postavitev(dp.razcleni_namizja(veliko), [])), dp.NAJVEC_NAMIZIJ)


class Upravljanje(unittest.TestCase):
    def test_brez_x11_ni_namizij(self):
        wm = _Wm()
        self.assertEqual(_nam(wm, WAYLAND_DISPLAY="wayland-0").seznam(), [])
        self.assertEqual(dp.Namizja(zazeni=wm, wmctrl="", okolje={"DISPLAY": ":0"}).seznam(), [])
        self.assertEqual(wm.klici, [])

    def test_seznam_in_preklop(self):
        wm = _Wm()
        n = _nam(wm)
        s = n.seznam()
        self.assertEqual([x["st"] for x in s], [0, 1, 2])
        self.assertEqual(len(s[1]["okna"]), 1)
        self.assertEqual(n.preklopi(2), {"ok": True, "st": 2})
        self.assertEqual(wm.trenutno, 2)

    def test_preklop_preveri_stevilko(self):
        wm = _Wm()
        n = _nam(wm)
        for slabo in (5, -1, "1", True, None, 1.0):
            self.assertFalse(n.preklopi(slabo)["ok"], slabo)
        self.assertNotIn(["-s", "5"], wm.klici)

    def test_dodaj(self):
        wm = _Wm(n=2)
        self.assertEqual(_nam(wm).dodaj(), {"ok": True, "st": 2})
        self.assertEqual((wm.n, wm.trenutno), (3, 2))

    def test_dodaj_meja_in_zavrnjeno(self):
        self.assertEqual(_nam(_Wm(n=dp.NAJVEC_NAMIZIJ)).dodaj()["koda"], "najvec")
        self.assertEqual(_nam(_Wm(n=2, sprejme_n=False), ).dodaj()["koda"], "ni_dodano")

    def test_wmctrl_obvisi(self):
        def obvisi(ukaz, **kw):
            raise subprocess.TimeoutExpired(ukaz, kw.get("timeout"))
        n = _nam(obvisi)
        self.assertEqual(n.seznam(), [])
        self.assertFalse(n.dodaj()["ok"])


if __name__ == "__main__":
    unittest.main()
