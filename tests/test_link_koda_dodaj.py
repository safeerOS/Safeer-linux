"""»Dodaj napravo« -> »Vnesi kodo z druge naprave« v Safeer Controlu: odziv na kodo pride do uporabnika.

11. 10. 2026 (lastnik): po vnosu kode je okno ostalo pri »Checking …« / »Preverjam …«. Zaledje je odgovorilo
(kodaNiSprejeta ali seznanitev), stran pa je odziv zapisala samo v polje prijavnega okna ali skritega dela okna.
Preizkus stran zares pozene (ogrodje iz test_link_stran_dogodki), vtipka kodo in poslje odziv zaledja.
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
    "const BERI = ['opombaDeljenje',", "const BERI = ['opombaDodajKoda', 'dodajVnosKode', 'opombaDeljenje',"
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
    def test_vnos_poslje_kodo(self):
        p = _stran([["__vnesi", "dodajVnosKode", "725038"]])
        self.assertIn(["potrdiKodo", "725038"], p["klici"])
        self.assertEqual(p["slike"][0]["opombaDodajKoda"]["besedilo"], "Preverjam …")

    def test_zavrnjena_koda_ne_ostane_pri_preverjam(self):
        for razlog in ("prijava_ne_obstaja", "napacna_koda", "prevec_poskusov"):
            p = _stran([["__vnesi", "dodajVnosKode", "725038"], ["kodaNiSprejeta", {"razlog": razlog}]])
            napis = p["slike"][1]["opombaDodajKoda"]["besedilo"]
            self.assertTrue(napis, razlog)
            self.assertNotEqual(napis, "Preverjam …", razlog)
            self.assertEqual(p["slike"][1]["dodajVnosKode"]["vrednost"], "", "vnos je prazen za novo kodo")

    def test_uspeh_in_nepotrjena(self):
        p = _stran([["__vnesi", "dodajVnosKode", "725038"], ["seznanitev", True]])
        self.assertNotIn(p["slike"][1]["opombaDodajKoda"]["besedilo"], ("", "Preverjam …"))
        p = _stran([["__vnesi", "dodajVnosKode", "725038"], ["seznanitev", False]])
        self.assertEqual(p["slike"][1]["opombaDodajKoda"]["besedilo"], "Koda ni bila potrjena. Poskusi znova.")
