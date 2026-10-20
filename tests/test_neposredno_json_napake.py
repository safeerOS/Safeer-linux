"""link_neposredno: branje in pisanje JSON ne podre klicatelja (odprta tocka neodvisnega pregleda 2).

_beri_json je lovil FileNotFoundError/JSONDecodeError/UnicodeDecodeError/OSError, json pa vrze tudi ValueError (stevilo
z vec kot 4300 stevkami) in RecursionError (globoko gnezden seznam) - izmerjeno 20. 10. 2026: izjema je sla do
klicatelja. _pisi_json je pisal v stalno <pot>.tmp (dve niti v isto datoteko; do chmod berljivo vsem). Shranjeno stanje z
napacno vrsto vrednosti (niz namesto stevila, niz namesto slovarja) je podrlo LokalniOdZunaj in NeposrednoHuba.
"""
import io
import json
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from core import link_neposredno as n


class BranjeNePodre(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.addCleanup(self._d.cleanup)
        self.d = self._d.name

    def _datoteka(self, ime, vsebina: bytes):
        p = os.path.join(self.d, ime)
        with open(p, "wb") as f:
            f.write(vsebina)
        return p

    def test_pokvarjena_vsebina_je_prazno(self):
        for ime, vsebina in (("globoko.json", b"[" * 200000), ("stevilo.json", b'{"a": ' + b"1" * 5000 + b"}"),
                             ("utf.json", b"\xff\xfe{}"), ("seznam.json", b"[1, 2]")):
            with self.subTest(ime):
                self.assertEqual(n._beri_json(self._datoteka(ime, vsebina)), {})

    def test_pravice_v_dnevnik(self):
        izpis = io.StringIO()
        with mock.patch("builtins.open", side_effect=PermissionError(13, "dovoljenje zavrnjeno")), \
                redirect_stdout(izpis):
            self.assertEqual(n._beri_json(os.path.join(self.d, "x.json")), {})
        self.assertIn("neposredno: branje", izpis.getvalue())


class PisanjeAtomsko(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.addCleanup(self._d.cleanup)
        self.pot = os.path.join(self._d.name, "spomin.json")

    def test_ne_potrebuje_stalne_zacasne_datoteke(self):
        os.mkdir(self.pot + ".tmp")          # stalno ime zasedeno (npr. ostanek ali druga nit): pisanje vseeno uspe
        self.assertIs(n._pisi_json(self.pot, {"a": 1}), True)
        with open(self.pot, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"a": 1})
        self.assertEqual(stat.S_IMODE(os.stat(self.pot).st_mode), 0o600)

    def test_globoka_vsebina_vrne_false(self):
        globoko = []
        for _ in range(100000):
            globoko = [globoko]
        with redirect_stdout(io.StringIO()):
            self.assertIs(n._pisi_json(self.pot, {"a": globoko}), False)
        self.assertEqual(os.listdir(os.path.dirname(self.pot)), [], "zacasna datoteka se pospravi")


class ShranjenoStanjeNapacneVrste(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.addCleanup(self._d.cleanup)

    def test_spomin_poti(self):
        pot = os.path.join(self._d.name, "spomin.json")
        with open(pot, "w", encoding="utf-8") as f:
            json.dump({"n-0123456789abcdef": "ni slovar"}, f)
        o = n.LokalniOdZunaj.__new__(n.LokalniOdZunaj)
        o.cilj, o._pot_spomina, o._kljuc, o._oglas, o._nas_uspeh = "n-0123456789abcdef", pot, None, None, {}
        o.ura = lambda: 0.0
        o._nalozi_spomin()
        self.assertEqual(o.zadnja_pot, "")

    def test_stanje_sredisca(self):
        pot = os.path.join(self._d.name, "stanje.json")
        with open(pot, "w", encoding="utf-8") as f:
            json.dump({"ip": "203.0.113.5", "preverjeno": "vceraj", "vrata": 40404}, f)
        h = n.NeposrednoHuba(lambda: 0, nastavitve_fn=lambda: {"vklopljeno": False, "vrata": 40404},
                             stun=lambda: "", pot_stanja=pot)
        self.assertFalse(h.preverjeno())
        self.assertEqual(h.stanje()["preverjeno_ob"], 0)


if __name__ == "__main__":
    unittest.main()
