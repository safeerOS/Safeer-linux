"""Radio v Medijskem centru: filter po drzavi (lastnik, 15. 10. 2026). Omrezje je nadomesceno."""
import json
import os
import urllib.parse
import unittest

from core import zakoniti_viri

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Odgovor:
    def __init__(self, podatki):
        self._b = json.dumps(podatki).encode()

    def read(self, *_a):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _postaja(i, drzava):
    return {"stationuuid": "u%s%d" % (drzava, i), "name": "Postaja %s %d" % (drzava, i), "url_resolved": "https://r.test/%s%d" % (drzava, i),
            "url": "https://r.test/%s%d" % (drzava, i), "country": drzava, "countrycode": drzava, "codec": "MP3", "bitrate": 128,
            "favicon": "", "tags": ""}


class RadioDrzava(unittest.TestCase):
    def setUp(self):
        self.zahteve = []

        def odpri(zahteva, timeout=None):
            url = zahteva if isinstance(zahteva, str) else zahteva.full_url
            self.zahteve.append(url)
            if "/json/countries" in url:
                return _Odgovor([{"name": "Slovenia", "iso_3166_1": "SI", "stationcount": 150},
                                 {"name": "Austria", "iso_3166_1": "AT", "stationcount": 900},
                                 {"name": "Tiny", "iso_3166_1": "TV", "stationcount": 1},
                                 {"name": "Bad", "iso_3166_1": "", "stationcount": 50}])
            if "opml.radiotime" in url:
                raise OSError("TuneIn ni v preizkusu")
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            drzava = (q.get("countrycode") or ["XX"])[0]
            return _Odgovor([_postaja(i, drzava) for i in range(3)])

        self.z = zakoniti_viri.ZakonitiViri(opener=odpri)

    def _radio_zahteve(self):
        return [urllib.parse.parse_qs(urllib.parse.urlsplit(u).query) for u in self.zahteve if "stations/search" in u]

    def test_izbrana_drzava_velja_za_vse_skupine(self):
        postaje = self.z.radio("", "", "at")
        self.assertTrue(postaje)
        self.assertTrue(all(p["drzava"] == "AT" for p in postaje))
        self.assertTrue(all(q.get("countrycode") == ["AT"] for q in self._radio_zahteve()))
        self.assertFalse(any("radiotime" in u for u in self.zahteve))     # TuneIn ne pove drzave

    def test_iskanje_in_zvrst_v_drzavi(self):
        self.z.radio("ena", "", "SI")
        self.z.radio("", next(iter(k for k, v in zakoniti_viri.GLASBENE_ZVRSTI.items() if v[2])), "SI")
        self.assertTrue(all(q.get("countrycode") == ["SI"] for q in self._radio_zahteve()))

    def test_neveljavna_koda_ne_filtrira(self):
        self.z.radio("", "", "SLO<script>")
        kode = {tuple(q.get("countrycode") or []) for q in self._radio_zahteve()}
        self.assertIn((), kode)                                            # svetovne skupine brez drzave
        self.assertNotIn(("SLO<SCRIPT>",), kode)

    def test_seznam_drzav(self):
        self.assertEqual(self.z.radio_drzave(), [{"id": "SI", "postaj": 150}, {"id": "AT", "postaj": 900}])

    def test_kljuc_kataloga_loci_drzave(self):
        from core import os_media
        self.assertEqual(os_media._drzava_radia(" si "), "SI")
        self.assertEqual(os_media._drzava_radia("SVN"), "")


class RadioDrzavaVmesnik(unittest.TestCase):
    def setUp(self):
        beri = lambda *d: open(os.path.join(KOREN, *d), encoding="utf-8").read()
        self.html, self.js, self.css = beri("assets", "os", "index.html"), beri("assets", "os", "os.js"), beri("assets", "os", "os.css")
        self.bes = beri("assets", "os", "besedila.js")

    def test_izbira_samo_pri_radiu(self):
        self.assertIn('id="mediaDrzavaPolje" hidden><select id="mediaDrzava">', self.html)
        self.assertIn('return !kat.seznam && kat.filter === "radio" ? (kat.drzavaRadia || "") : "";', self.js)
        self.assertIn("[], izbranJezik(), izbranaDrzavaRadia()]", self.js)
        self.assertIn('klic("mediaRadioDrzave", [])', self.js)

    def test_besedila_v_vseh_jezikih(self):
        for j in ("sl", "en", "de", "es", "fr", "it"):
            self.assertIn('Object.assign(BESEDILA_OS.%s, {"katDrzavaPostaj"' % j, self.bes)

    def test_gumb_skrci_ni_pod_drsnikom(self):
        # Lastnik 15. 10. 2026: drsnik leve navigacije je prekril gumb Skrci in klik ga ni dosegel.
        nav = self.html.split('<nav class="media-nav"', 1)[1].split("</nav>", 1)[0]
        self.assertLess(nav.index('id="mediaNavSkrci"'), nav.index('class="media-nav-drsno"'))
        self.assertIn(".media-nav-drsno { display: flex; flex-direction: column; gap: 24px; min-height: 0; overflow-y: auto;", self.css)
        siroko = self.css.split(".media-nav { position: sticky;", 1)[1].split("}", 1)[0]
        self.assertNotIn("overflow", siroko)


if __name__ == "__main__":
    unittest.main()
