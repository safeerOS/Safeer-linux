"""Sorazmerni delez (core/link_pretvorba.py, Skupina): vec videov razdeljenih med naprave - mocnejsa
opravi vec, nobena ne dela vec kot enega naenkrat, zavrnitev gre na drugo napravo."""
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_pretvorba  # noqa: E402

GB = 1024 ** 3


class _Streznik:
    odtis = "a" * 64

    def zazeni(self):
        pass

    def osnova(self, naslov):
        return "https://127.0.0.1:1"

    def dodaj_datoteko_toka(self, pot):
        return "/m/" + os.path.basename(pot)

    def zeton_za(self, i):
        return "z"


class _Datoteke:
    streznik = _Streznik()


class _Naprava:
    """Pretvori v `trajanje` sekundah; steje, koliko jih je delala hkrati."""

    def __init__(self, ime, trajanje, sirina=4096, pomaga=True, zavrni=""):
        self.ime, self.trajanje, self.sirina, self.pomaga, self.zavrni = ime, trajanje, sirina, pomaga, zavrni
        self.hkrati = 0
        self.najvec_hkrati = 0
        self.opravljeno = []
        self.opravila = {}
        self.zaklep = threading.Lock()

    def ukaz(self, dejanje, p):
        if dejanje == "host.info":
            return {"ok": True, "data": {"disk": {"prosto": 50 * GB, "skupaj": 100 * GB}, "cpu": {"jedra": 8},
                                         "gpu": {"strojno": True, "kodirniki": [{"vrsta": "avc", "sirina": self.sirina}]},
                                         "pomoc": {"lahko": self.pomaga}}}
        if dejanje == "video.transcode":
            if self.zavrni:
                return {"ok": False, "koda": self.zavrni}
            oid = "op%d" % len(self.opravila)
            o = {"id": oid, "state": "pretvarjam", "percent": 0}
            self.opravila[oid] = o
            with self.zaklep:
                self.hkrati += 1
                self.najvec_hkrati = max(self.najvec_hkrati, self.hkrati)

            def delo():
                time.sleep(self.trajanje)
                with self.zaklep:
                    self.hkrati -= 1
                self.opravljeno.append(p["name"])
                o.update({"state": "koncano", "percent": 100, "name": p["name"] + "-1080p.mp4",
                          "file_id": "media:shramba:" + oid, "size": 10, "where": "Download/Safeer Shramba/x"})
            threading.Thread(target=delo, daemon=True).start()
            return {"ok": True, "data": dict(o)}
        if dejanje == "video.status":
            return {"ok": True, "data": dict(self.opravila[p["id"]])}
        return {"ok": False}


