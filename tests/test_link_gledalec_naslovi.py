"""Oddaljeni zaslon: gledalec napravo isce na vec naslovih (docs/LINK-MESH.md, pravilo 8).

Naslov naprave v seznamu Safeer Linka pripise sredisce. V krogu 106 je bil ta naslov za napravo, pripeto na
sredisce druge naprave, 127.0.0.1 - zaslon se ni odprl, ceprav je bil racunalnik v istem omrezju. Zato racunalnik
v odgovoru na `screen.start` sam nasteje svoje naslove (`hosts`), gledalec pa jih poskusi za naslovom iz seznama.

Varnost ostane pri odtisu potrdila in enkratnem zetonu: zeton gre na pot sele po tem, ko se odtis ujema.
"""
import json
import shutil
import socket
import ssl
import struct
import tempfile
import threading
import time
import unittest
from unittest import mock

from core import link_daljinec, link_datoteke, link_gledalec
from core.link_gledalec import NapakaGledalca, kandidati_naslovov, razcleni_odgovor

ODTIS = "ab" * 32


class Kandidati(unittest.TestCase):
    def test_najprej_naslov_iz_seznama_nato_nasteti(self):
        self.assertEqual(kandidati_naslovov("192.168.0.220", ["192.168.0.220", "10.0.0.7"]),
                         ["192.168.0.220", "10.0.0.7"])

    def test_brez_nastetih_ostane_samo_naslov_iz_seznama(self):
        for hosts in (None, [], "192.168.0.9", {"a": 1}, 7):
            self.assertEqual(kandidati_naslovov("192.168.0.220", hosts), ["192.168.0.220"], hosts)

    def test_brez_naslova_iz_seznama_veljajo_nasteti(self):
        self.assertEqual(kandidati_naslovov("", ["192.168.0.135"]), ["192.168.0.135"])
        self.assertEqual(kandidati_naslovov(None, None), [])
        self.assertEqual(kandidati_naslovov("  ", ["  "]), [])

    def test_nasteti_naslovi_morajo_biti_stevilcni_in_dosegljivi_od_drugod(self):
        slabi = ["127.0.0.1", "127.8.9.1", "0.0.0.0", "0.1.2.3", "224.0.0.251", "240.0.0.1", "255.255.255.255",
                 "::", "::1", "ff02::1", "fe80::1", "2001:db8::5", "::ffff:192.168.0.6",
                 "racunalnik.local", "192.168.0.300", "192.168.01.5", "1.2.3", "1.2.3.4.5", "192.168.0.-5",
                 "\u0661\u0669\u0662.168.0.5", "192.168.0.5:8080", "http://192.168.0.5", "", None, 5,
                 ["192.168.0.5"], "192.168.0.5 "]
        # Zadnji ("192.168.0.5 ") je veljaven po obrezu - edini, ki ostane.
        self.assertEqual(kandidati_naslovov("192.168.0.220", slabi), ["192.168.0.220", "192.168.0.5"])

    def test_naslov_brez_dhcp_velja(self):
        self.assertEqual(kandidati_naslovov("", ["169.254.10.20", "100.64.0.7", "223.255.255.254"]),
                         ["169.254.10.20", "100.64.0.7", "223.255.255.254"])

    def test_najvec_stirje(self):
        hosts = ["10.0.0.%d" % i for i in range(1, 20)]
        self.assertEqual(kandidati_naslovov("192.168.0.220", hosts),
                         ["192.168.0.220", "10.0.0.1", "10.0.0.2", "10.0.0.3"])
        self.assertEqual(len(kandidati_naslovov("", hosts)), link_gledalec.NAJVEC_KANDIDATOV)

    def test_odgovor_ohrani_nastete_naslove(self):
        seja = razcleni_odgovor({"ok": True, "data": {"port": 4321, "fp": ODTIS, "token": "enkraten",
                                                      "hosts": ["192.168.0.135"]}})
        self.assertEqual(seja["hosts"], ["192.168.0.135"])
        g = link_gledalec.Gledalec("192.168.0.220", seja)
        self.assertEqual(g.kandidati, ["192.168.0.220", "192.168.0.135"])
        self.assertEqual(g.naslov, "192.168.0.220")

    def test_star_racunalnik_brez_nastetih_naslovov(self):
        g = link_gledalec.Gledalec("192.168.0.220", {"ok": True, "port": 4321, "fp": ODTIS, "token": "enkraten"})
        self.assertEqual(g.kandidati, ["192.168.0.220"])

    def test_brez_vsakega_naslova_je_napaka_razumljiva(self):
        g = link_gledalec.Gledalec("", {"ok": True, "port": 4321, "fp": ODTIS, "token": "enkraten",
                                        "hosts": ["127.0.0.1"]})
        with self.assertRaises(NapakaGledalca):
            g.povezi()


