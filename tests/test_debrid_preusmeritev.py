"""Zahteve s kljucem debrid in indeksatorja ne sledijo preusmeritvi na drug gostitelj (AGENTS.md: omrezje s kljucem).

Najdba pregleda 25. 10. 2026 (nacrt kljuci-namizje, tocka 3): core/debrid.klic je glavo »Authorization: Bearer <kljuc>«
poslal z urllib.urlopen, ki ob 302 glavo kopira tudi v zahtevo drugemu gostitelju - TorBox, Real-Debrid ali AllDebrid (ali
posrednik na poti) bi s preusmeritvijo kljuc odnesel tretjemu. Enako iskanje Usenet (kljuc v naslovu). Preizkus z dvema
lokalnima streznikoma: A (127.0.0.1) preusmeri, B (127.0.0.2, drug gostitelj) zabelezi vsako zahtevo, ki jo prejme.
Brez popravka B prejme zahtevo z glavo Authorization (preverjeno z zacasnim umikom popravka). Kljuci so izmisljeni.
"""
import http.server
import json
import threading
import unittest
from unittest import mock

from core import debrid, debrid_pravila as P, usenet_pravila as U

KLJUC = "q7Lm2Zx9Rt4Vb8Nc1Kd6Hs3Fg5Jw0Pe"
KLJUC_IX = "5e8a1c4f9b2d7e3a6c0f8b1d4e7a2c9f"
RSS = '<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'
NZB = '<?xml version="1.0" encoding="UTF-8"?>\n<nzb xmlns="http://www.newzbin.com/DTD/2003/nzb"><file subject="a"></file></nzb>'


def _streznik(gostitelj: str):
    """Streznik, ki zabelezi (metoda, pot, Authorization) in odgovori po razdelku .odgovori[pot brez poizvedbe]."""
    zahteve: list = []
    odgovori: dict = {}

    class Rocaj(http.server.BaseHTTPRequestHandler):
        def _odgovori(self):
            dolzina = int(self.headers.get("Content-Length") or 0)
            if dolzina:
                self.rfile.read(dolzina)
            zahteve.append((self.command, self.path, self.headers.get("Authorization")))
            koda, telo, glave = odgovori.get(self.path.split("?", 1)[0], (200, '{"success": true, "data": {}}', {}))
            self.send_response(koda)
            for k, v in glave.items():
                self.send_header(k, v)
            podatki = telo.encode()
            self.send_header("Content-Length", str(len(podatki)))
            self.end_headers()
            self.wfile.write(podatki)

        do_GET = do_POST = do_DELETE = _odgovori  # noqa: N815 - imena iz http.server

        def log_message(self, *_a):
            pass

    s = http.server.ThreadingHTTPServer((gostitelj, 0), Rocaj)
    s.zahteve, s.odgovori = zahteve, odgovori
    s.osnova = "http://%s:%d" % (gostitelj, s.server_address[1])
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


class Preusmeritev(unittest.TestCase):
    def setUp(self):
        self.a = _streznik("127.0.0.1")
        self.b = _streznik("127.0.0.2")
        for s in (self.a, self.b):
            self.addCleanup(s.server_close)
            self.addCleanup(s.shutdown)

    def _preusmeri(self, pot: str, koda: int = 302, cilj: str = ""):
        self.a.odgovori[pot] = (koda, "", {"Location": cilj or self.b.osnova + "/ukradi"})

    def _b_nic(self):
        self.assertEqual(self.b.zahteve, [], "drug gostitelj je prejel zahtevo (kljuc bi sel z njo)")

    def test_kljuc_v_glavi_get(self):
        self._preusmeri("/user/me")
        o = debrid.klic(self.a.osnova + "/user/me", KLJUC, rok=5)
        self._b_nic()
        self.assertEqual(o.koda, 302)
        self.assertFalse(o.uspeh)
        self.assertEqual(self.a.zahteve, [("GET", "/user/me", "Bearer " + KLJUC)])

    def test_kljuc_v_glavi_post_obrazec(self):
        for koda in (301, 302, 303):
            self._preusmeri("/torrents/addMagnet", koda)
            o = debrid.klic(self.a.osnova + "/torrents/addMagnet", KLJUC, "POST", [("magnet", "magnet:?xt=urn:btih:" + "a" * 40)], rok=5)
            self._b_nic()
            self.assertEqual(o.koda, koda)

    def test_kljuc_v_naslovu_requestdl(self):
        """TorBox requestdl nosi kljuc kot parameter token: preusmeritev ga ne sme peljati nikamor."""
        self._preusmeri("/requestdl")
        o = debrid.klic(self.a.osnova + "/requestdl?token=%s&torrent_id=1&file_id=0" % KLJUC, None, rok=5)
        self._b_nic()
        self.assertEqual(o.koda, 302)

    def test_torbox_preverba_ob_preusmeritvi_ni_veljavna(self):
        """3xx pri user/me ni potrditev kljuca: »ni odgovora« (shrani kot nepreverjen), kljuc ne gre drugam."""
        self._preusmeri("/user/me", 307)
        with mock.patch.object(P, "TORBOX_UPORABNIK", self.a.osnova + "/user/me"):
            izid = debrid.torbox_preveri(KLJUC, rok=5)
        self._b_nic()
        self.assertEqual(izid[0], P.PREVERBA_NI_ODGOVORA)

    def test_iskanje_usenet_ne_sledi(self):
        self._preusmeri("/api", 302, self.b.osnova + "/api")
        self.b.odgovori["/api"] = (200, RSS, {})
        self.assertEqual(debrid.usenet_isci(self.a.osnova, KLJUC_IX, "tt0111161", rok=5), [])
        self._b_nic()
        self.assertEqual(len(self.a.zahteve), 1)

    def test_nzb_na_tuj_http_zavrnjen(self):
        self._preusmeri("/getnzb", 302, self.b.osnova + "/nzb")
        self.b.odgovori["/nzb"] = (200, NZB, {})
        nzb, napaka = debrid.usenet_nzb(self.a.osnova + "/getnzb?id=1&apikey=" + KLJUC_IX, rok=5)
        self._b_nic()
        self.assertEqual((nzb, napaka), (None, U.NAPAKA_INDEKSATOR))

    def test_nzb_znotraj_istega_gostitelja_dela(self):
        """Indeksator v domacem omrezju (NZBHydra, Prowlarr) sme preusmeriti na svoj naslov - NZB se prenese."""
        self._preusmeri("/getnzb", 302, self.a.osnova + "/nzb")
        self.a.odgovori["/nzb"] = (200, NZB, {})
        nzb, napaka = debrid.usenet_nzb(self.a.osnova + "/getnzb?id=1&apikey=" + KLJUC_IX, rok=5)
        self.assertEqual((napaka, nzb), ("", NZB.encode()))
        self._b_nic()


