"""Izklop peskovnika WebKita (core/peskovnik_userns.py) velja samo za ta proces (odprta tocka pregleda 1.0.128).

Na Ubuntu 24.04+ brez nasega profila AppArmor pred_nitmi() da v okolje procesa
WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1 (sicer bi WebKit ob prvi strani koncal proces). Programi, ki jih uporabnik
odpre iz Safeer OS (meni, dock, »Odpri z«), dobijo okolje iz zasebni_webkit.okolje_za_zunanje() - prej s to
spremenljivko: GNOME Web, Evolution ali Geary (imajo svoj profil, peskovnik jim dela) so tekli brez peskovnika. AGENTS.md, Okolje procesa: okolja procesa med tekom ne spreminjamo
(odstranitev bi bila unsetenv ob tekocih nitih), podprocesu damo svoje okolje (env=).
"""
import os
import unittest
from unittest import mock

from core import peskovnik_userns as p
from core import zasebni_webkit

IZKLOPLJEN = {"omejeno": True, "oznaka": "unconfined", "deluje": False, "izklopljen": True}
DELUJE = {"omejeno": False, "oznaka": "", "deluje": True, "izklopljen": False}


class ZunanjiProgramBrezNasegaIzklopa(unittest.TestCase):
    def test_nas_izklop_ne_gre_v_zunanji_program(self):
        okolje = {"PATH": "/usr/bin", p.IZKLOP: "1", "HOME": "/tmp"}
        with mock.patch.object(p, "_ob_zagonu", dict(IZKLOPLJEN)):
            zunanje = zasebni_webkit.okolje_za_zunanje(okolje)
        self.assertFalse(p.IZKLOP in zunanje, "nas izklop v okolju zunanjega programa")
        self.assertEqual(zunanje["PATH"], "/usr/bin")
        self.assertEqual(okolje[p.IZKLOP], "1", "podano okolje (in okolje procesa) ostane nespremenjeno")

    def test_okolje_procesa_ostane(self):
        with mock.patch.object(p, "_ob_zagonu", dict(IZKLOPLJEN)), mock.patch.dict(os.environ, {p.IZKLOP: "1"}):
            prej = dict(os.environ)
            zunanje = zasebni_webkit.okolje_za_zunanje()
            self.assertEqual(dict(os.environ), prej)
        self.assertFalse(p.IZKLOP in zunanje, "nas izklop v okolju zunanjega programa")

    def test_uporabnikov_izklop_ostane(self):
        """Ce je spremenljivko nastavil uporabnik sam (peskovnik pri nas dela), je to njegova izbira za vse programe."""
        okolje = {p.IZKLOP: "1"}
        with mock.patch.object(p, "_ob_zagonu", dict(DELUJE)):
            self.assertEqual(zasebni_webkit.okolje_za_zunanje(okolje).get(p.IZKLOP), "1")
        with mock.patch.object(p, "_ob_zagonu", None):
            self.assertEqual(zasebni_webkit.okolje_za_zunanje(okolje).get(p.IZKLOP), "1")

    def test_druga_vrednost_ni_nasa(self):
        with mock.patch.object(p, "_ob_zagonu", dict(IZKLOPLJEN)):
            self.assertEqual(zasebni_webkit.okolje_za_zunanje({p.IZKLOP: "yes"}).get(p.IZKLOP), "yes")


if __name__ == "__main__":
    unittest.main()
