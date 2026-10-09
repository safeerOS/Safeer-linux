"""Meritev poti do sosednjega sredisca (core/link_pot.py) z vstavljeno uro.

Tovor pinga je 12 bajtov '>IQ'; vse drugo (prazen ping, tuj tovor) se ne steje. Zamik je EWMA, najmanjsi zamik
ne uposteva sond, ki so cakale za polno pisalno vrsto, sonda je zgresena sele po roku, mrtva pa je samo povezava,
ki je ze odgovarjala in nato trikrat zapored ni.
"""
import struct
import unittest

from core import link_pot


class Ura:
    def __init__(self, t: float = 500.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


class Tovor(unittest.TestCase):
    def test_paket_in_razpakiraj(self):
        p = link_pot.paket(17, 123456789012)
        self.assertEqual(len(p), 12)
        self.assertEqual(p, struct.pack(">IQ", 17, 123456789012))
        self.assertEqual(link_pot.razpakiraj(p), (17, 123456789012))
        self.assertEqual(link_pot.razpakiraj(bytearray(p)), (17, 123456789012))
        self.assertEqual(link_pot.razpakiraj(link_pot.paket(2 ** 32 + 5, 1)), (5, 1), "seq je 32-bitni")

    def test_tovor_ki_ni_12_bajtov_se_zavrne(self):
        for tovor in (b"", b"zivjo", bytes(11), bytes(13), None, "dvanajst zn."):
            self.assertIsNone(link_pot.razpakiraj(tovor), repr(tovor))

    def test_pot_iz_naslova(self):
        for naslov in ("wss://127.0.0.1:41234/cast/ws", "127.0.0.1", "::1", "[::1]", "localhost",
                       "::ffff:127.0.0.1"):
            self.assertEqual(link_pot.pot_naslova(naslov), "rele", naslov)
        for naslov in ("wss://192.168.0.77:8990/cast/ws", "192.168.0.50", "fe80::1", ""):
            self.assertEqual(link_pot.pot_naslova(naslov), "lan", naslov)


class _Osnova(unittest.TestCase):
    def setUp(self):
        self.ura = Ura()
        self.m = link_pot.MeritevPoti("lan", ura=self.ura)

    def sonda(self, rtt_ms=None, zaseden=False):
        """Sonda zdaj; z `rtt_ms` pride pong po toliko ms (ura se premakne)."""
        tovor = self.m.sonda(zaseden=zaseden)
        if rtt_ms is None:
            return tovor
        self.ura.t += rtt_ms / 1000.0
        rtt = self.m.pong(tovor)
        return None if rtt is None else round(rtt, 6)


class Zamik(_Osnova):
    def test_ewma_min_in_jitter(self):
        self.assertEqual(self.sonda(10), 10.0)
        self.assertAlmostEqual(self.m.rtt_ms, 10.0)
        self.assertAlmostEqual(self.m.min_ms, 10.0)
        self.assertIsNone(self.m.jitter_ms)
        self.sonda(20)
        self.assertAlmostEqual(self.m.rtt_ms, 12.5)            # 10 + 0,25 * (20 - 10)
        self.assertAlmostEqual(self.m.jitter_ms, 10.0)
        self.sonda(6)
        self.assertAlmostEqual(self.m.rtt_ms, 12.5 + 0.25 * (6 - 12.5))
        self.assertAlmostEqual(self.m.jitter_ms, 10.0 + 0.25 * (14 - 10.0))
        self.assertAlmostEqual(self.m.min_ms, 6.0)
        s = self.m.stanje()
        self.assertEqual((s["pot"], s["min_ms"], s["izgube"], s["sond"], s["odgovoril"]), ("lan", 6.0, 0, 3, True))

    def test_sonda_iz_polne_vrste_ne_steje_v_najmanjsi(self):
        self.sonda(30)
        self.assertEqual(self.sonda(2, zaseden=True), 2.0)    # cakala je za sporocili: zamik da, najmanjsi ne
        self.assertAlmostEqual(self.m.min_ms, 30.0)
        self.assertLess(self.m.rtt_ms, 30.0)
        self.sonda(25)
        self.assertAlmostEqual(self.m.min_ms, 25.0)

    def test_neznan_podvojen_in_tuj_pong(self):
        tovor = self.m.sonda()
        self.ura.t += 0.01
        self.assertIsNone(self.m.pong(b""), "prazen pong (stari utrip) ni meritev")
        self.assertIsNone(self.m.pong(link_pot.paket(999, 1)))
        seq, t_us = link_pot.razpakiraj(tovor)
        self.assertIsNone(self.m.pong(link_pot.paket(seq, t_us + 1)), "isti seq, tuj cas")
        self.assertAlmostEqual(self.m.pong(tovor), 10.0)
        self.assertIsNone(self.m.pong(tovor), "podvojen pong")
        self.assertEqual(self.m.odgovorov, 1)

    def test_poslano_z_zunanjim_casom(self):
        self.m.poslano(7, 100.0)
        self.assertAlmostEqual(self.m.pong(link_pot.paket(7, 100_000_000), 100.042), 42.0)


class Izgube(_Osnova):
    def test_zgresena_sele_po_roku(self):
        tovor = self.sonda()
        self.ura.t += 4.9
        self.assertEqual(self.m.preveri(), 0)
        self.assertEqual(self.m.stanje()["izgube"], 0)
        self.ura.t += 0.2
        self.assertEqual(self.m.preveri(), 1)
        self.assertEqual((self.m.izgube, self.m.zaporedno_brez), (1, 1))
        self.assertIsNone(self.m.pong(tovor), "pong po roku je ze stet kot zgresen")

    def test_rok_je_stirikratnik_pocasne_poti(self):
        self.sonda(2000)                                     # rele cez pol sveta: rok = max(5 s, 4 * 2 s)
        self.assertEqual(self.m.rok_s(), 8.0)
        self.sonda()
        self.ura.t += 7.0
        self.assertEqual(self.m.preveri(), 0)
        self.ura.t += 1.5
        self.assertEqual(self.m.preveri(), 1)

    def test_izgube_v_zadnjih_20(self):
        for i in range(30):
            if i % 3 == 0:
                self.sonda()
                self.ura.t += 6.0
                self.m.preveri()
            else:
                self.sonda(10)
        # Zadnjih 20 sond: i = 10..29, zgresene so i = 12, 15, 18, 21, 24, 27.
        s = self.m.stanje()
        self.assertEqual((s["sond"], s["izgube"]), (20, 6))

    def test_mrtva_sele_po_odgovoru_in_treh_zgresenih(self):
        for _ in range(5):
            self.sonda()
            self.ura.t += 6.0
            self.m.preveri()
        self.assertEqual(self.m.zaporedno_brez, 5)
        self.assertFalse(self.m.mrtva, "povezava, ki se ni nikoli odgovorila, ni mrtva (morda je stari sosed)")
        self.sonda(10)
        self.assertFalse(self.m.mrtva)
        for i in range(3):
            self.assertFalse(self.m.mrtva, "po %d zgresenih se ni mrtva" % i)
            self.sonda()
            self.ura.t += 6.0
            self.m.preveri()
        self.assertTrue(self.m.mrtva)

    def test_en_pong_ponastavi_zaporedne(self):
        self.sonda(10)
        for _ in range(2):
            self.sonda()
            self.ura.t += 6.0
            self.m.preveri()
        self.assertEqual(self.m.zaporedno_brez, 2)
        self.sonda(10)
        self.assertEqual(self.m.zaporedno_brez, 0)
        self.assertFalse(self.m.mrtva)
        self.assertEqual(self.m.izgube, 2)

    def test_delez_retrans_samo_v_lan(self):
        self.m.tcp({"bytes_sent": 1000, "bytes_retrans": 0})
        self.m.tcp({"bytes_sent": 11000, "bytes_retrans": 100})
        self.assertEqual(self.m.stanje()["delez_retrans"], 0.01)
        rele = link_pot.MeritevPoti("rele", ura=self.ura)
        rele.tcp({"bytes_sent": 1000, "bytes_retrans": 0})
        rele.tcp({"bytes_sent": 11000, "bytes_retrans": 100})
        self.assertIsNone(rele.stanje()["delez_retrans"], "prek releja je vticnica zanka")


if __name__ == "__main__":
    unittest.main()