class SkokNzb(unittest.TestCase):
    def test_pravilo(self):
        ix = "https://nzbfinder.ws/getnzb?id=1&apikey=" + KLJUC_IX
        self.assertTrue(U.dovoljen_skok(ix, "https://cdn.primer.test/nzb/1"))
        self.assertFalse(U.dovoljen_skok(ix, "http://nzbfinder.ws/getnzb?id=1&apikey=" + KLJUC_IX))   # s https na http
        self.assertFalse(U.dovoljen_skok(ix, "https://oseba@cdn.primer.test/nzb"))
        self.assertFalse(U.dovoljen_skok(ix, "ftp://cdn.primer.test/nzb"))
        lok = "http://192.168.1.20:5076/getnzb/api/1?apikey=" + KLJUC_IX
        self.assertTrue(U.dovoljen_skok(lok, "http://192.168.1.20:5076/nzb/1"))
        self.assertTrue(U.dovoljen_skok(lok, "https://cdn.primer.test/nzb/1"))
        self.assertFalse(U.dovoljen_skok(lok, "http://192.168.1.30/nzb/1"))                     # drug http gostitelj
        self.assertFalse(U.dovoljen_skok(lok, "http://napadalec.primer.test/nzb/1"))
        self.assertFalse(U.dovoljen_skok("", "http://[::1"))

    def test_internet_ne_v_domace_omrezje(self):
        """Grokov pregled 36, D5: indeksator z interneta je smel preusmeriti prenos NZB na https v domace omrezje ali na
        ta racunalnik (slepa zahteva GET); pri http so se vrata ignorirala."""
        ix = "https://nzbfinder.ws/getnzb?id=1&apikey=" + KLJUC_IX
        for cilj in ("https://192.168.1.1/nzb", "https://127.0.0.1:8080/nzb", "https://localhost/nzb", "https://[::1]/nzb",
                     "https://169.254.169.254/latest", "https://10.0.0.5./nzb", "https://nas.local/nzb", "https://100.64.0.1/x"):
            self.assertFalse(U.dovoljen_skok(ix, cilj), cilj)
        self.assertTrue(U.dovoljen_skok(ix, "https://cdn.primer.test/nzb/1"))
        self.assertTrue(U.dovoljen_skok(ix, "https://8.8.8.8/nzb/1"))
        lok = "http://192.168.1.20:5076/getnzb/api/1?apikey=" + KLJUC_IX
        self.assertFalse(U.dovoljen_skok(lok, "http://192.168.1.20:8080/nzb/1"))                # druga vrata
        self.assertTrue(U.dovoljen_skok(lok, "https://192.168.1.30/nzb/1"))                    # lokalni indeksator sme
        self.assertTrue(U.dovoljen_skok("http://192.168.1.20/a", "http://192.168.1.20:80/b"))
        rss = ('<rss><channel><item><title>A</title><enclosure url="https://192.168.1.1/a.nzb"/></item>'
               '<item><title>B</title><enclosure url="https://cdn.primer.test/b.nzb"/></item></channel></rss>')
        self.assertEqual([z.naslov for z in U.zadetki(rss, "https://nzbfinder.ws")], ["B"])
        self.assertEqual([z.naslov for z in U.zadetki(rss, "http://192.168.1.20:5076")], ["A", "B"])


if __name__ == "__main__":
    unittest.main()
