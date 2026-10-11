"""Seznanitev s kodo naprave (11. 10. 2026, lastnik: »vsaka naprava se lahko spari z vsako napravo«).

Naprava, ki se prijavlja, pokaze poleg QR kode se svojo 6-mestno kodo (ista prijava s QR kodo, Hub dobi samo SHA-256
kode). Clan Linka jo vpise v »Vpiši kodo z druge naprave« in s tem napravo dovoli. Tukaj: Hub (iskanje po kodi,
omejitev ugibanja, stari odjemalci brez kode), odjemalec (link_hub.zacni_qr, odobri_kodo).
"""
import hashlib
import unittest
from unittest import mock

from core import link_hub, link_hub_streznik


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class HubKodaNaprave(unittest.TestCase):
    def setUp(self):
        self.hub = link_hub_streznik.Hub(odtis="ab" * 32)
        self.ura = [1000.0]
        self.hub.ura = lambda: self.ura[0]
        self.qr_id, napaka = self.hub.zacni_qr("n-nov", "Nov racunalnik", "linux", _sha("dolga-skrivnost-qr"),
                                               "p" * 24, _sha("123456"))
        self.assertIsNone(napaka)

    def test_clan_dovoli_s_kodo_brez_qr_id(self):
        podatki, napaka = self.hub.qr_podatki("", "123456")
        self.assertEqual((podatki or {}).get("name"), "Nov racunalnik", napaka)
        podatki, napaka = self.hub.odobri_qr("", "123456", "n-telefon")
        self.assertIsNone(napaka)
        stanje, zeton = self.hub.prevzemi_qr(self.qr_id, "n-nov", "p" * 24)
        self.assertEqual(stanje, "odobreno")
        self.assertTrue(zeton)

    def test_qr_deluje_kot_prej(self):
        podatki, napaka = self.hub.odobri_qr(self.qr_id, "dolga-skrivnost-qr", "n-telefon")
        self.assertIsNone(napaka)
        # Koda ni skrivnost QR in obratno: dolga skrivnost brez qr_id ni koda.
        self.assertEqual(self.hub.odobri_qr("", "dolga-skrivnost-qr", "n-telefon")[1], "qr_ne_obstaja")

    def test_napacna_koda_in_ista_naprava(self):
        self.assertEqual(self.hub.odobri_qr("", "654321", "n-telefon"), (None, "qr_ne_obstaja"))
        self.assertEqual(self.hub.odobri_qr("", "12345", "n-telefon"), (None, "qr_ne_obstaja"))
        self.assertEqual(self.hub.odobri_qr("", "123456", "n-nov")[1], "ista_naprava")

    def test_ugibanje_je_omejeno(self):
        for i in range(link_hub_streznik.NAJVEC_KODA_NAPAK):
            self.assertEqual(self.hub.odobri_qr("", "%06d" % (900000 + i), "n-telefon")[1], "qr_ne_obstaja")
        # Tudi prava koda zdaj caka: ugibalec ne ve, ali je zadel.
        self.assertEqual(self.hub.odobri_qr("", "123456", "n-telefon")[1], "prevec_poskusov")
        self.ura[0] += 61
        self.assertIsNone(self.hub.odobri_qr("", "123456", "n-telefon")[1])

    def test_star_odjemalec_brez_kode(self):
        qr_id, _ = self.hub.zacni_qr("n-star", "Star", "android", _sha("x" * 32), "q" * 24)
        self.assertEqual(self.hub.odobri_qr("", "000000", "n-telefon")[1], "qr_ne_obstaja")
        self.assertIsNone(self.hub.odobri_qr(qr_id, "x" * 32, "n-telefon")[1])

    def test_potekla_koda(self):
        self.ura[0] += link_hub_streznik.PIN_VELJA_S + 1
        self.assertEqual(self.hub.odobri_qr("", "123456", "n-telefon")[1], "qr_ne_obstaja")


