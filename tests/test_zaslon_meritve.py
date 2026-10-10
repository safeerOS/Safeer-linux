"""Meritve seje deljenja zaslona (core/link_zaslon_meritve.py) z vstavljeno uro: brez vticnic, brez cakanja.

Preverjamo izracune, na katerih bodo stale meje naslednjih faz: zasedenost in hitrost iz pisanj, mediana treh
(en skok Wi-Fi ne steje), osnova v oknu 300 s, cakanje tudi pri popolnem zastoju, pozni pingi, dostava proti
oddaji iz ure in bajtov gledalca ter povzetek seje.
"""
import json
import threading
import time
import unittest

from core import link_zaslon_meritve as lzm


class Ura:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


class _Osnova(unittest.TestCase):
    def setUp(self):
        self.ura = Ura()
        self.m = lzm.Meritve(ura=self.ura, pot="neposredno", kodek="h264", kakovost="najvisja", kodirnik="vaapi")
        self.n = 0

    def ping(self, rtt_ms: float, **odmev) -> float:
        """Ping zdaj, odmev po `rtt_ms`; ura se premakne do odmeva."""
        self.n += 1
        t = self.ura.t * 1000.0
        self.m.ping_poslan(self.n, t)
        self.ura.t += rtt_ms / 1000.0
        return self.m.pong(dict({"vrsta": "rtt", "n": self.n, "t": t}, **odmev), self.ura.t)


class Posiljanje(_Osnova):
    def test_zasedenost_in_hitrost(self):
        self.ura.t += 5.0
        # Zadnja sekunda: 10 okvirjev slike po 100 kB, vsak sendall 30 ms; 50 kosov zvoka po 1925 B.
        for i in range(10):
            self.ura.t += 0.1
            self.m.poslano(lzm.SLIKA, 100_000, 0.03)
            for _ in range(5):
                self.m.poslano(lzm.ZVOK, 1925, 0.0005)
        p = self.m.posnetek()
        self.assertAlmostEqual(p["poslano_mbps"], 8.0, places=2)
        self.assertAlmostEqual(p["zvok_mbps"], 50 * 1925 * 8 / 1e6, places=2)
        self.assertAlmostEqual(p["zasedenost"], 0.3, places=2)
        self.assertAlmostEqual(p["najdaljse_pisanje_ms"], 30.0, places=1)
        # Cez dve sekundi brez pisanja je vse nic: okno je ena sekunda.
        self.ura.t += 2.0
        p = self.m.posnetek()
        self.assertEqual((p["poslano_mbps"], p["zvok_mbps"], p["zasedenost"]), (0.0, 0.0, 0.0))

    def test_dolgo_pisanje_steje_samo_v_oknu(self):
        self.ura.t += 10.0
        self.m.poslano(lzm.SLIKA, 32 * 1024, 4.0)        # en sendall, ki je cakal 4 s
        p = self.m.posnetek()
        self.assertEqual(p["zasedenost"], 1.0)
        self.assertEqual(p["najdaljse_pisanje_ms"], 4000.0)

    def test_zastoj_je_viden_medtem_ko_traja(self):
        """Crpalka 10 s pise 20 okvirjev po 32 KiB na sekundo (sendall 5 ms), nato en sendall obvisi 4 s (zastoj
        Wi-Fi). Med zastojem mora posnetek kazati polno zasedenost, ne prazne slike; po njem so v povzetku stiri
        zasedene sekunde in ne ena."""
        zacetek = self.ura.t
        for i in range(200):
            self.ura.t = zacetek + i * 0.05
            self.m.zacni_pisanje(lzm.SLIKA)
            self.ura.t += 0.005
            self.m.poslano(lzm.SLIKA, 32 * 1024, 0.005)
        self.assertAlmostEqual(self.m.posnetek()["zasedenost"], 0.1, places=3)
        self.ura.t = zacetek + 10.0
        self.m.zacni_pisanje(lzm.SLIKA)
        self.m.zacni_pisanje(lzm.ZVOK)                   # zvok caka za isto vticnico
        self.ura.t = zacetek + 12.0
        p = self.m.posnetek()
        self.assertEqual(p["zasedenost"], 1.0, "med zastojem crpalka ni prosta")
        self.assertEqual(p["najdaljse_pisanje_ms"], 2000.0)
        self.assertEqual(p["poslano_mbps"], 0.0)
        # Seja, ki se konca sredi zastoja: tudi cas pisanja, ki se traja, je v povzetku.
        self.ura.t = zacetek + 12.5
        self.assertEqual(self.m.povzetek()["zasedenost_p90"], 1.0)
        self.ura.t = zacetek + 14.0
        self.m.poslano(lzm.ZVOK, 1925, 4.0)
        self.m.poslano(lzm.SLIKA, 32 * 1024, 4.0)
        p = self.m.posnetek()
        self.assertEqual((p["zasedenost"], p["najdaljse_pisanje_ms"]), (1.0, 4000.0))
        self.assertEqual([round(z, 3) for z in self.m._sek_zasedeno[9:14]], [0.1, 1.0, 1.0, 1.0, 1.0])
        self.assertEqual(self.m.povzetek()["zasedenost_p90"], 1.0)
        # Pisanje je koncano: v naslednji sekundi je crpalka prosta.
        self.ura.t = zacetek + 15.5
        self.assertEqual(self.m.posnetek()["zasedenost"], 0.0)

    def test_tcp(self):
        self.m.tcp(None)                                 # vticnica ni TCP: nic se ne spremeni
        self.m.tcp({"state": 1, "rtt_us": 4200, "neposlano": 1000, "bytes_sent": 1000, "bytes_retrans": 0})
        self.m.tcp({"state": 1, "rtt_us": 4800, "neposlano": 2000, "bytes_sent": 11000, "bytes_retrans": 500})
        p = self.m.posnetek()
        self.assertEqual(p["neposlano_b"], 2000)
        self.assertEqual(p["tcp_rtt_ms"], 4.8)
        self.assertEqual(p["delez_retrans"], 0.05)


