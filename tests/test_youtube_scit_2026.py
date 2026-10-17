"""YouTube Scit, tehnike filtrov AdGuard in uBlock Origin (okt. 2026): neprekinljiv oglas (tudi SSAP) utisan,
prevrten in po njem obnovljen; oglasi v Shorts; protiblokada onAbnormalityDetected; Scit tudi v Medijskem centru."""

import os
import shutil
import subprocess
import unittest

from core.adblock import YOUTUBE_ADBLOCK_SCRIPT

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _del(zacetek, konec):
    i = YOUTUBE_ADBLOCK_SCRIPT.index(zacetek)
    return YOUTUBE_ADBLOCK_SCRIPT[i:YOUTUBE_ADBLOCK_SCRIPT.index(konec, i)]


@unittest.skipUnless(shutil.which("node"), "brez node")
class TestYoutubeScit2026(unittest.TestCase):
    def _node(self, koda):
        r = subprocess.run(["node", "-e", koda], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ["ok"], r.stderr + r.stdout)

    def test_neprekinljiv_in_ssap_oglas(self):
        koda = _del("    function isAdActive()", "    function superviseYouTube()")
        self._node(r"""
let razredi = new Set(['ad-showing']), info = '', iskano = null;
const v = { muted: false, playbackRate: 1, duration: 30, currentTime: 2 };
const p = { classList: { contains: c => razredi.has(c) }, getStatsForNerds: () => ({ debug_info: info }),
            getProgressState: () => ({ duration: 30, current: 2 }), seekTo: t => { iskano = t; } };
global.document = { getElementById: () => p, querySelector: () => v };
""" + koda + r"""
fastForwardAd();
if (!v.muted || v.playbackRate !== 16 || iskano !== 30) throw new Error('oglas ni prevrten');
razredi.clear(); fastForwardAd();
if (v.muted || v.playbackRate !== 1) throw new Error('po oglasu ni obnovljeno');
info = 'SSAP, AD 1'; if (!isAdActive()) throw new Error('SSAP');
info = 'SSAP, CONTENT'; if (isAdActive()) throw new Error('vsebina ni oglas');
v.muted = true; fastForwardAd(); if (!v.muted) throw new Error('uporabnikov utisan zvok spremenjen');
console.log('ok');
""")

    def test_shorts_in_protiblokada(self):
        koda = _del("    // Shorts: ad entries", "    // YouTube fetches through a clean")
        self._node(r"""
var stats = { removedFields: 0 };
global.location = { pathname: '/shorts/abc' };
""" + koda + r"""
const d = JSON.parse(JSON.stringify({ entries: [{ command: { reelWatchEndpoint: {} } },
  { command: { reelWatchEndpoint: { adClientParams: { isAd: true } } } }] }));
if (d.entries.length !== 1 || stats.removedFields !== 1) throw new Error('oglas v Shorts');
let klican = false;
Promise.resolve(1).then(function x() { /* onAbnormalityDetected */ klican = true; });
let navaden = false;
Promise.resolve(1).then(() => { navaden = true; }).then(() => {
  if (klican) throw new Error('protiblokada'); if (!navaden) throw new Error('navaden then');
  console.log('ok');
});
""")

    def test_medijski_center_ima_scit(self):
        s = open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8").read()
        self.assertIn("adblock.YOUTUBE_ADBLOCK_SCRIPT, WebKit2.UserContentInjectedFrames.ALL_FRAMES", s)


if __name__ == "__main__":
    unittest.main()
