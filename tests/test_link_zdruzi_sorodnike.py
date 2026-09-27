import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import safeer_link  # noqa: E402


class ZdruziSorodneNaprave(unittest.TestCase):
    """Tablica (ali racunalnik) z vec vlogami na istem kljucu (Safeer OS + zaslon,
    brskalnik + Safeer Control) dobi vec id-jev; hub jih oznaci z istim poljem
    "naprava". Brez zdruzevanja bi uporabnik v seznamu videl dve "napravi" za eno
    fizicno napravo - prijavljen bug (tablica se je po seznanitvi pokazala kot
    dve povezani tablici)."""

    def _naprava(self, id_, naprava="", zmoznosti=None):
        return {"id": id_, "ime": id_, "vloga": "receiver", "zmoznosti": zmoznosti or [],
                "naslov": "", "platforma": "tablet", "vrsta": "", "aplikacije": {},
                "naprava": naprava}

    def test_sorodnika_se_zdruzita(self):
        a = self._naprava("tv-sm-x210-os", naprava="n-abc123", zmoznosti=["apps"])
        b = self._naprava("tv-sm-x210", naprava="n-abc123", zmoznosti=["screen", "apps"])
        rezultat = safeer_link._zdruzi_sorodne_naprave([a, b])
        self.assertEqual(len(rezultat), 1)
        # Ostane tisti z vec zmoznostmi.
        self.assertEqual(rezultat[0]["id"], "tv-sm-x210")

    def test_brez_kljuca_ostane_locena(self):
        a = self._naprava("phone-star", naprava="")
        b = self._naprava("pc-janez", naprava="")
        rezultat = safeer_link._zdruzi_sorodne_naprave([a, b])
        self.assertEqual([n["id"] for n in rezultat], ["phone-star", "pc-janez"])

    def test_mesano_zdruzi_samo_sorodnike(self):
        tablica_os = self._naprava("n-t1-os", naprava="n-t1", zmoznosti=["apps"])
        tablica_zaslon = self._naprava("n-t1", naprava="n-t1", zmoznosti=["screen", "apps"])
        telefon = self._naprava("n-p1", naprava="n-p1")
        racunalnik = self._naprava("pc-janez", naprava="")
        rezultat = safeer_link._zdruzi_sorodne_naprave([racunalnik, tablica_os, telefon, tablica_zaslon])
        self.assertEqual(len(rezultat), 3)
        idji = [n["id"] for n in rezultat]
        self.assertIn("pc-janez", idji)
        self.assertIn("n-p1", idji)
        self.assertIn("n-t1", idji)          # tablicin zaslon (vec zmoznosti) je predstavnik
        self.assertNotIn("n-t1-os", idji)     # sorodnik se ne podvaja

    def test_prazen_seznam(self):
        self.assertEqual(safeer_link._zdruzi_sorodne_naprave([]), [])

    def test_vrstni_red_prve_pojavitve(self):
        a = self._naprava("a", naprava="")
        b = self._naprava("b-os", naprava="n-b", zmoznosti=["apps"])
        c = self._naprava("c", naprava="")
        d = self._naprava("b", naprava="n-b", zmoznosti=["screen", "apps"])
        rezultat = safeer_link._zdruzi_sorodne_naprave([a, b, c, d])
        self.assertEqual([n["id"] for n in rezultat], ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
