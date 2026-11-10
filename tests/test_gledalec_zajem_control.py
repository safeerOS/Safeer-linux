"""Safeer Control: gledalec ob padcu zajema na drugem racunalniku pokaze stavek v jeziku uporabnika, ne besede »zajem«
ali tehnicnega razloga (tests/test_gledalec_zajem.py za besedila). Prava pot OddaljeniGledalec._zacni (nit z
bralnikom okvirjev) in SafeerControl._nova_oddaljena_seja, brez okna in brez omrezja."""
import json
import types
import unittest
from unittest import mock

import safeer_control
from core import link_gledalec

JEZIKI = ("sl", "en", "de", "es", "fr", "it")


class _Gledalec:
    """Nadomestek core.link_gledalec.Gledalec: povezava uspe, nato pride obvestilo o koncu zajema."""

    def __init__(self, _naslov, _seja):
        pass

    def povezi(self):
        return types.SimpleNamespace(sirina=10, visina=10, podatki={})

    def okvirji(self):
        yield safeer_control.OKVIR_OBVESTILO, json.dumps({"konec": "zajem", "razlog": "izhod_234"}).encode()


def _nastavitve(jezik):
    return types.SimpleNamespace(get=lambda k, d=None: jezik if k == "ui_language" else d)


class GledalecVSeji(unittest.TestCase):
    def _napaka(self, jezik):
        okno = mock.MagicMock()
        okno.zaprto = False
        okno.control.nastavitve = _nastavitve(jezik)
        prikazano = []

        def idle(f, *a):
            if f is okno._pokazi_napako:
                prikazano.append(a[0])

        with mock.patch.object(safeer_control, "Gledalec", _Gledalec), \
                mock.patch.object(safeer_control.threading, "Thread") as nit, \
                mock.patch.object(safeer_control.GLib, "idle_add", side_effect=idle):
            safeer_control.OddaljeniGledalec._zacni(okno, {"naslov": "192.0.2.10:1", "seja": {}})
            nit.call_args.kwargs["target"]()
        self.assertEqual(len(prikazano), 1)
        return prikazano[0]

    def test_pokaze_stavek_ne_besede_zajem(self):
        for j in JEZIKI:
            self.assertEqual(self._napaka(j), link_gledalec.sporocilo_konca(j, "zajem"), j)


class ZacetekSeje(unittest.TestCase):
    def _lazna(self, odgovor, jezik="de"):
        lazna = mock.MagicMock()
        lazna.nastavitve = _nastavitve(jezik)
        lazna.link.naprave = [{"id": "n-1", "ime": "PC", "naslov": "192.0.2.10:7000"}]
        lazna.link.ukaz_pocakaj.return_value = odgovor
        with mock.patch("core.link_zaslon_profil.lokalno_omrezje", return_value={"vrsta": "lan"}):
            return safeer_control.SafeerControl._nova_oddaljena_seja(lazna, "n-1")

    def test_zajem_pada_razumljivo(self):
        r = self._lazna({"ok": False, "koda": "zajem_pada", "data": {"konec": "zajem", "razlog": "izhod_234"},
                         "message": "Zajem zaslona na tem racunalniku ne deluje (izhod_234). Poskusite znova cez 60 s."})
        self.assertEqual(r, {"ok": False, "koda": "zajem_pada", "message": link_gledalec.sporocilo_konca("de", "zajem")})

    def test_druga_zavrnitev_ostane_nespremenjena(self):
        r = self._lazna({"ok": False, "koda": "zavrnjeno", "message": "Uporabnik je zavrnil."})
        self.assertEqual(r, {"ok": False, "message": "Uporabnik je zavrnil.", "koda": "zavrnjeno"})


if __name__ == "__main__":
    unittest.main()
