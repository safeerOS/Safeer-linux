"""Pomoc ob gneci (core/gneca.py): detektor na sinteticnih zaporedjih, merilnik, oznake velikih oddaj in poti
oddaj skozi krajevne konce Global Linka (rele, neposredna pot).

Zaporedja posnemajo meritev na lastnikovi liniji 18. 10. 2026 (zamik do 1.1.1.1): mirovanje mediana 33 ms,
polni prenos 31 ms, polna oddaja mediana 203 ms in p95 418 ms; usmerjevalnik 0,4 ms tudi med oddajo.
"""
import math
import os
import random
import socket
import struct
import tempfile
import threading
import time
import unittest
from unittest import mock

from core import gneca


def _lognormal(rng, mediana, p95):
    """Vzorec z dano mediano in p95 (zamik ima dolg rep navzgor)."""
    sigma = math.log(p95 / mediana) / 1.645
    return mediana * math.exp(rng.gauss(0.0, sigma))


class Zaporedja:
    def __init__(self, seme=18):
        self.rng = random.Random(seme)

    def mirovanje(self, n):
        return [(0.4 + self.rng.random() * 0.2, _lognormal(self.rng, 33.0, 45.0)) for _ in range(n)]

    def prenos(self, n):
        return [(0.4 + self.rng.random() * 0.2, _lognormal(self.rng, 31.0, 44.0)) for _ in range(n)]

    def oddaja(self, n):
        return [(0.4 + self.rng.random() * 0.2, _lognormal(self.rng, 203.0, 418.0)) for _ in range(n)]

    def wifi_sunek(self, n):
        """Tezava v domacem omrezju: zamik do usmerjevalnika skoci, internet z njim."""
        izid = []
        for _ in range(n):
            prehod = 60.0 + self.rng.random() * 140.0
            izid.append((prehod, prehod + _lognormal(self.rng, 33.0, 45.0)))
        return izid


def _poganjaj(d, vzorci):
    return [d.dodaj(p, i) for p, i in vzorci]


