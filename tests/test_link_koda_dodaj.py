"""Seznanitev s kodo naprave na strani Safeer Linka (Safeer Control).

11. 10. 2026 (lastnik): »vsaka naprava se lahko spari z vsako napravo« - z vpisom kode druge naprave ALI s prikazom
svoje 6-mestne kode. Prej je »Vpiši kodo z druge naprave« v oknu povezanih naprav poskusil prijaviti TO napravo in
obvisel pri »Preverjam …«; prijavno okno svoje kode ni kazalo. Preizkus stran zares pozene (ogrodje iz
test_link_stran_dogodki), vtipka kodo in poslje odzive zaledja.
"""
import json
import shutil
import subprocess
import unittest

from tests import test_link_stran_dogodki as osnova

# Ogrodje osnovnega preizkusa, dopolnjeno: elementi si zapomnijo poslusalce, stran dobi most SafeerLink, korak
# ["__vnesi", id, besedilo] vtipka in pritisne Enter, ["__beri", id] vrne besedilo elementa.
OGRODJE = osnova.OGRODJE.replace(
    "addEventListener() {}, removeEventListener() {}, setAttribute() {}",
    "addEventListener(tip, f) { (stor.__poslusalci[tip] = stor.__poslusalci[tip] || []).push(f); }, "
    "removeEventListener() {}, setAttribute() {}",
).replace(
    "const stor = { id: id,", "const stor = { __poslusalci: {}, id: id,"
).replace(
    "  addEventListener() {}, removeEventListener() {},\n  createElement()",
    "  __poslusalci: {}, addEventListener(tip, f) { (document.__poslusalci[tip] = document.__poslusalci[tip] || []).push(f); },"
    " removeEventListener() {},\n  createElement()",
).replace(
    "okno.window = okno;",
    "okno.window = okno; okno.__klici = [];\n"
    "okno.SafeerLink = new Proxy({}, { get(t, k) { return function () { okno.__klici.push([String(k)].concat(Array.from(arguments))); }; } });",
).replace(
    "vm.runInContext(vir, okno);",
    "vm.runInContext(vir, okno);\n(document.__poslusalci.DOMContentLoaded || []).forEach(function (f) { try { f(); } catch (e) { okno.__napake.push(String(e.stack || e)); } });",
).replace(
    "  if (korak[0] === '__nastavi') el(korak[1])[korak[2]] = korak[3];",
    "  if (korak[0] === '__nastavi') el(korak[1])[korak[2]] = korak[3];\n"
    "  else if (korak[0] === '__vnesi') { const e = el(korak[1]); (e.__poslusalci.focus || []).forEach(f => f({}));"
    " e.value = korak[2]; (e.__poslusalci.keydown || []).forEach(f => f({ key: 'Enter', preventDefault() {} })); }",
).replace(
    "const BERI = ['opombaDeljenje',", "const BERI = ['opombaDodajKoda', 'dodajVnosKode', 'prijavaKodaTe', 'prijavaKodaTeBlok', 'opombaDeljenje',"
).replace(
    "console.log(JSON.stringify({ napake: okno.__napake, slike: slike }));",
    "console.log(JSON.stringify({ napake: okno.__napake, slike: slike, klici: okno.__klici }));",
)


def _stran(koraki):
    izid = subprocess.run([shutil.which("node"), "-e", OGRODJE, osnova.STRAN, json.dumps(koraki)],
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    if izid.returncode != 0:
        raise AssertionError("stran se ni izvedla: " + izid.stderr[-1500:])
    podatki = json.loads(izid.stdout)
    if podatki.get("ogrodje"):
        raise AssertionError("ogrodje preizkusa: " + podatki["ogrodje"])
    if podatki["napake"]:
        raise AssertionError("stran je padla: " + podatki["napake"][0][:1500])
    return podatki


@unittest.skipUnless(shutil.which("node"), "node ni namescen")
class KodaVDodajNapravo(unittest.TestCase):
    def test_vnos_dovoli_drugo_napravo(self):
        p = _stran([["__vnesi", "dodajVnosKode", "725 038"]])
        self.assertIn(["odobriKodo", "725038"], p["klici"])
        self.assertFalse(any(k[0] in ("potrdiKodo", "seznani") for k in p["klici"]),
                         "naprava v Linku se ne prijavlja znova: %r" % p["klici"])
        self.assertEqual(p["slike"][0]["opombaDodajKoda"]["besedilo"], "Preverjam …")

    def test_izidi(self):
        primeri = [({"ok": True, "ime": "Televizor"}, "Dovoljeno: Televizor se zdaj poveže."),
                   ({"ok": True, "ime": ""}, "Dovoljeno: naprava se zdaj poveže."),
                   ({"ok": False, "razlog": "qr_ne_obstaja"}, "Ta koda ne velja"),
                   ({"ok": False, "razlog": "prevec_poskusov"}, "Preveč napačnih kod"),
                   ({"ok": False, "razlog": "ista_naprava"}, "To je koda te naprave"),
                   ({"ok": False, "razlog": "ni_seznanjena"}, "še ni v Safeer Linku"),
                   ({"ok": False, "razlog": "ni_huba"}, "se ne oglasi")]
        for izid, napis in primeri:
            p = _stran([["__vnesi", "dodajVnosKode", "725038"], ["kodaOdobrena", izid]])
            self.assertIn(napis, p["slike"][1]["opombaDodajKoda"]["besedilo"], izid)
            self.assertEqual(p["slike"][1]["dodajVnosKode"]["vrednost"], "", "vnos je prazen za novo kodo")

    def test_kratka_koda(self):
        p = _stran([["__vnesi", "dodajVnosKode", "12"]])
        self.assertFalse(any(k[0] == "odobriKodo" for k in p["klici"]))
        self.assertTrue(p["slike"][0]["opombaDodajKoda"]["besedilo"])


@unittest.skipUnless(shutil.which("node"), "node ni namescen")
class LastnaKodaVPrijavi(unittest.TestCase):
    def test_qr_pokaze_kodo_te_naprave(self):
        p = _stran([["qr", {"svg": "<svg></svg>", "velja": 300, "koda": "123456"}]])
        self.assertEqual(p["slike"][0]["prijavaKodaTe"]["besedilo"], "123 456")
        self.assertFalse(p["slike"][0]["prijavaKodaTeBlok"]["skrit"])

    def test_brez_kode_ali_napaka(self):
        p = _stran([["qr", {"svg": "<svg></svg>", "velja": 300}], ["qr", {"napaka": "ni_huba"}]])
        self.assertTrue(p["slike"][0]["prijavaKodaTeBlok"]["skrit"], "star Hub ali brez kode: blok skrit")
        self.assertTrue(p["slike"][1]["prijavaKodaTeBlok"]["skrit"])
