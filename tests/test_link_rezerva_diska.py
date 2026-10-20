"""Rezerva diska v Linku iz enega vira (core/link_viri.rezerva_diska) - odprta tocka pregleda 1.0.128.

Hub (link_hub_deljenje) jo ze uporablja. Strezniku datotek (link_datoteke) je ostala ista napaka: rezerva popravkov
Teamworka REZERVA_DISKA = 512 MiB je bila ob uvozu modula tiho povozena z istoimensko mejo pomoci (2 GiB) nize v modulu.
"""
import ast
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import link_datoteke, link_teamwork, link_viri

KOREN = Path(__file__).resolve().parents[1]
GB = 1024 ** 3


class EnoImeEnaMeja(unittest.TestCase):
    def test_brez_povozenih_konstant_modula(self):
        drevo = ast.parse((KOREN / "core" / "link_datoteke.py").read_text(encoding="utf-8"))
        imena = [c.id for n in drevo.body if isinstance(n, ast.Assign) for c in n.targets
                 if isinstance(c, ast.Name) and c.id.isupper()]
        podvojena = sorted({i for i in imena if imena.count(i) > 1})
        self.assertEqual(podvojena, [], "konstanta modula, ki jo kasnejsa dodelitev povozi")


class _Obravnava:
    def __init__(self, dolzina):
        self.headers = {"X-Safeer-Token": "z", "Content-Length": str(dolzina)}
        self.close_connection = False
        self.connection = mock.MagicMock()


class PopravekTeamworkaZRezervoLinka(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.tw = mock.MagicMock()
        self.tw._mapa_zacasnih.return_value = self.mapa
        self.streznik = mock.MagicMock(teamwork=self.tw)
        self.streznik.zeton_velja.return_value = True
        self.streznik.naprava_zetona.return_value = "naprava-b"
        self.napake = []
        p = mock.patch.object(link_datoteke, "_napaka_http", lambda _o, koda, _s: self.napake.append(koda))
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(link_datoteke, "_sprejmi_popravek")
        self.sprejeto = p.start()
        self.addCleanup(p.stop)

    def _poslji(self, prosto, rezerva):
        disk = mock.MagicMock(free=prosto)
        with mock.patch.object(link_datoteke.shutil, "disk_usage", return_value=disk), \
                mock.patch.object(link_viri, "rezerva_diska", return_value=rezerva) as r:
            link_datoteke.sprejmi_popravek(_Obravnava(1024), self.streznik, "share:0:a.bin")
        return r

    def test_rezerva_iz_link_viri(self):
        r = self._poslji(3 * GB, 4 * GB)            # 3 GiB prosto, Link zahteva 4 GiB rezerve: ni prostora
        self.assertEqual(self.napake, [507])
        r.assert_called_once_with(self.mapa)
        self.sprejeto.assert_not_called()

    def test_dovolj_prostora(self):
        self._poslji(3 * GB, 1 * GB)
        self.assertEqual(self.napake, [])
        self.sprejeto.assert_called_once()
        self.assertLessEqual(1024, link_teamwork.NAJVEC_POPRAVKA)


if __name__ == "__main__":
    unittest.main()