class DetektorTest(unittest.TestCase):
    def setUp(self):
        self.z = Zaporedja()
        self.d = gneca.Detektor()

    def test_pragova_pri_izmerjeni_osnovi(self):
        vstop, izstop = gneca.pragova(33.0)
        self.assertEqual((vstop, izstop), (113.0, 73.0))
        # Hitra linija: +80 ms (x3 bi bil samo 30 ms), pocasna: x3.
        self.assertEqual(gneca.pragova(10.0)[0], 90.0)
        self.assertEqual(gneca.pragova(60.0)[0], 180.0)
        self.assertLess(203.0, 418.0)
        self.assertGreater(203.0, vstop, "mediana med oddajo mora biti nad pragom")
        self.assertLess(33.0, izstop)

    def test_mirovanje_ni_gneca(self):
        self.assertFalse(any(_poganjaj(self.d, self.z.mirovanje(600))))
        self.assertAlmostEqual(self.d.osnova(), 30.0, delta=4.0)

    def test_polni_prenos_ni_gneca(self):
        """Med prenosom dol ni vrste (31 ms) - telefona ne potrebujemo."""
        _poganjaj(self.d, self.z.mirovanje(30))
        self.assertFalse(any(_poganjaj(self.d, self.z.prenos(600))))

    def test_oddaja_je_gneca_in_konec_po_histerezi(self):
        _poganjaj(self.d, self.z.mirovanje(30))
        izid = _poganjaj(self.d, self.z.oddaja(300))
        prvi = izid.index(True)
        self.assertLessEqual(prvi, gneca.VSTOP_OKNO, "gneca se zazna v nekaj vzorcih (~10 s)")
        self.assertTrue(all(izid[prvi:]), "med dolgo oddajo (10 min) gneca ne izgine - osnova med gneco miruje")
        konec = _poganjaj(self.d, [(0.5, 33.0)] * 20)
        self.assertEqual(konec.index(False), gneca.IZSTOP_ZAPOREDNIH - 1, "konec po IZSTOP_ZAPOREDNIH nizkih vzorcih")
        self.assertLess(self.d.osnova(), 40.0, "oddaja osnove ne dvigne")

    def test_wifi_sunek_ni_gneca(self):
        """Pocasno je domace omrezje (usmerjevalnik ~60-200 ms): telefon ne pomaga, vzorec ne steje."""
        _poganjaj(self.d, self.z.mirovanje(30))
        self.assertFalse(any(_poganjaj(self.d, self.z.wifi_sunek(100))))

    def test_wifi_sunek_med_gneco_je_ne_konca(self):
        _poganjaj(self.d, self.z.mirovanje(30))
        _poganjaj(self.d, self.z.oddaja(20))
        self.assertTrue(self.d.gneca)
        self.assertTrue(all(_poganjaj(self.d, self.z.wifi_sunek(30))))

    def test_histereza_med_pragovoma(self):
        _poganjaj(self.d, [(0.5, 33.0)] * 30)
        self.assertFalse(any(_poganjaj(self.d, [(0.5, 90.0)] * 50)), "90 ms (med 73 in 113) gnece ne zacne")
        _poganjaj(self.d, [(0.5, 300.0)] * 5)
        self.assertTrue(self.d.gneca)
        self.assertTrue(all(_poganjaj(self.d, [(0.5, 90.0)] * 50)), "90 ms gnece tudi ne konca")

    def test_posamezni_sunki_ne_sprozijo(self):
        _poganjaj(self.d, [(0.5, 33.0)] * 30)
        vzorci = [(0.5, 400.0), (0.5, 33.0), (0.5, 33.0)] * 40
        self.assertFalse(any(_poganjaj(self.d, vzorci)))
        vzorci = [(0.5, 400.0), (0.5, 400.0), (0.5, 400.0), (0.5, 33.0), (0.5, 33.0)] * 20
        self.assertFalse(any(_poganjaj(self.d, vzorci)), "3 od 5 je premalo")

    def test_brez_osnove_ni_gnece(self):
        self.assertFalse(any(_poganjaj(self.d, [(0.5, 400.0)] * (gneca.OSNOVA_NAJMANJ - 1))))
        self.assertIsNone(self.d.osnova())

    def test_brez_odgovora_interneta_je_visok_vzorec(self):
        _poganjaj(self.d, [(0.5, 33.0)] * 30)
        self.assertEqual(_poganjaj(self.d, [(0.5, None)] * 4), [False, False, False, True])

    def test_nic_ne_odgovarja_ni_gneca(self):
        """Izpad omrezja presodi Sonda (nacin »izpad«), ne detektor gnece."""
        _poganjaj(self.d, [(0.5, 33.0)] * 30)
        self.assertFalse(any(_poganjaj(self.d, [(None, None)] * 20)))

    def test_neizmerljiv_usmerjevalnik(self):
        _poganjaj(self.d, [(None, 33.0)] * 30)
        self.assertTrue(_poganjaj(self.d, [(None, 300.0)] * 4)[-1])

    def test_ponastavitev(self):
        _poganjaj(self.d, [(0.5, 33.0)] * 30)
        _poganjaj(self.d, [(0.5, 300.0)] * 5)
        self.d.ponastavi()
        self.assertFalse(self.d.gneca)
        self.assertIsNone(self.d.osnova())

    def test_stanje(self):
        _poganjaj(self.d, [(0.4, 33.4)] * 12)
        st = self.d.stanje()
        self.assertEqual((st["gneca"], st["osnova_ms"], st["internet_ms"], st["prehod_ms"], st["vzorcev"]),
                         (False, 33.0, 33.4, 0.4, 12))


class LazniMerilnik:
    def __init__(self, vzorci, prehod="192.168.1.1"):
        self.vzorci = list(vzorci)
        self.naslov = prehod
        self.metoda = "icmp"
        self._zdaj = None

    def prehod(self):
        return self.naslov

    def rtt_prehoda(self, _naslov):
        self._zdaj = self.vzorci.pop(0)
        return self._zdaj[0]

    def rtt_interneta(self):
        return self._zdaj[1]


