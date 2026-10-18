"""rqbit na zahtevo (core/os_torrent.py, lastnik 18. 10. 2026): motor se zazene ob prvi rabi, ustavi po mirovanju
(MIROVANJE_S) in ga posrednik toka zazene znova, ko predvajalnik nadaljuje - z istim id-jem torrenta in istim naslovom.
Dokler kaj dela (prenos, ki se ni koncal, deljenje naprej, odprt tok), se ne ustavi.

Pravi rqbit 9.0.1 v vsebniku brez IPv6 ne tece (odjemalec sledilnikov UDP veze [::]:0 tudi z --ipv4-only - izmerjeno
18. 10. 2026), zato tu tece ponarejen motor kot pravi podproces: isti ukaz, geslo, API in shranjeno stanje s id-ji.
S pravim rqbit 9.0.1 na testnem PC (18. 10. 2026) isto zaporedje: ponovni zagon 0,05 s, id 0 -> 0, premor ostane,
tok po ponovnem zagonu 206 s pravimi bajti.
"""
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import unittest
import urllib.request

from core import os_torrent as ot
from core import storitve_na_zahtevo as snz

HASH = "a" * 40

#: Ponarejen rqbit: API z geslom (RQBIT_HTTP_BASIC_AUTH_USERPASS), torrenti z id-ji v --persistence-location/session.json
#: (kot pravi rqbit: po ponovnem zagonu isti id in isto stanje premora), tok z Range.
PROGRAM = r'''
import base64, http.server, json, os, sys
argv = sys.argv[1:]
naslov = argv[argv.index("--http-api-listen-addr") + 1]
stanje_mapa = argv[argv.index("--persistence-location") + 1]
os.makedirs(stanje_mapa, exist_ok=True)
SEJA = os.path.join(stanje_mapa, "session.json")
GESLO = os.environ.get("RQBIT_HTTP_BASIC_AUTH_USERPASS", "")
PODATKI = bytes(range(256)) * 4000
with open(os.path.join(stanje_mapa, "zagoni"), "a") as f:
    f.write("%d\n" % os.getpid())

def beri():
    with open(SEJA) as f:
        return json.load(f)

def pisi(s):
    with open(SEJA + ".tmp", "w") as f:
        json.dump(s, f)
    os.replace(SEJA + ".tmp", SEJA)

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a):
        pass
    def odg(self, koda, telo=b"", glave=None):
        self.send_response(koda)
        self.send_header("Content-Length", str(len(telo)))
        for k, v in (glave or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(telo)
    def ok(self):
        return self.headers.get("Authorization") == "Basic " + base64.b64encode(GESLO.encode()).decode()
    def do_GET(self):
        if not self.ok():
            return self.odg(401)
        s = beri()
        deli = self.path.strip("/").split("/")
        if self.path == "/torrents":
            return self.odg(200, json.dumps({"torrents": [{"id": int(i), "info_hash": t["hash"]} for i, t in s.items()]}).encode())
        t = s.get(deli[1]) if len(deli) > 1 else None
        if t is None:
            return self.odg(404)
        if len(deli) == 2:
            f = [{"name": "film.mp4", "length": len(PODATKI), "included": True}, {"name": "film.srt", "length": 10, "included": True}]
            return self.odg(200, json.dumps({"info_hash": t["hash"], "name": "Film", "files": f}).encode())
        if deli[2:] == ["stats", "v1"]:
            return self.odg(200, json.dumps({"state": "paused" if t["paused"] else "live", "finished": t["finished"]}).encode())
        if deli[2] == "stream":
            if t["paused"]:
                return self.odg(500, b'{"human_readable":"torrent is paused"}')
            if os.path.exists(os.path.join(stanje_mapa, "pocasen")):
                # Tok, ki ga predvajalnik v premoru ne bere: odgovor je vecji od medpomnilnika vticnice.
                self.send_response(200)
                self.send_header("Content-Length", str(len(PODATKI) * 100))
                self.end_headers()
                try:
                    for _ in range(100):
                        self.wfile.write(PODATKI)
                except OSError:
                    pass
                return
            a, b = 0, len(PODATKI) - 1
            r = self.headers.get("Range")
            if r:
                a, _, b2 = r[6:].partition("-")
                a, b = int(a), int(b2) if b2 else len(PODATKI) - 1
            return self.odg(206 if r else 200, PODATKI[a:b + 1], {"Accept-Ranges": "bytes"})
        return self.odg(404)
    do_HEAD = do_GET
    def do_POST(self):
        if not self.ok():
            return self.odg(401)
        s = beri()
        deli = self.path.strip("/").split("/")
        with open(os.path.join(stanje_mapa, "zahteve"), "a") as f:
            f.write(self.path + "\n")
        if len(deli) == 3 and deli[1] in s and deli[2] in ("pause", "start"):
            s[deli[1]]["paused"] = deli[2] == "pause"
            pisi(s)
            return self.odg(200, b"{}")
        return self.odg(404)

h, p = naslov.rsplit(":", 1)
http.server.ThreadingHTTPServer((h, int(p)), H).serve_forever()
'''


