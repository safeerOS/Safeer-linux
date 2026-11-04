"""Bliznjici »Safeer OS« in »Safeer brskalnik« v plosci naprave zazeneta paket, ki ga ta naprava ima (tedenski pregled
4. 11. 2026): prej sta na telefonu zagnala si.safeer.os in si.safeer.tv (paketa televizorja)."""
import json
import os
import shutil
import subprocess
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK_JS = os.path.join(KOREN, "assets", "link", "link.js")

SKRIPTA = r"""
const s = require('fs').readFileSync(process.argv[1], 'utf8');
const a = s.indexOf('  var PAKETI_ZASLONA = {');
const konec = 'function paketBrskalnika(n) { return paketNaZaslonu(n, "brskalnik"); }';
const b = s.indexOf(konec);
if (a < 0 || b < 0) { console.log('null'); process.exit(0); }
const f = new Function(s.slice(a, b + konec.length) + '; return {os: paketSafeerOs, br: paketBrskalnika};')();
const naprave = JSON.parse(process.argv[2]);
console.log(JSON.stringify(naprave.map(n => [f.os(n), f.br(n)])));
"""

PRIMERI = [
    ({"platforma": "tv"}, ["si.safeer.os", "si.safeer.tv"]),
    ({"vrsta": "screen"}, ["si.safeer.os", "si.safeer.tv"]),
    ({"platforma": "tablet"}, ["si.safeer.tablet", "si.safeer.tablet"]),
    ({"platforma": "phone"}, ["si.safeer.phone", "com.safeer.mobile.browser"]),
    ({"platforma": "phone", "aplikacije": {"com.safeer.mobile.browser": {}}}, ["", "com.safeer.mobile.browser"]),
    ({"platforma": "phone", "aplikacije": {"si.safeer.phone": {}}}, ["si.safeer.phone", ""]),
    ({"platforma": "tv", "aplikacije": {"si.safeer.tv": {}}}, ["", "si.safeer.tv"]),
    ({"platforma": "linux"}, ["", ""]),
    ({}, ["", ""]),
]


class PaketiZaslona(unittest.TestCase):
    def test_paket_po_platformi_in_katalogu(self):
        if not shutil.which("node"):
            self.skipTest("node ni namescen")
        izid = subprocess.run(["node", "-e", SKRIPTA, LINK_JS, json.dumps([n for n, _ in PRIMERI])],
                              capture_output=True, text=True, timeout=30, check=True).stdout
        dobljeno = json.loads(izid)
        self.assertIsNotNone(dobljeno, "ni funkcij paketSafeerOs/paketBrskalnika")
        for (naprava, pricakovano), d in zip(PRIMERI, dobljeno):
            self.assertEqual(d, pricakovano, naprava)

    def test_gumba_brez_paketa_skrita(self):
        with open(LINK_JS, encoding="utf-8") as f:
            s = f.read()
        self.assertIn('pokazi("gumbOdpriSafeerOs", !!paketOs);', s)
        self.assertIn('pokazi("gumbOdpriBrskalnik", !!paketBr);', s)
        self.assertNotIn('"si.safeer.tablet" : "si.safeer.tv"', s)


if __name__ == "__main__":
    unittest.main()
