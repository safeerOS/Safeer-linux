"""Javni katalogi (core/zakoniti_viri.py): katalog ne caka na streznik, ki ne odgovarja.

4. 10. 2026: vgrajeni streznik PeerTube ni odgovarjal; vsak pogled Videa, ki ga se ni bilo v predpomnilniku, je cakal
10 s. Streznik, ki pocasi odpove, zdaj nekaj minut preskakujemo in ga po premoru vprasamo znova v ozadju.
"""
import io
import json
import time
import unittest
import urllib.error

from core import zakoniti_viri as z


class _Odgovor(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def _pocakaj(pogoj, rok=3.0):
    konec = time.monotonic() + rok
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(0.01)
    return pogoj()


class BrezCakanja(unittest.TestCase):
    def setUp(self):
        self.klici = []                 # (streznik, cas, ki ga je zahteva dobila)
        self.mrtvi = set()
        self.napaka = OSError("timed out")
        self.zdaj = [1_000_000.0]

        def odpri(zahteva, timeout=None):
            host = zahteva.host
            self.klici.append((host, timeout))
            if host in self.mrtvi:
                raise self.napaka
            return _Odgovor(json.dumps({"data": [{"name": "Video z " + host, "uuid": host + "-1", "language": {"id": "sl"}}]}).encode())
        self.viri = z.ZakonitiViri(opener=odpri, clock=lambda: self.zdaj[0])
        self.viri._video_hosts = lambda configured: ["ziv.example", "mrtev.example"]

    def _stevilo(self, host):
        return sum(1 for h, _t in self.klici if h == host)

    def test_pocasna_napaka_izloci_streznik_za_nekaj_minut(self):
        self.viri._pocasi_s = 0         # vsaka napaka steje kot pocasna (v preizkusu ne cakamo zares)
        self.mrtvi.add("mrtev.example")
        prvi = self.viri.videos()
        self.assertEqual({v["streznik"] for v in prvi}, {"ziv.example"}, "zivi streznik da svoje videe")
        # Tri vprasanja (trije seznami) gredo hkrati; ko prvo odpove, se ostala ne posiljajo vec.
        prej = self._stevilo("mrtev.example")
        self.assertTrue(1 <= prej <= 3, prej)
        # Seznam videov ima krajsi rok kot ostale zahteve.
        self.assertEqual({t for _h, t in self.klici}, {z._TIMEOUT_SEZNAM})
        self.assertLess(z._TIMEOUT_SEZNAM, z._TIMEOUT)
        # Nov pogled (drug jezik = drugi naslovi): mrtvega streznika ne sprasujemo vec - uporabnik ne caka.
        self.viri.videos("", None, "sl")
        self.assertEqual(self._stevilo("mrtev.example"), prej)
        self.assertEqual(self._stevilo("ziv.example"), 6)
        with self.assertRaises(OSError):
            self.viri._json("https://mrtev.example/api/v1/config")
        self.assertEqual(self._stevilo("mrtev.example"), prej)

    def test_po_premoru_vprasamo_v_ozadju_in_streznik_se_vrne(self):
        self.viri._pocasi_s = 0
        self.mrtvi.add("mrtev.example")
        self.viri.videos()
        prej = self._stevilo("mrtev.example")
        self.mrtvi.clear()              # streznik spet dela
        self.zdaj[0] += z._PREMOR_STREZNIKA - 5
        self.viri.videos("", None, "de")
        self.assertEqual(self._stevilo("mrtev.example"), prej, "med premorom brez vprasanj")
        self.zdaj[0] += 10
        # Prvo vprasanje po premoru gre v ozadje (uporabnik nanj ne caka); zivi streznik odgovori kot vedno.
        z_ozadjem = self.viri.videos("", None, "fr")
        self.assertIn("ziv.example", {v["streznik"] for v in z_ozadjem})
        self.assertTrue(_pocakaj(lambda: "mrtev.example" not in self.viri._nedosegljivi and not self.viri._preverjam))
        # ... naslednji ga ze uporabi.
        nazaj = self.viri.videos("", None, "it")
        self.assertEqual({v["streznik"] for v in nazaj}, {"ziv.example", "mrtev.example"})

    def test_katalog_ne_caka_na_zadnji_pocasni_streznik(self):
        """Zivi streznik odgovori takoj, mrtvi visi: seznam pride po kratkem roku, ne po roku zahteve."""
        import threading
        spusti = threading.Event()

        def odpri(zahteva, timeout=None):
            if zahteva.host == "mrtev.example":
                spusti.wait(5)                              # »visi«, dokler ga preizkus ne spusti
                raise OSError("timed out")
            return _Odgovor(json.dumps({"data": [{"name": "Video", "uuid": zahteva.selector[-12:], "language": {"id": "sl"}}]}).encode())
        viri = z.ZakonitiViri(opener=odpri, clock=lambda: self.zdaj[0])
        viri._video_hosts = lambda configured: ["ziv.example", "mrtev.example"]
        viri._pocasi_s = 0.2
        staro = z._PO_PRVEM_S
        z._PO_PRVEM_S = 0.3
        try:
            zacetek = time.monotonic()
            videi = viri.videos()
            trajalo = time.monotonic() - zacetek
        finally:
            z._PO_PRVEM_S = staro
            spusti.set()
        self.assertTrue(videi and {v["streznik"] for v in videi} == {"ziv.example"})
        self.assertLess(trajalo, 2.0, "na viseci streznik ne cakamo")
        # Viseci streznik se, ko odpove, oznaci - naslednji pogled ga ne sprasuje.
        self.assertTrue(_pocakaj(lambda: "mrtev.example" in viri._nedosegljivi))

    def test_hitra_napaka_streznika_ne_izloci(self):
        self.mrtvi.add("mrtev.example")     # napaka pride takoj (zavrnjena povezava): nihce ne caka
        self.viri.videos()
        self.viri.videos("", None, "sl")
        self.assertEqual(self._stevilo("mrtev.example"), 6)
        self.assertEqual(self.viri._nedosegljivi, {})

    def test_napaka_http_pomeni_da_streznik_odgovarja(self):
        self.viri._pocasi_s = 0
        self.mrtvi.add("mrtev.example")
        self.napaka = urllib.error.HTTPError("https://mrtev.example/x", 404, "Not Found", {}, io.BytesIO(b""))
        with self.assertRaises(urllib.error.HTTPError):
            self.viri._json("https://mrtev.example/api/v1/videos/ni-ga")
        self.assertEqual(self.viri._nedosegljivi, {})
        with self.assertRaises(urllib.error.HTTPError):
            self.viri._json("https://mrtev.example/api/v1/videos/ni-ga")
        self.assertEqual(self._stevilo("mrtev.example"), 2)


if __name__ == "__main__":
    unittest.main()