class SorazmerniDelez(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-skupina-")
        for i in range(10):
            with open(os.path.join(self.mapa, "film%02d.mkv" % i), "wb") as d:
                d.write(b"x" * 1000)
        open(os.path.join(self.mapa, "zapiski.txt"), "w").close()
        open(os.path.join(self.mapa, "film00-1080p.mp4"), "w").close()   # ze pretvorjen: ne ponovno

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def _pretvorba(self, n):
        naprave = [{"id": k, "ime": v.ime, "zmoznosti": ["files"], "platforma": "phone"} for k, v in n.items()]
        return link_pretvorba.Pretvorba(lambda: naprave, lambda i, d, p: n[i].ukaz(d, p) if i in n else {"ok": False},
                                        _Datoteke(), cakaj=0.02, sonda=lambda pot: None)

    def _pocakaj(self, p, gid, cas=20):
        konec = time.time() + cas
        while time.time() < konec:
            r = p.stanje_skupine(gid)
            if r["koncano"]:
                return r
            time.sleep(0.05)
        self.fail("skupina se ni koncala")

    def test_mocnejsa_opravi_vec_nobena_preobremenjena(self):
        n = {"op9": _Naprava("OnePlus", 0.05), "tv": _Naprava("TV", 0.3, sirina=1920)}
        p = self._pretvorba(n)
        r = p.zacni_vec([self.mapa])
        self.assertEqual(r["skupaj"], 10)                      # brez .txt in ze pretvorjenega
        r = self._pocakaj(p, r["id"])
        self.assertEqual((r["uspesno"], r["napake"]), (10, 0))
        self.assertEqual(n["op9"].najvec_hkrati, 1)
        self.assertEqual(n["tv"].najvec_hkrati, 1)
        self.assertGreater(len(n["op9"].opravljeno), len(n["tv"].opravljeno))   # sorazmerno moci
        self.assertGreaterEqual(len(n["tv"].opravljeno), 1)                     # tudi sibkejsa prispeva
        self.assertEqual(sorted(n["op9"].opravljeno + n["tv"].opravljeno), sorted("film%02d.mkv" % i for i in range(10)))
        self.assertEqual(sum(r["po_napravah"].values()), 10)
        self.assertEqual(p.zasedene, {})

    def test_zadnjih_ne_damo_pocasni_napravi(self):
        n = {"op9": _Naprava("OnePlus", 0.05), "tv": _Naprava("TV", 0.6, sirina=1920)}
        p = self._pretvorba(n)
        r = self._pocakaj(p, p.zacni_vec([self.mapa])["id"])          # prvi krog: izmeri hitrosti
        self.assertEqual(r["uspesno"], 10)
        self.assertIn("tv", p.hitrosti)
        self.assertGreater(p.hitrosti["op9"], p.hitrosti["tv"])
        n["op9"].opravljeno.clear(); n["tv"].opravljeno.clear()
        zacetek = time.time()
        r = self._pocakaj(p, p.zacni_vec([os.path.join(self.mapa, "film01.mkv"), os.path.join(self.mapa, "film02.mkv"),
                                          os.path.join(self.mapa, "film03.mkv")])["id"])
        self.assertEqual(r["uspesno"], 3)
        self.assertEqual(n["tv"].opravljeno, [])                       # hitrejsa jih konca prej kot TV enega
        self.assertLess(time.time() - zacetek, 0.6)

    def test_zavrnitev_gre_drugam_in_brez_naprav(self):
        n = {"op9": _Naprava("OnePlus", 0.02, zavrni="baterija"), "tab": _Naprava("Tablica", 0.02, sirina=1920)}
        p = self._pretvorba(n)
        r = self._pocakaj(p, p.zacni_vec([os.path.join(self.mapa, "film01.mkv"), os.path.join(self.mapa, "film02.mkv")])["id"])
        self.assertEqual(r["uspesno"], 2)
        self.assertEqual(r["po_napravah"], {"Tablica": 2})
        n2 = {"tv": _Naprava("TV", 0.02, pomaga=False)}
        p2 = self._pretvorba(n2)
        r = self._pocakaj(p2, p2.zacni_vec([self.mapa])["id"])
        self.assertEqual((r["uspesno"], r["napake"]), (0, 10))
        self.assertEqual(r["opravila"][0]["napaka"], "ni_naprave")
        self.assertFalse(p2.zacni_vec([os.path.join(self.mapa, "zapiski.txt")])["ok"])

    def test_pusti_in_prenesi_skupino(self):
        n = {"op9": _Naprava("OnePlus", 0.01)}
        p = self._pretvorba(n)
        prenesi = []
        p._prenesi = lambda streznik, oznaka, cilj, o: prenesi.append(cilj)
        p.vprasaj_files = None
        r = self._pocakaj(p, p.zacni_vec([os.path.join(self.mapa, "film03.mkv")])["id"])
        self.assertEqual(p.pusti_skupino(r["id"])["opravila"][0]["stanje"], "pusceno")
        self.assertFalse(p.stanje_skupine("ni")["ok"])


if __name__ == "__main__":
    unittest.main()
