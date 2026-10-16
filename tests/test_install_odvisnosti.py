#!/usr/bin/env python3
"""install.sh preveri vse pakete, ki jih brskalnik iz izvorne kode (safeer_mint.py, GTK3) potrebuje za zagon.

Vir resnice je Depends paketa GTK3 v build_deb.sh. Pregled 16. 10. 2026: install.sh ni preveril gir1.2-soup-3.0,
core/doh_proxy.py pa zahteva Soup 3.0 - brskalnik je na svezem sistemu padel ob zagonu."""

import os
import re
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(ime: str) -> str:
    with open(os.path.join(KOREN, ime), encoding="utf-8") as f:
        return f.read()


class PreizkusOdvisnostiNamestitve(unittest.TestCase):
    def test_install_sh_preveri_odvisnosti_paketa_gtk3(self):
        namestitev = _beri("install.sh")
        seznam = re.search(r"^for pkg in ([^;]+); do", namestitev, re.M)
        self.assertIsNotNone(seznam)
        preverjeni = set(seznam.group(1).split())
        gtk3 = re.search(r'SAFEER_BRSKALNIK_GTK3:-0}" = 1 ]; then\s+ODVISNOSTI="([^"]+)"', _beri("build_deb.sh"))
        self.assertIsNotNone(gtk3)
        paketi = {re.sub(r"\s*\(.*\)", "", p).strip() for p in gtk3.group(1).split(",")} - {"python3"}
        self.assertLessEqual(paketi, preverjeni)

    def test_install_sh_zazene_brskalnik_gtk3(self):
        # Seznam zgoraj velja samo, dokler install.sh zaganja safeer_mint.py (GTK3); GTK4 brskalnik potrebuje drugega.
        self.assertIn('safeer_mint.py"', _beri("safeer-mint.sh"))
        self.assertIn("gi.require_version('Gtk', '3.0')", _beri("safeer_mint.py"))
        self.assertIn("gi.require_version('WebKit2', '4.1')", _beri("safeer_mint.py"))


if __name__ == "__main__":
    unittest.main()
