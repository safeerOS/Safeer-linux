"""Lupa namizja: vpis, ki je spletni naslov, ima prvi zadetek »Odpri safeer.si«, pod njim ostane »Isci »safeer.si« v
spletu« (kot omnibox Chrome in Safari; lastnik 21. 10. 2026). Prej se je pokazalo samo iskanje.

Obe lupi (namizje QML in delovna povrsina WebKit) vzameta naslov iz core/config.naslov_za_lupo - isto pravilo kot
naslovna vrstica Spleta."""
import os
import shutil
import subprocess
import sys
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import naslov_za_lupo  # noqa: E402
from besedila_namizja import JEZIKOV, stevilo  # noqa: E402


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class TestNaslovZaLupo(unittest.TestCase):
    def test_naslov(self):
        for vnos, naslov in (("safeer.si", "https://safeer.si"), (" github.com/safeerOS ", "https://github.com/safeerOS"),
                             ("192.168.0.1", "http://192.168.0.1"), ("localhost:8080", "http://localhost:8080"),
                             ("https://safeer.si/a b", "https://safeer.si/a%20b"), ("http://example.com", "http://example.com")):
            with self.subTest(vnos=vnos):
                self.assertEqual(naslov_za_lupo(vnos), naslov)

    def test_ni_naslov(self):
        for vnos in ("", "  ", "test", "vreme ljubljana", "racun.pdf", "?safeer.si", "ime@posta.si", "tel:123",
                     "javascript:alert(1)"):
            with self.subTest(vnos=vnos):
                self.assertEqual(naslov_za_lupo(vnos), "")


class TestLupa(unittest.TestCase):
    def test_zaledje(self):
        self.assertIn('"naslovLupe":', beri("safeer_os.py"))
        self.assertEqual(stevilo("odpriNaslov"), JEZIKOV)

    def test_namizje_qml(self):
        qml = beri("assets", "os", "qml", "Namizje.qml")
        self.assertIn('pocakaj("naslovLupe", [q], "naslov"', qml)
        sestavi = qml[qml.index("function sestavi()"):qml.index("function privzeti(")]
        # »Odpri« pred »Isci v spletu« v isti skupini
        self.assertLess(sestavi.index('vrsta: "spletNaslov"'), sestavi.index('vrsta: "splet", skupina'))
        privzeti = qml[qml.index("function privzeti("):qml.index("function enter()")]
        self.assertIn('v[n].vrsta === "spletNaslov"', privzeti)
        self.assertIn('z.vrsta === "spletNaslov"', qml[qml.index("function kljucZadetka"):qml.index("function ocene(")])

    def test_delovna_povrsina(self):
        js = beri("assets", "os", "delovna.js")
        self.assertIn('klic("naslovLupe", [q])', js)
        self.assertIn('[{ vrsta: "spletNaslov", url: r[6], q: q }]', js)
        izberi = js[js.index("  function izberiZadetek(v) {"):js.index("  function izberiZadetek(v) {") + 600]
        self.assertIn('v.vrsta === "spletNaslov") odpriSplet(v.url)', izberi)

    @unittest.skipUnless(shutil.which("node"), "node ni namescen")
    def test_delovna_privzeti_je_odpri(self):
        js = beri("assets", "os", "delovna.js")
        blok = js[js.index("  function ocenaPrograma(p, ql) {"):js.index("  function isci(q) {")]
        koda = """
var assert = require("assert");
var SafeerIskanje = require(process.argv[1]);
function t(k) { return k; }
var D = { naprave: [] }, P = { naprave: [] };
""" + blok + """
var odpri = { vrsta: "spletNaslov", url: "https://safeer.si", q: "safeer.si" }, isci = { vrsta: "splet", q: "safeer.si" };
var prg = { vrsta: "program", p: { id: "safeer.desktop", ime: "safeer.si pomocnik" } };
assert.strictEqual(kljucZadetka(odpri), "spletNaslov");
assert.strictEqual(privzetiZadetek([odpri, isci, prg], "safeer.si", {}), 0, "Enter odpre naslov");
U.izbire = [["safeer.si", "splet", Math.round(Date.now() / 1000), false]];
assert.strictEqual(privzetiZadetek([odpri, isci, prg], "safeer.si", naucenaOcena("safeer.si", Math.round(Date.now() / 1000))), 1,
                   "naucena izbira (iskanje) ostane prednost");
"""
        subprocess.run(["node", "-e", koda, os.path.join(KOREN, "assets", "os", "iskanje.js")], check=True)


if __name__ == "__main__":
    unittest.main()