class _Zaslon:
    """Deljenje zaslona, kot ga vidi link_daljinec: dovoljeno, mozno, seja z vrati, odtisom in zetonom."""

    def na_voljo(self):
        return {"dovoljeno": True, "mozno": True}

    def zacni(self, posiljatelj, kakovost, cilj):
        return {"port": 40123, "fp": ODTIS, "token": "zeton-zeton-zeton", "v": 2, "screen": cilj or "desktop"}


class OdgovorRacunalnika(unittest.TestCase):
    def _start(self):
        izidi = []
        link_daljinec.izvedi_control("screen.start", {"quality": "srednja", "screen": "desktop"}, lambda _u: None,
                                     izidi.append, posiljatelj="telefon", hub_url="wss://127.0.0.1:8990/cast/ws",
                                     zaslon=_Zaslon())
        self.assertEqual(len(izidi), 1)
        return izidi[0]

    def test_screen_start_nasteje_naslove(self):
        with mock.patch("core.link_zvok.lastni_naslovi", return_value=["192.168.0.135", "10.8.0.2"]) as klic:
            izid = self._start()
        self.assertTrue(izid["ok"], izid)
        self.assertEqual(izid["data"]["hosts"], ["192.168.0.135", "10.8.0.2"])
        self.assertEqual(klic.call_args[0][0], "wss://127.0.0.1:8990/cast/ws")
        # Vse, kar je seja imela prej, ostane.
        self.assertEqual((izid["data"]["port"], izid["data"]["fp"], izid["data"]["token"]),
                         (40123, ODTIS, "zeton-zeton-zeton"))

    def test_najvec_stirje_naslovi(self):
        with mock.patch("core.link_zvok.lastni_naslovi", return_value=["10.0.0.%d" % i for i in range(1, 9)]):
            izid = self._start()
        self.assertEqual(izid["data"]["hosts"], ["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4"])

    def test_napaka_pri_naslovih_seje_ne_podre(self):
        with mock.patch("core.link_zvok.lastni_naslovi", side_effect=OSError("ni omrezja")):
            izid = self._start()
        self.assertTrue(izid["ok"], izid)
        self.assertEqual(izid["data"]["hosts"], [])
        self.assertEqual(izid["data"]["port"], 40123)

    def test_pravi_naslovi_niso_zanka(self):
        izid = self._start()
        self.assertIsInstance(izid["data"]["hosts"], list)
        for naslov in izid["data"]["hosts"]:
            self.assertFalse(naslov.startswith("127."), naslov)
            self.assertEqual(kandidati_naslovov("", [naslov]), [naslov])


class _Naprava:
    """Naprava, ki deli zaslon, na enem naslovu zanke: po pozdravu poslje glavo in en okvir, nato molci."""

    def __init__(self, mapa: str, naslov: str, vrata: int = 0) -> None:
        kljuc, potrdilo, self.odtis = link_datoteke.zagotovi_potrdilo(mapa)
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(potrdilo, kljuc)
        self.posluh = socket.socket()
        self.posluh.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.posluh.bind((naslov, vrata))
        self.posluh.listen(4)
        self.vrata = self.posluh.getsockname()[1]
        self.pozdravi = []
        self.povezav = 0
        self.konec = threading.Event()
        self.nit = threading.Thread(target=self._teci, daemon=True)
        self.nit.start()

    def _teci(self) -> None:
        while not self.konec.is_set():
            try:
                surov, _ = self.posluh.accept()
            except OSError:
                return
            self.povezav += 1
            # Vsaka povezava svojo nit: naslednji gledalec ne caka, da prejsnji konca.
            threading.Thread(target=self._streci, args=(surov,), daemon=True).start()

    def _streci(self, surov) -> None:
        try:
            surov.settimeout(5)
            s = self.ctx.wrap_socket(surov, server_side=True)
            vrstica = b""
            while not vrstica.endswith(b"\n"):
                znak = s.recv(1)
                if not znak:
                    break
                vrstica += znak
            if vrstica:
                self.pozdravi.append(vrstica.decode("utf-8", "replace").strip())
                s.sendall((json.dumps({"v": 2, "w": 1280, "h": 720, "fps": 30}) + "\n").encode())
                s.sendall(bytes([1]) + struct.pack(">I", 4) + b"h264")
                self.konec.wait(6)
            s.close()
        except (OSError, ssl.SSLError):
            try:
                surov.close()
            except OSError:
                pass

    def zapri(self) -> None:
        self.konec.set()
        # Samo close() niti, ki caka v accept(), na Linuxu ne zbudi - shutdown jo.
        for zapri in (lambda: self.posluh.shutdown(socket.SHUT_RDWR), self.posluh.close):
            try:
                zapri()
            except OSError:
                pass
        self.nit.join(5)


