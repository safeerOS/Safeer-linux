"""Scit za Safeer OS na Linuxu: razresevalnik DNS, nabor domen, seznami (brez omrezja in brez resolvectl)."""
import os
import socket
import struct
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_scit  # noqa: E402


def vprasanje(ime: str, id_: int = 0x1234, vrsta: int = 1) -> bytes:
    telo = b"".join(struct.pack("B", len(d)) + d.encode() for d in ime.split(".")) + b"\x00"
    return struct.pack("!HHHHHH", id_, 0x0100, 1, 0, 0, 0) + telo + struct.pack("!HH", vrsta, 1)


class Paketi(unittest.TestCase):
    def test_ime_poizvedbe(self):
        self.assertEqual(os_scit.ime_poizvedbe(vprasanje("Ads.Example.COM")), "ads.example.com")
        self.assertEqual(os_scit.ime_poizvedbe(b"\x00" * 10), "")
        odgovor = bytearray(vprasanje("a.si"))
        odgovor[2] |= 0x80
        self.assertEqual(os_scit.ime_poizvedbe(bytes(odgovor)), "")

    def test_odgovor_zavrnjeno(self):
        p = vprasanje("bad.example", id_=0xBEEF)
        o = os_scit.odgovor_zavrnjeno(p)
        self.assertEqual(o[:2], b"\xbe\xef")
        zastavice, vprasanj, odgovorov = struct.unpack("!HHH", o[2:8])
        self.assertEqual(zastavice & 0x8000, 0x8000)   # odgovor
        self.assertEqual(zastavice & 0x000F, 3)        # NXDOMAIN
        self.assertEqual((vprasanj, odgovorov), (1, 0))
        self.assertEqual(o[12:], p[12:])               # vprasanje ponovljeno v celoti
        self.assertEqual(os_scit.ime_poizvedbe(bytes([o[0], o[1], 0x01]) + o[3:]), "bad.example")


class NaborDomen(unittest.TestCase):
    def test_razcleni_seznam(self):
        besedilo = "# komentar\n0.0.0.0 ads.example.com\n127.0.0.1 localhost\nplain.example\n" \
                   "phish.example.si CNAME .\n*.wild.example\n! easylist\n||ne.sme.com^\nlocalhost\n"
        self.assertEqual(list(os_scit.razcleni_seznam(besedilo)),
                         ["ads.example.com", "plain.example", "phish.example.si", "wild.example"])

    def test_nabor_poddomene_in_kategorija(self):
        n = os_scit.Nabor.iz_domen([("ads.example.com", "oglasi"), ("bad.example", "malware"),
                                    ("bad.example", "oglasi")])
        self.assertEqual(n.kategorija("ads.example.com"), "oglasi")
        self.assertEqual(n.kategorija("cdn.ads.example.com"), "oglasi")
        self.assertIsNone(n.kategorija("example.com"))
        self.assertEqual(n.kategorija("x.bad.example"), "malware")   # nevarnejsa kategorija prevlada
        self.assertIsNone(n.kategorija("safe.example"))

    def test_nabor_shrani_nalozi(self):
        n = os_scit.Nabor.iz_domen([("a.example", "phishing"), ("b.example", "groznje")])
        with tempfile.TemporaryDirectory() as m:
            pot = os.path.join(m, "domene.bin")
            n.shrani(pot)
            n2 = os_scit.Nabor.nalozi(pot)
            self.assertEqual(len(n2), 2)
            self.assertEqual(n2.kategorija("www.a.example"), "phishing")
            self.assertEqual(n2.kategorija("b.example"), "groznje")
            with open(pot, "wb") as f:
                f.write(b"smeti")
            self.assertIsNone(os_scit.Nabor.nalozi(pot))


KLJUC_PREIZKUS = "a1b2c3d4e5f6a7b8c9d0e1f2"


class SeznamiTest(unittest.TestCase):
    def test_kljuc_abusech(self):
        """Lastnik 9. 11. 2026: URLhaus samo s kljucem uporabnika; brez kljuca ni prenosa in ni napake."""
        self.assertTrue(os_scit.veljaven_kljuc(KLJUC_PREIZKUS))
        self.assertFalse(os_scit.veljaven_kljuc("abc/../x?y=1&z=2aaaaaaaaaaaa"))
        self.assertFalse(os_scit.veljaven_kljuc("kratek"))
        self.assertEqual(os_scit.ocisti_kljuc(' "a1b2 c3d4\u200b\n" '), "a1b2c3d4")
        klici = []

        def prenesi(url, etag, cas=60.0):
            klici.append(url)
            raise OSError("ni omrezja")
        with tempfile.TemporaryDirectory() as m:
            s = os_scit.Seznami(m, prenesi_fn=prenesi, kljuc_fn=lambda: None)
            s.osvezi()
            self.assertFalse(any("urlhaus" in u for u in klici))
            self.assertNotIn("urlhaus", s.napaka)
            klici.clear()
            s.kljuc_fn = lambda: KLJUC_PREIZKUS
            s.osvezi()
            self.assertIn("https://urlhaus-api.abuse.ch/v2/files/exports/%s/hostfile.txt" % KLJUC_PREIZKUS, klici)

    def test_osvezi_iz_lokalnih_prenosov(self):
        vsebine = {
            "hagezi-pro": "\n".join("ad%d.example" % i for i in range(1200)),
            "hagezi-tif": "\n".join("t%d.example" % i for i in range(1100)),
            "hagezi-fake": "\n".join("f%d.example" % i for i in range(1050)),
            # Glava StevenBlack (privzeti seznam Pi-hole): lokalna imena in naslovi ne gredo v nabor.
            "stevenblack": "# Title: StevenBlack/hosts\n127.0.0.1 localhost\n127.0.0.1 localhost.localdomain\n127.0.0.1 local\n"
                           "255.255.255.255 broadcasthost\n::1 localhost\nfe80::1%lo0 localhost\n" +
                           "\n".join("0.0.0.0 sb%d.example" % i for i in range(1000)),
            "adguard-dns": "! Title: AdGuard DNS filter\n" + "\n".join("||ag%d.example^" % i for i in range(1001)) +
                           "\n@@||ok.ag5.example^|\n",
            "urlhaus": "# urlhaus\n127.0.0.1 mal.example\n",
            "phishing-army": "phish.example\n",
            "si-cert": "cert.example CNAME .\n",
        }
        # Zastrupljen seznam OGLASOV (npr. prek CDN-ja) bi zaprl posodobitve - te ostanejo odprte. Seznam grozenj jih
        # ustavi (4. 11. 2026, en Scit z Androidom; tests/skupni-primeri/scit-pravila.json).
        vsebine["hagezi-pro"] += "\narchive.ubuntu.com\ngithub.com\npackages.linuxmint.com\n"
        klici = []

        def prenesi(url, etag, cas=60.0):
            oznaka = [o for o, u, _k in os_scit.VIRI if u.replace("{KLJUC}", KLJUC_PREIZKUS) == url][0]
            klici.append((oznaka, etag))
            if etag == "e-" + oznaka:
                return 304, b"", etag
            return 200, vsebine[oznaka].encode(), "e-" + oznaka

        with tempfile.TemporaryDirectory() as m:
            s = os_scit.Seznami(m, prenesi_fn=prenesi, kljuc_fn=lambda: KLJUC_PREIZKUS)
            self.assertTrue(s.osvezi())
            self.assertEqual(len(s.nabor), 1200 + 3 + 1100 + 1050 + 1000 + 1000 + 3)
            self.assertEqual(s.kategorija("x.ag7.example"), "oglasi")
            self.assertIsNone(s.kategorija("ag5.example"))
            self.assertEqual(s.kategorija("x.sb7.example"), "oglasi")
            self.assertIsNone(s.kategorija("localhost.localdomain"))
            self.assertEqual(s.kategorija("ad7.example"), "oglasi")
            self.assertEqual(s.kategorija("x.mal.example"), "malware")
            self.assertEqual(s.kategorija("cert.example"), "phishing")
            self.assertIsNone(s.kategorija("printer.local"))
            self.assertIsNone(s.kategorija("safeer.si"))
            self.assertIsNone(s.kategorija("ad7.example.safeer.si"))
            for ime in ("archive.ubuntu.com", "si.archive.ubuntu.com", "github.com", "packages.linuxmint.com"):
                self.assertIsNone(s.kategorija(ime), ime)
            # Seznam grozenj zascitenega gostitelja ustavi (prevzeto zrcalo ali stran), oglasi ne.
            s.nabor = os_scit.Nabor.iz_domen([("github.com", "phishing"), ("archive.ubuntu.com", "oglasi")])
            self.assertEqual(s.kategorija("objects.github.com"), "phishing")
            self.assertIsNone(s.kategorija("archive.ubuntu.com"))
            s.nabor = os_scit.Nabor.nalozi(os.path.join(m, "domene.bin"))
            # Drugi zagon iz iste mape: nabor je na disku, brez prenosa; osvezitev vrne 304 in nic ne prezida.
            s2 = os_scit.Seznami(m, prenesi_fn=prenesi, kljuc_fn=lambda: KLJUC_PREIZKUS)
            self.assertEqual(len(s2.nabor), len(s.nabor))
            self.assertTrue(s2.osvezi())
            self.assertEqual(klici[-1][1], "e-si-cert")
            self.assertEqual(s2.stanje()["seznami"]["urlhaus"], 1)

    def test_preusmeritev_na_drug_streznik_ni_sprejeta(self):
        from core.signed_feed import isti_gostitelj
        self.assertTrue(isti_gostitelj("https://cdn.jsdelivr.net/gh/a", "https://cdn.jsdelivr.net/gh/b"))
        self.assertFalse(isti_gostitelj("https://cdn.jsdelivr.net/gh/a", "https://zlo.example/a"))
        self.assertFalse(isti_gostitelj("https://phishing.army/x", "https://phishing.army.zlo.example/x"))

    def test_napaka_prenosa_ohrani_nabor(self):
        def prenesi(url, etag, cas=60.0):
            raise OSError("ni omrezja")
        with tempfile.TemporaryDirectory() as m:
            s = os_scit.Seznami(m, prenesi_fn=prenesi)
            self.assertFalse(s.osvezi())
            self.assertIn("hagezi-pro: OSError", s.napaka)
            self.assertEqual(len(s.nabor), 0)


