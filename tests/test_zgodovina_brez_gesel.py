"""Zgodovina, zaznamki in obnovljeni zavihki ne smejo hraniti uporabniskega imena in gesla (neodvisni pregled 1.0.131).

URL »http://admin:geslo@192.168.0.1/« ali »https://user:secret@evil.com/« ne sme na disk s poverilnicami.
core/config.prikazni_naslov odstrani userinfo."""
import json
import os
import struct
import sys
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import zgodovina  # noqa: E402
from core.config import ConfigManager  # noqa: E402
from core.uvoz_zavihkov import preberi_sejo, UKAZ_NAVIGACIJA, UKAZ_IZBRAN_INDEKS  # noqa: E402


class TestZgodovinaBrezPoverilnic(unittest.TestCase):
    def test_zgodovina_dodaj_brez_gesla(self):
        """core/zgodovina.dodaj v history.json nikoli ne zapise uporabnika in gesla."""
        with tempfile.TemporaryDirectory() as tmp:
            pot = os.path.join(tmp, "history.json")
            self.assertTrue(zgodovina.dodaj(pot, "http://admin:zelotajnogeslo@192.168.0.1/skrbnik"))
            with open(pot, "r", encoding="utf-8") as f:
                vsebina = f.read()
            self.assertNotIn("zelotajnogeslo", vsebina)
            self.assertNotIn("admin:", vsebina)
            vnosi = zgodovina.nalozi(pot)
            self.assertEqual(len(vnosi), 1)
            self.assertEqual(vnosi[0]["url"], "http://192.168.0.1/skrbnik")
            self.assertEqual(vnosi[0]["title"], "http://192.168.0.1/skrbnik")

    def test_zgodovina_naslov_in_ime_z_userinfo(self):
        """Tudi ce klicatelj kot naslov strani (ime) poda surov URL z geslom, se geslo odstrani."""
        with tempfile.TemporaryDirectory() as tmp:
            pot = os.path.join(tmp, "history.json")
            self.assertTrue(zgodovina.dodaj(pot, "https://user:skrivnost@primer.si/profil",
                                            "https://user:skrivnost@primer.si/profil"))
            with open(pot, "r", encoding="utf-8") as f:
                vsebina = f.read()
            self.assertNotIn("skrivnost", vsebina)
            self.assertNotIn("user:", vsebina)
            vnosi = zgodovina.nalozi(pot)
            self.assertEqual(vnosi[0]["url"], "https://primer.si/profil")
            self.assertEqual(vnosi[0]["title"], "https://primer.si/profil")


class TestPortaliBrezPoverilnic(unittest.TestCase):
    def test_add_portal_odstrani_userinfo(self):
        """Dodajanje priljubljene strani (core/config.add_portal) odstrani poverilnice iz URL in naslova."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = ConfigManager()
            cfg.config_dir = tmp
            cfg.config_file = os.path.join(tmp, "settings.json")
            p_id = cfg.add_portal("", "http://admin:tajna123@192.168.1.1/nadzor")
            self.assertTrue(p_id)
            portali = cfg.get_portals()
            dodan = next((p for p in portali if p.get("id") == p_id), None)
            self.assertIsNotNone(dodan)
            self.assertEqual(dodan["url"], "http://192.168.1.1/nadzor")
            self.assertNotIn("tajna123", json.dumps(portali))
            self.assertNotIn("admin:", json.dumps(portali))

    def test_update_portal_odstrani_userinfo(self):
        """Posodobitev priljubljene strani (core/config.update_portal) odstrani poverilnice."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = ConfigManager()
            cfg.config_dir = tmp
            cfg.config_file = os.path.join(tmp, "settings.json")
            p_id = cfg.add_portal("Test", "http://192.168.1.1/")
            uspeh = cfg.update_portal(p_id, "Novo", "http://root:skrito@192.168.1.1/admin", "🌐")
            self.assertTrue(uspeh)
            portali = cfg.get_portals()
            posodobljen = next((p for p in portali if p.get("id") == p_id), None)
            self.assertIsNotNone(posodobljen)
            self.assertEqual(posodobljen["url"], "http://192.168.1.1/admin")
            self.assertNotIn("skrito", json.dumps(portali))


class TestUvozZavihkovBrezPoverilnic(unittest.TestCase):
    def test_preberi_sejo_odstrani_userinfo(self):
        """core/uvoz_zavihkov.preberi_sejo odstrani poverilnice iz obnovljenih zavihkov."""
        # Zgradimo minimalno veljavno SNSS sejo z navigacijo
        url = "http://skrbnik:geslo123@usmerjevalnik.lan/"
        url_b = url.encode("utf-8")
        pad = ((len(url_b) + 3) & ~3) - len(url_b)
        niz_podatki = struct.pack("<i", len(url_b)) + url_b + (b"\x00" * pad)
        # Pickle payload: uint32 velikost_pickla, int32 tab, int32 indeks, niz url
        pickle_payload = struct.pack("<iii", len(niz_podatki) + 8, 1, 0) + niz_podatki
        ukaz_nav = struct.pack("<H", len(pickle_payload) + 1) + bytes([UKAZ_NAVIGACIJA]) + pickle_payload
        ukaz_izb = struct.pack("<H", 9) + bytes([UKAZ_IZBRAN_INDEKS]) + struct.pack("<ii", 1, 0)
        snss = b"SNSS" + struct.pack("<i", 1) + ukaz_nav + ukaz_izb

        naslovi = preberi_sejo(snss)
        self.assertEqual(len(naslovi), 1)
        self.assertEqual(naslovi[0], "http://usmerjevalnik.lan/")
        self.assertNotIn("geslo123", naslovi[0])


class TestKodaOsSplet(unittest.TestCase):
    def test_os_splet_shrani_prikazni_naslov(self):
        """core/os_splet.py _nalozen in _zapomni_zaprt morata uporabljati prikazni_naslov."""
        with open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8") as f:
            vsebina = f.read()
        self.assertIn("zgodovina.dodaj(os.path.join(self.config.config_dir, \"history.json\"), prikazni_naslov(naslov)",
                      vsebina, "zgodovina.dodaj v _nalozen mora shraniti prikazni_naslov(naslov)")
        zaprti_blok = vsebina[vsebina.index("def _zapomni_zaprt"):vsebina.index("def tipka")]
        self.assertIn("prikazni_naslov(naslov)", zaprti_blok,
                      "_zapomni_zaprt mora hraniti prikazni_naslov(naslov)")


if __name__ == "__main__":
    unittest.main()
