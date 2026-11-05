"""Ponudba posodobitve dovoljenja Scita ob zagonu Safeer OS ostane, dokler uporabnik ne izbere: navadno obvestilo jo
lahko za hip zamenja, ko se skrije, se ponudba vrne (CodeRabbit 4. 11. 2026: prej je obvesti() zamenjal gumba in po
2,6 s skril obvestilo - ponudbe v tej seji ni bilo vec mogoce sprejeti)."""
import json
import os
import shutil
import subprocess
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OS_JS = os.path.join(KOREN, "assets", "os", "os.js")

SKRIPTA = r"""
const s = require('fs').readFileSync(process.argv[1], 'utf8');
function kos(zacetek, konec) {
  const a = s.indexOf(zacetek), b = s.indexOf(konec, a);
  if (a < 0 || b < 0) throw new Error('ni kosa: ' + zacetek);
  return s.slice(a, b);
}
const koda = kos('  var obvestiloCas = 0;', '  // Prvi film iz torrenta') +
             kos('  function ponudiScitDovoljenje() {', '  function narisiScit() {');
function Element(oznaka) {
  const razredi = new Set();
  return { oznaka, otroci: [], poslusalci: {}, _besedilo: '',
    set textContent(v) { this._besedilo = String(v); this.otroci = []; },
    get textContent() { return this._besedilo + this.otroci.map(o => o.textContent).join(''); },
    classList: { add: (...r) => r.forEach(x => razredi.add(x)), remove: (...r) => r.forEach(x => razredi.delete(x)),
                 contains: r => razredi.has(r) },
    appendChild(o) { this.otroci.push(o); return o; },
    addEventListener(d, f) { this.poslusalci[d] = f; } };
}
const obvestilo = Element('div');
const casovniki = [];
const izbire = [];
const okolje = {
  $: () => obvestilo,
  el: (oznaka, _r, html) => { const e = Element(oznaka); e._besedilo = html || ''; return e; },
  t: k => k, ubezi: x => x,
  klic: () => ({ then: f => f({ dovoljenjePonudi: true, dovoljenje: 'siroko' }) }),
  posodobiScitDovoljenje: v => izbire.push(v),
  setTimeout: (f, ms) => { casovniki.push(f); return casovniki.length; }, clearTimeout: () => {},
  scitStanje: null,
};
const f = new Function(...Object.keys(okolje), koda + '; return {obvesti, ponudiScitDovoljenje};')(...Object.values(okolje));
const izid = {};
const gumbi = () => obvestilo.otroci.filter(o => o.oznaka === 'button').map(o => o.textContent);
f.ponudiScitDovoljenje();
casovniki.shift()();                                   // 4 s po zagonu: ponudba
izid.ponudba = [gumbi(), obvestilo.classList.contains('viden')];
f.obvesti('Kopirano');                                 // drugo obvestilo vmes
izid.vmes = [gumbi(), obvestilo.textContent];
casovniki.pop()();                                     // obvestilo se skrije po 2,6 s
izid.po = [gumbi(), obvestilo.classList.contains('viden')];
obvestilo.otroci.find(o => o.textContent === 'scitDovoljenjeNeZdaj').poslusalci.click();
f.obvesti('Drugo');
casovniki.pop()();
izid.izbrano = [izbire, gumbi(), obvestilo.classList.contains('viden')];
console.log(JSON.stringify(izid));
"""


class PonudbaObZagonu(unittest.TestCase):
    def test_ponudba_ostane_do_izbire(self):
        if not shutil.which("node"):
            self.skipTest("node ni namescen")
        izid = json.loads(subprocess.run(["node", "-e", SKRIPTA, OS_JS], capture_output=True, text=True, timeout=30,
                                         check=True).stdout)
        gumba = ["scitDovoljenjePosodobi", "scitDovoljenjeNeZdaj"]
        self.assertEqual(izid["ponudba"], [gumba, True])
        self.assertEqual(izid["vmes"], [[], "Kopirano"])
        self.assertEqual(izid["po"], [gumba, True], "ponudba se po drugem obvestilu ne vrne")
        self.assertEqual(izid["izbrano"], [[False], [], False], "po izbiri se ponudba ne vraca vec")


if __name__ == "__main__":
    unittest.main()
