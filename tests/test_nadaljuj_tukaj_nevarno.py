"""»Nadaljuj tukaj«: datoteke z druge naprave privzeti program ne odpre, ce bi jo izvedel (tedenski pregled 4. 11. 2026,
N3) - isto pravilo kot files.open (core/link_datoteke.nevarna_za_odpiranje)."""
import os
import tempfile
import unittest
from unittest import mock

import safeer_os
from core import link_nadaljuj, link_teamwork, os_datoteke, os_odpri_z


class NadaljujTukajNevarno(unittest.TestCase):
    def _odpri(self, ime, vsebina):
        mapa = tempfile.TemporaryDirectory()
        self.addCleanup(mapa.cleanup)
        d = mapa.name
        pot = os.path.join(d, ime)
        with open(pot, "wb") as f:
            f.write(vsebina)
        odprto = []
        with mock.patch.object(safeer_os, "_control_naprave", lambda *a: {}), \
                mock.patch.object(link_nadaljuj, "nadaljuj_tukaj", lambda *a, **k: {"ok": True, "pot": pot, "izvirnik": True}), \
                mock.patch.object(link_teamwork, "izberi_program",
                                  lambda *a: {"nacin": "podprt", "ime": "Urejevalnik", "program": "urejevalnik"}), \
                mock.patch.object(os_odpri_z, "odpri_z", lambda *a, **k: {"ok": False}), \
                mock.patch.object(os_datoteke, "odpri", lambda p: odprto.append(p) or True):
            izid = safeer_os.nadaljuj_tukaj({}, "", "x", "n-1", "Prenosnik", [ime])
        return izid, odprto

    def test_program_ni_odprt_s_privzetim_programom(self):
        izid, odprto = self._odpri("porocilo.odt", b"\x7fELF\x02\x01\x01" + b"\0" * 57)
        self.assertEqual(odprto, [])
        self.assertFalse(izid["odprto"])
        self.assertTrue(izid.get("nevarna"))

    def test_navadna_datoteka_se_odpre(self):
        izid, odprto = self._odpri("zapiski.txt", b"besedilo\n")
        self.assertEqual(len(odprto), 1)
        self.assertTrue(izid["odprto"])


if __name__ == "__main__":
    unittest.main()
