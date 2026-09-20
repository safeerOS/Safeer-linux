"""Krog zaupanja v zivo: Control tega racunalnika proti pravemu hubu (televizor).

Tece samo, ce je Safeer Control tu ze seznanjen (~/.config/safeer-control/link.json) in se hub
oglasa; sicer se test preskoci. Prvi vpis gre z zetonom in vpise kljuc v krog, drugi vpis mora
iti s podpisom kljuca brez zetona. Uporablja Controlovo identiteto, zato se tekoci Control za
trenutek odklopi in sam vrne (to je isto kot kratek izpad omrezja).
"""
import json
import os
import time
import unittest

from core import link_hub, link_krog

POT = os.path.expanduser("~/.config/safeer-control/link.json")


def _seznanitve():
    """[(hub_url, zeton, odtis)]: trenutna in vse zapomnjene seznanitve Controla."""
    try:
        with open(POT, "r", encoding="utf-8") as d:
            n = json.load(d) or {}
    except Exception:
        return []
    kandidati = []
    hub, zeton, odtis = n.get("hub_url"), n.get("control_token"), n.get("hub_fp")
    if hub and zeton and odtis:
        kandidati.append((str(hub), str(zeton), str(odtis)))
    s = n.get("seznanitve")
    if isinstance(s, dict):
        for fp, z in s.items():
            if isinstance(z, dict) and z.get("token") and z.get("hub_url"):
                kandidati.append((str(z["hub_url"]), str(z["token"]), str(fp)))
    return [k for k in kandidati if k[0].startswith("wss://")]


class KrogVZivo(unittest.TestCase):
    def test_vpis_in_prijava_s_podpisom(self):
        kandidati = _seznanitve()
        if not kandidati:
            self.skipTest("Control ni seznanjen")
        izbran = None
        for hub, zeton, odtis in kandidati:
            if link_hub.je_hub(link_hub._osnova(hub), odtis=odtis):
                izbran = (hub, zeton, odtis)
                break
        if not izbran:
            self.skipTest("noben seznanjeni hub se ne oglasa")
        hub, zeton, odtis = izbran
        print(f"\n  hub: {hub} (odtis {odtis[:12]}…)")
        ime_g = link_hub._ime_naprave().split(".")[0]
        device_id, ime = link_hub.id_naprave() + "-control", "Safeer Control (" + ime_g + ")"

        prej = link_krog.je_vpisan(device_id)
        sporocila = []
        p = link_hub.Povezava(hub, zeton, device_id, ime, odtis=odtis)
        p.ob_sporocilu = sporocila.append
        self.assertTrue(p.poveži(), "prva prijava")
        time.sleep(1.5)
        prva = (p.prijava_s_podpisom, p.vpisana_v_krog)
        p.zapri()
        potrditve = [s for s in sporocila if s.get("type") == "cast.ack"]
        print(f"  potrditev prijave: {[(s.get('status'), s.get('error_code')) for s in potrditve]}")
        self.assertTrue(potrditve and potrditve[0].get("status") == "accepted", "hub mora prijavo sprejeti (vstopnica je vezana na ta device_id)")
        print(f"  prej vpisan: {prej}; prva prijava s podpisom: {prva[0]}, vpisala v krog: {prva[1]}")
        self.assertTrue(link_krog.je_vpisan(device_id), "po prvi prijavi mora biti kljuc v krogu")
        if not prej:
            # Nov id iz kljuca: ce je nas kljuc v krogu ze pod starim id-jem, gre ze prva prijava s podpisom
            # in hub nov id vpise kot alias; sicer se z zetonom vpise v krog.
            self.assertTrue(prva[1] or prva[0], "z zetonom bi se moral vpisati v krog ali pa priti s podpisom (alias)")

        p2 = link_hub.Povezava(hub, zeton, device_id, ime, odtis=odtis)
        self.assertTrue(p2.poveži(), "druga prijava")
        time.sleep(1.0)
        druga = p2.prijava_s_podpisom
        p2.zapri()
        print(f"  druga prijava s podpisom: {druga}")
        self.assertTrue(druga, "druga prijava mora iti s podpisom kljuca, ne z zetonom")

        k = link_krog.krog()
        clani = {i: (c["ime"], c["platforma"]) for i, c in k.json()["clani"].items()}
        print(f"  krog ({k.stevilo()}): {clani}")
        self.assertGreaterEqual(k.stevilo(), 2, "v krogu morata biti vsaj hub in ta racunalnik")
        self.assertTrue(any(c["platforma"] == "tv" for c in k.json()["clani"].values()), "hub (tv) v krogu")


if __name__ == "__main__":
    unittest.main()