class OdjemalecKodaNaprave(unittest.TestCase):
    def test_zacni_qr_ima_kodo_in_dolgo_skrivnost(self):
        poslano = {}

        def zahteva(url, telo=None, zeton=None, timeout=5.0, pripeti=None):
            poslano["telo"] = telo
            return 200, {"qr_id": "ab" * 12, "expires_in_seconds": 300}, "f" * 64

        with mock.patch.object(link_hub.link_tls, "zahteva", zahteva):
            p = link_hub.zacni_qr("wss://192.168.0.77:8990/cast/ws", "n-pc", "PC")
        self.assertRegex(p["koda"], r"^\d{6}$")
        self.assertEqual(len(p["skrivnost"]), 32, "telefoni preverjajo dolzino skrivnosti QR (16..128)")
        self.assertEqual(poslano["telo"]["code_sha256"], _sha(p["koda"]))
        self.assertNotIn(p["koda"], str(poslano["telo"]))
        self.assertNotIn(p["koda"], p["povezava"])

    def test_odobri_kodo_odgovori(self):
        klici = []

        def zahteva(odgovor):
            def z(url, telo=None, zeton=None, timeout=5.0, pripeti=None):
                klici.append((url, telo, zeton))
                return odgovor + ("f" * 64,)
            return z
        primeri = [((200, {"approved": True, "name": "Racunalnik"}), {"ok": True, "ime": "Racunalnik"}),
                   ((404, {"code": "qr_ne_obstaja"}), {"ok": False, "razlog": "qr_ne_obstaja"}),
                   ((400, {"code": "qr_ne_obstaja"}), {"ok": False, "razlog": "qr_ne_obstaja"}),
                   ((429, {"code": "prevec_poskusov"}), {"ok": False, "razlog": "prevec_poskusov"}),
                   ((409, {"code": "ista_naprava"}), {"ok": False, "razlog": "ista_naprava"}),
                   ((401, {}), {"ok": False, "razlog": "ni_seznanjena"}),
                   ((0, {}), {"ok": False, "razlog": "ni_huba"})]
        for odgovor, pricakovano in primeri:
            with mock.patch.object(link_hub.link_tls, "zahteva", zahteva(odgovor)):
                self.assertEqual(link_hub.odobri_kodo("wss://h:8990/cast/ws", "zeton", "f" * 64, "123 456"), pricakovano)
        url, telo, zeton = klici[0]
        self.assertTrue(url.endswith("/cast/pair/qr/approve"))
        self.assertEqual(telo, {"qr_id": "", "secret": "123456"})
        self.assertEqual(zeton, "zeton")
        self.assertEqual(link_hub.odobri_kodo("wss://h:8990/cast/ws", "z", "f", "12"), {"ok": False, "razlog": "qr_ne_obstaja"})


class VZivo(unittest.TestCase):
    """Cela pot cez TLS: nova naprava odpre prijavo (QR + koda), clan Linka vpise kodo, nova naprava dobi zeton."""

    @classmethod
    def setUpClass(cls):
        cls.streznik = link_hub_streznik.HubStreznik()
        if not cls.streznik.zazeni():
            raise unittest.SkipTest("huba ni bilo mogoce zagnati")
        cls.naslov = "wss://127.0.0.1:%d%s" % (cls.streznik.vrata, link_hub_streznik.POT_WS)

    @classmethod
    def tearDownClass(cls):
        cls.streznik.ustavi()

    def test_koda_naprave_od_zacetka_do_zetona(self):
        prijava = link_hub.zacni_qr(self.naslov, "n-nov-pc", "Nov racunalnik", "linux")
        self.assertTrue(prijava and not prijava.get("napaka"), prijava)
        self.assertEqual(link_hub.stanje_qr(self.naslov, prijava, "n-nov-pc"), (None, "caka"))
        zeton_clana = self.streznik.hub._nov_zeton("n-telefon", "Telefon")
        napacna = "%06d" % ((int(prijava["koda"]) + 1) % 1000000)
        self.assertEqual(link_hub.odobri_kodo(self.naslov, zeton_clana, self.streznik.odtis, napacna),
                         {"ok": False, "razlog": "qr_ne_obstaja"})
        self.assertEqual(link_hub.odobri_kodo(self.naslov, "ni-zeton", self.streznik.odtis, prijava["koda"]),
                         {"ok": False, "razlog": "ni_seznanjena"})
        self.assertEqual(link_hub.odobri_kodo(self.naslov, zeton_clana, self.streznik.odtis, prijava["koda"]),
                         {"ok": True, "ime": "Nov racunalnik"})
        zeton, razlog = link_hub.stanje_qr(self.naslov, prijava, "n-nov-pc")
        self.assertTrue(zeton, razlog)
        self.assertEqual(self.streznik.hub.naprava_zetona(zeton)[0], "n-nov-pc")
