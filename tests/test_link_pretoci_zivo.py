"""»Pretoci aplikacijo« v zivo: racunalnik poslje tablici `apps.launch` s `stream: true`.

Tablica mora takoj odgovoriti `ok` z `data.stream == "pending"` in na zaslonu pokazati sistemsko vprasanje
za deljenje zaslona (potrdi ga uporabnik; test ga ne potrdi). Preskoci se brez huba ali tablice.
Tekoci Control se za trenutek odklopi (isti id) in sam vrne.
"""
import threading
import time
import unittest

from core import link_hub
from tests.test_link_krog_zivo import _seznanitve, posiljatelj
from tests.test_link_naprave_zivo import naprave_na_hubu


class PretociVZivo(unittest.TestCase):
    def test_apps_launch_stream(self):
        izbran = None
        for hub, zeton, odtis in _seznanitve():
            if link_hub.je_hub(link_hub._osnova(hub), odtis=odtis):
                izbran = (hub, zeton, odtis)
                break
        if not izbran:
            self.skipTest("noben seznanjeni hub se ne oglasa")
        hub, zeton, odtis = izbran
        device_id, ime_posiljatelja = posiljatelj("pretoci")
        prejeto = []
        dogodek = threading.Event()

        def ob_sporocilu(s):
            prejeto.append(s)
            if s.get("type") == "control.result" or (s.get("type") == "control.ack" and s.get("status") != "accepted"):
                dogodek.set()

        p = link_hub.Povezava(hub, zeton, device_id, ime_posiljatelja, odtis=odtis)
        p.ob_sporocilu = ob_sporocilu
        self.assertTrue(p.poveži(), "prijava")
        try:
            time.sleep(1.5)
            koda, naprave = naprave_na_hubu(hub, zeton, odtis)
            self.assertEqual(koda, 200)
            tablice = [n for n in naprave if n.get("role") == "receiver" and n.get("platform") == "tablet"]
            if not tablice:
                self.skipTest("na hubu ni tablice")
            cilj = tablice[0]
            p.poslji({"id": "pretoci-preizkus", "type": "control.command", "target": cilj["id"],
                      "payload": {"action": "apps.launch",
                                  "params": {"app": "si.safeer.tablet", "stream": True, "_posiljatelj": "ponareditev"}}})
            self.assertTrue(dogodek.wait(10), "tablica mora odgovoriti")
            s = [x for x in prejeto if x.get("type") in ("control.result", "control.ack")][-1]
            telo = s.get("payload") or {}
            print(f"\n  {cilj.get('id')}: {s.get('type')} {telo}")
            self.assertTrue(telo.get("ok"), telo)
            self.assertEqual((telo.get("data") or {}).get("stream"), "pending", telo)
        finally:
            p.zapri()


if __name__ == "__main__":
    unittest.main()
