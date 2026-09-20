"""Krog zaupanja Safeer Linka na Linuxu (core/link_krog.py).

Brez zivega Huba: ista pravila kot v UsmerjevalnikTest.preizkusKroga na Androidu -
 - kljuc naprave je EC P-256 (openssl), podpis SHA256withECDSA se preveri z javnim kljucem,
 - podpisani podatki so vezani na odtis huba, enkratni izziv in id naprave,
 - id nove naprave iz kljuca je "n-" + 16 hex SHA-256 zapisa SPKI,
 - zdruzevanje je deterministicno: vrstni red ne spremeni rezultata,
 - umik ima prednost pred starejsim vnosom, novejsi vnos napravo vrne,
 - pokvarjen zapis (brez kljuca, nesmiseln kljuc) kroga ne pokvari,
 - krog se ob spremembi zapise na disk z dovoljenji 0600 in se ob zagonu prebere.
"""
import base64
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

from core import link_hub, link_krog


def _nov_kljuc(mapa: str, ime: str) -> str:
    pot = os.path.join(mapa, ime + ".pem")
    subprocess.run(["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", pot],
                   check=True, capture_output=True)
    return pot


def _javni(pot_kljuca: str) -> str:
    der = subprocess.run(["openssl", "pkey", "-in", pot_kljuca, "-pubout", "-outform", "DER"],
                         check=True, capture_output=True).stdout
    return base64.b64encode(der).decode("ascii")


def _preveri(kljuc_b64: str, podatki: bytes, podpis_b64: str, mapa: str) -> bool:
    javni = os.path.join(mapa, "javni.der")
    with open(javni, "wb") as d:
        d.write(base64.b64decode(kljuc_b64))
    podpis = os.path.join(mapa, "podpis.der")
    with open(podpis, "wb") as d:
        d.write(base64.b64decode(podpis_b64))
    r = subprocess.run(["openssl", "dgst", "-sha256", "-verify", javni, "-keyform", "DER", "-signature", podpis],
                       input=podatki, capture_output=True)
    return r.returncode == 0


