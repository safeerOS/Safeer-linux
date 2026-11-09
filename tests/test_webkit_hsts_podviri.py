"""HSTS za podvire v nasem WebKitu (hsts-subresource-upgrade.patch, 8. 11. 2026).

Brez popravka (safeer-webkit 1.0.134, testni PC, 3/3): navigacija na vrhu se nadgradi na https, slika, skripta in
iframe do istega gostitelja s politiko HSTS pa gredo po http in nesejo piskotek. S popravkom morajo vsi po TLS.
Samo zanka (::1 / 127.0.0.1); potrebuje nas WebKit 6.0 (posel preizkusi-webkit) in xvfb-run."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKRIPTA = os.path.join(KOREN, "tests", "hsts_podviri_preizkus.py")


def _webkit_na_voljo():
    r = subprocess.run([sys.executable, "-c", "import gi; gi.require_version('WebKit', '6.0'); from gi.repository import WebKit"],
                       capture_output=True, timeout=60)
    return r.returncode == 0


@unittest.skipUnless(shutil.which("xvfb-run"), "potrebuje xvfb-run")
class HstsPodviri(unittest.TestCase):
    def test_podviri_po_tls_brez_piskotka_v_cistem_http(self):
        if not _webkit_na_voljo():
            self.skipTest("potrebuje WebKit 6.0")
        with tempfile.TemporaryDirectory() as mapa:
            r = subprocess.run(["xvfb-run", "-a", sys.executable, SKRIPTA, mapa], capture_output=True, text=True, timeout=120)
        vrstice = [v for v in r.stdout.splitlines() if v.startswith("JSON ")]
        self.assertTrue(vrstice, r.stdout[-2000:] + r.stderr[-2000:])
        izid = json.loads(vrstice[-1][5:])
        # Kontrola: politika HSTS je nalozena (navigacija na vrhu se nadgradi) - sicer preizkus ne dokazuje nicesar.
        self.assertEqual(izid.get("navigacija"), ["TLS"], izid)
        for vrsta in ("slika", "skripta", "okvir"):
            self.assertEqual(izid.get(vrsta), ["TLS"], "%s ni nadgrajen na https: %s" % (vrsta, izid))
        # Medizvorni fetch/XHR (POST s telesom in redirect:'error') se nadgradi brez preusmeritve - libsoup pri gostitelju
        # s HSTS potrdila z napako ne sprejme (RFC 6797 8.4: soup-hsts-enforcer.c on_sts_known_host_message_starting),
        # zato pri samopodpisanem potrdilu tega preizkusa zahteva ne stece do konca; preverimo, da ni sla po cistem HTTP.
        for vrsta in ("api", "api2 (redirect error)"):
            self.assertIn("TLS", izid.get(vrsta, []), izid)
            self.assertNotIn("HTTP", izid.get(vrsta, []), izid)
        # Razsirjeno (9. 11. 2026, testni PC izmenicno 1.0.134 / 1.0.134.1): vse druge vrste zahtev do gostitelja HSTS.
        for vrsta in ("css", "pisava", "ozadje css", "video", "avdio", "xhr", "beacon", "websocket", "obrazec v okvirju"):
            self.assertEqual(izid.get(vrsta), ["TLS"], "%s ni nadgrajen na https: %s" % (vrsta, izid))
        self.assertTrue(any(s.startswith("TLS") for s in izid.get("poddomena (includeSubDomains)", [])), izid)
        self.assertNotIn("HTTP", izid.get("poddomena (includeSubDomains)", []), izid)
        self.assertNotIn("HTTP", izid.get("eventsource", []), izid)
        self.assertFalse([v for v, s in izid.items() if isinstance(s, list) and "PISKOTEK V CISTEM HTTP" in s], izid)
        if izid.get("_zaupano"):
            # S potrdilom, ki mu sistem zaupa: POST ostane POST s telesom, Origin ostane izvor strani, redirect:'error' ne pade.
            self.assertIn("METODA POST", izid["api"], izid)
            self.assertIn("TELO OK", izid["api"], izid)
            for vrsta in ("api", "api2 (redirect error)"):
                self.assertIn("ORIGIN " + izid["_izvor_strani"], izid[vrsta], izid)
            self.assertEqual(izid.get("fetch (naslov strani)"), ["FETCH:ok|ok"], izid)
            # Medizvorni EventSource s CORS: 307 brez Access-Control-Allow-Origin ga je zavrnil (9. 11., brez zahteve).
            self.assertEqual(izid.get("eventsource"), ["TLS"], izid)
            self.assertEqual(izid.get("eventsource (stanje v strani)"), ["odprto"], izid)
            # Slepi pregled 9. 11.: viri v nacinu CORS, ki niso fetch/XHR - z v4 so vsi padli (brez zahteve do streznika).
            for vrsta in ("preflight (fetch JSON)", "slika crossorigin", "modul skripta", "beacon JSON", "izvor null (sandbox)"):
                self.assertIn("TLS", izid.get(vrsta, []), "%s: %s" % (vrsta, izid))
                self.assertNotIn("HTTP", izid.get(vrsta, []), izid)
            stanja = json.loads(izid["stanja v strani"][0])
            self.assertEqual(stanja, {"preflight": "ok", "crossorigin": "ok", "modul": "nalozen", "nul": "ok"}, izid)

if __name__ == "__main__":
    unittest.main()