class Zamik(_Osnova):
    def test_mediana_treh_odstrani_en_skok(self):
        for rtt in (9, 9, 9, 65, 9, 9):
            self.ping(rtt)
            self.ura.t += 0.5
            p = self.m.posnetek()
            self.assertEqual(p["rtt_med3_ms"], 9.0, "en sam skok Wi-Fi ne sme v mediano")
        self.assertEqual(p["rtt_osnova_ms"], 9.0)
        self.assertEqual(p["cakanje_ms"], 0.0)

    def test_osnova_potece_po_300_s(self):
        self.ping(5)
        for _ in range(10):
            self.ura.t += 20.0
            self.ping(20)
        self.assertEqual(self.m.posnetek()["rtt_osnova_ms"], 5.0)
        for _ in range(10):
            self.ura.t += 20.0
            self.ping(20)
        p = self.m.posnetek()
        self.assertEqual(p["rtt_osnova_ms"], 20.0, "najmanjsi zamik izpred vec kot 300 s ne velja vec")
        self.assertEqual(p["cakanje_ms"], 0.0)

    def test_cakanje_in_cakanje_eff_z_odprtim_pingom(self):
        for _ in range(3):
            self.ping(10)
            self.ura.t += 0.5
        for _ in range(3):
            self.ping(160)
            self.ura.t += 0.5
        p = self.m.posnetek()
        self.assertEqual(p["cakanje_ms"], 150.0)
        self.assertEqual(p["cakanje_eff_ms"], 150.0)
        # Ping, na katerega odmeva ni: cakanje_eff raste z njegovo starostjo, cakanje (zadnji odmevi) ne.
        self.m.ping_poslan(99, self.ura.t * 1000.0)
        self.ura.t += 2.0
        p = self.m.posnetek()
        self.assertEqual(p["odprt_ping_ms"], 2000.0)
        self.assertEqual(p["cakanje_ms"], 150.0)
        self.assertEqual(p["cakanje_eff_ms"], 1990.0)

    def test_odprt_ping_raste_in_pozni_po_5_s(self):
        self.ping(10)
        self.m.ping_poslan(50, self.ura.t * 1000.0)
        self.ura.t += 1.0
        self.assertEqual(self.m.posnetek()["odprt_ping_ms"], 1000.0)
        self.ura.t += 3.0
        p = self.m.posnetek()
        self.assertEqual(p["odprt_ping_ms"], 4000.0)
        self.assertEqual(p["pozni"], 0)
        self.ura.t += 1.5
        p = self.m.posnetek()
        self.assertEqual(p["odprt_ping_ms"], 5500.0)
        self.assertEqual(p["pozni"], 1)
        self.ura.t += 10.0
        self.assertEqual(self.m.posnetek()["pozni"], 1, "isti ping je pozen samo enkrat")
        # Odmev, ko je ping ze pozen: zamik se zabelezi, poznih pa ni vec.
        self.assertEqual(self.m.pong({"vrsta": "rtt", "n": 50}, self.ura.t), 15500.0)
        p = self.m.posnetek()
        self.assertEqual((p["pozni"], p["odprt_ping_ms"]), (1, 0.0))

    def test_podvojen_ali_neznan_n_se_ne_steje(self):
        self.assertEqual(self.ping(12), 12.0)
        self.assertIsNone(self.m.pong({"vrsta": "rtt", "n": self.n}, self.ura.t + 1))     # podvojen
        self.assertIsNone(self.m.pong({"vrsta": "rtt", "n": 777}, self.ura.t + 1))        # neznan
        self.assertIsNone(self.m.pong({"vrsta": "rtt", "n": "x"}, self.ura.t + 1))
        self.assertIsNone(self.m.pong({"vrsta": "rtt"}, self.ura.t + 1))
        self.assertIsNone(self.m.pong("ni slovar", self.ura.t + 1))
        self.m.ping_poslan(5, 1000.0)
        self.assertIsNone(self.m.pong({"vrsta": "rtt", "n": 5, "t": 1234}, self.ura.t), "tuj cas ni nas ping")
        p = self.m.posnetek()
        self.assertEqual((p["rtt_ms"], p["odmevov"]), (12.0, 1))

    def test_zadnji_rtt_za_prikaz(self):
        self.assertEqual(self.m.zadnji_rtt(), 0)
        self.ping(103.6)
        self.assertEqual(self.m.zadnji_rtt(), 104)


