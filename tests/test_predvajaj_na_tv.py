"""»Predvajaj na TV« - posiljatelj v jedru (core/predvajaj_na_tv): samo naprave ozjega kroga z zmoznostjo media.play,
samo dovoljena polja, iz odgovora TV samo ok in kratka koda. Lazni Link (seznam in ukaz), brez omrezja."""
import json
import os
import re
import unittest

from core import predvajaj_na_tv as P

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEZNAM = {"naprave": [
    {"id": "ta", "ime": "Ta racunalnik", "ta": True, "ozji": True, "zmoznosti": ["media.play"]},
    {"id": "tv", "ime": "Dnevna TV", "ozji": True, "zmoznosti": ["remote", "media.play"]},
    {"id": "tuj", "ime": "Tuja TV", "ozji": False, "zmoznosti": ["media.play"]},
    {"id": "stara", "ime": "Stara TV", "ozji": True, "zmoznosti": ["remote", "media.open"]},
    {"ime": "brez id", "ozji": True, "zmoznosti": ["media.play"]},
    "ni slovar",
]}
FILM = {"vrsta": "film", "id": "tt0133093", "naslov": "Matrica", "polozajMs": "0"}


class Lazni:
    def __init__(self, odgovor=None):
        self.klici = []
        self.odgovor = {"ok": True} if odgovor is None else odgovor

    def __call__(self, nid, dejanje, parametri):
        self.klici.append((nid, dejanje, json.loads(parametri)))
        if isinstance(self.odgovor, Exception):
            raise self.odgovor
        return self.odgovor


class Naprave(unittest.TestCase):
    def test_samo_ozji_krog_z_zmoznostjo(self):
        self.assertEqual(P.naprave(SEZNAM), [{"id": "tv", "ime": "Dnevna TV"}])
        self.assertEqual(P.naprave(None), [])
        self.assertEqual(P.naprave({"naprave": [{"id": "x", "ime": "y" * 500, "ozji": True,
                                                 "zmoznosti": ["media.play"]}]})[0]["ime"], "y" * 80)


class Poslji(unittest.TestCase):
    def test_poslje_media_play_samo_dovoljena_polja(self):
        u = Lazni()
        izid = P.poslji(lambda: SEZNAM, u, "tv", dict(FILM, url="http://zlo", ukaz="rm"))
        self.assertEqual(izid, {"ok": True, "razlog": "", "ime": "Dnevna TV"})
        self.assertEqual(u.klici, [("tv", "media.play", FILM)])

    def test_naprava_zunaj_kroga_ali_brez_zmoznosti_ne_dobi_nicesar(self):
        for nid in ("tuj", "stara", "ta", "neznana", ""):
            u = Lazni()
            self.assertEqual(P.poslji(lambda: SEZNAM, u, nid, FILM), {"ok": False, "razlog": "ni_naprave", "ime": ""}, nid)
            self.assertEqual(u.klici, [], nid)

    def test_napacna_polja(self):
        for polja in (None, [], {"vrsta": "film"}, {"vrsta": "glasba", "id": "tt0133093"}, dict(FILM, naslov=5),
                      dict(FILM, naslov="x" * (P.NAJVEC_POLJA + 1))):
            u = Lazni()
            self.assertEqual(P.poslji(lambda: SEZNAM, u, "tv", polja)["razlog"], "napacna_zahteva", polja)
            self.assertEqual(u.klici, [])

    def test_odgovor_tv(self):
        primeri = [({"ok": True, "message": "<b>x</b>"}, True, ""),
                   ({"ok": "true"}, False, ""),
                   ({"ok": False, "data": {"razlog": "NI_V_KROGU"}}, False, "NI_V_KROGU"),
                   ({"ok": False, "koda": "cas"}, False, "cas"),
                   ({"ok": False, "data": {"razlog": "<img src=x>"}, "koda": "x" * 41}, False, ""),
                   ({"ok": False, "data": "ni slovar"}, False, ""),
                   ("ni slovar", False, ""),
                   (RuntimeError("Control"), False, "napaka")]
        for odgovor, ok, razlog in primeri:
            izid = P.poslji(lambda: SEZNAM, Lazni(odgovor), "tv", FILM)
            self.assertEqual(izid, {"ok": ok, "razlog": razlog, "ime": "Dnevna TV"}, odgovor)

    def test_most_in_tovor(self):
        vir = open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8").read()
        self.assertRegex(vir, r'"napraveZaPredvajanje": naprave_za_predvajanje,')
        self.assertRegex(vir, r'"predvajajNaNapravi": lambda: predvajaj_na_napravi\(')
        # Ukaz gre po obstojecem kanalu (Control Ukaz -> control.command), ne po novem protokolu.
        self.assertRegex(vir, r'_control_naprave\("Ukaz", nid, dejanje, parametri\)')
        tovor = open(os.path.join(KOREN, "packaging", "install_os_payload.sh"), encoding="utf-8").read()
        self.assertTrue(re.search(r"\bpredvajaj_na_tv\b", tovor))


if __name__ == "__main__":
    unittest.main()
