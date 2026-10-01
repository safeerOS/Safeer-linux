"""Skupni prostor (core/link_shramba.py): izbira naprave, preverjena kopija, izbris izvirnika samo po potrditvi."""
import hashlib
import http.client
import os
import shutil
import ssl
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_datoteke, link_shramba  # noqa: E402

GB = 1024 ** 3


class _Naprava:
    """Namesto Android Shramba.kt: prenese datoteko z racunalnika po HTTPS in preveri SHA-256."""

    def __init__(self, prosto=50 * GB, pomaga=True, pokvari=False):
        self.prosto, self.pomaga, self.pokvari = prosto, pomaga, pokvari
        self.opravila = {}
        self.prejeto = b""

    def ukaz(self, dejanje, p):
        if dejanje == "host.info":
            return {"ok": True, "data": {"disk": {"prosto": self.prosto}, "pomoc": {"lahko": self.pomaga, "razlog": ""}}}
        if dejanje == "storage.put":
            o = {"id": "op1", "state": "prenasam", "done": 0, "where": "Download/Safeer Shramba/" + p["name"]}
            self.opravila["op1"] = o
            threading.Thread(target=self._prenesi, args=(o, p), daemon=True).start()
            return {"ok": True, "data": dict(o)}
        if dejanje == "storage.status":
            return {"ok": True, "data": dict(self.opravila[p["id"]])}
        return {"ok": False}

    def _prenesi(self, o, p):
        u = urllib.parse.urlparse(p["url"])
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        c = http.client.HTTPSConnection("127.0.0.1", u.port, context=ctx, timeout=5)
        c.request("GET", u.path, headers={"X-Safeer-Token": p["token"]})
        telo = c.getresponse().read()
        c.close()
        if self.pokvari:
            telo = telo[:-1] + b"X"
        self.prejeto = telo
        o["done"] = len(telo)
        o["state"] = "koncano" if hashlib.sha256(telo).hexdigest() == p["sha256"] else "napaka"


class SkupniProstor(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-shramba-")
        self.pot = os.path.join(self.mapa, "film.mkv")
        self.vsebina = os.urandom(300000)
        with open(self.pot, "wb") as d:
            d.write(self.vsebina)
        self.d = link_datoteke.Datoteke([], tls_mapa=os.path.join(self.mapa, "tls"))
        self.n = {"tablica": _Naprava(), "tv": _Naprava(prosto=3 * GB), "pc": _Naprava(prosto=900 * GB)}
        naprave = [{"id": "tablica", "ime": "Tablica", "zmoznosti": ["files"], "platforma": "tablet"},
                   {"id": "tv", "ime": "TV", "zmoznosti": ["files"], "platforma": "tv"},
                   {"id": "pc", "ime": "PC", "zmoznosti": ["files"], "platforma": "linux"},     # racunalnik ne sprejema
                   {"id": "jaz", "ime": "Jaz", "zmoznosti": ["files"], "platforma": "phone", "ta": True}]
        self.s = link_shramba.Shramba(lambda: naprave, lambda i, d, p: self.n[i].ukaz(d, p) if i in self.n else {"ok": False},
                                      self.d, cakaj=0.05)

    def tearDown(self):
        self.d.ustavi()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def _pocakaj(self, id_):
        for _ in range(200):
            r = self.s.stanje(id_)
            if r["stanje"] in ("kopija", "napaka"):
                return r
            time.sleep(0.05)
        self.fail("premik se ni koncal")

    def test_preverjena_kopija_in_izbris_samo_po_potrditvi(self):
        r = self._pocakaj(self.s.zacni(self.pot)["id"])
        self.assertEqual((r["stanje"], r["naprava"]), ("kopija", "Tablica"))   # najvec prostora, ne racunalnik
        self.assertEqual(self.n["tablica"].prejeto, self.vsebina)
        self.assertIn("Safeer Shramba/film.mkv", r["kje"])
        self.assertTrue(os.path.exists(self.pot))                              # sam se nic ne izbrise
        self.assertEqual(self.s.izbrisi_original(r["id"])["stanje"], "izbrisano")
        self.assertFalse(os.path.exists(self.pot))
        self.assertFalse(self.s.izbrisi_original(r["id"])["ok"])

    def test_obdrzi_oboje(self):
        r = self._pocakaj(self.s.zacni(self.pot)["id"])
        self.assertEqual(self.s.obdrzi(r["id"])["stanje"], "obdrzano")
        self.assertFalse(self.s.izbrisi_original(r["id"])["ok"])
        self.assertTrue(os.path.exists(self.pot))

    def test_spremenjena_datoteka_se_ne_izbrise(self):
        r = self._pocakaj(self.s.zacni(self.pot)["id"])
        with open(self.pot, "ab") as d:
            d.write(b"novo")
        self.assertEqual(self.s.izbrisi_original(r["id"])["koda"], "spremenjena")
        self.assertTrue(os.path.exists(self.pot))

    def test_pokvarjena_kopija_in_brez_naprave(self):
        self.n["tablica"].pokvari = True
        r = self._pocakaj(self.s.zacni(self.pot)["id"])
        self.assertEqual(r["stanje"], "napaka")
        self.assertTrue(os.path.exists(self.pot))
        for n in self.n.values():
            n.pomaga = False
        r = self._pocakaj(self.s.zacni(self.pot)["id"])
        self.assertEqual((r["stanje"], r["napaka"]), ("napaka", "ni_naprave"))
        self.assertFalse(self.s.zacni(os.path.join(self.mapa, "ni.mkv"))["ok"])


if __name__ == "__main__":
    unittest.main()