class NadzornikTest(unittest.TestCase):
    def test_sprememba_se_javi_in_drugo_omrezje_ponastavi(self):
        javljeno = []
        m = LazniMerilnik([(0.5, 33.0)] * 30 + [(0.5, 300.0)] * 5 + [(0.5, 300.0)] * 3)
        n = gneca.Nadzornik(javljeno.append, merilnik=m)
        for _ in range(35):
            n.korak()
        self.assertEqual(javljeno, [True])
        self.assertTrue(n.gneca)
        m.naslov = "10.0.0.1"                  # prenosnik je v drugem omrezju
        n.korak()
        self.assertEqual(javljeno, [True, False])
        self.assertIsNone(n.detektor.osnova())
        st = n.stanje()
        self.assertEqual((st["metoda"], st["meri"]), ("icmp", False))

    def test_zanka_meri_samo_kadar_je_dovoljeno(self):
        m = LazniMerilnik([(0.5, 33.0)] * 1000)
        dovoljeno = {"da": False}
        n = gneca.Nadzornik(lambda _g: None, merilnik=m, dovoljeno=lambda: dovoljeno["da"])
        with mock.patch.object(gneca, "INTERVAL_S", 0.01):
            n.zazeni()
            try:
                time.sleep(0.15)
                self.assertEqual(n.detektor.vzorcev, 0)
                dovoljeno["da"] = True
                konec = time.monotonic() + 3
                while n.detektor.vzorcev < 3 and time.monotonic() < konec:
                    time.sleep(0.01)
                self.assertGreaterEqual(n.detektor.vzorcev, 3)
            finally:
                n.ustavi()
        time.sleep(0.05)
        self.assertFalse(any(t.name == "safeer-internet-gneca" and t.is_alive() for t in threading.enumerate()))

    def test_ustavitev_konca_gneco(self):
        javljeno = []
        n = gneca.Nadzornik(javljeno.append, merilnik=LazniMerilnik([(0.5, 33.0)] * 30 + [(0.5, 300.0)] * 5))
        for _ in range(35):
            n.korak()
        n.ustavi()
        self.assertEqual(javljeno, [True, False])
        self.assertFalse(n.gneca)


class LaznaIcmp:
    """Vticnica ICMP brez pravic: na odmev odgovori z istim zaporedjem in tovorom (pred tem s tujim odgovorom)."""

    def __init__(self, odgovori=True):
        self.odgovori = odgovori
        self.poslano = b""
        self.zaprta = False
        self._vrsta = []

    def settimeout(self, _t):
        pass

    def sendto(self, paket, naslov):
        self.poslano = paket
        self.naslov = naslov
        if self.odgovori:
            tuj = bytes([0, 0, 0, 0, 0, 7]) + struct.pack("!H", 9999) + b"x" * 8
            self._vrsta = [tuj, bytes([0, 0, 0, 0]) + paket[4:]]

    def recvfrom(self, _n):
        if not self._vrsta:
            raise socket.timeout()
        return self._vrsta.pop(0), ("1.1.1.1", 0)

    def close(self):
        self.zaprta = True