class KljucNaprave(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-krog-")
        self.kljuc = _nov_kljuc(self.mapa, "naprava")
        link_krog._javni = None
        self._p = mock.patch.object(link_krog, "_pot_kljuca", return_value=self.kljuc)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        link_krog._javni = None
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_javni_kljuc_je_spki_p256(self):
        b64 = link_krog.javni_kljuc_b64()
        der = base64.b64decode(b64)
        self.assertEqual(len(der), 91)
        self.assertEqual(der[:1], b"\x30")
        self.assertTrue(link_krog._veljaven_kljuc(b64))
        self.assertEqual(b64, _javni(self.kljuc))

    def test_podpis_se_preveri_z_javnim_kljucem(self):
        podatki = link_krog.podatki_za_podpis("AB" * 32, "nonce-1", "pc-test")
        self.assertEqual(podatki, b"safeer-link-auth\n" + b"ab" * 32 + b"\nnonce-1\npc-test")
        podpis = link_krog.podpisi(podatki)
        self.assertTrue(_preveri(link_krog.javni_kljuc_b64(), podatki, podpis, self.mapa))
        # Drug izziv, drug hub ali druga naprava: isti podpis ne velja.
        for drugi in (("ab" * 32, "nonce-2", "pc-test"), ("cd" * 32, "nonce-1", "pc-test"), ("ab" * 32, "nonce-1", "pc-drug")):
            self.assertFalse(_preveri(link_krog.javni_kljuc_b64(), link_krog.podatki_za_podpis(*drugi), podpis, self.mapa))
        # Tuj kljuc podpisa ne potrdi.
        tuj = _javni(_nov_kljuc(self.mapa, "tuja"))
        self.assertFalse(_preveri(tuj, podatki, podpis, self.mapa))

    def test_id_iz_kljuca(self):
        b64 = link_krog.javni_kljuc_b64()
        i = link_krog.id_iz_kljuca(b64)
        self.assertTrue(i.startswith("n-"))
        self.assertEqual(len(i), 18)
        self.assertEqual(i, link_krog.id_iz_kljuca(b64))
        self.assertNotEqual(i, link_krog.id_iz_kljuca(_javni(_nov_kljuc(self.mapa, "druga"))))

    def test_je_vpisan_primerja_kljuc(self):
        k = link_krog.Krog()
        with mock.patch.object(link_krog, "krog", return_value=k):
            self.assertFalse(link_krog.je_vpisan("pc-test"))
            k.dodaj("pc-test", _javni(_nov_kljuc(self.mapa, "stara")), "Test", "linux", "hub")
            self.assertFalse(link_krog.je_vpisan("pc-test"), "star kljuc pod nasim id ni vpis")
            k.dodaj("pc-test", link_krog.javni_kljuc_b64(), "Test", "linux", "hub")
            self.assertTrue(link_krog.je_vpisan("pc-test"))
            k.umakni("pc-test", "hub")
            self.assertFalse(link_krog.je_vpisan("pc-test"))


class Zdruzevanje(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-krog-")
        self.k1 = _javni(_nov_kljuc(self.mapa, "a"))
        self.k2 = _javni(_nov_kljuc(self.mapa, "b"))

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_dodaj_in_umakni(self):
        k = link_krog.Krog()
        self.assertTrue(k.dodaj("tv-1", self.k1, "TV", "tv", "tv-1", dodano=100.0))
        self.assertTrue(k.dodaj("pc-1", self.k2, "PC", "linux", "tv-1", dodano=101.0))
        self.assertEqual(k.stevilo(), 2)
        self.assertTrue(k.je_clan("pc-1"))
        # Ista naprava, isti kljuc, novo ime: samo ime.
        self.assertTrue(k.dodaj("pc-1", self.k2, "Racunalnik", "linux", "tv-1", dodano=101.0))
        self.assertEqual(k.clan("pc-1")["ime"], "Racunalnik")
        self.assertFalse(k.dodaj("pc-1", self.k2, "Racunalnik", "linux", "tv-1", dodano=101.0))
        self.assertTrue(k.umakni("pc-1", "tv-1", ob=102.0))
        self.assertFalse(k.je_clan("pc-1"))
        self.assertEqual(k.stevilo(), 1)
        # Ponovna seznanitev, novejsa od umika, napravo vrne.
        self.assertTrue(k.dodaj("pc-1", self.k2, "PC", "linux", "tv-1", dodano=103.0))
        self.assertTrue(k.je_clan("pc-1"))
        self.assertNotIn("pc-1", k.json()["umiki"])

    def test_umik_neznane_naprave_ne_spremeni_nicesar(self):
        k = link_krog.Krog()
        k.dodaj("tv-1", self.k1, "TV", "tv", "tv-1", dodano=100.0)
        self.assertFalse(k.umakni("tuja-naprava", "tv-1"))
        self.assertEqual(k.json()["umiki"], {})
        # Zapis je urejen po id - isti krog je na vsaki napravi isti niz.
        k.dodaj("aa-0", self.k2, "A", "phone", "tv-1", dodano=101.0)
        self.assertEqual(list(k.json()["clani"]), ["aa-0", "tv-1"])

    def test_neveljaven_vnos_ne_pokvari_kroga(self):
        k = link_krog.Krog()
        self.assertFalse(k.dodaj("", self.k1, "X", "tv", "x"))
        self.assertFalse(k.dodaj("x", "ni-kljuc", "X", "tv", "x"))
        self.assertFalse(k.zdruzi("to ni json"))
        self.assertFalse(k.zdruzi({"clani": {"x": {"ime": "brez kljuca"}, "y": {"kljuc": "AAAA"}}}))
        self.assertEqual(k.stevilo(), 0)

    def test_zdruzevanje_je_deterministicno(self):
        a = {"clani": {"tv-1": {"kljuc": self.k1, "ime": "TV", "platforma": "tv", "dodano": 100.0, "dodal": "tv-1"},
                       "pc-1": {"kljuc": self.k2, "ime": "PC", "platforma": "linux", "dodano": 101.0, "dodal": "tv-1"}},
             "umiki": {}}
        b = {"clani": {"tv-1": {"kljuc": self.k1, "ime": "TV", "platforma": "tv", "dodano": 100.0, "dodal": "tv-1"}},
             "umiki": {"pc-1": {"umaknjeno": 102.0, "umaknil": "tv-1"}}}
        x, y = link_krog.Krog(), link_krog.Krog()
        x.zdruzi(a); x.zdruzi(b)
        y.zdruzi(b); y.zdruzi(a)
        self.assertEqual(x.json(), y.json())
        self.assertFalse(x.je_clan("pc-1"))
        self.assertTrue(x.je_clan("tv-1"))
        # Krog, ki ga izpljune json(), je enak, ce ga preberemo nazaj.
        z = link_krog.Krog()
        z.zdruzi(json.dumps(x.json()))
        self.assertEqual(z.json(), x.json())

    def test_zapis_na_disk(self):
        pot = os.path.join(self.mapa, "cfg", "krog.json")
        k = link_krog.Krog(pot)
        k.dodaj("tv-1", self.k1, "TV", "tv", "tv-1", dodano=100.0)
        self.assertTrue(os.path.isfile(pot))
        self.assertEqual(stat.S_IMODE(os.stat(pot).st_mode), 0o600)
        znova = link_krog.Krog(pot)
        self.assertEqual(znova.json(), k.json())
        self.assertTrue(znova.je_clan("tv-1"))

    def test_povezava_ima_privzete_zastavice(self):
        p = link_hub.Povezava("wss://127.0.0.1:1/cast/ws", "saf_x", "pc-test", "Test", odtis="ab" * 32)
        self.assertFalse(p.prijava_s_podpisom)
        self.assertFalse(p.vpisana_v_krog)


if __name__ == "__main__":
    unittest.main()