class LazniUpstream:
    """Streznik DNS na 127.0.0.1, ki na vsako vprasanje vrne odgovor z istim id in zastavico odgovora."""

    def __init__(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind(("127.0.0.1", 0))
        self.vrata = self.s.getsockname()[1]
        self.prejeto = []
        threading.Thread(target=self._tek, daemon=True).start()

    def _tek(self):
        while True:
            try:
                p, od = self.s.recvfrom(4096)
            except OSError:
                return
            self.prejeto.append(os_scit.ime_poizvedbe(p))
            self.s.sendto(p[:2] + b"\x81\x80" + p[4:], od)

    def zapri(self):
        self.s.close()


class RazresevalnikTest(unittest.TestCase):
    def test_zavrne_in_posreduje(self):
        gor = LazniUpstream()
        r = os_scit.Razresevalnik(lambda ime: "oglasi" if ime.endswith("ads.example") else None, lambda: ["127.0.0.1"])
        # Upstream na drugih vratih: posredovanje preusmerimo na lazni streznik.
        izvirni = r._posreduj

        def posreduj(paket, tcp):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.sendto(paket, ("127.0.0.1", gor.vrata))
            o, _ = s.recvfrom(4096)
            s.close()
            return o
        r._posreduj = posreduj
        vrata = r.zazeni()
        self.assertIn(vrata, os_scit.VRATA)
        try:
            k = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            k.settimeout(3)
            k.sendto(vprasanje("x.ads.example", id_=7), (os_scit.NASLOV, vrata))
            o, _ = k.recvfrom(4096)
            self.assertEqual(o[:2], b"\x00\x07")
            self.assertEqual(struct.unpack("!H", o[2:4])[0] & 0xF, 3)
            k.sendto(vprasanje("safeer.si", id_=8), (os_scit.NASLOV, vrata))
            o, _ = k.recvfrom(4096)
            self.assertEqual(o[:2], b"\x00\x08")
            self.assertEqual(o[2:4], b"\x81\x80")
            self.assertEqual(gor.prejeto, ["safeer.si"])
            # TCP: dolzina + paket.
            with socket.create_connection((os_scit.NASLOV, vrata), timeout=3) as t:
                p = vprasanje("y.ads.example", id_=9)
                t.sendall(struct.pack("!H", len(p)) + p)
                n = struct.unpack("!H", t.recv(2))[0]
                o = t.recv(n)
            self.assertEqual(o[:2], b"\x00\x09")
            self.assertEqual(r.blokiranih, 2)
            self.assertEqual(r.poizvedb, 3)
            self.assertEqual([z["ime"] for z in r.zadnje], ["y.ads.example", "x.ads.example"])
            k.close()
        finally:
            izvirni  # noqa: B018 - le da ostane sklic
            r.ustavi()
            gor.zapri()
        self.assertEqual(r.vrata, 0)


class UsmeriTest(unittest.TestCase):
    def test_rezerva_za_docker(self):
        """resolvectl dobi nas razresevalnik PRVI in streznike usmerjevalnika kot rezervo: brez njih bi
        /run/systemd/resolve/resolv.conf ostal brez uporabnega streznika (Docker izpusti loopback).

        V dveh korakih - najprej samo nas: systemd-resolved obdrzi streznik, ki ga trenutno uporablja, ce je ta tudi
        na novem seznamu, in bi v enem koraku ostal pri usmerjevalniku (Scit ne bi dobil nobene poizvedbe).
        Iskalnih domen se ne dotikamo (»~.« je prej izrinil domeno iz DHCP in kratka domaca imena niso delala)."""
        klici = []

        def zazeni(ukaz, cas=8.0):
            klici.append(ukaz)
            return 0, ""
        izvirni = os_scit._zazeni
        os_scit._zazeni = zazeni
        izvirna_pot = os_scit._rootova_pot
        os_scit._rootova_pot = lambda pot: False    # brez odvisnosti od gostitelja (pomocnik root)
        try:
            self.assertEqual(os_scit.usmeri("eth9", 5354, ["192.0.2.1", "1.1.1.1"]), "")
            self.assertEqual(klici, [["resolvectl", "dns", "eth9", "127.0.0.1:5354"],
                                     ["resolvectl", "dns", "eth9", "127.0.0.1:5354", "192.0.2.1", "1.1.1.1"]])
            del klici[:]
            self.assertEqual(os_scit.usmeri("eth9", 5355, []), "")
            self.assertEqual(klici, [["resolvectl", "dns", "eth9", "127.0.0.1:5355"]])
            # Prvi korak ne uspe (ni dovoljenja): drugega ni.
            del klici[:]
            os_scit._zazeni = lambda ukaz, cas=8.0: (klici.append(ukaz), (1, ""))[1]
            self.assertEqual(os_scit.usmeri("eth9", 5354, ["192.0.2.1"]), "pravilo")
            self.assertEqual(len(klici), 1)
            # Drugi korak (rezerva) pade: ne uspeh, ampak BREZ_REZERVE (pregled 4. 11. 2026 - prej tiho uspeh).
            del klici[:]
            os_scit._zazeni = lambda ukaz, cas=8.0: (klici.append(ukaz), (0, "") if len(klici) == 1 else (1, ""))[1]
            self.assertEqual(os_scit.usmeri("eth9", 5354, ["192.0.2.1"]), os_scit.BREZ_REZERVE)
            self.assertEqual(len(klici), 2)
        finally:
            os_scit._zazeni = izvirni
            os_scit._rootova_pot = izvirna_pot
        self.assertFalse([k for k in klici if "domain" in k or "revert" in k])

    def test_trenutni_streznik(self):
        izvirni = os_scit._zazeni
        os_scit._zazeni = lambda ukaz, cas=8.0: (0, "Link 2 (eth9)\n    Current DNS Server: 192.0.2.1\n       DNS Servers: 127.0.0.1:5354 192.0.2.1\n")
        try:
            self.assertEqual(os_scit.trenutni_streznik("eth9"), "192.0.2.1")
        finally:
            os_scit._zazeni = izvirni


class ScitTest(unittest.TestCase):
    def test_stanje_brez_sistema(self):
        class Shramba(dict):
            def get(self, k, d=None):
                return dict.get(self, k, d)

            def set(self, k, v):
                self[k] = v
        with tempfile.TemporaryDirectory() as m:
            sc = os_scit.Scit(Shramba(), mapa=m)
            st = sc.stanje()
            self.assertFalse(st["vklop"])
            self.assertFalse(st["tece"])
            self.assertEqual(st["blokiranih"], 0)
            self.assertIn("pravilo", st)
            # Izklop brez vklopa nic ne pokvari.
            self.assertFalse(sc.nastavi(False)["vklop"])

    def test_stanje_pulta_brez_podprocesov(self):
        """Pult bere stanje vsakih 15 s: razlog (systemctl, v Flatpaku cat na gostitelju) najvec vsakih RAZLOG_PULTA_S,
        pkcheck (pravilo) nikoli. Meritev 19. 10. 2026: prej 2-4 podprocesi na osvezitev."""
        class Shramba(dict):
            def get(self, k, d=None):
                return dict.get(self, k, d)

            def set(self, k, v):
                self[k] = v
        ura = [1000.0]
        with tempfile.TemporaryDirectory() as m, \
                mock.patch.object(os_scit, "razlog_nemoznosti", return_value="ni_resolved") as razlog, \
                mock.patch.object(os_scit, "pravilo_namesceno", side_effect=AssertionError("pult ne sme klicati pkcheck")), \
                mock.patch.object(os_scit.time, "monotonic", side_effect=lambda: ura[0]):
            sc = os_scit.Scit(Shramba(), mapa=m)
            self.assertFalse(sc.razlog_svez())
            st = sc.stanje_pulta()
            self.assertEqual((st["vklop"], st["mozno"], st["tece"], st["blokiranih"], st["premor"]), (False, False, False, 0, 0))
            self.assertTrue(sc.razlog_svez())
            for _ in range(10):
                ura[0] += 15
                sc.stanje_pulta()
            self.assertEqual(razlog.call_count, 1)
            ura[0] += sc.RAZLOG_PULTA_S
            self.assertFalse(sc.razlog_svez())
            razlog.return_value = ""
            self.assertFalse(sc.stanje_pulta(preveri=False)["mozno"])     # glavna nit: zadnji znani, brez podprocesa
            self.assertEqual(razlog.call_count, 1)
            self.assertTrue(sc.stanje_pulta()["mozno"])
            self.assertEqual(razlog.call_count, 2)


class IzjemeInPremor(unittest.TestCase):
    """Uporabnik dovoli domeno, ki je bila pravkar blokirana, ali da Ščit za nekaj minut na premor - namesto da ga
    izklopi v celoti."""

    class Shramba(dict):
        def get(self, k, d=None):
            return dict.get(self, k, d)

        def set(self, k, v):
            self[k] = v

    class Seznami:
        def kategorija(self, ime):
            if ime.endswith("lazna-banka.example"):
                return "phishing"
            return "oglasi" if ime.endswith("ads.example") or ime.endswith("dovoljena.example") else None

        def groznja(self, ime):
            return self.kategorija(ime) not in (None, "oglasi")

        def stanje(self):
            return {}

    def test_cista_domena(self):
        self.assertEqual(os_scit.cista_domena(" Primer.SI. "), "primer.si")
        self.assertEqual(os_scit.cista_domena("a_b.x-y.example"), "a_b.x-y.example")
        for slabo in ("", None, "localhost", "http://x.si", "x..si", "-a.si", "a-.si", "x.si/pot", "a b.si", "x." + "a" * 64 + ".si",
                      ".".join(["abc"] * 80)):
            self.assertEqual(os_scit.cista_domena(slabo), "", slabo)

    def test_izjeme(self):
        """Izjema velja NATANKO za to ime, 30 dni in nikoli za groznjo (4. 11. 2026, kot Android ScitPregled)."""
        with tempfile.TemporaryDirectory() as m:
            ura = [1_800_000_000.0]
            os_scit.Scit._ura = staticmethod(lambda: ura[0])
            self.addCleanup(setattr, os_scit.Scit, "_ura", staticmethod(os_scit.time.time))
            # Starejsa oblika (samo ime) dobi 30 dni od zdaj in se zapise na novo.
            shramba = self.Shramba({"scit_izjeme": ["Dovoljena.Example.", "ni domena", 5, "dovoljena.example"]})
            sc = os_scit.Scit(shramba, mapa=m)
            sc.seznami = self.Seznami()
            self.assertEqual(shramba["scit_izjeme"], [{"ime": "dovoljena.example", "do": int(ura[0]) + os_scit.IZJEMA_S}])
            self.assertEqual(sc.stanje()["izjeme"], ["dovoljena.example"])
            self.assertEqual(sc._kategorija("x.ads.example"), "oglasi")
            self.assertIsNone(sc._kategorija("dovoljena.example"))
            self.assertEqual(sc._kategorija("cdn.dovoljena.example"), "oglasi", "izjema ne velja za poddomene")
            self.assertEqual(sc._kategorija("nedovoljena.example"), "oglasi", "ne za ime, ki se samo konča enako")
            # Dovoliti je mogoče samo ime, ki je bilo pravkar blokirano - in nikoli groznje.
            sc.razresevalnik = os_scit.Razresevalnik(sc._kategorija, lambda: [])
            sc.razresevalnik.zadnje = [{"ime": "y.x.ads.example", "kategorija": "oglasi", "cas": 2.0},
                                       {"ime": "x.ads.example", "kategorija": "oglasi", "cas": 1.0},
                                       {"ime": "z.lazna-banka.example", "kategorija": "phishing", "cas": 0.5}]
            self.assertEqual(sc.dovoli("poljubna.example")["izjeme"], ["dovoljena.example"])
            self.assertEqual(sc.dovoli("ni domena")["izjeme"], ["dovoljena.example"])
            self.assertEqual(sc.dovoli("z.lazna-banka.example")["izjeme"], ["dovoljena.example"], "groznja: Nevarno")
            self.assertEqual(sc._kategorija("z.lazna-banka.example"), "phishing")
            st = sc.dovoli("X.ADS.example.")
            self.assertEqual(st["izjeme"], ["dovoljena.example", "x.ads.example"])
            self.assertEqual([z["ime"] for z in st["zadnje"]], ["y.x.ads.example", "z.lazna-banka.example"],
                             "s seznama gre samo dovoljeno ime")
            self.assertEqual(sc._kategorija("y.x.ads.example"), "oglasi")
            # Nov zagon prebere shranjene izjeme.
            self.assertEqual(os_scit.Scit(shramba, mapa=m).stanje()["izjeme"], ["dovoljena.example", "x.ads.example"])
            # Po 30 dneh izjema poteče.
            ura[0] += os_scit.IZJEMA_S
            self.assertEqual(sc._kategorija("x.ads.example"), "oglasi")
            self.assertEqual(sc.stanje()["izjeme"], [])
            ura[0] -= 1
            # »Blokiraj spet« izjemo odstrani.
            self.assertEqual(sc.dovoli("x.ads.example", False)["izjeme"], ["dovoljena.example"])
            self.assertEqual(sc._kategorija("x.ads.example"), "oglasi")

    def test_premor(self):
        with tempfile.TemporaryDirectory() as m:
            sc = os_scit.Scit(self.Shramba(), mapa=m)
            sc.seznami = self.Seznami()
            self.assertEqual(sc.stanje()["premor"], 0)
            st = sc.premor(15)
            self.assertTrue(890 < st["premor"] <= 901, st["premor"])
            self.assertIsNone(sc._kategorija("x.ads.example"), "med premorom oglasi in sledilci niso blokirani")
            self.assertEqual(sc._kategorija("prijava.lazna-banka.example"), "phishing", "nevarne strani ostanejo blokirane")
            sc._premor_do = time.monotonic() - 1                      # premor je potekel: Ščit nadaljuje sam
            self.assertEqual(sc._kategorija("x.ads.example"), "oglasi")
            self.assertEqual(sc.stanje()["premor"], 0)
            self.assertLessEqual(sc.premor(600)["premor"], os_scit.NAJDALJSI_PREMOR_MIN * 60 + 1, "največ ena ura")
            self.assertEqual(sc.premor(0)["premor"], 0)
            self.assertEqual(sc._kategorija("x.ads.example"), "oglasi")
            for slabo in ("x", None, -5):
                self.assertEqual(sc.premor(slabo)["premor"], 0)

    def test_most_in_stran(self):
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "safeer_os.py"), encoding="utf-8") as f:
            vir = f.read()
        self.assertIn('"scitDovoli": lambda: self._po_scitu(self.scit.dovoli(', vir)
        self.assertIn('"scitPremor": lambda: self._po_scitu(self.scit.premor(', vir)
        with open(os.path.join(koren, "assets", "os", "os.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn('klic("scitDovoli", [x.ime, true])', js)
        self.assertIn('klic("scitDovoli", [d, false])', js)
        self.assertIn('klic("scitPremor", [s.premor > 0 ? 0 : 15])', js)
        self.assertIn('if (x.kategorija === "oglasi") {', js)   # groznja: gumba Dovoli ni (4. 11. 2026)
        self.assertNotIn("scitDovoliRes", js)
        self.assertIn('s.naprejIzbran === false', js)          # prvi vklop: uporabnik izbere streznik naprej
        self.assertIn('klic("scitNaprej", ["router", ""])', js)
        with open(os.path.join(koren, "assets", "os", "besedila.js"), encoding="utf-8") as f:
            besedila = f.read()
        for kljuc in ("scitDovoli", "scitDovoljeno", "scitIzbiraNaslov", "scitIzbiraOpis", "scitIzbiraKrajevni", "scitIzbiraDrug", "scitIzjeme", "scitBlokirajSpet", "scitPremor", "scitNadaljuj", "scitPremorTece"):
            self.assertEqual(besedila.count(kljuc + ': "'), 6, "%s mora biti v vseh šestih jezikih" % kljuc)


class Zamenjave:
    """Zacasno zamenja funkcije modula os_scit (klici sistema) in jih na koncu vrne."""

    def __init__(self, **nove):
        # Preizkusi ne smejo biti odvisni od gostitelja: na racunalniku z namescenim paketom obstaja koren pomocnik
        # /usr/lib/safeer-os/scit-dns in koda izbere pkexec namesto resolvectl (17. 11. 2026: 3 preizkusi padli samo tam).
        self.nove = {"_rootova_pot": lambda pot: False, **nove}
        self.stare = {}

    def __enter__(self):
        for ime, f in self.nove.items():
            self.stare[ime] = getattr(os_scit, ime)
            setattr(os_scit, ime, f)
        return self

    def __exit__(self, *a):
        for ime, f in self.stare.items():
            setattr(os_scit, ime, f)


class Sistem:
    """Lazni nmcli/resolvectl: odgovori po zacetku ukaza, vsak klic se zapise."""

    def __init__(self, odgovori):
        self.odgovori = odgovori
        self.klici = []

    def __call__(self, ukaz, cas=8.0):
        self.klici.append(list(ukaz))
        for zacetek, izid in self.odgovori:
            if ukaz[:len(zacetek)] == zacetek:
                return izid
        return 0, ""

    def nastavitve(self):
        return [k for k in self.klici if k[0] == "resolvectl" and len(k) > 3 or k[:2] == ["resolvectl", "revert"]]


class VrnitevDns(unittest.TestCase):
    """Ob izklopu Scita ali izhodu iz Safeer OS vmesnik dobi nazaj streznike NetworkManagerja. `resolvectl revert`
    bi pobrisal tudi te - NetworkManager jih znova poslje sele ob naslednji povezavi, racunalnik pa bi bil do takrat
    brez DNS (preverjeno na pravem systemd-resolved: tools/scit_lab)."""

    def test_strezniki_networkmanagerja(self):
        s = Sistem([(["nmcli", "-g", "IP4.DNS,IP6.DNS"], (0, "192.0.2.1 | 192.0.2.2\n2001\\:db8\\:\\:1 | fe80\\:\\:1\n"))])
        with Zamenjave(_zazeni=s):
            self.assertEqual(os_scit.upstream_strezniki("eth9"), ["192.0.2.1", "192.0.2.2", "2001:db8::1", "fe80::1"])
        s = Sistem([(["nmcli"], (0, "127.0.0.1 | 192.0.2.1 | 192.0.2.1 | ni-naslov | 0.0.0.0\n\\:\\:1\n"))])
        with Zamenjave(_zazeni=s):
            self.assertEqual(os_scit.upstream_strezniki("eth9"), ["192.0.2.1"], "brez povratne zanke, dvojnikov in smeti")
        with Zamenjave(_zazeni=Sistem([(["nmcli"], (10, ""))])):
            self.assertEqual(os_scit.upstream_strezniki("eth9"), [])

    def test_samo_povratna_zanka_vzame_dhcp(self):
        """17. 11. 2026: profil NetworkManagerja je imel ipv4.dns 127.0.0.1 (ignore-auto-dns): Scit je po zagonu ostal
        brez strezniko naprej, odgovor SERVFAIL, ves racunalnik brez DNS. Vzame se DNS iz ponudbe DHCP."""
        s = Sistem([(["nmcli", "-g", "IP4.DNS,IP6.DNS"], (0, "127.0.0.1\n")),
                    (["nmcli", "-g", "DHCP4.OPTION"], (0, "ip_address = 192.0.2.78 | domain_name_servers = 192.0.2.1 192.0.2.1 127.0.0.1 | routers = 192.0.2.1\n"))])
        with Zamenjave(_zazeni=s):
            self.assertEqual(os_scit.upstream_strezniki("eth9"), ["192.0.2.1"])
        s = Sistem([(["nmcli", "-g", "IP4.DNS,IP6.DNS"], (0, "127.0.0.1\n")), (["nmcli", "-g", "DHCP4.OPTION"], (0, "routers = 192.0.2.1\n"))])
        with Zamenjave(_zazeni=s):
            self.assertEqual(os_scit.upstream_strezniki("eth9"), [], "brez ponudbe DNS se ne ugiba (router ni DNS)")
        self.assertEqual(os_scit.za_vticnico("fe80::1", "wlan0"), "fe80::1%wlan0")
        self.assertEqual(os_scit.za_vticnico("2001:db8::1", "wlan0"), "2001:db8::1")
        self.assertEqual(os_scit.za_vticnico("192.0.2.1", "wlan0"), "192.0.2.1")
        self.assertEqual(os_scit.za_vticnico("169.254.1.1", "wlan0"), "169.254.1.1")

    def test_povrni(self):
        s = Sistem([(["nmcli", "-g", "IP4.DNS,IP6.DNS"], (0, "192.0.2.1\nfe80\\:\\:1\n")),
                    (["resolvectl", "domain", "eth9"], (0, "Link 2 (eth9): lan\n"))])
        with Zamenjave(_zazeni=s):
            self.assertTrue(os_scit.povrni("eth9"))
        self.assertEqual(s.nastavitve(), [["resolvectl", "dns", "eth9", "192.0.2.1", "fe80::1"]])
        # NetworkManager za vmesnik nima streznikov: takrat (in samo takrat) revert.
        s = Sistem([(["nmcli"], (0, "\n\n"))])
        with Zamenjave(_zazeni=s):
            self.assertTrue(os_scit.povrni("eth9"))
        self.assertEqual(s.nastavitve(), [["resolvectl", "revert", "eth9"]])

    def test_iskalne_domene(self):
        def sistem(trenutne, nm):
            return Sistem([(["resolvectl", "domain", "eth9", ], (0, "Link 2 (eth9): %s\n" % trenutne)),
                           (["nmcli", "-g", "IP4.DOMAIN,IP6.DOMAIN,IP4.SEARCHES,IP6.SEARCHES"], (0, nm))])
        # Stara razlicica je iskalno domeno zamenjala z »~.«: vrnemo tisto iz NetworkManagerja.
        s = sistem("~.", "lan\n\n\n\n")
        with Zamenjave(_zazeni=s):
            os_scit.uredi_domene("eth9")
        self.assertEqual(s.klici[-1], ["resolvectl", "domain", "eth9", "lan"])
        # Stari izklop (revert) jih je pobrisal.
        s = sistem("", "lan | doma.example\n\n\n\n")
        with Zamenjave(_zazeni=s):
            os_scit.uredi_domene("eth9")
        self.assertEqual(s.klici[-1], ["resolvectl", "domain", "eth9", "lan", "doma.example"])
        # »~.« brez domen v NetworkManagerju: pocistimo.
        s = sistem("~.", "\n\n\n\n")
        with Zamenjave(_zazeni=s):
            os_scit.uredi_domene("eth9")
        self.assertEqual(s.klici[-1], ["resolvectl", "domain", "eth9", ""])
        # Domene so, kot jih je nastavil NetworkManager (ali uporabnik): ne dotikamo se.
        for trenutne, nm in (("lan", "lan\n\n\n\n"), ("podjetje.example ~vpn.example", "lan\n\n\n\n"), ("", "\n\n\n\n")):
            s = sistem(trenutne, nm)
            with Zamenjave(_zazeni=s):
                os_scit.uredi_domene("eth9")
            self.assertFalse(s.nastavitve(), trenutne)
        # Starejsi NetworkManager polja SEARCHES ne pozna.
        s = Sistem([(["nmcli", "-g", "IP4.DOMAIN,IP6.DOMAIN,IP4.SEARCHES,IP6.SEARCHES"], (2, "")),
                    (["nmcli", "-g", "IP4.DOMAIN,IP6.DOMAIN"], (0, "lan\n\n"))])
        with Zamenjave(_zazeni=s):
            self.assertEqual(os_scit.nm_domene("eth9"), ["lan"])

    def test_ostanek(self):
        with Zamenjave(dns_vmesnika=lambda v: "", nekdo_poslusa=lambda vrata: False):
            self.assertTrue(os_scit.je_ostanek("eth9"), "vmesnik brez streznikov (stari revert)")
        with Zamenjave(dns_vmesnika=lambda v: "127.0.0.1:5354 192.0.2.1", nekdo_poslusa=lambda vrata: False):
            self.assertTrue(os_scit.je_ostanek("eth9"), "nas streznik, na katerem nihce ne poslusa (sesutje)")
        # Kdo poslusa, je vedno zamenjano: prava vrata 5354 racunalnika (ali vticnica, ki jo je pustil drug preizkus) bi
        # izid spreminjala - preizkus je padal sam, v polnem teku pa je bil zelen (CI 20. 10. 2026).
        with Zamenjave(dns_vmesnika=lambda v: "127.0.0.1:5354 192.0.2.1", nekdo_poslusa=lambda vrata: True,
                       vrata_nasa=lambda vrata: False, tuj_scit=lambda dns, nasa: True):
            self.assertFalse(os_scit.je_ostanek("eth9"), "tam tece Scit drugega prijavljenega uporabnika")
        with Zamenjave(dns_vmesnika=lambda v: "127.0.0.1:5354 192.0.2.1", nekdo_poslusa=lambda vrata: True,
                       vrata_nasa=lambda vrata: True, tuj_scit=lambda dns, nasa: False):
            self.assertFalse(os_scit.je_ostanek("eth9"), "poslusa nas proces (Scit)")
        with Zamenjave(dns_vmesnika=lambda v: "127.0.0.1:5354 192.0.2.1", nekdo_poslusa=lambda vrata: True,
                       vrata_nasa=lambda vrata: False, tuj_scit=lambda dns, nasa: False):
            self.assertTrue(os_scit.je_ostanek("eth9"), "vrata je po sesutju zasedel tuj proces, ki ni Scit")
        with Zamenjave(dns_vmesnika=lambda v: "192.0.2.1", nekdo_poslusa=lambda vrata: False):
            self.assertFalse(os_scit.je_ostanek("eth9"))
        with Zamenjave(dns_vmesnika=lambda v: "127.0.0.1:9999 192.0.2.1", nekdo_poslusa=lambda vrata: False):
            self.assertFalse(os_scit.je_ostanek("eth9"), "tuja nastavitev, ne nasa")
        self.assertFalse(os_scit.nekdo_poslusa(1))


class Flatpak(unittest.TestCase):
    """V peskovniku Flatpak sistemska orodja tecejo na gostitelju (flatpak-spawn --host). Dvoje je tam drugace:
    pkcheck v peskovniku ne obstaja (in nas PID gostitelju nic ne pomeni), /tmp pa je zaseben."""

    # Dovoljenje in namestitev v Flatpaku in AppImage (pomocnik na gostitelju namesto sirokega pravila za resolve1,
    # pregled 4. 11. 2026): tests/test_scit_pomocnik.py, PomocnikGostitelja.

    def test_nastavitve_gostitelja_beremo_na_gostitelju(self):
        """Zrcalo /etc/resolv.conf v peskovniku zamuja, nsswitch.conf pa je tam od runtime-a: oboje preberemo zunaj."""
        s = Sistem([(["flatpak-spawn", "--host", "cat", "/etc/nsswitch.conf"], (0, "hosts: files dns\n")),
                    (["flatpak-spawn", "--host", "cat", "/etc/resolv.conf"], (0, "search .\n"))])
        with Zamenjave(_zazeni=s, v_flatpaku=lambda: True):
            self.assertFalse(os_scit.programi_uporabljajo_resolved(), "gostitelj ima svoj streznik DNS")
        self.assertEqual(len(s.klici), 2)
        s = Sistem([(["flatpak-spawn", "--host", "cat", "/etc/nsswitch.conf"], (0, "hosts: files dns\n")),
                    (["flatpak-spawn", "--host", "cat", "/etc/resolv.conf"], (0, "nameserver 127.0.0.53\nsearch lan\n"))])
        with Zamenjave(_zazeni=s, v_flatpaku=lambda: True):
            self.assertTrue(os_scit.programi_uporabljajo_resolved())
        with Zamenjave(_zazeni=Sistem([(["flatpak-spawn"], (1, ""))]), v_flatpaku=lambda: True):
            self.assertFalse(os_scit.programi_uporabljajo_resolved(), "ce gostitelja ne moremo vprasati, se DNS ne dotikamo")


class LastniDns(unittest.TestCase):
    """Racunalnik, kjer programi ne sprasujejo systemd-resolved (Pi-hole, AdGuard Home ...): Scit tam ne more
    filtrirati; z nastavitvijo v resolved bi celo zaobsel uporabnikov filter. Zato se DNS ne dotakne in to pove."""

    def test_kdo_razresuje(self):
        with tempfile.TemporaryDirectory() as m:
            r, n = os.path.join(m, "resolv.conf"), os.path.join(m, "nsswitch.conf")

            def primer(resolv, nsswitch="hosts: files mdns4_minimal [NOTFOUND=return] dns myhostname mymachines\n"):
                with open(r, "w", encoding="utf-8") as f:
                    f.write(resolv)
                with open(n, "w", encoding="utf-8") as f:
                    f.write(nsswitch)
                return os_scit.programi_uporabljajo_resolved(r, n)
            self.assertTrue(primer("# stub\nnameserver 127.0.0.53\noptions edns0 trust-ad\nsearch lan\n"))
            self.assertTrue(primer("nameserver 127.0.0.54\n"))
            self.assertFalse(primer("search .\n"), "brez streznika glibc vprasa 127.0.0.1 (lasten streznik DNS)")
            self.assertFalse(primer("nameserver 192.0.2.1\n"))
            self.assertFalse(primer("nameserver 127.0.0.53\nnameserver 192.0.2.1\n"))
            self.assertFalse(primer("nameserver 127.0.0.1\n"))
            self.assertFalse(primer("# nameserver 127.0.0.53\n"))
            self.assertTrue(primer("nameserver 192.0.2.1\n", "hosts: mymachines resolve [!UNAVAIL=return] files myhostname dns\n"))
            self.assertFalse(primer("nameserver 192.0.2.1\n", "hosts: files dns # resolve\n"))
            self.assertFalse(os_scit.programi_uporabljajo_resolved(os.path.join(m, "ni"), os.path.join(m, "ni")))

    def test_ne_dotakne_se_dns(self):
        klici = []
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                razlog_nemoznosti=lambda: "lastni_dns", pravilo_namesceno=lambda: True,
                namesti_pravilo=lambda: klici.append("pravilo") or True,
                vmesniki_povezani=lambda: klici.append("vmesniki") or ["eth9"],
                usmeri=lambda *a: klici.append("usmeri") or "", povrni=lambda v: klici.append("povrni") or True):
            shramba = IzjemeInPremor.Shramba({"scit": True})
            sc = os_scit.Scit(shramba, mapa=m)
            st = sc.stanje()
            self.assertEqual((st["mozno"], st["razlog"], st["tece"]), (False, "lastni_dns", False))
            sc._zagon()                                   # ob zagonu Safeer OS z vklopljenim Scitom v nastavitvah
            self.assertIsNone(sc.razresevalnik)
            st = sc.nastavi(True)
            self.assertEqual(st["napaka"], "lastni_dns")
            self.assertIsNone(sc.razresevalnik)
            sc2 = os_scit.Scit(IzjemeInPremor.Shramba(), mapa=m)
            self.assertEqual(sc2.nastavi(True)["napaka"], "lastni_dns")
            self.assertFalse(sc2.vklopljen)
            sc2._zagon()                                  # izklopljen: tudi ostankov ne pospravlja
        self.assertEqual(klici, [], "nobenega klica, ki bi spremenil ali sploh pregledoval DNS")

    def test_napaka_izgine_ko_je_spet_mozno(self):
        with tempfile.TemporaryDirectory() as m:
            sc = os_scit.Scit(IzjemeInPremor.Shramba(), mapa=m)
            sc.napaka = "lastni_dns"
            # Brez klica polkit na racunalniku, kjer preizkus tece (staro siroko pravilo preizkusa tests/test_scit_pomocnik.py).
            with Zamenjave(razlog_nemoznosti=lambda: "lastni_dns", pravilo_namesceno=lambda: False,
                           dovoljenje_za_posodobitev=lambda: ""):
                self.assertEqual(sc.stanje()["napaka"], "lastni_dns")
            with Zamenjave(razlog_nemoznosti=lambda: "", pravilo_namesceno=lambda: False,
                           dovoljenje_za_posodobitev=lambda: ""):
                self.assertEqual(sc.stanje()["napaka"], "")


class UporabiTest(unittest.TestCase):
    """Zivljenje Scita brez sistema: kdaj nastavi, kdaj vrne, kdaj ne sme nicesar."""

    class Razresevalnik:
        vrata = 5354
        blokiranih = poizvedb = 0
        zadnje: list = []

        def ustavi(self):
            self.vrata = 0

    def _scit(self, m, **shramba):
        sc = os_scit.Scit(IzjemeInPremor.Shramba(shramba), mapa=m)
        sc.razresevalnik = self.Razresevalnik()
        return sc

    def test_nastavi_in_strazi(self):
        dns = {"eth9": "192.0.2.1"}
        trenutni = {"eth9": "192.0.2.1"}
        klici = []

        def usmeri(v, vrata, rezerva):
            # Kam posredujemo, mora biti znano, preden resolved poslje prvo poizvedbo.
            self.assertEqual(sc.strezniki, ["192.0.2.1", "fe80::1%eth9"])
            klici.append(("usmeri", v, vrata, tuple(rezerva)))
            dns[v] = "127.0.0.1:%d %s" % (vrata, " ".join(rezerva))
            trenutni[v] = ""
            return ""
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                vmesniki_povezani=lambda: ["eth9"], upstream_strezniki=lambda v: ["192.0.2.1", "fe80::1"],
                dns_vmesnika=lambda v: dns[v], trenutni_streznik=lambda v: trenutni[v], usmeri=usmeri,
                pravilo_namesceno=lambda: True, uredi_domene=lambda v: klici.append(("domene", v)),
                izprazni_predpomnilnik=lambda: klici.append(("predpomnilnik",))):
            sc = self._scit(m, scit=True)
            sc._uporabi()
            self.assertEqual(klici, [("usmeri", "eth9", 5354, ("192.0.2.1", "fe80::1")), ("domene", "eth9"), ("predpomnilnik",)])
            self.assertEqual((sc.vmesniki, sc.napaka), (["eth9"], ""))
            # Vse je na mestu: naslednji pregled nicesar ne nastavlja.
            del klici[:]
            trenutni["eth9"] = "127.0.0.1:5354"
            sc._uporabi()
            self.assertEqual(klici, [])
            # resolved je presel na rezervo (nas razresevalnik mu ni odgovoril pravocasno): nastavimo znova.
            trenutni["eth9"] = "192.0.2.1"
            sc._uporabi()
            self.assertEqual([k[0] for k in klici], ["usmeri", "predpomnilnik"])
            # NetworkManager je po novi povezavi poslal svoje streznike.
            del klici[:]
            dns["eth9"] = "192.0.2.1"
            sc._uporabi()
            self.assertEqual([k[0] for k in klici], ["usmeri", "predpomnilnik"])

    def test_brez_dovoljenja_ni_okna_za_geslo(self):
        """resolvectl bi brez pravila polkit odprl okno za geslo (iz straze vsakih 20 s): brez dovoljenja ga ne klicemo."""
        klici = []
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                vmesniki_povezani=lambda: ["eth9"], upstream_strezniki=lambda v: ["192.0.2.1"],
                dns_vmesnika=lambda v: "192.0.2.1", trenutni_streznik=lambda v: "192.0.2.1",
                usmeri=lambda *a: klici.append("usmeri") or "", povrni=lambda v: klici.append("povrni") or True,
                pravilo_namesceno=lambda: False, uredi_domene=lambda v: None, izprazni_predpomnilnik=lambda: None):
            sc = self._scit(m, scit=True)
            sc._uporabi()
            self.assertEqual((sc.vmesniki, sc.napaka), ([], "pravilo"))
            sc.vmesniki = ["eth9"]
            sc._ustavi()                                   # tudi ob izhodu brez okna za geslo
        self.assertEqual(klici, [])

    def test_dva_uporabnika_ne_tekmujeta(self):
        """Vmesnik, ki ga ze varuje delujoc Scit drugega prijavljenega uporabnika (druga vrata), pustimo pri miru -
        sicer bi strazi obeh nastavitev izmenicno prepisovali."""
        klici = []
        dns = {"eth9": "127.0.0.1:5355 192.0.2.1"}
        poslusa = {5355: True}
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                vmesniki_povezani=lambda: ["eth9"], upstream_strezniki=lambda v: ["192.0.2.1"],
                dns_vmesnika=lambda v: dns[v], trenutni_streznik=lambda v: "127.0.0.1:5355",
                nekdo_poslusa=lambda vrata: poslusa.get(vrata, False),
                lastniki_vrat=lambda vrata: {os.getuid() + 1001}, _odgovori_kanarcku=lambda vrata, cas: True,
                usmeri=lambda *a: klici.append("usmeri") or "", pravilo_namesceno=lambda: True,
                uredi_domene=lambda v: None, izprazni_predpomnilnik=lambda: None):
            sc = self._scit(m, scit=True)
            sc._uporabi()
            self.assertEqual((klici, sc.vmesniki, sc.napaka), ([], [], ""))
            # Njegov Safeer OS se je koncal brez pospravljanja (nihce vec ne poslusa): vmesnik prevzamemo.
            poslusa[5355] = False
            sc._uporabi()
            self.assertEqual((klici, sc.vmesniki), (["usmeri"], ["eth9"]))
        self.assertFalse(os_scit.tuj_scit("127.0.0.1:5354 192.0.2.1", 5354), "to smo mi")
        self.assertFalse(os_scit.tuj_scit("192.0.2.1", 5354))
        self.assertFalse(os_scit.tuj_scit("", 5354))

    def test_brez_rezerve_ni_uspeh(self):
        """Pregled 4. 11. 2026: drugi resolvectl (Scit + strezniki usmerjevalnika) je padel, Scit pa je vrnil uspeh -
        rezerva se je tiho izgubila (Docker in padec Safeer OS brez DNS). Zdaj: napaka brez_rezerve v stanju (vmesnik
        jo pokaze), Scit filtrira naprej, straza poskusi znova; ko rezerva uspe, napaka izgine."""
        izidi = [os_scit.BREZ_REZERVE, os_scit.BREZ_REZERVE, ""]
        klici = []

        def usmeri(*a):
            klici.append(a[0])
            return izidi.pop(0)
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                vmesniki_povezani=lambda: ["eth9"], upstream_strezniki=lambda v: ["192.168.1.1"],
                dns_vmesnika=lambda v: "127.0.0.1:5354", trenutni_streznik=lambda v: "127.0.0.1:5354", usmeri=usmeri,
                pravilo_namesceno=lambda: True, uredi_domene=lambda v: None, izprazni_predpomnilnik=lambda: None,
                razlog_nemoznosti=lambda: ""):
            sc = self._scit(m)
            sc.vmesniki = []
            # Prvi vklop: dns se ni nas
            with Zamenjave(dns_vmesnika=lambda v: "192.168.1.1"):
                sc._uporabi()
            self.assertEqual((sc.vmesniki, sc.napaka, sorted(sc.brez_rezerve)), (["eth9"], "brez_rezerve", ["eth9"]))
            self.assertEqual(sc.stanje()["napaka"], "brez_rezerve")
            self.assertEqual(sc.stanje()["brezRezerve"], ["eth9"])
            sc._uporabi()                         # straza: nas je ze prvi, a rezerve ni - poskusi znova
            self.assertEqual(sc.napaka, "brez_rezerve")
            sc._uporabi()                         # tokrat uspe
            self.assertEqual((sc.napaka, sc.brez_rezerve, klici), ("", set(), ["eth9"] * 3))
            sc._uporabi()                         # vse v redu: nic vec ne klice
            self.assertEqual(len(klici), 3)

    def test_brez_omrezja_in_pozneje_povezan(self):
        povezani = []
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                vmesniki_povezani=lambda: list(povezani), upstream_strezniki=lambda v: ["192.0.2.1"],
                dns_vmesnika=lambda v: "192.0.2.1", trenutni_streznik=lambda v: "", usmeri=lambda *a: "",
                pravilo_namesceno=lambda: True, uredi_domene=lambda v: None, izprazni_predpomnilnik=lambda: None):
            sc = self._scit(m)
            sc._uporabi()
            # Brez krajevnega DNS ni tujega nadomestka (lastnik: SERVFAIL takoj, nikoli tuj razresevalnik).
            self.assertEqual((sc.vmesniki, sc.napaka, sc.strezniki), ([], "ni_omrezja", []))
            povezani.append("wlan0")
            sc._uporabi()
            self.assertEqual((sc.vmesniki, sc.napaka, sc.strezniki), (["wlan0"], "", ["192.0.2.1"]))
            del povezani[:]
            sc._uporabi()
            self.assertEqual((sc.vmesniki, sc.napaka), ([], "ni_omrezja"))

    def test_izklop_vrne_streznike(self):
        klici = []
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                razlog_nemoznosti=lambda: "", pravilo_namesceno=lambda: True, povrni=lambda v: klici.append(v) or True):
            sc = self._scit(m, scit=True)
            sc.vmesniki = ["eth9", "wlan0"]
            st = sc.nastavi(False)
            self.assertEqual(klici, ["eth9", "wlan0"])
            self.assertEqual((st["vklop"], st["tece"], st["vmesniki"]), (False, False, []))
            # Izhod iz Safeer OS (koncaj) po izklopu nicesar vec ne spreminja.
            sc.koncaj()
            self.assertEqual(klici, ["eth9", "wlan0"])

    def test_ostanki_ob_zagonu(self):
        """Scit je izklopljen, vmesnik pa je ostal brez DNS za starejso razlicico: ob zagonu ga popravimo - samo kjer
        smemo brez gesla in samo vmesnike, ki so res nas ostanek."""
        klici = []
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                razlog_nemoznosti=lambda: "", vmesniki_povezani=lambda: ["eth9", "wlan0", "eth1"],
                upstream_strezniki=lambda v: [] if v == "eth1" else ["192.0.2.1"],
                je_ostanek=lambda v: v != "wlan0", pravilo_namesceno=lambda: True,
                povrni=lambda v: klici.append(v) or True):
            sc = os_scit.Scit(IzjemeInPremor.Shramba(), mapa=m)
            sc._zagon()
            self.assertEqual(klici, ["eth9"])
            self.assertIsNone(sc.razresevalnik, "izklopljen Scit se ob zagonu ne zazene")
        del klici[:]
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                razlog_nemoznosti=lambda: "", vmesniki_povezani=lambda: ["eth9"], upstream_strezniki=lambda v: ["192.0.2.1"],
                je_ostanek=lambda v: True, pravilo_namesceno=lambda: False, povrni=lambda v: klici.append(v) or True):
            os_scit.Scit(IzjemeInPremor.Shramba(), mapa=m)._zagon()
        self.assertEqual(klici, [], "brez pravila polkit (Scit ni bil nikoli vklopljen) nicesar")

    def test_posredovanje_ipv6(self):
        try:
            gor = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            gor.bind(("::1", 0))
        except OSError:
            self.skipTest("ni IPv6 na povratni zanki")
        vrata = gor.getsockname()[1]

        def tek():
            try:
                p, od = gor.recvfrom(4096)
                gor.sendto(p[:2] + b"\x81\x80" + p[4:], od)
            except OSError:
                pass
        threading.Thread(target=tek, daemon=True).start()
        r = os_scit.Razresevalnik(lambda ime: None, lambda: ["::1"])
        izvirni = socket.getaddrinfo
        socket.getaddrinfo = lambda g, v, *a, **k: izvirni(g, vrata if v == 53 else v, *a, **k)
        try:
            o = r._posreduj(vprasanje("safeer.si", id_=0x77), False)
        finally:
            socket.getaddrinfo = izvirni
            gor.close()
        self.assertEqual(o[:4], b"\x00\x77\x81\x80")

    def test_straza_in_delovna(self):
        self.assertEqual(len(os_scit.znak_dns()), 2)
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "safeer_os.py"), encoding="utf-8") as f:
            vir = f.read()
        # Scit se zazene tudi, kadar Safeer OS tece kot delovna povrsina; prej se tam ni nikoli. Delovna povrsina ob
        # zagonu (--delovna) in pozneje v procesu, ki ze tece (_vklopi_delovno), imata skupen _ob_namizju (15. 10. 2026);
        # drugi mesti sta glavno okno in _ustvari_qml_okno (aplikacija v oknu, namizje QML, 14. 10. 2026).
        self.assertEqual(vir.count("self.scit.zacni_ce_vklopljen()"), 3)
        delovna = vir[vir.index("if self.delovna and not _ima_delovno(self):"):]
        self.assertLess(delovna.index("self._ob_namizju()"), delovna.index("return"))
        ob_namizju = vir[vir.index("    def _ob_namizju(self)"):]
        self.assertLess(ob_namizju.index("self.scit.zacni_ce_vklopljen()"), ob_namizju.index("\n    def "))
        with open(os.path.join(koren, "assets", "os", "os.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn('s.razlog === "lastni_dns" ? "scitNapaka_lastni_dns" : s.razlog === "pihole_ostanek" ? "scitNapaka_pihole_ostanek" : "scitNiMozno"', js)
        self.assertIn('.scit-zadnje:hover, .scit-zadnje button:focus', js)
        with open(os.path.join(koren, "assets", "os", "besedila.js"), encoding="utf-8") as f:
            self.assertEqual(f.read().count('scitNapaka_lastni_dns: "'), 6)


class VrataInZanke(unittest.TestCase):
    """Pregled 18. 10. 2026: vrata 5354-5357 lahko prvi zasede katerikoli lokalni proces; streznik naprej ne sme
    poizvedbe vrniti Scitu (zanka DoH); tiha izguba sifriranja mora biti vidna."""

    @staticmethod
    def _proc(mapa, udp="", udp6="", tcp="", tcp6=""):
        glava = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
        for ime, vsebina in (("udp", udp), ("udp6", udp6), ("tcp", tcp), ("tcp6", tcp6)):
            with open(os.path.join(mapa, ime), "w", encoding="ascii") as f:
                f.write(glava + vsebina)

    @staticmethod
    def _v4(naslov: str, vrata: int) -> str:
        surovo = socket.inet_aton(naslov)
        if sys.byteorder == "little":
            surovo = surovo[::-1]
        return "%s:%04X" % (surovo.hex().upper(), vrata)

    @staticmethod
    def _v6(naslov: str, vrata: int) -> str:
        surovo = socket.inet_pton(socket.AF_INET6, naslov)
        if sys.byteorder == "little":
            surovo = b"".join(surovo[i:i + 4][::-1] for i in range(0, 16, 4))
        return "%s:%04X" % (surovo.hex().upper(), vrata)

    def _vrstica(self, lokalno, st="07", uid=1000):
        return "   0: %s 00000000:0000 %s 00000000:00000000 00:00000000 00000000 %5d        0 123 2\n" % (lokalno, st, uid)

    def test_lastniki_vrat_iz_proc(self):
        with tempfile.TemporaryDirectory() as m:
            self._proc(m, udp=self._vrstica(self._v4("127.0.0.1", 5354), uid=1001)
                       + self._vrstica(self._v4("192.0.2.5", 5354), uid=7)          # drug naslov: ne sprejme
                       + self._vrstica(self._v4("0.0.0.0", 5355), uid=0),
                       udp6=self._vrstica(self._v6("::", 5356), uid=65534),
                       tcp=self._vrstica(self._v4("127.0.0.1", 5354), st="0A", uid=1001)
                       + self._vrstica(self._v4("127.0.0.1", 5357), st="01", uid=5),  # povezava, ne poslusa
                       tcp6=self._vrstica(self._v6("::ffff:127.0.0.1", 5357), st="0A", uid=1002))
            self.assertEqual(os_scit.lastniki_vrat(5354, m), {1001})
            self.assertEqual(os_scit.lastniki_vrat(5355, m), {0})
            self.assertEqual(os_scit.lastniki_vrat(5356, m), {65534})
            self.assertEqual(os_scit.lastniki_vrat(5357, m), {1002})
            self.assertEqual(os_scit.lastniki_vrat(5399, m), set())
        self.assertIsNone(os_scit.lastniki_vrat(5354, "/ni/take/mape"))

    def test_lastniki_pravih_vticnic(self):
        """Na tem sistemu: vticnica, ki jo odpremo sami, ima nas uid."""
        if not os.path.isdir("/proc/net"):
            self.skipTest("ni /proc/net")
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", 0))
        self.addCleanup(s.close)
        self.assertEqual(os_scit.lastniki_vrat(s.getsockname()[1]), {os.getuid()})

    def test_brskalnik_ne_uporabi_tujih_vrat(self):
        """Proces drugega uporabnika (ali sistemski) je prvi zasedel vrata in odgovarja kot Scit: brskalnik mu imen ne
        posilja. Nas razresevalnik v tem procesu pa velja brez sprasevanja."""
        lazni = os_scit.Razresevalnik(lambda ime: None, lambda: [])
        vrata = lazni.zazeni()
        if not vrata:
            self.skipTest("vrata 5354-5357 so zasedena")
        self.addCleanup(lazni.ustavi)
        os_scit._AKTIVNA_VRATA.discard(vrata)               # kot da tece v drugem procesu
        with Zamenjave(lastniki_vrat=lambda v: {os.getuid() + 1234} if v == vrata else set()):
            self.assertEqual(os_scit.tekoci_scit(), 0)
        with Zamenjave(lastniki_vrat=lambda v: {os.getuid()} if v == vrata else set()):
            self.assertEqual(os_scit.tekoci_scit(), vrata)     # nas drug proces (Safeer OS ob Safeer Browserju)
        with Zamenjave(lastniki_vrat=lambda v: None):
            self.assertEqual(os_scit.tekoci_scit(), 0)         # lastnika ni mogoce preveriti: ne
        os_scit._AKTIVNA_VRATA.add(vrata)
        with Zamenjave(lastniki_vrat=lambda v: None):
            self.assertEqual(os_scit.tekoci_scit(), vrata)     # razresevalnik v tem procesu

    def test_zasedena_vrata_v_resolved_prevzamemo(self):
        """systemd-resolved kaze na nasa vrata, tam pa poslusa proces, ki ni Scit cloveka (root, nobody) ali ne odgovori
        kot Scit: tak vmesnik ni »tuj Scit« - prevzamemo ga (vklopljen Scit) oziroma vrnemo (ostanek)."""
        sistemski = 7 if os.getuid() != 7 else 8                  # sistemski uporabnik (ne mi)
        for lastniki, kanarcek in (({sistemski}, True), ({UID_NOBODY}, True), ({os.getuid() + 1500}, False),
                                   ({os.getuid() + 1500, os.getuid() + 1501}, True)):
            with self.subTest(lastniki=lastniki), Zamenjave(
                    nekdo_poslusa=lambda v: True, lastniki_vrat=lambda v, l=lastniki: set(l),
                    _odgovori_kanarcku=lambda v, c, k=kanarcek: k, dns_vmesnika=lambda v: "127.0.0.1:5355 192.0.2.1"):
                self.assertFalse(os_scit.tuj_scit("127.0.0.1:5355 192.0.2.1", 5354))
                self.assertTrue(os_scit.je_ostanek("eth9"))
        with Zamenjave(nekdo_poslusa=lambda v: True, lastniki_vrat=lambda v: {os.getuid() + 1500},
                       _odgovori_kanarcku=lambda v, c: True, dns_vmesnika=lambda v: "127.0.0.1:5355 192.0.2.1"):
            self.assertTrue(os_scit.tuj_scit("127.0.0.1:5355 192.0.2.1", 5354))
            self.assertFalse(os_scit.je_ostanek("eth9"))

    def test_zanka_naprej(self):
        for v in ("127.0.0.53", "127.0.0.54", "127.0.0.1:5354", "127.0.0.1:5357", "[::1]:5355", "[::ffff:127.0.0.53]:53"):
            self.assertTrue(os_scit.je_zanka_naprej(v), v)
        for v in ("127.0.0.1:5053", "192.0.2.75", "9.9.9.9:53", "[::1]:5053", "ni-naslov"):
            self.assertFalse(os_scit.je_zanka_naprej(v), v)

        class Posrednik:
            actual_port = 40123
        doh = types.ModuleType("core.doh_proxy")
        doh._global_proxy = Posrednik()
        with mock.patch.dict(sys.modules, {"core.doh_proxy": doh}):
            self.assertTrue(os_scit.je_zanka_naprej("127.0.0.1:40123"))     # lokalni posrednik DoH Spleta
            self.assertFalse(os_scit.je_zanka_naprej("127.0.0.1:40124"))

    def test_ime_streznika_doh_gre_mimo_doh(self):
        """Ime streznika DoH naprej (dns.quad9.net) razresi sistemski DNS, ta pa je Scit: ne sme nazaj v DoH (zanka), gre
        naravnost usmerjevalniku - in to ni odpoved DoH (ne steje, ne ustavi DoH za 30 s)."""
        naprej, usmerjevalnik = [], []
        r = os_scit.Razresevalnik(lambda ime: None, lambda: ["192.0.2.1"],
                                  lambda p: naprej.append(os_scit.ime_poizvedbe(p)) or p[:2] + b"\x81\x80" + p[4:],
                                  zagonsko=lambda ime: ime == "dns.quad9.net")
        r._vprasaj_usmerjevalnik = lambda p, tcp: usmerjevalnik.append(os_scit.ime_poizvedbe(p)) or p[:2] + b"\x81\x80" + p[4:]
        self.assertIsNotNone(r._odgovori(vprasanje("dns.quad9.net"), False))
        self.assertIsNotNone(r._odgovori(vprasanje("example.com"), False))
        self.assertEqual((naprej, usmerjevalnik, r.rezerv, r.nesifrirano()), (["example.com"], ["dns.quad9.net"], 0, False))

    def test_zagonska_imena_po_izbiri(self):
        class Shramba(dict):
            def set(self, k, v):
                self[k] = v
        with tempfile.TemporaryDirectory() as m:
            sc = os_scit.Scit(Shramba(scit_naprej="quad9"), mapa=m)
            self.assertTrue(sc._zagonsko("dns.quad9.net"))
            self.assertFalse(sc._zagonsko("example.com"))
            sc.shramba["scit_naprej"] = "cloudflare"            # naslov IP: imena ni
            self.assertFalse(sc._zagonsko("1.1.1.1"))
            self.assertFalse(sc._zagonsko("dns.quad9.net"))
            sc.shramba.update(scit_naprej="custom", scit_naprej_po_meri="https://dns.primer.si/dns-query")
            self.assertTrue(sc._zagonsko("dns.primer.si"))

    def test_nesifrirano_je_vidno_usmerjevalnik_pa_ni_odpoved(self):
        klici = []
        r = os_scit.Razresevalnik(lambda ime: None, lambda: [], lambda p: klici.append(1) and None)
        self.assertFalse(r.nesifrirano())
        r._posreduj(vprasanje("example.com"), False)
        self.assertTrue(r.nesifrirano())
        r.nesifrirano_cas -= r.NESIFRIRANO_S + 1                 # DoH spet dela: oznaka izgine sama
        self.assertFalse(r.nesifrirano())
        izbran = os_scit.Razresevalnik(lambda ime: None, lambda: [], lambda p: klici.append(2))
        izbran.sifrirano_naprej = lambda: False                  # uporabnik je izbral »DNS usmerjevalnika«
        izbran._posreduj(vprasanje("example.com"), False)
        self.assertEqual((klici, izbran.rezerv, izbran.nesifrirano()), ([1], 0, False))

    def test_stanje_pokaze_nesifrirano(self):
        class Shramba(dict):
            def set(self, k, v):
                self[k] = v
        with tempfile.TemporaryDirectory() as m, Zamenjave(razlog_nemoznosti=lambda: "", pravilo_namesceno=lambda: True):
            sc = os_scit.Scit(Shramba(), mapa=m)
            r = os_scit.Razresevalnik(lambda ime: None, lambda: [], lambda p: None)
            r.vrata = 5354
            sc.razresevalnik = r
            self.assertFalse(sc.stanje()["nesifrirano"])
            r.nesifrirano_cas = time.time()
            self.assertTrue(sc.stanje()["nesifrirano"])
            sc.shramba["scit_naprej"] = "router"
            r.sifrirano_naprej = lambda: sc.naprej()[0] != "router"
            self.assertFalse(sc.stanje()["nesifrirano"])

    def test_telemetrija_storitev_tudi_v_dns(self):
        """Gostitelji samo za telemetrijo (seznam pravil Scita) so blokirani za ves racunalnik kot »oglasi in sledenje«
        (premor jih spusti); sledilci tretjih in storitve same ne."""
        s = os_scit.Seznami.__new__(os_scit.Seznami)
        s.nabor, s.storitev, s._kljuc = os_scit.Nabor(), None, threading.Lock()
        self.assertEqual(s.kategorija("dit.whatsapp.net"), "oglasi")
        self.assertEqual(s.kategorija("spade.twitch.tv"), "oglasi")
        for ime in ("web.whatsapp.com", "gql.twitch.tv", "www.google-analytics.com"):
            self.assertIsNone(s.kategorija(ime), ime)


UID_NOBODY = 65534



def _ime_dns(s):
    return b"".join(bytes([len(l)]) + l.encode() for l in s.split(".")) + b"\0"


class CnameTest(unittest.TestCase):
    """Lastnik 9. 11. 2026: Scit kot Pi-hole preveri verigo CNAME (enaki primeri kot TV ScitTest.cnameTest)."""

    def _odgovor(self):
        d = bytearray(b"\x12\x34\x81\x80\x00\x01\x00\x02\x00\x00\x00\x00")
        d += _ime_dns("stat.stran.si") + b"\x00\x01\x00\x01"
        cilj = _ime_dns("trk.sledilec.net")
        d += b"\xc0\x0c\x00\x05\x00\x01\x00\x00\x00\x3c\x00" + bytes([len(cilj)])
        zacetek = len(d)
        d += cilj
        d += b"\xc0" + bytes([zacetek]) + b"\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04\x01\x02\x03\x04"
        return bytes(d)

    def test_cilji(self):
        odg = self._odgovor()
        self.assertEqual(os_scit.cname_cilji(odg), ["trk.sledilec.net"])
        d = bytearray(b"\x00\x01\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00") + _ime_dns("www.stran.si") + b"\x00\x01\x00\x01"
        d += b"\xc0\x0c\x00\x05\x00\x01\x00\x00\x00\x3c\x00\x02\xc0\x10"
        self.assertEqual(os_scit.cname_cilji(bytes(d)), ["stran.si"])
        brez = bytearray(odg); brez[7] = 0
        self.assertEqual(os_scit.cname_cilji(bytes(brez)), [])
        self.assertIsNone(os_scit._ime_odgovora(b"\xc0\x00", 0))
        self.assertIsNone(os_scit._ime_odgovora(b"\xc0\x05\x00\x00\x00\x00", 0))
        for n in range(len(odg)):
            os_scit.cname_cilji(odg[:n])
        lazno = bytearray(odg); lazno[6:8] = b"\xff\xff"
        self.assertEqual(os_scit.cname_cilji(bytes(lazno)), ["trk.sledilec.net"])

    def test_razresevalnik_ustavi_prikrit_sledilec(self):
        r = os_scit.Razresevalnik(lambda i: "oglasi" if i.endswith("sledilec.net") else None, lambda: [])
        odg = self._odgovor()
        r._posreduj = lambda paket, tcp: odg
        poizvedba = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + _ime_dns("stat.stran.si") + b"\x00\x01\x00\x01"
        izid = r._odgovori(poizvedba, False)
        self.assertEqual(izid[3] & 0x0F, 3, "NXDOMAIN")
        self.assertEqual(r.blokiranih, 1)
        self.assertEqual(r.zadnje[0]["ime"], "stat.stran.si")
        # Izjema na vprasanem imenu velja tudi za verigo.
        r2 = os_scit.Razresevalnik(lambda i: "oglasi" if i.endswith("sledilec.net") else None, lambda: [],
                                   izjema=lambda i: i == "stat.stran.si")
        r2._posreduj = lambda paket, tcp: odg
        self.assertEqual(r2._odgovori(poizvedba, False), odg)

    def test_groznja_ima_prednost_zasciteni_in_izjema(self):
        """Neodvisni pregled 9. 11. 2026: izjema ali zascita spusti samo oglasni cilj, groznje nikoli."""
        def blokiraj(i):
            return "malware" if i.endswith("zlo.example") else ("oglasi" if i.endswith("sledilec.net") else None)

        def odgovor(ime, cilj):
            d = bytearray(b"\x00\x01\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00") + _ime_dns(ime) + b"\x00\x01\x00\x01"
            c = _ime_dns(cilj)
            return bytes(d + b"\xc0\x0c\x00\x05\x00\x01\x00\x00\x00\x3c\x00" + bytes([len(c)]) + c)

        r = os_scit.Razresevalnik(blokiraj, lambda: [], izjema=lambda i: i == "stat.stran.si")
        self.assertFalse(r._cname_ustavi("stat.stran.si", odgovor("stat.stran.si", "t.sledilec.net")))
        self.assertTrue(r._cname_ustavi("stat.stran.si", odgovor("stat.stran.si", "x.zlo.example")))
        self.assertEqual(r.zadnje[0]["ime"], "x.zlo.example")
        r2 = os_scit.Razresevalnik(blokiraj, lambda: [])
        self.assertFalse(r2._cname_ustavi("objects.github.com", odgovor("objects.github.com", "t.sledilec.net")))
        self.assertTrue(r2._cname_ustavi("objects.github.com", odgovor("objects.github.com", "x.zlo.example")))
        self.assertFalse(r2._cname_ustavi("tiskalnik.local", odgovor("tiskalnik.local", "t.sledilec.net")))

    def test_veliko_vprasanj_je_hitro(self):
        d = bytearray(b"\x00\x01\x81\x80\xff\xff\x00\x00\x00\x00\x00\x00") + _ime_dns("a" * 60 + ".example")
        d += b"\x00\x01\x00\x01" + b"\xc0\x0c\x00\x01\x00\x01" * 10000
        import time as _t
        z = _t.monotonic()
        os_scit.cname_cilji(bytes(d[:65535]))
        self.assertLess(_t.monotonic() - z, 0.05)

    def test_glava_stevenblack_brez_naslova(self):
        self.assertEqual(list(os_scit.razcleni_seznam("0.0.0.0 0.0.0.0\n0.0.0.0 ads.example-oglas.com\n")),
                         ["ads.example-oglas.com"])


    def test_adguard_izjeme(self):
        """Lastnik 9. 11. 2026: AdGuard DNS filter - ||ime^ je vnos, @@||ime^ izpusti ime in nadrejene iz istega seznama."""
        besedilo = ("! Title: AdGuard DNS filter\n||ads.example-oglas.com^\n||sled.net^\n||cdn.sled.net^\n"
                    "||ad-host-*.example.com^\n/^139\\.45/\n@@||ok.cdn.sled.net^|\n||drugi.example^$important\n@@|samo.example^|\n")
        self.assertEqual(os_scit.razcleni_seznam(besedilo, abp=True), ["ads.example-oglas.com"])



class PoMeriTest(unittest.TestCase):
    """Lastnik 9. 11. 2026: filtri po meri (kot AdGuard), enaka pravila kot TV ScitPoMeriPravila."""

    def test_naslov_in_oznaka(self):
        self.assertIsNone(os_scit.napaka_naslova("https://raw.githubusercontent.com/x/y/hosts"))
        self.assertEqual(os_scit.napaka_naslova("http://primer.si/hosts"), "https")
        self.assertEqual(os_scit.napaka_naslova("https://uporabnik:geslo@primer.si/h"), "gostitelj")
        self.assertEqual(os_scit.napaka_naslova("https://primer.si/a b"), "znaki")
        self.assertEqual(os_scit.napaka_naslova("https://lokalno/x"), "gostitelj")
        i = os_scit.id_po_meri("https://primer.si/hosts")
        self.assertTrue(i.startswith("pm-") and len(i) == 15 and i == os_scit.id_po_meri(" https://primer.si/hosts "))
        self.assertEqual(os_scit.ime_po_meri("https://raw.githubusercontent.com/x/y/hosts?a=1"), "raw.githubusercontent.com … hosts")

    def test_dodaj_vklop_odstrani(self):
        url = "https://primer.si/hosts"
        vsebine = {url: b"! Title: test\n||oglas.example^\n0.0.0.0 sled.example\n", "https://primer.si/html": b"<html>x</html>",
                   dict((o, u) for o, u, _k in os_scit.VIRI)["si-cert"]: b"cert.example\n"}

        def prenesi(u, etag, cas=60.0):
            if u in vsebine:
                return 200, vsebine[u], ""
            raise OSError("ni")
        with tempfile.TemporaryDirectory() as m:
            s = os_scit.Seznami(m, prenesi_fn=prenesi, kljuc_fn=lambda: None)
            # Brez niti v ozadju (sicer bi pisala v mapo, ko jo preizkus ze pobrise): osvezitev klice preizkus sam.
            s.osvezi = lambda: True
            s.osvezi_in_zgradi = lambda: None
            self.assertEqual(s.dodaj_po_meri("http://primer.si/hosts"), "naslov")
            self.assertEqual(s.dodaj_po_meri("https://primer.si/html"), "ni_seznam")
            self.assertEqual(s.dodaj_po_meri(url), "dodan")
            self.assertEqual(s.dodaj_po_meri(url), "ze_dodan")
            os_scit.Seznami.osvezi_in_zgradi(s)
            self.assertEqual(s.kategorija("x.oglas.example"), "oglasi")
            self.assertEqual(s.kategorija("sled.example"), "oglasi")
            ident = os_scit.id_po_meri(url)
            self.assertEqual(s.stanje()["poMeri"][0]["id"], ident)
            s.nastavi_po_meri(ident, False)
            os_scit.Seznami.osvezi_in_zgradi(s)
            self.assertIsNone(s.kategorija("oglas.example"))
            s.nastavi_po_meri(ident, None)
            self.assertEqual(os_scit.po_meri(m), [])


if __name__ == "__main__":
    unittest.main()
