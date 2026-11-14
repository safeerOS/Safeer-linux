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
SKRIPTA_MEDMESTNO = os.path.join(KOREN, "tests", "hsts_medmestno_preizkus.py")
SKRIPTA_PREUSMERITEV = os.path.join(KOREN, "tests", "hsts_preusmeritev_preizkus.py")


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
        # v7 (14. 11. 2026): poddomena DRUGEGA mesta (a.hsts2.localhost, stran na www.hsts.localhost) ostane po HTTP -
        # nadgradnja bi tretji strani dala branje stanja HSTS (supercookie); prvi popravek je ta primer nadgradil.
        self.assertIn("HTTP", izid.get("poddomena (includeSubDomains)", []), izid)
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
            # Streznik od d43c94a zapise tudi metodo (CORS_VRSTE), zato TLS in brez HTTP namesto natancno ["TLS"].
            self.assertIn("TLS", izid.get("eventsource", []), izid)
            self.assertNotIn("HTTP", izid.get("eventsource", []), izid)
            self.assertEqual(izid.get("eventsource (stanje v strani)"), ["odprto"], izid)
            # Slepi pregled 9. 11.: viri v nacinu CORS, ki niso fetch/XHR - z v4 so vsi padli (brez zahteve do streznika).
            for vrsta in ("preflight (fetch JSON)", "slika crossorigin", "modul skripta", "beacon JSON", "izvor null (sandbox)"):
                self.assertIn("TLS", izid.get(vrsta, []), "%s: %s" % (vrsta, izid))
                self.assertNotIn("HTTP", izid.get(vrsta, []), izid)
            stanja = json.loads(izid["stanja v strani"][0])
            # Slepi pregled v6 (najdba A): odziv, nadgrajen na mestu, ne sme okvirju istega naslova http dati izvora http.
            self.assertEqual(stanja.pop("okvir_iz_predpomnilnika", None), "https:", izid)
            self.assertEqual(stanja, {"preflight": "ok", "crossorigin": "ok", "modul": "nalozen", "nul": "ok"}, izid)

    def test_medmestni_podvir_ni_nadgrajen_istomestni_je(self):
        """HSTS stanje se ne sme dati brati medmestno (14. 11. 2026, testni PC, 3 izmenicni teki treh gradenj: brez popravka
        HTTP/HTTP, prvi popravek TLS/TLS (uhajanje), v7 HTTP za medmestno in TLS za istomestno). Kontrola: navigacija na vrhu TLS."""
        if not _webkit_na_voljo():
            self.skipTest("potrebuje WebKit 6.0")
        with tempfile.TemporaryDirectory() as mapa:
            r = subprocess.run(["xvfb-run", "-a", sys.executable, SKRIPTA_MEDMESTNO, mapa], capture_output=True, text=True, timeout=120)
        vrstice = [v for v in r.stdout.splitlines() if v.startswith("JSON ")]
        self.assertTrue(vrstice, r.stdout[-2000:] + r.stderr[-2000:])
        izid = json.loads(vrstice[-1][5:])
        kontrola = [v for k, v in izid.items() if "control" in k][0]
        medmestno = [v for k, v in izid.items() if "cross-site" in k][0]
        istomestno = [v for k, v in izid.items() if "same-site" in k][0]
        self.assertTrue(any(s.startswith("TLS") for s in kontrola), izid)      # politika je res nalozena
        self.assertTrue(medmestno and all(s.startswith("HTTP") for s in medmestno), izid)
        self.assertTrue(istomestno and all(s.startswith("TLS") for s in istomestno), izid)

    def test_preusmeritev_na_drugo_mesto_ni_nadgrajena(self):
        """Podvir istega mesta, ki ga 302 preusmeri na drugo mesto s politiko HSTS, ostane po HTTP (14. 11. 2026, testni PC,
        3 izmenicni teki: paket 1.0.135 HTTP, prejsnji namesceni paket TLS = uhajanje stanja HSTS). Kontrola: navigacija TLS."""
        if not _webkit_na_voljo():
            self.skipTest("potrebuje WebKit 6.0")
        with tempfile.TemporaryDirectory() as mapa:
            r = subprocess.run(["xvfb-run", "-a", sys.executable, SKRIPTA_PREUSMERITEV, mapa], capture_output=True, text=True, timeout=120)
        vrstice = [v for v in r.stdout.splitlines() if v.startswith("JSON ")]
        self.assertTrue(vrstice, r.stdout[-2000:] + r.stderr[-2000:])
        izid = json.loads(vrstice[-1][5:])
        kontrola = [v for k, v in izid.items() if "control" in k][0]
        cilj = [v for k, v in izid.items() if k.startswith("R target")][0]
        self.assertTrue(any(s.startswith("TLS") for s in kontrola), izid)
        self.assertTrue(cilj and all(s.startswith("HTTP") for s in cilj), izid)


if __name__ == "__main__":
    unittest.main()