class DostavaInOddaja(_Osnova):
    def test_iz_ure_in_bajtov_gledalca(self):
        r, b = 5000.0, 0
        for _ in range(4):
            self.m.poslano(lzm.SLIKA, 250_000, 0.001)      # 0,25 MB na pol sekunde = 4 Mb/s
            self.ping(20, r=r, b=b)
            r += 500.0                                       # gledalec bere enako hitro, kot posiljamo
            b += 250_000
            self.ura.t += 0.48
        p = self.m.posnetek()
        self.assertAlmostEqual(p["dostava_mbps"], 4.0, places=2)
        self.assertAlmostEqual(p["oddaja_mbps"], 4.0, places=2)
        self.assertIsNone(p["kapaciteta_mbps"], "brez zagozdenosti kapacitete ne vemo")

    def test_vrsta_raste(self):
        """Gledalec dobiva pinge redkeje, kot jih posiljamo: dostava je manjsa od oddaje (razmerje pod 1)."""
        r, b = 0.0, 0
        for i in range(6):
            self.m.poslano(lzm.SLIKA, 500_000, 0.001)
            self.ping(30 + 400 * i, r=r, b=b)
            self.ura.t -= (30 + 400 * i) / 1000.0            # posiljamo na pol sekunde ne glede na odmev
            self.ura.t += 0.5
            r += 900.0                                       # ...gledalec pa bere na 0,9 s
            b += 500_000
        p = self.m.posnetek()
        self.assertLess(p["dostava_mbps"] / p["oddaja_mbps"], 1.0)
        self.assertAlmostEqual(p["dostava_mbps"] / p["oddaja_mbps"], 0.5 / 0.9, places=2)
        self.assertIsNotNone(p["kapaciteta_mbps"], "med zagozdenostjo je dostava kapaciteta poti")

    def test_podatki_gledalca(self):
        self.ping(15, r=1, b=2, fps=59.8, mbps=4.12, dek=12, zastoji=2, izpusceno=0, pot="neposredno", rok=87)
        self.ping(15, r=500, b=4, fps="ni stevilo", zastoji=0)
        g = self.m.posnetek()["gledalec"]
        self.assertEqual(g, {"fps": 59.8, "mbps": 4.12, "dek": 12.0, "zastoji": 0.0, "izpusceno": 0.0,
                             "pot": "neposredno", "rok_ms": 87.0})

    def test_tuje_vrednosti_ne_pokvarijo_meritev(self):
        """Odmev je tuj (pokvarjen ali sovrazen gledalec): ogromno celo stevilo, deljenje s skoraj nic in vrednosti
        zunaj razpona ne smejo dvigniti izjeme sredi odmeva niti spraviti neskoncnosti v posnetek ali v povzetek."""
        ogromno = 10 ** 400                              # json.loads ga da kot int; float() pade z OverflowError
        self.assertEqual(self.ping(10, r=ogromno, b=0, fps=ogromno, zastoji=ogromno, rok=ogromno), 10.0)
        self.assertIsNone(self.m.pong({"vrsta": "rtt", "n": ogromno}, self.ura.t))
        self.ping(10, r=0, b=0)
        self.ping(10, r=1e-200, b=1e300)                 # dr skoraj nic: dostava bi bila neskoncna
        self.ping(10, r=-5.0, b=-1.0)
        for _ in range(3):
            self.ping(10, zastoji=1.7e308, izpusceno=-1, fps=5000, mbps=1e9, dek=-3)
        p = self.m.posnetek()
        self.assertIsNone(p["dostava_mbps"])
        self.assertEqual(p["gledalec"], {})
        self.assertEqual(p["odmevov"], 7)
        povzetek = self.m.povzetek()
        self.assertIsNone(povzetek["zastoji_na_min"])
        json.dumps(p, allow_nan=False)
        json.dumps(povzetek, allow_nan=False)
        # Pravi odmevi za tem se stejejo kot prej.
        self.ping(10, r=1000.0, b=0, fps=59.8, zastoji=1)
        self.ping(10, r=1500.0, b=250_000, zastoji=0)
        p = self.m.posnetek()
        self.assertAlmostEqual(p["dostava_mbps"], 4.0)
        self.assertEqual((p["gledalec"]["fps"], p["gledalec"]["zastoji"]), (59.8, 0.0))
        self.assertEqual(self.m.povzetek()["zastoji_na_min"], 30.0)


