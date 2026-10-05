"""Oddaljeni zaslon: naprave brez omreznega naslova za sliko sploh ne prosimo.

Slika gre neposredno z naprave. Naprava, dosegljiva samo prek Global Linka, naslova nima (tests/test_link_mesh_naslovi.py);
ce bi jo vseeno prosili, bi odprla vrata in zaman cakala, uporabnik pa bi dobil nerazumljivo napako.
"""
import unittest

import safeer_control


class _Link:
    def __init__(self, naprave, odgovor=None):
        self.naprave = naprave
        self.odgovor = odgovor or {"ok": True, "data": {"port": 40123, "fp": "ab" * 32, "token": "zeton-zeton-zeton"}}
        self.klici = []

    def ukaz_pocakaj(self, naprava, dejanje, parametri, cas=6.0):
        self.klici.append((naprava, dejanje))
        return self.odgovor


def _control(naprave):
    control = safeer_control.SafeerControl.__new__(safeer_control.SafeerControl)
    control.link = _Link(naprave)
    return control


class NaslovNaprave(unittest.TestCase):
    def test_brez_naslova_naprave_ne_prosimo(self):
        for naslov in ("", "   ", None):
            control = _control([{"id": "pc-1", "ime": "Pisarna", "naslov": naslov}])
            izid = control._nova_oddaljena_seja("pc-1")
            self.assertFalse(izid["ok"])
            self.assertEqual(izid["koda"], "ni_naslova")
            self.assertIn("Pisarna", izid["message"])
            self.assertEqual(control.link.klici, [], "naprava ne sme dobiti screen.start")

    def test_z_naslovom_prosimo_in_vrnemo_naslov(self):
        control = _control([{"id": "pc-1", "ime": "Pisarna", "naslov": "192.168.0.220"}])
        izid = control._nova_oddaljena_seja("pc-1")
        self.assertTrue(izid["ok"], izid)
        self.assertEqual(izid["naslov"], "192.168.0.220")
        self.assertEqual(control.link.klici, [("pc-1", "screen.start")])

    def test_neznana_naprava(self):
        control = _control([])
        izid = control._nova_oddaljena_seja("pc-1")
        self.assertFalse(izid["ok"])
        self.assertEqual(control.link.klici, [])


class NaslovIzSeznamaHuba(unittest.TestCase):
    """Hub programu na svojem racunalniku pripise 127.0.0.1. Kadar smo pripeti na Hub DRUGE naprave, je to naslov
    tiste naprave - ne nas. Starejsi Hubi zanko posljejo tudi odjemalcem od drugod."""

    def _link(self, hub):
        from unittest import mock
        from core import safeer_link
        link = safeer_link.SafeerLink.__new__(safeer_link.SafeerLink)
        link._hub = mock.Mock(return_value=hub)
        link._id = mock.Mock(return_value="jaz")
        link._odziv = mock.Mock()
        link._v_ozadju = lambda delo: delo()
        link.zapisi_stanje_za_os = mock.Mock()
        link.internet = None
        link.internet_upravitelj = None
        link.zvok = None
        return link

    SEZNAM = {"type": "cast.devices", "devices": [
        {"id": "tablica", "name": "Tablica", "ip": "127.0.0.1", "capabilities": ["remote"]},
        {"id": "pc-2", "name": "Pisarna", "ip": "192.168.0.220", "capabilities": ["desktop"]},
        {"id": "daleč", "name": "Telefon", "ip": "", "capabilities": ["remote"]},
    ]}

    def test_hub_drugje(self):
        link = self._link("wss://192.168.0.87:8990/cast/ws")
        link._na_sporocilo_huba(self.SEZNAM)
        naslovi = {n["id"]: n["naslov"] for n in link.naprave_vse}
        self.assertEqual(naslovi, {"tablica": "192.168.0.87", "pc-2": "192.168.0.220", "daleč": ""})

    def test_svoj_hub(self):
        link = self._link("wss://127.0.0.1:8990/cast/ws")
        link._na_sporocilo_huba(self.SEZNAM)
        naslovi = {n["id"]: n["naslov"] for n in link.naprave_vse}
        self.assertEqual(naslovi["tablica"], "127.0.0.1")
        self.assertEqual(naslovi["pc-2"], "192.168.0.220")


if __name__ == "__main__":
    unittest.main()
