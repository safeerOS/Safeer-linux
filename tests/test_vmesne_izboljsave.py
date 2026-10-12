"""Vmesne izboljsave 12. 10. 2026: dvojni Esc zapre Splet, Browser obnovi prevelik omrezni proces med mirovanjem,
Splet ob zaklepu zaslona sprosti pomnilnik."""
import ast
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KOREN = Path(__file__).resolve().parents[1]


def _funkcija(datoteka, ime):
    drevo = ast.parse((KOREN / datoteka).read_text(encoding="utf-8"))
    vozel = next(n for n in drevo.body if isinstance(n, ast.FunctionDef) and n.name == ime)
    prostor = {}
    exec(compile(ast.Module(body=[vozel], type_ignores=[]), datoteka, "exec"), prostor)
    return prostor[ime]


class DvojniEsc(unittest.TestCase):
    def setUp(self):
        self.f = _funkcija("safeer_os.py", "dvojni_esc")

    def test_hitro_zaporedje(self):
        self.assertTrue(self.f(1000, 1400))
        self.assertTrue(self.f(1000, 1600))

    def test_prepocasi_ali_prvi(self):
        self.assertFalse(self.f(1000, 1601))
        self.assertFalse(self.f(None, 1000))
        self.assertFalse(self.f(1000, 0))
        self.assertFalse(self.f(2000, 1000))

    def test_vgrajeno_v_tipko_spleta(self):
        besedilo = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
        zacetek = besedilo.index("def _tipka_splet_na_namizju")
        telo = besedilo[zacetek:besedilo.index("\n    def ", zacetek + 10)]
        self.assertLess(telo.index("dvojni_esc"), telo.index("propagate_key_event"))


class RecikliranjeOmreznega(unittest.TestCase):
    def setUp(self):
        from core.pomnilnik import recikliraj_omrezni
        self.f = recikliraj_omrezni
        self.osnova = dict(okno_aktivno=False, neaktivno_s=301, prenosi=False, nalaganje=False, zvok=False,
                           pss_mb=350, meja_mb=300)

    def test_mirovanje_nad_mejo(self):
        self.assertTrue(self.f(**self.osnova))

    def test_nikoli_med_uporabo(self):
        for kljuc, vrednost in (("okno_aktivno", True), ("prenosi", True), ("nalaganje", True), ("zvok", True),
                                ("neaktivno_s", 299), ("pss_mb", 299), ("meja_mb", 0)):
            with self.subTest(kljuc):
                self.assertFalse(self.f(**dict(self.osnova, **{kljuc: vrednost})))

    def test_browser_klice_odlocitev(self):
        besedilo = (KOREN / "safeer_mint.py").read_text(encoding="utf-8")
        self.assertIn("self._recikliraj_omrezni_proces(zdaj)", besedilo)
        self.assertIn("recikliraj_omrezni(", besedilo)


class OmrezniProcesShrambe(unittest.TestCase):
    def test_pss_tega_procesa(self):
        from core import os_splet
        self.assertGreater(os_splet.pss_mb(os.getpid()), 1)
        self.assertEqual(os_splet.pss_mb(2 ** 22 + 7), 0.0)

    def test_izbere_po_piskotkih(self):
        from core import os_splet
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "cookies.sqlite")
            odprte = {1: {"/x"}, 2: {os.path.realpath(p)}}
            with mock.patch.object(os_splet, "omrezni_procesi", return_value={1, 2}), \
                    mock.patch.object(os_splet, "odprte_datoteke", side_effect=lambda pid: odprte[pid]):
                self.assertEqual(os_splet.omrezni_procesi_shrambe(p), [2])


class ZaklepSpleta(unittest.TestCase):
    def _splet(self, mapa, nalaga=False):
        from core import os_splet
        s = os_splet.VdelaniSplet.__new__(os_splet.VdelaniSplet)
        pogled = mock.Mock()
        pogled.is_loading.return_value = nalaga
        s.zavihki, s.aktivni = [{"pogled": pogled}], pogled

        class Config:
            config_dir = mapa
        s.config = Config()
        return s, os_splet

    def test_velik_proces_obnovi_zavihki_ostanejo(self):
        with tempfile.TemporaryDirectory() as d:
            s, os_splet = self._splet(d)
            with mock.patch.object(os_splet.VdelaniSplet, "sprazni_predpomnilnik") as sp, \
                    mock.patch.object(os_splet, "omrezni_procesi_shrambe", return_value=[7]), \
                    mock.patch.object(os_splet, "pss_mb", return_value=400), \
                    mock.patch.object(os_splet.os, "kill") as kill:
                self.assertTrue(s.ob_zaklepu())
            sp.assert_called_once()
            kill.assert_called_once_with(7, 15)
            self.assertEqual(len(s.zavihki), 1)

    def test_majhen_ali_med_nalaganjem_ne(self):
        for nalaga, velikost in ((False, 100), (True, 900)):
            with tempfile.TemporaryDirectory() as d:
                s, os_splet = self._splet(d, nalaga)
                with mock.patch.object(os_splet.VdelaniSplet, "sprazni_predpomnilnik"), \
                        mock.patch.object(os_splet, "omrezni_procesi_shrambe", return_value=[7]), \
                        mock.patch.object(os_splet, "pss_mb", return_value=velikost), \
                        mock.patch.object(os_splet.os, "kill") as kill:
                    self.assertFalse(s.ob_zaklepu())
                kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
