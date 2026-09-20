"""Korak 6 v zivo: racunalnik in Android kot ponudnika aplikacij prek Safeer Linka (Protocol v1).

1. Racunalnik (Controlova identiteta) se prijavi s katalogom `apps` - hub ga pokaze v /cast/devices.
2. Isti odjemalec vprasa zaslon (Android) za `apps.list` in dobi seznam v enotni obliki
   {"enabled", "items": [{"id", "name"}]} - isti ukaz kot pri racunalniku.

Preskoci se, ce Control ni seznanjen ali hub ne odgovarja. Tekoci Control se za trenutek odklopi
in sam vrne (kot pri test_link_krog_zivo).
"""
import json
import threading
import time
import unittest

from core import link_hub
from tests.test_link_krog_zivo import _seznanitve
from tests.test_link_naprave_zivo import naprave_na_hubu

KATALOG = {"app:preizkus-safeer.desktop": {"name": "Preizkus Safeer", "kind": "linux"}}


class PonudnikVZivo(unittest.TestCase):
    def test_katalog_in_apps_list(self):
        izbran = None
        for hub, zeton, odtis in _seznanitve():
            if link_hub.je_hub(link_hub._osnova(hub), odtis=odtis):
                izbran = (hub, zeton, odtis)
                break
        if not izbran:
            self.skipTest("noben seznanjeni hub se ne oglasa")
        hub, zeton, odtis = izbran
        ime_g = link_hub._ime_naprave().split(".")[0]
        device_id = link_hub.id_naprave() + "-control"
        prejeto = []
        dogodek = threading.Event()

        def ob_sporocilu(s):
            prejeto.append(s)
            if s.get("type") == "control.result":
                dogodek.set()

        p = link_hub.Povezava(hub, zeton, device_id, "Safeer Control (" + ime_g + ")", odtis=odtis,
                              dodatne_zmoznosti=["apps"], katalog=lambda: KATALOG)
        p.ob_sporocilu = ob_sporocilu
        self.assertTrue(p.poveži(), "prijava")
        try:
            time.sleep(1.5)
            koda, naprave = naprave_na_hubu(hub, zeton, odtis)
            self.assertEqual(koda, 200)
            jaz = [n for n in naprave if n.get("id") == device_id]
            self.assertTrue(jaz, "racunalnik mora biti na seznamu")
            print(f"\n  racunalnik: kind={jaz[0].get('kind')} apps={jaz[0].get('apps')}")
            self.assertEqual(jaz[0].get("apps"), KATALOG, "hub mora hraniti katalog iz prijave")

            zasloni = [n for n in naprave if n.get("role") == "receiver" and "remote" in (n.get("capabilities") or [])]
            if not zasloni:
                self.skipTest("na hubu ni zaslona z daljincem")
            cilj = zasloni[0]
            p.poslji({"id": "p6-apps", "type": "control.command", "target": cilj["id"],
                      "payload": {"action": "apps.list", "params": {}}})
            self.assertTrue(dogodek.wait(10), "zaslon mora odgovoriti na apps.list")
            odgovor = [s for s in prejeto if s.get("type") == "control.result"][-1].get("payload") or {}
            podatki = odgovor.get("data") or {}
            print(f"  {cilj.get('id')} ({cilj.get('platform')}): ok={odgovor.get('ok')} "
                  f"enabled={podatki.get('enabled')} items={len(podatki.get('items') or [])}")
            self.assertTrue(odgovor.get("ok"), odgovor)
            self.assertTrue(podatki.get("enabled"))
            elementi = podatki.get("items") or []
            self.assertTrue(elementi and "id" in elementi[0] and "name" in elementi[0], elementi[:1])
        finally:
            p.zapri()


if __name__ == "__main__":
    unittest.main()
