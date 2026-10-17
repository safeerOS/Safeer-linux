"""Scit v strani Spotify (assets/safeer_drm/main.js SPOTIFY_SCIT): oglas utisa in prevrti, pesmi ne spremeni.
Preizkus 17. 10. 2026: straza Safeer OS je oglas zaznala sele po 7 s in ga le utisala (75 s tisine)."""

import os
import re
import shutil
import subprocess
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(KOREN, "assets", "safeer_drm", "main.js")


def _skript() -> str:
    s = open(MAIN, encoding="utf-8").read()
    m = re.search(r"const SPOTIFY_SCIT = `(.*?)`;\n", s, re.S)
    assert m, "SPOTIFY_SCIT ni najden"
    return m.group(1)


class TestSpotifyScitStran(unittest.TestCase):
    def test_vstavljen_samo_s_scitom(self):
        s = open(MAIN, encoding="utf-8").read()
        self.assertIn("pravila ? dbg.sendCommand('Page.addScriptToEvaluateOnNewDocument', { source: SPOTIFY_SCIT })", s)

    def test_oglas_se_ne_blokira_in_ne_nadomesca(self):
        s = open(MAIN, encoding="utf-8").read()
        self.assertNotIn("AD_RESOURCE_BLOCKED", s)
        self.assertNotIn("zamenjajOglas", s)
        self.assertNotIn("playbackRate = 16", _skript())

    @unittest.skipUnless(shutil.which("node"), "brez node")
    def test_oglas_utisan_pesem_ne(self):
        oder = r"""
let oznaka = null, naslov = 'Pesem', casi = [];
const m = { muted: false, playbackRate: 1 };
// Node 21+ ima navigator samo za branje: lastnost nastavimo na novo.
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { mediaSession: { get metadata() { return { title: naslov }; } } } });
global.document = { querySelector: s => oznaka, querySelectorAll: () => [m] };
let utis = false;
global.window = { __safeerSpotify: { mediji: () => [m], utisaj: d => { utis = d; m.muted = d; } } };
global.setInterval = f => casi.push(f);
global.MutationObserver = undefined;
eval(process.argv[process.argv.length - 1]);
const k = casi[0];
k(); if (m.playbackRate !== 1 || m.muted) throw new Error('pesem spremenjena');
naslov = 'Oglas'; k(); if (m.playbackRate !== 1 || !m.muted || !utis) throw new Error('oglas ni utisan (ali je pospesen)');
naslov = 'Druga pesem'; k(); if (m.playbackRate !== 1 || m.muted || utis) throw new Error('po oglasu ni vrnjeno');
oznaka = {}; k(); if (!m.muted || m.playbackRate !== 1) throw new Error('oznaka oglasa');
console.log('ok');
"""
        r = subprocess.run(["node", "-e", oder, _skript()], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.stdout.strip(), "ok", r.stderr)


if __name__ == "__main__":
    unittest.main()