class VecNaslovov(unittest.TestCase):
    def setUp(self):
        self.mape = []
        self.naprave = []

    def tearDown(self):
        for n in self.naprave:
            n.zapri()
        for m in self.mape:
            shutil.rmtree(m, ignore_errors=True)

    def _naprava(self, naslov: str, vrata: int = 0) -> _Naprava:
        mapa = tempfile.mkdtemp(prefix="safeer-gledalec-")
        self.mape.append(mapa)
        try:
            n = _Naprava(mapa, naslov, vrata)
        except Exception as e:  # noqa: BLE001 - brez orodja za potrdilo ali drugega naslova zanke preizkusa ni
            self.skipTest("naprave za preizkus ni mogoce pripraviti: %s" % e)
        self.naprave.append(n)
        return n

    def _gledalec(self, naprava: _Naprava, kandidati, cas: float = 8.0) -> link_gledalec.Gledalec:
        g = link_gledalec.Gledalec("", {"ok": True, "port": naprava.vrata, "token": "zeton", "fp": naprava.odtis},
                                   cas_povezave=cas)
        # Naslovi zanke v odgovoru naprave niso dovoljeni; preizkus jih zato nastavi neposredno.
        g.kandidati = list(kandidati)
        return g

    def test_prvi_naslov_mrtev_drugi_dela(self):
        naprava = self._naprava("127.0.0.1")
        g = self._gledalec(naprava, ["127.0.0.2", "127.0.0.1"])
        zacetek = time.monotonic()
        glava = g.povezi()
        self.assertEqual((glava.sirina, glava.visina), (1280, 720))
        self.assertEqual(g.naslov, "127.0.0.1")
        self.assertLess(time.monotonic() - zacetek, 3.0)
        self.assertEqual(next(g.okvirji()), (1, b"h264"))
        g.zapri()
        self.assertEqual(naprava.pozdravi, ["SAFEER-ZASLON zeton"])

    def test_na_prvem_naslovu_druga_naprava_zetona_ne_dobi(self):
        prava = self._naprava("127.0.0.1")
        tuja = self._naprava("127.0.0.2", prava.vrata)
        self.assertNotEqual(prava.odtis, tuja.odtis)
        g = self._gledalec(prava, ["127.0.0.2", "127.0.0.1"])
        g.povezi()
        self.assertEqual(g.naslov, "127.0.0.1")
        g.zapri()
        time.sleep(0.2)
        self.assertEqual(tuja.povezav, 1, "gledalec mora tujo napravo najprej poskusiti")
        self.assertEqual(tuja.pozdravi, [], "zeton ne sme do naprave z drugim potrdilom")
        self.assertEqual(prava.pozdravi, ["SAFEER-ZASLON zeton"])

    def test_samo_druga_naprava_napaka_o_odtisu(self):
        prava = self._naprava("127.0.0.1")
        tuja = self._naprava("127.0.0.2")
        g = link_gledalec.Gledalec("127.0.0.2", {"ok": True, "port": tuja.vrata, "token": "zeton",
                                                 "fp": prava.odtis})
        with self.assertRaisesRegex(NapakaGledalca, "Odtis"):
            g.povezi()
        time.sleep(0.2)
        self.assertEqual(tuja.pozdravi, [])

    def test_noben_naslov_ne_dela_razumljiv_stavek(self):
        naprava = self._naprava("127.0.0.1")
        g = self._gledalec(naprava, ["127.0.0.2", "127.0.0.3"])
        with self.assertRaisesRegex(NapakaGledalca, "ni bilo mogoče doseči"):
            g.povezi()
        self.assertIsNone(g.vticnica)
        self.assertEqual(naprava.povezav, 0)

    def test_po_povezavi_velja_cas_cele_seje(self):
        # Krajsi cas enega poskusa ne sme ostati na povezavi: seja bi se ob kratki tisini sama koncala.
        naprava = self._naprava("127.0.0.1")
        with mock.patch.object(link_gledalec, "CAS_KANDIDATA_S", 0.3):
            g = self._gledalec(naprava, ["127.0.0.2", "127.0.0.1"], cas=1.5)
            g.povezi()
        okvirji = g.okvirji()
        self.assertEqual(next(okvirji), (1, b"h264"))
        zacetek = time.monotonic()
        with self.assertRaisesRegex(NapakaGledalca, "ne odziva"):
            next(okvirji)                       # naprava molci
        self.assertGreater(time.monotonic() - zacetek, 1.2)
        g.zapri()

    def test_en_sam_naslov_dobi_ves_cas(self):
        naprava = self._naprava("127.0.0.1")
        klici = []
        pravi = socket.create_connection

        def belezi(cilj, cas=None, *a, **k):
            klici.append((cilj[0], cas))
            return pravi(cilj, cas, *a, **k)

        with mock.patch.object(link_gledalec.socket, "create_connection", belezi):
            g = self._gledalec(naprava, ["127.0.0.1"])
            g.povezi()
            g.zapri()
            g2 = self._gledalec(naprava, ["127.0.0.2", "127.0.0.1"])
            g2.povezi()
            g2.zapri()
        self.assertEqual(klici[0], ("127.0.0.1", 8.0))
        self.assertEqual(klici[1:], [("127.0.0.2", link_gledalec.CAS_KANDIDATA_S),
                                     ("127.0.0.1", link_gledalec.CAS_KANDIDATA_S)])


if __name__ == "__main__":
    unittest.main()