class Povzetek(_Osnova):
    def test_polja_p50_p90(self):
        for i in range(20):
            self.m.poslano(lzm.SLIKA, 125_000 * (1 + i % 2), 0.1)
            self.ping(10 + i, zastoji=1)
            self.ura.t += 1.0 - (10 + i) / 1000.0
        povzetek = self.m.povzetek()
        for kljuc in ("pot", "kodirnik", "kodek", "kakovost", "trajanje_s", "mbps_p50", "mbps_p95", "rtt_min_ms",
                      "rtt_p50_ms", "rtt_p90_ms", "cakanje_p90_ms", "zasedenost_p90", "zastoji_na_min", "pozni"):
            self.assertIn(kljuc, povzetek)
        self.assertEqual((povzetek["pot"], povzetek["kodirnik"], povzetek["kodek"], povzetek["kakovost"]),
                         ("neposredno", "vaapi", "h264", "najvisja"))
        self.assertEqual(povzetek["trajanje_s"], 20.0)
        self.assertEqual(povzetek["slika_mb"], 3.75)
        self.assertEqual(self.m.bajtov_slike(), 3_750_000)
        self.assertEqual(povzetek["mbps_p50"], 1.0)
        self.assertEqual(povzetek["mbps_p95"], 2.0)
        self.assertEqual(povzetek["rtt_min_ms"], 10.0)
        self.assertEqual(povzetek["rtt_p50_ms"], 19.0)
        self.assertEqual(povzetek["rtt_p90_ms"], 27.0)
        self.assertAlmostEqual(povzetek["zasedenost_p90"], 0.1)
        self.assertEqual(povzetek["zastoji_na_min"], 60.0)
        self.assertEqual(povzetek["pozni"], 0)

    def test_brez_gledalcevih_odmevov(self):
        self.ura.t += 3.0
        povzetek = self.m.povzetek()
        self.assertIsNone(povzetek["rtt_p50_ms"])
        self.assertIsNone(povzetek["zastoji_na_min"])
        self.assertEqual(povzetek["mbps_p50"], 0.0)


class HkratneNiti(unittest.TestCase):
    def test_tri_niti_hkrati(self):
        m = lzm.Meritve()
        napake = []
        konec = threading.Event()

        def crpalka():
            try:
                while not konec.is_set():
                    m.poslano(lzm.SLIKA, 32768, 0.0001)
                    m.poslano(lzm.ZVOK, 1925, 0.0)
            except Exception as e:  # noqa: BLE001
                napake.append(e)

        def utrip_in_odmev():
            try:
                n = 0
                while not konec.is_set():
                    n += 1
                    t = time.monotonic()
                    m.ping_poslan(n, t * 1000.0)
                    m.pong({"vrsta": "rtt", "n": n, "t": t * 1000.0, "r": n * 10, "b": n * 1000}, time.monotonic())
            except Exception as e:  # noqa: BLE001
                napake.append(e)

        def bralec():
            try:
                while not konec.is_set():
                    m.posnetek()
                    m.tcp({"state": 1, "rtt_us": 100, "bytes_sent": 1, "bytes_retrans": 0})
                    m.povzetek()
            except Exception as e:  # noqa: BLE001
                napake.append(e)

        niti = [threading.Thread(target=f, daemon=True) for f in (crpalka, utrip_in_odmev, bralec)]
        for n in niti:
            n.start()
        konec.wait(0.5)
        konec.set()
        for n in niti:
            n.join(5)
        self.assertEqual(napake, [])
        p = m.posnetek()
        self.assertGreater(p["odmevov"], 0)
        self.assertGreaterEqual(p["zasedenost"], 0.0)
        self.assertLessEqual(p["zasedenost"], 1.0)


if __name__ == "__main__":
    unittest.main()
