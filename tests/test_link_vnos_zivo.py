"""Safeer Vnos v zivo: racunalnik poslje input.* tablici (zaslonu z daljincem na Androidu).

Ce uporabnik Safeer Vnos (storitev dostopnosti) na tablici se ni vklopil, mora tablica odgovoriti
z jasno kodo `vnos_ni_vklopljen`; ce je vklopljen, prazno besedilo v polje s fokusom ne spremeni nicesar.
Preskoci se, ce Control ni seznanjen ali na hubu ni tablice/telefona z daljincem.
"""
import threading
import time
import unittest

from core import link_hub
from tests.test_link_krog_zivo import _seznanitve
from tests.test_link_naprave_zivo import naprave_na_hubu

PLATFORME_Z_VNOSOM = ("tablet", "handheld")


class VnosVZivo(unittest.TestCase):
    def test_input_na_tablici(self):
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
            if s.get("type") == "control.result" or (s.get("type") == "control.ack" and s.get("status") != "accepted"):
                dogodek.set()

        p = link_hub.Povezava(hub, zeton, device_id, "Safeer Control (" + ime_g + ")", odtis=odtis)
        p.ob_sporocilu = ob_sporocilu
        self.assertTrue(p.poveži(), "prijava")
        try:
            time.sleep(1.5)
            koda, naprave = naprave_na_hubu(hub, zeton, odtis)
            self.assertEqual(koda, 200)
            zasloni = [n for n in naprave if n.get("role") == "receiver" and n.get("platform") in PLATFORME_Z_VNOSOM
                       and "remote" in (n.get("capabilities") or [])]
            if not zasloni:
                self.skipTest("na hubu ni tablice ali telefona z daljincem")
            cilj = zasloni[0]
            p.poslji({"id": "vnos-preizkus", "type": "control.command", "target": cilj["id"],
                      "payload": {"action": "input.text", "params": {"text": ""}}})
            self.assertTrue(dogodek.wait(10), "naprava mora odgovoriti na input.text")
            s = [x for x in prejeto if x.get("type") in ("control.result", "control.ack")][-1]
            telo = s.get("payload") or {}
            print(f"\n  {cilj.get('id')} ({cilj.get('platform')}): {s.get('type')} {telo}")
            self.assertEqual(s.get("type"), "control.result", s)
            if not telo.get("ok"):
                self.assertIn(telo.get("code"), ("vnos_ni_vklopljen", "vnos_ni_uspel"), telo)
        finally:
            p.zapri()


if __name__ == "__main__":
    unittest.main()