class MerilnikTest(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-gneca-")

    def tearDown(self):
        for ime in os.listdir(self.mapa):
            os.unlink(os.path.join(self.mapa, ime))
        os.rmdir(self.mapa)

    def _poti(self, vsebina):
        pot = os.path.join(self.mapa, "route")
        with open(pot, "w", encoding="ascii") as f:
            f.write("Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n" + vsebina)
        return pot

    def test_privzeti_prehod(self):
        pot = self._poti("wlp2s0\t00000000\t0101A8C0\t0003\t0\t0\t600\t00000000\t0\t0\t0\n"
                         "enp1s0\t00000000\t FE01A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0\n".replace(" ", "")
                         + "enp1s0\t0001A8C0\t00000000\t0001\t0\t0\t100\t00FFFFFF\t0\t0\t0\n")
        self.assertEqual(gneca.privzeti_prehod(pot), "192.168.1.254", "najmanjsa metrika (zicno pred Wi-Fi)")
        self.assertIsNone(gneca.privzeti_prehod(self._poti("wg0\t00000000\t00000000\t0001\t0\t0\t0\t00000000\t0\t0\t0\n")))
        self.assertIsNone(gneca.privzeti_prehod(os.path.join(self.mapa, "ni")))

    def test_icmp_odmev(self):
        m = gneca.Merilnik()
        v = LaznaIcmp()
        with mock.patch.object(gneca.Merilnik, "_icmp_vticnica", staticmethod(lambda: v)):
            ms = m.rtt("1.1.1.1", 1.0, (443,))
        self.assertIsNotNone(ms)
        self.assertEqual(m.metoda, "icmp")
        self.assertEqual(v.poslano[0], 8, "zahteva odmeva")
        self.assertEqual(v.naslov, ("1.1.1.1", 0))
        self.assertTrue(v.zaprta)

    def test_icmp_ni_dovoljen_potem_tcp(self):
        """Brez net.ipv4.ping_group_range: merimo cas rokovanja TCP; zavrnitev (RST) je tudi odgovor."""
        m = gneca.Merilnik()
        s = socket.create_server(("127.0.0.1", 0))
        zaprta = socket.socket()
        zaprta.bind(("127.0.0.1", 0))
        prosta = zaprta.getsockname()[1]
        zaprta.close()
        try:
            with mock.patch.object(gneca.Merilnik, "_icmp_vticnica", staticmethod(lambda: None)):
                self.assertIsNotNone(m.rtt("127.0.0.1", 1.0, (s.getsockname()[1],)))
                self.assertEqual(m.metoda, "tcp")
                self.assertIsNotNone(m.rtt("127.0.0.1", 1.0, (prosta,)), "RST je odgovor")
                self.assertIsNotNone(m.rtt_prehoda("127.0.0.1"))
        finally:
            s.close()

    def test_icmp_filtriran_tcp_dela(self):
        m = gneca.Merilnik()
        s = socket.create_server(("127.0.0.1", 0))
        try:
            with mock.patch.object(gneca.Merilnik, "_icmp_vticnica", staticmethod(lambda: LaznaIcmp(odgovori=False))):
                self.assertIsNotNone(m.rtt("127.0.0.1", 0.2, (s.getsockname()[1],)))
        finally:
            s.close()
        self.assertEqual(m.metoda, "tcp")

    def test_icmp_dela_vzorec_brez_odgovora_ostane_brez(self):
        m = gneca.Merilnik()
        m.icmp = True
        with mock.patch.object(gneca.Merilnik, "_icmp_vticnica", staticmethod(lambda: LaznaIcmp(odgovori=False))), \
                mock.patch.object(gneca.Merilnik, "_tcp", side_effect=AssertionError("ne TCP")):
            self.assertIsNone(m.rtt("1.1.1.1", 0.1, (443,)))

    def test_drugi_cilj_po_treh_brez_odgovora(self):
        m = gneca.Merilnik()
        cilji = []
        with mock.patch.object(m, "rtt", side_effect=lambda c, _r, _v: cilji.append(c)):
            for _ in range(4):
                m.rtt_interneta()
        self.assertEqual(cilji, ["1.1.1.1"] * 3 + ["9.9.9.9"])


class Oddaje(unittest.TestCase):
    def tearDown(self):
        gneca.nastavi_odpiralnik(None)

    def test_oznaka_krajevnega_konca(self):
        """Oddaja na krajevni konec Global Linka (127.x) nese oznako po izvornih vratih - porabi se enkrat."""
        streznik = socket.create_server(("127.0.0.1", 0))
        try:
            gneca.nastavi_odpiralnik(lambda h, p, r: None)
            c = gneca.odpri_oddajo(("127.0.0.1", streznik.getsockname()[1]), 2.0)
            t, naslov = streznik.accept()
            self.assertEqual(naslov[1], c.getsockname()[1])
            self.assertTrue(gneca.vzemi_oddajo(naslov[1]))
            self.assertFalse(gneca.vzemi_oddajo(naslov[1]), "oznaka se porabi")
            c.close()
            t.close()
            gneca.nastavi_odpiralnik(None)
            c = gneca.odpri_oddajo(("127.0.0.1", streznik.getsockname()[1]), 2.0)
            t, naslov = streznik.accept()
            self.assertFalse(gneca.vzemi_oddajo(naslov[1]), "brez vklopljene pomoci ni oznak")
            c.close()
            t.close()
        finally:
            streznik.close()

    def test_oznaka_potece(self):
        gneca.oznaci_oddajo(4242)
        with mock.patch.object(gneca.time, "monotonic", return_value=time.monotonic() + gneca.OZNAKA_ODDAJE_S + 1):
            self.assertFalse(gneca.vzemi_oddajo(4242))

    def test_cilj_v_internetu_skozi_odpiralnik(self):
        a, b = socket.socketpair()
        klici = []
        gneca.nastavi_odpiralnik(lambda h, p, r: klici.append((h, p)) or a)
        try:
            self.assertIs(gneca.odpri_oddajo(("hub.example.net", 8443), 5.0), a)
            self.assertEqual(klici, [("hub.example.net", 8443)])
            # Domace omrezje nikoli skozi telefon (odpiralnika sploh ne vprasamo).
            self.assertIsNone(gneca.tcp_za_oddajo("192.168.1.10", 8443, 1.0))
            self.assertIsNone(gneca.tcp_za_oddajo("tiskalnik", 80, 1.0))
            self.assertEqual(len(klici), 1)
        finally:
            a.close()
            b.close()

    def test_brez_gnece_neposredno(self):
        gneca.nastavi_odpiralnik(lambda h, p, r: None)
        neposredno = object()
        with mock.patch.object(gneca.socket, "create_connection", return_value=neposredno) as cc:
            self.assertIs(gneca.odpri_oddajo(("hub.example.net", 8443), 5.0), neposredno)
            self.assertIs(gneca.odpri_tcp_za_oddajo("hub.example.net", 8443, 5.0), neposredno)
        self.assertEqual(cc.call_count, 2)

    def test_napaka_odpiralnika_je_tiha(self):
        def pade(h, p, r):
            raise RuntimeError("telefon")
        gneca.nastavi_odpiralnik(pade)
        self.assertIsNone(gneca.tcp_za_oddajo("hub.example.net", 8443, 1.0))


class PotiOddaj(unittest.TestCase):
    """Velika oddaja gre ob gneci skozi telefon tudi takrat, ko jo nese krajevni konec releja ali neposredne poti."""

    def tearDown(self):
        gneca.nastavi_odpiralnik(None)

    def test_posiljanje_datoteke_uporabi_odpiralnik_oddaj(self):
        from core import link_deljenje
        videno = {}

        class Povezava:
            def __init__(self, *a, **kw):
                videno.update(kw)

            def putrequest(self, *a):
                raise OSError("konec preizkusa")

            def close(self):
                pass

        with mock.patch.object(link_deljenje.link_tls, "_PripetaHttps", Povezava):
            try:
                link_deljenje._oddaja("127.0.0.1", 1, "", "z", "/cast/file", __file__, 1, "", 0, False, lambda _p: None)
            except OSError:
                pass
        self.assertIs(videno.get("odpri"), gneca.odpri_oddajo)

    def test_pripeta_https_odpre_z_odpiralnikom(self):
        from core import link_tls
        klici = []

        def odpri(naslov, rok):
            klici.append((naslov, rok))
            raise OSError("ni povezave")
        p = link_tls._PripetaHttps("hub.example.net", 8443, None, 7.0, odpri=odpri)
        with self.assertRaises(OSError):
            p.connect()
        self.assertEqual(klici, [(("hub.example.net", 8443), 7.0)])

    def test_rele_oddaja_skozi_telefon(self):
        from core import link_rele
        tls = object()
        with mock.patch.object(link_rele, "_tls_za_oddajo", return_value=tls) as za_oddajo, \
                mock.patch.object(link_rele, "WsOdjemalec", side_effect=lambda pot, glave, **kw: ("ws", kw.get("tls"))):
            self.assertEqual(link_rele.odpri_kanal("/v1/connect", lambda: {}, oddaja=True), ("ws", tls))
            self.assertEqual(za_oddajo.call_count, 1)
            topla = mock.Mock()
            topla.vzemi.return_value = None
            self.assertEqual(link_rele.odpri_kanal("/v1/connect", lambda: {}, topla), ("ws", None))
            self.assertEqual(za_oddajo.call_count, 1, "obicajen kanal ne sprasuje telefona")

    def test_rele_brez_gnece_po_topli(self):
        from core import link_rele
        topla = mock.Mock()
        topla.vzemi.return_value = "topla"
        with mock.patch.object(link_rele, "_tls_za_oddajo", return_value=None), \
                mock.patch.object(link_rele, "WsOdjemalec", side_effect=lambda pot, glave, **kw: kw.get("tls")):
            self.assertEqual(link_rele.odpri_kanal("/v1/connect", lambda: {}, topla, oddaja=True), "topla")

    def test_tls_za_oddajo_brez_gnece(self):
        from core import link_rele
        self.assertIsNone(link_rele._tls_za_oddajo())

    def test_krajevni_rele_prepozna_oddajo(self):
        from core import link_rele
        rele = link_rele.LokalniRele("n-cilj", kljuc=lambda: "k", podpisi=lambda _b: "p")
        kanali = []
        dogodek = threading.Event()

        def kanal(tcp, oddaja=False):
            kanali.append(oddaja)
            tcp.close()
            dogodek.set()
        rele._kanal = kanal
        try:
            gneca.nastavi_odpiralnik(lambda h, p, r: None)
            gneca.odpri_oddajo(("127.0.0.1", rele.vrata), 2.0).close()
            self.assertTrue(dogodek.wait(3))
            dogodek.clear()
            socket.create_connection(("127.0.0.1", rele.vrata), 2.0).close()
            self.assertTrue(dogodek.wait(3))
        finally:
            rele.zapri()
        self.assertEqual(kanali, [True, False])

    def test_neposredna_pot_z_odpiralnikom(self):
        from core import link_neposredno
        klici = []

        def odpri(ip, vrata, rok):
            klici.append((ip, vrata))
            raise OSError("ni")
        with self.assertRaises(link_neposredno.NapakaNeposredne):
            link_neposredno.odpri_neposredno("203.0.113.5", 4443, "n-" + "a" * 16, "k", "n-" + "b" * 16,
                                             lambda _b: b"", odpri=odpri)
        self.assertEqual(klici, [("203.0.113.5", 4443)])


if __name__ == "__main__":
    unittest.main()
