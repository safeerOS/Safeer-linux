"""Zacasne datoteke za atomski zapis imajo edinstveno ime (pregled 4. 11. 2026).

Prej je ~45 mest pisalo v stalno <pot>.tmp in ga nato z os.replace premaknilo na cilj. Dve niti (ali dva procesa) na
istem cilju sta pisali v ISTO zacasno datoteko: os.replace prve je premaknil napol zapisano vsebino druge, druga pa je
nato dobila FileNotFoundError. Zdaj vsa ta mesta pisejo prek core/shramba_json (mkstemp v mapi cilja)."""
import json
import os
import re
import stat
import tempfile
import threading
import unittest

from core import link_nadaljuj, shramba_json

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: Niz, ki se konca s ».tmp« - razen pripone za mkstemp (suffix=".tmp").
STALNO_TMP = re.compile(r"""(?<!suffix=)["'][^"'\n]*\.tmp["']""")


def _python_datoteke():
    for koren, mape, datoteke in os.walk(os.path.join(KOREN, "core")):
        mape[:] = [m for m in mape if m != "__pycache__"]
        for d in datoteke:
            if d.endswith(".py"):
                yield os.path.join(koren, d)
    for d in os.listdir(KOREN):
        if d.startswith("safeer_") and d.endswith(".py"):
            yield os.path.join(KOREN, d)


class BrezStalnegaImena(unittest.TestCase):
    def test_v_kodi_ni_stalnega_tmp(self):
        najdeno = []
        for pot in _python_datoteke():
            with open(pot, encoding="utf-8") as f:
                for st, vrstica in enumerate(f, 1):
                    if vrstica.lstrip().startswith("#"):
                        continue
                    if STALNO_TMP.search(vrstica):
                        najdeno.append("%s:%d: %s" % (os.path.relpath(pot, KOREN), st, vrstica.strip()))
        self.assertEqual(najdeno, [], "stalno zacasno ime - uporabi shramba_json.atomsko_odpri/atomska_pot")

    def test_vzorec_najde_stare_oblike(self):
        for primer in ('zacasna = pot + ".tmp"', "zacasna = '%s.%d.tmp' % (pot, 1)", 'f"{pot}.tmp"',
                       'pot.with_suffix(".tmp")'):
            self.assertTrue(STALNO_TMP.search(primer), primer)
        self.assertIsNone(STALNO_TMP.search('tempfile.mkstemp(prefix="x.", suffix=".tmp", dir=m)'))


class DveNiti(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-tmp-")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.mapa, ignore_errors=True)

    def _dve_niti(self, pisi, ponovitev=300):
        """Dve niti pisejo razlicno vsebino na isti cilj, tretja bere. Vrne napake in ostanke v mapi."""
        pot = os.path.join(self.mapa, "stanje.json")
        napake, konec = [], threading.Event()
        vsebine = [{"nit": n, "polnilo": "x" * 20000} for n in (0, 1)]

        def pisec(n):
            try:
                for _ in range(ponovitev):
                    pisi(pot, vsebine[n])
            except Exception as e:  # noqa: BLE001
                napake.append("pisanje: %r" % e)

        def bralec():
            while not konec.is_set():
                try:
                    with open(pot, encoding="utf-8") as f:
                        if json.load(f) not in vsebine:
                            napake.append("branje: tuja vsebina")
                except FileNotFoundError:
                    pass
                except ValueError as e:
                    napake.append("branje: napol zapisano %r" % e)

        niti = [threading.Thread(target=pisec, args=(n,)) for n in (0, 1)]
        b = threading.Thread(target=bralec)
        b.start()
        for t in niti:
            t.start()
        for t in niti:
            t.join()
        konec.set()
        b.join()
        ostanki = [d for d in os.listdir(self.mapa) if d != "stanje.json"]
        return napake, ostanki

    def test_mesto_v_kodi_dve_niti(self):
        # link_nadaljuj._pisi_json je eno od pretvorjenih mest (prej <pot>.tmp).
        napake, ostanki = self._dve_niti(link_nadaljuj._pisi_json)
        self.assertEqual(napake[:3], [])
        self.assertEqual(ostanki, [], "zacasne datoteke ne smejo ostati")

    def test_atomsko_odpri_pravice_in_napaka(self):
        pot = os.path.join(self.mapa, "skrivnost.json")
        with shramba_json.atomsko_odpri(pot) as f:
            json.dump({"a": 1}, f)
        self.assertEqual(stat.S_IMODE(os.stat(pot).st_mode), 0o600)
        with self.assertRaises(RuntimeError):
            with shramba_json.atomsko_odpri(pot) as f:
                f.write("{napol")
                raise RuntimeError("prekinjeno")
        with open(pot, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"a": 1}, "ob napaki ostane stara vsebina")
        self.assertEqual(sorted(os.listdir(self.mapa)), ["skrivnost.json"])

    def test_atomska_pot_in_bajti(self):
        pot = os.path.join(self.mapa, "slika.png")
        with shramba_json.atomska_pot(pot) as zacasna:
            self.assertNotEqual(zacasna, pot + ".tmp")  # noqa: zacasne-datoteke (primerjava, ne zapis)
            self.assertTrue(os.path.basename(zacasna).startswith("."))
            with open(zacasna, "wb") as f:
                f.write(b"\x89PNG")
        shramba_json.zapisi_besedilo_atomsko(pot + ".bin", b"\x00\x01", nacin=0o644)
        with open(pot, "rb") as f:
            self.assertEqual(f.read(), b"\x89PNG")
        self.assertEqual(stat.S_IMODE(os.stat(pot + ".bin").st_mode), 0o644)
        self.assertEqual(sorted(os.listdir(self.mapa)), ["slika.png", "slika.png.bin"])


if __name__ == "__main__":
    unittest.main()
