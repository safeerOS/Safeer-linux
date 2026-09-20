"""Kdo je povezan na hub (v zivo): /cast/devices z zetonom Controla tega racunalnika.

Preskoci se, ce Control ni seznanjen ali se hub ne oglasa. Preveri, da hub vidi vsaj samega sebe
(gostitelj je hkrati zaslon) - torej da se je njegov lastni sprejemnik prijavil z vezano vstopnico.
"""
import json
import unittest
from urllib.parse import urlparse

from core import link_hub, link_krog, link_tls
from tests.test_link_krog_zivo import _seznanitve


def naprave_na_hubu(hub: str, zeton: str, odtis: str):
    """/cast/devices vrne gol seznam (ne objekta), zato ga beremo mimo link_tls.zahteva."""
    u = urlparse(link_hub._osnova(hub))
    p = link_tls._PripetaHttps(u.hostname, u.port or 443, odtis, 5.0)
    try:
        p.request("GET", "/cast/devices", headers={"X-Safeer-Token": zeton})
        o = p.getresponse()
        return o.status, json.loads(o.read().decode("utf-8", "replace") or "[]")
    finally:
        p.close()


def je_id_naprave(device_id: str) -> bool:
    """Id iz kljuca (n-<16 hex>, zdajsnji) ali star id po vrsti naprave (tv-, phone-, tablet-, pc-)."""
    return link_krog.je_id_iz_kljuca(device_id) or device_id.startswith(("tv-", "phone-", "tablet-", "pc-"))


class NapraveVZivo(unittest.TestCase):
    def test_id_naprave(self):
        self.assertTrue(je_id_naprave("n-d3f9a8eed4e33899"))
        self.assertTrue(je_id_naprave("n-c7100e7a94c728e1-os"))
        self.assertTrue(je_id_naprave("tv-sm-x210"))
        self.assertFalse(je_id_naprave("nekaj"))

    def test_povezane_naprave(self):
        izbran = None
        for hub, zeton, odtis in _seznanitve():
            if link_hub.je_hub(link_hub._osnova(hub), odtis=odtis):
                izbran = (hub, zeton, odtis)
                break
        if not izbran:
            self.skipTest("noben seznanjeni hub se ne oglasa")
        hub, zeton, odtis = izbran
        koda, naprave = naprave_na_hubu(hub, zeton, odtis)
        self.assertEqual(koda, 200, "hub mora vrniti seznam naprav")
        self.assertIsInstance(naprave, list)
        print(f"\n  hub {hub}:")
        for n in naprave:
            # Protocol v1: model naprave in katalog aplikacij (prazno pri odjemalcih 0.2).
            print(f"    {n.get('id')}: role={n.get('role')} protocol={n.get('protocol')} platform={n.get('platform')} "
                  f"kind={n.get('kind')} version={n.get('version')} priority={n.get('priority')} "
                  f"apps={len(n.get('apps') or {})}")
        self.assertTrue(any(je_id_naprave(str(n.get("id", ""))) for n in naprave),
                        "hub mora imeti vsaj eno prijavljeno napravo")


if __name__ == "__main__":
    unittest.main()
