"""Nase skripte na vseh straneh uporabljajo izvirne casovnike, ne strani: JetStream Kotlin-compose-wasm zamenja
setTimeout s polyfillom, ki vrze napako za vsak drug rok - Wasm je dobil izjemo in test je v Safeerju obstal
(preizkus 17. 10. 2026)."""

import shutil
import subprocess
import unittest

from core.adblock import ADGUARD_PROTECTION_SCRIPT


@unittest.skipUnless(shutil.which("node"), "brez node")
class TestIzvirniCasovniki(unittest.TestCase):
    def test_stran_zamenja_settimeout_nase_skripte_je_ne_klicejo(self):
        oder = r"""
const izvirni = [];
const okno = {
  setTimeout(f, ms) { izvirni.push(ms); return izvirni.length; }, clearTimeout() {}, setInterval() { return 1; },
  location: { hostname: 'browserbench.org', href: 'https://browserbench.org/' }, performance: { now: () => 0 },
};
okno.window = okno;
globalThis.window = okno; globalThis.location = okno.location; globalThis.performance = okno.performance;
globalThis.document = { hidden: false, documentElement: {}, head: null, addEventListener() {}, querySelectorAll: () => [],
                        createElement: () => ({ style: {} }), getElementById: () => null, readyState: 'complete' };
globalThis.MutationObserver = function () { this.observe = () => {}; };
globalThis.navigator = globalThis.navigator || {};
const koda = process.argv[process.argv.length - 1];
try { (new Function('window', 'location', 'document', koda))(okno, okno.location, globalThis.document); } catch (e) {}
// Stran (JetStream) zamenja setTimeout s polyfillom, ki vrze napako za neznan rok.
let polyfill = 0;
okno.setTimeout = function (f, ms) { polyfill++; throw new Error('Unexpected delay for setTimeout polyfill: ' + ms); };
okno.__safeerSchedule(function () {}, 2500);
if (polyfill !== 0) throw new Error('nasa skripta je klicala setTimeout strani');
if (!izvirni.includes(2500)) throw new Error('nas casovnik ni bil nastavljen: ' + izvirni);
console.log('ok');
"""
        r = subprocess.run(["node", "-e", oder, ADGUARD_PROTECTION_SCRIPT], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ["ok"], r.stderr + r.stdout)


if __name__ == "__main__":
    unittest.main()
