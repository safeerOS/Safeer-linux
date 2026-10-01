"""Pretvorba videa (core/link_pretvorba.py): izbira naprave z najboljsim kodirnikom, potek, prenos nazaj."""
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

from core import link_datoteke, link_pretvorba  # noqa: E402

GB = 1024 ** 3


def kodirniki(*sirine_avc, hevc=False):
    k = [{"vrsta": "avc", "sirina": s, "visina": s * 9 // 16} for s in sirine_avc]
    if hevc:
        k.append({"vrsta": "hevc", "sirina": 3840, "visina": 2160})
    return k


class _Naprava:
    """Namesto Android Pretvorba.kt: prenese izvirnik po HTTPS in "pretvori" (obrne bajte)."""

    def __init__(self, kod, prosto=50 * GB, pomaga=True, deli=True, jedra=8, dek=None, zavrni=""):
        self.kod, self.prosto, self.pomaga, self.deli, self.jedra = kod, prosto, pomaga, deli, jedra
        self.dek = dek if dek is not None else [{"vrsta": "hevc", "sirina": 3840, "visina": 2160},
                                                {"vrsta": "avc", "sirina": 3840, "visina": 2160}]
        self.zavrni = zavrni
        self.parametri = None
        self.opravila = {}
        self.vprasan = 0
        self.izhod = b""

    def ukaz(self, dejanje, p):
        if dejanje == "host.info":
            self.vprasan += 1
            return {"ok": True, "data": {"disk": {"prosto": self.prosto, "skupaj": getattr(self, "skupaj", 0)}, "cpu": {"jedra": self.jedra},
                                         "gpu": {"kodirniki": self.kod, "strojno": bool(self.kod),
                                                 "dekodirniki": self.dek},
                                         "pomoc": {"lahko": self.pomaga, "razlog": ""}}}
        if dejanje == "video.transcode":
            self.parametri = p
            if self.zavrni:
                return {"ok": False, "koda": self.zavrni}
            o = {"id": "op1", "state": "prenasam", "percent": 0}
            self.opravila["op1"] = o
            threading.Thread(target=self._pretvori, args=(o, p), daemon=True).start()
            return {"ok": True, "data": dict(o)}
        if dejanje == "video.status":
            return {"ok": True, "data": dict(self.opravila[p["id"]])}
        if dejanje == "files.list":
            if not self.deli:
                return {"ok": True, "data": {"items": [], "shared": False}}
            return {"ok": True, "data": {"shared": True, "items": [{"id": "media:shramba:7", "name": "film-1080p.mp4"}],
                                         "server": {"base_url": "https://127.0.0.1:1", "fp": "a" * 64, "token": "z"}}}
        return {"ok": False}

    def _pretvori(self, o, p):
        u = urllib.parse.urlparse(p["url"])
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        c = http.client.HTTPSConnection("127.0.0.1", u.port, context=ctx, timeout=5)
        c.request("GET", u.path, headers={"X-Safeer-Token": p["token"]})
        telo = c.getresponse().read()
        c.close()
        o["state"] = "pretvarjam"
        time.sleep(0.1)
        self.izhod = telo[::-1]
        o.update({"state": "koncano", "percent": 100, "name": "film-1080p.mp4", "file_id": "media:shramba:7",
                  "size": len(self.izhod), "where": "Download/Safeer Shramba/film-1080p.mp4"})


class PretvorbaVidea(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-pretvorba-")
        self.pot = os.path.join(self.mapa, "film.mkv")
        self.vsebina = os.urandom(200000)
        with open(self.pot, "wb") as d:
            d.write(self.vsebina)
        self.d = link_datoteke.Datoteke([], tls_mapa=os.path.join(self.mapa, "tls"))
        self.n = {"tablica": _Naprava(kodirniki(1920)),
                  "tv": _Naprava(kodirniki(4096, hevc=True)),
                  "stara": _Naprava(kodirniki(1280)),                  # samo 720p - ne pride v postev
                  "pc": _Naprava(kodirniki(4096, hevc=True))}           # racunalnik ne pretvarja za druge
        self.naprave = [{"id": "tablica", "ime": "Tablica", "zmoznosti": ["files"], "platforma": "tablet"},
                        {"id": "tv", "ime": "TV", "zmoznosti": ["files"], "platforma": "tv"},
                        {"id": "stara", "ime": "Stara", "zmoznosti": ["files"], "platforma": "phone"},
                        {"id": "pc", "ime": "PC", "zmoznosti": ["files"], "platforma": "linux"},
                        {"id": "jaz", "ime": "Jaz", "zmoznosti": ["files"], "platforma": "phone", "ta": True}]
        self.preneseno = []
        self.oblika = None

        def prenesi(streznik, oznaka, cilj, o):
            self.preneseno.append((streznik["base_url"], oznaka))
            with open(cilj, "wb") as f:
                f.write(self.n[o.cilj].izhod)

        self.p = link_pretvorba.Pretvorba(lambda: self.naprave,
                                          lambda i, d, p: self.n[i].ukaz(d, p) if i in self.n else {"ok": False},
                                          self.d, cakaj=0.05, prenesi=prenesi, sonda=lambda pot: self.oblika)

    def tearDown(self):
        self.d.ustavi()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def _pocakaj(self, id_, koncna=("koncano", "napaka", "na_racunalniku", "pusceno")):
        for _ in range(200):
            r = self.p.stanje(id_)
            if r["stanje"] in koncna:
                return r
            time.sleep(0.05)
        self.fail("pretvorba se ni koncala")

    def test_najboljsi_kodirnik_in_prenos_nazaj(self):
        r = self._pocakaj(self.p.zacni(self.pot)["id"])
        self.assertEqual((r["stanje"], r["naprava"]), ("koncano", "TV"))      # 4K + HEVC, ne racunalnik
        self.assertEqual(self.n["tv"].izhod, self.vsebina[::-1])              # izvirnik prenesen v celoti
        self.assertIn("Safeer Shramba/film-1080p.mp4", r["kje"])
        self.assertEqual(self.n["pc"].vprasan, 0)
        r = self.p.prenesi(r["id"])
        r = self._pocakaj(r["id"], ("na_racunalniku", "koncano"))
        self.assertEqual(r["stanje"], "na_racunalniku")
        self.assertEqual(r["lokalno"], os.path.join(self.mapa, "film-1080p.mp4"))
        with open(r["lokalno"], "rb") as f:
            self.assertEqual(f.read(), self.vsebina[::-1])
        self.assertEqual(self.preneseno, [("https://127.0.0.1:1", "media:shramba:7")])
        with open(self.pot, "rb") as f:
            self.assertEqual(f.read(), self.vsebina)                         # izvirnik nedotaknjen

    def test_pusti_na_napravi_in_naprava_ne_deli(self):
        r = self._pocakaj(self.p.zacni(self.pot)["id"])
        self.assertEqual(self.p.pusti(r["id"])["stanje"], "pusceno")
        self.assertFalse(self.p.prenesi(r["id"])["ok"])
        self.n["tv"].deli = False
        r = self._pocakaj(self.p.zacni(self.pot)["id"])
        self.p.prenesi(r["id"])
        time.sleep(0.2)
        r = self.p.stanje(r["id"])
        self.assertEqual((r["stanje"], r["napaka"]), ("koncano", "naprava_ne_deli"))
        self.assertFalse(os.path.exists(os.path.join(self.mapa, "film-1080p.mp4")))

    def test_brez_moci_prostora_ali_kodirnika(self):
        self.n["tv"].pomaga = False                                          # npr. baterija
        r = self._pocakaj(self.p.zacni(self.pot)["id"])
        self.assertEqual(r["naprava"], "Tablica")
        self.n["tablica"].prosto = 2 * GB                                    # premalo za izvirnik + izhod + rezervo
        r = self._pocakaj(self.p.zacni(self.pot)["id"])
        self.assertEqual((r["stanje"], r["napaka"]), ("napaka", "ni_naprave"))
        self.assertFalse(self.p.zacni(os.path.join(self.mapa, "ni.mkv"))["ok"])
        dok = os.path.join(self.mapa, "zapiski.txt")
        open(dok, "w").close()
        self.assertEqual(self.p.zacni(dok)["koda"], "ni_video")

    def test_dekodirnik_in_zavrnitev(self):
        self.oblika = {"mime": "video/hevc", "width": 3840, "height": 2160}
        self.n["tv"].dek = [{"vrsta": "hevc", "sirina": 1920, "visina": 1080}]          # TV ne prebere 4K HEVC
        r = self._pocakaj(self.p.zacni(self.pot)["id"])
        self.assertEqual(r["naprava"], "Tablica")
        self.assertEqual(self.n["tablica"].parametri["mime"], "video/hevc")             # naprava preveri se sama
        self.n["tablica"].dek = []
        r = self._pocakaj(self.p.zacni(self.pot)["id"])
        self.assertEqual((r["stanje"], r["napaka"]), ("napaka", "ne_zna_dekodirati"))
        self.oblika = {"mime": "video/hevc", "width": 1080, "height": 1920}            # pokoncni video
        self.n["tv"].zavrni = "baterija"                                                 # najboljsa medtem reče ne
        self.n["tablica"].dek = [{"vrsta": "hevc", "sirina": 1920, "visina": 1080}]
        r = self._pocakaj(self.p.zacni(self.pot)["id"])
        self.assertEqual((r["stanje"], r["naprava"]), ("koncano", "Tablica"))

    def test_rezerva_po_velikosti_diska(self):
        self.assertEqual(link_pretvorba.rezerva(5 * GB), 512 * 1024 ** 2)          # televizor
        self.assertEqual(link_pretvorba.rezerva(64 * GB), 2 * GB)                  # tablica
        self.assertEqual(link_pretvorba.rezerva(0), 2 * GB)                        # neznano: previdno
        self.n = {"tv": _Naprava(kodirniki(4096), prosto=1800 * 1024 ** 2)}
        self.n["tv"].skupaj = 5 * GB
        self.naprave = [{"id": "tv", "ime": "TV", "zmoznosti": ["files"], "platforma": "tv"}]
        r = self._pocakaj(self.p.zacni(self.pot)["id"])
        self.assertEqual((r["stanje"], r["naprava"]), ("koncano", "TV"))

    def test_ime_in_prosta_pot(self):
        self.assertEqual(link_pretvorba.ime_pretvorjenega("Moj film.2024.mkv"), "Moj film.2024-1080p.mp4")
        open(os.path.join(self.mapa, "a-1080p.mp4"), "w").close()
        self.assertEqual(link_pretvorba.prosta_pot(self.mapa, "a-1080p.mp4"), os.path.join(self.mapa, "a-1080p (2).mp4"))


if __name__ == "__main__":
    unittest.main()