def _zivi(pid):
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def _cakaj(pogoj, rok=10.0):
    konec = time.monotonic() + rok
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(0.05)
    return pogoj()


@unittest.skipUnless(sys.platform.startswith("linux"), "podproces in /proc")
class MotorNaZahtevo(unittest.TestCase):
    def setUp(self):
        snz._za_preizkus()
        self.mapa = tempfile.mkdtemp(prefix="safeer-rqbit-preizkus-")
        self.program = os.path.join(self.mapa, "rqbit")
        with open(self.program, "w") as f:
            f.write("#!%s\n%s" % (sys.executable, PROGRAM))
        os.chmod(self.program, os.stat(self.program).st_mode | stat.S_IXUSR)
        self.stanje = os.path.join(self.mapa, "stanje")
        os.makedirs(self.stanje)
        # Shranjen, koncan torrent z id 3 (ne 0): po ponovnem zagonu mora ostati 3.
        with open(os.path.join(self.stanje, "session.json"), "w") as f:
            json.dump({"3": {"hash": HASH, "paused": True, "finished": True}}, f)
        self.t = ot.Torrenti(os.path.join(self.mapa, "prenosi"), self.stanje, program=self.program,
                             nastavitve=os.path.join(self.mapa, "n.json"))

    def tearDown(self):
        self.t.ustavi()
        snz._za_preizkus()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def _zagoni(self):
        with open(os.path.join(self.stanje, "zagoni")) as f:
            return [int(v) for v in f.read().split()]

    def _zahteve(self):
        try:
            with open(os.path.join(self.stanje, "zahteve")) as f:
                return f.read().split()
        except OSError:
            return []

    def _beri(self, url, rang="bytes=0-99"):
        z = urllib.request.Request(url, headers={"Range": rang})
        with urllib.request.urlopen(z, timeout=20) as o:
            return o.status, o.read()

    def test_register_ustavi_po_mirovanju_tok_zazene_znova_z_istim_id(self):
        s = snz.storitev("torrent")
        self.assertIsNotNone(s)
        self.assertEqual(s.mirovanje_s, ot.MIROVANJE_S)
        self.assertFalse(s.tece())
        t0 = time.monotonic()
        url = self.t.tok(3, 0)                    # prva raba: motor se zazene
        zagon_s = time.monotonic() - t0
        self.assertTrue(self.t.tece())
        pid = self.t._proces.pid
        self.assertEqual(snz.stanje()[0]["pidi"], [pid])
        self.assertEqual(self._beri(url), (206, bytes(range(100))))
        # Mirovanje: ura storitev po MIROVANJE_S motor ustavi (v kratki niti), naslov toka ostane.
        snz.tik(zdaj=time.time() + 5)
        self.assertTrue(self.t.tece())            # pred rokom ne
        snz.tik(zdaj=time.time() + ot.MIROVANJE_S + 1)
        self.assertTrue(_cakaj(lambda: not self.t.tece() and not _zivi(pid)), "motor se ni ustavil")
        self.assertEqual(s.ustavitev, 1)
        # Predvajalnik nadaljuje: posrednik zazene motor znova, torrent ima isti id, tok dela.
        t0 = time.monotonic()
        koda, podatki = self._beri(url, "bytes=1000-1099")
        ponovni_zagon_s = time.monotonic() - t0
        self.assertEqual((koda, podatki), (206, (bytes(range(256)) * 5)[1000:1100]))
        self.assertTrue(self.t.tece())
        self.assertEqual(len(self._zagoni()), 2)
        self.assertIn("/torrents/3/start", self._zahteve())
        print("\n[rqbit na zahtevo] prvi zagon %.2f s, ponovni zagon s tokom %.2f s (ponarejen motor)"
              % (zagon_s, ponovni_zagon_s))

    def test_ne_ustavi_med_prenosom_deljenjem_in_odprtim_tokom(self):
        self.t.zazeni()
        self.assertFalse(self.t._preveri())       # koncan in v premoru: nic ne dela
        # Prenos, ki se ni koncal: motor dela.
        with open(os.path.join(self.stanje, "session.json"), "w") as f:
            json.dump({"3": {"hash": HASH, "paused": False, "finished": False}}, f)
        self.assertTrue(self.t._preveri())
        snz.tik(zdaj=time.time() + ot.MIROVANJE_S + 1)
        time.sleep(0.3)
        self.assertTrue(self.t.tece())
        # Koncan torrent, ki ga uporabnik deli naprej: dela (koncanega brez deljenja nadzor da v premor).
        with open(os.path.join(self.stanje, "session.json"), "w") as f:
            json.dump({"3": {"hash": HASH, "paused": False, "finished": True}}, f)
        self.t.deli_naprej(HASH, True)
        self.assertTrue(self.t._preveri())
        self.t.deli_naprej(HASH, False)
        self.assertFalse(self.t._preveri())
        self.assertIn("/torrents/3/pause", self._zahteve())
        # Odprt tok (predvajalnik v premoru ne bere): dokler je povezava odprta, motor dela.
        self.t._api("POST", "/torrents/3/start")
        url = self.t.tok(3, 0)
        open(os.path.join(self.stanje, "pocasen"), "w").close()
        odziv = urllib.request.urlopen(url, timeout=20)
        odziv.read(10)
        self.assertTrue(_cakaj(lambda: self.t._aktivni_tokovi == 1, 5))
        self.assertTrue(self.t.zaposlen())
        snz.tik(zdaj=time.time() + 2 * ot.MIROVANJE_S)
        time.sleep(0.3)
        self.assertTrue(self.t.tece())
        odziv.close()
        self.assertTrue(_cakaj(lambda: self.t._aktivni_tokovi == 0, 10))

    def test_nadzor_motorja_ne_zazene(self):
        """Nadzor (vsakih 10 s) bere stanje brez zagona: ustavljen motor ostane ustavljen."""
        self.t.zazeni()
        self.t.ustavi_motor()
        self.assertFalse(self.t.tece())
        with self.assertRaises(OSError):
            self.t._beri_brez_zagona("/torrents")
        self.assertFalse(self.t.tece())
        self.assertEqual(len(self._zagoni()), 1)


class MotorJeStoritev(unittest.TestCase):
    def test_ime_storitve_in_pidi(self):
        snz._za_preizkus()
        d = tempfile.mkdtemp()
        try:
            a = ot.Torrenti(os.path.join(d, "p"), os.path.join(d, "s"), program="/ni/programa")
            b = ot.Torrenti(os.path.join(d, "p2"), os.path.join(d, "s2"), program="/ni/programa", svoj_dht=True)
            self.assertEqual((a.ime_storitve, b.ime_storitve), ("torrent", "torrent_naprave"))
            imena = {s["ime"]: s for s in snz.stanje()}
            self.assertEqual(imena["torrent"]["vrsta"], snz.NA_ZAHTEVO)
            self.assertFalse(imena["torrent_naprave"]["tece"])
            self.assertEqual(imena["torrent"]["pidi"], [])
        finally:
            snz._za_preizkus()
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
